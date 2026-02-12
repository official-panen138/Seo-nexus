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

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import httpx
import logging

# Import models
import sys

sys.path.insert(0, "/app/backend")
from models_v3 import (
    AssetDomainCreate,
    AssetDomainUpdate,
    AssetDomainResponse,
    NetworkUsageInfo,
    PaginationMeta,
    PaginatedResponse,
    SeoNetworkCreate,
    SeoNetworkUpdate,
    SeoNetworkResponse,
    SeoNetworkDetail,
    SeoNetworkCreateLegacy,
    MainNodeConfig,
    SeoStructureEntryCreate,
    SeoStructureEntryUpdate,
    SeoStructureEntryResponse,
    SeoStructureEntryCreateWithNote,
    SeoStructureEntryUpdateWithNote,
    SeoChangeLogResponse,
    SeoNetworkNotification,
    SeoChangeActionType,
    SeoNotificationType,
    ActivityLogResponse,
    RegistrarCreate,
    RegistrarUpdate,
    RegistrarResponse,
    RegistrarStatus,
    SeoConflict,
    ConflictType,
    ConflictSeverity,
    ConflictStatus,
    StoredConflict,
    ConflictResolutionCreate,
    ConflictResolutionResponse,
    LinkedConflictInfo,
    MonitoringSettings,
    MonitoringSettingsUpdate,
    AssetStatus,
    NetworkStatus,
    DomainRole,
    SeoStatus,
    IndexStatus,
    ActionType,
    EntityType,
    get_tier_label,
    SeoOptimizationCreate,
    SeoOptimizationUpdate,
    SeoOptimizationResponse,
    SeoOptimizationDetailResponse,
    OptimizationActivityType,
    OptimizationStatus,
    ComplaintStatus,
    ObservedImpact,
    OptimizationComplaintCreate,
    OptimizationComplaintResponse,
    ComplaintPriority,
    # New models for Domain Lifecycle & Quarantine
    DomainLifecycleStatus,
    QuarantineCategory,
    MONITORED_LIFECYCLE_STATUSES,
    QUARANTINE_CATEGORY_LABELS,
    MarkAsReleasedRequest,
    SetQuarantineRequest,
    RemoveQuarantineRequest,
    LifecycleChangeRequest,
    SeoMonitoringCoverageStats,
    TeamResponseCreate,
    TeamResponseEntry,
    ComplaintResolveRequest,
    OptimizationCloseRequest,
    NetworkAccessControl,
    NetworkVisibilityMode,
    MASTER_MENU_REGISTRY,
    DEFAULT_ADMIN_MENUS,
    DEFAULT_USER_MENUS,
    MenuPermissionUpdate,
    MenuPermissionResponse,
    UserTelegramSettings,
    NetworkManagersUpdate,
    OptimizationActivityTypeCreate,
    OptimizationActivityTypeResponse,
    UserSeoScore,
    TeamEvaluationSummary,
    ProjectComplaintCreate,
    ProjectComplaintResponse,
    ProjectComplaintResolveRequest,
)
from services.seo_optimization_telegram_service import SeoOptimizationTelegramService
from services.conflict_optimization_linker_service import get_conflict_linker_service
from services.conflict_metrics_service import get_conflict_metrics_service

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
    seo_telegram_svc=None,
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


async def get_current_user_wrapper(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
):
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
            response = await client.post(
                url,
                json={
                    "chat_id": settings["chat_id"],
                    "text": message,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
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
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this network. It is restricted to specific users.",
            )
        raise HTTPException(
            status_code=403, detail="You do not have access to this network."
        )


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
            detail="You are not assigned as a manager for this SEO Network. Only managers can perform this action.",
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
        raise HTTPException(
            status_code=403,
            detail="Access denied. This network has restricted visibility.",
        )

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
            detail=f"Change note is required and must be at least {MIN_CHANGE_NOTE_LENGTH} characters. This note will be sent to the SEO team via Telegram.",
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
    skip_rate_limit: bool = False,
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
            entry_id=entry_id,
        )

    # Step 2: Send Telegram notification (MANDATORY)
    notification_success = False
    error_message = None

    if seo_telegram_service:
        try:
            # Convert action_type to string for telegram service
            action_str = (
                action_type.value if hasattr(action_type, "value") else str(action_type)
            )

            notification_success = (
                await seo_telegram_service.send_seo_change_notification(
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
                    skip_rate_limit=skip_rate_limit,
                )
            )

            # Update notification status
            if seo_change_log_service and change_log_id:
                await seo_change_log_service.update_notification_status(
                    change_log_id, "success" if notification_success else "failed"
                )

        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")
            error_message = str(e)
            notification_success = False

            # Update notification status as failed
            if seo_change_log_service and change_log_id:
                await seo_change_log_service.update_notification_status(
                    change_log_id, "failed"
                )
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
    """Enrich asset domain with brand/category/registrar names and lifecycle info"""
    if asset.get("brand_id"):
        brand = await db.brands.find_one(
            {"id": asset["brand_id"]}, {"_id": 0, "name": 1}
        )
        asset["brand_name"] = brand["name"] if brand else None
    else:
        asset["brand_name"] = None

    if asset.get("category_id"):
        category = await db.categories.find_one(
            {"id": asset["category_id"]}, {"_id": 0, "name": 1}
        )
        asset["category_name"] = category["name"] if category else None
    else:
        asset["category_name"] = None

    # Enrich registrar name from registrar_id
    if asset.get("registrar_id"):
        registrar = await db.registrars.find_one(
            {"id": asset["registrar_id"]}, {"_id": 0, "name": 1}
        )
        asset["registrar_name"] = registrar["name"] if registrar else None
    else:
        asset["registrar_name"] = asset.get("registrar")  # Legacy fallback

    # Enrich SEO network usage
    structure_entries = await db.seo_structure_entries.find(
        {"asset_domain_id": asset["id"]}, {"_id": 0, "network_id": 1, "domain_role": 1, "optimized_path": 1}
    ).to_list(100)
    
    network_ids = [e["network_id"] for e in structure_entries]
    networks = await db.seo_networks.find(
        {"id": {"$in": network_ids}}, {"_id": 0, "id": 1, "name": 1}
    ).to_list(100)
    network_map = {n["id"]: n["name"] for n in networks}
    
    asset["seo_networks"] = [
        NetworkUsageInfo(
            network_id=e["network_id"],
            network_name=network_map.get(e["network_id"], "Unknown"),
            role=e.get("domain_role", "supporting"),
            optimized_path=e.get("optimized_path")
        )
        for e in structure_entries
    ]
    
    # Determine if used in SEO and if monitoring is required
    asset["is_used_in_seo_network"] = len(structure_entries) > 0
    
    lifecycle = asset.get("domain_lifecycle_status", DomainLifecycleStatus.ACTIVE.value)
    is_active_lifecycle = lifecycle in [
        DomainLifecycleStatus.ACTIVE.value, 
        DomainLifecycleStatus.EXPIRED_PENDING.value,
        None
    ]
    is_not_quarantined = not asset.get("quarantine_category")
    asset["requires_monitoring"] = asset["is_used_in_seo_network"] and is_active_lifecycle and is_not_quarantined
    
    # Add quarantine category label
    qc = asset.get("quarantine_category")
    if qc:
        asset["quarantine_category_label"] = QUARANTINE_CATEGORY_LABELS.get(qc, qc)
    
    # Ensure lifecycle status has a default
    if not asset.get("domain_lifecycle_status"):
        asset["domain_lifecycle_status"] = DomainLifecycleStatus.ACTIVE.value
    
    # Enrich user names for quarantine and release
    if asset.get("quarantined_by"):
        user = await db.users.find_one({"id": asset["quarantined_by"]}, {"_id": 0, "name": 1, "email": 1})
        asset["quarantined_by_name"] = user.get("name") or user.get("email") if user else None
    
    if asset.get("released_by"):
        user = await db.users.find_one({"id": asset["released_by"]}, {"_id": 0, "name": 1, "email": 1})
        asset["released_by_name"] = user.get("name") or user.get("email") if user else None

    return asset


async def enrich_structure_entry(
    entry: dict, network_tiers: Dict[str, int] = None
) -> dict:
    """Enrich structure entry with names, node label, and calculated tier"""
    # Get asset domain name
    if entry.get("asset_domain_id"):
        asset = await db.asset_domains.find_one(
            {"id": entry["asset_domain_id"]},
            {"_id": 0, "domain_name": 1, "brand_id": 1},
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
            brand = await db.brands.find_one(
                {"id": asset["brand_id"]}, {"_id": 0, "name": 1}
            )
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
            {"_id": 0, "asset_domain_id": 1, "optimized_path": 1},
        )
        if target_entry:
            target_asset = await db.asset_domains.find_one(
                {"id": target_entry["asset_domain_id"]}, {"_id": 0, "domain_name": 1}
            )
            if target_asset:
                entry["target_domain_name"] = target_asset["domain_name"]
                entry["target_entry_path"] = target_entry.get("optimized_path")
    elif entry.get("target_asset_domain_id"):
        # Legacy domain-to-domain relationship
        target = await db.asset_domains.find_one(
            {"id": entry["target_asset_domain_id"]}, {"_id": 0, "domain_name": 1}
        )
        entry["target_domain_name"] = target["domain_name"] if target else None

    # Get network name
    if entry.get("network_id"):
        network = await db.seo_networks.find_one(
            {"id": entry["network_id"]}, {"_id": 0, "name": 1}
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
            entry["network_id"], entry["id"]
        )
        entry["calculated_tier"] = tier
        entry["tier_label"] = label
    else:
        entry["calculated_tier"] = None
        entry["tier_label"] = None

    return entry


# ==================== MENU ACCESS CONTROL ENDPOINTS ====================


@router.get("/menu-registry")
async def get_menu_registry(current_user: dict = Depends(get_current_user_wrapper)):
    """Get the master menu registry with all available menus"""
    return {
        "menus": MASTER_MENU_REGISTRY,
        "total": len(MASTER_MENU_REGISTRY)
    }


@router.get("/my-menu-permissions")
async def get_my_menu_permissions(current_user: dict = Depends(get_current_user_wrapper)):
    """Get menu permissions for the current user"""
    user_role = current_user.get("role", "viewer")
    user_id = current_user.get("id")
    
    # Super Admin has full access
    if user_role == "super_admin":
        return {
            "user_id": user_id,
            "role": user_role,
            "enabled_menus": [m["key"] for m in MASTER_MENU_REGISTRY],
            "is_super_admin": True
        }
    
    # Check if user has custom menu permissions
    user_permissions = await db.menu_permissions.find_one({"user_id": user_id})
    
    if user_permissions:
        enabled_menus = user_permissions.get("enabled_menus", [])
    else:
        # Apply defaults based on role
        if user_role == "admin":
            enabled_menus = DEFAULT_ADMIN_MENUS.copy()
        else:
            enabled_menus = DEFAULT_USER_MENUS.copy()
    
    return {
        "user_id": user_id,
        "role": user_role,
        "enabled_menus": enabled_menus,
        "is_super_admin": False
    }


@router.get("/admin/menu-permissions/{user_id}")
async def get_user_menu_permissions(
    user_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get menu permissions for a specific user (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can view user menu permissions")
    
    # Get target user
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    target_role = target_user.get("role", "viewer")
    
    # Super Admin users cannot have their permissions modified
    if target_role == "super_admin":
        return {
            "user_id": user_id,
            "user_name": target_user.get("name", ""),
            "user_email": target_user.get("email", ""),
            "role": target_role,
            "enabled_menus": [m["key"] for m in MASTER_MENU_REGISTRY],
            "is_super_admin": True,
            "is_default": True
        }
    
    # Check for custom permissions
    user_permissions = await db.menu_permissions.find_one({"user_id": user_id})
    
    if user_permissions:
        enabled_menus = user_permissions.get("enabled_menus", [])
        is_default = False
    else:
        # Apply defaults
        if target_role == "admin":
            enabled_menus = DEFAULT_ADMIN_MENUS.copy()
        else:
            enabled_menus = DEFAULT_USER_MENUS.copy()
        is_default = True
    
    return {
        "user_id": user_id,
        "user_name": target_user.get("name", ""),
        "user_email": target_user.get("email", ""),
        "role": target_role,
        "enabled_menus": enabled_menus,
        "is_super_admin": False,
        "is_default": is_default
    }


@router.put("/admin/menu-permissions/{user_id}")
async def update_user_menu_permissions(
    user_id: str,
    permissions: MenuPermissionUpdate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Update menu permissions for a specific user (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can modify menu permissions")
    
    # Get target user
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    target_role = target_user.get("role", "viewer")
    
    # Cannot modify Super Admin permissions
    if target_role == "super_admin":
        raise HTTPException(status_code=400, detail="Cannot modify Super Admin menu permissions")
    
    # Validate menu keys
    valid_keys = {m["key"] for m in MASTER_MENU_REGISTRY}
    invalid_keys = set(permissions.enabled_menus) - valid_keys
    if invalid_keys:
        raise HTTPException(status_code=400, detail=f"Invalid menu keys: {invalid_keys}")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Upsert permissions
    await db.menu_permissions.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "enabled_menus": permissions.enabled_menus,
                "updated_at": now,
                "updated_by": current_user.get("id")
            },
            "$setOnInsert": {
                "created_at": now
            }
        },
        upsert=True
    )
    
    # Log the action
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "event_type": "menu_permissions_updated",
        "actor": current_user.get("email"),
        "actor_id": current_user.get("id"),
        "resource": f"user:{user_id}",
        "details": {
            "target_user": target_user.get("email"),
            "target_role": target_role,
            "enabled_menus": permissions.enabled_menus
        },
        "severity": "info",
        "status": "success",
        "timestamp": now
    })
    
    return {
        "message": "Menu permissions updated successfully",
        "user_id": user_id,
        "enabled_menus": permissions.enabled_menus
    }


@router.delete("/admin/menu-permissions/{user_id}")
async def reset_user_menu_permissions(
    user_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Reset menu permissions to default for a user (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can reset menu permissions")
    
    # Get target user
    target_user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    target_role = target_user.get("role", "viewer")
    
    if target_role == "super_admin":
        raise HTTPException(status_code=400, detail="Cannot modify Super Admin menu permissions")
    
    # Delete custom permissions (will fall back to defaults)
    await db.menu_permissions.delete_one({"user_id": user_id})
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Log the action
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "event_type": "menu_permissions_reset",
        "actor": current_user.get("email"),
        "actor_id": current_user.get("id"),
        "resource": f"user:{user_id}",
        "details": {
            "target_user": target_user.get("email"),
            "target_role": target_role
        },
        "severity": "info",
        "status": "success",
        "timestamp": now
    })
    
    # Return defaults
    if target_role == "admin":
        default_menus = DEFAULT_ADMIN_MENUS
    else:
        default_menus = DEFAULT_USER_MENUS
    
    return {
        "message": "Menu permissions reset to default",
        "user_id": user_id,
        "enabled_menus": default_menus
    }


class BulkMenuPermissionUpdate(BaseModel):
    """Model for bulk updating menu permissions"""
    user_ids: List[str] = Field(..., description="List of user IDs to update")
    enabled_menus: List[str] = Field(..., description="List of menu keys to assign")


@router.put("/admin/menu-permissions/bulk")
async def bulk_update_menu_permissions(
    bulk_update: BulkMenuPermissionUpdate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Bulk update menu permissions for multiple users (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can modify menu permissions")
    
    # Validate menu keys
    valid_keys = {m["key"] for m in MASTER_MENU_REGISTRY}
    invalid_keys = set(bulk_update.enabled_menus) - valid_keys
    if invalid_keys:
        raise HTTPException(status_code=400, detail=f"Invalid menu keys: {invalid_keys}")
    
    # Get all target users
    target_users = await db.users.find(
        {"id": {"$in": bulk_update.user_ids}},
        {"_id": 0, "id": 1, "email": 1, "role": 1}
    ).to_list(None)
    
    if not target_users:
        raise HTTPException(status_code=404, detail="No users found")
    
    user_map = {u["id"]: u for u in target_users}
    
    now = datetime.now(timezone.utc).isoformat()
    results = {
        "updated": [],
        "skipped_super_admin": [],
        "not_found": []
    }
    
    for user_id in bulk_update.user_ids:
        user = user_map.get(user_id)
        
        if not user:
            results["not_found"].append(user_id)
            continue
        
        if user.get("role") == "super_admin":
            results["skipped_super_admin"].append(user_id)
            continue
        
        # Upsert permissions
        await db.menu_permissions.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "enabled_menus": bulk_update.enabled_menus,
                    "updated_at": now,
                    "updated_by": current_user.get("id")
                },
                "$setOnInsert": {
                    "created_at": now
                }
            },
            upsert=True
        )
        results["updated"].append({"user_id": user_id, "email": user.get("email")})
    
    # Log the bulk action
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "event_type": "menu_permissions_bulk_updated",
        "actor": current_user.get("email"),
        "actor_id": current_user.get("id"),
        "resource": "bulk_users",
        "details": {
            "user_count": len(results["updated"]),
            "enabled_menus": bulk_update.enabled_menus,
            "skipped_super_admin": len(results["skipped_super_admin"])
        },
        "severity": "info",
        "status": "success",
        "timestamp": now
    })
    
    return {
        "message": f"Menu permissions updated for {len(results['updated'])} users",
        "results": results,
        "enabled_menus": bulk_update.enabled_menus
    }


class BulkBrandAccessUpdate(BaseModel):
    """Model for bulk updating brand access"""
    user_ids: List[str] = Field(..., description="List of user IDs to update")
    brand_scope_ids: List[str] = Field(..., description="List of brand IDs to assign")
    mode: str = Field(default="replace", description="'replace' to overwrite, 'add' to append")


@router.put("/admin/brand-access/bulk")
async def bulk_update_brand_access(
    bulk_update: BulkBrandAccessUpdate,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Bulk update brand access for multiple users (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can modify brand access")
    
    # Validate brand IDs exist
    valid_brands = await db.brands.find(
        {"id": {"$in": bulk_update.brand_scope_ids}},
        {"_id": 0, "id": 1, "name": 1}
    ).to_list(None)
    valid_brand_ids = {b["id"] for b in valid_brands}
    
    invalid_brand_ids = set(bulk_update.brand_scope_ids) - valid_brand_ids
    if invalid_brand_ids:
        raise HTTPException(status_code=400, detail=f"Invalid brand IDs: {invalid_brand_ids}")
    
    # Get all target users
    target_users = await db.users.find(
        {"id": {"$in": bulk_update.user_ids}},
        {"_id": 0, "id": 1, "email": 1, "role": 1, "brand_scope_ids": 1}
    ).to_list(None)
    
    if not target_users:
        raise HTTPException(status_code=404, detail="No users found")
    
    user_map = {u["id"]: u for u in target_users}
    
    now = datetime.now(timezone.utc).isoformat()
    results = {
        "updated": [],
        "skipped_super_admin": [],
        "not_found": []
    }
    
    for user_id in bulk_update.user_ids:
        user = user_map.get(user_id)
        
        if not user:
            results["not_found"].append(user_id)
            continue
        
        # Super admins have access to all brands, no need to update
        if user.get("role") == "super_admin":
            results["skipped_super_admin"].append(user_id)
            continue
        
        # Determine new brand_scope_ids based on mode
        if bulk_update.mode == "add":
            current_brands = set(user.get("brand_scope_ids", []))
            new_brands = list(current_brands | set(bulk_update.brand_scope_ids))
        else:  # replace
            new_brands = bulk_update.brand_scope_ids
        
        # Update user's brand_scope_ids
        await db.users.update_one(
            {"id": user_id},
            {
                "$set": {
                    "brand_scope_ids": new_brands,
                    "updated_at": now
                }
            }
        )
        results["updated"].append({
            "user_id": user_id, 
            "email": user.get("email"),
            "brand_count": len(new_brands)
        })
    
    # Log the bulk action
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "event_type": "brand_access_bulk_updated",
        "actor": current_user.get("email"),
        "actor_id": current_user.get("id"),
        "resource": "bulk_users",
        "details": {
            "user_count": len(results["updated"]),
            "brand_ids": bulk_update.brand_scope_ids,
            "mode": bulk_update.mode,
            "skipped_super_admin": len(results["skipped_super_admin"])
        },
        "severity": "info",
        "status": "success",
        "timestamp": now
    })
    
    return {
        "message": f"Brand access updated for {len(results['updated'])} users",
        "results": results,
        "brand_scope_ids": bulk_update.brand_scope_ids,
        "mode": bulk_update.mode
    }


# ==================== REGISTRAR ENDPOINTS (MASTER DATA) ====================


@router.get("/registrars", response_model=List[RegistrarResponse])
async def get_registrars(
    status: Optional[RegistrarStatus] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper),
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
        reg["domain_count"] = await db.asset_domains.count_documents(
            {"registrar_id": reg["id"]}
        )

    return [RegistrarResponse(**r) for r in registrars]


@router.get("/registrars/{registrar_id}", response_model=RegistrarResponse)
async def get_registrar(
    registrar_id: str, current_user: dict = Depends(get_current_user_wrapper)
):
    """Get a single registrar by ID"""
    registrar = await db.registrars.find_one({"id": registrar_id}, {"_id": 0})
    if not registrar:
        raise HTTPException(status_code=404, detail="Registrar not found")

    registrar["domain_count"] = await db.asset_domains.count_documents(
        {"registrar_id": registrar_id}
    )
    return RegistrarResponse(**registrar)


@router.post("/registrars", response_model=RegistrarResponse)
async def create_registrar(
    data: RegistrarCreate, current_user: dict = Depends(get_current_user_wrapper)
):
    """Create a new registrar (super_admin only)"""
    # Check super_admin role
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=403, detail="Only super_admin can manage registrars"
        )

    # Check for duplicate name
    existing = await db.registrars.find_one(
        {"name": {"$regex": f"^{data.name}$", "$options": "i"}}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Registrar name already exists")

    now = datetime.now(timezone.utc).isoformat()
    registrar = {
        "id": str(uuid.uuid4()),
        **data.model_dump(),
        "created_at": now,
        "updated_at": now,
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
            after_value=registrar,
        )

    registrar["domain_count"] = 0
    return RegistrarResponse(**registrar)


@router.put("/registrars/{registrar_id}", response_model=RegistrarResponse)
async def update_registrar(
    registrar_id: str,
    data: RegistrarUpdate,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Update a registrar (super_admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=403, detail="Only super_admin can manage registrars"
        )

    existing = await db.registrars.find_one({"id": registrar_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Registrar not found")

    update_dict = {k: v for k, v in data.model_dump().items() if v is not None}

    # Check for duplicate name if changing
    if "name" in update_dict and update_dict["name"] != existing["name"]:
        dup = await db.registrars.find_one(
            {
                "name": {"$regex": f"^{update_dict['name']}$", "$options": "i"},
                "id": {"$ne": registrar_id},
            }
        )
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
            after_value={**existing, **update_dict},
        )

    updated = await db.registrars.find_one({"id": registrar_id}, {"_id": 0})
    updated["domain_count"] = await db.asset_domains.count_documents(
        {"registrar_id": registrar_id}
    )
    return RegistrarResponse(**updated)


@router.delete("/registrars/{registrar_id}")
async def delete_registrar(
    registrar_id: str, current_user: dict = Depends(get_current_user_wrapper)
):
    """Delete a registrar (super_admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=403, detail="Only super_admin can manage registrars"
        )

    existing = await db.registrars.find_one({"id": registrar_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Registrar not found")

    # Check if used by any domains
    domain_count = await db.asset_domains.count_documents(
        {"registrar_id": registrar_id}
    )
    if domain_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete: {domain_count} domains use this registrar",
        )

    await db.registrars.delete_one({"id": registrar_id})

    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.DELETE,
            entity_type=EntityType.REGISTRAR,
            entity_id=registrar_id,
            before_value=existing,
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
    # New filters for lifecycle and quarantine
    lifecycle_status: Optional[DomainLifecycleStatus] = None,
    quarantine_category: Optional[str] = None,
    is_quarantined: Optional[bool] = None,
    used_in_seo: Optional[bool] = None,
    # Special view modes
    view_mode: Optional[str] = Query(default=None, description="Special view: 'released', 'quarantined', 'unmonitored'"),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    limit: int = Query(default=25, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get asset domains with SERVER-SIDE PAGINATION - BRAND SCOPED.

    New filters:
    - lifecycle_status: Filter by domain lifecycle (active, expired_pending, expired_released, inactive, archived)
    - quarantine_category: Filter by quarantine category
    - is_quarantined: true = only quarantined, false = only non-quarantined
    - used_in_seo: true = only domains in SEO networks, false = only unused domains
    - view_mode: Special views - 'released' (expired_released), 'quarantined', 'unmonitored' (in SEO but monitoring disabled)

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

    # New lifecycle filter
    if lifecycle_status:
        query["domain_lifecycle_status"] = lifecycle_status.value
    
    # Quarantine filters
    if quarantine_category:
        query["quarantine_category"] = quarantine_category
    if is_quarantined is not None:
        if is_quarantined:
            query["quarantine_category"] = {"$ne": None}
        else:
            query["$or"] = [
                {"quarantine_category": None},
                {"quarantine_category": {"$exists": False}}
            ]

    # Handle special view modes
    if view_mode == "released":
        query["domain_lifecycle_status"] = DomainLifecycleStatus.EXPIRED_RELEASED.value
    elif view_mode == "quarantined":
        query["quarantine_category"] = {"$ne": None}

    # Filter by network_id if provided (domains used in a specific SEO network)
    domain_ids_in_seo = None
    if network_id:
        # Get all asset_domain_ids used in this network
        structure_entries = await db.seo_structure_entries.find(
            {"network_id": network_id}, {"_id": 0, "asset_domain_id": 1}
        ).to_list(10000)
        domain_ids_in_network = [e["asset_domain_id"] for e in structure_entries]
        query["id"] = {"$in": domain_ids_in_network}
    elif used_in_seo is not None or view_mode == "unmonitored":
        # Get all domain IDs used in any SEO network
        all_structure_entries = await db.seo_structure_entries.find(
            {}, {"_id": 0, "asset_domain_id": 1}
        ).to_list(100000)
        domain_ids_in_seo = list(set([e["asset_domain_id"] for e in all_structure_entries]))
        
        if view_mode == "unmonitored":
            # Unmonitored = in SEO network + monitoring disabled + active lifecycle + not quarantined
            query["id"] = {"$in": domain_ids_in_seo}
            query["monitoring_enabled"] = False
            query["domain_lifecycle_status"] = {"$in": [
                DomainLifecycleStatus.ACTIVE.value,
                DomainLifecycleStatus.EXPIRED_PENDING.value,
                None  # Legacy domains without lifecycle status
            ]}
            query["$or"] = [
                {"quarantine_category": None},
                {"quarantine_category": {"$exists": False}}
            ]
        elif used_in_seo:
            query["id"] = {"$in": domain_ids_in_seo}
        else:
            query["id"] = {"$nin": domain_ids_in_seo}

    # Get total count for pagination
    total = await db.asset_domains.count_documents(query)
    total_pages = math.ceil(total / limit) if total > 0 else 1

    # Calculate skip from page number
    skip = (page - 1) * limit

    # Fetch paginated data
    assets = (
        await db.asset_domains.find(query, {"_id": 0})
        .sort("domain_name", 1)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )

    # Batch enrich - brands, categories, registrars
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
    registrars = {
        r["id"]: r["name"]
        for r in await db.registrars.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(
            1000
        )
    }

    # Batch fetch SEO network usage for all domains (efficient aggregation)
    asset_ids = [a["id"] for a in assets]

    # Aggregate: group structure entries by asset_domain_id, include network info
    network_usage_pipeline = [
        {"$match": {"asset_domain_id": {"$in": asset_ids}}},
        {
            "$lookup": {
                "from": "seo_networks",
                "localField": "network_id",
                "foreignField": "id",
                "as": "network",
            }
        },
        {"$unwind": {"path": "$network", "preserveNullAndEmptyArrays": True}},
        {
            "$group": {
                "_id": "$asset_domain_id",
                "networks": {
                    "$push": {
                        "network_id": "$network_id",
                        "network_name": "$network.name",
                        "role": "$domain_role",
                        "optimized_path": "$optimized_path",
                    }
                },
            }
        },
    ]

    network_usage_result = await db.seo_structure_entries.aggregate(
        network_usage_pipeline
    ).to_list(10000)
    network_usage_map = {item["_id"]: item["networks"] for item in network_usage_result}

    for asset in assets:
        asset["brand_name"] = brands.get(asset.get("brand_id"))
        asset["category_name"] = categories.get(asset.get("category_id"))
        # Use registrar_id lookup, fallback to legacy field
        asset["registrar_name"] = registrars.get(
            asset.get("registrar_id")
        ) or asset.get("registrar")

        # Add SEO network usage
        raw_networks = network_usage_map.get(asset["id"], [])
        asset["seo_networks"] = [
            NetworkUsageInfo(
                network_id=n.get("network_id", ""),
                network_name=n.get("network_name", "Unknown"),
                role=n.get("role", "supporting"),
                optimized_path=n.get("optimized_path"),
            )
            for n in raw_networks
            if n.get("network_id")
        ]

        # Enrich lifecycle and quarantine info
        is_used_in_seo = len(raw_networks) > 0
        asset["is_used_in_seo_network"] = is_used_in_seo
        
        # Check if monitoring is required (used in SEO + active lifecycle + not quarantined)
        lifecycle = asset.get("domain_lifecycle_status", DomainLifecycleStatus.ACTIVE.value)
        is_active_lifecycle = lifecycle in [
            DomainLifecycleStatus.ACTIVE.value, 
            DomainLifecycleStatus.EXPIRED_PENDING.value,
            None  # Legacy domains
        ]
        is_not_quarantined = not asset.get("quarantine_category")
        asset["requires_monitoring"] = is_used_in_seo and is_active_lifecycle and is_not_quarantined
        
        # Add quarantine category label
        qc = asset.get("quarantine_category")
        if qc:
            asset["quarantine_category_label"] = QUARANTINE_CATEGORY_LABELS.get(qc, qc)
        
        # Ensure lifecycle status has a default
        if not asset.get("domain_lifecycle_status"):
            asset["domain_lifecycle_status"] = DomainLifecycleStatus.ACTIVE.value

    # Batch fetch user names for quarantined_by and released_by
    user_ids_to_fetch = set()
    for asset in assets:
        if asset.get("quarantined_by"):
            user_ids_to_fetch.add(asset["quarantined_by"])
        if asset.get("released_by"):
            user_ids_to_fetch.add(asset["released_by"])
    
    if user_ids_to_fetch:
        users = await db.users.find(
            {"id": {"$in": list(user_ids_to_fetch)}}, 
            {"_id": 0, "id": 1, "name": 1, "email": 1}
        ).to_list(100)
        user_map = {u["id"]: u.get("name") or u.get("email", "Unknown") for u in users}
        
        for asset in assets:
            if asset.get("quarantined_by"):
                asset["quarantined_by_name"] = user_map.get(asset["quarantined_by"])
            if asset.get("released_by"):
                asset["released_by_name"] = user_map.get(asset["released_by"])

    # Return paginated response
    return {
        "data": [AssetDomainResponse(**a) for a in assets],
        "meta": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
        },
    }


@router.get("/asset-domains/{asset_id}", response_model=AssetDomainResponse)
async def get_asset_domain(
    asset_id: str, current_user: dict = Depends(get_current_user_wrapper)
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
    data: AssetDomainCreate, current_user: dict = Depends(get_current_user_wrapper)
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
        "updated_at": now,
    }

    # Convert enums to values
    if asset.get("status") and hasattr(asset["status"], "value"):
        asset["status"] = asset["status"].value
    if asset.get("monitoring_interval") and hasattr(
        asset["monitoring_interval"], "value"
    ):
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
            after_value=asset,
        )

    asset = await enrich_asset_domain(asset)
    return AssetDomainResponse(**asset)


@router.put("/asset-domains/{asset_id}", response_model=AssetDomainResponse)
async def update_asset_domain(
    asset_id: str,
    data: AssetDomainUpdate,
    current_user: dict = Depends(get_current_user_wrapper),
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
            after_value={**existing, **update_dict},
        )

    updated = await db.asset_domains.find_one({"id": asset_id}, {"_id": 0})
    updated = await enrich_asset_domain(updated)
    return AssetDomainResponse(**updated)


@router.delete("/asset-domains/{asset_id}")
async def delete_asset_domain(
    asset_id: str, current_user: dict = Depends(get_current_user_wrapper)
):
    """Delete an asset domain - BRAND SCOPED"""
    existing = await db.asset_domains.find_one({"id": asset_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Asset domain not found")

    # Validate brand access
    require_brand_access(existing.get("brand_id", ""), current_user)

    # Check if used in structure entries
    structure_count = await db.seo_structure_entries.count_documents(
        {"$or": [{"asset_domain_id": asset_id}, {"target_asset_domain_id": asset_id}]}
    )
    if structure_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete: domain is used in {structure_count} structure entries",
        )

    await db.asset_domains.delete_one({"id": asset_id})

    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.DELETE,
            entity_type=EntityType.ASSET_DOMAIN,
            entity_id=asset_id,
            before_value=existing,
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
    current_user: dict = Depends(get_current_user_wrapper),
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

    networks = (
        await db.seo_networks.find(query, {"_id": 0})
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )

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
    brands = {
        b["id"]: b["name"]
        for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    }

    # Compute ranking metrics for each network
    result = []
    for network in networks:
        network["brand_name"] = brands.get(network.get("brand_id"))

        # Get all structure entries for this network
        entries = await db.seo_structure_entries.find(
            {"network_id": network["id"]},
            {
                "_id": 0,
                "ranking_position": 1,
                "ranking_url": 1,
                "primary_keyword": 1,
                "index_status": 1,
            },
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
            has_ranking = (pos is not None and 1 <= pos <= 100) or bool(
                ranking_url.strip()
            )
            if has_ranking:
                if pos is not None and 1 <= pos <= 100:
                    ranking_nodes.append(pos)

            # Check if tracking (has keyword/url AND indexed, but no ranking position)
            has_tracking_data = bool(primary_keyword.strip()) or bool(
                ranking_url.strip()
            )
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
        open_complaints = await db.seo_optimizations.count_documents(
            {
                "network_id": network["id"],
                "complaint_status": {"$in": ["complained", "under_review"]},
            }
        )
        network["open_complaints_count"] = open_complaints

        # Get most recent optimization date
        last_opt = await db.seo_optimizations.find_one(
            {"network_id": network["id"]},
            {"_id": 0, "created_at": 1},
            sort=[("created_at", -1)],
        )
        network["last_optimization_at"] = last_opt["created_at"] if last_opt else None

        result.append(network)

    # Filter by ranking_status if specified
    if ranking_status:
        result = [n for n in result if n.get("ranking_status") == ranking_status]

    # Sort if specified
    if sort_by == "best_position":
        # Sort by best position (ascending), None values at end
        result.sort(
            key=lambda x: (
                x.get("best_ranking_position") is None,
                x.get("best_ranking_position") or 999,
            )
        )
    elif sort_by == "ranking_nodes":
        # Sort by ranking nodes count (descending)
        result.sort(key=lambda x: x.get("ranking_nodes_count", 0), reverse=True)

    return [SeoNetworkResponse(**n) for n in result]


# ==================== NETWORK SEARCH ENDPOINT ====================


@router.get("/networks/search")
async def search_networks(
    query: str = Query(
        min_length=1,
        max_length=100,
        description="Search query for domain name or optimized path",
    ),
    current_user: dict = Depends(get_current_user_wrapper),
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
        {
            "$lookup": {
                "from": "asset_domains",
                "localField": "asset_domain_id",
                "foreignField": "id",
                "as": "domain",
            }
        },
        {"$unwind": "$domain"},
        # Search filter: match domain_name OR optimized_path
        {
            "$match": {
                "$or": [
                    {"domain.domain_name": {"$regex": search_term, "$options": "i"}},
                    {"optimized_path": {"$regex": search_term, "$options": "i"}},
                ]
            }
        },
        # Join with seo_networks to get network name and brand_id
        {
            "$lookup": {
                "from": "seo_networks",
                "localField": "network_id",
                "foreignField": "id",
                "as": "network",
            }
        },
        {"$unwind": "$network"},
    ]

    # Apply brand scoping if user is not super admin
    if brand_scope is not None:
        if not brand_scope:
            return {"results": [], "total": 0}  # No brand access
        pipeline.append({"$match": {"network.brand_id": {"$in": brand_scope}}})

    # Project the fields we need
    pipeline.extend(
        [
            {
                "$project": {
                    "_id": 0,
                    "entry_id": "$id",
                    "network_id": "$network_id",
                    "network_name": "$network.name",
                    "asset_domain_id": "$asset_domain_id",
                    "domain_name": "$domain.domain_name",
                    "optimized_path": "$optimized_path",
                    "domain_role": "$domain_role",
                    "brand_id": "$network.brand_id",
                }
            },
            # Sort for consistent results
            {"$sort": {"domain_name": 1, "optimized_path": 1}},
            # Limit results for performance
            {"$limit": 10},
        ]
    )

    results = await db.seo_structure_entries.aggregate(pipeline).to_list(10)

    # Group results by domain for better UI display
    grouped = {}
    for r in results:
        domain_name = r["domain_name"]
        if domain_name not in grouped:
            grouped[domain_name] = {
                "domain_name": domain_name,
                "asset_domain_id": r["asset_domain_id"],
                "entries": [],
            }
        grouped[domain_name]["entries"].append(
            {
                "entry_id": r["entry_id"],
                "network_id": r["network_id"],
                "network_name": r["network_name"],
                "optimized_path": r.get("optimized_path") or "/",
                "role": r["domain_role"],
            }
        )

    return {
        "results": list(grouped.values()),
        "total": len(results),
        "query": search_term,
    }


@router.get("/networks/{network_id}", response_model=SeoNetworkDetail)
async def get_network(
    network_id: str,
    include_tiers: bool = True,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get a single SEO network with structure entries and calculated tiers - BRAND SCOPED"""
    logger.info(f"[GET_NETWORK] Fetching network: {network_id}")
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        logger.warning(f"[GET_NETWORK] Network not found: {network_id}")
        raise HTTPException(status_code=404, detail="Network not found")

    logger.info(
        f"[GET_NETWORK] Found network: {network.get('name')}, visibility: {network.get('visibility_mode', 'brand_based')}"
    )

    # Validate brand access first
    require_brand_access(network.get("brand_id", ""), current_user)

    # Validate network visibility access (Restricted mode enforcement)
    await require_network_access(network, current_user)

    # Get brand name
    if network.get("brand_id"):
        brand = await db.brands.find_one(
            {"id": network["brand_id"]}, {"_id": 0, "name": 1}
        )
        network["brand_name"] = brand["name"] if brand else None
    else:
        network["brand_name"] = None

    # Get structure entries
    entries = await db.seo_structure_entries.find(
        {"network_id": network_id}, {"_id": 0}
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
    open_complaints = await db.seo_optimizations.count_documents(
        {
            "network_id": network_id,
            "complaint_status": {"$in": ["complained", "under_review"]},
        }
    )
    network["open_complaints_count"] = open_complaints

    # Get most recent optimization date
    last_opt = await db.seo_optimizations.find_one(
        {"network_id": network_id},
        {"_id": 0, "created_at": 1},
        sort=[("created_at", -1)],
    )
    network["last_optimization_at"] = last_opt["created_at"] if last_opt else None

    return SeoNetworkDetail(**network)


@router.post("/networks", response_model=SeoNetworkResponse)
async def create_network(
    data: SeoNetworkCreate, current_user: dict = Depends(get_current_user_wrapper)
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
    main_domain = await db.asset_domains.find_one(
        {"id": data.main_node.asset_domain_id}
    )
    if not main_domain:
        raise HTTPException(status_code=400, detail="Main domain not found")

    if main_domain.get("brand_id") != data.brand_id:
        raise HTTPException(
            status_code=400,
            detail="Main domain must belong to the same brand as the network",
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
        "updated_at": now,
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
        "updated_at": now,
    }

    await db.seo_structure_entries.insert_one(main_entry)

    # Log activity for network creation
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.CREATE,
            entity_type=EntityType.SEO_NETWORK,
            entity_id=network_id,
            after_value={**network, "main_node_id": main_entry["id"]},
        )

        # Log activity for main node creation
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.CREATE,
            entity_type=EntityType.SEO_STRUCTURE_ENTRY,
            entity_id=main_entry["id"],
            after_value=main_entry,
            metadata={"node_type": "main", "domain": main_domain["domain_name"]},
        )

    # Send Telegram notification for network creation
    try:
        from services.seo_telegram_service import get_seo_telegram_service

        telegram_service = get_seo_telegram_service()
        if telegram_service:
            main_node_label = (
                f"{main_domain['domain_name']}{main_path if main_path != '/' else ''}"
            )
            await telegram_service.send_network_creation_notification(
                network_id=network_id,
                network_name=data.name,
                brand_id=data.brand_id,
                actor_user_id=current_user["id"],
                actor_email=current_user["email"],
                main_node_label=main_node_label,
            )
    except Exception as e:
        logger.error(f"Failed to send network creation notification: {e}")

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
    current_user: dict = Depends(get_current_user_wrapper),
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
            after_value={**existing, **update_dict},
        )

    updated = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    updated["domain_count"] = await db.seo_structure_entries.count_documents(
        {"network_id": network_id}
    )

    if updated.get("brand_id"):
        brand = await db.brands.find_one(
            {"id": updated["brand_id"]}, {"_id": 0, "name": 1}
        )
        updated["brand_name"] = brand["name"] if brand else None
    else:
        updated["brand_name"] = None

    return SeoNetworkResponse(**updated)


@router.delete("/networks/{network_id}")
async def delete_network(
    network_id: str, current_user: dict = Depends(get_current_user_wrapper)
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
            metadata={"deleted_entries": deleted.deleted_count},
        )

    return {
        "message": f"Network deleted with {deleted.deleted_count} structure entries"
    }


# ==================== SEO STRUCTURE ENDPOINTS ====================


@router.get("/structure", response_model=List[SeoStructureEntryResponse])
async def get_structure_entries(
    network_id: Optional[str] = None,
    asset_domain_id: Optional[str] = None,
    domain_role: Optional[DomainRole] = None,
    index_status: Optional[IndexStatus] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user_wrapper),
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

    entries = (
        await db.seo_structure_entries.find(query, {"_id": 0})
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )

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
    entry_id: str, current_user: dict = Depends(get_current_user_wrapper)
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
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Create a new SEO structure entry (node-based) with mandatory change note"""
    # Validate network exists
    network = await db.seo_networks.find_one({"id": data.network_id})
    if not network:
        raise HTTPException(status_code=400, detail="Network not found")

    # PERMISSION CHECK: Only super_admin or network managers can create nodes
    await require_manager_permission(network, current_user)

    # Validate asset domain exists
    asset = await db.asset_domains.find_one({"id": data.asset_domain_id})
    if not asset:
        raise HTTPException(status_code=400, detail="Asset domain not found")

    # BRAND SCOPING: Validate domain belongs to the same brand as the network
    if asset.get("brand_id") != network.get("brand_id"):
        raise HTTPException(
            status_code=400,
            detail="Domain must belong to the same brand as the SEO Network",
        )

    # Validate target_entry_id if provided (new node-to-node relationship)
    if data.target_entry_id:
        target_entry = await db.seo_structure_entries.find_one(
            {"id": data.target_entry_id}
        )
        if not target_entry:
            raise HTTPException(status_code=400, detail="Target entry not found")
        # Ensure target entry is in the same network
        if target_entry.get("network_id") != data.network_id:
            raise HTTPException(
                status_code=400, detail="Target entry must be in the same network"
            )

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
                detail="Main (LP/Money Site) nodes cannot have a target. They are the primary target.",
            )

        # Rule 2: Main nodes MUST have PRIMARY status (not canonical/redirect)
        if data.domain_status and data.domain_status not in [SeoStatus.PRIMARY, None]:
            raise HTTPException(
                status_code=400,
                detail=f"Main nodes must have 'primary' status, not '{data.domain_status.value}'. Main nodes don't redirect to themselves.",
            )

        # Rule 3: Check if network already has a main node
        existing_main = await db.seo_structure_entries.find_one(
            {"network_id": data.network_id, "domain_role": "main"}
        )
        if existing_main:
            raise HTTPException(
                status_code=400,
                detail="Network already has a main node. Use 'Switch Main Target' to change it.",
            )

    # Normalize the optimized_path
    normalized_path = normalize_path(data.optimized_path)

    # Check for duplicate node (same domain + path in same network)
    # A node is unique by: network_id + asset_domain_id + optimized_path
    existing_query = {
        "asset_domain_id": data.asset_domain_id,
        "network_id": data.network_id,
    }
    if normalized_path:
        existing_query["optimized_path"] = normalized_path
    else:
        existing_query["$or"] = [
            {"optimized_path": None},
            {"optimized_path": ""},
            {"optimized_path": {"$exists": False}},
        ]

    existing = await db.seo_structure_entries.find_one(existing_query)
    if existing:
        path_info = f" with path '{normalized_path}'" if normalized_path else ""
        raise HTTPException(
            status_code=400, detail=f"Node{path_info} already exists in this network"
        )

    # Extract change_note before creating entry
    change_note = data.change_note

    # CRITICAL: Validate change_note BEFORE any save operation
    validate_change_note(change_note)

    now = datetime.now(timezone.utc).isoformat()
    entry_data = data.model_dump(
        exclude={"change_note"}
    )  # Exclude change_note from entry data
    entry_data["optimized_path"] = normalized_path  # Use normalized path

    entry = {
        "id": str(uuid.uuid4()),
        "legacy_domain_id": None,
        **entry_data,
        "created_at": now,
        "updated_at": now,
    }

    # Convert enums
    for field in ["domain_role", "domain_status", "index_status"]:
        if entry.get(field) and hasattr(entry[field], "value"):
            entry[field] = entry[field].value

    await db.seo_structure_entries.insert_one(entry)

    # Build node label for logging
    node_label = f"{asset['domain_name']}{normalized_path or ''}"

    # ATOMIC: Log + Telegram notification (both must succeed conceptually)
    notification_success, change_log_id, error_msg = (
        await atomic_seo_change_with_notification(
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
            entry_id=entry["id"],
        )
    )

    # Log system activity (separate from SEO change log)
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.CREATE,
            entity_type=EntityType.SEO_STRUCTURE_ENTRY,
            entity_id=entry["id"],
            after_value=entry,
        )

    entry = await enrich_structure_entry(entry)
    return SeoStructureEntryResponse(**entry)


@router.put("/structure/{entry_id}", response_model=SeoStructureEntryResponse)
async def update_structure_entry(
    entry_id: str,
    data: SeoStructureEntryUpdateWithNote,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Update an SEO structure entry (node-based) with mandatory change note"""
    existing = await db.seo_structure_entries.find_one({"id": entry_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Structure entry not found")

    # PERMISSION CHECK: Only super_admin or network managers can update nodes
    network = await db.seo_networks.find_one({"id": existing.get("network_id")}, {"_id": 0})
    if network:
        await require_manager_permission(network, current_user)
    else:
        raise HTTPException(status_code=404, detail="Network not found for this entry")

    # Extract and remove change_note from update_dict
    change_note = data.change_note

    # CRITICAL: Validate change_note BEFORE any save operation
    validate_change_note(change_note)

    update_dict = {
        k: v
        for k, v in data.model_dump(exclude={"change_note"}).items()
        if v is not None
    }

    # Normalize optimized_path if provided
    if "optimized_path" in update_dict:
        update_dict["optimized_path"] = normalize_path(update_dict["optimized_path"])

    # ========================================================================
    # CRITICAL: STRICT DIFF VALIDATION - PREVENT NO-CHANGE SAVES
    # ========================================================================
    # Fields that constitute an actual data change (change_note excluded)
    TRACKED_FIELDS = [
        "domain_role",
        "domain_status", 
        "index_status",
        "target_entry_id",
        "target_asset_domain_id",
        "optimized_path",
        "ranking_url",
        "primary_keyword",
        "ranking_position",
        "notes",
    ]
    
    changed_fields = []
    for field in TRACKED_FIELDS:
        if field in update_dict:
            old_value = existing.get(field)
            new_value = update_dict[field]
            
            # Handle enum comparison
            if hasattr(new_value, "value"):
                new_value = new_value.value
            
            # Normalize None vs empty string
            if old_value is None:
                old_value = ""
            if new_value is None:
                new_value = ""
            
            # Check if actually different
            if str(old_value) != str(new_value):
                changed_fields.append({
                    "field": field,
                    "old": old_value,
                    "new": new_value
                })
    
    # REJECT if no actual changes detected
    if len(changed_fields) == 0:
        raise HTTPException(
            status_code=400,
            detail="No changes detected. Please modify at least one field before saving."
        )
    
    logger.info(f"SEO node update - {len(changed_fields)} field(s) changed: {[c['field'] for c in changed_fields]}")
    # ========================================================================

    # Validate target_entry_id if changing (node-to-node relationship)
    if "target_entry_id" in update_dict and update_dict["target_entry_id"]:
        target_entry = await db.seo_structure_entries.find_one(
            {"id": update_dict["target_entry_id"]}
        )
        if not target_entry:
            raise HTTPException(status_code=400, detail="Target entry not found")
        # Prevent self-reference
        if update_dict["target_entry_id"] == entry_id:
            raise HTTPException(status_code=400, detail="Entry cannot target itself")
        # Ensure same network
        if target_entry.get("network_id") != existing.get("network_id"):
            raise HTTPException(
                status_code=400, detail="Target entry must be in the same network"
            )

    # Validate target domain if changing (legacy support)
    if (
        "target_asset_domain_id" in update_dict
        and update_dict["target_asset_domain_id"]
    ):
        target = await db.asset_domains.find_one(
            {"id": update_dict["target_asset_domain_id"]}
        )
        if not target:
            raise HTTPException(status_code=400, detail="Target asset domain not found")

    # === MAIN NODE VALIDATION RULES ===
    # Determine the effective role after update
    new_role = update_dict.get("domain_role", existing.get("domain_role"))
    new_status = update_dict.get("domain_status", existing.get("domain_status"))
    new_target = update_dict.get("target_entry_id", existing.get("target_entry_id"))
    new_target_domain = update_dict.get(
        "target_asset_domain_id", existing.get("target_asset_domain_id")
    )

    if new_role == "main" or new_role == DomainRole.MAIN:
        # Rule 1: Main nodes MUST NOT have a target
        if new_target or new_target_domain:
            raise HTTPException(
                status_code=400,
                detail="Main (LP/Money Site) nodes cannot have a target. They are the primary target.",
            )

        # Rule 2: Main nodes MUST have PRIMARY status
        if new_status and new_status not in ["primary", SeoStatus.PRIMARY]:
            raise HTTPException(
                status_code=400,
                detail=f"Main nodes must have 'primary' status, not '{new_status}'. Main nodes don't redirect to themselves.",
            )

        # Rule 3: Check if changing TO main role, and another main already exists
        if existing.get("domain_role") != "main" and (
            new_role == "main" or new_role == DomainRole.MAIN
        ):
            existing_main = await db.seo_structure_entries.find_one(
                {
                    "network_id": existing["network_id"],
                    "domain_role": "main",
                    "id": {"$ne": entry_id},
                }
            )
            if existing_main:
                raise HTTPException(
                    status_code=400,
                    detail="Network already has a main node. Use 'Switch Main Target' to change it safely.",
                )

    # Convert enums
    for field in ["domain_role", "domain_status", "index_status"]:
        if field in update_dict and hasattr(update_dict[field], "value"):
            update_dict[field] = update_dict[field].value

    update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.seo_structure_entries.update_one({"id": entry_id}, {"$set": update_dict})

    # Get domain info for node label
    domain = await db.asset_domains.find_one(
        {"id": existing["asset_domain_id"]}, {"_id": 0, "domain_name": 1}
    )
    domain_name = domain["domain_name"] if domain else "unknown"
    node_label = f"{domain_name}{existing.get('optimized_path', '') or ''}"

    # Get network for brand_id
    network = await db.seo_networks.find_one(
        {"id": existing["network_id"]}, {"_id": 0, "brand_id": 1}
    )
    brand_id = network.get("brand_id", "") if network else ""

    # Determine action type based on what changed
    after_snapshot = {**existing, **update_dict}
    action_type_str = "update_node"
    action_type = None
    if seo_change_log_service:
        action_type = seo_change_log_service.determine_action_type(
            is_create=False, is_delete=False, before=existing, after=after_snapshot
        )
        action_type_str = (
            action_type.value if hasattr(action_type, "value") else action_type
        )

    # ATOMIC: Log + Telegram notification
    notification_success, change_log_id, error_msg = (
        await atomic_seo_change_with_notification(
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
            entry_id=entry_id,
        )
    )

    # Log system activity (separate from SEO change log)
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.SEO_STRUCTURE_ENTRY,
            entity_id=entry_id,
            before_value=existing,
            after_value=after_snapshot,
        )

    # Return the updated entry
    updated_entry = await db.seo_structure_entries.find_one(
        {"id": entry_id}, {"_id": 0}
    )
    if not updated_entry:
        raise HTTPException(status_code=500, detail="Failed to retrieve updated entry")

    # Enrich with domain info
    domain = await db.asset_domains.find_one(
        {"id": updated_entry["asset_domain_id"]},
        {"_id": 0, "domain_name": 1, "brand_id": 1},
    )
    if domain:
        updated_entry["domain_name"] = domain.get("domain_name")
        updated_entry["brand_id"] = domain.get("brand_id")

    return updated_entry


# ==================== SEO OPTIMIZATIONS ENDPOINTS ====================


@router.get("/networks/{network_id}/optimizations")
async def get_network_optimizations(
    network_id: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    activity_type: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper),
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
    optimizations = (
        await db.seo_optimizations.find(query, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )

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
            "total_pages": total_pages,
        },
    }


@router.get("/networks/{network_id}/optimizations/export")
async def export_network_optimizations_csv(
    network_id: str,
    status: Optional[str] = None,
    activity_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper),
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

    optimizations = (
        await db.seo_optimizations.find(query, {"_id": 0})
        .sort("created_at", -1)
        .to_list(1000)
    )

    # Get complaint counts
    complaint_counts = {}
    for opt in optimizations:
        count = await db.optimization_complaints.count_documents(
            {"optimization_id": opt["id"]}
        )
        complaint_counts[opt["id"]] = count

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(
        [
            "ID",
            "Title",
            "Activity Type",
            "Status",
            "Complaint Status",
            "Created By",
            "Created At",
            "Updated At",
            "Closed At",
            "Closed By",
            "Description",
            "Reason Note",
            "Affected Scope",
            "Target Domains",
            "Keywords",
            "Expected Impact",
            "Observed Impact",
            "Complaints Count",
            "Report URLs",
        ]
    )

    # Data rows
    for opt in optimizations:
        writer.writerow(
            [
                opt["id"],
                opt["title"],
                opt.get("activity_type", ""),
                opt["status"],
                opt.get("complaint_status", "none"),
                opt.get("created_by", {}).get("display_name", ""),
                opt.get("created_at", ""),
                opt.get("updated_at", ""),
                opt.get("closed_at", ""),
                (
                    opt.get("closed_by", {}).get("display_name", "")
                    if opt.get("closed_by")
                    else ""
                ),
                opt.get("description", ""),
                opt.get("reason_note", ""),
                opt.get("affected_scope", ""),
                "|".join(opt.get("target_domains", [])),
                "|".join(opt.get("keywords", [])),
                "|".join(opt.get("expected_impact", [])),
                opt.get("observed_impact", ""),
                complaint_counts.get(opt["id"], 0),
                "|".join(
                    [
                        r.get("url", r) if isinstance(r, dict) else r
                        for r in opt.get("report_urls", [])
                    ]
                ),
            ]
        )

    output.seek(0)

    # Filename
    network_name = network.get("name", "network").replace(" ", "_")
    filename = f"optimizations_{network_name}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post(
    "/networks/{network_id}/optimizations", response_model=SeoOptimizationResponse
)
async def create_network_optimization(
    network_id: str,
    data: SeoOptimizationCreate,
    current_user: dict = Depends(get_current_user_wrapper),
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
            detail="Reason note is required (minimum 20 characters). Please explain why this optimization is being done.",
        )

    # Resolve activity type
    activity_type_str = data.activity_type or "other"
    activity_type_name = None
    if data.activity_type_id:
        activity_type_doc = await db.seo_optimization_activity_types.find_one(
            {"id": data.activity_type_id}, {"_id": 0}
        )
        if activity_type_doc:
            activity_type_str = (
                activity_type_doc.get("name", "other").lower().replace(" ", "_")
            )
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
                raise HTTPException(
                    status_code=400, detail="Report URL is required for each entry"
                )
            if not url_entry.get("start_date"):
                raise HTTPException(
                    status_code=400,
                    detail="Report start date is required for each entry",
                )
            report_urls_data.append(url_entry)
        else:
            # Pydantic model
            entry_dict = (
                url_entry.model_dump()
                if hasattr(url_entry, "model_dump")
                else dict(url_entry)
            )
            if not entry_dict.get("url"):
                raise HTTPException(
                    status_code=400, detail="Report URL is required for each entry"
                )
            if not entry_dict.get("start_date"):
                raise HTTPException(
                    status_code=400,
                    detail="Report start date is required for each entry",
                )
            report_urls_data.append(entry_dict)

    optimization = {
        "id": str(uuid.uuid4()),
        "network_id": network_id,
        "brand_id": network["brand_id"],
        "created_by": {
            "user_id": current_user["id"],
            "display_name": current_user.get(
                "name", current_user["email"].split("@")[0].title()
            ),
            "email": current_user["email"],
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
        "telegram_notified_at": None,
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
            after_value={
                "title": optimization["title"],
                "activity_type": optimization["activity_type"],
                "reason_note": optimization["reason_note"],
            },
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
    current_user: dict = Depends(get_current_user_wrapper),
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
    current_user: dict = Depends(get_current_user_wrapper),
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

    return {"data": digest, "formatted_message": message}


@router.get("/optimizations/ai-summary")
async def get_ai_optimization_summary(
    network_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    days: int = Query(default=7, ge=1, le=30),
    current_user: dict = Depends(get_current_user_wrapper),
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
    optimization_id: str, current_user: dict = Depends(get_current_user_wrapper)
):
    """Get a single SEO optimization by ID"""
    optimization = await db.seo_optimizations.find_one(
        {"id": optimization_id}, {"_id": 0}
    )
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    require_brand_access(optimization["brand_id"], current_user)

    # Enrich with network and brand names
    network = await db.seo_networks.find_one(
        {"id": optimization["network_id"]}, {"_id": 0, "name": 1}
    )
    brand = await db.brands.find_one(
        {"id": optimization["brand_id"]}, {"_id": 0, "name": 1}
    )

    optimization["network_name"] = network["name"] if network else "Unknown"
    optimization["brand_name"] = brand["name"] if brand else "Unknown"

    return SeoOptimizationResponse(**optimization)


@router.put("/optimizations/{optimization_id}", response_model=SeoOptimizationResponse)
async def update_optimization(
    optimization_id: str,
    data: SeoOptimizationUpdate,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Update an SEO optimization activity.
    Sends Telegram notification if status changes to COMPLETED or REVERTED.

    Only Managers or Super Admin can update optimizations.
    """
    optimization = await db.seo_optimizations.find_one(
        {"id": optimization_id}, {"_id": 0}
    )
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    require_brand_access(optimization["brand_id"], current_user)

    # Get network to check manager permission
    network = await db.seo_networks.find_one(
        {"id": optimization["network_id"]}, {"_id": 0}
    )
    if network:
        await require_manager_permission(network, current_user)

    old_status = optimization.get("status")

    # Build update dict
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if data.activity_type is not None:
        # Handle both string and Enum types
        update_data["activity_type"] = data.activity_type.value if hasattr(data.activity_type, 'value') else data.activity_type
    if data.title is not None:
        if not data.title.strip():
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        update_data["title"] = data.title.strip()
    if data.description is not None:
        if not data.description.strip():
            raise HTTPException(status_code=400, detail="Description cannot be empty")
        update_data["description"] = data.description.strip()
    if data.affected_scope is not None:
        # Handle both string and Enum types
        update_data["affected_scope"] = data.affected_scope.value if hasattr(data.affected_scope, 'value') else data.affected_scope
    if data.target_domains is not None:
        update_data["target_domains"] = data.target_domains
    if data.keywords is not None:
        update_data["keywords"] = data.keywords
    if data.report_urls is not None:
        update_data["report_urls"] = data.report_urls
    if data.expected_impact is not None:
        # Handle both string and Enum types in list
        update_data["expected_impact"] = [i.value if hasattr(i, 'value') else i for i in data.expected_impact]
    if data.status is not None:
        # Handle both string and Enum types
        update_data["status"] = data.status.value if hasattr(data.status, 'value') else data.status

    await db.seo_optimizations.update_one(
        {"id": optimization_id}, {"$set": update_data}
    )

    # Get updated optimization
    updated_optimization = await db.seo_optimizations.find_one(
        {"id": optimization_id}, {"_id": 0}
    )

    # Check if status changed to completed or reverted
    new_status = update_data.get("status", old_status)
    
    # AUTO-SYNC: Update linked conflict status when optimization status changes
    linked_conflict_id = optimization.get("linked_conflict_id")
    if linked_conflict_id and new_status != old_status:
        conflict_update = {"updated_at": datetime.now(timezone.utc).isoformat()}
        
        if new_status == "completed":
            # When optimization is completed, mark conflict as RESOLVED and INACTIVE
            conflict_update["status"] = "resolved"
            conflict_update["is_active"] = False  # P0: Deactivate to remove from recurring list
            conflict_update["resolved_at"] = datetime.now(timezone.utc).isoformat()
            conflict_update["resolved_by"] = current_user.get("id")
            
            # Send resolution notification
            try:
                conflict = await db.seo_conflicts.find_one({"id": linked_conflict_id}, {"_id": 0})
                if conflict:
                    from services.conflict_optimization_linker_service import get_conflict_linker_service
                    linker_service = get_conflict_linker_service(db)
                    await linker_service._send_resolution_notification(conflict, current_user.get("id", ""))
            except Exception as e:
                logger.warning(f"Failed to send conflict resolution notification: {e}")
                
        elif new_status == "in_progress":
            # Confirm under_review status when work starts
            conflict_update["status"] = "under_review"
            
        elif new_status == "reverted":
            # If optimization is reverted, conflict goes back to detected and becomes active again
            conflict_update["status"] = "detected"
            conflict_update["is_active"] = True  # Reactivate on revert
            conflict_update["resolved_at"] = None
            conflict_update["resolved_by"] = None
        
        await db.seo_conflicts.update_one(
            {"id": linked_conflict_id},
            {"$set": conflict_update}
        )
        logger.info(f"Synced conflict {linked_conflict_id} status to match optimization status change to {new_status}")
    
    if new_status != old_status and new_status in ["completed", "reverted"]:
        # Get network and brand for notification
        network = await db.seo_networks.find_one(
            {"id": optimization["network_id"]}, {"_id": 0}
        )
        brand = await db.brands.find_one({"id": optimization["brand_id"]}, {"_id": 0})

        try:
            telegram_service = SeoOptimizationTelegramService(db)
            await telegram_service.send_status_change_notification(
                updated_optimization,
                network or {},
                brand or {},
                old_status,
                new_status,
                current_user,
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
            after_value=update_data,
        )

    # Enrich response
    network = await db.seo_networks.find_one(
        {"id": updated_optimization["network_id"]}, {"_id": 0, "name": 1}
    )
    brand = await db.brands.find_one(
        {"id": updated_optimization["brand_id"]}, {"_id": 0, "name": 1}
    )
    updated_optimization["network_name"] = network["name"] if network else "Unknown"
    updated_optimization["brand_name"] = brand["name"] if brand else "Unknown"

    return SeoOptimizationResponse(**updated_optimization)


@router.delete("/optimizations/{optimization_id}")
async def delete_optimization(
    optimization_id: str, current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Delete an SEO optimization activity.
    CRITICAL: Only Super Admin can delete optimizations.
    Optimizations are audit records - deletion by regular users breaks accountability.
    
    If the optimization has a linked conflict, the conflict will be reset to 'detected'
    status and can have a new optimization created for it.
    """
    # CRITICAL: Only Super Admin can delete optimizations
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=403,
            detail="Only Super Admin can delete optimization records. Optimizations are audit records that must be preserved.",
        )

    optimization = await db.seo_optimizations.find_one(
        {"id": optimization_id}, {"_id": 0}
    )
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    # Handle linked conflict - reset it back to detected
    linked_conflict_id = optimization.get("linked_conflict_id")
    if linked_conflict_id:
        await db.seo_conflicts.update_one(
            {"id": linked_conflict_id},
            {"$set": {
                "status": "detected",
                "optimization_id": None,
                "resolved_at": None,
                "resolved_by": None,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        logger.info(f"Reset conflict {linked_conflict_id} to 'detected' due to optimization deletion")

    await db.seo_optimizations.delete_one({"id": optimization_id})

    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.DELETE,
            entity_type=EntityType.SEO_OPTIMIZATION,
            entity_id=optimization_id,
            before_value={
                "title": optimization.get("title"),
                "deleted_by": "super_admin",
                "had_linked_conflict": linked_conflict_id is not None,
            },
        )

    return {"message": "Optimization deleted", "conflict_reset": linked_conflict_id is not None}


# ==================== OPTIMIZATION COMPLAINTS ====================


@router.post(
    "/optimizations/{optimization_id}/complaints",
    response_model=OptimizationComplaintResponse,
)
async def create_optimization_complaint(
    optimization_id: str,
    data: OptimizationComplaintCreate,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Create a complaint on an SEO optimization.
    Only Super Admin can create complaints.
    Automatically tags assigned users from network Access Summary via Telegram.
    """
    # Only Super Admin can create complaints
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=403, detail="Only Super Admin can create complaints"
        )

    optimization = await db.seo_optimizations.find_one(
        {"id": optimization_id}, {"_id": 0}
    )
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    # Validate required field
    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=400, detail="Complaint reason is required")

    # Get network to access managers from SEO Network Management
    network = await db.seo_networks.find_one(
        {"id": optimization["network_id"]}, {"_id": 0}
    )

    # Build responsible user list: combine explicit selection + network managers
    all_responsible_user_ids = set(data.responsible_user_ids or [])

    # Auto-add managers from network (they are responsible for execution)
    if network and network.get("manager_ids"):
        all_responsible_user_ids.update(network["manager_ids"])
        logger.info(
            f"[COMPLAINT] Auto-added {len(network['manager_ids'])} managers from SEO Network Management"
        )

    # Get responsible users info for notification
    responsible_users = []
    if all_responsible_user_ids:
        users = await db.users.find(
            {"id": {"$in": list(all_responsible_user_ids)}},
            {"_id": 0, "id": 1, "email": 1, "name": 1, "telegram_username": 1},
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
            "display_name": current_user.get(
                "name", current_user["email"].split("@")[0].title()
            ),
            "email": current_user["email"],
        },
        "created_at": now,
        "reason": data.reason.strip(),
        "responsible_user_ids": list(
            all_responsible_user_ids
        ),  # Store all responsible users
        "explicit_responsible_user_ids": data.responsible_user_ids
        or [],  # Explicitly selected users
        "auto_assigned_from_network": (
            True
            if network and network.get("visibility_mode") == "restricted"
            else False
        ),
        "priority": data.priority.value if data.priority else "medium",
        "report_urls": data.report_urls,
        "status": "open",
        "telegram_notified_at": None,
    }

    await db.optimization_complaints.insert_one(complaint)

    # Update optimization complaints count AND complaint_status
    await db.seo_optimizations.update_one(
        {"id": optimization_id},
        {
            "$inc": {"complaints_count": 1},
            "$set": {"complaint_status": "complained", "updated_at": now},
        },
    )

    # Get network and brand for notification
    network = await db.seo_networks.find_one(
        {"id": optimization["network_id"]}, {"_id": 0}
    )
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
            after_value={
                "action": "complaint_created",
                "complaint_id": complaint["id"],
                "priority": complaint["priority"],
            },
        )

    complaint["responsible_users"] = responsible_users
    return OptimizationComplaintResponse(**complaint)


@router.get("/optimizations/{optimization_id}/complaints")
async def get_optimization_complaints(
    optimization_id: str, current_user: dict = Depends(get_current_user_wrapper)
):
    """Get all complaints for an optimization"""
    optimization = await db.seo_optimizations.find_one(
        {"id": optimization_id}, {"_id": 0}
    )
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    require_brand_access(optimization["brand_id"], current_user)

    complaints = (
        await db.optimization_complaints.find(
            {"optimization_id": optimization_id}, {"_id": 0}
        )
        .sort("created_at", -1)
        .to_list(100)
    )

    # Enrich with responsible users
    for complaint in complaints:
        if complaint.get("responsible_user_ids"):
            users = await db.users.find(
                {"id": {"$in": complaint["responsible_user_ids"]}},
                {"_id": 0, "id": 1, "email": 1, "name": 1, "telegram_username": 1},
            ).to_list(100)
            complaint["responsible_users"] = users
        else:
            complaint["responsible_users"] = []

    return complaints


# ==================== PROJECT-LEVEL COMPLAINTS ====================


@router.post(
    "/networks/{network_id}/complaints", response_model=ProjectComplaintResponse
)
async def create_project_complaint(
    network_id: str,
    data: ProjectComplaintCreate,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Create a project-level complaint (not tied to a specific optimization).
    Only Super Admin can create project-level complaints.
    """
    # Only Super Admin can create complaints
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=403, detail="Only Super Admin can create project complaints"
        )

    # Validate network exists and get brand
    network = await db.seo_networks.find_one(
        {"id": network_id}, {"_id": 0, "brand_id": 1, "name": 1}
    )
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")

    # Validate brand access
    require_brand_access(network["brand_id"], current_user)

    # Validate reason length
    if len(data.reason.strip()) < 10:
        raise HTTPException(
            status_code=400, detail="Complaint reason must be at least 10 characters"
        )

    # Enrich responsible users
    responsible_users = []
    if data.responsible_user_ids:
        users = await db.users.find(
            {"id": {"$in": data.responsible_user_ids}},
            {"_id": 0, "id": 1, "name": 1, "email": 1, "telegram_username": 1},
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
            "email": current_user.get("email"),
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
        "responses": [],
    }

    await db.project_complaints.insert_one(complaint)

    # Send Telegram notification
    try:
        telegram_service = SeoOptimizationTelegramService(db)
        await telegram_service.send_project_complaint_notification(
            complaint=complaint,
            network_name=network["name"],
            responsible_users=responsible_users,
        )
    except Exception as e:
        logger.error(f"Failed to send project complaint Telegram notification: {e}")

    # Create in-app notifications for all tagged users
    for user_id in data.responsible_user_ids:
        try:
            await create_user_notification(
                user_id=user_id,
                notification_type="complaint_tagged",
                title=f"📢 New Complaint: {network['name']}",
                message=f"You have been tagged in a project complaint. Reason: {data.reason[:100]}...",
                link=f"/groups/{network_id}?tab=complaints",
                metadata={
                    "complaint_id": complaint["id"],
                    "network_id": network_id,
                    "network_name": network["name"],
                    "created_by": current_user.get("name") or current_user.get("email"),
                }
            )
        except Exception as e:
            logger.error(f"Failed to create notification for user {user_id}: {e}")

    return ProjectComplaintResponse(**complaint)


@router.get(
    "/networks/{network_id}/complaints", response_model=List[ProjectComplaintResponse]
)
async def get_project_complaints(
    network_id: str,
    status: Optional[str] = None,  # open, under_review, resolved, dismissed
    limit: int = 50,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get all project-level complaints for a network.
    """
    # Validate network exists
    network = await db.seo_networks.find_one(
        {"id": network_id}, {"_id": 0, "brand_id": 1}
    )
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")

    require_brand_access(network["brand_id"], current_user)

    query = {"network_id": network_id}
    if status:
        query["status"] = status

    complaints = (
        await db.project_complaints.find(query, {"_id": 0})
        .sort("created_at", -1)
        .to_list(limit)
    )

    return [ProjectComplaintResponse(**c) for c in complaints]


@router.post("/networks/{network_id}/complaints/{complaint_id}/respond")
async def respond_to_project_complaint(
    network_id: str,
    complaint_id: str,
    data: TeamResponseCreate,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Add a response to a project-level complaint.
    Managers and Super Admin can respond.
    """
    # Validate complaint exists
    complaint = await db.project_complaints.find_one(
        {"id": complaint_id, "network_id": network_id}, {"_id": 0}
    )
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    require_brand_access(complaint["brand_id"], current_user)

    # Validate note length
    if len(data.note.strip()) < 20:
        raise HTTPException(
            status_code=400, detail="Response must be at least 20 characters"
        )

    # Create response entry
    response_entry = {
        "id": str(uuid.uuid4()),
        "created_by": {
            "user_id": current_user["id"],
            "display_name": current_user.get("name") or current_user.get("email"),
            "email": current_user.get("email"),
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": data.note.strip(),
        "report_urls": data.report_urls or [],
    }

    # Update complaint with response and set to under_review if currently open
    update_data = {"$push": {"responses": response_entry}}
    if complaint.get("status") == "open":
        update_data["$set"] = {"status": "under_review"}

    await db.project_complaints.update_one({"id": complaint_id}, update_data)

    return {
        "message": "Response added successfully",
        "response_id": response_entry["id"],
    }


@router.patch("/networks/{network_id}/complaints/{complaint_id}/resolve")
async def resolve_project_complaint(
    network_id: str,
    complaint_id: str,
    data: ProjectComplaintResolveRequest,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Resolve a project-level complaint. Super Admin only.
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=403, detail="Only Super Admin can resolve complaints"
        )

    # Validate complaint exists
    complaint = await db.project_complaints.find_one(
        {"id": complaint_id, "network_id": network_id}, {"_id": 0}
    )
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    if len(data.resolution_note.strip()) < 10:
        raise HTTPException(
            status_code=400, detail="Resolution note must be at least 10 characters"
        )

    await db.project_complaints.update_one(
        {"id": complaint_id},
        {
            "$set": {
                "status": "resolved",
                "resolved_at": datetime.now(timezone.utc).isoformat(),
                "resolved_by": {
                    "user_id": current_user["id"],
                    "display_name": current_user.get("name")
                    or current_user.get("email"),
                    "email": current_user.get("email"),
                },
                "resolution_note": data.resolution_note.strip(),
            }
        },
    )

    return {"message": "Complaint resolved successfully"}


# ==================== OPTIMIZATION DETAIL & RESPONSE ENDPOINTS ====================


@router.get(
    "/optimizations/{optimization_id}/detail",
    response_model=SeoOptimizationDetailResponse,
)
async def get_optimization_detail(
    optimization_id: str, current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Get full optimization detail including complaints and responses.
    Used for the Optimization Detail drawer/page.
    """
    optimization = await db.seo_optimizations.find_one(
        {"id": optimization_id}, {"_id": 0}
    )
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    require_brand_access(optimization["brand_id"], current_user)

    # Get network and brand names
    network = await db.seo_networks.find_one(
        {"id": optimization["network_id"]}, {"_id": 0, "name": 1}
    )
    brand = await db.brands.find_one(
        {"id": optimization["brand_id"]}, {"_id": 0, "name": 1}
    )

    # Get all complaints sorted by date (newest first)
    complaints = (
        await db.optimization_complaints.find(
            {"optimization_id": optimization_id}, {"_id": 0}
        )
        .sort("created_at", -1)
        .to_list(100)
    )

    # Enrich complaints with user info
    for complaint in complaints:
        if complaint.get("responsible_user_ids"):
            users = await db.users.find(
                {"id": {"$in": complaint["responsible_user_ids"]}},
                {"_id": 0, "id": 1, "email": 1, "name": 1, "telegram_username": 1},
            ).to_list(100)
            complaint["responsible_users"] = users
        else:
            complaint["responsible_users"] = []

        # Calculate time to resolution if resolved
        if complaint.get("resolved_at") and complaint.get("created_at"):
            try:
                created = datetime.fromisoformat(
                    complaint["created_at"].replace("Z", "+00:00")
                )
                resolved = datetime.fromisoformat(
                    complaint["resolved_at"].replace("Z", "+00:00")
                )
                complaint["time_to_resolution_hours"] = (
                    resolved - created
                ).total_seconds() / 3600
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

    # Get linked conflict info if this is a conflict resolution optimization
    linked_conflict = None
    linked_conflict_id = optimization.get("linked_conflict_id")
    if linked_conflict_id:
        conflict = await db.seo_conflicts.find_one(
            {"id": linked_conflict_id},
            {"_id": 0}
        )
        if conflict:
            linked_conflict = {
                "id": conflict.get("id"),
                "conflict_type": conflict.get("conflict_type"),
                "severity": conflict.get("severity"),
                "status": conflict.get("status"),
                "detected_at": conflict.get("detected_at"),
                "domain_name": conflict.get("domain_name"),
                "node_a_label": conflict.get("node_a_label"),
                "node_b_label": conflict.get("node_b_label"),
                "description": conflict.get("description"),
                "affected_nodes": conflict.get("affected_nodes", []),
                "recurrence_count": conflict.get("recurrence_count", 0),
            }

    # Permission check - only managers can edit conflict resolution
    user_role = current_user.get("role", "user")
    is_manager = user_role in ["super_admin", "admin"]
    
    # Check if user is network manager
    if not is_manager and network:
        network_full = await db.seo_networks.find_one(
            {"id": optimization["network_id"]},
            {"_id": 0, "access_control": 1}
        )
        if network_full:
            access_control = network_full.get("access_control", {})
            manager_ids = access_control.get("manager_ids", [])
            if current_user.get("id") in manager_ids:
                is_manager = True
    
    can_edit = is_manager  # Non-managers can only view

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
        linked_conflict_id=linked_conflict_id,
        linked_conflict=linked_conflict,
        network_name=network.get("name") if network else None,
        brand_name=brand.get("name") if brand else None,
        complaints=complaints,
        active_complaint=active_complaint,
        responses=responses,
        complaints_count=len(complaints),
        has_repeated_issue=len(complaints) >= 2,
        is_blocked=is_blocked,
        blocked_reason=blocked_reason,
        can_edit=can_edit,
    )


@router.post("/optimizations/{optimization_id}/responses")
async def add_team_response(
    optimization_id: str,
    data: TeamResponseCreate,
    current_user: dict = Depends(get_current_user_wrapper),
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
        raise HTTPException(
            status_code=400, detail="Response note must be at least 20 characters"
        )
    if len(data.note.strip()) > 2000:
        raise HTTPException(
            status_code=400, detail="Response note cannot exceed 2000 characters"
        )

    optimization = await db.seo_optimizations.find_one(
        {"id": optimization_id}, {"_id": 0}
    )
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    require_brand_access(optimization["brand_id"], current_user)

    # Check manager permission - only managers can respond to complaints
    network = await db.seo_networks.find_one(
        {"id": optimization["network_id"]}, {"_id": 0}
    )
    if network:
        await require_manager_permission(network, current_user)

    # Create response entry
    response_entry = {
        "id": str(uuid.uuid4()),
        "created_by": {
            "user_id": current_user["id"],
            "display_name": current_user.get(
                "name", current_user["email"].split("@")[0]
            ),
            "email": current_user["email"],
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "note": data.note.strip(),
        "report_urls": data.report_urls,
    }

    # Find active complaint to link
    active_complaint = await db.optimization_complaints.find_one(
        {
            "optimization_id": optimization_id,
            "status": {"$in": ["open", "under_review"]},
        },
        {"_id": 0, "id": 1},
    )
    if active_complaint:
        response_entry["complaint_id"] = active_complaint["id"]

    # Update optimization
    update_data = {
        "$push": {"responses": response_entry},
        "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
    }

    # If complaint status is 'complained', move to 'under_review'
    if optimization.get("complaint_status") == "complained":
        update_data["$set"]["complaint_status"] = "under_review"

        # Also update the complaint record
        if active_complaint:
            await db.optimization_complaints.update_one(
                {"id": active_complaint["id"]}, {"$set": {"status": "under_review"}}
            )

    await db.seo_optimizations.update_one({"id": optimization_id}, update_data)

    # Send Telegram notification
    try:
        from services.seo_optimization_telegram_service import (
            seo_optimization_telegram_service,
        )

        if seo_optimization_telegram_service:
            network = await db.seo_networks.find_one(
                {"id": optimization["network_id"]}, {"_id": 0, "name": 1}
            )
            brand = await db.brands.find_one(
                {"id": optimization["brand_id"]}, {"_id": 0, "name": 1}
            )

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
            after_value={
                "action": "team_response_added",
                "response_id": response_entry["id"],
            },
        )

    return {
        "message": "Response added successfully",
        "response": response_entry,
        "complaint_status": optimization.get("complaint_status", "none"),
    }


@router.patch("/optimizations/{optimization_id}/complaints/{complaint_id}/resolve")
async def resolve_complaint(
    optimization_id: str,
    complaint_id: str,
    data: ComplaintResolveRequest,
    current_user: dict = Depends(get_current_user_wrapper),
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
        raise HTTPException(
            status_code=403, detail="Only Super Admin can resolve complaints"
        )

    if len(data.resolution_note.strip()) < 10:
        raise HTTPException(
            status_code=400, detail="Resolution note must be at least 10 characters"
        )

    optimization = await db.seo_optimizations.find_one(
        {"id": optimization_id}, {"_id": 0}
    )
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    complaint = await db.optimization_complaints.find_one(
        {"id": complaint_id}, {"_id": 0}
    )
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
        {
            "$set": {
                "status": "resolved",
                "resolved_at": now,
                "resolved_by": {
                    "user_id": current_user["id"],
                    "display_name": current_user.get(
                        "name", current_user["email"].split("@")[0]
                    ),
                    "email": current_user["email"],
                },
                "resolution_note": data.resolution_note.strip(),
                "time_to_resolution_hours": time_to_resolution_hours,
            }
        },
    )

    # Check if there are other unresolved complaints
    other_complaints = await db.optimization_complaints.count_documents(
        {
            "optimization_id": optimization_id,
            "id": {"$ne": complaint_id},
            "status": {"$in": ["open", "under_review"]},
        }
    )

    # Update optimization status
    opt_update = {
        "updated_at": now,
        "complaint_status": "none" if other_complaints == 0 else "complained",
    }

    if data.mark_optimization_complete and other_complaints == 0:
        opt_update["status"] = "completed"
        opt_update["closed_at"] = now
        opt_update["closed_by"] = {
            "user_id": current_user["id"],
            "display_name": current_user.get(
                "name", current_user["email"].split("@")[0]
            ),
            "email": current_user["email"],
        }

    await db.seo_optimizations.update_one({"id": optimization_id}, {"$set": opt_update})

    # Send Telegram notification
    try:
        from services.seo_optimization_telegram_service import (
            seo_optimization_telegram_service,
        )

        if seo_optimization_telegram_service:
            network = await db.seo_networks.find_one(
                {"id": optimization["network_id"]}, {"_id": 0, "name": 1}
            )
            brand = await db.brands.find_one(
                {"id": optimization["brand_id"]}, {"_id": 0, "name": 1}
            )

            status_text = (
                "✅ RESOLVED & COMPLETED"
                if data.mark_optimization_complete
                else "✅ RESOLVED"
            )

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
                "marked_complete": data.mark_optimization_complete,
            },
        )

    return {
        "message": "Complaint resolved successfully",
        "time_to_resolution_hours": time_to_resolution_hours,
        "optimization_status": (
            "completed" if data.mark_optimization_complete else optimization["status"]
        ),
        "remaining_complaints": other_complaints,
    }


@router.patch("/optimizations/{optimization_id}/close")
async def close_optimization(
    optimization_id: str,
    data: OptimizationCloseRequest,
    current_user: dict = Depends(get_current_user_wrapper),
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
        raise HTTPException(
            status_code=403, detail="Only Super Admin can close optimizations"
        )

    optimization = await db.seo_optimizations.find_one(
        {"id": optimization_id}, {"_id": 0}
    )
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    # Check for unresolved complaints
    unresolved_count = await db.optimization_complaints.count_documents(
        {
            "optimization_id": optimization_id,
            "status": {"$in": ["open", "under_review"]},
        }
    )

    if unresolved_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"⚠ Cannot close optimization: {unresolved_count} unresolved complaint(s). Resolve all complaints first.",
        )

    if optimization.get("status") == "completed" and optimization.get("closed_at"):
        raise HTTPException(status_code=400, detail="Optimization is already closed")

    now = datetime.now(timezone.utc).isoformat()

    await db.seo_optimizations.update_one(
        {"id": optimization_id},
        {
            "$set": {
                "status": "completed",
                "complaint_status": (
                    "resolved"
                    if optimization.get("complaint_status") != "none"
                    else "none"
                ),
                "closed_at": now,
                "closed_by": {
                    "user_id": current_user["id"],
                    "display_name": current_user.get(
                        "name", current_user["email"].split("@")[0]
                    ),
                    "email": current_user["email"],
                },
                "final_note": data.final_note,
                "updated_at": now,
            }
        },
    )

    # Send Telegram notification
    try:
        from services.seo_optimization_telegram_service import (
            seo_optimization_telegram_service,
        )

        if seo_optimization_telegram_service:
            network = await db.seo_networks.find_one(
                {"id": optimization["network_id"]}, {"_id": 0, "name": 1}
            )
            brand = await db.brands.find_one(
                {"id": optimization["brand_id"]}, {"_id": 0, "name": 1}
            )

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
            after_value={
                "action": "optimization_closed",
                "final_note": data.final_note,
            },
        )

    return {
        "message": "Optimization closed successfully",
        "status": "completed",
        "closed_at": now,
    }


# ==================== USER SEARCH FOR ACCESS CONTROL ====================


@router.get("/users/search")
async def search_users_for_access_control(
    q: str = Query(
        min_length=2,
        max_length=100,
        description="Search query for email, name, or display_name",
    ),
    network_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper),
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
    logger.info(
        f"[USER_SEARCH] Query: '{q}', network_id: {network_id}, user: {current_user.get('email')}"
    )

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
            {"display_name": search_regex},  # fallback field
        ]
    }

    # Exclude inactive/suspended users (unless super_admin)
    if not is_super_admin:
        base_query["status"] = {
            "$in": ["active", None]
        }  # Include users without status field (legacy)
    else:
        # Super Admin can see all, but still exclude rejected/pending by default
        base_query["status"] = {"$nin": ["rejected", "pending"]}

    # Brand scoping for non-super-admin
    # If network_id provided, get network's brand and filter users with that brand access
    if not is_super_admin and network_id:
        network = await db.seo_networks.find_one(
            {"id": network_id}, {"_id": 0, "brand_id": 1}
        )
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
    users = (
        await db.users.find(
            base_query,
            {
                "_id": 0,
                "id": 1,
                "email": 1,
                "name": 1,
                "display_name": 1,
                "role": 1,
                "status": 1,
            },
        )
        .limit(10)
        .to_list(10)
    )

    logger.info(f"[USER_SEARCH] Found {len(users)} users")

    # Format results
    results = []
    for u in users:
        results.append(
            {
                "id": u["id"],
                "email": u["email"],
                "name": u.get("name")
                or u.get("display_name")
                or u["email"].split("@")[0],
                "role": u.get("role", "viewer"),
                "status": u.get("status", "active"),
            }
        )

    return {"results": results, "total": len(results), "query": search_term}


@router.get("/users/by-ids")
async def get_users_by_ids(
    ids: str = Query(..., description="Comma-separated list of user IDs"),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get user details by IDs.
    Returns user info including telegram_username for notification tagging.
    """
    user_ids = [id.strip() for id in ids.split(",") if id.strip()]
    
    if not user_ids:
        return {"users": []}
    
    users = await db.users.find(
        {"id": {"$in": user_ids}},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "telegram_username": 1, "role": 1}
    ).to_list(100)
    
    return {"users": users}


# ==================== SEO NETWORK MANAGEMENT (MANAGERS) ====================


async def build_manager_summary_cache(manager_ids: List[str]) -> dict:
    """Build manager summary cache with user count and first 3 names"""
    if not manager_ids:
        return {"count": 0, "names": []}

    users = (
        await db.users.find(
            {"id": {"$in": manager_ids}}, {"_id": 0, "id": 1, "name": 1, "email": 1}
        )
        .limit(3)
        .to_list(3)
    )

    names = [u.get("name") or u["email"].split("@")[0] for u in users]

    return {"count": len(manager_ids), "names": names}


@router.put("/networks/{network_id}/managers")
async def update_network_managers(
    network_id: str,
    data: NetworkManagersUpdate,
    current_user: dict = Depends(get_current_user_wrapper),
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
        raise HTTPException(
            status_code=403, detail="Only Super Admin can modify SEO Network managers"
        )

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
        {
            "$set": {
                "visibility_mode": data.visibility_mode.value,
                "manager_ids": data.manager_ids,
                "manager_summary_cache": manager_summary_cache,
                "managers_updated_at": datetime.now(timezone.utc).isoformat(),
                "managers_updated_by": {
                    "user_id": current_user["id"],
                    "email": current_user["email"],
                    "name": current_user.get(
                        "name", current_user["email"].split("@")[0]
                    ),
                },
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    # Create audit log entry
    added_manager_names = []
    removed_manager_names = []

    if added_manager_ids:
        added_managers = await db.users.find(
            {"id": {"$in": added_manager_ids}}, {"_id": 0, "name": 1, "email": 1}
        ).to_list(100)
        added_manager_names = [
            u.get("name") or u["email"].split("@")[0] for u in added_managers
        ]

    if removed_manager_ids:
        removed_managers = await db.users.find(
            {"id": {"$in": removed_manager_ids}}, {"_id": 0, "name": 1, "email": 1}
        ).to_list(100)
        removed_manager_names = [
            u.get("name") or u["email"].split("@")[0] for u in removed_managers
        ]

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
            "name": current_user.get("name", current_user["email"].split("@")[0]),
        },
        "changed_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.network_managers_audit_logs.insert_one(audit_entry)
    logger.info(
        f"[MANAGERS_AUDIT] Network {network['name']}: {previous_mode} → {data.visibility_mode.value}, +{len(added_manager_ids)} -{len(removed_manager_ids)} managers"
    )

    # Log activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.UPDATE,
            entity_type=EntityType.SEO_NETWORK,
            entity_id=network_id,
            before_value={
                "visibility_mode": previous_mode,
                "manager_ids": list(previous_manager_ids),
            },
            after_value={
                "visibility_mode": data.visibility_mode.value,
                "manager_ids": data.manager_ids,
            },
        )

    return {
        "message": "SEO Network managers updated",
        "manager_summary_cache": manager_summary_cache,
    }


@router.get("/networks/{network_id}/managers")
async def get_network_managers(
    network_id: str, current_user: dict = Depends(get_current_user_wrapper)
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
            {
                "_id": 0,
                "id": 1,
                "email": 1,
                "name": 1,
                "role": 1,
                "telegram_username": 1,
            },
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
        "manager_summary_cache": network.get(
            "manager_summary_cache", {"count": 0, "names": []}
        ),
        "managers_updated_at": network.get("managers_updated_at"),
        "managers_updated_by": managers_updated_by,
        "is_current_user_manager": is_current_user_manager,
    }


# Keep legacy endpoint for backward compatibility (temporary)
@router.get("/networks/{network_id}/access-control")
async def get_network_access_control_legacy(
    network_id: str, current_user: dict = Depends(get_current_user_wrapper)
):
    """Legacy endpoint - redirects to managers endpoint"""
    return await get_network_managers(network_id, current_user)


@router.put("/networks/{network_id}/access-control")
async def update_network_access_control_legacy(
    network_id: str,
    data: NetworkManagersUpdate,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Legacy endpoint - redirects to managers endpoint"""
    return await update_network_managers(network_id, data, current_user)


@router.get("/networks/{network_id}/managers-audit-logs")
async def get_network_managers_audit_logs(
    network_id: str,
    limit: int = Query(default=20, le=100),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get audit logs for network manager changes (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")

    network = await db.seo_networks.find_one(
        {"id": network_id}, {"_id": 0, "brand_id": 1}
    )
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")

    require_brand_access(network["brand_id"], current_user)

    logs = (
        await db.network_managers_audit_logs.find(
            {"network_id": network_id}, {"_id": 0}
        )
        .sort("changed_at", -1)
        .limit(limit)
        .to_list(limit)
    )

    return {"logs": logs, "total": len(logs)}


# Legacy endpoint for backward compatibility
@router.get("/networks/{network_id}/access-audit-logs")
async def get_network_access_audit_logs_legacy(
    network_id: str,
    limit: int = Query(default=20, le=100),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Legacy endpoint - redirects to managers audit logs"""
    return await get_network_managers_audit_logs(network_id, limit, current_user)
    return await get_network_managers_audit_logs(network_id, limit, current_user)


# ==================== REMINDER CONFIGURATION ====================


@router.get("/settings/reminder-config")
async def get_reminder_config(current_user: dict = Depends(get_current_user_wrapper)):
    """Get global reminder configuration (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")

    settings = await db.settings.find_one({"key": "optimization_reminders"}, {"_id": 0})

    return settings or {
        "key": "optimization_reminders",
        "enabled": True,
        "interval_days": 2,
    }


@router.put("/settings/reminder-config")
async def update_reminder_config(
    data: dict, current_user: dict = Depends(get_current_user_wrapper)
):
    """Update global reminder configuration (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")

    interval_days = data.get("interval_days", 2)
    enabled = data.get("enabled", True)

    if interval_days < 1 or interval_days > 30:
        raise HTTPException(
            status_code=400, detail="Reminder interval must be between 1 and 30 days"
        )

    await db.settings.update_one(
        {"key": "optimization_reminders"},
        {
            "$set": {
                "key": "optimization_reminders",
                "enabled": enabled,
                "interval_days": interval_days,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": {
                    "user_id": current_user["id"],
                    "email": current_user["email"],
                },
            }
        },
        upsert=True,
    )

    return {
        "message": "Reminder configuration updated",
        "enabled": enabled,
        "interval_days": interval_days,
    }


@router.post("/settings/reminder-config/run")
async def run_reminder_check(current_user: dict = Depends(get_current_user_wrapper)):
    """
    Manually trigger a reminder check for all in-progress optimizations.
    Super Admin only.
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=403, detail="Only Super Admin can trigger reminder checks"
        )

    from services.optimization_reminder_scheduler import OptimizationReminderScheduler

    scheduler = OptimizationReminderScheduler(db)
    stats = await scheduler.run_reminder_check()

    return {"message": "Reminder check completed", "stats": stats}


@router.get("/networks/{network_id}/reminder-config")
async def get_network_reminder_config(
    network_id: str, current_user: dict = Depends(get_current_user_wrapper)
):
    """Get per-network reminder configuration override"""
    network = await db.seo_networks.find_one(
        {"id": network_id}, {"_id": 0, "brand_id": 1, "reminder_config": 1}
    )
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")

    require_brand_access(network["brand_id"], current_user)

    # Get global config as fallback
    global_config = await db.settings.find_one(
        {"key": "optimization_reminders"}, {"_id": 0}
    ) or {"enabled": True, "interval_days": 2}

    network_config = network.get("reminder_config") or {}

    return {
        "global_default": global_config,
        "network_override": network_config,
        "effective_interval_days": network_config.get("interval_days")
        or global_config.get("interval_days", 2),
    }


@router.put("/networks/{network_id}/reminder-config")
async def update_network_reminder_config(
    network_id: str, data: dict, current_user: dict = Depends(get_current_user_wrapper)
):
    """Update per-network reminder configuration override (Admin/Super Admin only)"""
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    network = await db.seo_networks.find_one(
        {"id": network_id}, {"_id": 0, "brand_id": 1}
    )
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")

    require_brand_access(network["brand_id"], current_user)

    interval_days = data.get("interval_days")
    use_global = data.get("use_global", False)

    if use_global:
        # Remove network override, use global default
        await db.seo_networks.update_one(
            {"id": network_id}, {"$unset": {"reminder_config": 1}}
        )
        return {"message": "Network will use global reminder settings"}

    if interval_days is not None:
        if interval_days < 1 or interval_days > 30:
            raise HTTPException(
                status_code=400,
                detail="Reminder interval must be between 1 and 30 days",
            )

        await db.seo_networks.update_one(
            {"id": network_id},
            {
                "$set": {
                    "reminder_config": {
                        "interval_days": interval_days,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "updated_by": {
                            "user_id": current_user["id"],
                            "email": current_user["email"],
                        },
                    }
                }
            },
        )
        return {
            "message": "Network reminder configuration updated",
            "interval_days": interval_days,
        }

    raise HTTPException(
        status_code=400, detail="Must provide interval_days or set use_global=true"
    )


@router.get("/optimization-reminders")
async def get_optimization_reminders(
    network_id: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get optimization reminder logs for accountability (Admin/Super Admin only)"""
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    query = {}
    if network_id:
        query["network_id"] = network_id

    reminders = (
        await db.optimization_reminders.find(query, {"_id": 0})
        .sort("sent_at", -1)
        .limit(limit)
        .to_list(limit)
    )

    return {"reminders": reminders, "total": len(reminders)}


@router.get("/scheduler/reminder-status")
async def get_reminder_scheduler_status(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get reminder scheduler status (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")

    from services.reminder_scheduler import get_reminder_scheduler

    scheduler = get_reminder_scheduler()

    if scheduler is None:
        return {
            "status": "not_initialized",
            "message": "Reminder scheduler is not initialized",
        }

    status = scheduler.get_status()

    # Get last execution log
    last_execution = await db.scheduler_execution_logs.find_one(
        {"job_id": "optimization_reminder_job"}, {"_id": 0}, sort=[("executed_at", -1)]
    )

    return {"scheduler": status, "last_execution": last_execution}


@router.post("/scheduler/trigger-reminders")
async def trigger_reminder_job(current_user: dict = Depends(get_current_user_wrapper)):
    """Manually trigger the reminder job (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")

    from services.reminder_scheduler import get_reminder_scheduler

    scheduler = get_reminder_scheduler()

    if scheduler is None:
        raise HTTPException(
            status_code=500, detail="Reminder scheduler is not initialized"
        )

    result = await scheduler.trigger_now()

    return {
        "message": "Reminder job triggered successfully",
        "result": result,
        "triggered_by": current_user["email"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/scheduler/execution-logs")
async def get_scheduler_execution_logs(
    job_id: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get scheduler execution logs (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")

    query = {}
    if job_id:
        query["job_id"] = job_id

    logs = (
        await db.scheduler_execution_logs.find(query, {"_id": 0})
        .sort("executed_at", -1)
        .limit(limit)
        .to_list(limit)
    )

    return {"logs": logs, "total": len(logs)}


@router.delete("/scheduler/execution-logs")
async def clear_scheduler_execution_logs(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Clear all scheduler execution logs (super_admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admins can clear execution logs")
    
    result = await db.scheduler_execution_logs.delete_many({})
    
    return {
        "message": "Execution logs cleared",
        "deleted_count": result.deleted_count
    }


# ==================== ACTIVITY TYPE MANAGEMENT ====================


@router.get("/optimization-activity-types")
async def get_optimization_activity_types(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get all optimization activity types (master data)"""
    types = (
        await db.seo_optimization_activity_types.find({}, {"_id": 0})
        .sort("name", 1)
        .to_list(100)
    )

    if not types:
        # Return default types if none exist
        return [
            {
                "id": "default_backlink",
                "name": "Backlink Campaign",
                "is_default": True,
                "usage_count": 0,
            },
            {
                "id": "default_onpage",
                "name": "On-Page Optimization",
                "is_default": True,
                "usage_count": 0,
            },
            {
                "id": "default_content",
                "name": "Content Update",
                "is_default": True,
                "usage_count": 0,
            },
            {
                "id": "default_technical",
                "name": "Technical SEO",
                "is_default": True,
                "usage_count": 0,
            },
            {
                "id": "default_schema",
                "name": "Schema Markup",
                "is_default": True,
                "usage_count": 0,
            },
            {
                "id": "default_internal",
                "name": "Internal Linking",
                "is_default": True,
                "usage_count": 0,
            },
            {
                "id": "default_experiment",
                "name": "SEO Experiment",
                "is_default": True,
                "usage_count": 0,
            },
            {
                "id": "default_other",
                "name": "Other",
                "is_default": True,
                "usage_count": 0,
            },
        ]

    # Get usage counts
    for t in types:
        count = await db.seo_optimizations.count_documents(
            {"activity_type_id": t["id"]}
        )
        t["usage_count"] = count

    return types


@router.post("/optimization-activity-types")
async def create_optimization_activity_type(
    data: OptimizationActivityTypeCreate,
    current_user: dict = Depends(get_current_user_wrapper),
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
        raise HTTPException(
            status_code=400, detail="Activity type with this name already exists"
        )

    now = datetime.now(timezone.utc).isoformat()
    activity_type = {
        "id": str(uuid.uuid4()),
        "name": data.name.strip(),
        "description": data.description,
        "icon": data.icon,
        "color": data.color,
        "is_default": False,
        "created_at": now,
    }

    await db.seo_optimization_activity_types.insert_one(activity_type)

    return activity_type


@router.delete("/optimization-activity-types/{type_id}")
async def delete_optimization_activity_type(
    type_id: str, current_user: dict = Depends(get_current_user_wrapper)
):
    """Delete an activity type - only if unused"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")

    # Check if in use
    usage_count = await db.seo_optimizations.count_documents(
        {"activity_type_id": type_id}
    )
    if usage_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete: activity type is used by {usage_count} optimization(s)",
        )

    await db.seo_optimization_activity_types.delete_one({"id": type_id})

    return {"message": "Activity type deleted"}


# ==================== OBSERVED IMPACT UPDATE ====================


@router.patch("/optimizations/{optimization_id}/observed-impact")
async def update_observed_impact(
    optimization_id: str,
    observed_impact: str,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Update observed impact for an optimization (after 14-30 days).
    Only Admin/Super Admin can update.
    """
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=403, detail="Admin access required to evaluate impact"
        )

    if observed_impact not in ["positive", "neutral", "no_impact", "negative"]:
        raise HTTPException(status_code=400, detail="Invalid observed_impact value")

    optimization = await db.seo_optimizations.find_one(
        {"id": optimization_id}, {"_id": 0}
    )
    if not optimization:
        raise HTTPException(status_code=404, detail="Optimization not found")

    require_brand_access(optimization["brand_id"], current_user)

    await db.seo_optimizations.update_one(
        {"id": optimization_id},
        {
            "$set": {
                "observed_impact": observed_impact,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {"message": "Observed impact updated", "observed_impact": observed_impact}


# ==================== TEAM EVALUATION ENDPOINTS ====================


@router.get("/team-evaluation/users")
async def get_team_evaluation_users(
    brand_id: Optional[str] = None,
    network_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper),
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
        {
            "$group": {
                "_id": "$created_by.user_id",
                "user_name": {"$first": "$created_by.display_name"},
                "user_email": {"$first": "$created_by.email"},
                "total_optimizations": {"$sum": 1},
                "completed_count": {
                    "$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}
                },
                "reverted_count": {
                    "$sum": {"$cond": [{"$eq": ["$status", "reverted"]}, 1, 0]}
                },
                "complaint_count": {
                    "$sum": {"$cond": [{"$ne": ["$complaint_status", "none"]}, 1, 0]}
                },
                "positive_impact": {
                    "$sum": {"$cond": [{"$eq": ["$observed_impact", "positive"]}, 1, 0]}
                },
                "negative_impact": {
                    "$sum": {"$cond": [{"$eq": ["$observed_impact", "negative"]}, 1, 0]}
                },
            }
        },
        {"$sort": {"total_optimizations": -1}},
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
            score -= revert_rate * 2  # -2 max for high revert rate
            score -= complaint_rate * 1.5  # -1.5 max for high complaint rate
            if r["positive_impact"] > 0:
                score += min(
                    r["positive_impact"] / r["total_optimizations"], 0.5
                )  # +0.5 max bonus

        score = max(0, min(5, score))  # Clamp to 0-5

        user_scores.append(
            UserSeoScore(
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
                    "revert_penalty": -round(
                        r["reverted_count"] / max(r["total_optimizations"], 1) * 2, 2
                    ),
                    "complaint_penalty": -round(
                        r["complaint_count"] / max(r["total_optimizations"], 1) * 1.5, 2
                    ),
                },
            )
        )

    return user_scores


@router.get("/team-evaluation/summary")
async def get_team_evaluation_summary(
    brand_id: Optional[str] = None,
    network_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper),
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
        count = await db.seo_optimizations.count_documents(
            {**query, "observed_impact": impact}
        )
        by_impact[impact] = count

    # By activity type
    type_pipeline = [
        {"$match": query},
        {"$group": {"_id": "$activity_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    type_results = await db.seo_optimizations.aggregate(type_pipeline).to_list(20)
    by_activity_type = {r["_id"]: r["count"] for r in type_results}

    # Total complaints
    total_complaints = await db.optimization_complaints.count_documents(
        {"created_at": {"$gte": start_date, "$lte": end_date}}
    )

    # Calculate average time-to-resolution for resolved complaints
    resolution_pipeline = [
        {
            "$match": {
                "created_at": {"$gte": start_date, "$lte": end_date},
                "status": "resolved",
                "time_to_resolution_hours": {"$exists": True, "$ne": None},
            }
        },
        {
            "$group": {
                "_id": None,
                "avg_hours": {"$avg": "$time_to_resolution_hours"},
                "resolved_count": {"$sum": 1},
            }
        },
    ]
    resolution_result = await db.optimization_complaints.aggregate(
        resolution_pipeline
    ).to_list(1)
    avg_resolution_time_hours = (
        resolution_result[0]["avg_hours"] if resolution_result else None
    )
    # resolved_count is available in resolution_result but not currently used in the response

    # Get top contributors
    top_users = await get_team_evaluation_users(
        brand_id, network_id, start_date, end_date, current_user
    )

    # Check for repeated issues (>2 complaints in 30 days per user)
    repeated_issue_pipeline = [
        {"$match": {**query, "complaint_status": {"$ne": "none"}}},
        {"$group": {"_id": "$created_by.user_id", "complaint_count": {"$sum": 1}}},
        {"$match": {"complaint_count": {"$gt": 2}}},
    ]
    repeated_results = await db.seo_optimizations.aggregate(
        repeated_issue_pipeline
    ).to_list(100)
    repeated_issue_users = [r["_id"] for r in repeated_results]

    return TeamEvaluationSummary(
        period_start=start_date,
        period_end=end_date,
        total_optimizations=total,
        by_status=by_status,
        by_activity_type=by_activity_type,
        by_observed_impact=by_impact,
        total_complaints=total_complaints,
        avg_resolution_time_hours=(
            round(avg_resolution_time_hours, 1) if avg_resolution_time_hours else None
        ),
        top_contributors=top_users[:5],
        most_complained_users=sorted(
            top_users, key=lambda x: x.complaint_count, reverse=True
        )[:5],
        repeated_issue_users=repeated_issue_users,
    )


@router.get("/team-evaluation/export")
async def export_team_evaluation_csv(
    brand_id: Optional[str] = None,
    network_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper),
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
    user_scores = await get_team_evaluation_users(
        brand_id, network_id, start_date, end_date, current_user
    )

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow(
        [
            "User Name",
            "Email",
            "Total Optimizations",
            "Completed",
            "Reverted",
            "Complaints",
            "Positive Impact",
            "Negative Impact",
            "Score (0-5)",
            "Score Status",
            "Revert Penalty",
            "Complaint Penalty",
        ]
    )

    # Data rows
    for user in user_scores:
        # Determine status label
        if user.score >= 4.5:
            status = "Excellent"
        elif user.score >= 3.5:
            status = "Good"
        elif user.score >= 2.5:
            status = "Average"
        else:
            status = "Needs Improvement"

        writer.writerow(
            [
                user.user_name or "Unknown",
                user.user_email or "",
                user.total_optimizations,
                user.completed_optimizations,
                user.reverted_optimizations,
                user.complaint_count,
                user.positive_impact_count,
                user.negative_impact_count,
                user.score,
                status,
                user.score_breakdown.get("revert_penalty", 0),
                user.score_breakdown.get("complaint_penalty", 0),
            ]
        )

    # Prepare response
    output.seek(0)

    # Generate filename with date range
    start_short = start_date[:10] if start_date else "unknown"
    end_short = end_date[:10] if end_date else "unknown"
    filename = f"seo_team_evaluation_{start_short}_to_{end_short}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


# ==================== SWITCH MAIN TARGET ENDPOINT ====================

from pydantic import BaseModel as PydanticBaseModel, Field as PydanticField


class SwitchMainTargetRequest(PydanticBaseModel):
    """Request model for switching the main target node"""

    new_main_entry_id: str
    change_note: str = PydanticField(
        ...,
        min_length=10,
        max_length=2000,
        description="Penjelasan perubahan main target (wajib, minimal 10 karakter)",
    )


@router.post("/networks/{network_id}/switch-main-target")
async def switch_main_target(
    network_id: str,
    data: SwitchMainTargetRequest,
    current_user: dict = Depends(get_current_user_wrapper),
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
    new_main = await db.seo_structure_entries.find_one(
        {"id": data.new_main_entry_id}, {"_id": 0}
    )
    if not new_main:
        raise HTTPException(status_code=404, detail="New main entry not found")

    if new_main.get("network_id") != network_id:
        raise HTTPException(status_code=400, detail="Entry must be in the same network")

    if new_main.get("domain_role") == "main":
        raise HTTPException(
            status_code=400, detail="This entry is already the main node"
        )

    # Find current main node
    current_main = await db.seo_structure_entries.find_one(
        {"network_id": network_id, "domain_role": "main"}, {"_id": 0}
    )

    now = datetime.now(timezone.utc).isoformat()

    # Step 1: Demote old main to supporting, pointing to new main
    if current_main:
        old_main_update = {
            "domain_role": "supporting",
            "domain_status": "canonical",  # Now it canonicalizes to new main
            "target_entry_id": data.new_main_entry_id,
            "updated_at": now,
        }
        await db.seo_structure_entries.update_one(
            {"id": current_main["id"]}, {"$set": old_main_update}
        )

        # Log the demotion
        if seo_change_log_service:
            old_domain = await db.asset_domains.find_one(
                {"id": current_main["asset_domain_id"]}, {"domain_name": 1, "_id": 0}
            )
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
                entry_id=current_main["id"],
            )

    # Step 2: Promote new main
    new_main_update = {
        "domain_role": "main",
        "domain_status": "primary",  # Main nodes have PRIMARY status
        "target_entry_id": None,  # Main nodes don't have targets
        "target_asset_domain_id": None,
        "updated_at": now,
    }
    await db.seo_structure_entries.update_one(
        {"id": data.new_main_entry_id}, {"$set": new_main_update}
    )

    # Log the promotion
    if seo_change_log_service:
        new_domain = await db.asset_domains.find_one(
            {"id": new_main["asset_domain_id"]}, {"domain_name": 1, "_id": 0}
        )
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
            entry_id=data.new_main_entry_id,
        )

    # Step 3: Recalculate tiers
    if tier_service:
        await tier_service.calculate_network_tiers(network_id)

    # Create notification for main domain change
    if seo_change_log_service:
        new_domain = await db.asset_domains.find_one(
            {"id": new_main["asset_domain_id"]}, {"domain_name": 1, "_id": 0}
        )
        await seo_change_log_service.create_notification(
            network_id=network_id,
            brand_id=network.get("brand_id", ""),
            notification_type=SeoNotificationType.MAIN_DOMAIN_CHANGE,
            title="Main Target Switched",
            message=f"Main target changed to '{new_domain['domain_name'] if new_domain else 'unknown'}{new_main.get('optimized_path', '') or ''}'",
            affected_node=new_node_label,
            actor_email=current_user["email"],
            change_note=data.change_note,
        )

    # Send SEO Telegram notification for main target switch
    if seo_telegram_service:
        new_domain = await db.asset_domains.find_one(
            {"id": new_main["asset_domain_id"]}, {"domain_name": 1, "_id": 0}
        )
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
            skip_rate_limit=True,  # Important changes should bypass rate limit
        )

    return {
        "message": "Main target switched successfully",
        "new_main_entry_id": data.new_main_entry_id,
        "previous_main_entry_id": current_main["id"] if current_main else None,
        "tiers_recalculated": True,
    }


class DeleteStructureEntryRequest(PydanticBaseModel):
    """Request model for deleting structure entry with mandatory change note"""

    change_note: str = PydanticField(
        ...,
        min_length=10,
        max_length=2000,
        description="Penjelasan penghapusan node (wajib, minimal 10 karakter)",
    )


@router.delete("/structure/{entry_id}")
async def delete_structure_entry(
    entry_id: str,
    data: DeleteStructureEntryRequest,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Delete an SEO structure entry (node) with mandatory change note.

    If other entries target this node, they become orphans.
    A warning is included in the response but deletion proceeds.
    """
    existing = await db.seo_structure_entries.find_one({"id": entry_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Structure entry not found")

    # PERMISSION CHECK: Only super_admin or network managers can delete nodes
    network = await db.seo_networks.find_one({"id": existing.get("network_id")}, {"_id": 0})
    if network:
        await require_manager_permission(network, current_user)
    else:
        raise HTTPException(status_code=404, detail="Network not found for this entry")

    # CRITICAL: Validate change_note BEFORE any operation
    validate_change_note(data.change_note)

    # Check if this is the main node
    if existing.get("domain_role") == DomainRole.MAIN.value:
        # Count other entries in network
        other_entries = await db.seo_structure_entries.count_documents(
            {"network_id": existing["network_id"], "id": {"$ne": entry_id}}
        )
        if other_entries > 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete main node while other nodes exist. Delete supporting nodes first or reassign main role.",
            )

    # ========================================================================
    # CAPTURE FULL PRE-DELETION SNAPSHOT FOR AUDIT
    # ========================================================================
    
    # Get domain name for this node
    domain = await db.asset_domains.find_one(
        {"id": existing["asset_domain_id"]}, {"_id": 0, "domain_name": 1}
    )
    domain_name = domain["domain_name"] if domain else "unknown"
    node_label = f"{domain_name}{existing.get('optimized_path', '') or ''}"
    
    # Get target node info if exists
    target_info = None
    if existing.get("target_entry_id"):
        target_entry = await db.seo_structure_entries.find_one(
            {"id": existing["target_entry_id"]}, {"_id": 0}
        )
        if target_entry:
            target_domain = await db.asset_domains.find_one(
                {"id": target_entry.get("asset_domain_id")}, {"_id": 0, "domain_name": 1}
            )
            target_domain_name = target_domain["domain_name"] if target_domain else "unknown"
            target_info = {
                "domain_name": target_domain_name,
                "path": target_entry.get("optimized_path", ""),
                "role": target_entry.get("domain_role", ""),
                "full_label": f"{target_domain_name}{target_entry.get('optimized_path', '') or ''}"
            }
    
    # Build upstream chain (path to Money Site)
    upstream_chain = []
    current_entry = existing
    visited = {entry_id}
    while current_entry and current_entry.get("target_entry_id"):
        next_entry = await db.seo_structure_entries.find_one(
            {"id": current_entry["target_entry_id"]}, {"_id": 0}
        )
        if not next_entry or next_entry.get("id") in visited:
            break
        visited.add(next_entry.get("id"))
        next_domain = await db.asset_domains.find_one(
            {"id": next_entry.get("asset_domain_id")}, {"_id": 0, "domain_name": 1}
        )
        next_domain_name = next_domain["domain_name"] if next_domain else "unknown"
        upstream_chain.append({
            "label": f"{next_domain_name}{next_entry.get('optimized_path', '') or ''}",
            "role": next_entry.get("domain_role", ""),
            "status": next_entry.get("domain_status", "")
        })
        current_entry = next_entry
    
    # Check how many entries point to this one (they will become orphans/affected)
    orphan_count = await db.seo_structure_entries.count_documents(
        {"target_entry_id": entry_id, "id": {"$ne": entry_id}}
    )
    
    # Get affected child nodes for impact analysis
    affected_children = []
    if orphan_count > 0:
        children = await db.seo_structure_entries.find(
            {"target_entry_id": entry_id, "id": {"$ne": entry_id}},
            {"_id": 0, "asset_domain_id": 1, "optimized_path": 1, "domain_role": 1}
        ).to_list(10)
        for child in children:
            child_domain = await db.asset_domains.find_one(
                {"id": child.get("asset_domain_id")}, {"_id": 0, "domain_name": 1}
            )
            child_domain_name = child_domain["domain_name"] if child_domain else "unknown"
            affected_children.append(f"{child_domain_name}{child.get('optimized_path', '') or ''}")
    
    # Get FULL structure BEFORE deletion
    structure_before = await db.seo_structure_entries.find(
        {"network_id": existing["network_id"]}, {"_id": 0}
    ).to_list(100)
    
    # Format structure for notification
    structure_before_formatted = []
    for entry in structure_before:
        entry_domain = await db.asset_domains.find_one(
            {"id": entry.get("asset_domain_id")}, {"_id": 0, "domain_name": 1}
        )
        entry_domain_name = entry_domain["domain_name"] if entry_domain else "unknown"
        entry_label = f"{entry_domain_name}{entry.get('optimized_path', '') or ''}"
        entry_status = entry.get("domain_status", "")
        entry_role = entry.get("domain_role", "")
        
        # Mark the node being deleted
        is_deleted = entry.get("id") == entry_id
        structure_before_formatted.append({
            "label": entry_label,
            "role": entry_role,
            "status": entry_status,
            "is_deleted_node": is_deleted
        })
    
    # Enrich the before_snapshot with all captured data
    enriched_before_snapshot = {
        **existing,
        "domain_name": domain_name,
        "node_label": node_label,
        "target_info": target_info,
        "upstream_chain": upstream_chain,
        "affected_children": affected_children,
        "orphan_count": orphan_count,
        "structure_before": structure_before_formatted,
    }
    # ========================================================================

    # Clear target_entry_id on orphaned entries
    if orphan_count > 0:
        await db.seo_structure_entries.update_many(
            {"target_entry_id": entry_id},
            {
                "$set": {
                    "target_entry_id": None,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )

    # Get network for brand_id
    network = await db.seo_networks.find_one(
        {"id": existing["network_id"]}, {"_id": 0, "brand_id": 1}
    )
    brand_id = network.get("brand_id", "") if network else ""

    await db.seo_structure_entries.delete_one({"id": entry_id})

    # ATOMIC: Log + Telegram notification
    # Skip rate limit for DELETE actions - critical notifications must always be sent
    notification_success, change_log_id, error_msg = (
        await atomic_seo_change_with_notification(
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
            before_snapshot=enriched_before_snapshot,
            after_snapshot=None,
            entry_id=entry_id,
            skip_rate_limit=True,  # DELETE actions bypass rate limit
        )
    )

    # Log system activity
    if activity_log_service:
        await activity_log_service.log(
            actor=current_user["email"],
            action_type=ActionType.DELETE,
            entity_type=EntityType.SEO_STRUCTURE_ENTRY,
            entity_id=entry_id,
            before_value=existing,
            metadata={
                "node_label": node_label,
                "orphaned_entries": orphan_count,
                "change_note": data.change_note,
            },
        )

    return {
        "message": "Structure entry deleted",
        "orphaned_entries": orphan_count,
        "notification_sent": notification_success,
        "warning": (
            f"{orphan_count} entries now have no target (orphaned)"
            if orphan_count > 0
            else None
        ),
    }


# ==================== BRAND-SCOPED DOMAIN SELECTION ====================


@router.get("/networks/{network_id}/available-domains")
async def get_available_domains_for_network(
    network_id: str, current_user: dict = Depends(get_current_user_wrapper)
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
        {"_id": 0, "id": 1, "domain_name": 1},
    ).to_list(10000)

    # Get existing entries in this network
    existing_entries = await db.seo_structure_entries.find(
        {"network_id": network_id},
        {"_id": 0, "asset_domain_id": 1, "optimized_path": 1},
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

        result.append(
            {
                "id": d["id"],
                "domain_name": d["domain_name"],
                "root_available": not root_used,
                "used_paths": used_paths,
            }
        )

    return result


@router.get("/networks/{network_id}/available-targets")
async def get_available_target_nodes(
    network_id: str,
    exclude_entry_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper),
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
        {"id": {"$in": domain_ids}}, {"_id": 0, "id": 1, "domain_name": 1}
    ).to_list(10000)
    domain_lookup = {d["id"]: d["domain_name"] for d in domains}

    result = []
    for e in entries:
        domain_name = domain_lookup.get(e["asset_domain_id"], "")
        path = e.get("optimized_path") or ""
        node_label = f"{domain_name}{path}" if path else domain_name

        result.append(
            {
                "id": e["id"],
                "domain_name": domain_name,
                "optimized_path": path,
                "node_label": node_label,
                "domain_role": e.get("domain_role", "supporting"),
            }
        )

    return result


# ==================== TIER CALCULATION ENDPOINTS ====================


@router.get("/networks/{network_id}/tiers")
async def get_network_tiers(
    network_id: str, current_user: dict = Depends(get_current_user_wrapper)
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
        asset = await db.asset_domains.find_one(
            {"id": asset_id}, {"_id": 0, "domain_name": 1}
        )
        tier_details.append(
            {
                "asset_domain_id": asset_id,
                "domain_name": asset["domain_name"] if asset else None,
                "tier": tier,
                "tier_label": get_tier_label(tier),
            }
        )

    # Sort by tier
    tier_details.sort(key=lambda x: x["tier"])

    return {
        "network_id": network_id,
        "network_name": network["name"],
        "distribution": distribution,
        "domains": tier_details,
        "issues": issues,
    }


# ==================== ACTIVITY LOGS ENDPOINTS ====================


@router.get("/activity-logs", response_model=List[ActivityLogResponse])
async def get_activity_logs(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    actor: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get activity logs"""
    if not activity_log_service:
        raise HTTPException(
            status_code=500, detail="Activity log service not initialized"
        )

    return await activity_log_service.get_logs(
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        limit=limit,
        skip=skip,
    )


@router.get("/activity-logs/stats")
async def get_activity_stats(current_user: dict = Depends(get_current_user_wrapper)):
    """Get activity log statistics"""
    if not activity_log_service:
        raise HTTPException(
            status_code=500, detail="Activity log service not initialized"
        )

    return await activity_log_service.get_stats()


# ==================== REPORTS & ANALYTICS ====================


@router.get("/reports/dashboard")
async def get_v3_dashboard(current_user: dict = Depends(get_current_user_wrapper)):
    """Get V3 dashboard statistics"""
    asset_count = await db.asset_domains.count_documents({})
    network_count = await db.seo_networks.count_documents({})
    structure_count = await db.seo_structure_entries.count_documents({})

    # Status distributions
    asset_active = await db.asset_domains.count_documents({"status": "active"})
    asset_inactive = await db.asset_domains.count_documents({"status": "inactive"})
    asset_expired = await db.asset_domains.count_documents({"status": "expired"})

    main_domains = await db.seo_structure_entries.count_documents(
        {"domain_role": "main"}
    )
    supporting_domains = await db.seo_structure_entries.count_documents(
        {"domain_role": "supporting"}
    )

    indexed = await db.seo_structure_entries.count_documents({"index_status": "index"})
    noindexed = await db.seo_structure_entries.count_documents(
        {"index_status": "noindex"}
    )

    # Monitoring stats
    monitored = await db.asset_domains.count_documents({"monitoring_enabled": True})
    up = await db.asset_domains.count_documents(
        {"monitoring_enabled": True, "ping_status": "up"}
    )
    down = await db.asset_domains.count_documents(
        {"monitoring_enabled": True, "ping_status": "down"}
    )

    return {
        "collections": {
            "asset_domains": asset_count,
            "seo_networks": network_count,
            "seo_structure_entries": structure_count,
        },
        "asset_status": {
            "active": asset_active,
            "inactive": asset_inactive,
            "expired": asset_expired,
        },
        "domain_roles": {"main": main_domains, "supporting": supporting_domains},
        "index_status": {
            "indexed": indexed,
            "noindexed": noindexed,
            "index_rate": (
                round(indexed / structure_count * 100, 1) if structure_count > 0 else 0
            ),
        },
        "monitoring": {
            "total_monitored": monitored,
            "up": up,
            "down": down,
            "unknown": monitored - up - down,
        },
    }


@router.get("/reports/domains-by-brand")
async def get_domains_by_brand(current_user: dict = Depends(get_current_user_wrapper)):
    """Get total domain count grouped by brand"""
    # Aggregate domains by brand
    pipeline = [
        {"$match": {"brand_id": {"$exists": True, "$ne": None}}},
        {
            "$group": {
                "_id": "$brand_id",
                "count": {"$sum": 1}
            }
        }
    ]
    
    brand_counts = {}
    async for doc in db.asset_domains.aggregate(pipeline):
        brand_counts[doc["_id"]] = doc["count"]
    
    # Get brand names
    brand_ids = list(brand_counts.keys())
    brands = await db.brands.find(
        {"id": {"$in": brand_ids}},
        {"_id": 0, "id": 1, "name": 1}
    ).to_list(None)
    
    brand_name_map = {b["id"]: b["name"] for b in brands}
    
    # Build result sorted by count (descending)
    result = []
    for brand_id, count in brand_counts.items():
        result.append({
            "brand_id": brand_id,
            "brand_name": brand_name_map.get(brand_id, "Unknown"),
            "domain_count": count
        })
    
    result.sort(key=lambda x: x["domain_count"], reverse=True)
    
    return {
        "data": result,
        "total_brands": len(result),
        "total_domains": sum(r["domain_count"] for r in result)
    }


@router.get("/reports/conflicts", response_model=None)
async def get_v3_conflicts(
    network_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper),
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
            {"network_id": network["id"]}, {"_id": 0}
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
            {"id": {"$in": domain_ids}}, {"_id": 0, "id": 1, "domain_name": 1}
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
                        for e2 in kw_entries[i + 1 :]:
                            conflicts.append(
                                {
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
                                    "detected_at": now,
                                }
                            )

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
                    for group2 in target_entries[i + 1 :]:
                        e1 = group1[0]
                        e2 = group2[0]
                        t1 = entry_lookup.get(e1.get("target_entry_id"))
                        t2 = entry_lookup.get(e2.get("target_entry_id"))

                        conflicts.append(
                            {
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
                                "detected_at": now,
                            }
                        )

            # TYPE C: Canonical Mismatch
            # Path A has canonical pointing to Path B, but B is still indexed
            for e in domain_entry_list:
                if (
                    e.get("domain_status") == "redirect_301"
                    or e.get("domain_status") == "redirect_302"
                ):
                    target_id = e.get("target_entry_id")
                    if target_id:
                        target = entry_lookup.get(target_id)
                        if target and target.get("index_status") == "index":
                            conflicts.append(
                                {
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
                                    "detected_at": now,
                                }
                            )

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
                                conflicts.append(
                                    {
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
                                        "detected_at": now,
                                    }
                                )

        # ============ NETWORK-WIDE CONFLICT DETECTION ============
        
        # Build reverse lookup: target_entry_id -> list of source entries
        target_sources = {}  # target_entry_id -> [source entries]
        for entry in entries:
            target_id = entry.get("target_entry_id")
            if target_id:
                if target_id not in target_sources:
                    target_sources[target_id] = []
                target_sources[target_id].append(entry)
        
        # TYPE E: Redirect/Canonical Loops
        # Detect A -> B -> A or A -> B -> C -> A cycles
        def detect_redirect_loop(start_entry_id, visited=None, path=None):
            """Detect redirect loops starting from entry"""
            if visited is None:
                visited = set()
            if path is None:
                path = []
            
            if start_entry_id in visited:
                return path  # Loop found
            
            visited.add(start_entry_id)
            path.append(start_entry_id)
            
            entry = entry_lookup.get(start_entry_id)
            if entry:
                target_id = entry.get("target_entry_id")
                # Only follow redirects/canonicals
                if target_id and entry.get("domain_status") in ["redirect_301", "redirect_302", "canonical"]:
                    return detect_redirect_loop(target_id, visited, path)
            
            return None  # No loop
        
        detected_loops = set()
        for entry in entries:
            if entry.get("domain_status") in ["redirect_301", "redirect_302", "canonical"]:
                loop_path = detect_redirect_loop(entry["id"])
                if loop_path and len(loop_path) > 1:
                    loop_key = tuple(sorted(loop_path))
                    if loop_key not in detected_loops:
                        detected_loops.add(loop_key)
                        first_entry = entry_lookup.get(loop_path[0])
                        last_entry = entry_lookup.get(loop_path[-1]) if loop_path else None
                        conflicts.append({
                            "conflict_type": ConflictType.REDIRECT_LOOP.value,
                            "severity": ConflictSeverity.CRITICAL.value,
                            "network_id": network["id"],
                            "network_name": network["name"],
                            "domain_name": domain_name_lookup.get(first_entry["asset_domain_id"], "") if first_entry else "",
                            "node_a_id": loop_path[0],
                            "node_a_path": first_entry.get("optimized_path") if first_entry else None,
                            "node_a_label": node_label(first_entry) if first_entry else "",
                            "node_b_id": loop_path[-1] if loop_path else None,
                            "node_b_path": last_entry.get("optimized_path") if last_entry else None,
                            "node_b_label": node_label(last_entry) if last_entry else "",
                            "description": f"Redirect/canonical loop detected with {len(loop_path)} nodes",
                            "suggestion": "Break the loop by removing one redirect",
                            "detected_at": now,
                        })
        
        # TYPE F: Multiple Parents pointing to Money Site without intent
        # Find main node
        main_entries = [e for e in entries if e.get("domain_role") == "main"]
        for main_entry in main_entries:
            main_id = main_entry["id"]
            
            # Find all entries pointing to this main
            sources_to_main = target_sources.get(main_id, [])
            
            # Filter out expected supporting nodes
            non_supporting_sources = [
                s for s in sources_to_main 
                if s.get("domain_role") != "supporting" and s.get("domain_status") not in ["redirect_301", "redirect_302"]
            ]
            
            if len(non_supporting_sources) > 1:
                # Multiple non-supporting nodes point to main - potential issue
                for src in non_supporting_sources:
                    conflicts.append({
                        "conflict_type": ConflictType.MULTIPLE_PARENTS_TO_MAIN.value,
                        "severity": ConflictSeverity.MEDIUM.value,
                        "network_id": network["id"],
                        "network_name": network["name"],
                        "domain_name": domain_name_lookup.get(src["asset_domain_id"], ""),
                        "node_a_id": src["id"],
                        "node_a_path": src.get("optimized_path"),
                        "node_a_label": node_label(src),
                        "node_b_id": main_id,
                        "node_b_path": main_entry.get("optimized_path"),
                        "node_b_label": node_label(main_entry),
                        "description": f"Non-supporting node pointing to Money Site (total {len(non_supporting_sources)} similar)",
                        "suggestion": "Change to supporting role or redirect if intentional",
                        "detected_at": now,
                    })
        
        # TYPE G: Index/Noindex Mismatch in Link Chain
        # Node A (indexed) links to Node B (noindex) - potential issue
        for entry in entries:
            if entry.get("index_status") == "index":
                target_id = entry.get("target_entry_id")
                if target_id:
                    target = entry_lookup.get(target_id)
                    if target and target.get("index_status") == "noindex":
                        entry_tier = tiers.get(entry["id"], 5)
                        target_tier = tiers.get(target_id, 5)
                        
                        # Only flag if indexed node is lower tier pointing to noindex higher tier
                        if entry_tier > target_tier:
                            conflicts.append({
                                "conflict_type": ConflictType.INDEX_NOINDEX_MISMATCH.value,
                                "severity": ConflictSeverity.HIGH.value,
                                "network_id": network["id"],
                                "network_name": network["name"],
                                "domain_name": domain_name_lookup.get(entry["asset_domain_id"], ""),
                                "node_a_id": entry["id"],
                                "node_a_path": entry.get("optimized_path"),
                                "node_a_label": node_label(entry),
                                "node_b_id": target_id,
                                "node_b_path": target.get("optimized_path"),
                                "node_b_label": node_label(target),
                                "description": "Indexed node links to NOINDEX target in higher tier",
                                "suggestion": "Index the target or remove the link",
                                "detected_at": now,
                            })

        # ============ LEGACY CONFLICT DETECTION ============

        for entry in entries:
            entry_id = entry["id"]
            asset_id = entry["asset_domain_id"]
            tier = tiers.get(entry_id, 5)
            domain_name = domain_name_lookup.get(asset_id, asset_id)

            # NOINDEX in high tier (0-2)
            if entry.get("index_status") == "noindex" and tier <= 2:
                conflicts.append(
                    {
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
                        "detected_at": now,
                    }
                )

            # Orphan (no target and not main)
            if (
                entry.get("domain_role") != "main"
                and not entry.get("target_entry_id")
                and not entry.get("target_asset_domain_id")
            ):
                if tier >= 5:
                    conflicts.append(
                        {
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
                            "detected_at": now,
                        }
                    )

    # Sort by severity
    severity_order = {
        ConflictSeverity.CRITICAL.value: 0,
        ConflictSeverity.HIGH.value: 1,
        ConflictSeverity.MEDIUM.value: 2,
        ConflictSeverity.LOW.value: 3,
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
            "critical": len(
                [
                    c
                    for c in conflicts
                    if c.get("severity") == ConflictSeverity.CRITICAL.value
                ]
            ),
            "high": len(
                [
                    c
                    for c in conflicts
                    if c.get("severity") == ConflictSeverity.HIGH.value
                ]
            ),
            "medium": len(
                [
                    c
                    for c in conflicts
                    if c.get("severity") == ConflictSeverity.MEDIUM.value
                ]
            ),
            "low": len(
                [
                    c
                    for c in conflicts
                    if c.get("severity") == ConflictSeverity.LOW.value
                ]
            ),
        },
    }


# ==================== STORED CONFLICTS & AUTO-OPTIMIZATION ENDPOINTS ====================


@router.get("/conflicts/stored")
async def get_stored_conflicts(
    network_id: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get stored conflicts with their linked optimization status.
    
    These conflicts have been processed and linked to optimization tasks.
    """
    conflict_service = get_conflict_linker_service(db)
    
    conflicts = await conflict_service.get_stored_conflicts(
        network_id=network_id,
        status=status,
        severity=severity,
        limit=limit
    )
    
    # Enrich with optimization info
    for conflict in conflicts:
        if conflict.get("optimization_id"):
            opt = await db.seo_optimizations.find_one(
                {"id": conflict["optimization_id"]},
                {"_id": 0, "id": 1, "title": 1, "status": 1, "created_at": 1}
            )
            conflict["linked_optimization"] = opt
    
    # Calculate stats
    by_status = {}
    by_severity = {}
    for c in conflicts:
        s = c.get("status", "unknown")
        sev = c.get("severity", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        by_severity[sev] = by_severity.get(sev, 0) + 1
    
    return {
        "conflicts": conflicts,
        "total": len(conflicts),
        "by_status": by_status,
        "by_severity": by_severity,
    }


@router.get("/conflicts/stored/{conflict_id}")
async def get_stored_conflict_detail(
    conflict_id: str,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get detailed info for a single stored conflict."""
    conflict_service = get_conflict_linker_service(db)
    
    conflict = await conflict_service.get_conflict_by_id(conflict_id)
    
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")
    
    # Enrich with optimization info
    if conflict.get("optimization_id"):
        opt = await db.seo_optimizations.find_one(
            {"id": conflict["optimization_id"]},
            {"_id": 0}
        )
        conflict["linked_optimization"] = opt
    
    return conflict


@router.post("/conflicts/process")
async def process_and_store_conflicts(
    network_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Detect conflicts and auto-create optimization tasks.
    
    This endpoint:
    1. Detects all SEO conflicts (like /reports/conflicts)
    2. Stores new conflicts in seo_conflicts collection
    3. Auto-creates optimization tasks for each new conflict
    4. Sends Telegram notifications
    
    Use this for scheduled conflict detection with auto-linking.
    """
    # Check permission - only managers or super admin
    user_role = current_user.get("role", "user")
    if user_role not in ["super_admin", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only managers and super admins can process conflicts"
        )
    
    conflict_service = get_conflict_linker_service(db)
    
    # Get all networks or specific one
    if network_id:
        networks = await db.seo_networks.find(
            {"id": network_id},
            {"_id": 0}
        ).to_list(1)
    else:
        networks = await db.seo_networks.find({}, {"_id": 0}).to_list(500)
    
    total_processed = 0
    total_new = 0
    total_recurring = 0
    total_optimizations = 0
    
    for network in networks:
        nid = network.get("id")
        
        # Detect conflicts for this network (similar to /reports/conflicts)
        detected_conflicts = await _detect_network_conflicts(nid)
        
        if detected_conflicts:
            result = await conflict_service.process_detected_conflicts(
                conflicts=detected_conflicts,
                network_id=nid,
                triggered_by=current_user.get("id", "system")
            )
            
            total_processed += result.get("processed", 0)
            total_new += result.get("new_conflicts", 0)
            total_recurring += result.get("recurring_conflicts", 0)
            total_optimizations += result.get("optimizations_created", 0)
    
    return {
        "success": True,
        "networks_scanned": len(networks),
        "conflicts_processed": total_processed,
        "new_conflicts": total_new,
        "recurring_conflicts": total_recurring,
        "optimizations_created": total_optimizations,
    }


async def _detect_network_conflicts(network_id: str) -> List[Dict[str, Any]]:
    """
    Helper to detect conflicts for a single network.
    Returns list of conflict dictionaries.
    """
    conflicts = []
    
    # Get network
    network = await db.seo_networks.find_one(
        {"id": network_id},
        {"_id": 0, "id": 1, "name": 1}
    )
    if not network:
        return []
    
    network_name = network.get("name", "Unknown")
    
    # Get tier service
    from services.tier_service import get_tier_service
    tier_svc = get_tier_service()
    
    tiers = await tier_svc.calculate_network_tiers(network_id)
    entries = await db.seo_structure_entries.find(
        {"network_id": network_id},
        {"_id": 0}
    ).to_list(1000)
    
    if not entries:
        return []
    
    # Build node map
    node_map = {}
    for e in entries:
        node_id = e.get("id")
        tier = tiers.get(node_id, 99)
        e["tier"] = tier
        node_map[node_id] = e
    
    now_str = datetime.now(timezone.utc).isoformat()
    
    # Group entries by domain
    by_domain = {}
    for e in entries:
        domain = e.get("optimized_domain") or e.get("asset_domain_name") or ""
        if domain:
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(e)
    
    # Detect conflicts (simplified version of the main detection logic)
    for domain, domain_entries in by_domain.items():
        if len(domain_entries) < 2:
            continue
        
        # Check for competing targets
        targets = {}
        for e in domain_entries:
            target = e.get("target_node_id")
            if target:
                if target not in targets:
                    targets[target] = []
                targets[target].append(e)
        
        # Cross-path conflicts
        for target_id, target_entries in targets.items():
            if len(target_entries) >= 2:
                # Multiple paths targeting same node
                entry_a = target_entries[0]
                entry_b = target_entries[1]
                
                conflicts.append({
                    "conflict_type": ConflictType.COMPETING_TARGETS.value,
                    "severity": ConflictSeverity.MEDIUM.value,
                    "network_id": network_id,
                    "network_name": network_name,
                    "domain_name": domain,
                    "node_a_id": entry_a.get("id"),
                    "node_a_path": entry_a.get("optimized_path"),
                    "node_a_label": f"{domain}{entry_a.get('optimized_path', '')}",
                    "node_b_id": entry_b.get("id"),
                    "node_b_path": entry_b.get("optimized_path"),
                    "node_b_label": f"{domain}{entry_b.get('optimized_path', '')}",
                    "description": f"Multiple paths on {domain} are targeting the same node",
                    "suggestion": "Consolidate paths or differentiate their targets",
                    "detected_at": now_str,
                })
    
    # Check for tier inversions
    for e in entries:
        source_tier = e.get("tier", 99)
        target_id = e.get("target_node_id")
        
        if target_id and target_id in node_map:
            target_entry = node_map[target_id]
            target_tier = target_entry.get("tier", 99)
            
            # Tier inversion: source has lower tier number (higher authority) than target
            if source_tier < target_tier and source_tier != 99 and target_tier != 99:
                domain = e.get("optimized_domain") or e.get("asset_domain_name") or ""
                
                conflicts.append({
                    "conflict_type": ConflictType.TIER_INVERSION.value,
                    "severity": ConflictSeverity.CRITICAL.value,
                    "network_id": network_id,
                    "network_name": network_name,
                    "domain_name": domain,
                    "node_a_id": e.get("id"),
                    "node_a_path": e.get("optimized_path"),
                    "node_a_label": f"{domain}{e.get('optimized_path', '')} (Tier {source_tier})",
                    "node_b_id": target_id,
                    "node_b_path": target_entry.get("optimized_path"),
                    "node_b_label": f"{target_entry.get('optimized_domain', '')}{target_entry.get('optimized_path', '')} (Tier {target_tier})",
                    "description": f"Higher authority node (Tier {source_tier}) is supporting lower authority node (Tier {target_tier})",
                    "suggestion": "Reverse the link direction or restructure the hierarchy",
                    "detected_at": now_str,
                })
    
    # Check for orphan nodes (not connected to main)
    main_entry = None
    for e in entries:
        if e.get("domain_role") == "main":
            main_entry = e
            break
    
    if main_entry:
        # Find all nodes that can reach main
        reachable = set()
        reachable.add(main_entry.get("id"))
        
        changed = True
        while changed:
            changed = False
            for e in entries:
                target_id = e.get("target_node_id")
                if target_id in reachable and e.get("id") not in reachable:
                    reachable.add(e.get("id"))
                    changed = True
        
        # Nodes not reachable are orphans
        for e in entries:
            if e.get("id") not in reachable and e.get("domain_role") != "main":
                domain = e.get("optimized_domain") or e.get("asset_domain_name") or ""
                
                conflicts.append({
                    "conflict_type": "orphan",
                    "severity": ConflictSeverity.MEDIUM.value,
                    "network_id": network_id,
                    "network_name": network_name,
                    "domain_name": domain,
                    "node_a_id": e.get("id"),
                    "node_a_path": e.get("optimized_path"),
                    "node_a_label": f"{domain}{e.get('optimized_path', '')}",
                    "node_b_id": None,
                    "node_b_path": None,
                    "node_b_label": None,
                    "description": "Node is not connected to the main hierarchy",
                    "suggestion": "Connect this node to the network structure or remove it",
                    "detected_at": now_str,
                })
    
    return conflicts


@router.post("/conflicts/{conflict_id}/create-optimization")
async def create_optimization_for_conflict(
    conflict_id: str,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Create an optimization task for a specific conflict.
    
    Use this when:
    - A conflict exists without a linked optimization (e.g., after deletion)
    - You want to manually create a task for a conflict
    
    Only managers and super admins can create optimization tasks.
    """
    # Check permission
    user_role = current_user.get("role", "user")
    if user_role not in ["super_admin", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only managers and super admins can create optimization tasks"
        )
    
    # Get the conflict
    conflict = await db.seo_conflicts.find_one({"id": conflict_id}, {"_id": 0})
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict not found")
    
    # Check if conflict already has an optimization
    if conflict.get("optimization_id"):
        # Verify the optimization still exists
        existing_opt = await db.seo_optimizations.find_one(
            {"id": conflict["optimization_id"]},
            {"_id": 0, "id": 1}
        )
        if existing_opt:
            raise HTTPException(
                status_code=400,
                detail="Conflict already has a linked optimization task"
            )
    
    # Get network info
    network = await db.seo_networks.find_one(
        {"id": conflict.get("network_id")},
        {"_id": 0, "name": 1, "brand_id": 1}
    )
    network_name = network.get("name", "Unknown") if network else "Unknown"
    brand_id = network.get("brand_id") if network else None
    
    # Create the optimization
    from services.conflict_optimization_linker_service import get_conflict_linker_service
    linker_service = get_conflict_linker_service(db)
    
    opt_id = await linker_service._create_optimization_for_conflict(
        conflict_id=conflict_id,
        conflict=conflict,
        network_id=conflict.get("network_id"),
        network_name=network_name,
        brand_id=brand_id,
        is_recurring=conflict.get("recurrence_count", 0) > 0,
        recurrence_count=conflict.get("recurrence_count", 0)
    )
    
    if not opt_id:
        raise HTTPException(status_code=500, detail="Failed to create optimization")
    
    # Update conflict with the new optimization link
    await db.seo_conflicts.update_one(
        {"id": conflict_id},
        {"$set": {
            "optimization_id": opt_id,
            "status": "under_review",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {
        "success": True,
        "conflict_id": conflict_id,
        "optimization_id": opt_id,
        "message": "Optimization task created successfully"
    }


@router.post("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: str,
    resolution_note: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Mark a conflict as resolved.
    
    Only managers and super admins can resolve conflicts.
    This should be called after the linked optimization is completed
    AND the structure has been validated.
    """
    # Check permission
    user_role = current_user.get("role", "user")
    if user_role not in ["super_admin", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only managers and super admins can resolve conflicts"
        )
    
    conflict_service = get_conflict_linker_service(db)
    
    result = await conflict_service.resolve_conflict(
        conflict_id=conflict_id,
        resolved_by_user_id=current_user.get("id", ""),
        resolution_note=resolution_note
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Unknown error"))
    
    return result


@router.post("/conflicts/{conflict_id}/approve")
async def approve_conflict(
    conflict_id: str,
    approval_note: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Super Admin approval of a conflict.
    
    IMPORTANT: Approval implies resolution.
    This action will:
    1. Set status to 'approved'
    2. Mark conflict as inactive (is_active = false)
    3. Reset recurrence_count to 0
    4. Set resolved_at timestamp
    5. Remove from all recurring/active conflict lists
    
    Approved conflicts will only appear in audit logs and history (read-only).
    """
    # Check permission - Super Admin only
    user_role = current_user.get("role", "user")
    if user_role != "super_admin":
        raise HTTPException(
            status_code=403,
            detail="Only Super Admins can approve conflicts"
        )
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Update the conflict with approval status
    result = await db.seo_conflicts.find_one_and_update(
        {"id": conflict_id},
        {
            "$set": {
                "status": "approved",
                "is_active": False,  # Deactivate to prevent appearing in recurring
                "recurrence_count": 0,  # Reset recurrence count
                "resolved_at": now,
                "approved_by": current_user.get("id", ""),
                "approved_at": now,
                "updated_at": now,
            }
        },
        return_document=True
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Conflict not found")
    
    # Also complete/cancel any linked optimization
    if result.get("optimization_id"):
        await db.seo_optimizations.update_one(
            {"id": result["optimization_id"]},
            {
                "$set": {
                    "status": "completed",
                    "completed_at": now,
                    "completed_by": current_user.get("id", ""),
                    "notes": f"Auto-completed due to conflict approval. {approval_note or ''}"
                }
            }
        )
    
    return {
        "success": True,
        "message": "Conflict approved and deactivated",
        "conflict_id": conflict_id,
        "status": "approved",
        "is_active": False,
        "approved_by": current_user.get("id", ""),
        "approved_at": now
    }


@router.post("/conflicts/migrate-approved")
async def migrate_approved_conflicts(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    ONE-TIME MIGRATION: Fix legacy conflicts data.
    
    This migration will:
    1. Find all conflicts with status 'resolved' or 'approved' that have is_active=true
    2. Set is_active = false
    3. Reset recurrence_count = 0
    4. Ensure resolved_at is set
    5. Backfill fingerprints for all conflicts
    6. Set first_detected_at from detected_at
    
    Super Admin only.
    """
    user_role = current_user.get("role", "user")
    if user_role != "super_admin":
        raise HTTPException(
            status_code=403,
            detail="Only Super Admins can run migrations"
        )
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Import fingerprint generator
    from services.conflict_metrics_service import generate_conflict_fingerprint
    
    stats = {
        "status_fixed": 0,
        "fingerprints_added": 0,
        "first_detected_set": 0,
        "total_processed": 0
    }
    
    # Find and update all legacy approved/resolved conflicts
    result = await db.seo_conflicts.update_many(
        {
            "status": {"$in": ["resolved", "approved", "ignored"]},
            "$or": [
                {"is_active": True},
                {"is_active": {"$exists": False}},
                {"recurrence_count": {"$gt": 0}}
            ]
        },
        {
            "$set": {
                "is_active": False,
                "recurrence_count": 0,
                "updated_at": now,
            },
            "$setOnInsert": {
                "resolved_at": now
            }
        }
    )
    stats["status_fixed"] = result.modified_count
    
    # Also ensure all conflicts have is_active field
    await db.seo_conflicts.update_many(
        {"is_active": {"$exists": False}},
        {"$set": {"is_active": True}}
    )
    
    # Backfill fingerprints for conflicts without them
    conflicts_no_fp = await db.seo_conflicts.find(
        {"$or": [{"fingerprint": None}, {"fingerprint": ""}, {"fingerprint": {"$exists": False}}]},
        {"_id": 0}
    ).to_list(5000)
    
    for conflict in conflicts_no_fp:
        conflict_id = conflict.get("id")
        if not conflict_id:
            continue
        
        update_data = {"updated_at": now}
        
        # Generate fingerprint
        fingerprint = generate_conflict_fingerprint(
            network_id=conflict.get("network_id", ""),
            conflict_type=conflict.get("conflict_type", ""),
            domain_id=conflict.get("domain_id") or conflict.get("node_a_id", ""),
            node_path=conflict.get("node_a_path", ""),
            tier=conflict.get("node_a_tier"),
            target_path=conflict.get("target_path") or conflict.get("node_b_path", "")
        )
        update_data["fingerprint"] = fingerprint
        stats["fingerprints_added"] += 1
        
        # Set first_detected_at if missing
        if not conflict.get("first_detected_at") and conflict.get("detected_at"):
            update_data["first_detected_at"] = conflict.get("detected_at")
            stats["first_detected_set"] += 1
        
        # Initialize missing fields
        if conflict.get("is_false_resolution") is None:
            update_data["is_false_resolution"] = False
        if conflict.get("recurrence_history") is None:
            update_data["recurrence_history"] = []
        
        await db.seo_conflicts.update_one(
            {"id": conflict_id},
            {"$set": update_data}
        )
        stats["total_processed"] += 1
    
    return {
        "success": True,
        "message": "Migration complete",
        "stats": stats
    }


@router.get("/conflicts/metrics")
async def get_conflict_metrics(
    network_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    days: int = 30,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get comprehensive conflict resolution metrics.
    
    Production-grade dashboard metrics with:
    - Fingerprint-based recurrence detection
    - Status derived from linked optimizations
    - Accurate resolution time calculations (first_detected_at → completed_at)
    - Filtered top resolvers (excludes system/null users)
    - False resolution rate tracking
    - Recurrence interval analysis
    
    Returns all P0 and P1 metrics for the dashboard.
    """
    metrics_service = get_conflict_metrics_service(db)
    
    metrics = await metrics_service.get_dashboard_metrics(
        network_id=network_id,
        brand_id=brand_id,
        days=days
    )
    
    return metrics


# ==================== TELEGRAM ALERT ENDPOINTS ====================


@router.post("/alerts/send-conflicts")
async def send_conflict_alerts(current_user: dict = Depends(get_current_user_wrapper)):
    """Send all V3 conflicts as Telegram alerts"""
    # Get conflicts
    conflicts = []

    networks = await db.seo_networks.find({}, {"_id": 0}).to_list(1000)

    for network in networks:
        if not tier_service:
            continue

        tiers = await tier_service.calculate_network_tiers(network["id"])
        entries = await db.seo_structure_entries.find(
            {"network_id": network["id"]}, {"_id": 0}
        ).to_list(10000)

        for entry in entries:
            asset_id = entry["asset_domain_id"]
            tier = tiers.get(asset_id, 5)

            asset = await db.asset_domains.find_one(
                {"id": asset_id}, {"_id": 0, "domain_name": 1}
            )
            domain_name = asset["domain_name"] if asset else asset_id

            if entry.get("index_status") == "noindex" and tier <= 2:
                conflicts.append(
                    {
                        "type": "NOINDEX in high tier",
                        "severity": "🔴 HIGH",
                        "network": network["name"],
                        "domain": domain_name,
                        "tier": get_tier_label(tier),
                    }
                )

            if (
                entry.get("domain_role") != "main"
                and not entry.get("target_asset_domain_id")
                and tier >= 5
            ):
                conflicts.append(
                    {
                        "type": "Orphan domain",
                        "severity": "🟡 MEDIUM",
                        "network": network["name"],
                        "domain": domain_name,
                        "tier": get_tier_label(tier),
                    }
                )

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
        "conflicts": len(conflicts),
    }


@router.post("/alerts/test")
async def send_v3_test_alert(current_user: dict = Depends(get_current_user_wrapper)):
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
        raise HTTPException(
            status_code=500,
            detail="Failed to send V3 test alert. Check Telegram configuration.",
        )


@router.post("/alerts/domain-change")
async def send_domain_change_alert(
    asset_domain_id: str,
    action: str,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Send alert when a domain is changed"""
    asset = await db.asset_domains.find_one({"id": asset_domain_id}, {"_id": 0})

    if not asset:
        raise HTTPException(status_code=404, detail="Asset domain not found")

    action_emoji = {"create": "➕", "update": "✏️", "delete": "🗑️"}.get(
        action.lower(), "📝"
    )

    message = f"""<b>{action_emoji} Domain {action.capitalize()}</b>

<b>Domain:</b> <code>{asset['domain_name']}</code>
<b>Status:</b> {asset.get('status', 'N/A')}
<b>Monitoring:</b> {'✅ Enabled' if asset.get('monitoring_enabled') else '❌ Disabled'}

<i>By: {current_user['email']}</i>
<i>Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</i>"""

    success = await send_v3_telegram_alert(message)

    return {
        "message": "Alert sent" if success else "Failed to send alert",
        "success": success,
    }


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
    request: BulkImportRequest, current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Bulk import asset domains from CSV data.

    Expected fields: domain_name, brand_name (optional), registrar (optional),
    expiration_date (optional), status (optional), notes (optional)
    """
    results = {"imported": 0, "skipped": 0, "errors": [], "details": []}

    # Get brand mapping
    brands = await db.brands.find({}, {"_id": 0}).to_list(1000)
    brand_map = {b["name"].lower(): b["id"] for b in brands}

    for item in request.domains:
        try:
            # Check for duplicate
            existing = await db.asset_domains.find_one(
                {"domain_name": item.domain_name}
            )
            if existing:
                if request.skip_duplicates:
                    results["skipped"] += 1
                    results["details"].append(
                        {
                            "domain": item.domain_name,
                            "status": "skipped",
                            "reason": "Domain already exists",
                        }
                    )
                    continue
                else:
                    results["errors"].append(
                        {"domain": item.domain_name, "error": "Domain already exists"}
                    )
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
                        "updated_at": datetime.now(timezone.utc).isoformat(),
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
                "updated_at": now,
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
                    metadata={"source": "bulk_import"},
                )

            results["imported"] += 1
            results["details"].append(
                {"domain": item.domain_name, "status": "imported", "id": asset["id"]}
            )

        except Exception as e:
            results["errors"].append({"domain": item.domain_name, "error": str(e)})

    return results


@router.get("/import/template")
async def get_import_template(current_user: dict = Depends(get_current_user_wrapper)):
    """Get CSV template for bulk import"""
    return {
        "headers": [
            "domain_name",
            "brand_name",
            "registrar",
            "expiration_date",
            "status",
            "notes",
        ],
        "example_row": [
            "example.com",
            "MyBrand",
            "GoDaddy",
            "2026-12-31",
            "active",
            "Main site",
        ],
        "status_options": ["active", "inactive", "pending", "expired"],
        "notes": "domain_name is required. Other fields are optional.",
    }


# ==================== EXPORT ENDPOINTS ====================


@router.get("/export/asset-domains")
async def export_asset_domains(
    format: str = Query("json", enum=["json", "csv"]),
    brand_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Export asset domains to JSON or CSV"""
    query = {}
    if brand_id:
        query["brand_id"] = brand_id
    if status:
        query["status"] = status

    assets = await db.asset_domains.find(query, {"_id": 0}).to_list(10000)

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
    registrars = {
        r["id"]: r["name"]
        for r in await db.registrars.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(
            1000
        )
    }

    for asset in assets:
        asset["brand_name"] = brands.get(asset.get("brand_id"), "")
        asset["category_name"] = categories.get(asset.get("category_id"), "")
        asset["registrar_name"] = registrars.get(
            asset.get("registrar_id")
        ) or asset.get("registrar", "")

    if format == "csv":
        import csv
        import io

        output = io.StringIO()
        fieldnames = [
            "domain_name",
            "brand_name",
            "category_name",
            "registrar_name",
            "status",
            "expiration_date",
            "auto_renew",
            "monitoring_enabled",
            "ping_status",
            "http_status",
            "notes",
            "created_at",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(assets)

        from fastapi.responses import Response

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=asset_domains_export.csv"
            },
        )

    return {
        "data": assets,
        "total": len(assets),
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/export/networks/{network_id}")
async def export_network_structure(
    network_id: str,
    format: str = Query("json", enum=["json", "csv"]),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Export a network with full structure (entries, relationships, tiers)"""
    network = await db.seo_networks.find_one({"id": network_id}, {"_id": 0})
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")

    # Get brand name
    if network.get("brand_id"):
        brand = await db.brands.find_one(
            {"id": network["brand_id"]}, {"_id": 0, "name": 1}
        )
        network["brand_name"] = brand["name"] if brand else ""

    # Get all entries with tiers
    entries = await db.seo_structure_entries.find(
        {"network_id": network_id}, {"_id": 0}
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
        {"id": {"$in": domain_ids}}, {"_id": 0, "id": 1, "domain_name": 1}
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
                target_domain = domain_lookup.get(
                    target_entry.get("asset_domain_id"), ""
                )
                target_node_label = target_domain
                if target_entry.get("optimized_path"):
                    target_node_label = (
                        f"{target_domain}{target_entry['optimized_path']}"
                    )
        elif entry.get("target_asset_domain_id"):
            target_node_label = domain_lookup.get(entry["target_asset_domain_id"], "")

        enriched_entries.append(
            {
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
                "notes": entry.get("notes", ""),
            }
        )

    if format == "csv":
        import csv
        import io

        output = io.StringIO()
        fieldnames = [
            "domain_name",
            "optimized_path",
            "node_label",
            "domain_role",
            "domain_status",
            "index_status",
            "target_node",
            "calculated_tier",
            "tier_label",
            "ranking_url",
            "primary_keyword",
            "ranking_position",
            "notes",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(enriched_entries)

        from fastapi.responses import Response

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=network_{network['name']}_export.csv"
            },
        )

    return {
        "network": {
            "id": network["id"],
            "name": network["name"],
            "brand_name": network.get("brand_name", ""),
            "description": network.get("description", ""),
            "status": network.get("status", "active"),
        },
        "entries": enriched_entries,
        "total_entries": len(enriched_entries),
        "tier_distribution": {
            get_tier_label(i): len(
                [e for e in enriched_entries if e["calculated_tier"] == i]
            )
            for i in range(6)
        },
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/export/networks")
async def export_all_networks(
    format: str = Query("json", enum=["json", "csv"]),
    brand_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Export all networks with metadata"""
    query = {}
    if brand_id:
        query["brand_id"] = brand_id

    networks = await db.seo_networks.find(query, {"_id": 0}).to_list(1000)

    # Enrich with brand names and domain counts
    brands = {
        b["id"]: b["name"]
        for b in await db.brands.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)
    }

    for network in networks:
        network["brand_name"] = brands.get(network.get("brand_id"), "")
        network["domain_count"] = await db.seo_structure_entries.count_documents(
            {"network_id": network["id"]}
        )

    if format == "csv":
        import csv
        import io

        output = io.StringIO()
        fieldnames = [
            "name",
            "brand_name",
            "description",
            "status",
            "domain_count",
            "created_at",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(networks)

        from fastapi.responses import Response

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=networks_export.csv"},
        )

    return {
        "data": networks,
        "total": len(networks),
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/export/activity-logs")
async def export_activity_logs(
    format: str = Query("json", enum=["json", "csv"]),
    entity_type: Optional[str] = None,
    action_type: Optional[str] = None,
    actor: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(get_current_user_wrapper),
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

    logs = (
        await db.activity_logs_v3.find(query, {"_id": 0})
        .sort("timestamp", -1)
        .to_list(10000)
    )

    if format == "csv":
        import csv
        import io

        # Flatten before/after for CSV
        flattened = []
        for log in logs:
            flattened.append(
                {
                    "timestamp": log.get("timestamp", ""),
                    "actor": log.get("actor", ""),
                    "action_type": log.get("action_type", ""),
                    "entity_type": log.get("entity_type", ""),
                    "entity_id": log.get("entity_id", ""),
                    "summary": log.get("summary", ""),
                }
            )

        output = io.StringIO()
        fieldnames = [
            "timestamp",
            "actor",
            "action_type",
            "entity_type",
            "entity_id",
            "summary",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(flattened)

        from fastapi.responses import Response

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=activity_logs_export.csv"
            },
        )

    return {
        "data": logs,
        "total": len(logs),
        "exported_at": datetime.now(timezone.utc).isoformat(),
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
    target_path: Optional[str] = None  # Path of target node
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
    current_user: dict = Depends(get_current_user_wrapper),
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

    results = {"imported": [], "skipped": [], "errors": [], "domains_created": []}

    # First pass: ensure all domains exist and build lookup
    domain_lookup = {}  # domain_name -> asset_domain_id
    all_domains = await db.asset_domains.find(
        {}, {"_id": 0, "id": 1, "domain_name": 1}
    ).to_list(10000)
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
                    "updated_at": now,
                }
                await db.asset_domains.insert_one(new_domain)
                domain_lookup[domain_lower] = new_domain["id"]
                results["domains_created"].append(node.domain_name)

    # Second pass: create entries and build entry lookup
    entry_lookup = {}  # (domain_name.lower, path) -> entry_id

    # Load existing entries for this network
    existing_entries = await db.seo_structure_entries.find(
        {"network_id": request.network_id}, {"_id": 0}
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
                results["errors"].append(
                    {
                        "domain": node.domain_name,
                        "error": f"Domain not found: {node.domain_name}",
                    }
                )
                continue

            # Check if entry already exists
            entry_key = (domain_lower, node.optimized_path or "")
            if entry_key in entry_lookup:
                results["skipped"].append(
                    {
                        "domain": node.domain_name,
                        "path": node.optimized_path,
                        "reason": "Entry already exists",
                    }
                )
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
                "target_path": node.target_path,  # Temp storage
                "ranking_url": node.ranking_url,
                "primary_keyword": node.primary_keyword,
                "notes": node.notes,
                "created_at": now,
                "updated_at": now,
            }

            entries_to_create.append(entry)
            entry_lookup[entry_key] = entry["id"]

        except Exception as e:
            results["errors"].append({"domain": node.domain_name, "error": str(e)})

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
                    if dname == target_domain.lower() and (
                        not target_path or path == target_path
                    ):
                        entry["target_entry_id"] = eid
                        break

        await db.seo_structure_entries.insert_one(entry)
        results["imported"].append(
            {
                "domain": entry.get("domain_name", ""),
                "path": entry.get("optimized_path", ""),
                "entry_id": entry["id"],
            }
        )

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
                "errors": len(results["errors"]),
            },
        )

    return {
        "success": True,
        "summary": {
            "imported": len(results["imported"]),
            "skipped": len(results["skipped"]),
            "errors": len(results["errors"]),
            "domains_created": len(results["domains_created"]),
        },
        "details": results,
    }


@router.get("/import/nodes/template")
async def get_node_import_template(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get CSV template for bulk node import"""
    return {
        "headers": [
            "domain_name",
            "optimized_path",
            "domain_role",
            "domain_status",
            "index_status",
            "target_domain",
            "target_path",
            "ranking_url",
            "primary_keyword",
            "notes",
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
                "notes": "Money site",
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
                "notes": "Tier 1 supporting blog",
            },
        ],
        "role_options": ["main", "supporting"],
        "status_options": ["canonical", "redirect_301", "redirect_302"],
        "index_options": ["index", "noindex"],
        "notes": [
            "domain_name is required",
            "optimized_path is optional (leave empty for domain-level nodes)",
            "target_domain + target_path define the relationship to another node",
            "main role should have no target (it's the root)",
        ],
    }


# ==================== SETTINGS ENDPOINTS ====================


@router.get("/settings/dashboard-refresh")
async def get_dashboard_refresh_setting(
    current_user: dict = Depends(get_current_user_wrapper),
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
            {"value": 900, "label": "15 minutes"},
        ],
    }


@router.put("/settings/dashboard-refresh")
async def update_dashboard_refresh_setting(
    interval: int = Query(..., ge=0, le=900),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Update dashboard refresh interval setting"""
    user_id = current_user.get("id")

    valid_intervals = [0, 30, 60, 300, 900]
    if interval not in valid_intervals:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interval. Must be one of: {valid_intervals}",
        )

    now = datetime.now(timezone.utc).isoformat()

    await db.user_preferences.update_one(
        {"user_id": user_id},
        {
            "$set": {"dashboard_refresh_interval": interval, "updated_at": now},
            "$setOnInsert": {"user_id": user_id, "created_at": now},
        },
        upsert=True,
    )

    return {"success": True, "refresh_interval": interval}


@router.get("/dashboard/stats")
async def get_dashboard_stats_only(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get lightweight dashboard stats for auto-refresh (no heavy computations)"""
    # Apply brand filtering for non-super-admin users
    brand_filter = build_brand_filter(current_user)

    # Domain filters
    domain_base_filter = brand_filter.copy() if brand_filter else {}
    domain_active_filter = {**domain_base_filter, "status": "active"}
    domain_monitored_filter = {**domain_base_filter, "monitoring_enabled": True}
    domain_up_filter = {**domain_base_filter, "ping_status": "up"}
    domain_down_filter = {**domain_base_filter, "ping_status": "down"}

    # Network filter
    network_filter = brand_filter.copy() if brand_filter else {}

    stats = {
        "total_domains": await db.asset_domains.count_documents(domain_base_filter),
        "total_networks": await db.seo_networks.count_documents(network_filter),
        "active_domains": await db.asset_domains.count_documents(domain_active_filter),
        "monitored_count": await db.asset_domains.count_documents(
            domain_monitored_filter
        ),
        "indexed_count": await db.seo_structure_entries.count_documents(
            {"index_status": "index"}
        ),
        "noindex_count": await db.seo_structure_entries.count_documents(
            {"index_status": "noindex"}
        ),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    stats["ping_up"] = await db.asset_domains.count_documents(domain_up_filter)
    stats["ping_down"] = await db.asset_domains.count_documents(domain_down_filter)
    stats["active_alerts"] = await db.alerts.count_documents({"acknowledged": False})

    return stats


# ==================== MONITORING ENDPOINTS ====================


@router.get("/monitoring/settings")
async def get_monitoring_settings(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get monitoring configuration settings"""
    from services.monitoring_service import MonitoringSettingsService

    settings_service = MonitoringSettingsService(db)
    settings = await settings_service.get_settings()
    return settings


@router.put("/monitoring/settings")
async def update_monitoring_settings(
    updates: MonitoringSettingsUpdate,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Update monitoring configuration settings (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=403, detail="Only super admins can update monitoring settings"
        )

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
async def get_monitoring_stats(current_user: dict = Depends(get_current_user_wrapper)):
    """Get current monitoring statistics"""
    now = datetime.now(timezone.utc)

    # Availability stats
    total_monitored = await db.asset_domains.count_documents(
        {"monitoring_enabled": True}
    )
    up_count = await db.asset_domains.count_documents(
        {"monitoring_enabled": True, "ping_status": "up"}
    )
    down_count = await db.asset_domains.count_documents(
        {"monitoring_enabled": True, "ping_status": "down"}
    )
    unknown_count = await db.asset_domains.count_documents(
        {"monitoring_enabled": True, "ping_status": {"$nin": ["up", "down"]}}
    )

    # Expiration stats
    from datetime import timedelta

    week_later = (now + timedelta(days=7)).isoformat()
    month_later = (now + timedelta(days=30)).isoformat()

    expiring_7_days = await db.asset_domains.count_documents(
        {"expiration_date": {"$ne": None, "$lte": week_later, "$gt": now.isoformat()}}
    )

    expiring_30_days = await db.asset_domains.count_documents(
        {"expiration_date": {"$ne": None, "$lte": month_later, "$gt": now.isoformat()}}
    )

    expired = await db.asset_domains.count_documents(
        {"expiration_date": {"$ne": None, "$lte": now.isoformat()}}
    )

    # Alert stats
    monitoring_alerts = await db.alerts.count_documents(
        {"alert_type": "monitoring", "acknowledged": False}
    )
    expiration_alerts = await db.alerts.count_documents(
        {"alert_type": "expiration", "acknowledged": False}
    )

    return {
        "availability": {
            "total_monitored": total_monitored,
            "up": up_count,
            "down": down_count,
            "unknown": unknown_count,
        },
        "expiration": {
            "expiring_7_days": expiring_7_days,
            "expiring_30_days": expiring_30_days,
            "expired": expired,
        },
        "alerts": {
            "monitoring_unacknowledged": monitoring_alerts,
            "expiration_unacknowledged": expiration_alerts,
        },
        "updated_at": now.isoformat(),
    }


@router.post("/monitoring/check-expiration")
async def trigger_expiration_check(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user_wrapper),
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
    current_user: dict = Depends(get_current_user_wrapper),
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
    current_user: dict = Depends(get_current_user_wrapper),
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
    result = await availability_service._check_domain_availability(
        domain, avail_settings
    )

    return {
        "domain_name": domain["domain_name"],
        "status": result["status"],
        "http_code": result.get("http_code"),
        "alert_sent": result.get("alert_sent", False),
    }


@router.get("/monitoring/expiring-domains")
async def get_expiring_domains(
    days: int = Query(default=30, ge=1, le=365),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get list of domains expiring within specified days"""
    now = datetime.now(timezone.utc)
    cutoff = (now + timedelta(days=days)).isoformat()

    domains = (
        await db.asset_domains.find(
            {"expiration_date": {"$ne": None, "$lte": cutoff}}, {"_id": 0}
        )
        .sort("expiration_date", 1)
        .to_list(1000)
    )

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
            brand = await db.brands.find_one(
                {"id": domain["brand_id"]}, {"_id": 0, "name": 1}
            )
            brand_name = brand["name"] if brand else None

        result.append(
            {
                "id": domain["id"],
                "domain_name": domain["domain_name"],
                "brand_name": brand_name,
                "expiration_date": exp_date[:10] if exp_date else None,
                "days_remaining": days_remaining,
                "auto_renew": domain.get("auto_renew", False),
                "registrar": domain.get("registrar"),
                "status": (
                    "expired"
                    if days_remaining and days_remaining < 0
                    else (
                        "critical"
                        if days_remaining and days_remaining <= 3
                        else (
                            "warning"
                            if days_remaining and days_remaining <= 7
                            else "upcoming"
                        )
                    )
                ),
            }
        )

    return {"domains": result, "total": len(result), "query_days": days}


@router.get("/monitoring/down-domains")
async def get_down_domains(current_user: dict = Depends(get_current_user_wrapper)):
    """Get list of domains currently down"""
    domains = await db.asset_domains.find(
        {"monitoring_enabled": True, "ping_status": "down"}, {"_id": 0}
    ).to_list(1000)

    result = []
    for domain in domains:
        # Get brand name
        brand_name = None
        if domain.get("brand_id"):
            brand = await db.brands.find_one(
                {"id": domain["brand_id"]}, {"_id": 0, "name": 1}
            )
            brand_name = brand["name"] if brand else None

        # Check if in SEO network
        entry = await db.seo_structure_entries.find_one(
            {"asset_domain_id": domain["id"]},
            {"_id": 0, "network_id": 1, "domain_role": 1},
        )

        network_name = None
        if entry:
            network = await db.seo_networks.find_one(
                {"id": entry["network_id"]}, {"_id": 0, "name": 1}
            )
            network_name = network["name"] if network else None

        result.append(
            {
                "id": domain["id"],
                "domain_name": domain["domain_name"],
                "brand_name": brand_name,
                "last_http_code": domain.get("last_http_code")
                or domain.get("http_status_code"),
                "last_checked_at": domain.get("last_checked_at")
                or domain.get("last_check"),
                "network_name": network_name,
                "domain_role": entry.get("domain_role") if entry else None,
            }
        )

    return {"domains": result, "total": len(result)}


# ==================== FORCED MONITORING & TEST ALERTS ====================


class TestAlertRequest(BaseModel):
    """Request model for test domain down alert"""
    domain: str = Field(..., description="Domain name to simulate alert for")
    issue_type: str = Field(default="DOWN", description="DOWN or SOFT_BLOCKED")
    reason: str = Field(default="Timeout", description="Timeout, JS Challenge, Country Block, etc.")
    force_severity: Optional[str] = Field(default=None, description="LOW, MEDIUM, HIGH, CRITICAL")


@router.get("/monitoring/unmonitored-in-seo")
async def get_unmonitored_domains_in_seo(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Get all domains used in SEO networks that don't have monitoring enabled.
    
    These domains SHOULD have monitoring enabled because:
    - If the root domain goes DOWN, all paths become inaccessible
    - SEO network integrity depends on domain availability
    """
    from services.forced_monitoring_service import ForcedMonitoringService
    
    service = ForcedMonitoringService(db)
    unmonitored = await service.get_unmonitored_domains_in_seo()
    
    return {
        "unmonitored_domains": unmonitored,
        "total": len(unmonitored),
        "warning": "These domains are used in SEO networks but don't have monitoring enabled."
    }


@router.get("/monitoring/domain-seo-usage/{domain_id}")
async def check_domain_seo_usage(
    domain_id: str,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Check if a specific domain is used in any SEO network and its monitoring status.
    
    Returns:
    - Whether domain is used in SEO
    - Whether monitoring is required (true if used in SEO)
    - List of networks where domain is used
    """
    from services.forced_monitoring_service import ForcedMonitoringService
    
    service = ForcedMonitoringService(db)
    usage = await service.check_domain_seo_usage(domain_id)
    
    return usage


@router.post("/monitoring/send-unmonitored-reminders")
async def send_unmonitored_reminders(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Send reminder notifications for unmonitored domains in SEO networks.
    
    Rate limited to once per 24 hours to avoid spam.
    """
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin role required")
    
    from services.forced_monitoring_service import ForcedMonitoringService
    
    service = ForcedMonitoringService(db)
    
    async def send_reminders():
        result = await service.send_unmonitored_reminders()
        logger.info(f"Unmonitored domain reminder result: {result}")
    
    background_tasks.add_task(send_reminders)
    
    return {"message": "Reminder check scheduled", "status": "running"}


@router.post("/monitoring/domain-down/test")
async def send_test_domain_down_alert(
    request: TestAlertRequest,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Send a TEST domain down alert without affecting real monitoring data.
    
    Purpose:
    - Validate Telegram format
    - Validate SEO context enrichment
    - Test chain traversal & impact scoring
    - Train team without real downtime
    
    Test alerts:
    - Do NOT change real domain status
    - Do NOT affect monitoring schedules
    - Include 🧪 TEST MODE marker
    - Are logged separately from real incidents
    """
    if current_user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin role required")
    
    # Validate issue_type
    if request.issue_type not in ["DOWN", "SOFT_BLOCKED"]:
        raise HTTPException(status_code=400, detail="issue_type must be DOWN or SOFT_BLOCKED")
    
    # Validate force_severity if provided
    if request.force_severity and request.force_severity.upper() not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        raise HTTPException(status_code=400, detail="force_severity must be LOW, MEDIUM, HIGH, or CRITICAL")
    
    from services.forced_monitoring_service import TestAlertService
    
    service = TestAlertService(db)
    result = await service.send_test_domain_down_alert(
        domain_name=request.domain,
        issue_type=request.issue_type,
        reason=request.reason,
        force_severity=request.force_severity,
        actor_id=current_user.get("id"),
        actor_email=current_user.get("email")
    )
    
    return result


@router.get("/monitoring/test-alerts/history")
async def get_test_alert_history(
    limit: int = Query(default=50, le=200),
    domain: Optional[str] = None,
    current_user: dict = Depends(get_current_user_wrapper)
):
    """Get history of test alerts."""
    from services.forced_monitoring_service import TestAlertService
    
    service = TestAlertService(db)
    history = await service.get_test_alert_history(limit=limit, domain=domain)
    
    return {"history": history, "total": len(history)}


@router.get("/monitoring/seo-domains-summary")
async def get_seo_domains_monitoring_summary(
    current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Get a summary of monitoring status for all domains used in SEO networks.
    
    Returns:
    - Total domains in SEO networks
    - Monitored count
    - Unmonitored count (these need attention)
    - By network breakdown
    """
    # Get all unique domain IDs used in SEO
    pipeline = [
        {"$match": {"asset_domain_id": {"$exists": True, "$ne": None}}},
        {"$group": {
            "_id": "$asset_domain_id",
            "networks": {"$addToSet": "$network_id"}
        }}
    ]
    
    seo_domains = await db.seo_structure_entries.aggregate(pipeline).to_list(None)
    domain_ids = [d["_id"] for d in seo_domains if d["_id"]]
    
    if not domain_ids:
        return {
            "total_seo_domains": 0,
            "monitored": 0,
            "unmonitored": 0,
            "monitoring_coverage": 100
        }
    
    # Count monitored vs unmonitored
    monitored_count = await db.asset_domains.count_documents({
        "id": {"$in": domain_ids},
        "monitoring_enabled": True
    })
    
    total = len(domain_ids)
    unmonitored = total - monitored_count
    coverage = (monitored_count / total * 100) if total > 0 else 100
    
    return {
        "total_seo_domains": total,
        "monitored": monitored_count,
        "unmonitored": unmonitored,
        "monitoring_coverage": round(coverage, 1),
        "status": "good" if coverage >= 100 else "warning" if coverage >= 80 else "critical"
    }


# ==================== SEO CHANGE LOG ENDPOINTS ====================


@router.get(
    "/networks/{network_id}/change-history", response_model=List[SeoChangeLogResponse]
)
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
    current_user: dict = Depends(get_current_user_wrapper),
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
    logs = (
        await db.seo_change_logs.find(query, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )

    # Helper function to enrich snapshot with human-readable labels
    async def enrich_snapshot(snapshot):
        if not snapshot:
            return None

        enriched = dict(snapshot)

        # Translate target_entry_id to node_label
        if enriched.get("target_entry_id"):
            target = await db.seo_structure_entries.find_one(
                {"id": enriched["target_entry_id"]},
                {"_id": 0, "asset_domain_id": 1, "optimized_path": 1},
            )
            if target:
                domain = await db.asset_domains.find_one(
                    {"id": target["asset_domain_id"]}, {"_id": 0, "domain_name": 1}
                )
                enriched["target_node_label"] = (
                    f"{domain['domain_name'] if domain else 'unknown'}{target.get('optimized_path', '') or ''}"
                )

        # Translate status codes to labels
        status_labels = {
            "primary": "Primary Target",
            "canonical": "Canonical",
            "301_redirect": "301 Redirect",
            "302_redirect": "302 Redirect",
            "restore": "Restore",
        }
        if enriched.get("domain_status"):
            enriched["domain_status_label"] = status_labels.get(
                enriched["domain_status"], enriched["domain_status"]
            )

        # Translate role to labels
        role_labels = {"main": "Main (LP/Money Site)", "supporting": "Supporting"}
        if enriched.get("domain_role"):
            enriched["domain_role_label"] = role_labels.get(
                enriched["domain_role"], enriched["domain_role"]
            )

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
            brand = await db.brands.find_one(
                {"id": log["brand_id"]}, {"_id": 0, "name": 1}
            )
            log["brand_name"] = brand["name"] if brand else None

        # Enrich before/after snapshots with human-readable labels
        log["before_snapshot"] = await enrich_snapshot(log.get("before_snapshot"))
        log["after_snapshot"] = await enrich_snapshot(log.get("after_snapshot"))

        enriched.append(SeoChangeLogResponse(**log))

    return enriched


@router.get(
    "/networks/{network_id}/notifications", response_model=List[SeoNetworkNotification]
)
async def get_network_notifications(
    network_id: str,
    unread_only: bool = False,
    skip: int = 0,
    limit: int = Query(default=20, le=100),
    current_user: dict = Depends(get_current_user_wrapper),
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
        network_id=network_id, unread_only=unread_only, skip=skip, limit=limit
    )

    # Enrich with network name
    for notif in notifications:
        notif["network_name"] = network.get("name")

    return [SeoNetworkNotification(**n) for n in notifications]


@router.post("/networks/{network_id}/notifications/{notification_id}/read")
async def mark_notification_read(
    network_id: str,
    notification_id: str,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Mark a notification as read"""
    if not seo_change_log_service:
        raise HTTPException(
            status_code=500, detail="SEO change log service not initialized"
        )

    success = await seo_change_log_service.mark_notification_read(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")

    return {"message": "Notification marked as read"}


@router.post("/networks/{network_id}/notifications/read-all")
async def mark_all_notifications_read(
    network_id: str, current_user: dict = Depends(get_current_user_wrapper)
):
    """Mark all notifications in a network as read"""
    if not seo_change_log_service:
        raise HTTPException(
            status_code=500, detail="SEO change log service not initialized"
        )

    count = await seo_change_log_service.mark_all_notifications_read(network_id)
    return {"message": f"Marked {count} notifications as read", "count": count}


@router.get("/change-logs/stats")
async def get_change_log_stats(
    days: int = Query(default=30, ge=1, le=365),
    current_user: dict = Depends(get_current_user_wrapper),
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
        brand_ids=brand_scope, days=days
    )

    # Enrich with network names
    if stats.get("changes_by_network"):
        network_ids = [c["_id"] for c in stats["changes_by_network"]]
        networks = await db.seo_networks.find(
            {"id": {"$in": network_ids}}, {"_id": 0, "id": 1, "name": 1}
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
            response = await client.post(
                url,
                json={
                    "chat_id": settings["chat_id"],
                    "text": message,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send SEO Telegram alert: {e}")
        return False


@router.put("/settings/telegram-seo")
async def update_telegram_seo_settings(
    settings: dict, current_user: dict = Depends(get_current_user_wrapper)
):
    """Update SEO Telegram channel settings with forum topic support"""
    # Require super_admin for settings
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=403, detail="Only super admin can update Telegram settings"
        )

    # Get existing settings first
    existing = await db.settings.find_one({"key": "telegram_seo"}, {"_id": 0})

    # Build update dict - only update provided fields
    update_data = {
        "key": "telegram_seo",
        "updated_at": datetime.now(timezone.utc).isoformat(),
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
        update_data["enable_topic_routing"] = existing.get(
            "enable_topic_routing", False
        )

    # Topic IDs for forum routing
    topic_fields = [
        "seo_change_topic_id",
        "seo_optimization_topic_id",
        "seo_complaint_topic_id",
        "seo_reminder_topic_id",
    ]
    for field in topic_fields:
        if field in settings:
            update_data[field] = settings[field] if settings[field] else None
        elif existing and existing.get(field):
            update_data[field] = existing[field]

    # SEO Leader Telegram usernames (for global tagging on all SEO notifications)
    # Support multiple leaders as comma-separated or array
    if "seo_leader_telegram_usernames" in settings:
        leaders = settings["seo_leader_telegram_usernames"]
        # Handle both string (comma-separated) and list
        if isinstance(leaders, str):
            leaders = [name.strip() for name in leaders.split(",") if name.strip()]
        update_data["seo_leader_telegram_usernames"] = leaders if leaders else []
    elif existing and existing.get("seo_leader_telegram_usernames"):
        update_data["seo_leader_telegram_usernames"] = existing["seo_leader_telegram_usernames"]
    # Also handle legacy single field
    elif "seo_leader_telegram_username" in settings:
        single_leader = settings["seo_leader_telegram_username"]
        update_data["seo_leader_telegram_usernames"] = [single_leader] if single_leader else []
    elif existing and existing.get("seo_leader_telegram_username"):
        update_data["seo_leader_telegram_usernames"] = [existing["seo_leader_telegram_username"]]

    await db.settings.update_one(
        {"key": "telegram_seo"}, {"$set": update_data}, upsert=True
    )

    return {
        "message": "SEO Telegram settings updated",
        "settings": {k: v for k, v in update_data.items() if k != "key"},
    }


@router.get("/settings/telegram-seo")
async def get_telegram_seo_settings(
    current_user: dict = Depends(get_current_user_wrapper),
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
            "seo_reminder_topic_id": None,
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
        "seo_reminder_topic_id": settings.get("seo_reminder_topic_id"),
        "seo_leader_telegram_usernames": settings.get("seo_leader_telegram_usernames", []),
    }


@router.post("/settings/telegram-seo/test")
async def test_telegram_seo_alert(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Send a test message to SEO Telegram channel"""
    # Use the new service if available
    if seo_telegram_service:
        success = await seo_telegram_service.send_test_notification(
            current_user["email"]
        )
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
        return {
            "message": "Test message sent successfully / Pesan test berhasil dikirim"
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to send test message. Check Telegram configuration.",
        )


# ==================== DOMAIN MONITORING TELEGRAM SETTINGS ====================


@router.get("/settings/telegram-monitoring")
async def get_telegram_monitoring_settings(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get dedicated Domain Monitoring Telegram configuration.
    This is SEPARATE from SEO notifications.
    """
    settings = await db.settings.find_one({"key": "telegram_monitoring"}, {"_id": 0})
    if not settings:
        return {
            "configured": False,
            "enabled": True,
            "chat_id": None,
            "bot_token": None,
        }

    return {
        "configured": bool(settings.get("bot_token") and settings.get("chat_id")),
        "enabled": settings.get("enabled", True),
        "chat_id": settings.get("chat_id"),
        "bot_token": settings.get("bot_token"),
    }


@router.put("/settings/telegram-monitoring")
async def update_telegram_monitoring_settings(
    settings: dict, current_user: dict = Depends(get_current_user_wrapper)
):
    """
    Update dedicated Domain Monitoring Telegram configuration.
    This channel is for domain expiration and availability alerts ONLY.
    NO fallback to SEO Telegram - must be configured separately.
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(
            status_code=403, detail="Only Super Admin can update Telegram settings"
        )

    # Get existing settings
    existing = await db.settings.find_one({"key": "telegram_monitoring"}, {"_id": 0})

    update_data = {
        "key": "telegram_monitoring",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Bot token (required for separate channel)
    if "bot_token" in settings and settings["bot_token"]:
        update_data["bot_token"] = settings["bot_token"]
    elif existing and existing.get("bot_token"):
        update_data["bot_token"] = existing["bot_token"]

    # Chat ID (required)
    if "chat_id" in settings and settings["chat_id"]:
        update_data["chat_id"] = settings["chat_id"]
    elif existing and existing.get("chat_id"):
        update_data["chat_id"] = existing["chat_id"]

    # Enabled toggle
    if "enabled" in settings:
        update_data["enabled"] = settings["enabled"]
    elif existing:
        update_data["enabled"] = existing.get("enabled", True)
    else:
        update_data["enabled"] = True

    await db.settings.update_one(
        {"key": "telegram_monitoring"}, {"$set": update_data}, upsert=True
    )

    return {"message": "Domain Monitoring Telegram settings updated"}


@router.post("/settings/telegram-monitoring/test")
async def test_telegram_monitoring_alert(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Send a test notification to the Domain Monitoring Telegram channel.
    Tests the dedicated monitoring channel (NOT SEO channel).
    """
    from services.monitoring_service import DomainMonitoringTelegramService
    from services.timezone_helper import format_now_local, get_system_timezone

    tz_str, tz_label = await get_system_timezone(db)
    local_time = format_now_local(tz_str, tz_label)

    message = f"""🔔 <b>DOMAIN MONITORING TEST</b>

Ini adalah pesan test dari sistem Domain Monitoring.

━━━━━━━━━━━━━━━━━━━━━━
📌 <b>DETAIL TEST</b>
• Dikirim Oleh: {current_user.get('name') or current_user.get('email')}
• Waktu: {local_time}
• Channel: Domain Monitoring (Dedicated)

━━━━━━━━━━━━━━━━━━━━━━
<b>Catatan:</b>
• Channel ini untuk alert DOMAIN (expiration, availability)
• BUKAN untuk SEO change notifications
• Alert akan mencakup SEO context jika domain ada di SEO Network

✅ Jika Anda melihat pesan ini, konfigurasi Telegram untuk Domain Monitoring sudah benar!

<i>TEST MESSAGE - NO ACTUAL ALERT</i>"""

    telegram_service = DomainMonitoringTelegramService(db)
    success = await telegram_service.send_alert(message)

    if success:
        return {
            "message": "Test message sent successfully to Domain Monitoring channel"
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to send test message. Check Domain Monitoring Telegram configuration (bot_token and chat_id required).",
        )


# ==================== EMAIL ALERT SETTINGS ====================

from pydantic import EmailStr


class EmailAlertSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    resend_api_key: Optional[str] = None
    sender_email: Optional[str] = None
    global_admin_emails: Optional[List[str]] = None
    severity_threshold: Optional[str] = None  # "high" or "critical"
    include_network_managers: Optional[bool] = None


@router.get("/settings/email-alerts")
async def get_email_alert_settings(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get email alert configuration for domain monitoring.
    Super Admin only.
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")

    from services.email_alert_service import get_email_alert_service

    email_service = get_email_alert_service(db)

    settings = await email_service.get_email_settings()
    return settings


@router.put("/settings/email-alerts")
async def update_email_alert_settings(
    data: EmailAlertSettingsUpdate,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Update email alert configuration for domain monitoring.
    Super Admin only.
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")

    # Validate severity threshold
    if data.severity_threshold and data.severity_threshold not in ["high", "critical"]:
        raise HTTPException(
            status_code=400, detail="severity_threshold must be 'high' or 'critical'"
        )

    # Validate emails format
    if data.global_admin_emails:
        for email in data.global_admin_emails:
            if email and "@" not in email:
                raise HTTPException(
                    status_code=400, detail=f"Invalid email format: {email}"
                )

    from services.email_alert_service import get_email_alert_service

    email_service = get_email_alert_service(db)

    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    settings = await email_service.update_email_settings(updates)

    return settings


@router.post("/settings/email-alerts/test")
async def test_email_alert(
    recipient_email: str = Query(..., description="Email address to send test to"),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Send a test email to verify email alert configuration.
    Super Admin only.
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")

    if "@" not in recipient_email:
        raise HTTPException(status_code=400, detail="Invalid email address")

    from services.email_alert_service import get_email_alert_service

    email_service = get_email_alert_service(db)

    result = await email_service.send_test_email(recipient_email)

    if result.get("success"):
        return {"message": result.get("message", "Test email sent successfully")}
    else:
        raise HTTPException(
            status_code=500, detail=result.get("error", "Failed to send test email")
        )


# ==================== WEEKLY DIGEST SETTINGS ====================


class WeeklyDigestSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    schedule_day: Optional[str] = None  # monday, tuesday, etc.
    schedule_hour: Optional[int] = None  # 0-23
    schedule_minute: Optional[int] = None  # 0-59
    include_expiring_domains: Optional[bool] = None
    include_down_domains: Optional[bool] = None
    include_soft_blocked: Optional[bool] = None
    expiring_days_threshold: Optional[int] = None  # 7-90


@router.get("/settings/weekly-digest")
async def get_weekly_digest_settings(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get weekly digest email configuration.
    Super Admin only.
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")

    from services.weekly_digest_service import get_weekly_digest_service

    digest_service = get_weekly_digest_service(db)

    settings = await digest_service.get_digest_settings()
    return settings


@router.put("/settings/weekly-digest")
async def update_weekly_digest_settings(
    data: WeeklyDigestSettingsUpdate,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Update weekly digest email configuration.
    Super Admin only.
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")

    # Validate schedule_day
    valid_days = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    if data.schedule_day and data.schedule_day.lower() not in valid_days:
        raise HTTPException(
            status_code=400,
            detail=f"schedule_day must be one of: {', '.join(valid_days)}",
        )

    # Validate expiring_days_threshold
    if data.expiring_days_threshold is not None:
        if not 7 <= data.expiring_days_threshold <= 90:
            raise HTTPException(
                status_code=400,
                detail="expiring_days_threshold must be between 7 and 90",
            )

    from services.weekly_digest_service import get_weekly_digest_service

    digest_service = get_weekly_digest_service(db)

    try:
        updates = {k: v for k, v in data.model_dump().items() if v is not None}
        settings = await digest_service.update_digest_settings(updates)
        return settings
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/settings/weekly-digest/send")
async def send_weekly_digest_now(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Manually trigger sending the weekly digest email.
    Super Admin only.
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")

    from services.weekly_digest_service import get_weekly_digest_service

    digest_service = get_weekly_digest_service(db)

    result = await digest_service.generate_and_send_digest()

    if result.get("success"):
        return result
    else:
        raise HTTPException(
            status_code=500, detail=result.get("error", "Failed to send digest")
        )


@router.get("/settings/weekly-digest/preview")
async def preview_weekly_digest(current_user: dict = Depends(get_current_user_wrapper)):
    """
    Preview the weekly digest data without sending.
    Super Admin only.
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin access required")

    from services.weekly_digest_service import get_weekly_digest_service

    digest_service = get_weekly_digest_service(db)

    preview = await digest_service.preview_digest()
    return preview


# ==================== USER IN-APP NOTIFICATIONS ====================

@router.get("/notifications")
async def get_user_notifications(
    limit: int = Query(20, le=100),
    unread_only: bool = Query(False),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get notifications for the current user.
    Used for in-app notification bell.
    """
    user_id = current_user.get("id")
    
    query = {"user_id": user_id}
    if unread_only:
        query["read"] = False
    
    notifications = await db.user_notifications.find(
        query, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Count unread
    unread_count = await db.user_notifications.count_documents({"user_id": user_id, "read": False})
    
    return {
        "notifications": notifications,
        "unread_count": unread_count
    }


@router.post("/notifications/{notification_id}/read")
async def mark_user_notification_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Mark a notification as read."""
    user_id = current_user.get("id")
    
    result = await db.user_notifications.update_one(
        {"id": notification_id, "user_id": user_id},
        {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"success": True}


@router.post("/notifications/read-all")
async def mark_all_user_notifications_read(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Mark all notifications as read for current user."""
    user_id = current_user.get("id")
    
    await db.user_notifications.update_many(
        {"user_id": user_id, "read": False},
        {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"success": True}


async def create_user_notification(
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    link: str = None,
    metadata: dict = None,
):
    """
    Create an in-app notification for a user.
    Used when users are tagged in complaints, etc.
    """
    notification = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "link": link,
        "metadata": metadata or {},
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.user_notifications.insert_one(notification)
    return notification


# ==================== USER PRESENCE / ONLINE STATUS ====================

# Consider user online if heartbeat within last 60 seconds
ONLINE_THRESHOLD_SECONDS = 60


@router.post("/presence/heartbeat")
async def send_heartbeat(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Send heartbeat to update user's online status.
    Should be called every 30 seconds by the frontend.
    """
    user_id = current_user.get("id")
    now = datetime.now(timezone.utc).isoformat()
    
    # Update user's last_seen and current page
    await db.user_presence.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "last_seen": now,
                "user_name": current_user.get("name") or current_user.get("email"),
                "user_email": current_user.get("email"),
                "user_role": current_user.get("role"),
            }
        },
        upsert=True
    )
    
    # Also update user's last_online in users collection
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"last_online": now}}
    )
    
    return {"success": True, "timestamp": now}


@router.get("/presence/online")
async def get_online_users(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get list of currently online users.
    Users are considered online if heartbeat within last 60 seconds.
    """
    threshold = datetime.now(timezone.utc) - timedelta(seconds=ONLINE_THRESHOLD_SECONDS)
    threshold_str = threshold.isoformat()
    
    # Get all users with recent heartbeat
    online_presence = await db.user_presence.find(
        {"last_seen": {"$gte": threshold_str}},
        {"_id": 0}
    ).to_list(100)
    
    # Get recently offline users (last 24 hours)
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    day_ago_str = day_ago.isoformat()
    
    recent_users = await db.user_presence.find(
        {
            "last_seen": {"$gte": day_ago_str, "$lt": threshold_str}
        },
        {"_id": 0}
    ).sort("last_seen", -1).limit(20).to_list(20)
    
    return {
        "online": online_presence,
        "online_count": len(online_presence),
        "recently_active": recent_users
    }


@router.get("/users/{user_id}/status")
async def get_user_status(
    user_id: str,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get online status and last seen for a specific user."""
    presence = await db.user_presence.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    if not presence:
        # Check users collection for last_online
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "last_online": 1})
        return {
            "user_id": user_id,
            "is_online": False,
            "last_seen": user.get("last_online") if user else None
        }
    
    # Check if online
    threshold = datetime.now(timezone.utc) - timedelta(seconds=ONLINE_THRESHOLD_SECONDS)
    last_seen = presence.get("last_seen")
    is_online = last_seen and last_seen >= threshold.isoformat()
    
    return {
        "user_id": user_id,
        "is_online": is_online,
        "last_seen": last_seen,
        "user_name": presence.get("user_name"),
    }



# ==================== NOTIFICATION TEMPLATES API ====================


@router.get("/settings/notification-templates")
async def list_notification_templates(
    channel: Optional[str] = Query(None, description="Filter by channel: telegram, email"),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    List all notification templates.
    Only super_admin can access.
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can manage templates")
    
    from services.notification_template_engine import get_template_crud
    crud = get_template_crud(db)
    
    templates = await crud.list_templates(channel)
    return {"templates": templates}


@router.get("/settings/notification-templates/events")
async def get_available_template_events(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get list of available notification event types."""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can manage templates")
    
    from services.notification_template_engine import get_template_crud
    crud = get_template_crud(db)
    
    return {"events": crud.get_available_events()}


@router.get("/settings/notification-templates/variables")
async def get_available_template_variables(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get list of allowed template variables."""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can manage templates")
    
    from services.notification_template_engine import NotificationTemplateEngine, ALLOWED_VARIABLES
    
    # Group variables by category
    grouped = {}
    for var in sorted(ALLOWED_VARIABLES):
        category = var.split(".")[0]
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(var)
    
    return {"variables": grouped, "all_variables": sorted(list(ALLOWED_VARIABLES))}


@router.get("/settings/notification-templates/{channel}/{event_type}")
async def get_notification_template(
    channel: str,
    event_type: str,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get a specific notification template."""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can manage templates")
    
    from services.notification_template_engine import get_template_crud
    crud = get_template_crud(db)
    
    template = await crud.get_template(channel, event_type)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template not found: {channel}/{event_type}")
    
    return template


@router.put("/settings/notification-templates/{channel}/{event_type}")
async def update_notification_template(
    channel: str,
    event_type: str,
    body: dict,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Update a notification template.
    Only super_admin can update.
    
    Body can contain:
    - title: str (optional)
    - template_body: str (optional)
    - enabled: bool (optional)
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can manage templates")
    
    from services.notification_template_engine import get_template_crud
    crud = get_template_crud(db)
    
    try:
        template = await crud.update_template(
            channel=channel,
            event_type=event_type,
            title=body.get("title"),
            template_body=body.get("template_body"),
            enabled=body.get("enabled"),
            updated_by=current_user.get("email"),
        )
        
        # Log the change using audit service
        from services.audit_log_service import get_audit_service
        audit_service = get_audit_service(db)
        await audit_service.log_template_change(
            actor_email=current_user.get("email"),
            channel=channel,
            event_type=event_type,
            action="update",
            changes={"fields_changed": list(body.keys())},
        )
        
        return template
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/settings/notification-templates/{channel}/{event_type}/reset")
async def reset_notification_template(
    channel: str,
    event_type: str,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Reset a notification template to its default."""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can manage templates")
    
    from services.notification_template_engine import get_template_crud
    crud = get_template_crud(db)
    
    try:
        template = await crud.reset_template(channel, event_type)
        
        # Log the reset using audit service
        from services.audit_log_service import get_audit_service
        audit_service = get_audit_service(db)
        await audit_service.log_template_change(
            actor_email=current_user.get("email"),
            channel=channel,
            event_type=event_type,
            action="reset",
        )
        
        return template
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/settings/notification-templates/{channel}/{event_type}/preview")
async def preview_notification_template(
    channel: str,
    event_type: str,
    body: dict = None,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Preview a notification template with sample data.
    
    Body can optionally contain:
    - template_body: str (to preview custom text without saving)
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can manage templates")
    
    from services.notification_template_engine import get_template_crud
    crud = get_template_crud(db)
    
    try:
        template_body = body.get("template_body") if body else None
        rendered = await crud.preview_template(channel, event_type, template_body)
        return {"preview": rendered, "channel": channel, "event_type": event_type}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/settings/notification-templates/validate")
async def validate_template_body(
    body: dict,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Validate a template body for unknown variables.
    
    Body must contain:
    - template_body: str
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can manage templates")
    
    template_body = body.get("template_body", "")
    if not template_body:
        raise HTTPException(status_code=400, detail="template_body is required")
    
    from services.notification_template_engine import NotificationTemplateEngine
    engine = NotificationTemplateEngine(db)
    
    invalid_vars = engine.validate_template(template_body)
    
    return {
        "valid": len(invalid_vars) == 0,
        "invalid_variables": invalid_vars,
        "message": "Template is valid" if not invalid_vars else f"Unknown variables: {', '.join(invalid_vars)}"
    }



# ==================== DOMAIN EXPIRATION TEST ALERTS ====================


@router.post("/monitoring/expiration/test")
async def send_test_expiration_alert(
    body: dict,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Send a TEST domain expiration alert for QA purposes.
    
    Body:
    - domain_id: str (required) - The domain to test
    - simulated_days: int (required) - Days until expiration to simulate (30, 14, 7, 3, 0, -1)
    
    Test alerts:
    - Use same formatting as real alerts
    - Marked as TEST MODE
    - Do NOT affect deduplication or schedules
    - Logged with is_test=true
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can send test alerts")
    
    domain_id = body.get("domain_id")
    simulated_days = body.get("simulated_days", 7)
    
    if not domain_id:
        raise HTTPException(status_code=400, detail="domain_id is required")
    
    if not isinstance(simulated_days, int):
        raise HTTPException(status_code=400, detail="simulated_days must be an integer")
    
    from services.monitoring_service import ExpirationMonitoringService
    
    monitoring_service = ExpirationMonitoringService(db)
    
    result = await monitoring_service.send_test_expiration_alert(
        domain_id=domain_id,
        simulated_days=simulated_days,
        triggered_by=current_user.get("email", "unknown"),
    )
    
    if result.get("error"):
        raise HTTPException(
            status_code=500, 
            detail=result.get("error", "Failed to send test alert")
        )
    
    if not result.get("success"):
        # Telegram might not be configured - still return result with details
        return {
            **result,
            "warning": "Telegram notification may not have been delivered. Check Domain Monitoring Telegram settings."
        }
    
    return result


@router.get("/monitoring/expiration/test-options")
async def get_expiration_test_options(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get available test options for expiration alerts.
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can access test options")
    
    return {
        "thresholds": [
            {"value": 30, "label": "30 days (first warning)"},
            {"value": 14, "label": "14 days"},
            {"value": 7, "label": "7 days (critical threshold)"},
            {"value": 3, "label": "3 days (urgent)"},
            {"value": 1, "label": "1 day (expires tomorrow)"},
            {"value": 0, "label": "0 days (expires today)"},
            {"value": -1, "label": "-1 day (already expired)"},
        ],
        "reminder_schedule": {
            "30_days": "One-time alert",
            "14_days": "One-time alert",
            "7_days": "One-time alert",
            "less_than_7": "2x daily (09:00 & 18:00 GMT+7)",
        }
    }


# ==================== AUDIT LOGS API ====================


@router.get("/audit-logs")
async def get_audit_logs(
    event_type: Optional[str] = Query(None),
    actor_email: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    success: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    skip: int = Query(0),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get audit logs (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can view audit logs")
    
    from services.audit_log_service import get_audit_service
    audit_service = get_audit_service(db)
    
    logs = await audit_service.get_logs(
        event_type=event_type,
        actor_email=actor_email,
        resource_type=resource_type,
        severity=severity,
        success=success,
        limit=limit,
        skip=skip,
    )
    
    return {"logs": logs, "count": len(logs)}


@router.get("/audit-logs/stats")
async def get_audit_stats(
    days: int = Query(7, ge=1, le=90),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get audit log statistics (Super Admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can view audit stats")
    
    from services.audit_log_service import get_audit_service
    audit_service = get_audit_service(db)
    
    stats = await audit_service.get_stats(days=days)
    return stats


@router.get("/audit-logs/event-types")
async def get_audit_event_types(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Get available audit event types"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can view audit logs")
    
    from services.audit_log_service import AuditLogService
    
    return {
        "event_types": [
            {"value": AuditLogService.EVENT_TEMPLATE_CHANGE, "label": "Template Change"},
            {"value": AuditLogService.EVENT_TEMPLATE_RESET, "label": "Template Reset"},
            {"value": AuditLogService.EVENT_PERMISSION_VIOLATION, "label": "Permission Violation"},
            {"value": AuditLogService.EVENT_NOTIFICATION_FAILED, "label": "Notification Failed"},
            {"value": AuditLogService.EVENT_NOTIFICATION_SENT, "label": "Notification Sent"},
            {"value": AuditLogService.EVENT_SETTINGS_CHANGE, "label": "Settings Change"},
            {"value": AuditLogService.EVENT_SEO_CHANGE, "label": "SEO Change"},
        ],
        "severities": [
            {"value": AuditLogService.SEVERITY_INFO, "label": "Info"},
            {"value": AuditLogService.SEVERITY_WARNING, "label": "Warning"},
            {"value": AuditLogService.SEVERITY_ERROR, "label": "Error"},
            {"value": AuditLogService.SEVERITY_CRITICAL, "label": "Critical"},
        ],
    }


@router.delete("/audit-logs")
async def clear_audit_logs(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """Clear all audit logs (super_admin only)"""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only super admins can clear audit logs")
    
    result = await db.audit_logs.delete_many({})
    
    return {
        "message": "Audit logs cleared",
        "deleted_count": result.deleted_count
    }


# ==================== METRICS & ANALYTICS API ====================


@router.get("/metrics/reminder-effectiveness")
async def get_reminder_effectiveness_metrics(
    days: int = Query(30, ge=1, le=90),
    network_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get reminder effectiveness metrics.
    
    Returns response rates, average response times, and breakdown by type.
    """
    if current_user.get("role") not in ["super_admin", "manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    from services.reminder_effectiveness_service import get_reminder_effectiveness_service
    service = get_reminder_effectiveness_service(db)
    
    metrics = await service.get_effectiveness_metrics(days=days, network_id=network_id)
    return metrics


@router.get("/metrics/conflict-aging")
async def get_conflict_aging_metrics(
    network_id: Optional[str] = Query(None),
    brand_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get conflict/complaint aging metrics.
    
    Returns how long complaints have been open and identifies bottlenecks.
    """
    if current_user.get("role") not in ["super_admin", "manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    from services.conflict_aging_service import get_conflict_aging_service
    service = get_conflict_aging_service(db)
    
    metrics = await service.get_aging_metrics(network_id=network_id, brand_id=brand_id)
    return metrics


@router.get("/metrics/conflict-resolution")
async def get_conflict_resolution_metrics(
    days: int = Query(30, ge=1, le=90),
    network_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get conflict/complaint resolution time metrics.
    
    Returns average resolution times and breakdown by time buckets.
    """
    if current_user.get("role") not in ["super_admin", "manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    from services.conflict_aging_service import get_conflict_aging_service
    service = get_conflict_aging_service(db)
    
    metrics = await service.get_resolution_metrics(days=days, network_id=network_id)
    return metrics


@router.get("/metrics/dashboard")
async def get_metrics_dashboard(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get combined metrics dashboard data.
    
    Returns key metrics from all tracking systems.
    """
    if current_user.get("role") not in ["super_admin", "manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    from services.reminder_effectiveness_service import get_reminder_effectiveness_service
    from services.conflict_aging_service import get_conflict_aging_service
    from services.audit_log_service import get_audit_service
    
    reminder_service = get_reminder_effectiveness_service(db)
    conflict_service = get_conflict_aging_service(db)
    audit_service = get_audit_service(db)
    
    # Get metrics in parallel would be better, but for simplicity:
    reminder_metrics = await reminder_service.get_effectiveness_metrics(days=7)
    conflict_aging = await conflict_service.get_aging_metrics()
    conflict_resolution = await conflict_service.get_resolution_metrics(days=30)
    audit_stats = await audit_service.get_stats(days=7)
    
    return {
        "reminder_effectiveness": {
            "response_rate_percent": reminder_metrics.get("response_rate_percent", 0),
            "avg_response_time_hours": reminder_metrics.get("avg_response_time_hours", 0),
            "total_reminders_7d": reminder_metrics.get("total_reminders", 0),
        },
        "conflict_aging": {
            "total_open": conflict_aging.get("total_open", 0),
            "critical_count": conflict_aging.get("critical_count", 0),
            "avg_age_days": conflict_aging.get("avg_age_days", 0),
        },
        "conflict_resolution": {
            "total_resolved_30d": conflict_resolution.get("total_resolved", 0),
            "avg_resolution_time_days": conflict_resolution.get("avg_resolution_time_days", 0),
        },
        "audit": {
            "total_events_7d": audit_stats.get("total_events", 0),
            "permission_violations": audit_stats.get("permission_violations", 0),
            "notification_failures": audit_stats.get("notification_failures", 0),
        },
    }



# ==================== TEAM PERFORMANCE ALERTS API ====================


@router.get("/performance/thresholds")
async def get_performance_thresholds(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get current team performance alert thresholds.
    
    Super Admin/Manager only.
    """
    if current_user.get("role") not in ["super_admin", "manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    from services.team_performance_alert_service import get_team_performance_service
    
    service = get_team_performance_service(db)
    thresholds = await service.get_thresholds()
    
    return {
        "thresholds": thresholds,
        "description": {
            "false_resolution_rate_percent": "Alert if false resolution rate exceeds this %",
            "stale_conflict_days": "Alert if conflicts remain open longer than this many days",
            "open_conflict_backlog": "Alert if more than this many conflicts are open",
            "avg_resolution_hours": "Alert if average resolution time exceeds this many hours",
            "check_interval_hours": "How often to run performance checks"
        }
    }


@router.put("/performance/thresholds")
async def update_performance_thresholds(
    thresholds: Dict[str, Any] = Body(...),
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Update team performance alert thresholds.
    
    Super Admin only.
    
    Available thresholds:
    - false_resolution_rate_percent: Alert if > this % (default: 15)
    - stale_conflict_days: Alert if conflict open > this days (default: 7)
    - open_conflict_backlog: Alert if > this many open (default: 10)
    - avg_resolution_hours: Alert if avg > this hours (default: 48)
    - check_interval_hours: How often to check (default: 24)
    """
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admins can update thresholds")
    
    from services.team_performance_alert_service import get_team_performance_service
    
    # Validate thresholds
    valid_keys = {
        "false_resolution_rate_percent",
        "stale_conflict_days", 
        "open_conflict_backlog",
        "avg_resolution_hours",
        "check_interval_hours"
    }
    
    filtered_thresholds = {k: v for k, v in thresholds.items() if k in valid_keys}
    
    service = get_team_performance_service(db)
    await service.save_thresholds(filtered_thresholds)
    
    return {
        "success": True,
        "thresholds": await service.get_thresholds()
    }


@router.post("/performance/check")
async def run_performance_check(
    force: bool = False,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Manually trigger a team performance check.
    
    Super Admin/Manager only.
    
    Set force=true to bypass the check interval.
    """
    if current_user.get("role") not in ["super_admin", "manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    from services.team_performance_alert_service import get_team_performance_service
    
    service = get_team_performance_service(db)
    
    if force:
        # Reset last check to force immediate run
        await db.settings.delete_one({"key": "team_performance_last_check"})
    
    result = await service.check_performance_and_alert()
    
    return result


@router.get("/performance/history")
async def get_performance_alert_history(
    days: int = 30,
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get team performance alert history.
    
    Super Admin/Manager only.
    """
    if current_user.get("role") not in ["super_admin", "manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    from services.team_performance_alert_service import get_team_performance_service
    
    service = get_team_performance_service(db)
    history = await service.get_alert_history(days=days)
    
    return {
        "alerts": history,
        "count": len(history),
        "period_days": days
    }


@router.get("/performance/metrics")
async def get_current_performance_metrics(
    current_user: dict = Depends(get_current_user_wrapper),
):
    """
    Get current team performance metrics without sending alerts.
    
    Useful for displaying in dashboard before thresholds are breached.
    """
    if current_user.get("role") not in ["super_admin", "manager"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    from services.team_performance_alert_service import get_team_performance_service
    
    service = get_team_performance_service(db)
    thresholds = await service.get_thresholds()
    metrics = await service._gather_performance_metrics()
    
    # Add threshold comparison
    metrics["threshold_status"] = {
        "false_resolution_rate": {
            "current": metrics["false_resolution_rate_percent"],
            "threshold": thresholds["false_resolution_rate_percent"],
            "breached": metrics["false_resolution_rate_percent"] > thresholds["false_resolution_rate_percent"]
        },
        "stale_conflicts": {
            "current": len(metrics["stale_conflicts"]),
            "threshold_days": thresholds["stale_conflict_days"],
            "breached": len(metrics["stale_conflicts"]) > 0
        },
        "open_backlog": {
            "current": metrics["open_count"],
            "threshold": thresholds["open_conflict_backlog"],
            "breached": metrics["open_count"] > thresholds["open_conflict_backlog"]
        },
        "avg_resolution_time": {
            "current": metrics["avg_resolution_hours"],
            "threshold": thresholds["avg_resolution_hours"],
            "breached": metrics["avg_resolution_hours"] > thresholds["avg_resolution_hours"]
        }
    }
    
    return metrics

