"""
Weekly Digest Email Service for Domain Monitoring
==================================================

Sends a weekly summary email to global admins with:
- Domains expiring in next 30 days (grouped by urgency)
- Currently down domains
- Soft-blocked domains
- SEO impact summary per issue

Schedule: Weekly (default Monday 9:00 AM), configurable
Recipients: Global admin emails only
"""

import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Check if resend is available
try:
    import resend

    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("Resend package not installed. Digest emails disabled.")


class WeeklyDigestService:
    """
    Weekly digest email service for domain health overview.
    Sends to global admins only.
    """

    # Day name to number mapping (for APScheduler)
    DAY_MAP = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._initialized = False
        self._api_key = None
        self._sender_email = None

    async def _init_resend(self) -> bool:
        """Initialize Resend SDK with API key"""
        if not RESEND_AVAILABLE:
            logger.warning("Resend package not available")
            return False

        # Get email alert settings (shared with email_alert_service)
        settings = await self.db.settings.find_one({"key": "email_alerts"}, {"_id": 0})

        if not settings:
            logger.warning("Email alert settings not configured")
            return False

        api_key = settings.get("resend_api_key")
        sender_email = settings.get("sender_email", "onboarding@resend.dev")

        if not api_key:
            logger.warning("Resend API key not configured")
            return False

        resend.api_key = api_key
        self._api_key = api_key
        self._sender_email = sender_email
        self._initialized = True
        return True

    async def get_digest_settings(self) -> Dict[str, Any]:
        """Get weekly digest configuration"""
        settings = await self.db.settings.find_one({"key": "weekly_digest"}, {"_id": 0})

        if not settings:
            return {
                "enabled": False,
                "schedule_day": "monday",
                "schedule_hour": 9,
                "schedule_minute": 0,
                "last_sent_at": None,
                "include_expiring_domains": True,
                "include_down_domains": True,
                "include_soft_blocked": True,
                "expiring_days_threshold": 30,
            }

        return {
            "enabled": settings.get("enabled", False),
            "schedule_day": settings.get("schedule_day", "monday"),
            "schedule_hour": settings.get("schedule_hour", 9),
            "schedule_minute": settings.get("schedule_minute", 0),
            "last_sent_at": settings.get("last_sent_at"),
            "include_expiring_domains": settings.get("include_expiring_domains", True),
            "include_down_domains": settings.get("include_down_domains", True),
            "include_soft_blocked": settings.get("include_soft_blocked", True),
            "expiring_days_threshold": settings.get("expiring_days_threshold", 30),
        }

    async def update_digest_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update weekly digest configuration"""
        current = await self.get_digest_settings()

        # Validate schedule_day
        if "schedule_day" in updates:
            day = updates["schedule_day"].lower()
            if day not in self.DAY_MAP:
                raise ValueError(f"Invalid schedule_day: {day}")
            updates["schedule_day"] = day

        # Validate hour/minute
        if "schedule_hour" in updates:
            hour = int(updates["schedule_hour"])
            if not 0 <= hour <= 23:
                raise ValueError("schedule_hour must be 0-23")
            updates["schedule_hour"] = hour

        if "schedule_minute" in updates:
            minute = int(updates["schedule_minute"])
            if not 0 <= minute <= 59:
                raise ValueError("schedule_minute must be 0-59")
            updates["schedule_minute"] = minute

        # Merge updates
        for key, value in updates.items():
            if key in current:
                current[key] = value

        current["updated_at"] = datetime.now(timezone.utc).isoformat()

        await self.db.settings.update_one(
            {"key": "weekly_digest"},
            {"$set": {**current, "key": "weekly_digest"}},
            upsert=True,
        )

        return await self.get_digest_settings()

    async def _get_global_admin_emails(self) -> List[str]:
        """Get global admin emails from email alert settings"""
        settings = await self.db.settings.find_one({"key": "email_alerts"}, {"_id": 0})

        if not settings:
            return []

        emails = settings.get("global_admin_emails", [])
        return [e.strip().lower() for e in emails if e and "@" in e]

    async def _collect_expiring_domains(
        self, days_threshold: int = 30
    ) -> Dict[str, List[Dict]]:
        """
        Collect domains expiring within threshold days.
        Groups by urgency: critical (≤7 days), high (8-14 days), medium (15-30 days)
        """
        now = datetime.now(timezone.utc)
        threshold_date = (now + timedelta(days=days_threshold)).isoformat()

        domains = await self.db.asset_domains.find(
            {
                "expiration_date": {"$ne": None, "$lte": threshold_date},
                "$or": [{"auto_renew": False}, {"auto_renew": {"$exists": False}}],
            },
            {"_id": 0},
        ).to_list(1000)

        # Group by urgency
        critical = []  # ≤7 days or expired
        high = []  # 8-14 days
        medium = []  # 15-30 days

        for domain in domains:
            exp_str = domain.get("expiration_date")
            if not exp_str:
                continue

            try:
                exp_date = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                days_remaining = (exp_date.date() - now.date()).days

                # Enrich with brand name
                if domain.get("brand_id"):
                    brand = await self.db.brands.find_one(
                        {"id": domain["brand_id"]}, {"_id": 0, "name": 1}
                    )
                    domain["brand_name"] = brand["name"] if brand else "Unknown"
                else:
                    domain["brand_name"] = "N/A"

                domain["days_remaining"] = days_remaining

                # Get SEO context
                seo_usage = await self._get_domain_seo_usage(domain["id"])
                domain["seo_networks_count"] = seo_usage.get("networks_count", 0)
                domain["highest_tier"] = seo_usage.get("highest_tier")

                if days_remaining <= 7:
                    critical.append(domain)
                elif days_remaining <= 14:
                    high.append(domain)
                else:
                    medium.append(domain)

            except (ValueError, TypeError):
                continue

        # Sort each group by days_remaining
        critical.sort(key=lambda x: x.get("days_remaining", 999))
        high.sort(key=lambda x: x.get("days_remaining", 999))
        medium.sort(key=lambda x: x.get("days_remaining", 999))

        return {
            "critical": critical,
            "high": high,
            "medium": medium,
            "total": len(critical) + len(high) + len(medium),
        }

    async def _collect_down_domains(self) -> List[Dict]:
        """Collect currently down domains"""
        domains = await self.db.asset_domains.find(
            {"monitoring_enabled": True, "ping_status": "down"}, {"_id": 0}
        ).to_list(500)

        result = []
        for domain in domains:
            # Enrich with brand name
            if domain.get("brand_id"):
                brand = await self.db.brands.find_one(
                    {"id": domain["brand_id"]}, {"_id": 0, "name": 1}
                )
                domain["brand_name"] = brand["name"] if brand else "Unknown"
            else:
                domain["brand_name"] = "N/A"

            # Get SEO context
            seo_usage = await self._get_domain_seo_usage(domain["id"])
            domain["seo_networks_count"] = seo_usage.get("networks_count", 0)
            domain["highest_tier"] = seo_usage.get("highest_tier")

            # Get last check time
            domain["last_checked"] = domain.get("last_checked_at") or domain.get(
                "last_check"
            )

            result.append(domain)

        return result

    async def _collect_soft_blocked_domains(self) -> List[Dict]:
        """Collect currently soft-blocked domains"""
        domains = await self.db.asset_domains.find(
            {"monitoring_enabled": True, "ping_status": "soft_blocked"}, {"_id": 0}
        ).to_list(500)

        result = []
        for domain in domains:
            # Enrich with brand name
            if domain.get("brand_id"):
                brand = await self.db.brands.find_one(
                    {"id": domain["brand_id"]}, {"_id": 0, "name": 1}
                )
                domain["brand_name"] = brand["name"] if brand else "Unknown"
            else:
                domain["brand_name"] = "N/A"

            # Get SEO context
            seo_usage = await self._get_domain_seo_usage(domain["id"])
            domain["seo_networks_count"] = seo_usage.get("networks_count", 0)
            domain["highest_tier"] = seo_usage.get("highest_tier")

            # Get block type
            domain["block_type"] = domain.get("soft_block_type", "unknown")

            result.append(domain)

        return result

    async def _get_domain_seo_usage(self, domain_id: str) -> Dict[str, Any]:
        """Get SEO network usage summary for a domain"""
        entries = await self.db.seo_structure_entries.find(
            {"asset_domain_id": domain_id},
            {"_id": 0, "network_id": 1, "domain_role": 1},
        ).to_list(100)

        if not entries:
            return {"networks_count": 0, "highest_tier": None}

        network_ids = list(set(e["network_id"] for e in entries))

        # Check if any entry is a main node (highest importance)
        has_main = any(e.get("domain_role") == "main" for e in entries)

        return {
            "networks_count": len(network_ids),
            "highest_tier": "Main/LP" if has_main else "Supporting",
            "is_main_node": has_main,
        }

    def _format_digest_email(self, data: Dict[str, Any]) -> tuple:
        """Format weekly digest email (subject, html_content)"""
        now = datetime.now(timezone.utc)
        week_start = (now - timedelta(days=now.weekday())).strftime("%b %d")
        week_end = now.strftime("%b %d, %Y")

        expiring = data.get("expiring_domains", {})
        down_domains = data.get("down_domains", [])
        soft_blocked = data.get("soft_blocked_domains", [])

        total_issues = expiring.get("total", 0) + len(down_domains) + len(soft_blocked)

        # Determine overall health status
        if expiring.get("critical") or down_domains:
            health_status = "Needs Attention"
            health_color = "#dc2626"
            health_emoji = "🔴"
        elif expiring.get("high") or soft_blocked:
            health_status = "Warning"
            health_color = "#f59e0b"
            health_emoji = "🟡"
        elif total_issues > 0:
            health_status = "Minor Issues"
            health_color = "#3b82f6"
            health_emoji = "🔵"
        else:
            health_status = "All Clear"
            health_color = "#22c55e"
            health_emoji = "✅"

        subject = (
            f"[SEO-NOC] Weekly Domain Health Digest - {health_emoji} {health_status}"
        )

        # Build sections
        sections = []

        # Executive Summary
        summary_html = f"""
        <div style="background: #1a1a1a; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
            <h3 style="color: #ffffff; margin: 0 0 12px 0;">Executive Summary</h3>
            <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                <div style="text-align: center; padding: 12px 20px; background: #262626; border-radius: 6px;">
                    <div style="font-size: 24px; font-weight: bold; color: {health_color};">{total_issues}</div>
                    <div style="font-size: 12px; color: #9ca3af;">Total Issues</div>
                </div>
                <div style="text-align: center; padding: 12px 20px; background: #262626; border-radius: 6px;">
                    <div style="font-size: 24px; font-weight: bold; color: #ef4444;">{len(expiring.get('critical', []))}</div>
                    <div style="font-size: 12px; color: #9ca3af;">Critical Expiring</div>
                </div>
                <div style="text-align: center; padding: 12px 20px; background: #262626; border-radius: 6px;">
                    <div style="font-size: 24px; font-weight: bold; color: #ef4444;">{len(down_domains)}</div>
                    <div style="font-size: 12px; color: #9ca3af;">Down</div>
                </div>
                <div style="text-align: center; padding: 12px 20px; background: #262626; border-radius: 6px;">
                    <div style="font-size: 24px; font-weight: bold; color: #f59e0b;">{len(soft_blocked)}</div>
                    <div style="font-size: 12px; color: #9ca3af;">Soft Blocked</div>
                </div>
            </div>
        </div>
        """
        sections.append(summary_html)

        # Expiring Domains Section
        if expiring.get("total", 0) > 0:
            exp_rows = ""

            # Critical (≤7 days)
            if expiring.get("critical"):
                exp_rows += '<tr><td colspan="5" style="padding: 8px; background: #3f1d1d; color: #fca5a5; font-weight: bold;">🔴 CRITICAL (≤7 days)</td></tr>'
                for d in expiring["critical"][:10]:
                    seo_badge = (
                        f'<span style="background: #1e3a5f; color: #60a5fa; padding: 2px 6px; border-radius: 3px; font-size: 10px;">{d.get("seo_networks_count", 0)} networks</span>'
                        if d.get("seo_networks_count", 0) > 0
                        else '<span style="color: #6b7280; font-size: 10px;">No SEO</span>'
                    )
                    days_text = (
                        f'{d.get("days_remaining")} days'
                        if d.get("days_remaining", 0) >= 0
                        else f'EXPIRED {abs(d.get("days_remaining", 0))}d ago'
                    )
                    exp_rows += f"""
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #333; font-family: monospace;">{d.get("domain_name", "N/A")}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #333;">{d.get("brand_name", "N/A")}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #333; color: #ef4444; font-weight: bold;">{days_text}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #333;">{seo_badge}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #333; color: #6b7280;">{d.get("registrar_name", "N/A")}</td>
                    </tr>
                    """

            # High (8-14 days)
            if expiring.get("high"):
                exp_rows += '<tr><td colspan="5" style="padding: 8px; background: #3d2e1a; color: #fcd34d; font-weight: bold;">🟠 HIGH (8-14 days)</td></tr>'
                for d in expiring["high"][:10]:
                    seo_badge = (
                        f'<span style="background: #1e3a5f; color: #60a5fa; padding: 2px 6px; border-radius: 3px; font-size: 10px;">{d.get("seo_networks_count", 0)} networks</span>'
                        if d.get("seo_networks_count", 0) > 0
                        else '<span style="color: #6b7280; font-size: 10px;">No SEO</span>'
                    )
                    exp_rows += f"""
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #333; font-family: monospace;">{d.get("domain_name", "N/A")}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #333;">{d.get("brand_name", "N/A")}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #333; color: #f59e0b;">{d.get("days_remaining")} days</td>
                        <td style="padding: 8px; border-bottom: 1px solid #333;">{seo_badge}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #333; color: #6b7280;">{d.get("registrar_name", "N/A")}</td>
                    </tr>
                    """

            # Medium (15-30 days)
            if expiring.get("medium"):
                exp_rows += '<tr><td colspan="5" style="padding: 8px; background: #1e3a5f; color: #93c5fd; font-weight: bold;">🔵 MEDIUM (15-30 days)</td></tr>'
                for d in expiring["medium"][:10]:
                    seo_badge = (
                        f'<span style="background: #1e3a5f; color: #60a5fa; padding: 2px 6px; border-radius: 3px; font-size: 10px;">{d.get("seo_networks_count", 0)} networks</span>'
                        if d.get("seo_networks_count", 0) > 0
                        else '<span style="color: #6b7280; font-size: 10px;">No SEO</span>'
                    )
                    exp_rows += f"""
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #333; font-family: monospace;">{d.get("domain_name", "N/A")}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #333;">{d.get("brand_name", "N/A")}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #333; color: #3b82f6;">{d.get("days_remaining")} days</td>
                        <td style="padding: 8px; border-bottom: 1px solid #333;">{seo_badge}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #333; color: #6b7280;">{d.get("registrar_name", "N/A")}</td>
                    </tr>
                    """

            expiring_html = f"""
            <div style="margin-bottom: 20px;">
                <h3 style="color: #ffffff; margin: 0 0 12px 0;">📅 Expiring Domains ({expiring.get('total', 0)})</h3>
                <table style="width: 100%; border-collapse: collapse; background: #171717; border-radius: 6px; overflow: hidden;">
                    <tr style="background: #262626;">
                        <th style="padding: 10px; text-align: left; color: #9ca3af; font-size: 12px;">Domain</th>
                        <th style="padding: 10px; text-align: left; color: #9ca3af; font-size: 12px;">Brand</th>
                        <th style="padding: 10px; text-align: left; color: #9ca3af; font-size: 12px;">Expires</th>
                        <th style="padding: 10px; text-align: left; color: #9ca3af; font-size: 12px;">SEO Impact</th>
                        <th style="padding: 10px; text-align: left; color: #9ca3af; font-size: 12px;">Registrar</th>
                    </tr>
                    {exp_rows}
                </table>
            </div>
            """
            sections.append(expiring_html)

        # Down Domains Section
        if down_domains:
            down_rows = ""
            for d in down_domains[:15]:
                seo_badge = (
                    f'<span style="background: #1e3a5f; color: #60a5fa; padding: 2px 6px; border-radius: 3px; font-size: 10px;">{d.get("seo_networks_count", 0)} networks</span>'
                    if d.get("seo_networks_count", 0) > 0
                    else '<span style="color: #6b7280; font-size: 10px;">No SEO</span>'
                )
                down_rows += f"""
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #333; font-family: monospace;">{d.get("domain_name", "N/A")}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #333;">{d.get("brand_name", "N/A")}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #333; color: #ef4444;">DOWN</td>
                    <td style="padding: 8px; border-bottom: 1px solid #333;">{seo_badge}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #333; color: #6b7280;">{d.get("last_http_code", "N/A")}</td>
                </tr>
                """

            down_html = f"""
            <div style="margin-bottom: 20px;">
                <h3 style="color: #ffffff; margin: 0 0 12px 0;">🔴 Down Domains ({len(down_domains)})</h3>
                <table style="width: 100%; border-collapse: collapse; background: #171717; border-radius: 6px; overflow: hidden;">
                    <tr style="background: #262626;">
                        <th style="padding: 10px; text-align: left; color: #9ca3af; font-size: 12px;">Domain</th>
                        <th style="padding: 10px; text-align: left; color: #9ca3af; font-size: 12px;">Brand</th>
                        <th style="padding: 10px; text-align: left; color: #9ca3af; font-size: 12px;">Status</th>
                        <th style="padding: 10px; text-align: left; color: #9ca3af; font-size: 12px;">SEO Impact</th>
                        <th style="padding: 10px; text-align: left; color: #9ca3af; font-size: 12px;">HTTP Code</th>
                    </tr>
                    {down_rows}
                </table>
            </div>
            """
            sections.append(down_html)

        # Soft Blocked Section
        if soft_blocked:
            blocked_rows = ""
            block_type_labels = {
                "cloudflare_challenge": "Cloudflare",
                "captcha": "Captcha",
                "geo_blocked": "Geo-Block",
                "bot_protection": "Bot Protection",
            }
            for d in soft_blocked[:15]:
                seo_badge = (
                    f'<span style="background: #1e3a5f; color: #60a5fa; padding: 2px 6px; border-radius: 3px; font-size: 10px;">{d.get("seo_networks_count", 0)} networks</span>'
                    if d.get("seo_networks_count", 0) > 0
                    else '<span style="color: #6b7280; font-size: 10px;">No SEO</span>'
                )
                block_label = block_type_labels.get(
                    d.get("block_type", ""), d.get("block_type", "Unknown")
                )
                blocked_rows += f"""
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #333; font-family: monospace;">{d.get("domain_name", "N/A")}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #333;">{d.get("brand_name", "N/A")}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #333; color: #f59e0b;">{block_label}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #333;">{seo_badge}</td>
                </tr>
                """

            blocked_html = f"""
            <div style="margin-bottom: 20px;">
                <h3 style="color: #ffffff; margin: 0 0 12px 0;">🟡 Soft Blocked Domains ({len(soft_blocked)})</h3>
                <table style="width: 100%; border-collapse: collapse; background: #171717; border-radius: 6px; overflow: hidden;">
                    <tr style="background: #262626;">
                        <th style="padding: 10px; text-align: left; color: #9ca3af; font-size: 12px;">Domain</th>
                        <th style="padding: 10px; text-align: left; color: #9ca3af; font-size: 12px;">Brand</th>
                        <th style="padding: 10px; text-align: left; color: #9ca3af; font-size: 12px;">Block Type</th>
                        <th style="padding: 10px; text-align: left; color: #9ca3af; font-size: 12px;">SEO Impact</th>
                    </tr>
                    {blocked_rows}
                </table>
            </div>
            """
            sections.append(blocked_html)

        # No issues message
        if total_issues == 0:
            sections.append("""
            <div style="text-align: center; padding: 40px; background: #1a1a1a; border-radius: 8px;">
                <div style="font-size: 48px; margin-bottom: 16px;">✅</div>
                <h3 style="color: #22c55e; margin: 0 0 8px 0;">All Clear!</h3>
                <p style="color: #9ca3af; margin: 0;">No domain health issues detected this week.</p>
            </div>
            """)

        sections_html = "".join(sections)

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0a; color: #e5e5e5; padding: 20px; margin: 0;">
            <div style="max-width: 800px; margin: 0 auto; background: #171717; border-radius: 12px; overflow: hidden; border: 1px solid #262626;">
                <!-- Header -->
                <div style="background: linear-gradient(135deg, #1e3a5f 0%, #312e81 100%); padding: 24px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0 0 8px 0; font-size: 24px;">Weekly Domain Health Digest</h1>
                    <p style="color: #93c5fd; margin: 0; font-size: 14px;">{week_start} - {week_end}</p>
                    <div style="margin-top: 16px; display: inline-block; padding: 8px 16px; background: rgba(0,0,0,0.3); border-radius: 20px;">
                        <span style="color: {health_color}; font-weight: bold;">{health_emoji} {health_status}</span>
                    </div>
                </div>
                
                <!-- Content -->
                <div style="padding: 24px;">
                    {sections_html}
                </div>
                
                <!-- Footer -->
                <div style="background: #0a0a0a; padding: 16px; text-align: center; border-top: 1px solid #262626;">
                    <p style="color: #6b7280; margin: 0; font-size: 12px;">
                        This is an automated weekly digest from SEO-NOC Domain Monitoring.<br>
                        Manage digest settings in Settings → Email Alerts → Weekly Digest
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        return subject, html_content

    async def generate_and_send_digest(self) -> Dict[str, Any]:
        """Generate and send the weekly digest email"""
        settings = await self.get_digest_settings()

        if not settings.get("enabled", False):
            return {"success": False, "error": "Weekly digest is disabled"}

        if not self._initialized:
            if not await self._init_resend():
                return {"success": False, "error": "Email service not configured"}

        recipients = await self._get_global_admin_emails()
        if not recipients:
            return {"success": False, "error": "No global admin emails configured"}

        # Collect data
        data = {}

        if settings.get("include_expiring_domains", True):
            threshold = settings.get("expiring_days_threshold", 30)
            data["expiring_domains"] = await self._collect_expiring_domains(threshold)

        if settings.get("include_down_domains", True):
            data["down_domains"] = await self._collect_down_domains()

        if settings.get("include_soft_blocked", True):
            data["soft_blocked_domains"] = await self._collect_soft_blocked_domains()

        # Format and send
        subject, html_content = self._format_digest_email(data)

        try:
            params = {
                "from": self._sender_email,
                "to": recipients,
                "subject": subject,
                "html": html_content,
            }

            await asyncio.to_thread(resend.Emails.send, params)

            # Update last_sent_at
            await self.db.settings.update_one(
                {"key": "weekly_digest"},
                {"$set": {"last_sent_at": datetime.now(timezone.utc).isoformat()}},
            )

            logger.info(f"Weekly digest sent to {recipients}")
            return {
                "success": True,
                "message": f"Digest sent to {len(recipients)} recipients",
                "recipients": recipients,
                "issues_count": data.get("expiring_domains", {}).get("total", 0)
                + len(data.get("down_domains", []))
                + len(data.get("soft_blocked_domains", [])),
            }

        except Exception as e:
            logger.error(f"Failed to send weekly digest: {e}")
            return {"success": False, "error": str(e)}

    async def preview_digest(self) -> Dict[str, Any]:
        """Generate digest data without sending (for preview)"""
        settings = await self.get_digest_settings()

        data = {}

        if settings.get("include_expiring_domains", True):
            threshold = settings.get("expiring_days_threshold", 30)
            data["expiring_domains"] = await self._collect_expiring_domains(threshold)

        if settings.get("include_down_domains", True):
            data["down_domains"] = await self._collect_down_domains()

        if settings.get("include_soft_blocked", True):
            data["soft_blocked_domains"] = await self._collect_soft_blocked_domains()

        subject, _ = self._format_digest_email(data)

        return {
            "subject": subject,
            "expiring_domains": data.get("expiring_domains", {}),
            "down_domains_count": len(data.get("down_domains", [])),
            "soft_blocked_count": len(data.get("soft_blocked_domains", [])),
            "total_issues": data.get("expiring_domains", {}).get("total", 0)
            + len(data.get("down_domains", []))
            + len(data.get("soft_blocked_domains", [])),
        }


# Singleton instance
_digest_service: Optional[WeeklyDigestService] = None


def get_weekly_digest_service(db: AsyncIOMotorDatabase) -> WeeklyDigestService:
    """Get or create weekly digest service instance"""
    global _digest_service
    if _digest_service is None:
        _digest_service = WeeklyDigestService(db)
    return _digest_service
