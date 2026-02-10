"""
Domain Monitoring Services for SEO-NOC V3
==========================================

Two independent monitoring engines:
1. Domain Expiration Monitoring - Daily job
2. Domain Availability (Ping/HTTP) Monitoring - Interval-based job

These engines operate INDEPENDENTLY and send Telegram alerts separately.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
from services.timezone_helper import (
    format_to_local_time,
    format_now_local,
    get_system_timezone,
)

logger = logging.getLogger(__name__)


# ==================== MONITORING SETTINGS MODEL ====================

DEFAULT_MONITORING_SETTINGS = {
    "expiration": {
        "enabled": True,
        "alert_window_days": 30,  # Start alerting 30 days before expiration
        "alert_thresholds": [30, 14, 7],  # Specific days to send one-time alerts
        "critical_threshold": 7,  # Below this, send 2x daily alerts
        "critical_alert_hours": [9, 18],  # GMT+7 hours for <7 days alerts
        "include_auto_renew": False,  # Include domains with auto-renew enabled
    },
    "availability": {
        "enabled": True,
        "default_interval_seconds": 300,  # 5 minutes
        "alert_on_down": True,  # Alert when status changes UP → DOWN
        "alert_on_recovery": False,  # Alert when status changes DOWN → UP
        "timeout_seconds": 15,
        "follow_redirects": True,
    },
    "telegram": {
        "enabled": True,
    },
}


class MonitoringSettingsService:
    """Service for managing monitoring configuration"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.monitoring_settings

    async def get_settings(self) -> Dict[str, Any]:
        """Get current monitoring settings, or defaults if not configured"""
        settings = await self.collection.find_one(
            {"key": "monitoring_config"}, {"_id": 0}
        )
        if settings:
            # Merge with defaults to ensure all keys exist
            result = DEFAULT_MONITORING_SETTINGS.copy()
            for category in ["expiration", "availability", "telegram"]:
                if category in settings:
                    result[category] = {**result[category], **settings[category]}
            return result
        return DEFAULT_MONITORING_SETTINGS.copy()

    async def update_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update monitoring settings"""
        current = await self.get_settings()

        # Merge updates
        for category, values in updates.items():
            if category in current and isinstance(values, dict):
                current[category] = {**current[category], **values}

        await self.collection.update_one(
            {"key": "monitoring_config"},
            {
                "$set": {
                    **current,
                    "key": "monitoring_config",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
            upsert=True,
        )
        return current


class TelegramAlertService:
    """Service for sending Telegram alerts to the general monitoring channel"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def get_telegram_config(self) -> tuple:
        """Get Telegram bot token and chat ID from settings"""
        settings = await self.db.settings.find_one({"key": "telegram"}, {"_id": 0})
        if settings:
            return settings.get("bot_token", ""), settings.get("chat_id", "")
        return "", ""

    async def send_alert(self, message: str) -> bool:
        """Send alert to Telegram"""
        bot_token, chat_id = await self.get_telegram_config()

        if not bot_token or not chat_id:
            logger.warning("Telegram not configured, skipping alert")
            return False

        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                    timeout=10,
                )
                if response.status_code == 200:
                    logger.info("Telegram alert sent successfully")
                    return True
                else:
                    logger.error(f"Telegram API error: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False


class DomainMonitoringTelegramService:
    """
    Dedicated Telegram service for Domain Monitoring alerts.
    Uses SEPARATE configuration from SEO notifications.
    NO fallback to other channels - if not configured, alerts are logged but not sent.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def get_telegram_config(self) -> Optional[Dict[str, Any]]:
        """
        Get dedicated Domain Monitoring Telegram configuration.
        Returns None if not configured (NO fallback).
        """
        settings = await self.db.settings.find_one(
            {"key": "telegram_monitoring"}, {"_id": 0}
        )

        if not settings:
            logger.warning("Domain Monitoring Telegram not configured")
            return None

        if not settings.get("enabled", True):
            logger.info("Domain Monitoring Telegram notifications disabled")
            return None

        bot_token = settings.get("bot_token")
        chat_id = settings.get("chat_id")

        if not bot_token or not chat_id:
            logger.warning("Domain Monitoring Telegram missing bot_token or chat_id")
            return None

        return settings

    async def send_alert(self, message: str) -> bool:
        """
        Send alert to dedicated Domain Monitoring Telegram channel.
        NO fallback - if not configured, returns False.
        """
        config = await self.get_telegram_config()

        if not config:
            logger.warning("Domain Monitoring alert not sent - Telegram not configured")
            return False

        try:
            url = f"https://api.telegram.org/bot{config['bot_token']}/sendMessage"
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json={
                        "chat_id": config["chat_id"],
                        "text": message,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                    timeout=15,
                )

                if response.status_code == 200:
                    logger.info("Domain Monitoring Telegram alert sent successfully")
                    return True
                else:
                    logger.error(
                        f"Domain Monitoring Telegram API error: {response.text}"
                    )
                    return False
        except Exception as e:
            logger.error(f"Failed to send Domain Monitoring alert: {e}")
            return False


# ==================== EXPIRATION MONITORING ENGINE ====================


class ExpirationMonitoringService:
    """
    Domain Expiration Monitoring Engine (SEO-Aware)

    - Runs daily
    - Alerts at thresholds: 30, 14, 7 days, then daily when < 7
    - Includes full SEO context, upstream chain, downstream impact
    - Uses dedicated Domain Monitoring Telegram channel
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.telegram = DomainMonitoringTelegramService(db)
        self.settings_service = MonitoringSettingsService(db)
        # Import SEO context enricher
        from services.seo_context_enricher import SeoContextEnricher

        self.seo_enricher = SeoContextEnricher(db)

    async def check_all_domains(self) -> Dict[str, Any]:
        """Check all domains for expiration alerts"""
        settings = await self.settings_service.get_settings()
        exp_settings = settings.get("expiration", {})

        if not exp_settings.get("enabled", True):
            logger.info("Expiration monitoring is disabled")
            return {"checked": 0, "alerts_sent": 0, "skipped": 0}

        alert_thresholds = exp_settings.get("alert_thresholds", [30, 14, 7, 3, 1, 0])
        include_auto_renew = exp_settings.get("include_auto_renew", False)

        # Build query for domains with expiration dates
        query = {"expiration_date": {"$ne": None, "$exists": True}}

        # Optionally exclude auto-renew domains
        if not include_auto_renew:
            query["$or"] = [{"auto_renew": False}, {"auto_renew": {"$exists": False}}]

        domains = await self.db.asset_domains.find(query, {"_id": 0}).to_list(10000)

        now = datetime.now(timezone.utc)
        checked = 0
        alerts_sent = 0
        skipped = 0

        for domain in domains:
            checked += 1
            result = await self._check_domain_expiration(domain, now, alert_thresholds)
            if result == "sent":
                alerts_sent += 1
            elif result == "skipped":
                skipped += 1

        logger.info(
            f"Expiration check complete: {checked} checked, {alerts_sent} alerts sent, {skipped} skipped"
        )
        return {"checked": checked, "alerts_sent": alerts_sent, "skipped": skipped}

    async def _check_domain_expiration(
        self, domain: Dict[str, Any], now: datetime, alert_thresholds: list
    ) -> str:
        """Check single domain expiration and send SEO-aware alert if needed"""
        expiration_str = domain.get("expiration_date")
        if not expiration_str:
            return "no_date"

        try:
            # Parse expiration date
            expiration = datetime.fromisoformat(expiration_str.replace("Z", "+00:00"))
            days_remaining = (expiration.date() - now.date()).days

            # Get settings
            settings = await self.settings_service.get_settings()
            exp_settings = settings.get("expiration", {})
            alert_thresholds = exp_settings.get("alert_thresholds", [30, 14, 7])
            critical_threshold = exp_settings.get("critical_threshold", 7)
            critical_hours = exp_settings.get("critical_alert_hours", [9, 18])
            
            # Check if we should alert
            should_alert = False
            alert_reason = ""
            
            # Get current hour in GMT+7
            gmt7_offset = timedelta(hours=7)
            current_hour_gmt7 = (now + gmt7_offset).hour
            
            if days_remaining < 0:
                # Already expired - alert immediately
                should_alert = True
                alert_reason = "expired"
            elif days_remaining < critical_threshold:
                # < 7 days: Send 2x daily at 09:00 and 18:00 GMT+7
                # Check if current hour is within 1 hour of alert times
                for alert_hour in critical_hours:
                    if abs(current_hour_gmt7 - alert_hour) <= 1:
                        should_alert = True
                        alert_reason = f"critical_{alert_hour}h"
                        break
            else:
                # Check specific thresholds (30, 14, 7 days)
                for threshold in sorted(alert_thresholds, reverse=True):
                    if days_remaining == threshold:
                        should_alert = True
                        alert_reason = f"threshold_{threshold}"
                        break

            if not should_alert:
                return "not_due"

            # Check deduplication
            last_alert_str = domain.get("expiration_alert_sent_at")
            last_threshold = domain.get("last_expiration_threshold")
            last_alert_reason = domain.get("last_alert_reason", "")

            if last_alert_str:
                last_alert = datetime.fromisoformat(
                    last_alert_str.replace("Z", "+00:00")
                )
                hours_since_alert = (now - last_alert).total_seconds() / 3600

                if days_remaining < critical_threshold:
                    # For critical (<7 days): allow alerts every 10 hours (2x/day)
                    if hours_since_alert < 10:
                        return "skipped"
                else:
                    # For threshold alerts (30, 14, 7): only once per threshold
                    if last_alert_reason == alert_reason:
                        return "skipped"
                    # Also skip if alerted within 20 hours for same day count
                    if hours_since_alert < 20 and last_threshold == days_remaining:
                        return "skipped"

            # Enrich with brand/registrar and SEO context
            enriched = await self._enrich_domain_full(domain)

            # Format and send Telegram alert
            message = self._format_expiration_alert_seo_aware(enriched, days_remaining)
            sent = await self.telegram.send_alert(message)

            # Also send email alert for HIGH/CRITICAL severity
            try:
                from services.email_alert_service import get_email_alert_service

                email_service = get_email_alert_service(self.db)

                # Get network_id from SEO context if available
                network_id = None
                seo = enriched.get("seo", {})
                if seo.get("seo_context"):
                    network_id = seo["seo_context"][0].get("network_id")

                await email_service.send_expiration_alert(
                    enriched, days_remaining, network_id
                )
            except Exception as email_err:
                logger.warning(
                    f"Email alert failed for {domain.get('domain_name')}: {email_err}"
                )

            if sent:
                # Update tracking
                await self.db.asset_domains.update_one(
                    {"id": domain["id"]},
                    {
                        "$set": {
                            "expiration_alert_sent_at": now.isoformat(),
                            "last_expiration_threshold": days_remaining,
                            "last_alert_reason": alert_reason,
                        }
                    },
                )

                # Create alert record
                await self._create_alert_record(enriched, days_remaining)

                return "sent"

            return "failed"

        except Exception as e:
            logger.error(
                f"Error checking expiration for {domain.get('domain_name')}: {e}"
            )
            return "error"

    async def _enrich_domain_full(self, domain: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich domain with brand, registrar, and full SEO context"""
        enriched = {**domain}

        # Brand
        if domain.get("brand_id"):
            brand = await self.db.brands.find_one(
                {"id": domain["brand_id"]}, {"_id": 0, "name": 1}
            )
            enriched["brand_name"] = brand["name"] if brand else "Unknown"
        else:
            enriched["brand_name"] = "N/A"

        # Registrar
        if domain.get("registrar_id"):
            registrar = await self.db.registrars.find_one(
                {"id": domain["registrar_id"]}, {"_id": 0, "name": 1}
            )
            enriched["registrar_name"] = (
                registrar["name"] if registrar else domain.get("registrar", "N/A")
            )
        else:
            enriched["registrar_name"] = domain.get("registrar", "N/A")

        # Timezone
        tz_str, tz_label = await get_system_timezone(self.db)
        enriched["_timezone_str"] = tz_str
        enriched["_timezone_label"] = tz_label

        # SEO context enrichment
        seo_context = await self.seo_enricher.enrich_domain_with_seo_context(
            domain.get("domain_name", ""), domain.get("id")
        )
        enriched["seo"] = seo_context

        return enriched

    def _format_expiration_alert_seo_aware(
        self, domain: Dict[str, Any], days_remaining: int, is_test: bool = False
    ) -> str:
        """Format SEO-aware expiration alert for Telegram"""
        seo = domain.get("seo", {})
        impact_score = seo.get("impact_score", {})

        # Determine severity based on SEO impact
        base_severity = impact_score.get("severity", "LOW")
        if days_remaining <= 0:
            severity = "CRITICAL"
        elif days_remaining <= 3:
            severity = "CRITICAL" if base_severity in ["CRITICAL", "HIGH"] else "HIGH"
        elif days_remaining <= 7:
            severity = (
                base_severity if base_severity in ["CRITICAL", "HIGH"] else "MEDIUM"
            )
        else:
            severity = base_severity

        severity_emoji = {
            "CRITICAL": "🔴",
            "HIGH": "🟠",
            "MEDIUM": "🟡",
            "LOW": "🔵",
        }.get(severity, "⚪")

        # Issue text
        if days_remaining < 0:
            issue = f"EXPIRED ({abs(days_remaining)} days ago)"
        elif days_remaining == 0:
            issue = "EXPIRES TODAY"
        elif days_remaining == 1:
            issue = "Expires TOMORROW"
        else:
            issue = f"Expires in {days_remaining} days"

        # Timezone
        tz_str = domain.get("_timezone_str", "Asia/Jakarta")
        tz_label = domain.get("_timezone_label", "GMT+7")
        local_time = format_now_local(tz_str, tz_label)

        # Build message
        test_marker = "🧪 <b>TEST MODE</b> - " if is_test else ""
        lines = [
            f"{test_marker}{severity_emoji} <b>DOMAIN EXPIRATION ALERT</b>",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━",
            "📅 <b>EXPIRATION INFO</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"• <b>Domain:</b> <code>{domain.get('domain_name', 'Unknown')}</code>",
            f"• <b>Brand:</b> {domain.get('brand_name', 'N/A')}",
            f"• <b>Registrar:</b> {domain.get('registrar_name', 'N/A')}",
            f"• <b>Status:</b> {issue}",
            f"• <b>Expiry Date:</b> {domain.get('expiration_date', 'N/A')}",
            f"• <b>Severity:</b> {severity}",
        ]

        # SEO Context section
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🧩 <b>SEO CONTEXT</b>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        
        if seo.get("used_in_seo"):
            for ctx in seo.get("seo_context", [])[:3]:
                lines.append(f"• <b>Network:</b> {ctx.get('network_name', 'N/A')}")
                lines.append(f"• <b>Brand:</b> {ctx.get('brand_name', 'N/A')}")
                lines.append(f"• <b>Role:</b> {ctx.get('role', 'N/A')}")
                lines.append(f"• <b>Tier:</b> {ctx.get('tier_label', 'N/A')}")
                lines.append(
                    f"• <b>Status:</b> {ctx.get('domain_status', 'N/A').replace('_', ' ').title()}"
                )

            if seo.get("additional_networks_count", 0) > 0:
                lines.append("")
                lines.append(
                    f"<i>Also used in +{seo['additional_networks_count']} other networks</i>"
                )

            # Structure Chain - use full network structure formatted by tiers
            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("🔗 <b>FULL SEO STRUCTURE</b>")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            
            # Use pre-fetched full structure if available
            full_structure_lines = seo.get("full_structure_lines", [])
            if full_structure_lines:
                for line in full_structure_lines:
                    lines.append(line)
            else:
                # Fallback to old chain display
                chain = seo.get("upstream_chain", [])
                if chain:
                    # Start with the domain
                    first_ctx = seo.get("seo_context", [{}])[0]
                    status_label = first_ctx.get("domain_status", "").replace("_", " ").title()
                    lines.append(f"🗑️ {domain.get('domain_name', 'Unknown')} [{status_label}]")
                    
                    for hop in chain:
                        target = hop.get("target", hop.get("node", ""))
                        relation = hop.get("target_relation", hop.get("relation", ""))
                        
                        if hop.get("is_end"):
                            end_reason = hop.get("end_reason", "END")
                            if "money" in end_reason.lower() or hop.get("relation") == "main":
                                lines.append(f"   → 💰 {hop.get('node', target)} [{relation}]")
                                lines.append("   → END: 💰 MONEY SITE")
                            else:
                                lines.append(f"   → {hop.get('node', target)} [{relation}]")
                                lines.append(f"   → END: {end_reason}")
                        else:
                            lines.append(f"   → {target} [{relation}]")
                    
                    # If chain didn't end with money site marker
                    if not chain or not chain[-1].get("is_end"):
                        if chain:
                            last_hop = chain[-1]
                            if last_hop.get("relation") == "main" or "money" in str(last_hop.get("target", "")).lower():
                                lines.append("   → END: 💰 MONEY SITE")
                            else:
                                lines.append("   → END: (chain incomplete)")
                else:
                    # No chain - check if it's orphan or main
                    first_ctx = seo.get("seo_context", [{}])[0] if seo.get("seo_context") else {}
                    if first_ctx.get("role") == "main":
                        lines.append(f"💰 {domain.get('domain_name', 'Unknown')} [Primary]")
                        lines.append("   → END: 💰 THIS IS MONEY SITE")
                    else:
                        status_label = first_ctx.get("domain_status", "").replace("_", " ").title()
                        lines.append(f"⚠️ {domain.get('domain_name', 'Unknown')} [{status_label}]")
                        lines.append("   → END: ⚠️ ORPHAN NODE (no target)")

            # Downstream Impact
            downstream = seo.get("downstream_impact", [])
            if downstream:
                lines.append("")
                lines.append("━━━━━━━━━━━━━━━━━━━━━━")
                lines.append("📌 <b>DOWNSTREAM IMPACT</b>")
                lines.append("━━━━━━━━━━━━━━━━━━━━━━")
                lines.append(f"<b>{len(downstream)}</b> nodes will lose authority flow:")
                for d in downstream[:5]:
                    lines.append(f"  • {d['node']} [{d.get('relation', '')}]")
                if len(downstream) > 5:
                    lines.append(f"  ... +{len(downstream) - 5} more")

            # Impact Score
            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("🔥 <b>SEO IMPACT</b>")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"• <b>Severity:</b> {impact_score.get('severity', 'LOW')}")
            lines.append(
                f"• <b>Networks Affected:</b> {impact_score.get('networks_affected', 0)}"
            )
            lines.append(
                f"• <b>Downstream Nodes:</b> {impact_score.get('downstream_nodes_count', 0)}"
            )
            lines.append(
                f"• <b>Reaches Money Site:</b> {'✅ YES' if impact_score.get('reaches_money_site') else '❌ NO'}"
            )
            if impact_score.get("highest_tier_impacted") is not None:
                lines.append(
                    f"• <b>Highest Tier:</b> Tier {impact_score.get('highest_tier_impacted')}"
                )
        else:
            lines.append("<i>Domain not used in any SEO Network</i>")
            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("🔥 <b>SEO IMPACT</b>")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("• <b>Severity:</b> LOW")
            lines.append("• <b>Networks Affected:</b> 0")
            lines.append("• <b>Reaches Money Site:</b> ❌ NO")

        # Footer
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"🕐 <b>Checked:</b> {local_time}")
        
        if is_test:
            lines.append("")
            lines.append("<i>⚠️ This is a TEST alert - no action tracking affected</i>")

        return "\n".join(lines)

    async def _create_alert_record(self, domain: Dict[str, Any], days_remaining: int):
        """Create alert record in database"""
        import uuid

        seo = domain.get("seo", {})
        impact_score = seo.get("impact_score", {})
        severity = impact_score.get("severity", "low").lower()

        if days_remaining <= 0:
            severity = "critical"
        elif days_remaining <= 3 and severity not in ["critical"]:
            severity = "high"

        alert = {
            "id": str(uuid.uuid4()),
            "domain_id": domain["id"],
            "domain_name": domain.get("domain_name", "Unknown"),
            "brand_name": domain.get("brand_name"),
            "alert_type": "expiration",
            "severity": severity,
            "title": (
                "Domain Expired"
                if days_remaining <= 0
                else f"Expires in {days_remaining} days"
            ),
            "message": f"Domain {domain['domain_name']} expiration warning",
            "details": {
                "days_remaining": days_remaining,
                "expiration_date": domain.get("expiration_date"),
                "auto_renew": domain.get("auto_renew", False),
                "registrar": domain.get("registrar_name"),
                "seo_context": seo,
            },
            "acknowledged": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await self.db.alerts.insert_one(alert)

    async def send_test_expiration_alert(
        self,
        domain_id: str,
        simulated_days: int,
        triggered_by: str,
    ) -> Dict[str, Any]:
        """
        Send a TEST expiration alert for QA purposes.
        
        - Uses same formatting as real alerts
        - Marked as TEST MODE
        - Does NOT affect deduplication counters or schedules
        - Logged with is_test=true
        
        Args:
            domain_id: The domain ID to test
            simulated_days: Simulated days until expiration (e.g., 30, 14, 7, 3, 0, -1)
            triggered_by: User email who triggered the test
            
        Returns:
            Dict with success status and message details
        """
        import uuid
        
        # Get domain
        domain = await self.db.asset_domains.find_one({"id": domain_id}, {"_id": 0})
        if not domain:
            return {"success": False, "error": "Domain not found"}
        
        # Enrich with full SEO context
        enriched = await self._enrich_domain_full(domain)
        
        # Format message with TEST marker
        message = self._format_expiration_alert_seo_aware(enriched, simulated_days, is_test=True)
        
        # Send via Telegram
        sent = await self.telegram.send_alert(message)
        
        # Log the test (but don't affect domain tracking)
        test_log = {
            "id": str(uuid.uuid4()),
            "domain_id": domain_id,
            "domain_name": domain.get("domain_name"),
            "alert_type": "expiration_test",
            "simulated_days": simulated_days,
            "triggered_by": triggered_by,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "is_test": True,
            "telegram_sent": sent,
            "seo_context": enriched.get("seo", {}),
        }
        await self.db.monitoring_test_logs.insert_one(test_log)
        
        return {
            "success": sent,
            "domain_name": domain.get("domain_name"),
            "simulated_days": simulated_days,
            "message_preview": message[:500] + "..." if len(message) > 500 else message,
            "seo_used": enriched.get("seo", {}).get("used_in_seo", False),
        }


# ==================== AVAILABILITY MONITORING ENGINE ====================


class AvailabilityMonitoringService:
    """
    Domain Availability (Ping/HTTP) Monitoring Engine (SEO-Aware)

    - Runs at configurable intervals (e.g., every 5 min)
    - Only checks domains with monitoring_enabled=True
    - Detects: UP, DOWN (timeout, DNS, 5xx), SOFT_BLOCKED (Cloudflare, captcha, geo-block)
    - Alerts on UP → DOWN transition (CRITICAL)
    - Alerts on SOFT_BLOCKED (WARNING)
    - Optional recovery alert on DOWN → UP
    - Includes full SEO context, upstream chain, downstream impact
    - Uses dedicated Domain Monitoring Telegram channel
    """

    # Soft block detection patterns
    SOFT_BLOCK_INDICATORS = {
        "cloudflare_challenge": [
            "cf-ray",
            "checking your browser",
            "challenge-platform",
        ],
        "captcha": ["captcha", "recaptcha", "hcaptcha"],
        "geo_blocked": [
            "access denied",
            "not available in your country",
            "region blocked",
        ],
        "bot_protection": ["bot detected", "automated access", "please verify"],
    }

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.telegram = DomainMonitoringTelegramService(db)
        self.settings_service = MonitoringSettingsService(db)
        # Import SEO context enricher
        from services.seo_context_enricher import SeoContextEnricher

        self.seo_enricher = SeoContextEnricher(db)

    async def check_all_domains(self) -> Dict[str, Any]:
        """Check all monitored domains for availability"""
        settings = await self.settings_service.get_settings()
        avail_settings = settings.get("availability", {})

        if not avail_settings.get("enabled", True):
            logger.info("Availability monitoring is disabled")
            return {
                "checked": 0,
                "up": 0,
                "down": 0,
                "soft_blocked": 0,
                "alerts_sent": 0,
            }

        # Get domains with monitoring enabled
        domains = await self.db.asset_domains.find(
            {"monitoring_enabled": True}, {"_id": 0}
        ).to_list(10000)

        now = datetime.now(timezone.utc)
        checked = 0
        up_count = 0
        down_count = 0
        soft_blocked_count = 0
        alerts_sent = 0

        for domain in domains:
            # Check if it's time to monitor based on interval
            if not self._should_check_now(domain, now):
                continue

            checked += 1
            result = await self._check_domain_availability(domain, avail_settings)

            if result["status"] == "up":
                up_count += 1
            elif result["status"] == "down":
                down_count += 1
            elif result["status"] == "soft_blocked":
                soft_blocked_count += 1

            if result.get("alert_sent"):
                alerts_sent += 1

        logger.info(
            f"Availability check complete: {checked} checked, {up_count} up, {down_count} down, {soft_blocked_count} soft_blocked, {alerts_sent} alerts"
        )
        return {
            "checked": checked,
            "up": up_count,
            "down": down_count,
            "soft_blocked": soft_blocked_count,
            "alerts_sent": alerts_sent,
        }

    def _should_check_now(self, domain: Dict[str, Any], now: datetime) -> bool:
        """Determine if domain should be checked based on interval"""
        last_check_str = domain.get("last_checked_at")
        interval = domain.get("monitoring_interval", "1hour")

        interval_map = {"5min": 300, "15min": 900, "1hour": 3600, "daily": 86400}
        interval_secs = interval_map.get(interval, 3600)

        if not last_check_str:
            return True

        try:
            last_check = datetime.fromisoformat(last_check_str.replace("Z", "+00:00"))
            elapsed = (now - last_check).total_seconds()
            return elapsed >= interval_secs
        except (ValueError, TypeError):
            return True

    def _detect_soft_block(self, response_text: str, status_code: int) -> Optional[str]:
        """Detect soft block from response content and status code"""
        # 403/451 may indicate geo-blocking
        if status_code in [403, 451]:
            return "geo_blocked"

        # Check response content for patterns
        if response_text:
            text_lower = response_text.lower()
            for block_type, patterns in self.SOFT_BLOCK_INDICATORS.items():
                for pattern in patterns:
                    if pattern in text_lower:
                        return block_type

        return None

    async def _check_domain_availability(
        self, domain: Dict[str, Any], settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check single domain availability with soft-block detection"""
        domain_name = domain.get("domain_name", "")
        if not domain_name:
            return {"status": "error", "alert_sent": False}

        url = f"https://{domain_name}"
        previous_status = domain.get(
            "last_ping_status", domain.get("ping_status", "unknown")
        )

        timeout = settings.get("timeout_seconds", 15)
        follow_redirects = settings.get("follow_redirects", True)
        alert_on_down = settings.get("alert_on_down", True)
        alert_on_recovery = settings.get("alert_on_recovery", False)

        new_status = "down"
        new_http_code = None
        error_message = None
        soft_block_type = None
        response_text = ""

        try:
            async with httpx.AsyncClient(
                follow_redirects=follow_redirects, timeout=timeout
            ) as client:
                response = await client.get(url)
                new_http_code = response.status_code

                # Get partial response text for soft-block detection (max 5KB)
                try:
                    response_text = response.text[:5000] if response.text else ""
                except Exception:
                    response_text = ""

                if 200 <= response.status_code < 400:
                    # Check for soft-block even on 200
                    soft_block_type = self._detect_soft_block(
                        response_text, response.status_code
                    )
                    if soft_block_type:
                        new_status = "soft_blocked"
                        error_message = (
                            f"Soft Blocked: {soft_block_type.replace('_', ' ').title()}"
                        )
                    else:
                        new_status = "up"
                elif response.status_code in [403, 451]:
                    # Check for soft-block
                    soft_block_type = self._detect_soft_block(
                        response_text, response.status_code
                    )
                    if soft_block_type:
                        new_status = "soft_blocked"
                        error_message = f"Soft Blocked: {soft_block_type.replace('_', ' ').title()} (HTTP {response.status_code})"
                    else:
                        new_status = "down"
                        error_message = f"HTTP {response.status_code}"
                elif response.status_code >= 500:
                    new_status = "down"
                    error_message = f"Server Error: HTTP {response.status_code}"
                else:
                    new_status = "down"
                    error_message = f"HTTP {response.status_code}"

        except httpx.TimeoutException:
            new_status = "down"
            error_message = "Connection Timeout"
        except httpx.ConnectError as e:
            new_status = "down"
            if "DNS" in str(e) or "getaddrinfo" in str(e):
                error_message = "DNS Error"
            else:
                error_message = "Connection Failed"
        except Exception as e:
            new_status = "down"
            error_message = str(e)[:100]

        now = datetime.now(timezone.utc)

        # Update domain with new status
        update_data = {
            "last_ping_status": new_status,
            "ping_status": new_status,
            "last_http_code": new_http_code,
            "http_status_code": new_http_code,
            "last_checked_at": now.isoformat(),
            "last_check": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        if soft_block_type:
            update_data["soft_block_type"] = soft_block_type

        await self.db.asset_domains.update_one(
            {"id": domain["id"]}, {"$set": update_data}
        )

        alert_sent = False

        # Helper to send email alerts
        async def send_email_alert(enriched_domain, alert_type, err_msg=None):
            try:
                from services.email_alert_service import get_email_alert_service

                email_service = get_email_alert_service(self.db)

                # Get network_id from SEO context if available
                network_id = None
                seo = enriched_domain.get("seo", {})
                if seo.get("seo_context"):
                    network_id = seo["seo_context"][0].get("network_id")

                await email_service.send_availability_alert(
                    enriched_domain, err_msg or "Unreachable", alert_type, network_id
                )
            except Exception as email_err:
                logger.warning(
                    f"Email alert failed for {enriched_domain.get('domain_name')}: {email_err}"
                )

        # Check for status transitions
        if new_status == "down" and previous_status in [
            "up",
            "unknown",
            "soft_blocked",
        ]:
            # Transition to DOWN - CRITICAL
            if alert_on_down:
                # Check rate limit (max 1 alert/domain/24h)
                if await self._can_send_alert(domain, "down"):
                    enriched = await self._enrich_domain_full(domain)
                    message = self._format_down_alert_seo_aware(
                        enriched, error_message, previous_status
                    )
                    sent = await self.telegram.send_alert(message)
                    if sent:
                        await self._update_alert_timestamp(domain, "down")
                        await self._create_alert_record(
                            enriched, "down", error_message, previous_status
                        )
                        alert_sent = True
                        # Also send email alert
                        await send_email_alert(enriched, "down", error_message)

        elif new_status == "soft_blocked" and previous_status in ["up", "unknown"]:
            # Transition to SOFT_BLOCKED - WARNING (HIGH severity)
            if await self._can_send_alert(domain, "soft_blocked"):
                enriched = await self._enrich_domain_full(domain)
                message = self._format_soft_block_alert_seo_aware(
                    enriched, error_message, soft_block_type
                )
                sent = await self.telegram.send_alert(message)
                if sent:
                    await self._update_alert_timestamp(domain, "soft_blocked")
                    await self._create_alert_record(
                        enriched, "soft_blocked", error_message, previous_status
                    )
                    alert_sent = True
                    # Also send email alert
                    await send_email_alert(enriched, "soft_blocked", error_message)

        elif new_status == "up" and previous_status in ["down", "soft_blocked"]:
            # Recovery
            if alert_on_recovery:
                enriched = await self._enrich_domain_full(domain)
                message = self._format_recovery_alert_seo_aware(
                    enriched, previous_status
                )
                sent = await self.telegram.send_alert(message)
                if sent:
                    await self._create_alert_record(
                        enriched, "recovery", None, previous_status
                    )
                    alert_sent = True

        logger.info(
            f"Checked {domain_name}: {previous_status} → {new_status}, HTTP={new_http_code}"
        )

        return {
            "status": new_status,
            "http_code": new_http_code,
            "alert_sent": alert_sent,
        }

    async def _can_send_alert(self, domain: Dict[str, Any], alert_type: str) -> bool:
        """Check rate limit - max 1 alert/domain/24h per alert type"""
        last_alert_key = f"last_{alert_type}_alert_at"
        last_alert_str = domain.get(last_alert_key)

        if not last_alert_str:
            return True

        try:
            last_alert = datetime.fromisoformat(last_alert_str.replace("Z", "+00:00"))
            hours_since = (
                datetime.now(timezone.utc) - last_alert
            ).total_seconds() / 3600
            return hours_since >= 24
        except (ValueError, TypeError):
            return True

    async def _update_alert_timestamp(self, domain: Dict[str, Any], alert_type: str):
        """Update last alert timestamp for rate limiting"""
        await self.db.asset_domains.update_one(
            {"id": domain["id"]},
            {
                "$set": {
                    f"last_{alert_type}_alert_at": datetime.now(
                        timezone.utc
                    ).isoformat()
                }
            },
        )

    async def _enrich_domain_full(self, domain: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich domain with brand, category, and full SEO context"""
        enriched = {**domain}

        # Brand
        if domain.get("brand_id"):
            brand = await self.db.brands.find_one(
                {"id": domain["brand_id"]}, {"_id": 0, "name": 1}
            )
            enriched["brand_name"] = brand["name"] if brand else "Unknown"
        else:
            enriched["brand_name"] = "N/A"

        # Category
        if domain.get("category_id"):
            category = await self.db.categories.find_one(
                {"id": domain["category_id"]}, {"_id": 0, "name": 1}
            )
            enriched["category_name"] = category["name"] if category else "N/A"
        else:
            enriched["category_name"] = "N/A"

        # Timezone
        tz_str, tz_label = await get_system_timezone(self.db)
        enriched["_timezone_str"] = tz_str
        enriched["_timezone_label"] = tz_label

        # SEO context enrichment
        seo_context = await self.seo_enricher.enrich_domain_with_seo_context(
            domain.get("domain_name", ""), domain.get("id")
        )
        enriched["seo"] = seo_context

        return enriched

    def _format_down_alert_seo_aware(
        self, domain: Dict[str, Any], error_message: str, previous_status: str, is_test: bool = False
    ) -> str:
        """Format SEO-aware DOWN alert for Telegram with full context"""
        seo = domain.get("seo", {})
        impact_score = seo.get("impact_score", {})
        severity = impact_score.get("severity", "LOW")

        # DOWN is always at least HIGH severity
        if severity == "LOW":
            severity = "MEDIUM"
        elif severity == "MEDIUM":
            severity = "HIGH"
        elif severity in ["HIGH", "CRITICAL"]:
            severity = "CRITICAL"

        severity_emoji = {
            "CRITICAL": "🔴",
            "HIGH": "🟠",
            "MEDIUM": "🟡",
            "LOW": "🔵",
        }.get(severity, "⚪")

        # Timezone
        tz_str = domain.get("_timezone_str", "Asia/Jakarta")
        tz_label = domain.get("_timezone_label", "GMT+7")
        local_time = format_now_local(tz_str, tz_label)

        test_marker = "🧪 <b>TEST MODE</b> - " if is_test else ""
        
        lines = [
            f"{test_marker}{severity_emoji} <b>DOMAIN DOWN ALERT</b>",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━",
            "🚨 <b>INCIDENT INFO</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"• <b>Domain:</b> <code>{domain.get('domain_name', 'Unknown')}</code>",
            f"• <b>Brand:</b> {domain.get('brand_name', 'N/A')}",
            f"• <b>Issue:</b> {error_message or 'Unreachable'}",
            f"• <b>Previous Status:</b> {previous_status.upper() if previous_status else 'Unknown'}",
            f"• <b>Severity:</b> {severity}",
        ]

        # SEO Context section
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🧩 <b>SEO CONTEXT</b>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        
        if seo.get("used_in_seo"):
            for ctx in seo.get("seo_context", [])[:3]:
                lines.append(f"• <b>Network:</b> {ctx.get('network_name', 'N/A')}")
                lines.append(f"• <b>Role:</b> {ctx.get('role', 'N/A')}")
                lines.append(f"• <b>Tier:</b> {ctx.get('tier_label', 'N/A')}")
                lines.append(f"• <b>Status:</b> {ctx.get('domain_status', 'N/A').replace('_', ' ').title()}")

            # Structure - use full network structure formatted by tiers
            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("🔗 <b>FULL SEO STRUCTURE</b>")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            
            # Use pre-fetched full structure if available
            full_structure_lines = seo.get("full_structure_lines", [])
            if full_structure_lines:
                for line in full_structure_lines:
                    lines.append(line)
            else:
                # Fallback to old chain display
                chain = seo.get("upstream_chain", [])
                if chain:
                    first_ctx = seo.get("seo_context", [{}])[0]
                    status_label = first_ctx.get("domain_status", "").replace("_", " ").title()
                    lines.append(f"⚠️ {domain.get('domain_name', 'Unknown')} [{status_label}] ← DOWN")
                    
                    for hop in chain:
                        target = hop.get("target", hop.get("node", ""))
                        relation = hop.get("target_relation", hop.get("relation", ""))
                        
                        if hop.get("is_end") or hop.get("relation") == "main":
                            lines.append(f"   → 💰 {hop.get('node', target)} [{relation}]")
                            lines.append("   → END: 💰 MONEY SITE")
                            break
                        else:
                            lines.append(f"   → {target} [{relation}]")
                else:
                    first_ctx = seo.get("seo_context", [{}])[0] if seo.get("seo_context") else {}
                    if first_ctx.get("role") == "main":
                        lines.append(f"💰 {domain.get('domain_name', 'Unknown')} [Primary] ← DOWN")
                        lines.append("   → END: ⚠️ THIS IS THE MONEY SITE!")
                    else:
                        lines.append(f"⚠️ {domain.get('domain_name', 'Unknown')} ← DOWN")
                        lines.append("   → END: ⚠️ ORPHAN NODE (no target)")

            # Downstream Impact
            downstream = seo.get("downstream_impact", [])
            if downstream:
                lines.append("")
                lines.append("━━━━━━━━━━━━━━━━━━━━━━")
                lines.append("📌 <b>DOWNSTREAM IMPACT</b>")
                lines.append("━━━━━━━━━━━━━━━━━━━━━━")
                lines.append(f"<b>{len(downstream)}</b> nodes affected by this outage:")
                for d in downstream[:5]:
                    lines.append(f"  • {d['node']} [{d.get('relation', '')}]")
                if len(downstream) > 5:
                    lines.append(f"  ... +{len(downstream) - 5} more")

            # Impact Score
            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("🔥 <b>SEO IMPACT</b>")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"• <b>Severity:</b> {impact_score.get('severity', 'LOW')}")
            lines.append(f"• <b>Networks Affected:</b> {impact_score.get('networks_affected', 0)}")
            lines.append(f"• <b>Downstream Nodes:</b> {impact_score.get('downstream_nodes_count', 0)}")
            lines.append(f"• <b>Reaches Money Site:</b> {'✅ YES' if impact_score.get('reaches_money_site') else '❌ NO'}")
        else:
            lines.append("<i>Domain not used in any SEO Network</i>")
            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("🔥 <b>SEO IMPACT</b>")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("• <b>Severity:</b> LOW")
            lines.append("• <b>Networks Affected:</b> 0")

        # Footer
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"🕐 <b>Detected:</b> {local_time}")
        lines.append("")
        lines.append("🚨 <b>URGENT:</b>")
        lines.append("<i>Investigate and restore domain immediately!</i>")
        
        if is_test:
            lines.append("")
            lines.append("<i>⚠️ This is a TEST alert</i>")

        return "\n".join(lines)

    def _format_soft_block_alert_seo_aware(
        self, domain: Dict[str, Any], error_message: str, block_type: str
    ) -> str:
        """Format SEO-aware SOFT BLOCK alert (WARNING level)"""
        seo = domain.get("seo", {})

        # Soft blocks are warnings, not critical - severity_emoji is 🟡
        severity_emoji = "🟡"

        # Timezone
        tz_str = domain.get("_timezone_str", "Asia/Jakarta")
        tz_label = domain.get("_timezone_label", "GMT+7")
        local_time = format_now_local(tz_str, tz_label)

        block_descriptions = {
            "cloudflare_challenge": "Cloudflare JS Challenge",
            "captcha": "Captcha/Bot Protection",
            "geo_blocked": "Geographic/Access Restriction",
            "bot_protection": "Bot Protection Active",
        }

        lines = [
            f"{severity_emoji} <b>DOMAIN MONITORING ALERT</b>",
            "",
            f"<b>Domain:</b> <code>{domain.get('domain_name', 'Unknown')}</code>",
            f"<b>Brand:</b> {domain.get('brand_name', 'N/A')}",
            f"<b>Issue:</b> Soft Blocked - {block_descriptions.get(block_type, block_type)}",
            f"<b>Checked At:</b> {local_time}",
            "",
            "⚠️ <i>This is a WARNING. The domain may still be accessible to real users.</i>",
        ]

        # SEO Context
        lines.extend(self._format_seo_context_section(seo))

        return "\n".join(lines)

    def _format_recovery_alert_seo_aware(
        self, domain: Dict[str, Any], previous_status: str
    ) -> str:
        """Format recovery alert"""
        # Timezone
        tz_str = domain.get("_timezone_str", "Asia/Jakarta")
        tz_label = domain.get("_timezone_label", "GMT+7")
        local_time = format_now_local(tz_str, tz_label)

        return f"""✅ <b>DOMAIN RECOVERED</b>

<b>Domain:</b> <code>{domain.get('domain_name', 'Unknown')}</code>
<b>Brand:</b> {domain.get('brand_name', 'N/A')}

<b>Status:</b> {previous_status.upper()} → <b>UP</b>
<b>HTTP Code:</b> {domain.get('last_http_code', 'N/A')}

<b>Recovered:</b> {local_time}"""

    def _format_seo_context_section(self, seo: Dict[str, Any]) -> List[str]:
        """Format SEO context section for Telegram message"""
        lines = []
        impact_score = seo.get("impact_score", {})

        if seo.get("used_in_seo"):
            lines.append("")
            lines.append("🧩 <b>SEO CONTEXT</b>")

            for ctx in seo.get("seo_context", [])[:3]:
                lines.append(f"<b>Network:</b> {ctx.get('network_name', 'N/A')}")
                lines.append(f"<b>Node:</b> {ctx.get('node', 'N/A')}")
                lines.append(f"<b>Role:</b> {ctx.get('role', 'N/A')}")
                lines.append(f"<b>Tier:</b> {ctx.get('tier_label', 'N/A')}")
                lines.append(
                    f"<b>Status:</b> {ctx.get('domain_status', 'N/A').replace('_', ' ').title()}"
                )
                if ctx.get("target_node"):
                    lines.append(f"<b>Target:</b> {ctx.get('target_node')}")
                lines.append("")

            if seo.get("additional_networks_count", 0) > 0:
                lines.append(
                    f"<i>Used in +{seo['additional_networks_count']} other networks (see UI)</i>"
                )
                lines.append("")

            # Structure Chain
            chain = seo.get("upstream_chain", [])
            if chain:
                lines.append("🧭 <b>SEO STRUCTURE CHAIN (To Final Target)</b>")
                for i, hop in enumerate(chain, 1):
                    if hop.get("is_end"):
                        lines.append(f"{i}) {hop['node']} [{hop['relation']}]")
                        lines.append(f"END: {hop.get('end_reason', 'Reached')}")
                    else:
                        lines.append(
                            f"{i}) {hop['node']} [{hop['relation']}] → {hop['target']} [{hop.get('target_relation', '')}]"
                        )
                lines.append("")

            # Downstream Impact
            downstream = seo.get("downstream_impact", [])
            if downstream:
                lines.append("📌 <b>DOWNSTREAM IMPACT (Direct Children)</b>")
                for d in downstream[:5]:
                    lines.append(f"• {d['node']} [{d['relation']}] → {d['target']}")
                if len(downstream) > 5:
                    lines.append(f"(+{len(downstream) - 5} more...)")
                lines.append("")

            # Impact Score
            lines.append("🔥 <b>IMPACT SCORE</b>")
            lines.append(f"• <b>Severity:</b> {impact_score.get('severity', 'LOW')}")
            lines.append(
                f"• <b>Networks Affected:</b> {impact_score.get('networks_affected', 0)}"
            )
            lines.append(
                f"• <b>Downstream Nodes:</b> {impact_score.get('downstream_nodes_count', 0)}"
            )
            lines.append(
                f"• <b>Reaches Money Site:</b> {'YES' if impact_score.get('reaches_money_site') else 'NO'}"
            )
            if impact_score.get("highest_tier_impacted") is not None:
                lines.append(
                    f"• <b>Highest Tier:</b> Tier {impact_score.get('highest_tier_impacted')}"
                )
        else:
            lines.append("")
            lines.append("🧩 <b>SEO CONTEXT</b>")
            lines.append("<i>Not used in any SEO Network</i>")

        return lines

    async def _create_alert_record(
        self,
        domain: Dict[str, Any],
        alert_type: str,
        error_message: Optional[str],
        previous_status: str,
    ):
        """Create alert record in database"""
        import uuid

        seo = domain.get("seo", {})
        impact_score = seo.get("impact_score", {})
        severity = impact_score.get("severity", "low").lower()

        if alert_type == "down":
            if severity in ["low", "medium"]:
                severity = "high"
        elif alert_type == "soft_blocked":
            severity = "medium"
        elif alert_type == "recovery":
            severity = "low"

        title_map = {
            "down": "Domain Down",
            "soft_blocked": "Domain Soft Blocked",
            "recovery": "Domain Recovered",
        }

        alert = {
            "id": str(uuid.uuid4()),
            "domain_id": domain["id"],
            "domain_name": domain.get("domain_name", "Unknown"),
            "brand_name": domain.get("brand_name"),
            "category_name": domain.get("category_name"),
            "alert_type": "monitoring",
            "severity": severity,
            "title": title_map.get(alert_type, "Domain Alert"),
            "message": f"Domain {domain['domain_name']} is {alert_type}",
            "details": {
                "previous_status": previous_status,
                "new_status": alert_type,
                "error_message": error_message,
                "http_code": domain.get("last_http_code"),
                "seo_context": seo,
            },
            "acknowledged": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await self.db.alerts.insert_one(alert)


# ==================== UNIFIED MONITORING SCHEDULER ====================


class MonitoringScheduler:
    """
    Unified scheduler that runs both monitoring engines independently
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.expiration_service = ExpirationMonitoringService(db)
        self.availability_service = AvailabilityMonitoringService(db)
        self.settings_service = MonitoringSettingsService(db)
        self._running = False

    async def start(self):
        """Start both monitoring loops"""
        self._running = True
        logger.info("Starting monitoring scheduler...")

        # Run both engines as independent tasks
        await asyncio.gather(self._run_expiration_loop(), self._run_availability_loop())

    async def stop(self):
        """Stop monitoring loops"""
        self._running = False
        logger.info("Stopping monitoring scheduler...")

    async def _run_expiration_loop(self):
        """Run expiration monitoring daily"""
        logger.info("Starting expiration monitoring loop (daily)")

        while self._running:
            try:
                await self.expiration_service.check_all_domains()
            except Exception as e:
                logger.error(f"Expiration monitoring error: {e}")

            # Run daily (every 24 hours)
            # But check more frequently in case of restart
            await asyncio.sleep(3600)  # Check every hour, but service tracks last alert

    async def _run_availability_loop(self):
        """Run availability monitoring at configured interval"""
        logger.info("Starting availability monitoring loop")

        while self._running:
            try:
                await self.availability_service.check_all_domains()
            except Exception as e:
                logger.error(f"Availability monitoring error: {e}")

            # Get configured interval
            settings = await self.settings_service.get_settings()
            interval = settings.get("availability", {}).get(
                "default_interval_seconds", 300
            )

            await asyncio.sleep(interval)


# ==================== INITIALIZATION ====================


def init_monitoring_services(db: AsyncIOMotorDatabase) -> tuple:
    """Initialize all monitoring services"""
    expiration_service = ExpirationMonitoringService(db)
    availability_service = AvailabilityMonitoringService(db)
    settings_service = MonitoringSettingsService(db)
    scheduler = MonitoringScheduler(db)

    return expiration_service, availability_service, settings_service, scheduler
