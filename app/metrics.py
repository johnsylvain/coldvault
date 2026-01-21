"""
Storage metrics recording and cost calculation service
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import StorageMetrics, Snapshot, Job, StorageClass

logger = logging.getLogger(__name__)

# AWS Storage pricing (per GB per month, as of 2024)
# Update these periodically to reflect current pricing
STORAGE_PRICING = {
    StorageClass.STANDARD: 0.023,  # $0.023/GB/month
    StorageClass.GLACIER_IR: 0.004,  # $0.004/GB/month
    StorageClass.GLACIER_FLEXIBLE: 0.0036,  # $0.0036/GB/month
    StorageClass.DEEP_ARCHIVE: 0.00099,  # $0.00099/GB/month
}


class MetricsService:
    """Service for recording and querying storage metrics"""
    
    def record_daily_metrics(self, db: Session) -> StorageMetrics:
        """
        Record today's storage metrics snapshot
        
        Returns the created StorageMetrics record
        """
        # Check if we already recorded today
        today = datetime.utcnow().date()
        existing = db.query(StorageMetrics).filter(
            func.date(StorageMetrics.recorded_at) == today
        ).first()
        
        if existing:
            logger.info(f"Metrics already recorded for {today}, updating...")
            metrics = existing
        else:
            metrics = StorageMetrics()
            db.add(metrics)
        
        # Calculate totals by storage class
        total_size = 0
        size_by_class = {}
        total_files = 0
        job_breakdown = {}
        
        for storage_class in StorageClass:
            # Get total size for this storage class
            result = db.query(func.sum(Snapshot.size_bytes)).filter(
                Snapshot.storage_class == storage_class,
                Snapshot.retained == True
            ).scalar() or 0
            
            size_by_class[storage_class] = int(result)
            total_size += int(result)
        
        # Get total file count
        total_files = db.query(func.sum(Snapshot.files_count)).filter(
            Snapshot.retained == True
        ).scalar() or 0
        
        # Calculate costs
        monthly_cost = 0.0
        cost_by_class = {}
        
        for storage_class, price_per_gb in STORAGE_PRICING.items():
            size_gb = size_by_class[storage_class] / (1024**3)
            cost = size_gb * price_per_gb
            cost_by_class[storage_class] = cost
            monthly_cost += cost
        
        # Per-job breakdown
        jobs = db.query(Job).all()
        for job in jobs:
            job_snapshots = db.query(Snapshot).filter(
                Snapshot.job_id == job.id,
                Snapshot.retained == True
            ).all()
            
            job_size = sum(s.size_bytes or 0 for s in job_snapshots)
            job_files = sum(s.files_count or 0 for s in job_snapshots)
            
            # Get storage class (use most common or job default)
            job_storage_class = job.storage_class
            if job_snapshots:
                # Use the storage class from snapshots
                job_storage_class = job_snapshots[0].storage_class or job.storage_class
            
            job_cost = (job_size / (1024**3)) * STORAGE_PRICING.get(job_storage_class, STORAGE_PRICING[StorageClass.DEEP_ARCHIVE])
            
            job_breakdown[job.id] = {
                "job_name": job.name,
                "size_bytes": job_size,
                "size_gb": round(job_size / (1024**3), 2),
                "files_count": job_files,
                "storage_class": job_storage_class.value if job_storage_class else None,
                "monthly_cost": round(job_cost, 2)
            }
        
        # Update metrics record
        metrics.recorded_at = datetime.utcnow()
        metrics.total_size_bytes = total_size
        metrics.size_standard_bytes = size_by_class.get(StorageClass.STANDARD, 0)
        metrics.size_glacier_ir_bytes = size_by_class.get(StorageClass.GLACIER_IR, 0)
        metrics.size_glacier_flexible_bytes = size_by_class.get(StorageClass.GLACIER_FLEXIBLE, 0)
        metrics.size_deep_archive_bytes = size_by_class.get(StorageClass.DEEP_ARCHIVE, 0)
        metrics.total_files = total_files or 0
        metrics.monthly_cost_estimate = round(monthly_cost, 2)
        metrics.cost_standard = round(cost_by_class.get(StorageClass.STANDARD, 0), 2)
        metrics.cost_glacier_ir = round(cost_by_class.get(StorageClass.GLACIER_IR, 0), 2)
        metrics.cost_glacier_flexible = round(cost_by_class.get(StorageClass.GLACIER_FLEXIBLE, 0), 2)
        metrics.cost_deep_archive = round(cost_by_class.get(StorageClass.DEEP_ARCHIVE, 0), 2)
        metrics.job_breakdown = json.dumps(job_breakdown)
        
        db.commit()
        logger.info(f"Recorded daily metrics: {total_size / (1024**3):.2f} GB, ${monthly_cost:.2f}/month")
        
        return metrics
    
    def get_historical_metrics(
        self,
        db: Session,
        days: int = 30,
        job_id: Optional[int] = None
    ) -> List[Dict]:
        """
        Get historical metrics for the last N days
        
        Args:
            days: Number of days to retrieve
            job_id: Optional job ID to filter by
            
        Returns:
            List of metric records as dictionaries
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = db.query(StorageMetrics).filter(
            StorageMetrics.recorded_at >= cutoff_date
        ).order_by(StorageMetrics.recorded_at.asc())
        
        metrics = query.all()
        
        result = []
        for m in metrics:
            job_breakdown = json.loads(m.job_breakdown) if m.job_breakdown else {}
            
            # Filter by job_id if specified
            if job_id is not None:
                if job_id not in job_breakdown:
                    continue
                job_breakdown = {job_id: job_breakdown[job_id]}
            
            result.append({
                "date": m.recorded_at.isoformat(),
                "total_size_bytes": m.total_size_bytes,
                "total_size_gb": round(m.total_size_bytes / (1024**3), 2),
                "total_size_tb": round(m.total_size_bytes / (1024**4), 2),
                "total_files": m.total_files,
                "size_by_class": {
                    "STANDARD": round(m.size_standard_bytes / (1024**3), 2),
                    "GLACIER_IR": round(m.size_glacier_ir_bytes / (1024**3), 2),
                    "GLACIER_FLEXIBLE": round(m.size_glacier_flexible_bytes / (1024**3), 2),
                    "DEEP_ARCHIVE": round(m.size_deep_archive_bytes / (1024**3), 2),
                },
                "monthly_cost": m.monthly_cost_estimate,
                "cost_by_class": {
                    "STANDARD": m.cost_standard,
                    "GLACIER_IR": m.cost_glacier_ir,
                    "GLACIER_FLEXIBLE": m.cost_glacier_flexible,
                    "DEEP_ARCHIVE": m.cost_deep_archive,
                },
                "job_breakdown": job_breakdown
            })
        
        return result
    
    def calculate_projection(
        self,
        db: Session,
        days_ahead: int = 30,
        job_id: Optional[int] = None
    ) -> Dict:
        """
        Calculate cost and storage projections based on historical growth
        
        Args:
            days_ahead: Number of days to project ahead
            job_id: Optional job ID to filter by
            
        Returns:
            Dictionary with projections
        """
        # Get historical data (last 30 days minimum for good projection)
        historical = self.get_historical_metrics(db, days=30, job_id=job_id)
        
        if len(historical) < 2:
            # Not enough data for projection
            latest = self.record_daily_metrics(db)
            current_size = latest.total_size_bytes
            current_cost = latest.monthly_cost_estimate
            
            return {
                "current": {
                    "size_gb": round(current_size / (1024**3), 2),
                    "monthly_cost": current_cost
                },
                "projection": {
                    "days_ahead": days_ahead,
                    "projected_size_gb": round(current_size / (1024**3), 2),
                    "projected_monthly_cost": current_cost,
                    "projected_annual_cost": round(current_cost * 12, 2)
                },
                "growth_rate": {
                    "daily_gb": 0,
                    "daily_percent": 0,
                    "monthly_percent": 0
                },
                "note": "Insufficient historical data for accurate projection"
            }
        
        # Calculate growth rate
        oldest = historical[0]
        newest = historical[-1]
        
        days_span = (datetime.fromisoformat(newest["date"]) - datetime.fromisoformat(oldest["date"])).days
        if days_span == 0:
            days_span = 1
        
        size_growth = newest["total_size_bytes"] - oldest["total_size_bytes"]
        daily_growth_bytes = size_growth / days_span
        daily_growth_gb = daily_growth_bytes / (1024**3)
        
        # Calculate growth percentage
        if oldest["total_size_bytes"] > 0:
            daily_growth_percent = (size_growth / oldest["total_size_bytes"]) / days_span * 100
            monthly_growth_percent = daily_growth_percent * 30
        else:
            daily_growth_percent = 0
            monthly_growth_percent = 0
        
        # Project future size
        current_size = newest["total_size_bytes"]
        projected_size = current_size + (daily_growth_bytes * days_ahead)
        
        # Project future cost (assume same storage class distribution)
        current_cost = newest["monthly_cost"]
        if current_size > 0:
            cost_per_gb = current_cost / (current_size / (1024**3))
            projected_cost = (projected_size / (1024**3)) * cost_per_gb
        else:
            projected_cost = current_cost
        
        return {
            "current": {
                "size_gb": round(current_size / (1024**3), 2),
                "size_tb": round(current_size / (1024**4), 2),
                "monthly_cost": round(current_cost, 2),
                "annual_cost": round(current_cost * 12, 2)
            },
            "projection": {
                "days_ahead": days_ahead,
                "projected_size_gb": round(projected_size / (1024**3), 2),
                "projected_size_tb": round(projected_size / (1024**4), 2),
                "projected_monthly_cost": round(projected_cost, 2),
                "projected_annual_cost": round(projected_cost * 12, 2)
            },
            "growth_rate": {
                "daily_gb": round(daily_growth_gb, 2),
                "daily_percent": round(daily_growth_percent, 2),
                "monthly_percent": round(monthly_growth_percent, 2)
            },
            "historical_days": len(historical),
            "note": "Projections based on linear growth trend"
        }


metrics_service = MetricsService()
