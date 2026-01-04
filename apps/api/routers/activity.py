"""Activity log API endpoints."""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timezone, timedelta

import main

router = APIRouter()


@router.get("/events")
async def get_events(
    since: Optional[str] = Query(None, description="ISO timestamp to get events since"),
    limit: int = Query(250, description="Maximum number of events to return"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    service: Optional[str] = Query(None, description="Filter by service")
):
    """Get system events (activity log)."""
    try:
        if not main.activity_logger:
            raise HTTPException(status_code=503, detail="Activity logger not initialized")
        
        # Parse since timestamp
        since_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid timestamp format. Use ISO format.")
        
        events = await main.activity_logger.get_events(
            since=since_dt,
            limit=limit,
            event_type=event_type,
            service=service
        )
        
        return {"events": events, "count": len(events)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get events: {str(e)}")


@router.get("/events/recent")
async def get_recent_events(limit: int = Query(50, description="Maximum number of events to return")):
    """Get most recent system events."""
    try:
        if not main.activity_logger:
            raise HTTPException(status_code=503, detail="Activity logger not initialized")
        
        events = await main.activity_logger.get_recent_events(limit=limit)
        
        return {"events": events, "count": len(events)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recent events: {str(e)}")
