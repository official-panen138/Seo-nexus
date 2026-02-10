"""
Forced Domain Monitoring & Test Alert Service
==============================================

SEO-AWARE DOMAIN MONITORING + STRUCTURED ALERT OUTPUT

Provides:
1. Forced monitoring enforcement - ensures all domains used in SEO networks are monitored
2. Unmonitored domain detection and reminders with ⚠️ MONITORING NOT CONFIGURED alerts
3. Test alert system for safe simulation of domain down alerts
4. Structured SEO Snapshot (STRUKTUR SEO TERKINI) in all alerts

Key Rules:
- Any domain/path used in SEO Network MUST have monitoring enabled
- Path-only usage requires root domain monitoring (if root is down, all paths are down)
- Daily reminders for unmonitored domains
- Test alerts use same formatter but don't persist or affect real monitoring

SEVERITY CALCULATION (STRICT):
- CRITICAL: Domain reaches Money Site OR domain is LP/Primary
- HIGH: Tier 1 node OR downstream nodes ≥ 3
- MEDIUM: Tier 2+ indirect impact
- LOW: Orphan/unused node

TELEGRAM MESSAGE ORDER:
1. Alert Type (DOWN / EXPIRATION / CONFIG MISSING)
2. Domain Info
3. SEO Context Summary
4. 🧭 STRUKTUR SEO TERKINI (Tier-based)
5. 🔥 Impact Summary
6. ⏰ Reminder / Next Action
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
import uuid
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


# ==================== SEVERITY CALCULATION ====================

def calculate_strict_severity(
    is_money_site: bool,
    reaches_money_site: bool,
    tier: Optional[int],
    downstream_count: int,
    is_orphan: bool
) -> str:
    """
    Calculate severity using STRICT rules:
    
    CRITICAL: Domain is Money Site/LP or directly reaches one
    HIGH: Tier 1 node or has ≥3 downstream nodes
    MEDIUM: Tier 2+ node with indirect impact
    LOW: Orphaned/unused node
    """
    if is_money_site:
        return "CRITICAL"
    
    if tier is not None and tier == 1 and reaches_money_site:
        return "CRITICAL"
    
    if tier == 1 or downstream_count >= 3:
        return "HIGH"
    
    if tier is not None and tier >= 2 and reaches_money_site:
        return "MEDIUM"
    
    if is_orphan or tier is None or tier >= 99:
        return "LOW"
    
    return "MEDIUM"


def get_severity_emoji(severity: str) -> str:
    """Get emoji for severity level"""
    return {
        "CRITICAL": "🚨",
        "HIGH": "🔴",
        "MEDIUM": "🟠",
        "LOW": "🟡"
    }.get(severity.upper(), "⚪")


class ForcedMonitoringService:
    """
    Service to enforce monitoring on all domains used in SEO networks.
    
    Detects unmonitored domains and sends reminder notifications.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    async def get_unmonitored_domains_in_seo(self) -> List[Dict[str, Any]]:
        """
        Find all domains used in SEO networks that don't have monitoring enabled.
        
        Returns list of unmonitored domains with their SEO usage info.
        """
        # Get all unique domains used in SEO structure entries
        pipeline = [
            {"$match": {"asset_domain_id": {"$exists": True, "$ne": None}}},
            {"$group": {
                "_id": "$asset_domain_id",
                "networks": {"$addToSet": "$network_id"},
                "paths": {"$addToSet": "$optimized_path"},
                "entry_count": {"$sum": 1}
            }}
        ]
        
        seo_domain_usage = await self.db.seo_structure_entries.aggregate(pipeline).to_list(None)
        
        if not seo_domain_usage:
            return []
        
        # Get all domain IDs used in SEO
        domain_ids = [u["_id"] for u in seo_domain_usage if u["_id"]]
        
        # Find which of these domains don't have monitoring enabled
        unmonitored = await self.db.asset_domains.find({
            "id": {"$in": domain_ids},
            "$or": [
                {"monitoring_enabled": False},
                {"monitoring_enabled": {"$exists": False}}
            ]
        }, {"_id": 0, "id": 1, "domain_name": 1, "brand_id": 1}).to_list(None)
        
        # Build result with SEO usage info
        result = []
        for domain in unmonitored:
            usage = next((u for u in seo_domain_usage if u["_id"] == domain["id"]), None)
            if usage:
                # Get network names
                network_names = []
                if usage["networks"]:
                    networks = await self.db.seo_networks.find(
                        {"id": {"$in": usage["networks"]}},
                        {"_id": 0, "id": 1, "name": 1}
                    ).to_list(None)
                    network_names = [n["name"] for n in networks]
                
                result.append({
                    "domain_id": domain["id"],
                    "domain_name": domain["domain_name"],
                    "brand_id": domain.get("brand_id"),
                    "monitoring_enabled": False,
                    "networks_used_in": network_names,
                    "network_count": len(usage["networks"]),
                    "paths_used": [p for p in usage["paths"] if p],
                    "entry_count": usage["entry_count"]
                })
        
        return result
    
    async def check_domain_seo_usage(self, domain_id: str) -> Dict[str, Any]:
        """
        Check if a specific domain is used in any SEO network.
        
        Returns usage details and monitoring status.
        """
        # Get domain
        domain = await self.db.asset_domains.find_one(
            {"id": domain_id},
            {"_id": 0, "id": 1, "domain_name": 1, "monitoring_enabled": 1}
        )
        
        if not domain:
            return {"used_in_seo": False, "monitoring_enabled": False}
        
        # Check SEO usage
        entries = await self.db.seo_structure_entries.find(
            {"asset_domain_id": domain_id},
            {"_id": 0, "network_id": 1, "optimized_path": 1}
        ).to_list(100)
        
        if not entries:
            return {
                "domain_id": domain_id,
                "domain_name": domain["domain_name"],
                "used_in_seo": False,
                "monitoring_enabled": domain.get("monitoring_enabled", False),
                "monitoring_required": False
            }
        
        # Get unique networks
        network_ids = list(set(e["network_id"] for e in entries if e.get("network_id")))
        networks = await self.db.seo_networks.find(
            {"id": {"$in": network_ids}},
            {"_id": 0, "id": 1, "name": 1}
        ).to_list(None)
        
        return {
            "domain_id": domain_id,
            "domain_name": domain["domain_name"],
            "used_in_seo": True,
            "monitoring_enabled": domain.get("monitoring_enabled", False),
            "monitoring_required": True,
            "networks": [{"id": n["id"], "name": n["name"]} for n in networks],
            "paths_used": [e["optimized_path"] for e in entries if e.get("optimized_path")]
        }
    
    async def send_unmonitored_reminders(self) -> Dict[str, Any]:
        """
        Send daily reminders for unmonitored domains used in SEO networks.
        
        Returns count of reminders sent.
        """
        unmonitored = await self.get_unmonitored_domains_in_seo()
        
        if not unmonitored:
            logger.info("No unmonitored domains in SEO networks")
            return {"reminders_sent": 0, "domains": []}
        
        # Check last reminder time to avoid spamming
        now = datetime.now(timezone.utc)
        reminder_key = "unmonitored_domain_reminder"
        
        last_reminder = await self.db.scheduler_state.find_one(
            {"key": reminder_key},
            {"_id": 0}
        )
        
        if last_reminder:
            last_time = datetime.fromisoformat(last_reminder["last_run"])
            if (now - last_time).total_seconds() < 86400:  # Less than 24 hours
                logger.info("Skipping reminder - last sent less than 24 hours ago")
                return {"reminders_sent": 0, "skipped": "too_recent", "domains": []}
        
        # Import telegram service
        from services.monitoring_service import DomainMonitoringTelegramService
        telegram = DomainMonitoringTelegramService(self.db)
        
        # Build reminder message
        message_lines = [
            "⚠️ UNMONITORED DOMAINS IN SEO NETWORKS",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"Found {len(unmonitored)} domain(s) used in SEO networks without monitoring enabled:",
            ""
        ]
        
        for d in unmonitored[:10]:  # Limit to 10 to avoid too long message
            message_lines.append(f"• {d['domain_name']}")
            message_lines.append(f"  Networks: {', '.join(d['networks_used_in'][:3])}")
            if d['paths_used']:
                paths_preview = d['paths_used'][:2]
                message_lines.append(f"  Paths: {', '.join(paths_preview)}")
            message_lines.append("")
        
        if len(unmonitored) > 10:
            message_lines.append(f"... and {len(unmonitored) - 10} more domains")
            message_lines.append("")
        
        message_lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "ACTION REQUIRED:",
            "Enable monitoring for these domains in Asset Domains settings.",
            "",
            "If a root domain goes DOWN, all paths become inaccessible."
        ])
        
        message = "\n".join(message_lines)
        
        # Send via telegram
        success = await telegram.send_alert(message)
        
        if success:
            # Update last reminder time
            await self.db.scheduler_state.update_one(
                {"key": reminder_key},
                {"$set": {"key": reminder_key, "last_run": now.isoformat()}},
                upsert=True
            )
            
            logger.info(f"Sent unmonitored domain reminder for {len(unmonitored)} domains")
            return {
                "reminders_sent": 1,
                "domains_count": len(unmonitored),
                "domains": [d["domain_name"] for d in unmonitored]
            }
        
        return {"reminders_sent": 0, "error": "telegram_failed", "domains": []}


class TestAlertService:
    """
    Service for generating test domain monitoring alerts.
    
    Uses the same formatters and logic as real alerts but:
    - Does NOT change real domain status
    - Does NOT affect monitoring schedules
    - Does NOT increment deduplication counters
    - Marks all messages with 🧪 TEST MODE
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        from services.seo_context_enricher import SeoContextEnricher
        from services.monitoring_service import DomainMonitoringTelegramService
        
        self.seo_enricher = SeoContextEnricher(db)
        self.telegram = DomainMonitoringTelegramService(db)
    
    async def send_test_domain_down_alert(
        self,
        domain_name: str,
        issue_type: str = "DOWN",
        reason: str = "Timeout",
        force_severity: Optional[str] = None,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a test domain down alert.
        
        Uses the same formatting as real alerts but with TEST MODE markers.
        Does not affect real monitoring data.
        
        Args:
            domain_name: Domain to simulate alert for
            issue_type: "DOWN" or "SOFT_BLOCKED"
            reason: "Timeout", "JS Challenge", "Country Block", etc.
            force_severity: Optional override for severity level
            actor_id: ID of user triggering the test
            actor_email: Email of user triggering the test
            
        Returns:
            Result dict with message_sent status and alert content
        """
        # Validate domain exists
        domain = await self.db.asset_domains.find_one(
            {"domain_name": domain_name},
            {"_id": 0}
        )
        
        if not domain:
            # Try partial match
            domain = await self.db.asset_domains.find_one(
                {"domain_name": {"$regex": domain_name, "$options": "i"}},
                {"_id": 0}
            )
        
        # Get SEO context (same as real alerts)
        seo_context = await self.seo_enricher.enrich_domain_with_seo_context(
            domain_name, 
            domain.get("id") if domain else None
        )
        
        # Build test alert message (reusing real alert format)
        message = await self._build_test_alert_message(
            domain_name=domain_name,
            domain=domain,
            issue_type=issue_type,
            reason=reason,
            seo_context=seo_context,
            force_severity=force_severity
        )
        
        # Send via telegram
        success = await self.telegram.send_alert(message)
        
        # Log test event separately
        now = datetime.now(timezone.utc)
        await self.db.test_alert_logs.insert_one({
            "id": str(uuid.uuid4()),
            "domain": domain_name,
            "issue_type": issue_type,
            "reason": reason,
            "force_severity": force_severity,
            "actor_id": actor_id,
            "actor_email": actor_email,
            "test_mode": True,
            "message_sent": success,
            "timestamp": now.isoformat()
        })
        
        return {
            "success": success,
            "domain": domain_name,
            "issue_type": issue_type,
            "reason": reason,
            "seo_context": seo_context,
            "message_preview": message[:500] + "..." if len(message) > 500 else message,
            "test_mode": True
        }
    
    async def _build_test_alert_message(
        self,
        domain_name: str,
        domain: Optional[Dict[str, Any]],
        issue_type: str,
        reason: str,
        seo_context: Dict[str, Any],
        force_severity: Optional[str] = None
    ) -> str:
        """Build test alert message using same format as real alerts."""
        
        # Determine severity
        if force_severity:
            severity = force_severity.upper()
        else:
            impact = seo_context.get("impact_score", {})
            severity = impact.get("severity", "LOW")
        
        severity_emoji = {
            "LOW": "🟡",
            "MEDIUM": "🟠",
            "HIGH": "🔴",
            "CRITICAL": "🚨"
        }.get(severity, "⚪")
        
        issue_emoji = "🔴" if issue_type == "DOWN" else "🟠"
        
        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "🧪 TEST MODE – DOMAIN MONITORING ALERT",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"{issue_emoji} {issue_type}: {domain_name}",
            f"Reason: {reason}",
            f"Severity: {severity_emoji} {severity}",
            ""
        ]
        
        # Add domain info if available
        if domain:
            lines.append("📋 DOMAIN INFO")
            lines.append(f"  Status: {domain.get('status', 'Unknown')}")
            if domain.get("brand_id"):
                brand = await self.db.brands.find_one({"id": domain["brand_id"]}, {"_id": 0, "name": 1})
                if brand:
                    lines.append(f"  Brand: {brand['name']}")
            if domain.get("expiration_date"):
                lines.append(f"  Expires: {domain['expiration_date'][:10]}")
            lines.append("")
        
        # Add SEO context
        if seo_context.get("used_in_seo"):
            lines.append("🔗 SEO CONTEXT")
            
            impact = seo_context.get("impact_score", {})
            lines.append(f"  Networks Affected: {impact.get('networks_affected', 0)}")
            lines.append(f"  Downstream Nodes: {impact.get('downstream_nodes_count', 0)}")
            lines.append(f"  Reaches Money Site: {'✅ Yes' if impact.get('reaches_money_site') else '❌ No'}")
            
            if impact.get("highest_tier_impacted"):
                lines.append(f"  Highest Tier: {impact.get('highest_tier_impacted')}")
            
            lines.append("")
            
            # Add structure chain
            if seo_context.get("seo_context"):
                lines.append("📊 STRUCTURE")
                for ctx in seo_context["seo_context"][:3]:
                    lines.append(f"  Network: {ctx.get('network_name', 'Unknown')}")
                    if ctx.get("node_role"):
                        lines.append(f"    Role: {ctx['node_role']}")
                    if ctx.get("tier"):
                        lines.append(f"    Tier: {ctx['tier']}")
                lines.append("")
            
            # Add upstream chain
            if seo_context.get("upstream_chain"):
                lines.append("⬆️ UPSTREAM CHAIN (to Money Site)")
                for node in seo_context["upstream_chain"][:5]:
                    tier_label = f"[T{node.get('tier', '?')}]" if node.get("tier") else ""
                    lines.append(f"  {tier_label} {node.get('label', node.get('domain', 'Unknown'))}")
                lines.append("")
            
            # Add downstream impact
            if seo_context.get("downstream_impact"):
                lines.append("⬇️ DOWNSTREAM IMPACT")
                for node in seo_context["downstream_impact"][:5]:
                    lines.append(f"  → {node.get('label', node.get('domain', 'Unknown'))}")
                if len(seo_context["downstream_impact"]) > 5:
                    lines.append(f"  ... and {len(seo_context['downstream_impact']) - 5} more")
                lines.append("")
        else:
            lines.append("ℹ️ This domain is NOT used in any SEO network")
            lines.append("")
        
        # Add test mode footer
        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "🧪 THIS IS A TEST ALERT",
            "No real monitoring data was affected.",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ])
        
        return "\n".join(lines)
    
    async def get_test_alert_history(
        self,
        limit: int = 50,
        domain: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get history of test alerts."""
        query = {"test_mode": True}
        if domain:
            query["domain"] = {"$regex": domain, "$options": "i"}
        
        logs = await self.db.test_alert_logs.find(
            query,
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        return logs
