from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

import main

router = APIRouter()


@router.get("")
async def list_services():
    """List all services."""
    try:
        rows = await main.clickhouse_client.execute(
            "SELECT DISTINCT service FROM metrics_timeseries ORDER BY service"
        )
        services = [row[0] for row in rows]
        return {"services": services}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list services: {str(e)}")


@router.get("/metrics")
async def list_metrics(service: Optional[str] = Query(None)):
    """List metrics, optionally filtered by service."""
    try:
        if service:
            rows = await main.clickhouse_client.execute(
                f"SELECT DISTINCT metric FROM metrics_timeseries WHERE service = '{service}' ORDER BY metric"
            )
        else:
            rows = await main.clickhouse_client.execute(
                "SELECT DISTINCT metric FROM metrics_timeseries ORDER BY metric"
            )
        
        metrics = [row[0] for row in rows]
        return {"metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list metrics: {str(e)}")


@router.get("/metrics/latest")
async def get_latest_metric(
    service: str = Query(..., description="Service name"),
    metric: str = Query(..., description="Metric name")
):
    """Get the latest value for a specific metric from a service."""
    try:
        query = f"""
            SELECT ts, value 
            FROM metrics_timeseries 
            WHERE service = '{service}' 
              AND metric = '{metric}' 
            ORDER BY ts DESC 
            LIMIT 1
        """
        rows = await main.clickhouse_client.execute(query)
        
        if not rows:
            return {"value": None, "ts": None}
        
        ts, value = rows[0]
        return {"value": value, "ts": ts.isoformat() if hasattr(ts, 'isoformat') else str(ts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get latest metric: {str(e)}")

