#!/usr/bin/env python3
"""Replay incident from ClickHouse and run detector+RCA offline."""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from clickhouse_driver import Client
import asyncpg

# Import detector and RCA components
from apps.detector.detector.anomaly_detector import AnomalyDetector
from apps.detector.detector.incident_grouper import IncidentGrouper
from apps.rca.rca.candidate_generator import CandidateGenerator
from apps.rca.rca.feature_extractor import FeatureExtractor
from apps.rca.rca.ranker import HeuristicRanker


async def replay_incident(
    incident_id: str,
    clickhouse_client: Client,
    postgres_pool: asyncpg.Pool
) -> Dict[str, Any]:
    """Replay an incident and compute metrics."""
    
    # Get incident details
    async with postgres_pool.acquire() as conn:
        incident = await conn.fetchrow(
            "SELECT id, start_ts, end_ts FROM incidents WHERE id = $1",
            incident_id
        )
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")
        
        # Get true cause (from labels)
        true_cause = await conn.fetchrow(
            """
            SELECT suspect_id FROM labels
            WHERE incident_id = $1 AND label = 1
            LIMIT 1
            """,
            incident_id
        )
        
        if not true_cause:
            print(f"Warning: No true cause labeled for incident {incident_id}")
            true_cause_id = None
        else:
            true_cause_id = str(true_cause['suspect_id'])
    
    incident_start = incident['start_ts']
    incident_end = incident['end_ts'] or incident_start + timedelta(hours=1)
    
    print(f"Replaying incident {incident_id}")
    print(f"  Start: {incident_start}")
    print(f"  End: {incident_end}")
    print(f"  True cause: {true_cause_id}")
    
    # Step 1: Replay metrics
    print("\n1. Replaying metrics...")
    metrics_window_start = incident_start - timedelta(hours=24)
    metrics_window_end = incident_end
    
    metrics_query = f"""
        SELECT ts, service, metric, value
        FROM metrics_timeseries
        WHERE ts >= '{metrics_window_start.isoformat()}'
        AND ts <= '{metrics_window_end.isoformat()}'
        ORDER BY service, metric, ts
    """
    metrics_data = clickhouse_client.execute(metrics_query)
    
    # Group by (service, metric)
    time_series = {}
    for ts, service, metric, value in metrics_data:
        key = (service, metric)
        if key not in time_series:
            time_series[key] = {'timestamps': [], 'values': []}
        time_series[key]['timestamps'].append(ts)
        time_series[key]['values'].append(value)
    
    print(f"  Loaded {len(time_series)} time series")
    
    # Step 2: Run detector
    print("\n2. Running anomaly detection...")
    detector = AnomalyDetector(z_threshold=3.0, min_points=10)
    detected_anomalies = []
    
    for (service, metric), data in time_series.items():
        anomalies = detector.detect_anomalies_in_window(
            values=data['values'],
            timestamps=data['timestamps'],
            metric=metric,
            window_minutes=5,
            required_anomalies=3
        )
        for start_ts, end_ts, score in anomalies:
            detected_anomalies.append({
                'service': service,
                'metric': metric,
                'start_ts': start_ts,
                'end_ts': end_ts,
                'score': score
            })
    
    print(f"  Detected {len(detected_anomalies)} anomalies")
    
    # Step 3: Group into incidents
    print("\n3. Grouping incidents...")
    grouper = IncidentGrouper(gap_minutes=10)
    anomaly_dicts = [
        {
            'id': f"anom_{i}",
            'start_ts': a['start_ts'],
            'end_ts': a['end_ts'],
            'service': a['service'],
            'metric': a['metric'],
            'score': a['score']
        }
        for i, a in enumerate(detected_anomalies)
    ]
    incidents = grouper.group_anomalies(anomaly_dicts)
    
    print(f"  Grouped into {len(incidents)} incidents")
    
    # Step 4: Run RCA
    print("\n4. Running RCA...")
    if not incidents:
        print("  No incidents to analyze")
        return {
            'incident_id': incident_id,
            'precision_at_1': 0.0,
            'precision_at_3': 0.0,
            'mrr': 0.0,
            'time_to_detect': None
        }
    
    # Use first incident (should match our incident)
    incident = incidents[0]
    affected_services = list(set(a['service'] for a in detected_anomalies))
    
    candidate_generator = CandidateGenerator(lookback_hours=2, lookforward_hours=0)
    candidates = await candidate_generator.generate_candidates(
        postgres_pool,
        incident['start_ts'],
        incident['end_ts'],
        affected_services
    )
    
    print(f"  Generated {len(candidates)} candidates")
    
    # Extract features
    feature_extractor = FeatureExtractor()
    candidates_with_features = []
    for candidate in candidates:
        features = await feature_extractor.extract_features(
            candidate,
            incident['start_ts'],
            incident['end_ts'],
            affected_services,
            clickhouse_client,
            postgres_pool
        )
        candidate['evidence'] = features
        candidates_with_features.append(candidate)
    
    # Rank
    ranker = HeuristicRanker()
    ranked = ranker.rank(candidates_with_features)
    
    print(f"  Ranked {len(ranked)} suspects")
    
    # Step 5: Compute metrics
    print("\n5. Computing metrics...")
    
    if true_cause_id:
        # Find rank of true cause
        true_cause_rank = None
        for i, suspect in enumerate(ranked):
            if suspect['suspect_key'] == true_cause_id:
                true_cause_rank = i + 1
                break
        
        if true_cause_rank:
            precision_at_1 = 1.0 if true_cause_rank == 1 else 0.0
            precision_at_3 = 1.0 if true_cause_rank <= 3 else 0.0
            mrr = 1.0 / true_cause_rank
        else:
            precision_at_1 = 0.0
            precision_at_3 = 0.0
            mrr = 0.0
            print(f"  Warning: True cause not found in ranked suspects")
    else:
        precision_at_1 = None
        precision_at_3 = None
        mrr = None
        print(f"  Warning: No true cause labeled, skipping ranking metrics")
    
    # Time to detect
    if detected_anomalies:
        first_anomaly_time = min(a['start_ts'] for a in detected_anomalies)
        time_to_detect = (first_anomaly_time - incident_start).total_seconds() / 60
    else:
        time_to_detect = None
    
    results = {
        'incident_id': incident_id,
        'precision_at_1': precision_at_1,
        'precision_at_3': precision_at_3,
        'mrr': mrr,
        'time_to_detect_minutes': time_to_detect,
        'num_anomalies': len(detected_anomalies),
        'num_candidates': len(candidates),
        'num_suspects': len(ranked)
    }
    
    print(f"\nResults:")
    print(f"  Precision@1: {precision_at_1}")
    print(f"  Precision@3: {precision_at_3}")
    print(f"  MRR: {mrr}")
    print(f"  Time to detect: {time_to_detect} minutes")
    
    return results


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python replay_incident.py <incident_id>")
        sys.exit(1)
    
    incident_id = sys.argv[1]
    
    # Connect to services
    clickhouse_client = Client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
        database=os.getenv("CLICKHOUSE_DB", "rca")
    )
    
    postgres_pool = await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "rca"),
        user=os.getenv("POSTGRES_USER", "rca"),
        password=os.getenv("POSTGRES_PASSWORD", "rca_password")
    )
    
    try:
        results = await replay_incident(incident_id, clickhouse_client, postgres_pool)
        print(f"\n{json.dumps(results, indent=2)}")
    finally:
        await postgres_pool.close()
        clickhouse_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())


