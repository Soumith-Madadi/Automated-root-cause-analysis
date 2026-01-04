#!/usr/bin/env python3
"""Generate 24 hours of demo data with realistic patterns and one incident."""
import asyncio
import aiohttp
import random
from datetime import datetime, timedelta, timezone
import json
import uuid
import asyncpg

API_URL = "http://localhost:8000"

# 10 services
SERVICES = [
    "user-service", "auth-service", "payment-service", "order-service",
    "inventory-service", "shipping-service", "notification-service",
    "analytics-service", "search-service", "api-gateway"
]

# 3 metrics per service
METRICS = ["p95_latency_ms", "error_rate", "qps"]

# Define 6 incidents with different services and causes
INCIDENTS = [
    {
        "service": "user-service",
        "commit_sha": "abc123def456",
        "version": "v2.1.0",
        "author": "alice@example.com",
        "diff_summary": "Updated database connection pool timeout settings. Increased retry attempts for DB queries. Modified cache TTL configuration.",
        "links": {
            "pr": "https://github.com/org/repo/pull/123",
            "commit": "https://github.com/org/repo/commit/abc123def456"
        },
        "hours_ago": 12,
        "duration_minutes": 30
    },
    {
        "service": "payment-service",
        "commit_sha": "xyz789ghi012",
        "version": "v1.6.0",
        "author": "bob@example.com",
        "diff_summary": "Changed payment gateway timeout from 5s to 3s. Updated retry logic for failed transactions.",
        "links": {
            "pr": "https://github.com/org/repo/pull/124",
            "commit": "https://github.com/org/repo/commit/xyz789ghi012"
        },
        "hours_ago": 10,
        "duration_minutes": 45
    },
    {
        "service": "order-service",
        "commit_sha": "def456jkl345",
        "version": "v3.0.2",
        "author": "charlie@example.com",
        "diff_summary": "Modified order processing queue configuration. Reduced batch size for order updates.",
        "links": {
            "pr": "https://github.com/org/repo/pull/125",
            "commit": "https://github.com/org/repo/commit/def456jkl345"
        },
        "hours_ago": 8,
        "duration_minutes": 25
    },
    {
        "service": "inventory-service",
        "commit_sha": "mno789pqr678",
        "version": "v2.3.1",
        "author": "diana@example.com",
        "diff_summary": "Updated inventory cache invalidation strategy. Changed cache refresh interval.",
        "links": {
            "pr": "https://github.com/org/repo/pull/126",
            "commit": "https://github.com/org/repo/commit/mno789pqr678"
        },
        "hours_ago": 6,
        "duration_minutes": 40
    },
    {
        "service": "shipping-service",
        "commit_sha": "stu012vwx901",
        "version": "v1.8.3",
        "author": "eve@example.com",
        "diff_summary": "Updated shipping API client configuration. Modified rate limiting settings.",
        "links": {
            "pr": "https://github.com/org/repo/pull/127",
            "commit": "https://github.com/org/repo/commit/stu012vwx901"
        },
        "hours_ago": 4,
        "duration_minutes": 35
    },
    {
        "service": "notification-service",
        "commit_sha": "yza345bcd234",
        "version": "v2.0.5",
        "author": "frank@example.com",
        "diff_summary": "Changed notification queue worker pool size. Updated message batch processing logic.",
        "links": {
            "pr": "https://github.com/org/repo/pull/128",
            "commit": "https://github.com/org/repo/commit/yza345bcd234"
        },
        "hours_ago": 2,
        "duration_minutes": 20
    }
]

# Keep the first incident as the default for backward compatibility
INCIDENT_DEPLOYMENT = INCIDENTS[0]
INCIDENT_START = datetime.now(timezone.utc) - timedelta(hours=INCIDENTS[0]["hours_ago"])
INCIDENT_DURATION = timedelta(minutes=INCIDENTS[0]["duration_minutes"])
INCIDENT_DEPLOY_TIME = INCIDENT_START - timedelta(minutes=5)


def generate_normal_metric_value(service: str, metric: str, base_time: datetime) -> float:
    """Generate a normal metric value with some noise."""
    # Base values vary by service and metric
    if metric == "p95_latency_ms":
        base = 50.0 + hash(service) % 100  # 50-150ms
        # Add time-of-day variation (higher during business hours)
        hour = base_time.hour
        if 9 <= hour <= 17:
            base *= 1.2
    elif metric == "error_rate":
        base = 0.01 + (hash(service) % 10) / 1000  # 0.01-0.1%
    else:  # qps
        base = 100.0 + hash(service) % 500  # 100-600 QPS
    
    # Add random noise
    noise = random.gauss(0, base * 0.1)
    return max(0, base + noise)


def generate_incident_metric_value(service: str, metric: str, time_since_start: timedelta, incident_service: str) -> float:
    """Generate metric value during incident."""
    normal = generate_normal_metric_value(service, metric, datetime.now(timezone.utc))
    
    if service == incident_service:
        if metric == "p95_latency_ms":
            # Latency spikes to 3-5x normal
            spike_factor = 3.0 + (time_since_start.total_seconds() / 1800) * 2.0  # Ramp up
            return normal * spike_factor
        elif metric == "error_rate":
            # Error rate increases to 5-10%
            return 0.05 + (time_since_start.total_seconds() / 1800) * 0.05
        elif metric == "qps":
            # QPS drops slightly due to errors
            return normal * 0.8
    
    return normal


async def seed_metrics():
    """Generate 24 hours of metrics data with incidents."""
    print("Generating metrics data...")
    start_time = datetime.now(timezone.utc) - timedelta(hours=24)
    points = []
    
    # Build incident time windows
    incident_windows = []
    for incident in INCIDENTS:
        incident_start = datetime.now(timezone.utc) - timedelta(hours=incident["hours_ago"])
        incident_end = incident_start + timedelta(minutes=incident["duration_minutes"])
        incident_windows.append({
            "start": incident_start,
            "end": incident_end,
            "service": incident["service"]
        })
    
    # Generate data point every minute for 24 hours
    current_time = start_time
    while current_time < datetime.now(timezone.utc):
        # Check if we're in any incident window
        active_incident = None
        for window in incident_windows:
            if window["start"] <= current_time < window["end"]:
                active_incident = window
                break
        
        for service in SERVICES:
            for metric in METRICS:
                if active_incident and service == active_incident["service"]:
                    time_since_start = current_time - active_incident["start"]
                    value = generate_incident_metric_value(service, metric, time_since_start, active_incident["service"])
                else:
                    value = generate_normal_metric_value(service, metric, current_time)
                
                points.append({
                    "ts": current_time.isoformat(),
                    "service": service,
                    "metric": metric,
                    "value": value,
                    "tags": {"endpoint": "/api/v1/endpoint", "region": "us-east-1"}
                })
        
        current_time += timedelta(minutes=1)
        
        # Batch insert every 100 points
        if len(points) >= 100:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{API_URL}/ingest/metrics",
                    json={"points": points}
                ) as resp:
                    if resp.status not in [200, 201]:
                        print(f"Warning: Failed to insert metrics batch: {resp.status}")
            points = []
    
    # Insert remaining points
    if points:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_URL}/ingest/metrics",
                json={"points": points}
            ) as resp:
                if resp.status not in [200, 201]:
                    print(f"Warning: Failed to insert final metrics batch: {resp.status}")
    
    print(f"[OK] Generated metrics data")


async def seed_logs():
    """Generate log entries, with error spikes during incidents."""
    print("Generating logs data...")
    start_time = datetime.now(timezone.utc) - timedelta(hours=24)
    entries = []
    
    # Build incident time windows
    incident_windows = []
    for incident in INCIDENTS:
        incident_start = datetime.now(timezone.utc) - timedelta(hours=incident["hours_ago"])
        incident_end = incident_start + timedelta(minutes=incident["duration_minutes"])
        incident_windows.append({
            "start": incident_start,
            "end": incident_end,
            "service": incident["service"]
        })
    
    current_time = start_time
    while current_time < datetime.now(timezone.utc):
        # Check if we're in any incident window
        active_incident = None
        for window in incident_windows:
            if window["start"] <= current_time < window["end"]:
                active_incident = window
                break
        
        for service in SERVICES:
            # Normal log rate: 1-5 logs per minute per service
            log_count = random.randint(1, 5)
            
            if active_incident and service == active_incident["service"]:
                # During incident: more error logs
                log_count = random.randint(10, 20)
                error_rate = 0.3  # 30% errors
            else:
                error_rate = 0.01  # 1% errors normally
            
            for _ in range(log_count):
                is_error = random.random() < error_rate
                level = "ERROR" if is_error else random.choice(["INFO", "DEBUG", "WARN"])
                
                if is_error and active_incident and service == active_incident["service"]:
                    event = "DB_TIMEOUT"
                    message = "Database connection timeout after 5s. Retry attempt failed."
                else:
                    event = f"request_{random.randint(1, 100)}"
                    message = f"Processing request {random.randint(1000, 9999)}"
                
                entries.append({
                    "ts": current_time.isoformat(),
                    "service": service,
                    "level": level,
                    "event": event,
                    "message": message,
                    "fields": {"request_id": f"req_{random.randint(10000, 99999)}"},
                    "trace_id": f"trace_{random.randint(100000, 999999)}" if random.random() < 0.3 else None
                })
        
        current_time += timedelta(minutes=1)
        
        # Batch insert every 100 entries
        if len(entries) >= 100:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{API_URL}/ingest/logs",
                    json={"entries": entries}
                ) as resp:
                    if resp.status not in [200, 201]:
                        print(f"Warning: Failed to insert logs batch: {resp.status}")
            entries = []
    
    # Insert remaining entries
    if entries:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_URL}/ingest/logs",
                json={"entries": entries}
            ) as resp:
                if resp.status not in [200, 201]:
                    print(f"Warning: Failed to insert final logs batch: {resp.status}")
    
    print(f"[OK] Generated logs data")


async def seed_deployments():
    """Generate deployments for all incidents plus some non-incident deployments."""
    print("Generating deployments...")
    
    deployments = []
    
    # Add deployments for each incident (5 minutes before incident start)
    for incident in INCIDENTS:
        incident_start = datetime.now(timezone.utc) - timedelta(hours=incident["hours_ago"])
        deploy_time = incident_start - timedelta(minutes=5)
        deployments.append({
            "ts": deploy_time.isoformat(),
            "service": incident["service"],
            "commit_sha": incident["commit_sha"],
            "version": incident["version"],
            "author": incident["author"],
            "diff_summary": incident["diff_summary"],
            "links": incident["links"]
        })
    
    # Add a few non-incident deployments (these won't cause incidents)
    deployments.extend([
        {
            "ts": (datetime.now(timezone.utc) - timedelta(hours=18)).isoformat(),
            "service": "analytics-service",
            "commit_sha": "xyz789abc123",
            "version": "v1.5.2",
            "author": "bob@example.com",
            "diff_summary": "Added new analytics dashboard features",
            "links": {"pr": "https://github.com/org/repo/pull/120"}
        },
        {
            "ts": (datetime.now(timezone.utc) - timedelta(hours=14)).isoformat(),
            "service": "search-service",
            "commit_sha": "def456ghi789",
            "version": "v2.0.1",
            "author": "charlie@example.com",
            "diff_summary": "Performance improvements in search indexing",
            "links": {"pr": "https://github.com/org/repo/pull/125"}
        }
    ])
    
    async with aiohttp.ClientSession() as session:
        for deployment in deployments:
            async with session.post(
                f"{API_URL}/ingest/deployments",
                json=deployment
            ) as resp:
                if resp.status not in [200, 201]:
                    print(f"Warning: Failed to insert deployment: {resp.status}")
                else:
                    print(f"  [OK] Deployed {deployment['service']} at {deployment['ts']}")
    
    print(f"[OK] Generated {len(deployments)} deployments")


async def seed_config_changes():
    """Generate a few config changes."""
    print("Generating config changes...")
    
    config_changes = [
        {
            "ts": (datetime.now(timezone.utc) - timedelta(hours=20)).isoformat(),
            "service": "api-gateway",
            "key": "rate_limit.requests_per_minute",
            "old_value_hash": "hash1",
            "new_value_hash": "hash2",
            "diff_summary": "Increased rate limit from 1000 to 2000 req/min",
            "source": "terraform"
        },
        {
            "ts": (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat(),
            "service": "user-service",
            "key": "cache.ttl_seconds",
            "old_value_hash": "hash3",
            "new_value_hash": "hash4",
            "diff_summary": "Reduced cache TTL from 300s to 60s",
            "source": "config-service"
        }
    ]
    
    async with aiohttp.ClientSession() as session:
        for change in config_changes:
            async with session.post(
                f"{API_URL}/ingest/config_changes",
                json=change
            ) as resp:
                if resp.status not in [200, 201]:
                    print(f"Warning: Failed to insert config change: {resp.status}")
    
    print(f"[OK] Generated {len(config_changes)} config changes")


async def seed_flag_changes():
    """Generate a few feature flag changes."""
    print("Generating feature flag changes...")
    
    flag_changes = [
        {
            "ts": (datetime.now(timezone.utc) - timedelta(hours=15)).isoformat(),
            "flag_name": "new_checkout_flow",
            "service": "order-service",
            "old_state": {"enabled": False, "rollout_percent": 0},
            "new_state": {"enabled": True, "rollout_percent": 10}
        },
        {
            "ts": (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat(),
            "flag_name": "experimental_search",
            "service": "search-service",
            "old_state": {"enabled": False},
            "new_state": {"enabled": True, "beta_users_only": True}
        }
    ]
    
    async with aiohttp.ClientSession() as session:
        for change in flag_changes:
            async with session.post(
                f"{API_URL}/ingest/flag_changes",
                json=change
            ) as resp:
                if resp.status not in [200, 201]:
                    print(f"Warning: Failed to insert flag change: {resp.status}")
    
    print(f"[OK] Generated {len(flag_changes)} flag changes")


async def seed_incident(incident_config: dict):
    """Create a demo incident directly in Postgres."""
    incident_start = datetime.now(timezone.utc) - timedelta(hours=incident_config["hours_ago"])
    incident_end = incident_start + timedelta(minutes=incident_config["duration_minutes"])
    
    # Connect to Postgres
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        database='rca',
        user='rca',
        password='rca_password'
    )
    
    try:
        incident_id = str(uuid.uuid4())
        
        # Create incident
        await conn.execute(
            """
            INSERT INTO incidents (id, start_ts, end_ts, title, status, summary)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            incident_id,
            incident_start,
            incident_end,
            f"Incident in {incident_config['service']}",
            'OPEN',
            f"Performance degradation detected after deployment {incident_config['commit_sha']}"
        )
        
        # Create a few demo anomalies and link them
        num_anomalies = 3
        for i in range(num_anomalies):
            anomaly_id = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO anomalies (id, start_ts, end_ts, service, metric, score, detector, details)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                anomaly_id,
                incident_start + timedelta(minutes=i * (incident_config["duration_minutes"] / num_anomalies)),
                incident_start + timedelta(minutes=(i+1) * (incident_config["duration_minutes"] / num_anomalies)),
                incident_config['service'],
                'p95_latency_ms',
                4.5 + i * 0.5,
                'demo',
                json.dumps({'reason': 'Latency spike detected'})
            )
            
            # Link anomaly to incident
            await conn.execute(
                """
                INSERT INTO incident_anomalies (incident_id, anomaly_id)
                VALUES ($1, $2)
                """,
                incident_id,
                anomaly_id
            )
        
        print(f"  [OK] Created incident: {incident_id}")
        print(f"    Title: Incident in {incident_config['service']}")
        print(f"    Time: {incident_start.isoformat()} to {incident_end.isoformat()}")
        
        return incident_id
        
    finally:
        await conn.close()


async def wait_for_suspects(incident_id: str, max_wait_seconds: int = 30) -> list:
    """Wait for suspects to be generated and return them."""
    print(f"\nWaiting for suspects to be generated (max {max_wait_seconds}s)...")
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        database='rca',
        user='rca',
        password='rca_password'
    )
    
    try:
        for i in range(max_wait_seconds):
            rows = await conn.fetch(
                "SELECT id, suspect_type, suspect_key FROM suspects WHERE incident_id = $1",
                incident_id
            )
            if len(rows) > 0:
                print(f"[OK] Found {len(rows)} suspects")
                return rows
            await asyncio.sleep(1)
            if (i + 1) % 5 == 0:
                print(f"  Still waiting... ({i + 1}s)")
        
        print(f"[WARNING] No suspects found after {max_wait_seconds}s")
        return []
    finally:
        await conn.close()


async def seed_labels(incident_id: str, incident_config: dict):
    """Add labels to suspects - the actual cause gets label=1, others get label=0."""
    # Wait for suspects to be generated
    suspects = await wait_for_suspects(incident_id)
    
    if not suspects:
        print(f"[WARNING] No suspects found for incident {incident_id}, skipping label seeding")
        return 0
    
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        database='rca',
        user='rca',
        password='rca_password'
    )
    
    try:
        # Find the deployment ID for the actual cause
        deployment_row = await conn.fetchrow(
            """
            SELECT id FROM deployments 
            WHERE service = $1 AND commit_sha = $2
            ORDER BY ts DESC
            LIMIT 1
            """,
            incident_config['service'],
            incident_config['commit_sha']
        )
        
        if not deployment_row:
            print(f"[WARNING] Could not find deployment for {incident_config['service']}:{incident_config['commit_sha']}")
            return 0
        
        actual_cause_deployment_id = str(deployment_row['id'])
        labeled_count = 0
        
        for suspect in suspects:
            suspect_id = suspect['id']
            suspect_key = suspect['suspect_key']
            suspect_type = suspect['suspect_type']
            
            # Label the actual cause (deployment with matching ID) as 1, others as 0
            label = 1 if (suspect_type == 'DEPLOYMENT' and suspect_key == actual_cause_deployment_id) else 0
            
            # Check if label already exists
            existing = await conn.fetchrow(
                "SELECT id FROM labels WHERE suspect_id = $1",
                suspect_id
            )
            
            if not existing:
                await conn.execute(
                    """
                    INSERT INTO labels (incident_id, suspect_id, label, labeler, notes)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    incident_id,
                    suspect_id,
                    label,
                    'seed_script',
                    'Auto-labeled by seed script - actual cause' if label == 1 else 'Auto-labeled as not cause'
                )
                labeled_count += 1
        
        return labeled_count
        
    finally:
        await conn.close()


async def train_ml_model():
    """Train the ML model using labeled data."""
    print("\nTraining ML model...")
    
    import subprocess
    import sys
    import os
    
    # Get the project root directory (parent of scripts/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    rca_dir = os.path.join(project_root, "apps", "rca")
    
    # Run the training script
    result = subprocess.run(
        [sys.executable, "-m", "rca.train"],
        cwd=rca_dir,
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("[OK] Model trained successfully")
        # Print key output lines
        for line in result.stdout.split('\n'):
            if any(keyword in line for keyword in ['Loaded', 'Training', 'Test Metrics', 'Precision', 'Recall', 'F1', 'AUC', 'Model saved']):
                print(f"  {line}")
        return True
    else:
        print(f"[ERROR] Model training failed:")
        if result.stderr:
            print(result.stderr)
        if result.stdout:
            print(result.stdout)
        return False


async def restart_rca_worker():
    """Restart the RCA worker Docker container."""
    print("\nRestarting RCA worker...")
    
    import subprocess
    
    result = subprocess.run(
        ["docker", "compose", "restart", "rca"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("[OK] RCA worker restarted")
        return True
    else:
        print(f"[WARNING] Failed to restart RCA worker: {result.stderr}")
        print("    You may need to restart it manually: docker compose restart rca")
        return False


async def main():
    """Run all seeding functions."""
    print("=" * 60)
    print("Seeding Demo Data")
    print("=" * 60)
    print(f"Creating {len(INCIDENTS)} incidents across different services")
    print()
    
    # Check API health first
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}/health") as resp:
            if resp.status != 200:
                print(f"[ERROR] API health check failed: {resp.status}")
                print("Make sure the API is running: docker compose up")
                return
            data = await resp.json()
            if data.get("status") != "healthy":
                print(f"X API is unhealthy: {data}")
                return
    
    print("[OK] API is healthy\n")
    
    # Seed base data (metrics, logs, deployments, etc.)
    await seed_metrics()
    await seed_logs()
    await seed_deployments()
    await seed_config_changes()
    await seed_flag_changes()
    
    # Create all incidents
    print(f"\nCreating {len(INCIDENTS)} incidents...")
    incident_ids = []
    for i, incident_config in enumerate(INCIDENTS, 1):
        print(f"\n[{i}/{len(INCIDENTS)}] Creating incident for {incident_config['service']}...")
        incident_id = await seed_incident(incident_config)
        if incident_id:
            incident_ids.append((incident_id, incident_config))
    
    print(f"\n[OK] Created {len(incident_ids)} incidents")
    
    # Process each incident: trigger RCA, wait for suspects, and label them
    total_labeled = 0
    for i, (incident_id, incident_config) in enumerate(incident_ids, 1):
        print(f"\n[{i}/{len(incident_ids)}] Processing incident {incident_id[:8]}... ({incident_config['service']})")
        
        # Trigger RCA analysis
        print("  Triggering RCA analysis...")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_URL}/incidents/{incident_id}/rerun_rca"
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"  [OK] RCA analysis triggered")
                else:
                    print(f"  [WARNING] Failed to trigger RCA: {resp.status}")
                    continue
        
        # Wait for suspects and add labels
        print("  Adding labels to suspects...")
        labeled_count = await seed_labels(incident_id, incident_config)
        if labeled_count > 0:
            print(f"  [OK] Added {labeled_count} labels for this incident")
            total_labeled += labeled_count
        else:
            print(f"  [WARNING] No labels added for this incident")
    
    print(f"\n[OK] Total labels created: {total_labeled}")
    
    # Train model if we have enough labels
    if total_labeled >= 10:
        print(f"\n[OK] Created {total_labeled} labels (need 10 minimum for training)")
        # Train the model
        if await train_ml_model():
            # Restart RCA worker to load the new model
            if await restart_rca_worker():
                print("\n" + "=" * 60)
                print("[OK] ML model is now active!")
                print("=" * 60)
                print("The RCA worker will now use ML-based ranking for future incidents.")
            else:
                print("\n[WARNING] Model trained but RCA worker restart failed.")
                print("    Restart manually: docker compose restart rca")
        else:
            print("\n[WARNING] Model training failed, but you can try again later")
            print("    Run: cd apps/rca && python -m rca.train")
    else:
        print(f"\n[WARNING] Only {total_labeled} labels created. Need at least 10 for training.")
        print("    The system will use heuristic ranking until enough labels are collected.")
        print("    You can add more labels via the UI and then train the model manually.")
    
    print()
    print("=" * 60)
    print("[OK] Demo data seeding complete!")
    print("=" * 60)
    print(f"\nCreated {len(incident_ids)} incidents with {total_labeled} total labels")
    if incident_ids:
        print(f"\nView incidents at: http://localhost:3001")


if __name__ == "__main__":
    asyncio.run(main())


