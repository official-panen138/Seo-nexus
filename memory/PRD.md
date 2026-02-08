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

### V3 Architecture (IN PROGRESS - Feb 8, 2026)
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
- ✅ Migration scripts with dry-run mode:
  - Phase 2: `/app/backend/migrations/migration_phase2_domains.py`
  - Phase 3: `/app/backend/migrations/migration_phase3_networks.py`
  - Phase 4: `/app/backend/migrations/migration_phase4_structure.py`

**Migration Scripts - Ready for Review**
- All scripts include legacy_id mapping for traceability
- All scripts log to activity_logs_v3 with actor: system:migration_v3
- Dry-run mode validates prerequisites before execution

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

### P0 (Critical - Complete)
- ✅ All core features implemented

### P1 (High Priority)
- Configure Telegram Chat ID for live alerts
- Bulk domain import from CSV
- Email notification channel (Resend/SendGrid)
- Dashboard refresh interval setting

### P2 (Medium Priority)
- Mobile push notifications
- Slack/Discord integration
- Domain health history graphs
- Automated SEO conflict resolution suggestions
- Multi-language support

### P3 (Low Priority)
- API rate limiting
- Redis caching layer
- Webhook notifications
- Team workspaces
- White-label option

## Next Tasks List
1. Configure Telegram Chat ID (use @userinfobot or add bot to group)
2. Test live alert delivery
3. Enable monitoring on critical domains
4. Set up expiration alert thresholds
5. Document API endpoints for external integrations
