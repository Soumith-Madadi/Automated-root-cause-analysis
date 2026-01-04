"""Extract evidence features for candidate suspects."""
from typing import Dict, Any, List
from datetime import datetime, timedelta, timezone
from clickhouse_driver import Client
import asyncpg
import logging
import re

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """Extracts features from metrics, logs, and metadata."""
    
    def __init__(self):
        self.diff_keywords = ['timeout', 'retry', 'cache', 'db', 'database', 'connection', 'pool']
    
    def _format_clickhouse_ts(self, dt: datetime) -> str:
        """Format datetime for ClickHouse queries.
        
        ClickHouse DateTime64(3) expects format: 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DDTHH:MM:SS'
        We remove timezone info and format appropriately.
        """
        # Convert to UTC if timezone-aware, then remove timezone
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        # Format for ClickHouse
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    
    async def extract_features(
        self,
        candidate: Dict[str, Any],
        incident_start: datetime,
        incident_end: datetime,
        affected_services: List[str],
        clickhouse_client: Client,
        postgres_pool: asyncpg.Pool
    ) -> Dict[str, Any]:
        """
        Extract all features for a candidate.
        
        Returns:
            Dict with feature names and values
        """
        features = {}
        
        # Time proximity features
        features.update(self._extract_time_features(candidate, incident_start))
        
        # Blast radius / correlation features
        features.update(await self._extract_correlation_features(
            candidate, incident_start, incident_end, affected_services, clickhouse_client
        ))
        
        # Log evidence features
        features.update(await self._extract_log_features(
            candidate, incident_start, incident_end, clickhouse_client
        ))
        
        # Diff evidence features
        features.update(self._extract_diff_features(candidate))
        
        # Historical risk features (simplified for v1)
        features.update(await self._extract_historical_features(
            candidate, postgres_pool
        ))
        
        return features
    
    def _extract_time_features(
        self,
        candidate: Dict[str, Any],
        incident_start: datetime
    ) -> Dict[str, float]:
        """Extract time proximity features."""
        candidate_ts = candidate['ts']
        minutes_before = (incident_start - candidate_ts).total_seconds() / 60
        
        return {
            'minutes_before_incident': minutes_before,
            'is_before_incident': 1.0 if minutes_before >= 0 else 0.0,
            'time_proximity_score': max(0, 1.0 - abs(minutes_before) / 60.0)  # Decay over 1 hour
        }
    
    async def _extract_correlation_features(
        self,
        candidate: Dict[str, Any],
        incident_start: datetime,
        incident_end: datetime,
        affected_services: List[str],
        clickhouse_client: Client
    ) -> Dict[str, float]:
        """Extract correlation features from metrics."""
        if candidate['suspect_type'] != 'DEPLOYMENT':
            return {
                'metric_delta_count': 0.0,
                'max_metric_delta': 0.0
            }
        
        service = candidate['service']
        if service not in affected_services:
            return {
                'metric_delta_count': 0.0,
                'max_metric_delta': 0.0
            }
        
        try:
            # Get metrics before and after candidate timestamp
            before_window = (candidate['ts'] - timedelta(minutes=10), candidate['ts'])
            after_window = (candidate['ts'], incident_end)
            
            # Query baseline (before)
            before_query = f"""
                SELECT metric, avg(value) as avg_value
                FROM metrics_timeseries
                WHERE service = '{service}'
                AND ts >= '{self._format_clickhouse_ts(before_window[0])}'
                AND ts < '{self._format_clickhouse_ts(before_window[1])}'
                GROUP BY metric
            """
            before_results = clickhouse_client.execute(before_query)
            before_metrics = {row[0]: row[1] for row in before_results}
            
            # Query after
            after_query = f"""
                SELECT metric, avg(value) as avg_value
                FROM metrics_timeseries
                WHERE service = '{service}'
                AND ts >= '{self._format_clickhouse_ts(after_window[0])}'
                AND ts <= '{self._format_clickhouse_ts(after_window[1])}'
                GROUP BY metric
            """
            after_results = clickhouse_client.execute(after_query)
            after_metrics = {row[0]: row[1] for row in after_results}
            
            # Compute deltas
            deltas = []
            for metric in set(before_metrics.keys()) & set(after_metrics.keys()):
                before_val = before_metrics[metric]
                after_val = after_metrics[metric]
                if before_val > 0:
                    delta = abs(after_val - before_val) / before_val
                    deltas.append(delta)
            
            if deltas:
                return {
                    'metric_delta_count': float(len(deltas)),
                    'max_metric_delta': float(max(deltas)),
                    'avg_metric_delta': float(sum(deltas) / len(deltas))
                }
            else:
                return {
                    'metric_delta_count': 0.0,
                    'max_metric_delta': 0.0,
                    'avg_metric_delta': 0.0
                }
        except Exception as e:
            logger.warning(f"Error extracting correlation features: {e}")
            return {
                'metric_delta_count': 0.0,
                'max_metric_delta': 0.0,
                'avg_metric_delta': 0.0
            }
    
    async def _extract_log_features(
        self,
        candidate: Dict[str, Any],
        incident_start: datetime,
        incident_end: datetime,
        clickhouse_client: Client
    ) -> Dict[str, float]:
        """Extract log evidence features."""
        if candidate['suspect_type'] != 'DEPLOYMENT':
            return {
                'error_log_delta': 0.0,
                'new_error_signature': 0.0
            }
        
        service = candidate['service']
        
        try:
            # Count errors before and after
            before_window = (candidate['ts'] - timedelta(minutes=10), candidate['ts'])
            after_window = (candidate['ts'], incident_end)
            
            before_query = f"""
                SELECT count() as cnt
                FROM logs
                WHERE service = '{service}'
                AND level = 'ERROR'
                AND ts >= '{self._format_clickhouse_ts(before_window[0])}'
                AND ts < '{self._format_clickhouse_ts(before_window[1])}'
            """
            before_count = clickhouse_client.execute(before_query)
            before_errors = before_count[0][0] if before_count else 0
            
            after_query = f"""
                SELECT count() as cnt
                FROM logs
                WHERE service = '{service}'
                AND level = 'ERROR'
                AND ts >= '{self._format_clickhouse_ts(after_window[0])}'
                AND ts <= '{self._format_clickhouse_ts(after_window[1])}'
            """
            after_count = clickhouse_client.execute(after_query)
            after_errors = after_count[0][0] if after_count else 0
            
            error_delta = (after_errors - before_errors) / max(before_errors, 1)
            
            # Check for new error signatures (simplified: check for DB_TIMEOUT)
            new_error_query = f"""
                SELECT count() as cnt
                FROM logs
                WHERE service = '{service}'
                AND level = 'ERROR'
                AND event = 'DB_TIMEOUT'
                AND ts >= '{self._format_clickhouse_ts(after_window[0])}'
                AND ts <= '{self._format_clickhouse_ts(after_window[1])}'
            """
            new_error_count = clickhouse_client.execute(new_error_query)
            new_error_signature = 1.0 if (new_error_count and new_error_count[0][0] > 0) else 0.0
            
            return {
                'error_log_delta': float(error_delta),
                'new_error_signature': new_error_signature
            }
        except Exception as e:
            logger.warning(f"Error extracting log features: {e}")
            return {
                'error_log_delta': 0.0,
                'new_error_signature': 0.0
            }
    
    def _extract_diff_features(self, candidate: Dict[str, Any]) -> Dict[str, float]:
        """Extract features from diff summary."""
        diff_summary = candidate.get('metadata', {}).get('diff_summary', '')
        if not diff_summary:
            return {
                'diff_length': 0.0,
                'diff_keyword_hit': 0.0
            }
        
        # Check for keywords
        diff_lower = diff_summary.lower()
        keyword_hits = sum(1 for keyword in self.diff_keywords if keyword in diff_lower)
        
        return {
            'diff_length': float(len(diff_summary)),
            'diff_keyword_hit': 1.0 if keyword_hits > 0 else 0.0,
            'diff_keyword_count': float(keyword_hits)
        }
    
    async def _extract_historical_features(
        self,
        candidate: Dict[str, Any],
        postgres_pool: asyncpg.Pool
    ) -> Dict[str, float]:
        """Extract historical risk features."""
        # Simplified: just check if service has had incidents recently
        service = candidate.get('service')
        if not service:
            return {'service_incident_rate_30d': 0.0}
        
        try:
            async with postgres_pool.acquire() as conn:
                count = await conn.fetchval(
                    """
                    SELECT count(DISTINCT i.id)
                    FROM incidents i
                    JOIN incident_anomalies ia ON i.id = ia.incident_id
                    JOIN anomalies a ON ia.anomaly_id = a.id
                    WHERE a.service = $1
                    AND i.start_ts >= NOW() - INTERVAL '30 days'
                    """,
                    service
                )
            
            return {
                'service_incident_rate_30d': float(count or 0)
            }
        except Exception as e:
            logger.warning(f"Error extracting historical features: {e}")
            return {'service_incident_rate_30d': 0.0}


