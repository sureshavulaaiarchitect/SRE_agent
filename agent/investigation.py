import datetime
import uuid
import structlog
import asyncio
import time

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_

from agent.incident_router import IncidentRouter
from api.websocket import feed_manager
from agent.safety_guardrails import SafetyGate
from agent.pattern_layer import PatternDetectionLayer
from agent.decision_engine import decision_engine
from agent.correlation_engine import CorrelationEngine
from ai.root_cause_engine import AIRootCauseEngine
from infrastructure.evidence_collector import EvidenceCollector
from infrastructure.remediation import remediation_engine, RemediationContext

from models.incident import Incident
from detection.watcher import IncidentEvent

# Metrics
from observability.metrics_collector import (
    incidents_detected_total,
    incidents_resolved_total,
    remediation_actions_total,
    safety_gate_blocked_total,
    investigation_time_seconds,
    active_incidents,
)

logger = structlog.get_logger(__name__)


class InvestigationService:

    def __init__(self):
        self.router = IncidentRouter()
        self.correlation_engine = CorrelationEngine()
        self.safety_gate = SafetyGate()
        from notifications.slack import SlackNotifier
        self.slack = SlackNotifier()

    async def process_full_pipeline(self, event: IncidentEvent, db: AsyncSession) -> dict:
        """
        Consolidated pipeline: detect → investigate → decide → remediate → notify.
        """
        start_time = time.time()
        namespace = event.namespace
        pod_name = event.pod_name
        cluster_id = event.cluster_id
        incident_type = event.reason or "unknown"

        # 0. INPUT VALIDATION (Fix 3: Reject "string" or empty)
        invalid_values = ("string", "unknown", "", None, "null", "undefined")
        if cluster_id in invalid_values or namespace in invalid_values or pod_name in invalid_values:
            logger.warning("invalid_data_insertion", cluster=cluster_id, ns=namespace, pod=pod_name)
            return {"status": "error", "message": "Invalid or placeholder data provided"}

        # 1. DUPLICATE CHECK
        if await self._is_duplicate(db, namespace, pod_name, incident_type):
            logger.info("Duplicate incident skipped", pod=pod_name, type=incident_type)
            return {"status": "ignored", "message": "Duplicate within 5 min"}

        # 2. CREATE INCIDENT
        incident_id = str(uuid.uuid4())
        try:
            db_incident = Incident(
                id=incident_id,
                cluster_id=cluster_id,
                namespace=namespace,
                pod_name=pod_name,
                incident_type=incident_type,
                status="investigating"
            )
            db.add(db_incident)
            await db.commit()
            logger.info("Incident created", id=incident_id, pod=pod_name)
            
            # Broadcast "investigating" state immediately
            await feed_manager.broadcast({
                "incident_id": incident_id,
                "status": "investigating",
                "pod_name": pod_name,
                "namespace": namespace,
                "incident_type": incident_type,
                "created_at": datetime.datetime.utcnow().isoformat()
            })
        except Exception as e:
            await db.rollback()
            logger.error("Incident creation failed", error=str(e))
            return {"status": "error", "message": str(e)}

        # Metrics
        incidents_detected_total.labels(cluster_id=cluster_id, incident_type=incident_type).inc()
        active_incidents.labels(cluster_id=cluster_id).inc()

        try:
            # 3. EVIDENCE COLLECTION
            collector = EvidenceCollector()
            evidence = await collector.collect_full_evidence(namespace, pod_name)

            # 4. RULE ENGINE
            try:
                rule_result = PatternDetectionLayer().check(evidence.model_dump())
            except Exception as e:
                logger.error("Rule engine failed", error=str(e))
                rule_result = {}

            # 5. AI ENGINE
            try:
                ai_result = await AIRootCauseEngine().analyze(evidence)
            except Exception as e:
                logger.error("AI engine failed", error=str(e))
                ai_result = None

            # 6. DECISION
            decision = decision_engine.merge_results(rule_result, ai_result)
            action = decision.get("action") or decision.get("recommended_action") or "manual_investigation"

            logger.info("Decision made", action=action, confidence=decision.get("confidence"))

            # 7. SAFETY GATE (Pre-execution check)
            gate_context = {
                "namespace": namespace,
                "pod_name": pod_name,
                "confidence": decision.get("confidence"),
                "reason": incident_type
            }
            gate = self.safety_gate.validate(action, gate_context)

            if not gate.approved:
                action = "manual_investigation"
                final_status = "awaiting_approval"
                safety_gate_blocked_total.labels(action=action, reason=gate.reason).inc()
            else:
                final_status = "awaiting_approval" if gate.requires_human else "executing"

            # 8. UPDATE INCIDENT WITH FINDINGS
            await db.execute(
                update(Incident)
                .where(Incident.id == incident_id)
                .values(
                    root_cause=decision.get("root_cause"),
                    confidence=decision.get("confidence"),
                    recommended_action=action,
                    explanation=decision.get("explanation"),
                    status=final_status,
                    ai_used=(ai_result is not None),
                )
            )
            await db.commit()

            # 9. NOTIFICATION (Investigation result)
            response = {
                "incident_id": incident_id,
                "status": final_status,
                "pod_name": pod_name,
                "namespace": namespace,
                "root_cause": decision.get("root_cause"),
                "recommended_action": action,
                "confidence": decision.get("confidence"),
                "incident_type": incident_type,
                "explanation": decision.get("explanation")
            }
            try:
                await self.slack.send_incident_alert(response)
            except Exception as e:
                logger.error("Slack alert failed", error=str(e))
            
            await feed_manager.broadcast(response)

            # 10. REMEDIATION (if approved and safe)
            if final_status == "executing" and action:
                if action not in ("manual_investigation", "none"):
                    context = RemediationContext(pod_name=pod_name, namespace=namespace)
                    result = await remediation_engine.execute(action, context)
                    
                    # Record in safety gate history
                    self.safety_gate.record_execution(action, gate_context)
                    logger.info("Remediation executed", action=action, pod=pod_name)

                    # Update Status Post-Remediation
                    if result.success:
                        new_status = "resolved"
                        mttr = int(time.time() - start_time)
                        logger.info("remediation_success", id=incident_id, action=action, mttr=mttr)
                        
                        # Metrics
                        incidents_resolved_total.labels(cluster_id=cluster_id, incident_type=incident_type, action=action).inc()
                        remediation_actions_total.labels(action=action, result="success").inc()
                        
                        # Resolution Notification
                        try:
                            await self.slack.send_resolution_alert({**response, "action": action, "mttr_seconds": mttr})
                        except Exception as e:
                            logger.error("Slack resolution failed", error=str(e))
                    else:
                        new_status = "failed"
                        logger.warning("remediation_failed", id=incident_id, error=result.message)
                        remediation_actions_total.labels(action=action, result="failed").inc()
                    
                    resolution_t = int(time.time() - start_time) if result.success else None
                else:
                    new_status = "skipped"
                    logger.info("remediation_skipped", id=incident_id, action=action)
                    resolution_t = None

                await db.execute(
                    update(Incident).where(Incident.id == incident_id).values(status=new_status, resolution_time=resolution_t)
                )
                await db.commit()
                response["status"] = new_status
                await feed_manager.broadcast(response)

            investigation_time_seconds.labels(cluster_id=cluster_id, incident_type=incident_type).observe(time.time() - start_time)
            return response

        except Exception as e:
            logger.error("Pipeline failed", error=str(e), incident_id=incident_id)
            return {"status": "error", "message": str(e)}
        finally:
            active_incidents.labels(cluster_id=cluster_id).dec()


    async def investigate_and_save(self, namespace: str, pod_name: str, cluster_id: str, db: AsyncSession, reason: str = "unknown") -> dict:
        """Compatibility adapter for process_full_pipeline."""
        from detection.watcher import IncidentEvent
        event = IncidentEvent(namespace=namespace, pod_name=pod_name, cluster_id=cluster_id, reason=reason, timestamp=datetime.datetime.utcnow())
        return await self.process_full_pipeline(event, db)


    async def analyze_incident(self, payload: dict, db: AsyncSession) -> dict:
        """Adapter for route handlers that pass a payload dict."""
        from detection.watcher import IncidentEvent
        event = IncidentEvent(
            namespace=payload.get("namespace", "default"),
            pod_name=payload.get("pod_name", "unknown"),
            cluster_id=payload.get("cluster_id", "default"),
            reason=payload.get("reason", "unknown"),
            timestamp=datetime.datetime.utcnow()
        )
        return await self.process_full_pipeline(event, db)

    # -------------------------
    # RATE LIMIT (Legacy/Redundant but kept for safety in other calls)
    # -------------------------
    async def _check_action_limit(self, db, namespace, pod_name, action):
        from datetime import timedelta
        five_min_ago = datetime.datetime.utcnow() - timedelta(minutes=5)
        query = select(Incident).where(
            and_(
                Incident.namespace == namespace,
                Incident.pod_name == pod_name,
                Incident.recommended_action == action,
                Incident.timestamp >= five_min_ago
            )
        )
        result = await db.execute(query)
        return len(result.fetchall()) < 3

    # -------------------------
    # DUPLICATE CHECK
    # -------------------------
    async def _is_duplicate(self, db, namespace, pod_name, incident_type):
        from datetime import timedelta
        five_min_ago = datetime.datetime.utcnow() - timedelta(minutes=5)
        query = select(Incident).where(
            and_(
                Incident.namespace == namespace,
                Incident.pod_name == pod_name,
                Incident.incident_type == incident_type,
                Incident.timestamp >= five_min_ago,
                Incident.status != "resolved"
            )
        )
        result = await db.execute(query)
        return result.scalars().first() is not None


# Singleton
investigation_service = InvestigationService()
