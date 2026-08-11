import asyncio
import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from api.schemas import ApproveRequest, ApproveResponse
from api.auth import require_role
from infrastructure.database import get_db
from models.incident import Incident
from models.activity import Activity
from agent.safety_guardrails import safety_gate
from infrastructure.remediation import remediation_engine, RemediationContext
from infrastructure.validation import validation_engine
from api.websocket import feed_manager
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/incident", tags=["approvals"])

# Removed local instantiations in favor of singletons

@router.post("/{incident_id}/approve", response_model=ApproveResponse)
async def approve_incident(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin", "operator"))
):
    """
    Approve an incident remediation.
    Transitions state to executing, runs remediation, and updates status.
    """
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident.status != "awaiting_approval":
        raise HTTPException(status_code=400, detail=f"Invalid state: {incident.status}. Must be 'awaiting_approval'")

    # Transition to executing
    incident.status = "executing"
    await db.commit()

    # Create Activity for execution
    db.add(Activity(
        type="remediation",
        message=f"Remediation approved by {user.get('username')}: {incident.recommended_action}",
        severity="high",
        incident_id=incident_id
    ))
    await db.commit()

    # Broadcast state transition to "executing"
    await feed_manager.broadcast({
        "incident_id": incident_id,
        "status": "executing",
        "pod_name": incident.pod_name,
        "namespace": incident.namespace,
        "recommended_action": incident.recommended_action
    })

    # Execute remediation
    from infrastructure.remediation import remediation_engine, RemediationContext
    ctx = RemediationContext(
        pod_name=incident.pod_name,
        namespace=incident.namespace
    )

    rem_result = await remediation_engine.execute(incident.recommended_action, ctx)

    # Validate recovery
    from infrastructure.validation import validation_engine
    
    # Give K8s a few seconds to start the new pod before validating
    await asyncio.sleep(5)
    
    validation = await validation_engine.validate_pod_recovery(
        namespace=incident.namespace, pod_name=incident.pod_name
    )

    incident.status = "resolved" if validation.success else "failed"
    if validation.success:
        diff = datetime.datetime.utcnow() - incident.timestamp
        try:
            incident.resolution_time = int(diff.total_seconds())
        except Exception:
            incident.resolution_time = 0
    
    await db.commit()

    # Broadcast final state transition
    await feed_manager.broadcast({
        "incident_id": incident_id,
        "status": incident.status,
        "pod_name": incident.pod_name,
        "namespace": incident.namespace,
        "resolution_time": incident.resolution_time if incident.status == "resolved" else None
    })

    return ApproveResponse(
        incident_id=incident_id,
        execution_status="success" if rem_result.success else "failed",
        validation_result="recovered" if validation.success else "not_recovered",
        message=rem_result.message or ("Remediation successful" if rem_result.success else "Remediation failed"),
        recommended_action=incident.recommended_action,
        namespace=incident.namespace,
        pod_name=incident.pod_name
    )
