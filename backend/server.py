from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
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

# Create the main app
app = FastAPI(title="SEO Domain Network Manager API")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# Enums
class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    VIEWER = "viewer"

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

# Tier hierarchy for validation
TIER_HIERARCHY = {
    "tier_5": 5,
    "tier_4": 4,
    "tier_3": 3,
    "tier_2": 2,
    "tier_1": 1,
    "lp_money_site": 0
}

# Models
class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: UserRole = UserRole.VIEWER

class UserCreate(UserBase):
    password: str

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

class BrandBase(BaseModel):
    name: str
    description: Optional[str] = ""

class BrandCreate(BrandBase):
    pass

class BrandResponse(BrandBase):
    model_config = ConfigDict(extra="ignore")
    id: str
    created_at: str
    updated_at: str

class DomainBase(BaseModel):
    domain_name: str
    brand_id: str
    domain_status: DomainStatus = DomainStatus.CANONICAL
    index_status: IndexStatus = IndexStatus.INDEX
    tier_level: TierLevel = TierLevel.TIER_5
    group_id: Optional[str] = None
    parent_domain_id: Optional[str] = None
    notes: Optional[str] = ""

class DomainCreate(DomainBase):
    pass

class DomainUpdate(BaseModel):
    domain_name: Optional[str] = None
    brand_id: Optional[str] = None
    domain_status: Optional[DomainStatus] = None
    index_status: Optional[IndexStatus] = None
    tier_level: Optional[TierLevel] = None
    group_id: Optional[str] = None
    parent_domain_id: Optional[str] = None
    notes: Optional[str] = None

class DomainResponse(DomainBase):
    model_config = ConfigDict(extra="ignore")
    id: str
    brand_name: Optional[str] = None
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

# Helper functions
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

# Auth endpoints
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
        id=user["id"],
        email=user["email"],
        name=user["name"],
        role=user["role"],
        created_at=user["created_at"],
        updated_at=user["updated_at"]
    )
    return TokenResponse(access_token=token, user=user_response)

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user["id"], user["email"], user["role"])
    user_response = UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        role=user["role"],
        created_at=user["created_at"],
        updated_at=user["updated_at"]
    )
    return TokenResponse(access_token=token, user=user_response)

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(**current_user)

# User management (Super Admin only)
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

# Brand endpoints
@api_router.get("/brands", response_model=List[BrandResponse])
async def get_brands(current_user: dict = Depends(get_current_user)):
    brands = await db.brands.find({}, {"_id": 0}).to_list(1000)
    return [BrandResponse(**b) for b in brands]

@api_router.post("/brands", response_model=BrandResponse)
async def create_brand(brand_data: BrandCreate, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))):
    now = datetime.now(timezone.utc).isoformat()
    brand = {
        "id": str(uuid.uuid4()),
        **brand_data.model_dump(),
        "created_at": now,
        "updated_at": now
    }
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

# Domain endpoints
@api_router.get("/domains", response_model=List[DomainResponse])
async def get_domains(
    brand_id: Optional[str] = None,
    domain_status: Optional[DomainStatus] = None,
    index_status: Optional[IndexStatus] = None,
    tier_level: Optional[TierLevel] = None,
    group_id: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    query = {}
    if brand_id:
        query["brand_id"] = brand_id
    if domain_status:
        query["domain_status"] = domain_status.value
    if index_status:
        query["index_status"] = index_status.value
    if tier_level:
        query["tier_level"] = tier_level.value
    if group_id:
        query["group_id"] = group_id
    if search:
        query["domain_name"] = {"$regex": search, "$options": "i"}
    
    domains = await db.domains.find(query, {"_id": 0}).to_list(10000)
    
    # Enrich with brand and group names
    brands = {b["id"]: b["name"] for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    groups = {g["id"]: g["name"] for g in await db.groups.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    
    result = []
    for d in domains:
        d["brand_name"] = brands.get(d.get("brand_id"), "")
        d["group_name"] = groups.get(d.get("group_id"), "")
        result.append(DomainResponse(**d))
    
    return result

@api_router.get("/domains/{domain_id}", response_model=DomainResponse)
async def get_domain(domain_id: str, current_user: dict = Depends(get_current_user)):
    domain = await db.domains.find_one({"id": domain_id}, {"_id": 0})
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    brand = await db.brands.find_one({"id": domain.get("brand_id")}, {"_id": 0, "name": 1})
    group = await db.groups.find_one({"id": domain.get("group_id")}, {"_id": 0, "name": 1}) if domain.get("group_id") else None
    
    domain["brand_name"] = brand["name"] if brand else ""
    domain["group_name"] = group["name"] if group else ""
    
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
            raise HTTPException(status_code=400, detail="Child tier must be higher than parent tier (Tier 5 > Tier 4 > ... > LP)")
    
    now = datetime.now(timezone.utc).isoformat()
    domain = {
        "id": str(uuid.uuid4()),
        **domain_data.model_dump(),
        "created_at": now,
        "updated_at": now
    }
    # Convert enums to values
    domain["domain_status"] = domain["domain_status"].value if isinstance(domain["domain_status"], DomainStatus) else domain["domain_status"]
    domain["index_status"] = domain["index_status"].value if isinstance(domain["index_status"], IndexStatus) else domain["index_status"]
    domain["tier_level"] = domain["tier_level"].value if isinstance(domain["tier_level"], TierLevel) else domain["tier_level"]
    
    await db.domains.insert_one(domain)
    await log_audit(current_user["id"], current_user["email"], "create", "domain", domain["id"], {"domain_name": domain_data.domain_name})
    
    domain["brand_name"] = brand["name"]
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
        if isinstance(new_tier, TierLevel):
            new_tier = new_tier.value
        
        parent_tier = TIER_HIERARCHY.get(parent["tier_level"], 0)
        child_tier = TIER_HIERARCHY.get(new_tier, 0)
        
        if child_tier <= parent_tier:
            raise HTTPException(status_code=400, detail="Child tier must be higher than parent tier")
    
    # Convert enums
    for field in ["domain_status", "index_status", "tier_level"]:
        if field in update_dict and update_dict[field]:
            if hasattr(update_dict[field], 'value'):
                update_dict[field] = update_dict[field].value
    
    update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.domains.find_one_and_update(
        {"id": domain_id},
        {"$set": update_dict},
        return_document=True
    )
    
    await log_audit(current_user["id"], current_user["email"], "update", "domain", domain_id, update_dict)
    
    brand = await db.brands.find_one({"id": result.get("brand_id")}, {"_id": 0, "name": 1})
    group = await db.groups.find_one({"id": result.get("group_id")}, {"_id": 0, "name": 1}) if result.get("group_id") else None
    
    result["brand_name"] = brand["name"] if brand else ""
    result["group_name"] = group["name"] if group else ""
    
    return DomainResponse(**{k: v for k, v in result.items() if k != "_id"})

@api_router.delete("/domains/{domain_id}")
async def delete_domain(domain_id: str, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN]))):
    # Check if any domain has this as parent
    children = await db.domains.count_documents({"parent_domain_id": domain_id})
    if children > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete domain with {children} child domains")
    
    result = await db.domains.delete_one({"id": domain_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    await log_audit(current_user["id"], current_user["email"], "delete", "domain", domain_id, {})
    return {"message": "Domain deleted"}

# Group endpoints
@api_router.get("/groups", response_model=List[GroupResponse])
async def get_groups(current_user: dict = Depends(get_current_user)):
    groups = await db.groups.find({}, {"_id": 0}).to_list(1000)
    
    # Get domain counts
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
    
    domain_responses = []
    for d in domains:
        d["brand_name"] = brands.get(d.get("brand_id"), "")
        d["group_name"] = group["name"]
        domain_responses.append(DomainResponse(**d))
    
    group["domain_count"] = len(domains)
    group["domains"] = domain_responses
    
    return GroupDetail(**group)

@api_router.post("/groups", response_model=GroupResponse)
async def create_group(group_data: GroupCreate, current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ADMIN]))):
    now = datetime.now(timezone.utc).isoformat()
    group = {
        "id": str(uuid.uuid4()),
        **group_data.model_dump(),
        "created_at": now,
        "updated_at": now
    }
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
    # Remove group reference from domains
    await db.domains.update_many({"group_id": group_id}, {"$set": {"group_id": None, "parent_domain_id": None}})
    
    result = await db.groups.delete_one({"id": group_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Group not found")
    
    await log_audit(current_user["id"], current_user["email"], "delete", "group", group_id, {})
    return {"message": "Group deleted"}

# Reports endpoints
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
            "noindex": {"$sum": {"$cond": [{"$eq": ["$index_status", "noindex"]}, 1, 0]}}
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
        "health_score": round((r["indexed"] / r["total"] * 100) if r["total"] > 0 else 0, 1)
    } for r in results]

@api_router.get("/reports/orphan-domains")
async def get_orphan_domains(current_user: dict = Depends(get_current_user)):
    """Find domains that should have parents but don't"""
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

@api_router.get("/reports/dashboard-stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    total_domains = await db.domains.count_documents({})
    total_groups = await db.groups.count_documents({})
    total_brands = await db.brands.count_documents({})
    indexed_count = await db.domains.count_documents({"index_status": "index"})
    noindex_count = await db.domains.count_documents({"index_status": "noindex"})
    
    return {
        "total_domains": total_domains,
        "total_groups": total_groups,
        "total_brands": total_brands,
        "indexed_count": indexed_count,
        "noindex_count": noindex_count,
        "index_rate": round((indexed_count / total_domains * 100) if total_domains > 0 else 0, 1)
    }

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
    groups = {g["id"]: g["name"] for g in await db.groups.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    
    export_data = []
    for d in domains:
        export_data.append({
            "domain_name": d["domain_name"],
            "brand": brands.get(d.get("brand_id"), ""),
            "group": groups.get(d.get("group_id"), ""),
            "tier_level": d["tier_level"],
            "domain_status": d["domain_status"],
            "index_status": d["index_status"],
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

# Audit logs
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

# Seed data endpoint (for demo)
@api_router.post("/seed-data")
async def seed_demo_data(current_user: dict = Depends(require_roles([UserRole.SUPER_ADMIN]))):
    # Check if data already exists
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
    
    # Create groups
    groups = [
        {"id": str(uuid.uuid4()), "name": "Main SEO Network", "description": "Primary link building network", "created_at": now, "updated_at": now},
        {"id": str(uuid.uuid4()), "name": "Support Network", "description": "Secondary support links", "created_at": now, "updated_at": now}
    ]
    await db.groups.insert_many(groups)
    
    # Create domains with hierarchy
    domains = []
    
    # LP/Money Site
    lp = {"id": str(uuid.uuid4()), "domain_name": "moneysite.com", "brand_id": brands[0]["id"], "domain_status": "canonical", "index_status": "index", "tier_level": "lp_money_site", "group_id": groups[0]["id"], "parent_domain_id": None, "notes": "Main money site", "created_at": now, "updated_at": now}
    domains.append(lp)
    
    # Tier 1 domains
    t1_domains = [
        {"id": str(uuid.uuid4()), "domain_name": f"tier1-site{i}.com", "brand_id": brands[0]["id"], "domain_status": "canonical", "index_status": "index", "tier_level": "tier_1", "group_id": groups[0]["id"], "parent_domain_id": lp["id"], "notes": f"Tier 1 site {i}", "created_at": now, "updated_at": now}
        for i in range(1, 4)
    ]
    domains.extend(t1_domains)
    
    # Tier 2 domains
    t2_domains = []
    for i, t1 in enumerate(t1_domains):
        for j in range(1, 3):
            t2 = {"id": str(uuid.uuid4()), "domain_name": f"tier2-site{i+1}-{j}.com", "brand_id": brands[1]["id"], "domain_status": "canonical", "index_status": "index" if j == 1 else "noindex", "tier_level": "tier_2", "group_id": groups[0]["id"], "parent_domain_id": t1["id"], "notes": f"Tier 2 under tier1-site{i+1}", "created_at": now, "updated_at": now}
            t2_domains.append(t2)
    domains.extend(t2_domains)
    
    # Tier 3 domains
    t3_domains = []
    for i, t2 in enumerate(t2_domains[:3]):
        for j in range(1, 3):
            t3 = {"id": str(uuid.uuid4()), "domain_name": f"tier3-site{i+1}-{j}.net", "brand_id": brands[2]["id"], "domain_status": "301_redirect" if j == 2 else "canonical", "index_status": "noindex", "tier_level": "tier_3", "group_id": groups[0]["id"], "parent_domain_id": t2["id"], "notes": "", "created_at": now, "updated_at": now}
            t3_domains.append(t3)
    domains.extend(t3_domains)
    
    # Some orphan domains (for testing analysis)
    orphan = {"id": str(uuid.uuid4()), "domain_name": "orphan-domain.com", "brand_id": brands[0]["id"], "domain_status": "canonical", "index_status": "noindex", "tier_level": "tier_3", "group_id": groups[0]["id"], "parent_domain_id": None, "notes": "Orphan domain for testing", "created_at": now, "updated_at": now}
    domains.append(orphan)
    
    # Domains in second group
    lp2 = {"id": str(uuid.uuid4()), "domain_name": "support-main.com", "brand_id": brands[1]["id"], "domain_status": "canonical", "index_status": "index", "tier_level": "lp_money_site", "group_id": groups[1]["id"], "parent_domain_id": None, "notes": "Support network main", "created_at": now, "updated_at": now}
    domains.append(lp2)
    
    for i in range(1, 4):
        d = {"id": str(uuid.uuid4()), "domain_name": f"support-tier1-{i}.com", "brand_id": brands[1]["id"], "domain_status": "canonical", "index_status": "index", "tier_level": "tier_1", "group_id": groups[1]["id"], "parent_domain_id": lp2["id"], "notes": "", "created_at": now, "updated_at": now}
        domains.append(d)
    
    await db.domains.insert_many(domains)
    
    return {"message": f"Seeded {len(brands)} brands, {len(groups)} groups, {len(domains)} domains"}

# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
