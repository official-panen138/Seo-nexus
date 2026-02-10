"""
Email Alert Service for Domain Monitoring
==========================================

Sends email notifications for HIGH/CRITICAL severity domain alerts.
Acts as redundancy layer alongside Telegram notifications.

Recipients:
- Global admin emails (configured in settings)
- Per-network manager emails

Triggers:
- Domain expiration (≤7 days)
- Domain DOWN (availability failures)
- Soft-blocked domains (Cloudflare, captcha)
"""

import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Check if resend is available
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("Resend package not installed. Email alerts disabled.")


class EmailAlertService:
    """
    Email notification service for domain monitoring alerts.
    Only sends for HIGH/CRITICAL severity.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._initialized = False
        self._api_key = None
        self._sender_email = None
    
    async def _init_resend(self) -> bool:
        """Initialize Resend SDK with API key from environment or settings"""
        if not RESEND_AVAILABLE:
            logger.warning("Resend package not available")
            return False
        
        # Try environment variable first
        api_key = os.environ.get("RESEND_API_KEY")
        sender_email = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
        
        # Fallback to database settings
        if not api_key:
            settings = await self.db.settings.find_one({"key": "email_alerts"}, {"_id": 0})
            if settings:
                api_key = settings.get("resend_api_key")
                sender_email = settings.get("sender_email", sender_email)
        
        if not api_key:
            logger.warning("Resend API key not configured")
            return False
        
        resend.api_key = api_key
        self._api_key = api_key
        self._sender_email = sender_email
        self._initialized = True
        return True
    
    async def get_email_settings(self) -> Dict[str, Any]:
        """Get email alert configuration"""
        settings = await self.db.settings.find_one({"key": "email_alerts"}, {"_id": 0})
        
        if not settings:
            return {
                "enabled": False,
                "configured": False,
                "global_admin_emails": [],
                "severity_threshold": "high",
                "include_network_managers": True
            }
        
        return {
            "enabled": settings.get("enabled", False),
            "configured": bool(settings.get("resend_api_key")),
            "global_admin_emails": settings.get("global_admin_emails", []),
            "severity_threshold": settings.get("severity_threshold", "high"),
            "include_network_managers": settings.get("include_network_managers", True),
            "sender_email": settings.get("sender_email", "onboarding@resend.dev")
        }
    
    async def update_email_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update email alert configuration"""
        current = await self.get_email_settings()
        
        # Merge updates
        for key, value in updates.items():
            if key in ["enabled", "resend_api_key", "global_admin_emails", 
                       "severity_threshold", "include_network_managers", "sender_email"]:
                current[key] = value
        
        current["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        await self.db.settings.update_one(
            {"key": "email_alerts"},
            {"$set": {**current, "key": "email_alerts"}},
            upsert=True
        )
        
        # Re-initialize if API key changed
        if "resend_api_key" in updates:
            self._initialized = False
        
        return await self.get_email_settings()
    
    async def _get_recipients(self, network_id: Optional[str] = None) -> List[str]:
        """
        Get email recipients for an alert.
        Combines global admin emails + network manager emails (if enabled).
        """
        settings = await self.get_email_settings()
        recipients = set()
        
        # Add global admin emails
        global_emails = settings.get("global_admin_emails", [])
        for email in global_emails:
            if email and "@" in email:
                recipients.add(email.strip().lower())
        
        # Add network manager emails if enabled and network_id provided
        if settings.get("include_network_managers", True) and network_id:
            network = await self.db.seo_networks.find_one(
                {"id": network_id}, 
                {"_id": 0, "manager_ids": 1}
            )
            if network and network.get("manager_ids"):
                # Get manager emails
                managers = await self.db.users.find(
                    {"id": {"$in": network["manager_ids"]}},
                    {"_id": 0, "email": 1}
                ).to_list(100)
                for manager in managers:
                    if manager.get("email"):
                        recipients.add(manager["email"].strip().lower())
        
        return list(recipients)
    
    def _should_send_email(self, severity: str, settings: Dict[str, Any]) -> bool:
        """Check if email should be sent based on severity threshold"""
        if not settings.get("enabled", False):
            return False
        
        severity_levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        threshold = settings.get("severity_threshold", "high")
        
        alert_level = severity_levels.get(severity.lower(), 0)
        threshold_level = severity_levels.get(threshold.lower(), 3)
        
        return alert_level >= threshold_level
    
    def _format_expiration_email(self, domain: Dict[str, Any], days_remaining: int) -> tuple:
        """Format expiration alert email (subject, html_content)"""
        severity = "CRITICAL" if days_remaining <= 3 else "HIGH"
        domain_name = domain.get("domain_name", "Unknown")
        brand_name = domain.get("brand_name", "N/A")
        
        if days_remaining < 0:
            status = f"EXPIRED ({abs(days_remaining)} days ago)"
        elif days_remaining == 0:
            status = "EXPIRES TODAY"
        else:
            status = f"Expires in {days_remaining} days"
        
        subject = f"[{severity}] Domain Expiration Alert: {domain_name}"
        
        # SEO context
        seo = domain.get("seo", {})
        seo_section = ""
        if seo.get("used_in_seo"):
            contexts = seo.get("seo_context", [])[:3]
            seo_rows = ""
            for ctx in contexts:
                seo_rows += f"""
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #333;">{ctx.get('network_name', 'N/A')}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #333;">{ctx.get('role', 'N/A')}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #333;">{ctx.get('tier_label', 'N/A')}</td>
                </tr>
                """
            
            impact = seo.get("impact_score", {})
            seo_section = f"""
            <div style="margin-top: 20px;">
                <h3 style="color: #f59e0b; margin-bottom: 10px;">SEO Context</h3>
                <table style="width: 100%; border-collapse: collapse; background: #1a1a1a;">
                    <tr style="background: #262626;">
                        <th style="padding: 8px; text-align: left; color: #9ca3af;">Network</th>
                        <th style="padding: 8px; text-align: left; color: #9ca3af;">Role</th>
                        <th style="padding: 8px; text-align: left; color: #9ca3af;">Tier</th>
                    </tr>
                    {seo_rows}
                </table>
                <div style="margin-top: 10px; padding: 10px; background: #1a1a1a; border-radius: 4px;">
                    <strong style="color: #ef4444;">Impact Score:</strong>
                    <span style="color: #fbbf24;">{impact.get('severity', 'N/A')}</span> |
                    Networks: {impact.get('networks_affected', 0)} |
                    Downstream: {impact.get('downstream_nodes_count', 0)} |
                    Reaches Money Site: {'Yes' if impact.get('reaches_money_site') else 'No'}
                </div>
            </div>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0a; color: #e5e5e5; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: #171717; border-radius: 8px; padding: 24px; border: 1px solid #262626;">
                <div style="text-align: center; margin-bottom: 20px;">
                    <span style="background: {'#dc2626' if severity == 'CRITICAL' else '#f59e0b'}; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 12px;">
                        {severity} ALERT
                    </span>
                </div>
                
                <h2 style="color: #ffffff; margin-bottom: 16px; text-align: center;">Domain Expiration Warning</h2>
                
                <table style="width: 100%; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 8px 0; color: #9ca3af;">Domain:</td>
                        <td style="padding: 8px 0; color: #ffffff; font-family: monospace; font-weight: bold;">{domain_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #9ca3af;">Brand:</td>
                        <td style="padding: 8px 0; color: #ffffff;">{brand_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #9ca3af;">Status:</td>
                        <td style="padding: 8px 0; color: {'#ef4444' if days_remaining <= 0 else '#f59e0b'}; font-weight: bold;">{status}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #9ca3af;">Expiration Date:</td>
                        <td style="padding: 8px 0; color: #ffffff;">{domain.get('expiration_date', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #9ca3af;">Registrar:</td>
                        <td style="padding: 8px 0; color: #ffffff;">{domain.get('registrar_name', 'N/A')}</td>
                    </tr>
                </table>
                
                {seo_section}
                
                <div style="margin-top: 24px; padding: 16px; background: #262626; border-radius: 4px; text-align: center;">
                    <p style="color: #9ca3af; margin: 0; font-size: 14px;">
                        This is an automated alert from SEO-NOC Domain Monitoring.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return subject, html_content
    
    def _format_availability_email(self, domain: Dict[str, Any], error_message: str, alert_type: str) -> tuple:
        """Format availability alert email (subject, html_content)"""
        domain_name = domain.get("domain_name", "Unknown")
        brand_name = domain.get("brand_name", "N/A")
        
        if alert_type == "down":
            severity = "CRITICAL"
            status = "DOWN"
            status_color = "#dc2626"
        else:  # soft_blocked
            severity = "HIGH"
            status = "SOFT BLOCKED"
            status_color = "#f59e0b"
        
        subject = f"[{severity}] Domain {status}: {domain_name}"
        
        # SEO context
        seo = domain.get("seo", {})
        seo_section = ""
        if seo.get("used_in_seo"):
            contexts = seo.get("seo_context", [])[:3]
            seo_rows = ""
            for ctx in contexts:
                seo_rows += f"""
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #333;">{ctx.get('network_name', 'N/A')}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #333;">{ctx.get('role', 'N/A')}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #333;">{ctx.get('tier_label', 'N/A')}</td>
                </tr>
                """
            
            impact = seo.get("impact_score", {})
            seo_section = f"""
            <div style="margin-top: 20px;">
                <h3 style="color: #f59e0b; margin-bottom: 10px;">SEO Context</h3>
                <table style="width: 100%; border-collapse: collapse; background: #1a1a1a;">
                    <tr style="background: #262626;">
                        <th style="padding: 8px; text-align: left; color: #9ca3af;">Network</th>
                        <th style="padding: 8px; text-align: left; color: #9ca3af;">Role</th>
                        <th style="padding: 8px; text-align: left; color: #9ca3af;">Tier</th>
                    </tr>
                    {seo_rows}
                </table>
                <div style="margin-top: 10px; padding: 10px; background: #1a1a1a; border-radius: 4px;">
                    <strong style="color: #ef4444;">Impact Score:</strong>
                    <span style="color: #fbbf24;">{impact.get('severity', 'N/A')}</span> |
                    Networks: {impact.get('networks_affected', 0)} |
                    Downstream: {impact.get('downstream_nodes_count', 0)} |
                    Reaches Money Site: {'Yes' if impact.get('reaches_money_site') else 'No'}
                </div>
            </div>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0a; color: #e5e5e5; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: #171717; border-radius: 8px; padding: 24px; border: 1px solid #262626;">
                <div style="text-align: center; margin-bottom: 20px;">
                    <span style="background: {status_color}; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 12px;">
                        {severity} ALERT
                    </span>
                </div>
                
                <h2 style="color: #ffffff; margin-bottom: 16px; text-align: center;">Domain Availability Alert</h2>
                
                <table style="width: 100%; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 8px 0; color: #9ca3af;">Domain:</td>
                        <td style="padding: 8px 0; color: #ffffff; font-family: monospace; font-weight: bold;">{domain_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #9ca3af;">Brand:</td>
                        <td style="padding: 8px 0; color: #ffffff;">{brand_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #9ca3af;">Status:</td>
                        <td style="padding: 8px 0; color: {status_color}; font-weight: bold;">{status}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #9ca3af;">Issue:</td>
                        <td style="padding: 8px 0; color: #ef4444;">{error_message or 'Unreachable'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #9ca3af;">HTTP Code:</td>
                        <td style="padding: 8px 0; color: #ffffff;">{domain.get('last_http_code', 'N/A')}</td>
                    </tr>
                </table>
                
                {seo_section}
                
                <div style="margin-top: 24px; padding: 16px; background: #262626; border-radius: 4px; text-align: center;">
                    <p style="color: #9ca3af; margin: 0; font-size: 14px;">
                        This is an automated alert from SEO-NOC Domain Monitoring.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return subject, html_content
    
    async def send_expiration_alert(
        self, 
        domain: Dict[str, Any], 
        days_remaining: int,
        network_id: Optional[str] = None
    ) -> bool:
        """
        Send email alert for domain expiration.
        Only sends for HIGH/CRITICAL severity (≤7 days).
        """
        settings = await self.get_email_settings()
        
        # Determine severity
        severity = "critical" if days_remaining <= 3 else "high" if days_remaining <= 7 else "medium"
        
        if not self._should_send_email(severity, settings):
            logger.debug(f"Email alert skipped for {domain.get('domain_name')} - severity {severity} below threshold")
            return False
        
        if not self._initialized:
            if not await self._init_resend():
                return False
        
        recipients = await self._get_recipients(network_id)
        if not recipients:
            logger.warning("No email recipients configured for expiration alert")
            return False
        
        subject, html_content = self._format_expiration_email(domain, days_remaining)
        
        return await self._send_email(recipients, subject, html_content)
    
    async def send_availability_alert(
        self,
        domain: Dict[str, Any],
        error_message: str,
        alert_type: str,  # "down" or "soft_blocked"
        network_id: Optional[str] = None
    ) -> bool:
        """
        Send email alert for domain availability issues.
        DOWN = CRITICAL, SOFT_BLOCKED = HIGH
        """
        settings = await self.get_email_settings()
        
        # Determine severity
        severity = "critical" if alert_type == "down" else "high"
        
        if not self._should_send_email(severity, settings):
            logger.debug(f"Email alert skipped for {domain.get('domain_name')} - severity {severity} below threshold")
            return False
        
        if not self._initialized:
            if not await self._init_resend():
                return False
        
        recipients = await self._get_recipients(network_id)
        if not recipients:
            logger.warning("No email recipients configured for availability alert")
            return False
        
        subject, html_content = self._format_availability_email(domain, error_message, alert_type)
        
        return await self._send_email(recipients, subject, html_content)
    
    async def _send_email(self, recipients: List[str], subject: str, html_content: str) -> bool:
        """Send email via Resend API (non-blocking)"""
        if not RESEND_AVAILABLE or not self._initialized:
            return False
        
        try:
            params = {
                "from": self._sender_email,
                "to": recipients,
                "subject": subject,
                "html": html_content
            }
            
            # Run sync SDK in thread to keep FastAPI non-blocking
            await asyncio.to_thread(resend.Emails.send, params)
            
            logger.info(f"Email sent to {recipients}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    async def send_test_email(self, recipient: str) -> Dict[str, Any]:
        """Send a test email to verify configuration"""
        if not self._initialized:
            if not await self._init_resend():
                return {"success": False, "error": "Resend not configured. Add API key first."}
        
        subject = "[TEST] SEO-NOC Email Alert System"
        html_content = """
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0a; color: #e5e5e5; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: #171717; border-radius: 8px; padding: 24px; border: 1px solid #262626;">
                <div style="text-align: center; margin-bottom: 20px;">
                    <span style="background: #22c55e; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 12px;">
                        TEST
                    </span>
                </div>
                
                <h2 style="color: #ffffff; margin-bottom: 16px; text-align: center;">Email Configuration Test</h2>
                
                <p style="color: #9ca3af; text-align: center;">
                    This is a test email from SEO-NOC Domain Monitoring.<br>
                    If you received this, your email alerts are configured correctly.
                </p>
                
                <div style="margin-top: 24px; padding: 16px; background: #262626; border-radius: 4px; text-align: center;">
                    <p style="color: #22c55e; margin: 0; font-weight: bold;">
                        Configuration Successful
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        success = await self._send_email([recipient], subject, html_content)
        
        if success:
            return {"success": True, "message": f"Test email sent to {recipient}"}
        else:
            return {"success": False, "error": "Failed to send test email. Check API key and recipient."}


# Singleton instance
_email_service: Optional[EmailAlertService] = None


def get_email_alert_service(db: AsyncIOMotorDatabase) -> EmailAlertService:
    """Get or create email alert service instance"""
    global _email_service
    if _email_service is None:
        _email_service = EmailAlertService(db)
    return _email_service
