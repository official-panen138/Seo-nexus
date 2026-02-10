"""
Activity Log Service for SEO-NOC V3
===================================
Records all create, update, delete, and migration actions.
Enabled from migration start with actor: system:migration_v3
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

from models_v3 import (
    ActionType,
    EntityType,
    ActivityLogCreate,
    ActivityLogResponse,
    ActivityLogMetadata,
)

logger = logging.getLogger(__name__)


class ActivityLogService:
    """Service for recording and querying activity logs"""

    SYSTEM_MIGRATION_ACTOR = "system:migration_v3"
    SYSTEM_SCHEDULER_ACTOR = "system:scheduler"
    SYSTEM_MONITORING_ACTOR = "system:monitoring"

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.activity_logs_v3

    async def log(
        self,
        actor: str,
        action_type: ActionType,
        entity_type: EntityType,
        entity_id: str,
        before_value: Optional[Dict[str, Any]] = None,
        after_value: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record an activity log entry.

        Args:
            actor: User email or system identifier (e.g., system:migration_v3)
            action_type: Type of action performed
            entity_type: Type of entity affected
            entity_id: ID of the entity affected
            before_value: Snapshot of entity before change (for updates/deletes)
            after_value: Snapshot of entity after change (for creates/updates)
            metadata: Additional context (migration phase, legacy IDs, etc.)

        Returns:
            ID of the created log entry
        """
        log_id = str(uuid.uuid4())

        log_entry = {
            "id": log_id,
            "actor": actor,
            "action_type": (
                action_type.value
                if isinstance(action_type, ActionType)
                else action_type
            ),
            "entity_type": (
                entity_type.value
                if isinstance(entity_type, EntityType)
                else entity_type
            ),
            "entity_id": entity_id,
            "before_value": self._sanitize_for_storage(before_value),
            "after_value": self._sanitize_for_storage(after_value),
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await self.collection.insert_one(log_entry)
        logger.info(f"Activity logged: {actor} {action_type} {entity_type} {entity_id}")

        return log_id

    async def log_migration(
        self,
        action_type: ActionType,
        entity_type: EntityType,
        entity_id: str,
        phase: str,
        legacy_ids: Dict[str, str],
        before_value: Optional[Dict[str, Any]] = None,
        after_value: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Convenience method for logging migration actions.

        Args:
            action_type: Type of migration action
            entity_type: Type of entity being migrated
            entity_id: ID of the new entity
            phase: Migration phase (e.g., "phase_2_domains")
            legacy_ids: Mapping of legacy IDs for traceability
            before_value: Original V2 data
            after_value: New V3 data

        Returns:
            ID of the created log entry
        """
        metadata = {"migration_phase": phase, "legacy_ids": legacy_ids}

        return await self.log(
            actor=self.SYSTEM_MIGRATION_ACTOR,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            before_value=before_value,
            after_value=after_value,
            metadata=metadata,
        )

    async def get_logs(
        self,
        entity_type: Optional[EntityType] = None,
        entity_id: Optional[str] = None,
        actor: Optional[str] = None,
        action_type: Optional[ActionType] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[ActivityLogResponse]:
        """
        Query activity logs with optional filters.

        Args:
            entity_type: Filter by entity type
            entity_id: Filter by specific entity
            actor: Filter by actor
            action_type: Filter by action type
            limit: Maximum number of results
            skip: Number of results to skip (pagination)

        Returns:
            List of activity log entries
        """
        query = {}

        if entity_type:
            query["entity_type"] = (
                entity_type.value
                if isinstance(entity_type, EntityType)
                else entity_type
            )
        if entity_id:
            query["entity_id"] = entity_id
        if actor:
            query["actor"] = actor
        if action_type:
            query["action_type"] = (
                action_type.value
                if isinstance(action_type, ActionType)
                else action_type
            )

        cursor = self.collection.find(query, {"_id": 0})
        cursor = cursor.sort("created_at", -1).skip(skip).limit(limit)

        logs = await cursor.to_list(limit)

        # Sanitize any nested ObjectId in before_value/after_value
        sanitized_logs = []
        for log in logs:
            log["before_value"] = self._sanitize_for_storage(log.get("before_value"))
            log["after_value"] = self._sanitize_for_storage(log.get("after_value"))
            sanitized_logs.append(ActivityLogResponse(**log))

        return sanitized_logs

    async def get_entity_history(
        self, entity_type: EntityType, entity_id: str, limit: int = 50
    ) -> List[ActivityLogResponse]:
        """
        Get complete history for a specific entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            limit: Maximum number of history entries

        Returns:
            List of activity log entries for the entity
        """
        return await self.get_logs(
            entity_type=entity_type, entity_id=entity_id, limit=limit
        )

    async def get_migration_logs(
        self, phase: Optional[str] = None, limit: int = 1000
    ) -> List[ActivityLogResponse]:
        """
        Get migration-specific logs.

        Args:
            phase: Filter by migration phase
            limit: Maximum number of results

        Returns:
            List of migration activity logs
        """
        query = {"actor": self.SYSTEM_MIGRATION_ACTOR}

        if phase:
            query["metadata.migration_phase"] = phase

        cursor = self.collection.find(query, {"_id": 0})
        cursor = cursor.sort("created_at", -1).limit(limit)

        logs = await cursor.to_list(limit)
        return [ActivityLogResponse(**log) for log in logs]

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get activity log statistics.

        Returns:
            Dictionary with log statistics
        """
        total = await self.collection.count_documents({})

        # Count by action type
        action_pipeline = [{"$group": {"_id": "$action_type", "count": {"$sum": 1}}}]
        action_counts = await self.collection.aggregate(action_pipeline).to_list(10)

        # Count by entity type
        entity_pipeline = [{"$group": {"_id": "$entity_type", "count": {"$sum": 1}}}]
        entity_counts = await self.collection.aggregate(entity_pipeline).to_list(10)

        # Migration stats
        migration_count = await self.collection.count_documents(
            {"actor": self.SYSTEM_MIGRATION_ACTOR}
        )

        return {
            "total_logs": total,
            "migration_logs": migration_count,
            "by_action": {r["_id"]: r["count"] for r in action_counts},
            "by_entity": {r["_id"]: r["count"] for r in entity_counts},
        }

    def _sanitize_for_storage(
        self, data: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Sanitize data for MongoDB storage.
        Removes ObjectId and other non-JSON-serializable types.
        """
        if data is None:
            return None

        # Create a copy to avoid mutating original
        sanitized = {}
        for key, value in data.items():
            # Skip MongoDB _id
            if key == "_id":
                continue
            # Convert datetime objects to ISO strings
            if isinstance(value, datetime):
                sanitized[key] = value.isoformat()
            # Handle nested dicts
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_for_storage(value)
            # Handle lists
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_for_storage(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized


# Singleton instance will be created in server.py
activity_log_service: Optional[ActivityLogService] = None


def get_activity_log_service() -> ActivityLogService:
    """Get the activity log service instance"""
    if activity_log_service is None:
        raise RuntimeError("ActivityLogService not initialized")
    return activity_log_service


def init_activity_log_service(db: AsyncIOMotorDatabase) -> ActivityLogService:
    """Initialize the activity log service"""
    global activity_log_service
    activity_log_service = ActivityLogService(db)
    return activity_log_service
