"""
SEO-NOC V3 Models
=================
New architecture with separated concerns:
- AssetDomain: Pure inventory
- SeoNetwork: Strategy containers  
- SeoStructureEntry: Relationship layer
- ActivityLog: Audit trail

IMPORTANT: Tiers are DERIVED, not stored.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


# ==================== ENUMS ====================

class AssetStatus(str, Enum):
    """Status of asset domain in inventory"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    EXPIRED = "expired"


class NetworkStatus(str, Enum):
    """Status of SEO network"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class DomainRole(str, Enum):
    """Role of domain within a network"""
    MAIN = "main"  # Money site / LP
    SUPPORTING = "supporting"  # Link building domain


class SeoStatus(str, Enum):
    """SEO relationship status"""
    CANONICAL = "canonical"
    REDIRECT_301 = "301_redirect"
    REDIRECT_302 = "302_redirect"
    RESTORE = "restore"


class IndexStatus(str, Enum):
    """Index status for search engines"""
    INDEX = "index"
    NOINDEX = "noindex"


class MonitoringInterval(str, Enum):
    """Monitoring check frequency"""
    FIVE_MIN = "5min"
    FIFTEEN_MIN = "15min"
    ONE_HOUR = "1hour"
    DAILY = "daily"


class PingStatus(str, Enum):
    """Domain availability status"""
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class ActionType(str, Enum):
    """Types of actions for activity logging"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MIGRATE = "migrate"


class EntityType(str, Enum):
    """Entity types for activity logging"""
    ASSET_DOMAIN = "asset_domain"
    SEO_NETWORK = "seo_network"
    SEO_STRUCTURE_ENTRY = "seo_structure_entry"
    BRAND = "brand"
    CATEGORY = "category"
    USER = "user"
    REGISTRAR = "registrar"


class RegistrarStatus(str, Enum):
    """Status of registrar in master data"""
    ACTIVE = "active"
    INACTIVE = "inactive"


# ==================== ASSET DOMAIN MODELS ====================

class AssetDomainBase(BaseModel):
    """Base model for asset domain - pure inventory"""
    domain_name: str
    brand_id: str
    category_id: Optional[str] = None
    domain_type_id: Optional[str] = None
    
    # Asset Management
    registrar_id: Optional[str] = None  # FK to registrars collection
    registrar: Optional[str] = None  # Legacy field (deprecated, use registrar_id)
    buy_date: Optional[str] = None
    expiration_date: Optional[str] = None
    auto_renew: bool = False
    status: AssetStatus = AssetStatus.ACTIVE
    
    # Monitoring
    monitoring_enabled: bool = False
    monitoring_interval: MonitoringInterval = MonitoringInterval.ONE_HOUR
    last_check: Optional[str] = None
    ping_status: PingStatus = PingStatus.UNKNOWN
    http_status: Optional[str] = None
    http_status_code: Optional[int] = None
    
    notes: Optional[str] = ""


class AssetDomainCreate(AssetDomainBase):
    """Model for creating an asset domain"""
    pass


class AssetDomainUpdate(BaseModel):
    """Model for updating an asset domain"""
    domain_name: Optional[str] = None
    brand_id: Optional[str] = None
    category_id: Optional[str] = None
    domain_type_id: Optional[str] = None
    registrar: Optional[str] = None
    buy_date: Optional[str] = None
    expiration_date: Optional[str] = None
    auto_renew: Optional[bool] = None
    status: Optional[AssetStatus] = None
    monitoring_enabled: Optional[bool] = None
    monitoring_interval: Optional[MonitoringInterval] = None
    notes: Optional[str] = None


class AssetDomainResponse(AssetDomainBase):
    """Response model for asset domain"""
    model_config = ConfigDict(extra="ignore")
    id: str
    legacy_id: Optional[str] = None  # Traceability to V2
    brand_name: Optional[str] = None
    category_name: Optional[str] = None
    created_at: str
    updated_at: str


# ==================== SEO NETWORK MODELS ====================

class SeoNetworkBase(BaseModel):
    """Base model for SEO network - strategy container"""
    name: str
    brand_id: Optional[str] = None
    description: Optional[str] = ""
    status: NetworkStatus = NetworkStatus.ACTIVE


class SeoNetworkCreate(SeoNetworkBase):
    """Model for creating an SEO network"""
    pass


class SeoNetworkUpdate(BaseModel):
    """Model for updating an SEO network"""
    name: Optional[str] = None
    brand_id: Optional[str] = None
    description: Optional[str] = None
    status: Optional[NetworkStatus] = None


class SeoNetworkResponse(SeoNetworkBase):
    """Response model for SEO network"""
    model_config = ConfigDict(extra="ignore")
    id: str
    legacy_id: Optional[str] = None  # Traceability to V2 groups
    brand_name: Optional[str] = None
    domain_count: int = 0
    created_at: str
    updated_at: str


class SeoNetworkDetail(SeoNetworkResponse):
    """Detailed response with structure entries"""
    entries: List["SeoStructureEntryResponse"] = []


# ==================== SEO STRUCTURE ENTRY MODELS ====================

class SeoStructureEntryBase(BaseModel):
    """Base model for SEO structure entry - relationship layer"""
    asset_domain_id: str
    network_id: str
    
    # Domain Role
    domain_role: DomainRole = DomainRole.SUPPORTING
    domain_status: SeoStatus = SeoStatus.CANONICAL
    index_status: IndexStatus = IndexStatus.INDEX
    
    # Relationship (target domain this entry points to)
    target_asset_domain_id: Optional[str] = None
    
    # Ranking & Path Tracking (NEW)
    ranking_url: Optional[str] = None  # Specific path that ranks
    primary_keyword: Optional[str] = None
    ranking_position: Optional[int] = None
    last_rank_check: Optional[str] = None
    
    notes: Optional[str] = ""


class SeoStructureEntryCreate(SeoStructureEntryBase):
    """Model for creating an SEO structure entry"""
    pass


class SeoStructureEntryUpdate(BaseModel):
    """Model for updating an SEO structure entry"""
    domain_role: Optional[DomainRole] = None
    domain_status: Optional[SeoStatus] = None
    index_status: Optional[IndexStatus] = None
    target_asset_domain_id: Optional[str] = None
    ranking_url: Optional[str] = None
    primary_keyword: Optional[str] = None
    ranking_position: Optional[int] = None
    last_rank_check: Optional[str] = None
    notes: Optional[str] = None


class SeoStructureEntryResponse(SeoStructureEntryBase):
    """Response model for SEO structure entry"""
    model_config = ConfigDict(extra="ignore")
    id: str
    legacy_domain_id: Optional[str] = None  # Traceability to V2 domains
    
    # Enriched data
    domain_name: Optional[str] = None
    target_domain_name: Optional[str] = None
    network_name: Optional[str] = None
    brand_name: Optional[str] = None
    
    # DERIVED tier (calculated, not stored)
    calculated_tier: Optional[int] = None
    tier_label: Optional[str] = None
    
    created_at: str
    updated_at: str


# ==================== ACTIVITY LOG MODELS ====================

class ActivityLogMetadata(BaseModel):
    """Metadata for activity log entries"""
    migration_phase: Optional[str] = None
    legacy_ids: Optional[Dict[str, str]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class ActivityLogCreate(BaseModel):
    """Model for creating an activity log entry"""
    actor: str  # email or system:migration_v3
    action_type: ActionType
    entity_type: EntityType
    entity_id: str
    before_value: Optional[Dict[str, Any]] = None
    after_value: Optional[Dict[str, Any]] = None
    metadata: Optional[ActivityLogMetadata] = None


class ActivityLogResponse(BaseModel):
    """Response model for activity log"""
    model_config = ConfigDict(extra="ignore")
    id: str
    actor: str
    action_type: str
    entity_type: str
    entity_id: str
    before_value: Optional[Dict[str, Any]] = None
    after_value: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: str


# ==================== TIER CALCULATION (DERIVED) ====================

# Tier labels for display
TIER_LABELS = {
    0: "LP/Money Site",
    1: "Tier 1",
    2: "Tier 2", 
    3: "Tier 3",
    4: "Tier 4",
    5: "Tier 5+"
}

def get_tier_label(tier: int) -> str:
    """Convert numeric tier to display label"""
    if tier >= 5:
        return TIER_LABELS[5]
    return TIER_LABELS.get(tier, f"Tier {tier}")


# ==================== DOMAIN TYPE MODELS (OPTIONAL EXTENSION) ====================

class DomainTypeBase(BaseModel):
    """Base model for domain type classification"""
    name: str
    description: Optional[str] = ""
    color: Optional[str] = None  # For UI display


class DomainTypeResponse(DomainTypeBase):
    """Response model for domain type"""
    model_config = ConfigDict(extra="ignore")
    id: str
    created_at: str
    updated_at: str


# Forward reference update
SeoNetworkDetail.model_rebuild()
