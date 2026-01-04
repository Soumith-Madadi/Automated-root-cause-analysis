"""Generate candidate suspects for an incident."""
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
import asyncpg
import logging

logger = logging.getLogger(__name__)


class CandidateGenerator:
    """Generates candidate suspects from deployments, config changes, flags, etc."""
    
    def __init__(
        self,
        lookback_hours: int = 2,
        lookforward_hours: int = 0
    ):
        """
        Args:
            lookback_hours: Hours before incident start to look for changes
            lookforward_hours: Hours after incident end to look for changes
        """
        self.lookback_hours = lookback_hours
        self.lookforward_hours = lookforward_hours
    
    async def generate_candidates(
        self,
        postgres_pool: asyncpg.Pool,
        incident_start: datetime,
        incident_end: datetime,
        affected_services: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Generate all candidate suspects.
        
        Returns:
            List of candidate dicts with keys:
                - suspect_type: DEPLOYMENT, CONFIG, FLAG, SERVICE, ENDPOINT
                - suspect_key: unique identifier
                - ts: timestamp of change
                - service: affected service
                - metadata: additional info
        """
        candidates = []
        
        # Time window
        window_start = incident_start - timedelta(hours=self.lookback_hours)
        window_end = incident_end + timedelta(hours=self.lookforward_hours)
        
        # Get deployments
        deployments = await self._get_deployments(
            postgres_pool, window_start, window_end, affected_services
        )
        candidates.extend(deployments)
        
        # Get config changes
        config_changes = await self._get_config_changes(
            postgres_pool, window_start, window_end, affected_services
        )
        candidates.extend(config_changes)
        
        # Get flag changes
        flag_changes = await self._get_flag_changes(
            postgres_pool, window_start, window_end, affected_services
        )
        candidates.extend(flag_changes)
        
        # Fallback: If no candidates found, create a SERVICE candidate for each affected service
        # This ensures RCA always has something to analyze, even in demo scenarios
        if not candidates and affected_services:
            for service in affected_services:
                candidates.append({
                    'suspect_type': 'SERVICE',
                    'suspect_key': f'service_{service}',
                    'ts': incident_start - timedelta(minutes=30),  # 30 min before incident
                    'service': service,
                    'metadata': {
                        'reason': 'No deployments/config changes found, analyzing service behavior'
                    }
                })
            logger.info(f"No traditional candidates found, created {len(candidates)} SERVICE candidates as fallback")
        
        logger.info(f"Generated {len(candidates)} candidates for incident")
        return candidates
    
    async def _get_deployments(
        self,
        postgres_pool: asyncpg.Pool,
        window_start: datetime,
        window_end: datetime,
        affected_services: List[str]
    ) -> List[Dict[str, Any]]:
        """Get deployments in time window."""
        async with postgres_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, ts, service, commit_sha, version, author, diff_summary, links
                FROM deployments
                WHERE ts >= $1 AND ts <= $2
                AND service = ANY($3)
                ORDER BY ts DESC
                """,
                window_start, window_end, affected_services
            )
        
        candidates = []
        for row in rows:
            candidates.append({
                'suspect_type': 'DEPLOYMENT',
                'suspect_key': str(row['id']),
                'ts': row['ts'],
                'service': row['service'],
                'metadata': {
                    'commit_sha': row['commit_sha'],
                    'version': row['version'],
                    'author': row['author'],
                    'diff_summary': row['diff_summary'],
                    'links': row['links']
                }
            })
        
        return candidates
    
    async def _get_config_changes(
        self,
        postgres_pool: asyncpg.Pool,
        window_start: datetime,
        window_end: datetime,
        affected_services: List[str]
    ) -> List[Dict[str, Any]]:
        """Get config changes in time window."""
        async with postgres_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, ts, service, key, old_value_hash, new_value_hash, diff_summary, source
                FROM config_changes
                WHERE ts >= $1 AND ts <= $2
                AND service = ANY($3)
                ORDER BY ts DESC
                """,
                window_start, window_end, affected_services
            )
        
        candidates = []
        for row in rows:
            candidates.append({
                'suspect_type': 'CONFIG',
                'suspect_key': str(row['id']),
                'ts': row['ts'],
                'service': row['service'],
                'metadata': {
                    'key': row['key'],
                    'old_value_hash': row['old_value_hash'],
                    'new_value_hash': row['new_value_hash'],
                    'diff_summary': row['diff_summary'],
                    'source': row['source']
                }
            })
        
        return candidates
    
    async def _get_flag_changes(
        self,
        postgres_pool: asyncpg.Pool,
        window_start: datetime,
        window_end: datetime,
        affected_services: List[str]
    ) -> List[Dict[str, Any]]:
        """Get feature flag changes in time window."""
        async with postgres_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, ts, flag_name, service, old_state, new_state
                FROM feature_flag_changes
                WHERE ts >= $1 AND ts <= $2
                AND (service = ANY($3) OR service IS NULL)
                ORDER BY ts DESC
                """,
                window_start, window_end, affected_services
            )
        
        candidates = []
        for row in rows:
            candidates.append({
                'suspect_type': 'FLAG',
                'suspect_key': str(row['id']),
                'ts': row['ts'],
                'service': row['service'],
                'metadata': {
                    'flag_name': row['flag_name'],
                    'old_state': row['old_state'],
                    'new_state': row['new_state']
                }
            })
        
        return candidates


