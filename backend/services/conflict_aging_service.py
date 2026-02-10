"""
Conflict/Complaint Aging Tracking Service

Tracks:
- How long complaints remain unresolved
- Resolution times by status
- Aging analysis for bottleneck identification
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)


class ConflictAgingService:
    """Service for tracking complaint/conflict aging"""
    
    # Complaint statuses
    STATUS_OPEN = "complained"
    STATUS_UNDER_REVIEW = "under_review"
    STATUS_RESOLVED = "resolved"
    STATUS_CLOSED = "closed"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    async def get_aging_metrics(
        self,
        network_id: Optional[str] = None,
        brand_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculate complaint aging metrics.
        
        Returns aging statistics for open complaints.
        """
        now = datetime.now(timezone.utc)
        
        # Find all open/under_review complaints
        query = {
            "status": {"$in": [self.STATUS_OPEN, self.STATUS_UNDER_REVIEW]},
        }
        if network_id:
            query["network_id"] = network_id
        if brand_id:
            # Need to join with network to filter by brand
            pass
        
        complaints = await self.db.seo_optimizations.find(
            query,
            {"_id": 0, "id": 1, "status": 1, "created_at": 1, "network_id": 1, "title": 1}
        ).to_list(500)
        
        if not complaints:
            return {
                "total_open": 0,
                "by_status": {},
                "by_age_bucket": {},
                "avg_age_days": 0,
                "max_age_days": 0,
                "critical_count": 0,  # > 7 days
                "oldest_complaints": [],
            }
        
        # Calculate ages
        ages = []
        by_status = {}
        by_age_bucket = {
            "0-1_days": 0,
            "2-3_days": 0,
            "4-7_days": 0,
            "8-14_days": 0,
            "15-30_days": 0,
            "30+_days": 0,
        }
        oldest = []
        
        for c in complaints:
            created_str = c.get("created_at", "")
            if not created_str:
                continue
            
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                age_days = (now - created).days
                ages.append(age_days)
                
                # By status
                status = c.get("status", "unknown")
                if status not in by_status:
                    by_status[status] = {"count": 0, "total_age_days": 0}
                by_status[status]["count"] += 1
                by_status[status]["total_age_days"] += age_days
                
                # By age bucket
                if age_days <= 1:
                    by_age_bucket["0-1_days"] += 1
                elif age_days <= 3:
                    by_age_bucket["2-3_days"] += 1
                elif age_days <= 7:
                    by_age_bucket["4-7_days"] += 1
                elif age_days <= 14:
                    by_age_bucket["8-14_days"] += 1
                elif age_days <= 30:
                    by_age_bucket["15-30_days"] += 1
                else:
                    by_age_bucket["30+_days"] += 1
                
                # Track for oldest
                oldest.append({
                    "id": c.get("id"),
                    "title": c.get("title", ""),
                    "network_id": c.get("network_id"),
                    "status": status,
                    "age_days": age_days,
                    "created_at": created_str,
                })
            except Exception as e:
                logger.warning(f"Failed to parse date for complaint {c.get('id')}: {e}")
        
        # Calculate averages per status
        for status in by_status:
            count = by_status[status]["count"]
            total_age = by_status[status]["total_age_days"]
            by_status[status]["avg_age_days"] = round(total_age / count, 1) if count > 0 else 0
        
        # Sort oldest
        oldest.sort(key=lambda x: x["age_days"], reverse=True)
        
        avg_age = sum(ages) / len(ages) if ages else 0
        max_age = max(ages) if ages else 0
        critical_count = len([a for a in ages if a > 7])
        
        return {
            "total_open": len(complaints),
            "by_status": by_status,
            "by_age_bucket": by_age_bucket,
            "avg_age_days": round(avg_age, 1),
            "max_age_days": max_age,
            "critical_count": critical_count,
            "oldest_complaints": oldest[:10],  # Top 10 oldest
        }
    
    async def get_resolution_metrics(
        self,
        days: int = 30,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculate resolution time metrics for recently resolved complaints.
        """
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        query = {
            "status": {"$in": [self.STATUS_RESOLVED, self.STATUS_CLOSED]},
            "resolved_at": {"$gte": start_date},
        }
        if network_id:
            query["network_id"] = network_id
        
        resolved = await self.db.seo_optimizations.find(
            query,
            {"_id": 0, "id": 1, "created_at": 1, "resolved_at": 1, "status": 1}
        ).to_list(500)
        
        if not resolved:
            return {
                "period_days": days,
                "total_resolved": 0,
                "avg_resolution_time_days": 0,
                "min_resolution_time_days": 0,
                "max_resolution_time_days": 0,
                "by_time_bucket": {},
            }
        
        resolution_times = []
        by_time_bucket = {
            "same_day": 0,
            "1-2_days": 0,
            "3-7_days": 0,
            "8-14_days": 0,
            "15+_days": 0,
        }
        
        for c in resolved:
            created_str = c.get("created_at", "")
            resolved_str = c.get("resolved_at", "")
            
            if not created_str or not resolved_str:
                continue
            
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                resolved_at = datetime.fromisoformat(resolved_str.replace("Z", "+00:00"))
                resolution_days = (resolved_at - created).days
                resolution_times.append(resolution_days)
                
                if resolution_days == 0:
                    by_time_bucket["same_day"] += 1
                elif resolution_days <= 2:
                    by_time_bucket["1-2_days"] += 1
                elif resolution_days <= 7:
                    by_time_bucket["3-7_days"] += 1
                elif resolution_days <= 14:
                    by_time_bucket["8-14_days"] += 1
                else:
                    by_time_bucket["15+_days"] += 1
            except Exception as e:
                logger.warning(f"Failed to calculate resolution time for {c.get('id')}: {e}")
        
        avg_time = sum(resolution_times) / len(resolution_times) if resolution_times else 0
        min_time = min(resolution_times) if resolution_times else 0
        max_time = max(resolution_times) if resolution_times else 0
        
        return {
            "period_days": days,
            "total_resolved": len(resolved),
            "avg_resolution_time_days": round(avg_time, 1),
            "min_resolution_time_days": min_time,
            "max_resolution_time_days": max_time,
            "by_time_bucket": by_time_bucket,
        }


# Global instance
_conflict_aging_service: Optional[ConflictAgingService] = None


def get_conflict_aging_service(db: AsyncIOMotorDatabase) -> ConflictAgingService:
    """Get or create the conflict aging service"""
    global _conflict_aging_service
    if _conflict_aging_service is None:
        _conflict_aging_service = ConflictAgingService(db)
    return _conflict_aging_service
