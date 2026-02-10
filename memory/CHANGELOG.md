# SEO-NOC Changelog

## [3.2.0] - 2026-02-10

### Auto-Link Conflict → Optimization Task - COMPLETE

Transforms conflict detection into actionable SEO execution by automatically creating optimization tasks from detected conflicts.

#### Features Implemented
- **Auto Optimization Creation** - System auto-creates optimization when conflict detected
- **One-to-One Relationship** - Each conflict links to exactly one optimization
- **Status Flow** - `detected` → `under_review` (optimization created) → `resolved` (validated)
- **Permission Enforcement** - Only managers/super_admin can update/resolve
- **Telegram Notifications** - Alerts on conflict detection and resolution
- **Metrics Tracking** - Time-to-resolution, by severity, by type, by resolver
- **Recurrence Detection** - Tracks recurring conflicts with count and timestamp

#### New Models (models_v3.py)
- `ConflictStatus` enum: detected, under_review, resolved, ignored
- `StoredConflict` - Persistent conflict with optimization link
- `ConflictResolutionCreate/Response` - API request/response models
- `LinkedConflictInfo` - Conflict info embedded in optimization detail
- Added `linked_conflict_id` and `linked_conflict` to optimization models
- Added `can_edit` field to SeoOptimizationDetailResponse

#### New Service
- `conflict_optimization_linker_service.py`:
  - `process_detected_conflicts()` - Stores conflicts and creates optimizations
  - `_create_optimization_for_conflict()` - Creates linked optimization task
  - `resolve_conflict()` - Marks conflict as resolved
  - `get_conflict_metrics()` - Returns resolution metrics
  - `_send_conflict_notification()` - Telegram alerts

#### New API Endpoints
- `GET /api/v3/conflicts/stored` - List stored conflicts with linked optimization
- `GET /api/v3/conflicts/stored/{id}` - Get single conflict detail
- `POST /api/v3/conflicts/process` - Detect and auto-link conflicts to optimizations
- `POST /api/v3/conflicts/{id}/resolve` - Mark conflict as resolved
- `GET /api/v3/conflicts/metrics` - Get resolution metrics

#### Frontend Changes
- Updated `AlertsPage.jsx`:
  - "Create Optimization Tasks" button to process conflicts
  - "Linked Optimization" badge on conflicts with linked tasks
  - "View Task" button to navigate to optimization detail
- Updated `api.js` with conflictsAPI methods

#### Testing
- 100% backend test pass rate (17/17 tests)
- All features verified via testing agent

---

## [3.1.0] - 2026-02-10

### SEO-Aware Domain Monitoring + Structured Alert Output - COMPLETE

#### Features Implemented
- **STRUKTUR SEO TERKINI** - Tier-based SEO snapshot in all domain monitoring alerts
- **Strict Severity Calculation** - CRITICAL/HIGH/MEDIUM/LOW based on tier and money site proximity
- **Daily Unmonitored Domain Reminders** - ⚠️ MONITORING NOT CONFIGURED alerts via Telegram
- **Enhanced Test Alerts** - Full SEO context and structure in test mode alerts

#### Template Alerts Updated
- `domain_down` - Full SEO structure with STRUKTUR SEO TERKINI section
- `domain_expiration` - Full SEO structure with STRUKTUR SEO TERKINI section
- `monitoring_not_configured` - NEW template for unmonitored domain reminders

#### New Template Variables
- `structure.full_structure` - STRUKTUR SEO TERKINI formatted content
- `node.tier_label` - "Tier 1", "Tier 2", "LP/Money Site" labels
- `node.relation` - Relation type (301 Redirect, Canonical, etc.)
- `impact.reaches_money_site` - ✅ YES / ❌ NO
- `impact.money_site_warning` - Warning if money site affected
- `impact.action_required` - Next action based on severity
- `domain.error_message` - Error reason for down alerts
- `domain.category` - Domain category
- `domains.count` - Count for unmonitored reminder
- `domains.list` - List of unmonitored domains

#### Severity Calculation Rules
- **CRITICAL**: Domain is Money Site/LP OR Tier 1 reaching Money Site
- **HIGH**: Tier 1 node OR has ≥3 downstream nodes
- **MEDIUM**: Tier 2+ node with indirect money site impact
- **LOW**: Orphan/unused node

#### Message Format (New Standard)
1. Alert Type (DOWN / EXPIRATION / CONFIG MISSING)
2. Domain Info
3. SEO Context Summary
4. 🧭 STRUKTUR SEO TERKINI (Tier-based)
5. 🔥 Impact Summary
6. ⏰ Next Action

#### Backend Changes
- Enhanced `forced_monitoring_service.py`:
  - `calculate_strict_severity()` - Strict severity calculation
  - `_build_test_alert_message()` - New structured format
  - `send_unmonitored_reminders()` - SEO-aware reminders
- Enhanced `monitoring_service.py`:
  - `_format_down_alert_seo_aware()` - New message order
- Enhanced `reminder_scheduler.py`:
  - Added `unmonitored_domain_reminder_job` (daily 8:00 AM)
- Enhanced `notification_template_engine.py`:
  - Updated `domain_down` and `domain_expiration` templates
  - Added `monitoring_not_configured` template
  - Added new template variables
- `seo_context_enricher.py`:
  - `get_full_network_structure_formatted()` - STRUKTUR SEO TERKINI

#### API Endpoints
- `GET /api/v3/monitoring/unmonitored-in-seo` - List unmonitored domains in SEO
- `POST /api/v3/monitoring/domain-down/test` - Send test alert with full SEO context
- `POST /api/v3/monitoring/send-unmonitored-reminders` - Manual trigger (24h rate limited)
- `GET /api/v3/monitoring/test-alerts/history` - Test alert history

#### Testing
- 100% backend test pass rate (20/20 tests)
- All features verified via testing agent

---

## [3.0.0] - 2026-02-08

### V3 Architecture Migration - COMPLETE

#### Migration Summary
- **Phase 0**: Database backup at `/app/backups/v2_backup_20260208_085617`
- **Phase 1**: New V3 schema and services created
- **Phase 2**: 23 domains migrated to `asset_domains`
- **Phase 3**: 4 groups migrated to `seo_networks`
- **Phase 4**: 23 structure entries created in `seo_structure_entries`
- **Phase 5**: V3 API endpoints implemented
- **Phase 6**: Frontend updated to use V3 API

#### New Features
- **Derived Tiers**: Tiers are now calculated via BFS from main domain, not stored
- **Activity Logging**: All operations tracked with actor identification
- **Separated Concerns**: Asset inventory separate from SEO strategy
- **V3 API Endpoints**:
  - `/api/v3/asset-domains` - Pure inventory CRUD
  - `/api/v3/networks` - Strategy containers with tier calculation
  - `/api/v3/structure` - Relationship layer with derived tiers
  - `/api/v3/activity-logs` - Audit trail queries
  - `/api/v3/reports/dashboard` - V3 stats
  - `/api/v3/reports/conflicts` - SEO conflict detection

#### Backend Changes
- Added `models_v3.py` with new data models
- Added `tier_service.py` for BFS tier calculation
- Added `activity_log_service.py` for audit trail
- Added `v3_router.py` with all V3 endpoints
- Migration scripts in `/app/backend/migrations/`

#### Frontend Changes
- Updated `api.js` with V3 API client
- Updated `NetworkGraph.jsx` for derived tier visualization
- Updated `GroupDetailPage.jsx` for V3 network detail
- Updated `DomainsPage.jsx` for V3 asset domains

#### Testing
- 100% backend test pass rate (20/20 tests)
- All frontend V3 features verified
- Tier distribution verified: LP/Money Site: 1, Tier 1: 3, Tier 2: 6, Tier 3: 6, Tier 5+: 1

---

## [2.0.0] - 2026-02-07

### SEO-NOC V2 Features

#### Monitoring & Alerts
- Background domain monitoring scheduler
- Ping and HTTP status checks
- Expiration tracking with alerts
- 14 types of SEO conflict detection
- Telegram bot integration for alerts

#### Dashboard
- Stats grid with key metrics
- Tier distribution chart
- Index status pie chart
- Recent alerts panel
- SEO conflicts panel

#### Domain Management
- Full CRUD for domains
- Detail panel with monitoring controls
- Check Now functionality
- Mute/Unmute alerts
- Activity history tracking

---

## [1.0.0] - 2026-02-06

### Initial Release

#### Core Features
- JWT-based authentication with RBAC
- Brand management
- Category management (8 defaults)
- Domain CRUD with tier hierarchy
- Group/Network management
- D3.js network visualization

#### Roles
- Super Admin: Full access
- Admin: Domain/network management
- Viewer: Read-only access
