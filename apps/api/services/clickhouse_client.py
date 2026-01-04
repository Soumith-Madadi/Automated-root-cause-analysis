from clickhouse_driver import Client
from clickhouse_driver.errors import Error
import asyncio
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ClickHouseClient:
    """Async wrapper for ClickHouse client."""
    
    def __init__(self, host: str, port: int, database: str, user: str = "default", password: str = ""):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.client: Client = None
        self._executor = None
    
    async def connect(self):
        """Initialize the ClickHouse client."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._create_client)
        logger.info(f"Connected to ClickHouse at {self.host}:{self.port}")
    
    def _create_client(self):
        """Create synchronous ClickHouse client."""
        client_params = {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "settings": {'use_numpy': False}
        }
        # Only add user/password if explicitly provided (not empty strings)
        if self.user and self.user != "default":
            client_params["user"] = self.user
        if self.password:
            client_params["password"] = self.password
        self.client = Client(**client_params)
    
    async def execute(self, query: str, params: Dict[str, Any] = None):
        """Execute a query asynchronously."""
        if not self.client:
            raise RuntimeError("ClickHouse client not connected")
        
        loop = asyncio.get_event_loop()
        if params:
            return await loop.run_in_executor(
                None, 
                lambda: self.client.execute(query, params)
            )
        else:
            return await loop.run_in_executor(
                None,
                lambda: self.client.execute(query)
            )
    
    async def insert(self, table: str, data: List[Dict[str, Any]]):
        """Insert data into a table."""
        if not data:
            return
        
        if not self.client:
            raise RuntimeError("ClickHouse client not connected")
        
        # Convert dictionaries to tuples in column order
        # ClickHouse driver expects tuples, not dictionaries
        if table == 'metrics_timeseries':
            rows = [
                (row['ts'], row['service'], row['metric'], row['value'], row.get('tags', {}))
                for row in data
            ]
        elif table == 'logs':
            rows = [
                (row['ts'], row['service'], row['level'], row.get('event', ''), 
                 row['message'], row.get('fields', {}), row.get('trace_id', ''))
                for row in data
            ]
        else:
            # Generic fallback: convert dict to tuple in key order
            if data:
                keys = list(data[0].keys())
                rows = [tuple(row[k] for k in keys) for row in data]
            else:
                rows = []
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.client.execute(f"INSERT INTO {self.database}.{table} VALUES", rows)
        )
    
    async def disconnect(self):
        """Close the connection."""
        if self.client:
            self.client.disconnect()
            logger.info("Disconnected from ClickHouse")


