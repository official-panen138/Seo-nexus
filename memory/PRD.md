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

## What's Been Implemented

### P0 Bug Fix: "Failed to load conflicts" Toast Error (Feb 13, 2026) - COMPLETE
**Issue:** The unified SEO Conflicts dashboard at `/alerts` displayed a "Failed to load conflicts" toast error immediately upon page load, even though the API was functioning correctly.

**Root Cause:** In `AlertsPage.jsx`, the code was calling `conflictsAPI.getAll()` which doesn't exist in the API definition. The correct method is `conflictsAPI.getStored()`.

**Fix Applied:**
- Changed `conflictsAPI.getAll()` to `conflictsAPI.getStored()` in `AlertsPage.jsx` line 151
- Deleted obsolete `ConflictDashboardPage.jsx` file (replaced by unified AlertsPage)
- Removed the dead import from `App.js`

**Files Updated:**
- `/app/frontend/src/pages/AlertsPage.jsx` - Fixed API call
- `/app/frontend/src/App.js` - Removed dead import
- `/app/frontend/src/pages/ConflictDashboardPage.jsx` - DELETED (obsolete)

---

### Merged SEO Conflicts Dashboard (Feb 12, 2026) - COMPLETE
**Feature:** Merged two separate conflict dashboards (SEO Conflicts + Resolution Dashboard) into one unified page.

**Before:** Two separate pages with overlapping functionality
- `/alerts` - Basic conflicts list with tabs
- `/conflicts/dashboard` - Detailed metrics, charts, top resolvers

**After:** Single unified dashboard at `/alerts` with all features:
- Top metrics: Total Conflicts, Resolution Rate, Avg Resolution Time, Recurring Conflicts
- Extended metrics: False Resolution Rate, Avg Recurrence Interval, Resolution Time Breakdown
- Analysis cards: Conflicts by Severity, Conflicts by Type, Top Resolvers
- Tracked Conflicts table with tabs (All, Detected, In Progress, Resolved)
- Period selector (7/14/30/90 days)
- Create Optimization Tasks button

**Files Updated:**
- `/app/frontend/src/pages/AlertsPage.jsx` - Completely rewritten to merge both dashboards
- `/app/frontend/src/App.js` - `/conflicts/dashboard` now redirects to AlertsPage

---

### Telegram Expiration Alert - SEO Structure Section (Feb 12, 2026) - COMPLETE
**Feature:** Updated Domain Expiration Alert Telegram notifications to use "🧭 STRUKTUR SEO TERKINI" section header (consistent with other SEO notifications).

**Implementation:**
- Updated `_format_expiration_alert_seo_aware` in `/app/backend/services/monitoring_service.py`
- Changed "🔗 FULL SEO STRUCTURE" to "🧭 STRUKTUR SEO TERKINI" for consistency with Domain Down alerts and other SEO notifications

---

### Enhanced Import/Export Asset Domains (Feb 12, 2026) - COMPLETE
**Feature:** Comprehensive import/export functionality for asset domains with validation preview.

**Export:**
- CSV format with all required fields (Domain, Brand, Category, Domain Active Status, Monitoring Status, Lifecycle, Quarantine Category, SEO Networks comma-separated, Expiration Date, Monitoring Enabled ON/OFF)
- Respects ALL current filters (exports only filtered/visible data)
- Includes registrar and notes fields

**Import:**
- CSV upload with mandatory validation preview before confirm
- 3-step flow: Upload → Preview → Result
- Shows separate sections: New domains (green), Updated domains (blue), Errors (red)
- Toggle switches to select Create New / Update Existing
- Invalid rows displayed with clear error messages and NOT imported
- No silent overwrite - conflicts shown clearly
- Supports date formats: YYYY-MM-DD, YYYY/MM/DD, DD-MM-YYYY, DD/MM/YYYY

**Backend Endpoints:**
- `GET /api/v3/export/asset-domains` - Enhanced export with all filters
- `POST /api/v3/import/domains/preview` - Validation without commit
- `POST /api/v3/import/domains/confirm` - Apply validated changes
- `GET /api/v3/import/domains/template` - Download CSV template

---

### Quarantine Categories - Dedicated Settings Page (Feb 12, 2026) - COMPLETE
**Feature:** Moved Quarantine Category management from Settings page "Master Data" tab to a dedicated page with its own sidebar entry.

**Implementation:**
- Created new `QuarantineCategoriesPage.jsx` at `/app/frontend/src/pages/QuarantineCategoriesPage.jsx`
- Added sidebar menu item "Quarantine Categories" with ShieldAlert icon in `Layout.jsx`
- Added route `/settings/quarantine-categories` in `App.js` with menu permission check
- Removed "Master Data" tab from `SettingsPage.jsx`
- Added path mapping in `menuPermissions.jsx` for the new route

**Features:**
- Full CRUD for quarantine categories (Add, Edit, Delete)
- Super Admin only access (with permission check)
- Auto-converts category value to lowercase with underscores
- Toast notifications for all actions
- Proper loading states and error handling

**Tests:** 100% pass rate (13/13 frontend tests)

---

### Domain Status, Monitoring & Lifecycle Refactor V2 (Feb 12, 2026) - COMPLETE
**Feature:** Complete separation of domain statuses with column sorting and tooltips.

**Core Concepts (MUST FOLLOW):**
| Concept | Type | Description |
|---------|------|-------------|
| `Monitoring Toggle` | CONTROL | Human decision (ON/OFF) - enables/disables monitoring |
| `Monitoring Status` | RESULT | System-generated (Up/Down/Soft Blocked/Unknown) - NEVER editable |
| `Domain Active Status` | BUSINESS | Time-based (Active/Expired) - computed from expiration_date |
| `Lifecycle` | STRATEGIC | SEO strategy (Active/Released/Quarantined/Not Renewed) |

**Automatic Rules:**
1. **Auto-transition:** When `domain_active_status=Expired` → `lifecycle_status=Not Renewed` (forced)
2. **Monitoring Matrix:** Only `lifecycle=Active` AND `domain_active_status=Active` allows monitoring
3. **Invalid State Blocking:** Cannot set `lifecycle=Active` when domain is expired (HTTP 400)

**Column Sorting:**
- Sortable: Domain, Brand, Domain Active Status, Monitoring Status, Lifecycle, SEO Networks, Expiration
- Default sort: "critical" - prioritizes Down → Soft Blocked → Quarantined → Expired → A-Z

**View Mode Tabs:**
- All Domains, Unmonitored in SEO, Released, Quarantined, **Not Renewed** (new)

**Tooltips (MANDATORY):**
- Monitoring Toggle: "Enable or disable technical monitoring for this domain..."
- Monitoring Status: "Latest technical check result. Unknown means monitoring is disabled..."
- Lifecycle: "Describes how the domain is used in SEO strategy..."

**Tests:** 100% pass rate (backend + frontend)

---

### Domain Status, Monitoring & Lifecycle Refactor (Feb 12, 2026) - COMPLETE
**Feature:** Complete separation of domain statuses into three distinct concepts for noise-free SEO operations.

**1. Three-Part Status System:**
| Field | Type | Purpose |
|-------|------|---------|
| `domain_active_status` | AUTO | Administrative status based on expiration_date (Active/Expired) |
| `monitoring_status` | AUTO | Technical availability from monitoring engine (Up/Down/JS Challenge/etc.) |
| `lifecycle_status` | MANUAL | Strategic SEO decision (Active/Released/Quarantined) - Super Admin only |
| `quarantine_category` | MANUAL | Reason for quarantine (Spam/DMCA/Manual Penalty/etc.) |

**2. Automatic Rules (Mandatory):**
- Auto-Release on Expiration: When `domain_active_status=Expired`, system auto-sets `lifecycle_status=Released`
- Invalid State Prevention: Cannot set `lifecycle_status=Active` if domain is expired (HTTP 400)
- Monitoring Matrix: Only `lifecycle_status=Active` domains can be monitored

**3. Table Columns (Asset Domains Page):**
- Domain, Brand, Category, Domain Active Status, Monitoring Status, Lifecycle (with tooltip), Quarantine Category, SEO Networks, Monitoring Toggle, Expiration, Actions

**4. Filters:**
- Domain Active Status (Active/Expired)
- Monitoring Status (Up/Down/Soft Blocked/JS Challenge/Country Block/Captcha/Unknown)
- Lifecycle (Active/Released/Quarantined)
- Quarantine Category
- Monitoring Toggle (ON/OFF)
- Used in SEO Network

**5. View Mode Tabs:**
- All Domains, Unmonitored in SEO, Released, Quarantined

**6. Super Admin Actions:**
- Change Lifecycle, Quarantine Domain, Remove Quarantine, Release Domain, Delete Domain

**API Endpoints:**
- `GET /api/v3/asset-domains` - List with filters: domain_active_status, monitoring_status, lifecycle_status, quarantine_category
- `POST /api/v3/asset-domains/{id}/set-lifecycle` - Change lifecycle status
- `POST /api/v3/asset-domains/{id}/quarantine` - Quarantine domain
- `POST /api/v3/asset-domains/{id}/remove-quarantine` - Remove quarantine
- `POST /api/v3/asset-domains/{id}/mark-released` - Mark as released

**Tests:** 100% pass rate (28/28 backend, 100% frontend)

### SEO Network Health Indicators (Feb 12, 2026) - COMPLETE
**Feature:** Visual health indicators on SEO Network cards showing domain issues.

**Implementation:**
- Added `expired_domains_count` field to network response (computed from expiration dates)
- Added `quarantined_domains_count` field (computed from lifecycle_status and quarantine_category)
- Network cards now display:
  - 🔴 "{N} expired" badge if any domains are expired
  - 🟠 "{N} quarantined" badge if any domains are quarantined
- Helps quickly identify networks that need attention

---

### SEO-Aware Domain Monitoring + Structured Alert Output (Feb 10, 2026) - COMPLETE
**Feature:** Transform domain monitoring into a true SEO Incident Response System

**1. Structured Alert Format (STRUKTUR SEO TERKINI):**
- All monitoring alerts include tier-based SEO snapshot
- Format: LP/Money Site → Tier 1 → Tier 2 → ... with relation types
- No "Unknown" in test mode if domain exists in SEO network
- Full graph resolution for upstream/downstream chains

**2. Strict Severity Calculation:**
- **CRITICAL**: Domain is Money Site OR Tier 1 reaching Money Site
- **HIGH**: Tier 1 node OR ≥3 downstream nodes
- **MEDIUM**: Tier 2+ with indirect money site impact
- **LOW**: Orphan/unused node

**3. Message Order (Telegram):**
1. Alert Type (DOWN / EXPIRATION / CONFIG MISSING)
2. Domain Info (Status, Brand, Monitoring)
3. SEO Context Summary (Network, Tier, Role, Reaches Money Site)
4. 🧭 STRUKTUR SEO TERKINI (Tier-based structure)
5. 🔥 Impact Summary (Severity, downstream nodes)
6. ⏰ Next Action (based on severity)

**4. Unmonitored Domain Reminders:**
- Daily ⚠️ MONITORING NOT CONFIGURED alerts at 8:00 AM
- Sent for domains in SEO networks without monitoring enabled
- Stops only when monitoring enabled OR domain removed from network
- 24h rate limit to prevent spam

**API Endpoints:**
- `GET /api/v3/monitoring/unmonitored-in-seo` - List unmonitored SEO domains
- `POST /api/v3/monitoring/domain-down/test` - Test alert with full SEO context
- `POST /api/v3/monitoring/send-unmonitored-reminders` - Manual reminder trigger

**Tests:** 100% pass rate (20/20 backend tests)

---

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


---

### Legacy Monitoring Alerts Removal (Feb 10, 2026) - COMPLETE
**Feature:** Complete removal of the legacy "Monitoring Alerts" feature, replaced by the new SEO-aware Domain Monitoring system.

**What was removed:**

**1. Frontend - AlertsPage.jsx:**
- ❌ REMOVED: "Alerts" tab showing generic monitoring alerts
- ❌ REMOVED: Tabbed interface (Alerts | SEO Conflicts)
- ✅ KEPT: SEO Conflicts display (now the main and only view)
- ✅ Refactored to single-purpose "SEO Conflicts" page

**2. Frontend - SettingsPage.jsx:**
- ❌ REMOVED: Legacy "Monitoring Alerts" tab
- ✅ Fixed: Duplicate `loadSettings` function syntax error
- ✅ KEPT: 4 tabs only: Branding, Timezone, SEO Notifications, Domain Monitoring

**3. Frontend - api.js:**
- ✅ Updated: `monitoringAPI.getStats()` now points to `/api/v3/monitoring/stats`
- ✅ KEPT: alertsAPI for acknowledging alerts (still used by dashboard)

**4. Backend - v3_router.py:**
- ✅ KEPT: `/api/v3/monitoring/stats` endpoint (provides availability/expiration stats for dashboard)
- ✅ Fixed: Unused `resolved_complaints_count` variable (linter warning)

**What was kept (New Domain Monitoring System):**
- `/api/v3/settings/telegram-monitoring` - Dedicated Telegram channel for domain alerts
- `/api/v3/monitoring/stats` - Monitoring statistics for dashboard
- SEO-aware alerts via `monitoring_service.py` with:
  - Full SEO context (structure chain, impact score)
  - Upstream chain to Money Site
  - Downstream impact analysis
  - Soft-block detection (Cloudflare, captcha, geo-blocking)

**Tests:** 100% pass rate (12/12 backend, 100% frontend UI verified) ✅

---

## Future Tasks (Backlog)

### P1 - High Priority
1. **Reminder effectiveness metric** - Track how many reminders are sent before optimization is resolved
2. **Conflict aging metric** - Track how long SEO conflicts remain unresolved in Alert Center

### P2 - Medium Priority  
1. **Deep-link Drawer Auto-Open** - Auto-open optimization detail drawer when URL has `?optimization_id=...`
2. Correlate optimization timeline with ranking history


---

### Email Alerts for Domain Monitoring (Feb 10, 2026) - COMPLETE
**Feature:** Email notifications as redundancy layer for HIGH/CRITICAL domain alerts.

**Implementation Summary:**

**1. Backend - Email Alert Service (`/app/backend/services/email_alert_service.py`):**
- Uses Resend API for transactional email delivery
- Static HTML templates (no AI-generated content)
- Severity-aware filtering (HIGH/CRITICAL only)
- Recipient logic: Global admin emails + per-network managers

**2. API Endpoints:**
- `GET /api/v3/settings/email-alerts` - Retrieve email alert configuration
- `PUT /api/v3/settings/email-alerts` - Update settings (enabled, severity_threshold, emails)
- `POST /api/v3/settings/email-alerts/test` - Send test email

**3. Frontend - Settings Page Email Alerts Tab:**
- Enable/disable toggle
- Resend API key configuration
- Sender email (optional, verified domain required)
- Severity threshold dropdown (HIGH / CRITICAL only)
- Include Network Managers toggle
- Global Admin Emails management (add/remove)
- Test email functionality

**4. Integration with Monitoring Service:**
- Expiration alerts (≤7 days) trigger email
- DOWN alerts (CRITICAL) trigger email
- Soft-blocked alerts (HIGH) trigger email
- Email includes full SEO context when applicable

**Email Alert Recipients:**
- **Global Admins:** Receive ALL alerts regardless of network
- **Network Managers:** Receive alerts for domains in their networks (if enabled)

**Severity Mapping:**
| Alert Type | Severity | Email Sent? (threshold=HIGH) |
|------------|----------|------------------------------|
| Domain DOWN | CRITICAL | Yes |
| Domain Expired/≤3 days | CRITICAL | Yes |
| Soft Blocked | HIGH | Yes |
| Expiring 4-7 days | HIGH | Yes |
| Expiring 8-30 days | MEDIUM | No |

**Tests:** 100% pass rate (15/15 backend, all frontend UI verified) ✅



---

### Weekly Digest Email (Feb 10, 2026) - COMPLETE
**Feature:** Scheduled weekly summary email for management visibility into domain health.

**Implementation Summary:**

**1. Backend - Weekly Digest Service (`/app/backend/services/weekly_digest_service.py`):**
- Collects expiring domains grouped by urgency: Critical (≤7d), High (8-14d), Medium (15-30d)
- Collects currently down domains with SEO context
- Collects soft-blocked domains with block type
- Generates professional HTML email with executive summary

**2. Scheduler Integration (`reminder_scheduler.py`):**
- Added CronTrigger-based job for weekly digest
- Configurable day of week and hour
- Auto-updates schedule from database settings

**3. API Endpoints:**
- `GET /api/v3/settings/weekly-digest` - Get digest settings
- `PUT /api/v3/settings/weekly-digest` - Update settings (day, hour, threshold, includes)
- `GET /api/v3/settings/weekly-digest/preview` - Preview digest data without sending
- `POST /api/v3/settings/weekly-digest/send` - Manually trigger digest send

**4. Frontend - Settings Page Weekly Digest Card:**
- Enable/disable toggle
- Day of week dropdown (Monday-Sunday)
- Hour dropdown (0-23)
- Expiring threshold dropdown (7, 14, 30, 60, 90 days)
- Include toggles: Expiring domains, Down domains, Soft-blocked
- Preview button with inline preview panel
- Send Now button (requires Resend API key)

**Digest Email Content:**
| Section | Content |
|---------|---------|
| Executive Summary | Total issues, Critical expiring, Down, Soft blocked counts |
| Expiring Domains | Grouped by CRITICAL (≤7d), HIGH (8-14d), MEDIUM (15-30d) |
| Down Domains | Domain, brand, status, SEO impact, HTTP code |
| Soft Blocked | Domain, brand, block type, SEO impact |
| Health Status | All Clear ✅, Minor Issues 🔵, Warning 🟡, Needs Attention 🔴 |

**Recipients:** Global admin emails only (from email_alerts settings)

**Tests:** 100% pass rate (17/17 backend, all frontend UI verified) ✅

**Note:** Requires Resend API key from resend.com to actually send emails. Get key at: https://resend.com/api-keys



---

### Bug Fixes and Role-Based Access Control (Feb 10, 2026) - COMPLETE

**1. Fixed UserRole Enum:**
- Added `MANAGER = "manager"` to UserRole enum in server.py
- Manager login was previously failing with Pydantic validation error

**2. Fixed Dashboard Stats Brand Filtering:**
- Updated `/api/reports/dashboard-stats` to use V3 collections (`asset_domains`, `seo_networks`)
- Applied `brand_scope_ids` filtering for non-super-admin users
- Manager now sees only their assigned brand's data

**3. Domain Save Verification:**
- Tested domain creation via UI - working correctly
- Domain form validates required fields (domain_name, brand_id)

**Role Access Summary:**

| Feature | Super Admin | Manager | Viewer |
|---------|-------------|---------|--------|
| Dashboard Stats | All data | Brand-scoped | Brand-scoped |
| SEO Networks | All 5 | 3 (brand filtered) | Brand-scoped |
| Asset Domains | All 32 | 11 (brand filtered) | Brand-scoped |
| Settings | Full access | Limited | No access |
| Email Alerts | Full access | No access | No access |

**Tests:** Domain save working, manager role filtering working ✅

---

### P0 Manager Role SEO Network Operations Fix (Feb 10, 2026) - COMPLETE

**Issue:** Manager role could not create/edit SEO Network nodes. The issue was reported as "In the SEO network project menu, there is still an error or it failed to update".

**Investigation & Resolution:**

1. **Backend API Testing (via curl):**
   - ✅ `GET /api/v3/networks/{network_id}/available-domains` - Returns correct list of brand-scoped domains
   - ✅ `GET /api/v3/networks/{network_id}/available-targets` - Returns correct list of target nodes
   - ✅ `POST /api/v3/structure` - Node creation works for manager role
   - ✅ `PUT /api/v3/structure/{entry_id}` - Node update works, returns updated entry

2. **Frontend UI Testing:**
   - ✅ Manager login works (manager@test.com / manager123)
   - ✅ SEO Networks list shows brand-scoped networks (3 networks for Panen138)
   - ✅ Network detail page loads correctly with stats
   - ✅ "Add Node" button visible (canEdit permission working)
   - ✅ Add Node dialog opens with domain dropdown populated
   - ✅ Domain selection, target node selection, change note all functional
   - ✅ Node successfully added via UI (verified with toast notification and stats update)
   - ✅ Domain List tab shows nodes with Edit/Delete action dropdowns

3. **Test Credentials Updated:**
   - Manager: `manager@test.com` / `manager123` (Panen138 brand)
   - Viewer: `viewer@test.com` / `viewer123` (Panen138 brand)
   - Super Admin: `admin@test.com` / `admin123` (all brands)

**Verification Summary:**
| Feature | Manager | Viewer |
|---------|---------|--------|
| View SEO Networks | ✅ Brand-scoped | ✅ Brand-scoped |
| Add Node | ✅ Working | ❌ Button hidden |
| Edit Node | ✅ Dropdown visible | ❌ Dropdown hidden |
| Delete Node | ✅ Dropdown visible | ❌ Dropdown hidden |
| Add Optimization | ✅ Working | ❌ 403 Forbidden |
| View Change History | ✅ Working | ✅ Working |

**Tests:** 100% pass rate (14/14 backend, 15/15 frontend UI checks) ✅

---

### P0 STRICT Permission Refactor (Feb 10, 2026) - COMPLETE

**Requirement:** Only Super Admin OR users explicitly listed in `network.manager_ids` can create/edit/delete SEO structure nodes. ALL other users must be VIEW-ONLY.

**Key Changes:**

1. **Backend Permission Enforcement:**
   - Added `require_manager_permission()` check to ALL structure endpoints:
     - `POST /api/v3/structure` (create node) - Line 1700
     - `PUT /api/v3/structure/{entry_id}` (update node) - Line 1861
     - `DELETE /api/v3/structure/{entry_id}` (delete node) - Line 4912
   - Non-managers receive: `403 Forbidden: "You are not assigned as a manager for this SEO Network. Only managers can perform this action."`

2. **Frontend Permission Check:**
   - `canEdit` in `GroupDetailPage.jsx` now checks:
     ```javascript
     const canEdit = (role === 'super_admin' || role === 'admin') || managerIds.includes(userId);
     ```
   - **NOT** based on user role - based on `network.manager_ids` membership

3. **API Model Fix (Critical):**
   - Added `manager_ids: Optional[List[str]] = []` to `SeoNetworkResponse` model in `models_v3.py`
   - Without this, frontend couldn't get `manager_ids` to check permissions

4. **Telegram Tagging Rules:**
   - **SEO Notifications** (change, optimization, node update): Tag Global SEO Leader (`seo_leader_telegram_username`)
   - **Complaint Notifications**: Tag ONLY Network Manager(s) - NOT global users, NOT viewers

5. **New Settings Field:**
   - Added `seo_leader_telegram_username` to Settings → SEO Notifications
   - Description: "SEO Leader akan di-tag pada semua notifikasi SEO. Untuk complaint, hanya Network Manager yang di-tag."

**Test Credentials:**
- Super Admin: `admin@test.com` / `admin123` (can edit ANY network)
- Network Manager: `manager@test.com` / `manager123` (in `manager_ids` for Test Network V5)
- Viewer (Not Manager): `notmanager@test.com` / `notmanager123` (gets 403 on all write ops)

**Tests:** 100% pass rate (10/10 backend, 9/9 frontend UI checks) ✅

---

3. Automatic optimization impact score calculation

  - Node counts per tier, collapse/expand functionality
  - Grouped/Flat view toggle
- ✅ **Filterable SEO Change History Timeline** (Feb 9, 2026)
  - Filters: User, Action type, Node, Date range
  - Human-readable diffs (Role, Status, Target as domain names not IDs)
  - "View Node in Graph" button for highlighting
- ✅ **SEO Change Notifications via Telegram** (Feb 9, 2026)
  - Dedicated Telegram channel for SEO changes (separate from monitoring)
  - Full Bahasa Indonesia message format with detailed structure snapshot
  - Settings UI at Settings → SEO Notifications tab
  - **ATOMIC SAVE + NOTIFICATION**: Change note validation (min 10 chars) blocks save if invalid
  - Telegram notification tracked with `notified_at` and `notification_status` fields
  - Frontend shows warning: "⚠️ Catatan ini wajib dan akan dikirim ke tim SEO via Telegram"
  - Save button disabled until change_note is valid (10+ characters)
  - Rate limiting (1 msg per network per minute)
  - Fallback to main Telegram if SEO channel not configured
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
1. ✅ **P0: Access Summary Panel** - COMPLETE (Feb 10, 2026)
   - Network cards show managers, complaints, last activity
   - Network detail header shows full access summary
2. ✅ **P1: Manual Project Complaint UI** - COMPLETE (Feb 10, 2026)
   - Created "Complaints" tab with Project-Level and Optimization sub-tabs
   - Super Admin can create project-level complaints with reason, priority, category
   - Users can respond to complaints (updates status to under_review)
   - Super Admin can resolve complaints with resolution note
   - Telegram notification sent on complaint creation
3. ✅ **SEO Telegram Notifications (Phase 1)** - COMPLETE (Feb 10, 2026)
   - Forum topic routing for different notification types (SEO_CHANGE, SEO_OPTIMIZATION, SEO_COMPLAINT, SEO_REMINDER)
   - Settings UI for topic IDs configuration at /settings > SEO Notifications
   - Global reminder interval (default 2 days) + per-network override
   - Manual reminder check via POST /api/v3/settings/reminder-config/run
   - DO NOT send domain monitoring alerts (out of scope)
4. ✅ **Domain Monitoring Alerts (Phase 2)** - COMPLETE (Feb 10, 2026)
   - SEPARATE Telegram channel from SEO notifications (NO fallback)
   - Settings UI at /settings > Domain Monitoring tab
   - SEO-aware context enrichment for domain alerts:
     - Full upstream chain traversal (BFS with loop detection) to Money Site
     - Downstream impact calculation (direct children)
     - Impact score (LOW/MEDIUM/HIGH/CRITICAL)
   - Soft-block detection: Cloudflare JS challenge, captcha, geo-block
   - Alert types: Domain Expiration (30/14/7/daily), Domain Availability (DOWN/SOFT_BLOCKED/RECOVERY)
   - All timestamps in GMT+7 (Asia/Jakarta)
5. ✅ **P1: Reminder System Override UI** - COMPLETE (Feb 10, 2026)
   - New "Settings" tab in GroupDetailPage (after Managers tab)
   - Per-network reminder interval override (1-30 days)
   - Use Global Default toggle
   - Save and Reset to Global buttons
6. ✅ **P1: Conflict Detection UI** - COMPLETE (Feb 10, 2026)
   - "SEO Conflicts" tab in Alert Center
   - Stats: Total, Critical, High Priority with refresh button
   - Conflict cards with severity badges and affected nodes
   - Quick jump to network via View Network button
7. ✅ **P1: Network Creation Telegram Notification** - COMPLETE (Feb 10, 2026)
   - Notification sent immediately when new SEO network created
   - Sent to seo_change_topic_id
   - Includes: Network name, Brand, Creator, Main node, Timestamp
8. **P1: Root vs. Path Main Node Visualization** - Solid vs dashed border in D3 graph
9. **P1: Milestone Tag on Change Notes** - Optional milestone field
10. Email notification integration (Resend/SendGrid)
11. Scheduled conflict alerts (cron)
12. Domain health check improvements
13. Alert history and analytics
14. **BACKLOG: Compare Changes** - Advanced diff viewer (parked)

### P0 SEO Telegram Notification - Full Authority Chains (Feb 9, 2026) - COMPLETE
**Issue:** Telegram notifications showed ObjectIDs instead of human-readable domain names, and didn't display complete authority chains.

**Fixed Implementation:**
- ✅ `seo_telegram_service.py` - Complete rewrite of notification formatting
- ✅ **Full Authority Chains:** Structure snapshot now shows complete paths like:
  - `tier1-site2.com [Canonical] → tier1-site1.com [301 Redirect] → moneysite.com [Primary]`
- ✅ **Human-Readable Labels:** All ObjectIDs replaced with domain names + status
  - Before: `target_entry_id: 210a8a26-a296-42bc-b1c0-afeaf6b43299`
  - After: `Target: tier1-site1.com [301 Redirect]`
- ✅ **Status Labels:** Clear status for each node:
  - `[Primary]` for main nodes
  - `[Canonical]`, `[301 Redirect]`, `[302 Redirect]`, `[Restore]` for supporting nodes
- ✅ **Tier Grouping:** Structure organized by tier (LP/Money Site, Tier 1, Tier 2, etc.)
- ✅ **Before/After Details:** Shows target changes with full domain labels

**Notification Format (Bahasa Indonesia):**
```
👤 PEMBARUAN OPTIMASI BAGAN SEO
{user} telah melakukan perubahan pada network '{network}' untuk brand '{brand}'

📌 RINGKASAN AKSI
• Aksi: {action}
• Dilakukan Oleh: {user}
• Waktu: {timestamp}

📝 ALASAN PERUBAHAN
"{change_note}"

🔄 Detail Perubahan:
• Node: {domain}{path}
• Target Sebelumnya: domain.com [Status]
• Target Baru: domain.com [Status]

🧭 STRUKTUR SEO TERKINI
LP / Money Site:
  • moneysite.com [Primary]
Tier 1:
  • tier1.com [301 Redirect] → moneysite.com [Primary]
Tier 2:
  • tier2.com [Canonical] → tier1.com [301 Redirect] → moneysite.com [Primary]
```

**Tests:** Verified with live Telegram notification - all chains displayed correctly

### Server-Side Pagination for Asset Domains (Feb 9, 2026) - COMPLETE

**Implementation:**
- ✅ Backend API updated: `GET /api/v3/asset-domains` with query params:
  - `page` (default: 1)
  - `limit` (default: 25, max: 100)
  - `search`, `brand_id`, `status`, `network_id` filters
- ✅ Paginated response format: `{ data: [...], meta: { page, limit, total, total_pages } }`
- ✅ Database indexes created on startup for optimal query performance:
  - `domain_name`, `brand_id`, `status`, `created_at`
  - Compound indexes for common filter combinations
- ✅ Frontend `DomainsPage.jsx` updated with:
  - Server-side filtering (no client-side load-all)
  - Pagination controls (Prev/Next, Page indicator)
  - Page size selector (25/50/100)
  - "Showing X of Y domains" counter
  - Loading skeleton while fetching
  - Debounced search (400ms)
  - Filters preserved across pages

**Key Files:**
- `backend/models_v3.py` - Added `PaginationMeta`, `PaginatedResponse` models
- `backend/routers/v3_router.py` - Updated `get_asset_domains` endpoint
- `backend/server.py` - Added `create_database_indexes()` function
- `frontend/src/pages/DomainsPage.jsx` - Full server-side pagination UI

**Tests:** Verified with API curl tests and browser screenshots ✅

### User Deactivation (Soft Disable) Feature (Feb 9, 2026) - COMPLETE

**Implementation:**
- ✅ **Data Model:** Extended `UserStatus` enum with `inactive` and `suspended` values
- ✅ **Auth Control:** Inactive/suspended users blocked at login AND on every API request
- ✅ **API Endpoints:**
  - `PATCH /api/users/{id}/deactivate` - Deactivate user (Super Admin only)
  - `PATCH /api/users/{id}/activate` - Reactivate user (Super Admin only)
- ✅ **Safety Rules:**
  - Cannot deactivate yourself
  - Cannot deactivate last Super Admin
- ✅ **Activity Logging:** All status changes logged with before/after values
- ✅ **Frontend UI:**
  - Actions dropdown menu with Edit, Deactivate, Delete options
  - Status badges for `active`, `inactive`, `suspended`
  - Confirmation dialogs with clear messaging

**Key Files:**
- `backend/server.py` - Updated `UserStatus`, `get_current_user`, added activate/deactivate endpoints
- `frontend/src/pages/UsersPage.jsx` - Dropdown menu, dialogs, handlers

**Tests:** Verified with API curl tests and browser screenshots ✅

### App Settings & Monitoring Timezone (Feb 9, 2026) - COMPLETE

**1. App Branding Settings:**
- ✅ `GET/PUT /api/settings/branding` - Site title, description, logo URL
- ✅ `POST /api/settings/branding/upload-logo` - Logo upload (PNG, JPEG, SVG, WebP, max 2MB)
- ✅ Frontend Settings page with Branding tab

**2. Monitoring Timezone Standardization:**
- ✅ `GET/PUT /api/settings/timezone` - Default timezone configuration
- ✅ Centralized timezone helper (`/app/backend/services/timezone_helper.py`)
- ✅ Default: GMT+7 (Asia/Jakarta)
- ✅ All monitoring Telegram alerts use configured timezone
- ✅ Format: `2026-02-09 23:02 GMT+7 (Asia/Jakarta)`
- ✅ Internal storage remains UTC (display-level conversion only)

**Updated Services:**
- `monitoring_service.py` - Down alerts, recovery alerts, expiration alerts
- `server.py` - Test Telegram message

**Key Files:**
- `backend/services/timezone_helper.py` - Centralized timezone conversion
- `backend/server.py` - Branding & timezone API endpoints
- `frontend/src/pages/SettingsPage.jsx` - New Branding & Timezone tabs

**Tests:** Verified with API curl tests and browser screenshots ✅

### SEO Optimizations Module (Feb 9, 2026) - COMPLETE

**Feature Overview:**
- New "Optimizations" tab in SEO Network detail page
- Track SEO activities that do NOT change the network structure (graph)
- Telegram notifications on CREATE and status change (COMPLETED/REVERTED)
- Messages in Bahasa Indonesia with GMT+7 timezone

**Data Model:** `seo_optimizations` collection
- Fields: `network_id`, `brand_id`, `created_by`, `activity_type`, `title`, `description`, `affected_scope`, `affected_targets`, `keywords`, `report_urls`, `expected_impact`, `status`, `telegram_notified_at`

**Activity Types:**
- `backlink`, `onpage`, `content`, `technical`, `schema`, `internal-link`, `experiment`, `other`

**API Endpoints:**
- `GET /api/v3/networks/{network_id}/optimizations` - Paginated list with filters
- `POST /api/v3/networks/{network_id}/optimizations` - Create (triggers notification)
- `PUT /api/v3/optimizations/{id}` - Update (triggers notification on status change to completed/reverted)
- `DELETE /api/v3/optimizations/{id}` - Delete

**Key Files:**
- `backend/models_v3.py` - Optimization models & enums
- `backend/routers/v3_router.py` - API endpoints
- `backend/services/seo_optimization_telegram_service.py` - Telegram notifications
- `frontend/src/components/OptimizationsTab.jsx` - UI component

**Tests:** Verified with API curl tests and browser screenshots ✅

## Test Credentials
- **Super Admin**: `superadmin@seonoc.com` / `SuperAdmin123!`
- **Alt Super Admin**: `admin@test.com` / `admin123`
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

### SEO Optimizations PRD Addendum (Feb 9, 2026) - COMPLETE

**Implemented Enhancements:**

**1. Optimization Deletion Rule (CRITICAL GOVERNANCE):**
- ✅ Only Super Admin can delete optimization records
- ✅ Non-super-admin receives 403 error with clear message
- ✅ Delete button hidden in UI for non-super-admins

**2. User Telegram Settings:**
- ✅ `telegram_username`, `telegram_user_id`, `telegram_linked_at` fields
- ✅ `GET/PUT /api/users/{id}/telegram` endpoints
- ✅ Users can update their own, Super Admin can update any

**3. Optimization Complaints:**
- ✅ `POST /api/v3/optimizations/{id}/complaints` - Create complaint (Super Admin)
- ✅ `GET /api/v3/optimizations/{id}/complaints` - List complaints
- ✅ Priority levels: low, medium, high
- ✅ Telegram notification with user tagging (@telegram_username)
- ✅ Complaint count indicator badge on optimization cards

**4. Network Access Control:**
- ✅ `visibility_mode`: restricted, brand_based, public
- ✅ `allowed_user_ids` for restricted access
- ✅ `GET/PUT /api/v3/networks/{id}/access-control` endpoints

**Telegram Complaint Format:**
```
🚨 SEO OPTIMIZATION COMPLAINT

{Super Admin} telah mengajukan komplain
pada SEO Network '{network}' untuk brand '{brand}'.

👥 Tagged Users:
  • @telegram_username
  • user@email.com (no Telegram)

📌 Optimization:
  • Judul: ...
  • Jenis: Backlink Campaign
  • Status: Selesai

🔴 Prioritas: Tinggi

📝 Alasan Komplain:
"..."

⚠️ Action Required:
Please review and respond to this complaint.
```

**Key Files:**
- `backend/routers/v3_router.py` - Complaint & access control endpoints
- `backend/server.py` - User Telegram settings endpoints
- `backend/services/seo_optimization_telegram_service.py` - Complaint notifications
- `frontend/src/components/OptimizationsTab.jsx` - Complaint dialog, delete restriction

**Tests:** Verified with API curl tests and browser screenshots ✅




### SEO Team Evaluation Dashboard (Feb 11, 2026) - COMPLETE

**Feature Overview:**
Team Evaluation Dashboard providing performance metrics and scoring for the SEO optimization team.

**1. Team Evaluation Dashboard (`/reports/team-evaluation`):**
- ✅ Summary stat cards: Total Optimizations, Completed, Total Complaints, Reverted
- ✅ Top Contributors table with scoring (0-5 scale)
- ✅ Score formula: base 5.0 - revert_penalty - complaint_penalty
- ✅ Status labels: Excellent (4.5+), Good (3.5+), Average (2.5+), Needs Improvement (<2.5)
- ✅ Status Distribution pie chart (Completed, In Progress, Planned, Reverted)
- ✅ Activity Types bar chart (Backlink, On-Page, etc.)
- ✅ Most Complained Users alert section
- ✅ Date range filter (7/30/90/365 days)
- ✅ Brand filter dropdown

**2. Mandatory Reason Note (`reason_note`) for Optimizations:**
- ✅ Minimum 20 characters required for new optimizations
- ✅ Character count indicator with color feedback (amber → green when valid)
- ✅ Warning text: "Catatan ini wajib dan akan dikirim ke tim SEO via Telegram"
- ✅ Create button disabled until validation passes
- ✅ reason_note displayed on optimization cards with "Alasan:" prefix

**3. Activity Types API (Master Data):**
- ✅ `GET /api/v3/optimization-activity-types` - List all types
- ✅ `POST /api/v3/optimization-activity-types` - Create new type (Super Admin)
- ✅ `DELETE /api/v3/optimization-activity-types/{id}` - Delete type (Super Admin)
- ✅ Default types: Backlink Campaign, On-Page Optimization, Technical SEO, Content Update, Other

**4. Team Evaluation Summary API:**
- ✅ `GET /api/v3/team-evaluation/summary` - Aggregated metrics
- ✅ Response includes: period_start, period_end, total_optimizations, by_status, by_activity_type, by_observed_impact, total_complaints, top_contributors, most_complained_users

**5. Export to CSV:**
- ✅ `GET /api/v3/team-evaluation/export` - Download team evaluation data as CSV
- ✅ Export button in Team Evaluation Dashboard header
- ✅ CSV includes: User Name, Email, Total Optimizations, Completed, Reverted, Complaints, Positive/Negative Impact, Score, Status, Penalties
- ✅ Filename includes date range: `seo_team_evaluation_{start}_to_{end}.csv`

**Key Files:**
- `frontend/src/pages/TeamEvaluationPage.jsx` - Dashboard UI with recharts
- `frontend/src/components/OptimizationsTab.jsx` - Updated form with reason_note
- `frontend/src/lib/api.js` - teamEvaluationAPI, activityTypesAPI
- `backend/routers/v3_router.py` - Team evaluation & activity types endpoints

**Tests:** 100% pass rate (12/12 backend, 100% frontend) ✅

### Optimization View + Complaint Flow (Feb 11, 2026) - COMPLETE

**Feature Overview:**
Full optimization detail view with complaint thread, team response system, and controlled closure workflow.

**1. Optimization Detail Drawer:**
- ✅ View button (Eye icon) on optimization cards
- ✅ Slide-out drawer with all sections:
  - Summary (Activity Type, Status, Created By, Dates)
  - Reason for Optimization (highlighted amber section)
  - Scope & Targets (domains, keywords, expected impact)
  - Reports & Timeline (clickable URLs with dates)
  - Complaint Thread (chronological, expandable)
  - Team Responses (history with add form)
  - Final Closure (Super Admin only)
- ✅ Copy Link button for deep-linking
- ✅ Full View button for detailed audit view
- ✅ URL updates with `optimization_id` param

**2. Complaint Thread System:**
- ✅ Chronological display of all complaints
- ✅ Complaint numbering (#1, #2, etc.)
- ✅ Active complaint highlighted
- ✅ Status badges: complained (red), under_review (amber), resolved (green)
- ✅ Collapsible older complaints
- ✅ Time-to-resolution metric calculated

**3. Team Response System:**
- ✅ `POST /api/v3/optimizations/{id}/responses` endpoint
- ✅ Validation: min 20 chars, max 2000 chars
- ✅ Response form visible to Admin/Super Admin
- ✅ Auto-changes status from `complained` to `under_review`
- ✅ Telegram notification on response

**4. Complaint Resolution (Super Admin Only):**
- ✅ `PATCH /api/v3/optimizations/{id}/complaints/{complaint_id}/resolve`
- ✅ Resolution note required (min 10 chars)
- ✅ Option to mark optimization as completed
- ✅ Time-to-resolution recorded
- ✅ Telegram notification on resolution

**5. Final Closure (Super Admin Only):**
- ✅ `PATCH /api/v3/optimizations/{id}/close`
- ✅ Blocked if unresolved complaints exist
- ✅ Warning displayed: "⚠ Blocked by Complaint – resolve before closing"
- ✅ Final note optional
- ✅ Telegram notification on closure

**6. Status & Blocking Rules:**
- ✅ Status badges on optimization cards (🟢 Completed, 🔴 Complained, 🟡 Under Review)
- ✅ Cannot mark `completed` if unresolved complaint exists
- ✅ Proper validation enforced at API level

**Key Files:**
- `frontend/src/components/OptimizationDetailDrawer.jsx` - Detail drawer component
- `frontend/src/components/OptimizationsTab.jsx` - Updated with View button
- `backend/routers/v3_router.py` - New endpoints: /detail, /responses, /resolve, /close
- `backend/models_v3.py` - New models: TeamResponseCreate, ComplaintResolveRequest, etc.

**Tests:** 82% backend (9/11), 95% frontend ✅

### P1 Features (Feb 11, 2026) - COMPLETE

**1. Full Page Optimization View (`/optimizations/{id}`):**
- ✅ Dedicated full-screen page for deep audits
- ✅ All sections from drawer in expanded layout
- ✅ Back button, Copy Link, Print button
- ✅ Two-column layout: Main content + Sidebar
- ✅ "Optimization Completed" success badge
- ✅ Print-friendly CSS (@media print)

**2. Activity Type Management UI (`/settings/activity-types`):**
- ✅ CRUD interface for Super Admin
- ✅ Table with Name, Description, Usage Count, Default status
- ✅ Add Activity Type dialog
- ✅ Delete with usage protection (cannot delete if in use)
- ✅ Default types are protected (cannot be deleted)
- ✅ Info card explaining functionality

**3. Project-Level User Visibility:**
- ✅ Backend: `check_network_visibility_access()` helper function
- ✅ Backend: Filter networks in GET /networks by visibility mode
- ✅ Frontend: `NetworkAccessSettings.jsx` component
- ✅ Settings tab in Network Detail page
- ✅ Visibility modes: brand_based, restricted, public
- ✅ User selection for restricted mode
- ✅ Save access settings API

**Key Files:**
- `frontend/src/pages/OptimizationDetailPage.jsx` - Full page view
- `frontend/src/pages/ActivityTypesPage.jsx` - Activity types CRUD
- `frontend/src/components/NetworkAccessSettings.jsx` - Access control UI
- `backend/routers/v3_router.py` - Access control filtering

**Tests:** All features manually verified ✅

### P2 Features (Feb 11, 2026) - COMPLETE

**1. Auto-switch to Optimizations Tab on Deep-link:**
- ✅ Added `useSearchParams` hook to GroupDetailPage
- ✅ Auto-switches to Optimizations tab when `?optimization_id=xxx` is in URL
- ✅ Seamless deep-linking experience

**2. Optimization Export to CSV:**
- ✅ `GET /api/v3/networks/{network_id}/optimizations/export` endpoint
- ✅ Export button in Optimizations header
- ✅ CSV includes: ID, Title, Type, Status, Complaints, Dates, Description, etc.
- ✅ Filename includes network name and date

**3. Telegram Account Linking:**
- ✅ Added `telegram_username` to User model
- ✅ `PATCH /api/users/me/telegram` for self-update
- ✅ Telegram Username field in User Edit dialog
- ✅ Used for @mentions in complaint notifications

**4. Weekly SEO Optimization Digest:**
- ✅ `SeoDigestService` for generating digests
- ✅ `POST /api/v3/optimizations/digest` - Send digest via Telegram
- ✅ `GET /api/v3/optimizations/digest/preview` - Preview without sending
- ✅ Aggregates: by status, activity type, user, network
- ✅ Top performers, complaint stats, resolution rates
- ✅ Formatted Telegram message in Bahasa Indonesia

**5. AI-generated Optimization Summaries:**
- ✅ `AiSummaryService` using GPT-4o via Emergent LLM key
- ✅ `GET /api/v3/optimizations/ai-summary` - Generate period summary
- ✅ `GET /api/v3/optimizations/{id}/ai-summary` - Single optimization summary
- ✅ Summaries in Bahasa Indonesia
- ✅ Includes: activity analysis, focus insights, recommendations

**Key Files:**
- `backend/services/seo_digest_service.py` - Weekly digest generation
- `backend/services/ai_summary_service.py` - AI summary service
- `frontend/src/pages/UsersPage.jsx` - Telegram username field
- `frontend/src/components/OptimizationsTab.jsx` - Export CSV button

**Tests:** All API endpoints verified via curl ✅

### SEO Network Access Control - User Search/Add Enhancement (Feb 9, 2026) - COMPLETE
**Bug Fix + Enhancement:** SEO Network Access Control – Allowed Users Search/Add Not Working

**Issues Fixed:**
1. ✅ "Failed to load access settings" error - Fixed double `/api` prefix in frontend API calls
2. ✅ User search always showing "No users found" - Implemented proper `/api/v3/users/search` endpoint
3. ✅ Duplicate function definitions in backend causing overwriting issues

**New Features Implemented:**

**1. User Search API (`GET /api/v3/users/search`):**
- ✅ Search by email OR name (case-insensitive partial match)
- ✅ Minimum 2 characters required
- ✅ Maximum 10 results returned for performance
- ✅ Excludes inactive/disabled users (unless super_admin)
- ✅ Brand scoping support via `network_id` parameter
- ✅ Returns: id, email, name, role, status

**2. Frontend Access Control UI:**
- ✅ Complete rewrite of `NetworkAccessSettings.jsx`
- ✅ Fixed API client to use correct `/api/v3` base URL
- ✅ Debounced search input (300ms)
- ✅ Dropdown with search results showing: avatar, name, email, role badge, "+" button
- ✅ Selected users list with: avatar, name, email, role badge, "X" remove button
- ✅ Warning message when no users selected in Restricted mode
- ✅ Info box explaining visibility modes
- ✅ Proper data-testids for all interactive elements

**3. Backend Access Enforcement:**
- ✅ `require_network_access()` - Raises 403 for unauthorized users
- ✅ Enforced on: `GET /networks/{id}`, `GET /networks/{id}/optimizations`, CSV export
- ✅ Network list endpoint filters out restricted networks from non-allowed users
- ✅ Super Admin always has access

**4. Acceptance Criteria Verified:**
- ✅ Typing user email/name shows user in suggestions
- ✅ Clicking suggestion adds user to Allowed Users list
- ✅ Saving persists allowed_user_ids in DB
- ✅ Reload page: settings still shown
- ✅ Restricted mode prevents unlisted users from accessing network (403)
- ✅ Super admin can always access

**Tests:** 100% pass rate (15/15 backend, 100% frontend) ✅

---

### SEO Network Access Transparency & Visibility Management (Feb 9, 2026) - COMPLETE
**Feature:** Full accountability system for SEO Network access with clear ownership and visibility.

**Phase 1: Access Summary & Visibility (COMPLETE)**
- ✅ Data model updated: `access_summary_cache`, `access_updated_at`, `access_updated_by` fields
- ✅ Network cards show access badges (🔒 Restricted · 3 users, 👥 Brand Based, 🌐 Public)
- ✅ Network detail header shows "Visible To:" section with click navigation to Access tab
- ✅ Settings tab renamed to "Access" tab with Shield icon
- ✅ "Last Updated" info showing timestamp and user who made changes
- ✅ Audit logging for all `NETWORK_ACCESS_CHANGED` events in `network_access_audit_logs` collection

**Phase 2: Telegram Auto-Tagging (COMPLETE)**
- ✅ When Super Admin creates complaint, auto-includes assigned users from network Access Summary
- ✅ Users with `telegram_username` are tagged with @mention
- ✅ Fallback to name/email for users without Telegram linked
- ✅ Complaint model stores `auto_assigned_from_network` flag

**Phase 3: Auto-Reminder System (COMPLETE)**
- ✅ Reminder service for "In Progress" optimizations (`/app/backend/services/optimization_reminder_service.py`)
- ✅ Global reminder config (`GET/PUT /api/v3/settings/reminder-config`)
- ✅ Per-network reminder override (`GET/PUT /api/v3/networks/{id}/reminder-config`)
- ✅ Reminder logs for accountability (`GET /api/v3/optimization-reminders`)
- ✅ `send_in_progress_reminder()` method in Telegram service
- ⏳ Scheduler integration pending (APScheduler or similar)

**Key Files:**
- `frontend/src/pages/GroupsPage.jsx` - Access badges on network cards
- `frontend/src/pages/GroupDetailPage.jsx` - Header visibility info, Access tab
- `frontend/src/components/NetworkAccessSettings.jsx` - Last Updated section
- `backend/routers/v3_router.py` - Reminder config endpoints, audit logging
- `backend/services/optimization_reminder_service.py` - Reminder service
- `backend/services/seo_optimization_telegram_service.py` - Telegram notifications

**Tests:** 100% pass rate (11/11 backend, 100% frontend) ✅

---

### SEO Network Managers - Project Ownership System (Feb 9, 2026) - COMPLETE
**Feature:** Redefine Access Control to SEO Network Managers for clear project ownership and accountability.

**Conceptual Change:**
- FROM: "Access Control" (access restriction)
- TO: "SEO Network Managers" (project ownership/responsibility)

**What was implemented:**

**1. Database Migration:**
- ✅ `allowed_user_ids` → `manager_ids`
- ✅ `access_summary_cache` → `manager_summary_cache`
- ✅ `access_updated_at/by` → `managers_updated_at/by`
- ✅ Legacy field backward compatibility

**2. Role Behavior:**
- ✅ **Super Admin:** Full access to everything, no need to be listed as manager
- ✅ **Managers:** Can create/update optimizations, respond to complaints, receive notifications
- ✅ **Non-Managers:** View only - see data but cannot execute

**3. API Changes:**
- ✅ `GET/PUT /networks/{id}/managers` - New primary endpoints
- ✅ `GET /networks/{id}/managers` returns `is_current_user_manager` flag
- ✅ Legacy `/access-control` endpoints redirect to `/managers`
- ✅ `require_manager_permission()` helper for execution checks

**4. Permission Enforcement:**
- ✅ `POST /networks/{id}/optimizations` - Managers only
- ✅ `PUT /optimizations/{id}` - Managers only  
- ✅ `POST /optimizations/{id}/responses` - Managers only
- ✅ 403 error: "You are not assigned as a manager for this SEO Network"

**5. UI Updates:**
- ✅ "Access Control" → "SEO Network Management"
- ✅ "Access" tab → "Managers" tab
- ✅ "Allowed Users" → "SEO Network Managers"
- ✅ "Visible To:" → "Managed By:" in header
- ✅ Non-managers see "View Only" status with disabled actions

**6. Visibility Mode (Separate from Managers):**
- ✅ **Brand Based:** All brand users can VIEW
- ✅ **Brand Based:** All brand users can VIEW (default)
- ✅ **Restricted:** Only managers and Super Admins can VIEW
- ❌ **Public (Super Admin):** REMOVED - December 2025
- ✅ Visibility ≠ Execution (execution controlled by manager_ids)

**Tests:** 100% pass rate (11/11 backend, 14/14 frontend) ✅

---

## Prioritized Backlog

### P0 - Critical
1. ✅ **Access Summary Panel** - COMPLETE (Feb 10, 2026)
   - Network cards show: managers count/names, open complaints badge, last optimization date
   - Network detail header shows: visibility mode, managers, open complaints count, last activity date
   - API endpoints return `open_complaints_count` and `last_optimization_at` fields
   - Backend queries `seo_optimizations` for complaints with status `complained` or `under_review`
   - Frontend conditionally renders badges only when data exists

2. ✅ **Notification Template System** - COMPLETE (Feb 10, 2026)
   - Global template management for Telegram & Email notifications
   - Settings UI: Settings → Templates tab (Super Admin only)
   - Features:
     - List all 11 notification event types
     - Edit template title, body, enabled toggle
     - Live preview with sample data
     - Variable validation against ALLOWED_VARIABLES
     - Reset to default functionality
   - API Endpoints:
     - GET `/api/v3/settings/notification-templates` - list all
     - GET `/api/v3/settings/notification-templates/variables` - allowed vars
     - GET `/api/v3/settings/notification-templates/{channel}/{event_type}` - get one
     - PUT `/api/v3/settings/notification-templates/{channel}/{event_type}` - update
     - POST `/api/v3/settings/notification-templates/{channel}/{event_type}/reset` - reset
     - POST `/api/v3/settings/notification-templates/{channel}/{event_type}/preview` - preview
     - POST `/api/v3/settings/notification-templates/validate` - validate
   - Template syntax: `{{variable}}` (Mustache-style)
   - Event types: seo_change, seo_network_created, seo_optimization, seo_optimization_status, seo_complaint, seo_project_complaint, seo_reminder, domain_expiration, domain_down, seo_node_deleted, test
   - Files: `notification_template_engine.py`, `NotificationTemplatesTab.jsx`
   - Tests: 100% pass (25/25 backend, 16/16 frontend)

### P1 - High Priority
1. ✅ **Scheduler Integration for Reminders** - COMPLETE (Feb 9, 2026)
   - APScheduler integrated with FastAPI
   - Runs every 24 hours to check for in_progress optimizations
   - APIs: `/scheduler/reminder-status`, `/scheduler/trigger-reminders`, `/scheduler/execution-logs`
   - Graceful shutdown implemented
2. ✅ **Complaint Timeline UI** - COMPLETE (Dec 11, 2025)
   - Visual timeline component (`ComplaintTimeline.jsx`) showing chronological history
   - Events: Complaint Created (red), Team Response (blue), Complaint Resolved (green)
   - Interactive expand/collapse for event details
   - Summary stats bar showing complaint/response/resolved counts
   - Average resolution time displayed
   - Integrated into OptimizationDetailDrawer.jsx
3. ✅ **Time-to-Resolution Metric** - Backend logic already implemented
4. ✅ **Visibility Mode Cleanup** - COMPLETE (Dec 11, 2025)
   - Removed "Public (Super Admin)" visibility option
   - Clarified: Visibility = VIEW access, Managers = EXECUTE access
   - Updated UI descriptions and backend validation

### P2 - Medium Priority
1. ✅ **Scheduler Dashboard UI** - COMPLETE (Feb 9, 2026)
   - Page at `/settings/scheduler` with full dashboard
   - Scheduler status, next run time, last execution results
   - Manual trigger button with confirmation
   - Global reminder settings (enable/disable, interval days)
   - Execution history with detailed stats
2. **Deep-link Drawer Auto-Open** - Auto-open optimization detail drawer when URL has `?optimization_id=...`
3. **Frontend UI for AI Summary** - Button to trigger AI summary generation and display result
3. **Reminder Settings UI** - Frontend page to configure global and per-network reminder intervals
4. **Scheduler Dashboard UI** - View scheduler status, execution logs, and manual trigger button
5. Correlate optimization timeline with ranking history
6. Automatic optimization impact score calculation
---

### Bug Fix: Manual Trigger for Optimization Reminders (Feb 10, 2026) - COMPLETE

**Issue:** Manual trigger for "Manage automatic optimization reminders" was not working. When clicking the trigger button in the Settings UI, no reminders were being sent.

**Root Cause Analysis:**
1. The `ReminderScheduler` was initialized with `telegram_service=seo_optimization_telegram_service`
2. However, `seo_optimization_telegram_service` was imported directly but never initialized - it was `None`
3. The `init_seo_optimization_telegram_service(db)` function was never called in `server.py`
4. As a result, the reminder service had no Telegram service to send notifications

**Fix Applied:**
Changed in `/app/backend/server.py`:
```python
# Before (broken):
from services.seo_optimization_telegram_service import (
    seo_optimization_telegram_service,
)
reminder_scheduler = init_reminder_scheduler(
    db, telegram_service=seo_optimization_telegram_service
)

# After (fixed):
from services.seo_optimization_telegram_service import (
    init_seo_optimization_telegram_service,
)
optimization_telegram_service = init_seo_optimization_telegram_service(db)
reminder_scheduler = init_reminder_scheduler(
    db, telegram_service=optimization_telegram_service
)
```

**Additional Fix:**
Fixed login endpoint to handle missing `created_at`/`updated_at` fields gracefully using `.get()` instead of direct key access.

**Test Results:**
- ✅ Manual trigger API: `POST /api/v3/scheduler/trigger-reminders`
- ✅ Found 1 optimization needing reminder (5+ days old)
- ✅ Telegram HTTP Request: 200 OK
- ✅ Notification sent successfully
- ✅ Reminder logged to database
- ✅ `reminders_sent: 1`

**Files Modified:**
- `/app/backend/server.py` - Fixed initialization of optimization Telegram service

---

### Audit & Metrics Features Implementation (Feb 10, 2026) - COMPLETE

**Features Implemented:**

1. **Audit Logging System** ✅
   - Backend service: `/app/backend/services/audit_log_service.py`
   - API endpoints: `GET /api/v3/audit-logs`, `GET /api/v3/audit-logs/stats`, `GET /api/v3/audit-logs/event-types`
   - Frontend page: `/app/frontend/src/pages/AuditLogsPage.jsx`
   - Features: Filters by event type, severity, success status; Stats cards; Detailed log table

2. **Domain Down Alerts with SEO Context** ✅
   - Already implemented in `/app/backend/services/monitoring_service.py`
   - Method: `_format_down_alert_seo_aware()`
   - Includes: Network, Role, Tier, Status, Authority Chain, Downstream Impact

3. **Reminder Effectiveness Metric** ✅
   - Backend service: `/app/backend/services/reminder_effectiveness_service.py`
   - API endpoints: `GET /api/v3/metrics/reminder-effectiveness`
   - Tracks: Total reminders sent, Response rates, Response times, Breakdown by type/action

4. **Conflict Aging Metric** ✅
   - Backend service: `/app/backend/services/conflict_aging_service.py`
   - API endpoints: `GET /api/v3/metrics/conflict-aging`, `GET /api/v3/metrics/conflict-resolution`
   - Tracks: Open complaints aging, Resolution times, Critical complaints (>7 days)

5. **Metrics Dashboard Page** ✅ (NEW)
   - Frontend page: `/app/frontend/src/pages/MetricsDashboardPage.jsx`
   - Features:
     - Quick stats cards (Response Rate, Avg Response Time, Open Conflicts, Avg Resolution)
     - Reminder Effectiveness panel with time period selector
     - Conflict Aging Analysis with age distribution chart
     - Resolution Metrics with time buckets
     - Audit Log Summary with link to full logs
   - Access: Super Admin, Manager roles
   - Route: `/metrics`
   - Navigation: Added to sidebar with BarChart3 icon

**Files Created/Modified:**
- Created: `/app/frontend/src/pages/MetricsDashboardPage.jsx`
- Modified: `/app/frontend/src/pages/AuditLogsPage.jsx` (enhanced with v3 API)
- Modified: `/app/frontend/src/lib/api.js` (added metricsAPI, enhanced auditAPI)
- Modified: `/app/frontend/src/App.js` (added metrics route)
- Modified: `/app/frontend/src/components/Layout.jsx` (added Metrics nav item)

---

### Handle Invalid Telegram topic_id Gracefully (Feb 10, 2026) - COMPLETE

**Issue:** Telegram notifications failed silently when an invalid `topic_id` (message_thread_id) was configured.

**Fix Applied:**
Updated `_send_telegram_message()` in both Telegram services to:

1. **Detect topic_id errors** - Check if Telegram API error contains "thread", "topic", or "message_thread_id"
2. **Log warning** - Inform admin about the invalid topic_id
3. **Automatic fallback** - Retry sending without topic_id to main chat
4. **Success logging** - Log that fallback was used

**Code Pattern:**
```python
if message_thread_id and ("thread" in error_text or "topic" in error_text):
    logger.warning(f"Invalid topic_id '{message_thread_id}' for {topic_type}. Retrying...")
    del payload["message_thread_id"]
    retry_response = await client.post(url, json=payload, timeout=30.0)
    if retry_response.status_code == 200:
        logger.info("SEO Telegram notification sent (fallback to main chat)")
        return True
```

**Files Modified:**
- `/app/backend/services/seo_telegram_service.py`
- `/app/backend/services/seo_optimization_telegram_service.py`

**Behavior:**
- If topic_id is valid → Message sent to specific topic ✅
- If topic_id is invalid → Warning logged, message sent to main chat ✅
- If both fail → Error logged, returns False ❌


---

### P0 SEO Conflict Reporting System Unified (Feb 10, 2026) - COMPLETE

**Issue:** SEO Conflict dashboard displayed 14 conflicts using legacy API (`/api/seo/conflicts`) reading from deprecated `domains` collection, while V3 API (`/api/v3/reports/conflicts`) using current `seo_structure_entries` collection showed zero conflicts. This caused inconsistent/misleading conflict data.

**Root Cause:** Frontend was calling legacy endpoint that queried outdated data collection.

**Fix Applied:**

**1. Frontend API Migration:**
- Updated `/app/frontend/src/lib/api.js`:
  - `conflictsAPI.detect()` now calls `/api/v3/reports/conflicts` instead of `/api/seo/conflicts`
  - Added optional `networkId` parameter for filtered queries

**2. Frontend Response Handling:**
- Updated `/app/frontend/src/pages/DashboardPage.jsx`:
  - Updated conflict card display to handle V3 response format
  - Supports both V3 fields (`conflict_type`, `description`, `node_a_label`) and legacy fallbacks

**3. Legacy Endpoint Deprecated:**
- Updated `/app/backend/server.py`:
  - Added clear deprecation notice to `/api/seo/conflicts` endpoint docstring
  - Legacy endpoint kept for backward compatibility but marked for future removal

**4. Enhanced Conflict Detection (V3):**
- Added new conflict types to `/app/backend/models_v3.py` ConflictType enum:
  - `REDIRECT_LOOP` - Redirect/canonical loop detected
  - `MULTIPLE_PARENTS_TO_MAIN` - Multiple non-supporting nodes pointing to Money Site
  - `INDEX_NOINDEX_MISMATCH` - Indexed node links to NOINDEX target in higher tier
  - `ORPHAN_NODE` - Node not connected to main hierarchy
  - `NOINDEX_HIGH_TIER` - NOINDEX node in high tier

**5. V3 Conflict Detection Logic (`/app/backend/routers/v3_router.py`):**
- TYPE A: Keyword Cannibalization (same keyword, different paths)
- TYPE B: Competing Targets (different paths targeting different nodes)
- TYPE C: Canonical Mismatch (path redirects to indexed path)
- TYPE D: Tier Inversion (higher tier supports lower tier) - CRITICAL severity
- TYPE E: Redirect/Canonical Loops (cycle detection with BFS)
- TYPE F: Multiple Parents to Money Site (non-supporting nodes pointing to main)
- TYPE G: Index/Noindex Mismatch (indexed node → noindex target)
- Legacy: NOINDEX in high tier, Orphan nodes

**API Response Structure:**
```json
{
  "conflicts": [...],
  "total": 0,
  "by_type": {},
  "by_severity": {
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0
  }
}
```

**Conflict Object Fields:**
- `conflict_type`, `severity`, `network_id`, `network_name`, `domain_name`
- `node_a_id`, `node_a_path`, `node_a_label`
- `node_b_id` (optional), `node_b_path` (optional), `node_b_label` (optional)
- `description`, `suggestion`, `detected_at`

**Tests:** 100% pass rate (12/12 backend, 8/8 frontend) verified by testing_agent_v3_fork

**Files Modified:**
- `/app/frontend/src/lib/api.js` - Line 113-117
- `/app/frontend/src/pages/DashboardPage.jsx` - Lines 551-577
- `/app/backend/server.py` - Lines 2513-2589
- `/app/backend/models_v3.py` - ConflictType enum
- `/app/backend/routers/v3_router.py` - Lines 5473-5900

---





---

### Menu-Level Access Control System (Feb 10, 2026) - COMPLETE

**Feature Request:** Implement a menu-level access control system where Super Admin can explicitly define which menus are accessible by Admin and User roles.

**Implementation:**

**1. Role Behavior:**
- **Super Admin:** Full access to ALL 17 menus. Cannot be restricted.
- **Admin:** All menus enabled by default. Can be restricted by Super Admin.
- **User/Viewer:** NO menus enabled by default. Must be explicitly assigned by Super Admin.

**2. Master Menu Registry (17 menus):**
- Dashboard, Asset Domains, SEO Networks, Alert Center, Reports
- Team Evaluation, Brands, Categories, Registrars, Users
- Audit Logs, Metrics, V3 Activity, Activity Types, Scheduler
- Monitoring, Settings

**3. Backend API Endpoints:**
- `GET /api/v3/menu-registry` - Get all available menus
- `GET /api/v3/my-menu-permissions` - Get current user's permissions
- `GET /api/v3/admin/menu-permissions/{user_id}` - Get user permissions (Super Admin only)
- `PUT /api/v3/admin/menu-permissions/{user_id}` - Update user permissions (Super Admin only)
- `DELETE /api/v3/admin/menu-permissions/{user_id}` - Reset to defaults (Super Admin only)

**4. Frontend Implementation:**
- `MenuPermissionsProvider` context for global permission state
- Sidebar filtering via `canAccessMenu()` in Layout.jsx
- Route guards via `MenuProtectedRoute` in App.js
- Access Denied page for unauthorized access
- Menu Access dialog in Users page with:
  - Checkbox toggles for each menu
  - Select All / Clear All buttons
  - Reset to Default button
  - Save Changes button

**5. Security Features:**
- Super Admin permissions cannot be modified (API returns 400)
- Direct URL access blocked via MenuProtectedRoute
- API endpoints protected with role checks (403 for non-super-admin)
- Audit logging for permission changes

**Files Modified/Created:**
- `/app/backend/models_v3.py` - MASTER_MENU_REGISTRY, DEFAULT_ADMIN_MENUS, DEFAULT_USER_MENUS
- `/app/backend/routers/v3_router.py` - Menu permission endpoints (lines 589-810)
- `/app/frontend/src/lib/api.js` - menuPermissionsAPI
- `/app/frontend/src/lib/menuPermissions.jsx` - MenuPermissionsProvider (NEW)
- `/app/frontend/src/components/Layout.jsx` - Sidebar filtering
- `/app/frontend/src/App.js` - MenuProtectedRoute, MenuPermissionsProvider
- `/app/frontend/src/pages/UsersPage.jsx` - Menu Access dialog
- `/app/frontend/src/pages/AccessDeniedPage.jsx` - Access Denied page (NEW)

**Tests:** 100% pass rate (12/12 backend, 14/14 frontend) - `/app/test_reports/iteration_42.json`

---


### Alerts Page - Enhanced Detailed View (Feb 10, 2026) - COMPLETE

**Issue:** User reported the "View All" button on the Conflict Resolution Dashboard was working but the destination (Alerts page) didn't show detailed enough information.

**Solution:** Enhanced the Alerts page (`/alerts`) to show comprehensive, detailed conflict data matching the Conflict Resolution Dashboard's level of detail.

**Changes Implemented:**

**1. New "Tracked Conflicts" Section:**
- Dedicated section showing all persisted conflicts from `stored_seo_conflicts` collection
- Detailed table with columns: Type, Severity, Status, Node, Network (clickable), Detected Date, Resolved Date, Action
- Status filtering tabs: All, Detected, In Progress, Resolved (with counts)
- "Create Task" button for detected conflicts without linked optimizations
- "View Task" button to navigate to linked optimization

**2. View Mode Toggle:**
- Added Table/Cards view toggle buttons
- Table view: Compact, scannable format for quick overview
- Cards view: Expanded cards with more detail (original format preserved)

**3. Active Conflicts Section:**
- Shows real-time detected conflicts (dynamic)
- Supports both table and card view modes
- Shows linked optimization status and action buttons

**4. Additional Features:**
- Clickable network links (navigate to network detail)
- Color-coded severity badges (Critical=red, High=amber, Medium=yellow, Low=blue)
- Color-coded status badges (Detected=amber, In Progress=blue, Resolved=green)
- Responsive table design with proper overflow handling

**Files Modified:**
- `/app/frontend/src/pages/AlertsPage.jsx` - Complete enhancement with tabs, table view, stored conflicts

**Tests:** Visual verification via screenshot - Alerts page now shows 6 tracked conflicts with full detail

---

### Conflict Resolution Dashboard - Production-Grade Overhaul (Feb 12, 2026) - COMPLETE

**Issue:** The dashboard provided inaccurate and misleading metrics, requiring a full production-grade overhaul.

**P0 Requirements (Critical Fixes) - ALL IMPLEMENTED:**

**1. Fix Recurring Conflict Logic with Fingerprints:**
- Created `generate_conflict_fingerprint()` function
- Fingerprint = hash(network_id + conflict_type + domain_id + normalized_path + tier + target_path)
- Accurately tracks when same structural conflict reappears after resolution
- Only ACTIVE, UNRESOLVED conflicts with recurrence > 0 shown in recurring list

**2. Fix Top Resolvers Data Integrity:**
- Excludes `null` and `system` users from leaderboard
- Only counts valid human users who resolved `conflict_resolution` type tasks
- Returns array of objects with `user_id`, `name`, `email`, `resolved_count`

**3. Fix Status Source of Truth:**
- `_derive_true_status()` derives conflict status from linked optimization
- Optimization `completed` → Conflict `resolved`
- Optimization `in_progress` → Conflict `under_review`
- Optimization `reverted` → Conflict `detected` (reactivated)

**4. Fix Average Resolution Time Calculation:**
- Uses `first_detected_at` → `optimization.completed_at`
- Falls back to `detected_at` → `resolved_at` if optimization data unavailable

**5. Data Migration Script:**
- `POST /api/v3/conflicts/migrate-approved` endpoint (Super Admin only)
- Backfills `fingerprint` for all conflicts
- Sets `first_detected_at` from `detected_at`
- Marks resolved/approved conflicts as `is_active = false`
- Resets `recurrence_count` for terminal status conflicts

**6. UX Improvement:**
- Info text explaining approved conflicts are auto-resolved and removed from recurring list

**P1 Requirements (Important Improvements) - ALL IMPLEMENTED:**

**1. False Resolution Rate Metric:**
- `false_resolution_rate_percent`: Conflicts that reappeared within 7 days
- `false_resolution_count`: Raw count of false resolutions

**2. Average Recurrence Interval:**
- `avg_recurrence_interval_days`: Average time between resolution and reappearance
- Shows "N/A" if no recurrences detected

**3. Resolution Time Breakdown:**
- `resolution_times_breakdown`: {under_1_hour, 1_to_24_hours, 1_to_7_days, over_7_days}
- Visual representation in dashboard with colored dots

**4. Recurring Conflict CTA:**
- `recurring_conflict_ids` array returned for frontend CTA list
- "Create Task" button shown for recurring conflicts without linked optimizations

**New Files Created:**
- `/app/backend/services/conflict_metrics_service.py` - Core metrics logic
- `/app/backend/migrations/conflict_fingerprint_migration.py` - Standalone migration script

**Files Modified:**
- `/app/backend/routers/v3_router.py` - Updated `GET /conflicts/metrics` endpoint, enhanced migration endpoint
- `/app/frontend/src/pages/ConflictDashboardPage.jsx` - Updated UI with all P0/P1 metrics

**API Changes:**
- `GET /api/v3/conflicts/metrics` now returns:
  - `resolution_rate_percent`, `avg_resolution_time_hours`
  - `resolution_times_breakdown` object
  - `recurring_conflicts` (count), `recurring_conflict_ids` (array)
  - `false_resolution_count`, `false_resolution_rate_percent`
  - `avg_recurrence_interval_days`
  - `top_resolvers` array with user details (not just user_id counts)
  - `by_severity`, `by_type` breakdown objects

**Tests:** 100% pass rate (15/15 backend, 100% frontend) - `/app/test_reports/iteration_48.json`

---

### Domain Lifecycle & Quarantine Management System (Feb 12, 2026) - REVISED & COMPLETE

**Feature:** Revised Domain Monitoring system with clear separation of Status (technical) vs Lifecycle (strategic)

**Core Concept:**
- **Status** = Technical condition (Active / Down / Expired)
- **Lifecycle** = Strategic decision (Active / Released / Quarantined / Archived)
- Only **Active** lifecycle domains are included in real-time monitoring
- All other lifecycles are excluded from ALL alerts and notifications

**Lifecycle Values:**
- `active` - Actively used in SEO (MONITORED)
- `released` - Intentionally retired/not renewed (NOT monitored)
- `quarantined` - Blocked due to issues (NOT monitored)
- `archived` - History only, no operational usage (NOT monitored)

**Validation Rules Implemented:**
1. **Invalid State Prevention**: Cannot set lifecycle to "Active" if domain is expired
2. **Auto-Suggestion**: System suggests marking expired domains as Released/Quarantined
3. **Quarantine Requirement**: Quarantine category required when setting lifecycle to Quarantined

**UI Warnings:**
- Warning banner (⚠️) shown when lifecycle contradicts status
- Examples: Active lifecycle + Expired status, Active lifecycle + DOWN status
- Tooltip on Lifecycle column explaining the concept

**Quarantine Categories:**
- Spam Murni
- DMCA  
- Manual Penalty
- Rollback / Restore
- Other (custom with required note)

**API Changes:**
- `GET /api/v3/lifecycle-info` - Returns lifecycle labels and tooltip
- `GET /api/v3/monitoring/coverage` - Updated to only count Active lifecycle as monitorable
- `POST /api/v3/asset-domains/{id}/quarantine` - Now sets lifecycle to 'quarantined'
- `POST /api/v3/asset-domains/{id}/remove-quarantine` - Restores lifecycle to 'active'
- `POST /api/v3/asset-domains/{id}/set-lifecycle` - Includes validation rules

**Data Migration:** Migrated existing data from old values (expired_released → released, expired_pending → active, inactive → archived)

**Tests:** Backend and frontend verified working

---

## Prioritized Backlog

### P1 - Completed
- ✅ **Verified "Unknown" in Test Mode Alerts (Feb 10, 2026):** Test alerts for SEO network domains properly show all data without "Unknown" values:
  - Money Site domains show correct tier, severity (CRITICAL), and network info
  - Supporting domains show proper upstream chain to Money Site (e.g., `tier1-site1.com → moneysite.com/landing → Money Site reached`)
  - Full structure lines (`STRUKTUR SEO TERKINI`) display correctly with tier hierarchy
  - Non-SEO domains gracefully show "not used in SEO" without errors

- ✅ **Team Performance Alerts (Feb 12, 2026):** Automatic performance monitoring with Telegram alerts
  - Configurable thresholds: false resolution rate, stale conflict days, backlog, avg resolution time
  - Daily automatic checks at 9:00 AM
  - Manual check via Settings > Performance Alerts tab
  - Alert history tracking in database

- ✅ **Domain Lifecycle & Quarantine (Feb 12, 2026):** Complete domain monitoring overhaul
  - Lifecycle statuses (active, expired_pending, expired_released, inactive, archived)
  - Quarantine system with categories (spam_murni, DMCA, penalized, etc.)
  - Super Admin only permissions for lifecycle/quarantine management
  - SEO Monitoring Coverage panel with real-time stats
  - View mode tabs (All, Unmonitored, Released, Quarantined)

### P2 - Future
- **Email Notifications:** Optional email notifications for conflict detection/resolution
- **Advanced Auto-Assign:** Complex assignment rules by tier, workload, or expertise
- **v3_router.py Refactoring:** Break down the 3000+ line file into smaller domain-specific routers
- **Root Domain Monitoring Rule:** Auto-detect when SEO networks use paths (e.g., domain.com/blog) and require root domain monitoring

