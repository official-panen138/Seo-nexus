"""
Notification Template Engine

Provides Mustache-style template rendering for notifications.
Supports Telegram and Email channels with variable substitution.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# GMT+7 timezone
GMT7 = timezone(timedelta(hours=7))

# Predefined variables that templates can use
ALLOWED_VARIABLES = {
    # User/Actor variables
    "user.display_name",
    "user.email",
    "user.role",
    "user.id",
    
    # Network variables
    "network.name",
    "network.id",
    "network.description",
    
    # Brand variables
    "brand.name",
    "brand.id",
    
    # Node/Structure variables
    "node.domain",
    "node.full_path",
    "node.role",
    "node.tier",
    "node.status",
    "node.id",
    
    # Change/Action variables
    "change.action",
    "change.action_label",
    "change.reason",
    "change.before",
    "change.after",
    "change.details",
    
    # Optimization variables
    "optimization.title",
    "optimization.description",
    "optimization.type",
    "optimization.type_label",
    "optimization.status",
    "optimization.status_label",
    "optimization.targets",
    "optimization.keywords",
    "optimization.reports",
    "optimization.expected_impact",
    
    # Complaint variables
    "complaint.reason",
    "complaint.priority",
    "complaint.priority_label",
    "complaint.category",
    "complaint.category_label",
    "complaint.reports",
    "complaint.status",
    
    # Domain monitoring variables
    "domain.name",
    "domain.expiry_date",
    "domain.days_until_expiry",
    "domain.registrar",
    "domain.status",
    "domain.http_status",
    "domain.response_time",
    
    # Impact/Severity variables
    "impact.severity",
    "impact.severity_emoji",
    "impact.description",
    "impact.affected_count",
    
    # Timestamp variables
    "timestamp.gmt7",
    "timestamp.iso",
    "timestamp.date",
    "timestamp.time",
    
    # Telegram tagging
    "telegram.leaders",
    "telegram.project_managers",
    "telegram.tagged_users",
    
    # Structure/hierarchy
    "structure.current",
    "structure.upstream_chain",
    "structure.downstream_impact",
    
    # Reminder specific
    "reminder.days_in_progress",
    "reminder.optimization_title",
    "reminder.optimization_status",
}

# Default templates for each event type
DEFAULT_TEMPLATES = {
    # SEO Change notification (Telegram)
    ("telegram", "seo_change"): {
        "title": "SEO Structure Update",
        "template_body": """👤 <b>PEMBARUAN OPTIMASI BAGAN SEO</b>

{{user.display_name}} telah melakukan perubahan optimasi bagan SEO pada network '<b>{{network.name}}</b>' untuk brand '<b>{{brand.name}}</b>', dengan detail sebagai berikut:

━━━━━━━━━━━━━━━━━━━━━━
📌 <b>RINGKASAN AKSI</b>
━━━━━━━━━━━━━━━━━━━━━━
• Aksi: {{change.action_label}}
• Dilakukan Oleh: {{user.display_name}} ({{user.email}})
• Waktu: {{timestamp.gmt7}}

━━━━━━━━━━━━━━━━━━━━━━
📝 <b>ALASAN PERUBAHAN</b>
━━━━━━━━━━━━━━━━━━━━━━
"{{change.reason}}"

━━━━━━━━━━━━━━━━━━━━━━
{{change.details}}

━━━━━━━━━━━━━━━━━━━━━━
🧭 <b>STRUKTUR SEO TERKINI</b>
━━━━━━━━━━━━━━━━━━━━━━
{{structure.current}}

👁 <b>CC:</b> {{telegram.leaders}}"""
    },
    
    # SEO Network Created (Telegram)
    ("telegram", "seo_network_created"): {
        "title": "New SEO Network Created",
        "template_body": """👤 <b>SEO NETWORK BARU DIBUAT</b>

{{user.display_name}} telah membuat SEO Network baru '<b>{{network.name}}</b>' untuk brand '<b>{{brand.name}}</b>'.

━━━━━━━━━━━━━━━━━━━━━━
📌 <b>DETAIL NETWORK BARU</b>
━━━━━━━━━━━━━━━━━━━━━━
• Nama Network: {{network.name}}
• Brand: {{brand.name}}
• Dibuat Oleh: {{user.display_name}} ({{user.email}})
• Waktu: {{timestamp.gmt7}}

━━━━━━━━━━━━━━━━━━━━━━
🧭 <b>STRUKTUR SEO AWAL</b>
━━━━━━━━━━━━━━━━━━━━━━
{{structure.current}}

👁 <b>CC:</b> {{telegram.leaders}}"""
    },
    
    # SEO Optimization Created/Updated (Telegram)
    ("telegram", "seo_optimization"): {
        "title": "SEO Optimization Activity",
        "template_body": """📘 <b>SEO OPTIMIZATION ACTIVITY</b>

<b>{{user.display_name}}</b> telah menambahkan aktivitas optimasi SEO
pada network '<b>{{network.name}}</b>' untuk brand '<b>{{brand.name}}</b>'.

━━━━━━━━━━━━━━━━━━━━━━
📌 <b>RINGKASAN</b>
━━━━━━━━━━━━━━━━━━━━━━
• <b>Jenis:</b> {{optimization.type_label}}
• <b>Status:</b> {{optimization.status_label}}
• <b>Dilakukan:</b> {{user.display_name}} ({{user.email}})
• <b>Waktu:</b> {{timestamp.gmt7}}

📝 <b>Judul:</b>
{{optimization.title}}

📄 <b>Deskripsi:</b>
"{{optimization.description}}"

🎯 <b>Target:</b>
{{optimization.targets}}

🔑 <b>Keyword:</b>
{{optimization.keywords}}

📊 <b>Expected Impact:</b>
{{optimization.expected_impact}}

📎 <b>Report:</b>
{{optimization.reports}}

━━━━━━━━━━━━━━━━━━━━━━
<i>⚠️ Catatan: Tidak ada perubahan struktur SEO</i>

👁 <b>CC:</b> {{telegram.leaders}}"""
    },
    
    # SEO Optimization Status Change (Telegram)
    ("telegram", "seo_optimization_status"): {
        "title": "SEO Optimization Status Update",
        "template_body": """{{impact.severity_emoji}} <b>SEO OPTIMIZATION STATUS UPDATE</b>

<b>{{user.display_name}}</b> telah mengubah status aktivitas optimasi SEO
pada network '<b>{{network.name}}</b>' untuk brand '<b>{{brand.name}}</b>'.

━━━━━━━━━━━━━━━━━━━━━━
📝 <b>Aktivitas:</b>
{{optimization.title}}

🔄 <b>Perubahan Status:</b>
{{change.before}} → <b>{{change.after}}</b>

👤 <b>Diubah oleh:</b> {{user.display_name}} ({{user.email}})
🕐 <b>Waktu:</b> {{timestamp.gmt7}}

━━━━━━━━━━━━━━━━━━━━━━
<i>⚠️ Catatan: Tidak ada perubahan struktur SEO</i>

👁 <b>CC:</b> {{telegram.leaders}}"""
    },
    
    # SEO Complaint - Optimization Level (Telegram)
    ("telegram", "seo_complaint"): {
        "title": "SEO Optimization Complaint",
        "template_body": """🚨 <b>SEO OPTIMIZATION COMPLAINT</b>

<b>{{user.display_name}}</b> telah mengajukan komplain
pada SEO Network '<b>{{network.name}}</b>' untuk brand '<b>{{brand.name}}</b>'.

━━━━━━━━━━━━━━━━━━━━━━
📌 <b>DETAIL OPTIMASI</b>
━━━━━━━━━━━━━━━━━━━━━━
• Judul: {{optimization.title}}
• Jenis: {{optimization.type_label}}
• Status: {{optimization.status_label}}

━━━━━━━━━━━━━━━━━━━━━━
👥 <b>Network Manager (Tagged):</b>
{{telegram.project_managers}}

📁 <b>Kategori:</b> {{complaint.category_label}}
{{complaint.priority_label}}

━━━━━━━━━━━━━━━━━━━━━━
📝 <b>Alasan Komplain:</b>
"{{complaint.reason}}"

📎 <b>Related Reports:</b>
{{complaint.reports}}

🕐 <b>Waktu:</b> {{timestamp.gmt7}}

━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>Action Required:</b>
<i>Please review and respond to this complaint.</i>"""
    },
    
    # Project-Level Complaint (Telegram)
    ("telegram", "seo_project_complaint"): {
        "title": "Project-Level Complaint",
        "template_body": """🚨 <b>PROJECT-LEVEL COMPLAINT</b>

<b>{{user.display_name}}</b> telah mengajukan komplain
pada SEO Network '<b>{{network.name}}</b>'.

<i>Komplain ini tidak terkait dengan optimasi tertentu,
tetapi menyangkut pengelolaan proyek secara keseluruhan.</i>

━━━━━━━━━━━━━━━━━━━━━━
👥 <b>Network Manager (Tagged):</b>
{{telegram.project_managers}}

📁 <b>Kategori:</b> {{complaint.category_label}}
{{complaint.priority_label}}

━━━━━━━━━━━━━━━━━━━━━━
📝 <b>Alasan Komplain:</b>
"{{complaint.reason}}"

📎 <b>Related Reports:</b>
{{complaint.reports}}

🕐 <b>Waktu:</b> {{timestamp.gmt7}}

━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>Action Required:</b>
<i>Please review and respond to this complaint.</i>"""
    },
    
    # SEO Reminder (Telegram)
    ("telegram", "seo_reminder"): {
        "title": "SEO Optimization Reminder",
        "template_body": """⏰ <b>SEO OPTIMIZATION REMINDER</b>

Optimasi berikut sudah berjalan <b>{{reminder.days_in_progress}} hari</b> dan masih dalam status "<b>{{reminder.optimization_status}}</b>".

━━━━━━━━━━━━━━━━━━━━━━
📝 <b>Detail Optimasi:</b>
• <b>Network:</b> {{network.name}}
• <b>Brand:</b> {{brand.name}}
• <b>Judul:</b> {{optimization.title}}
• <b>Status:</b> {{optimization.status_label}}

━━━━━━━━━━━━━━━━━━━━━━
👥 <b>Tagged:</b>
{{telegram.tagged_users}}

━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>Action Required:</b>
<i>Mohon update status optimasi ini atau berikan catatan progress.</i>"""
    },
    
    # Domain Expiration Alert (Telegram)
    ("telegram", "domain_expiration"): {
        "title": "Domain Expiration Alert",
        "template_body": """⚠️ <b>DOMAIN EXPIRATION ALERT</b>

Domain <b>{{domain.name}}</b> akan expire dalam <b>{{domain.days_until_expiry}} hari</b>.

━━━━━━━━━━━━━━━━━━━━━━
📌 <b>DETAIL DOMAIN</b>
━━━━━━━━━━━━━━━━━━━━━━
• Domain: {{domain.name}}
• Expiry Date: {{domain.expiry_date}}
• Registrar: {{domain.registrar}}

━━━━━━━━━━━━━━━━━━━━━━
🧭 <b>SEO NETWORK CONTEXT</b>
━━━━━━━━━━━━━━━━━━━━━━
• Network: {{network.name}}
• Role: {{node.role}}
• Tier: {{node.tier}}

📊 <b>IMPACT ANALYSIS</b>
━━━━━━━━━━━━━━━━━━━━━━
• Severity: {{impact.severity_emoji}} {{impact.severity}}
• Upstream Chain: {{structure.upstream_chain}}
• Downstream Impact: {{structure.downstream_impact}}

━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>Action Required:</b>
<i>Renew domain before expiration to avoid SEO impact.</i>"""
    },
    
    # Domain Down Alert (Telegram)
    ("telegram", "domain_down"): {
        "title": "Domain Down Alert",
        "template_body": """🔴 <b>DOMAIN DOWN ALERT</b>

Domain <b>{{domain.name}}</b> tidak dapat diakses!

━━━━━━━━━━━━━━━━━━━━━━
📌 <b>DETAIL STATUS</b>
━━━━━━━━━━━━━━━━━━━━━━
• Domain: {{domain.name}}
• HTTP Status: {{domain.http_status}}
• Response Time: {{domain.response_time}}
• Checked At: {{timestamp.gmt7}}

━━━━━━━━━━━━━━━━━━━━━━
🧭 <b>SEO NETWORK CONTEXT</b>
━━━━━━━━━━━━━━━━━━━━━━
• Network: {{network.name}}
• Role: {{node.role}}
• Tier: {{node.tier}}

📊 <b>IMPACT ANALYSIS</b>
━━━━━━━━━━━━━━━━━━━━━━
• Severity: {{impact.severity_emoji}} {{impact.severity}}
• Affected Nodes: {{impact.affected_count}}
• Upstream Chain: {{structure.upstream_chain}}

━━━━━━━━━━━━━━━━━━━━━━
🚨 <b>URGENT Action Required:</b>
<i>Investigate and restore domain immediately.</i>"""
    },
    
    # Node Deleted (Telegram) - Enhanced with full pre-deletion details
    ("telegram", "seo_node_deleted"): {
        "title": "SEO Node Deleted",
        "template_body": """🗑️ <b>NODE SEO DIHAPUS</b>

<b>{{user.display_name}}</b> telah menghapus node dari network '<b>{{network.name}}</b>' untuk brand '<b>{{brand.name}}</b>'.

━━━━━━━━━━━━━━━━━━━━━━
📌 <b>DETAIL NODE (SEBELUM DIHAPUS)</b>
━━━━━━━━━━━━━━━━━━━━━━
• <b>Node:</b> {{node.domain_name}}
• <b>Role:</b> {{node.domain_role}}
• <b>Status:</b> {{node.domain_status}}
• <b>Index:</b> {{node.index_status}}
• <b>Target:</b> {{node.target}}

━━━━━━━━━━━━━━━━━━━━━━
📝 <b>ALASAN PENGHAPUSAN</b>
━━━━━━━━━━━━━━━━━━━━━━
"{{change.reason}}"

━━━━━━━━━━━━━━━━━━━━━━
⚠️ <b>DAMPAK PENGHAPUSAN</b>
━━━━━━━━━━━━━━━━━━━━━━
• <b>Authority Flow:</b> TERPUTUS
• <b>Severity:</b> {{impact.severity}}
• <b>Node Terdampak:</b> {{impact.affected_count}}

━━━━━━━━━━━━━━━━━━━━━━
🧭 <b>STRUKTUR SEO (SEBELUM PENGHAPUSAN)</b>
━━━━━━━━━━━━━━━━━━━━━━
{{structure.before_deletion}}

━━━━━━━━━━━━━━━━━━━━━━
🕐 <b>Waktu:</b> {{timestamp.gmt7}}
👤 <b>Oleh:</b> {{user.display_name}} ({{user.email}})

👁 <b>CC:</b> {{telegram.leaders}}"""
    },
    
    # Test notification
    ("telegram", "test"): {
        "title": "Test Notification",
        "template_body": """🔔 <b>PESAN TEST - TIDAK ADA PERUBAHAN SEO</b>

Ini adalah pesan test untuk memverifikasi konfigurasi notifikasi Telegram.

━━━━━━━━━━━━━━━━━━━━━━
• Dikirim Oleh: {{user.display_name}} ({{user.email}})
• Waktu: {{timestamp.gmt7}}
━━━━━━━━━━━━━━━━━━━━━━

✅ Jika Anda menerima pesan ini, konfigurasi berhasil."""
    },
}


class NotificationTemplateEngine:
    """Template engine for notification messages."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self._template_cache: Dict[str, Dict] = {}
    
    async def get_template(self, channel: str, event_type: str) -> Dict[str, Any]:
        """
        Get template for given channel and event type.
        Returns from DB if exists, otherwise returns default.
        """
        cache_key = f"{channel}:{event_type}"
        
        # Check cache first
        if cache_key in self._template_cache:
            return self._template_cache[cache_key]
        
        # Try to get from database
        template = await self.db.notification_templates.find_one(
            {"channel": channel, "event_type": event_type},
            {"_id": 0}
        )
        
        if template:
            self._template_cache[cache_key] = template
            return template
        
        # Fallback to default
        default_key = (channel, event_type)
        if default_key in DEFAULT_TEMPLATES:
            default = DEFAULT_TEMPLATES[default_key]
            return {
                "channel": channel,
                "event_type": event_type,
                "title": default["title"],
                "template_body": default["template_body"],
                "default_template_body": default["template_body"],
                "enabled": True,
            }
        
        return None
    
    def clear_cache(self):
        """Clear the template cache (call after template updates)."""
        self._template_cache.clear()
    
    def render(self, template_body: str, context: Dict[str, Any]) -> str:
        """
        Render template with given context.
        Replaces {{variable}} with values from context.
        """
        def replace_var(match):
            var_name = match.group(1).strip()
            
            # Handle nested variables like user.display_name
            parts = var_name.split(".")
            value = context
            
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    # Variable not found, return empty or placeholder
                    return ""
            
            # Convert to string
            if value is None:
                return ""
            if isinstance(value, list):
                return ", ".join(str(v) for v in value)
            return str(value)
        
        # Replace all {{variable}} patterns
        pattern = r'\{\{([^}]+)\}\}'
        result = re.sub(pattern, replace_var, template_body)
        
        return result
    
    def validate_template(self, template_body: str) -> List[str]:
        """
        Validate template for unknown variables.
        Returns list of invalid variables.
        """
        pattern = r'\{\{([^}]+)\}\}'
        matches = re.findall(pattern, template_body)
        
        invalid = []
        for var_name in matches:
            var_name = var_name.strip()
            if var_name not in ALLOWED_VARIABLES:
                invalid.append(var_name)
        
        return invalid
    
    def get_allowed_variables(self) -> List[str]:
        """Get list of allowed variables for UI display."""
        return sorted(list(ALLOWED_VARIABLES))


async def initialize_default_templates(db: AsyncIOMotorDatabase):
    """
    Initialize default templates in database if they don't exist.
    Called on application startup.
    """
    for (channel, event_type), template_data in DEFAULT_TEMPLATES.items():
        existing = await db.notification_templates.find_one({
            "channel": channel,
            "event_type": event_type
        })
        
        if not existing:
            import uuid
            template = {
                "id": str(uuid.uuid4()),
                "channel": channel,
                "event_type": event_type,
                "title": template_data["title"],
                "template_body": template_data["template_body"],
                "default_template_body": template_data["template_body"],
                "enabled": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.notification_templates.insert_one(template)
            logger.info(f"Created default template: {channel}/{event_type}")


def format_timestamp_gmt7(dt: datetime = None) -> str:
    """Format datetime to GMT+7 string."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    gmt7_time = dt.astimezone(GMT7)
    return gmt7_time.strftime("%Y-%m-%d %H:%M:%S GMT+7")


def build_notification_context(
    user: Dict = None,
    network: Dict = None,
    brand: Dict = None,
    node: Dict = None,
    change: Dict = None,
    optimization: Dict = None,
    complaint: Dict = None,
    domain: Dict = None,
    impact: Dict = None,
    structure: Dict = None,
    reminder: Dict = None,
    telegram_leaders: List[str] = None,
    telegram_project_managers: List[str] = None,
    telegram_tagged_users: List[str] = None,
) -> Dict[str, Any]:
    """
    Build context dictionary for template rendering.
    All parameters are optional - only pass what's relevant.
    """
    context = {
        "timestamp": {
            "gmt7": format_timestamp_gmt7(),
            "iso": datetime.now(timezone.utc).isoformat(),
            "date": datetime.now(GMT7).strftime("%Y-%m-%d"),
            "time": datetime.now(GMT7).strftime("%H:%M:%S"),
        }
    }
    
    if user:
        context["user"] = {
            "display_name": user.get("display_name") or user.get("name") or user.get("email", "Unknown"),
            "email": user.get("email", ""),
            "role": user.get("role", ""),
            "id": user.get("id", ""),
        }
    
    if network:
        context["network"] = {
            "name": network.get("name", "Unknown"),
            "id": network.get("id", ""),
            "description": network.get("description", ""),
        }
    
    if brand:
        context["brand"] = {
            "name": brand.get("name", "Unknown"),
            "id": brand.get("id", ""),
        }
    
    if node:
        context["node"] = {
            "domain": node.get("domain_name") or node.get("domain", ""),
            "full_path": node.get("full_path") or node.get("optimized_path", "/"),
            "role": node.get("domain_role", ""),
            "tier": node.get("tier", ""),
            "status": node.get("domain_status", ""),
            "id": node.get("id", ""),
        }
    
    if change:
        context["change"] = {
            "action": change.get("action", ""),
            "action_label": change.get("action_label", ""),
            "reason": change.get("reason") or change.get("change_note", "(Tidak ada alasan)"),
            "before": change.get("before", ""),
            "after": change.get("after", ""),
            "details": change.get("details", ""),
        }
    
    if optimization:
        context["optimization"] = {
            "title": optimization.get("title", "(Tanpa judul)"),
            "description": optimization.get("description", "(Tidak ada deskripsi)"),
            "type": optimization.get("activity_type", "other"),
            "type_label": _get_activity_type_label(optimization.get("activity_type", "other")),
            "status": optimization.get("status", ""),
            "status_label": _get_status_label(optimization.get("status", "")),
            "targets": _format_list(optimization.get("affected_targets", [])),
            "keywords": _format_list(optimization.get("keywords", [])),
            "reports": _format_list(optimization.get("report_urls", [])),
            "expected_impact": _format_list([_get_impact_label(i) for i in optimization.get("expected_impact", [])]),
        }
    
    if complaint:
        priority = complaint.get("priority", "medium")
        context["complaint"] = {
            "reason": complaint.get("reason", "(Tidak ada alasan)"),
            "priority": priority,
            "priority_label": f"{'🔵' if priority == 'low' else '🟡' if priority == 'medium' else '🔴'} Prioritas: {_get_priority_label(priority)}",
            "category": complaint.get("category", ""),
            "category_label": _get_category_label(complaint.get("category", "")),
            "reports": _format_list(complaint.get("report_urls", [])),
            "status": complaint.get("status", ""),
        }
    
    if domain:
        context["domain"] = {
            "name": domain.get("domain_name") or domain.get("name", ""),
            "expiry_date": domain.get("expiry_date", ""),
            "days_until_expiry": domain.get("days_until_expiry", ""),
            "registrar": domain.get("registrar", "Unknown"),
            "status": domain.get("status", ""),
            "http_status": domain.get("http_status", ""),
            "response_time": domain.get("response_time", ""),
        }
    
    if impact:
        severity = impact.get("severity", "LOW")
        context["impact"] = {
            "severity": severity,
            "severity_emoji": {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}.get(severity, "⚪"),
            "description": impact.get("description", ""),
            "affected_count": impact.get("affected_count", 0),
        }
    
    if structure:
        context["structure"] = {
            "current": structure.get("current", ""),
            "upstream_chain": structure.get("upstream_chain", ""),
            "downstream_impact": structure.get("downstream_impact", ""),
        }
    
    if reminder:
        context["reminder"] = {
            "days_in_progress": reminder.get("days_in_progress", 0),
            "optimization_title": reminder.get("optimization_title", ""),
            "optimization_status": reminder.get("optimization_status", ""),
        }
    
    # Telegram tagging
    context["telegram"] = {
        "leaders": " ".join([f"@{leader.replace('@', '')}" for leader in (telegram_leaders or [])]) or "(tidak ada)",
        "project_managers": "\n".join([f"  • @{mgr.replace('@', '')}" for mgr in (telegram_project_managers or [])]) or "  (tidak ada)",
        "tagged_users": "\n".join([f"  • @{usr.replace('@', '')}" for usr in (telegram_tagged_users or [])]) or "  (tidak ada)",
    }
    
    return context


def _format_list(items: List, prefix: str = "  • ") -> str:
    """Format list items with prefix."""
    if not items:
        return "  (tidak ada)"
    return "\n".join([f"{prefix}{item}" for item in items])


def _get_activity_type_label(activity_type: str) -> str:
    """Get human-readable activity type label."""
    labels = {
        "backlink_campaign": "Backlink Campaign",
        "content_optimization": "Content Optimization",
        "technical_seo": "Technical SEO",
        "link_building": "Link Building",
        "on_page": "On-Page SEO",
        "off_page": "Off-Page SEO",
        "other": "Lainnya",
    }
    return labels.get(activity_type, activity_type.replace("_", " ").title())


def _get_status_label(status: str) -> str:
    """Get human-readable status label."""
    labels = {
        "planned": "Direncanakan",
        "in_progress": "Sedang Berjalan",
        "completed": "Selesai",
        "reverted": "Dibatalkan",
    }
    return labels.get(status, status.replace("_", " ").title())


def _get_priority_label(priority: str) -> str:
    """Get human-readable priority label."""
    labels = {
        "low": "Rendah",
        "medium": "Sedang",
        "high": "Tinggi",
    }
    return labels.get(priority, priority.title())


def _get_category_label(category: str) -> str:
    """Get human-readable category label."""
    labels = {
        "communication": "Komunikasi",
        "deadline": "Deadline",
        "quality": "Kualitas",
        "process": "Proses",
    }
    return labels.get(category, category.title() if category else "Umum")


def _get_impact_label(impact: str) -> str:
    """Get human-readable impact label."""
    labels = {
        "traffic_increase": "Peningkatan Traffic",
        "ranking_improvement": "Peningkatan Ranking",
        "authority_boost": "Peningkatan Authority",
        "indexation": "Indexation",
    }
    return labels.get(impact, impact.replace("_", " ").title())


# ==================== TEMPLATE CRUD SERVICE ====================

class NotificationTemplateCRUD:
    """CRUD operations for notification templates."""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.engine = NotificationTemplateEngine(db)
    
    async def list_templates(self, channel: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all templates, optionally filtered by channel."""
        query = {}
        if channel:
            query["channel"] = channel
        
        templates = await self.db.notification_templates.find(
            query, {"_id": 0}
        ).sort([("channel", 1), ("event_type", 1)]).to_list(100)
        
        # Also add defaults that aren't in DB
        existing_keys = {(t["channel"], t["event_type"]) for t in templates}
        
        for (ch, evt), default in DEFAULT_TEMPLATES.items():
            if (ch, evt) not in existing_keys:
                if not channel or ch == channel:
                    templates.append({
                        "id": None,
                        "channel": ch,
                        "event_type": evt,
                        "title": default["title"],
                        "template_body": default["template_body"],
                        "default_template_body": default["template_body"],
                        "enabled": True,
                        "is_default": True,
                    })
        
        return templates
    
    async def get_template(self, channel: str, event_type: str) -> Optional[Dict[str, Any]]:
        """Get a specific template by channel and event type."""
        template = await self.db.notification_templates.find_one(
            {"channel": channel, "event_type": event_type},
            {"_id": 0}
        )
        
        if template:
            return template
        
        # Return default if available
        default_key = (channel, event_type)
        if default_key in DEFAULT_TEMPLATES:
            default = DEFAULT_TEMPLATES[default_key]
            return {
                "id": None,
                "channel": channel,
                "event_type": event_type,
                "title": default["title"],
                "template_body": default["template_body"],
                "default_template_body": default["template_body"],
                "enabled": True,
                "is_default": True,
            }
        
        return None
    
    async def update_template(
        self,
        channel: str,
        event_type: str,
        title: Optional[str] = None,
        template_body: Optional[str] = None,
        enabled: Optional[bool] = None,
        updated_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update or create a template."""
        import uuid as uuid_mod
        
        # Validate template if body provided
        if template_body:
            invalid_vars = self.engine.validate_template(template_body)
            if invalid_vars:
                raise ValueError(f"Invalid variables: {', '.join(invalid_vars)}")
        
        # Get existing or default
        existing = await self.db.notification_templates.find_one(
            {"channel": channel, "event_type": event_type}
        )
        
        # Get default body
        default_key = (channel, event_type)
        default_body = DEFAULT_TEMPLATES.get(default_key, {}).get("template_body", "")
        default_title = DEFAULT_TEMPLATES.get(default_key, {}).get("title", "")
        
        if existing:
            # Update existing
            update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
            if title is not None:
                update_data["title"] = title
            if template_body is not None:
                update_data["template_body"] = template_body
            if enabled is not None:
                update_data["enabled"] = enabled
            if updated_by:
                update_data["updated_by"] = updated_by
            
            await self.db.notification_templates.update_one(
                {"channel": channel, "event_type": event_type},
                {"$set": update_data}
            )
            
            # Clear cache
            self.engine.clear_cache()
            
            # Return updated
            return await self.get_template(channel, event_type)
        else:
            # Create new
            template = {
                "id": str(uuid_mod.uuid4()),
                "channel": channel,
                "event_type": event_type,
                "title": title or default_title,
                "template_body": template_body or default_body,
                "default_template_body": default_body,
                "enabled": enabled if enabled is not None else True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": updated_by,
            }
            await self.db.notification_templates.insert_one(template)
            
            # Clear cache
            self.engine.clear_cache()
            
            # Return without _id
            template.pop("_id", None)
            return template
    
    async def reset_template(self, channel: str, event_type: str) -> Dict[str, Any]:
        """Reset a template to its default."""
        default_key = (channel, event_type)
        if default_key not in DEFAULT_TEMPLATES:
            raise ValueError(f"No default template for {channel}/{event_type}")
        
        default = DEFAULT_TEMPLATES[default_key]
        
        # Update to default values
        await self.db.notification_templates.update_one(
            {"channel": channel, "event_type": event_type},
            {
                "$set": {
                    "template_body": default["template_body"],
                    "title": default["title"],
                    "enabled": True,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "reset_at": datetime.now(timezone.utc).isoformat(),
                }
            },
            upsert=True
        )
        
        # Clear cache
        self.engine.clear_cache()
        
        return await self.get_template(channel, event_type)
    
    async def preview_template(
        self,
        channel: str,
        event_type: str,
        template_body: Optional[str] = None,
    ) -> str:
        """Preview a template with sample data."""
        # Get template if body not provided
        if not template_body:
            template = await self.get_template(channel, event_type)
            if not template:
                raise ValueError(f"Template not found: {channel}/{event_type}")
            template_body = template.get("template_body", "")
        
        # Build sample context
        sample_context = build_notification_context(
            user={"display_name": "John Doe", "email": "john@example.com", "role": "manager", "id": "user-123"},
            network={"name": "Main SEO Network", "id": "net-123", "description": "Primary network for main brand"},
            brand={"name": "PANEN77", "id": "brand-123"},
            node={"domain_name": "example.com", "full_path": "/blog/article", "domain_role": "supporting", "tier": "Tier 2", "domain_status": "canonical"},
            change={"action": "update_node", "action_label": "Mengubah Node", "reason": "Memperbaiki struktur linking untuk meningkatkan authority flow", "before": "Canonical", "after": "301 Redirect", "details": "• Target Sebelumnya: old-target.com\n• Target Baru: new-target.com"},
            optimization={"title": "Backlink Campaign Q4", "description": "Menambahkan 50 backlink berkualitas dari situs authority tinggi", "activity_type": "backlink_campaign", "status": "in_progress", "affected_targets": ["page1.com/landing", "page2.com/promo"], "keywords": ["slot online", "casino bonus"], "report_urls": ["https://docs.google.com/report-123"], "expected_impact": ["traffic_increase", "ranking_improvement"]},
            complaint={"reason": "Deadline tidak tercapai dan tidak ada komunikasi", "priority": "high", "category": "deadline", "report_urls": ["https://docs.google.com/evidence"]},
            domain={"domain_name": "example.com", "expiry_date": "2026-03-15", "days_until_expiry": "30", "registrar": "Namecheap", "status": "active", "http_status": "200"},
            impact={"severity": "HIGH", "description": "Affects tier 1-2 nodes", "affected_count": 5},
            structure={"current": "LP / Money Site:\n  • moneysite.com [Primary]\nTier 1:\n  • tier1.com [301 Redirect] → moneysite.com", "upstream_chain": "example.com → tier1.com → moneysite.com", "downstream_impact": "3 nodes affected"},
            reminder={"days_in_progress": 7, "optimization_title": "Content Update Campaign", "optimization_status": "In Progress"},
            telegram_leaders=["seo_leader1", "seo_leader2"],
            telegram_project_managers=["manager1", "manager2"],
            telegram_tagged_users=["user1", "user2"],
        )
        
        # Render template
        return self.engine.render(template_body, sample_context)
    
    def get_available_events(self) -> List[Dict[str, str]]:
        """Get list of available event types with descriptions."""
        return [
            {"channel": "telegram", "event_type": "seo_change", "description": "SEO structure changes (create/update/delete node)"},
            {"channel": "telegram", "event_type": "seo_network_created", "description": "New SEO network created"},
            {"channel": "telegram", "event_type": "seo_optimization", "description": "New optimization activity added"},
            {"channel": "telegram", "event_type": "seo_optimization_status", "description": "Optimization status changed (completed/reverted)"},
            {"channel": "telegram", "event_type": "seo_complaint", "description": "Complaint on optimization"},
            {"channel": "telegram", "event_type": "seo_project_complaint", "description": "Project-level complaint"},
            {"channel": "telegram", "event_type": "seo_reminder", "description": "Reminder for in-progress optimization"},
            {"channel": "telegram", "event_type": "domain_expiration", "description": "Domain expiration warning"},
            {"channel": "telegram", "event_type": "domain_down", "description": "Domain down alert"},
            {"channel": "telegram", "event_type": "seo_node_deleted", "description": "SEO node deleted notification"},
            {"channel": "telegram", "event_type": "test", "description": "Test notification"},
        ]


# ==================== GLOBAL INSTANCE ====================

_template_crud: Optional[NotificationTemplateCRUD] = None


def get_template_crud(db: AsyncIOMotorDatabase) -> NotificationTemplateCRUD:
    """Get or create the template CRUD service."""
    global _template_crud
    if _template_crud is None:
        _template_crud = NotificationTemplateCRUD(db)
    return _template_crud


async def render_notification(
    db: AsyncIOMotorDatabase,
    channel: str,
    event_type: str,
    context_data: Dict[str, Any],
) -> Optional[str]:
    """
    Render a notification using the template system.
    
    This is the main entry point for services to render notifications.
    Automatically handles:
    - Template lookup from database
    - Fallback to default template
    - Variable substitution
    - Enabled/disabled checks
    
    Args:
        db: Database connection
        channel: "telegram" or "email"
        event_type: The event type (e.g., "seo_change", "seo_optimization")
        context_data: Context data to pass to build_notification_context()
    
    Returns:
        Rendered template string, or None if template is disabled
    """
    try:
        logger.info(f"Rendering notification template: {channel}/{event_type}")
        
        crud = get_template_crud(db)
        template = await crud.get_template(channel, event_type)
        
        if not template:
            logger.warning(f"No template found for {channel}/{event_type}")
            return None
        
        # Check if enabled
        if template.get("enabled") is False:
            logger.info(f"Template {channel}/{event_type} is disabled, skipping")
            return None
        
        logger.info(f"Template found: {template.get('title', 'N/A')}, is_default: {template.get('is_default', False)}")
        
        # Build context from data
        context = build_notification_context(**context_data)
        
        # Render template
        engine = NotificationTemplateEngine(db)
        rendered = engine.render(template.get("template_body", ""), context)
        
        logger.info(f"Template rendered successfully, length: {len(rendered)} chars")
        return rendered
    except Exception as e:
        logger.error(f"Failed to render notification {channel}/{event_type}: {e}", exc_info=True)
        # Return None to allow services to fall back to hardcoded templates
        return None
