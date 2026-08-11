import asyncio
import structlog
import uvicorn
import subprocess
import time
from typing import Optional, Set

from api.app import app
from infrastructure.kubernetes_client import init_k8s_client
from detection.watcher import IncidentDetectionService, IncidentEvent
from notifications.slack import SlackNotifier
from infrastructure.database import SessionLocal, engine
from models import Base
from configs.config import settings
from infrastructure.remediation import remediation_engine, RemediationContext
from observability.metrics_collector import (
    incidents_detected_total,
    incidents_resolved_total,
    active_incidents,
    remediation_success_rate,
    investigation_time_seconds,
    remediation_actions_total,
    safety_gate_blocked_total,
    errors_total
)
from sqlalchemy import select
from models.incident import Incident
from agent.safety_guardrails import safety_gate

# Configuration for structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Incident Deduplication Cache (Global)
processed_incidents: Set[str] = set()
DEDUPE_TTL = 300 # 5 minutes

# -------------------------
# INCIDENT PROCESSING PIPELINE
# -------------------------
async def process_incident(event: IncidentEvent):
    """
    Full pipeline entry point.
    """
    from agent.investigation import investigation_service

    # Deduplication check (Quick check before DB)
    dedupe_key = f"{event.cluster_id}:{event.namespace}:{event.pod_name}:{event.reason}"
    if dedupe_key in processed_incidents:
        logger.info("Incident deduplicated (cache)", key=dedupe_key)
        return

    processed_incidents.add(dedupe_key)
    async def cleanup_dedupe():
        await asyncio.sleep(DEDUPE_TTL)
        processed_incidents.discard(dedupe_key)
    asyncio.create_task(cleanup_dedupe())

    try:
        async with SessionLocal() as db:
            await investigation_service.process_full_pipeline(event, db)
    except Exception as e:
        logger.error("Global pipeline failure", error=str(e), pod=event.pod_name)
    finally:
        # active_incidents dec is handled inside process_full_pipeline
        pass

# -------------------------
# CLUSTER LOOP
# -------------------------
async def create_cluster_loop(cluster_id: str):
    queue: asyncio.Queue[IncidentEvent] = asyncio.Queue(maxsize=100)
    detector = IncidentDetectionService(queue, cluster_id)
    asyncio.create_task(detector.start())

    logger.info("SRE Agent watching cluster", cluster_id=cluster_id)
    semaphore = asyncio.Semaphore(5)

    while True:
        event = await queue.get()
        # Rate limiting: wait 0.5s between processing starts to avoid bursts
        await asyncio.sleep(0.5)

        async def limited_process():
            try:
                async with semaphore:
                    await process_incident(event)
            except Exception as e:
                logger.error("Worker failed", error=str(e))
            finally:
                queue.task_done()

        asyncio.create_task(limited_process())

async def get_current_cluster() -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            'kubectl', 'config', 'current-context',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return stdout.decode().strip()
    except Exception:
        pass
    return "local-dev-cluster"

async def incident_loops():
    cluster_id = await get_current_cluster()
    await create_cluster_loop(cluster_id)

async def start_api():
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="error") # Only error logs for uvicorn, we use structlog
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    init_k8s_client()
    
    # DB INIT with Retry
    retries = 5
    while retries > 0:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database ready")
            break
        except Exception as e:
            retries -= 1
            logger.warning("Database connection failed", error=str(e), retries_left=retries)
            await asyncio.sleep(5)

    if retries == 0:
        logger.error("Database initialization failed")
        return

    logger.info("Starting Kubernetes SRE Agent hardening v2", cluster=settings.CURRENT_CLUSTER_ID)

    try:
        await asyncio.gather(incident_loops(), start_api())
    except asyncio.CancelledError:
        logger.info("Graceful shutdown initiated")

if __name__ == "__main__":
    asyncio.run(main())
