"""Main detector worker that consumes metrics and detects anomalies."""
import asyncio
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List
import json
import uuid

from aiokafka import AIOKafkaConsumer
from clickhouse_driver import Client
import asyncpg
import redis.asyncio as redis

from detector.anomaly_detector import AnomalyDetector
from detector.incident_grouper import IncidentGrouper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DetectorWorker:
    """Main detector worker."""
    
    def __init__(self):
        self.clickhouse_client = None
        self.postgres_pool = None
        self.kafka_consumer = None
        self.kafka_producer = None
        self.redis_client = None
        self.detector = AnomalyDetector(
            z_threshold=3.0,
            min_points=10,
            lookback_days=7
        )
        self.grouper = IncidentGrouper(gap_minutes=10)
        self.metrics_buffer: Dict[str, List] = {}  # Key: (service, metric), Value: list of (ts, value)
    
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
            'metrics.raw',
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id='detector-worker',
            auto_offset_reset='latest'
        )
        await self.kafka_consumer.start()
        logger.info("Connected to Kafka")
        
        # Load historical metrics from ClickHouse to populate buffer
        await self.load_historical_metrics()
    
    async def load_historical_metrics(self, lookback_hours: int = 1):
        """Load historical metrics from ClickHouse to populate the buffer."""
        try:
            logger.info(f"Loading historical metrics from last {lookback_hours} hour(s)...")
            
            cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
            
            # Query ClickHouse for recent metrics
            # Use table name directly since client is already connected to the database
            # ClickHouse driver returns list of tuples: [(ts, service, metric, value, tags), ...]
            # Format datetime as YYYY-MM-DD HH:MM:SS.mmm (ClickHouse doesn't like ISO format with timezone)
            cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  # Remove last 3 digits to get milliseconds
            query = f"""
                SELECT ts, service, metric, value
                FROM metrics_timeseries
                WHERE ts >= toDateTime64('{cutoff_str}', 3)
                ORDER BY ts ASC
            """
            
            # ClickHouse client is synchronous, so we need to run in executor
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.clickhouse_client.execute(query)
            )
            
            if not results:
                logger.info("No historical metrics found in ClickHouse")
                return
            
            # Group by (service, metric) and populate buffer
            count = 0
            for row in results:
                # ClickHouse returns tuples: (ts, service, metric, value, tags)
                # But we only selected 4 columns, so: (ts, service, metric, value)
                ts, service, metric, value = row[0], row[1], row[2], row[3]
                
                # Parse timestamp (ClickHouse returns datetime objects or strings)
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                elif isinstance(ts, datetime):
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                else:
                    # Skip if we can't parse
                    continue
                
                key = (service, metric)
                if key not in self.metrics_buffer:
                    self.metrics_buffer[key] = []
                
                self.metrics_buffer[key].append((ts, float(value)))
                count += 1
            
            # Sort each buffer by timestamp
            for key in self.metrics_buffer:
                self.metrics_buffer[key].sort(key=lambda x: x[0])
            
            logger.info(f"Loaded {count} historical metric points into buffer")
            logger.info(f"Buffer now contains {len(self.metrics_buffer)} service/metric combinations")
            
            # Log buffer sizes for debugging
            for key, data in self.metrics_buffer.items():
                if len(data) > 0:
                    logger.debug(f"  {key[0]}/{key[1]}: {len(data)} points")
        
        except Exception as e:
            logger.warning(f"Failed to load historical metrics: {e}", exc_info=True)
            logger.warning("Continuing without historical data - detector will build buffer from new metrics")
    
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
    
    async def process_metric_point(self, message: Dict):
        """Process a single metric point."""
        try:
            ts = datetime.fromisoformat(message['ts'].replace('Z', '+00:00'))
            service = message['service']
            metric = message['metric']
            value = message['value']
            
            key = (service, metric)
            if key not in self.metrics_buffer:
                self.metrics_buffer[key] = []
            
            self.metrics_buffer[key].append((ts, value))
            
            # Keep only last 24 hours of data in buffer
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            self.metrics_buffer[key] = [
                (t, v) for t, v in self.metrics_buffer[key]
                if t >= cutoff
            ]
            
            # Check for anomalies after every point if we have enough data
            # This ensures faster detection
            if len(self.metrics_buffer[key]) >= 20:
                await self.check_anomalies(service, metric)
        
        except Exception as e:
            logger.error(f"Error processing metric point: {e}", exc_info=True)
    
    async def check_anomalies(self, service: str, metric: str):
        """Check for anomalies in a service/metric time series."""
        key = (service, metric)
        if key not in self.metrics_buffer:
            return
        
        data = self.metrics_buffer[key]
        if len(data) < 20:  # Need enough data
            return
        
        # Sort by timestamp
        data.sort(key=lambda x: x[0])
        
        timestamps = [d[0] for d in data]
        values = [d[1] for d in data]
        
        # Detect anomalies
        anomalies = self.detector.detect_anomalies_in_window(
            values=values,
            timestamps=timestamps,
            metric=metric,
            window_minutes=5,
            required_anomalies=3
        )
        
        # Store anomalies in Postgres
        for start_ts, end_ts, score in anomalies:
            await self.store_anomaly(service, metric, start_ts, end_ts, score)
    
    async def store_anomaly(
        self,
        service: str,
        metric: str,
        start_ts: datetime,
        end_ts: datetime,
        score: float
    ):
        """Store an anomaly in Postgres."""
        anomaly_id = str(uuid.uuid4())
        
        async with self.postgres_pool.acquire() as conn:
            # Check if similar anomaly already exists (within 1 minute)
            # Calculate bounds in Python to avoid PostgreSQL parameter/interval arithmetic issues
            lower_bound = start_ts - timedelta(minutes=1)
            upper_bound = start_ts + timedelta(minutes=1)
            
            existing = await conn.fetchrow(
                """
                SELECT id FROM anomalies
                WHERE service = $1 AND metric = $2
                AND start_ts >= $3
                AND start_ts <= $4
                """,
                service, metric, lower_bound, upper_bound
            )
            
            if existing:
                logger.debug(f"Anomaly already exists: {existing['id']}")
                return
            
            # Insert anomaly
            await conn.execute(
                """
                INSERT INTO anomalies (id, start_ts, end_ts, service, metric, score, detector, details)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                anomaly_id,
                start_ts,
                end_ts,
                service,
                metric,
                score,
                'robust_zscore',
                json.dumps({'z_score': score})
            )
            
            logger.info(f"Detected anomaly: {service}/{metric} at {start_ts} (score: {score:.2f})")
            
            # Log activity event
            await self.log_activity_event(
                event_type="anomaly_detected",
                service=service,
                message=f"Anomaly detected: {metric} (score: {score:.2f})",
                metadata={"metric": metric, "score": score, "anomaly_id": anomaly_id}
            )
            
            # Emit to Kafka
            from aiokafka import AIOKafkaProducer
            producer = AIOKafkaProducer(
                bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            await producer.start()
            try:
                await producer.send('anomalies.detected', {
                    'id': anomaly_id,
                    'service': service,
                    'metric': metric,
                    'start_ts': start_ts.isoformat(),
                    'end_ts': end_ts.isoformat(),
                    'score': score
                })
            finally:
                await producer.stop()
            
            # Group anomalies into incidents
            await self.group_and_create_incidents()
    
    async def group_and_create_incidents(self):
        """Group recent anomalies into incidents."""
        async with self.postgres_pool.acquire() as conn:
            # Get recent anomalies (last hour) that aren't in incidents yet
            # Use explicit timestamp arithmetic to avoid type issues
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            anomalies = await conn.fetch(
                """
                SELECT a.id, a.start_ts, a.end_ts, a.service, a.metric, a.score
                FROM anomalies a
                LEFT JOIN incident_anomalies ia ON a.id = ia.anomaly_id
                WHERE ia.anomaly_id IS NULL
                AND a.start_ts >= $1
                ORDER BY a.start_ts
                """,
                one_hour_ago
            )
            
            if not anomalies:
                return
            
            # Convert to dicts
            anomaly_dicts = [
                {
                    'id': str(a['id']),
                    'start_ts': a['start_ts'],
                    'end_ts': a['end_ts'],
                    'service': a['service'],
                    'metric': a['metric'],
                    'score': float(a['score'])
                }
                for a in anomalies
            ]
            
            # Group into incidents
            incidents = self.grouper.group_anomalies(anomaly_dicts)
            
            # Create incidents in Postgres
            for incident in incidents:
                # Check if incident already exists
                existing = await conn.fetchrow(
                    "SELECT id FROM incidents WHERE id = $1",
                    incident['id']
                )
                
                if existing:
                    continue
                
                # Create incident
                await conn.execute(
                    """
                    INSERT INTO incidents (id, start_ts, end_ts, title, status, summary)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    incident['id'],
                    incident['start_ts'],
                    incident['end_ts'],
                    incident['title'],
                    incident['status'],
                    None
                )
                
                # Link anomalies
                for anomaly_id in incident['anomaly_ids']:
                    await conn.execute(
                        """
                        INSERT INTO incident_anomalies (incident_id, anomaly_id)
                        VALUES ($1, $2)
                        ON CONFLICT DO NOTHING
                        """,
                        incident['id'],
                        anomaly_id
                    )
                
                logger.info(f"Created incident: {incident['id']} - {incident['title']}")
                
                # Log activity event
                affected_services = list(set(a['service'] for a in anomaly_dicts if a['id'] in incident['anomaly_ids']))
                await self.log_activity_event(
                    event_type="incident_created",
                    service=affected_services[0] if affected_services else None,
                    message=f"Incident created: {incident['title']}",
                    metadata={"incident_id": incident['id'], "affected_services": affected_services}
                )
                
                # Emit RCA request
                from aiokafka import AIOKafkaProducer
                producer = AIOKafkaProducer(
                    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
                await producer.start()
                try:
                    await producer.send('rca.requests', {
                        'incident_id': incident['id'],
                        'start_ts': incident['start_ts'].isoformat(),
                        'end_ts': incident['end_ts'].isoformat()
                    })
                finally:
                    await producer.stop()
    
    async def run(self):
        """Main run loop."""
        logger.info("Starting detector worker...")
        await self.connect()
        
        try:
            async for message in self.kafka_consumer:
                await self.process_metric_point(message.value)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await self.disconnect()


async def main():
    """Entry point."""
    worker = DetectorWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())


