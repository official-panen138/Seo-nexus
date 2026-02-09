"""
SEO Telegram Notification Service
=================================
Sends comprehensive SEO change notifications to a dedicated Telegram channel.

Features:
- Full Bahasa Indonesia messages
- Human-readable user context
- Complete SEO structure snapshot
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
    "create_node": "Membuat Node",
    "update_node": "Mengubah Node",
    "delete_node": "Menghapus Node",
    "relink_node": "Mengubah Target Node",
    "change_role": "Mengubah Role Node",
    "change_path": "Mengubah Path Node",
    "create_network": "Membuat SEO Network",
}

# Status labels in Bahasa Indonesia
STATUS_LABELS = {
    "primary": "Primary",
    "canonical": "Canonical",
    "301_redirect": "301 Redirect",
    "302_redirect": "302 Redirect",
    "restore": "Restore",
}

# Role labels in Bahasa Indonesia
ROLE_LABELS = {
    "main": "Main (Target Utama)",
    "supporting": "Supporting",
}

# Index labels
INDEX_LABELS = {
    "index": "Index",
    "noindex": "NoIndex",
}


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
        
        if settings and settings.get("enabled", True) and settings.get("bot_token") and settings.get("chat_id"):
            return settings
        
        # Fallback to main Telegram channel
        logger.info("SEO Telegram channel not configured, using main channel as fallback")
        main_settings = await self.db.settings.find_one({"key": "telegram"}, {"_id": 0})
        
        if main_settings and main_settings.get("bot_token") and main_settings.get("chat_id"):
            return main_settings
        
        logger.warning("No Telegram channel configured for SEO notifications")
        return None
    
    async def _send_telegram_message(self, message: str) -> bool:
        """Send message to Telegram"""
        settings = await self._get_telegram_settings()
        if not settings:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{settings['bot_token']}/sendMessage"
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={
                    "chat_id": settings["chat_id"],
                    "text": message,
                    "parse_mode": "HTML"
                }, timeout=15)
                
                if response.status_code == 200:
                    return True
                else:
                    logger.error(f"Telegram API error: {response.status_code} - {response.text}")
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
                logger.debug(f"Rate limited: Network {network_id}, {self._rate_limit_seconds - elapsed:.0f}s remaining")
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
    
    async def _get_network_structure(self, network_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get the current SEO structure for a network, grouped by tier.
        Returns dict with tier labels as keys and list of entries as values.
        """
        entries = await self.db.seo_structure_entries.find(
            {"network_id": network_id},
            {"_id": 0}
        ).to_list(1000)
        
        if not entries:
            return {}
        
        # Build domain lookup
        domain_ids = list(set(e.get("asset_domain_id") for e in entries if e.get("asset_domain_id")))
        domains = await self.db.asset_domains.find(
            {"id": {"$in": domain_ids}},
            {"_id": 0, "id": 1, "domain_name": 1}
        ).to_list(1000)
        domain_lookup = {d["id"]: d["domain_name"] for d in domains}
        
        # Build entry lookup for target resolution
        entry_lookup = {e["id"]: e for e in entries}
        
        # Calculate tiers using BFS
        # Find main node(s)
        main_entries = [e for e in entries if e.get("domain_role") == "main"]
        
        # Calculate tier for each entry
        tiers = {}
        if main_entries:
            # BFS from main nodes
            queue = [(e["id"], 0) for e in main_entries]
            visited = set()
            
            while queue:
                entry_id, tier = queue.pop(0)
                if entry_id in visited:
                    continue
                visited.add(entry_id)
                tiers[entry_id] = tier
                
                # Find entries pointing to this one
                for e in entries:
                    if e.get("target_entry_id") == entry_id and e["id"] not in visited:
                        queue.append((e["id"], tier + 1))
        
        # Assign orphans to tier -1
        for e in entries:
            if e["id"] not in tiers:
                tiers[e["id"]] = -1
        
        # Group by tier
        tier_groups = defaultdict(list)
        for entry in entries:
            tier = tiers.get(entry["id"], -1)
            domain_name = domain_lookup.get(entry.get("asset_domain_id"), "unknown")
            path = entry.get("optimized_path", "")
            node_label = f"{domain_name}{path}" if path and path != "/" else domain_name
            
            # Get target label
            target_label = None
            if entry.get("target_entry_id"):
                target_entry = entry_lookup.get(entry["target_entry_id"])
                if target_entry:
                    target_domain = domain_lookup.get(target_entry.get("asset_domain_id"), "unknown")
                    target_path = target_entry.get("optimized_path", "")
                    target_label = f"{target_domain}{target_path}" if target_path and target_path != "/" else target_domain
            
            tier_groups[tier].append({
                "node_label": node_label,
                "role": entry.get("domain_role"),
                "target_label": target_label
            })
        
        # Convert to labeled groups
        result = {}
        tier_labels = {
            0: "LP / Money Site",
            1: "Tier 1",
            2: "Tier 2",
            3: "Tier 3",
            4: "Tier 4",
            5: "Tier 5+",
            -1: "Orphan (Tidak Terhubung)"
        }
        
        for tier, entries_list in sorted(tier_groups.items()):
            label = tier_labels.get(tier, f"Tier {tier}")
            # Sort: main first, then alphabetically
            entries_list.sort(key=lambda x: (0 if x["role"] == "main" else 1, x["node_label"]))
            result[label] = entries_list
        
        return result
    
    def _format_structure_snapshot(self, structure: Dict[str, List[Dict[str, Any]]]) -> str:
        """Format the structure snapshot for Telegram message"""
        if not structure:
            return "Tidak ada node dalam network ini."
        
        lines = []
        for tier_label, entries in structure.items():
            lines.append(f"<b>{tier_label}:</b>")
            for entry in entries:
                node = entry["node_label"]
                target = entry.get("target_label")
                if target:
                    lines.append(f"  • {node} → {target}")
                else:
                    lines.append(f"  • {node}")
            lines.append("")  # Empty line between tiers
        
        return "\n".join(lines).strip()
    
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
        skip_rate_limit: bool = False
    ) -> bool:
        """
        Send SEO change notification to Telegram.
        
        Returns True if sent, False if rate limited or failed.
        """
        # Check rate limit
        if not skip_rate_limit and not self._check_rate_limit(network_id):
            return False
        
        try:
            # Get network info
            network = await self.db.seo_networks.find_one({"id": network_id}, {"_id": 0, "name": 1})
            network_name = network.get("name", "Unknown Network") if network else "Unknown Network"
            
            # Get brand info
            brand = await self.db.brands.find_one({"id": brand_id}, {"_id": 0, "name": 1})
            brand_name = brand.get("name", "Unknown Brand") if brand else "Unknown Brand"
            
            # Get user display name
            user_display_name = await self._get_user_display_name(actor_user_id, actor_email)
            
            # Get current structure
            structure = await self._get_network_structure(network_id)
            structure_text = self._format_structure_snapshot(structure)
            
            # Format action label
            action_label = ACTION_LABELS.get(action_type, action_type)
            
            # Format timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            
            # Build change details
            change_details = self._format_change_details(action_type, affected_node, before_snapshot, after_snapshot)
            
            # Build message
            message = f"""👤 <b>PEMBARUAN OPTIMASI SEO</b>

{user_display_name} telah melakukan perubahan optimasi bagan SEO pada network '<b>{network_name}</b>' untuk brand '<b>{brand_name}</b>', dengan detail sebagai berikut:

📌 <b>Ringkasan Aksi</b>
• Aksi            : {action_label}
• Dilakukan Oleh  : {user_display_name} ({actor_email})
• Waktu           : {timestamp}

📝 <b>Alasan Perubahan:</b>
"{change_note}"

{change_details}

🧭 <b>STRUKTUR SEO TERKINI:</b>
{structure_text}"""

            # Send message
            success = await self._send_telegram_message(message)
            
            if success:
                # Update rate limit tracker
                self._update_rate_limit(network_id)
                
                # Update change log with notification info
                if change_log_id:
                    await self.db.seo_change_logs.update_one(
                        {"id": change_log_id},
                        {"$set": {
                            "notified_at": datetime.now(timezone.utc).isoformat(),
                            "notification_channel": "seo_telegram"
                        }}
                    )
                
                logger.info(f"SEO notification sent for network {network_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send SEO change notification: {e}")
            return False
    
    def _format_change_details(
        self,
        action_type: str,
        affected_node: str,
        before: Optional[Dict[str, Any]],
        after: Optional[Dict[str, Any]]
    ) -> str:
        """Format the change details section"""
        lines = ["🔄 <b>Perubahan yang Dilakukan:</b>"]
        lines.append(f"• Node             : {affected_node}")
        
        if action_type == "create_node":
            # New node created
            if after:
                role = ROLE_LABELS.get(after.get("domain_role"), after.get("domain_role", "-"))
                status = STATUS_LABELS.get(after.get("domain_status"), after.get("domain_status", "-"))
                index = INDEX_LABELS.get(after.get("index_status"), after.get("index_status", "-"))
                lines.append(f"• Role             : {role}")
                lines.append(f"• Status           : {status}")
                lines.append(f"• Index            : {index}")
        
        elif action_type == "delete_node":
            # Node deleted
            if before:
                role = ROLE_LABELS.get(before.get("domain_role"), before.get("domain_role", "-"))
                lines.append(f"• Role (sebelum)   : {role}")
            lines.append(f"• Status           : <b>DIHAPUS</b>")
        
        elif action_type == "relink_node":
            # Target changed
            before_target = before.get("target_node_label") if before else None
            after_target = after.get("target_node_label") if after else None
            if not before_target and before and before.get("target_entry_id"):
                before_target = before.get("target_entry_id")[:8] + "..."
            if not after_target and after and after.get("target_entry_id"):
                after_target = after.get("target_entry_id")[:8] + "..."
            
            role = ROLE_LABELS.get(
                (after or before or {}).get("domain_role"),
                (after or before or {}).get("domain_role", "-")
            )
            status = STATUS_LABELS.get(
                (after or before or {}).get("domain_status"),
                (after or before or {}).get("domain_status", "-")
            )
            
            lines.append(f"• Role             : {role}")
            lines.append(f"• Status           : {status}")
            lines.append(f"• Target Sebelumnya: {before_target or '-'}")
            lines.append(f"• Target Baru      : {after_target or '-'}")
        
        elif action_type == "change_role":
            # Role changed
            before_role = ROLE_LABELS.get(before.get("domain_role"), before.get("domain_role", "-")) if before else "-"
            after_role = ROLE_LABELS.get(after.get("domain_role"), after.get("domain_role", "-")) if after else "-"
            after_status = STATUS_LABELS.get(after.get("domain_status"), after.get("domain_status", "-")) if after else "-"
            
            lines.append(f"• Role Sebelumnya  : {before_role}")
            lines.append(f"• Role Baru        : {after_role}")
            lines.append(f"• Status           : {after_status}")
        
        elif action_type == "change_path":
            # Path changed
            before_path = before.get("optimized_path", "/") if before else "/"
            after_path = after.get("optimized_path", "/") if after else "/"
            lines.append(f"• Path Sebelumnya  : {before_path or '/'}")
            lines.append(f"• Path Baru        : {after_path or '/'}")
        
        else:
            # Generic update
            if after:
                role = ROLE_LABELS.get(after.get("domain_role"), after.get("domain_role", "-"))
                status = STATUS_LABELS.get(after.get("domain_status"), after.get("domain_status", "-"))
                index = INDEX_LABELS.get(after.get("index_status"), after.get("index_status", "-"))
                lines.append(f"• Role             : {role}")
                lines.append(f"• Status           : {status}")
                lines.append(f"• Index            : {index}")
        
        return "\n".join(lines)
    
    async def send_network_creation_notification(
        self,
        network_id: str,
        network_name: str,
        brand_id: str,
        actor_user_id: str,
        actor_email: str,
        main_node_label: Optional[str] = None,
        change_log_id: Optional[str] = None
    ) -> bool:
        """
        Send notification for new SEO network creation.
        """
        try:
            # Get brand info
            brand = await self.db.brands.find_one({"id": brand_id}, {"_id": 0, "name": 1})
            brand_name = brand.get("name", "Unknown Brand") if brand else "Unknown Brand"
            
            # Get user display name
            user_display_name = await self._get_user_display_name(actor_user_id, actor_email)
            
            # Format timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            
            # Get initial structure (may be empty or have 1 main node)
            structure = await self._get_network_structure(network_id)
            structure_text = self._format_structure_snapshot(structure) if structure else "Belum ada node dalam network ini."
            
            # Build message
            message = f"""👤 <b>SEO NETWORK BARU DIBUAT</b>

{user_display_name} telah membuat SEO Network baru '<b>{network_name}</b>' untuk brand '<b>{brand_name}</b>'.

📌 <b>Detail Network Baru</b>
• Nama Network     : {network_name}
• Brand            : {brand_name}
• Dibuat Oleh      : {user_display_name} ({actor_email})
• Waktu            : {timestamp}
{f'• Target Utama     : {main_node_label}' if main_node_label else ''}

🧭 <b>STRUKTUR SEO AWAL:</b>
{structure_text}"""

            # Send message
            success = await self._send_telegram_message(message)
            
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
        Clearly labeled as TEST.
        """
        user_display_name = actor_email.split("@")[0].title()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        
        message = f"""🔔 <b>PESAN TEST - TIDAK ADA PERUBAHAN SEO</b>

Ini adalah pesan test dari sistem notifikasi SEO.

📌 <b>Detail Test</b>
• Dikirim Oleh     : {user_display_name} ({actor_email})
• Waktu            : {timestamp}
• Channel          : SEO Change Notifications

✅ Jika Anda melihat pesan ini, konfigurasi Telegram untuk notifikasi SEO sudah benar!

<i>TEST MESSAGE - NO SEO CHANGE APPLIED</i>"""

        return await self._send_telegram_message(message)
