"""
SEO Optimization Telegram Notification Service
===============================================

Handles Telegram notifications for SEO Optimization activities.
Messages are sent in Bahasa Indonesia to match team requirements.

NOTIFICATION TRIGGERS:
- Optimization is CREATED
- Optimization status changes to COMPLETED or REVERTED
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
from services.timezone_helper import format_to_local_time, get_system_timezone

logger = logging.getLogger(__name__)


# Activity type labels in Bahasa Indonesia
ACTIVITY_TYPE_LABELS = {
    "backlink": "Backlink Campaign",
    "onpage": "On-Page Optimization",
    "content": "Content Update",
    "technical": "Technical SEO",
    "schema": "Schema Markup",
    "internal-link": "Internal Linking",
    "experiment": "SEO Experiment",
    "other": "Lainnya",
}

# Status labels in Bahasa Indonesia
STATUS_LABELS = {
    "planned": "Direncanakan",
    "in_progress": "Sedang Berjalan",
    "completed": "Selesai",
    "reverted": "Dibatalkan",
}

# Impact labels in Bahasa Indonesia
IMPACT_LABELS = {
    "ranking": "Ranking",
    "authority": "Authority",
    "crawl": "Crawl",
    "conversion": "Conversion",
}

# Scope labels
SCOPE_LABELS = {
    "money_site": "Money Site",
    "domain": "Domain",
    "path": "Path",
    "whole_network": "Seluruh Network",
}


class SeoOptimizationTelegramService:
    """Service for sending SEO Optimization notifications to Telegram"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def _get_telegram_config(self) -> Optional[Dict[str, Any]]:
        """
        Get Telegram configuration for SEO Optimizations.
        Uses the same channel as SEO structure notifications.
        Falls back to main monitoring channel if not configured.
        """
        # Try SEO-specific Telegram config first
        seo_config = await self.db.settings.find_one(
            {"key": "telegram_seo"}, {"_id": 0}
        )
        if seo_config and seo_config.get("bot_token") and seo_config.get("chat_id"):
            if seo_config.get("enabled", True):
                return seo_config
            else:
                logger.info("SEO Telegram notifications are disabled")
                return None

        # Fallback to main monitoring channel
        logger.warning(
            "SEO Telegram not configured, falling back to main monitoring channel"
        )
        main_config = await self.db.settings.find_one({"key": "telegram"}, {"_id": 0})
        if main_config and main_config.get("bot_token") and main_config.get("chat_id"):
            return main_config

        logger.warning("No Telegram configuration found for SEO Optimizations")
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
    
    async def _get_network_manager_usernames(self, network_id: str) -> List[str]:
        """
        Get raw Telegram usernames for all managers of a specific network.
        Returns list of usernames WITHOUT @ prefix (for template engine).
        """
        network = await self.db.seo_networks.find_one(
            {"id": network_id}, {"_id": 0, "manager_ids": 1}
        )
        if not network or not network.get("manager_ids"):
            return []

        # Get users with their telegram usernames
        managers = await self.db.users.find(
            {"id": {"$in": network["manager_ids"]}},
            {"_id": 0, "telegram_username": 1}
        ).to_list(100)

        usernames = []
        for manager in managers:
            if manager.get("telegram_username"):
                username = manager["telegram_username"].replace("@", "")
                usernames.append(username)
        
        return usernames

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
        config = await self._get_telegram_config()
        if not config:
            return False

        bot_token = config.get("bot_token")
        chat_id = config.get("chat_id")

        if not bot_token or not chat_id:
            logger.warning("Telegram bot_token or chat_id not configured")
            return False

        # Determine message_thread_id for forum topic routing
        message_thread_id = None
        if config.get("enable_topic_routing") and topic_type:
            topic_id_field = f"{topic_type}_topic_id"
            message_thread_id = config.get(topic_id_field)
            if not message_thread_id:
                logger.warning(
                    f"Topic routing enabled but {topic_id_field} not configured, sending to General"
                )

        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }

            # Add message_thread_id for forum topic
            if message_thread_id:
                payload["message_thread_id"] = int(message_thread_id)

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=30.0)

                if response.status_code == 200:
                    topic_info = f" (topic: {topic_type})" if message_thread_id else ""
                    logger.info(
                        f"SEO Telegram notification sent successfully{topic_info}"
                    )
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
                        retry_response = await client.post(url, json=payload, timeout=30.0)
                        if retry_response.status_code == 200:
                            logger.info("SEO Telegram notification sent (fallback to main chat after invalid topic_id)")
                            return True
                        else:
                            logger.error(f"Telegram API error (retry): {retry_response.status_code} - {retry_response.text}")
                            return False
                    
                    logger.error(
                        f"Telegram API error: {response.status_code} - {response.text}"
                    )
                    return False
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    async def send_optimization_created_notification(
        self,
        optimization: Dict[str, Any],
        network: Dict[str, Any],
        brand: Dict[str, Any],
    ) -> bool:
        """
        Send notification when a new optimization is created.
        Uses template system with fallback to hardcoded message.
        """
        from services.notification_template_engine import render_notification
        
        try:
            # Get timezone settings
            tz_str, tz_label = await get_system_timezone(self.db)
            local_time = format_to_local_time(
                optimization.get("created_at", datetime.now(timezone.utc).isoformat()),
                tz_str,
                tz_label,
            )

            # Get creator info
            created_by = optimization.get("created_by", {})
            creator_name = created_by.get("display_name", "Unknown")
            creator_email = created_by.get("email", "")

            # Format activity type
            activity_type = optimization.get("activity_type", "other")
            activity_label = ACTIVITY_TYPE_LABELS.get(
                activity_type, activity_type.replace("_", " ").title()
            )

            # Format status
            status = optimization.get("status", "completed")
            status_label = STATUS_LABELS.get(status, status.replace("_", " ").title())

            # Format affected targets
            targets = optimization.get("affected_targets", [])
            targets_text = (
                "\n".join([f"  • {t}" for t in targets])
                if targets
                else "  (Tidak ada target spesifik)"
            )

            # Format keywords
            keywords = optimization.get("keywords", [])
            keywords_text = ", ".join(keywords) if keywords else "(Tidak ada)"

            # Format report URLs with dates
            report_urls = optimization.get("report_urls", [])
            reports_text_lines = []
            for r in report_urls:
                if isinstance(r, dict):
                    url = r.get("url", "")
                    start_date = r.get("start_date", "")
                    if start_date:
                        reports_text_lines.append(
                            f"  • {url}\n    📅 Tanggal: {start_date}"
                        )
                    else:
                        reports_text_lines.append(f"  • {url}")
                else:
                    reports_text_lines.append(f"  • {r}")
            reports_text = (
                "\n".join(reports_text_lines) if reports_text_lines else "  (Tidak ada)"
            )

            # Format expected impact
            impacts = optimization.get("expected_impact", [])
            impact_labels = [IMPACT_LABELS.get(i, i) for i in impacts]
            impact_text = (
                ", ".join(impact_labels) if impact_labels else "(Tidak ditentukan)"
            )

            # Get SEO Leader tags
            seo_leaders = await self._get_seo_leader_usernames()
            seo_leader_tag = await self._get_seo_leader_tag()
            
            # Try to use template system
            message = await render_notification(
                db=self.db,
                channel="telegram",
                event_type="seo_optimization",
                context_data={
                    "user": {"display_name": creator_name, "email": creator_email},
                    "network": {"name": network.get("name", "Unknown"), "id": network.get("id", "")},
                    "brand": {"name": brand.get("name", "Unknown"), "id": brand.get("id", "")},
                    "optimization": {
                        "title": optimization.get("title", "(Tanpa judul)"),
                        "description": optimization.get("description", "(Tidak ada deskripsi)"),
                        "activity_type": activity_label,
                        "status": status_label,
                        "affected_targets": targets,
                        "keywords": keywords,
                        "report_urls": [r.get("url", r) if isinstance(r, dict) else r for r in report_urls],
                        "expected_impact": impacts,
                    },
                    "telegram_leaders": seo_leaders,
                }
            )
            
            # Fallback to hardcoded if template disabled or failed
            if not message:
                leader_section = ""
                if seo_leader_tag:
                    leader_section = f"\n\n👁 <b>CC:</b> {seo_leader_tag}"

                message = f"""📘 <b>SEO OPTIMIZATION ACTIVITY</b>

<b>{creator_name}</b> telah menambahkan aktivitas optimasi SEO
pada network '<b>{network.get('name', 'Unknown')}</b>' untuk brand '<b>{brand.get('name', 'Unknown')}</b>'.

━━━━━━━━━━━━━━━━━━━━━━
📌 <b>RINGKASAN</b>
━━━━━━━━━━━━━━━━━━━━━━
• <b>Jenis:</b> {activity_label}
• <b>Status:</b> {status_label}
• <b>Dilakukan:</b> {creator_name} ({creator_email})
• <b>Waktu:</b> {local_time}

📝 <b>Judul:</b>
{optimization.get('title', '(Tanpa judul)')}

📄 <b>Deskripsi:</b>
"{optimization.get('description', '(Tidak ada deskripsi)')}"

🎯 <b>Target:</b>
{targets_text}

🔑 <b>Keyword:</b>
{keywords_text}

📊 <b>Expected Impact:</b>
{impact_text}

📎 <b>Report:</b>
{reports_text}

━━━━━━━━━━━━━━━━━━━━━━
<i>⚠️ Catatan: Tidak ada perubahan struktur SEO</i>{leader_section}"""

            success = await self._send_telegram_message(
                message, topic_type="seo_optimization"
            )

            if success:
                # Update optimization with notification timestamp
                await self.db.seo_optimizations.update_one(
                    {"id": optimization["id"]},
                    {
                        "$set": {
                            "telegram_notified_at": datetime.now(
                                timezone.utc
                            ).isoformat()
                        }
                    },
                )

            return success

        except Exception as e:
            logger.error(f"Failed to send optimization created notification: {e}")
            return False

    async def send_status_change_notification(
        self,
        optimization: Dict[str, Any],
        network: Dict[str, Any],
        brand: Dict[str, Any],
        old_status: str,
        new_status: str,
        changed_by: Dict[str, Any],
    ) -> bool:
        """
        Send notification when optimization status changes to COMPLETED or REVERTED.
        """
        # Only notify for completed or reverted
        if new_status not in ["completed", "reverted"]:
            return True  # Not an error, just not notifying

        try:
            # Get timezone settings
            tz_str, tz_label = await get_system_timezone(self.db)
            local_time = format_to_local_time(
                datetime.now(timezone.utc).isoformat(), tz_str, tz_label
            )

            # Get user info
            changer_name = changed_by.get("name", changed_by.get("email", "Unknown"))
            changer_email = changed_by.get("email", "")

            # Format status
            old_status_label = STATUS_LABELS.get(old_status, old_status)
            new_status_label = STATUS_LABELS.get(new_status, new_status)

            # Status emoji
            status_emoji = "✅" if new_status == "completed" else "🔄"

            # Get SEO Leader tag for global oversight
            seo_leader_tag = await self._get_seo_leader_tag()
            leader_section = ""
            if seo_leader_tag:
                leader_section = f"\n\n👁 <b>CC:</b> {seo_leader_tag}"

            message = f"""{status_emoji} <b>SEO OPTIMIZATION STATUS UPDATE</b>

<b>{changer_name}</b> telah mengubah status aktivitas optimasi SEO
pada network '<b>{network.get('name', 'Unknown')}</b>' untuk brand '<b>{brand.get('name', 'Unknown')}</b>'.

━━━━━━━━━━━━━━━━━━━━━━
📝 <b>Aktivitas:</b>
{optimization.get('title', '(Tanpa judul)')}

🔄 <b>Perubahan Status:</b>
{old_status_label} → <b>{new_status_label}</b>

👤 <b>Diubah oleh:</b> {changer_name} ({changer_email})
🕐 <b>Waktu:</b> {local_time}

━━━━━━━━━━━━━━━━━━━━━━
<i>⚠️ Catatan: Tidak ada perubahan struktur SEO</i>{leader_section}"""

            success = await self._send_telegram_message(
                message, topic_type="seo_optimization"
            )

            if success:
                # Update optimization with notification timestamp
                await self.db.seo_optimizations.update_one(
                    {"id": optimization["id"]},
                    {
                        "$set": {
                            "telegram_notified_at": datetime.now(
                                timezone.utc
                            ).isoformat()
                        }
                    },
                )

            return success

        except Exception as e:
            logger.error(f"Failed to send status change notification: {e}")
            return False

    async def send_complaint_notification(
        self,
        complaint: Dict[str, Any],
        optimization: Dict[str, Any],
        network: Dict[str, Any],
        brand: Dict[str, Any],
        responsible_users: List[Dict[str, Any]],  # Deprecated - now using network managers
    ) -> bool:
        """
        Send notification when Super Admin creates a complaint on an optimization.
        Uses template system with fallback.
        
        IMPORTANT: Per new policy, complaints ONLY tag Network Manager(s) -
        NOT global users, NOT viewers, NOT SEO leader.
        """
        from services.notification_template_engine import render_notification
        
        try:
            # Get timezone settings
            tz_str, tz_label = await get_system_timezone(self.db)
            local_time = format_to_local_time(
                complaint.get("created_at", datetime.now(timezone.utc).isoformat()),
                tz_str,
                tz_label,
            )

            # Get creator info
            created_by = complaint.get("created_by", {})
            creator_name = created_by.get("display_name", "Unknown")
            creator_email = created_by.get("email", "")

            # POLICY: Complaints ONLY tag Network Manager(s) of the specific project
            network_id = network.get("id")
            manager_tags = await self._get_network_manager_tags(network_id)
            manager_usernames = await self._get_network_manager_usernames(network_id)
            
            if manager_tags:
                tagged_users_text = "\n".join([f"  • {tag}" for tag in manager_tags])
            else:
                tagged_users_text = "  (Tidak ada Network Manager yang ditag)"

            # Format activity type
            activity_type = optimization.get("activity_type", "other")
            activity_label = ACTIVITY_TYPE_LABELS.get(
                activity_type, activity_type.replace("_", " ").title()
            )

            # Format status
            status = optimization.get("status", "unknown")
            status_label = STATUS_LABELS.get(status, status.replace("_", " ").title())

            # Format scope
            scope = optimization.get("affected_scope", "domain")
            scope_label = SCOPE_LABELS.get(scope, scope.replace("_", " ").title())

            # Format priority
            priority = complaint.get("priority", "medium")
            priority_emoji = {"low": "🔵", "medium": "🟡", "high": "🔴"}.get(
                priority, "🟡"
            )
            priority_label = {
                "low": "Rendah",
                "medium": "Sedang",
                "high": "Tinggi",
            }.get(priority, "Sedang")

            # Format report URLs
            report_urls = complaint.get("report_urls", [])
            reports_text = (
                "\n".join([f"  • {url}" for url in report_urls])
                if report_urls
                else "  (Tidak ada)"
            )
            
            # Try to use template system
            message = await render_notification(
                db=self.db,
                channel="telegram",
                event_type="seo_complaint",
                context_data={
                    "user": {"display_name": creator_name, "email": creator_email},
                    "network": {"name": network.get("name", "Unknown"), "id": network_id},
                    "brand": {"name": brand.get("name", "Unknown"), "id": brand.get("id", "")},
                    "optimization": {
                        "title": optimization.get("title", "(Tanpa judul)"),
                        "activity_type": activity_label,
                        "status": status_label,
                    },
                    "complaint": {
                        "reason": complaint.get("reason", "(Tidak ada alasan)"),
                        "priority": priority_label,
                        "category": complaint.get("category", "other"),
                        "report_urls": report_urls,
                    },
                    "telegram_project_managers": manager_usernames,
                }
            )
            
            # Fallback to hardcoded if template disabled or failed
            if not message:
                message = f"""🚨 <b>SEO OPTIMIZATION COMPLAINT</b>

<b>{creator_name}</b> telah mengajukan komplain
pada SEO Network '<b>{network.get('name', 'Unknown')}</b>' untuk brand '<b>{brand.get('name', 'Unknown')}</b>'.

━━━━━━━━━━━━━━━━━━━━━━
👥 <b>Tagged Users:</b>
{tagged_users_text}

📌 <b>Optimization:</b>
  • Judul: {optimization.get('title', '(Tanpa judul)')}
  • Jenis: {activity_label}
  • Status: {status_label}
  • Scope: {scope_label}

{priority_emoji} <b>Prioritas:</b> {priority_label}

📝 <b>Alasan Komplain:</b>
"{complaint.get('reason', '(Tidak ada alasan)')}"

📎 <b>Related Reports:</b>
{reports_text}

🕐 <b>Waktu:</b> {local_time}

━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>Action Required:</b>
<i>Please review and respond to this complaint.</i>"""

            success = await self._send_telegram_message(
                message, topic_type="seo_complaint"
            )

            if success:
                # Update complaint with notification timestamp
                await self.db.optimization_complaints.update_one(
                    {"id": complaint["id"]},
                    {
                        "$set": {
                            "telegram_notified_at": datetime.now(
                                timezone.utc
                            ).isoformat()
                        }
                    },
                )

            return success

        except Exception as e:
            logger.error(f"Failed to send complaint notification: {e}")
            return False

    async def send_in_progress_reminder(
        self,
        optimization: Dict[str, Any],
        network: Dict[str, Any],
        brand: Dict[str, Any],
        users: List[Dict[str, Any]],
        days_in_progress: int,
    ) -> bool:
        """
        Send reminder notification for optimizations that have been in_progress for too long.
        Tags all assigned users + creator via Telegram.
        """
        try:
            # Get timezone settings
            tz_str, tz_label = await get_system_timezone(self.db)
            local_time = format_to_local_time(
                datetime.now(timezone.utc).isoformat(), tz_str, tz_label
            )

            # Build user tags
            tags = []
            for user in users:
                if user.get("telegram_username"):
                    tags.append(f"@{user['telegram_username']}")
                else:
                    tags.append(
                        f"{user.get('name', user.get('email', 'Unknown'))} (no Telegram)"
                    )

            tags_text = (
                "\n".join([f"  • {tag}" for tag in tags])
                if tags
                else "  (Tidak ada pengguna yang ditag)"
            )

            message = f"""⏰ <b>SEO OPTIMIZATION REMINDER</b>

<b>Aktivitas optimasi masih berstatus IN PROGRESS</b>
selama <b>{days_in_progress} hari</b>.

━━━━━━━━━━━━━━━━━━━━━━
📌 <b>DETAIL</b>
━━━━━━━━━━━━━━━━━━━━━━
• <b>Network:</b> {network.get('name', 'Unknown')}
• <b>Brand:</b> {brand.get('name', 'Unknown')}
• <b>Judul:</b> {optimization.get('title', '(Tanpa judul)')}
• <b>Status:</b> In Progress (Sedang Berjalan)

👥 <b>Pengguna yang Bertanggung Jawab:</b>
{tags_text}

🕐 <b>Waktu Reminder:</b> {local_time}

━━━━━━━━━━━━━━━━━━━━━━
<i>⚠️ Mohon segera update status optimasi ini.</i>
<i>Reminder akan terus dikirim sampai status diubah.</i>"""

            success = await self._send_telegram_message(
                message, topic_type="seo_reminder"
            )
            return success

        except Exception as e:
            logger.error(f"Failed to send in-progress reminder notification: {e}")
            return False

    async def send_message(self, message: str, topic_type: str = None) -> bool:
        """
        Public method to send a custom Telegram message.
        Used by other parts of the system to send notifications.

        topic_type: Optional forum topic routing (seo_change, seo_optimization, seo_complaint, seo_reminder)
        """
        return await self._send_telegram_message(message, topic_type=topic_type)

    async def send_project_complaint_notification(
        self,
        complaint: Dict[str, Any],
        network_name: str,
        responsible_users: List[Dict[str, Any]],
    ) -> bool:
        """
        Send notification when Super Admin creates a project-level complaint.
        Tags network managers (project owners) via @telegram_username.
        
        NOTE: For complaints, we tag Network Managers ONLY - not global SEO leaders.
        SEO leaders are only tagged on SEO change/optimization notifications.
        """
        try:
            # Get timezone settings
            tz_str, tz_label = await get_system_timezone(self.db)
            local_time = format_to_local_time(
                complaint.get("created_at", datetime.now(timezone.utc).isoformat()),
                tz_str,
                tz_label,
            )

            # Get creator info
            created_by = complaint.get("created_by", {})
            creator_name = created_by.get("name", created_by.get("email", "Unknown"))

            # Get network managers from network's manager_ids
            network_id = complaint.get("network_id")
            manager_tags = []
            if network_id:
                manager_tags = await self._get_network_manager_tags(network_id)
            
            # Combine with responsible_users passed in (for backward compatibility)
            if responsible_users:
                for user in responsible_users:
                    if user.get("telegram_username"):
                        tag = f"@{user['telegram_username']}"
                        if tag not in manager_tags:
                            manager_tags.append(tag)
            
            # Format tagged users
            if manager_tags:
                tagged_users_text = "\n".join([f"  • {tag}" for tag in manager_tags])
            else:
                tagged_users_text = "  (Tidak ada Network Manager yang ditag)"

            # Format priority
            priority = complaint.get("priority", "medium")
            priority_emoji = {"low": "🔵", "medium": "🟡", "high": "🔴"}.get(
                priority, "🟡"
            )
            priority_label = {
                "low": "Rendah",
                "medium": "Sedang",
                "high": "Tinggi",
            }.get(priority, "Sedang")

            # Format category
            category = complaint.get("category") or "Umum"
            category_label = {
                "communication": "Komunikasi",
                "deadline": "Deadline",
                "quality": "Kualitas",
                "process": "Proses",
            }.get(category, category.title())

            # Format report URLs
            report_urls = complaint.get("report_urls", [])
            reports_text = (
                "\n".join([f"  • {url}" for url in report_urls])
                if report_urls
                else "  (Tidak ada)"
            )

            message = f"""🚨 <b>PROJECT-LEVEL COMPLAINT</b>

<b>{creator_name}</b> telah mengajukan komplain
pada SEO Network '<b>{network_name}</b>'.

<i>Komplain ini tidak terkait dengan optimasi tertentu,
tetapi menyangkut pengelolaan proyek secara keseluruhan.</i>

━━━━━━━━━━━━━━━━━━━━━━
👥 <b>Network Manager (Tagged):</b>
{tagged_users_text}

📁 <b>Kategori:</b> {category_label}
{priority_emoji} <b>Prioritas:</b> {priority_label}

━━━━━━━━━━━━━━━━━━━━━━
📝 <b>Alasan Komplain:</b>
"{complaint.get('reason', '(Tidak ada alasan)')}"

📎 <b>Related Reports:</b>
{reports_text}

🕐 <b>Waktu:</b> {local_time}

━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>Action Required:</b>
<i>Please review and respond to this complaint.</i>"""

            success = await self._send_telegram_message(
                message, topic_type="seo_complaint"
            )

            if success:
                # Update complaint with notification timestamp
                await self.db.project_complaints.update_one(
                    {"id": complaint["id"]},
                    {
                        "$set": {
                            "telegram_notified_at": datetime.now(
                                timezone.utc
                            ).isoformat()
                        }
                    },
                )

            return success

        except Exception as e:
            logger.error(f"Failed to send project complaint notification: {e}")
            return False


# Global instance for use across the application
seo_optimization_telegram_service: Optional[SeoOptimizationTelegramService] = None


def init_seo_optimization_telegram_service(db: AsyncIOMotorDatabase):
    """Initialize the global SEO optimization Telegram service instance"""
    global seo_optimization_telegram_service
    seo_optimization_telegram_service = SeoOptimizationTelegramService(db)
    return seo_optimization_telegram_service
