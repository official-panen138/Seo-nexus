"""
Team Performance Alert Service
==============================

Automatically monitors team conflict resolution performance and sends
alerts to managers when thresholds are breached.

Alert Types:
1. High False Resolution Rate (>15% by default)
2. Stale Conflicts (unresolved for >7 days by default)
3. Resolution Backlog (>10 open conflicts by default)
4. Slow Average Resolution Time (>48 hours by default)

Integrates with Telegram for notifications.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Default thresholds (can be overridden in settings)
DEFAULT_THRESHOLDS = {
    "false_resolution_rate_percent": 15.0,  # Alert if > 15%
    "stale_conflict_days": 7,               # Alert if conflict unresolved > 7 days
    "open_conflict_backlog": 10,            # Alert if > 10 open conflicts
    "avg_resolution_hours": 48.0,           # Alert if avg > 48 hours
    "check_interval_hours": 24,             # How often to check (daily)
}


class TeamPerformanceAlertService:
    """
    Service for monitoring team performance and sending alerts.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._thresholds = None
        self._last_check_key = "team_performance_last_check"
    
    async def get_thresholds(self) -> Dict[str, Any]:
        """Get performance thresholds from settings or use defaults."""
        if self._thresholds:
            return self._thresholds
        
        settings = await self.db.settings.find_one(
            {"key": "team_performance_thresholds"},
            {"_id": 0}
        )
        
        if settings and settings.get("value"):
            self._thresholds = {**DEFAULT_THRESHOLDS, **settings.get("value", {})}
        else:
            self._thresholds = DEFAULT_THRESHOLDS
        
        return self._thresholds
    
    async def save_thresholds(self, thresholds: Dict[str, Any]) -> None:
        """Save custom thresholds to settings."""
        await self.db.settings.update_one(
            {"key": "team_performance_thresholds"},
            {
                "$set": {
                    "key": "team_performance_thresholds",
                    "value": thresholds,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
        self._thresholds = {**DEFAULT_THRESHOLDS, **thresholds}
    
    async def check_performance_and_alert(self) -> Dict[str, Any]:
        """
        Main entry point - check all performance metrics and send alerts if needed.
        
        Returns a summary of checks performed and alerts sent.
        """
        thresholds = await self.get_thresholds()
        
        # Check if enough time has passed since last check
        should_check = await self._should_run_check(thresholds)
        if not should_check:
            return {
                "checked": False,
                "reason": "Check interval not reached",
                "alerts_sent": 0
            }
        
        # Gather metrics
        metrics = await self._gather_performance_metrics()
        
        # Check each threshold and collect alerts
        alerts = []
        
        # 1. False Resolution Rate
        if metrics["false_resolution_rate_percent"] > thresholds["false_resolution_rate_percent"]:
            alerts.append({
                "type": "high_false_resolution_rate",
                "severity": "HIGH",
                "current_value": metrics["false_resolution_rate_percent"],
                "threshold": thresholds["false_resolution_rate_percent"],
                "message": f"False resolution rate is {metrics['false_resolution_rate_percent']:.1f}% "
                          f"(threshold: {thresholds['false_resolution_rate_percent']}%)"
            })
        
        # 2. Stale Conflicts
        if metrics["stale_conflicts"]:
            alerts.append({
                "type": "stale_conflicts",
                "severity": "MEDIUM",
                "current_value": len(metrics["stale_conflicts"]),
                "threshold": thresholds["stale_conflict_days"],
                "message": f"{len(metrics['stale_conflicts'])} conflicts unresolved for "
                          f">{thresholds['stale_conflict_days']} days",
                "conflict_ids": [c["id"] for c in metrics["stale_conflicts"][:5]]
            })
        
        # 3. Open Conflict Backlog
        if metrics["open_count"] > thresholds["open_conflict_backlog"]:
            alerts.append({
                "type": "conflict_backlog",
                "severity": "MEDIUM",
                "current_value": metrics["open_count"],
                "threshold": thresholds["open_conflict_backlog"],
                "message": f"{metrics['open_count']} open conflicts "
                          f"(threshold: {thresholds['open_conflict_backlog']})"
            })
        
        # 4. Slow Average Resolution Time
        if metrics["avg_resolution_hours"] > thresholds["avg_resolution_hours"]:
            alerts.append({
                "type": "slow_resolution_time",
                "severity": "LOW",
                "current_value": metrics["avg_resolution_hours"],
                "threshold": thresholds["avg_resolution_hours"],
                "message": f"Average resolution time is {metrics['avg_resolution_hours']:.1f} hours "
                          f"(threshold: {thresholds['avg_resolution_hours']} hours)"
            })
        
        # Send alerts if any
        alerts_sent = 0
        if alerts:
            alerts_sent = await self._send_performance_alerts(alerts, metrics)
        
        # Update last check timestamp
        await self._update_last_check()
        
        return {
            "checked": True,
            "metrics": metrics,
            "alerts": alerts,
            "alerts_sent": alerts_sent,
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
    
    async def _gather_performance_metrics(self) -> Dict[str, Any]:
        """Gather all performance metrics from the database."""
        thresholds = await self.get_thresholds()
        now = datetime.now(timezone.utc)
        
        # Get all open conflicts
        open_conflicts = await self.db.seo_conflicts.find(
            {
                "status": {"$nin": ["resolved", "approved", "ignored"]},
                "is_active": {"$ne": False}
            },
            {"_id": 0}
        ).to_list(500)
        
        # Get resolved conflicts in last 30 days for rate calculation
        thirty_days_ago = (now - timedelta(days=30)).isoformat()
        resolved_conflicts = await self.db.seo_conflicts.find(
            {
                "status": {"$in": ["resolved", "approved"]},
                "resolved_at": {"$gte": thirty_days_ago}
            },
            {"_id": 0}
        ).to_list(500)
        
        # Calculate false resolution rate
        false_resolutions = [c for c in resolved_conflicts if c.get("is_false_resolution")]
        false_resolution_rate = (
            len(false_resolutions) / len(resolved_conflicts) * 100
            if resolved_conflicts else 0
        )
        
        # Find stale conflicts (open for > threshold days)
        stale_threshold = now - timedelta(days=thresholds["stale_conflict_days"])
        stale_conflicts = []
        for c in open_conflicts:
            detected_str = c.get("first_detected_at") or c.get("detected_at")
            if detected_str:
                try:
                    detected = datetime.fromisoformat(detected_str.replace("Z", "+00:00"))
                    if detected < stale_threshold:
                        days_open = (now - detected).days
                        stale_conflicts.append({
                            "id": c["id"],
                            "conflict_type": c.get("conflict_type"),
                            "days_open": days_open,
                            "network_name": c.get("network_name")
                        })
                except Exception:
                    pass
        
        # Calculate average resolution time
        resolution_times = []
        for c in resolved_conflicts:
            detected_str = c.get("first_detected_at") or c.get("detected_at")
            resolved_str = c.get("resolved_at")
            if detected_str and resolved_str:
                try:
                    detected = datetime.fromisoformat(detected_str.replace("Z", "+00:00"))
                    resolved = datetime.fromisoformat(resolved_str.replace("Z", "+00:00"))
                    hours = (resolved - detected).total_seconds() / 3600
                    if hours >= 0:
                        resolution_times.append(hours)
                except Exception:
                    pass
        
        avg_resolution_hours = (
            sum(resolution_times) / len(resolution_times)
            if resolution_times else 0
        )
        
        return {
            "open_count": len(open_conflicts),
            "resolved_count_30d": len(resolved_conflicts),
            "false_resolution_count": len(false_resolutions),
            "false_resolution_rate_percent": round(false_resolution_rate, 1),
            "stale_conflicts": stale_conflicts,
            "avg_resolution_hours": round(avg_resolution_hours, 1),
            "checked_at": now.isoformat()
        }
    
    async def _send_performance_alerts(
        self, 
        alerts: List[Dict], 
        metrics: Dict
    ) -> int:
        """Send performance alerts via Telegram."""
        try:
            # Get Telegram config
            telegram_config = await self.db.settings.find_one(
                {"key": "telegram"},
                {"_id": 0, "value": 1}
            )
            
            if not telegram_config or not telegram_config.get("value"):
                logger.warning("Telegram not configured, skipping performance alerts")
                return 0
            
            config = telegram_config["value"]
            bot_token = config.get("bot_token")
            chat_id = config.get("chat_id")
            
            if not bot_token or not chat_id:
                logger.warning("Telegram bot_token or chat_id missing")
                return 0
            
            # Build alert message
            message = self._format_performance_alert_message(alerts, metrics)
            
            # Send via Telegram
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "HTML"
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    logger.info(f"Performance alert sent: {len(alerts)} issues")
                    
                    # Log alert to database
                    await self._log_alert(alerts, metrics)
                    return len(alerts)
                else:
                    logger.error(f"Failed to send Telegram alert: {response.text}")
                    return 0
                    
        except Exception as e:
            logger.error(f"Error sending performance alert: {e}")
            return 0
    
    def _format_performance_alert_message(
        self, 
        alerts: List[Dict], 
        metrics: Dict
    ) -> str:
        """Format the performance alert message for Telegram."""
        severity_emoji = {
            "HIGH": "🔴",
            "MEDIUM": "🟡", 
            "LOW": "🟢"
        }
        
        lines = [
            "📊 <b>TEAM PERFORMANCE ALERT</b>",
            "",
            f"<b>Threshold Breaches:</b> {len(alerts)}",
            ""
        ]
        
        for alert in alerts:
            emoji = severity_emoji.get(alert["severity"], "⚪")
            lines.append(f"{emoji} <b>{alert['severity']}</b>: {alert['message']}")
            
            if alert.get("conflict_ids"):
                lines.append(f"   └─ IDs: {', '.join(alert['conflict_ids'][:3])}...")
        
        lines.extend([
            "",
            "<b>Current Metrics (30d):</b>",
            f"• Open Conflicts: {metrics['open_count']}",
            f"• Resolved: {metrics['resolved_count_30d']}",
            f"• Avg Resolution: {metrics['avg_resolution_hours']} hrs",
            f"• False Resolution Rate: {metrics['false_resolution_rate_percent']}%",
            "",
            "⏰ Next check in 24 hours",
            "",
            "📍 <i>Review at /conflicts/dashboard</i>"
        ])
        
        return "\n".join(lines)
    
    async def _log_alert(self, alerts: List[Dict], metrics: Dict) -> None:
        """Log alert to database for history."""
        await self.db.performance_alerts.insert_one({
            "type": "team_performance",
            "alerts": alerts,
            "metrics": metrics,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    async def _should_run_check(self, thresholds: Dict) -> bool:
        """Check if enough time has passed since last check."""
        last_check = await self.db.settings.find_one(
            {"key": self._last_check_key},
            {"_id": 0, "value": 1}
        )
        
        if not last_check or not last_check.get("value"):
            return True
        
        try:
            last_check_time = datetime.fromisoformat(
                last_check["value"].replace("Z", "+00:00")
            )
            interval = timedelta(hours=thresholds.get("check_interval_hours", 24))
            return datetime.now(timezone.utc) > last_check_time + interval
        except Exception:
            return True
    
    async def _update_last_check(self) -> None:
        """Update last check timestamp."""
        await self.db.settings.update_one(
            {"key": self._last_check_key},
            {
                "$set": {
                    "key": self._last_check_key,
                    "value": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
    
    async def get_alert_history(self, days: int = 30) -> List[Dict]:
        """Get performance alert history."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        alerts = await self.db.performance_alerts.find(
            {"created_at": {"$gte": cutoff}},
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        
        return alerts


# Global instance
_performance_service: Optional[TeamPerformanceAlertService] = None


def get_team_performance_service(db: AsyncIOMotorDatabase) -> TeamPerformanceAlertService:
    """Get or create the team performance alert service."""
    global _performance_service
    if _performance_service is None:
        _performance_service = TeamPerformanceAlertService(db)
    return _performance_service
