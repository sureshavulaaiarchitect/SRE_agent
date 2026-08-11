import httpx
import os
import structlog
from configs.config import settings

logger = structlog.get_logger(__name__)

PAGERDUTY_API_URL = "https://api.pagerduty.com/incidents"

class PagerDutyNotifier:
    def __init__(self):
        self.api_key     = settings.PAGERDUTY_API_KEY
        self.service_id  = settings.PAGERDUTY_SERVICE_ID
        self.from_email  = settings.PAGERDUTY_FROM_EMAIL

    async def create_incident(self, incident: dict):
        """Create a PagerDuty incident for high-severity failures."""
        if not self.api_key:
            logger.warning("PAGERDUTY_API_KEY not set — skipping PagerDuty notification")
            return
        
        payload = {
            "incident": {
                "type": "incident",
                "title": f"SRE Agent: {incident.get('incident_type','unknown')} on {incident.get('pod_name','?')}",
                "service": {"id": self.service_id, "type": "service_reference"},
                "body": {
                    "type": "incident_body",
                    "details": f"Root Cause: {incident.get('root_cause','?')}\nRecommended: {incident.get('recommended_action','?')}"
                }
            }
        }
        headers = {
            "Authorization": f"Token token={self.api_key}",
            "Accept": "application/vnd.pagerduty+json;version=2",
            "From": self.from_email
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(PAGERDUTY_API_URL, json=payload, headers=headers)
            if response.status_code in (200, 201):
                logger.info("PagerDuty incident created")
            else:
                logger.error("PagerDuty create failed", status=response.status_code)

    async def resolve_incident(self, pd_incident_id: str):
        """Auto-resolve a PagerDuty incident after successful remediation."""
        if not self.api_key:
            return

        payload = {"incident": {"type": "incident", "status": "resolved"}}
        headers = {
            "Authorization": f"Token token={self.api_key}",
            "Accept": "application/vnd.pagerduty+json;version=2",
            "From": self.from_email
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.put(f"{PAGERDUTY_API_URL}/{pd_incident_id}", json=payload, headers=headers)
            if response.status_code == 200:
                logger.info("PagerDuty incident resolved", pd_incident_id=pd_incident_id)
            else:
                logger.error("PagerDuty resolve failed", status=response.status_code)
