"""
SEO-NOC V3 API Router
=====================
New API endpoints for V3 architecture:
- /api/v3/asset-domains - Pure inventory management
- /api/v3/networks - SEO network management
- /api/v3/structure - SEO structure entries with derived tiers
- /api/v3/activity-logs - Activity log queries
- /api/v3/monitoring - Domain monitoring settings and controls
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import httpx
import logging

# Import models
import sys
sys.path.insert(0, '/app/backend')
from models_v3 import (
    AssetDomainCreate, AssetDomainUpdate, AssetDomainResponse,
    SeoNetworkCreate, SeoNetworkUpdate, SeoNetworkResponse, SeoNetworkDetail,
    SeoNetworkCreateLegacy, MainNodeConfig,
    SeoStructureEntryCreate, SeoStructureEntryUpdate, SeoStructureEntryResponse,
    ActivityLogResponse,
    RegistrarCreate, RegistrarUpdate, RegistrarResponse, RegistrarStatus,
    SeoConflict, ConflictType, ConflictSeverity,
    MonitoringSettings, MonitoringSettingsUpdate,
    AssetStatus, NetworkStatus, DomainRole, SeoStatus, IndexStatus,
    ActionType, EntityType, get_tier_label
)

logger = logging.getLogger(__name__)

# Router
router = APIRouter(prefix="/api/v3", tags=["V3 API"])


# ==================== DEPENDENCIES ====================

# These will be injected from server.py
db = None
get_current_user = None
require_roles = None
activity_log_service = None
tier_service = None


def init_v3_router(
    database,
    current_user_dep,
    roles_dep,
    activity_service,
    tier_svc
):
    """Initialize V3 router with dependencies"""
    global db, _get_current_user_dep, require_roles, activity_log_service, tier_service
    db = database
    _get_current_user_dep = current_user_dep
    require_roles = roles_dep
    activity_log_service = activity_service
    tier_service = tier_svc


# Store the dependency reference
_get_current_user_dep = None
_security = HTTPBearer()


async def get_current_user_wrapper(credentials: HTTPAuthorizationCredentials = Depends(_security)):
    """Wrapper that calls the injected auth dependency"""
    if _get_current_user_dep is None:
        raise HTTPException(status_code=500, detail="Auth not initialized")
    return await _get_current_user_dep(credentials)


# ==================== TELEGRAM HELPER ====================

async def send_v3_telegram_alert(message: str) -> bool:
    """Send alert to Telegram for V3 events"""
    settings = await db.settings.find_one({"key": "telegram"}, {"_id": 0})
    
    if not settings or not settings.get("bot_token") or not settings.get("chat_id"):
        logger.warning("Telegram not configured, skipping V3 alert")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{settings['bot_token']}/sendMessage"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={
                "chat_id": settings["chat_id"],
                "text": message,
                "parse_mode": "HTML"
            }, timeout=10)
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send V3 Telegram alert: {e}")
        return False


# ==================== BRAND SCOPING HELPERS ====================

def get_user_brand_scope(user: dict) -> Optional[List[str]]:
    """
    Get user's brand scope.
    Returns None for Super Admin (full access), or list of brand_ids for restricted users.
    """
    if user.get("role") == "super_admin":
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


# ==================== HELPER FUNCTIONS ====================

def normalize_path(path: str | None) -> str | None:
    """
    Normalize an optimized_path value.
    
    Rules:
    - Empty/None/whitespace-only → None (represents domain root)
    - "/" alone → None (represents domain root)
    - Otherwise, ensure path starts with "/"
    - Strip trailing slashes (except root)
    """
    if not path or path.strip() == "" or path.strip() == "/":
        return None
    
    path = path.strip()
    if not path.startswith("/"):
        path = "/" + path
    
    # Remove trailing slash if not root
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    
    return path


async def enrich_asset_domain(asset: dict) -> dict:
    """Enrich asset domain with brand/category/registrar names"""
    if asset.get("brand_id"):
        brand = await db.brands.find_one({"id": asset["brand_id"]}, {"_id": 0, "name": 1})
        asset["brand_name"] = brand["name"] if brand else None
    else:
        asset["brand_name"] = None
    
    if asset.get("category_id"):
        category = await db.categories.find_one({"id": asset["category_id"]}, {"_id": 0, "name": 1})
        asset["category_name"] = category["name"] if category else None
    else:
        asset["category_name"] = None
    
    # Enrich registrar name from registrar_id
    if asset.get("registrar_id"):
        registrar = await db.registrars.find_one({"id": asset["registrar_id"]}, {"_id": 0, "name": 1})
        asset["registrar_name"] = registrar["name"] if registrar else None
    else:
        asset["registrar_name"] = asset.get("registrar")  # Legacy fallback
    
    return asset


async def enrich_structure_entry(entry: dict, network_tiers: Dict[str, int] = None) -> dict:
    """Enrich structure entry with names, node label, and calculated tier"""
    # Get asset domain name
    if entry.get("asset_domain_id"):
        asset = await db.asset_domains.find_one(
            {"id": entry["asset_domain_id"]}, 
            {"_id": 0, "domain_name": 1, "brand_id": 1}
        )
        entry["domain_name"] = asset["domain_name"] if asset else None
        
        # Build node_label (domain + optional path)
        if asset:
            if entry.get("optimized_path"):
                entry["node_label"] = f"{asset['domain_name']}{entry['optimized_path']}"
            else:
                entry["node_label"] = asset["domain_name"]
        else:
            entry["node_label"] = None
        
        # Get brand name
        if asset and asset.get("brand_id"):
            brand = await db.brands.find_one({"id": asset["brand_id"]}, {"_id": 0, "name": 1})
            entry["brand_name"] = brand["name"] if brand else None
        else:
            entry["brand_name"] = None
    
    # Get target info - support both new (target_entry_id) and legacy (target_asset_domain_id)
    entry["target_domain_name"] = None
    entry["target_entry_path"] = None
    
    if entry.get("target_entry_id"):
        # Node-to-node relationship
        target_entry = await db.seo_structure_entries.find_one(
            {"id": entry["target_entry_id"]},
            {"_id": 0, "asset_domain_id": 1, "optimized_path": 1}
        )
        if target_entry:
            target_asset = await db.asset_domains.find_one(
                {"id": target_entry["asset_domain_id"]},
                {"_id": 0, "domain_name": 1}
            )
            if target_asset:
                entry["target_domain_name"] = target_asset["domain_name"]
                entry["target_entry_path"] = target_entry.get("optimized_path")
    elif entry.get("target_asset_domain_id"):
        # Legacy domain-to-domain relationship
        target = await db.asset_domains.find_one(
            {"id": entry["target_asset_domain_id"]},
            {"_id": 0, "domain_name": 1}
        )
        entry["target_domain_name"] = target["domain_name"] if target else None
    
    # Get network name
    if entry.get("network_id"):
        network = await db.seo_networks.find_one(
            {"id": entry["network_id"]},
            {"_id": 0, "name": 1}
        )
        entry["network_name"] = network["name"] if network else None
    else:
        entry["network_name"] = None
    
    # Calculate tier based on entry_id (node-based)
    if network_tiers and entry.get("id"):
        tier = network_tiers.get(entry["id"], 5)
        entry["calculated_tier"] = tier
        entry["tier_label"] = get_tier_label(tier)
    elif entry.get("network_id") and tier_service:
        tier, label = await tier_service.calculate_domain_tier(
            entry["network_id"],
            entry["id"]
        )
        entry["calculated_tier"] = tier
        entry["tier_label"] = label
    else:
        entry["calculated_tier"] = None
        entry["tier_label"] = None
    
    return entry


# ==================== REGISTRAR ENDPOINTS (MASTER DATA) ====================

@router.get("/registrars", response_model=List[RegistrarResponse])
async def get_registrars(
    status: Optional[RegistrarStatus] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get all registrars with optional filters"""
    query = {}
    
    if status:
        query["status"] = status.value
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    
    registrars = await db.registrars.find(query, {"_id": 0}).to_list(1000)
    
    # Add domain counts
    for reg in registrars:
        reg["domain_count"] = await db.asset_domains.count_documents({"registrar_id": reg["id"]})
    
    return [RegistrarResponse(**r) for r in registrars]


@router.get("/registrars/{registrar_id}", response_model=RegistrarResponse)
async def get_registrar(
    registrar_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get a single registrar by ID"""
    registrar = await db.registrars.find_one({"id": registrar_id}, {"_id": 0})
    if not registrar:
        raise HTTPException(status_code=404, detail="Registrar not found")
    
    registrar["domain_count"] = await db.asset_domains.count_documents({"registrar_id": registrar_id})
    return RegistrarResponse(**registrar)


@router.post("/registrars", response_model=RegistrarResponse)
async def create_registrar(
    data: RegistrarCreate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Create a new registrar (super_admin only)"""
    # Check super_admin role
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only super_admin can manage registrars")
    
    # Check for duplicate name
    existing = await db.registrars.find_one({"name": {"$regex": f"^{data.name}$", "$options": "i"}})
    if existing:
        raise HTTPException(status_code=400, detail="Registrar name already exists")
    
    now = datetime.now(timezone.utc).isoformat()
    registrar = {
        "id": str(uuid.uuid4()),
        **data.model_dump(),
        "created_at": now,
        "updated_at": now
    }
    
    # Convert enums
    if registrar.get("status") and hasattr(registrar["status"], "value"):
        registrar["status"] = registrar["status"].value
    
    await db.registrars.insert_one(registrar)
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.CREATE,
            entity_type=EntityType.REGISTRAR,
            entity_id=registrar["id"],
            after_value=registrar
        )
    
    registrar["domain_count"] = 0
    return RegistrarResponse(**registrar)


@router.put("/registrars/{registrar_id}", response_model=RegistrarResponse)
async def update_registrar(
    registrar_id: str,
    data: RegistrarUpdate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Update a registrar (super_admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only super_admin can manage registrars")
    
    existing = await db.registrars.find_one({"id": registrar_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Registrar not found")
    
    update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
    
    # Check for duplicate name if changing
    if "name" in update_dict and update_dict["name"] != existing["name"]:
        dup = await db.registrars.find_one({
            "name": {"$regex": f"^{update_dict['name']}$", "$options": "i"},
            "id": {"$ne": registrar_id}
        })
        if dup:
            raise HTTPException(status_code=400, detail="Registrar name already exists")
    
    # Convert enums
    if update_dict.get("status") and hasattr(update_dict["status"], "value"):
        update_dict["status"] = update_dict["status"].value
    
    update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.registrars.update_one({"id": registrar_id}, {"$set": update_dict})
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.REGISTRAR,
            entity_id=registrar_id,
            before_value=existing,
            after_value={**existing, **update_dict}
        )
    
    updated = await db.registrars.find_one({"id": registrar_id}, {"_id": 0})
    updated["domain_count"] = await db.asset_domains.count_documents({"registrar_id": registrar_id})
    return RegistrarResponse(**updated)


@router.delete("/registrars/{registrar_id}")
async def delete_registrar(
    registrar_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Delete a registrar (super_admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only super_admin can manage registrars")
    
    existing = await db.registrars.find_one({"id": registrar_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Registrar not found")
    
    # Check if used by any domains
    domain_count = await db.asset_domains.count_documents({"registrar_id": registrar_id})
    if domain_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete: {domain_count} domains use this registrar"
        )
    
    await db.registrars.delete_one({"id": registrar_id})
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.DELETE,
            entity_type=EntityType.REGISTRAR,
            entity_id=registrar_id,
            before_value=existing
        )
    
    return {"message": "Registrar deleted"}


# ==================== ASSET DOMAINS ENDPOINTS ====================

@router.get("/asset-domains", response_model=List[AssetDomainResponse])
async def get_asset_domains(
    brand_id: Optional[str] = None,
    category_id: Optional[str] = None,
    registrar_id: Optional[str] = None,
    status: Optional[AssetStatus] = None,
    monitoring_enabled: Optional[bool] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get all asset domains with optional filters - BRAND SCOPED"""
    # Start with brand scope filter
    query = build_brand_filter(current_user)
    
    # If specific brand requested, validate access
    if brand_id:
        require_brand_access(brand_id, current_user)
        query["brand_id"] = brand_id
    
    if category_id:
        query["category_id"] = category_id
    if registrar_id:
        query["registrar_id"] = registrar_id
    if status:
        query["status"] = status.value
    if monitoring_enabled is not None:
        query["monitoring_enabled"] = monitoring_enabled
    if search:
        query["domain_name"] = {"$regex": search, "$options": "i"}
    
    assets = await db.asset_domains.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    
    # Batch enrich
    brands = {b["id"]: b["name"] for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    categories = {c["id"]: c["name"] for c in await db.categories.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    registrars = {r["id"]: r["name"] for r in await db.registrars.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    
    for asset in assets:
        asset["brand_name"] = brands.get(asset.get("brand_id"))
        asset["category_name"] = categories.get(asset.get("category_id"))
        # Use registrar_id lookup, fallback to legacy field
        asset["registrar_name"] = registrars.get(asset.get("registrar_id")) or asset.get("registrar")
    
    return [AssetDomainResponse(**a) for a in assets]


@router.get("/asset-domains/{asset_id}", response_model=AssetDomainResponse)
async def get_asset_domain(
    asset_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get a single asset domain by ID - BRAND SCOPED"""
    asset = await db.asset_domains.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset domain not found")
    
    # Validate brand access
    require_brand_access(asset.get("brand_id", ""), current_user)
    
    asset = await enrich_asset_domain(asset)
    return AssetDomainResponse(**asset)


@router.post("/asset-domains", response_model=AssetDomainResponse)
async def create_asset_domain(
    data: AssetDomainCreate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Create a new asset domain - BRAND SCOPED"""
    # Validate brand exists and user has access
    if data.brand_id:
        brand = await db.brands.find_one({"id": data.brand_id})
        if not brand:
            raise HTTPException(status_code=400, detail="Brand not found")
        require_brand_access(data.brand_id, current_user)
    else:
        raise HTTPException(status_code=400, detail="brand_id is required")
    
    # Validate registrar exists if provided
    if data.registrar_id:
        registrar = await db.registrars.find_one({"id": data.registrar_id})
        if not registrar:
            raise HTTPException(status_code=400, detail="Registrar not found")
    
    # Check for duplicate domain name
    existing = await db.asset_domains.find_one({"domain_name": data.domain_name})
    if existing:
        raise HTTPException(status_code=400, detail="Domain name already exists")
    
    now = datetime.now(timezone.utc).isoformat()
    asset = {
        "id": str(uuid.uuid4()),
        "legacy_id": None,
        **data.model_dump(),
        "created_at": now,
        "updated_at": now
    }
    
    # Convert enums to values
    if asset.get("status") and hasattr(asset["status"], "value"):
        asset["status"] = asset["status"].value
    if asset.get("monitoring_interval") and hasattr(asset["monitoring_interval"], "value"):
        asset["monitoring_interval"] = asset["monitoring_interval"].value
    if asset.get("ping_status") and hasattr(asset["ping_status"], "value"):
        asset["ping_status"] = asset["ping_status"].value
    
    await db.asset_domains.insert_one(asset)
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.CREATE,
            entity_type=EntityType.ASSET_DOMAIN,
            entity_id=asset["id"],
            after_value=asset
        )
    
    asset = await enrich_asset_domain(asset)
    return AssetDomainResponse(**asset)


@router.put("/asset-domains/{asset_id}", response_model=AssetDomainResponse)
async def update_asset_domain(
    asset_id: str,
    data: AssetDomainUpdate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Update an asset domain - BRAND SCOPED"""
    existing = await db.asset_domains.find_one({"id": asset_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Asset domain not found")
    
    # Validate brand access for existing domain
    require_brand_access(existing.get("brand_id", ""), current_user)
    
    update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
    
    # Convert enums
    for field in ["status", "monitoring_interval"]:
        if field in update_dict and hasattr(update_dict[field], "value"):
            update_dict[field] = update_dict[field].value
    
    update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.asset_domains.update_one({"id": asset_id}, {"$set": update_dict})
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.ASSET_DOMAIN,
            entity_id=asset_id,
            before_value=existing,
            after_value={**existing, **update_dict}
        )
    
    updated = await db.asset_domains.find_one({"id": asset_id}, {"_id": 0})
    updated = await enrich_asset_domain(updated)
    return AssetDomainResponse(**updated)


@router.delete("/asset-domains/{asset_id}")
async def delete_asset_domain(
    asset_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Delete an asset domain"""
    existing = await db.asset_domains.find_one({"id": asset_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Asset domain not found")
    
    # Check if used in structure entries
    structure_count = await db.seo_structure_entries.count_documents({
        "$or": [
            {"asset_domain_id": asset_id},
            {"target_asset_domain_id": asset_id}
        ]
    })
    if structure_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete: domain is used in {structure_count} structure entries"
        )
    
    await db.asset_domains.delete_one({"id": asset_id})
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.DELETE,
            entity_type=EntityType.ASSET_DOMAIN,
            entity_id=asset_id,
            before_value=existing
        )
    
    return {"message": "Asset domain deleted"}


# ==================== SEO NETWORKS ENDPOINTS ====================

@router.get("/networks", response_model=List[SeoNetworkResponse])
async def get_networks(
    brand_id: Optional[str] = None,
    status: Optional[NetworkStatus] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get all SEO networks"""
    query = {}
    
    if brand_id:
        query["brand_id"] = brand_id
    if status:
        query["status"] = status.value
    
    networks = await db.seo_networks.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    
    # Get brand names and domain counts
    brands = {b["id"]: b["name"] for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    
    for network in networks:
        network["brand_name"] = brands.get(network.get("brand_id"))
        network["domain_count"] = await db.seo_structure_entries.count_documents({"network_id": network["id"]})
    
    return [SeoNetworkResponse(**n) for n in networks]


@router.get("/networks/{network_id}", response_model=SeoNetworkDetail)
async def get_network(
    network_id: str,
    include_tiers: bool = True,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get a single SEO network with structure entries and calculated tiers"""
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    # Get brand name
    if network.get("brand_id"):
        brand = await db.brands.find_one({"id": network["brand_id"]}, {"_id": 0, "name": 1})
        network["brand_name"] = brand["name"] if brand else None
    else:
        network["brand_name"] = None
    
    # Get structure entries
    entries = await db.seo_structure_entries.find(
        {"network_id": network_id},
        {"_id": 0}
    ).to_list(10000)
    
    # Calculate tiers for entire network (more efficient)
    network_tiers = {}
    if include_tiers and tier_service:
        network_tiers = await tier_service.calculate_network_tiers(network_id)
    
    # Enrich entries
    enriched_entries = []
    for entry in entries:
        entry = await enrich_structure_entry(entry, network_tiers)
        enriched_entries.append(SeoStructureEntryResponse(**entry))
    
    network["domain_count"] = len(entries)
    network["entries"] = enriched_entries
    
    return SeoNetworkDetail(**network)


@router.post("/networks", response_model=SeoNetworkResponse)
async def create_network(
    data: SeoNetworkCreate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Create a new SEO network with initial main node.
    
    Every network MUST have a main node defined at creation time.
    The main domain MUST belong to the same brand as the network.
    """
    # Validate brand exists (required field)
    brand = await db.brands.find_one({"id": data.brand_id})
    if not brand:
        raise HTTPException(status_code=400, detail="Brand not found")
    
    # Validate main domain exists and belongs to the same brand
    main_domain = await db.asset_domains.find_one({"id": data.main_node.asset_domain_id})
    if not main_domain:
        raise HTTPException(status_code=400, detail="Main domain not found")
    
    if main_domain.get("brand_id") != data.brand_id:
        raise HTTPException(
            status_code=400, 
            detail="Main domain must belong to the same brand as the network"
        )
    
    now = datetime.now(timezone.utc).isoformat()
    network_id = str(uuid.uuid4())
    
    # Create network (exclude main_node from storage)
    network_data = data.model_dump(exclude={"main_node"})
    network = {
        "id": network_id,
        "legacy_id": None,
        **network_data,
        "created_at": now,
        "updated_at": now
    }
    
    # Convert enums
    if network.get("status") and hasattr(network["status"], "value"):
        network["status"] = network["status"].value
    
    await db.seo_networks.insert_one(network)
    
    # Create the main node (seo_structure_entry)
    main_path = data.main_node.optimized_path or "/"
    main_entry = {
        "id": str(uuid.uuid4()),
        "asset_domain_id": data.main_node.asset_domain_id,
        "network_id": network_id,
        "optimized_path": main_path if main_path != "/" else None,
        "domain_role": DomainRole.MAIN.value,
        "domain_status": SeoStatus.CANONICAL.value,
        "index_status": IndexStatus.INDEX.value,
        "target_entry_id": None,  # Main node has no target
        "created_at": now,
        "updated_at": now
    }
    
    await db.seo_structure_entries.insert_one(main_entry)
    
    # Log activity for network creation
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.CREATE,
            entity_type=EntityType.SEO_NETWORK,
            entity_id=network_id,
            after_value={**network, "main_node_id": main_entry["id"]}
        )
        
        # Log activity for main node creation
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.CREATE,
            entity_type=EntityType.SEO_STRUCTURE_ENTRY,
            entity_id=main_entry["id"],
            after_value=main_entry,
            metadata={"node_type": "main", "domain": main_domain["domain_name"]}
        )
    
    # Build response
    network["domain_count"] = 1
    network["brand_name"] = brand["name"]
    network["main_node_id"] = main_entry["id"]
    network["main_domain_name"] = main_domain["domain_name"]
    
    return SeoNetworkResponse(**network)


@router.put("/networks/{network_id}", response_model=SeoNetworkResponse)
async def update_network(
    network_id: str,
    data: SeoNetworkUpdate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Update an SEO network"""
    existing = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Network not found")
    
    update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
    
    # Convert enums
    if update_dict.get("status") and hasattr(update_dict["status"], "value"):
        update_dict["status"] = update_dict["status"].value
    
    update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.seo_networks.update_one({"id": network_id}, {"$set": update_dict})
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.SEO_NETWORK,
            entity_id=network_id,
            before_value=existing,
            after_value={**existing, **update_dict}
        )
    
    updated = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    updated["domain_count"] = await db.seo_structure_entries.count_documents({"network_id": network_id})
    
    if updated.get("brand_id"):
        brand = await db.brands.find_one({"id": updated["brand_id"]}, {"_id": 0, "name": 1})
        updated["brand_name"] = brand["name"] if brand else None
    else:
        updated["brand_name"] = None
    
    return SeoNetworkResponse(**updated)


@router.delete("/networks/{network_id}")
async def delete_network(
    network_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Delete an SEO network"""
    existing = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Network not found")
    
    # Delete associated structure entries
    deleted = await db.seo_structure_entries.delete_many({"network_id": network_id})
    
    await db.seo_networks.delete_one({"id": network_id})
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.DELETE,
            entity_type=EntityType.SEO_NETWORK,
            entity_id=network_id,
            before_value=existing,
            metadata={"deleted_entries": deleted.deleted_count}
        )
    
    return {"message": f"Network deleted with {deleted.deleted_count} structure entries"}


# ==================== SEO STRUCTURE ENDPOINTS ====================

@router.get("/structure", response_model=List[SeoStructureEntryResponse])
async def get_structure_entries(
    network_id: Optional[str] = None,
    asset_domain_id: Optional[str] = None,
    domain_role: Optional[DomainRole] = None,
    index_status: Optional[IndexStatus] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get SEO structure entries with calculated tiers"""
    query = {}
    
    if network_id:
        query["network_id"] = network_id
    if asset_domain_id:
        query["asset_domain_id"] = asset_domain_id
    if domain_role:
        query["domain_role"] = domain_role.value
    if index_status:
        query["index_status"] = index_status.value
    
    entries = await db.seo_structure_entries.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    
    # Calculate tiers by network for efficiency
    network_tier_cache = {}
    
    enriched = []
    for entry in entries:
        nid = entry.get("network_id")
        if nid and nid not in network_tier_cache and tier_service:
            network_tier_cache[nid] = await tier_service.calculate_network_tiers(nid)
        
        entry = await enrich_structure_entry(entry, network_tier_cache.get(nid, {}))
        enriched.append(SeoStructureEntryResponse(**entry))
    
    return enriched


@router.get("/structure/{entry_id}", response_model=SeoStructureEntryResponse)
async def get_structure_entry(
    entry_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get a single structure entry with calculated tier"""
    entry = await db.seo_structure_entries.find_one({"id": entry_id}, {"_id": 0})
    if not entry:
        raise HTTPException(status_code=404, detail="Structure entry not found")
    
    entry = await enrich_structure_entry(entry)
    return SeoStructureEntryResponse(**entry)


@router.post("/structure", response_model=SeoStructureEntryResponse)
async def create_structure_entry(
    data: SeoStructureEntryCreate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Create a new SEO structure entry (node-based)"""
    # Validate asset domain exists
    asset = await db.asset_domains.find_one({"id": data.asset_domain_id})
    if not asset:
        raise HTTPException(status_code=400, detail="Asset domain not found")
    
    # Validate network exists
    network = await db.seo_networks.find_one({"id": data.network_id})
    if not network:
        raise HTTPException(status_code=400, detail="Network not found")
    
    # BRAND SCOPING: Validate domain belongs to the same brand as the network
    if asset.get("brand_id") != network.get("brand_id"):
        raise HTTPException(
            status_code=400, 
            detail="Domain must belong to the same brand as the SEO Network"
        )
    
    # Validate target_entry_id if provided (new node-to-node relationship)
    if data.target_entry_id:
        target_entry = await db.seo_structure_entries.find_one({"id": data.target_entry_id})
        if not target_entry:
            raise HTTPException(status_code=400, detail="Target entry not found")
        # Ensure target entry is in the same network
        if target_entry.get("network_id") != data.network_id:
            raise HTTPException(status_code=400, detail="Target entry must be in the same network")
    
    # Validate target domain if provided (legacy support)
    if data.target_asset_domain_id:
        target = await db.asset_domains.find_one({"id": data.target_asset_domain_id})
        if not target:
            raise HTTPException(status_code=400, detail="Target asset domain not found")
    
    # Normalize the optimized_path
    normalized_path = normalize_path(data.optimized_path)
    
    # Check for duplicate node (same domain + path in same network)
    # A node is unique by: network_id + asset_domain_id + optimized_path
    existing_query = {
        "asset_domain_id": data.asset_domain_id,
        "network_id": data.network_id
    }
    if normalized_path:
        existing_query["optimized_path"] = normalized_path
    else:
        existing_query["$or"] = [
            {"optimized_path": None},
            {"optimized_path": ""},
            {"optimized_path": {"$exists": False}}
        ]
    
    existing = await db.seo_structure_entries.find_one(existing_query)
    if existing:
        path_info = f" with path '{normalized_path}'" if normalized_path else ""
        raise HTTPException(status_code=400, detail=f"Node{path_info} already exists in this network")
    
    now = datetime.now(timezone.utc).isoformat()
    entry_data = data.model_dump()
    entry_data["optimized_path"] = normalized_path  # Use normalized path
    
    entry = {
        "id": str(uuid.uuid4()),
        "legacy_domain_id": None,
        **entry_data,
        "created_at": now,
        "updated_at": now
    }
    
    # Convert enums
    for field in ["domain_role", "domain_status", "index_status"]:
        if entry.get(field) and hasattr(entry[field], "value"):
            entry[field] = entry[field].value
    
    await db.seo_structure_entries.insert_one(entry)
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.CREATE,
            entity_type=EntityType.SEO_STRUCTURE_ENTRY,
            entity_id=entry["id"],
            after_value=entry
        )
    
    entry = await enrich_structure_entry(entry)
    return SeoStructureEntryResponse(**entry)


@router.put("/structure/{entry_id}", response_model=SeoStructureEntryResponse)
async def update_structure_entry(
    entry_id: str,
    data: SeoStructureEntryUpdate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Update an SEO structure entry (node-based)"""
    existing = await db.seo_structure_entries.find_one({"id": entry_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Structure entry not found")
    
    update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
    
    # Normalize optimized_path if provided
    if "optimized_path" in update_dict:
        update_dict["optimized_path"] = normalize_path(update_dict["optimized_path"])
    
    # Validate target_entry_id if changing (node-to-node relationship)
    if "target_entry_id" in update_dict and update_dict["target_entry_id"]:
        target_entry = await db.seo_structure_entries.find_one({"id": update_dict["target_entry_id"]})
        if not target_entry:
            raise HTTPException(status_code=400, detail="Target entry not found")
        # Prevent self-reference
        if update_dict["target_entry_id"] == entry_id:
            raise HTTPException(status_code=400, detail="Entry cannot target itself")
        # Ensure same network
        if target_entry.get("network_id") != existing.get("network_id"):
            raise HTTPException(status_code=400, detail="Target entry must be in the same network")
    
    # Validate target domain if changing (legacy support)
    if "target_asset_domain_id" in update_dict and update_dict["target_asset_domain_id"]:
        target = await db.asset_domains.find_one({"id": update_dict["target_asset_domain_id"]})
        if not target:
            raise HTTPException(status_code=400, detail="Target asset domain not found")
    
    # Convert enums
    for field in ["domain_role", "domain_status", "index_status"]:
        if field in update_dict and hasattr(update_dict[field], "value"):
            update_dict[field] = update_dict[field].value
    
    update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.seo_structure_entries.update_one({"id": entry_id}, {"$set": update_dict})
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.SEO_STRUCTURE_ENTRY,
            entity_id=entry_id,
            before_value=existing,
            after_value={**existing, **update_dict}
        )
    
    updated = await db.seo_structure_entries.find_one({"id": entry_id}, {"_id": 0})
    updated = await enrich_structure_entry(updated)
    return SeoStructureEntryResponse(**updated)


@router.delete("/structure/{entry_id}")
async def delete_structure_entry(
    entry_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Delete an SEO structure entry (node).
    
    If other entries target this node, they become orphans.
    A warning is included in the response but deletion proceeds.
    """
    existing = await db.seo_structure_entries.find_one({"id": entry_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Structure entry not found")
    
    # Check if this is the main node
    if existing.get("domain_role") == DomainRole.MAIN.value:
        # Count other entries in network
        other_entries = await db.seo_structure_entries.count_documents({
            "network_id": existing["network_id"],
            "id": {"$ne": entry_id}
        })
        if other_entries > 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete main node while other nodes exist. Delete supporting nodes first or reassign main role."
            )
    
    # Check how many entries point to this one (they will become orphans)
    orphan_count = await db.seo_structure_entries.count_documents({
        "target_entry_id": entry_id,
        "id": {"$ne": entry_id}
    })
    
    # Clear target_entry_id on orphaned entries
    if orphan_count > 0:
        await db.seo_structure_entries.update_many(
            {"target_entry_id": entry_id},
            {"$set": {"target_entry_id": None, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    
    # Get domain name for logging
    domain = await db.asset_domains.find_one({"id": existing["asset_domain_id"]}, {"_id": 0, "domain_name": 1})
    domain_name = domain["domain_name"] if domain else "unknown"
    node_label = f"{domain_name}{existing.get('optimized_path', '') or ''}"
    
    await db.seo_structure_entries.delete_one({"id": entry_id})
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.DELETE,
            entity_type=EntityType.SEO_STRUCTURE_ENTRY,
            entity_id=entry_id,
            before_value=existing,
            metadata={"node_label": node_label, "orphaned_entries": orphan_count}
        )
    
    return {
        "message": "Structure entry deleted",
        "orphaned_entries": orphan_count,
        "warning": f"{orphan_count} entries now have no target (orphaned)" if orphan_count > 0 else None
    }


# ==================== BRAND-SCOPED DOMAIN SELECTION ====================

@router.get("/networks/{network_id}/available-domains")
async def get_available_domains_for_network(
    network_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Get domains available for adding to a network.
    
    Returns only domains that:
    1. Belong to the same brand as the network
    2. Are not already used in the network (or show which paths are available)
    """
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    brand_id = network.get("brand_id")
    if not brand_id:
        raise HTTPException(status_code=400, detail="Network has no brand")
    
    # Get all domains for this brand
    domains = await db.asset_domains.find(
        {"brand_id": brand_id, "status": "active"},
        {"_id": 0, "id": 1, "domain_name": 1}
    ).to_list(10000)
    
    # Get existing entries in this network
    existing_entries = await db.seo_structure_entries.find(
        {"network_id": network_id},
        {"_id": 0, "asset_domain_id": 1, "optimized_path": 1}
    ).to_list(10000)
    
    # Build set of used (domain_id, path) combinations
    used_nodes = set()
    for e in existing_entries:
        path = e.get("optimized_path") or ""
        used_nodes.add((e["asset_domain_id"], path))
    
    # Annotate domains with usage info
    result = []
    for d in domains:
        # Check if root path is used
        root_used = (d["id"], "") in used_nodes or (d["id"], "/") in used_nodes
        
        # Count how many paths are used for this domain
        used_paths = [node[1] for node in used_nodes if node[0] == d["id"]]
        
        result.append({
            "id": d["id"],
            "domain_name": d["domain_name"],
            "root_available": not root_used,
            "used_paths": used_paths
        })
    
    return result


@router.get("/networks/{network_id}/available-targets")
async def get_available_target_nodes(
    network_id: str,
    exclude_entry_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Get available target nodes for a network.
    
    Returns all entries in the network except the one being edited.
    Used for the Target Node dropdown.
    """
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    query = {"network_id": network_id}
    if exclude_entry_id:
        query["id"] = {"$ne": exclude_entry_id}
    
    entries = await db.seo_structure_entries.find(query, {"_id": 0}).to_list(10000)
    
    # Enrich with domain names
    domain_ids = list(set([e["asset_domain_id"] for e in entries]))
    domains = await db.asset_domains.find(
        {"id": {"$in": domain_ids}},
        {"_id": 0, "id": 1, "domain_name": 1}
    ).to_list(10000)
    domain_lookup = {d["id"]: d["domain_name"] for d in domains}
    
    result = []
    for e in entries:
        domain_name = domain_lookup.get(e["asset_domain_id"], "")
        path = e.get("optimized_path") or ""
        node_label = f"{domain_name}{path}" if path else domain_name
        
        result.append({
            "id": e["id"],
            "domain_name": domain_name,
            "optimized_path": path,
            "node_label": node_label,
            "domain_role": e.get("domain_role", "supporting")
        })
    
    return result


# ==================== TIER CALCULATION ENDPOINTS ====================

@router.get("/networks/{network_id}/tiers")
async def get_network_tiers(
    network_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get tier distribution for a network"""
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    if not tier_service:
        raise HTTPException(status_code=500, detail="Tier service not initialized")
    
    # Calculate tiers
    tiers = await tier_service.calculate_network_tiers(network_id)
    distribution = await tier_service.get_tier_distribution(network_id)
    issues = await tier_service.validate_hierarchy(network_id)
    
    # Get domain names for tier mapping
    tier_details = []
    for asset_id, tier in tiers.items():
        asset = await db.asset_domains.find_one({"id": asset_id}, {"_id": 0, "domain_name": 1})
        tier_details.append({
            "asset_domain_id": asset_id,
            "domain_name": asset["domain_name"] if asset else None,
            "tier": tier,
            "tier_label": get_tier_label(tier)
        })
    
    # Sort by tier
    tier_details.sort(key=lambda x: x["tier"])
    
    return {
        "network_id": network_id,
        "network_name": network["name"],
        "distribution": distribution,
        "domains": tier_details,
        "issues": issues
    }


# ==================== ACTIVITY LOGS ENDPOINTS ====================

@router.get("/activity-logs", response_model=List[ActivityLogResponse])
async def get_activity_logs(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    actor: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get activity logs"""
    if not activity_log_service:
        raise HTTPException(status_code=500, detail="Activity log service not initialized")
    
    return await activity_log_service.get_logs(
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        limit=limit,
        skip=skip
    )


@router.get("/activity-logs/stats")
async def get_activity_stats(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get activity log statistics"""
    if not activity_log_service:
        raise HTTPException(status_code=500, detail="Activity log service not initialized")
    
    return await activity_log_service.get_stats()


# ==================== REPORTS & ANALYTICS ====================

@router.get("/reports/dashboard")
async def get_v3_dashboard(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get V3 dashboard statistics"""
    asset_count = await db.asset_domains.count_documents({})
    network_count = await db.seo_networks.count_documents({})
    structure_count = await db.seo_structure_entries.count_documents({})
    
    # Status distributions
    asset_active = await db.asset_domains.count_documents({"status": "active"})
    asset_inactive = await db.asset_domains.count_documents({"status": "inactive"})
    asset_expired = await db.asset_domains.count_documents({"status": "expired"})
    
    main_domains = await db.seo_structure_entries.count_documents({"domain_role": "main"})
    supporting_domains = await db.seo_structure_entries.count_documents({"domain_role": "supporting"})
    
    indexed = await db.seo_structure_entries.count_documents({"index_status": "index"})
    noindexed = await db.seo_structure_entries.count_documents({"index_status": "noindex"})
    
    # Monitoring stats
    monitored = await db.asset_domains.count_documents({"monitoring_enabled": True})
    up = await db.asset_domains.count_documents({"monitoring_enabled": True, "ping_status": "up"})
    down = await db.asset_domains.count_documents({"monitoring_enabled": True, "ping_status": "down"})
    
    return {
        "collections": {
            "asset_domains": asset_count,
            "seo_networks": network_count,
            "seo_structure_entries": structure_count
        },
        "asset_status": {
            "active": asset_active,
            "inactive": asset_inactive,
            "expired": asset_expired
        },
        "domain_roles": {
            "main": main_domains,
            "supporting": supporting_domains
        },
        "index_status": {
            "indexed": indexed,
            "noindexed": noindexed,
            "index_rate": round(indexed / structure_count * 100, 1) if structure_count > 0 else 0
        },
        "monitoring": {
            "total_monitored": monitored,
            "up": up,
            "down": down,
            "unknown": monitored - up - down
        }
    }


@router.get("/reports/conflicts", response_model=None)
async def get_v3_conflicts(
    network_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Detect SEO conflicts including cross-path conflicts within the same domain.
    
    Conflict Types:
    - Type A: Keyword Cannibalization (same keyword, different paths)
    - Type B: Competing Targets (different paths targeting different nodes)
    - Type C: Canonical Mismatch (path A canonical to B, B still indexed)
    - Type D: Tier Inversion (higher tier supports lower tier)
    - Legacy: NOINDEX in high tier, Orphan nodes
    """
    conflicts = []
    now = datetime.now(timezone.utc).isoformat()
    
    # Filter by network if provided
    query = {"id": network_id} if network_id else {}
    networks = await db.seo_networks.find(query, {"_id": 0}).to_list(1000)
    
    for network in networks:
        if not tier_service:
            continue
        
        # Get tiers for network
        tiers = await tier_service.calculate_network_tiers(network["id"])
        
        # Get entries
        entries = await db.seo_structure_entries.find(
            {"network_id": network["id"]},
            {"_id": 0}
        ).to_list(10000)
        
        # Build lookup structures
        domain_entries = {}  # asset_domain_id -> [entries]
        entry_lookup = {e["id"]: e for e in entries}
        
        for entry in entries:
            did = entry["asset_domain_id"]
            if did not in domain_entries:
                domain_entries[did] = []
            domain_entries[did].append(entry)
        
        # Get all domain names
        domain_ids = list(domain_entries.keys())
        domains = await db.asset_domains.find(
            {"id": {"$in": domain_ids}},
            {"_id": 0, "id": 1, "domain_name": 1}
        ).to_list(10000)
        domain_name_lookup = {d["id"]: d["domain_name"] for d in domains}
        
        # Helper to build node label
        def node_label(entry):
            dname = domain_name_lookup.get(entry["asset_domain_id"], "")
            path = entry.get("optimized_path") or ""
            return f"{dname}{path}" if path else dname
        
        # ============ CROSS-PATH CONFLICT DETECTION ============
        
        for domain_id, domain_entry_list in domain_entries.items():
            domain_name = domain_name_lookup.get(domain_id, domain_id)
            
            if len(domain_entry_list) < 2:
                continue  # Need at least 2 paths to have cross-path conflicts
            
            # TYPE A: Keyword Cannibalization
            # Same domain, different paths, same or similar primary_keyword
            keywords = {}
            for e in domain_entry_list:
                kw = (e.get("primary_keyword") or "").lower().strip()
                if kw:
                    if kw not in keywords:
                        keywords[kw] = []
                    keywords[kw].append(e)
            
            for kw, kw_entries in keywords.items():
                if len(kw_entries) > 1:
                    # Multiple paths targeting same keyword
                    for i, e1 in enumerate(kw_entries):
                        for e2 in kw_entries[i+1:]:
                            conflicts.append({
                                "conflict_type": ConflictType.KEYWORD_CANNIBALIZATION.value,
                                "severity": ConflictSeverity.HIGH.value,
                                "network_id": network["id"],
                                "network_name": network["name"],
                                "domain_name": domain_name,
                                "node_a_id": e1["id"],
                                "node_a_path": e1.get("optimized_path"),
                                "node_a_label": node_label(e1),
                                "node_b_id": e2["id"],
                                "node_b_path": e2.get("optimized_path"),
                                "node_b_label": node_label(e2),
                                "description": f"Both paths target keyword '{kw}'",
                                "suggestion": "Consolidate content or differentiate keywords",
                                "detected_at": now
                            })
            
            # TYPE B: Competing Targets
            # Different paths of same domain targeting different nodes
            targets = {}
            for e in domain_entry_list:
                target_id = e.get("target_entry_id")
                if target_id:
                    if target_id not in targets:
                        targets[target_id] = []
                    targets[target_id].append(e)
            
            if len(targets) > 1:
                # Multiple different targets from same domain
                target_entries = list(targets.values())
                for i, group1 in enumerate(target_entries):
                    for group2 in target_entries[i+1:]:
                        e1 = group1[0]
                        e2 = group2[0]
                        t1 = entry_lookup.get(e1.get("target_entry_id"))
                        t2 = entry_lookup.get(e2.get("target_entry_id"))
                        
                        conflicts.append({
                            "conflict_type": ConflictType.COMPETING_TARGETS.value,
                            "severity": ConflictSeverity.MEDIUM.value,
                            "network_id": network["id"],
                            "network_name": network["name"],
                            "domain_name": domain_name,
                            "node_a_id": e1["id"],
                            "node_a_path": e1.get("optimized_path"),
                            "node_a_label": node_label(e1),
                            "node_b_id": e2["id"],
                            "node_b_path": e2.get("optimized_path"),
                            "node_b_label": node_label(e2),
                            "description": f"Paths target different nodes: {node_label(t1) if t1 else 'unknown'} vs {node_label(t2) if t2 else 'unknown'}",
                            "suggestion": "Consolidate link strategy for this domain",
                            "detected_at": now
                        })
            
            # TYPE C: Canonical Mismatch
            # Path A has canonical pointing to Path B, but B is still indexed
            for e in domain_entry_list:
                if e.get("domain_status") == "redirect_301" or e.get("domain_status") == "redirect_302":
                    target_id = e.get("target_entry_id")
                    if target_id:
                        target = entry_lookup.get(target_id)
                        if target and target.get("index_status") == "index":
                            conflicts.append({
                                "conflict_type": ConflictType.CANONICAL_MISMATCH.value,
                                "severity": ConflictSeverity.HIGH.value,
                                "network_id": network["id"],
                                "network_name": network["name"],
                                "domain_name": domain_name,
                                "node_a_id": e["id"],
                                "node_a_path": e.get("optimized_path"),
                                "node_a_label": node_label(e),
                                "node_b_id": target["id"],
                                "node_b_path": target.get("optimized_path"),
                                "node_b_label": node_label(target),
                                "description": "Redirects to indexed path",
                                "suggestion": "Review canonical chain or noindex the target",
                                "detected_at": now
                            })
            
            # TYPE D: Tier Inversion (within same domain)
            # Higher-tier path supports lower-tier path
            for e in domain_entry_list:
                if e.get("domain_role") == "supporting":
                    target_id = e.get("target_entry_id")
                    if target_id:
                        target = entry_lookup.get(target_id)
                        if target:
                            e_tier = tiers.get(e["id"], 5)
                            t_tier = tiers.get(target_id, 5)
                            
                            if e_tier < t_tier:
                                conflicts.append({
                                    "conflict_type": ConflictType.TIER_INVERSION.value,
                                    "severity": ConflictSeverity.CRITICAL.value,
                                    "network_id": network["id"],
                                    "network_name": network["name"],
                                    "domain_name": domain_name,
                                    "node_a_id": e["id"],
                                    "node_a_path": e.get("optimized_path"),
                                    "node_a_label": node_label(e),
                                    "node_b_id": target["id"],
                                    "node_b_path": target.get("optimized_path"),
                                    "node_b_label": node_label(target),
                                    "description": f"Tier {e_tier} ({get_tier_label(e_tier)}) supports Tier {t_tier} ({get_tier_label(t_tier)})",
                                    "suggestion": "Reverse the relationship or restructure hierarchy",
                                    "detected_at": now
                                })
        
        # ============ LEGACY CONFLICT DETECTION ============
        
        for entry in entries:
            entry_id = entry["id"]
            asset_id = entry["asset_domain_id"]
            tier = tiers.get(entry_id, 5)
            domain_name = domain_name_lookup.get(asset_id, asset_id)
            
            # NOINDEX in high tier (0-2)
            if entry.get("index_status") == "noindex" and tier <= 2:
                conflicts.append({
                    "conflict_type": "noindex_high_tier",
                    "severity": ConflictSeverity.HIGH.value,
                    "network_id": network["id"],
                    "network_name": network["name"],
                    "domain_name": domain_name,
                    "node_a_id": entry_id,
                    "node_a_path": entry.get("optimized_path"),
                    "node_a_label": node_label(entry),
                    "node_b_id": None,
                    "node_b_path": None,
                    "node_b_label": None,
                    "description": f"NOINDEX node in {get_tier_label(tier)}",
                    "suggestion": "Change to INDEX or move to lower tier",
                    "detected_at": now
                })
            
            # Orphan (no target and not main)
            if entry.get("domain_role") != "main" and not entry.get("target_entry_id") and not entry.get("target_asset_domain_id"):
                if tier >= 5:
                    conflicts.append({
                        "conflict_type": "orphan",
                        "severity": ConflictSeverity.MEDIUM.value,
                        "network_id": network["id"],
                        "network_name": network["name"],
                        "domain_name": domain_name,
                        "node_a_id": entry_id,
                        "node_a_path": entry.get("optimized_path"),
                        "node_a_label": node_label(entry),
                        "node_b_id": None,
                        "node_b_path": None,
                        "node_b_label": None,
                        "description": "Node not connected to main hierarchy",
                        "suggestion": "Assign a target node or remove from network",
                        "detected_at": now
                    })
    
    # Sort by severity
    severity_order = {
        ConflictSeverity.CRITICAL.value: 0,
        ConflictSeverity.HIGH.value: 1,
        ConflictSeverity.MEDIUM.value: 2,
        ConflictSeverity.LOW.value: 3
    }
    conflicts.sort(key=lambda c: severity_order.get(c.get("severity"), 4))
    
    # Count by type
    by_type = {}
    for c in conflicts:
        ct = c.get("conflict_type")
        by_type[ct] = by_type.get(ct, 0) + 1
    
    return {
        "conflicts": conflicts,
        "total": len(conflicts),
        "by_type": by_type,
        "by_severity": {
            "critical": len([c for c in conflicts if c.get("severity") == ConflictSeverity.CRITICAL.value]),
            "high": len([c for c in conflicts if c.get("severity") == ConflictSeverity.HIGH.value]),
            "medium": len([c for c in conflicts if c.get("severity") == ConflictSeverity.MEDIUM.value]),
            "low": len([c for c in conflicts if c.get("severity") == ConflictSeverity.LOW.value])
        }
    }


# ==================== TELEGRAM ALERT ENDPOINTS ====================

@router.post("/alerts/send-conflicts")
async def send_conflict_alerts(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Send all V3 conflicts as Telegram alerts"""
    # Get conflicts
    conflicts = []
    
    networks = await db.seo_networks.find({}, {"_id": 0}).to_list(1000)
    
    for network in networks:
        if not tier_service:
            continue
        
        tiers = await tier_service.calculate_network_tiers(network["id"])
        entries = await db.seo_structure_entries.find(
            {"network_id": network["id"]},
            {"_id": 0}
        ).to_list(10000)
        
        for entry in entries:
            asset_id = entry["asset_domain_id"]
            tier = tiers.get(asset_id, 5)
            
            asset = await db.asset_domains.find_one({"id": asset_id}, {"_id": 0, "domain_name": 1})
            domain_name = asset["domain_name"] if asset else asset_id
            
            if entry.get("index_status") == "noindex" and tier <= 2:
                conflicts.append({
                    "type": "NOINDEX in high tier",
                    "severity": "🔴 HIGH",
                    "network": network["name"],
                    "domain": domain_name,
                    "tier": get_tier_label(tier)
                })
            
            if entry.get("domain_role") != "main" and not entry.get("target_asset_domain_id") and tier >= 5:
                conflicts.append({
                    "type": "Orphan domain",
                    "severity": "🟡 MEDIUM",
                    "network": network["name"],
                    "domain": domain_name,
                    "tier": get_tier_label(tier)
                })
    
    if not conflicts:
        return {"message": "No conflicts found", "sent": 0}
    
    # Build message
    message = "<b>🚨 SEO-NOC V3 Conflict Report</b>\n\n"
    message += f"<b>Total conflicts:</b> {len(conflicts)}\n\n"
    
    for i, c in enumerate(conflicts[:10], 1):  # Limit to 10
        message += f"<b>{i}. {c['severity']} - {c['type']}</b>\n"
        message += f"   📁 Network: {c['network']}\n"
        message += f"   🌐 Domain: <code>{c['domain']}</code>\n"
        message += f"   📊 Tier: {c['tier']}\n\n"
    
    if len(conflicts) > 10:
        message += f"<i>...and {len(conflicts) - 10} more conflicts</i>\n"
    
    message += f"\n<i>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>"
    
    success = await send_v3_telegram_alert(message)
    
    return {
        "message": "Conflict alerts sent" if success else "Failed to send alerts",
        "sent": len(conflicts) if success else 0,
        "conflicts": len(conflicts)
    }


@router.post("/alerts/test")
async def send_v3_test_alert(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Send a test alert from V3 system"""
    message = f"""<b>🧪 SEO-NOC V3 Test Alert</b>

This is a test message from the V3 API.

<b>System Status:</b>
✅ V3 API: Online
✅ Tier Calculation: Active
✅ Activity Logging: Enabled

<i>Sent by: {current_user['email']}</i>
<i>Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>"""
    
    success = await send_v3_telegram_alert(message)
    
    if success:
        return {"message": "V3 test alert sent successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send V3 test alert. Check Telegram configuration.")


@router.post("/alerts/domain-change")
async def send_domain_change_alert(
    asset_domain_id: str,
    action: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Send alert when a domain is changed"""
    asset = await db.asset_domains.find_one({"id": asset_domain_id}, {"_id": 0})
    
    if not asset:
        raise HTTPException(status_code=404, detail="Asset domain not found")
    
    action_emoji = {
        "create": "➕",
        "update": "✏️",
        "delete": "🗑️"
    }.get(action.lower(), "📝")
    
    message = f"""<b>{action_emoji} Domain {action.capitalize()}</b>

<b>Domain:</b> <code>{asset['domain_name']}</code>
<b>Status:</b> {asset.get('status', 'N/A')}
<b>Monitoring:</b> {'✅ Enabled' if asset.get('monitoring_enabled') else '❌ Disabled'}

<i>By: {current_user['email']}</i>
<i>Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>"""
    
    success = await send_v3_telegram_alert(message)
    
    return {"message": "Alert sent" if success else "Failed to send alert", "success": success}


# ==================== BULK IMPORT ENDPOINTS ====================

from pydantic import BaseModel as PydanticBaseModel

class BulkImportItem(PydanticBaseModel):
    domain_name: str
    brand_name: Optional[str] = None
    registrar: Optional[str] = None
    expiration_date: Optional[str] = None
    status: Optional[str] = "active"
    notes: Optional[str] = None

class BulkImportRequest(PydanticBaseModel):
    domains: List[BulkImportItem]
    skip_duplicates: bool = True

@router.post("/import/domains")
async def bulk_import_domains(
    request: BulkImportRequest,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Bulk import asset domains from CSV data.
    
    Expected fields: domain_name, brand_name (optional), registrar (optional), 
    expiration_date (optional), status (optional), notes (optional)
    """
    results = {
        "imported": 0,
        "skipped": 0,
        "errors": [],
        "details": []
    }
    
    # Get brand mapping
    brands = await db.brands.find({}, {"_id": 0}).to_list(1000)
    brand_map = {b["name"].lower(): b["id"] for b in brands}
    
    for item in request.domains:
        try:
            # Check for duplicate
            existing = await db.asset_domains.find_one({"domain_name": item.domain_name})
            if existing:
                if request.skip_duplicates:
                    results["skipped"] += 1
                    results["details"].append({
                        "domain": item.domain_name,
                        "status": "skipped",
                        "reason": "Domain already exists"
                    })
                    continue
                else:
                    results["errors"].append({
                        "domain": item.domain_name,
                        "error": "Domain already exists"
                    })
                    continue
            
            # Find or create brand
            brand_id = None
            if item.brand_name:
                brand_id = brand_map.get(item.brand_name.lower())
                if not brand_id:
                    # Create new brand
                    new_brand = {
                        "id": str(uuid.uuid4()),
                        "name": item.brand_name,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                    await db.brands.insert_one(new_brand)
                    brand_id = new_brand["id"]
                    brand_map[item.brand_name.lower()] = brand_id
            
            # Create asset domain
            now = datetime.now(timezone.utc).isoformat()
            asset = {
                "id": str(uuid.uuid4()),
                "legacy_id": None,
                "domain_name": item.domain_name,
                "brand_id": brand_id,
                "category_id": None,
                "domain_type_id": None,
                "registrar": item.registrar,
                "buy_date": None,
                "expiration_date": item.expiration_date,
                "auto_renew": False,
                "status": item.status or "active",
                "monitoring_enabled": False,
                "monitoring_interval": "1hour",
                "last_check": None,
                "ping_status": "unknown",
                "http_status": None,
                "http_status_code": None,
                "notes": item.notes or "",
                "created_at": now,
                "updated_at": now
            }
            
            await db.asset_domains.insert_one(asset)
            
            # Log activity
            if activity_log_service:
                await activity_log_service.log(
                    actor=current_user["email"],
                    action_type=ActionType.CREATE,
                    entity_type=EntityType.ASSET_DOMAIN,
                    entity_id=asset["id"],
                    after_value=asset,
                    metadata={"source": "bulk_import"}
                )
            
            results["imported"] += 1
            results["details"].append({
                "domain": item.domain_name,
                "status": "imported",
                "id": asset["id"]
            })
            
        except Exception as e:
            results["errors"].append({
                "domain": item.domain_name,
                "error": str(e)
            })
    
    return results


@router.get("/import/template")
async def get_import_template(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get CSV template for bulk import"""
    return {
        "headers": ["domain_name", "brand_name", "registrar", "expiration_date", "status", "notes"],
        "example_row": ["example.com", "MyBrand", "GoDaddy", "2026-12-31", "active", "Main site"],
        "status_options": ["active", "inactive", "pending", "expired"],
        "notes": "domain_name is required. Other fields are optional."
    }


# ==================== EXPORT ENDPOINTS ====================

@router.get("/export/asset-domains")
async def export_asset_domains(
    format: str = Query("json", enum=["json", "csv"]),
    brand_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Export asset domains to JSON or CSV"""
    query = {}
    if brand_id:
        query["brand_id"] = brand_id
    if status:
        query["status"] = status
    
    assets = await db.asset_domains.find(query, {"_id": 0}).to_list(10000)
    
    # Enrich with names
    brands = {b["id"]: b["name"] for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    categories = {c["id"]: c["name"] for c in await db.categories.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    registrars = {r["id"]: r["name"] for r in await db.registrars.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    
    for asset in assets:
        asset["brand_name"] = brands.get(asset.get("brand_id"), "")
        asset["category_name"] = categories.get(asset.get("category_id"), "")
        asset["registrar_name"] = registrars.get(asset.get("registrar_id")) or asset.get("registrar", "")
    
    if format == "csv":
        import csv
        import io
        
        output = io.StringIO()
        fieldnames = [
            "domain_name", "brand_name", "category_name", "registrar_name",
            "status", "expiration_date", "auto_renew", "monitoring_enabled",
            "ping_status", "http_status", "notes", "created_at"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(assets)
        
        from fastapi.responses import Response
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=asset_domains_export.csv"}
        )
    
    return {
        "data": assets,
        "total": len(assets),
        "exported_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/export/networks/{network_id}")
async def export_network_structure(
    network_id: str,
    format: str = Query("json", enum=["json", "csv"]),
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Export a network with full structure (entries, relationships, tiers)"""
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    # Get brand name
    if network.get("brand_id"):
        brand = await db.brands.find_one({"id": network["brand_id"]}, {"_id": 0, "name": 1})
        network["brand_name"] = brand["name"] if brand else ""
    
    # Get all entries with tiers
    entries = await db.seo_structure_entries.find(
        {"network_id": network_id},
        {"_id": 0}
    ).to_list(10000)
    
    # Calculate tiers
    tiers = {}
    if tier_service:
        tiers = await tier_service.calculate_network_tiers(network_id)
    
    # Build entry lookup for target resolution
    entry_lookup = {e["id"]: e for e in entries}
    
    # Get all asset domains for name lookup
    domain_ids = list(set([e["asset_domain_id"] for e in entries]))
    domains = await db.asset_domains.find(
        {"id": {"$in": domain_ids}},
        {"_id": 0, "id": 1, "domain_name": 1}
    ).to_list(10000)
    domain_lookup = {d["id"]: d["domain_name"] for d in domains}
    
    # Enrich entries
    enriched_entries = []
    for entry in entries:
        entry_id = entry.get("id")
        tier = tiers.get(entry_id, 5)
        
        # Get domain name
        domain_name = domain_lookup.get(entry.get("asset_domain_id"), "")
        
        # Build node label
        node_label = domain_name
        if entry.get("optimized_path"):
            node_label = f"{domain_name}{entry['optimized_path']}"
        
        # Get target info
        target_node_label = ""
        if entry.get("target_entry_id"):
            target_entry = entry_lookup.get(entry["target_entry_id"])
            if target_entry:
                target_domain = domain_lookup.get(target_entry.get("asset_domain_id"), "")
                target_node_label = target_domain
                if target_entry.get("optimized_path"):
                    target_node_label = f"{target_domain}{target_entry['optimized_path']}"
        elif entry.get("target_asset_domain_id"):
            target_node_label = domain_lookup.get(entry["target_asset_domain_id"], "")
        
        enriched_entries.append({
            "entry_id": entry_id,
            "domain_name": domain_name,
            "optimized_path": entry.get("optimized_path", ""),
            "node_label": node_label,
            "domain_role": entry.get("domain_role", "supporting"),
            "domain_status": entry.get("domain_status", "canonical"),
            "index_status": entry.get("index_status", "index"),
            "target_node": target_node_label,
            "calculated_tier": tier,
            "tier_label": get_tier_label(tier),
            "ranking_url": entry.get("ranking_url", ""),
            "primary_keyword": entry.get("primary_keyword", ""),
            "ranking_position": entry.get("ranking_position"),
            "notes": entry.get("notes", "")
        })
    
    if format == "csv":
        import csv
        import io
        
        output = io.StringIO()
        fieldnames = [
            "domain_name", "optimized_path", "node_label", "domain_role",
            "domain_status", "index_status", "target_node", "calculated_tier",
            "tier_label", "ranking_url", "primary_keyword", "ranking_position", "notes"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(enriched_entries)
        
        from fastapi.responses import Response
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=network_{network['name']}_export.csv"}
        )
    
    return {
        "network": {
            "id": network["id"],
            "name": network["name"],
            "brand_name": network.get("brand_name", ""),
            "description": network.get("description", ""),
            "status": network.get("status", "active")
        },
        "entries": enriched_entries,
        "total_entries": len(enriched_entries),
        "tier_distribution": {
            get_tier_label(i): len([e for e in enriched_entries if e["calculated_tier"] == i])
            for i in range(6)
        },
        "exported_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/export/networks")
async def export_all_networks(
    format: str = Query("json", enum=["json", "csv"]),
    brand_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Export all networks with metadata"""
    query = {}
    if brand_id:
        query["brand_id"] = brand_id
    
    networks = await db.seo_networks.find(query, {"_id": 0}).to_list(1000)
    
    # Enrich with brand names and domain counts
    brands = {b["id"]: b["name"] for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    
    for network in networks:
        network["brand_name"] = brands.get(network.get("brand_id"), "")
        network["domain_count"] = await db.seo_structure_entries.count_documents({"network_id": network["id"]})
    
    if format == "csv":
        import csv
        import io
        
        output = io.StringIO()
        fieldnames = ["name", "brand_name", "description", "status", "domain_count", "created_at"]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(networks)
        
        from fastapi.responses import Response
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=networks_export.csv"}
        )
    
    return {
        "data": networks,
        "total": len(networks),
        "exported_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/export/activity-logs")
async def export_activity_logs(
    format: str = Query("json", enum=["json", "csv"]),
    entity_type: Optional[str] = None,
    action_type: Optional[str] = None,
    actor: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Export activity logs to JSON or CSV"""
    query = {}
    
    if entity_type:
        query["entity_type"] = entity_type
    if action_type:
        query["action_type"] = action_type
    if actor:
        query["actor"] = {"$regex": actor, "$options": "i"}
    
    # Limit by date range
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    query["timestamp"] = {"$gte": cutoff}
    
    logs = await db.activity_logs_v3.find(query, {"_id": 0}).sort("timestamp", -1).to_list(10000)
    
    if format == "csv":
        import csv
        import io
        
        # Flatten before/after for CSV
        flattened = []
        for log in logs:
            flattened.append({
                "timestamp": log.get("timestamp", ""),
                "actor": log.get("actor", ""),
                "action_type": log.get("action_type", ""),
                "entity_type": log.get("entity_type", ""),
                "entity_id": log.get("entity_id", ""),
                "summary": log.get("summary", "")
            })
        
        output = io.StringIO()
        fieldnames = ["timestamp", "actor", "action_type", "entity_type", "entity_id", "summary"]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(flattened)
        
        from fastapi.responses import Response
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=activity_logs_export.csv"}
        )
    
    return {
        "data": logs,
        "total": len(logs),
        "exported_at": datetime.now(timezone.utc).isoformat()
    }


# ==================== BULK NODE IMPORT ====================

from pydantic import BaseModel

class BulkNodeImportItem(BaseModel):
    """Single node for bulk import"""
    domain_name: str
    optimized_path: Optional[str] = None
    domain_role: Optional[str] = "supporting"
    domain_status: Optional[str] = "canonical"
    index_status: Optional[str] = "index"
    target_domain: Optional[str] = None  # Domain name of target
    target_path: Optional[str] = None     # Path of target node
    ranking_url: Optional[str] = None
    primary_keyword: Optional[str] = None
    notes: Optional[str] = None


class BulkNodeImportRequest(BaseModel):
    """Request for bulk node import"""
    network_id: str
    nodes: List[BulkNodeImportItem]
    create_missing_domains: bool = False  # If true, create domains that don't exist


@router.post("/import/nodes")
async def bulk_import_nodes(
    request: BulkNodeImportRequest,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Bulk import nodes (structure entries) with path support.
    
    CSV format: domain_name, optimized_path, domain_role, target_domain, target_path, ...
    
    Process:
    1. Validate network exists
    2. For each node, find or create the domain
    3. Create structure entry with path and relationships
    4. Resolve target_domain + target_path to target_entry_id
    """
    # Validate network
    network = await db.seo_networks.find_one({"id": request.network_id})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    results = {
        "imported": [],
        "skipped": [],
        "errors": [],
        "domains_created": []
    }
    
    # First pass: ensure all domains exist and build lookup
    domain_lookup = {}  # domain_name -> asset_domain_id
    all_domains = await db.asset_domains.find({}, {"_id": 0, "id": 1, "domain_name": 1}).to_list(10000)
    for d in all_domains:
        domain_lookup[d["domain_name"].lower()] = d["id"]
    
    # Create missing domains if requested
    if request.create_missing_domains:
        for node in request.nodes:
            domain_lower = node.domain_name.lower()
            if domain_lower not in domain_lookup:
                # Create domain with network's brand
                now = datetime.now(timezone.utc).isoformat()
                new_domain = {
                    "id": str(uuid.uuid4()),
                    "domain_name": node.domain_name,
                    "brand_id": network.get("brand_id"),
                    "status": "active",
                    "monitoring_enabled": False,
                    "auto_renew": False,
                    "created_at": now,
                    "updated_at": now
                }
                await db.asset_domains.insert_one(new_domain)
                domain_lookup[domain_lower] = new_domain["id"]
                results["domains_created"].append(node.domain_name)
    
    # Second pass: create entries and build entry lookup
    entry_lookup = {}  # (domain_name.lower, path) -> entry_id
    
    # Load existing entries for this network
    existing_entries = await db.seo_structure_entries.find(
        {"network_id": request.network_id},
        {"_id": 0}
    ).to_list(10000)
    
    for e in existing_entries:
        domain_id = e.get("asset_domain_id")
        # Find domain name
        for dname, did in domain_lookup.items():
            if did == domain_id:
                key = (dname, e.get("optimized_path") or "")
                entry_lookup[key] = e["id"]
                break
    
    # Third pass: create entries
    entries_to_create = []
    for node in request.nodes:
        try:
            domain_lower = node.domain_name.lower()
            asset_id = domain_lookup.get(domain_lower)
            
            if not asset_id:
                results["errors"].append({
                    "domain": node.domain_name,
                    "error": f"Domain not found: {node.domain_name}"
                })
                continue
            
            # Check if entry already exists
            entry_key = (domain_lower, node.optimized_path or "")
            if entry_key in entry_lookup:
                results["skipped"].append({
                    "domain": node.domain_name,
                    "path": node.optimized_path,
                    "reason": "Entry already exists"
                })
                continue
            
            # Create entry (target will be resolved later)
            now = datetime.now(timezone.utc).isoformat()
            entry = {
                "id": str(uuid.uuid4()),
                "asset_domain_id": asset_id,
                "network_id": request.network_id,
                "optimized_path": node.optimized_path,
                "domain_role": node.domain_role or "supporting",
                "domain_status": node.domain_status or "canonical",
                "index_status": node.index_status or "index",
                "target_entry_id": None,  # Will be resolved
                "target_domain": node.target_domain,  # Temp storage
                "target_path": node.target_path,      # Temp storage
                "ranking_url": node.ranking_url,
                "primary_keyword": node.primary_keyword,
                "notes": node.notes,
                "created_at": now,
                "updated_at": now
            }
            
            entries_to_create.append(entry)
            entry_lookup[entry_key] = entry["id"]
            
        except Exception as e:
            results["errors"].append({
                "domain": node.domain_name,
                "error": str(e)
            })
    
    # Fourth pass: resolve targets and insert
    for entry in entries_to_create:
        target_domain = entry.pop("target_domain", None)
        target_path = entry.pop("target_path", None)
        
        if target_domain:
            target_key = (target_domain.lower(), target_path or "")
            target_entry_id = entry_lookup.get(target_key)
            
            if target_entry_id:
                entry["target_entry_id"] = target_entry_id
            else:
                # Target not found - might be in existing entries or not created yet
                # Try to find by domain only
                for (dname, path), eid in entry_lookup.items():
                    if dname == target_domain.lower() and (not target_path or path == target_path):
                        entry["target_entry_id"] = eid
                        break
        
        await db.seo_structure_entries.insert_one(entry)
        results["imported"].append({
            "domain": entry.get("domain_name", ""),
            "path": entry.get("optimized_path", ""),
            "entry_id": entry["id"]
        })
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.CREATE,
            entity_type=EntityType.SEO_STRUCTURE_ENTRY,
            entity_id=request.network_id,
            after_value={
                "type": "bulk_node_import",
                "imported": len(results["imported"]),
                "skipped": len(results["skipped"]),
                "errors": len(results["errors"])
            }
        )
    
    return {
        "success": True,
        "summary": {
            "imported": len(results["imported"]),
            "skipped": len(results["skipped"]),
            "errors": len(results["errors"]),
            "domains_created": len(results["domains_created"])
        },
        "details": results
    }


@router.get("/import/nodes/template")
async def get_node_import_template(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get CSV template for bulk node import"""
    return {
        "headers": [
            "domain_name", "optimized_path", "domain_role", "domain_status",
            "index_status", "target_domain", "target_path", "ranking_url",
            "primary_keyword", "notes"
        ],
        "example_rows": [
            {
                "domain_name": "main-site.com",
                "optimized_path": "",
                "domain_role": "main",
                "domain_status": "canonical",
                "index_status": "index",
                "target_domain": "",
                "target_path": "",
                "ranking_url": "https://main-site.com/best-product",
                "primary_keyword": "best product 2026",
                "notes": "Money site"
            },
            {
                "domain_name": "tier1-support.com",
                "optimized_path": "/blog/review",
                "domain_role": "supporting",
                "domain_status": "canonical",
                "index_status": "index",
                "target_domain": "main-site.com",
                "target_path": "",
                "ranking_url": "",
                "primary_keyword": "",
                "notes": "Tier 1 supporting blog"
            }
        ],
        "role_options": ["main", "supporting"],
        "status_options": ["canonical", "redirect_301", "redirect_302"],
        "index_options": ["index", "noindex"],
        "notes": [
            "domain_name is required",
            "optimized_path is optional (leave empty for domain-level nodes)",
            "target_domain + target_path define the relationship to another node",
            "main role should have no target (it's the root)"
        ]
    }



# ==================== SETTINGS ENDPOINTS ====================

@router.get("/settings/dashboard-refresh")
async def get_dashboard_refresh_setting(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get dashboard refresh interval setting"""
    user_id = current_user.get("id")
    pref = await db.user_preferences.find_one({"user_id": user_id}, {"_id": 0})
    
    return {
        "refresh_interval": pref.get("dashboard_refresh_interval", 0) if pref else 0,
        "options": [
            {"value": 0, "label": "Manual only"},
            {"value": 30, "label": "30 seconds"},
            {"value": 60, "label": "1 minute"},
            {"value": 300, "label": "5 minutes"},
            {"value": 900, "label": "15 minutes"}
        ]
    }


@router.put("/settings/dashboard-refresh")
async def update_dashboard_refresh_setting(
    interval: int = Query(..., ge=0, le=900),
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Update dashboard refresh interval setting"""
    user_id = current_user.get("id")
    
    valid_intervals = [0, 30, 60, 300, 900]
    if interval not in valid_intervals:
        raise HTTPException(status_code=400, detail=f"Invalid interval. Must be one of: {valid_intervals}")
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.user_preferences.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "dashboard_refresh_interval": interval,
                "updated_at": now
            },
            "$setOnInsert": {
                "user_id": user_id,
                "created_at": now
            }
        },
        upsert=True
    )
    
    return {
        "success": True,
        "refresh_interval": interval
    }


@router.get("/dashboard/stats")
async def get_dashboard_stats_only(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get lightweight dashboard stats for auto-refresh (no heavy computations)"""
    stats = {
        "total_domains": await db.asset_domains.count_documents({}),
        "total_networks": await db.seo_networks.count_documents({}),
        "active_domains": await db.asset_domains.count_documents({"status": "active"}),
        "monitored_count": await db.asset_domains.count_documents({"monitoring_enabled": True}),
        "indexed_count": await db.seo_structure_entries.count_documents({"index_status": "index"}),
        "noindex_count": await db.seo_structure_entries.count_documents({"index_status": "noindex"}),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    stats["ping_up"] = await db.asset_domains.count_documents({"ping_status": "up"})
    stats["ping_down"] = await db.asset_domains.count_documents({"ping_status": "down"})
    stats["active_alerts"] = await db.alerts.count_documents({"acknowledged": False})
    
    return stats


# ==================== MONITORING ENDPOINTS ====================

@router.get("/monitoring/settings")
async def get_monitoring_settings(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get monitoring configuration settings"""
    from services.monitoring_service import MonitoringSettingsService
    settings_service = MonitoringSettingsService(db)
    settings = await settings_service.get_settings()
    return settings


@router.put("/monitoring/settings")
async def update_monitoring_settings(
    updates: MonitoringSettingsUpdate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Update monitoring configuration settings (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admins can update monitoring settings")
    
    from services.monitoring_service import MonitoringSettingsService
    settings_service = MonitoringSettingsService(db)
    
    # Convert Pydantic model to dict
    update_dict = {}
    if updates.expiration:
        update_dict["expiration"] = updates.expiration
    if updates.availability:
        update_dict["availability"] = updates.availability
    if updates.telegram:
        update_dict["telegram"] = updates.telegram
    
    settings = await settings_service.update_settings(update_dict)
    return {"success": True, "settings": settings}


@router.get("/monitoring/stats")
async def get_monitoring_stats(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get current monitoring statistics"""
    now = datetime.now(timezone.utc)
    
    # Availability stats
    total_monitored = await db.asset_domains.count_documents({"monitoring_enabled": True})
    up_count = await db.asset_domains.count_documents({"monitoring_enabled": True, "ping_status": "up"})
    down_count = await db.asset_domains.count_documents({"monitoring_enabled": True, "ping_status": "down"})
    unknown_count = await db.asset_domains.count_documents({"monitoring_enabled": True, "ping_status": "unknown"})
    
    # Expiration stats
    from datetime import timedelta
    week_later = (now + timedelta(days=7)).isoformat()
    month_later = (now + timedelta(days=30)).isoformat()
    
    expiring_7_days = await db.asset_domains.count_documents({
        "expiration_date": {"$ne": None, "$lte": week_later, "$gt": now.isoformat()}
    })
    
    expiring_30_days = await db.asset_domains.count_documents({
        "expiration_date": {"$ne": None, "$lte": month_later, "$gt": now.isoformat()}
    })
    
    expired = await db.asset_domains.count_documents({
        "expiration_date": {"$ne": None, "$lte": now.isoformat()}
    })
    
    # Alert stats
    monitoring_alerts = await db.alerts.count_documents({"alert_type": "monitoring", "acknowledged": False})
    expiration_alerts = await db.alerts.count_documents({"alert_type": "expiration", "acknowledged": False})
    
    return {
        "availability": {
            "total_monitored": total_monitored,
            "up": up_count,
            "down": down_count,
            "unknown": unknown_count
        },
        "expiration": {
            "expiring_7_days": expiring_7_days,
            "expiring_30_days": expiring_30_days,
            "expired": expired
        },
        "alerts": {
            "monitoring_unacknowledged": monitoring_alerts,
            "expiration_unacknowledged": expiration_alerts
        },
        "updated_at": now.isoformat()
    }


@router.post("/monitoring/check-expiration")
async def trigger_expiration_check(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Manually trigger expiration check for all domains (Admin only)"""
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin role required")
    
    from services.monitoring_service import ExpirationMonitoringService
    expiration_service = ExpirationMonitoringService(db)
    
    # Run in background
    async def run_check():
        result = await expiration_service.check_all_domains()
        logger.info(f"Manual expiration check complete: {result}")
    
    background_tasks.add_task(run_check)
    
    return {"message": "Expiration check scheduled", "status": "running"}


@router.post("/monitoring/check-availability")
async def trigger_availability_check(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Manually trigger availability check for all monitored domains (Admin only)"""
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin role required")
    
    from services.monitoring_service import AvailabilityMonitoringService
    availability_service = AvailabilityMonitoringService(db)
    
    # Run in background
    async def run_check():
        result = await availability_service.check_all_domains()
        logger.info(f"Manual availability check complete: {result}")
    
    background_tasks.add_task(run_check)
    
    return {"message": "Availability check scheduled", "status": "running"}


@router.post("/monitoring/check-domain/{domain_id}")
async def check_single_domain(
    domain_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Trigger availability check for a single domain"""
    domain = await db.asset_domains.find_one({"id": domain_id}, {"_id": 0})
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    from services.monitoring_service import AvailabilityMonitoringService
    availability_service = AvailabilityMonitoringService(db)
    
    # Get settings
    from services.monitoring_service import MonitoringSettingsService
    settings_service = MonitoringSettingsService(db)
    settings = await settings_service.get_settings()
    avail_settings = settings.get("availability", {})
    
    # Run check
    result = await availability_service._check_domain_availability(domain, avail_settings)
    
    return {
        "domain_name": domain["domain_name"],
        "status": result["status"],
        "http_code": result.get("http_code"),
        "alert_sent": result.get("alert_sent", False)
    }


@router.get("/monitoring/expiring-domains")
async def get_expiring_domains(
    days: int = Query(default=30, ge=1, le=365),
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get list of domains expiring within specified days"""
    now = datetime.now(timezone.utc)
    cutoff = (now + timedelta(days=days)).isoformat()
    
    domains = await db.asset_domains.find(
        {
            "expiration_date": {"$ne": None, "$lte": cutoff}
        },
        {"_id": 0}
    ).sort("expiration_date", 1).to_list(1000)
    
    # Enrich with brand names and calculate days remaining
    result = []
    for domain in domains:
        exp_date = domain.get("expiration_date", "")
        days_remaining = None
        if exp_date:
            try:
                exp = datetime.fromisoformat(exp_date.replace("Z", "+00:00"))
                days_remaining = (exp.date() - now.date()).days
            except (ValueError, TypeError):
                pass
        
        # Get brand name
        brand_name = None
        if domain.get("brand_id"):
            brand = await db.brands.find_one({"id": domain["brand_id"]}, {"_id": 0, "name": 1})
            brand_name = brand["name"] if brand else None
        
        result.append({
            "id": domain["id"],
            "domain_name": domain["domain_name"],
            "brand_name": brand_name,
            "expiration_date": exp_date[:10] if exp_date else None,
            "days_remaining": days_remaining,
            "auto_renew": domain.get("auto_renew", False),
            "registrar": domain.get("registrar"),
            "status": "expired" if days_remaining and days_remaining < 0 else (
                "critical" if days_remaining and days_remaining <= 3 else (
                    "warning" if days_remaining and days_remaining <= 7 else "upcoming"
                )
            )
        })
    
    return {
        "domains": result,
        "total": len(result),
        "query_days": days
    }


@router.get("/monitoring/down-domains")
async def get_down_domains(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get list of domains currently down"""
    domains = await db.asset_domains.find(
        {"monitoring_enabled": True, "ping_status": "down"},
        {"_id": 0}
    ).to_list(1000)
    
    result = []
    for domain in domains:
        # Get brand name
        brand_name = None
        if domain.get("brand_id"):
            brand = await db.brands.find_one({"id": domain["brand_id"]}, {"_id": 0, "name": 1})
            brand_name = brand["name"] if brand else None
        
        # Check if in SEO network
        entry = await db.seo_structure_entries.find_one(
            {"asset_domain_id": domain["id"]},
            {"_id": 0, "network_id": 1, "domain_role": 1}
        )
        
        network_name = None
        if entry:
            network = await db.seo_networks.find_one({"id": entry["network_id"]}, {"_id": 0, "name": 1})
            network_name = network["name"] if network else None
        
        result.append({
            "id": domain["id"],
            "domain_name": domain["domain_name"],
            "brand_name": brand_name,
            "last_http_code": domain.get("last_http_code") or domain.get("http_status_code"),
            "last_checked_at": domain.get("last_checked_at") or domain.get("last_check"),
            "network_name": network_name,
            "domain_role": entry.get("domain_role") if entry else None
        })
    
    return {
        "domains": result,
        "total": len(result)
    }

