"""Main RCA worker that consumes rca.requests and generates ranked suspects."""
import asyncio
import os
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
import json
import uuid

from aiokafka import AIOKafkaConsumer
from clickhouse_driver import Client
import asyncpg
import redis.asyncio as redis

from rca.candidate_generator import CandidateGenerator
from rca.feature_extractor import FeatureExtractor
from rca.ml_ranker import MLRanker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RCAWorker:
    """Main RCA worker."""
    
    def __init__(self):
        self.clickhouse_client = None
        self.postgres_pool = None
        self.kafka_consumer = None
        self.redis_client = None
        self.candidate_generator = CandidateGenerator(
            lookback_hours=2,
            lookforward_hours=0
        )
        self.feature_extractor = FeatureExtractor()
        # Use ML ranker - will fallback to heuristic if no model is trained
        model_path = os.getenv('ML_MODEL_PATH', 'models/ranker.pkl')
        self.ranker = MLRanker(model_path=model_path)
    
    async def connect(self):
        """Connect to all services."""
        # ClickHouse
        self.clickhouse_client = Client(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
            database=os.getenv("CLICKHOUSE_DB", "rca")
        )
        logger.info("Connected to ClickHouse")
        
        # Postgres
        self.postgres_pool = await asyncpg.create_pool(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "rca"),
            user=os.getenv("POSTGRES_USER", "rca"),
            password=os.getenv("POSTGRES_PASSWORD", "rca_password"),
            min_size=2,
            max_size=10
        )
        logger.info("Connected to Postgres")
        
        # Redis (for activity logging)
        try:
            self.redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis (activity logging will be disabled): {e}")
            self.redis_client = None
        
        # Kafka consumer
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.kafka_consumer = AIOKafkaConsumer(
            'rca.requests',
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id='rca-worker',
            auto_offset_reset='latest'
        )
        await self.kafka_consumer.start()
        logger.info("Connected to Kafka")
    
    async def disconnect(self):
        """Disconnect from all services."""
        if self.kafka_consumer:
            await self.kafka_consumer.stop()
        if self.postgres_pool:
            await self.postgres_pool.close()
        if self.clickhouse_client:
            self.clickhouse_client.disconnect()
        if self.redis_client:
            await self.redis_client.close()
    
    async def log_activity_event(self, event_type: str, service: str = None, message: str = None, metadata: dict = None):
        """Log an activity event to Redis."""
        if not self.redis_client:
            return
        
        try:
            import json
            from datetime import datetime, timezone
            
            event = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "type": event_type,
                "service": service,
                "message": message,
                "metadata": metadata or {}
            }
            
            timestamp = datetime.now(timezone.utc).timestamp()
            event_json = json.dumps(event)
            
            await self.redis_client.zadd("activity:events", {event_json: timestamp})
            await self.redis_client.expire("activity:events", 3600)  # 1 hour TTL
            
        except Exception as e:
            logger.debug(f"Failed to log activity event: {e}")
    
    async def process_rca_request(self, message: Dict):
        """Process an RCA request for an incident."""
        try:
            incident_id = message['incident_id']
            incident_start = datetime.fromisoformat(message['start_ts'].replace('Z', '+00:00'))
            incident_end = datetime.fromisoformat(message['end_ts'].replace('Z', '+00:00'))
            
            logger.info(f"Processing RCA request for incident {incident_id}")
            
            # Log activity event
            await self.log_activity_event(
                event_type="rca_started",
                service=None,
                message=f"RCA analysis started for incident {incident_id}",
                metadata={"incident_id": incident_id}
            )
            
            # Get affected services from incident anomalies
            affected_services = await self._get_affected_services(incident_id)
            
            # Generate candidates
            candidates = await self.candidate_generator.generate_candidates(
                self.postgres_pool,
                incident_start,
                incident_end,
                affected_services
            )
            
            if not candidates:
                logger.warning(f"No candidates found for incident {incident_id}")
                return
            
            # Extract features for each candidate
            candidates_with_features = []
            for candidate in candidates:
                features = await self.feature_extractor.extract_features(
                    candidate,
                    incident_start,
                    incident_end,
                    affected_services,
                    self.clickhouse_client,
                    self.postgres_pool
                )
                candidate['evidence'] = features
                candidates_with_features.append(candidate)
            
            # Rank candidates
            ranked = self.ranker.rank(candidates_with_features)
            
            # Store suspects in Postgres
            await self._store_suspects(incident_id, ranked)
            
            logger.info(f"Generated {len(ranked)} ranked suspects for incident {incident_id}")
            
            # Log activity event
            top_suspects = [s.get('suspect_key', 'N/A') for s in ranked[:3]]
            await self.log_activity_event(
                event_type="suspects_generated",
                service=affected_services[0] if affected_services else None,
                message=f"Generated {len(ranked)} suspects for incident {incident_id}",
                metadata={
                    "incident_id": incident_id,
                    "suspect_count": len(ranked),
                    "top_suspects": top_suspects
                }
            )
        
        except Exception as e:
            logger.error(f"Error processing RCA request: {e}", exc_info=True)
    
    async def _get_affected_services(self, incident_id: str) -> List[str]:
        """Get list of affected services from incident anomalies."""
        async with self.postgres_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT a.service
                FROM incidents i
                JOIN incident_anomalies ia ON i.id = ia.incident_id
                JOIN anomalies a ON ia.anomaly_id = a.id
                WHERE i.id = $1
                """,
                incident_id
            )
        
        return [row['service'] for row in rows]
    
    async def _store_suspects(self, incident_id: str, ranked: List[Dict[str, Any]]):
        """Store ranked suspects in Postgres."""
        async with self.postgres_pool.acquire() as conn:
            # Delete existing suspects for this incident
            await conn.execute(
                "DELETE FROM suspects WHERE incident_id = $1",
                incident_id
            )
            
            # Insert new suspects
            for suspect in ranked:
                suspect_id = str(uuid.uuid4())
                await conn.execute(
                    """
                    INSERT INTO suspects (id, incident_id, suspect_type, suspect_key, rank, score, evidence)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    suspect_id,
                    incident_id,
                    suspect['suspect_type'],
                    suspect['suspect_key'],
                    suspect['rank'],
                    suspect['score'],
                    json.dumps(suspect['evidence'])
                )
    
    async def run(self):
        """Main run loop."""
        logger.info("Starting RCA worker...")
        await self.connect()
        
        try:
            async for message in self.kafka_consumer:
                await self.process_rca_request(message.value)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await self.disconnect()


async def main():
    """Entry point."""
    worker = RCAWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())


