"""
Reminder Effectiveness Tracking Service

Tracks:
- When reminders are sent
- Response rates (optimizations completed after reminders)
- Completion times
- Effectiveness metrics
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)


class ReminderEffectivenessService:
    """Service for tracking reminder effectiveness"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.reminder_tracking
    
    async def record_reminder_sent(
        self,
        optimization_id: str,
        network_id: str,
        reminder_type: str,
        days_in_progress: int,
        recipient_ids: List[str] = None,
    ) -> str:
        """Record that a reminder was sent"""
        record_id = str(uuid.uuid4())
        
        record = {
            "id": record_id,
            "optimization_id": optimization_id,
            "network_id": network_id,
            "reminder_type": reminder_type,  # "in_progress", "stalled", "deadline"
            "days_in_progress": days_in_progress,
            "recipient_ids": recipient_ids or [],
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "responded": False,
            "responded_at": None,
            "response_action": None,  # "completed", "updated", "cancelled", None
            "response_time_hours": None,
        }
        
        await self.collection.insert_one(record)
        logger.info(f"Reminder recorded: {reminder_type} for optimization {optimization_id}")
        
        return record_id
    
    async def record_response(
        self,
        optimization_id: str,
        response_action: str,
    ) -> int:
        """
        Record a response to reminders for an optimization.
        Updates all pending reminders for this optimization.
        
        Args:
            optimization_id: The optimization that was responded to
            response_action: The action taken (completed, updated, cancelled)
            
        Returns:
            Number of reminder records updated
        """
        now = datetime.now(timezone.utc)
        
        # Find all un-responded reminders for this optimization
        pending = await self.collection.find({
            "optimization_id": optimization_id,
            "responded": False,
        }).to_list(100)
        
        updated_count = 0
        for reminder in pending:
            sent_at = datetime.fromisoformat(reminder["sent_at"].replace("Z", "+00:00"))
            response_time_hours = (now - sent_at).total_seconds() / 3600
            
            await self.collection.update_one(
                {"id": reminder["id"]},
                {
                    "$set": {
                        "responded": True,
                        "responded_at": now.isoformat(),
                        "response_action": response_action,
                        "response_time_hours": round(response_time_hours, 2),
                    }
                }
            )
            updated_count += 1
        
        if updated_count > 0:
            logger.info(f"Response recorded: {response_action} for optimization {optimization_id}, updated {updated_count} reminders")
        
        return updated_count
    
    async def get_effectiveness_metrics(
        self,
        days: int = 30,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calculate reminder effectiveness metrics.
        
        Returns:
            Dict with metrics including response rate, avg response time, etc.
        """
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        query = {"sent_at": {"$gte": start_date}}
        if network_id:
            query["network_id"] = network_id
        
        all_reminders = await self.collection.find(query, {"_id": 0}).to_list(1000)
        
        if not all_reminders:
            return {
                "period_days": days,
                "total_reminders": 0,
                "responded": 0,
                "not_responded": 0,
                "response_rate_percent": 0,
                "avg_response_time_hours": 0,
                "by_type": {},
                "by_action": {},
            }
        
        total = len(all_reminders)
        responded = [r for r in all_reminders if r.get("responded")]
        not_responded = total - len(responded)
        
        response_rate = (len(responded) / total * 100) if total > 0 else 0
        
        response_times = [r["response_time_hours"] for r in responded if r.get("response_time_hours")]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # By reminder type
        by_type = {}
        for r in all_reminders:
            rtype = r.get("reminder_type", "unknown")
            if rtype not in by_type:
                by_type[rtype] = {"total": 0, "responded": 0}
            by_type[rtype]["total"] += 1
            if r.get("responded"):
                by_type[rtype]["responded"] += 1
        
        # By response action
        by_action = {}
        for r in responded:
            action = r.get("response_action", "unknown")
            by_action[action] = by_action.get(action, 0) + 1
        
        return {
            "period_days": days,
            "total_reminders": total,
            "responded": len(responded),
            "not_responded": not_responded,
            "response_rate_percent": round(response_rate, 1),
            "avg_response_time_hours": round(avg_response_time, 1),
            "by_type": by_type,
            "by_action": by_action,
        }
    
    async def get_pending_reminders(
        self,
        network_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get reminders that haven't been responded to"""
        query = {"responded": False}
        if network_id:
            query["network_id"] = network_id
        
        return await self.collection.find(
            query, {"_id": 0}
        ).sort("sent_at", -1).limit(limit).to_list(limit)


# Global instance
_reminder_service: Optional[ReminderEffectivenessService] = None


def get_reminder_effectiveness_service(db: AsyncIOMotorDatabase) -> ReminderEffectivenessService:
    """Get or create the reminder effectiveness service"""
    global _reminder_service
    if _reminder_service is None:
        _reminder_service = ReminderEffectivenessService(db)
    return _reminder_service
