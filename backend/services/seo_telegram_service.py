"""
SEO Telegram Notification Service
=================================
Sends comprehensive SEO change notifications to a dedicated Telegram channel.

Features:
- Full Bahasa Indonesia messages
- Human-readable user context
- Complete SEO structure snapshot with full authority chains
- Status labels on every node
- Rate limiting and deduplication
- Fallback to main Telegram channel
"""

import logging
import httpx
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from collections import defaultdict

logger = logging.getLogger(__name__)


# Action type labels in Bahasa Indonesia
ACTION_LABELS = {
    "create_node": "Membuat Node Baru",
    "update_node": "Mengubah Node",
    "delete_node": "Menghapus Node",
    "relink_node": "Mengubah Target Node",
    "change_role": "Mengubah Role Node",
    "change_path": "Mengubah Path Node",
    "create_network": "Membuat SEO Network Baru",
}

# Status labels - Human readable
STATUS_LABELS = {
    "primary": "Primary",
    "canonical": "Canonical",
    "301_redirect": "301 Redirect",
    "302_redirect": "302 Redirect",
    "restore": "Restore",
}

# Role labels
ROLE_LABELS = {
    "main": "Main (LP)",
    "supporting": "Supporting",
}

# Index labels
INDEX_LABELS = {
    "index": "Index",
    "noindex": "NoIndex",
}


def format_node_with_status(
    domain: str, path: str = "", status: str = "", role: str = ""
) -> str:
    """
    Format a node with its status for display.
    Format: {domain}{path} [{status}]
    """
    node_label = f"{domain}{path}" if path and path != "/" else domain

    # Determine display status
    if role == "main":
        display_status = "Primary"
    else:
        display_status = STATUS_LABELS.get(
            status, status.replace("_", " ").title() if status else ""
        )

    if display_status:
        return f"{node_label} [{display_status}]"
    return node_label


class SeoTelegramService:
    """Service for sending SEO change notifications via Telegram"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        # Rate limiting: track last message time per network
        self._last_notification_time: Dict[str, datetime] = {}
        self._rate_limit_seconds = 60  # 1 minute per network

    async def _get_telegram_settings(self) -> Optional[Dict[str, Any]]:
        """
        Get Telegram settings for SEO notifications.
        Falls back to main Telegram if SEO channel not configured.
        """
        # Try SEO-specific channel first
        settings = await self.db.settings.find_one({"key": "telegram_seo"}, {"_id": 0})

        if (
            settings
            and settings.get("enabled", True)
            and settings.get("bot_token")
            and settings.get("chat_id")
        ):
            return settings

        # Fallback to main Telegram channel
        logger.info(
            "SEO Telegram channel not configured, using main channel as fallback"
        )
        main_settings = await self.db.settings.find_one({"key": "telegram"}, {"_id": 0})

        if (
            main_settings
            and main_settings.get("bot_token")
            and main_settings.get("chat_id")
        ):
            return main_settings

        logger.warning("No Telegram channel configured for SEO notifications")
        return None

    async def _get_seo_leader_tag(self) -> str:
        """
        Get the SEO Leader's Telegram tags for global notification tagging.
        Supports multiple leaders. Returns @username format or empty string if not configured.
        """
        settings = await self.db.settings.find_one({"key": "telegram_seo"}, {"_id": 0})
        if not settings:
            return ""
        
        # Try multiple leaders first (new format)
        leaders = settings.get("seo_leader_telegram_usernames", [])
        if not leaders:
            # Fallback to legacy single leader
            single = settings.get("seo_leader_telegram_username")
            if single:
                leaders = [single]
        
        if not leaders:
            return ""
        
        tags = []
        for username in leaders:
            if username:
                # Ensure @ prefix
                if not username.startswith("@"):
                    username = f"@{username}"
                tags.append(username)
        
        return " ".join(tags) if tags else ""
    
    async def _get_seo_leader_usernames(self) -> List[str]:
        """
        Get SEO Leader Telegram usernames WITHOUT @ prefix (for template engine).
        Returns list of raw usernames.
        """
        settings = await self.db.settings.find_one({"key": "telegram_seo"}, {"_id": 0})
        if not settings:
            return []
        
        # Try multiple leaders first (new format)
        leaders = settings.get("seo_leader_telegram_usernames", [])
        if not leaders:
            # Fallback to legacy single leader
            single = settings.get("seo_leader_telegram_username")
            if single:
                leaders = [single]
        
        if not leaders:
            return []
        
        # Return usernames without @ prefix
        return [username.replace("@", "") for username in leaders if username]

    async def _get_network_manager_tags(self, network_id: str) -> List[str]:
        """
        Get Telegram tags for all managers of a specific network.
        Returns list of @username tags.
        """
        network = await self.db.seo_networks.find_one(
            {"id": network_id}, {"_id": 0, "manager_ids": 1}
        )
        if not network or not network.get("manager_ids"):
            return []

        # Get users with their telegram usernames
        managers = await self.db.users.find(
            {"id": {"$in": network["manager_ids"]}},
            {"_id": 0, "telegram_username": 1, "name": 1, "email": 1}
        ).to_list(100)

        tags = []
        for manager in managers:
            if manager.get("telegram_username"):
                username = manager["telegram_username"]
                if not username.startswith("@"):
                    username = f"@{username}"
                tags.append(username)
            else:
                # Fallback: mention by name/email if no telegram
                name = manager.get("name") or manager.get("email", "Unknown")
                tags.append(f"{name} (no Telegram)")
        
        return tags

    async def _send_telegram_message(
        self, message: str, topic_type: str = None
    ) -> bool:
        """
        Send message to Telegram with optional forum topic routing.

        topic_type can be:
        - "seo_change" → Uses seo_change_topic_id
        - "seo_optimization" → Uses seo_optimization_topic_id
        - "seo_complaint" → Uses seo_complaint_topic_id
        - "seo_reminder" → Uses seo_reminder_topic_id
        - None → Sends to General (no topic)
        """
        settings = await self._get_telegram_settings()
        if not settings:
            return False

        # Determine message_thread_id for forum topic routing
        message_thread_id = None
        if settings.get("enable_topic_routing") and topic_type:
            topic_id_field = f"{topic_type}_topic_id"
            message_thread_id = settings.get(topic_id_field)
            if not message_thread_id:
                logger.warning(
                    f"Topic routing enabled but {topic_id_field} not configured, sending to General"
                )

        try:
            url = f"https://api.telegram.org/bot{settings['bot_token']}/sendMessage"

            payload = {
                "chat_id": settings["chat_id"],
                "text": message,
                "parse_mode": "HTML",
            }

            # Add message_thread_id for forum topic
            if message_thread_id:
                payload["message_thread_id"] = int(message_thread_id)

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=15)

                if response.status_code == 200:
                    topic_info = f" (topic: {topic_type})" if message_thread_id else ""
                    logger.info(f"SEO Telegram notification sent{topic_info}")
                    return True
                else:
                    # Check if error is due to invalid topic_id
                    error_text = response.text.lower()
                    if message_thread_id and ("thread" in error_text or "topic" in error_text or "message_thread_id" in error_text):
                        logger.warning(
                            f"Invalid topic_id '{message_thread_id}' for {topic_type}. Retrying without topic routing..."
                        )
                        # Retry without message_thread_id
                        del payload["message_thread_id"]
                        retry_response = await client.post(url, json=payload, timeout=15)
                        if retry_response.status_code == 200:
                            logger.info(f"SEO Telegram notification sent (fallback to main chat after invalid topic_id)")
                            return True
                        else:
                            logger.error(f"Telegram API error (retry): {retry_response.status_code} - {retry_response.text}")
                            return False
                    
                    logger.error(
                        f"Telegram API error: {response.status_code} - {response.text}"
                    )
                    return False
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def _check_rate_limit(self, network_id: str) -> bool:
        """
        Check if we can send a notification for this network.
        Returns True if allowed, False if rate limited.
        """
        now = datetime.now(timezone.utc)
        last_time = self._last_notification_time.get(network_id)

        if last_time:
            elapsed = (now - last_time).total_seconds()
            if elapsed < self._rate_limit_seconds:
                logger.warning(
                    f"Rate limited: Network {network_id}, {self._rate_limit_seconds - elapsed:.0f}s remaining"
                )
                return False

        return True

    def _update_rate_limit(self, network_id: str):
        """Update the last notification time for a network"""
        self._last_notification_time[network_id] = datetime.now(timezone.utc)

    async def _get_user_display_name(self, user_id: str, email: str) -> str:
        """Get user's display name, fallback to email prefix"""
        if user_id:
            user = await self.db.users.find_one({"id": user_id}, {"_id": 0, "name": 1})
            if user and user.get("name"):
                return user["name"]

        # Fallback to email prefix
        return email.split("@")[0].title() if email else "Unknown"

    async def _resolve_entry_to_label(
        self, entry_id: str, domain_lookup: Dict[str, str], entry_lookup: Dict[str, Any]
    ) -> str:
        """
        Resolve an entry ID to a human-readable label with status.
        Returns: "domain.com/path [Status]"
        """
        if not entry_id:
            return None

        entry = entry_lookup.get(entry_id)
        if not entry:
            # Try to fetch from DB if not in lookup
            entry = await self.db.seo_structure_entries.find_one(
                {"id": entry_id}, {"_id": 0}
            )
            if not entry:
                return None

        domain_name = domain_lookup.get(entry.get("asset_domain_id"), "unknown")
        path = entry.get("optimized_path", "")
        status = entry.get("domain_status", "")
        role = entry.get("domain_role", "")

        return format_node_with_status(domain_name, path, status, role)

    async def _build_full_authority_chain(
        self,
        entry: Dict[str, Any],
        domain_lookup: Dict[str, str],
        entry_lookup: Dict[str, Any],
        visited: set = None,
    ) -> str:
        """
        Build the complete authority chain from a node to its final destination (main node).
        Returns: "node1 [Status] → node2 [Status] → main [Primary]"
        """
        if visited is None:
            visited = set()

        # Prevent infinite loops
        if entry["id"] in visited:
            return "⚠️ Circular Reference"
        visited.add(entry["id"])

        # Format current node
        domain_name = domain_lookup.get(entry.get("asset_domain_id"), "unknown")
        path = entry.get("optimized_path", "")
        status = entry.get("domain_status", "")
        role = entry.get("domain_role", "")

        current_label = format_node_with_status(domain_name, path, status, role)

        # If this is the main node (final destination), stop here
        if role == "main" or not entry.get("target_entry_id"):
            return current_label

        # Get target and build chain recursively
        target_entry = entry_lookup.get(entry.get("target_entry_id"))
        if not target_entry:
            return current_label

        target_chain = await self._build_full_authority_chain(
            target_entry, domain_lookup, entry_lookup, visited
        )

        return f"{current_label} → {target_chain}"

    async def _get_network_structure_with_chains(
        self, network_id: str
    ) -> Dict[str, List[str]]:
        """
        Get the current SEO structure for a network with FULL authority chains.
        Returns dict with tier labels as keys and list of full chain strings as values.
        """
        entries = await self.db.seo_structure_entries.find(
            {"network_id": network_id}, {"_id": 0}
        ).to_list(1000)

        if not entries:
            return {}

        # Build domain lookup
        domain_ids = list(
            set(e.get("asset_domain_id") for e in entries if e.get("asset_domain_id"))
        )
        domains = await self.db.asset_domains.find(
            {"id": {"$in": domain_ids}}, {"_id": 0, "id": 1, "domain_name": 1}
        ).to_list(1000)
        domain_lookup = {d["id"]: d["domain_name"] for d in domains}

        # Build entry lookup
        entry_lookup = {e["id"]: e for e in entries}

        # Calculate tiers using BFS from main nodes
        main_entries = [e for e in entries if e.get("domain_role") == "main"]
        tiers = {}

        if main_entries:
            queue = [(e["id"], 0) for e in main_entries]
            visited = set()

            while queue:
                entry_id, tier = queue.pop(0)
                if entry_id in visited:
                    continue
                visited.add(entry_id)
                tiers[entry_id] = tier

                # Find entries pointing to this one (reverse direction for tier calc)
                for e in entries:
                    if e.get("target_entry_id") == entry_id and e["id"] not in visited:
                        queue.append((e["id"], tier + 1))

        # Assign orphans to tier -1
        for e in entries:
            if e["id"] not in tiers:
                tiers[e["id"]] = -1

        # Build full chains grouped by tier
        tier_groups = defaultdict(list)

        for entry in entries:
            tier = tiers.get(entry["id"], -1)

            # Build the full authority chain for this entry
            full_chain = await self._build_full_authority_chain(
                entry, domain_lookup, entry_lookup
            )

            tier_groups[tier].append(
                {
                    "chain": full_chain,
                    "domain_name": domain_lookup.get(entry.get("asset_domain_id"), ""),
                    "role": entry.get("domain_role"),
                }
            )

        # Convert to labeled groups and sort
        tier_labels = {
            0: "LP / Money Site",
            1: "Tier 1",
            2: "Tier 2",
            3: "Tier 3",
            4: "Tier 4",
            5: "Tier 5+",
            -1: "Orphan (Tidak Terhubung)",
        }

        result = {}
        for tier in sorted(tier_groups.keys()):
            label = tier_labels.get(tier, f"Tier {tier}")
            entries_list = tier_groups[tier]

            # Sort: main first, then alphabetically by domain
            entries_list.sort(
                key=lambda x: (0 if x["role"] == "main" else 1, x["domain_name"])
            )

            result[label] = [e["chain"] for e in entries_list]

        return result

    def _format_structure_snapshot(self, structure: Dict[str, List[str]]) -> str:
        """Format the structure snapshot with full authority chains for Telegram message"""
        if not structure:
            return "Tidak ada node dalam network ini."

        lines = []
        for tier_label, chains in structure.items():
            lines.append(f"<b>{tier_label}:</b>")
            for chain in chains:
                lines.append(f"  • {chain}")
            lines.append("")  # Empty line between tiers

        return "\n".join(lines).strip()

    async def _resolve_target_simple(
        self,
        target_entry_id: str,
        domain_lookup: Dict[str, str] = None,
        entry_lookup: Dict[str, Any] = None,
    ) -> str:
        """
        Resolve a target entry ID to SIMPLE format: domain/path (NO STATUS).
        Used for BEFORE/AFTER sections where we only show the target location.
        Status annotations belong ONLY in STRUKTUR SEO TERKINI section.
        """
        if not target_entry_id:
            return None

        # Get the target entry
        target_entry = None
        if entry_lookup:
            target_entry = entry_lookup.get(target_entry_id)

        if not target_entry:
            target_entry = await self.db.seo_structure_entries.find_one(
                {"id": target_entry_id}, {"_id": 0}
            )

        if not target_entry:
            return None

        # Get domain name
        domain_name = None
        if domain_lookup:
            domain_name = domain_lookup.get(target_entry.get("asset_domain_id"))

        if not domain_name:
            domain = await self.db.asset_domains.find_one(
                {"id": target_entry.get("asset_domain_id")},
                {"_id": 0, "domain_name": 1},
            )
            domain_name = domain["domain_name"] if domain else "unknown"

        path = target_entry.get("optimized_path", "")

        # Return ONLY domain + path (NO STATUS)
        if path and path != "/":
            return f"{domain_name}{path}"
        return domain_name

    def _format_change_details(
        self,
        action_type: str,
        affected_node: str,
        before: Optional[Dict[str, Any]],
        after: Optional[Dict[str, Any]],
        before_target_label: str = None,
        after_target_label: str = None,
    ) -> str:
        """Format the change details section with full human-readable labels"""
        lines = ["🔄 <b>Detail Perubahan:</b>"]
        lines.append(f"• Node: {affected_node}")

        if action_type == "create_node":
            # New node created
            if after:
                role = ROLE_LABELS.get(
                    after.get("domain_role"), after.get("domain_role", "-")
                )
                status = STATUS_LABELS.get(
                    after.get("domain_status"), after.get("domain_status", "-")
                )
                index = INDEX_LABELS.get(
                    after.get("index_status"), after.get("index_status", "-")
                )
                target = after_target_label or "-"

                lines.append(f"• Role: {role}")
                lines.append(f"• Status: {status}")
                lines.append(f"• Index: {index}")
                if target and target != "-":
                    lines.append(f"• Target: {target}")

        elif action_type == "delete_node":
            # Node deleted
            if before:
                role = ROLE_LABELS.get(
                    before.get("domain_role"), before.get("domain_role", "-")
                )
                status = STATUS_LABELS.get(
                    before.get("domain_status"), before.get("domain_status", "-")
                )
                lines.append(f"• Role (sebelum dihapus): {role}")
                lines.append(f"• Status (sebelum dihapus): {status}")
            lines.append("• Status Sekarang: <b>DIHAPUS</b>")

        elif action_type == "relink_node":
            # Target changed
            role = ROLE_LABELS.get(
                (after or before or {}).get("domain_role"),
                (after or before or {}).get("domain_role", "-"),
            )
            status = STATUS_LABELS.get(
                (after or before or {}).get("domain_status"),
                (after or before or {}).get("domain_status", "-"),
            )

            lines.append(f"• Role: {role}")
            lines.append(f"• Status: {status}")
            lines.append(f"• Target Sebelumnya: {before_target_label or '-'}")
            lines.append(f"• Target Baru: {after_target_label or '-'}")

        elif action_type == "change_role":
            # Role changed
            before_role = (
                ROLE_LABELS.get(
                    before.get("domain_role"), before.get("domain_role", "-")
                )
                if before
                else "-"
            )
            after_role = (
                ROLE_LABELS.get(after.get("domain_role"), after.get("domain_role", "-"))
                if after
                else "-"
            )
            after_status = (
                STATUS_LABELS.get(
                    after.get("domain_status"), after.get("domain_status", "-")
                )
                if after
                else "-"
            )

            lines.append(f"• Role Sebelumnya: {before_role}")
            lines.append(f"• Role Baru: {after_role}")
            lines.append(f"• Status: {after_status}")

        elif action_type == "change_path":
            # Path changed
            before_path = before.get("optimized_path", "/") if before else "/"
            after_path = after.get("optimized_path", "/") if after else "/"
            lines.append(f"• Path Sebelumnya: {before_path or '/'}")
            lines.append(f"• Path Baru: {after_path or '/'}")

        else:
            # Generic update - show before/after comparison
            if before and after:
                lines.append("")
                lines.append("<b>Sebelum:</b>")
                before_role = ROLE_LABELS.get(
                    before.get("domain_role"), before.get("domain_role", "-")
                )
                before_status = STATUS_LABELS.get(
                    before.get("domain_status"), before.get("domain_status", "-")
                )
                before_index = INDEX_LABELS.get(
                    before.get("index_status"), before.get("index_status", "-")
                )
                lines.append(f"  • Role: {before_role}")
                lines.append(f"  • Status: {before_status}")
                lines.append(f"  • Index: {before_index}")
                if before_target_label:
                    lines.append(f"  • Target: {before_target_label}")

                lines.append("")
                lines.append("<b>Sesudah:</b>")
                after_role = ROLE_LABELS.get(
                    after.get("domain_role"), after.get("domain_role", "-")
                )
                after_status = STATUS_LABELS.get(
                    after.get("domain_status"), after.get("domain_status", "-")
                )
                after_index = INDEX_LABELS.get(
                    after.get("index_status"), after.get("index_status", "-")
                )
                lines.append(f"  • Role: {after_role}")
                lines.append(f"  • Status: {after_status}")
                lines.append(f"  • Index: {after_index}")
                if after_target_label:
                    lines.append(f"  • Target: {after_target_label}")
            elif after:
                role = ROLE_LABELS.get(
                    after.get("domain_role"), after.get("domain_role", "-")
                )
                status = STATUS_LABELS.get(
                    after.get("domain_status"), after.get("domain_status", "-")
                )
                index = INDEX_LABELS.get(
                    after.get("index_status"), after.get("index_status", "-")
                )
                lines.append(f"• Role: {role}")
                lines.append(f"• Status: {status}")
                lines.append(f"• Index: {index}")

        return "\n".join(lines)

    async def send_seo_change_notification(
        self,
        network_id: str,
        brand_id: str,
        actor_user_id: str,
        actor_email: str,
        action_type: str,
        affected_node: str,
        change_note: str,
        before_snapshot: Optional[Dict[str, Any]] = None,
        after_snapshot: Optional[Dict[str, Any]] = None,
        change_log_id: Optional[str] = None,
        skip_rate_limit: bool = False,
    ) -> bool:
        """
        Send SEO change notification to Telegram with full human-readable details.
        Uses template system with fallback to hardcoded message.

        Returns True if sent, False if rate limited or failed.
        """
        from services.notification_template_engine import render_notification
        
        # Check rate limit
        if not skip_rate_limit and not self._check_rate_limit(network_id):
            return False

        try:
            # Get network info
            network = await self.db.seo_networks.find_one(
                {"id": network_id}, {"_id": 0, "name": 1}
            )
            network_name = (
                network.get("name", "Unknown Network") if network else "Unknown Network"
            )

            # Get brand info
            brand = await self.db.brands.find_one(
                {"id": brand_id}, {"_id": 0, "name": 1}
            )
            brand_name = (
                brand.get("name", "Unknown Brand") if brand else "Unknown Brand"
            )

            # Get user display name
            user_display_name = await self._get_user_display_name(
                actor_user_id, actor_email
            )

            # Format action label
            action_label = ACTION_LABELS.get(action_type, action_type)

            # Format timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

            # Get SEO Leader tags
            seo_leaders = await self._get_seo_leader_usernames()
            seo_leader_tag = await self._get_seo_leader_tag()

            # ================================================================
            # SPECIAL HANDLING FOR DELETE NODE
            # ================================================================
            is_delete = action_type in ["delete_node", "DELETE_NODE"]
            if hasattr(action_type, "value"):
                is_delete = is_delete or action_type.value == "delete_node"
            
            if is_delete and before_snapshot:
                # Use seo_node_deleted template for DELETE operations
                message = await self._build_delete_notification(
                    before_snapshot=before_snapshot,
                    network_name=network_name,
                    brand_name=brand_name,
                    user_display_name=user_display_name,
                    actor_email=actor_email,
                    change_note=change_note,
                    seo_leaders=seo_leaders,
                    seo_leader_tag=seo_leader_tag,
                    timestamp=timestamp,
                )
            else:
                # Standard update/create notification
                message = await self._build_change_notification(
                    network_id=network_id,
                    network_name=network_name,
                    brand_name=brand_name,
                    user_display_name=user_display_name,
                    actor_email=actor_email,
                    actor_user_id=actor_user_id,
                    action_type=action_type,
                    action_label=action_label,
                    affected_node=affected_node,
                    change_note=change_note,
                    before_snapshot=before_snapshot,
                    after_snapshot=after_snapshot,
                    seo_leaders=seo_leaders,
                    seo_leader_tag=seo_leader_tag,
                    timestamp=timestamp,
                )

            # Send message with topic routing
            success = await self._send_telegram_message(
                message, topic_type="seo_change"
            )

            if success:
                # Update rate limit tracker
                self._update_rate_limit(network_id)
                logger.info(f"SEO notification sent for network {network_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to send SEO change notification: {e}")
            return False

    async def _build_delete_notification(
        self,
        before_snapshot: Dict[str, Any],
        network_name: str,
        brand_name: str,
        user_display_name: str,
        actor_email: str,
        change_note: str,
        seo_leaders: List[str],
        seo_leader_tag: str,
        timestamp: str,
    ) -> str:
        """Build DELETE node notification with full pre-deletion details."""
        from services.notification_template_engine import render_notification
        
        # Extract enriched data from before_snapshot
        node_label = before_snapshot.get("node_label", before_snapshot.get("domain_name", "Unknown"))
        domain_role = before_snapshot.get("domain_role", "unknown")
        domain_status = before_snapshot.get("domain_status", "unknown")
        index_status = before_snapshot.get("index_status", "unknown")
        target_info = before_snapshot.get("target_info")
        upstream_chain = before_snapshot.get("upstream_chain", [])
        affected_children = before_snapshot.get("affected_children", [])
        orphan_count = before_snapshot.get("orphan_count", 0)
        structure_before = before_snapshot.get("structure_before", [])
        
        # Format role label
        role_labels = {
            "main": "LP / Money Site",
            "supporting": "Supporting / Tier 2",
            "tier3": "Tier 3",
            "pbn": "PBN",
        }
        role_label = role_labels.get(domain_role, domain_role)
        
        # Format status label
        status_labels = {
            "canonical": "Canonical",
            "301_redirect": "301 Redirect",
            "302_redirect": "302 Redirect",
            "primary": "Primary",
            "noindex": "No Index",
        }
        status_label = status_labels.get(domain_status, domain_status)
        
        # ================================================================
        # BUILD CHAIN STRUCTURE: node → target → ... → END
        # ================================================================
        is_orphan = not target_info
        
        # Build the chain from deleted node to money site
        chain_lines = []
        
        # Start with deleted node
        chain_lines.append(f"🗑️ {node_label} [{status_label}]")
        
        if is_orphan:
            # Orphan node - no target
            chain_lines.append("   → END: ⚠️ ORPHAN NODE (tidak ada target)")
        else:
            # Has target - build the chain
            if target_info:
                target_role_label = role_labels.get(target_info.get('role', ''), target_info.get('role', ''))
                chain_lines.append(f"   → {target_info.get('full_label', 'unknown')} [{target_role_label}]")
            
            # Continue with upstream chain
            for item in upstream_chain:
                item_role_label = role_labels.get(item.get('role', ''), item.get('role', ''))
                
                if item.get('role') == 'main':
                    chain_lines.append(f"   → 💰 {item['label']} [{item_role_label}]")
                    chain_lines.append("   → END: 💰 MONEY SITE")
                else:
                    chain_lines.append(f"   → {item['label']} [{item_role_label}]")
            
            # If chain doesn't end with money site, add end marker
            if not upstream_chain or upstream_chain[-1].get('role') != 'main':
                if target_info and target_info.get('role') == 'main':
                    chain_lines.append("   → END: 💰 MONEY SITE")
                elif not upstream_chain:
                    chain_lines.append("   → END: (chain tidak lengkap)")
        
        chain_text = "\n".join(chain_lines)
        
        # Format affected children (downstream nodes that will be orphaned)
        affected_text = "(Tidak ada)"
        if affected_children:
            affected_text = "\n".join([f"  • {child}" for child in affected_children[:5]])
            if len(affected_children) > 5:
                affected_text += f"\n  ... dan {len(affected_children) - 5} node lainnya"
        
        # Format full structure before deletion showing all nodes
        structure_lines = []
        for entry in structure_before:
            is_deleted = entry.get("is_deleted_node")
            marker = "🗑️ " if is_deleted else "   "
            role_emoji = "💰" if entry.get("role") == "main" else "🔗"
            entry_status = status_labels.get(entry.get('status', ''), entry.get('status', ''))
            structure_lines.append(f"{marker}{role_emoji} {entry['label']} [{entry_status}]")
        
        if not structure_lines:
            full_structure_text = "(Tidak ada struktur)"
        else:
            full_structure_text = "\n".join(structure_lines)
        
        # Try to use template system
        message = await render_notification(
            db=self.db,
            channel="telegram",
            event_type="seo_node_deleted",
            context_data={
                "user": {"display_name": user_display_name, "email": actor_email},
                "network": {"name": network_name},
                "brand": {"name": brand_name},
                "node": {
                    "domain_name": node_label,
                    "full_path": "",
                    "domain_role": role_label,
                    "domain_status": status_label,
                    "index_status": index_status,
                    "is_orphan": is_orphan,
                },
                "change": {
                    "action": "delete_node",
                    "action_label": "Menghapus Node",
                    "reason": change_note,
                },
                "structure": {
                    "chain": chain_text,
                    "before_deletion": full_structure_text,
                },
                "impact": {
                    "severity": "HIGH" if orphan_count > 0 else ("MEDIUM" if is_orphan else "LOW"),
                    "description": f"{orphan_count} node terdampak" if orphan_count > 0 else "Tidak ada node terdampak",
                    "affected_count": orphan_count,
                    "affected_children": affected_text,
                },
                "telegram_leaders": seo_leaders,
            }
        )
        
        # Fallback to hardcoded if template disabled or failed
        if not message:
            leader_section = ""
            if seo_leader_tag:
                leader_section = f"\n\n👁 <b>CC:</b> {seo_leader_tag}"
            
            message = f"""🗑️ <b>NODE SEO DIHAPUS</b>

<b>{user_display_name}</b> telah menghapus node dari network '<b>{network_name}</b>' untuk brand '<b>{brand_name}</b>'.

━━━━━━━━━━━━━━━━━━━━━━
📌 <b>DETAIL NODE (SEBELUM DIHAPUS)</b>
━━━━━━━━━━━━━━━━━━━━━━
• <b>Node:</b> {node_label}
• <b>Role:</b> {role_label}
• <b>Status:</b> {status_label}
• <b>Index:</b> {index_status}

━━━━━━━━━━━━━━━━━━━━━━
🔗 <b>UPSTREAM CHAIN (KE MONEY SITE)</b>
━━━━━━━━━━━━━━━━━━━━━━
{chain_text}

━━━━━━━━━━━━━━━━━━━━━━
📝 <b>ALASAN PENGHAPUSAN</b>
━━━━━━━━━━━━━━━━━━━━━━
"{change_note}"

━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>DAMPAK PENGHAPUSAN</b>
━━━━━━━━━━━━━━━━━━━━━━
• <b>Authority Flow:</b> TERPUTUS
• <b>Node Terdampak ({orphan_count}):</b>
{affected_text}

━━━━━━━━━━━━━━━━━━━━━━
🧭 <b>STRUKTUR SEO (SEBELUM PENGHAPUSAN)</b>
━━━━━━━━━━━━━━━━━━━━━━
{full_structure_text}
━━━━━━━━━━━━━━━━━━━━━━
🕐 <b>Waktu:</b> {timestamp}
👤 <b>Oleh:</b> {user_display_name} ({actor_email}){leader_section}"""
        
        return message

    async def _build_change_notification(
        self,
        network_id: str,
        network_name: str,
        brand_name: str,
        user_display_name: str,
        actor_email: str,
        actor_user_id: str,
        action_type: str,
        action_label: str,
        affected_node: str,
        change_note: str,
        before_snapshot: Optional[Dict[str, Any]],
        after_snapshot: Optional[Dict[str, Any]],
        seo_leaders: List[str],
        seo_leader_tag: str,
        timestamp: str,
    ) -> str:
        """Build standard UPDATE/CREATE notification."""
        from services.notification_template_engine import render_notification
        
        # Resolve target labels for before/after
        before_target_label = None
        after_target_label = None

        if before_snapshot and before_snapshot.get("target_entry_id"):
            before_target_label = await self._resolve_target_simple(
                before_snapshot.get("target_entry_id")
            )

        if after_snapshot and after_snapshot.get("target_entry_id"):
            after_target_label = await self._resolve_target_simple(
                after_snapshot.get("target_entry_id")
            )

        # Get current structure with full authority chains
        structure = await self._get_network_structure_with_chains(network_id)
        structure_text = self._format_structure_snapshot(structure)

        # Build change details with resolved targets
        change_details = self._format_change_details(
            action_type,
            affected_node,
            before_snapshot,
            after_snapshot,
            before_target_label,
            after_target_label,
        )
        
        # Try to use template system
        message = await render_notification(
            db=self.db,
            channel="telegram",
            event_type="seo_change",
            context_data={
                "user": {"display_name": user_display_name, "email": actor_email, "id": actor_user_id},
                "network": {"name": network_name, "id": network_id},
                "brand": {"name": brand_name},
                "change": {
                    "action": action_type,
                    "action_label": action_label,
                    "reason": change_note,
                    "details": change_details,
                    "before": before_target_label or "",
                    "after": after_target_label or "",
                },
                "structure": {"current": structure_text},
                "telegram_leaders": seo_leaders,
            }
        )

        # Fallback to hardcoded if template disabled or failed
        if not message:
            logger.warning("Template returned None, using fallback hardcoded message")
            leader_section = ""
            if seo_leader_tag:
                leader_section = f"\n\n👁 <b>CC:</b> {seo_leader_tag}"

            message = f"""👤 <b>PEMBARUAN OPTIMASI BAGAN SEO</b>

{user_display_name} telah melakukan perubahan optimasi bagan SEO pada network '<b>{network_name}</b>' untuk brand '<b>{brand_name}</b>', dengan detail sebagai berikut:

━━━━━━━━━━━━━━━━━━━━━━
📌 <b>RINGKASAN AKSI</b>
━━━━━━━━━━━━━━━━━━━━━━
• Aksi: {action_label}
• Dilakukan Oleh: {user_display_name} ({actor_email})
• Waktu: {timestamp}

━━━━━━━━━━━━━━━━━━━━━━
📝 <b>ALASAN PERUBAHAN</b>
━━━━━━━━━━━━━━━━━━━━━━
"{change_note}"

━━━━━━━━━━━━━━━━━━━━━━
{change_details}

━━━━━━━━━━━━━━━━━━━━━━
🧭 <b>STRUKTUR SEO TERKINI</b>
━━━━━━━━━━━━━━━━━━━━━━
{structure_text}{leader_section}"""
        else:
            logger.info("Using template-rendered message")

        return message

    async def send_network_creation_notification(
        self,
        network_id: str,
        network_name: str,
        brand_id: str,
        actor_user_id: str,
        actor_email: str,
        main_node_label: Optional[str] = None,
        change_log_id: Optional[str] = None,
    ) -> bool:
        """
        Send notification for new SEO network creation.
        """
        try:
            # Get brand info
            brand = await self.db.brands.find_one(
                {"id": brand_id}, {"_id": 0, "name": 1}
            )
            brand_name = (
                brand.get("name", "Unknown Brand") if brand else "Unknown Brand"
            )

            # Get user display name
            user_display_name = await self._get_user_display_name(
                actor_user_id, actor_email
            )

            # Format timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

            # Get initial structure (may be empty or have 1 main node)
            structure = await self._get_network_structure_with_chains(network_id)
            structure_text = (
                self._format_structure_snapshot(structure)
                if structure
                else "Belum ada node dalam network ini."
            )

            # Build message
            # Get SEO Leader tag for global oversight
            seo_leader_tag = await self._get_seo_leader_tag()
            leader_section = ""
            if seo_leader_tag:
                leader_section = f"\n\n👁 <b>CC:</b> {seo_leader_tag}"

            message = f"""👤 <b>SEO NETWORK BARU DIBUAT</b>

{user_display_name} telah membuat SEO Network baru '<b>{network_name}</b>' untuk brand '<b>{brand_name}</b>'.

━━━━━━━━━━━━━━━━━━━━━━
📌 <b>DETAIL NETWORK BARU</b>
━━━━━━━━━━━━━━━━━━━━━━
• Nama Network: {network_name}
• Brand: {brand_name}
• Dibuat Oleh: {user_display_name} ({actor_email})
• Waktu: {timestamp}
{f'• Target Utama: {main_node_label}' if main_node_label else ''}

━━━━━━━━━━━━━━━━━━━━━━
🧭 <b>STRUKTUR SEO AWAL</b>
━━━━━━━━━━━━━━━━━━━━━━
{structure_text}{leader_section}"""

            # Send message with topic routing
            success = await self._send_telegram_message(
                message, topic_type="seo_change"
            )

            if success:
                self._update_rate_limit(network_id)
                logger.info(f"Network creation notification sent for {network_name}")

            return success

        except Exception as e:
            logger.error(f"Failed to send network creation notification: {e}")
            return False

    async def send_test_notification(self, actor_email: str) -> bool:
        """
        Send a test notification to verify Telegram configuration.
        Clearly labeled as TEST. Uses template system.
        """
        from services.notification_template_engine import render_notification
        
        user_display_name = actor_email.split("@")[0].title()
        
        # Try to use template system
        message = await render_notification(
            db=self.db,
            channel="telegram",
            event_type="test",
            context_data={
                "user": {"display_name": user_display_name, "email": actor_email},
            }
        )
        
        # Fallback to hardcoded if template disabled or not found
        if not message:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            message = f"""🔔 <b>PESAN TEST - TIDAK ADA PERUBAHAN SEO</b>

Ini adalah pesan test dari sistem notifikasi SEO.

━━━━━━━━━━━━━━━━━━━━━━
📌 <b>DETAIL TEST</b>
━━━━━━━━━━━━━━━━━━━━━━
• Dikirim Oleh: {user_display_name} ({actor_email})
• Waktu: {timestamp}
• Channel: SEO Change Notifications

✅ Jika Anda melihat pesan ini, konfigurasi Telegram untuk notifikasi SEO sudah benar!

<i>TEST MESSAGE - NO SEO CHANGE APPLIED</i>"""

        return await self._send_telegram_message(message, topic_type="seo_change")
