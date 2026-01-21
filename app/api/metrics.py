"""
API endpoints for storage metrics and cost tracking
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.metrics import metrics_service

router = APIRouter()


@router.post("/metrics/record")
def record_metrics(db: Session = Depends(get_db)):
    """
    Manually trigger recording of today's storage metrics
    (Normally called automatically by scheduler)
    """
    metrics = metrics_service.record_daily_metrics(db)
    return {
        "message": "Metrics recorded successfully",
        "recorded_at": metrics.recorded_at.isoformat(),
        "total_size_gb": round(metrics.total_size_bytes / (1024**3), 2),
        "monthly_cost": metrics.monthly_cost_estimate
    }


@router.get("/metrics/history")
def get_historical_metrics(
    days: int = Query(30, description="Number of days of history to retrieve"),
    job_id: Optional[int] = Query(None, description="Filter by job ID"),
    db: Session = Depends(get_db)
):
    """
    Get historical storage and cost metrics
    
    Returns daily snapshots of storage usage and costs
    """
    history = metrics_service.get_historical_metrics(db, days=days, job_id=job_id)
    return {
        "days": days,
        "job_id": job_id,
        "records": history,
        "count": len(history)
    }


@router.get("/metrics/projection")
def get_cost_projection(
    days_ahead: int = Query(30, description="Number of days to project ahead"),
    job_id: Optional[int] = Query(None, description="Filter by job ID"),
    db: Session = Depends(get_db)
):
    """
    Get cost and storage projections based on historical growth trends
    
    Projects future storage usage and costs based on historical growth rate
    """
    projection = metrics_service.calculate_projection(db, days_ahead=days_ahead, job_id=job_id)
    return projection


@router.get("/metrics/summary")
def get_metrics_summary(
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get summary of metrics including trends and statistics
    """
    history = metrics_service.get_historical_metrics(db, days=days)
    
    if not history:
        # Record current metrics if none exist
        metrics_service.record_daily_metrics(db)
        history = metrics_service.get_historical_metrics(db, days=1)
    
    if not history:
        return {
            "error": "No metrics available"
        }
    
    latest = history[-1]
    oldest = history[0] if len(history) > 1 else latest
    
    # Calculate trends
    size_change = latest["total_size_bytes"] - oldest["total_size_bytes"]
    cost_change = latest["monthly_cost"] - oldest["monthly_cost"]
    
    # Find peak usage
    peak = max(history, key=lambda x: x["total_size_bytes"])
    
    return {
        "period_days": days,
        "current": {
            "date": latest["date"],
            "size_gb": latest["total_size_gb"],
            "size_tb": latest["total_size_tb"],
            "files": latest["total_files"],
            "monthly_cost": latest["monthly_cost"],
            "annual_cost": round(latest["monthly_cost"] * 12, 2)
        },
        "trends": {
            "size_change_gb": round(size_change / (1024**3), 2),
            "size_change_percent": round((size_change / oldest["total_size_bytes"] * 100) if oldest["total_size_bytes"] > 0 else 0, 2),
            "cost_change": round(cost_change, 2),
            "cost_change_percent": round((cost_change / oldest["monthly_cost"] * 100) if oldest["monthly_cost"] > 0 else 0, 2)
        },
        "peak": {
            "date": peak["date"],
            "size_gb": peak["total_size_gb"],
            "size_tb": peak["total_size_tb"],
            "monthly_cost": peak["monthly_cost"]
        },
        "breakdown": {
            "by_storage_class": latest["size_by_class"],
            "cost_by_storage_class": latest["cost_by_class"]
        }
    }
