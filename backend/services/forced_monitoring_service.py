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
    Implements the ⚠️ MONITORING NOT CONFIGURED alert system.
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
                # Get network names and IDs
                network_names = []
                network_ids = []
                if usage["networks"]:
                    networks = await self.db.seo_networks.find(
                        {"id": {"$in": usage["networks"]}},
                        {"_id": 0, "id": 1, "name": 1}
                    ).to_list(None)
                    network_names = [n["name"] for n in networks]
                    network_ids = [n["id"] for n in networks]
                
                result.append({
                    "domain_id": domain["id"],
                    "domain_name": domain["domain_name"],
                    "brand_id": domain.get("brand_id"),
                    "monitoring_enabled": False,
                    "networks_used_in": network_names,
                    "network_ids": network_ids,
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
        
        REQUIRED BEHAVIOR (per spec):
        - If a domain is used in ANY SEO Network AND monitoring is NOT enabled:
          - Send Telegram reminder to Monitoring Channel
          - Message type: ⚠️ DOMAIN MONITORING NOT ENABLED
          - Repeat: Once per day
          - Stop only when: monitoring_enabled = true OR domain removed from all SEO Networks
        
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
        
        # Import SEO context enricher for structure
        from services.seo_context_enricher import SeoContextEnricher
        seo_enricher = SeoContextEnricher(self.db)
        
        reminders_sent = 0
        domains_notified = []
        
        # Send individual alert for each unmonitored domain
        for d in unmonitored:
            domain_name = d['domain_name']
            
            # Get brand name
            brand_name = "N/A"
            if d.get("brand_id"):
                brand = await self.db.brands.find_one({"id": d["brand_id"]}, {"_id": 0, "name": 1})
                if brand:
                    brand_name = brand["name"]
            
            # Get SEO context for this domain
            seo_context = await seo_enricher.enrich_domain_with_seo_context(
                domain_name, d.get('domain_id')
            )
            
            # Build message for this domain
            message = await self._build_unmonitored_alert_message(
                domain_name=domain_name,
                brand_name=brand_name,
                domain_info=d,
                seo_context=seo_context
            )
            
            # Send via telegram
            success = await telegram.send_alert(message)
            
            if success:
                reminders_sent += 1
                domains_notified.append(domain_name)
                logger.info(f"Sent unmonitored domain reminder for {domain_name}")
        
        if reminders_sent > 0:
            # Update last reminder time
            await self.db.scheduler_state.update_one(
                {"key": reminder_key},
                {"$set": {"key": reminder_key, "last_run": now.isoformat()}},
                upsert=True
            )
            
            logger.info(f"Sent unmonitored domain reminders for {reminders_sent} domains")
        
        return {
            "reminders_sent": reminders_sent,
            "domains_count": len(unmonitored),
            "domains": domains_notified
        }
    
    async def _build_unmonitored_alert_message(
        self,
        domain_name: str,
        brand_name: str,
        domain_info: Dict[str, Any],
        seo_context: Dict[str, Any]
    ) -> str:
        """
        Build alert message for unmonitored domain using exact format spec.
        
        Format:
        - Header: ⚠️ DOMAIN MONITORING NOT ENABLED
        - Domain Info: Domain, Brand, Used In SEO, Monitoring status
        - SEO CONTEXT: Network, Node Used, Role, Tier, Target
        - 🧭 STRUKTUR SEO TERKINI
        - ⚠️ RISK section
        """
        lines = []
        
        # Header
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚠️ DOMAIN MONITORING NOT ENABLED")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        # Domain Info
        lines.append(f"Domain        : {domain_name}")
        lines.append(f"Brand         : {brand_name}")
        lines.append(f"Used In SEO   : YES")
        lines.append(f"Monitoring    : ❌ Disabled")
        lines.append("")
        
        # SEO CONTEXT
        ctx_list = seo_context.get("seo_context", [])
        if ctx_list:
            first_ctx = ctx_list[0]
            network_name = first_ctx.get("network_name", "N/A")
            node_path = first_ctx.get("node") or domain_name
            role = first_ctx.get("role", "N/A")
            tier_label = first_ctx.get("tier_label", "N/A")
            target_node = first_ctx.get("target_node", "N/A")
            
            lines.append("SEO CONTEXT:")
            lines.append(f"Network       : {network_name}")
            lines.append(f"Node Used     : {node_path}")
            lines.append(f"Role          : {role}")
            lines.append(f"Tier          : {tier_label}")
            lines.append(f"Target        : {target_node}")
        else:
            lines.append("SEO CONTEXT:")
            lines.append(f"Network       : {', '.join(domain_info.get('networks_used_in', ['N/A']))}")
            lines.append(f"Node Used     : {domain_name}")
            lines.append(f"Role          : N/A")
            lines.append(f"Tier          : N/A")
            lines.append(f"Target        : N/A")
        lines.append("")
        
        # STRUKTUR SEO TERKINI
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🧭 STRUKTUR SEO TERKINI")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        full_structure = seo_context.get("full_structure_lines", [])
        if full_structure:
            for line in full_structure:
                # Remove HTML tags for plain text
                clean_line = line.replace("<b>", "").replace("</b>", "")
                lines.append(clean_line)
        else:
            lines.append("(Structure data unavailable)")
        lines.append("")
        
        # RISK section
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚠️ RISK:")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("Domain ini aktif digunakan dalam struktur SEO")
        lines.append("tetapi pemantauan TIDAK diaktifkan.")
        lines.append("Jika domain DOWN, alur otoritas SEO akan TERPUTUS.")
        
        return "\n".join(lines)


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
        """
        Build test alert message using the SAME format as real alerts.
        
        MESSAGE ORDER (per spec):
        1. Alert Type (🧪 TEST MODE – DOWN / EXPIRATION / CONFIG MISSING)
        2. Domain Info
        3. SEO Context Summary
        4. 🧭 STRUKTUR SEO TERKINI (Tier-based)
        5. 🔥 Impact Summary
        6. ⏰ Reminder / Next Action
        """
        impact_score = seo_context.get("impact_score", {})
        
        # Calculate STRICT severity
        if force_severity:
            severity = force_severity.upper()
        else:
            is_money_site = impact_score.get("node_role") == "main"
            reaches_money = impact_score.get("reaches_money_site", False)
            tier = impact_score.get("highest_tier_impacted")
            downstream_count = impact_score.get("downstream_nodes_count", 0)
            
            severity = calculate_strict_severity(
                is_money_site=is_money_site,
                reaches_money_site=reaches_money,
                tier=tier,
                downstream_count=downstream_count,
                is_orphan=(tier is None or tier >= 99)
            )
        
        severity_emoji = get_severity_emoji(severity)
        issue_emoji = "🔴" if issue_type == "DOWN" else "🟠"
        
        lines = []
        
        # 1. ALERT TYPE
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🧪 <b>TEST MODE – DOMAIN MONITORING ALERT</b>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append(f"{issue_emoji} <b>{issue_type}:</b> <code>{domain_name}</code>")
        lines.append(f"• <b>Reason:</b> {reason}")
        lines.append(f"• <b>Severity:</b> {severity_emoji} {severity}")
        lines.append("")
        
        # 2. DOMAIN INFO
        if domain:
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("📋 <b>DOMAIN INFO</b>")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"• <b>Status:</b> {domain.get('status', 'Unknown')}")
            if domain.get("brand_id"):
                brand = await self.db.brands.find_one({"id": domain["brand_id"]}, {"_id": 0, "name": 1})
                if brand:
                    lines.append(f"• <b>Brand:</b> {brand['name']}")
            if domain.get("expiration_date"):
                lines.append(f"• <b>Expires:</b> {domain['expiration_date'][:10]}")
            lines.append(f"• <b>Monitoring:</b> {'✅ Enabled' if domain.get('monitoring_enabled') else '❌ Disabled'}")
            lines.append("")
        
        # 3. SEO CONTEXT SUMMARY
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🔗 <b>SEO CONTEXT</b>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        if seo_context.get("used_in_seo"):
            ctx_list = seo_context.get("seo_context", [])
            if ctx_list:
                first_ctx = ctx_list[0]
                lines.append(f"• <b>Network:</b> {first_ctx.get('network_name', 'N/A')}")
                lines.append(f"• <b>Tier:</b> {first_ctx.get('tier_label', 'N/A')}")
                lines.append(f"• <b>Role:</b> {first_ctx.get('role', 'N/A')}")
                lines.append(f"• <b>Relation:</b> {first_ctx.get('domain_status', 'N/A').replace('_', ' ').title()}")
            
            lines.append(f"• <b>Networks Affected:</b> {impact_score.get('networks_affected', 0)}")
            lines.append(f"• <b>Downstream Nodes:</b> {impact_score.get('downstream_nodes_count', 0)}")
            lines.append(f"• <b>Reaches Money Site:</b> {'✅ YES' if impact_score.get('reaches_money_site') else '❌ NO'}")
            lines.append("")
            
            # 4. 🧭 STRUKTUR SEO TERKINI (Tier-based)
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("🧭 <b>STRUKTUR SEO TERKINI</b>")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            # Use the full_structure_lines from SEO context enricher
            full_structure = seo_context.get("full_structure_lines", [])
            if full_structure and len(full_structure) > 0:
                for line in full_structure:
                    lines.append(line)
            else:
                # Fallback: Build from upstream chain
                chain = seo_context.get("upstream_chain", [])
                if ctx_list:
                    first_ctx = ctx_list[0]
                    node_label = first_ctx.get("node") or domain_name
                    status_label = first_ctx.get("domain_status", "").replace("_", " ").title()
                    
                    if first_ctx.get("domain_role") == "main":
                        lines.append("")
                        lines.append("<b>LP / Money Site:</b>")
                        lines.append(f"  • {node_label} [Primary]")
                    else:
                        tier_label = first_ctx.get("tier_label", "Unknown")
                        lines.append("")
                        lines.append(f"<b>{tier_label}:</b>")
                        
                        target_node = first_ctx.get("target_node")
                        if target_node:
                            lines.append(f"  • {node_label} [{status_label}] → {target_node}")
                        else:
                            lines.append(f"  • {node_label} [{status_label}]")
                        
                        # Show chain to money site
                        if chain:
                            for hop in chain:
                                if hop.get("is_end"):
                                    end_reason = hop.get("end_reason", "END")
                                    if "money" in end_reason.lower():
                                        lines.append("  → END: 💰 MONEY SITE")
                                    else:
                                        lines.append(f"  → END: {end_reason}")
                                    break
                else:
                    lines.append("<i>Structure data unavailable</i>")
            lines.append("")
            
            # UPSTREAM CHAIN - consistent with structure
            if seo_context.get("upstream_chain"):
                lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                lines.append("⬆️ <b>UPSTREAM CHAIN</b>")
                lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                for hop in seo_context["upstream_chain"]:
                    node = hop.get("node", "Unknown")
                    relation = hop.get("relation", "")
                    
                    if hop.get("is_end"):
                        end_reason = hop.get("end_reason", "END")
                        if "money" in end_reason.lower():
                            lines.append(f"💰 {node} [{relation}]")
                            lines.append("→ END: 💰 MONEY SITE")
                        elif "orphan" in end_reason.lower():
                            lines.append(f"⚠️ {node} [{relation}]")
                            lines.append("→ END: ⚠️ ORPHAN NODE")
                        else:
                            lines.append(f"{node} [{relation}]")
                            lines.append(f"→ END: {end_reason}")
                    else:
                        target = hop.get("target", "")
                        target_relation = hop.get("target_relation", "")
                        lines.append(f"• {node} [{relation}] → {target} [{target_relation}]")
                lines.append("")
            
            # DOWNSTREAM IMPACT
            downstream = seo_context.get("downstream_impact", [])
            if downstream:
                lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                lines.append("⬇️ <b>DOWNSTREAM IMPACT</b>")
                lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                lines.append(f"<b>{len(downstream)}</b> nodes affected if this goes DOWN:")
                for node in downstream[:7]:
                    node_name = node.get("node", "Unknown")
                    relation = node.get("relation", "")
                    target = node.get("target", "")
                    lines.append(f"  • {node_name} [{relation}] → {target}")
                if len(downstream) > 7:
                    lines.append(f"  <i>+{len(downstream) - 7} more nodes</i>")
                lines.append("")
        else:
            lines.append("<i>This domain is NOT used in any SEO network</i>")
            lines.append("• <b>Severity:</b> LOW")
            lines.append("• <b>Networks Affected:</b> 0")
            lines.append("• <b>SEO Impact:</b> None")
            lines.append("")
        
        # 5. 🔥 IMPACT SUMMARY
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🔥 <b>IMPACT SUMMARY</b>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"• <b>Severity:</b> {severity_emoji} {severity}")
        
        if seo_context.get("used_in_seo"):
            if impact_score.get("reaches_money_site"):
                lines.append("• ⚠️ Link flow to Money Site is BROKEN")
            lines.append(f"• {impact_score.get('downstream_nodes_count', 0)} downstream nodes affected")
            if impact_score.get("node_role") == "main":
                lines.append("• 🚨 THIS IS THE MONEY SITE!")
        else:
            lines.append("• No SEO impact (domain not in any network)")
        lines.append("")
        
        # 6. ⏰ NEXT ACTION
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("⏰ <b>NEXT ACTION</b>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        if severity == "CRITICAL":
            lines.append("🚨 <b>IMMEDIATE ACTION REQUIRED</b>")
            lines.append("Investigate and restore domain IMMEDIATELY!")
        elif severity == "HIGH":
            lines.append("⚠️ <b>HIGH PRIORITY</b>")
            lines.append("Investigate within 1 hour")
        else:
            lines.append("📝 <b>INVESTIGATE</b>")
            lines.append("Review domain status and restore if needed")
        lines.append("")
        
        # TEST MODE FOOTER
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🧪 <b>THIS IS A TEST ALERT</b>")
        lines.append("<i>No real monitoring data was affected.</i>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
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
