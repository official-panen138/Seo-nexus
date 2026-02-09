# SEO Network Operations Center (SEO-NOC) - PRD

## Original Problem Statement
Build a full-stack SEO Network Operations Center combining:
- Asset Domain Management (inventory, ownership, expiration, monitoring)
- SEO Structure Monitoring (tier hierarchy, relationships, conflicts)
- Automated Monitoring & Alerting with Telegram integration

## User Personas
1. **Super Admin**: Full access - users, roles, brands, categories, domains, networks, settings, Telegram config
2. **Admin**: Domain/network management, assign tiers/categories, view reports, acknowledge alerts
3. **Viewer**: Read-only access to domains, networks, alerts, reports

## Core Requirements (Static)

### Asset Domain Management
- Domain name, brand, category, registrar, expiration date, auto-renew
- Monitoring status (active/inactive), interval (5min/15min/1hour/daily)
- Ping status (up/down/unknown), HTTP status codes
- Last check timestamp

### Domain Categories (Customizable)
- Default: Fresh Domain, Aged Domain, Redirect Domain, AMP Domain, Money Site, Subdomain Money Site, PBN, Parking

### SEO Structure Monitoring
- Tier hierarchy: Tier 5 → 4 → 3 → 2 → 1 → LP/Money Site
- Relationship types: Canonical, 301 Redirect, 302 Redirect
- Parent-child relationships with validation

### Alert System
- Monitoring alerts (ping/HTTP failures)
- Expiration alerts (7 days, 1 day, expired)
- SEO conflict alerts (orphans, noindex in high tier, tier jumps)
- Severity: CRITICAL (Money Site), HIGH (Tier 1-2), MEDIUM (Tier 3-4), LOW (Tier 5)

### Telegram Integration
- Real-time alerts to configured chat
- /ack {domain} - Acknowledge alert
- /mute {domain} {duration} - Mute alerts
- Formatted messages with domain, brand, tier, issue, severity

## Tech Stack
- **Backend**: FastAPI (Python) + MongoDB + APScheduler
- **Frontend**: React + Tailwind CSS + Shadcn/UI + Recharts
- **Visualization**: D3.js force-directed graph
- **Auth**: JWT-based authentication
- **Monitoring**: Background scheduler (5-minute cycles)
- **Alerts**: Telegram Bot API

## What's Been Implemented (Feb 8, 2026)

### Full Multi-Brand Support (Feb 8, 2026) - COMPLETE
**Feature:** Enterprise-ready multi-brand data isolation

**1. Brand Entity Enhancement:**
- Brand model with: id, name, slug, status (active/archived), notes
- Archive/unarchive functionality (soft delete)
- Cannot hard-delete brands with associated data
- API: `/api/brands`, `/api/brands/{id}/archive`, `/api/brands/{id}/unarchive`

**2. User Brand Scoping:**
- User model with `brand_scope_ids` array
- Super Admin: `brand_scope_ids = null` (full access to all brands)
- Admin/Viewer: Must have at least one brand assigned
- Migration ran to assign all existing users to all brands

**3. Backend Enforcement (API Level):**
- `build_brand_filter()` - Build MongoDB filter based on user's brand scope
- `require_brand_access()` - Validate brand access, returns 403 if unauthorized
- All V3 APIs enforce brand scoping: asset-domains, networks, structure
- POST operations validate brand ownership

**4. Frontend Brand Filtering:**
- `BrandContext` - Manages brand state and filtering
- `BrandSwitcher` component in sidebar
  - Super Admin: "All Brands" option + any brand
  - Admin/Viewer: Only assigned brands (no "All Brands")
- Brand selection persists in localStorage (Super Admin only)

**5. User Management UI:**
- Users page with "Brand Access" column
- Shows "All Brands" badge (green) for Super Admin
- Shows brand badges for Admin/Viewer users
- Edit dialog with brand multi-select
- "Select All" / "Clear" buttons
- Validation: At least one brand required for non-Super Admin

**Tests:** 100% pass rate (14/14 backend, 100% frontend)

### P0 Enhanced Change Note UX + Main Node Logic + Switch Main Target (Feb 9, 2026) - COMPLETE
**Feature 1: Enhanced Change Note UX**
- ✅ `ChangeNoteInput` reusable component with:
  - Large auto-resize textarea (140px min-height)
  - Character counter (0 / 2000)
  - Quick templates dropdown (4 categories: Linking Strategy, Cannibalization Fix, Optimization, Maintenance)
  - "Min 3 chars required" badge + "Recommended 150+" guidance
  - Variant styles: default (amber), delete (red), add (emerald)
- ✅ Used in: Add Node, Edit Node, Delete Node, Switch Main Target dialogs

**Feature 2: Main Node Logic Fix**
- ✅ Backend validation (v3_router.py):
  - Main nodes MUST NOT have `target_entry_id` - returns 400 with clear message
  - Main nodes MUST have `PRIMARY` status (not canonical/redirect)
  - Network can only have ONE main node at a time
- ✅ New `SeoStatus.PRIMARY` enum value for main nodes
- ✅ Frontend Status dropdown shows role-specific options:
  - Main: "Primary Target" only (dropdown disabled)
  - Supporting: Canonical, 301/302 Redirect, Restore

**Feature 3: Switch Main Target (Safe Role Swap)**
- ✅ `POST /api/v3/networks/{id}/switch-main-target` endpoint
- ✅ Safe operation (no node deletion):
  1. Old main → Supporting (canonical, targets new main)
  2. New main → Main (primary status, no target)
  3. All tiers recalculated via BFS
- ✅ Requires mandatory `change_note` (min 3 chars)
- ✅ Creates SEO change logs and notification for main domain change
- ✅ UI: "Switch to Main Target" in node dropdown menu (supporting nodes only)
- ✅ Confirmation dialog shows what will happen

**Tests:** 100% pass rate (7/7 backend pytest, 100% frontend Playwright)

### P0 SEO Change History & Alerts UI (Feb 9, 2026) - COMPLETE
**Feature 1: Change History Tab**
- ✅ Added "Change History" tab to Network Detail page
- ✅ Table view: Date | User | Domain/Path | Action | Note | Details
- ✅ Relative timestamps (Just now, Xm ago, Xh ago, Xd ago)
- ✅ Action type badges with color coding:
  - Created (emerald), Updated (blue), Deleted (red), Relinked (purple), Role Changed (orange), Path Changed (cyan)
- ✅ Click row → Opens detail drawer
- ✅ Detail drawer shows:
  - Affected node, changed by, date
  - Change note (amber highlight)
  - Before/After snapshot comparison
  - "View Node in Graph" button → highlights node in D3 and switches tab

**Feature 2: Network Alerts Panel**
- ✅ Added "Alerts" tab with unread count badge
- ✅ Shows SEO-related notifications only:
  - Main Domain Changed, Node Deleted, Target Relinked, Orphan Detected, SEO Conflict, High Tier NoIndex
- ✅ Read/unread visual state
- ✅ "Mark all read" button
- ✅ Click notification → Opens related change history entry (via change_log_id link)
- ✅ Shows: notification type, message, affected node, timestamp, actor, change note

**Tests:** 100% pass rate (14/14 backend, 100% frontend)

### P0 SEO Change Intelligence Layer (Feb 9, 2026) - COMPLETE
**Feature Overview:** Separates system logs from SEO decision logs. Forces human-readable explanations for all SEO structure changes.

**1. Log Separation (TWO DISTINCT LOG SYSTEMS):**
- **System Logs** (`activity_logs_v3`): Infrastructure & operations (monitoring, background jobs, migrations)
- **SEO Change Logs** (`seo_change_logs`): Human SEO decisions with mandatory change_note

**2. SEO Change Logs - Data Model:**
```
Collection: seo_change_logs
Fields: id, network_id, brand_id, actor_user_id, actor_email, action_type,
        affected_node, before_snapshot, after_snapshot, change_note (REQUIRED),
        entry_id, archived, archived_at, created_at
```
- Action types: create_node, update_node, delete_node, relink_node, change_role, change_path

**3. Mandatory Change Note (NON-NEGOTIABLE):**
- ✅ All structure CRUD operations require `change_note` field (min 3 chars, max 500)
- ✅ Pydantic validation enforced at API level (422 if missing)
- ✅ Frontend dialogs show amber-highlighted Change Note field
- ✅ Save/Delete buttons disabled until change_note is filled
- Example notes: "Support halaman promo utama", "Perbaikan keyword cannibalization"

**4. API Endpoints:**
- `GET /api/v3/networks/{id}/change-history` - Get SEO change logs for a network
- `GET /api/v3/networks/{id}/notifications` - Get network notifications
- `POST /api/v3/networks/{id}/notifications/{id}/read` - Mark notification as read
- `POST /api/v3/networks/{id}/notifications/read-all` - Mark all as read
- `GET /api/v3/change-logs/stats?days=30` - Team evaluation metrics

**5. SEO Network Notifications:**
- Auto-triggered on important events: Main domain change, Node deletion, Target relink, Orphan detected
- Stored in `seo_network_notifications` collection
- UI panel in Network Detail page (to be implemented in Phase 4)

**6. Separate SEO Telegram Channel:**
- `GET /api/v3/settings/telegram-seo` - Get SEO telegram config
- `POST /api/v3/settings/telegram-seo` - Update SEO telegram settings
- `POST /api/v3/settings/telegram-seo/test` - Send test message
- Falls back to main Telegram channel if not configured

**7. Log Lifecycle:**
- `archived` and `archived_at` fields for retention management
- Archived logs remain in same collection (not moved)
- Method: `archive_old_logs(days_old=90)`

**Tests:** 100% pass rate (16/16 backend, 100% frontend)

### P0 Asset Domain ↔ SEO Network Visibility (Feb 9, 2026) - COMPLETE
**Feature 1: Show SEO Network Usage in Asset Domains Table**
- ✅ Enhanced `GET /api/v3/asset-domains` to include `seo_networks` array
- ✅ Each network entry contains: `network_id`, `network_name`, `role`, `optimized_path`
- ✅ Data derived from `seo_structure_entries` via MongoDB aggregation (efficient, no N+1)
- ✅ Frontend `SeoNetworksBadges` component added to `DomainsPage.jsx`
  - Shows first 2 network badges with colors (green=main, purple=supporting)
  - "+N more" tooltip for domains with >2 networks
  - "—" indicator for unused domains
  - Badges are clickable → navigate to network detail page
  - Tooltip shows: network name, role, path

**Feature 2: Domain Search + Auto-Suggest in SEO Networks**
- ✅ New endpoint `GET /api/v3/networks/search?query=` 
  - Searches `seo_structure_entries` by domain_name OR optimized_path
  - Brand-scoped (users only see results from their brands)
  - Max 10 results for performance
  - Returns results grouped by domain
  - Each result: `entry_id`, `network_id`, `network_name`, `domain_name`, `optimized_path`, `role`
- ✅ Frontend search UI in `GroupsPage.jsx`:
  - Debounced search input (350ms delay)
  - Auto-suggest dropdown with grouped results
  - Shows: domain → path → role → network name
  - Two click actions:
    1. Click row → Highlight matching networks in list (dimming others)
    2. "Open" button → Navigate directly to network detail
  - "N highlighted" badge with "Clear filter" link

**Tests:** 100% pass rate (9/9 backend, 100% frontend)

### P0 Domain Monitoring Fix (Feb 8, 2026) - COMPLETE
**Issue:** Monitoring was not properly split into independent engines

**Two Independent Engines Implemented:**

1. **Domain Expiration Monitoring** (ExpirationMonitoringService)
   - Runs on daily loop (hourly check with 24-hour alert deduplication)
   - Alerts when expiration_date <= today + alert_window_days
   - Sends Telegram alert with: domain, brand, registrar, expiration, auto-renew
   - Tracks `expiration_alert_sent_at` to avoid spam
   - Configurable alert thresholds (30, 14, 7, 3, 1, 0 days)
   - Option to include/exclude auto-renew domains

2. **Domain Availability Monitoring** (AvailabilityMonitoringService)
   - Runs at configurable intervals (default 5 minutes)
   - Only checks domains with `monitoring_enabled: true`
   - Alerts ONLY on UP → DOWN transition
   - Optional recovery alert on DOWN → UP
   - Includes SEO context if domain is in SEO Network
   - Tracks: `last_ping_status`, `last_http_code`, `last_checked_at`

**New Fields Added:**
- `expiration_alert_sent_at` - Track last expiration alert timestamp
- `last_ping_status` - Previous status for transition detection
- `last_http_code` - Last HTTP response code
- `last_checked_at` - Last availability check timestamp

**Settings → Monitoring Page:**
- `/settings/monitoring` with 4 tabs
- Expiration Monitoring: enabled, alert_window, thresholds, include_auto_renew
- Availability Monitoring: enabled, interval, timeout, alert_on_down, alert_on_recovery, follow_redirects
- Expiring Domains list (with days remaining, status badges)
- Down Domains list (with HTTP code, network context)

**API Endpoints:**
- `GET /api/v3/monitoring/settings` - Get config
- `PUT /api/v3/monitoring/settings` - Update config (Super Admin)
- `GET /api/v3/monitoring/stats` - Get counts
- `POST /api/v3/monitoring/check-expiration` - Manual trigger
- `POST /api/v3/monitoring/check-availability` - Manual trigger
- `GET /api/v3/monitoring/expiring-domains?days=N` - List expiring
- `GET /api/v3/monitoring/down-domains` - List down

**Tests:** 100% pass rate (11/11 backend, 100% frontend)

### P0 Critical Bug Fix - Node Linking (Feb 8, 2026) - COMPLETE
**Issue:** Node-to-node linking was broken in UI and graph visualization

**6-Point Fix Applied:**
1. ✅ **API Fix:** `GET /api/v3/structure` returns `node_label` (domain + path) and `entry.id`
2. ✅ **Frontend Dropdown:** Target Node dropdown populated from structure entries (not asset domains)
3. ✅ **Dropdown Rules:**
   - label = node_label
   - value = entry.id
   - Includes "None (Orphan)" option
   - Excludes self from list
4. ✅ **Save Logic:** Sends `target_entry_id` (entry.id) to backend
5. ✅ **D3 Graph:** Links built using `source: e.id`, `target: e.target_entry_id`, `forceLink().id(d => d.id)`
6. ✅ **Path Normalization:** Empty/null paths → None; paths always start with `/`

**Results:**
- Correct node-to-node linking
- Connected visual graph with visible links
- Accurate derived tiers via BFS algorithm
- All tests passed (16/16 backend, 100% frontend)

### V3 P0 Features - COMPLETE (Feb 8, 2026)

**Feature 1: Registrar as Master Data - COMPLETE**
- ✅ New `registrars` collection with CRUD API at `/api/v3/registrars`
- ✅ Fields: name (required, unique), website, status (active/inactive), notes
- ✅ Write access restricted to `super_admin` role (403 for others)
- ✅ Updated `AssetDomain` model with `registrar_id` foreign key
- ✅ Registrar Management page at `/registrars` (Settings menu)
- ✅ Searchable dropdown in Domain Add/Edit forms (auto-suggest)
- ✅ All changes logged in `activity_logs_v3`
- ✅ Initial data: GoDaddy, Namecheap registrars

**Feature 2: SEO Networks with Brand Association - COMPLETE**
- ✅ `brand_id` is now REQUIRED on `SeoNetwork` model
- ✅ Network creation validates brand existence (400 if not found)
- ✅ Create Network dialog shows Brand as required field with dropdown
- ✅ Networks list displays brand name badge on cards
- ✅ Brand filter dropdown on Networks page
- ✅ `brand_name` enriched in API responses

**Feature 3: Path-Level SEO Nodes - COMPLETE**
- ✅ `optimized_path` field added to `SeoStructureEntry`
  - Enables page-level SEO targeting (e.g., /blog/best-product)
- ✅ Node-to-node relationships via `target_entry_id` (in addition to legacy `target_asset_domain_id`)
- ✅ Node = Domain + optional Path
- ✅ `node_label` computed for display (domain + path)
- ✅ Target Node dropdown shows entries from same network
- ✅ Edit Structure Entry dialog has "Path Configuration" section

**Feature 4: Updated Tier Calculation - COMPLETE**
- ✅ `TierCalculationService` updated for node-based graph traversal
- ✅ BFS algorithm traverses `target_entry_id` relationships
- ✅ Legacy `target_asset_domain_id` supported for backward compatibility
- ✅ Tiers keyed by `entry_id` (not `asset_domain_id`)
- ✅ Visual graph and tier distribution working correctly

**Feature 5: SEO Workflow Refinement - COMPLETE**
- ✅ Network creation: Name, Brand, Description only
- ✅ Domain assignment with full SEO structure fields (in Network detail)
- ✅ Clear CTAs: "Add Domains to Network" after creation
- ✅ Edit Structure Entry dialog has all fields:
  - Path Configuration (optimized_path)
  - SEO Structure (role, status, index, target node)
  - Ranking & Path Tracking (URL, keyword, position)

### V2 Backend (LEGACY - Functional)
- ✅ JWT authentication with RBAC (super_admin, admin, viewer)
- ✅ Categories CRUD with 8 default categories
- ✅ Brands CRUD
- ✅ Domains CRUD with full Asset Management fields
- ✅ Groups/Networks CRUD with D3 visualization
- ✅ Background monitoring scheduler (APScheduler)
- ✅ Domain health checks (ping/HTTP)
- ✅ Expiration tracking with alerts
- ✅ SEO Conflict Detection (14 types)
- ✅ Alert system with acknowledge/mute
- ✅ Telegram Bot integration
- ✅ Audit logging
- ✅ CSV/JSON export

### V3 Architecture (MIGRATION COMPLETE - Feb 8, 2026)
**Phase 0 - Preparation: COMPLETED**
- ✅ Full database backup at `/app/backups/v2_backup_20260208_085617`
- ✅ Migration plan documented at `/app/docs/migration/V3_MIGRATION_PLAN.md`

**Phase 1 - Create New Schema: COMPLETED**
- ✅ V3 Models defined (`/app/backend/models_v3.py`)
  - AssetDomain: Pure inventory (no SEO structure)
  - SeoNetwork: Strategy containers
  - SeoStructureEntry: Relationship layer
  - ActivityLog: Enhanced audit trail
- ✅ ActivityLog service (`/app/backend/services/activity_log_service.py`)
- ✅ Tier Calculation service (`/app/backend/services/tier_service.py`)
  - Tiers are DERIVED from graph distance, not stored

**Phase 2-4 - Data Migration: COMPLETED**
- ✅ Phase 2: 23 domains → 23 asset_domains
- ✅ Phase 3: 4 groups → 4 seo_networks  
- ✅ Phase 4: 23 seo_structure_entries (3 main, 20 supporting)
- ✅ 50 activity logs created (actor: system:migration_v3)
- ✅ Legacy ID mappings saved in `/app/docs/migration/`

**Phase 5 - V3 API: COMPLETED**
- ✅ V3 Router created (`/app/backend/routers/v3_router.py`)
- ✅ Asset Domains CRUD: `/api/v3/asset-domains`
- ✅ SEO Networks CRUD: `/api/v3/networks`
- ✅ Structure Entries CRUD: `/api/v3/structure`
- ✅ Activity Logs: `/api/v3/activity-logs`
- ✅ Tier Calculation: `/api/v3/networks/{id}/tiers`
- ✅ V3 Dashboard: `/api/v3/reports/dashboard`
- ✅ Conflict Detection: `/api/v3/reports/conflicts`

**Phase 6 - Frontend Update: COMPLETED**
- ✅ V3 API service layer (`/app/frontend/src/lib/api.js`)
- ✅ NetworkGraph.jsx updated for V3 with derived tiers
- ✅ GroupDetailPage.jsx uses V3 API with tier distribution
- ✅ DomainsPage.jsx updated to use V3 assetDomainsAPI

### New Features (Feb 8, 2026)
- ✅ **Telegram Integration**: Bot @monitoringseo_bot configured
  - Test alerts, Conflict alerts, Domain change alerts
- ✅ **Ranking & Path Tracking**: Fields added to structure entries
  - ranking_url, primary_keyword, ranking_position
  - Edit dialog in Network detail page
- ✅ **Bulk CSV Import**: `/api/v3/import/domains`
  - Import CSV button on Domains page
  - Template download, preview, import results
- ✅ **Activity Logs Viewer**: `/activity-logs` page
  - Filter by entity, action, actor

### P1 Features (Feb 8, 2026) - ALL COMPLETED

**Feature 1: Export V3 Data to CSV/JSON - COMPLETE**
- ✅ Export Asset Domains: `GET /api/v3/export/asset-domains?format=csv|json`
  - Enriched with brand_name, category_name, registrar_name
  - Filter by brand_id, status
- ✅ Export Network Structure: `GET /api/v3/export/networks/{id}?format=csv|json`
  - Full structure with all entries, tiers, relationships
  - tier_distribution summary
- ✅ Export All Networks: `GET /api/v3/export/networks?format=csv|json`
  - Metadata with domain_count
- ✅ Export Activity Logs: `GET /api/v3/export/activity-logs?format=csv|json`
  - Filter by entity_type, action_type, actor, days
- ✅ Frontend: Export dropdown on Domains page and Network detail page

**Feature 2: Dashboard Refresh Interval - COMPLETE**
- ✅ User preference setting: `GET/PUT /api/v3/settings/dashboard-refresh`
  - Options: Manual (0), 30s, 1m, 5m, 15m
  - Stored in user_preferences collection
- ✅ Lightweight stats API: `GET /api/v3/dashboard/stats`
  - Only counts (no heavy joins) for smooth refresh
- ✅ Frontend: Refresh interval dropdown in Dashboard header
  - Data-only refresh (no page flicker)

**Feature 3: Bulk Node Import with Path Support - COMPLETE**
- ✅ Node Import API: `POST /api/v3/import/nodes`
  - CSV format: domain_name, optimized_path, domain_role, target_domain, target_path, etc.
  - create_missing_domains option
  - Resolves target_domain + target_path → target_entry_id
  - Returns summary with imported/skipped/errors counts
- ✅ Template API: `GET /api/v3/import/nodes/template`
  - Example rows for main and supporting nodes
- ✅ Frontend: Import Nodes button and dialog on Network detail page
  - CSV file upload with preview
  - Create missing domains toggle
  - View log details with before/after values
  - Stats cards for action types

**V3 Architecture - FULLY COMPLETE**

### Frontend
- ✅ SEO-NOC Dashboard with:
  - Stats grid (domains, networks, monitored, index rate, alerts, conflicts)
  - Tier distribution chart
  - Index status pie chart
  - Monitoring status chart
  - Recent alerts panel
  - SEO Conflicts panel
- ✅ Asset Domains page with filters and Detail panel
- ✅ Domain Detail Panel with:
  - Monitoring section (Check Now, Mute/Unmute)
  - Asset Information (registrar, expiration, category)
  - SEO Configuration (status, index, tier, network)
  - Network Hierarchy (parent/children)
  - Notes & Context
  - Activity History
  - Danger Zone actions
- ✅ Alert Center with filters (severity, type, acknowledged)
- ✅ Categories management (Super Admin)
- ✅ Settings page with Telegram configuration
- ✅ SEO Networks with D3 visualization

### Telegram Alerts
- ✅ Bot token configured
- ✅ Alert format: Domain, Brand, Category, SEO Structure, Issue, Severity
- ✅ Expiration alert format
- ✅ SEO Conflict alert format
- ✅ Test message functionality

## Demo Data
- 3 brands (Panen138, PANEN77, DEWI138)
- 8 default categories
- 2 registrars (GoDaddy, Namecheap)
- 5 networks (Main SEO Network, Support Network, Test Network, Domain A, Test V3 Network)
- 23-25 domains with hierarchy
- 14 SEO conflicts detected

## Prioritized Backlog

### P0 (Critical) - ALL COMPLETED
- ✅ V3 Architecture Migration (Phases 0-4)
- ✅ V3 API Endpoints
- ✅ Frontend V3 Integration (Networks, Domains)
- ✅ Derived Tier Calculation
- ✅ Telegram Integration
- ✅ Ranking & Path Tracking UI
- ✅ Bulk CSV Import
- ✅ Activity Logs Viewer
- ✅ **Registrar as Master Data** (Feb 8, 2026)
- ✅ **SEO Networks with Brand Association** (Feb 8, 2026)
- ✅ **Path-Level SEO Nodes** (Feb 8, 2026)
- ✅ **SEO Workflow Refinement** (Feb 8, 2026)

### P1 (High Priority)
- ✅ **Export V3 Data to CSV/JSON** (Feb 8, 2026)
- ✅ **Dashboard Refresh Interval** (Feb 8, 2026)
- ✅ **Bulk Node Import with Path Support** (Feb 8, 2026)
- ✅ **Tier-based Grouping in Domain List** (Feb 9, 2026)
  - Accordion-style tier groups (LP/Money Site, Tier 1, Tier 2, etc.)
  - Node counts per tier, collapse/expand functionality
  - Grouped/Flat view toggle
- ✅ **Filterable SEO Change History Timeline** (Feb 9, 2026)
  - Filters: User, Action type, Node, Date range
  - Human-readable diffs (Role, Status, Target as domain names not IDs)
  - "View Node in Graph" button for highlighting
- ✅ **SEO Change Notifications via Telegram** (Feb 9, 2026)
  - Dedicated Telegram channel for SEO changes (separate from monitoring)
  - Full Bahasa Indonesia message format
  - Settings UI at Settings → SEO Notifications tab
  - Change note enforcement (minimum 10 characters)
  - Rate limiting (1 msg per network per minute)
  - Fallback to main Telegram if SEO channel not configured
  - Real-time SEO structure snapshot in notifications
- ✅ **User Registration Approval & Super Admin User Management** (Feb 9, 2026)
  - New users register with status=pending, cannot login until approved
  - Super Admin can view pending users in Users → Pending Approvals tab
  - Super Admin can approve (assign role + brand scope) or reject users
  - Super Admin can manually create users (active immediately, manual or auto-generated password)
  - Login shows specific messages for pending/rejected users
  - All actions logged for audit trail
- ✅ **SEO Network Ranking Visibility & Status Indicator** (Feb 9, 2026)
  - Each network shows ranking_status: ranking (green), tracking (amber), none (gray)
  - Visual priority: Ranking networks have green border highlight
  - Mini metrics: ranking nodes count, best position (#X), tracked URLs count
  - Filters: ranking status filter (Ranking/Tracking/No Ranking)
  - Sorting: by best position (ASC) or most ranking nodes (DESC)
- 🟡 **Conflict Detection UI** - Backend API exists, frontend needed:
  - Alert Center integration
  - Node highlighting in D3 graph
  - Conflict details in node panel

### P2 (Medium Priority - Remaining)
- Email notification channel (Resend/SendGrid)
- Scheduled conflict alerts (cron job)
- Domain health check improvements
- Alert history and analytics
- Mobile push notifications
- Slack/Discord integration

### P3 (Low Priority)
- Multi-user collaboration features
- API documentation (OpenAPI)
- Webhook integrations
- Team workspaces
- White-label option

## Next Tasks List
1. **P1: Conflict Detection UI** (Backend API exists at `/api/v3/reports/conflicts`)
   - Alert Center panel for conflicts
   - Node highlighting in D3 diagram
   - Conflict details in node detail panel
2. **P1: Root vs. Path Main Node Visualization** - Solid vs dashed border in D3 graph
3. **P1: Milestone Tag on Change Notes** - Optional milestone field
4. **P1: Network Creation Telegram Notification** - Trigger notification when new SEO network is created
5. Email notification integration (Resend/SendGrid)
6. Scheduled conflict alerts (cron)
7. Domain health check improvements
8. Alert history and analytics
9. **BACKLOG: Compare Changes** - Advanced diff viewer (parked)

## Test Credentials
- **Super Admin**: `admin@test.com` / `admin123` (confirmed working)
- **Alt Super Admin**: `superadmin@seonoc.com` / `SuperAdmin123!`
- **Admin**: `admin@seonoc.com` / `Admin123!`

## Key Files Reference
- V2 Backend: `/app/backend/server.py`
- V3 Models: `/app/backend/models_v3.py`
- V3 Router: `/app/backend/routers/v3_router.py`
- V3 Services: `/app/backend/services/`
- Migration Scripts: `/app/backend/migrations/`
- Migration Plan: `/app/docs/migration/V3_MIGRATION_PLAN.md`
- Database Backup: `/app/backups/v2_backup_20260208_085617/`
- Technical Docs: `/app/docs/` (README, API, INSTALL, DEPLOYMENT, etc.)
