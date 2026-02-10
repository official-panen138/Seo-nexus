"""
Audit Logging Service

Centralized audit logging for:
- Template changes
- Permission violations
- Failed notifications
- Security events
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)


class AuditLogService:
    """Service for centralized audit logging"""
    
    # Audit event types
    EVENT_TEMPLATE_CHANGE = "template_change"
    EVENT_TEMPLATE_RESET = "template_reset"
    EVENT_PERMISSION_VIOLATION = "permission_violation"
    EVENT_NOTIFICATION_FAILED = "notification_failed"
    EVENT_NOTIFICATION_SENT = "notification_sent"
    EVENT_LOGIN_SUCCESS = "login_success"
    EVENT_LOGIN_FAILED = "login_failed"
    EVENT_SETTINGS_CHANGE = "settings_change"
    EVENT_SEO_CHANGE = "seo_change"
    EVENT_DATA_EXPORT = "data_export"
    
    # Severity levels
    SEVERITY_INFO = "info"
    SEVERITY_WARNING = "warning"
    SEVERITY_ERROR = "error"
    SEVERITY_CRITICAL = "critical"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.audit_logs
    
    async def log(
        self,
        event_type: str,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "info",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> str:
        """
        Create an audit log entry.
        
        Args:
            event_type: Type of event (use class constants)
            actor_id: User ID who performed the action
            actor_email: Email of the actor
            resource_type: Type of resource affected (e.g., "template", "network")
            resource_id: ID of the affected resource
            action: Specific action taken (e.g., "update", "delete")
            details: Additional context as dict
            severity: Log severity level
            ip_address: Client IP if available
            user_agent: Client user agent if available
            success: Whether the action succeeded
            error_message: Error message if failed
            
        Returns:
            The audit log ID
        """
        log_id = str(uuid.uuid4())
        
        audit_entry = {
            "id": log_id,
            "event_type": event_type,
            "actor_id": actor_id,
            "actor_email": actor_email,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "details": details or {},
            "severity": severity,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
            "error_message": error_message,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        try:
            await self.collection.insert_one(audit_entry)
            logger.info(f"Audit log created: {event_type} by {actor_email} on {resource_type}/{resource_id}")
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
        
        return log_id
    
    async def log_template_change(
        self,
        actor_email: str,
        channel: str,
        event_type: str,
        action: str,
        changes: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log a notification template change"""
        return await self.log(
            event_type=self.EVENT_TEMPLATE_CHANGE if action != "reset" else self.EVENT_TEMPLATE_RESET,
            actor_email=actor_email,
            resource_type="notification_template",
            resource_id=f"{channel}/{event_type}",
            action=action,
            details={"channel": channel, "template_event_type": event_type, "changes": changes},
            severity=self.SEVERITY_INFO,
        )
    
    async def log_permission_violation(
        self,
        actor_id: Optional[str],
        actor_email: Optional[str],
        resource_type: str,
        resource_id: str,
        action: str,
        required_permission: str,
        ip_address: Optional[str] = None,
    ) -> str:
        """Log a permission violation (403 Forbidden)"""
        return await self.log(
            event_type=self.EVENT_PERMISSION_VIOLATION,
            actor_id=actor_id,
            actor_email=actor_email,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details={"required_permission": required_permission, "denied": True},
            severity=self.SEVERITY_WARNING,
            ip_address=ip_address,
            success=False,
            error_message=f"Permission denied: requires {required_permission}",
        )
    
    async def log_notification_failed(
        self,
        channel: str,
        notification_type: str,
        recipient: Optional[str] = None,
        error_message: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log a failed notification"""
        return await self.log(
            event_type=self.EVENT_NOTIFICATION_FAILED,
            resource_type="notification",
            resource_id=f"{channel}/{notification_type}",
            action="send",
            details={
                "channel": channel,
                "notification_type": notification_type,
                "recipient": recipient,
                **(details or {}),
            },
            severity=self.SEVERITY_ERROR,
            success=False,
            error_message=error_message,
        )
    
    async def log_notification_sent(
        self,
        channel: str,
        notification_type: str,
        recipient: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log a successful notification"""
        return await self.log(
            event_type=self.EVENT_NOTIFICATION_SENT,
            resource_type="notification",
            resource_id=f"{channel}/{notification_type}",
            action="send",
            details={
                "channel": channel,
                "notification_type": notification_type,
                "recipient": recipient,
                **(details or {}),
            },
            severity=self.SEVERITY_INFO,
            success=True,
        )
    
    async def get_logs(
        self,
        event_type: Optional[str] = None,
        actor_email: Optional[str] = None,
        resource_type: Optional[str] = None,
        severity: Optional[str] = None,
        success: Optional[bool] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """Query audit logs with filters"""
        query = {}
        
        if event_type:
            query["event_type"] = event_type
        if actor_email:
            query["actor_email"] = actor_email
        if resource_type:
            query["resource_type"] = resource_type
        if severity:
            query["severity"] = severity
        if success is not None:
            query["success"] = success
        if start_date:
            query["created_at"] = {"$gte": start_date}
        if end_date:
            if "created_at" in query:
                query["created_at"]["$lte"] = end_date
            else:
                query["created_at"] = {"$lte": end_date}
        
        cursor = self.collection.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
        return await cursor.to_list(limit)
    
    async def get_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get audit log statistics"""
        from datetime import timedelta
        
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        pipeline = [
            {"$match": {"created_at": {"$gte": start_date}}},
            {"$group": {
                "_id": {
                    "event_type": "$event_type",
                    "success": "$success",
                },
                "count": {"$sum": 1},
            }},
        ]
        
        results = await self.collection.aggregate(pipeline).to_list(100)
        
        stats = {
            "total_events": 0,
            "by_event_type": {},
            "failures": 0,
            "permission_violations": 0,
            "notification_failures": 0,
        }
        
        for r in results:
            event_type = r["_id"]["event_type"]
            success = r["_id"]["success"]
            count = r["count"]
            
            stats["total_events"] += count
            
            if event_type not in stats["by_event_type"]:
                stats["by_event_type"][event_type] = {"success": 0, "failed": 0}
            
            if success:
                stats["by_event_type"][event_type]["success"] += count
            else:
                stats["by_event_type"][event_type]["failed"] += count
                stats["failures"] += count
                
                if event_type == self.EVENT_PERMISSION_VIOLATION:
                    stats["permission_violations"] += count
                elif event_type == self.EVENT_NOTIFICATION_FAILED:
                    stats["notification_failures"] += count
        
        return stats


# Global instance
_audit_service: Optional[AuditLogService] = None


def get_audit_service(db: AsyncIOMotorDatabase) -> AuditLogService:
    """Get or create the audit log service"""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditLogService(db)
    return _audit_service
