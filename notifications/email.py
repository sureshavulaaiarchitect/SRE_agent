import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import structlog
from configs.config import settings

logger = structlog.get_logger(__name__)

class EmailNotifier:
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_pass = settings.SMTP_PASS
        self.from_addr = settings.ALERT_FROM_EMAIL
        self.to_addrs  = settings.ALERT_TO_EMAILS.split(",") if settings.ALERT_TO_EMAILS else []

    async def send_incident_detected(self, incident: dict):
        subject = f"[SRE Agent] Incident Detected: {incident.get('pod_name')} ({incident.get('incident_type')})"
        body = self._html_body(incident)
        await self._send(subject, body)

    async def send_incident_resolved(self, incident: dict):
        subject = f"[SRE Agent] Incident Resolved: {incident.get('pod_name')} — MTTR {incident.get('mttr_seconds', '?')}s"
        body = self._html_body(incident, resolved=True)
        await self._send(subject, body)

    def _html_body(self, incident: dict, resolved: bool = False) -> str:
        status_color = "#27ae60" if resolved else "#e74c3c"
        status_text  = "RESOLVED" if resolved else "DETECTED"
        return f"""
        <html><body>
        <h2 style="color:{status_color}">Incident {status_text}</h2>
        <table border="1" cellpadding="6">
          <tr><td><b>Pod</b></td><td>{incident.get('pod_name','N/A')}</td></tr>
          <tr><td><b>Namespace</b></td><td>{incident.get('namespace','N/A')}</td></tr>
          <tr><td><b>Incident Type</b></td><td>{incident.get('incident_type','N/A')}</td></tr>
          <tr><td><b>Root Cause</b></td><td>{incident.get('root_cause','N/A')}</td></tr>
          <tr><td><b>Confidence</b></td><td>{incident.get('confidence','N/A')}</td></tr>
          <tr><td><b>Recommended Action</b></td><td>{incident.get('recommended_action','N/A')}</td></tr>
        </table>
        </body></html>
        """

    async def _send(self, subject: str, html_body: str):
        if not self.smtp_user:
            logger.warning("SMTP not configured — skipping email")
            return
        
        def _sync_send():
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = self.from_addr
            msg["To"]      = ", ".join(self.to_addrs)
            msg.attach(MIMEText(html_body, "html"))
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())

        try:
            await asyncio.to_thread(_sync_send)
            logger.info("Email notification sent", subject=subject)
        except Exception as e:
            logger.error("Failed to send email", error=str(e))
