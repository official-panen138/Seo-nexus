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
  - assetDomainsAPI, networksAPI, structureAPI, activityLogsAPI, v3ReportsAPI
- ✅ NetworkGraph.jsx updated for V3 with derived tiers
- ✅ GroupDetailPage.jsx uses V3 API with automatic fallback to V2
  - Tier distribution displayed (Derived)
  - D3 visualization shows correct tier colors
  - Domain list shows Role, Target, and calculated tier
- ✅ DomainsPage.jsx updated to use V3 assetDomainsAPI
  - Shows Asset Domains with V3 badge
  - Columns: Domain, Brand, Status, Monitoring, Expiration
  - Create/Edit dialog supports V3 asset fields

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
- 3 networks (Main SEO Network, Support Network, Test Network)
- 22 domains with hierarchy
- 14 SEO conflicts detected

## Prioritized Backlog

### P0 (Critical) - ALL COMPLETED
- ✅ V3 Architecture Migration (Phases 0-4)
- ✅ V3 API Endpoints
- ✅ Frontend V3 Integration (Networks, Domains)
- ✅ Derived Tier Calculation

### P1 (High Priority - Remaining)
- ✅ Configure Telegram Chat ID for live alerts - DONE
- Bulk domain import from CSV
- Ranking & Path Tracking UI (new V3 fields)
- Email notification channel (Resend/SendGrid)
- Dashboard refresh interval setting

### P2 (Medium Priority)
- Activity logs viewer page
- Export V3 data to CSV/JSON
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
1. Configure Telegram Chat ID for live alerts
2. Add ranking & path tracking fields to structure entry UI
3. Bulk domain CSV import feature
4. Activity logs viewer page
5. Export V3 data functionality

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
