from aiokafka import AIOKafkaProducer
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class KafkaProducer:
    """Async Kafka producer wrapper."""
    
    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self.producer: AIOKafkaProducer = None
    
    async def start(self):
        """Initialize the Kafka producer."""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.producer.start()
        logger.info(f"Kafka producer started, connected to {self.bootstrap_servers}")
    
    async def send(self, topic: str, value: Dict[str, Any], key: str = None):
        """Send a message to a topic."""
        if not self.producer:
            raise RuntimeError("Kafka producer not started")
        
        try:
            await self.producer.send_and_wait(topic, value, key=key.encode('utf-8') if key else None)
        except Exception as e:
            logger.error(f"Failed to send message to {topic}: {e}")
            raise
    
    async def stop(self):
        """Stop the producer."""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")


