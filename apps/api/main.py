from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from contextlib import asynccontextmanager

from services.clickhouse_client import ClickHouseClient
from services.postgres_client import PostgresClient
from services.kafka_producer import KafkaProducer
from services.activity_logger import ActivityLogger
import redis.asyncio as redis


# Global clients
clickhouse_client: ClickHouseClient = None
postgres_client: PostgresClient = None
kafka_producer: KafkaProducer = None
redis_client: redis.Redis = None
activity_logger: ActivityLogger = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global clickhouse_client, postgres_client, kafka_producer, redis_client, activity_logger
    
    try:
        clickhouse_client = ClickHouseClient(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
            database=os.getenv("CLICKHOUSE_DB", "rca"),
            user=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", "")
        )
        await clickhouse_client.connect()
    except Exception as e:
        import logging
        logging.error(f"Failed to connect to ClickHouse: {e}")
        raise
    
    postgres_client = PostgresClient(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "rca"),
        user=os.getenv("POSTGRES_USER", "rca"),
        password=os.getenv("POSTGRES_PASSWORD", "rca_password")
    )
    await postgres_client.connect()
    
    kafka_producer = KafkaProducer(
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    )
    await kafka_producer.start()
    
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        decode_responses=True
    )
    await redis_client.ping()
    
    # Initialize activity logger
    activity_logger = ActivityLogger(redis_client)
    
    yield
    
    # Shutdown
    await clickhouse_client.disconnect()
    await postgres_client.disconnect()
    await kafka_producer.stop()
    await redis_client.close()


app = FastAPI(
    title="RCA System API",
    description="Production-Grade Root Cause Analysis System",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint that verifies all dependencies."""
    checks = {
        "status": "healthy",
        "checks": {}
    }
    
    # Check ClickHouse
    try:
        await clickhouse_client.execute("SELECT 1")
        checks["checks"]["clickhouse"] = "ok"
    except Exception as e:
        checks["checks"]["clickhouse"] = f"error: {str(e)}"
        checks["status"] = "unhealthy"
    
    # Check Postgres
    try:
        await postgres_client.execute("SELECT 1")
        checks["checks"]["postgres"] = "ok"
    except Exception as e:
        checks["checks"]["postgres"] = f"error: {str(e)}"
        checks["status"] = "unhealthy"
    
    # Check Redis
    try:
        await redis_client.ping()
        checks["checks"]["redis"] = "ok"
    except Exception as e:
        checks["checks"]["redis"] = f"error: {str(e)}"
        checks["status"] = "unhealthy"
    
    # Check Kafka
    try:
        # Just check if producer is initialized
        if kafka_producer and kafka_producer.producer:
            checks["checks"]["kafka"] = "ok"
        else:
            checks["checks"]["kafka"] = "not initialized"
            checks["status"] = "unhealthy"
    except Exception as e:
        checks["checks"]["kafka"] = f"error: {str(e)}"
        checks["status"] = "unhealthy"
    
    status_code = 200 if checks["status"] == "healthy" else 503
    return checks


# Import routers
from routers import ingest, incidents, services, activity
app.include_router(ingest.router, prefix="/ingest", tags=["ingestion"])
app.include_router(incidents.router, prefix="/incidents", tags=["incidents"])
app.include_router(services.router, prefix="/services", tags=["services"])
app.include_router(activity.router, prefix="/activity", tags=["activity"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

