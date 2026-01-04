from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime
import json

import main

router = APIRouter()


@router.get("")
async def list_incidents(status: Optional[str] = Query(None, description="Filter by status: OPEN or CLOSED")):
    """List incidents, optionally filtered by status."""
    try:
        if status:
            rows = await main.postgres_client.fetch(
                "SELECT id, start_ts, end_ts, title, status, summary FROM incidents WHERE status = $1 ORDER BY start_ts DESC LIMIT 250",
                status
            )
        else:
            rows = await main.postgres_client.fetch(
                "SELECT id, start_ts, end_ts, title, status, summary FROM incidents ORDER BY start_ts DESC LIMIT 250"
            )
        
        incidents = []
        for row in rows:
            incidents.append({
                "id": str(row["id"]),
                "start_ts": row["start_ts"].isoformat(),
                "end_ts": row["end_ts"].isoformat() if row["end_ts"] else None,
                "title": row["title"],
                "status": row["status"],
                "summary": row["summary"]
            })
        
        return {"incidents": incidents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list incidents: {str(e)}")


@router.get("/{incident_id}")
async def get_incident(incident_id: str):
    """Get incident details."""
    try:
        row = await main.postgres_client.fetchrow(
            "SELECT id, start_ts, end_ts, title, status, summary FROM incidents WHERE id = $1",
            incident_id
        )
        
        if not row:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        return {
            "id": str(row["id"]),
            "start_ts": row["start_ts"].isoformat(),
            "end_ts": row["end_ts"].isoformat() if row["end_ts"] else None,
            "title": row["title"],
            "status": row["status"],
            "summary": row["summary"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get incident: {str(e)}")


@router.get("/{incident_id}/anomalies")
async def get_incident_anomalies(incident_id: str):
    """Get anomalies for an incident."""
    try:
        rows = await main.postgres_client.fetch(
            """
            SELECT a.id, a.start_ts, a.end_ts, a.service, a.metric, a.score, a.detector, a.details
            FROM incidents i
            JOIN incident_anomalies ia ON i.id = ia.incident_id
            JOIN anomalies a ON ia.anomaly_id = a.id
            WHERE i.id = $1
            ORDER BY a.start_ts
            """,
            incident_id
        )
        
        anomalies = []
        for row in rows:
            anomalies.append({
                "id": str(row["id"]),
                "start_ts": row["start_ts"].isoformat(),
                "end_ts": row["end_ts"].isoformat(),
                "service": row["service"],
                "metric": row["metric"],
                "score": float(row["score"]),
                "detector": row["detector"],
                "details": row["details"] if row["details"] else {}
            })
        
        return {"anomalies": anomalies}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get anomalies: {str(e)}")


@router.get("/{incident_id}/suspects")
async def get_incident_suspects(incident_id: str):
    """Get ranked suspects for an incident."""
    try:
        rows = await main.postgres_client.fetch(
            """
            SELECT id, suspect_type, suspect_key, rank, score, evidence
            FROM suspects
            WHERE incident_id = $1
            ORDER BY rank
            """,
            incident_id
        )
        
        suspects = []
        for row in rows:
            evidence = row["evidence"] if row["evidence"] else {}
            if isinstance(evidence, str):
                evidence = json.loads(evidence)
            
            suspects.append({
                "id": str(row["id"]),
                "suspect_type": row["suspect_type"],
                "suspect_key": row["suspect_key"],
                "rank": row["rank"],
                "score": float(row["score"]),
                "evidence": evidence
            })
        
        return {"suspects": suspects}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get suspects: {str(e)}")


@router.post("/{incident_id}/label")
async def label_suspect(
    incident_id: str,
    suspect_id: str,
    label: int = Query(..., description="1 for true cause, 0 for not cause"),
    labeler: Optional[str] = Query(None),
    notes: Optional[str] = Query(None)
):
    """Provide human feedback on a suspect."""
    try:
        # Check if incident and suspect exist
        incident = await main.postgres_client.fetchrow(
            "SELECT id FROM incidents WHERE id = $1",
            incident_id
        )
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        suspect = await main.postgres_client.fetchrow(
            "SELECT id FROM suspects WHERE id = $1 AND incident_id = $2",
            suspect_id, incident_id
        )
        if not suspect:
            raise HTTPException(status_code=404, detail="Suspect not found")
        
        # Check if label already exists
        existing_label = await main.postgres_client.fetchrow(
            """
            SELECT id, label FROM labels 
            WHERE incident_id = $1 AND suspect_id = $2
            ORDER BY created_at DESC
            LIMIT 1
            """,
            incident_id, suspect_id
        )
        
        if existing_label:
            # Update existing label
            await main.postgres_client.execute(
                """
                UPDATE labels 
                SET label = $1, labeler = $2, notes = $3, created_at = now()
                WHERE id = $4
                """,
                label, labeler, notes, existing_label['id']
            )
            return {"status": "ok", "message": "Label updated"}
        else:
            # Insert new label
            await main.postgres_client.execute(
                """
                INSERT INTO labels (incident_id, suspect_id, label, labeler, notes)
                VALUES ($1, $2, $3, $4, $5)
                """,
                incident_id, suspect_id, label, labeler, notes
            )
            return {"status": "ok", "message": "Label recorded"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record label: {str(e)}")


@router.get("/{incident_id}/status")
async def get_incident_status(incident_id: str):
    """Get RCA status for an incident."""
    try:
        # Check if incident exists
        incident = await main.postgres_client.fetchrow(
            "SELECT id, start_ts FROM incidents WHERE id = $1",
            incident_id
        )
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Get suspect count
        suspect_count_row = await main.postgres_client.fetchrow(
            "SELECT COUNT(*) as count FROM suspects WHERE incident_id = $1",
            incident_id
        )
        suspect_count = suspect_count_row['count'] if suspect_count_row else 0
        
        # Determine RCA status
        if suspect_count == 0:
            rca_status = "not_started"
        else:
            # Check if suspects were recently updated (within last 30 seconds)
            recent_suspect = await main.postgres_client.fetchrow(
                """
                SELECT id FROM suspects 
                WHERE incident_id = $1 
                ORDER BY id DESC 
                LIMIT 1
                """,
                incident_id
            )
            # For now, if suspects exist, consider it completed
            # In a more sophisticated system, we could check if RCA is still running
            rca_status = "completed"
        
        # Get last updated timestamp (from most recent suspect or incident creation)
        if suspect_count > 0:
            last_suspect = await main.postgres_client.fetchrow(
                """
                SELECT id FROM suspects 
                WHERE incident_id = $1 
                ORDER BY id DESC 
                LIMIT 1
                """,
                incident_id
            )
            # Use current time as approximation (we don't track suspect creation time separately)
            last_updated = datetime.utcnow()
        else:
            last_updated = incident['start_ts']
        
        return {
            "incident_id": incident_id,
            "rca_status": rca_status,
            "suspects_count": suspect_count,
            "last_updated": last_updated.isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get incident status: {str(e)}")


@router.post("/{incident_id}/rerun_rca")
async def rerun_rca(incident_id: str):
    """Trigger RCA rerun for an incident."""
    try:
        # Get incident details
        incident = await main.postgres_client.fetchrow(
            "SELECT id, start_ts, end_ts FROM incidents WHERE id = $1",
            incident_id
        )
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        # Emit RCA request to Kafka
        await main.kafka_producer.send('rca.requests', {
            'incident_id': str(incident['id']),
            'start_ts': incident['start_ts'].isoformat(),
            'end_ts': incident['end_ts'].isoformat() if incident['end_ts'] else datetime.utcnow().isoformat()
        })
        
        return {"status": "ok", "message": "RCA rerun triggered"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger RCA rerun: {str(e)}")


