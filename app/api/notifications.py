"""
Notification management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db, Notification

router = APIRouter()

class NotificationResponse(BaseModel):
    id: int
    job_id: int | None
    backup_run_id: int | None
    notification_type: str
    severity: str
    message: str
    sent_at: str
    email_sent: bool
    webhook_sent: bool
    
    class Config:
        from_attributes = True

class NotificationConfig(BaseModel):
    email_enabled: bool = False
    webhook_enabled: bool = False
    webhook_url: Optional[str] = None
    alert_on_failure: bool = True
    alert_on_missed_schedule: bool = True
    alert_on_verification_failure: bool = True
    alert_on_cost_threshold: bool = False
    cost_threshold_dollars: Optional[float] = None

@router.get("/", response_model=List[NotificationResponse])
def list_notifications(limit: int = 50, db: Session = Depends(get_db)):
    """List recent notifications"""
    notifications = db.query(Notification).order_by(
        Notification.sent_at.desc()
    ).limit(limit).all()
    
    result = []
    for notif in notifications:
        notif_dict = {
            **{k: v for k, v in notif.__dict__.items() if not k.startswith('_')},
            'sent_at': notif.sent_at.isoformat() if notif.sent_at else None,
        }
        result.append(NotificationResponse(**notif_dict))
    return result

@router.get("/config")
def get_notification_config():
    """Get notification configuration"""
    from app.config import settings
    return {
        "email_enabled": bool(settings.smtp_host),
        "webhook_enabled": bool(settings.webhook_url),
        "smtp_configured": bool(settings.smtp_host and settings.smtp_user),
        "webhook_configured": bool(settings.webhook_url)
    }

@router.put("/config")
def update_notification_config(config: NotificationConfig):
    """Update notification configuration"""
    # TODO: Persist notification config
    return {"message": "Configuration updated", "config": config}
