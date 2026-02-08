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

### P1 (High Priority) - ALL COMPLETED
- ✅ **Export V3 Data to CSV/JSON** (Feb 8, 2026)
- ✅ **Dashboard Refresh Interval** (Feb 8, 2026)
- ✅ **Bulk Node Import with Path Support** (Feb 8, 2026)

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
1. Email notification integration (Resend/SendGrid)
2. Scheduled conflict alerts (cron)
3. Domain health check improvements
4. Alert history and analytics

## Telegram Configuration
- **Bot**: @monitoringseo_bot
- **Chat ID**: 5125449265 (configured in settings collection)
- **V3 Alert Endpoints**:
  - `POST /api/v3/alerts/test` - Send test alert
  - `POST /api/v3/alerts/send-conflicts` - Send all SEO conflicts
  - `POST /api/v3/alerts/domain-change` - Alert on domain changes

## New Features (Feb 8, 2026)
- **Ranking & Path Tracking**: Network detail → Domain List → Edit button
- **Bulk CSV Import**: Domains page → Import CSV → Upload → Import
- **Activity Logs**: Sidebar → V3 Activity → Filter and view details

## Test Credentials
- **Super Admin**: `superadmin@seonoc.com` / `SuperAdmin123!`
- **Admin**: `admin@seonoc.com` / `Admin123!`

## Key Files Reference
- V2 Backend: `/app/backend/server.py`
- V3 Models: `/app/backend/models_v3.py`
- V3 Services: `/app/backend/services/`
- Migration Scripts: `/app/backend/migrations/`
- Migration Plan: `/app/docs/migration/V3_MIGRATION_PLAN.md`
- Database Backup: `/app/backups/v2_backup_20260208_085617/`
