import asyncpg
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class PostgresClient:
    """Async Postgres client wrapper."""
    
    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.pool: asyncpg.Pool = None
    
    async def connect(self):
        """Create connection pool."""
        self.pool = await asyncpg.create_pool(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
            min_size=2,
            max_size=10
        )
        logger.info(f"Connected to Postgres at {self.host}:{self.port}")
    
    async def execute(self, query: str, *args):
        """Execute a query."""
        if not self.pool:
            raise RuntimeError("Postgres pool not connected")
        
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        """Fetch rows."""
        if not self.pool:
            raise RuntimeError("Postgres pool not connected")
        
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Fetch a single row."""
        if not self.pool:
            raise RuntimeError("Postgres pool not connected")
        
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def disconnect(self):
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Disconnected from Postgres")


