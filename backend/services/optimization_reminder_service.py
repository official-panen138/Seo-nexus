"""
SEO Optimization Reminder Service
==================================

Sends automatic Telegram reminders for "In Progress" optimizations.
Reminders are sent to:
1. The optimization creator
2. All assigned users from network Access Summary

Reminder interval is configurable:
- Global default: 2 days (from settings)
- Per-network override (from network config)

Reminders stop when optimization is completed or closed.
All reminders are logged for accountability.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import uuid

logger = logging.getLogger(__name__)


class OptimizationReminderService:
    """Service for managing optimization reminders"""

    DEFAULT_REMINDER_INTERVAL_DAYS = 2

    def __init__(self, db: AsyncIOMotorDatabase, telegram_service=None):
        self.db = db
        self.telegram_service = telegram_service

    async def get_global_reminder_config(self) -> Dict[str, Any]:
        """Get global reminder configuration from settings"""
        settings = await self.db.settings.find_one(
            {"key": "optimization_reminders"}, {"_id": 0}
        )

        if settings:
            return {
                "enabled": settings.get("enabled", True),
                "interval_days": settings.get(
                    "interval_days", self.DEFAULT_REMINDER_INTERVAL_DAYS
                ),
            }

        return {"enabled": True, "interval_days": self.DEFAULT_REMINDER_INTERVAL_DAYS}

    async def get_network_reminder_config(
        self, network_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get per-network reminder override if configured"""
        network = await self.db.seo_networks.find_one(
            {"id": network_id}, {"_id": 0, "reminder_config": 1}
        )

        if network and network.get("reminder_config"):
            return network["reminder_config"]

        return None

    async def get_effective_reminder_interval(self, network_id: str) -> int:
        """Get effective reminder interval for a network (network override or global default)"""
        # Check network-specific config first
        network_config = await self.get_network_reminder_config(network_id)
        if network_config and "interval_days" in network_config:
            return network_config["interval_days"]

        # Fall back to global config
        global_config = await self.get_global_reminder_config()
        return global_config.get("interval_days", self.DEFAULT_REMINDER_INTERVAL_DAYS)

    async def get_in_progress_optimizations_needing_reminder(
        self,
    ) -> List[Dict[str, Any]]:
        """
        Get all 'in_progress' optimizations that need reminders.

        Criteria:
        - Status is 'in_progress'
        - Last reminder was sent >= reminder_interval days ago (or never sent)
        - Optimization is not completed or closed
        """
        global_config = await self.get_global_reminder_config()

        if not global_config.get("enabled", True):
            logger.info("[REMINDER] Global reminders are disabled")
            return []

        # Find all in_progress optimizations
        optimizations = await self.db.seo_optimizations.find(
            {"status": "in_progress"}, {"_id": 0}
        ).to_list(500)

        need_reminder = []
        now = datetime.now(timezone.utc)

        for opt in optimizations:
            network_id = opt.get("network_id")
            interval_days = await self.get_effective_reminder_interval(network_id)

            # Check if reminder is needed
            last_reminder = opt.get("last_reminder_at")

            if last_reminder:
                last_reminder_dt = datetime.fromisoformat(
                    last_reminder.replace("Z", "+00:00")
                )
                days_since_reminder = (now - last_reminder_dt).days

                if days_since_reminder >= interval_days:
                    need_reminder.append(
                        {
                            **opt,
                            "days_since_reminder": days_since_reminder,
                            "reminder_interval": interval_days,
                        }
                    )
            else:
                # Never sent a reminder - check days since creation
                created_at = opt.get("created_at")
                if created_at:
                    created_dt = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )
                    days_since_creation = (now - created_dt).days

                    if days_since_creation >= interval_days:
                        need_reminder.append(
                            {
                                **opt,
                                "days_since_reminder": days_since_creation,
                                "reminder_interval": interval_days,
                                "first_reminder": True,
                            }
                        )

        logger.info(
            f"[REMINDER] Found {len(need_reminder)} optimizations needing reminder"
        )
        return need_reminder

    async def get_users_to_notify(
        self, optimization: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get all users who should be notified for a reminder.

        Recipients:
        1. Optimization creator
        2. All users assigned to the network (from Access Summary)
        """
        user_ids = set()

        # Add creator
        created_by = optimization.get("created_by", {})
        if created_by.get("user_id"):
            user_ids.add(created_by["user_id"])

        # Add network assigned users (from Access Summary)
        network = await self.db.seo_networks.find_one(
            {"id": optimization.get("network_id")},
            {"_id": 0, "visibility_mode": 1, "allowed_user_ids": 1},
        )

        if (
            network
            and network.get("visibility_mode") == "restricted"
            and network.get("allowed_user_ids")
        ):
            user_ids.update(network["allowed_user_ids"])

        # Fetch user details
        if user_ids:
            users = await self.db.users.find(
                {
                    "id": {"$in": list(user_ids)},
                    "status": {"$nin": ["inactive", "suspended"]},
                },
                {"_id": 0, "id": 1, "email": 1, "name": 1, "telegram_username": 1},
            ).to_list(100)
            return users

        return []

    async def send_reminder(
        self, optimization: Dict[str, Any], users: List[Dict[str, Any]]
    ) -> bool:
        """Send reminder notification via Telegram"""
        if not self.telegram_service:
            logger.warning("[REMINDER] Telegram service not available")
            return False

        try:
            # Get network and brand info
            network = await self.db.seo_networks.find_one(
                {"id": optimization.get("network_id")}, {"_id": 0, "name": 1}
            )
            brand = await self.db.brands.find_one(
                {"id": optimization.get("brand_id")}, {"_id": 0, "name": 1}
            )

            # Build user tags
            tags = []
            for user in users:
                if user.get("telegram_username"):
                    tags.append(f"@{user['telegram_username']}")
                else:
                    tags.append(user.get("name", user.get("email", "Unknown")))

            days_in_progress = optimization.get("days_since_reminder", 0)

            # Send notification
            success = await self.telegram_service.send_in_progress_reminder(
                optimization=optimization,
                network=network or {"name": "Unknown"},
                brand=brand or {"name": "Unknown"},
                users=users,
                days_in_progress=days_in_progress,
            )

            return success

        except Exception as e:
            logger.error(f"[REMINDER] Failed to send reminder: {e}")
            return False

    async def log_reminder(
        self,
        optimization: Dict[str, Any],
        users: List[Dict[str, Any]],
        telegram_sent: bool,
    ) -> str:
        """Log reminder to database for accountability"""
        now = datetime.now(timezone.utc).isoformat()

        log_entry = {
            "id": str(uuid.uuid4()),
            "optimization_id": optimization["id"],
            "network_id": optimization.get("network_id"),
            "brand_id": optimization.get("brand_id"),
            "reminder_type": "in_progress_reminder",
            "sent_at": now,
            "tagged_users": [
                {
                    "user_id": u["id"],
                    "email": u.get("email"),
                    "name": u.get("name"),
                    "telegram_username": u.get("telegram_username"),
                }
                for u in users
            ],
            "telegram_sent": telegram_sent,
            "optimization_status": optimization.get("status"),
            "optimization_title": optimization.get("title"),
            "days_since_creation": optimization.get("days_since_reminder", 0),
        }

        await self.db.optimization_reminders.insert_one(log_entry)

        logger.info(
            f"[REMINDER] Logged reminder {log_entry['id']} for optimization {optimization['id']}"
        )

        return log_entry["id"]

    async def update_optimization_reminder_timestamp(self, optimization_id: str):
        """Update optimization with last reminder timestamp"""
        await self.db.seo_optimizations.update_one(
            {"id": optimization_id},
            {"$set": {"last_reminder_at": datetime.now(timezone.utc).isoformat()}},
        )

    async def process_all_reminders(self) -> Dict[str, Any]:
        """
        Process all pending reminders.
        Called by scheduler.

        Returns summary of processed reminders.
        """
        logger.info("[REMINDER] Starting reminder processing...")

        optimizations = await self.get_in_progress_optimizations_needing_reminder()

        results = {
            "total_found": len(optimizations),
            "reminders_sent": 0,
            "reminders_failed": 0,
            "logs_created": 0,
        }

        for opt in optimizations:
            try:
                # Get users to notify
                users = await self.get_users_to_notify(opt)

                if not users:
                    logger.info(
                        f"[REMINDER] No users to notify for optimization {opt['id']}"
                    )
                    continue

                # Send reminder
                telegram_sent = await self.send_reminder(opt, users)

                if telegram_sent:
                    results["reminders_sent"] += 1
                else:
                    results["reminders_failed"] += 1

                # Log reminder (always log, even if Telegram failed)
                await self.log_reminder(opt, users, telegram_sent)
                results["logs_created"] += 1

                # Update optimization timestamp
                await self.update_optimization_reminder_timestamp(opt["id"])

            except Exception as e:
                logger.error(
                    f"[REMINDER] Failed to process optimization {opt['id']}: {e}"
                )
                results["reminders_failed"] += 1

        logger.info(f"[REMINDER] Processing complete: {results}")
        return results


# Add method to SeoOptimizationTelegramService for in-progress reminders
async def add_reminder_method_to_telegram_service():
    """
    Adds send_in_progress_reminder method to SeoOptimizationTelegramService.
    This should be called on startup to extend the service.
    """
    from services.seo_optimization_telegram_service import (
        SeoOptimizationTelegramService,
    )
    from services.timezone_helper import format_to_local_time, get_system_timezone

    async def send_in_progress_reminder(
        self,
        optimization: Dict[str, Any],
        network: Dict[str, Any],
        brand: Dict[str, Any],
        users: List[Dict[str, Any]],
        days_in_progress: int,
    ) -> bool:
        """Send reminder for in-progress optimization"""
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
                else "  (No users tagged)"
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

            success = await self._send_telegram_message(message)
            return success

        except Exception as e:
            logger.error(f"[TELEGRAM] Failed to send in-progress reminder: {e}")
            return False

    # Add method to class
    SeoOptimizationTelegramService.send_in_progress_reminder = send_in_progress_reminder
