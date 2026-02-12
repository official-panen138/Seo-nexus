"""
Conflict-Optimization Linker Service
=====================================

Auto-converts detected SEO conflicts into actionable optimization tasks.

Features:
1. Auto Optimization Creation - Creates optimization when conflict detected
2. Relationship Rules - One conflict → one optimization
3. Permission Enforcement - Only managers can update
4. Notification Integration - Telegram alerts on detection/resolution
5. Metrics Tracking - Time-to-resolution, conflicts per manager, recurrence
6. Fingerprint-based Recurrence Detection - Detects same conflict reappearing

Conflict Status Flow:
- detected → under_review (when optimization exists)
- resolved (when optimization marked completed AND structure validated)
"""

import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# False resolution threshold (days)
FALSE_RESOLUTION_THRESHOLD_DAYS = 7


# Conflict type labels for readable titles
CONFLICT_TYPE_LABELS = {
    "keyword_cannibalization": "Keyword Cannibalization",
    "competing_targets": "Competing Targets",
    "canonical_mismatch": "Canonical Mismatch",
    "tier_inversion": "Tier Inversion",
    "redirect_loop": "Redirect Loop",
    "multiple_parents_to_main": "Multiple Parents to Main",
    "canonical_redirect_conflict": "Canonical-Redirect Conflict",
    "index_noindex_mismatch": "Index/Noindex Mismatch",
    "orphan": "Orphan Node",
    "noindex_high_tier": "Noindex High Tier",
}

# Priority mapping based on severity
SEVERITY_PRIORITY = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}


def generate_conflict_fingerprint(
    network_id: str,
    conflict_type: str,
    domain_id: Optional[str],
    node_path: Optional[str],
    tier: Optional[int],
    target_path: Optional[str]
) -> str:
    """
    Generate a unique fingerprint for conflict recurrence detection.
    
    The fingerprint is based on structural identity, not temporary IDs.
    If the same structural conflict reappears, it will have the same fingerprint.
    """
    # Normalize path: lowercase, strip leading/trailing slashes
    normalized_path = ""
    if node_path:
        normalized_path = node_path.lower().strip("/")
    
    normalized_target = ""
    if target_path:
        normalized_target = target_path.lower().strip("/")
    
    # Build fingerprint string
    fingerprint_parts = [
        network_id or "",
        conflict_type or "",
        domain_id or "",
        normalized_path,
        str(tier) if tier is not None else "",
        normalized_target
    ]
    
    fingerprint_string = "|".join(fingerprint_parts)
    
    # Generate hash
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]


class ConflictOptimizationLinkerService:
    """
    Service to automatically link detected conflicts to optimization tasks.
    
    When a conflict is detected:
    1. Check if conflict already exists (by hash of key fields)
    2. If new: Store conflict + auto-create optimization
    3. If existing: Update recurrence count
    4. Send Telegram notifications
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    def _generate_conflict_hash(self, conflict: Dict[str, Any]) -> str:
        """
        Generate a unique hash for conflict deduplication.
        Based on: network_id + conflict_type + node_a_id + node_b_id
        """
        parts = [
            conflict.get("network_id", ""),
            conflict.get("conflict_type", ""),
            conflict.get("node_a_id", ""),
            conflict.get("node_b_id", "") or "",
        ]
        return "|".join(parts)
    
    async def process_detected_conflicts(
        self,
        conflicts: List[Dict[str, Any]],
        network_id: str,
        triggered_by: str = "system"
    ) -> Dict[str, Any]:
        """
        Process a list of detected conflicts.
        
        For each conflict:
        - If new: Store + create optimization + notify
        - If existing & resolved: Increment recurrence + re-open + notify
        - If existing & open: Update timestamp only
        
        Returns summary of processed conflicts.
        """
        now = datetime.now(timezone.utc).isoformat()
        
        new_conflicts = 0
        recurring_conflicts = 0
        optimizations_created = 0
        notifications_sent = 0
        
        # Get network info for notifications
        network = await self.db.seo_networks.find_one(
            {"id": network_id},
            {"_id": 0, "name": 1, "brand_id": 1, "created_by": 1}
        )
        network_name = network.get("name", "Unknown") if network else "Unknown"
        brand_id = network.get("brand_id") if network else None
        
        # Get existing stored conflicts for this network
        existing_conflicts = await self.db.seo_conflicts.find(
            {"network_id": network_id},
            {"_id": 0}
        ).to_list(500)
        
        existing_hashes = {
            self._generate_conflict_hash(c): c for c in existing_conflicts
        }
        
        for conflict in conflicts:
            conflict_hash = self._generate_conflict_hash(conflict)
            
            if conflict_hash in existing_hashes:
                # Existing conflict
                existing = existing_hashes[conflict_hash]
                existing_id = existing.get("id")
                existing_status = existing.get("status", "detected")
                
                if existing_status in ["resolved", "ignored"]:
                    # Conflict recurred! Re-open it
                    recurring_conflicts += 1
                    
                    await self.db.seo_conflicts.update_one(
                        {"id": existing_id},
                        {"$set": {
                            "status": "detected",
                            "recurrence_count": existing.get("recurrence_count", 0) + 1,
                            "last_recurrence_at": now,
                            "updated_at": now,
                            "optimization_id": None,  # Unlink old optimization
                        }}
                    )
                    
                    # Create new optimization for recurring conflict
                    opt_id = await self._create_optimization_for_conflict(
                        conflict_id=existing_id,
                        conflict=conflict,
                        network_id=network_id,
                        network_name=network_name,
                        brand_id=brand_id,
                        is_recurring=True,
                        recurrence_count=existing.get("recurrence_count", 0) + 1
                    )
                    
                    if opt_id:
                        optimizations_created += 1
                        
                        # Update conflict with new optimization link
                        await self.db.seo_conflicts.update_one(
                            {"id": existing_id},
                            {"$set": {"optimization_id": opt_id, "status": "under_review"}}
                        )
                    
                    # Send recurrence notification
                    await self._send_conflict_notification(
                        conflict=conflict,
                        network_name=network_name,
                        brand_id=brand_id,
                        is_new=False,
                        is_recurring=True,
                        recurrence_count=existing.get("recurrence_count", 0) + 1
                    )
                    notifications_sent += 1
                else:
                    # Still open, just update timestamp
                    await self.db.seo_conflicts.update_one(
                        {"id": existing_id},
                        {"$set": {"updated_at": now}}
                    )
            else:
                # New conflict
                new_conflicts += 1
                conflict_id = str(uuid.uuid4())
                
                # Get affected nodes
                affected_nodes = [conflict.get("node_a_id")]
                if conflict.get("node_b_id"):
                    affected_nodes.append(conflict.get("node_b_id"))
                
                # Store the conflict
                stored_conflict = {
                    "id": conflict_id,
                    "conflict_type": conflict.get("conflict_type"),
                    "severity": conflict.get("severity"),
                    "status": "detected",
                    "network_id": network_id,
                    "network_name": network_name,
                    "domain_name": conflict.get("domain_name", ""),
                    "node_a_id": conflict.get("node_a_id"),
                    "node_a_path": conflict.get("node_a_path"),
                    "node_a_label": conflict.get("node_a_label"),
                    "node_b_id": conflict.get("node_b_id"),
                    "node_b_path": conflict.get("node_b_path"),
                    "node_b_label": conflict.get("node_b_label"),
                    "affected_nodes": affected_nodes,
                    "description": conflict.get("description", ""),
                    "suggestion": conflict.get("suggestion"),
                    "detected_at": now,
                    "updated_at": now,
                    "recurrence_count": 0,
                    "optimization_id": None,
                }
                
                await self.db.seo_conflicts.insert_one(stored_conflict)
                
                # Auto-create optimization
                opt_id = await self._create_optimization_for_conflict(
                    conflict_id=conflict_id,
                    conflict=conflict,
                    network_id=network_id,
                    network_name=network_name,
                    brand_id=brand_id,
                    is_recurring=False
                )
                
                if opt_id:
                    optimizations_created += 1
                    
                    # Update conflict with optimization link and status
                    await self.db.seo_conflicts.update_one(
                        {"id": conflict_id},
                        {"$set": {"optimization_id": opt_id, "status": "under_review"}}
                    )
                
                # Send new conflict notification
                await self._send_conflict_notification(
                    conflict=conflict,
                    network_name=network_name,
                    brand_id=brand_id,
                    is_new=True,
                    is_recurring=False
                )
                notifications_sent += 1
        
        return {
            "processed": len(conflicts),
            "new_conflicts": new_conflicts,
            "recurring_conflicts": recurring_conflicts,
            "optimizations_created": optimizations_created,
            "notifications_sent": notifications_sent,
        }
    
    async def _create_optimization_for_conflict(
        self,
        conflict_id: str,
        conflict: Dict[str, Any],
        network_id: str,
        network_name: str,
        brand_id: Optional[str],
        is_recurring: bool = False,
        recurrence_count: int = 0
    ) -> Optional[str]:
        """
        Create an optimization task for a conflict.
        
        Returns optimization ID if created successfully.
        """
        now = datetime.now(timezone.utc).isoformat()
        opt_id = str(uuid.uuid4())
        
        conflict_type = conflict.get("conflict_type", "unknown")
        severity = conflict.get("severity", "medium")
        type_label = CONFLICT_TYPE_LABELS.get(conflict_type, conflict_type.replace("_", " ").title())
        
        # Build title
        recurrence_marker = f" [RECURRING #{recurrence_count}]" if is_recurring else ""
        title = f"[Conflict Resolution] {type_label}{recurrence_marker}"
        
        # Build description
        description_parts = [
            "**Auto-generated from detected SEO conflict**",
            "",
            f"**Conflict Type:** {type_label}",
            f"**Severity:** {severity.upper()}",
            f"**Network:** {network_name}",
            f"**Domain:** {conflict.get('domain_name', 'N/A')}",
            "",
            "**Description:**",
            conflict.get("description", "No description provided."),
            "",
            "**Affected Nodes:**",
            f"- {conflict.get('node_a_label', 'Node A')}",
        ]
        
        if conflict.get("node_b_label"):
            description_parts.append(f"- {conflict.get('node_b_label')}")
        
        if conflict.get("suggestion"):
            description_parts.extend([
                "",
                "**Suggested Fix:**",
                conflict.get("suggestion"),
            ])
        
        description = "\n".join(description_parts)
        
        # Build reason note
        reason_note = f"Automatically created to resolve {type_label} conflict detected in {network_name}. Severity: {severity.upper()}."
        if is_recurring:
            reason_note += f" This conflict has recurred {recurrence_count} time(s)."
        
        # Get activity type ID for conflict_resolution
        activity_type_doc = await self.db.seo_optimization_activity_types.find_one(
            {"name": {"$regex": "conflict", "$options": "i"}},
            {"_id": 0, "id": 1}
        )
        activity_type_id = activity_type_doc.get("id") if activity_type_doc else None
        
        # Get network manager for assignment
        assigned_manager = None
        if network_id:
            network_doc = await self.db.seo_networks.find_one(
                {"id": network_id},
                {"_id": 0, "created_by": 1}
            )
            if network_doc:
                assigned_manager = network_doc.get("created_by")
        
        # Create optimization
        optimization = {
            "id": opt_id,
            "network_id": network_id,
            "brand_id": brand_id,
            "created_by": {
                "user_id": "system",
                "display_name": "System (Auto)",
                "email": "system@seo-noc.local",
            },
            "created_at": now,
            "updated_at": now,
            "activity_type_id": activity_type_id,
            "activity_type": "conflict_resolution",
            "title": title,
            "description": description,
            "reason_note": reason_note,
            "affected_scope": "specific_domain",
            "target_domains": [conflict.get("domain_name", "")] if conflict.get("domain_name") else [],
            "keywords": [],
            "report_urls": [],
            "expected_impact": ["authority"],  # Conflict resolution typically impacts authority flow
            "status": "planned",  # Start as planned
            "complaint_status": "none",
            "linked_conflict_id": conflict_id,
            "assigned_to": assigned_manager,
            "priority": SEVERITY_PRIORITY.get(severity, "medium"),
        }
        
        await self.db.seo_optimizations.insert_one(optimization)
        
        logger.info(f"Created optimization {opt_id} for conflict {conflict_id}")
        
        return opt_id
    
    async def _send_conflict_notification(
        self,
        conflict: Dict[str, Any],
        network_name: str,
        brand_id: Optional[str],
        is_new: bool,
        is_recurring: bool = False,
        recurrence_count: int = 0
    ):
        """
        Send Telegram notification for conflict detection.
        
        Tags:
        - Project manager(s)
        - SEO leader
        """
        try:
            from services.seo_optimization_telegram_service import SeoOptimizationTelegramService
            telegram = SeoOptimizationTelegramService(self.db)
            
            conflict_type = conflict.get("conflict_type", "unknown")
            severity = conflict.get("severity", "medium")
            type_label = CONFLICT_TYPE_LABELS.get(conflict_type, conflict_type.replace("_", " ").title())
            
            severity_emoji = {
                "critical": "🚨",
                "high": "🔴",
                "medium": "🟠",
                "low": "🟡",
            }.get(severity, "⚪")
            
            # Build message
            if is_recurring:
                header = f"🔄 RECURRING SEO CONFLICT #{recurrence_count}"
            else:
                header = "⚠️ NEW SEO CONFLICT DETECTED"
            
            message_lines = [
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                header,
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"Type          : {type_label}",
                f"Severity      : {severity_emoji} {severity.upper()}",
                f"Network       : {network_name}",
                f"Domain        : {conflict.get('domain_name', 'N/A')}",
                "",
                "Affected Nodes:",
                f"  • {conflict.get('node_a_label', 'Node A')}",
            ]
            
            if conflict.get("node_b_label"):
                message_lines.append(f"  • {conflict.get('node_b_label')}")
            
            message_lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "📋 DESCRIPTION:",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                conflict.get("description", "No description"),
                "",
            ])
            
            if conflict.get("suggestion"):
                message_lines.extend([
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                    "💡 SUGGESTED FIX:",
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                    conflict.get("suggestion"),
                    "",
                ])
            
            message_lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "⏰ ACTION REQUIRED",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "An optimization task has been auto-created.",
                "Please review and resolve this conflict.",
            ])
            
            if is_recurring:
                message_lines.extend([
                    "",
                    f"⚠️ This conflict has recurred {recurrence_count} time(s)!",
                    "Consider a permanent structural fix.",
                ])
            
            message = "\n".join(message_lines)
            
            # Send notification
            await telegram.send_seo_change_notification(
                message=message,
                brand_id=brand_id,
                network_id=conflict.get("network_id"),
                is_conflict_alert=True
            )
            
        except Exception as e:
            logger.error(f"Failed to send conflict notification: {e}")
    
    async def resolve_conflict(
        self,
        conflict_id: str,
        resolved_by_user_id: str,
        resolution_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mark a conflict as resolved.
        
        Called when the linked optimization is marked as completed
        AND the structure has been validated.
        """
        now = datetime.now(timezone.utc).isoformat()
        
        conflict = await self.db.seo_conflicts.find_one(
            {"id": conflict_id},
            {"_id": 0}
        )
        
        if not conflict:
            return {"success": False, "error": "Conflict not found"}
        
        # Update conflict status - resolution also deactivates the conflict
        await self.db.seo_conflicts.update_one(
            {"id": conflict_id},
            {"$set": {
                "status": "resolved",
                "is_active": False,  # Deactivate to prevent appearing in recurring
                "recurrence_count": 0,  # Reset recurrence count
                "resolved_at": now,
                "updated_at": now,
                "resolution_note": resolution_note,
                "resolved_by": resolved_by_user_id,
            }}
        )
        
        # Send resolution notification
        await self._send_resolution_notification(conflict, resolved_by_user_id)
        
        return {"success": True, "status": "resolved", "is_active": False}
    
    async def _send_resolution_notification(
        self,
        conflict: Dict[str, Any],
        resolved_by_user_id: str
    ):
        """Send notification when conflict is resolved."""
        try:
            from services.seo_optimization_telegram_service import SeoOptimizationTelegramService
            telegram = SeoOptimizationTelegramService(self.db)
            
            # Get user info
            user = await self.db.users.find_one(
                {"id": resolved_by_user_id},
                {"_id": 0, "display_name": 1, "email": 1}
            )
            resolver_name = user.get("display_name", "Unknown") if user else "Unknown"
            
            conflict_type = conflict.get("conflict_type", "unknown")
            type_label = CONFLICT_TYPE_LABELS.get(conflict_type, conflict_type.replace("_", " ").title())
            
            message_lines = [
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "✅ SEO CONFLICT RESOLVED",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"Type          : {type_label}",
                f"Network       : {conflict.get('network_name', 'N/A')}",
                f"Domain        : {conflict.get('domain_name', 'N/A')}",
                f"Resolved By   : {resolver_name}",
                "",
                "The conflict has been resolved and the",
                "SEO structure has been validated.",
            ]
            
            if conflict.get("recurrence_count", 0) > 0:
                message_lines.extend([
                    "",
                    f"📊 This conflict had recurred {conflict.get('recurrence_count')} time(s).",
                ])
            
            message = "\n".join(message_lines)
            
            await telegram.send_seo_change_notification(
                message=message,
                brand_id=conflict.get("brand_id"),
                network_id=conflict.get("network_id"),
                is_conflict_alert=True
            )
            
        except Exception as e:
            logger.error(f"Failed to send resolution notification: {e}")
    
    async def get_conflict_metrics(
        self,
        network_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get conflict resolution metrics.
        
        Returns:
        - Time-to-resolution per conflict
        - Conflicts resolved per manager
        - Recurring conflicts count
        """
        from datetime import timedelta
        
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        query = {"detected_at": {"$gte": start_date}}
        if network_id:
            query["network_id"] = network_id
        
        conflicts = await self.db.seo_conflicts.find(
            query,
            {"_id": 0}
        ).to_list(500)
        
        if not conflicts:
            return {
                "period_days": days,
                "total_conflicts": 0,
                "resolved_count": 0,
                "avg_resolution_time_hours": 0,
                "recurring_conflicts": 0,
                "by_severity": {},
                "by_type": {},
                "by_resolver": {},
            }
        
        total = len(conflicts)
        # Resolved includes both 'resolved' and 'approved' status
        resolved = [c for c in conflicts if c.get("status") in ("resolved", "approved")]
        
        # CRITICAL FIX: Recurring conflicts must exclude resolved/approved/inactive
        # Only count ACTIVE conflicts with recurrence_count > 0
        recurring = [
            c for c in conflicts 
            if c.get("recurrence_count", 0) > 0 
            and c.get("is_active", True) == True
            and c.get("status") not in ("resolved", "approved", "ignored")
        ]
        
        # Calculate resolution times
        resolution_times = []
        for c in resolved:
            if c.get("detected_at") and c.get("resolved_at"):
                try:
                    detected = datetime.fromisoformat(c["detected_at"].replace("Z", "+00:00"))
                    resolved_at = datetime.fromisoformat(c["resolved_at"].replace("Z", "+00:00"))
                    hours = (resolved_at - detected).total_seconds() / 3600
                    resolution_times.append(hours)
                except Exception:
                    pass
        
        avg_resolution = sum(resolution_times) / len(resolution_times) if resolution_times else 0
        
        # Group by severity
        by_severity = {}
        for c in conflicts:
            sev = c.get("severity", "unknown")
            if sev not in by_severity:
                by_severity[sev] = {"total": 0, "resolved": 0}
            by_severity[sev]["total"] += 1
            if c.get("status") in ("resolved", "approved"):
                by_severity[sev]["resolved"] += 1
        
        # Group by type
        by_type = {}
        for c in conflicts:
            ct = c.get("conflict_type", "unknown")
            if ct not in by_type:
                by_type[ct] = {"total": 0, "resolved": 0}
            by_type[ct]["total"] += 1
            if c.get("status") in ("resolved", "approved"):
                by_type[ct]["resolved"] += 1
        
        # Group by resolver
        by_resolver = {}
        for c in resolved:
            resolver = c.get("resolved_by", "unknown")
            if resolver not in by_resolver:
                by_resolver[resolver] = 0
            by_resolver[resolver] += 1
        
        return {
            "period_days": days,
            "total_conflicts": total,
            "resolved_count": len(resolved),
            "open_count": total - len(resolved),
            "avg_resolution_time_hours": round(avg_resolution, 1),
            "recurring_conflicts": len(recurring),
            "by_severity": by_severity,
            "by_type": by_type,
            "by_resolver": by_resolver,
        }
    
    async def get_stored_conflicts(
        self,
        network_id: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get stored conflicts with optional filters."""
        query = {}
        if network_id:
            query["network_id"] = network_id
        if status:
            query["status"] = status
        if severity:
            query["severity"] = severity
        
        conflicts = await self.db.seo_conflicts.find(
            query,
            {"_id": 0}
        ).sort("detected_at", -1).limit(limit).to_list(limit)
        
        return conflicts
    
    async def get_conflict_by_id(self, conflict_id: str) -> Optional[Dict[str, Any]]:
        """Get a single conflict by ID."""
        return await self.db.seo_conflicts.find_one(
            {"id": conflict_id},
            {"_id": 0}
        )


# Global instance
_conflict_linker_service: Optional[ConflictOptimizationLinkerService] = None


def get_conflict_linker_service(db: AsyncIOMotorDatabase) -> ConflictOptimizationLinkerService:
    """Get or create the conflict linker service"""
    global _conflict_linker_service
    if _conflict_linker_service is None:
        _conflict_linker_service = ConflictOptimizationLinkerService(db)
    return _conflict_linker_service
