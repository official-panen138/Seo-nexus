"""
Optimization Reminder Scheduler
===============================

Integrates APScheduler with FastAPI to run automatic reminders for
"In Progress" optimizations and weekly digest emails.

Features:
- Runs at configurable intervals (default: every 2 days)
- Reads interval from global settings
- Supports manual trigger via API
- Weekly digest email scheduler
- Graceful shutdown on app termination
"""

import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """Scheduler for automatic optimization reminders and weekly digest"""
    
    DEFAULT_INTERVAL_HOURS = 24  # Check daily, but only send if interval_days passed
    JOB_ID = "optimization_reminder_job"
    DIGEST_JOB_ID = "weekly_digest_job"
    
    # Day name to APScheduler day_of_week mapping
    DAY_MAP = {
        'monday': 'mon', 'tuesday': 'tue', 'wednesday': 'wed', 'thursday': 'thu',
        'friday': 'fri', 'saturday': 'sat', 'sunday': 'sun'
    }
    
    def __init__(self, db: AsyncIOMotorDatabase, telegram_service=None):
        self.db = db
        self.telegram_service = telegram_service
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._reminder_service = None
        self._digest_service = None
    
    @property
    def reminder_service(self):
        """Lazy load reminder service to avoid circular imports"""
        if self._reminder_service is None:
            from services.optimization_reminder_service import OptimizationReminderService
            self._reminder_service = OptimizationReminderService(
                db=self.db,
                telegram_service=self.telegram_service
            )
        return self._reminder_service
    
    @property
    def digest_service(self):
        """Lazy load weekly digest service"""
        if self._digest_service is None:
            from services.weekly_digest_service import get_weekly_digest_service
            self._digest_service = get_weekly_digest_service(self.db)
        return self._digest_service
    
    async def _run_digest_job(self):
        """Execute the weekly digest email job"""
        logger.info("[SCHEDULER] Starting weekly digest job execution...")
        
        try:
            # Check if digest is enabled
            settings = await self.digest_service.get_digest_settings()
            
            if not settings.get("enabled", False):
                logger.info("[SCHEDULER] Weekly digest is disabled, skipping...")
                return
            
            # Send the digest
            result = await self.digest_service.generate_and_send_digest()
            
            # Log execution
            await self.db.scheduler_execution_logs.insert_one({
                "job_id": self.DIGEST_JOB_ID,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "results": result,
                "status": "success" if result.get("success") else "failed"
            })
            
            logger.info(f"[SCHEDULER] Weekly digest job completed: {result}")
            
        except Exception as e:
            logger.error(f"[SCHEDULER] Weekly digest job failed: {e}")
            
            await self.db.scheduler_execution_logs.insert_one({
                "job_id": self.DIGEST_JOB_ID,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "status": "failed"
            })
    
    async def _run_reminder_job(self):
        """Execute the reminder processing job"""
        logger.info("[SCHEDULER] Starting reminder job execution...")
        
        try:
            # Check if reminders are globally enabled
            settings = await self.db.settings.find_one(
                {"key": "optimization_reminders"},
                {"_id": 0}
            )
            
            if settings and not settings.get("enabled", True):
                logger.info("[SCHEDULER] Reminders are disabled globally, skipping...")
                return
            
            # Run the reminder processing
            results = await self.reminder_service.process_all_reminders()
            
            # Log execution to database
            await self.db.scheduler_execution_logs.insert_one({
                "job_id": self.JOB_ID,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "results": results,
                "status": "success"
            })
            
            logger.info(f"[SCHEDULER] Reminder job completed: {results}")
            
        except Exception as e:
            logger.error(f"[SCHEDULER] Reminder job failed: {e}")
            
            # Log failure
            await self.db.scheduler_execution_logs.insert_one({
                "job_id": self.JOB_ID,
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "status": "failed"
            })
    
    def start(self):
        """Start the scheduler"""
        if self.scheduler is not None:
            logger.warning("[SCHEDULER] Scheduler already running")
            return
        
        self.scheduler = AsyncIOScheduler()
        
        # Add the reminder job - runs every 24 hours
        # The job itself checks if individual optimizations need reminders based on interval_days
        self.scheduler.add_job(
            self._run_reminder_job,
            trigger=IntervalTrigger(hours=self.DEFAULT_INTERVAL_HOURS),
            id=self.JOB_ID,
            name="Optimization In-Progress Reminders",
            replace_existing=True
        )
        
        # Add the weekly digest job - runs weekly on configured day/time
        # Default: Monday 9:00 AM (will be updated dynamically based on settings)
        self.scheduler.add_job(
            self._run_digest_job,
            trigger=CronTrigger(day_of_week='mon', hour=9, minute=0),
            id=self.DIGEST_JOB_ID,
            name="Weekly Domain Health Digest",
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info(f"[SCHEDULER] Started reminder scheduler (runs every {self.DEFAULT_INTERVAL_HOURS} hours)")
        logger.info("[SCHEDULER] Started weekly digest scheduler (Monday 9:00 AM default)")
        
        # Update digest schedule from settings asynchronously
        import asyncio
        asyncio.create_task(self._update_digest_schedule())
    
    def stop(self):
        """Stop the scheduler gracefully"""
        if self.scheduler is not None:
            self.scheduler.shutdown(wait=False)
            self.scheduler = None
            logger.info("[SCHEDULER] Reminder scheduler stopped")
    
    async def trigger_now(self) -> dict:
        """Manually trigger the reminder job"""
        logger.info("[SCHEDULER] Manual trigger requested")
        await self._run_reminder_job()
        return {"message": "Reminder job triggered manually", "timestamp": datetime.now(timezone.utc).isoformat()}
    
    def get_next_run_time(self) -> Optional[str]:
        """Get the next scheduled run time"""
        if self.scheduler is None:
            return None
        
        job = self.scheduler.get_job(self.JOB_ID)
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
        return None
    
    def get_status(self) -> dict:
        """Get scheduler status"""
        digest_next_run = None
        if self.scheduler:
            digest_job = self.scheduler.get_job(self.DIGEST_JOB_ID)
            if digest_job and digest_job.next_run_time:
                digest_next_run = digest_job.next_run_time.isoformat()
        
        return {
            "running": self.scheduler is not None and self.scheduler.running,
            "job_id": self.JOB_ID,
            "interval_hours": self.DEFAULT_INTERVAL_HOURS,
            "next_run_time": self.get_next_run_time(),
            "digest_job_id": self.DIGEST_JOB_ID,
            "digest_next_run_time": digest_next_run
        }
    
    async def _update_digest_schedule(self):
        """Update digest job schedule from settings"""
        try:
            settings = await self.digest_service.get_digest_settings()
            
            day = settings.get("schedule_day", "monday").lower()
            hour = settings.get("schedule_hour", 9)
            minute = settings.get("schedule_minute", 0)
            
            day_of_week = self.DAY_MAP.get(day, 'mon')
            
            if self.scheduler:
                self.scheduler.reschedule_job(
                    self.DIGEST_JOB_ID,
                    trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute)
                )
                logger.info(f"[SCHEDULER] Updated digest schedule: {day} at {hour:02d}:{minute:02d}")
        except Exception as e:
            logger.warning(f"[SCHEDULER] Failed to update digest schedule: {e}")
    
    async def update_digest_schedule(self, day: str, hour: int, minute: int):
        """Update the weekly digest schedule"""
        if not self.scheduler:
            return
        
        day_of_week = self.DAY_MAP.get(day.lower(), 'mon')
        
        self.scheduler.reschedule_job(
            self.DIGEST_JOB_ID,
            trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute)
        )
        logger.info(f"[SCHEDULER] Updated digest schedule: {day} at {hour:02d}:{minute:02d}")
    
    async def trigger_digest_now(self) -> dict:
        """Manually trigger the weekly digest job"""
        logger.info("[SCHEDULER] Manual digest trigger requested")
        await self._run_digest_job()
        return {"message": "Digest job triggered manually", "timestamp": datetime.now(timezone.utc).isoformat()}


# Global scheduler instance (initialized in server.py)
reminder_scheduler: Optional[ReminderScheduler] = None


def get_reminder_scheduler() -> Optional[ReminderScheduler]:
    """Get the global reminder scheduler instance"""
    return reminder_scheduler


def init_reminder_scheduler(db: AsyncIOMotorDatabase, telegram_service=None) -> ReminderScheduler:
    """Initialize the global reminder scheduler"""
    global reminder_scheduler
    reminder_scheduler = ReminderScheduler(db=db, telegram_service=telegram_service)
    return reminder_scheduler
