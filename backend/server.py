from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi import status as fastapi_status
from fastapi import BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from enum import Enum
import httpx
import asyncio
from contextlib import asynccontextmanager

# Import action/entity types for activity logging
from models_v3 import ActionType, EntityType

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# MongoDB connection
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# JWT Settings
JWT_SECRET = os.environ.get("JWT_SECRET", "seo-nexus-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Background monitoring state
monitoring_tasks = {}

# V3 Services
from services.activity_log_service import init_activity_log_service
from services.tier_service import init_tier_service
from services.seo_change_log_service import SeoChangeLogService
from services.seo_telegram_service import SeoTelegramService
from services.reminder_scheduler import init_reminder_scheduler, get_reminder_scheduler
from routers.v3_router import router as v3_router, init_v3_router

# Initialize V3 services
activity_log_service = init_activity_log_service(db)
seo_change_log_service = SeoChangeLogService(db)
seo_telegram_service = SeoTelegramService(db)
tier_service = init_tier_service(db)


# Create the main app with lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting SEO-NOC application...")
    await initialize_default_categories()

    # Seed default super admin if needed
    await seed_default_super_admin()

    # Create database indexes for performance
    await create_database_indexes()

    # Start V3 monitoring scheduler (two independent engines)
    from services.monitoring_service import MonitoringScheduler

    monitoring_scheduler = MonitoringScheduler(db)
    asyncio.create_task(monitoring_scheduler.start())
    logger.info("V3 Monitoring Scheduler started (Expiration + Availability engines)")

    # Start Reminder Scheduler for In-Progress optimizations
    from services.seo_optimization_telegram_service import (
        init_seo_optimization_telegram_service,
    )

    # Initialize the optimization telegram service
    optimization_telegram_service = init_seo_optimization_telegram_service(db)
    
    reminder_scheduler = init_reminder_scheduler(
        db, telegram_service=optimization_telegram_service
    )
    reminder_scheduler.start()
    logger.info("Optimization Reminder Scheduler started")

    # Start Team Performance Check Scheduler (daily)
    from services.team_performance_alert_service import get_team_performance_service
    
    async def run_performance_check():
        """Background task to check team performance daily."""
        try:
            service = get_team_performance_service(db)
            result = await service.check_performance_and_alert()
            if result.get("alerts_sent", 0) > 0:
                logger.info(f"Team performance alerts sent: {result['alerts_sent']}")
            else:
                logger.debug("Team performance check: no alerts needed")
        except Exception as e:
            logger.error(f"Team performance check failed: {e}")
    
    # Schedule daily performance check
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    
    performance_scheduler = AsyncIOScheduler()
    performance_scheduler.add_job(
        run_performance_check,
        trigger=CronTrigger(hour=9, minute=0),  # Daily at 9:00 AM
        id="team_performance_check",
        replace_existing=True
    )
    performance_scheduler.start()
    logger.info("Team Performance Check Scheduler started (daily at 9:00 AM)")

    logger.info(
        "V3 services initialized: ActivityLog, TierCalculation, Monitoring, Reminders"
    )
    yield
    # Shutdown
    logger.info("Shutting down SEO-NOC application...")

    # Stop reminder scheduler gracefully
    if get_reminder_scheduler():
        get_reminder_scheduler().stop()

    client.close()


async def create_database_indexes():
    """Create database indexes for optimal query performance"""
    try:
        # Users indexes
        await db.users.create_index("email", unique=True)
        await db.users.create_index("id", unique=True)
        await db.users.create_index("role")
        await db.users.create_index("status")

        # Brands indexes
        await db.brands.create_index("id", unique=True)
        await db.brands.create_index("status")
        await db.brands.create_index("name")

        # Asset domains indexes for pagination and filtering
        await db.asset_domains.create_index("id", unique=True)
        await db.asset_domains.create_index("domain_name")
        await db.asset_domains.create_index("brand_id")
        await db.asset_domains.create_index("status")
        await db.asset_domains.create_index("lifecycle_status")
        await db.asset_domains.create_index("monitoring_status")
        await db.asset_domains.create_index("domain_active_status")
        await db.asset_domains.create_index("created_at")
        await db.asset_domains.create_index("expiration_date")
        await db.asset_domains.create_index([("domain_name", 1), ("brand_id", 1)])
        await db.asset_domains.create_index([("brand_id", 1), ("created_at", -1)])

        # SEO structure entries indexes
        await db.seo_structure_entries.create_index("id", unique=True)
        await db.seo_structure_entries.create_index("network_id")
        await db.seo_structure_entries.create_index("asset_domain_id")
        await db.seo_structure_entries.create_index("tier")
        await db.seo_structure_entries.create_index([("network_id", 1), ("asset_domain_id", 1)])

        # SEO networks indexes
        await db.seo_networks.create_index("id", unique=True)
        await db.seo_networks.create_index("brand_id")
        await db.seo_networks.create_index("name")
        await db.seo_networks.create_index("created_at")
        await db.seo_networks.create_index([("brand_id", 1), ("created_at", -1)])

        # SEO optimizations indexes
        await db.seo_optimizations.create_index("id", unique=True)
        await db.seo_optimizations.create_index("network_id")
        await db.seo_optimizations.create_index("brand_id")
        await db.seo_optimizations.create_index("status")
        await db.seo_optimizations.create_index("created_at")
        await db.seo_optimizations.create_index([("network_id", 1), ("created_at", -1)])
        await db.seo_optimizations.create_index([("brand_id", 1), ("status", 1)])

        # SEO conflicts indexes
        await db.seo_conflicts.create_index("id", unique=True)
        await db.seo_conflicts.create_index("network_id")
        await db.seo_conflicts.create_index("status")
        await db.seo_conflicts.create_index("severity")
        await db.seo_conflicts.create_index("created_at")
        await db.seo_conflicts.create_index([("network_id", 1), ("status", 1)])

        # Activity logs indexes
        await db.activity_logs.create_index("created_at")
        await db.activity_logs.create_index("user_id")
        await db.activity_logs.create_index([("created_at", -1)])

        # Audit logs indexes
        await db.audit_logs.create_index("timestamp")
        await db.audit_logs.create_index([("timestamp", -1)])

        # Categories and Registrars indexes
        await db.categories.create_index("id", unique=True)
        await db.registrars.create_index("id", unique=True)

        logger.info("Database indexes created/verified")
    except Exception as e:
        logger.warning(f"Index creation warning (may already exist): {e}")


app = FastAPI(title="SEO-NOC API", lifespan=lifespan)

@app.get("/api/health")
async def health_check():
    """
    Health check endpoint
    Used by Docker / infrastructure monitoring
    """
    return {"status": "ok"}

api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# ==================== ENUMS ====================


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"


class BrandStatus(str, Enum):
    """Status of brand"""

    ACTIVE = "active"
    ARCHIVED = "archived"


class DomainStatus(str, Enum):
    CANONICAL = "canonical"
    REDIRECT_301 = "301_redirect"
    REDIRECT_302 = "302_redirect"
    RESTORE = "restore"


class IndexStatus(str, Enum):
    INDEX = "index"
    NOINDEX = "noindex"


class TierLevel(str, Enum):
    TIER_5 = "tier_5"
    TIER_4 = "tier_4"
    TIER_3 = "tier_3"
    TIER_2 = "tier_2"
    TIER_1 = "tier_1"
    LP_MONEY_SITE = "lp_money_site"


class MonitoringInterval(str, Enum):
    FIVE_MIN = "5min"
    FIFTEEN_MIN = "15min"
    ONE_HOUR = "1hour"
    DAILY = "daily"


class PingStatus(str, Enum):
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class HttpStatus(str, Enum):
    OK_200 = "200"
    REDIRECT_3XX = "3xx"
    CLIENT_ERROR_4XX = "4xx"
    SERVER_ERROR_5XX = "5xx"
    TIMEOUT = "timeout"
    ERROR = "error"


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertType(str, Enum):
    MONITORING = "monitoring"
    EXPIRATION = "expiration"
    SEO_CONFLICT = "seo_conflict"


# Tier hierarchy for validation
TIER_HIERARCHY = {
    "tier_5": 5,
    "tier_4": 4,
    "tier_3": 3,
    "tier_2": 2,
    "tier_1": 1,
    "lp_money_site": 0,
}

# Monitoring intervals in seconds
INTERVAL_SECONDS = {"5min": 300, "15min": 900, "1hour": 3600, "daily": 86400}

# Default categories
DEFAULT_CATEGORIES = [
    {"name": "Fresh Domain", "description": "Newly registered domain"},
    {"name": "Aged Domain", "description": "Domain with history and age"},
    {"name": "Redirect Domain", "description": "Domain used for redirects"},
    {"name": "AMP Domain", "description": "AMP-enabled domain"},
    {"name": "Money Site", "description": "Primary revenue-generating site"},
    {"name": "Subdomain Money Site", "description": "Subdomain of money site"},
    {"name": "PBN", "description": "Private Blog Network domain"},
    {"name": "Parking", "description": "Parked domain"},
]

# ==================== MODELS ====================


class UserStatus(str, Enum):
    """User account status for approval workflow and access control"""

    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"  # Soft disabled - preserves history
    REJECTED = "rejected"
    SUSPENDED = "suspended"  # Future use - policy violations


class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: UserRole = UserRole.VIEWER
    brand_scope_ids: Optional[List[str]] = (
        None  # NULL = Super Admin (all brands), array = restricted to specific brands
    )
    status: UserStatus = UserStatus.PENDING  # Default to pending for new registrations


class UserCreate(UserBase):
    password: str
    telegram_username: Optional[str] = None


class UserUpdate(BaseModel):
    """Model for updating user"""

    name: Optional[str] = None
    role: Optional[UserRole] = None
    brand_scope_ids: Optional[List[str]] = None
    status: Optional[UserStatus] = None
    telegram_username: Optional[str] = None


class UserResponse(UserBase):
    model_config = ConfigDict(extra="ignore")
    id: str
    telegram_username: Optional[str] = None
    created_at: str
    updated_at: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None


class UserApprovalRequest(BaseModel):
    """Request model for approving a user"""

    role: UserRole
    brand_scope_ids: List[str] = []


class UserManualCreate(BaseModel):
    """Model for Super Admin to manually create a user"""

    email: EmailStr
    name: str
    role: UserRole = UserRole.VIEWER
    brand_scope_ids: List[str] = []
    password: Optional[str] = None  # If not provided, auto-generate
    telegram_username: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = ""


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    model_config = ConfigDict(extra="ignore")
    id: str
    created_at: str
    updated_at: str


class BrandBase(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = ""
    status: BrandStatus = BrandStatus.ACTIVE
    notes: Optional[str] = ""


class BrandCreate(BrandBase):
    pass


class BrandUpdate(BaseModel):
    """Model for updating brand"""

    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    status: Optional[BrandStatus] = None
    notes: Optional[str] = None


class BrandResponse(BrandBase):
    model_config = ConfigDict(extra="ignore")
    id: str
    created_at: str
    updated_at: str


# Asset Domain with full monitoring fields
class DomainBase(BaseModel):
    domain_name: str
    brand_id: str
    category_id: Optional[str] = None
    # SEO Structure fields
    domain_status: DomainStatus = DomainStatus.CANONICAL
    index_status: IndexStatus = IndexStatus.INDEX
    tier_level: TierLevel = TierLevel.TIER_5
    group_id: Optional[str] = None
    parent_domain_id: Optional[str] = None
    # Asset Management fields
    registrar: Optional[str] = None
    expiration_date: Optional[str] = None
    auto_renew: bool = False
    # Monitoring fields
    monitoring_enabled: bool = False
    monitoring_interval: MonitoringInterval = MonitoringInterval.ONE_HOUR
    last_check: Optional[str] = None
    ping_status: PingStatus = PingStatus.UNKNOWN
    http_status: Optional[str] = None
    http_status_code: Optional[int] = None
    # Notes
    notes: Optional[str] = ""


class DomainCreate(DomainBase):
    pass


class DomainUpdate(BaseModel):
    domain_name: Optional[str] = None
    brand_id: Optional[str] = None
    category_id: Optional[str] = None
    domain_status: Optional[DomainStatus] = None
    index_status: Optional[IndexStatus] = None
    tier_level: Optional[TierLevel] = None
    group_id: Optional[str] = None
    parent_domain_id: Optional[str] = None
    registrar: Optional[str] = None
    expiration_date: Optional[str] = None
    auto_renew: Optional[bool] = None
    monitoring_enabled: Optional[bool] = None
    monitoring_interval: Optional[MonitoringInterval] = None
    notes: Optional[str] = None


class DomainResponse(DomainBase):
    model_config = ConfigDict(extra="ignore")
    id: str
    brand_name: Optional[str] = None
    category_name: Optional[str] = None
    group_name: Optional[str] = None
    created_at: str
    updated_at: str


class GroupBase(BaseModel):
    name: str
    description: Optional[str] = ""


class GroupCreate(GroupBase):
    pass


class GroupResponse(GroupBase):
    model_config = ConfigDict(extra="ignore")
    id: str
    domain_count: int = 0
    created_at: str
    updated_at: str


class GroupDetail(GroupResponse):
    domains: List[DomainResponse] = []


class AlertBase(BaseModel):
    domain_id: str
    domain_name: str
    brand_name: Optional[str] = None
    category_name: Optional[str] = None
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    details: Dict[str, Any] = {}


class AlertResponse(AlertBase):
    model_config = ConfigDict(extra="ignore")
    id: str
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None
    muted_until: Optional[str] = None
    created_at: str


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    user_email: str
    action: str
    entity_type: str
    entity_id: str
    details: Dict[str, Any]
    created_at: str


class TelegramConfig(BaseModel):
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None


class AppBrandingSettings(BaseModel):
    """App branding settings - title, description, logo, tagline"""

    site_title: Optional[str] = None
    site_description: Optional[str] = None
    logo_url: Optional[str] = None
    tagline: Optional[str] = None


class TimezoneSettings(BaseModel):
    """Timezone settings for monitoring display"""

    default_timezone: str = "Asia/Jakarta"
    timezone_label: str = "GMT+7"


class MonitoringStats(BaseModel):
    total_monitored: int = 0
    up_count: int = 0
    down_count: int = 0
    unknown_count: int = 0
    expiring_soon: int = 0
    expired: int = 0


# ==================== TIMEZONE HELPER ====================


def format_to_local_time(dt_str: str, timezone_str: str = "Asia/Jakarta") -> str:
    """
    Convert UTC datetime string to local timezone for display.
    Storage remains UTC - this is DISPLAY-LEVEL only.

    Args:
        dt_str: ISO format datetime string (UTC)
        timezone_str: Target timezone (default: Asia/Jakarta = GMT+7)

    Returns:
        Formatted string like "2026-02-09 23:02 GMT+7 (Asia/Jakarta)"
    """
    try:
        from zoneinfo import ZoneInfo

        # Parse the datetime string
        if isinstance(dt_str, str):
            # Handle various formats
            if "T" in dt_str:
                dt_str = dt_str.replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(dt_str)
            except (ValueError, TypeError):
                dt = datetime.strptime(dt_str[:19], "%Y-%m-%d %H:%M:%S")
                dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt_str

        # If naive datetime, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # Convert to target timezone
        local_tz = ZoneInfo(timezone_str)
        local_dt = dt.astimezone(local_tz)

        # Format with timezone label
        tz_label = "GMT+7" if timezone_str == "Asia/Jakarta" else timezone_str
        return f"{local_dt.strftime('%Y-%m-%d %H:%M')} {tz_label} ({timezone_str})"
    except Exception as e:
        logger.warning(f"Timezone conversion error: {e}")
        return dt_str  # Return original if conversion fails


async def get_system_timezone() -> tuple:
    """Get the configured system timezone from settings"""
    settings = await db.settings.find_one({"key": "timezone"}, {"_id": 0})
    if settings:
        return settings.get("default_timezone", "Asia/Jakarta"), settings.get(
            "timezone_label", "GMT+7"
        )
    return "Asia/Jakarta", "GMT+7"


# ==================== HELPER FUNCTIONS ====================


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")

        # Check if user is still active (invalidate token if deactivated)
        user_status = user.get("status", "active")
        if user_status == "inactive":
            raise HTTPException(
                status_code=403,
                detail="User account is inactive. Please contact administrator.",
            )
        if user_status == "suspended":
            raise HTTPException(
                status_code=403,
                detail="User account is suspended. Please contact administrator.",
            )
        if user_status not in ["active"]:
            raise HTTPException(
                status_code=403,
                detail="User account is not active. Please contact administrator.",
            )

        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_roles(allowed_roles: List[UserRole]):
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in [r.value for r in allowed_roles]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

    return role_checker


# ==================== BRAND SCOPING HELPERS ====================


def get_user_brand_scope(user: dict) -> Optional[List[str]]:
    """
    Get user's brand scope.
    Returns None for Super Admin (full access), or list of brand_ids for restricted users.
    """
    if user.get("role") == UserRole.SUPER_ADMIN.value:
        return None  # Full access
    return user.get("brand_scope_ids") or []


def build_brand_filter(user: dict, brand_field: str = "brand_id") -> dict:
    """
    Build MongoDB filter for brand scoping.
    Super Admin: no filter (empty dict)
    Others: filter by brand_scope_ids
    """
    brand_scope = get_user_brand_scope(user)
    if brand_scope is None:
        return {}  # Super Admin - no filter
    if not brand_scope:
        return {brand_field: {"$in": []}}  # No brands = no access
    return {brand_field: {"$in": brand_scope}}


def check_brand_access(user: dict, brand_id: str) -> bool:
    """
    Check if user has access to a specific brand.
    Returns True for Super Admin or if brand_id is in user's scope.
    """
    brand_scope = get_user_brand_scope(user)
    if brand_scope is None:
        return True  # Super Admin
    return brand_id in brand_scope


def require_brand_access(brand_id: str, user: dict):
    """
    Raise 403 if user doesn't have access to the brand.
    """
    if not check_brand_access(user, brand_id):
        raise HTTPException(status_code=403, detail="Access denied for this brand.")


async def log_audit(
    user_id: str,
    user_email: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict,
):
    audit_log = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "user_email": user_email,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.audit_logs.insert_one(audit_log)


def calculate_severity(domain: dict) -> AlertSeverity:
    """Calculate alert severity based on tier and category"""
    category_name = domain.get("category_name", "").lower()
    tier = domain.get("tier_level", "tier_5")

    # Money Site categories are always CRITICAL
    if "money site" in category_name or "money_site" in category_name:
        return AlertSeverity.CRITICAL

    # LP/Money Site tier is CRITICAL
    if tier == "lp_money_site":
        return AlertSeverity.CRITICAL

    # Tier 1-2 are HIGH
    if tier in ["tier_1", "tier_2"]:
        return AlertSeverity.HIGH

    # Tier 3-4 are MEDIUM
    if tier in ["tier_3", "tier_4"]:
        return AlertSeverity.MEDIUM

    # Tier 5 and others are LOW
    return AlertSeverity.LOW


async def send_telegram_alert(message: str):
    """Send alert to Telegram"""
    bot_token = TELEGRAM_BOT_TOKEN
    chat_id = TELEGRAM_CHAT_ID

    # Try to get from settings collection
    settings = await db.settings.find_one({"key": "telegram"}, {"_id": 0})
    if settings:
        bot_token = settings.get("bot_token", bot_token)
        chat_id = settings.get("chat_id", chat_id)

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


def format_monitoring_alert(domain: dict, error_type: str, previous_status: str) -> str:
    """Format monitoring alert for Telegram"""
    seo_structure = "Not assigned"
    if domain.get("group_id"):
        tier = domain.get("tier_level", "unknown").replace("_", " ").title()
        relation = domain.get("domain_status", "canonical").replace("_", " ")
        parent = domain.get("parent_domain_name", "N/A")
        seo_structure = f"{tier} ({relation} → {parent})"

    severity = calculate_severity(domain)

    return f"""⚠️ <b>DOMAIN ALERT</b>

Domain        : <code>{domain.get('domain_name', 'Unknown')}</code>
Brand         : {domain.get('brand_name', 'N/A')}
Category      : {domain.get('category_name', 'N/A')}
SEO Structure : {seo_structure}

Issue         : {error_type}
Last Status   : {previous_status} → DOWN
Checked At    : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
Severity      : <b>{severity.value.upper()}</b>"""


def format_expiration_alert(domain: dict, days_remaining: int) -> str:
    """Format expiration alert for Telegram"""
    severity = (
        "CRITICAL"
        if days_remaining <= 0
        else ("WARNING" if days_remaining <= 7 else "MEDIUM")
    )
    if domain.get("tier_level") in ["lp_money_site", "tier_1"]:
        severity = "CRITICAL"

    return f"""⏰ <b>DOMAIN EXPIRATION ALERT</b>

Domain     : <code>{domain.get('domain_name', 'Unknown')}</code>
Brand      : {domain.get('brand_name', 'N/A')}
Category   : {domain.get('category_name', 'N/A')}
Registrar  : {domain.get('registrar', 'N/A')}

Expires In : {days_remaining} days
Expire On  : {domain.get('expiration_date', 'N/A')}
Severity   : <b>{severity}</b>"""


def format_seo_conflict_alert(domain: dict, conflict_type: str, details: str) -> str:
    """Format SEO conflict alert for Telegram"""
    return f"""⚠️ <b>SEO STRUCTURE ALERT</b>

Domain        : <code>{domain.get('domain_name', 'Unknown')}</code>
Brand         : {domain.get('brand_name', 'N/A')}
Network       : {domain.get('group_name', 'N/A')}
Tier          : {domain.get('tier_level', 'N/A').replace('_', ' ').title()}

Issue         : {conflict_type}
Details       : {details}
Detected At   : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
Severity      : <b>HIGH</b>"""


async def create_alert(
    domain: dict, alert_type: AlertType, title: str, message: str, details: dict = {}
):
    """Create alert in database and send to Telegram"""
    severity = calculate_severity(domain)

    # Check if domain is muted
    mute = await db.muted_domains.find_one(
        {
            "domain_id": domain["id"],
            "muted_until": {"$gt": datetime.now(timezone.utc).isoformat()},
        },
        {"_id": 0},
    )

    if mute:
        logger.info(f"Domain {domain['domain_name']} is muted, skipping alert")
        return None

    # Check for recent similar alert (cooldown)
    recent = await db.alerts.find_one(
        {
            "domain_id": domain["id"],
            "alert_type": alert_type.value,
            "created_at": {
                "$gt": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
            },
        },
        {"_id": 0},
    )

    if recent and not recent.get("acknowledged"):
        logger.info(
            f"Recent unacknowledged alert exists for {domain['domain_name']}, skipping"
        )
        return None

    alert = {
        "id": str(uuid.uuid4()),
        "domain_id": domain["id"],
        "domain_name": domain.get("domain_name", "Unknown"),
        "brand_name": domain.get("brand_name"),
        "category_name": domain.get("category_name"),
        "alert_type": alert_type.value,
        "severity": severity.value,
        "title": title,
        "message": message,
        "details": details,
        "acknowledged": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.alerts.insert_one(alert)

    # Send Telegram notification
    if alert_type == AlertType.MONITORING:
        telegram_msg = format_monitoring_alert(
            domain, title, details.get("previous_status", "unknown")
        )
    elif alert_type == AlertType.EXPIRATION:
        telegram_msg = format_expiration_alert(domain, details.get("days_remaining", 0))
    else:
        telegram_msg = format_seo_conflict_alert(domain, title, message)

    await send_telegram_alert(telegram_msg)

    return alert


# ==================== MONITORING SERVICE ====================


async def check_domain_health(domain: dict):
    """Check domain ping and HTTP status"""
    domain_name = domain.get("domain_name", "")
    if not domain_name:
        return

    url = f"https://{domain_name}"
    previous_ping = domain.get("ping_status", "unknown")

    new_ping = PingStatus.DOWN
    new_http_status = "error"
    new_http_code = None

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            response = await client.get(url)
            new_http_code = response.status_code

            if 200 <= response.status_code < 300:
                new_ping = PingStatus.UP
                new_http_status = "200"
            elif 300 <= response.status_code < 400:
                new_ping = PingStatus.UP
                new_http_status = "3xx"
            elif 400 <= response.status_code < 500:
                new_ping = PingStatus.DOWN
                new_http_status = "4xx"
            else:
                new_ping = PingStatus.DOWN
                new_http_status = "5xx"

    except httpx.TimeoutException:
        new_http_status = "timeout"
    except Exception as e:
        logger.error(f"Error checking {domain_name}: {e}")
        new_http_status = "error"

    # Update domain
    await db.domains.update_one(
        {"id": domain["id"]},
        {
            "$set": {
                "ping_status": new_ping.value,
                "http_status": new_http_status,
                "http_status_code": new_http_code,
                "last_check": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    # Create alert if status changed to DOWN
    if new_ping == PingStatus.DOWN and previous_ping != PingStatus.DOWN.value:
        # Enrich domain with names
        brand = await db.brands.find_one(
            {"id": domain.get("brand_id")}, {"_id": 0, "name": 1}
        )
        category = await db.categories.find_one(
            {"id": domain.get("category_id")}, {"_id": 0, "name": 1}
        )
        group = await db.groups.find_one(
            {"id": domain.get("group_id")}, {"_id": 0, "name": 1}
        )

        enriched = {
            **domain,
            "brand_name": brand["name"] if brand else None,
            "category_name": category["name"] if category else None,
            "group_name": group["name"] if group else None,
        }

        await create_alert(
            enriched,
            AlertType.MONITORING,
            (
                f"HTTP {new_http_status.upper()}"
                if new_http_status != "error"
                else "Connection Error"
            ),
            f"Domain {domain_name} is unreachable",
            {
                "previous_status": previous_ping,
                "http_status": new_http_status,
                "http_code": new_http_code,
            },
        )

    logger.info(f"Checked {domain_name}: ping={new_ping.value}, http={new_http_status}")


async def check_domain_expiration(domain: dict):
    """Check domain expiration and create alerts"""
    expiration_str = domain.get("expiration_date")
    if not expiration_str:
        return

    try:
        expiration = datetime.fromisoformat(expiration_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days_remaining = (expiration - now).days

        # Trigger alerts at 7 days, 1 day, and 0 days
        if days_remaining in [7, 1, 0] or days_remaining < 0:
            brand = await db.brands.find_one(
                {"id": domain.get("brand_id")}, {"_id": 0, "name": 1}
            )
            category = await db.categories.find_one(
                {"id": domain.get("category_id")}, {"_id": 0, "name": 1}
            )

            enriched = {
                **domain,
                "brand_name": brand["name"] if brand else None,
                "category_name": category["name"] if category else None,
            }

            title = (
                "Domain Expired"
                if days_remaining <= 0
                else f"Expires in {days_remaining} days"
            )

            await create_alert(
                enriched,
                AlertType.EXPIRATION,
                title,
                f"Domain {domain['domain_name']} expiration warning",
                {"days_remaining": days_remaining, "expiration_date": expiration_str},
            )
    except Exception as e:
        logger.error(f"Error checking expiration for {domain.get('domain_name')}: {e}")


async def run_monitoring_cycle():
    """Run one cycle of domain monitoring"""
    logger.info("Starting monitoring cycle...")

    # Get all domains with monitoring enabled
    domains = await db.domains.find({"monitoring_enabled": True}, {"_id": 0}).to_list(
        10000
    )

    now = datetime.now(timezone.utc)

    for domain in domains:
        # Check if it's time to monitor based on interval
        last_check_str = domain.get("last_check")
        interval = domain.get("monitoring_interval", "1hour")
        interval_secs = INTERVAL_SECONDS.get(interval, 3600)

        should_check = True
        if last_check_str:
            try:
                last_check = datetime.fromisoformat(
                    last_check_str.replace("Z", "+00:00")
                )
                if (now - last_check).total_seconds() < interval_secs:
                    should_check = False
            except (ValueError, TypeError):
                pass

        if should_check:
            await check_domain_health(domain)

        # Always check expiration
        await check_domain_expiration(domain)

    logger.info(f"Monitoring cycle complete. Checked {len(domains)} domains.")


async def start_monitoring_scheduler():
    """Start the background monitoring scheduler"""
    logger.info("Starting monitoring scheduler...")
    while True:
        try:
            await run_monitoring_cycle()
        except Exception as e:
            logger.error(f"Monitoring cycle error: {e}")

        # Run every 5 minutes
        await asyncio.sleep(300)


async def initialize_default_categories():
    """Initialize default domain categories if none exist"""
    count = await db.categories.count_documents({})
    if count == 0:
        now = datetime.now(timezone.utc).isoformat()
        categories = [
            {
                "id": str(uuid.uuid4()),
                "name": cat["name"],
                "description": cat["description"],
                "created_at": now,
                "updated_at": now,
            }
            for cat in DEFAULT_CATEGORIES
        ]
        await db.categories.insert_many(categories)
        logger.info(f"Initialized {len(categories)} default categories")


# Default Super Admin credentials (can be overridden by environment variables)
DEFAULT_ADMIN_EMAIL = os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@seonoc.com")
DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "Admin@123!")
DEFAULT_ADMIN_NAME = os.environ.get("DEFAULT_ADMIN_NAME", "Super Admin")


async def seed_default_super_admin():
    """
    Seed default super admin user if no super_admin exists.
    This runs on every server startup but is safe - it won't create duplicates.
    """
    try:
        # Check if any super_admin exists
        existing_super_admin = await db.users.find_one({"role": "super_admin"})
        
        if existing_super_admin:
            logger.info(f"Super Admin exists: {existing_super_admin.get('email')}")
            return
        
        # Check if the default admin email already exists
        existing_user = await db.users.find_one({"email": DEFAULT_ADMIN_EMAIL})
        
        if existing_user:
            # User exists but is not super_admin - upgrade to super_admin
            logger.info(f"Upgrading {DEFAULT_ADMIN_EMAIL} to Super Admin role")
            await db.users.update_one(
                {"email": DEFAULT_ADMIN_EMAIL},
                {
                    "$set": {
                        "role": "super_admin",
                        "status": "active",
                        "brand_scope_ids": None,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            logger.info(f"User upgraded to Super Admin!")
            return
        
        # Create new default super admin
        logger.info("Creating default Super Admin user...")
        
        now = datetime.now(timezone.utc).isoformat()
        new_admin = {
            "id": str(uuid.uuid4()),
            "email": DEFAULT_ADMIN_EMAIL,
            "name": DEFAULT_ADMIN_NAME,
            "password": hash_password(DEFAULT_ADMIN_PASSWORD),
            "role": "super_admin",
            "status": "active",
            "brand_scope_ids": None,
            "telegram_username": None,
            "created_at": now,
            "updated_at": now,
            "approved_by": "system",
            "approved_at": now,
            "menu_permissions": None
        }
        
        await db.users.insert_one(new_admin)
        
        logger.info(f"Default Super Admin created: {DEFAULT_ADMIN_EMAIL}")
        logger.warning(f"Default password is: {DEFAULT_ADMIN_PASSWORD} - CHANGE IT AFTER FIRST LOGIN!")
        
    except Exception as e:
        logger.error(f"Failed to seed default admin: {e}")


# ==================== AUTH ENDPOINTS ====================


@api_router.post("/auth/register")
async def register(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_count = await db.users.count_documents({})

    # First user becomes Super Admin with active status
    is_first_user = user_count == 0
    role = UserRole.SUPER_ADMIN if is_first_user else UserRole.VIEWER
    status = UserStatus.ACTIVE if is_first_user else UserStatus.PENDING

    # Super Admin has NULL brand_scope_ids (full access)
    # Other roles start with empty brand_scope_ids (no access until approved)
    brand_scope_ids = None if role == UserRole.SUPER_ADMIN else []

    now = datetime.now(timezone.utc).isoformat()
    user = {
        "id": str(uuid.uuid4()),
        "email": user_data.email,
        "name": user_data.name,
        "password": hash_password(user_data.password),
        "role": role.value if isinstance(role, UserRole) else role,
        "status": status.value if isinstance(status, UserStatus) else status,
        "brand_scope_ids": brand_scope_ids,
        "telegram_username": user_data.telegram_username,
        "approved_by": None,
        "approved_at": None,
        "created_at": now,
        "updated_at": now,
    }
    await db.users.insert_one(user)

    # If pending, return message instead of token
    if status == UserStatus.PENDING:
        return {
            "message": "Registration successful. Your account is pending Super Admin approval.",
            "status": "pending",
            "email": user["email"],
        }

    # First user (Super Admin) gets token immediately
    token = create_token(user["id"], user["email"], user["role"])
    user_response = UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        role=user["role"],
        brand_scope_ids=user["brand_scope_ids"],
        status=user["status"],
        created_at=user["created_at"],
        updated_at=user["updated_at"],
    )
    return TokenResponse(access_token=token, user=user_response)


@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check user status
    user_status = user.get("status", "active")  # Default to active for existing users

    if user_status == "pending":
        raise HTTPException(
            status_code=403,
            detail="Your account is awaiting Super Admin approval. Please wait for approval to access the system.",
        )

    if user_status == "rejected":
        raise HTTPException(
            status_code=403,
            detail="Your account registration has been rejected. Please contact the administrator.",
        )

    if user_status == "inactive":
        raise HTTPException(
            status_code=403,
            detail="User account is inactive. Please contact administrator.",
        )

    if user_status == "suspended":
        raise HTTPException(
            status_code=403,
            detail="User account is suspended due to policy violation. Please contact administrator.",
        )

    token = create_token(user["id"], user["email"], user["role"])
    
    # Convert datetime objects to ISO strings if needed
    created_at = user.get("created_at")
    if hasattr(created_at, 'isoformat'):
        created_at = created_at.isoformat()
    elif created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()
    
    updated_at = user.get("updated_at")
    if hasattr(updated_at, 'isoformat'):
        updated_at = updated_at.isoformat()
    elif updated_at is None:
        updated_at = datetime.now(timezone.utc).isoformat()
    
    approved_at = user.get("approved_at")
    if hasattr(approved_at, 'isoformat'):
        approved_at = approved_at.isoformat()
    
    user_response = UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        role=user["role"],
        brand_scope_ids=user.get("brand_scope_ids"),
        status=user.get("status", "active"),
        telegram_username=user.get("telegram_username"),
        approved_by=user.get("approved_by"),
        approved_at=approved_at,
        created_at=created_at,
        updated_at=updated_at,
    )
    return TokenResponse(access_token=token, user=user_response)


@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(**current_user)


# ==================== USER MANAGEMENT ====================


@api_router.get("/users", response_model=List[UserResponse])
async def get_users(
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    users = await db.users.find({}, {"_id": 0, "password": 0}).to_list(1000)
    return [UserResponse(**{**u, "status": u.get("status", "active")}) for u in users]


@api_router.get("/users/pending", response_model=List[UserResponse])
async def get_pending_users(
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    """Get all users with pending status - Super Admin only"""
    users = await db.users.find(
        {"status": "pending"}, {"_id": 0, "password": 0}
    ).to_list(1000)
    return [UserResponse(**u) for u in users]


@api_router.post("/users/{user_id}/approve", response_model=UserResponse)
async def approve_user(
    user_id: str,
    approval: UserApprovalRequest,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    """Approve a pending user - Super Admin only"""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.get("status") != "pending":
        raise HTTPException(status_code=400, detail="User is not in pending status")

    now = datetime.now(timezone.utc).isoformat()

    # Validate role - cannot approve as Super Admin
    if approval.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=400, detail="Cannot approve user as Super Admin"
        )

    update_data = {
        "status": UserStatus.ACTIVE.value,
        "role": approval.role.value,
        "brand_scope_ids": approval.brand_scope_ids,
        "approved_by": current_user["id"],
        "approved_at": now,
        "updated_at": now,
    }

    await db.users.update_one({"id": user_id}, {"$set": update_data})

    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.USER,
            entity_id=user_id,
            after_value={
                "action": "user_approved",
                "role": approval.role.value,
                "brand_scope_ids": approval.brand_scope_ids,
            },
        )

    updated_user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    return UserResponse(**updated_user)


@api_router.post("/users/{user_id}/reject")
async def reject_user(
    user_id: str, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))
):
    """Reject a pending user - Super Admin only"""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.get("status") != "pending":
        raise HTTPException(status_code=400, detail="User is not in pending status")

    now = datetime.now(timezone.utc).isoformat()

    await db.users.update_one(
        {"id": user_id},
        {"$set": {"status": UserStatus.REJECTED.value, "updated_at": now}},
    )

    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.USER,
            entity_id=user_id,
            after_value={"action": "user_rejected"},
        )

    return {"message": "User rejected successfully"}


@api_router.post("/users/create", response_model=dict)
async def create_user_manually(
    user_data: UserManualCreate,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    """Manually create a user - Super Admin only. User is active immediately."""
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Validate role - cannot create Super Admin
    if user_data.role == UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=400, detail="Cannot create Super Admin user")

    # Use provided password or generate random one
    import secrets
    import string

    if user_data.password and len(user_data.password) >= 6:
        # Use manually provided password
        final_password = user_data.password
        password_was_generated = False
    else:
        # Generate random password
        password_chars = string.ascii_letters + string.digits + "!@#$%"
        final_password = "".join(secrets.choice(password_chars) for _ in range(12))
        password_was_generated = True

    now = datetime.now(timezone.utc).isoformat()
    user = {
        "id": str(uuid.uuid4()),
        "email": user_data.email,
        "name": user_data.name,
        "password": hash_password(final_password),
        "role": user_data.role.value,
        "status": UserStatus.ACTIVE.value,  # Active immediately
        "brand_scope_ids": user_data.brand_scope_ids,
        "telegram_username": user_data.telegram_username,
        "approved_by": current_user["id"],
        "approved_at": now,
        "created_at": now,
        "updated_at": now,
    }
    await db.users.insert_one(user)

    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.CREATE,
            entity_type=EntityType.USER,
            entity_id=user["id"],
            after_value={
                "action": "user_created_by_admin",
                "role": user_data.role.value,
                "brand_scope_ids": user_data.brand_scope_ids,
            },
        )

    response = {
        "message": "User created successfully",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "brand_scope_ids": user["brand_scope_ids"],
            "status": user["status"],
        },
        "password_was_generated": password_was_generated,
    }

    # Only return password if it was auto-generated (for security)
    if password_was_generated:
        response["generated_password"] = final_password

    return response


@api_router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))
):
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**{**user, "status": user.get("status", "active")})


@api_router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    """Update user - Super Admin only"""
    existing = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    update_dict = {k: v for k, v in user_data.model_dump().items() if v is not None}

    # Validate brand scoping rules
    new_role = update_dict.get("role", existing.get("role"))
    if hasattr(new_role, "value"):
        new_role = new_role.value
    update_dict["role"] = new_role

    # Super Admin must have NULL brand_scope_ids
    if new_role == UserRole.SUPER_ADMIN.value:
        update_dict["brand_scope_ids"] = None
    else:
        # Admin/Viewer must have at least one brand
        brand_scope = update_dict.get(
            "brand_scope_ids", existing.get("brand_scope_ids")
        )
        if not brand_scope or len(brand_scope) == 0:
            raise HTTPException(
                status_code=400,
                detail="Admin and Viewer users must have at least one brand assigned",
            )
        update_dict["brand_scope_ids"] = brand_scope

    update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = await db.users.find_one_and_update(
        {"id": user_id}, {"$set": update_dict}, return_document=True
    )

    await log_audit(
        current_user["id"],
        current_user["email"],
        "update",
        "user",
        user_id,
        {"before": existing, "after": update_dict},
    )
    return UserResponse(
        **{k: v for k, v in result.items() if k != "_id" and k != "password"}
    )


@api_router.delete("/users/{user_id}")
async def delete_user(
    user_id: str, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))
):
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    await log_audit(
        current_user["id"], current_user["email"], "delete", "user", user_id, {}
    )
    return {"message": "User deleted"}


class TelegramSettingsUpdate(BaseModel):
    """Update user's Telegram settings"""

    telegram_username: Optional[str] = None


@api_router.patch("/users/me/telegram")
async def update_my_telegram_settings(
    settings: TelegramSettingsUpdate, current_user: dict = Depends(get_current_user)
):
    """Update current user's Telegram settings"""
    update_dict = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if settings.telegram_username is not None:
        # Clean up the username (remove @ if present)
        username = settings.telegram_username.strip()
        if username.startswith("@"):
            username = username[1:]
        update_dict["telegram_username"] = username if username else None

    await db.users.update_one({"id": current_user["id"]}, {"$set": update_dict})

    return {
        "message": "Telegram settings updated",
        "telegram_username": update_dict.get("telegram_username"),
    }


@api_router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))
):
    """
    Deactivate a user - Super Admin only.
    User loses access immediately but all history is preserved.
    """
    # Prevent self-deactivation
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user is already inactive
    if user.get("status") == "inactive":
        raise HTTPException(status_code=400, detail="User is already inactive")

    # Prevent deactivating the last Super Admin
    if user.get("role") == UserRole.SUPER_ADMIN.value:
        active_super_admins = await db.users.count_documents(
            {"role": UserRole.SUPER_ADMIN.value, "status": "active"}
        )
        if active_super_admins <= 1:
            raise HTTPException(
                status_code=400,
                detail="At least one active Super Admin is required. Cannot deactivate the last Super Admin.",
            )

    now = datetime.now(timezone.utc).isoformat()
    before_status = user.get("status", "active")

    await db.users.update_one(
        {"id": user_id},
        {
            "$set": {
                "status": UserStatus.INACTIVE.value,
                "deactivated_by": current_user["id"],
                "deactivated_at": now,
                "updated_at": now,
            }
        },
    )

    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.USER,
            entity_id=user_id,
            before_value={"status": before_status},
            after_value={"action": "user_deactivated", "status": "inactive"},
        )

    return {
        "message": "User deactivated successfully",
        "user_id": user_id,
        "status": "inactive",
    }


@api_router.patch("/users/{user_id}/activate")
async def activate_user(
    user_id: str, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))
):
    """
    Reactivate a deactivated user - Super Admin only.
    User regains access based on their role and brand scope.
    """
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    current_status = user.get("status", "active")

    # Only allow activating inactive or suspended users
    if current_status not in ["inactive", "suspended"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot activate user with status '{current_status}'. Only inactive or suspended users can be activated.",
        )

    now = datetime.now(timezone.utc).isoformat()

    await db.users.update_one(
        {"id": user_id},
        {
            "$set": {
                "status": UserStatus.ACTIVE.value,
                "reactivated_by": current_user["id"],
                "reactivated_at": now,
                "updated_at": now,
            }
        },
    )

    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.USER,
            entity_id=user_id,
            before_value={"status": current_status},
            after_value={"action": "user_activated", "status": "active"},
        )

    return {
        "message": "User activated successfully",
        "user_id": user_id,
        "status": "active",
    }


# ==================== USER TELEGRAM SETTINGS ====================


@api_router.get("/users/{user_id}/telegram")
async def get_user_telegram_settings(
    user_id: str, current_user: dict = Depends(get_current_user)
):
    """Get Telegram settings for a user"""
    # Users can view their own, Super Admin can view any
    if user_id != current_user["id"] and current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    user = await db.users.find_one(
        {"id": user_id},
        {
            "_id": 0,
            "telegram_username": 1,
            "telegram_user_id": 1,
            "telegram_linked_at": 1,
        },
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "telegram_username": user.get("telegram_username"),
        "telegram_user_id": user.get("telegram_user_id"),
        "telegram_linked_at": user.get("telegram_linked_at"),
    }


@api_router.put("/users/{user_id}/telegram")
async def update_user_telegram_settings(
    user_id: str,
    telegram_username: Optional[str] = None,
    telegram_user_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Update Telegram settings for a user"""
    # Users can update their own, Super Admin can update any
    if user_id != current_user["id"] and current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(timezone.utc).isoformat()
    update_data = {"updated_at": now}

    if telegram_username is not None:
        # Clean up the username (remove @ if present)
        clean_username = (
            telegram_username.strip().lstrip("@") if telegram_username else None
        )
        update_data["telegram_username"] = clean_username
        if clean_username and not user.get("telegram_linked_at"):
            update_data["telegram_linked_at"] = now

    if telegram_user_id is not None:
        update_data["telegram_user_id"] = telegram_user_id

    await db.users.update_one({"id": user_id}, {"$set": update_data})

    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.USER,
            entity_id=user_id,
            after_value={
                "action": "telegram_settings_updated",
                "telegram_username": update_data.get("telegram_username"),
            },
        )

    return {"message": "Telegram settings updated"}


# ==================== CATEGORY ENDPOINTS ====================


@api_router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(current_user: dict = Depends(get_current_user)):
    categories = await db.categories.find({}, {"_id": 0}).to_list(1000)
    return [CategoryResponse(**c) for c in categories]


@api_router.post("/categories", response_model=CategoryResponse)
async def create_category(
    data: CategoryCreate,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    now = datetime.now(timezone.utc).isoformat()
    category = {
        "id": str(uuid.uuid4()),
        **data.model_dump(),
        "created_at": now,
        "updated_at": now,
    }
    await db.categories.insert_one(category)
    await log_audit(
        current_user["id"],
        current_user["email"],
        "create",
        "category",
        category["id"],
        data.model_dump(),
    )
    return CategoryResponse(**category)


@api_router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: str,
    data: CategoryCreate,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    result = await db.categories.find_one_and_update(
        {"id": category_id},
        {
            "$set": {
                **data.model_dump(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Category not found")
    await log_audit(
        current_user["id"],
        current_user["email"],
        "update",
        "category",
        category_id,
        data.model_dump(),
    )
    return CategoryResponse(**{k: v for k, v in result.items() if k != "_id"})


@api_router.delete("/categories/{category_id}")
async def delete_category(
    category_id: str,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    # Remove category from domains
    await db.domains.update_many(
        {"category_id": category_id}, {"$set": {"category_id": None}}
    )
    result = await db.categories.delete_one({"id": category_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    await log_audit(
        current_user["id"], current_user["email"], "delete", "category", category_id, {}
    )
    return {"message": "Category deleted"}


# ==================== BRAND ENDPOINTS ====================


@api_router.get("/brands", response_model=List[BrandResponse])
async def get_brands(
    status: Optional[BrandStatus] = None,
    include_archived: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """Get brands - filtered by user's brand scope"""
    # Build base filter
    query = {}

    # Status filter
    if status:
        query["status"] = status.value
    elif not include_archived:
        # By default, exclude archived brands
        query["$or"] = [
            {"status": {"$ne": BrandStatus.ARCHIVED.value}},
            {"status": {"$exists": False}},
        ]

    # Brand scope filter for non-Super Admin
    brand_scope = get_user_brand_scope(current_user)
    if brand_scope is not None:
        if brand_scope:
            query["id"] = {"$in": brand_scope}
        else:
            return []  # No brands in scope

    brands = await db.brands.find(query, {"_id": 0}).to_list(1000)
    return [BrandResponse(**b) for b in brands]


@api_router.get("/brands/{brand_id}", response_model=BrandResponse)
async def get_brand(brand_id: str, current_user: dict = Depends(get_current_user)):
    """Get single brand - requires brand access"""
    require_brand_access(brand_id, current_user)

    brand = await db.brands.find_one({"id": brand_id}, {"_id": 0})
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return BrandResponse(**brand)


@api_router.post("/brands", response_model=BrandResponse)
async def create_brand(
    brand_data: BrandCreate,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    """Create brand - Super Admin only"""
    now = datetime.now(timezone.utc).isoformat()

    # Generate slug if not provided
    slug = brand_data.slug
    if not slug:
        slug = brand_data.name.lower().replace(" ", "-").replace("_", "-")
        # Ensure unique slug
        existing = await db.brands.find_one({"slug": slug})
        if existing:
            slug = f"{slug}-{str(uuid.uuid4())[:8]}"

    brand = {
        "id": str(uuid.uuid4()),
        **brand_data.model_dump(),
        "slug": slug,
        "status": (
            brand_data.status.value if brand_data.status else BrandStatus.ACTIVE.value
        ),
        "created_at": now,
        "updated_at": now,
    }
    await db.brands.insert_one(brand)
    await log_audit(
        current_user["id"],
        current_user["email"],
        "create",
        "brand",
        brand["id"],
        brand_data.model_dump(),
    )
    return BrandResponse(**brand)


@api_router.put("/brands/{brand_id}", response_model=BrandResponse)
async def update_brand(
    brand_id: str,
    brand_data: BrandUpdate,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    """Update brand - Super Admin only"""
    existing = await db.brands.find_one({"id": brand_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Brand not found")

    # Check if archived - archived brands are read-only
    if existing.get("status") == BrandStatus.ARCHIVED.value:
        # Only allow status change (unarchive)
        if brand_data.status != BrandStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail="Archived brands are read-only. Unarchive first to edit.",
            )

    update_dict = {k: v for k, v in brand_data.model_dump().items() if v is not None}
    if "status" in update_dict and hasattr(update_dict["status"], "value"):
        update_dict["status"] = update_dict["status"].value
    update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = await db.brands.find_one_and_update(
        {"id": brand_id}, {"$set": update_dict}, return_document=True
    )

    await log_audit(
        current_user["id"],
        current_user["email"],
        "update",
        "brand",
        brand_id,
        {"before": existing, "after": update_dict},
    )
    return BrandResponse(**{k: v for k, v in result.items() if k != "_id"})


@api_router.post("/brands/{brand_id}/archive", response_model=BrandResponse)
async def archive_brand(
    brand_id: str, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))
):
    """Archive brand - soft delete, data preserved"""
    existing = await db.brands.find_one({"id": brand_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Brand not found")

    if existing.get("status") == BrandStatus.ARCHIVED.value:
        raise HTTPException(status_code=400, detail="Brand is already archived")

    result = await db.brands.find_one_and_update(
        {"id": brand_id},
        {
            "$set": {
                "status": BrandStatus.ARCHIVED.value,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        return_document=True,
    )

    await log_audit(
        current_user["id"],
        current_user["email"],
        "archive",
        "brand",
        brand_id,
        {
            "before_status": existing.get("status"),
            "after_status": BrandStatus.ARCHIVED.value,
        },
    )
    return BrandResponse(**{k: v for k, v in result.items() if k != "_id"})


@api_router.post("/brands/{brand_id}/unarchive", response_model=BrandResponse)
async def unarchive_brand(
    brand_id: str, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))
):
    """Unarchive brand - restore from archive"""
    existing = await db.brands.find_one({"id": brand_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Brand not found")

    if existing.get("status") != BrandStatus.ARCHIVED.value:
        raise HTTPException(status_code=400, detail="Brand is not archived")

    result = await db.brands.find_one_and_update(
        {"id": brand_id},
        {
            "$set": {
                "status": BrandStatus.ACTIVE.value,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        return_document=True,
    )

    await log_audit(
        current_user["id"],
        current_user["email"],
        "unarchive",
        "brand",
        brand_id,
        {
            "before_status": BrandStatus.ARCHIVED.value,
            "after_status": BrandStatus.ACTIVE.value,
        },
    )
    return BrandResponse(**{k: v for k, v in result.items() if k != "_id"})


@api_router.delete("/brands/{brand_id}")
async def delete_brand(
    brand_id: str, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))
):
    """Delete brand - only if no data exists. Use archive for soft delete."""
    # Check for associated data
    domains_count = await db.asset_domains.count_documents({"brand_id": brand_id})
    networks_count = await db.seo_networks.count_documents({"brand_id": brand_id})
    legacy_domains_count = await db.domains.count_documents({"brand_id": brand_id})

    total_data = domains_count + networks_count + legacy_domains_count
    if total_data > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete brand with associated data ({domains_count} domains, {networks_count} networks). Use archive instead.",
        )

    result = await db.brands.delete_one({"id": brand_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Brand not found")

    await log_audit(
        current_user["id"], current_user["email"], "delete", "brand", brand_id, {}
    )
    return {"message": "Brand deleted"}


# ==================== DOMAIN ENDPOINTS ====================


async def enrich_domain(domain: dict) -> dict:
    """Enrich domain with related names"""
    brands = {
        b["id"]: b["name"]
        for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    }
    categories = {
        c["id"]: c["name"]
        for c in await db.categories.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(
            1000
        )
    }
    groups = {
        g["id"]: g["name"]
        for g in await db.groups.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    }

    domain["brand_name"] = brands.get(domain.get("brand_id"), "")
    domain["category_name"] = categories.get(domain.get("category_id"), "")
    domain["group_name"] = groups.get(domain.get("group_id"), "")
    return domain


@api_router.get("/domains", response_model=List[DomainResponse])
async def get_domains(
    brand_id: Optional[str] = None,
    category_id: Optional[str] = None,
    domain_status: Optional[DomainStatus] = None,
    index_status: Optional[IndexStatus] = None,
    tier_level: Optional[TierLevel] = None,
    group_id: Optional[str] = None,
    monitoring_enabled: Optional[bool] = None,
    ping_status: Optional[PingStatus] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    query = {}
    if brand_id:
        query["brand_id"] = brand_id
    if category_id:
        query["category_id"] = category_id
    if domain_status:
        query["domain_status"] = domain_status.value
    if index_status:
        query["index_status"] = index_status.value
    if tier_level:
        query["tier_level"] = tier_level.value
    if group_id:
        query["group_id"] = group_id
    if monitoring_enabled is not None:
        query["monitoring_enabled"] = monitoring_enabled
    if ping_status:
        query["ping_status"] = ping_status.value
    if search:
        query["domain_name"] = {"$regex": search, "$options": "i"}

    domains = await db.domains.find(query, {"_id": 0}).to_list(10000)

    # Enrich with names
    brands = {
        b["id"]: b["name"]
        for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    }
    categories = {
        c["id"]: c["name"]
        for c in await db.categories.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(
            1000
        )
    }
    groups = {
        g["id"]: g["name"]
        for g in await db.groups.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    }

    result = []
    for d in domains:
        d["brand_name"] = brands.get(d.get("brand_id"), "")
        d["category_name"] = categories.get(d.get("category_id"), "")
        d["group_name"] = groups.get(d.get("group_id"), "")
        result.append(DomainResponse(**d))

    return result


@api_router.get("/domains/{domain_id}", response_model=DomainResponse)
async def get_domain(domain_id: str, current_user: dict = Depends(get_current_user)):
    domain = await db.domains.find_one({"id": domain_id}, {"_id": 0})
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    domain = await enrich_domain(domain)
    return DomainResponse(**domain)


@api_router.post("/domains", response_model=DomainResponse)
async def create_domain(
    domain_data: DomainCreate,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN])),
):
    # Validate brand exists
    brand = await db.brands.find_one({"id": domain_data.brand_id}, {"_id": 0})
    if not brand:
        raise HTTPException(status_code=400, detail="Brand not found")

    # Validate group exists if provided
    if domain_data.group_id:
        group = await db.groups.find_one({"id": domain_data.group_id}, {"_id": 0})
        if not group:
            raise HTTPException(status_code=400, detail="Group not found")

    # Validate parent domain and tier hierarchy
    if domain_data.parent_domain_id:
        parent = await db.domains.find_one(
            {"id": domain_data.parent_domain_id}, {"_id": 0}
        )
        if not parent:
            raise HTTPException(status_code=400, detail="Parent domain not found")

        parent_tier = TIER_HIERARCHY.get(parent["tier_level"], 0)
        child_tier = TIER_HIERARCHY.get(domain_data.tier_level.value, 0)

        if child_tier <= parent_tier:
            raise HTTPException(
                status_code=400, detail="Child tier must be higher than parent tier"
            )

    now = datetime.now(timezone.utc).isoformat()
    domain = {
        "id": str(uuid.uuid4()),
        **domain_data.model_dump(),
        "created_at": now,
        "updated_at": now,
    }

    # Convert enums to values
    for field in [
        "domain_status",
        "index_status",
        "tier_level",
        "monitoring_interval",
        "ping_status",
    ]:
        if field in domain and hasattr(domain[field], "value"):
            domain[field] = domain[field].value

    await db.domains.insert_one(domain)
    await log_audit(
        current_user["id"],
        current_user["email"],
        "create",
        "domain",
        domain["id"],
        {"domain_name": domain_data.domain_name},
    )

    domain["brand_name"] = brand["name"]
    domain["category_name"] = ""
    domain["group_name"] = ""

    return DomainResponse(**domain)


@api_router.put("/domains/{domain_id}", response_model=DomainResponse)
async def update_domain(
    domain_id: str,
    domain_data: DomainUpdate,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN])),
):
    existing = await db.domains.find_one({"id": domain_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Domain not found")

    update_dict = {k: v for k, v in domain_data.model_dump().items() if v is not None}

    # Validate tier hierarchy if parent is changing
    if "parent_domain_id" in update_dict and update_dict["parent_domain_id"]:
        parent = await db.domains.find_one(
            {"id": update_dict["parent_domain_id"]}, {"_id": 0}
        )
        if not parent:
            raise HTTPException(status_code=400, detail="Parent domain not found")

        new_tier = update_dict.get("tier_level", existing["tier_level"])
        if hasattr(new_tier, "value"):
            new_tier = new_tier.value

        parent_tier = TIER_HIERARCHY.get(parent["tier_level"], 0)
        child_tier = TIER_HIERARCHY.get(new_tier, 0)

        if child_tier <= parent_tier:
            raise HTTPException(
                status_code=400, detail="Child tier must be higher than parent tier"
            )

    # Convert enums
    for field in ["domain_status", "index_status", "tier_level", "monitoring_interval"]:
        if (
            field in update_dict
            and update_dict[field]
            and hasattr(update_dict[field], "value")
        ):
            update_dict[field] = update_dict[field].value

    update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = await db.domains.find_one_and_update(
        {"id": domain_id}, {"$set": update_dict}, return_document=True
    )

    await log_audit(
        current_user["id"],
        current_user["email"],
        "update",
        "domain",
        domain_id,
        update_dict,
    )

    result = await enrich_domain({k: v for k, v in result.items() if k != "_id"})
    return DomainResponse(**result)


@api_router.delete("/domains/{domain_id}")
async def delete_domain(
    domain_id: str,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN])),
):
    children = await db.domains.count_documents({"parent_domain_id": domain_id})
    if children > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete domain with {children} child domains",
        )

    result = await db.domains.delete_one({"id": domain_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Domain not found")

    await log_audit(
        current_user["id"], current_user["email"], "delete", "domain", domain_id, {}
    )
    return {"message": "Domain deleted"}


# ==================== MONITORING ENDPOINTS ====================


@api_router.post("/domains/{domain_id}/check")
async def check_domain_now(
    domain_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN])),
):
    """Manually trigger a health check for a domain"""
    domain = await db.domains.find_one({"id": domain_id}, {"_id": 0})
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    background_tasks.add_task(check_domain_health, domain)
    return {"message": f"Health check scheduled for {domain['domain_name']}"}


@api_router.get("/monitoring/stats", response_model=MonitoringStats)
async def get_monitoring_stats(current_user: dict = Depends(get_current_user)):
    """Get monitoring statistics from asset_domains collection"""
    # Query asset_domains for monitoring data
    total = await db.asset_domains.count_documents({"monitoring_enabled": True})
    up = await db.asset_domains.count_documents(
        {"monitoring_enabled": True, "ping_status": "up"}
    )
    down = await db.asset_domains.count_documents(
        {"monitoring_enabled": True, "ping_status": "down"}
    )
    unknown = await db.asset_domains.count_documents(
        {"monitoring_enabled": True, "ping_status": {"$nin": ["up", "down"]}}
    )

    # Check expiring domains (within 7 days)
    now = datetime.now(timezone.utc)
    week_later = (now + timedelta(days=7)).isoformat()

    expiring = await db.asset_domains.count_documents(
        {"expiration_date": {"$ne": None, "$lte": week_later, "$gt": now.isoformat()}}
    )

    expired = await db.asset_domains.count_documents(
        {"expiration_date": {"$ne": None, "$lte": now.isoformat()}}
    )

    return MonitoringStats(
        total_monitored=total,
        up_count=up,
        down_count=down,
        unknown_count=unknown,
        expiring_soon=expiring,
        expired=expired,
    )


# ==================== ALERT ENDPOINTS ====================


@api_router.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(
    alert_type: Optional[AlertType] = None,
    severity: Optional[AlertSeverity] = None,
    acknowledged: Optional[bool] = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
):
    query = {}
    if alert_type:
        query["alert_type"] = alert_type.value
    if severity:
        query["severity"] = severity.value
    if acknowledged is not None:
        query["acknowledged"] = acknowledged

    alerts = (
        await db.alerts.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    )
    return [AlertResponse(**a) for a in alerts]


@api_router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN])),
):
    result = await db.alerts.find_one_and_update(
        {"id": alert_id},
        {
            "$set": {
                "acknowledged": True,
                "acknowledged_by": current_user["email"],
                "acknowledged_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert acknowledged"}


@api_router.post("/domains/{domain_id}/mute")
async def mute_domain(
    domain_id: str,
    duration: str = "1h",
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN])),
):
    """Mute alerts for a domain temporarily"""
    domain = await db.domains.find_one({"id": domain_id}, {"_id": 0})
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    # Parse duration
    duration_map = {"30m": 30, "1h": 60, "6h": 360, "24h": 1440}
    minutes = duration_map.get(duration, 60)
    mute_until = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    await db.muted_domains.update_one(
        {"domain_id": domain_id},
        {
            "$set": {
                "domain_id": domain_id,
                "domain_name": domain["domain_name"],
                "muted_by": current_user["email"],
                "muted_at": datetime.now(timezone.utc).isoformat(),
                "muted_until": mute_until.isoformat(),
            }
        },
        upsert=True,
    )

    return {"message": f"Domain muted until {mute_until.isoformat()}"}


@api_router.delete("/domains/{domain_id}/mute")
async def unmute_domain(
    domain_id: str,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN])),
):
    """Remove mute from a domain"""
    await db.muted_domains.delete_one({"domain_id": domain_id})
    return {"message": "Domain unmuted"}


# ==================== GROUP ENDPOINTS ====================


@api_router.get("/groups", response_model=List[GroupResponse])
async def get_groups(current_user: dict = Depends(get_current_user)):
    groups = await db.groups.find({}, {"_id": 0}).to_list(1000)
    for group in groups:
        count = await db.domains.count_documents({"group_id": group["id"]})
        group["domain_count"] = count
    return [GroupResponse(**g) for g in groups]


@api_router.get("/groups/{group_id}", response_model=GroupDetail)
async def get_group(group_id: str, current_user: dict = Depends(get_current_user)):
    group = await db.groups.find_one({"id": group_id}, {"_id": 0})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    domains = await db.domains.find({"group_id": group_id}, {"_id": 0}).to_list(10000)

    brands = {
        b["id"]: b["name"]
        for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    }
    categories = {
        c["id"]: c["name"]
        for c in await db.categories.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(
            1000
        )
    }

    domain_responses = []
    for d in domains:
        d["brand_name"] = brands.get(d.get("brand_id"), "")
        d["category_name"] = categories.get(d.get("category_id"), "")
        d["group_name"] = group["name"]
        domain_responses.append(DomainResponse(**d))

    group["domain_count"] = len(domains)
    group["domains"] = domain_responses

    return GroupDetail(**group)


@api_router.post("/groups", response_model=GroupResponse)
async def create_group(
    group_data: GroupCreate,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN])),
):
    now = datetime.now(timezone.utc).isoformat()
    group = {
        "id": str(uuid.uuid4()),
        **group_data.model_dump(),
        "created_at": now,
        "updated_at": now,
    }
    await db.groups.insert_one(group)
    await log_audit(
        current_user["id"],
        current_user["email"],
        "create",
        "group",
        group["id"],
        group_data.model_dump(),
    )
    group["domain_count"] = 0
    return GroupResponse(**group)


@api_router.put("/groups/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: str,
    group_data: GroupCreate,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN])),
):
    result = await db.groups.find_one_and_update(
        {"id": group_id},
        {
            "$set": {
                **group_data.model_dump(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Group not found")
    await log_audit(
        current_user["id"],
        current_user["email"],
        "update",
        "group",
        group_id,
        group_data.model_dump(),
    )
    count = await db.domains.count_documents({"group_id": group_id})
    result["domain_count"] = count
    return GroupResponse(**{k: v for k, v in result.items() if k != "_id"})


@api_router.delete("/groups/{group_id}")
async def delete_group(
    group_id: str,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN])),
):
    await db.domains.update_many(
        {"group_id": group_id}, {"$set": {"group_id": None, "parent_domain_id": None}}
    )
    result = await db.groups.delete_one({"id": group_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Group not found")
    await log_audit(
        current_user["id"], current_user["email"], "delete", "group", group_id, {}
    )
    return {"message": "Group deleted"}


# ==================== CONFLICT DETECTION (DEPRECATED) ====================


@api_router.get("/seo/conflicts")
async def detect_seo_conflicts(current_user: dict = Depends(get_current_user)):
    """
    [DEPRECATED] Detect SEO structure conflicts - LEGACY ENDPOINT
    
    WARNING: This endpoint uses the OLD 'domains' collection which is no longer maintained.
    Frontend should use /api/v3/reports/conflicts instead, which works with the current
    'seo_structure_entries' collection.
    
    This endpoint is kept for backward compatibility but will be removed in a future version.
    """
    conflicts = []

    # Get all domains in groups
    domains = await db.domains.find({"group_id": {"$ne": None}}, {"_id": 0}).to_list(
        10000
    )
    domain_map = {d["id"]: d for d in domains}

    for domain in domains:
        # 1. Orphan domains (no parent but not LP)
        if domain["tier_level"] != "lp_money_site" and not domain.get(
            "parent_domain_id"
        ):
            conflicts.append(
                {
                    "type": "orphan_domain",
                    "domain_id": domain["id"],
                    "domain_name": domain["domain_name"],
                    "severity": "medium",
                    "message": "Domain has no parent in the hierarchy",
                }
            )

        # 2. NOINDEX domains in Tier 1-2
        if domain["index_status"] == "noindex" and domain["tier_level"] in [
            "tier_1",
            "tier_2",
        ]:
            conflicts.append(
                {
                    "type": "noindex_high_tier",
                    "domain_id": domain["id"],
                    "domain_name": domain["domain_name"],
                    "severity": "high",
                    "message": f"NOINDEX domain used in {domain['tier_level'].replace('_', ' ').title()}",
                }
            )

        # 3. Tier jump violations
        if domain.get("parent_domain_id"):
            parent = domain_map.get(domain["parent_domain_id"])
            if parent:
                parent_tier = TIER_HIERARCHY.get(parent["tier_level"], 0)
                child_tier = TIER_HIERARCHY.get(domain["tier_level"], 0)

                if child_tier - parent_tier > 1:
                    conflicts.append(
                        {
                            "type": "tier_jump",
                            "domain_id": domain["id"],
                            "domain_name": domain["domain_name"],
                            "severity": "medium",
                            "message": f"Tier jump from {parent['tier_level']} to {domain['tier_level']}",
                        }
                    )

        # 4. Canonical pointing to non-LP
        if domain["domain_status"] == "canonical" and domain.get("parent_domain_id"):
            parent = domain_map.get(domain["parent_domain_id"])
            if parent and parent["tier_level"] != "lp_money_site":
                conflicts.append(
                    {
                        "type": "canonical_not_to_lp",
                        "domain_id": domain["id"],
                        "domain_name": domain["domain_name"],
                        "severity": "high",
                        "message": f"Canonical pointing to non-Money Site ({parent['domain_name']})",
                    }
                )

    return {"conflicts": conflicts, "total": len(conflicts)}


# ==================== REPORTS ENDPOINTS ====================


@api_router.get("/reports/dashboard-stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    # Apply brand filtering for non-super-admin users
    brand_filter = {}
    brand_scope_ids = current_user.get("brand_scope_ids")
    if current_user.get("role") != "super_admin" and brand_scope_ids:
        brand_filter = {"brand_id": {"$in": brand_scope_ids}}

    # Use asset_domains collection (new V3 data)
    domain_base_filter = brand_filter.copy()
    domain_indexed_filter = {**domain_base_filter, "index_status": "index"}
    domain_noindex_filter = {**domain_base_filter, "index_status": "noindex"}
    domain_monitored_filter = {**domain_base_filter, "monitoring_enabled": True}
    domain_up_filter = {
        **domain_base_filter,
        "monitoring_enabled": True,
        "ping_status": "up",
    }
    domain_down_filter = {
        **domain_base_filter,
        "monitoring_enabled": True,
        "ping_status": "down",
    }

    # Use seo_networks collection (new V3 data)
    network_filter = brand_filter.copy()

    # Use asset_domains for domain counts
    total_domains = await db.asset_domains.count_documents(domain_base_filter)
    total_networks = await db.seo_networks.count_documents(network_filter)
    total_brands = await db.brands.count_documents(
        {}
        if not brand_scope_ids or current_user.get("role") == "super_admin"
        else {"id": {"$in": brand_scope_ids}}
    )
    indexed_count = await db.asset_domains.count_documents(domain_indexed_filter)
    noindex_count = await db.asset_domains.count_documents(domain_noindex_filter)

    # Monitoring stats from asset_domains
    monitored = await db.asset_domains.count_documents(domain_monitored_filter)
    up = await db.asset_domains.count_documents(domain_up_filter)
    down = await db.asset_domains.count_documents(domain_down_filter)

    # Active alerts
    active_alerts = await db.alerts.count_documents({"acknowledged": False})
    
    # Get domains that are currently DOWN
    down_domain_names = []
    down_domains_cursor = db.asset_domains.find(
        domain_down_filter,
        {"_id": 0, "domain": 1}
    )
    async for doc in down_domains_cursor:
        if doc.get("domain"):
            down_domain_names.append(doc["domain"])
    
    # Critical alerts: only count alerts for domains that are CURRENTLY down
    # This ensures banner disappears when domain is fixed
    critical_filter = {"acknowledged": False, "severity": "critical"}
    if down_domain_names:
        # Only show critical alerts for domains that are still down
        critical_filter["domain_name"] = {"$in": down_domain_names}
    else:
        # No domains down, no critical alerts to show
        critical_filter["domain_name"] = {"$in": []}  # Match nothing
    
    critical_alerts_count = await db.alerts.count_documents(critical_filter)
    
    # Get critical alert details (domain names) for dashboard display
    critical_alert_details = []
    if critical_alerts_count > 0:
        critical_alerts_cursor = db.alerts.find(
            critical_filter,
            {"_id": 0, "domain_name": 1, "title": 1, "alert_type": 1, "created_at": 1}
        ).limit(5)  # Show max 5 in banner
        critical_alert_details = await critical_alerts_cursor.to_list(5)

    return {
        "total_domains": total_domains,
        "total_groups": total_networks,  # Keeping old key name for frontend compatibility
        "total_brands": total_brands,
        "indexed_count": indexed_count,
        "noindex_count": noindex_count,
        "index_rate": round(
            (indexed_count / total_domains * 100) if total_domains > 0 else 0, 1
        ),
        "monitored_count": monitored,
        "up_count": up,
        "down_count": down,
        "active_alerts": active_alerts,
        "critical_alerts": critical_alerts_count,
        "critical_alert_details": critical_alert_details,
    }


@api_router.get("/reports/tier-distribution")
async def get_tier_distribution(
    brand_id: Optional[str] = None, current_user: dict = Depends(get_current_user)
):
    query = {}
    if brand_id:
        query["brand_id"] = brand_id

    pipeline = [
        {"$match": query},
        {"$group": {"_id": "$tier_level", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]

    results = await db.domains.aggregate(pipeline).to_list(100)
    return [{"tier": r["_id"], "count": r["count"]} for r in results]


@api_router.get("/reports/index-status")
async def get_index_status_report(
    brand_id: Optional[str] = None, current_user: dict = Depends(get_current_user)
):
    query = {}
    if brand_id:
        query["brand_id"] = brand_id

    pipeline = [
        {"$match": query},
        {"$group": {"_id": "$index_status", "count": {"$sum": 1}}},
    ]

    results = await db.domains.aggregate(pipeline).to_list(100)
    return [{"status": r["_id"], "count": r["count"]} for r in results]


@api_router.get("/reports/brand-health")
async def get_brand_health(current_user: dict = Depends(get_current_user)):
    pipeline = [
        {
            "$group": {
                "_id": "$brand_id",
                "total": {"$sum": 1},
                "indexed": {
                    "$sum": {"$cond": [{"$eq": ["$index_status", "index"]}, 1, 0]}
                },
                "noindex": {
                    "$sum": {"$cond": [{"$eq": ["$index_status", "noindex"]}, 1, 0]}
                },
                "up": {"$sum": {"$cond": [{"$eq": ["$ping_status", "up"]}, 1, 0]}},
                "down": {"$sum": {"$cond": [{"$eq": ["$ping_status", "down"]}, 1, 0]}},
            }
        }
    ]

    results = await db.domains.aggregate(pipeline).to_list(100)
    brands = {
        b["id"]: b["name"]
        for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    }

    return [
        {
            "brand_id": r["_id"],
            "brand_name": brands.get(r["_id"], "Unknown"),
            "total": r["total"],
            "indexed": r["indexed"],
            "noindex": r["noindex"],
            "up": r["up"],
            "down": r["down"],
            "health_score": round(
                (r["indexed"] / r["total"] * 100) if r["total"] > 0 else 0, 1
            ),
        }
        for r in results
    ]


@api_router.get("/reports/orphan-domains")
async def get_orphan_domains(current_user: dict = Depends(get_current_user)):
    pipeline = [
        {
            "$match": {
                "tier_level": {"$ne": "lp_money_site"},
                "parent_domain_id": None,
                "group_id": {"$ne": None},
            }
        }
    ]

    domains = await db.domains.aggregate(pipeline).to_list(1000)
    brands = {
        b["id"]: b["name"]
        for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    }

    return [
        {
            "id": d["id"],
            "domain_name": d["domain_name"],
            "tier_level": d["tier_level"],
            "brand_name": brands.get(d.get("brand_id"), "Unknown"),
            "group_id": d.get("group_id"),
        }
        for d in domains
    ]


@api_router.get("/reports/export")
async def export_domains(
    format: str = "json",
    brand_id: Optional[str] = None,
    group_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    query = {}
    if brand_id:
        query["brand_id"] = brand_id
    if group_id:
        query["group_id"] = group_id

    domains = await db.domains.find(query, {"_id": 0}).to_list(100000)
    brands = {
        b["id"]: b["name"]
        for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    }
    categories = {
        c["id"]: c["name"]
        for c in await db.categories.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(
            1000
        )
    }
    groups = {
        g["id"]: g["name"]
        for g in await db.groups.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    }

    export_data = []
    for d in domains:
        export_data.append(
            {
                "domain_name": d["domain_name"],
                "brand": brands.get(d.get("brand_id"), ""),
                "category": categories.get(d.get("category_id"), ""),
                "group": groups.get(d.get("group_id"), ""),
                "tier_level": d["tier_level"],
                "domain_status": d["domain_status"],
                "index_status": d["index_status"],
                "registrar": d.get("registrar", ""),
                "expiration_date": d.get("expiration_date", ""),
                "monitoring_enabled": d.get("monitoring_enabled", False),
                "ping_status": d.get("ping_status", "unknown"),
                "created_at": d["created_at"],
            }
        )

    if format == "csv":
        import csv
        import io

        output = io.StringIO()
        if export_data:
            writer = csv.DictWriter(output, fieldnames=export_data[0].keys())
            writer.writeheader()
            writer.writerows(export_data)
        return {"data": output.getvalue(), "format": "csv"}

    return {"data": export_data, "format": "json"}


# ==================== SETTINGS ENDPOINTS ====================


@api_router.get("/settings/telegram")
async def get_telegram_settings(
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    settings = await db.settings.find_one({"key": "telegram"}, {"_id": 0})
    if settings:
        # Mask token for security
        if settings.get("bot_token"):
            settings["bot_token"] = (
                settings["bot_token"][:10] + "..." + settings["bot_token"][-5:]
            )
    return settings or {"bot_token": "", "chat_id": ""}


@api_router.put("/settings/telegram")
async def update_telegram_settings(
    config: TelegramConfig,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    update_data = {
        "key": "telegram",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if config.bot_token:
        update_data["bot_token"] = config.bot_token
    if config.chat_id:
        update_data["chat_id"] = config.chat_id

    await db.settings.update_one(
        {"key": "telegram"}, {"$set": update_data}, upsert=True
    )
    return {"message": "Telegram settings updated"}


@api_router.post("/settings/telegram/test")
async def test_telegram(
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    """Send a test message to verify Telegram configuration"""
    tz_str, tz_label = await get_system_timezone()
    local_time = format_to_local_time(datetime.now(timezone.utc).isoformat(), tz_str)

    message = f"""✅ <b>SEO-NOC Test Alert</b>

This is a test message from SEO-NOC.
Sent by: {current_user['email']}
Time: {local_time}"""

    success = await send_telegram_alert(message)
    if success:
        return {"message": "Test message sent successfully"}
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to send test message. Check your Telegram configuration.",
        )


# ==================== APP BRANDING SETTINGS ====================


@api_router.get("/settings/branding")
async def get_branding_settings(current_user: dict = Depends(get_current_user)):
    """Get app branding settings (title, description, logo, tagline)"""
    settings = await db.settings.find_one({"key": "branding"}, {"_id": 0})
    return settings or {
        "site_title": "SEO//NOC",
        "site_description": "SEO Network Operations Center - Manage your domain networks efficiently",
        "logo_url": "",
        "tagline": "Domain Network Management System",
    }


@api_router.put("/settings/branding")
async def update_branding_settings(
    config: AppBrandingSettings,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    """Update app branding settings - Super Admin only"""
    update_data = {
        "key": "branding",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if config.site_title is not None:
        update_data["site_title"] = config.site_title
    if config.site_description is not None:
        update_data["site_description"] = config.site_description
    if config.logo_url is not None:
        update_data["logo_url"] = config.logo_url
    if config.tagline is not None:
        update_data["tagline"] = config.tagline

    await db.settings.update_one(
        {"key": "branding"}, {"$set": update_data}, upsert=True
    )

    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.SETTINGS,
            entity_id="branding",
            after_value={"action": "branding_updated", **update_data},
        )

    return {"message": "Branding settings updated"}


@api_router.post("/settings/branding/upload-logo")
async def upload_logo(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    """Upload a logo image - Super Admin only"""
    import base64

    # Validate file type
    allowed_types = ["image/png", "image/jpeg", "image/svg+xml", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="File type not allowed. Use: PNG, JPEG, SVG, or WebP",
        )

    # Validate file size (max 2MB)
    contents = await file.read()
    if len(contents) > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=400, detail="File too large. Maximum size is 2MB"
        )

    # Store as base64 data URL
    b64_content = base64.b64encode(contents).decode("utf-8")
    data_url = f"data:{file.content_type};base64,{b64_content}"

    # Update branding settings with logo
    await db.settings.update_one(
        {"key": "branding"},
        {
            "$set": {
                "logo_url": data_url,
                "logo_filename": file.filename,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )

    return {"message": "Logo uploaded successfully", "logo_url": data_url}


# ==================== TIMEZONE SETTINGS ====================


@api_router.get("/settings/timezone")
async def get_timezone_settings(current_user: dict = Depends(get_current_user)):
    """Get timezone settings for monitoring display"""
    settings = await db.settings.find_one({"key": "timezone"}, {"_id": 0})
    return settings or {"default_timezone": "Asia/Jakarta", "timezone_label": "GMT+7"}


@api_router.put("/settings/timezone")
async def update_timezone_settings(
    config: TimezoneSettings,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    """Update timezone settings - Super Admin only"""
    # Validate timezone
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(config.default_timezone)
    except Exception:
        raise HTTPException(
            status_code=400, detail=f"Invalid timezone: {config.default_timezone}"
        )

    update_data = {
        "key": "timezone",
        "default_timezone": config.default_timezone,
        "timezone_label": config.timezone_label,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.settings.update_one(
        {"key": "timezone"}, {"$set": update_data}, upsert=True
    )

    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.SETTINGS,
            entity_id="timezone",
            after_value={"action": "timezone_updated", **update_data},
        )

    return {"message": "Timezone settings updated"}


# ==================== AUDIT LOGS ====================


@api_router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    limit: int = 100,
    entity_type: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    query = {}
    if entity_type:
        query["entity_type"] = entity_type

    logs = (
        await db.audit_logs.find(query, {"_id": 0})
        .sort("created_at", -1)
        .to_list(limit)
    )
    return [AuditLogResponse(**log) for log in logs]


# ==================== SEED DATA ====================


@api_router.post("/seed-data")
async def seed_demo_data(
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN])),
):
    existing_brands = await db.brands.count_documents({})
    if existing_brands > 0:
        raise HTTPException(
            status_code=400, detail="Data already exists. Clear database first."
        )

    now = datetime.now(timezone.utc).isoformat()

    # Create brands
    brands = [
        {
            "id": str(uuid.uuid4()),
            "name": "Panen138",
            "description": "Premium brand network",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "PANEN77",
            "description": "Secondary brand network",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "DEWI138",
            "description": "Emerging brand network",
            "created_at": now,
            "updated_at": now,
        },
    ]
    await db.brands.insert_many(brands)

    # Get categories
    categories = await db.categories.find({}, {"_id": 0}).to_list(100)
    cat_map = {c["name"]: c["id"] for c in categories}

    # Create groups
    groups = [
        {
            "id": str(uuid.uuid4()),
            "name": "Main SEO Network",
            "description": "Primary link building network",
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Support Network",
            "description": "Secondary support links",
            "created_at": now,
            "updated_at": now,
        },
    ]
    await db.groups.insert_many(groups)

    # Create domains with full asset management fields
    domains = []

    # LP/Money Site
    lp = {
        "id": str(uuid.uuid4()),
        "domain_name": "moneysite.com",
        "brand_id": brands[0]["id"],
        "category_id": cat_map.get("Money Site"),
        "domain_status": "canonical",
        "index_status": "index",
        "tier_level": "lp_money_site",
        "group_id": groups[0]["id"],
        "parent_domain_id": None,
        "registrar": "Namecheap",
        "expiration_date": (
            datetime.now(timezone.utc) + timedelta(days=365)
        ).isoformat(),
        "auto_renew": True,
        "monitoring_enabled": True,
        "monitoring_interval": "5min",
        "ping_status": "unknown",
        "notes": "Main money site",
        "created_at": now,
        "updated_at": now,
    }
    domains.append(lp)

    # Tier 1 domains
    t1_domains = []
    for i in range(1, 4):
        t1 = {
            "id": str(uuid.uuid4()),
            "domain_name": f"tier1-site{i}.com",
            "brand_id": brands[0]["id"],
            "category_id": cat_map.get("Aged Domain"),
            "domain_status": "canonical",
            "index_status": "index",
            "tier_level": "tier_1",
            "group_id": groups[0]["id"],
            "parent_domain_id": lp["id"],
            "registrar": "GoDaddy",
            "expiration_date": (
                datetime.now(timezone.utc) + timedelta(days=180 + i * 30)
            ).isoformat(),
            "auto_renew": True,
            "monitoring_enabled": True,
            "monitoring_interval": "15min",
            "ping_status": "unknown",
            "notes": f"Tier 1 site {i}",
            "created_at": now,
            "updated_at": now,
        }
        t1_domains.append(t1)
    domains.extend(t1_domains)

    # Tier 2 domains
    t2_domains = []
    for i, t1 in enumerate(t1_domains):
        for j in range(1, 3):
            t2 = {
                "id": str(uuid.uuid4()),
                "domain_name": f"tier2-site{i+1}-{j}.com",
                "brand_id": brands[1]["id"],
                "category_id": cat_map.get("PBN"),
                "domain_status": "canonical",
                "index_status": "index" if j == 1 else "noindex",
                "tier_level": "tier_2",
                "group_id": groups[0]["id"],
                "parent_domain_id": t1["id"],
                "registrar": "Dynadot",
                "expiration_date": (
                    datetime.now(timezone.utc) + timedelta(days=90)
                ).isoformat(),
                "auto_renew": False,
                "monitoring_enabled": True,
                "monitoring_interval": "1hour",
                "ping_status": "unknown",
                "notes": f"Tier 2 under tier1-site{i+1}",
                "created_at": now,
                "updated_at": now,
            }
            t2_domains.append(t2)
    domains.extend(t2_domains)

    # Tier 3 domains
    for i, t2 in enumerate(t2_domains[:3]):
        for j in range(1, 3):
            t3 = {
                "id": str(uuid.uuid4()),
                "domain_name": f"tier3-site{i+1}-{j}.net",
                "brand_id": brands[2]["id"],
                "category_id": cat_map.get("Fresh Domain"),
                "domain_status": "301_redirect" if j == 2 else "canonical",
                "index_status": "noindex",
                "tier_level": "tier_3",
                "group_id": groups[0]["id"],
                "parent_domain_id": t2["id"],
                "registrar": "Namecheap",
                "expiration_date": (
                    datetime.now(timezone.utc) + timedelta(days=30)
                ).isoformat(),
                "auto_renew": False,
                "monitoring_enabled": False,
                "monitoring_interval": "daily",
                "ping_status": "unknown",
                "notes": "",
                "created_at": now,
                "updated_at": now,
            }
            domains.append(t3)

    # Orphan domain
    orphan = {
        "id": str(uuid.uuid4()),
        "domain_name": "orphan-domain.com",
        "brand_id": brands[0]["id"],
        "category_id": cat_map.get("Parking"),
        "domain_status": "canonical",
        "index_status": "noindex",
        "tier_level": "tier_3",
        "group_id": groups[0]["id"],
        "parent_domain_id": None,
        "registrar": "Namecheap",
        "expiration_date": (
            datetime.now(timezone.utc) + timedelta(days=5)
        ).isoformat(),  # Expiring soon!
        "auto_renew": False,
        "monitoring_enabled": True,
        "monitoring_interval": "1hour",
        "ping_status": "unknown",
        "notes": "Orphan domain for testing",
        "created_at": now,
        "updated_at": now,
    }
    domains.append(orphan)

    # Support network domains
    lp2 = {
        "id": str(uuid.uuid4()),
        "domain_name": "support-main.com",
        "brand_id": brands[1]["id"],
        "category_id": cat_map.get("Subdomain Money Site"),
        "domain_status": "canonical",
        "index_status": "index",
        "tier_level": "lp_money_site",
        "group_id": groups[1]["id"],
        "parent_domain_id": None,
        "registrar": "GoDaddy",
        "expiration_date": (
            datetime.now(timezone.utc) + timedelta(days=200)
        ).isoformat(),
        "auto_renew": True,
        "monitoring_enabled": True,
        "monitoring_interval": "15min",
        "ping_status": "unknown",
        "notes": "Support network main",
        "created_at": now,
        "updated_at": now,
    }
    domains.append(lp2)

    for i in range(1, 4):
        d = {
            "id": str(uuid.uuid4()),
            "domain_name": f"support-tier1-{i}.com",
            "brand_id": brands[1]["id"],
            "category_id": cat_map.get("Aged Domain"),
            "domain_status": "canonical",
            "index_status": "index",
            "tier_level": "tier_1",
            "group_id": groups[1]["id"],
            "parent_domain_id": lp2["id"],
            "registrar": "Namecheap",
            "expiration_date": (
                datetime.now(timezone.utc) + timedelta(days=150)
            ).isoformat(),
            "auto_renew": True,
            "monitoring_enabled": True,
            "monitoring_interval": "1hour",
            "ping_status": "unknown",
            "notes": "",
            "created_at": now,
            "updated_at": now,
        }
        domains.append(d)

    await db.domains.insert_many(domains)

    return {
        "message": f"Seeded {len(brands)} brands, {len(groups)} groups, {len(domains)} domains"
    }


# Initialize V3 router with dependencies
init_v3_router(
    database=db,
    current_user_dep=get_current_user,
    roles_dep=require_roles,
    activity_service=activity_log_service,
    tier_svc=tier_service,
    seo_change_svc=seo_change_log_service,
    seo_telegram_svc=seo_telegram_service,
)

# Include routers
app.include_router(api_router)  # V2 API (legacy)
app.include_router(v3_router)  # V3 API (new architecture)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
