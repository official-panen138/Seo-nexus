"""
SEO Change Log Service
=======================
Handles SEO-specific change logging (separate from system activity logs).

This service is for HUMAN SEO DECISIONS, not system operations.
All logs require a human-readable change_note.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase

from models_v3 import SeoChangeActionType, SeoNotificationType


class SeoChangeLogService:
    """Service for managing SEO change logs and notifications"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.change_logs = db.seo_change_logs
        self.notifications = db.seo_network_notifications
    
    def _clean_snapshot(self, snapshot: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Remove MongoDB _id from snapshot to prevent serialization errors"""
        if snapshot is None:
            return None
        # Create a copy to avoid modifying the original
        cleaned = {k: v for k, v in snapshot.items() if k != "_id"}
        return cleaned
    
    async def log_change(
        self,
        network_id: str,
        brand_id: str,
        actor_user_id: str,
        actor_email: str,
        action_type: SeoChangeActionType,
        affected_node: str,
        change_note: str,
        before_snapshot: Optional[Dict[str, Any]] = None,
        after_snapshot: Optional[Dict[str, Any]] = None,
        entry_id: Optional[str] = None
    ) -> str:
        """
        Log an SEO change with mandatory change note.
        Returns the log ID.
        """
        now = datetime.now(timezone.utc).isoformat()
        
        # Clean snapshots to remove MongoDB _id
        cleaned_before = self._clean_snapshot(before_snapshot)
        cleaned_after = self._clean_snapshot(after_snapshot)
        
        log_entry = {
            "id": str(uuid.uuid4()),
            "network_id": network_id,
            "brand_id": brand_id,
            "actor_user_id": actor_user_id,
            "actor_email": actor_email,
            "action_type": action_type.value if hasattr(action_type, 'value') else action_type,
            "affected_node": affected_node,
            "before_snapshot": cleaned_before,
            "after_snapshot": cleaned_after,
            "change_note": change_note,
            "entry_id": entry_id,  # For linking back to structure entry
            "archived": False,
            "archived_at": None,
            "created_at": now
        }
        
        await self.change_logs.insert_one(log_entry)
        
        # Trigger notifications for important changes
        await self._check_and_notify(log_entry, before_snapshot, after_snapshot)
        
        return log_entry["id"]
    
    async def _check_and_notify(
        self,
        log_entry: Dict[str, Any],
        before: Optional[Dict[str, Any]],
        after: Optional[Dict[str, Any]]
    ):
        """Check if this change should trigger a notification"""
        action = log_entry["action_type"]
        notifications = []
        
        # Main domain change
        if action == SeoChangeActionType.CHANGE_ROLE.value:
            before_role = before.get("domain_role") if before else None
            after_role = after.get("domain_role") if after else None
            if before_role != after_role and after_role == "main":
                notifications.append({
                    "type": SeoNotificationType.MAIN_DOMAIN_CHANGE,
                    "title": "Main Domain Changed",
                    "message": f"Node '{log_entry['affected_node']}' is now the main domain."
                })
        
        # Node deletion
        if action == SeoChangeActionType.DELETE_NODE.value:
            notifications.append({
                "type": SeoNotificationType.NODE_DELETED,
                "title": "Node Deleted",
                "message": f"Node '{log_entry['affected_node']}' was deleted."
            })
        
        # Target relink
        if action == SeoChangeActionType.RELINK_NODE.value:
            before_target = before.get("target_entry_id") if before else None
            after_target = after.get("target_entry_id") if after else None
            if before_target != after_target:
                notifications.append({
                    "type": SeoNotificationType.TARGET_RELINKED,
                    "title": "Target Relinked",
                    "message": f"Node '{log_entry['affected_node']}' target was changed."
                })
        
        # Create notifications
        for notif in notifications:
            await self.create_notification(
                network_id=log_entry["network_id"],
                brand_id=log_entry["brand_id"],
                notification_type=notif["type"],
                title=notif["title"],
                message=notif["message"],
                affected_node=log_entry["affected_node"],
                actor_email=log_entry.get("actor_email"),
                change_log_id=log_entry["id"],
                change_note=log_entry["change_note"]
            )
    
    async def create_notification(
        self,
        network_id: str,
        brand_id: str,
        notification_type: SeoNotificationType,
        title: str,
        message: str,
        affected_node: Optional[str] = None,
        actor_email: Optional[str] = None,
        change_log_id: Optional[str] = None,
        change_note: Optional[str] = None
    ) -> str:
        """Create a network notification"""
        now = datetime.now(timezone.utc).isoformat()
        
        notification = {
            "id": str(uuid.uuid4()),
            "network_id": network_id,
            "brand_id": brand_id,
            "notification_type": notification_type.value if hasattr(notification_type, 'value') else notification_type,
            "title": title,
            "message": message,
            "affected_node": affected_node,
            "actor_email": actor_email,
            "change_log_id": change_log_id,
            "change_note": change_note,
            "read": False,
            "read_at": None,
            "created_at": now
        }
        
        await self.notifications.insert_one(notification)
        return notification["id"]
    
    async def get_network_change_history(
        self,
        network_id: str,
        include_archived: bool = False,
        skip: int = 0,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get change history for a network"""
        query = {"network_id": network_id}
        if not include_archived:
            query["archived"] = {"$ne": True}
        
        logs = await self.change_logs.find(
            query, {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        return logs
    
    async def get_network_notifications(
        self,
        network_id: str,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get notifications for a network"""
        query = {"network_id": network_id}
        if unread_only:
            query["read"] = False
        
        notifications = await self.notifications.find(
            query, {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        return notifications
    
    async def mark_notification_read(self, notification_id: str) -> bool:
        """Mark a notification as read"""
        result = await self.notifications.update_one(
            {"id": notification_id},
            {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}}
        )
        return result.modified_count > 0
    
    async def mark_all_notifications_read(self, network_id: str) -> int:
        """Mark all notifications in a network as read"""
        result = await self.notifications.update_many(
            {"network_id": network_id, "read": False},
            {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}}
        )
        return result.modified_count
    
    async def archive_old_logs(self, days_old: int = 90) -> int:
        """Archive logs older than specified days"""
        cutoff = datetime.now(timezone.utc)
        cutoff = cutoff.replace(day=cutoff.day - days_old)
        
        result = await self.change_logs.update_many(
            {
                "created_at": {"$lt": cutoff.isoformat()},
                "archived": {"$ne": True}
            },
            {"$set": {"archived": True, "archived_at": datetime.now(timezone.utc).isoformat()}}
        )
        return result.modified_count
    
    async def get_team_stats(
        self,
        brand_ids: Optional[List[str]] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get team evaluation metrics"""
        from datetime import timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        query = {"created_at": {"$gte": cutoff.isoformat()}}
        if brand_ids:
            query["brand_id"] = {"$in": brand_ids}
        
        # Changes per user
        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$actor_email",
                "change_count": {"$sum": 1},
                "last_change": {"$max": "$created_at"}
            }},
            {"$sort": {"change_count": -1}}
        ]
        
        changes_by_user = await self.change_logs.aggregate(pipeline).to_list(100)
        
        # Changes per network
        network_pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$network_id",
                "change_count": {"$sum": 1},
                "last_change": {"$max": "$created_at"}
            }},
            {"$sort": {"change_count": -1}}
        ]
        
        changes_by_network = await self.change_logs.aggregate(network_pipeline).to_list(100)
        
        # Most modified domains
        domain_pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$affected_node",
                "change_count": {"$sum": 1}
            }},
            {"$sort": {"change_count": -1}},
            {"$limit": 20}
        ]
        
        most_modified = await self.change_logs.aggregate(domain_pipeline).to_list(20)
        
        # Total stats
        total_changes = await self.change_logs.count_documents(query)
        unique_users = len(changes_by_user)
        
        return {
            "period_days": days,
            "total_changes": total_changes,
            "unique_users": unique_users,
            "changes_by_user": changes_by_user,
            "changes_by_network": changes_by_network,
            "most_modified_nodes": most_modified
        }
    
    def determine_action_type(
        self,
        is_create: bool,
        is_delete: bool,
        before: Optional[Dict[str, Any]],
        after: Optional[Dict[str, Any]]
    ) -> SeoChangeActionType:
        """Determine the specific action type based on what changed"""
        if is_create:
            return SeoChangeActionType.CREATE_NODE
        
        if is_delete:
            return SeoChangeActionType.DELETE_NODE
        
        # For updates, determine the most significant change
        if before and after:
            # Role change
            if before.get("domain_role") != after.get("domain_role"):
                return SeoChangeActionType.CHANGE_ROLE
            
            # Target relink
            if before.get("target_entry_id") != after.get("target_entry_id"):
                return SeoChangeActionType.RELINK_NODE
            
            # Path change
            if before.get("optimized_path") != after.get("optimized_path"):
                return SeoChangeActionType.CHANGE_PATH
        
        # Generic update
        return SeoChangeActionType.UPDATE_NODE
