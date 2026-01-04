from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid
import json
import logging

import main

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models for request validation
class MetricPoint(BaseModel):
    ts: str  # ISO format datetime
    service: str
    metric: str
    value: float
    tags: Dict[str, str] = Field(default_factory=dict)


class MetricsIngestRequest(BaseModel):
    points: List[MetricPoint]


class LogEntry(BaseModel):
    ts: str
    service: str
    level: str
    event: Optional[str] = None
    message: str
    fields: Dict[str, str] = Field(default_factory=dict)
    trace_id: Optional[str] = None


class LogsIngestRequest(BaseModel):
    entries: List[LogEntry]


class DeploymentIngestRequest(BaseModel):
    ts: str
    service: str
    commit_sha: str
    version: Optional[str] = None
    author: Optional[str] = None
    diff_summary: Optional[str] = None
    links: Optional[Dict[str, str]] = None


class ConfigChangeIngestRequest(BaseModel):
    ts: str
    service: str
    key: str
    old_value_hash: Optional[str] = None
    new_value_hash: Optional[str] = None
    diff_summary: Optional[str] = None
    source: Optional[str] = None


class FlagChangeIngestRequest(BaseModel):
    ts: str
    flag_name: str
    service: Optional[str] = None
    old_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None


@router.post("/metrics")
async def ingest_metrics(request: MetricsIngestRequest):
    """Ingest metrics points into ClickHouse and publish to Kafka."""
    if not request.points:
        raise HTTPException(status_code=400, detail="No points provided")
    
    try:
        # Prepare data for ClickHouse
        clickhouse_data = []
        for point in request.points:
            ts = datetime.fromisoformat(point.ts.replace('Z', '+00:00'))
            clickhouse_data.append({
                'ts': ts,
                'service': point.service,
                'metric': point.metric,
                'value': point.value,
                'tags': point.tags
            })
        
        # Insert into ClickHouse
        await main.clickhouse_client.insert('metrics_timeseries', clickhouse_data)
        
        # Publish to Kafka
        for point in request.points:
            await main.kafka_producer.send('metrics.raw', {
                'ts': point.ts,
                'service': point.service,
                'metric': point.metric,
                'value': point.value,
                'tags': point.tags
            })
        
        # Log activity event (batched, every 10+ points)
        if len(request.points) >= 10 and main.activity_logger:
            services = list(set(p.service for p in request.points))
            await main.activity_logger.log_event(
                event_type="metrics_ingested",
                service=services[0] if len(services) == 1 else None,
                message=f"Ingested {len(request.points)} metric points",
                metadata={"count": len(request.points), "services": services}
            )
        
        return {"status": "ok", "count": len(request.points)}
    except Exception as e:
        logger.exception(f"Failed to ingest metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest metrics: {str(e)}")


@router.post("/logs")
async def ingest_logs(request: LogsIngestRequest):
    """Ingest log entries into ClickHouse and publish to Kafka."""
    if not request.entries:
        raise HTTPException(status_code=400, detail="No entries provided")
    
    try:
        # Prepare data for ClickHouse
        clickhouse_data = []
        for entry in request.entries:
            ts = datetime.fromisoformat(entry.ts.replace('Z', '+00:00'))
            clickhouse_data.append({
                'ts': ts,
                'service': entry.service,
                'level': entry.level,
                'event': entry.event or '',
                'message': entry.message,
                'fields': entry.fields,
                'trace_id': entry.trace_id or ''
            })
        
        # Insert into ClickHouse
        await main.clickhouse_client.insert('logs', clickhouse_data)
        
        # Publish to Kafka
        for entry in request.entries:
            await main.kafka_producer.send('logs.raw', {
                'ts': entry.ts,
                'service': entry.service,
                'level': entry.level,
                'event': entry.event,
                'message': entry.message,
                'fields': entry.fields,
                'trace_id': entry.trace_id
            })
        
        return {"status": "ok", "count": len(request.entries)}
    except Exception as e:
        logger.exception(f"Failed to ingest logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest logs: {str(e)}")


@router.post("/deployments")
async def ingest_deployments(request: DeploymentIngestRequest):
    """Ingest deployment events into Postgres and publish to Kafka."""
    try:
        ts = datetime.fromisoformat(request.ts.replace('Z', '+00:00'))
        deployment_id = str(uuid.uuid4())
        
        # Insert into Postgres
        await main.postgres_client.execute(
            """
            INSERT INTO deployments (id, ts, service, commit_sha, version, author, diff_summary, links)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            deployment_id,
            ts,
            request.service,
            request.commit_sha,
            request.version,
            request.author,
            request.diff_summary,
            json.dumps(request.links) if request.links else None
        )
        
        # Publish to Kafka
        await main.kafka_producer.send('deployments.raw', {
            'id': deployment_id,
            'ts': request.ts,
            'service': request.service,
            'commit_sha': request.commit_sha,
            'version': request.version,
            'author': request.author,
            'diff_summary': request.diff_summary,
            'links': request.links
        })
        
        return {"status": "ok", "id": deployment_id}
    except Exception as e:
        logger.exception(f"Failed to ingest deployment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest deployment: {str(e)}")


@router.post("/config_changes")
async def ingest_config_changes(request: ConfigChangeIngestRequest):
    """Ingest config changes into Postgres and publish to Kafka."""
    try:
        ts = datetime.fromisoformat(request.ts.replace('Z', '+00:00'))
        config_id = str(uuid.uuid4())
        
        # Insert into Postgres
        await main.postgres_client.execute(
            """
            INSERT INTO config_changes (id, ts, service, key, old_value_hash, new_value_hash, diff_summary, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            config_id,
            ts,
            request.service,
            request.key,
            request.old_value_hash,
            request.new_value_hash,
            request.diff_summary,
            request.source
        )
        
        # Publish to Kafka
        await main.kafka_producer.send('config.raw', {
            'id': config_id,
            'ts': request.ts,
            'service': request.service,
            'key': request.key,
            'old_value_hash': request.old_value_hash,
            'new_value_hash': request.new_value_hash,
            'diff_summary': request.diff_summary,
            'source': request.source
        })
        
        return {"status": "ok", "id": config_id}
    except Exception as e:
        logger.exception(f"Failed to ingest config change: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest config change: {str(e)}")


@router.post("/flag_changes")
async def ingest_flag_changes(request: FlagChangeIngestRequest):
    """Ingest feature flag changes into Postgres and publish to Kafka."""
    try:
        ts = datetime.fromisoformat(request.ts.replace('Z', '+00:00'))
        flag_id = str(uuid.uuid4())
        
        # Insert into Postgres
        await main.postgres_client.execute(
            """
            INSERT INTO feature_flag_changes (id, ts, flag_name, service, old_state, new_state)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            flag_id,
            ts,
            request.flag_name,
            request.service,
            json.dumps(request.old_state) if request.old_state else None,
            json.dumps(request.new_state) if request.new_state else None
        )
        
        # Publish to Kafka
        await main.kafka_producer.send('flags.raw', {
            'id': flag_id,
            'ts': request.ts,
            'flag_name': request.flag_name,
            'service': request.service,
            'old_state': request.old_state,
            'new_state': request.new_state
        })
        
        return {"status": "ok", "id": flag_id}
    except Exception as e:
        logger.exception(f"Failed to ingest flag change: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest flag change: {str(e)}")


