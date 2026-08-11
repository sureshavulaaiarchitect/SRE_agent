import httpx
import structlog
from configs.config import settings
from string import Template

logger = structlog.get_logger(__name__)

def _render_template(template_obj: dict, values: dict) -> dict:
    """Recursively substitute {{ key }} placeholders in a block kit template."""
    import json
    
    # Ensure all required keys have at least a default value to avoid unrendered templates
    defaults = {
        "pod_name": "unknown-pod",
        "namespace": "unknown-namespace",
        "incident_type": "unknown-incident",
        "confidence": "low",
        "root_cause": "Unknown",
        "recommended_action": "manual_investigation",
        "incident_id": "none",
        "action": "none",
        "mttr_seconds": "0",
        "explanation": "No explanation provided"
    }
    render_values = {**defaults, **values}
    
    raw = json.dumps(template_obj)
    for k, v in render_values.items():
        placeholder = "{{ " + str(k) + " }}"
        # Robust replacement: convert to string and handle JSON escaping if needed
        val_str = str(v).replace('"', '\\"').replace('\n', '\\n') if v is not None else "N/A"
        raw = raw.replace(placeholder, val_str)
    
    # Final check: if any {{ }} remain, it's a bug or missing key
    if "{{" in raw:
        logger.warning("Template contains unrendered placeholders", raw=raw[raw.find("{{"):raw.find("{{")+50])
        
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("Template rendering produced invalid JSON", error=str(e), raw=raw[:200])
        return {"text": "Error rendering template"}

INCIDENT_ALERT_TEMPLATE = {
    "blocks": [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": ":rotating_light:  SRE Agent — Incident Detected"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": "*Pod:*\n{{ pod_name }}"},
                {"type": "mrkdwn", "text": "*Namespace:*\n{{ namespace }}"},
                {"type": "mrkdwn", "text": "*Incident Type:*\n{{ incident_type }}"},
                {"type": "mrkdwn", "text": "*Confidence:*\n{{ confidence }}"},
            ]
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Root Cause:*\n{{ root_cause }}"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Proposed Fix:*\n`{{ recommended_action }}`"}
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":white_check_mark:  Approve"},
                    "style": "primary",
                    "action_id": "approve_fix",
                    "value": "{{ incident_id }}"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":x:  Reject"},
                    "style": "danger",
                    "action_id": "reject_fix",
                    "value": "{{ incident_id }}"
                }
            ]
        }
    ]
}

RESOLUTION_TEMPLATE = {
    "blocks": [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": ":white_check_mark:  SRE Agent — Incident Resolved"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": "*Pod:*\n{{ pod_name }}"},
                {"type": "mrkdwn", "text": "*Namespace:*\n{{ namespace }}"},
                {"type": "mrkdwn", "text": "*Action Taken:*\n`{{ action }}`"},
                {"type": "mrkdwn", "text": "*MTTR:*\n{{ mttr_seconds }}s"},
            ]
        }
    ]
}

class SlackNotifier:
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or settings.SLACK_WEBHOOK_URL

    async def send_incident_alert(self, incident_data: dict):
        """Send incident detected notification with Approve/Reject buttons."""
        if not self.webhook_url:
            logger.warning("SLACK_WEBHOOK_URL not configured — skipping notification")
            return
        payload = _render_template(INCIDENT_ALERT_TEMPLATE, incident_data)
        await self._post(payload)

    async def send_resolution_alert(self, incident_data: dict):
        """Send incident resolved notification."""
        if not self.webhook_url:
            return
        payload = _render_template(RESOLUTION_TEMPLATE, incident_data)
        await self._post(payload)

    async def _post(self, payload: dict):
        import asyncio
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=10.0) as http:
                    response = await http.post(self.webhook_url, json=payload)
                    if response.status_code == 200:
                        logger.info("Slack notification sent")
                        return
                    logger.error("Slack notification failed", status=response.status_code, body=response.text)
            except Exception as e:
                logger.error("Slack post exception", error=str(e), attempt=attempt+1)
            
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                await asyncio.sleep(wait)
        
        logger.error("Slack notification failed after all retries")
