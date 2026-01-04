"""Activity logger service for tracking system events in real-time."""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import redis.asyncio as redis

logger = logging.getLogger(__name__)

EVENT_TYPES = {
    'metrics_ingested': 'Metrics ingested',
    'anomaly_detected': 'Anomaly detected',
    'incident_created': 'Incident created',
    'rca_started': 'RCA analysis started',
    'suspects_generated': 'Suspects generated',
    'suspect_score_updated': 'Suspect score updated'
}


class ActivityLogger:
    """Service for logging and retrieving system events."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.events_key = "activity:events"
        self.ttl_seconds = 3600  # 1 hour
    
    async def log_event(
        self,
        event_type: str,
        service: Optional[str] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log a system event."""
        if event_type not in EVENT_TYPES:
            logger.warning(f"Unknown event type: {event_type}")
            return
        
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "service": service,
            "message": message or EVENT_TYPES[event_type],
            "metadata": metadata or {}
        }
        
        try:
            # Use sorted set with timestamp as score for efficient range queries
            # Key format: activity:events
            # Score: timestamp (Unix timestamp)
            # Value: JSON-encoded event
            timestamp = datetime.now(timezone.utc).timestamp()
            event_json = json.dumps(event)
            
            # Add to sorted set
            await self.redis_client.zadd(
                self.events_key,
                {event_json: timestamp}
            )
            
            # Set TTL on the key (refresh on each add)
            await self.redis_client.expire(self.events_key, self.ttl_seconds)
            
            logger.debug(f"Logged event: {event_type} for {service}")
            
        except Exception as e:
            logger.error(f"Failed to log event: {e}", exc_info=True)
    
    async def get_events(
        self,
        since: Optional[datetime] = None,
        limit: int = 250,
        event_type: Optional[str] = None,
        service: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get events since a timestamp."""
        try:
            # Get all events since timestamp
            if since:
                min_score = since.timestamp()
            else:
                # Default: last hour
                min_score = datetime.now(timezone.utc).timestamp() - self.ttl_seconds
            
            max_score = datetime.now(timezone.utc).timestamp()
            
            # Get events from sorted set (range query)
            events_data = await self.redis_client.zrangebyscore(
                self.events_key,
                min=min_score,
                max=max_score,
                withscores=False,
                start=0,
                num=limit * 2  # Get more to filter, then limit
            )
            
            # Parse events
            events = []
            for event_json in events_data:
                try:
                    event = json.loads(event_json)
                    
                    # Apply filters
                    if event_type and event.get("type") != event_type:
                        continue
                    if service and event.get("service") != service:
                        continue
                    
                    events.append(event)
                    
                    if len(events) >= limit:
                        break
                        
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse event: {event_json}")
                    continue
            
            # Sort by timestamp (newest first)
            events.sort(key=lambda x: x.get("ts", ""), reverse=True)
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get events: {e}", exc_info=True)
            return []
    
    async def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get most recent events."""
        return await self.get_events(limit=limit)
    
    async def clear_events(self):
        """Clear all events (for testing/debugging)."""
        try:
            await self.redis_client.delete(self.events_key)
            logger.info("Cleared all activity events")
        except Exception as e:
            logger.error(f"Failed to clear events: {e}", exc_info=True)
