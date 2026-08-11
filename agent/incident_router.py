from enum import Enum
import structlog
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from detection.watcher import IncidentEvent
from agent.correlation_engine import CorrelationEngine

logger = structlog.get_logger(__name__)

class IncidentType(Enum):
    POD_CRASH          = 'pod_crash'
    IMAGE_PULL_ERROR   = 'image_pull_error'
    OOM_KILLED         = 'oom_killed'
    PENDING_POD        = 'pending_pod'
    DEPLOYMENT_FAILURE = 'deployment_failure'
    NODE_NOT_READY     = 'node_not_ready'
    NETWORK_TIMEOUT    = 'network_timeout'
    UNKNOWN            = 'unknown'

REASON_MAP = {
    'CrashLoopBackOff': IncidentType.POD_CRASH,
    'BackOff':          IncidentType.POD_CRASH,
    'Error':            IncidentType.POD_CRASH,
    'OOMKilled':        IncidentType.OOM_KILLED,
    'ImagePullBackOff': IncidentType.IMAGE_PULL_ERROR,
    'ErrImagePull':     IncidentType.IMAGE_PULL_ERROR,
    'ContainerCannotRun': IncidentType.POD_CRASH,
    'CreateContainerError': IncidentType.POD_CRASH,
    'RunContainerError': IncidentType.POD_CRASH,
    'FailedScheduling': IncidentType.PENDING_POD,
    'NodeNotReady':     IncidentType.NODE_NOT_READY,
}

# Substring patterns for fuzzy fallback when exact REASON_MAP lookup fails.
# Ordered from most-specific to least-specific.
_FUZZY_PATTERNS: list[tuple[str, IncidentType]] = [
    ("oomkilled",            IncidentType.OOM_KILLED),
    ("imagepullbackoff",     IncidentType.IMAGE_PULL_ERROR),
    ("errimagepull",         IncidentType.IMAGE_PULL_ERROR),
    ("imagepull",            IncidentType.IMAGE_PULL_ERROR),
    ("crashloopbackoff",     IncidentType.POD_CRASH),
    ("containercannotrun",   IncidentType.POD_CRASH),
    ("runcontainererror",    IncidentType.POD_CRASH),
    ("createcontainererror", IncidentType.POD_CRASH),
    ("backoff",              IncidentType.POD_CRASH),
    ("error",                IncidentType.POD_CRASH),
    ("failedscheduling",     IncidentType.PENDING_POD),
    ("unschedulable",        IncidentType.PENDING_POD),
    ("nodenotready",         IncidentType.NODE_NOT_READY),
]


class IncidentRouter:
    def classify(self, event: IncidentEvent) -> IncidentType:
        """Public classification method for direct use and testing."""
        return self._classify_reason(event.reason)

    async def classify_and_correlate(
        self, 
        db: AsyncSession, 
        event: IncidentEvent, 
        cluster_id: str
    ) -> Tuple[IncidentType, Optional[str]]:
        """Classify incident type and attempt correlation to existing group."""
        incident_type = self._classify_reason(event.reason)
        correlation_engine = CorrelationEngine()
        correlated_group_id = await correlation_engine.correlate_incidents(
            db, 
            new_incident_id=event.pod_name + '-' + str(hash(event.reason)),  # Temp ID
            namespace=event.namespace,
            pod_name=event.pod_name,
            incident_type=incident_type.value,
            cluster_id=cluster_id
        )
        logger.info("Classification complete", type=incident_type.value, correlated=correlated_group_id)
        return incident_type, correlated_group_id

    def _classify_reason(self, reason: str) -> IncidentType:
        """Classify based on reason string (exact or fuzzy match)."""
        # 1. Exact lookup
        incident_type = REASON_MAP.get(reason)
        if incident_type is not None:
            logger.info("Classified incident (exact)", reason=reason, type=incident_type.value)
            return incident_type

        # 2. Case-insensitive substring fallback
        reason_lower = (reason or "").lower()
        for pattern, itype in _FUZZY_PATTERNS:
            if pattern in reason_lower:
                logger.info("Classified incident (fuzzy)", reason=reason, matched=pattern, type=itype.value)
                return itype

        logger.info("Classified incident (unknown)", reason=reason)
        return IncidentType.UNKNOWN

    def route(self, incident_type: IncidentType) -> str:
        return f"playbooks/{incident_type.value}.yaml"

