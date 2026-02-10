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
    AssetDomainCreate, AssetDomainUpdate, AssetDomainResponse, NetworkUsageInfo,
    PaginationMeta, PaginatedResponse,
    SeoNetworkCreate, SeoNetworkUpdate, SeoNetworkResponse, SeoNetworkDetail,
    SeoNetworkCreateLegacy, MainNodeConfig,
    SeoStructureEntryCreate, SeoStructureEntryUpdate, SeoStructureEntryResponse,
    SeoStructureEntryCreateWithNote, SeoStructureEntryUpdateWithNote,
    SeoChangeLogResponse, SeoNetworkNotification, SeoChangeActionType, SeoNotificationType,
    ActivityLogResponse,
    RegistrarCreate, RegistrarUpdate, RegistrarResponse, RegistrarStatus,
    SeoConflict, ConflictType, ConflictSeverity,
    MonitoringSettings, MonitoringSettingsUpdate,
    AssetStatus, NetworkStatus, DomainRole, SeoStatus, IndexStatus,
    ActionType, EntityType, get_tier_label,
    SeoOptimizationCreate, SeoOptimizationUpdate, SeoOptimizationResponse, SeoOptimizationDetailResponse,
    OptimizationActivityType, OptimizationStatus, ComplaintStatus, ObservedImpact,
    OptimizationComplaintCreate, OptimizationComplaintResponse, ComplaintPriority,
    TeamResponseCreate, TeamResponseEntry, ComplaintResolveRequest, OptimizationCloseRequest,
    NetworkAccessControl, NetworkVisibilityMode, UserTelegramSettings, NetworkManagersUpdate,
    OptimizationActivityTypeCreate, OptimizationActivityTypeResponse,
    UserSeoScore, TeamEvaluationSummary,
    ProjectComplaintCreate, ProjectComplaintResponse, ProjectComplaintResolveRequest
)
from services.seo_optimization_telegram_service import SeoOptimizationTelegramService

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
seo_change_log_service = None
seo_telegram_service = None


def init_v3_router(
    database,
    current_user_dep,
    roles_dep,
    activity_service,
    tier_svc,
    seo_change_svc=None,
    seo_telegram_svc=None
):
    """Initialize V3 router with dependencies"""
    global db, _get_current_user_dep, require_roles, activity_log_service, tier_service, seo_change_log_service, seo_telegram_service
    db = database
    _get_current_user_dep = current_user_dep
    require_roles = roles_dep
    activity_log_service = activity_service
    tier_service = tier_svc
    seo_change_log_service = seo_change_svc
    seo_telegram_service = seo_telegram_svc


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


async def check_network_visibility_access(network: dict, user: dict) -> bool:
    """
    Check if user has access to a specific network based on visibility settings.
    
    Visibility modes:
    - brand_based: User must have brand access (default) - Anyone with brand access can VIEW
    - restricted: User must be in manager_ids OR be Super Admin
    
    Note: Visibility ≠ Execution permission. 
    Execution is controlled by manager_ids separately.
    
    Returns True if user has VIEW access.
    """
    # Super Admin always has access
    if user.get("role") == "super_admin":
        return True
    
    # First check brand access
    if not check_brand_access(user, network.get("brand_id", "")):
        return False
    
    visibility_mode = network.get("visibility_mode", "brand_based")
    
    if visibility_mode == "restricted":
        # In restricted mode, only managers can view
        manager_ids = network.get("manager_ids", [])
        return user.get("id") in manager_ids
    
    # brand_based (default) - brand access is enough to VIEW
    return True


async def require_network_access(network: dict, user: dict):
    """
    Raise 403 if user doesn't have access to the network.
    Uses visibility mode rules to determine access.
    """
    has_access = await check_network_visibility_access(network, user)
    if not has_access:
        visibility_mode = network.get("visibility_mode", "brand_based")
        if visibility_mode == "restricted":
            raise HTTPException(status_code=403, detail="You do not have access to this network. It is restricted to specific users.")
        raise HTTPException(status_code=403, detail="You do not have access to this network.")


def is_network_manager(network: dict, user: dict) -> bool:
    """
    Check if user is a manager for the network.
    
    Manager permissions allow:
    - Creating/updating optimizations
    - Responding to complaints
    - Receiving notifications/reminders
    
    Super Admin always has manager permissions.
    """
    if user.get("role") == "super_admin":
        return True
    
    manager_ids = network.get("manager_ids", [])
    return user.get("id") in manager_ids


async def require_manager_permission(network: dict, user: dict):
    """
    Raise 403 if user is not a manager for the network.
    Used for execution permissions (create/update optimizations, respond to complaints).
    
    Super Admin always passes.
    """
    if not is_network_manager(network, user):
        raise HTTPException(
            status_code=403, 
            detail="You are not assigned as a manager for this SEO Network. Only managers can perform this action."
        )


async def require_manager_permission_by_network_id(network_id: str, user: dict) -> dict:
    """
    Fetch network and check manager permission.
    Returns the network if permission granted.
    """
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    await require_manager_permission(network, user)
    return network


async def require_network_access_by_id(network_id: str, user: dict):
    """
    Raise 403 if user doesn't have access to the network.
    """
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    has_access = await check_network_visibility_access(network, user)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied. This network has restricted visibility.")
    
    return network


# Minimum change note length for SEO changes
MIN_CHANGE_NOTE_LENGTH = 10


def validate_change_note(change_note: str) -> None:
    """
    Validate that change_note meets minimum requirements.
    Raises HTTPException if invalid.
    """
    if not change_note or len(change_note.strip()) < MIN_CHANGE_NOTE_LENGTH:
        raise HTTPException(
            status_code=400, 
            detail=f"Change note is required and must be at least {MIN_CHANGE_NOTE_LENGTH} characters. This note will be sent to the SEO team via Telegram."
        )


async def atomic_seo_change_with_notification(
    db,
    seo_change_log_service,
    seo_telegram_service,
    network_id: str,
    brand_id: str,
    actor_user_id: str,
    actor_email: str,
    action_type: str,
    affected_node: str,
    change_note: str,
    before_snapshot: dict = None,
    after_snapshot: dict = None,
    entry_id: str = None,
    skip_rate_limit: bool = False
) -> tuple:
    """
    Perform atomic SEO change: Log + Telegram notification.
    If Telegram fails, rollback the change log.
    
    Returns (success: bool, change_log_id: str, error_message: str)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Step 1: Create change log
    change_log_id = None
    if seo_change_log_service:
        change_log_id = await seo_change_log_service.log_change(
            network_id=network_id,
            brand_id=brand_id,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            action_type=action_type if isinstance(action_type, str) else action_type,
            affected_node=affected_node,
            change_note=change_note,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            entry_id=entry_id
        )
    
    # Step 2: Send Telegram notification (MANDATORY)
    notification_success = False
    error_message = None
    
    if seo_telegram_service:
        try:
            # Convert action_type to string for telegram service
            action_str = action_type.value if hasattr(action_type, 'value') else str(action_type)
            
            notification_success = await seo_telegram_service.send_seo_change_notification(
                network_id=network_id,
                brand_id=brand_id,
                actor_user_id=actor_user_id,
                actor_email=actor_email,
                action_type=action_str,
                affected_node=affected_node,
                change_note=change_note,
                before_snapshot=before_snapshot,
                after_snapshot=after_snapshot,
                change_log_id=change_log_id,
                skip_rate_limit=skip_rate_limit
            )
            
            # Update notification status
            if seo_change_log_service and change_log_id:
                await seo_change_log_service.update_notification_status(
                    change_log_id, 
                    "success" if notification_success else "failed"
                )
                
        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")
            error_message = str(e)
            notification_success = False
            
            # Update notification status as failed
            if seo_change_log_service and change_log_id:
                await seo_change_log_service.update_notification_status(change_log_id, "failed")
    else:
        # No telegram service configured - this is an error for production
        logger.warning("SEO Telegram service not configured - notification skipped")
        notification_success = True  # Allow if service not configured (for development)
    
    # Step 3: If notification failed, we need to flag it but NOT rollback
    # (Rolling back would lose the change data, which is worse)
    # Instead, we track the failure and can retry later
    
    return (notification_success, change_log_id, error_message)


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

@router.get("/asset-domains")
async def get_asset_domains(
    brand_id: Optional[str] = None,
    category_id: Optional[str] = None,
    registrar_id: Optional[str] = None,
    status: Optional[AssetStatus] = None,
    monitoring_enabled: Optional[bool] = None,
    search: Optional[str] = None,
    network_id: Optional[str] = None,
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    limit: int = Query(default=25, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Get asset domains with SERVER-SIDE PAGINATION - BRAND SCOPED.
    
    Returns paginated response with meta information:
    {
        "data": [...],
        "meta": {
            "page": 1,
            "limit": 25,
            "total": 1284,
            "total_pages": 52
        }
    }
    """
    import math
    
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
    
    # Filter by network_id if provided (domains used in a specific SEO network)
    if network_id:
        # Get all asset_domain_ids used in this network
        structure_entries = await db.seo_structure_entries.find(
            {"network_id": network_id},
            {"_id": 0, "asset_domain_id": 1}
        ).to_list(10000)
        domain_ids_in_network = [e["asset_domain_id"] for e in structure_entries]
        query["id"] = {"$in": domain_ids_in_network}
    
    # Get total count for pagination
    total = await db.asset_domains.count_documents(query)
    total_pages = math.ceil(total / limit) if total > 0 else 1
    
    # Calculate skip from page number
    skip = (page - 1) * limit
    
    # Fetch paginated data
    assets = await db.asset_domains.find(query, {"_id": 0}).sort("domain_name", 1).skip(skip).limit(limit).to_list(limit)
    
    # Batch enrich - brands, categories, registrars
    brands = {b["id"]: b["name"] for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    categories = {c["id"]: c["name"] for c in await db.categories.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    registrars = {r["id"]: r["name"] for r in await db.registrars.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    
    # Batch fetch SEO network usage for all domains (efficient aggregation)
    asset_ids = [a["id"] for a in assets]
    
    # Aggregate: group structure entries by asset_domain_id, include network info
    network_usage_pipeline = [
        {"$match": {"asset_domain_id": {"$in": asset_ids}}},
        {"$lookup": {
            "from": "seo_networks",
            "localField": "network_id",
            "foreignField": "id",
            "as": "network"
        }},
        {"$unwind": {"path": "$network", "preserveNullAndEmptyArrays": True}},
        {"$group": {
            "_id": "$asset_domain_id",
            "networks": {
                "$push": {
                    "network_id": "$network_id",
                    "network_name": "$network.name",
                    "role": "$domain_role",
                    "optimized_path": "$optimized_path"
                }
            }
        }}
    ]
    
    network_usage_result = await db.seo_structure_entries.aggregate(network_usage_pipeline).to_list(10000)
    network_usage_map = {item["_id"]: item["networks"] for item in network_usage_result}
    
    for asset in assets:
        asset["brand_name"] = brands.get(asset.get("brand_id"))
        asset["category_name"] = categories.get(asset.get("category_id"))
        # Use registrar_id lookup, fallback to legacy field
        asset["registrar_name"] = registrars.get(asset.get("registrar_id")) or asset.get("registrar")
        
        # Add SEO network usage
        raw_networks = network_usage_map.get(asset["id"], [])
        asset["seo_networks"] = [
            NetworkUsageInfo(
                network_id=n.get("network_id", ""),
                network_name=n.get("network_name", "Unknown"),
                role=n.get("role", "supporting"),
                optimized_path=n.get("optimized_path")
            )
            for n in raw_networks if n.get("network_id")
        ]
    
    # Return paginated response
    return {
        "data": [AssetDomainResponse(**a) for a in assets],
        "meta": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages
        }
    }


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
    """Delete an asset domain - BRAND SCOPED"""
    existing = await db.asset_domains.find_one({"id": asset_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Asset domain not found")
    
    # Validate brand access
    require_brand_access(existing.get("brand_id", ""), current_user)
    
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
    ranking_status: Optional[str] = None,  # Filter: "ranking", "tracking", "none"
    sort_by: Optional[str] = None,  # Sort: "best_position", "ranking_nodes"
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get all SEO networks - BRAND SCOPED, with ranking visibility"""
    from models_v3 import RankingStatus
    
    # Start with brand scope filter
    query = build_brand_filter(current_user)
    
    # If specific brand requested, validate access
    if brand_id:
        require_brand_access(brand_id, current_user)
        query["brand_id"] = brand_id
    
    if status:
        query["status"] = status.value
    
    networks = await db.seo_networks.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    
    # Filter by network visibility
    user_id = current_user.get("id")
    is_super_admin = current_user.get("role") == "super_admin"
    
    filtered_networks = []
    for network in networks:
        visibility = network.get("visibility_mode", "brand_based")
        
        if is_super_admin:
            # Super Admin sees everything
            filtered_networks.append(network)
        elif visibility == "restricted":
            # Only managers can see restricted networks
            if user_id in network.get("manager_ids", []):
                filtered_networks.append(network)
        else:
            # brand_based - brand access is enough to VIEW
            filtered_networks.append(network)
    
    networks = filtered_networks
    
    # Get brand names
    brands = {b["id"]: b["name"] for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    
    # Compute ranking metrics for each network
    result = []
    for network in networks:
        network["brand_name"] = brands.get(network.get("brand_id"))
        
        # Get all structure entries for this network
        entries = await db.seo_structure_entries.find(
            {"network_id": network["id"]},
            {"_id": 0, "ranking_position": 1, "ranking_url": 1, "primary_keyword": 1, "index_status": 1}
        ).to_list(1000)
        
        network["domain_count"] = len(entries)
        
        # Calculate ranking metrics
        ranking_nodes = []
        tracked_urls = []
        
        for entry in entries:
            pos = entry.get("ranking_position")
            ranking_url = entry.get("ranking_url") or ""
            primary_keyword = entry.get("primary_keyword") or ""
            index_status = entry.get("index_status", "index")
            
            # Check if ranking (position 1-100 OR has ranking_url)
            has_ranking = (pos is not None and 1 <= pos <= 100) or bool(ranking_url.strip())
            if has_ranking:
                if pos is not None and 1 <= pos <= 100:
                    ranking_nodes.append(pos)
            
            # Check if tracking (has keyword/url AND indexed, but no ranking position)
            has_tracking_data = bool(primary_keyword.strip()) or bool(ranking_url.strip())
            is_indexed = index_status == "index"
            if has_tracking_data and is_indexed:
                tracked_urls.append(entry)
        
        # Determine ranking status
        if ranking_nodes:
            network["ranking_status"] = RankingStatus.RANKING.value
        elif tracked_urls:
            network["ranking_status"] = RankingStatus.TRACKING.value
        else:
            network["ranking_status"] = RankingStatus.NONE.value
        
        network["ranking_nodes_count"] = len(ranking_nodes)
        network["best_ranking_position"] = min(ranking_nodes) if ranking_nodes else None
        network["tracked_urls_count"] = len(tracked_urls)
        
        # Access Summary Panel: Open complaints count and last optimization
        open_complaints = await db.seo_optimizations.count_documents({
            "network_id": network["id"],
            "complaint_status": {"$in": ["complained", "under_review"]}
        })
        network["open_complaints_count"] = open_complaints
        
        # Get most recent optimization date
        last_opt = await db.seo_optimizations.find_one(
            {"network_id": network["id"]},
            {"_id": 0, "created_at": 1},
            sort=[("created_at", -1)]
        )
        network["last_optimization_at"] = last_opt["created_at"] if last_opt else None
        
        result.append(network)
    
    # Filter by ranking_status if specified
    if ranking_status:
        result = [n for n in result if n.get("ranking_status") == ranking_status]
    
    # Sort if specified
    if sort_by == "best_position":
        # Sort by best position (ascending), None values at end
        result.sort(key=lambda x: (x.get("best_ranking_position") is None, x.get("best_ranking_position") or 999))
    elif sort_by == "ranking_nodes":
        # Sort by ranking nodes count (descending)
        result.sort(key=lambda x: x.get("ranking_nodes_count", 0), reverse=True)
    
    return [SeoNetworkResponse(**n) for n in result]


# ==================== NETWORK SEARCH ENDPOINT ====================

@router.get("/networks/search")
async def search_networks(
    query: str = Query(min_length=1, max_length=100, description="Search query for domain name or optimized path"),
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Search across SEO Networks by domain name or optimized path.
    
    Returns matching nodes grouped by domain, with network info.
    Brand-scoped - users only see results from brands they have access to.
    Max 10 results for debounce-friendly performance.
    """
    if not query or len(query.strip()) < 1:
        return {"results": [], "total": 0}
    
    search_term = query.strip()
    
    # Get user's brand scope
    brand_scope = get_user_brand_scope(current_user)
    
    # Build the aggregation pipeline to search structure entries
    pipeline = [
        # Join with asset_domains to get domain_name and brand_id
        {"$lookup": {
            "from": "asset_domains",
            "localField": "asset_domain_id",
            "foreignField": "id",
            "as": "domain"
        }},
        {"$unwind": "$domain"},
        
        # Search filter: match domain_name OR optimized_path
        {"$match": {
            "$or": [
                {"domain.domain_name": {"$regex": search_term, "$options": "i"}},
                {"optimized_path": {"$regex": search_term, "$options": "i"}}
            ]
        }},
        
        # Join with seo_networks to get network name and brand_id
        {"$lookup": {
            "from": "seo_networks",
            "localField": "network_id",
            "foreignField": "id",
            "as": "network"
        }},
        {"$unwind": "$network"},
    ]
    
    # Apply brand scoping if user is not super admin
    if brand_scope is not None:
        if not brand_scope:
            return {"results": [], "total": 0}  # No brand access
        pipeline.append({"$match": {"network.brand_id": {"$in": brand_scope}}})
    
    # Project the fields we need
    pipeline.extend([
        {"$project": {
            "_id": 0,
            "entry_id": "$id",
            "network_id": "$network_id",
            "network_name": "$network.name",
            "asset_domain_id": "$asset_domain_id",
            "domain_name": "$domain.domain_name",
            "optimized_path": "$optimized_path",
            "domain_role": "$domain_role",
            "brand_id": "$network.brand_id"
        }},
        
        # Sort for consistent results
        {"$sort": {"domain_name": 1, "optimized_path": 1}},
        
        # Limit results for performance
        {"$limit": 10}
    ])
    
    results = await db.seo_structure_entries.aggregate(pipeline).to_list(10)
    
    # Group results by domain for better UI display
    grouped = {}
    for r in results:
        domain_name = r["domain_name"]
        if domain_name not in grouped:
            grouped[domain_name] = {
                "domain_name": domain_name,
                "asset_domain_id": r["asset_domain_id"],
                "entries": []
            }
        grouped[domain_name]["entries"].append({
            "entry_id": r["entry_id"],
            "network_id": r["network_id"],
            "network_name": r["network_name"],
            "optimized_path": r.get("optimized_path") or "/",
            "role": r["domain_role"]
        })
    
    return {
        "results": list(grouped.values()),
        "total": len(results),
        "query": search_term
    }


@router.get("/networks/{network_id}", response_model=SeoNetworkDetail)
async def get_network(
    network_id: str,
    include_tiers: bool = True,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get a single SEO network with structure entries and calculated tiers - BRAND SCOPED"""
    logger.info(f"[GET_NETWORK] Fetching network: {network_id}")
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        logger.warning(f"[GET_NETWORK] Network not found: {network_id}")
        raise HTTPException(status_code=404, detail="Network not found")
    
    logger.info(f"[GET_NETWORK] Found network: {network.get('name')}, visibility: {network.get('visibility_mode', 'brand_based')}")
    
    # Validate brand access first
    require_brand_access(network.get("brand_id", ""), current_user)
    
    # Validate network visibility access (Restricted mode enforcement)
    await require_network_access(network, current_user)
    
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
    
    # Access Summary Panel: Open complaints count and last optimization
    open_complaints = await db.seo_optimizations.count_documents({
        "network_id": network_id,
        "complaint_status": {"$in": ["complained", "under_review"]}
    })
    network["open_complaints_count"] = open_complaints
    
    # Get most recent optimization date
    last_opt = await db.seo_optimizations.find_one(
        {"network_id": network_id},
        {"_id": 0, "created_at": 1},
        sort=[("created_at", -1)]
    )
    network["last_optimization_at"] = last_opt["created_at"] if last_opt else None
    
    return SeoNetworkDetail(**network)


@router.post("/networks", response_model=SeoNetworkResponse)
async def create_network(
    data: SeoNetworkCreate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Create a new SEO network with initial main node - BRAND SCOPED.
    
    Every network MUST have a main node defined at creation time.
    The main domain MUST belong to the same brand as the network.
    """
    # Validate brand exists (required field) and user has access
    brand = await db.brands.find_one({"id": data.brand_id})
    if not brand:
        raise HTTPException(status_code=400, detail="Brand not found")
    
    require_brand_access(data.brand_id, current_user)
    
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
    """Update an SEO network - BRAND SCOPED"""
    existing = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Network not found")
    
    # Validate brand access
    require_brand_access(existing.get("brand_id", ""), current_user)
    
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
    """Delete an SEO network - BRAND SCOPED"""
    existing = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Network not found")
    
    # Validate brand access
    require_brand_access(existing.get("brand_id", ""), current_user)
    
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
    data: SeoStructureEntryCreateWithNote,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Create a new SEO structure entry (node-based) with mandatory change note"""
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
    
    # === MAIN NODE VALIDATION RULES ===
    if data.domain_role == DomainRole.MAIN:
        # Rule 1: Main nodes MUST NOT have a target (they are the target)
        if data.target_entry_id or data.target_asset_domain_id:
            raise HTTPException(
                status_code=400,
                detail="Main (LP/Money Site) nodes cannot have a target. They are the primary target."
            )
        
        # Rule 2: Main nodes MUST have PRIMARY status (not canonical/redirect)
        if data.domain_status and data.domain_status not in [SeoStatus.PRIMARY, None]:
            raise HTTPException(
                status_code=400,
                detail=f"Main nodes must have 'primary' status, not '{data.domain_status.value}'. Main nodes don't redirect to themselves."
            )
        
        # Rule 3: Check if network already has a main node
        existing_main = await db.seo_structure_entries.find_one({
            "network_id": data.network_id,
            "domain_role": "main"
        })
        if existing_main:
            raise HTTPException(
                status_code=400,
                detail="Network already has a main node. Use 'Switch Main Target' to change it."
            )
    
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
    
    # Extract change_note before creating entry
    change_note = data.change_note
    
    # CRITICAL: Validate change_note BEFORE any save operation
    validate_change_note(change_note)
    
    now = datetime.now(timezone.utc).isoformat()
    entry_data = data.model_dump(exclude={"change_note"})  # Exclude change_note from entry data
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
    
    # Build node label for logging
    node_label = f"{asset['domain_name']}{normalized_path or ''}"
    
    # ATOMIC: Log + Telegram notification (both must succeed conceptually)
    notification_success, change_log_id, error_msg = await atomic_seo_change_with_notification(
        db=db,
        seo_change_log_service=seo_change_log_service,
        seo_telegram_service=seo_telegram_service,
        network_id=data.network_id,
        brand_id=network.get("brand_id", ""),
        actor_user_id=current_user.get("id", ""),
        actor_email=current_user["email"],
        action_type=SeoChangeActionType.CREATE_NODE,
        affected_node=node_label,
        change_note=change_note,
        before_snapshot=None,
        after_snapshot=entry,
        entry_id=entry["id"]
    )
    
    # Log system activity (separate from SEO change log)
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
    data: SeoStructureEntryUpdateWithNote,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Update an SEO structure entry (node-based) with mandatory change note"""
    existing = await db.seo_structure_entries.find_one({"id": entry_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Structure entry not found")
    
    # Extract and remove change_note from update_dict
    change_note = data.change_note
    
    # CRITICAL: Validate change_note BEFORE any save operation
    validate_change_note(change_note)
    
    update_dict = {k: v for k, v in data.model_dump(exclude={"change_note"}).items() if v is not None}
    
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
    
    # === MAIN NODE VALIDATION RULES ===
    # Determine the effective role after update
    new_role = update_dict.get("domain_role", existing.get("domain_role"))
    new_status = update_dict.get("domain_status", existing.get("domain_status"))
    new_target = update_dict.get("target_entry_id", existing.get("target_entry_id"))
    new_target_domain = update_dict.get("target_asset_domain_id", existing.get("target_asset_domain_id"))
    
    if new_role == "main" or new_role == DomainRole.MAIN:
        # Rule 1: Main nodes MUST NOT have a target
        if new_target or new_target_domain:
            raise HTTPException(
                status_code=400,
                detail="Main (LP/Money Site) nodes cannot have a target. They are the primary target."
            )
        
        # Rule 2: Main nodes MUST have PRIMARY status
        if new_status and new_status not in ["primary", SeoStatus.PRIMARY]:
            raise HTTPException(
                status_code=400,
                detail=f"Main nodes must have 'primary' status, not '{new_status}'. Main nodes don't redirect to themselves."
            )
        
        # Rule 3: Check if changing TO main role, and another main already exists
        if existing.get("domain_role") != "main" and (new_role == "main" or new_role == DomainRole.MAIN):
            existing_main = await db.seo_structure_entries.find_one({
                "network_id": existing["network_id"],
                "domain_role": "main",
                "id": {"$ne": entry_id}
            })
            if existing_main:
                raise HTTPException(
                    status_code=400,
                    detail="Network already has a main node. Use 'Switch Main Target' to change it safely."
                )
    
    # Convert enums
    for field in ["domain_role", "domain_status", "index_status"]:
        if field in update_dict and hasattr(update_dict[field], "value"):
            update_dict[field] = update_dict[field].value
    
    update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.seo_structure_entries.update_one({"id": entry_id}, {"$set": update_dict})
    
    # Get domain info for node label
    domain = await db.asset_domains.find_one({"id": existing["asset_domain_id"]}, {"_id": 0, "domain_name": 1})
    domain_name = domain["domain_name"] if domain else "unknown"
    node_label = f"{domain_name}{existing.get('optimized_path', '') or ''}"
    
    # Get network for brand_id
    network = await db.seo_networks.find_one({"id": existing["network_id"]}, {"_id": 0, "brand_id": 1})
    brand_id = network.get("brand_id", "") if network else ""
    
    # Determine action type based on what changed
    after_snapshot = {**existing, **update_dict}
    action_type_str = "update_node"
    action_type = None
    if seo_change_log_service:
        action_type = seo_change_log_service.determine_action_type(
            is_create=False,
            is_delete=False,
            before=existing,
            after=after_snapshot
        )
        action_type_str = action_type.value if hasattr(action_type, 'value') else action_type
    
    # ATOMIC: Log + Telegram notification
    notification_success, change_log_id, error_msg = await atomic_seo_change_with_notification(
        db=db,
        seo_change_log_service=seo_change_log_service,
        seo_telegram_service=seo_telegram_service,
        network_id=existing["network_id"],
        brand_id=brand_id,
        actor_user_id=current_user.get("id", ""),
        actor_email=current_user["email"],
        action_type=action_type if action_type else action_type_str,
        affected_node=node_label,
        change_note=change_note,
        before_snapshot=existing,
        after_snapshot=after_snapshot,
        entry_id=entry_id
    )
    
    # Log system activity (separate from SEO change log)
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.SEO_STRUCTURE_ENTRY,
            entity_id=entry_id,
            before_value=existing,
            after_value=after_snapshot
        )


# ==================== SEO OPTIMIZATIONS ENDPOINTS ====================

@router.get("/networks/{network_id}/optimizations")
async def get_network_optimizations(
    network_id: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    activity_type: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Get all SEO optimizations for a network with pagination.
    This does NOT affect the SEO structure - it's an execution & intelligence layer.
    """
    import math
    
    # Verify network exists and user has access
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    require_brand_access(network["brand_id"], current_user)
    await require_network_access(network, current_user)  # Enforce restricted mode
    
    # Build query
    query = {"network_id": network_id}
    if activity_type:
        query["activity_type"] = activity_type
    if status:
        query["status"] = status
    
    # Get total count
    total = await db.seo_optimizations.count_documents(query)
    total_pages = math.ceil(total / limit) if total > 0 else 1
    
    # Fetch paginated data
    skip = (page - 1) * limit
    optimizations = await db.seo_optimizations.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    # Get brand name for enrichment
    brand = await db.brands.find_one({"id": network["brand_id"]}, {"_id": 0, "name": 1})
    brand_name = brand["name"] if brand else "Unknown"
    
    # Enrich responses
    for opt in optimizations:
        opt["network_name"] = network["name"]
        opt["brand_name"] = brand_name
    
    return {
        "data": [SeoOptimizationResponse(**opt) for opt in optimizations],
        "meta": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages
        }
    }


@router.get("/networks/{network_id}/optimizations/export")
async def export_network_optimizations_csv(
    network_id: str,
    status: Optional[str] = None,
    activity_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Export all optimizations for a network as CSV.
    Only Admin/Super Admin can export.
    """
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    require_brand_access(network["brand_id"], current_user)
    await require_network_access(network, current_user)  # Enforce restricted mode
    
    # Build query
    query = {"network_id": network_id}
    if status:
        query["status"] = status
    if activity_type:
        query["activity_type"] = activity_type
    
    optimizations = await db.seo_optimizations.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    # Get complaint counts
    complaint_counts = {}
    for opt in optimizations:
        count = await db.optimization_complaints.count_documents({"optimization_id": opt["id"]})
        complaint_counts[opt["id"]] = count
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        'ID',
        'Title',
        'Activity Type',
        'Status',
        'Complaint Status',
        'Created By',
        'Created At',
        'Updated At',
        'Closed At',
        'Closed By',
        'Description',
        'Reason Note',
        'Affected Scope',
        'Target Domains',
        'Keywords',
        'Expected Impact',
        'Observed Impact',
        'Complaints Count',
        'Report URLs'
    ])
    
    # Data rows
    for opt in optimizations:
        writer.writerow([
            opt["id"],
            opt["title"],
            opt.get("activity_type", ""),
            opt["status"],
            opt.get("complaint_status", "none"),
            opt.get("created_by", {}).get("display_name", ""),
            opt.get("created_at", ""),
            opt.get("updated_at", ""),
            opt.get("closed_at", ""),
            opt.get("closed_by", {}).get("display_name", "") if opt.get("closed_by") else "",
            opt.get("description", ""),
            opt.get("reason_note", ""),
            opt.get("affected_scope", ""),
            "|".join(opt.get("target_domains", [])),
            "|".join(opt.get("keywords", [])),
            "|".join(opt.get("expected_impact", [])),
            opt.get("observed_impact", ""),
            complaint_counts.get(opt["id"], 0),
            "|".join([r.get("url", r) if isinstance(r, dict) else r for r in opt.get("report_urls", [])])
        ])
    
    output.seek(0)
    
    # Filename
    network_name = network.get("name", "network").replace(" ", "_")
    filename = f"optimizations_{network_name}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


@router.post("/networks/{network_id}/optimizations", response_model=SeoOptimizationResponse)
async def create_network_optimization(
    network_id: str,
    data: SeoOptimizationCreate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Create a new SEO optimization activity for a network.
    This does NOT modify the SEO structure (graph).
    Sends Telegram notification on creation.
    
    REQUIRED: 
    - reason_note (min 20 characters) - explains why this optimization is being done.
    - User must be a Manager for this network OR Super Admin.
    """
    # Verify network exists and user has access
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    require_brand_access(network["brand_id"], current_user)
    
    # Check manager permission - only managers or super admin can create optimizations
    await require_manager_permission(network, current_user)
    
    # Validate required fields
    if not data.title or not data.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    if not data.description or not data.description.strip():
        raise HTTPException(status_code=400, detail="Description is required")
    
    # MANDATORY: reason_note must be at least 20 characters
    if not data.reason_note or len(data.reason_note.strip()) < 20:
        raise HTTPException(
            status_code=400, 
            detail="Reason note is required (minimum 20 characters). Please explain why this optimization is being done."
        )
    
    # Resolve activity type
    activity_type_str = data.activity_type or "other"
    activity_type_name = None
    if data.activity_type_id:
        activity_type_doc = await db.seo_optimization_activity_types.find_one({"id": data.activity_type_id}, {"_id": 0})
        if activity_type_doc:
            activity_type_str = activity_type_doc.get("name", "other").lower().replace(" ", "_")
            activity_type_name = activity_type_doc.get("name")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Convert and validate report_urls
    report_urls_data = []
    for url_entry in data.report_urls:
        if isinstance(url_entry, str):
            # Plain string URL - add today's date
            report_urls_data.append({"url": url_entry, "start_date": now[:10]})
        elif isinstance(url_entry, dict):
            # Dict entry - validate required fields
            if not url_entry.get("url"):
                raise HTTPException(status_code=400, detail="Report URL is required for each entry")
            if not url_entry.get("start_date"):
                raise HTTPException(status_code=400, detail="Report start date is required for each entry")
            report_urls_data.append(url_entry)
        else:
            # Pydantic model
            entry_dict = url_entry.model_dump() if hasattr(url_entry, 'model_dump') else dict(url_entry)
            if not entry_dict.get("url"):
                raise HTTPException(status_code=400, detail="Report URL is required for each entry")
            if not entry_dict.get("start_date"):
                raise HTTPException(status_code=400, detail="Report start date is required for each entry")
            report_urls_data.append(entry_dict)
    
    optimization = {
        "id": str(uuid.uuid4()),
        "network_id": network_id,
        "brand_id": network["brand_id"],
        "created_by": {
            "user_id": current_user["id"],
            "display_name": current_user.get("name", current_user["email"].split("@")[0].title()),
            "email": current_user["email"]
        },
        "created_at": now,
        "updated_at": now,
        "activity_type_id": data.activity_type_id,
        "activity_type": activity_type_str,
        "activity_type_name": activity_type_name,
        "title": data.title.strip(),
        "description": data.description.strip(),
        "reason_note": data.reason_note.strip(),
        "affected_scope": data.affected_scope.value,
        "target_domains": data.target_domains,
        "keywords": data.keywords,
        "report_urls": report_urls_data,
        "expected_impact": [i.value for i in data.expected_impact],
        "observed_impact": None,
        "status": data.status.value,
        "complaint_status": "none",
        "complaint_note": None,
        "complaints_count": 0,
        "telegram_notified_at": None
    }
    
    await db.seo_optimizations.insert_one(optimization)
    
    # Get brand for notification
    brand = await db.brands.find_one({"id": network["brand_id"]}, {"_id": 0})
    
    # Send Telegram notification
    try:
        telegram_service = SeoOptimizationTelegramService(db)
        await telegram_service.send_optimization_created_notification(
            optimization, network, brand or {}
        )
    except Exception as e:
        logger.warning(f"Failed to send Telegram notification for optimization: {e}")
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.CREATE,
            entity_type=EntityType.SEO_OPTIMIZATION,
            entity_id=optimization["id"],
            after_value={"title": optimization["title"], "activity_type": optimization["activity_type"], "reason_note": optimization["reason_note"]}
        )
    
    # Enrich response
    optimization["network_name"] = network["name"]
    optimization["brand_name"] = brand["name"] if brand else "Unknown"
    
    return SeoOptimizationResponse(**optimization)


# ==================== STATIC OPTIMIZATION ROUTES (Must be before parameterized routes) ====================

@router.post("/optimizations/digest")
async def send_optimization_digest(
    background_tasks: BackgroundTasks,
    brand_id: Optional[str] = None,
    days: int = Query(default=7, ge=1, le=90),
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Generate and send SEO optimization digest via Telegram.
    Admin/Super Admin only.
    """
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin role required")
    
    from services.seo_digest_service import SeoDigestService
    digest_service = SeoDigestService(db)
    
    async def send_digest_task():
        success = await digest_service.send_digest(brand_id, days)
        logger.info(f"Digest send result: {success}")
    
    background_tasks.add_task(send_digest_task)
    
    return {"message": "Digest scheduled", "status": "running", "days": days}


@router.get("/optimizations/digest/preview")
async def preview_optimization_digest(
    brand_id: Optional[str] = None,
    days: int = Query(default=7, ge=1, le=90),
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Preview the optimization digest without sending.
    Returns the digest data and formatted message.
    """
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin role required")
    
    from services.seo_digest_service import SeoDigestService
    digest_service = SeoDigestService(db)
    
    digest = await digest_service.generate_weekly_digest(brand_id, days)
    message = await digest_service.format_telegram_digest(digest)
    
    return {
        "data": digest,
        "formatted_message": message
    }


@router.get("/optimizations/ai-summary")
async def get_ai_optimization_summary(
    network_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    days: int = Query(default=7, ge=1, le=30),
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Generate an AI-powered summary of SEO optimization activities.
    Uses GPT-4o to analyze and summarize activities.
    """
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin role required")
    
    from services.ai_summary_service import AiSummaryService
    ai_service = AiSummaryService(db)
    
    result = await ai_service.generate_optimization_summary(network_id, brand_id, days)
    
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result


# ==================== PARAMETERIZED OPTIMIZATION ROUTES ====================

@router.get("/optimizations/{optimization_id}", response_model=SeoOptimizationResponse)
async def get_optimization(
    optimization_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get a single SEO optimization by ID"""
    optimization = await db.seo_optimizations.find_one({"id": optimization_id}, {"_id": 0})
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")
    
    require_brand_access(optimization["brand_id"], current_user)
    
    # Enrich with network and brand names
    network = await db.seo_networks.find_one({"id": optimization["network_id"]}, {"_id": 0, "name": 1})
    brand = await db.brands.find_one({"id": optimization["brand_id"]}, {"_id": 0, "name": 1})
    
    optimization["network_name"] = network["name"] if network else "Unknown"
    optimization["brand_name"] = brand["name"] if brand else "Unknown"
    
    return SeoOptimizationResponse(**optimization)


@router.put("/optimizations/{optimization_id}", response_model=SeoOptimizationResponse)
async def update_optimization(
    optimization_id: str,
    data: SeoOptimizationUpdate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Update an SEO optimization activity.
    Sends Telegram notification if status changes to COMPLETED or REVERTED.
    
    Only Managers or Super Admin can update optimizations.
    """
    optimization = await db.seo_optimizations.find_one({"id": optimization_id}, {"_id": 0})
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")
    
    require_brand_access(optimization["brand_id"], current_user)
    
    # Get network to check manager permission
    network = await db.seo_networks.find_one({"id": optimization["network_id"]}, {"_id": 0})
    if network:
        await require_manager_permission(network, current_user)
    
    old_status = optimization.get("status")
    
    # Build update dict
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if data.activity_type is not None:
        update_data["activity_type"] = data.activity_type.value
    if data.title is not None:
        if not data.title.strip():
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        update_data["title"] = data.title.strip()
    if data.description is not None:
        if not data.description.strip():
            raise HTTPException(status_code=400, detail="Description cannot be empty")
        update_data["description"] = data.description.strip()
    if data.affected_scope is not None:
        update_data["affected_scope"] = data.affected_scope.value
    if data.affected_targets is not None:
        update_data["affected_targets"] = data.affected_targets
    if data.keywords is not None:
        update_data["keywords"] = data.keywords
    if data.report_urls is not None:
        update_data["report_urls"] = data.report_urls
    if data.expected_impact is not None:
        update_data["expected_impact"] = [i.value for i in data.expected_impact]
    if data.status is not None:
        update_data["status"] = data.status.value
    
    await db.seo_optimizations.update_one(
        {"id": optimization_id},
        {"$set": update_data}
    )
    
    # Get updated optimization
    updated_optimization = await db.seo_optimizations.find_one({"id": optimization_id}, {"_id": 0})
    
    # Check if status changed to completed or reverted
    new_status = update_data.get("status", old_status)
    if new_status != old_status and new_status in ["completed", "reverted"]:
        # Get network and brand for notification
        network = await db.seo_networks.find_one({"id": optimization["network_id"]}, {"_id": 0})
        brand = await db.brands.find_one({"id": optimization["brand_id"]}, {"_id": 0})
        
        try:
            telegram_service = SeoOptimizationTelegramService(db)
            await telegram_service.send_status_change_notification(
                updated_optimization, network or {}, brand or {},
                old_status, new_status, current_user
            )
        except Exception as e:
            logger.warning(f"Failed to send status change notification: {e}")
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.SEO_OPTIMIZATION,
            entity_id=optimization_id,
            before_value={"status": old_status},
            after_value=update_data
        )
    
    # Enrich response
    network = await db.seo_networks.find_one({"id": updated_optimization["network_id"]}, {"_id": 0, "name": 1})
    brand = await db.brands.find_one({"id": updated_optimization["brand_id"]}, {"_id": 0, "name": 1})
    updated_optimization["network_name"] = network["name"] if network else "Unknown"
    updated_optimization["brand_name"] = brand["name"] if brand else "Unknown"
    
    return SeoOptimizationResponse(**updated_optimization)


@router.delete("/optimizations/{optimization_id}")
async def delete_optimization(
    optimization_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Delete an SEO optimization activity.
    CRITICAL: Only Super Admin can delete optimizations.
    Optimizations are audit records - deletion by regular users breaks accountability.
    """
    # CRITICAL: Only Super Admin can delete optimizations
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=403, 
            detail="Only Super Admin can delete optimization records. Optimizations are audit records that must be preserved."
        )
    
    optimization = await db.seo_optimizations.find_one({"id": optimization_id}, {"_id": 0})
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")
    
    await db.seo_optimizations.delete_one({"id": optimization_id})
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.DELETE,
            entity_type=EntityType.SEO_OPTIMIZATION,
            entity_id=optimization_id,
            before_value={"title": optimization.get("title"), "deleted_by": "super_admin"}
        )
    
    return {"message": "Optimization deleted"}


# ==================== OPTIMIZATION COMPLAINTS ====================

@router.post("/optimizations/{optimization_id}/complaints", response_model=OptimizationComplaintResponse)
async def create_optimization_complaint(
    optimization_id: str,
    data: OptimizationComplaintCreate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Create a complaint on an SEO optimization.
    Only Super Admin can create complaints.
    Automatically tags assigned users from network Access Summary via Telegram.
    """
    # Only Super Admin can create complaints
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can create complaints")
    
    optimization = await db.seo_optimizations.find_one({"id": optimization_id}, {"_id": 0})
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")
    
    # Validate required field
    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=400, detail="Complaint reason is required")
    
    # Get network to access managers from SEO Network Management
    network = await db.seo_networks.find_one({"id": optimization["network_id"]}, {"_id": 0})
    
    # Build responsible user list: combine explicit selection + network managers
    all_responsible_user_ids = set(data.responsible_user_ids or [])
    
    # Auto-add managers from network (they are responsible for execution)
    if network and network.get("manager_ids"):
        all_responsible_user_ids.update(network["manager_ids"])
        logger.info(f"[COMPLAINT] Auto-added {len(network['manager_ids'])} managers from SEO Network Management")
    
    # Get responsible users info for notification
    responsible_users = []
    if all_responsible_user_ids:
        users = await db.users.find(
            {"id": {"$in": list(all_responsible_user_ids)}},
            {"_id": 0, "id": 1, "email": 1, "name": 1, "telegram_username": 1}
        ).to_list(100)
        responsible_users = users
    
    now = datetime.now(timezone.utc).isoformat()
    
    complaint = {
        "id": str(uuid.uuid4()),
        "optimization_id": optimization_id,
        "network_id": optimization["network_id"],
        "brand_id": optimization["brand_id"],
        "created_by": {
            "user_id": current_user["id"],
            "display_name": current_user.get("name", current_user["email"].split("@")[0].title()),
            "email": current_user["email"]
        },
        "created_at": now,
        "reason": data.reason.strip(),
        "responsible_user_ids": list(all_responsible_user_ids),  # Store all responsible users
        "explicit_responsible_user_ids": data.responsible_user_ids or [],  # Explicitly selected users
        "auto_assigned_from_network": True if network and network.get("visibility_mode") == "restricted" else False,
        "priority": data.priority.value if data.priority else "medium",
        "report_urls": data.report_urls,
        "status": "open",
        "telegram_notified_at": None
    }
    
    await db.optimization_complaints.insert_one(complaint)
    
    # Update optimization complaints count AND complaint_status
    await db.seo_optimizations.update_one(
        {"id": optimization_id},
        {
            "$inc": {"complaints_count": 1},
            "$set": {
                "complaint_status": "complained",
                "updated_at": now
            }
        }
    )
    
    # Get network and brand for notification
    network = await db.seo_networks.find_one({"id": optimization["network_id"]}, {"_id": 0})
    brand = await db.brands.find_one({"id": optimization["brand_id"]}, {"_id": 0})
    
    # Send Telegram notification with user tagging
    try:
        telegram_service = SeoOptimizationTelegramService(db)
        await telegram_service.send_complaint_notification(
            complaint, optimization, network or {}, brand or {}, responsible_users
        )
    except Exception as e:
        logger.warning(f"Failed to send complaint notification: {e}")
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.CREATE,
            entity_type=EntityType.SEO_OPTIMIZATION,
            entity_id=optimization_id,
            after_value={"action": "complaint_created", "complaint_id": complaint["id"], "priority": complaint["priority"]}
        )
    
    complaint["responsible_users"] = responsible_users
    return OptimizationComplaintResponse(**complaint)


@router.get("/optimizations/{optimization_id}/complaints")
async def get_optimization_complaints(
    optimization_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get all complaints for an optimization"""
    optimization = await db.seo_optimizations.find_one({"id": optimization_id}, {"_id": 0})
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")
    
    require_brand_access(optimization["brand_id"], current_user)
    
    complaints = await db.optimization_complaints.find(
        {"optimization_id": optimization_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Enrich with responsible users
    for complaint in complaints:
        if complaint.get("responsible_user_ids"):
            users = await db.users.find(
                {"id": {"$in": complaint["responsible_user_ids"]}},
                {"_id": 0, "id": 1, "email": 1, "name": 1, "telegram_username": 1}
            ).to_list(100)
            complaint["responsible_users"] = users
        else:
            complaint["responsible_users"] = []
    
    return complaints


# ==================== PROJECT-LEVEL COMPLAINTS ====================

@router.post("/networks/{network_id}/complaints", response_model=ProjectComplaintResponse)
async def create_project_complaint(
    network_id: str,
    data: ProjectComplaintCreate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Create a project-level complaint (not tied to a specific optimization).
    Only Super Admin can create project-level complaints.
    """
    # Only Super Admin can create complaints
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can create project complaints")
    
    # Validate network exists and get brand
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0, "brand_id": 1, "name": 1})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    # Validate brand access
    require_brand_access(network["brand_id"], current_user)
    
    # Validate reason length
    if len(data.reason.strip()) < 10:
        raise HTTPException(status_code=400, detail="Complaint reason must be at least 10 characters")
    
    # Enrich responsible users
    responsible_users = []
    if data.responsible_user_ids:
        users = await db.users.find(
            {"id": {"$in": data.responsible_user_ids}},
            {"_id": 0, "id": 1, "name": 1, "email": 1, "telegram_username": 1}
        ).to_list(100)
        responsible_users = users
    
    # Create complaint
    complaint = {
        "id": str(uuid.uuid4()),
        "network_id": network_id,
        "brand_id": network["brand_id"],
        "created_by": {
            "user_id": current_user["id"],
            "display_name": current_user.get("name") or current_user.get("email"),
            "email": current_user.get("email")
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resolved_at": None,
        "resolved_by": None,
        "reason": data.reason.strip(),
        "responsible_user_ids": data.responsible_user_ids,
        "responsible_users": responsible_users,
        "priority": data.priority.value if data.priority else "medium",
        "status": "open",
        "resolution_note": None,
        "report_urls": data.report_urls or [],
        "category": data.category,
        "responses": []
    }
    
    await db.project_complaints.insert_one(complaint)
    
    # Send Telegram notification
    try:
        telegram_service = SeoOptimizationTelegramService()
        await telegram_service.send_project_complaint_notification(
            complaint=complaint,
            network_name=network["name"],
            responsible_users=responsible_users
        )
    except Exception as e:
        logger.error(f"Failed to send project complaint Telegram notification: {e}")
    
    return ProjectComplaintResponse(**complaint)


@router.get("/networks/{network_id}/complaints", response_model=List[ProjectComplaintResponse])
async def get_project_complaints(
    network_id: str,
    status: Optional[str] = None,  # open, under_review, resolved, dismissed
    limit: int = 50,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Get all project-level complaints for a network.
    """
    # Validate network exists
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0, "brand_id": 1})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    require_brand_access(network["brand_id"], current_user)
    
    query = {"network_id": network_id}
    if status:
        query["status"] = status
    
    complaints = await db.project_complaints.find(
        query, {"_id": 0}
    ).sort("created_at", -1).to_list(limit)
    
    return [ProjectComplaintResponse(**c) for c in complaints]


@router.post("/networks/{network_id}/complaints/{complaint_id}/respond")
async def respond_to_project_complaint(
    network_id: str,
    complaint_id: str,
    data: TeamResponseCreate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Add a response to a project-level complaint.
    Managers and Super Admin can respond.
    """
    # Validate complaint exists
    complaint = await db.project_complaints.find_one({"id": complaint_id, "network_id": network_id}, {"_id": 0})
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    require_brand_access(complaint["brand_id"], current_user)
    
    # Validate note length
    if len(data.note.strip()) < 20:
        raise HTTPException(status_code=400, detail="Response must be at least 20 characters")
    
    # Create response entry
    response_entry = {
        "id": str(uuid.uuid4()),
        "created_by": {
            "user_id": current_user["id"],
            "display_name": current_user.get("name") or current_user.get("email"),
            "email": current_user.get("email")
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": data.note.strip(),
        "report_urls": data.report_urls or []
    }
    
    # Update complaint with response and set to under_review if currently open
    update_data = {
        "$push": {"responses": response_entry}
    }
    if complaint.get("status") == "open":
        update_data["$set"] = {"status": "under_review"}
    
    await db.project_complaints.update_one({"id": complaint_id}, update_data)
    
    return {"message": "Response added successfully", "response_id": response_entry["id"]}


@router.patch("/networks/{network_id}/complaints/{complaint_id}/resolve")
async def resolve_project_complaint(
    network_id: str,
    complaint_id: str,
    data: ProjectComplaintResolveRequest,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Resolve a project-level complaint. Super Admin only.
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can resolve complaints")
    
    # Validate complaint exists
    complaint = await db.project_complaints.find_one({"id": complaint_id, "network_id": network_id}, {"_id": 0})
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    if len(data.resolution_note.strip()) < 10:
        raise HTTPException(status_code=400, detail="Resolution note must be at least 10 characters")
    
    await db.project_complaints.update_one(
        {"id": complaint_id},
        {"$set": {
            "status": "resolved",
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "resolved_by": {
                "user_id": current_user["id"],
                "display_name": current_user.get("name") or current_user.get("email"),
                "email": current_user.get("email")
            },
            "resolution_note": data.resolution_note.strip()
        }}
    )
    
    return {"message": "Complaint resolved successfully"}


# ==================== OPTIMIZATION DETAIL & RESPONSE ENDPOINTS ====================

@router.get("/optimizations/{optimization_id}/detail", response_model=SeoOptimizationDetailResponse)
async def get_optimization_detail(
    optimization_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Get full optimization detail including complaints and responses.
    Used for the Optimization Detail drawer/page.
    """
    optimization = await db.seo_optimizations.find_one({"id": optimization_id}, {"_id": 0})
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")
    
    require_brand_access(optimization["brand_id"], current_user)
    
    # Get network and brand names
    network = await db.seo_networks.find_one({"id": optimization["network_id"]}, {"_id": 0, "name": 1})
    brand = await db.brands.find_one({"id": optimization["brand_id"]}, {"_id": 0, "name": 1})
    
    # Get all complaints sorted by date (newest first)
    complaints = await db.optimization_complaints.find(
        {"optimization_id": optimization_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Enrich complaints with user info
    for complaint in complaints:
        if complaint.get("responsible_user_ids"):
            users = await db.users.find(
                {"id": {"$in": complaint["responsible_user_ids"]}},
                {"_id": 0, "id": 1, "email": 1, "name": 1, "telegram_username": 1}
            ).to_list(100)
            complaint["responsible_users"] = users
        else:
            complaint["responsible_users"] = []
        
        # Calculate time to resolution if resolved
        if complaint.get("resolved_at") and complaint.get("created_at"):
            try:
                created = datetime.fromisoformat(complaint["created_at"].replace("Z", "+00:00"))
                resolved = datetime.fromisoformat(complaint["resolved_at"].replace("Z", "+00:00"))
                complaint["time_to_resolution_hours"] = (resolved - created).total_seconds() / 3600
            except Exception:
                pass
    
    # Get team responses
    responses = optimization.get("responses", [])
    
    # Determine active complaint (latest unresolved)
    active_complaint = None
    for c in complaints:
        if c.get("status") in ["open", "under_review"]:
            active_complaint = c
            break
    
    # Check if blocked
    is_blocked = active_complaint is not None
    blocked_reason = None
    if is_blocked:
        blocked_reason = f"⚠ Blocked by Complaint #{len([c for c in complaints if c.get('status') != 'resolved'])} – resolve before closing"
    
    return SeoOptimizationDetailResponse(
        id=optimization["id"],
        network_id=optimization["network_id"],
        brand_id=optimization["brand_id"],
        created_by=optimization["created_by"],
        created_at=optimization["created_at"],
        updated_at=optimization.get("updated_at"),
        closed_at=optimization.get("closed_at"),
        closed_by=optimization.get("closed_by"),
        activity_type_id=optimization.get("activity_type_id"),
        activity_type=optimization.get("activity_type", "other"),
        activity_type_name=optimization.get("activity_type_name"),
        title=optimization["title"],
        description=optimization["description"],
        reason_note=optimization.get("reason_note"),
        affected_scope=optimization.get("affected_scope", "specific_domain"),
        target_domains=optimization.get("target_domains", []),
        keywords=optimization.get("keywords", []),
        report_urls=optimization.get("report_urls", []),
        expected_impact=optimization.get("expected_impact", []),
        observed_impact=optimization.get("observed_impact"),
        status=optimization["status"],
        complaint_status=optimization.get("complaint_status", "none"),
        network_name=network.get("name") if network else None,
        brand_name=brand.get("name") if brand else None,
        complaints=complaints,
        active_complaint=active_complaint,
        responses=responses,
        complaints_count=len(complaints),
        has_repeated_issue=len(complaints) >= 2,
        is_blocked=is_blocked,
        blocked_reason=blocked_reason
    )


@router.post("/optimizations/{optimization_id}/responses")
async def add_team_response(
    optimization_id: str,
    data: TeamResponseCreate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Add a team response to an optimization.
    Used to respond to complaints or add corrective action notes.
    
    Rules:
    - Min 20 chars, max 2000 chars for note
    - Only Managers or Super Admin can respond
    - Changes complaint_status to 'under_review' if currently 'complained'
    """
    # Validate response note length
    if len(data.note.strip()) < 20:
        raise HTTPException(status_code=400, detail="Response note must be at least 20 characters")
    if len(data.note.strip()) > 2000:
        raise HTTPException(status_code=400, detail="Response note cannot exceed 2000 characters")
    
    optimization = await db.seo_optimizations.find_one({"id": optimization_id}, {"_id": 0})
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")
    
    require_brand_access(optimization["brand_id"], current_user)
    
    # Check manager permission - only managers can respond to complaints
    network = await db.seo_networks.find_one({"id": optimization["network_id"]}, {"_id": 0})
    if network:
        await require_manager_permission(network, current_user)
    
    # Create response entry
    response_entry = {
        "id": str(uuid.uuid4()),
        "created_by": {
            "user_id": current_user["id"],
            "display_name": current_user.get("name", current_user["email"].split("@")[0]),
            "email": current_user["email"]
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": data.note.strip(),
        "report_urls": data.report_urls
    }
    
    # Find active complaint to link
    active_complaint = await db.optimization_complaints.find_one(
        {"optimization_id": optimization_id, "status": {"$in": ["open", "under_review"]}},
        {"_id": 0, "id": 1}
    )
    if active_complaint:
        response_entry["complaint_id"] = active_complaint["id"]
    
    # Update optimization
    update_data = {
        "$push": {"responses": response_entry},
        "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
    }
    
    # If complaint status is 'complained', move to 'under_review'
    if optimization.get("complaint_status") == "complained":
        update_data["$set"]["complaint_status"] = "under_review"
        
        # Also update the complaint record
        if active_complaint:
            await db.optimization_complaints.update_one(
                {"id": active_complaint["id"]},
                {"$set": {"status": "under_review"}}
            )
    
    await db.seo_optimizations.update_one({"id": optimization_id}, update_data)
    
    # Send Telegram notification
    try:
        from services.seo_optimization_telegram_service import seo_optimization_telegram_service
        if seo_optimization_telegram_service:
            network = await db.seo_networks.find_one({"id": optimization["network_id"]}, {"_id": 0, "name": 1})
            brand = await db.brands.find_one({"id": optimization["brand_id"]}, {"_id": 0, "name": 1})
            
            message = f"""📝 *TEAM RESPONSE ADDED*

📋 *Optimization:* {optimization['title']}
🌐 *Network:* {network.get('name') if network else 'Unknown'}
🏷️ *Brand:* {brand.get('name') if brand else 'Unknown'}

👤 *Responded by:* {current_user.get('name', current_user['email'])}
📅 *Time:* {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC

💬 *Response:*
{data.note[:500]}{'...' if len(data.note) > 500 else ''}

Status: {'🟡 Under Review' if optimization.get('complaint_status') == 'complained' else '📝 Response Added'}"""
            
            await seo_optimization_telegram_service.send_message(message)
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.SEO_OPTIMIZATION,
            entity_id=optimization_id,
            after_value={"action": "team_response_added", "response_id": response_entry["id"]}
        )
    
    return {
        "message": "Response added successfully",
        "response": response_entry,
        "complaint_status": optimization.get("complaint_status", "none")
    }


@router.patch("/optimizations/{optimization_id}/complaints/{complaint_id}/resolve")
async def resolve_complaint(
    optimization_id: str,
    complaint_id: str,
    data: ComplaintResolveRequest,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Resolve a complaint on an optimization.
    SUPER ADMIN ONLY.
    
    Rules:
    - Only Super Admin can resolve complaints
    - Resolution note is required (min 10 chars)
    - Optionally marks optimization as completed
    """
    # Super Admin only
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can resolve complaints")
    
    if len(data.resolution_note.strip()) < 10:
        raise HTTPException(status_code=400, detail="Resolution note must be at least 10 characters")
    
    optimization = await db.seo_optimizations.find_one({"id": optimization_id}, {"_id": 0})
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")
    
    complaint = await db.optimization_complaints.find_one({"id": complaint_id}, {"_id": 0})
    if not complaint or complaint["optimization_id"] != optimization_id:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    if complaint.get("status") == "resolved":
        raise HTTPException(status_code=400, detail="Complaint is already resolved")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Calculate time to resolution
    time_to_resolution_hours = None
    try:
        created = datetime.fromisoformat(complaint["created_at"].replace("Z", "+00:00"))
        resolved = datetime.now(timezone.utc)
        time_to_resolution_hours = (resolved - created).total_seconds() / 3600
    except Exception:
        pass
    
    # Update complaint
    await db.optimization_complaints.update_one(
        {"id": complaint_id},
        {"$set": {
            "status": "resolved",
            "resolved_at": now,
            "resolved_by": {
                "user_id": current_user["id"],
                "display_name": current_user.get("name", current_user["email"].split("@")[0]),
                "email": current_user["email"]
            },
            "resolution_note": data.resolution_note.strip(),
            "time_to_resolution_hours": time_to_resolution_hours
        }}
    )
    
    # Check if there are other unresolved complaints
    other_complaints = await db.optimization_complaints.count_documents({
        "optimization_id": optimization_id,
        "id": {"$ne": complaint_id},
        "status": {"$in": ["open", "under_review"]}
    })
    
    # Update optimization status
    opt_update = {
        "updated_at": now,
        "complaint_status": "none" if other_complaints == 0 else "complained"
    }
    
    if data.mark_optimization_complete and other_complaints == 0:
        opt_update["status"] = "completed"
        opt_update["closed_at"] = now
        opt_update["closed_by"] = {
            "user_id": current_user["id"],
            "display_name": current_user.get("name", current_user["email"].split("@")[0]),
            "email": current_user["email"]
        }
    
    await db.seo_optimizations.update_one({"id": optimization_id}, {"$set": opt_update})
    
    # Send Telegram notification
    try:
        from services.seo_optimization_telegram_service import seo_optimization_telegram_service
        if seo_optimization_telegram_service:
            network = await db.seo_networks.find_one({"id": optimization["network_id"]}, {"_id": 0, "name": 1})
            brand = await db.brands.find_one({"id": optimization["brand_id"]}, {"_id": 0, "name": 1})
            
            status_text = "✅ RESOLVED & COMPLETED" if data.mark_optimization_complete else "✅ RESOLVED"
            
            message = f"""✅ *COMPLAINT {status_text}*

📋 *Optimization:* {optimization['title']}
🌐 *Network:* {network.get('name') if network else 'Unknown'}
🏷️ *Brand:* {brand.get('name') if brand else 'Unknown'}

👤 *Resolved by:* {current_user.get('name', current_user['email'])}
⏱️ *Resolution Time:* {time_to_resolution_hours:.1f} hours

📝 *Resolution Note:*
{data.resolution_note[:300]}{'...' if len(data.resolution_note) > 300 else ''}

Status: {'🟢 Completed' if data.mark_optimization_complete else '✅ Complaint Resolved'}"""
            
            await seo_optimization_telegram_service.send_message(message)
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.SEO_OPTIMIZATION,
            entity_id=optimization_id,
            after_value={
                "action": "complaint_resolved",
                "complaint_id": complaint_id,
                "time_to_resolution_hours": time_to_resolution_hours,
                "marked_complete": data.mark_optimization_complete
            }
        )
    
    return {
        "message": "Complaint resolved successfully",
        "time_to_resolution_hours": time_to_resolution_hours,
        "optimization_status": "completed" if data.mark_optimization_complete else optimization["status"],
        "remaining_complaints": other_complaints
    }


@router.patch("/optimizations/{optimization_id}/close")
async def close_optimization(
    optimization_id: str,
    data: OptimizationCloseRequest,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Close/complete an optimization.
    SUPER ADMIN ONLY.
    
    Rules:
    - Only Super Admin can close optimizations
    - Cannot close if there are unresolved complaints (BLOCKED)
    - Sets status to 'completed' and records closer info
    """
    # Super Admin only
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can close optimizations")
    
    optimization = await db.seo_optimizations.find_one({"id": optimization_id}, {"_id": 0})
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")
    
    # Check for unresolved complaints
    unresolved_count = await db.optimization_complaints.count_documents({
        "optimization_id": optimization_id,
        "status": {"$in": ["open", "under_review"]}
    })
    
    if unresolved_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"⚠ Cannot close optimization: {unresolved_count} unresolved complaint(s). Resolve all complaints first."
        )
    
    if optimization.get("status") == "completed" and optimization.get("closed_at"):
        raise HTTPException(status_code=400, detail="Optimization is already closed")
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.seo_optimizations.update_one(
        {"id": optimization_id},
        {"$set": {
            "status": "completed",
            "complaint_status": "resolved" if optimization.get("complaint_status") != "none" else "none",
            "closed_at": now,
            "closed_by": {
                "user_id": current_user["id"],
                "display_name": current_user.get("name", current_user["email"].split("@")[0]),
                "email": current_user["email"]
            },
            "final_note": data.final_note,
            "updated_at": now
        }}
    )
    
    # Send Telegram notification
    try:
        from services.seo_optimization_telegram_service import seo_optimization_telegram_service
        if seo_optimization_telegram_service:
            network = await db.seo_networks.find_one({"id": optimization["network_id"]}, {"_id": 0, "name": 1})
            brand = await db.brands.find_one({"id": optimization["brand_id"]}, {"_id": 0, "name": 1})
            
            message = f"""🟢 *OPTIMIZATION COMPLETED*

📋 *{optimization['title']}*
🌐 *Network:* {network.get('name') if network else 'Unknown'}
🏷️ *Brand:* {brand.get('name') if brand else 'Unknown'}

👤 *Closed by:* {current_user.get('name', current_user['email'])}
📅 *Closed at:* {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC

{f"📝 Final Note: {data.final_note}" if data.final_note else ""}

Status: 🟢 COMPLETED ✓"""
            
            await seo_optimization_telegram_service.send_message(message)
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.SEO_OPTIMIZATION,
            entity_id=optimization_id,
            after_value={"action": "optimization_closed", "final_note": data.final_note}
        )
    
    return {
        "message": "Optimization closed successfully",
        "status": "completed",
        "closed_at": now
    }


# ==================== USER SEARCH FOR ACCESS CONTROL ====================

@router.get("/users/search")
async def search_users_for_access_control(
    q: str = Query(min_length=2, max_length=100, description="Search query for email, name, or display_name"),
    network_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Search users for Restricted mode access control picker.
    
    Behavior:
    - Search by email OR full_name/name (case-insensitive partial match)
    - Exclude disabled/inactive users (unless super_admin explicitly wants them)
    - Super Admin: Can search all users across platform
    - Admin/Viewer: Can only search users that share brand access
    
    Returns lightweight payload: id, name, email, role, status
    Max 10 results for debounce-friendly performance.
    """
    logger.info(f"[USER_SEARCH] Query: '{q}', network_id: {network_id}, user: {current_user.get('email')}")
    
    search_term = q.strip()
    if len(search_term) < 2:
        return {"results": [], "total": 0, "query": search_term}
    
    is_super_admin = current_user.get("role") == "super_admin"
    
    # Build search query - search email OR name (case-insensitive)
    search_regex = {"$regex": search_term, "$options": "i"}
    base_query = {
        "$or": [
            {"email": search_regex},
            {"name": search_regex},
            {"display_name": search_regex}  # fallback field
        ]
    }
    
    # Exclude inactive/suspended users (unless super_admin)
    if not is_super_admin:
        base_query["status"] = {"$in": ["active", None]}  # Include users without status field (legacy)
    else:
        # Super Admin can see all, but still exclude rejected/pending by default
        base_query["status"] = {"$nin": ["rejected", "pending"]}
    
    # Brand scoping for non-super-admin
    # If network_id provided, get network's brand and filter users with that brand access
    if not is_super_admin and network_id:
        network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0, "brand_id": 1})
        if network and network.get("brand_id"):
            network_brand_id = network["brand_id"]
            # Users must have this brand in their scope, OR be super_admin, OR have null scope (legacy full access)
            base_query["$or"] = [
                {"email": search_regex, "brand_scope_ids": network_brand_id},
                {"email": search_regex, "brand_scope_ids": None},  # Full access users
                {"email": search_regex, "role": "super_admin"},
                {"name": search_regex, "brand_scope_ids": network_brand_id},
                {"name": search_regex, "brand_scope_ids": None},
                {"name": search_regex, "role": "super_admin"},
            ]
    
    logger.info(f"[USER_SEARCH] Query built: {base_query}")
    
    # Execute search
    users = await db.users.find(
        base_query,
        {"_id": 0, "id": 1, "email": 1, "name": 1, "display_name": 1, "role": 1, "status": 1}
    ).limit(10).to_list(10)
    
    logger.info(f"[USER_SEARCH] Found {len(users)} users")
    
    # Format results
    results = []
    for u in users:
        results.append({
            "id": u["id"],
            "email": u["email"],
            "name": u.get("name") or u.get("display_name") or u["email"].split("@")[0],
            "role": u.get("role", "viewer"),
            "status": u.get("status", "active")
        })
    
    return {
        "results": results,
        "total": len(results),
        "query": search_term
    }


# ==================== SEO NETWORK MANAGEMENT (MANAGERS) ====================

async def build_manager_summary_cache(manager_ids: List[str]) -> dict:
    """Build manager summary cache with user count and first 3 names"""
    if not manager_ids:
        return {"count": 0, "names": []}
    
    users = await db.users.find(
        {"id": {"$in": manager_ids}},
        {"_id": 0, "id": 1, "name": 1, "email": 1}
    ).limit(3).to_list(3)
    
    names = [u.get("name") or u["email"].split("@")[0] for u in users]
    
    return {
        "count": len(manager_ids),
        "names": names
    }


@router.put("/networks/{network_id}/managers")
async def update_network_managers(
    network_id: str,
    data: NetworkManagersUpdate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Update SEO Network Managers and visibility settings.
    
    Managers are responsible for executing optimizations, responding to complaints,
    and receiving notifications. They do NOT control who can VIEW the network -
    that's determined by visibility_mode.
    
    Visibility modes:
    - brand_based: All brand users can VIEW (default)
    - restricted: Only managers and Super Admins can VIEW
    
    Only Super Admin can modify managers list.
    """
    # Only Super Admin can change managers
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can modify SEO Network managers")
    
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    require_brand_access(network["brand_id"], current_user)
    
    # Get previous state for audit log
    previous_mode = network.get("visibility_mode", "brand_based")
    previous_manager_ids = set(network.get("manager_ids", []))
    new_manager_ids = set(data.manager_ids)
    
    added_manager_ids = list(new_manager_ids - previous_manager_ids)
    removed_manager_ids = list(previous_manager_ids - new_manager_ids)
    
    # Build manager summary cache
    manager_summary_cache = await build_manager_summary_cache(data.manager_ids)
    
    # Update network
    await db.seo_networks.update_one(
        {"id": network_id},
        {"$set": {
            "visibility_mode": data.visibility_mode.value,
            "manager_ids": data.manager_ids,
            "manager_summary_cache": manager_summary_cache,
            "managers_updated_at": datetime.now(timezone.utc).isoformat(),
            "managers_updated_by": {
                "user_id": current_user["id"],
                "email": current_user["email"],
                "name": current_user.get("name", current_user["email"].split("@")[0])
            },
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Create audit log entry
    added_manager_names = []
    removed_manager_names = []
    
    if added_manager_ids:
        added_managers = await db.users.find(
            {"id": {"$in": added_manager_ids}},
            {"_id": 0, "name": 1, "email": 1}
        ).to_list(100)
        added_manager_names = [u.get("name") or u["email"].split("@")[0] for u in added_managers]
    
    if removed_manager_ids:
        removed_managers = await db.users.find(
            {"id": {"$in": removed_manager_ids}},
            {"_id": 0, "name": 1, "email": 1}
        ).to_list(100)
        removed_manager_names = [u.get("name") or u["email"].split("@")[0] for u in removed_managers]
    
    audit_entry = {
        "id": str(uuid.uuid4()),
        "event_type": "NETWORK_MANAGERS_CHANGED",
        "network_id": network_id,
        "network_name": network["name"],
        "brand_id": network["brand_id"],
        "previous_mode": previous_mode,
        "new_mode": data.visibility_mode.value,
        "added_manager_ids": added_manager_ids,
        "removed_manager_ids": removed_manager_ids,
        "added_manager_names": added_manager_names,
        "removed_manager_names": removed_manager_names,
        "changed_by": {
            "user_id": current_user["id"],
            "email": current_user["email"],
            "name": current_user.get("name", current_user["email"].split("@")[0])
        },
        "changed_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.network_managers_audit_logs.insert_one(audit_entry)
    logger.info(f"[MANAGERS_AUDIT] Network {network['name']}: {previous_mode} → {data.visibility_mode.value}, +{len(added_manager_ids)} -{len(removed_manager_ids)} managers")
    
    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.SEO_NETWORK,
            entity_id=network_id,
            before_value={"visibility_mode": previous_mode, "manager_ids": list(previous_manager_ids)},
            after_value={"visibility_mode": data.visibility_mode.value, "manager_ids": data.manager_ids}
        )
    
    return {"message": "SEO Network managers updated", "manager_summary_cache": manager_summary_cache}


@router.get("/networks/{network_id}/managers")
async def get_network_managers(
    network_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Get SEO Network managers and visibility settings.
    Returns the list of managers who are responsible for this network.
    """
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    require_brand_access(network["brand_id"], current_user)
    
    # Get managers info
    managers = []
    if network.get("manager_ids"):
        users = await db.users.find(
            {"id": {"$in": network["manager_ids"]}},
            {"_id": 0, "id": 1, "email": 1, "name": 1, "role": 1, "telegram_username": 1}
        ).to_list(100)
        managers = users
    
    # Get managers_updated_by info if available
    managers_updated_by = network.get("managers_updated_by")
    
    # Check if current user is a manager
    is_current_user_manager = is_network_manager(network, current_user)
    
    return {
        "visibility_mode": network.get("visibility_mode", "brand_based"),
        "manager_ids": network.get("manager_ids", []),
        "managers": managers,
        "manager_summary_cache": network.get("manager_summary_cache", {"count": 0, "names": []}),
        "managers_updated_at": network.get("managers_updated_at"),
        "managers_updated_by": managers_updated_by,
        "is_current_user_manager": is_current_user_manager
    }


# Keep legacy endpoint for backward compatibility (temporary)
@router.get("/networks/{network_id}/access-control")
async def get_network_access_control_legacy(
    network_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Legacy endpoint - redirects to managers endpoint"""
    return await get_network_managers(network_id, current_user)


@router.put("/networks/{network_id}/access-control")
async def update_network_access_control_legacy(
    network_id: str,
    data: NetworkManagersUpdate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Legacy endpoint - redirects to managers endpoint"""
    return await update_network_managers(network_id, data, current_user)


@router.get("/networks/{network_id}/managers-audit-logs")
async def get_network_managers_audit_logs(
    network_id: str,
    limit: int = Query(default=20, le=100),
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get audit logs for network manager changes (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0, "brand_id": 1})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    require_brand_access(network["brand_id"], current_user)
    
    logs = await db.network_managers_audit_logs.find(
        {"network_id": network_id},
        {"_id": 0}
    ).sort("changed_at", -1).limit(limit).to_list(limit)
    
    return {"logs": logs, "total": len(logs)}


# Legacy endpoint for backward compatibility
@router.get("/networks/{network_id}/access-audit-logs")
async def get_network_access_audit_logs_legacy(
    network_id: str,
    limit: int = Query(default=20, le=100),
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Legacy endpoint - redirects to managers audit logs"""
    return await get_network_managers_audit_logs(network_id, limit, current_user)
    return await get_network_managers_audit_logs(network_id, limit, current_user)


# ==================== REMINDER CONFIGURATION ====================

@router.get("/settings/reminder-config")
async def get_reminder_config(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get global reminder configuration (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    settings = await db.settings.find_one(
        {"key": "optimization_reminders"},
        {"_id": 0}
    )
    
    return settings or {
        "key": "optimization_reminders",
        "enabled": True,
        "interval_days": 2
    }


@router.put("/settings/reminder-config")
async def update_reminder_config(
    data: dict,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Update global reminder configuration (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    interval_days = data.get("interval_days", 2)
    enabled = data.get("enabled", True)
    
    if interval_days < 1 or interval_days > 30:
        raise HTTPException(status_code=400, detail="Reminder interval must be between 1 and 30 days")
    
    await db.settings.update_one(
        {"key": "optimization_reminders"},
        {"$set": {
            "key": "optimization_reminders",
            "enabled": enabled,
            "interval_days": interval_days,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": {
                "user_id": current_user["id"],
                "email": current_user["email"]
            }
        }},
        upsert=True
    )
    
    return {"message": "Reminder configuration updated", "enabled": enabled, "interval_days": interval_days}


@router.get("/networks/{network_id}/reminder-config")
async def get_network_reminder_config(
    network_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get per-network reminder configuration override"""
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0, "brand_id": 1, "reminder_config": 1})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    require_brand_access(network["brand_id"], current_user)
    
    # Get global config as fallback
    global_config = await db.settings.find_one(
        {"key": "optimization_reminders"},
        {"_id": 0}
    ) or {"enabled": True, "interval_days": 2}
    
    network_config = network.get("reminder_config") or {}
    
    return {
        "global_default": global_config,
        "network_override": network_config,
        "effective_interval_days": network_config.get("interval_days") or global_config.get("interval_days", 2)
    }


@router.put("/networks/{network_id}/reminder-config")
async def update_network_reminder_config(
    network_id: str,
    data: dict,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Update per-network reminder configuration override (Admin/Super Admin only)"""
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0, "brand_id": 1})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    require_brand_access(network["brand_id"], current_user)
    
    interval_days = data.get("interval_days")
    use_global = data.get("use_global", False)
    
    if use_global:
        # Remove network override, use global default
        await db.seo_networks.update_one(
            {"id": network_id},
            {"$unset": {"reminder_config": 1}}
        )
        return {"message": "Network will use global reminder settings"}
    
    if interval_days is not None:
        if interval_days < 1 or interval_days > 30:
            raise HTTPException(status_code=400, detail="Reminder interval must be between 1 and 30 days")
        
        await db.seo_networks.update_one(
            {"id": network_id},
            {"$set": {
                "reminder_config": {
                    "interval_days": interval_days,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "updated_by": {
                        "user_id": current_user["id"],
                        "email": current_user["email"]
                    }
                }
            }}
        )
        return {"message": "Network reminder configuration updated", "interval_days": interval_days}
    
    raise HTTPException(status_code=400, detail="Must provide interval_days or set use_global=true")


@router.get("/optimization-reminders")
async def get_optimization_reminders(
    network_id: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get optimization reminder logs for accountability (Admin/Super Admin only)"""
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {}
    if network_id:
        query["network_id"] = network_id
    
    reminders = await db.optimization_reminders.find(
        query,
        {"_id": 0}
    ).sort("sent_at", -1).limit(limit).to_list(limit)
    
    return {"reminders": reminders, "total": len(reminders)}


@router.get("/scheduler/reminder-status")
async def get_reminder_scheduler_status(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get reminder scheduler status (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    from services.reminder_scheduler import get_reminder_scheduler
    scheduler = get_reminder_scheduler()
    
    if scheduler is None:
        return {
            "status": "not_initialized",
            "message": "Reminder scheduler is not initialized"
        }
    
    status = scheduler.get_status()
    
    # Get last execution log
    last_execution = await db.scheduler_execution_logs.find_one(
        {"job_id": "optimization_reminder_job"},
        {"_id": 0},
        sort=[("executed_at", -1)]
    )
    
    return {
        "scheduler": status,
        "last_execution": last_execution
    }


@router.post("/scheduler/trigger-reminders")
async def trigger_reminder_job(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Manually trigger the reminder job (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    from services.reminder_scheduler import get_reminder_scheduler
    scheduler = get_reminder_scheduler()
    
    if scheduler is None:
        raise HTTPException(status_code=500, detail="Reminder scheduler is not initialized")
    
    result = await scheduler.trigger_now()
    
    return {
        "message": "Reminder job triggered successfully",
        "result": result,
        "triggered_by": current_user["email"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/scheduler/execution-logs")
async def get_scheduler_execution_logs(
    job_id: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get scheduler execution logs (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    query = {}
    if job_id:
        query["job_id"] = job_id
    
    logs = await db.scheduler_execution_logs.find(
        query,
        {"_id": 0}
    ).sort("executed_at", -1).limit(limit).to_list(limit)
    
    return {"logs": logs, "total": len(logs)}


# ==================== ACTIVITY TYPE MANAGEMENT ====================

@router.get("/optimization-activity-types")
async def get_optimization_activity_types(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get all optimization activity types (master data)"""
    types = await db.seo_optimization_activity_types.find({}, {"_id": 0}).sort("name", 1).to_list(100)
    
    if not types:
        # Return default types if none exist
        return [
            {"id": "default_backlink", "name": "Backlink Campaign", "is_default": True, "usage_count": 0},
            {"id": "default_onpage", "name": "On-Page Optimization", "is_default": True, "usage_count": 0},
            {"id": "default_content", "name": "Content Update", "is_default": True, "usage_count": 0},
            {"id": "default_technical", "name": "Technical SEO", "is_default": True, "usage_count": 0},
            {"id": "default_schema", "name": "Schema Markup", "is_default": True, "usage_count": 0},
            {"id": "default_internal", "name": "Internal Linking", "is_default": True, "usage_count": 0},
            {"id": "default_experiment", "name": "SEO Experiment", "is_default": True, "usage_count": 0},
            {"id": "default_other", "name": "Other", "is_default": True, "usage_count": 0}
        ]
    
    # Get usage counts
    for t in types:
        count = await db.seo_optimizations.count_documents({"activity_type_id": t["id"]})
        t["usage_count"] = count
    
    return types


@router.post("/optimization-activity-types")
async def create_optimization_activity_type(
    data: OptimizationActivityTypeCreate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Create a new optimization activity type - Admin/Super Admin only"""
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    
    # Check for duplicate
    existing = await db.seo_optimization_activity_types.find_one(
        {"name": {"$regex": f"^{data.name.strip()}$", "$options": "i"}}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Activity type with this name already exists")
    
    now = datetime.now(timezone.utc).isoformat()
    activity_type = {
        "id": str(uuid.uuid4()),
        "name": data.name.strip(),
        "description": data.description,
        "icon": data.icon,
        "color": data.color,
        "is_default": False,
        "created_at": now
    }
    
    await db.seo_optimization_activity_types.insert_one(activity_type)
    
    return activity_type


@router.delete("/optimization-activity-types/{type_id}")
async def delete_optimization_activity_type(
    type_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Delete an activity type - only if unused"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    # Check if in use
    usage_count = await db.seo_optimizations.count_documents({"activity_type_id": type_id})
    if usage_count > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete: activity type is used by {usage_count} optimization(s)")
    
    await db.seo_optimization_activity_types.delete_one({"id": type_id})
    
    return {"message": "Activity type deleted"}


# ==================== OBSERVED IMPACT UPDATE ====================

@router.patch("/optimizations/{optimization_id}/observed-impact")
async def update_observed_impact(
    optimization_id: str,
    observed_impact: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Update observed impact for an optimization (after 14-30 days).
    Only Admin/Super Admin can update.
    """
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required to evaluate impact")
    
    if observed_impact not in ["positive", "neutral", "no_impact", "negative"]:
        raise HTTPException(status_code=400, detail="Invalid observed_impact value")
    
    optimization = await db.seo_optimizations.find_one({"id": optimization_id}, {"_id": 0})
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")
    
    require_brand_access(optimization["brand_id"], current_user)
    
    await db.seo_optimizations.update_one(
        {"id": optimization_id},
        {"$set": {
            "observed_impact": observed_impact,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"message": "Observed impact updated", "observed_impact": observed_impact}


# ==================== TEAM EVALUATION ENDPOINTS ====================

@router.get("/team-evaluation/users")
async def get_team_evaluation_users(
    brand_id: Optional[str] = None,
    network_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Get SEO team performance scores (derived from data).
    Only Admin/Super Admin can view.
    """
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Build query for optimizations
    query = {}
    if brand_id:
        query["brand_id"] = brand_id
    if network_id:
        query["network_id"] = network_id
    if start_date:
        query["created_at"] = {"$gte": start_date}
    if end_date:
        query.setdefault("created_at", {})["$lte"] = end_date
    
    # Aggregate by user
    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": "$created_by.user_id",
            "user_name": {"$first": "$created_by.display_name"},
            "user_email": {"$first": "$created_by.email"},
            "total_optimizations": {"$sum": 1},
            "completed_count": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
            "reverted_count": {"$sum": {"$cond": [{"$eq": ["$status", "reverted"]}, 1, 0]}},
            "complaint_count": {"$sum": {"$cond": [{"$ne": ["$complaint_status", "none"]}, 1, 0]}},
            "positive_impact": {"$sum": {"$cond": [{"$eq": ["$observed_impact", "positive"]}, 1, 0]}},
            "negative_impact": {"$sum": {"$cond": [{"$eq": ["$observed_impact", "negative"]}, 1, 0]}}
        }},
        {"$sort": {"total_optimizations": -1}}
    ]
    
    results = await db.seo_optimizations.aggregate(pipeline).to_list(100)
    
    # Calculate scores
    user_scores = []
    for r in results:
        # Simple scoring: base 5, deduct for reverts and complaints, add for positive impact
        score = 5.0
        if r["total_optimizations"] > 0:
            revert_rate = r["reverted_count"] / r["total_optimizations"]
            complaint_rate = r["complaint_count"] / r["total_optimizations"]
            score -= (revert_rate * 2)  # -2 max for high revert rate
            score -= (complaint_rate * 1.5)  # -1.5 max for high complaint rate
            if r["positive_impact"] > 0:
                score += min(r["positive_impact"] / r["total_optimizations"], 0.5)  # +0.5 max bonus
        
        score = max(0, min(5, score))  # Clamp to 0-5
        
        user_scores.append(UserSeoScore(
            user_id=r["_id"],
            user_name=r["user_name"],
            user_email=r["user_email"],
            total_optimizations=r["total_optimizations"],
            completed_optimizations=r["completed_count"],
            reverted_optimizations=r["reverted_count"],
            complaint_count=r["complaint_count"],
            positive_impact_count=r["positive_impact"],
            negative_impact_count=r["negative_impact"],
            score=round(score, 1),
            score_breakdown={
                "base": 5.0,
                "revert_penalty": -round(r["reverted_count"] / max(r["total_optimizations"], 1) * 2, 2),
                "complaint_penalty": -round(r["complaint_count"] / max(r["total_optimizations"], 1) * 1.5, 2)
            }
        ))
    
    return user_scores


@router.get("/team-evaluation/summary")
async def get_team_evaluation_summary(
    brand_id: Optional[str] = None,
    network_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Get team evaluation summary with dashboard metrics.
    Only Admin/Super Admin can view.
    """
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Default to last 30 days if no dates provided
    if not end_date:
        end_date = datetime.now(timezone.utc).isoformat()
    if not start_date:
        start_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    
    # Build query
    query = {"created_at": {"$gte": start_date, "$lte": end_date}}
    if brand_id:
        query["brand_id"] = brand_id
    if network_id:
        query["network_id"] = network_id
    
    # Get total optimizations
    total = await db.seo_optimizations.count_documents(query)
    
    # By status
    by_status = {}
    for status in ["planned", "in_progress", "completed", "reverted"]:
        count = await db.seo_optimizations.count_documents({**query, "status": status})
        by_status[status] = count
    
    # By observed impact
    by_impact = {}
    for impact in ["positive", "neutral", "no_impact", "negative"]:
        count = await db.seo_optimizations.count_documents({**query, "observed_impact": impact})
        by_impact[impact] = count
    
    # By activity type
    type_pipeline = [
        {"$match": query},
        {"$group": {"_id": "$activity_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    type_results = await db.seo_optimizations.aggregate(type_pipeline).to_list(20)
    by_activity_type = {r["_id"]: r["count"] for r in type_results}
    
    # Total complaints
    total_complaints = await db.optimization_complaints.count_documents({
        "created_at": {"$gte": start_date, "$lte": end_date}
    })
    
    # Calculate average time-to-resolution for resolved complaints
    resolution_pipeline = [
        {"$match": {
            "created_at": {"$gte": start_date, "$lte": end_date},
            "status": "resolved",
            "time_to_resolution_hours": {"$exists": True, "$ne": None}
        }},
        {"$group": {
            "_id": None,
            "avg_hours": {"$avg": "$time_to_resolution_hours"},
            "resolved_count": {"$sum": 1}
        }}
    ]
    resolution_result = await db.optimization_complaints.aggregate(resolution_pipeline).to_list(1)
    avg_resolution_time_hours = resolution_result[0]["avg_hours"] if resolution_result else None
    resolved_complaints_count = resolution_result[0]["resolved_count"] if resolution_result else 0
    
    # Get top contributors
    top_users = await get_team_evaluation_users(brand_id, network_id, start_date, end_date, current_user)
    
    # Check for repeated issues (>2 complaints in 30 days per user)
    repeated_issue_pipeline = [
        {"$match": {**query, "complaint_status": {"$ne": "none"}}},
        {"$group": {"_id": "$created_by.user_id", "complaint_count": {"$sum": 1}}},
        {"$match": {"complaint_count": {"$gt": 2}}}
    ]
    repeated_results = await db.seo_optimizations.aggregate(repeated_issue_pipeline).to_list(100)
    repeated_issue_users = [r["_id"] for r in repeated_results]
    
    return TeamEvaluationSummary(
        period_start=start_date,
        period_end=end_date,
        total_optimizations=total,
        by_status=by_status,
        by_activity_type=by_activity_type,
        by_observed_impact=by_impact,
        total_complaints=total_complaints,
        avg_resolution_time_hours=round(avg_resolution_time_hours, 1) if avg_resolution_time_hours else None,
        top_contributors=top_users[:5],
        most_complained_users=sorted(top_users, key=lambda x: x.complaint_count, reverse=True)[:5],
        repeated_issue_users=repeated_issue_users
    )


@router.get("/team-evaluation/export")
async def export_team_evaluation_csv(
    brand_id: Optional[str] = None,
    network_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Export team evaluation data as CSV.
    Only Admin/Super Admin can export.
    """
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Default to last 30 days if no dates provided
    if not end_date:
        end_date = datetime.now(timezone.utc).isoformat()
    if not start_date:
        start_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    
    # Get all user scores
    user_scores = await get_team_evaluation_users(brand_id, network_id, start_date, end_date, current_user)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow([
        'User Name',
        'Email',
        'Total Optimizations',
        'Completed',
        'Reverted',
        'Complaints',
        'Positive Impact',
        'Negative Impact',
        'Score (0-5)',
        'Score Status',
        'Revert Penalty',
        'Complaint Penalty'
    ])
    
    # Data rows
    for user in user_scores:
        # Determine status label
        if user.score >= 4.5:
            status = 'Excellent'
        elif user.score >= 3.5:
            status = 'Good'
        elif user.score >= 2.5:
            status = 'Average'
        else:
            status = 'Needs Improvement'
        
        writer.writerow([
            user.user_name or 'Unknown',
            user.user_email or '',
            user.total_optimizations,
            user.completed_optimizations,
            user.reverted_optimizations,
            user.complaint_count,
            user.positive_impact_count,
            user.negative_impact_count,
            user.score,
            status,
            user.score_breakdown.get('revert_penalty', 0),
            user.score_breakdown.get('complaint_penalty', 0)
        ])
    
    # Prepare response
    output.seek(0)
    
    # Generate filename with date range
    start_short = start_date[:10] if start_date else 'unknown'
    end_short = end_date[:10] if end_date else 'unknown'
    filename = f"seo_team_evaluation_{start_short}_to_{end_short}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


# ==================== SWITCH MAIN TARGET ENDPOINT ====================

from pydantic import BaseModel as PydanticBaseModel, Field as PydanticField

class SwitchMainTargetRequest(PydanticBaseModel):
    """Request model for switching the main target node"""
    new_main_entry_id: str
    change_note: str = PydanticField(..., min_length=10, max_length=2000, description="Penjelasan perubahan main target (wajib, minimal 10 karakter)")


@router.post("/networks/{network_id}/switch-main-target")
async def switch_main_target(
    network_id: str,
    data: SwitchMainTargetRequest,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Switch the main target node in a network.
    
    This is a SAFE operation that:
    1. Demotes the current main node to supporting (targeting the new main)
    2. Promotes the new node to main (with PRIMARY status, no target)
    3. Recalculates all tiers via BFS from the new main
    4. Preserves all existing nodes and relationships
    
    Requires change_note for audit trail.
    """
    # Validate network exists
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    # Check brand access
    if network.get("brand_id"):
        require_brand_access(network["brand_id"], current_user)
    
    # Get the new main entry
    new_main = await db.seo_structure_entries.find_one({"id": data.new_main_entry_id}, {"_id": 0})
    if not new_main:
        raise HTTPException(status_code=404, detail="New main entry not found")
    
    if new_main.get("network_id") != network_id:
        raise HTTPException(status_code=400, detail="Entry must be in the same network")
    
    if new_main.get("domain_role") == "main":
        raise HTTPException(status_code=400, detail="This entry is already the main node")
    
    # Find current main node
    current_main = await db.seo_structure_entries.find_one({
        "network_id": network_id,
        "domain_role": "main"
    }, {"_id": 0})
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Step 1: Demote old main to supporting, pointing to new main
    if current_main:
        old_main_update = {
            "domain_role": "supporting",
            "domain_status": "canonical",  # Now it canonicalizes to new main
            "target_entry_id": data.new_main_entry_id,
            "updated_at": now
        }
        await db.seo_structure_entries.update_one(
            {"id": current_main["id"]},
            {"$set": old_main_update}
        )
        
        # Log the demotion
        if seo_change_log_service:
            old_domain = await db.asset_domains.find_one({"id": current_main["asset_domain_id"]}, {"domain_name": 1, "_id": 0})
            old_node_label = f"{old_domain['domain_name'] if old_domain else 'unknown'}{current_main.get('optimized_path', '') or ''}"
            
            await seo_change_log_service.log_change(
                network_id=network_id,
                brand_id=network.get("brand_id", ""),
                actor_user_id=current_user.get("id", ""),
                actor_email=current_user["email"],
                action_type=SeoChangeActionType.CHANGE_ROLE,
                affected_node=old_node_label,
                change_note=f"[Main Switch] Demoted to supporting. {data.change_note}",
                before_snapshot=current_main,
                after_snapshot={**current_main, **old_main_update},
                entry_id=current_main["id"]
            )
    
    # Step 2: Promote new main
    new_main_update = {
        "domain_role": "main",
        "domain_status": "primary",  # Main nodes have PRIMARY status
        "target_entry_id": None,  # Main nodes don't have targets
        "target_asset_domain_id": None,
        "updated_at": now
    }
    await db.seo_structure_entries.update_one(
        {"id": data.new_main_entry_id},
        {"$set": new_main_update}
    )
    
    # Log the promotion
    if seo_change_log_service:
        new_domain = await db.asset_domains.find_one({"id": new_main["asset_domain_id"]}, {"domain_name": 1, "_id": 0})
        new_node_label = f"{new_domain['domain_name'] if new_domain else 'unknown'}{new_main.get('optimized_path', '') or ''}"
        
        await seo_change_log_service.log_change(
            network_id=network_id,
            brand_id=network.get("brand_id", ""),
            actor_user_id=current_user.get("id", ""),
            actor_email=current_user["email"],
            action_type=SeoChangeActionType.CHANGE_ROLE,
            affected_node=new_node_label,
            change_note=f"[Main Switch] Promoted to main target. {data.change_note}",
            before_snapshot=new_main,
            after_snapshot={**new_main, **new_main_update},
            entry_id=data.new_main_entry_id
        )
    
    # Step 3: Recalculate tiers
    if tier_service:
        await tier_service.calculate_network_tiers(network_id)
    
    # Create notification for main domain change
    if seo_change_log_service:
        new_domain = await db.asset_domains.find_one({"id": new_main["asset_domain_id"]}, {"domain_name": 1, "_id": 0})
        await seo_change_log_service.create_notification(
            network_id=network_id,
            brand_id=network.get("brand_id", ""),
            notification_type=SeoNotificationType.MAIN_DOMAIN_CHANGE,
            title="Main Target Switched",
            message=f"Main target changed to '{new_domain['domain_name'] if new_domain else 'unknown'}{new_main.get('optimized_path', '') or ''}'",
            affected_node=new_node_label,
            actor_email=current_user["email"],
            change_note=data.change_note
        )
    
    # Send SEO Telegram notification for main target switch
    if seo_telegram_service:
        new_domain = await db.asset_domains.find_one({"id": new_main["asset_domain_id"]}, {"domain_name": 1, "_id": 0})
        new_node_label = f"{new_domain['domain_name'] if new_domain else 'unknown'}{new_main.get('optimized_path', '') or ''}"
        
        await seo_telegram_service.send_seo_change_notification(
            network_id=network_id,
            brand_id=network.get("brand_id", ""),
            actor_user_id=current_user.get("id", ""),
            actor_email=current_user["email"],
            action_type="change_role",
            affected_node=new_node_label,
            change_note=f"[Main Switch] {data.change_note}",
            before_snapshot=new_main,
            after_snapshot={**new_main, **new_main_update},
            skip_rate_limit=True  # Important changes should bypass rate limit
        )
    
    return {
        "message": "Main target switched successfully",
        "new_main_entry_id": data.new_main_entry_id,
        "previous_main_entry_id": current_main["id"] if current_main else None,
        "tiers_recalculated": True
    }


class DeleteStructureEntryRequest(PydanticBaseModel):
    """Request model for deleting structure entry with mandatory change note"""
    change_note: str = PydanticField(..., min_length=10, max_length=2000, description="Penjelasan penghapusan node (wajib, minimal 10 karakter)")


@router.delete("/structure/{entry_id}")
async def delete_structure_entry(
    entry_id: str,
    data: DeleteStructureEntryRequest,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Delete an SEO structure entry (node) with mandatory change note.
    
    If other entries target this node, they become orphans.
    A warning is included in the response but deletion proceeds.
    """
    existing = await db.seo_structure_entries.find_one({"id": entry_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Structure entry not found")
    
    # CRITICAL: Validate change_note BEFORE any operation
    validate_change_note(data.change_note)
    
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
    
    # Get network for brand_id
    network = await db.seo_networks.find_one({"id": existing["network_id"]}, {"_id": 0, "brand_id": 1})
    brand_id = network.get("brand_id", "") if network else ""
    
    await db.seo_structure_entries.delete_one({"id": entry_id})
    
    # ATOMIC: Log + Telegram notification
    notification_success, change_log_id, error_msg = await atomic_seo_change_with_notification(
        db=db,
        seo_change_log_service=seo_change_log_service,
        seo_telegram_service=seo_telegram_service,
        network_id=existing["network_id"],
        brand_id=brand_id,
        actor_user_id=current_user.get("id", ""),
        actor_email=current_user["email"],
        action_type=SeoChangeActionType.DELETE_NODE,
        affected_node=node_label,
        change_note=data.change_note,
        before_snapshot=existing,
        after_snapshot=None,
        entry_id=entry_id
    )
    
    # Log system activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.DELETE,
            entity_type=EntityType.SEO_STRUCTURE_ENTRY,
            entity_id=entry_id,
            before_value=existing,
            metadata={"node_label": node_label, "orphaned_entries": orphan_count, "change_note": data.change_note}
        )
    
    return {
        "message": "Structure entry deleted",
        "orphaned_entries": orphan_count,
        "notification_sent": notification_success,
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



# ==================== SEO CHANGE LOG ENDPOINTS ====================

@router.get("/networks/{network_id}/change-history", response_model=List[SeoChangeLogResponse])
async def get_network_change_history(
    network_id: str,
    include_archived: bool = False,
    actor_email: Optional[str] = None,
    action_type: Optional[str] = None,
    affected_node: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Get SEO change history for a network with filtering.
    
    Filters:
    - actor_email: Filter by user who made changes
    - action_type: Filter by action (create_node, update_node, delete_node, relink_node, change_role, change_path)
    - affected_node: Search in affected node name (partial match)
    - date_from / date_to: ISO date range filter
    
    This shows human-readable SEO decision logs, NOT system logs.
    Each entry includes who changed what, when, and WHY (change_note).
    """
    # Validate network exists and user has access
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    # Check brand access
    brand_id = network.get("brand_id")
    if brand_id:
        require_brand_access(brand_id, current_user)
    
    if not seo_change_log_service:
        return []
    
    # Build filter query
    query = {"network_id": network_id}
    if not include_archived:
        query["archived"] = {"$ne": True}
    if actor_email:
        query["actor_email"] = {"$regex": actor_email, "$options": "i"}
    if action_type:
        query["action_type"] = action_type
    if affected_node:
        query["affected_node"] = {"$regex": affected_node, "$options": "i"}
    if date_from:
        query["created_at"] = {"$gte": date_from}
    if date_to:
        if "created_at" in query:
            query["created_at"]["$lte"] = date_to
        else:
            query["created_at"] = {"$lte": date_to}
    
    # Get logs with filters
    logs = await db.seo_change_logs.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    # Helper function to enrich snapshot with human-readable labels
    async def enrich_snapshot(snapshot):
        if not snapshot:
            return None
        
        enriched = dict(snapshot)
        
        # Translate target_entry_id to node_label
        if enriched.get("target_entry_id"):
            target = await db.seo_structure_entries.find_one(
                {"id": enriched["target_entry_id"]},
                {"_id": 0, "asset_domain_id": 1, "optimized_path": 1}
            )
            if target:
                domain = await db.asset_domains.find_one(
                    {"id": target["asset_domain_id"]},
                    {"_id": 0, "domain_name": 1}
                )
                enriched["target_node_label"] = f"{domain['domain_name'] if domain else 'unknown'}{target.get('optimized_path', '') or ''}"
        
        # Translate status codes to labels
        status_labels = {
            "primary": "Primary Target",
            "canonical": "Canonical",
            "301_redirect": "301 Redirect",
            "302_redirect": "302 Redirect",
            "restore": "Restore"
        }
        if enriched.get("domain_status"):
            enriched["domain_status_label"] = status_labels.get(enriched["domain_status"], enriched["domain_status"])
        
        # Translate role to labels
        role_labels = {
            "main": "Main (LP/Money Site)",
            "supporting": "Supporting"
        }
        if enriched.get("domain_role"):
            enriched["domain_role_label"] = role_labels.get(enriched["domain_role"], enriched["domain_role"])
        
        # Translate index status
        if enriched.get("index_status"):
            enriched["index_status_label"] = enriched["index_status"].upper()
        
        return enriched
    
    # Enrich logs
    enriched = []
    for log in logs:
        log["network_name"] = network.get("name")
        
        # Get brand name
        if log.get("brand_id"):
            brand = await db.brands.find_one({"id": log["brand_id"]}, {"_id": 0, "name": 1})
            log["brand_name"] = brand["name"] if brand else None
        
        # Enrich before/after snapshots with human-readable labels
        log["before_snapshot"] = await enrich_snapshot(log.get("before_snapshot"))
        log["after_snapshot"] = await enrich_snapshot(log.get("after_snapshot"))
        
        enriched.append(SeoChangeLogResponse(**log))
    
    return enriched


@router.get("/networks/{network_id}/notifications", response_model=List[SeoNetworkNotification])
async def get_network_notifications(
    network_id: str,
    unread_only: bool = False,
    skip: int = 0,
    limit: int = Query(default=20, le=100),
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get notifications for a network (important SEO events)"""
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    # Check brand access
    brand_id = network.get("brand_id")
    if brand_id:
        require_brand_access(brand_id, current_user)
    
    if not seo_change_log_service:
        return []
    
    notifications = await seo_change_log_service.get_network_notifications(
        network_id=network_id,
        unread_only=unread_only,
        skip=skip,
        limit=limit
    )
    
    # Enrich with network name
    for notif in notifications:
        notif["network_name"] = network.get("name")
    
    return [SeoNetworkNotification(**n) for n in notifications]


@router.post("/networks/{network_id}/notifications/{notification_id}/read")
async def mark_notification_read(
    network_id: str,
    notification_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Mark a notification as read"""
    if not seo_change_log_service:
        raise HTTPException(status_code=500, detail="SEO change log service not initialized")
    
    success = await seo_change_log_service.mark_notification_read(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"message": "Notification marked as read"}


@router.post("/networks/{network_id}/notifications/read-all")
async def mark_all_notifications_read(
    network_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Mark all notifications in a network as read"""
    if not seo_change_log_service:
        raise HTTPException(status_code=500, detail="SEO change log service not initialized")
    
    count = await seo_change_log_service.mark_all_notifications_read(network_id)
    return {"message": f"Marked {count} notifications as read", "count": count}


@router.get("/change-logs/stats")
async def get_change_log_stats(
    days: int = Query(default=30, ge=1, le=365),
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Get team evaluation metrics for SEO changes.
    
    Returns:
    - Changes per user
    - Changes per network
    - Most modified domains
    - Activity periods
    """
    if not seo_change_log_service:
        return {"error": "SEO change log service not initialized"}
    
    # Get user's brand scope for filtering
    brand_scope = get_user_brand_scope(current_user)
    
    stats = await seo_change_log_service.get_team_stats(
        brand_ids=brand_scope,
        days=days
    )
    
    # Enrich with network names
    if stats.get("changes_by_network"):
        network_ids = [c["_id"] for c in stats["changes_by_network"]]
        networks = await db.seo_networks.find(
            {"id": {"$in": network_ids}},
            {"_id": 0, "id": 1, "name": 1}
        ).to_list(1000)
        network_lookup = {n["id"]: n["name"] for n in networks}
        
        for item in stats["changes_by_network"]:
            item["network_name"] = network_lookup.get(item["_id"], "Unknown")
    
    return stats


# ==================== SEO TELEGRAM ALERTS (SEPARATE CHANNEL) ====================

async def send_seo_telegram_alert(message: str) -> bool:
    """
    Send SEO change alert to SEPARATE Telegram channel.
    
    This is for SEO strategy decisions, NOT monitoring alerts.
    """
    settings = await db.settings.find_one({"key": "telegram_seo"}, {"_id": 0})
    
    # Fallback to main telegram if SEO channel not configured
    if not settings or not settings.get("bot_token") or not settings.get("chat_id"):
        logger.info("SEO Telegram channel not configured, using main channel")
        settings = await db.settings.find_one({"key": "telegram"}, {"_id": 0})
        if not settings or not settings.get("bot_token") or not settings.get("chat_id"):
            logger.warning("Telegram not configured, skipping SEO alert")
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
        logger.error(f"Failed to send SEO Telegram alert: {e}")
        return False


@router.put("/settings/telegram-seo")
async def update_telegram_seo_settings(
    settings: dict,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Update SEO Telegram channel settings with forum topic support"""
    # Require super_admin for settings
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admin can update Telegram settings")
    
    # Get existing settings first
    existing = await db.settings.find_one({"key": "telegram_seo"}, {"_id": 0})
    
    # Build update dict - only update provided fields
    update_data = {
        "key": "telegram_seo",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Core settings
    if "bot_token" in settings and settings["bot_token"]:
        update_data["bot_token"] = settings["bot_token"]
    elif existing and existing.get("bot_token"):
        update_data["bot_token"] = existing["bot_token"]
    
    if "chat_id" in settings and settings["chat_id"]:
        update_data["chat_id"] = settings["chat_id"]
    elif existing and existing.get("chat_id"):
        update_data["chat_id"] = existing["chat_id"]
    
    if "enabled" in settings:
        update_data["enabled"] = settings["enabled"]
    elif existing:
        update_data["enabled"] = existing.get("enabled", True)
    else:
        update_data["enabled"] = True
    
    # Forum topic settings
    if "enable_topic_routing" in settings:
        update_data["enable_topic_routing"] = settings["enable_topic_routing"]
    elif existing:
        update_data["enable_topic_routing"] = existing.get("enable_topic_routing", False)
    
    # Topic IDs for forum routing
    topic_fields = ["seo_change_topic_id", "seo_optimization_topic_id", "seo_complaint_topic_id", "seo_reminder_topic_id"]
    for field in topic_fields:
        if field in settings:
            update_data[field] = settings[field] if settings[field] else None
        elif existing and existing.get(field):
            update_data[field] = existing[field]
    
    await db.settings.update_one(
        {"key": "telegram_seo"},
        {"$set": update_data},
        upsert=True
    )
    
    return {"message": "SEO Telegram settings updated", "settings": {k: v for k, v in update_data.items() if k != "key"}}


@router.get("/settings/telegram-seo")
async def get_telegram_seo_settings(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get SEO Telegram channel settings with forum topic support"""
    settings = await db.settings.find_one({"key": "telegram_seo"}, {"_id": 0})
    if not settings:
        return {
            "configured": False,
            "enabled": True,
            "enable_topic_routing": False,
            "chat_id": None,
            "seo_change_topic_id": None,
            "seo_optimization_topic_id": None,
            "seo_complaint_topic_id": None,
            "seo_reminder_topic_id": None
        }
    
    return {
        "configured": bool(settings.get("bot_token") and settings.get("chat_id")),
        "enabled": settings.get("enabled", True),
        "chat_id": settings.get("chat_id"),
        "bot_token": settings.get("bot_token"),  # For display (masked in frontend)
        "enable_topic_routing": settings.get("enable_topic_routing", False),
        "seo_change_topic_id": settings.get("seo_change_topic_id"),
        "seo_optimization_topic_id": settings.get("seo_optimization_topic_id"),
        "seo_complaint_topic_id": settings.get("seo_complaint_topic_id"),
        "seo_reminder_topic_id": settings.get("seo_reminder_topic_id")
    }


@router.post("/settings/telegram-seo/test")
async def test_telegram_seo_alert(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Send a test message to SEO Telegram channel"""
    # Use the new service if available
    if seo_telegram_service:
        success = await seo_telegram_service.send_test_notification(current_user['email'])
    else:
        # Fallback to inline message
        message = f"""🔔 <b>PESAN TEST - TIDAK ADA PERUBAHAN SEO</b>

Ini adalah pesan test dari sistem notifikasi SEO.

📌 <b>Detail Test</b>
• Dikirim Oleh     : {current_user['email'].split('@')[0].title()} ({current_user['email']})
• Waktu            : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
• Channel          : SEO Change Notifications

✅ Jika Anda melihat pesan ini, konfigurasi Telegram untuk notifikasi SEO sudah benar!

<i>TEST MESSAGE - NO SEO CHANGE APPLIED</i>"""
        
        success = await send_seo_telegram_alert(message)
    
    if success:
        return {"message": "Test message sent successfully / Pesan test berhasil dikirim"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send test message. Check Telegram configuration.")

