"""
Notification service
"""
import logging
import aiosmtplib
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import settings
from app.database import Notification

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.smtp_configured = bool(
            settings.smtp_host and 
            settings.smtp_user and 
            settings.smtp_password
        )
        self.webhook_configured = bool(settings.webhook_url)
    
    async def send_email(self, subject: str, body: str, to: str = None):
        """Send email notification"""
        if not self.smtp_configured:
            logger.warning("SMTP not configured, skipping email notification")
            return False
        
        try:
            message = MIMEMultipart()
            message["From"] = settings.smtp_from or settings.smtp_user
            message["To"] = to or settings.smtp_user
            message["Subject"] = subject
            message.attach(MIMEText(body, "plain"))
            
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user,
                password=settings.smtp_password,
                use_tls=True
            )
            
            logger.info(f"Sent email notification: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    async def send_webhook(self, payload: dict):
        """Send webhook notification"""
        if not self.webhook_configured:
            logger.warning("Webhook not configured, skipping webhook notification")
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.webhook_url,
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
            
            logger.info("Sent webhook notification")
            return True
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
            return False
    
    def send_backup_failure(self, job, backup_run, error_message: str):
        """Send backup failure notification"""
        subject = f"ColdVault Backup Failed: {job.name}"
        body = f"""
Backup job '{job.name}' (ID: {job.id}) has failed.

Error: {error_message}
Started at: {backup_run.started_at}
Duration: {backup_run.duration_seconds} seconds

Please check the logs for more details.
"""
        
        # Send notifications asynchronously (fire and forget)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if self.smtp_configured:
            loop.run_until_complete(self.send_email(subject, body))
        
        if self.webhook_configured:
            payload = {
                "event": "backup_failure",
                "job_id": job.id,
                "job_name": job.name,
                "backup_run_id": backup_run.id,
                "error": error_message
            }
            loop.run_until_complete(self.send_webhook(payload))
    
    def send_backup_success(self, job, backup_run):
        """Send backup success notification (optional)"""
        # Typically not needed, but available if configured
        pass

notification_service = NotificationService()
