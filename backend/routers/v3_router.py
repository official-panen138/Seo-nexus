"""
SEO-NOC V3 API Router
=====================
New API endpoints for V3 architecture:
- /api/v3/asset-domains - Pure inventory management
- /api/v3/networks - SEO network management
- /api/v3/structure - SEO structure entries with derived tiers
- /api/v3/activity-logs - Activity log queries
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import httpx
import logging

# Import models
import sys
sys.path.insert(0, '/app/backend')
from models_v3 import (
    AssetDomainCreate, AssetDomainUpdate, AssetDomainResponse,
    SeoNetworkCreate, SeoNetworkUpdate, SeoNetworkResponse, SeoNetworkDetail,
    SeoStructureEntryCreate, SeoStructureEntryUpdate, SeoStructureEntryResponse,
    ActivityLogResponse,
    RegistrarCreate, RegistrarUpdate, RegistrarResponse, RegistrarStatus,
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


# ==================== HELPER FUNCTIONS ====================

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
    """Get all asset domains with optional filters"""
    query = {}
    
    if brand_id:
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
    """Get a single asset domain by ID"""
    asset = await db.asset_domains.find_one({"id": asset_id}, {"_id": 0})
    if not asset:
        raise HTTPException(status_code=404, detail="Asset domain not found")
    
    asset = await enrich_asset_domain(asset)
    return AssetDomainResponse(**asset)


@router.post("/asset-domains", response_model=AssetDomainResponse)
async def create_asset_domain(
    data: AssetDomainCreate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Create a new asset domain"""
    # Validate brand exists
    if data.brand_id:
        brand = await db.brands.find_one({"id": data.brand_id})
        if not brand:
            raise HTTPException(status_code=400, detail="Brand not found")
    
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
    """Update an asset domain"""
    existing = await db.asset_domains.find_one({"id": asset_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Asset domain not found")
    
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
    """Create a new SEO network"""
    now = datetime.now(timezone.utc).isoformat()
    network = {
        "id": str(uuid.uuid4()),
        "legacy_id": None,
        **data.model_dump(),
        "created_at": now,
        "updated_at": now
    }
    
    # Convert enums
    if network.get("status") and hasattr(network["status"], "value"):
        network["status"] = network["status"].value
    
    await db.seo_networks.insert_one(network)
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.CREATE,
            entity_type=EntityType.SEO_NETWORK,
            entity_id=network["id"],
            after_value=network
        )
    
    network["domain_count"] = 0
    network["brand_name"] = None
    
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
    """Create a new SEO structure entry"""
    # Validate asset domain exists
    asset = await db.asset_domains.find_one({"id": data.asset_domain_id})
    if not asset:
        raise HTTPException(status_code=400, detail="Asset domain not found")
    
    # Validate network exists
    network = await db.seo_networks.find_one({"id": data.network_id})
    if not network:
        raise HTTPException(status_code=400, detail="Network not found")
    
    # Validate target domain if provided
    if data.target_asset_domain_id:
        target = await db.asset_domains.find_one({"id": data.target_asset_domain_id})
        if not target:
            raise HTTPException(status_code=400, detail="Target asset domain not found")
    
    # Check for duplicate entry (same domain in same network)
    existing = await db.seo_structure_entries.find_one({
        "asset_domain_id": data.asset_domain_id,
        "network_id": data.network_id
    })
    if existing:
        raise HTTPException(status_code=400, detail="Domain already exists in this network")
    
    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": str(uuid.uuid4()),
        "legacy_domain_id": None,
        **data.model_dump(),
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
    """Update an SEO structure entry"""
    existing = await db.seo_structure_entries.find_one({"id": entry_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Structure entry not found")
    
    update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
    
    # Validate target if changing
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
    """Delete an SEO structure entry"""
    existing = await db.seo_structure_entries.find_one({"id": entry_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Structure entry not found")
    
    # Check if other entries point to this one's asset
    pointing_to = await db.seo_structure_entries.count_documents({
        "target_asset_domain_id": existing["asset_domain_id"],
        "id": {"$ne": entry_id}
    })
    
    if pointing_to > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete: {pointing_to} other entries point to this domain"
        )
    
    await db.seo_structure_entries.delete_one({"id": entry_id})
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.DELETE,
            entity_type=EntityType.SEO_STRUCTURE_ENTRY,
            entity_id=entry_id,
            before_value=existing
        )
    
    return {"message": "Structure entry deleted"}


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


@router.get("/reports/conflicts")
async def get_v3_conflicts(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Detect SEO conflicts using V3 data and derived tiers"""
    conflicts = []
    
    networks = await db.seo_networks.find({}, {"_id": 0}).to_list(1000)
    
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
        
        for entry in entries:
            asset_id = entry["asset_domain_id"]
            tier = tiers.get(asset_id, 5)
            
            # Get domain name
            asset = await db.asset_domains.find_one({"id": asset_id}, {"_id": 0, "domain_name": 1})
            domain_name = asset["domain_name"] if asset else asset_id
            
            # Conflict 1: NOINDEX in high tier (0-2)
            if entry.get("index_status") == "noindex" and tier <= 2:
                conflicts.append({
                    "type": "noindex_high_tier",
                    "severity": "high",
                    "network_id": network["id"],
                    "network_name": network["name"],
                    "asset_domain_id": asset_id,
                    "domain_name": domain_name,
                    "tier": tier,
                    "tier_label": get_tier_label(tier),
                    "message": f"NOINDEX domain in {get_tier_label(tier)}"
                })
            
            # Conflict 2: Orphan (no target and not main)
            if entry.get("domain_role") != "main" and not entry.get("target_asset_domain_id"):
                # Check if it's truly orphaned (tier 5)
                if tier >= 5:
                    conflicts.append({
                        "type": "orphan",
                        "severity": "medium",
                        "network_id": network["id"],
                        "network_name": network["name"],
                        "asset_domain_id": asset_id,
                        "domain_name": domain_name,
                        "tier": tier,
                        "tier_label": get_tier_label(tier),
                        "message": "Domain not connected to main domain hierarchy"
                    })
    
    return {
        "conflicts": conflicts,
        "total": len(conflicts),
        "by_type": {
            "noindex_high_tier": len([c for c in conflicts if c["type"] == "noindex_high_tier"]),
            "orphan": len([c for c in conflicts if c["type"] == "orphan"])
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
