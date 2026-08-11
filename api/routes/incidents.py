import datetime
import uuid
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from api.schemas import AnalyzeRequest, AnalyzeResponse, IncidentSummary
from api.auth import get_current_user
from api.websocket import feed_manager
from infrastructure.evidence_collector import EvidenceCollector
from infrastructure.kubernetes_client import init_k8s_client
from infrastructure.database import get_db
from models.incident import Incident
from models.activity import Activity
# from agent.investigation import InvestigationService

router = APIRouter(tags=["incidents"])

@router.get("/incidents", response_model=list[IncidentSummary])
async def list_incidents(
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """GET /incidents -> returns list (max 50)"""
    query = select(Incident).order_by(Incident.timestamp.desc()).limit(limit)
    result = await db.execute(query)
    incidents = result.scalars().all()
    
    return [
        IncidentSummary(
            id=i.id or str(uuid.uuid4()),
            timestamp=i.timestamp or datetime.datetime.utcnow(),
            cluster_id=i.cluster_id or "unknown",
            namespace=i.namespace or "default",
            pod_name=i.pod_name or "unknown",
            incident_type=i.incident_type or "unknown",
            root_cause=i.root_cause or "unresolved",
            confidence=i.confidence or "low",
            recommended_action=i.recommended_action or "manual_investigation",
            explanation=i.explanation or "Analysis in progress",
            status=i.status or "open",
            resolution_time=i.resolution_time or 0,
            ai_used=i.ai_used or False
        ) for i in incidents
    ]

@router.get("/incident/history", response_model=list[IncidentSummary])
async def incident_history(
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Legacy alias for frontend compatibility."""
    return await list_incidents(limit, db)

@router.post("/incident/analyze", response_model=AnalyzeResponse)
async def analyze_incident(
    req: AnalyzeRequest, 
    db: AsyncSession = Depends(get_db)
):
    """POST /incident/analyze -> Trigger a full investigation."""
    from agent.investigation import investigation_service
    payload = req.dict()
    incident_data = await investigation_service.analyze_incident(payload, db)
    
    return AnalyzeResponse(
        incident_id=incident_data.get("incident_id", "unknown"),
        pod_name=req.pod_name,
        namespace=req.namespace,
        incident_type=incident_data.get("incident_type", "unknown"),
        root_cause=incident_data.get("root_cause", "unknown"),
        confidence=incident_data.get("confidence", "low"),
        recommended_action=incident_data.get("recommended_action", "manual_investigation"),
        explanation=incident_data.get("explanation", "Analysis complete"),
        status=incident_data.get("status", "error"),
        created_at=datetime.datetime.utcnow()
    )

@router.get("/incident/activity")
async def get_activity(
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Return latest activity events."""
    result = await db.execute(select(Activity).order_by(Activity.timestamp.desc()).limit(limit))
    return result.scalars().all()

@router.get("/incident/{incident_id}")
async def get_incident(
    incident_id: str, 
    db: AsyncSession = Depends(get_db)
):
    """GET /incident/{id} -> full details"""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        return {"incident_id": incident_id, "status": "not_found"}
    return incident

@router.get("/incident/{incident_id}/activity")
async def get_incident_activity(
    incident_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Return activity timeline for a specific incident."""
    result = await db.execute(
        select(Activity)
        .where(Activity.incident_id == incident_id)
        .order_by(Activity.timestamp.asc())
    )
    activities = result.scalars().all()
    return {
        "incident_id": incident_id,
        "timeline": [
            {
                "event": a.type or "unknown",
                "time": (a.timestamp or datetime.datetime.utcnow()).isoformat(),
                "message": a.message or "No message",
                "severity": a.severity or "info"
            } for a in activities
        ]
    }

