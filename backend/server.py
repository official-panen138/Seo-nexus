from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, BackgroundTasks
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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Settings
JWT_SECRET = os.environ.get('JWT_SECRET', 'seo-nexus-secret-key-change-in-production')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Background monitoring state
monitoring_tasks = {}

# V3 Services
from services.activity_log_service import init_activity_log_service
from services.tier_service import init_tier_service
from routers.v3_router import router as v3_router, init_v3_router

# Initialize V3 services
activity_log_service = init_activity_log_service(db)
tier_service = init_tier_service(db)

# Create the main app with lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting SEO-NOC application...")
    await initialize_default_categories()
    
    # Start V3 monitoring scheduler (two independent engines)
    from services.monitoring_service import MonitoringScheduler
    monitoring_scheduler = MonitoringScheduler(db)
    asyncio.create_task(monitoring_scheduler.start())
    logger.info("V3 Monitoring Scheduler started (Expiration + Availability engines)")
    
    logger.info("V3 services initialized: ActivityLog, TierCalculation, Monitoring")
    yield
    # Shutdown
    logger.info("Shutting down SEO-NOC application...")
    client.close()

app = FastAPI(title="SEO-NOC API", lifespan=lifespan)
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# ==================== ENUMS ====================

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
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
    "tier_5": 5, "tier_4": 4, "tier_3": 3, "tier_2": 2, "tier_1": 1, "lp_money_site": 0
}

# Monitoring intervals in seconds
INTERVAL_SECONDS = {
    "5min": 300,
    "15min": 900,
    "1hour": 3600,
    "daily": 86400
}

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

class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: UserRole = UserRole.VIEWER
    brand_scope_ids: Optional[List[str]] = None  # NULL = Super Admin (all brands), array = restricted to specific brands


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    """Model for updating user"""
    name: Optional[str] = None
    role: Optional[UserRole] = None
    brand_scope_ids: Optional[List[str]] = None


class UserResponse(UserBase):
    model_config = ConfigDict(extra="ignore")
    id: str
    created_at: str
    updated_at: str


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

class MonitoringStats(BaseModel):
    total_monitored: int = 0
    up_count: int = 0
    down_count: int = 0
    unknown_count: int = 0
    expiring_soon: int = 0
    expired: int = 0

# ==================== HELPER FUNCTIONS ====================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
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

async def log_audit(user_id: str, user_email: str, action: str, entity_type: str, entity_id: str, details: dict):
    audit_log = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "user_email": user_email,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details,
        "created_at": datetime.now(timezone.utc).isoformat()
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
            response = await client.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }, timeout=10)
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
    severity = "CRITICAL" if days_remaining <= 0 else ("WARNING" if days_remaining <= 7 else "MEDIUM")
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

async def create_alert(domain: dict, alert_type: AlertType, title: str, message: str, details: dict = {}):
    """Create alert in database and send to Telegram"""
    severity = calculate_severity(domain)
    
    # Check if domain is muted
    mute = await db.muted_domains.find_one({
        "domain_id": domain["id"],
        "muted_until": {"$gt": datetime.now(timezone.utc).isoformat()}
    }, {"_id": 0})
    
    if mute:
        logger.info(f"Domain {domain['domain_name']} is muted, skipping alert")
        return None
    
    # Check for recent similar alert (cooldown)
    recent = await db.alerts.find_one({
        "domain_id": domain["id"],
        "alert_type": alert_type.value,
        "created_at": {"$gt": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()}
    }, {"_id": 0})
    
    if recent and not recent.get("acknowledged"):
        logger.info(f"Recent unacknowledged alert exists for {domain['domain_name']}, skipping")
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
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.alerts.insert_one(alert)
    
    # Send Telegram notification
    if alert_type == AlertType.MONITORING:
        telegram_msg = format_monitoring_alert(domain, title, details.get("previous_status", "unknown"))
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
        {"$set": {
            "ping_status": new_ping.value,
            "http_status": new_http_status,
            "http_status_code": new_http_code,
            "last_check": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Create alert if status changed to DOWN
    if new_ping == PingStatus.DOWN and previous_ping != PingStatus.DOWN.value:
        # Enrich domain with names
        brand = await db.brands.find_one({"id": domain.get("brand_id")}, {"_id": 0, "name": 1})
        category = await db.categories.find_one({"id": domain.get("category_id")}, {"_id": 0, "name": 1})
        group = await db.groups.find_one({"id": domain.get("group_id")}, {"_id": 0, "name": 1})
        
        enriched = {
            **domain,
            "brand_name": brand["name"] if brand else None,
            "category_name": category["name"] if category else None,
            "group_name": group["name"] if group else None
        }
        
        await create_alert(
            enriched,
            AlertType.MONITORING,
            f"HTTP {new_http_status.upper()}" if new_http_status != "error" else "Connection Error",
            f"Domain {domain_name} is unreachable",
            {"previous_status": previous_ping, "http_status": new_http_status, "http_code": new_http_code}
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
            brand = await db.brands.find_one({"id": domain.get("brand_id")}, {"_id": 0, "name": 1})
            category = await db.categories.find_one({"id": domain.get("category_id")}, {"_id": 0, "name": 1})
            
            enriched = {
                **domain,
                "brand_name": brand["name"] if brand else None,
                "category_name": category["name"] if category else None
            }
            
            title = "Domain Expired" if days_remaining <= 0 else f"Expires in {days_remaining} days"
            
            await create_alert(
                enriched,
                AlertType.EXPIRATION,
                title,
                f"Domain {domain['domain_name']} expiration warning",
                {"days_remaining": days_remaining, "expiration_date": expiration_str}
            )
    except Exception as e:
        logger.error(f"Error checking expiration for {domain.get('domain_name')}: {e}")

async def run_monitoring_cycle():
    """Run one cycle of domain monitoring"""
    logger.info("Starting monitoring cycle...")
    
    # Get all domains with monitoring enabled
    domains = await db.domains.find(
        {"monitoring_enabled": True},
        {"_id": 0}
    ).to_list(10000)
    
    now = datetime.now(timezone.utc)
    
    for domain in domains:
        # Check if it's time to monitor based on interval
        last_check_str = domain.get("last_check")
        interval = domain.get("monitoring_interval", "1hour")
        interval_secs = INTERVAL_SECONDS.get(interval, 3600)
        
        should_check = True
        if last_check_str:
            try:
                last_check = datetime.fromisoformat(last_check_str.replace("Z", "+00:00"))
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
                "updated_at": now
            }
            for cat in DEFAULT_CATEGORIES
        ]
        await db.categories.insert_many(categories)
        logger.info(f"Initialized {len(categories)} default categories")

# ==================== AUTH ENDPOINTS ====================

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_count = await db.users.count_documents({})
    role = UserRole.SUPER_ADMIN if user_count == 0 else user_data.role
    
    now = datetime.now(timezone.utc).isoformat()
    user = {
        "id": str(uuid.uuid4()),
        "email": user_data.email,
        "name": user_data.name,
        "password": hash_password(user_data.password),
        "role": role.value if isinstance(role, UserRole) else role,
        "created_at": now,
        "updated_at": now
    }
    await db.users.insert_one(user)
    
    token = create_token(user["id"], user["email"], user["role"])
    user_response = UserResponse(
        id=user["id"], email=user["email"], name=user["name"],
        role=user["role"], created_at=user["created_at"], updated_at=user["updated_at"]
    )
    return TokenResponse(access_token=token, user=user_response)

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user["id"], user["email"], user["role"])
    user_response = UserResponse(
        id=user["id"], email=user["email"], name=user["name"],
        role=user["role"], created_at=user["created_at"], updated_at=user["updated_at"]
    )
    return TokenResponse(access_token=token, user=user_response)

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(**current_user)

# ==================== USER MANAGEMENT ====================

@api_router.get("/users", response_model=List[UserResponse])
async def get_users(current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))):
    users = await db.users.find({}, {"_id": 0, "password": 0}).to_list(1000)
    return [UserResponse(**u) for u in users]

@api_router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, role: UserRole, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))):
    result = await db.users.find_one_and_update(
        {"id": user_id},
        {"$set": {"role": role.value, "updated_at": datetime.now(timezone.utc).isoformat()}},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    await log_audit(current_user["id"], current_user["email"], "update", "user", user_id, {"new_role": role.value})
    return UserResponse(**{k: v for k, v in result.items() if k != "_id" and k != "password"})

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))):
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    await log_audit(current_user["id"], current_user["email"], "delete", "user", user_id, {})
    return {"message": "User deleted"}

# ==================== CATEGORY ENDPOINTS ====================

@api_router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(current_user: dict = Depends(get_current_user)):
    categories = await db.categories.find({}, {"_id": 0}).to_list(1000)
    return [CategoryResponse(**c) for c in categories]

@api_router.post("/categories", response_model=CategoryResponse)
async def create_category(data: CategoryCreate, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))):
    now = datetime.now(timezone.utc).isoformat()
    category = {
        "id": str(uuid.uuid4()),
        **data.model_dump(),
        "created_at": now,
        "updated_at": now
    }
    await db.categories.insert_one(category)
    await log_audit(current_user["id"], current_user["email"], "create", "category", category["id"], data.model_dump())
    return CategoryResponse(**category)

@api_router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(category_id: str, data: CategoryCreate, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))):
    result = await db.categories.find_one_and_update(
        {"id": category_id},
        {"$set": {**data.model_dump(), "updated_at": datetime.now(timezone.utc).isoformat()}},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Category not found")
    await log_audit(current_user["id"], current_user["email"], "update", "category", category_id, data.model_dump())
    return CategoryResponse(**{k: v for k, v in result.items() if k != "_id"})

@api_router.delete("/categories/{category_id}")
async def delete_category(category_id: str, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))):
    # Remove category from domains
    await db.domains.update_many({"category_id": category_id}, {"$set": {"category_id": None}})
    result = await db.categories.delete_one({"id": category_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    await log_audit(current_user["id"], current_user["email"], "delete", "category", category_id, {})
    return {"message": "Category deleted"}

# ==================== BRAND ENDPOINTS ====================

@api_router.get("/brands", response_model=List[BrandResponse])
async def get_brands(current_user: dict = Depends(get_current_user)):
    brands = await db.brands.find({}, {"_id": 0}).to_list(1000)
    return [BrandResponse(**b) for b in brands]

@api_router.post("/brands", response_model=BrandResponse)
async def create_brand(brand_data: BrandCreate, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))):
    now = datetime.now(timezone.utc).isoformat()
    brand = {"id": str(uuid.uuid4()), **brand_data.model_dump(), "created_at": now, "updated_at": now}
    await db.brands.insert_one(brand)
    await log_audit(current_user["id"], current_user["email"], "create", "brand", brand["id"], brand_data.model_dump())
    return BrandResponse(**brand)

@api_router.put("/brands/{brand_id}", response_model=BrandResponse)
async def update_brand(brand_id: str, brand_data: BrandCreate, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))):
    result = await db.brands.find_one_and_update(
        {"id": brand_id},
        {"$set": {**brand_data.model_dump(), "updated_at": datetime.now(timezone.utc).isoformat()}},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Brand not found")
    await log_audit(current_user["id"], current_user["email"], "update", "brand", brand_id, brand_data.model_dump())
    return BrandResponse(**{k: v for k, v in result.items() if k != "_id"})

@api_router.delete("/brands/{brand_id}")
async def delete_brand(brand_id: str, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))):
    domains_with_brand = await db.domains.count_documents({"brand_id": brand_id})
    if domains_with_brand > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete brand with {domains_with_brand} associated domains")
    result = await db.brands.delete_one({"id": brand_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Brand not found")
    await log_audit(current_user["id"], current_user["email"], "delete", "brand", brand_id, {})
    return {"message": "Brand deleted"}

# ==================== DOMAIN ENDPOINTS ====================

async def enrich_domain(domain: dict) -> dict:
    """Enrich domain with related names"""
    brands = {b["id"]: b["name"] for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    categories = {c["id"]: c["name"] for c in await db.categories.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    groups = {g["id"]: g["name"] for g in await db.groups.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    
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
    current_user: dict = Depends(get_current_user)
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
    brands = {b["id"]: b["name"] for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    categories = {c["id"]: c["name"] for c in await db.categories.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    groups = {g["id"]: g["name"] for g in await db.groups.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    
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
async def create_domain(domain_data: DomainCreate, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN]))):
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
        parent = await db.domains.find_one({"id": domain_data.parent_domain_id}, {"_id": 0})
        if not parent:
            raise HTTPException(status_code=400, detail="Parent domain not found")
        
        parent_tier = TIER_HIERARCHY.get(parent["tier_level"], 0)
        child_tier = TIER_HIERARCHY.get(domain_data.tier_level.value, 0)
        
        if child_tier <= parent_tier:
            raise HTTPException(status_code=400, detail="Child tier must be higher than parent tier")
    
    now = datetime.now(timezone.utc).isoformat()
    domain = {
        "id": str(uuid.uuid4()),
        **domain_data.model_dump(),
        "created_at": now,
        "updated_at": now
    }
    
    # Convert enums to values
    for field in ["domain_status", "index_status", "tier_level", "monitoring_interval", "ping_status"]:
        if field in domain and hasattr(domain[field], 'value'):
            domain[field] = domain[field].value
    
    await db.domains.insert_one(domain)
    await log_audit(current_user["id"], current_user["email"], "create", "domain", domain["id"], {"domain_name": domain_data.domain_name})
    
    domain["brand_name"] = brand["name"]
    domain["category_name"] = ""
    domain["group_name"] = ""
    
    return DomainResponse(**domain)

@api_router.put("/domains/{domain_id}", response_model=DomainResponse)
async def update_domain(domain_id: str, domain_data: DomainUpdate, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN]))):
    existing = await db.domains.find_one({"id": domain_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    update_dict = {k: v for k, v in domain_data.model_dump().items() if v is not None}
    
    # Validate tier hierarchy if parent is changing
    if "parent_domain_id" in update_dict and update_dict["parent_domain_id"]:
        parent = await db.domains.find_one({"id": update_dict["parent_domain_id"]}, {"_id": 0})
        if not parent:
            raise HTTPException(status_code=400, detail="Parent domain not found")
        
        new_tier = update_dict.get("tier_level", existing["tier_level"])
        if hasattr(new_tier, 'value'):
            new_tier = new_tier.value
        
        parent_tier = TIER_HIERARCHY.get(parent["tier_level"], 0)
        child_tier = TIER_HIERARCHY.get(new_tier, 0)
        
        if child_tier <= parent_tier:
            raise HTTPException(status_code=400, detail="Child tier must be higher than parent tier")
    
    # Convert enums
    for field in ["domain_status", "index_status", "tier_level", "monitoring_interval"]:
        if field in update_dict and update_dict[field] and hasattr(update_dict[field], 'value'):
            update_dict[field] = update_dict[field].value
    
    update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.domains.find_one_and_update(
        {"id": domain_id},
        {"$set": update_dict},
        return_document=True
    )
    
    await log_audit(current_user["id"], current_user["email"], "update", "domain", domain_id, update_dict)
    
    result = await enrich_domain({k: v for k, v in result.items() if k != "_id"})
    return DomainResponse(**result)

@api_router.delete("/domains/{domain_id}")
async def delete_domain(domain_id: str, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN]))):
    children = await db.domains.count_documents({"parent_domain_id": domain_id})
    if children > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete domain with {children} child domains")
    
    result = await db.domains.delete_one({"id": domain_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    await log_audit(current_user["id"], current_user["email"], "delete", "domain", domain_id, {})
    return {"message": "Domain deleted"}

# ==================== MONITORING ENDPOINTS ====================

@api_router.post("/domains/{domain_id}/check")
async def check_domain_now(domain_id: str, background_tasks: BackgroundTasks, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN]))):
    """Manually trigger a health check for a domain"""
    domain = await db.domains.find_one({"id": domain_id}, {"_id": 0})
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    background_tasks.add_task(check_domain_health, domain)
    return {"message": f"Health check scheduled for {domain['domain_name']}"}

@api_router.get("/monitoring/stats", response_model=MonitoringStats)
async def get_monitoring_stats(current_user: dict = Depends(get_current_user)):
    """Get monitoring statistics"""
    total = await db.domains.count_documents({"monitoring_enabled": True})
    up = await db.domains.count_documents({"monitoring_enabled": True, "ping_status": "up"})
    down = await db.domains.count_documents({"monitoring_enabled": True, "ping_status": "down"})
    unknown = await db.domains.count_documents({"monitoring_enabled": True, "ping_status": "unknown"})
    
    # Check expiring domains (within 7 days)
    now = datetime.now(timezone.utc)
    week_later = (now + timedelta(days=7)).isoformat()
    
    expiring = await db.domains.count_documents({
        "expiration_date": {"$ne": None, "$lte": week_later, "$gt": now.isoformat()}
    })
    
    expired = await db.domains.count_documents({
        "expiration_date": {"$ne": None, "$lte": now.isoformat()}
    })
    
    return MonitoringStats(
        total_monitored=total,
        up_count=up,
        down_count=down,
        unknown_count=unknown,
        expiring_soon=expiring,
        expired=expired
    )

# ==================== ALERT ENDPOINTS ====================

@api_router.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(
    alert_type: Optional[AlertType] = None,
    severity: Optional[AlertSeverity] = None,
    acknowledged: Optional[bool] = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    query = {}
    if alert_type:
        query["alert_type"] = alert_type.value
    if severity:
        query["severity"] = severity.value
    if acknowledged is not None:
        query["acknowledged"] = acknowledged
    
    alerts = await db.alerts.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return [AlertResponse(**a) for a in alerts]

@api_router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN]))):
    result = await db.alerts.find_one_and_update(
        {"id": alert_id},
        {"$set": {
            "acknowledged": True,
            "acknowledged_by": current_user["email"],
            "acknowledged_at": datetime.now(timezone.utc).isoformat()
        }},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert acknowledged"}

@api_router.post("/domains/{domain_id}/mute")
async def mute_domain(domain_id: str, duration: str = "1h", current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN]))):
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
        {"$set": {
            "domain_id": domain_id,
            "domain_name": domain["domain_name"],
            "muted_by": current_user["email"],
            "muted_at": datetime.now(timezone.utc).isoformat(),
            "muted_until": mute_until.isoformat()
        }},
        upsert=True
    )
    
    return {"message": f"Domain muted until {mute_until.isoformat()}"}

@api_router.delete("/domains/{domain_id}/mute")
async def unmute_domain(domain_id: str, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN]))):
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
    
    brands = {b["id"]: b["name"] for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    categories = {c["id"]: c["name"] for c in await db.categories.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    
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
async def create_group(group_data: GroupCreate, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN]))):
    now = datetime.now(timezone.utc).isoformat()
    group = {"id": str(uuid.uuid4()), **group_data.model_dump(), "created_at": now, "updated_at": now}
    await db.groups.insert_one(group)
    await log_audit(current_user["id"], current_user["email"], "create", "group", group["id"], group_data.model_dump())
    group["domain_count"] = 0
    return GroupResponse(**group)

@api_router.put("/groups/{group_id}", response_model=GroupResponse)
async def update_group(group_id: str, group_data: GroupCreate, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN]))):
    result = await db.groups.find_one_and_update(
        {"id": group_id},
        {"$set": {**group_data.model_dump(), "updated_at": datetime.now(timezone.utc).isoformat()}},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Group not found")
    await log_audit(current_user["id"], current_user["email"], "update", "group", group_id, group_data.model_dump())
    count = await db.domains.count_documents({"group_id": group_id})
    result["domain_count"] = count
    return GroupResponse(**{k: v for k, v in result.items() if k != "_id"})

@api_router.delete("/groups/{group_id}")
async def delete_group(group_id: str, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN]))):
    await db.domains.update_many({"group_id": group_id}, {"$set": {"group_id": None, "parent_domain_id": None}})
    result = await db.groups.delete_one({"id": group_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Group not found")
    await log_audit(current_user["id"], current_user["email"], "delete", "group", group_id, {})
    return {"message": "Group deleted"}

# ==================== CONFLICT DETECTION ====================

@api_router.get("/seo/conflicts")
async def detect_seo_conflicts(current_user: dict = Depends(get_current_user)):
    """Detect SEO structure conflicts"""
    conflicts = []
    
    # Get all domains in groups
    domains = await db.domains.find({"group_id": {"$ne": None}}, {"_id": 0}).to_list(10000)
    domain_map = {d["id"]: d for d in domains}
    
    for domain in domains:
        # 1. Orphan domains (no parent but not LP)
        if domain["tier_level"] != "lp_money_site" and not domain.get("parent_domain_id"):
            conflicts.append({
                "type": "orphan_domain",
                "domain_id": domain["id"],
                "domain_name": domain["domain_name"],
                "severity": "medium",
                "message": "Domain has no parent in the hierarchy"
            })
        
        # 2. NOINDEX domains in Tier 1-2
        if domain["index_status"] == "noindex" and domain["tier_level"] in ["tier_1", "tier_2"]:
            conflicts.append({
                "type": "noindex_high_tier",
                "domain_id": domain["id"],
                "domain_name": domain["domain_name"],
                "severity": "high",
                "message": f"NOINDEX domain used in {domain['tier_level'].replace('_', ' ').title()}"
            })
        
        # 3. Tier jump violations
        if domain.get("parent_domain_id"):
            parent = domain_map.get(domain["parent_domain_id"])
            if parent:
                parent_tier = TIER_HIERARCHY.get(parent["tier_level"], 0)
                child_tier = TIER_HIERARCHY.get(domain["tier_level"], 0)
                
                if child_tier - parent_tier > 1:
                    conflicts.append({
                        "type": "tier_jump",
                        "domain_id": domain["id"],
                        "domain_name": domain["domain_name"],
                        "severity": "medium",
                        "message": f"Tier jump from {parent['tier_level']} to {domain['tier_level']}"
                    })
        
        # 4. Canonical pointing to non-LP
        if domain["domain_status"] == "canonical" and domain.get("parent_domain_id"):
            parent = domain_map.get(domain["parent_domain_id"])
            if parent and parent["tier_level"] != "lp_money_site":
                conflicts.append({
                    "type": "canonical_not_to_lp",
                    "domain_id": domain["id"],
                    "domain_name": domain["domain_name"],
                    "severity": "high",
                    "message": f"Canonical pointing to non-Money Site ({parent['domain_name']})"
                })
    
    return {"conflicts": conflicts, "total": len(conflicts)}

# ==================== REPORTS ENDPOINTS ====================

@api_router.get("/reports/dashboard-stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    total_domains = await db.domains.count_documents({})
    total_groups = await db.groups.count_documents({})
    total_brands = await db.brands.count_documents({})
    indexed_count = await db.domains.count_documents({"index_status": "index"})
    noindex_count = await db.domains.count_documents({"index_status": "noindex"})
    
    # Monitoring stats
    monitored = await db.domains.count_documents({"monitoring_enabled": True})
    up = await db.domains.count_documents({"monitoring_enabled": True, "ping_status": "up"})
    down = await db.domains.count_documents({"monitoring_enabled": True, "ping_status": "down"})
    
    # Active alerts
    active_alerts = await db.alerts.count_documents({"acknowledged": False})
    critical_alerts = await db.alerts.count_documents({"acknowledged": False, "severity": "critical"})
    
    return {
        "total_domains": total_domains,
        "total_groups": total_groups,
        "total_brands": total_brands,
        "indexed_count": indexed_count,
        "noindex_count": noindex_count,
        "index_rate": round((indexed_count / total_domains * 100) if total_domains > 0 else 0, 1),
        "monitored_count": monitored,
        "up_count": up,
        "down_count": down,
        "active_alerts": active_alerts,
        "critical_alerts": critical_alerts
    }

@api_router.get("/reports/tier-distribution")
async def get_tier_distribution(brand_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if brand_id:
        query["brand_id"] = brand_id
    
    pipeline = [
        {"$match": query},
        {"$group": {"_id": "$tier_level", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    
    results = await db.domains.aggregate(pipeline).to_list(100)
    return [{"tier": r["_id"], "count": r["count"]} for r in results]

@api_router.get("/reports/index-status")
async def get_index_status_report(brand_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if brand_id:
        query["brand_id"] = brand_id
    
    pipeline = [
        {"$match": query},
        {"$group": {"_id": "$index_status", "count": {"$sum": 1}}}
    ]
    
    results = await db.domains.aggregate(pipeline).to_list(100)
    return [{"status": r["_id"], "count": r["count"]} for r in results]

@api_router.get("/reports/brand-health")
async def get_brand_health(current_user: dict = Depends(get_current_user)):
    pipeline = [
        {"$group": {
            "_id": "$brand_id",
            "total": {"$sum": 1},
            "indexed": {"$sum": {"$cond": [{"$eq": ["$index_status", "index"]}, 1, 0]}},
            "noindex": {"$sum": {"$cond": [{"$eq": ["$index_status", "noindex"]}, 1, 0]}},
            "up": {"$sum": {"$cond": [{"$eq": ["$ping_status", "up"]}, 1, 0]}},
            "down": {"$sum": {"$cond": [{"$eq": ["$ping_status", "down"]}, 1, 0]}}
        }}
    ]
    
    results = await db.domains.aggregate(pipeline).to_list(100)
    brands = {b["id"]: b["name"] for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    
    return [{
        "brand_id": r["_id"],
        "brand_name": brands.get(r["_id"], "Unknown"),
        "total": r["total"],
        "indexed": r["indexed"],
        "noindex": r["noindex"],
        "up": r["up"],
        "down": r["down"],
        "health_score": round((r["indexed"] / r["total"] * 100) if r["total"] > 0 else 0, 1)
    } for r in results]

@api_router.get("/reports/orphan-domains")
async def get_orphan_domains(current_user: dict = Depends(get_current_user)):
    pipeline = [
        {"$match": {
            "tier_level": {"$ne": "lp_money_site"},
            "parent_domain_id": None,
            "group_id": {"$ne": None}
        }}
    ]
    
    domains = await db.domains.aggregate(pipeline).to_list(1000)
    brands = {b["id"]: b["name"] for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    
    return [{
        "id": d["id"],
        "domain_name": d["domain_name"],
        "tier_level": d["tier_level"],
        "brand_name": brands.get(d.get("brand_id"), "Unknown"),
        "group_id": d.get("group_id")
    } for d in domains]

@api_router.get("/reports/export")
async def export_domains(
    format: str = "json",
    brand_id: Optional[str] = None,
    group_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {}
    if brand_id:
        query["brand_id"] = brand_id
    if group_id:
        query["group_id"] = group_id
    
    domains = await db.domains.find(query, {"_id": 0}).to_list(100000)
    brands = {b["id"]: b["name"] for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    categories = {c["id"]: c["name"] for c in await db.categories.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    groups = {g["id"]: g["name"] for g in await db.groups.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    
    export_data = []
    for d in domains:
        export_data.append({
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
            "created_at": d["created_at"]
        })
    
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
async def get_telegram_settings(current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))):
    settings = await db.settings.find_one({"key": "telegram"}, {"_id": 0})
    if settings:
        # Mask token for security
        if settings.get("bot_token"):
            settings["bot_token"] = settings["bot_token"][:10] + "..." + settings["bot_token"][-5:]
    return settings or {"bot_token": "", "chat_id": ""}

@api_router.put("/settings/telegram")
async def update_telegram_settings(config: TelegramConfig, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))):
    update_data = {"key": "telegram", "updated_at": datetime.now(timezone.utc).isoformat()}
    if config.bot_token:
        update_data["bot_token"] = config.bot_token
    if config.chat_id:
        update_data["chat_id"] = config.chat_id
    
    await db.settings.update_one(
        {"key": "telegram"},
        {"$set": update_data},
        upsert=True
    )
    return {"message": "Telegram settings updated"}

@api_router.post("/settings/telegram/test")
async def test_telegram(current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))):
    """Send a test message to verify Telegram configuration"""
    message = f"""✅ <b>SEO-NOC Test Alert</b>

This is a test message from SEO-NOC.
Sent by: {current_user['email']}
Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"""
    
    success = await send_telegram_alert(message)
    if success:
        return {"message": "Test message sent successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send test message. Check your Telegram configuration.")

# ==================== AUDIT LOGS ====================

@api_router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    limit: int = 100,
    entity_type: Optional[str] = None,
    current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))
):
    query = {}
    if entity_type:
        query["entity_type"] = entity_type
    
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return [AuditLogResponse(**log) for log in logs]

# ==================== SEED DATA ====================

@api_router.post("/seed-data")
async def seed_demo_data(current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))):
    existing_brands = await db.brands.count_documents({})
    if existing_brands > 0:
        raise HTTPException(status_code=400, detail="Data already exists. Clear database first.")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Create brands
    brands = [
        {"id": str(uuid.uuid4()), "name": "Panen138", "description": "Premium brand network", "created_at": now, "updated_at": now},
        {"id": str(uuid.uuid4()), "name": "PANEN77", "description": "Secondary brand network", "created_at": now, "updated_at": now},
        {"id": str(uuid.uuid4()), "name": "DEWI138", "description": "Emerging brand network", "created_at": now, "updated_at": now}
    ]
    await db.brands.insert_many(brands)
    
    # Get categories
    categories = await db.categories.find({}, {"_id": 0}).to_list(100)
    cat_map = {c["name"]: c["id"] for c in categories}
    
    # Create groups
    groups = [
        {"id": str(uuid.uuid4()), "name": "Main SEO Network", "description": "Primary link building network", "created_at": now, "updated_at": now},
        {"id": str(uuid.uuid4()), "name": "Support Network", "description": "Secondary support links", "created_at": now, "updated_at": now}
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
        "expiration_date": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
        "auto_renew": True,
        "monitoring_enabled": True,
        "monitoring_interval": "5min",
        "ping_status": "unknown",
        "notes": "Main money site",
        "created_at": now,
        "updated_at": now
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
            "expiration_date": (datetime.now(timezone.utc) + timedelta(days=180 + i*30)).isoformat(),
            "auto_renew": True,
            "monitoring_enabled": True,
            "monitoring_interval": "15min",
            "ping_status": "unknown",
            "notes": f"Tier 1 site {i}",
            "created_at": now,
            "updated_at": now
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
                "expiration_date": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
                "auto_renew": False,
                "monitoring_enabled": True,
                "monitoring_interval": "1hour",
                "ping_status": "unknown",
                "notes": f"Tier 2 under tier1-site{i+1}",
                "created_at": now,
                "updated_at": now
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
                "expiration_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                "auto_renew": False,
                "monitoring_enabled": False,
                "monitoring_interval": "daily",
                "ping_status": "unknown",
                "notes": "",
                "created_at": now,
                "updated_at": now
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
        "expiration_date": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),  # Expiring soon!
        "auto_renew": False,
        "monitoring_enabled": True,
        "monitoring_interval": "1hour",
        "ping_status": "unknown",
        "notes": "Orphan domain for testing",
        "created_at": now,
        "updated_at": now
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
        "expiration_date": (datetime.now(timezone.utc) + timedelta(days=200)).isoformat(),
        "auto_renew": True,
        "monitoring_enabled": True,
        "monitoring_interval": "15min",
        "ping_status": "unknown",
        "notes": "Support network main",
        "created_at": now,
        "updated_at": now
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
            "expiration_date": (datetime.now(timezone.utc) + timedelta(days=150)).isoformat(),
            "auto_renew": True,
            "monitoring_enabled": True,
            "monitoring_interval": "1hour",
            "ping_status": "unknown",
            "notes": "",
            "created_at": now,
            "updated_at": now
        }
        domains.append(d)
    
    await db.domains.insert_many(domains)
    
    return {"message": f"Seeded {len(brands)} brands, {len(groups)} groups, {len(domains)} domains"}

# Initialize V3 router with dependencies
init_v3_router(
    database=db,
    current_user_dep=get_current_user,
    roles_dep=require_roles,
    activity_service=activity_log_service,
    tier_svc=tier_service
)

# Include routers
app.include_router(api_router)  # V2 API (legacy)
app.include_router(v3_router)   # V3 API (new architecture)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
