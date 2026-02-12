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
from typing import Optional, Dict, Any, List, Generic, TypeVar
from enum import Enum
from datetime import datetime

# ==================== PAGINATION MODELS ====================

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Pagination metadata"""

    page: int
    limit: int
    total: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper"""

    data: List[T]
    meta: PaginationMeta


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

    PRIMARY = "primary"  # For main nodes - no redirect/canonical relationship
    CANONICAL = "canonical"
    REDIRECT_301 = "301_redirect"
    REDIRECT_302 = "302_redirect"
    RESTORE = "restore"


# Status options allowed for main nodes (no redirect/canonical)
MAIN_NODE_ALLOWED_STATUSES = [SeoStatus.PRIMARY]
# Status options allowed for supporting nodes
SUPPORTING_NODE_ALLOWED_STATUSES = [
    SeoStatus.CANONICAL,
    SeoStatus.REDIRECT_301,
    SeoStatus.REDIRECT_302,
    SeoStatus.RESTORE,
]


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
    SEO_OPTIMIZATION = "seo_optimization"
    BRAND = "brand"
    CATEGORY = "category"
    USER = "user"
    REGISTRAR = "registrar"
    SETTINGS = "settings"


class RegistrarStatus(str, Enum):
    """Status of registrar in master data"""

    ACTIVE = "active"
    INACTIVE = "inactive"


class SeoChangeActionType(str, Enum):
    """Types of SEO structure change actions (human-readable)"""

    CREATE_NODE = "create_node"
    UPDATE_NODE = "update_node"
    DELETE_NODE = "delete_node"
    RELINK_NODE = "relink_node"  # Change target_entry_id
    CHANGE_ROLE = "change_role"  # Main <-> Supporting
    CHANGE_PATH = "change_path"  # optimized_path change


class SeoNotificationType(str, Enum):
    """Types of SEO Network notifications"""

    MAIN_DOMAIN_CHANGE = "main_domain_change"
    NODE_DELETED = "node_deleted"
    TARGET_RELINKED = "target_relinked"
    ORPHAN_DETECTED = "orphan_detected"
    SEO_CONFLICT = "seo_conflict"
    HIGH_TIER_NOINDEX = "high_tier_noindex"


# ==================== SEO OPTIMIZATION MODELS ====================


class OptimizationActivityType(str, Enum):
    """Types of SEO optimization activities"""

    BACKLINK = "backlink"
    ONPAGE = "onpage"
    CONTENT = "content"
    TECHNICAL = "technical"
    SCHEMA = "schema"
    INTERNAL_LINK = "internal-link"
    EXPERIMENT = "experiment"
    CONFLICT_RESOLUTION = "conflict_resolution"  # Auto-created from detected conflicts
    OTHER = "other"


class OptimizationAffectedScope(str, Enum):
    """Scope of SEO optimization"""

    MONEY_SITE = "money_site"
    SPECIFIC_DOMAIN = "specific_domain"
    SPECIFIC_PATH = "specific_path"
    WHOLE_NETWORK = "whole_network"


class OptimizationExpectedImpact(str, Enum):
    """Expected impact of optimization"""

    RANKING = "ranking"
    AUTHORITY = "authority"
    CRAWL = "crawl"
    CONVERSION = "conversion"


class ObservedImpact(str, Enum):
    """Observed impact after optimization (filled 14-30 days later)"""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NO_IMPACT = "no_impact"
    NEGATIVE = "negative"


class OptimizationStatus(str, Enum):
    """Status of optimization activity"""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REVERTED = "reverted"


class ComplaintStatus(str, Enum):
    """Complaint status for optimizations"""

    NONE = "none"
    COMPLAINED = "complained"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"


class NetworkVisibilityMode(str, Enum):
    """Visibility mode for SEO networks

    - BRAND_BASED: All users with brand access can VIEW (default)
    - RESTRICTED: Only managers and Super Admins can VIEW

    Note: Execution rights are controlled separately by manager_ids.
    Only managers or Super Admins can execute (create/update optimizations).
    """

    RESTRICTED = "restricted"  # Only managers + Super Admins can view
    BRAND_BASED = "brand_based"  # Users with brand access can view (default)


class ComplaintPriority(str, Enum):
    """Priority level for optimization complaints"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OptimizationOutcome(str, Enum):
    """Manual outcome evaluation for completed optimizations"""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class OptimizationCreatedBy(BaseModel):
    """User who created the optimization"""

    user_id: str
    display_name: str
    email: str


class ReportUrlEntry(BaseModel):
    """Report URL with date range"""

    url: str
    start_date: str  # Required
    end_date: Optional[str] = None


class SeoOptimizationCreate(BaseModel):
    """Create SEO optimization activity"""

    activity_type_id: Optional[str] = (
        None  # FK to activity_types, optional for backward compat
    )
    activity_type: Optional[str] = None  # Legacy string type, will be deprecated
    title: str
    description: str
    reason_note: str  # REQUIRED, min 20 chars - reason for this optimization
    affected_scope: OptimizationAffectedScope = (
        OptimizationAffectedScope.SPECIFIC_DOMAIN
    )
    target_domains: List[str] = []  # domains or paths
    keywords: List[str] = []
    report_urls: List[ReportUrlEntry] = []  # With start/end dates
    expected_impact: List[OptimizationExpectedImpact] = []
    status: OptimizationStatus = OptimizationStatus.COMPLETED
    
    # Linked conflict (for auto-created conflict resolution)
    linked_conflict_id: Optional[str] = None


class SeoOptimizationUpdate(BaseModel):
    """Update SEO optimization activity"""

    activity_type_id: Optional[str] = None
    activity_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    reason_note: Optional[str] = None
    affected_scope: Optional[OptimizationAffectedScope] = None
    target_domains: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    report_urls: Optional[List[ReportUrlEntry]] = None
    expected_impact: Optional[List[OptimizationExpectedImpact]] = None
    status: Optional[OptimizationStatus] = None
    observed_impact: Optional[ObservedImpact] = None  # Set after 14-30 days


class SeoOptimizationResponse(BaseModel):
    """SEO optimization response model"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    network_id: str
    brand_id: str
    created_by: OptimizationCreatedBy
    created_at: str
    updated_at: Optional[str] = None
    activity_type_id: Optional[str] = None
    activity_type: str  # Legacy or resolved from activity_type_id
    activity_type_name: Optional[str] = None  # Resolved name from master
    title: str
    description: str
    reason_note: Optional[str] = None
    affected_scope: str
    target_domains: List[str] = []
    keywords: List[str] = []
    report_urls: List[Any] = []  # List of ReportUrlEntry or strings
    expected_impact: List[str] = []
    observed_impact: Optional[str] = None  # Set after 14-30 days
    status: str
    complaint_status: str = "none"  # none, complained, under_review, resolved
    complaint_note: Optional[str] = None
    telegram_notified_at: Optional[str] = None

    # Linked conflict (for conflict resolution type)
    linked_conflict_id: Optional[str] = None
    linked_conflict: Optional[Any] = None  # LinkedConflictInfo when enriched

    # Enriched fields
    network_name: Optional[str] = None
    brand_name: Optional[str] = None

    # Derived metrics
    complaints_count: int = 0
    has_repeated_issue: bool = False  # Badge for >2 complaints in 30 days


# ==================== ACTIVITY TYPE MODELS ====================


class OptimizationActivityTypeCreate(BaseModel):
    """Create activity type"""

    name: str
    description: Optional[str] = None
    icon: Optional[str] = None  # Icon identifier
    color: Optional[str] = None  # Badge color


class OptimizationActivityTypeResponse(BaseModel):
    """Activity type response"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    is_default: bool = False
    usage_count: int = 0
    created_at: str


# ==================== TEAM EVALUATION MODELS ====================


class UserSeoScore(BaseModel):
    """Derived SEO performance score for a user"""

    user_id: str
    user_name: str
    user_email: str
    total_optimizations: int = 0
    completed_optimizations: int = 0
    reverted_optimizations: int = 0
    complaint_count: int = 0
    resolved_complaints: int = 0
    avg_resolution_time_hours: Optional[float] = (
        None  # Average time to resolve complaints
    )
    positive_impact_count: int = 0
    negative_impact_count: int = 0
    has_repeated_issues: bool = False
    score: float = 0.0  # Derived score 0-5
    score_breakdown: Dict[str, float] = {}


class TeamEvaluationSummary(BaseModel):
    """Summary for team evaluation dashboard"""

    period_start: str
    period_end: str
    total_optimizations: int = 0
    by_status: Dict[str, int] = {}
    by_activity_type: Dict[str, int] = {}
    by_observed_impact: Dict[str, int] = {}
    total_complaints: int = 0
    avg_resolution_time_hours: Optional[float] = None
    top_contributors: List[UserSeoScore] = []
    most_complained_users: List[UserSeoScore] = []
    repeated_issue_users: List[str] = []


class OptimizationComplaintCreate(BaseModel):
    """Create a complaint on an optimization"""

    reason: str  # Required complaint text
    responsible_user_ids: List[str] = []  # Users to tag
    priority: Optional[ComplaintPriority] = ComplaintPriority.MEDIUM
    report_urls: List[str] = []


class OptimizationComplaintResponse(BaseModel):
    """Response model for optimization complaint"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    optimization_id: str
    created_by: OptimizationCreatedBy
    created_at: str
    resolved_at: Optional[str] = None
    resolved_by: Optional[OptimizationCreatedBy] = None
    reason: str
    responsible_user_ids: List[str] = []
    responsible_users: List[Dict[str, Any]] = []  # Enriched user info
    priority: str
    report_urls: List[str] = []
    telegram_notified_at: Optional[str] = None
    status: str = "open"  # open, under_review, resolved, dismissed
    resolution_note: Optional[str] = None
    time_to_resolution_hours: Optional[float] = None  # For metrics


class TeamResponseCreate(BaseModel):
    """Create a team response to a complaint"""

    note: str  # Required, min 20 chars, max 2000 chars
    report_urls: List[str] = []  # Additional evidence URLs


class TeamResponseEntry(BaseModel):
    """Team response entry in optimization"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    created_by: OptimizationCreatedBy
    created_at: str
    note: str
    report_urls: List[str] = []
    complaint_id: Optional[str] = None  # Links to specific complaint


class ComplaintResolveRequest(BaseModel):
    """Request to resolve a complaint (Super Admin only)"""

    resolution_note: str  # Required, min 10 chars
    mark_optimization_complete: bool = False  # Optionally mark complete


# ==================== PROJECT-LEVEL COMPLAINT MODELS ====================


class ProjectComplaintCreate(BaseModel):
    """Create a project-level complaint (not tied to optimization)"""

    reason: str  # Required complaint text, min 10 chars
    responsible_user_ids: List[str] = []  # Users to tag (managers)
    priority: Optional[ComplaintPriority] = ComplaintPriority.MEDIUM
    report_urls: List[str] = []  # Evidence URLs
    category: Optional[str] = (
        None  # e.g., "communication", "deadline", "quality", "process"
    )


class ProjectComplaintResponse(BaseModel):
    """Response model for project-level complaint"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    network_id: str
    brand_id: str
    created_by: OptimizationCreatedBy
    created_at: str
    resolved_at: Optional[str] = None
    resolved_by: Optional[OptimizationCreatedBy] = None
    reason: str
    responsible_user_ids: List[str] = []
    responsible_users: List[Dict[str, Any]] = []  # Enriched user info
    priority: str = "medium"
    status: str = "open"  # open, under_review, resolved, dismissed
    resolution_note: Optional[str] = None
    report_urls: List[str] = []
    category: Optional[str] = None
    responses: List[Dict[str, Any]] = []  # Team responses


class ProjectComplaintResolveRequest(BaseModel):
    """Request to resolve a project-level complaint"""

    resolution_note: str  # Required, min 10 chars


class OptimizationCloseRequest(BaseModel):
    """Request to close/complete an optimization (Super Admin only)"""

    final_note: Optional[str] = None


class SeoOptimizationDetailResponse(BaseModel):
    """Full optimization detail with complaints and responses"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    network_id: str
    brand_id: str
    created_by: OptimizationCreatedBy
    created_at: str
    updated_at: Optional[str] = None
    closed_at: Optional[str] = None
    closed_by: Optional[OptimizationCreatedBy] = None
    activity_type_id: Optional[str] = None
    activity_type: str
    activity_type_name: Optional[str] = None
    title: str
    description: str
    reason_note: Optional[str] = None
    affected_scope: str
    target_domains: List[str] = []
    keywords: List[str] = []
    report_urls: List[Any] = []
    expected_impact: List[str] = []
    observed_impact: Optional[str] = None
    status: str
    complaint_status: str = "none"

    # Linked conflict (for conflict resolution type)
    linked_conflict_id: Optional[str] = None
    linked_conflict: Optional[Any] = None  # LinkedConflictInfo when enriched

    # Enriched fields
    network_name: Optional[str] = None
    brand_name: Optional[str] = None

    # Complaint thread
    complaints: List[OptimizationComplaintResponse] = []
    active_complaint: Optional[OptimizationComplaintResponse] = None

    # Team responses
    responses: List[TeamResponseEntry] = []

    # Metrics
    complaints_count: int = 0
    has_repeated_issue: bool = False
    is_blocked: bool = False  # True if has unresolved complaint
    blocked_reason: Optional[str] = None
    
    # Permission info
    can_edit: bool = True  # False for non-managers viewing conflict resolution


class UserTelegramSettings(BaseModel):
    """Telegram settings for user"""

    telegram_username: Optional[str] = None
    telegram_user_id: Optional[str] = None


class NetworkAccessControl(BaseModel):
    """SEO Network Management settings - defines managers responsible for execution"""

    visibility_mode: NetworkVisibilityMode = NetworkVisibilityMode.BRAND_BASED
    manager_ids: List[str] = []  # Users who can execute optimizations


class ManagerSummaryCache(BaseModel):
    """Cached manager summary for performance"""

    count: int = 0
    names: List[str] = []  # First 2-3 display names


class NetworkManagersUpdate(BaseModel):
    """Update SEO Network Managers with audit trail"""

    visibility_mode: NetworkVisibilityMode = NetworkVisibilityMode.BRAND_BASED
    manager_ids: List[str] = []  # Users responsible for this network


class NetworkManagersResponse(BaseModel):
    """Response model for SEO Network Management settings"""

    visibility_mode: str
    manager_ids: List[str] = []
    managers: List[Dict[str, Any]] = []  # Enriched user info
    manager_summary_cache: Optional[ManagerSummaryCache] = None
    managers_updated_at: Optional[str] = None
    managers_updated_by: Optional[Dict[str, Any]] = None


class NetworkManagersAuditLog(BaseModel):
    """Audit log entry for network manager changes"""

    network_id: str
    network_name: str
    previous_mode: str
    new_mode: str
    added_manager_ids: List[str] = []
    removed_manager_ids: List[str] = []
    added_manager_names: List[str] = []
    removed_manager_names: List[str] = []
    changed_by: Dict[str, Any]  # user_id, email, name
    changed_at: str


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

    # Monitoring - Availability (Ping/HTTP)
    monitoring_enabled: bool = False
    monitoring_interval: MonitoringInterval = MonitoringInterval.ONE_HOUR
    last_checked_at: Optional[str] = None  # Last availability check timestamp
    last_ping_status: Optional[str] = (
        None  # Previous ping status for transition detection
    )
    last_http_code: Optional[int] = None  # Last HTTP response code

    # Legacy monitoring fields (kept for backward compatibility)
    last_check: Optional[str] = None
    ping_status: PingStatus = PingStatus.UNKNOWN
    http_status: Optional[str] = None
    http_status_code: Optional[int] = None

    # Monitoring - Expiration
    expiration_alert_sent_at: Optional[str] = (
        None  # Track when last expiration alert was sent
    )
    last_expiration_days: Optional[int] = (
        None  # Days remaining when last alert was sent
    )

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
    registrar_id: Optional[str] = None
    registrar: Optional[str] = None  # Legacy
    buy_date: Optional[str] = None
    expiration_date: Optional[str] = None
    auto_renew: Optional[bool] = None
    status: Optional[AssetStatus] = None
    monitoring_enabled: Optional[bool] = None
    monitoring_interval: Optional[MonitoringInterval] = None
    last_checked_at: Optional[str] = None
    last_ping_status: Optional[str] = None
    last_http_code: Optional[int] = None
    expiration_alert_sent_at: Optional[str] = None
    notes: Optional[str] = None


class NetworkUsageInfo(BaseModel):
    """Info about a network that uses this asset domain"""

    network_id: str
    network_name: str
    role: str  # "main" or "supporting"
    optimized_path: Optional[str] = None


class AssetDomainResponse(AssetDomainBase):
    """Response model for asset domain"""

    model_config = ConfigDict(extra="ignore")
    id: str
    legacy_id: Optional[str] = None  # Traceability to V2
    brand_name: Optional[str] = None
    category_name: Optional[str] = None
    registrar_name: Optional[str] = None  # Enriched from registrar_id

    # Monitoring status display
    monitoring_status: Optional[str] = None  # up/down/unknown
    days_until_expiration: Optional[int] = None  # Calculated field

    # SEO Network usage - derived from seo_structure_entries
    seo_networks: List[NetworkUsageInfo] = []

    created_at: str
    updated_at: str


# ==================== SEO NETWORK MODELS ====================


class SeoNetworkBase(BaseModel):
    """Base model for SEO network - strategy container"""

    name: str
    brand_id: str  # Required - networks must be associated with a brand
    description: Optional[str] = ""
    status: NetworkStatus = NetworkStatus.ACTIVE


class MainNodeConfig(BaseModel):
    """Configuration for the initial main node when creating a network"""

    asset_domain_id: str  # Required - the main domain
    optimized_path: Optional[str] = None  # Optional - defaults to "/" if empty


class SeoNetworkCreate(SeoNetworkBase):
    """Model for creating an SEO network with initial main node"""

    main_node: MainNodeConfig  # Required - every network must have a main node


class SeoNetworkCreateLegacy(SeoNetworkBase):
    """Legacy model for creating without main node (backward compat)"""

    pass


class SeoNetworkUpdate(BaseModel):
    """Model for updating an SEO network"""

    name: Optional[str] = None
    brand_id: Optional[str] = None
    description: Optional[str] = None
    status: Optional[NetworkStatus] = None


class RankingStatus(str, Enum):
    """SEO Network ranking status"""

    RANKING = (
        "ranking"  # Has at least one node with ranking_position 1-100 or ranking_url
    )
    TRACKING = "tracking"  # No ranking but has primary_keyword/ranking_url with INDEX
    NONE = "none"  # No ranking data


class SeoNetworkResponse(SeoNetworkBase):
    """Response model for SEO network"""

    model_config = ConfigDict(extra="ignore")
    id: str
    legacy_id: Optional[str] = None  # Traceability to V2 groups
    brand_name: Optional[str] = None
    domain_count: int = 0
    main_node_id: Optional[str] = None  # ID of the main structure entry
    main_domain_name: Optional[str] = None  # Name of main domain for display

    # Ranking visibility fields (derived from structure entries)
    ranking_status: RankingStatus = RankingStatus.NONE
    ranking_nodes_count: int = 0  # Nodes with ranking_position 1-100
    best_ranking_position: Optional[int] = None  # Lowest position (best rank)
    tracked_urls_count: int = 0  # Nodes with ranking_url or primary_keyword

    # SEO Network Management fields
    visibility_mode: Optional[str] = "brand_based"  # brand_based, restricted, public
    manager_ids: Optional[List[str]] = []  # List of user IDs who can execute actions
    manager_summary_cache: Optional[Dict[str, Any]] = None  # {count: int, names: [str]}

    # Access Summary Panel fields (P0)
    open_complaints_count: int = (
        0  # Optimizations with complaint_status in [complained, under_review]
    )
    last_optimization_at: Optional[str] = None  # Most recent optimization date

    created_at: str
    updated_at: str


class SeoNetworkDetail(SeoNetworkResponse):
    """Detailed response with structure entries"""

    entries: List["SeoStructureEntryResponse"] = []


# ==================== SEO STRUCTURE ENTRY MODELS ====================


class SeoStructureEntryBase(BaseModel):
    """Base model for SEO structure entry - relationship layer (node-based)"""

    asset_domain_id: str
    network_id: str

    # Path-level node: domain + optional path = node
    optimized_path: Optional[str] = None  # e.g., /blog/best-product or /landing-page

    # Domain Role
    domain_role: DomainRole = DomainRole.SUPPORTING
    domain_status: SeoStatus = SeoStatus.CANONICAL
    index_status: IndexStatus = IndexStatus.INDEX

    # Node-to-node relationship (target is another SeoStructureEntry, not just a domain)
    target_entry_id: Optional[str] = None  # FK to another SeoStructureEntry
    target_asset_domain_id: Optional[str] = None  # Legacy field (for backward compat)

    # Ranking & Path Tracking
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
    optimized_path: Optional[str] = None
    target_entry_id: Optional[str] = None
    target_asset_domain_id: Optional[str] = None  # Legacy
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
    target_entry_path: Optional[str] = None  # For node-to-node display
    network_name: Optional[str] = None
    brand_name: Optional[str] = None

    # Node identifier for display (domain + path)
    node_label: Optional[str] = None

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
    5: "Tier 5+",
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


# ==================== REGISTRAR MODELS (MASTER DATA) ====================


class RegistrarBase(BaseModel):
    """Base model for registrar - master data"""

    name: str
    website: Optional[str] = None
    status: RegistrarStatus = RegistrarStatus.ACTIVE
    notes: Optional[str] = ""


class RegistrarCreate(RegistrarBase):
    """Model for creating a registrar"""

    pass


class RegistrarUpdate(BaseModel):
    """Model for updating a registrar"""

    name: Optional[str] = None
    website: Optional[str] = None
    status: Optional[RegistrarStatus] = None
    notes: Optional[str] = None


class RegistrarResponse(RegistrarBase):
    """Response model for registrar"""

    model_config = ConfigDict(extra="ignore")
    id: str
    domain_count: int = 0  # Number of domains using this registrar
    created_at: str
    updated_at: str


# ==================== CONFLICT DETECTION MODELS ====================


class ConflictSeverity(str, Enum):
    """Severity levels for SEO conflicts"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConflictType(str, Enum):
    """Types of SEO conflicts"""

    KEYWORD_CANNIBALIZATION = "keyword_cannibalization"  # Same keyword, different paths
    COMPETING_TARGETS = "competing_targets"  # Different paths targeting different nodes
    CANONICAL_MISMATCH = "canonical_mismatch"  # Path A canonical to B, B still indexed
    TIER_INVERSION = "tier_inversion"  # Higher tier supports lower tier
    REDIRECT_LOOP = "redirect_loop"  # Redirect/canonical loop detected
    MULTIPLE_PARENTS_TO_MAIN = "multiple_parents_to_main"  # Multiple non-supporting nodes pointing to main
    CANONICAL_REDIRECT_CONFLICT = "canonical_redirect_conflict"  # Node has both canonical and redirect set
    INDEX_NOINDEX_MISMATCH = "index_noindex_mismatch"  # Conflicting index status in link chain
    ORPHAN_NODE = "orphan"  # Node not connected to main hierarchy
    NOINDEX_HIGH_TIER = "noindex_high_tier"  # NOINDEX node in high tier


class SeoConflict(BaseModel):
    """Model for a detected SEO conflict"""

    conflict_type: ConflictType
    severity: ConflictSeverity
    network_id: str
    network_name: Optional[str] = None
    domain_name: str

    # Involved nodes
    node_a_id: str
    node_a_path: Optional[str] = None
    node_a_label: str

    node_b_id: Optional[str] = None
    node_b_path: Optional[str] = None
    node_b_label: Optional[str] = None

    # Details
    description: str
    suggestion: Optional[str] = None

    # Metadata
    detected_at: str


# ==================== STORED CONFLICT MODELS ====================


class ConflictStatus(str, Enum):
    """Status of a stored conflict"""
    DETECTED = "detected"  # Initial state when conflict is found
    UNDER_REVIEW = "under_review"  # Optimization created, being worked on
    RESOLVED = "resolved"  # Conflict resolved and validated
    APPROVED = "approved"  # Approved by Super Admin (auto-resolved and deactivated)
    IGNORED = "ignored"  # Marked as intentional/acceptable


class StoredConflict(BaseModel):
    """Model for a stored SEO conflict with tracking"""
    
    id: str
    conflict_type: str  # ConflictType value
    severity: str  # ConflictSeverity value
    status: str = ConflictStatus.DETECTED.value
    
    # Network info
    network_id: str
    network_name: Optional[str] = None
    
    # Domain info
    domain_name: str
    domain_id: Optional[str] = None
    
    # Involved nodes
    node_a_id: str
    node_a_path: Optional[str] = None
    node_a_label: str
    
    node_b_id: Optional[str] = None
    node_b_path: Optional[str] = None
    node_b_label: Optional[str] = None
    
    # Affected nodes list
    affected_nodes: List[str] = []
    
    # Details
    description: str
    suggestion: Optional[str] = None
    
    # Linked optimization
    optimization_id: Optional[str] = None
    
    # Timestamps
    detected_at: str
    updated_at: Optional[str] = None
    resolved_at: Optional[str] = None
    
    # Metrics
    recurrence_count: int = 0  # How many times this conflict was re-detected
    last_recurrence_at: Optional[str] = None


class ConflictResolutionCreate(BaseModel):
    """Request to create conflict resolution optimization"""
    
    conflict_id: str
    assigned_to_user_id: Optional[str] = None  # If not provided, auto-assign to network manager
    priority: Optional[str] = "high"
    notes: Optional[str] = None


class ConflictResolutionResponse(BaseModel):
    """Response for conflict resolution creation"""
    
    conflict_id: str
    optimization_id: str
    assigned_to: Optional[str] = None
    status: str
    message: str


class LinkedConflictInfo(BaseModel):
    """Conflict info embedded in optimization detail"""
    
    id: str
    conflict_type: str
    severity: str
    status: str
    detected_at: str
    domain_name: str
    node_a_label: str
    node_b_label: Optional[str] = None
    description: str
    affected_nodes: List[str] = []


# ==================== MONITORING SETTINGS MODELS ====================


class ExpirationMonitoringSettings(BaseModel):
    """Settings for domain expiration monitoring"""

    enabled: bool = True
    alert_window_days: int = 7  # Alert when expiration <= today + N days
    alert_thresholds: List[int] = [30, 14, 7, 3, 1, 0]  # Days to send alerts
    include_auto_renew: bool = False  # Include domains with auto-renew enabled


class AvailabilityMonitoringSettings(BaseModel):
    """Settings for domain availability (ping/HTTP) monitoring"""

    enabled: bool = True
    default_interval_seconds: int = 300  # 5 minutes
    alert_on_down: bool = True  # Alert when status changes UP → DOWN
    alert_on_recovery: bool = False  # Alert when status changes DOWN → UP
    timeout_seconds: int = 15
    follow_redirects: bool = True


class TelegramMonitoringSettings(BaseModel):
    """Telegram alert settings for monitoring"""

    enabled: bool = True


class MonitoringSettings(BaseModel):
    """Combined monitoring settings"""

    expiration: ExpirationMonitoringSettings = ExpirationMonitoringSettings()
    availability: AvailabilityMonitoringSettings = AvailabilityMonitoringSettings()
    telegram: TelegramMonitoringSettings = TelegramMonitoringSettings()


class MonitoringSettingsUpdate(BaseModel):
    """Model for updating monitoring settings"""

    expiration: Optional[Dict[str, Any]] = None
    availability: Optional[Dict[str, Any]] = None
    telegram: Optional[Dict[str, Any]] = None


# ==================== SEO CHANGE LOG MODELS ====================


class SeoChangeLogCreate(BaseModel):
    """Model for creating an SEO change log entry (internal use)"""

    network_id: str
    brand_id: str
    actor_user_id: str
    action_type: SeoChangeActionType
    affected_node: str  # domain + optimized_path
    before_snapshot: Optional[Dict[str, Any]] = None
    after_snapshot: Optional[Dict[str, Any]] = None
    change_note: str  # REQUIRED - human explanation



# ==================== MENU ACCESS CONTROL MODELS ====================

# Master menu registry - static list of all menus
MASTER_MENU_REGISTRY = [
    {"key": "dashboard", "label": "Dashboard", "path": "/dashboard"},
    {"key": "asset_domains", "label": "Asset Domains", "path": "/domains"},
    {"key": "seo_networks", "label": "SEO Networks", "path": "/groups"},
    {"key": "alert_center", "label": "Alert Center", "path": "/alerts"},
    {"key": "reports", "label": "Reports", "path": "/reports"},
    {"key": "team_evaluation", "label": "Team Evaluation", "path": "/reports/team-evaluation"},
    {"key": "brands", "label": "Brands", "path": "/brands"},
    {"key": "categories", "label": "Categories", "path": "/categories"},
    {"key": "registrars", "label": "Registrars", "path": "/registrars"},
    {"key": "users", "label": "Users", "path": "/users"},
    {"key": "audit_logs", "label": "Audit Logs", "path": "/audit-logs"},
    {"key": "metrics", "label": "Metrics", "path": "/metrics"},
    {"key": "v3_activity", "label": "V3 Activity", "path": "/activity-logs"},
    {"key": "activity_types", "label": "Activity Types", "path": "/settings/activity-types"},
    {"key": "scheduler", "label": "Scheduler", "path": "/settings/scheduler"},
    {"key": "monitoring", "label": "Monitoring", "path": "/settings/monitoring"},
    {"key": "settings", "label": "Settings", "path": "/settings"},
]

# Default menu access by role
DEFAULT_ADMIN_MENUS = [m["key"] for m in MASTER_MENU_REGISTRY]  # All menus enabled by default
DEFAULT_USER_MENUS = []  # No menus enabled by default


class MenuPermissionUpdate(BaseModel):
    """Model for updating menu permissions for a user"""
    enabled_menus: List[str] = Field(
        ...,
        description="List of menu keys that the user can access"
    )


class MenuPermissionResponse(BaseModel):
    """Response model for menu permissions"""
    user_id: str
    role: str
    enabled_menus: List[str]
    is_super_admin: bool = False


class SeoChangeLogResponse(BaseModel):
    """Response model for SEO change log"""

    model_config = ConfigDict(extra="ignore")
    id: str
    network_id: str
    network_name: Optional[str] = None  # Enriched
    brand_id: str
    brand_name: Optional[str] = None  # Enriched
    actor_user_id: str
    actor_email: Optional[str] = None  # Enriched
    action_type: str
    affected_node: str
    before_snapshot: Optional[Dict[str, Any]] = None
    after_snapshot: Optional[Dict[str, Any]] = None
    change_note: str
    archived: bool = False
    archived_at: Optional[str] = None
    created_at: str


# ==================== SEO NETWORK NOTIFICATION MODELS ====================


class SeoNetworkNotification(BaseModel):
    """Model for SEO network notifications"""

    model_config = ConfigDict(extra="ignore")
    id: str
    network_id: str
    network_name: Optional[str] = None
    brand_id: str
    notification_type: str
    title: str
    message: str
    affected_node: Optional[str] = None
    actor_email: Optional[str] = None
    change_log_id: Optional[str] = None  # Link to related change log
    read: bool = False
    read_at: Optional[str] = None
    created_at: str


class SeoChangeNoteRequest(BaseModel):
    """Request model for structure changes requiring change note"""

    change_note: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Penjelasan perubahan SEO ini (wajib, minimal 10 karakter). Disarankan ≥50 karakter untuk penjelasan yang jelas.",
    )


class SeoStructureEntryCreateWithNote(BaseModel):
    """Model for creating structure entry with mandatory change note"""

    asset_domain_id: str
    network_id: str
    optimized_path: Optional[str] = None
    domain_role: DomainRole = DomainRole.SUPPORTING
    domain_status: SeoStatus = SeoStatus.CANONICAL
    index_status: IndexStatus = IndexStatus.INDEX
    target_entry_id: Optional[str] = None
    target_asset_domain_id: Optional[str] = None
    ranking_url: Optional[str] = None
    primary_keyword: Optional[str] = None
    ranking_position: Optional[int] = None
    last_rank_check: Optional[str] = None
    notes: Optional[str] = ""
    # Mandatory change note - minimum 10 chars for clear SEO reasoning
    change_note: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Penjelasan perubahan SEO ini (wajib, minimal 10 karakter). Disarankan ≥50 karakter.",
    )


class SeoStructureEntryUpdateWithNote(BaseModel):
    """Model for updating structure entry with mandatory change note"""

    domain_role: Optional[DomainRole] = None
    domain_status: Optional[SeoStatus] = None
    index_status: Optional[IndexStatus] = None
    optimized_path: Optional[str] = None
    target_entry_id: Optional[str] = None
    target_asset_domain_id: Optional[str] = None
    ranking_url: Optional[str] = None
    primary_keyword: Optional[str] = None
    ranking_position: Optional[int] = None
    last_rank_check: Optional[str] = None
    notes: Optional[str] = None
    # Mandatory change note - minimum 10 chars for clear SEO reasoning
    change_note: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Penjelasan perubahan SEO ini (wajib, minimal 10 karakter). Disarankan ≥50 karakter.",
    )
