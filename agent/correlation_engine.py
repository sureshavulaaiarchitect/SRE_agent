import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from models.incident import Incident
import structlog

logger = structlog.get_logger(__name__)

class CorrelationEngine:
    """Groups related incidents into service-level incidents for SRE correlation."""

    async def correlate_incidents(
        self, 
        db: AsyncSession, 
        new_incident_id: str,
        namespace: str,
        pod_name: str,
        incident_type: str,
        cluster_id: str,
        time_window_minutes: int = 10
    ) -> Optional[str]:
        """
        Check if new incident correlates with recent open incidents.
        
        Correlation rules:
        - Same namespace/service (owner_ref or pod prefix)
        - Same cluster
        - Within time window
        - Similar types (crash/OOM/network)
        - Open status (investigating/awaiting)
        
        Returns correlated_group_id or None (standalone).
        """
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=time_window_minutes)
        
        # Query recent open incidents in same namespace
        query = select(Incident).where(
            and_(
                Incident.namespace == namespace,
                Incident.cluster_id == cluster_id,
                Incident.status.in_(['investigating', 'awaiting_approval']),
                Incident.timestamp >= window_start,
                Incident.id != new_incident_id
            )
        ).order_by(Incident.timestamp.desc()).limit(5)
        
        result = await db.execute(query)
        candidates = result.scalars().all()
        
        for candidate in candidates:
            # Service correlation: same deployment/owner or pod prefix match
            service_match = (
                candidate.pod_name.startswith(pod_name.split('-')[0]) or
                pod_name.startswith(candidate.pod_name.split('-')[0])
            )
            
            # Type similarity groups
            crash_types = {'pod_crash', 'oom_killed', 'deployment_failure'}
            network_types = {'network_timeout'}
            
            type_related = (
                incident_type in crash_types and candidate.incident_type in crash_types or
                incident_type == candidate.incident_type
            )
            
            if service_match and type_related:
                logger.info(
                    "Correlated incident to group",
                    new_id=new_incident_id,
                    group_id=candidate.correlated_group_id or candidate.id,
                    service_match=service_match,
                    type_related=type_related
                )
                return candidate.correlated_group_id or candidate.id
        
        logger.info("Standalone incident", incident_id=new_incident_id)
        return None

    async def update_correlation_group(self, db: AsyncSession, group_id: str):
        """Update group metadata (count, severity)."""
        result = await db.execute(
            select(func.count(Incident.id)).where(
                and_(
                    Incident.correlated_group_id == group_id,
                    Incident.status.notin_(['resolved', 'closed_no_action'])
                )
            )
        )
        count = result.scalar_one()
        logger.info("Correlation group updated", group_id=group_id, active_count=count)

