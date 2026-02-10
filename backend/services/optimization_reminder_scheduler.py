"""
Optimization Reminder Scheduler
================================
Sends periodic reminders for optimizations that are "in_progress" for too long.

Rules:
- Global default reminder interval: 2 days
- Per-network override is supported
- Cron runs every 6 hours
- Reminder stops when status = completed OR reverted
- Update last_reminded_at to prevent spam
"""

import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from services.seo_optimization_telegram_service import SeoOptimizationTelegramService
from services.timezone_helper import format_to_local_time, get_system_timezone

logger = logging.getLogger(__name__)

# Default reminder interval in days
DEFAULT_REMINDER_INTERVAL_DAYS = 2


class OptimizationReminderScheduler:
    """Scheduler for sending in-progress optimization reminders"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.telegram_service = SeoOptimizationTelegramService(db)
        self._running = False

    async def get_global_reminder_config(self) -> Dict[str, Any]:
        """Get global reminder configuration"""
        config = await self.db.settings.find_one({"key": "reminder_config"}, {"_id": 0})
        return config or {
            "enabled": True,
            "default_interval_days": DEFAULT_REMINDER_INTERVAL_DAYS,
        }

    async def get_network_reminder_config(
        self, network_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get per-network reminder configuration override"""
        network = await self.db.seo_networks.find_one(
            {"id": network_id}, {"_id": 0, "reminder_config": 1}
        )
        return network.get("reminder_config") if network else None

    async def get_effective_reminder_interval(self, network_id: str) -> int:
        """
        Get the effective reminder interval for a network.
        Returns interval in days.
        Uses per-network override if set, otherwise global default.
        """
        # Check per-network override
        network_config = await self.get_network_reminder_config(network_id)
        if network_config:
            if not network_config.get("enabled", True):
                return -1  # Disabled for this network
            if network_config.get("interval_days"):
                return network_config["interval_days"]

        # Use global default
        global_config = await self.get_global_reminder_config()
        if not global_config.get("enabled", True):
            return -1  # Globally disabled

        return global_config.get(
            "default_interval_days", DEFAULT_REMINDER_INTERVAL_DAYS
        )

    async def should_send_reminder(self, optimization: Dict[str, Any]) -> bool:
        """
        Check if a reminder should be sent for this optimization.

        Conditions:
        - Status must be "in_progress"
        - Time since last activity >= reminder_interval
        - Time since last reminder >= reminder_interval (to prevent spam)
        """
        if optimization.get("status") != "in_progress":
            return False

        network_id = optimization.get("network_id")
        interval_days = await self.get_effective_reminder_interval(network_id)

        if interval_days < 0:
            # Reminders disabled
            return False

        now = datetime.now(timezone.utc)
        interval = timedelta(days=interval_days)

        # Check last activity
        last_activity = optimization.get("last_activity_at") or optimization.get(
            "created_at"
        )
        if last_activity:
            if isinstance(last_activity, str):
                last_activity = datetime.fromisoformat(
                    last_activity.replace("Z", "+00:00")
                )

            if now - last_activity < interval:
                return False

        # Check last reminder to prevent spam
        last_reminded = optimization.get("last_reminded_at")
        if last_reminded:
            if isinstance(last_reminded, str):
                last_reminded = datetime.fromisoformat(
                    last_reminded.replace("Z", "+00:00")
                )

            if now - last_reminded < interval:
                return False

        return True

    async def send_reminder(self, optimization: Dict[str, Any]) -> bool:
        """Send a reminder notification for an in-progress optimization"""
        try:
            # Get network and brand info
            network = await self.db.seo_networks.find_one(
                {"id": optimization["network_id"]},
                {"_id": 0, "name": 1, "brand_id": 1, "manager_ids": 1},
            )
            if not network:
                logger.warning(
                    f"Network not found for optimization {optimization['id']}"
                )
                return False

            brand = await self.db.brands.find_one(
                {"id": network.get("brand_id")}, {"_id": 0, "name": 1}
            )

            # Get manager info for tagging
            manager_ids = network.get("manager_ids") or []
            managers = []
            if manager_ids:
                managers = await self.db.users.find(
                    {"id": {"$in": manager_ids}},
                    {"_id": 0, "id": 1, "name": 1, "email": 1, "telegram_username": 1},
                ).to_list(50)

            # Calculate days since last update
            last_activity = optimization.get("last_activity_at") or optimization.get(
                "created_at"
            )
            days_since_update = 0
            if last_activity:
                if isinstance(last_activity, str):
                    last_activity = datetime.fromisoformat(
                        last_activity.replace("Z", "+00:00")
                    )
                days_since_update = (datetime.now(timezone.utc) - last_activity).days

            # Send the reminder
            success = await self.telegram_service.send_in_progress_reminder(
                optimization=optimization,
                network={"name": network.get("name", "Unknown")},
                brand={"name": brand.get("name", "Unknown") if brand else "Unknown"},
                users=managers,
                days_in_progress=days_since_update,
            )

            if success:
                # Update last_reminded_at
                await self.db.seo_optimizations.update_one(
                    {"id": optimization["id"]},
                    {
                        "$set": {
                            "last_reminded_at": datetime.now(timezone.utc).isoformat()
                        }
                    },
                )
                logger.info(f"Sent reminder for optimization {optimization['id']}")

            return success

        except Exception as e:
            logger.error(
                f"Failed to send reminder for optimization {optimization['id']}: {e}"
            )
            return False

    async def run_reminder_check(self) -> Dict[str, Any]:
        """
        Run a single check for all in-progress optimizations.
        Returns stats about the run.
        """
        stats = {"checked": 0, "reminders_sent": 0, "errors": 0, "skipped": 0}

        try:
            # Find all in-progress optimizations
            cursor = self.db.seo_optimizations.find(
                {"status": "in_progress"}, {"_id": 0}
            )

            async for optimization in cursor:
                stats["checked"] += 1

                try:
                    if await self.should_send_reminder(optimization):
                        success = await self.send_reminder(optimization)
                        if success:
                            stats["reminders_sent"] += 1
                        else:
                            stats["errors"] += 1
                    else:
                        stats["skipped"] += 1
                except Exception as e:
                    logger.error(
                        f"Error processing optimization {optimization.get('id')}: {e}"
                    )
                    stats["errors"] += 1

            logger.info(f"Reminder check complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Reminder check failed: {e}")
            stats["errors"] += 1
            return stats

    async def start_scheduler(self, interval_hours: int = 6):
        """
        Start the background scheduler loop.
        Runs every interval_hours hours.
        """
        self._running = True
        logger.info(
            f"Starting optimization reminder scheduler (interval: {interval_hours}h)"
        )

        while self._running:
            try:
                await self.run_reminder_check()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            # Wait for next interval
            await asyncio.sleep(interval_hours * 3600)

    def stop_scheduler(self):
        """Stop the background scheduler"""
        self._running = False
        logger.info("Optimization reminder scheduler stopped")


# Global scheduler instance
_scheduler: Optional[OptimizationReminderScheduler] = None


def get_reminder_scheduler() -> Optional[OptimizationReminderScheduler]:
    """Get the global scheduler instance"""
    return _scheduler


def init_reminder_scheduler(db: AsyncIOMotorDatabase) -> OptimizationReminderScheduler:
    """Initialize the global scheduler instance"""
    global _scheduler
    _scheduler = OptimizationReminderScheduler(db)
    return _scheduler
