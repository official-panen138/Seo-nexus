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
    "other": "Lainnya"
}

# Status labels in Bahasa Indonesia
STATUS_LABELS = {
    "planned": "Direncanakan",
    "in_progress": "Sedang Berjalan",
    "completed": "Selesai",
    "reverted": "Dibatalkan"
}

# Impact labels in Bahasa Indonesia
IMPACT_LABELS = {
    "ranking": "Ranking",
    "authority": "Authority",
    "crawl": "Crawl",
    "conversion": "Conversion"
}

# Scope labels
SCOPE_LABELS = {
    "money_site": "Money Site",
    "domain": "Domain",
    "path": "Path",
    "whole_network": "Seluruh Network"
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
        seo_config = await self.db.settings.find_one({"key": "telegram_seo"}, {"_id": 0})
        if seo_config and seo_config.get("bot_token") and seo_config.get("chat_id"):
            if seo_config.get("enabled", True):
                return seo_config
            else:
                logger.info("SEO Telegram notifications are disabled")
                return None
        
        # Fallback to main monitoring channel
        logger.warning("SEO Telegram not configured, falling back to main monitoring channel")
        main_config = await self.db.settings.find_one({"key": "telegram"}, {"_id": 0})
        if main_config and main_config.get("bot_token") and main_config.get("chat_id"):
            return main_config
        
        logger.warning("No Telegram configuration found for SEO Optimizations")
        return None
    
    async def _send_telegram_message(self, message: str) -> bool:
        """Send message to Telegram"""
        config = await self._get_telegram_config()
        if not config:
            return False
        
        bot_token = config.get("bot_token")
        chat_id = config.get("chat_id")
        
        if not bot_token or not chat_id:
            logger.warning("Telegram bot_token or chat_id not configured")
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    logger.info("SEO Optimization Telegram notification sent successfully")
                    return True
                else:
                    logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False
    
    async def send_optimization_created_notification(
        self,
        optimization: Dict[str, Any],
        network: Dict[str, Any],
        brand: Dict[str, Any]
    ) -> bool:
        """
        Send notification when a new optimization is created.
        """
        try:
            # Get timezone settings
            tz_str, tz_label = await get_system_timezone(self.db)
            local_time = format_to_local_time(
                optimization.get("created_at", datetime.now(timezone.utc).isoformat()),
                tz_str, tz_label
            )
            
            # Get creator info
            created_by = optimization.get("created_by", {})
            creator_name = created_by.get("display_name", "Unknown")
            creator_email = created_by.get("email", "")
            
            # Format activity type
            activity_type = optimization.get("activity_type", "other")
            activity_label = ACTIVITY_TYPE_LABELS.get(activity_type, activity_type.replace("_", " ").title())
            
            # Format status
            status = optimization.get("status", "completed")
            status_label = STATUS_LABELS.get(status, status.replace("_", " ").title())
            
            # Format affected targets
            targets = optimization.get("affected_targets", [])
            targets_text = "\n".join([f"  • {t}" for t in targets]) if targets else "  (Tidak ada target spesifik)"
            
            # Format keywords
            keywords = optimization.get("keywords", [])
            keywords_text = ", ".join(keywords) if keywords else "(Tidak ada)"
            
            # Format report URLs
            report_urls = optimization.get("report_urls", [])
            reports_text = "\n".join([f"  • {url}" for url in report_urls]) if report_urls else "  (Tidak ada)"
            
            # Format expected impact
            impacts = optimization.get("expected_impact", [])
            impact_labels = [IMPACT_LABELS.get(i, i) for i in impacts]
            impact_text = ", ".join(impact_labels) if impact_labels else "(Tidak ditentukan)"
            
            # Build message
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
<i>⚠️ Catatan: Tidak ada perubahan struktur SEO</i>"""
            
            success = await self._send_telegram_message(message)
            
            if success:
                # Update optimization with notification timestamp
                await self.db.seo_optimizations.update_one(
                    {"id": optimization["id"]},
                    {"$set": {"telegram_notified_at": datetime.now(timezone.utc).isoformat()}}
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
        changed_by: Dict[str, Any]
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
                datetime.now(timezone.utc).isoformat(),
                tz_str, tz_label
            )
            
            # Get user info
            changer_name = changed_by.get("name", changed_by.get("email", "Unknown"))
            changer_email = changed_by.get("email", "")
            
            # Format status
            old_status_label = STATUS_LABELS.get(old_status, old_status)
            new_status_label = STATUS_LABELS.get(new_status, new_status)
            
            # Status emoji
            status_emoji = "✅" if new_status == "completed" else "🔄"
            
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
<i>⚠️ Catatan: Tidak ada perubahan struktur SEO</i>"""
            
            success = await self._send_telegram_message(message)
            
            if success:
                # Update optimization with notification timestamp
                await self.db.seo_optimizations.update_one(
                    {"id": optimization["id"]},
                    {"$set": {"telegram_notified_at": datetime.now(timezone.utc).isoformat()}}
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
        responsible_users: List[Dict[str, Any]]
    ) -> bool:
        """
        Send notification when Super Admin creates a complaint on an optimization.
        Tags responsible users via @telegram_username.
        """
        try:
            # Get timezone settings
            tz_str, tz_label = await get_system_timezone(self.db)
            local_time = format_to_local_time(
                complaint.get("created_at", datetime.now(timezone.utc).isoformat()),
                tz_str, tz_label
            )
            
            # Get creator info
            created_by = complaint.get("created_by", {})
            creator_name = created_by.get("display_name", "Unknown")
            
            # Format tagged users
            tagged_users_text = ""
            if responsible_users:
                tags = []
                for user in responsible_users:
                    if user.get("telegram_username"):
                        tags.append(f"@{user['telegram_username']}")
                    else:
                        # Fallback to email if no Telegram username
                        tags.append(f"{user.get('name', user.get('email', 'Unknown'))} (no Telegram)")
                tagged_users_text = "\n".join([f"  • {tag}" for tag in tags])
            else:
                tagged_users_text = "  (Tidak ada pengguna yang ditag)"
            
            # Format activity type
            activity_type = optimization.get("activity_type", "other")
            activity_label = ACTIVITY_TYPE_LABELS.get(activity_type, activity_type.replace("_", " ").title())
            
            # Format status
            status = optimization.get("status", "unknown")
            status_label = STATUS_LABELS.get(status, status.replace("_", " ").title())
            
            # Format scope
            scope = optimization.get("affected_scope", "domain")
            scope_label = SCOPE_LABELS.get(scope, scope.replace("_", " ").title())
            
            # Format priority
            priority = complaint.get("priority", "medium")
            priority_emoji = {"low": "🔵", "medium": "🟡", "high": "🔴"}.get(priority, "🟡")
            priority_label = {"low": "Rendah", "medium": "Sedang", "high": "Tinggi"}.get(priority, "Sedang")
            
            # Format report URLs
            report_urls = complaint.get("report_urls", [])
            reports_text = "\n".join([f"  • {url}" for url in report_urls]) if report_urls else "  (Tidak ada)"
            
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
            
            success = await self._send_telegram_message(message)
            
            if success:
                # Update complaint with notification timestamp
                await self.db.optimization_complaints.update_one(
                    {"id": complaint["id"]},
                    {"$set": {"telegram_notified_at": datetime.now(timezone.utc).isoformat()}}
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send complaint notification: {e}")
            return False
    
    async def send_message(self, message: str) -> bool:
        """
        Public method to send a custom Telegram message.
        Used by other parts of the system to send notifications.
        """
        return await self._send_telegram_message(message)


# Global instance for use across the application
seo_optimization_telegram_service: Optional[SeoOptimizationTelegramService] = None


def init_seo_optimization_telegram_service(db: AsyncIOMotorDatabase):
    """Initialize the global SEO optimization Telegram service instance"""
    global seo_optimization_telegram_service
    seo_optimization_telegram_service = SeoOptimizationTelegramService(db)
    return seo_optimization_telegram_service
