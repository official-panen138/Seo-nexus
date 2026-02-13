# SEO Network Operations Center (SEO-NOC) - PRD

## Original Problem Statement
Build a full-stack SEO Network Operations Center combining:
- Asset Domain Management (inventory, ownership, expiration, monitoring)
- SEO Structure Monitoring (tier hierarchy, relationships, conflicts)
- Automated Monitoring & Alerting with Telegram integration

## Tech Stack
- **Backend**: FastAPI (Python) + MongoDB + APScheduler
- **Frontend**: React + Tailwind CSS + Shadcn/UI + Recharts
- **Visualization**: D3.js force-directed graph
- **Auth**: JWT-based authentication
- **Monitoring**: Background scheduler (5-minute cycles)
- **Alerts**: Telegram Bot API

## User Personas
1. **Super Admin**: Full access - users, roles, brands, categories, domains, networks, settings, Telegram config
2. **Admin/Manager**: Domain/network management, assign tiers/categories, view reports
3. **Viewer**: Read-only access to domains, networks, alerts, reports

## Core Architecture
- NO soft-delete/archive for SEO Networks (permanent hard-delete with cascade)
- NO archive feature for Asset Domains
- Three-part domain status: domain_active_status (auto), monitoring_status (auto), lifecycle_status (manual)
- Server-side pagination for all list endpoints
- Brand-scoped data isolation

## Key Endpoints
- `GET /api/health` - Infrastructure health check (no auth, no DB)
- `GET /api/v3/asset-domains` - Paginated, filtered asset domains
- `DELETE /api/v3/seo-networks/{id}` - Cascading hard-delete
- Full CRUD for networks, structure entries, optimizations, conflicts

## What's Implemented (Complete)
- Full V3 architecture with migration from V2
- Asset Domain Management with monitoring, lifecycle, quarantine
- SEO Network Management with D3 visualization
- Conflict Detection (14 types)
- Telegram Integration (monitoring + SEO notifications, separate channels)
- Email Alerts via Resend API
- Weekly Digest Email
- Import/Export (CSV)
- User Registration Approval Workflow
- Multi-Brand Support with scoping
- SEO Change Intelligence (mandatory change notes)
- Team Performance Alerts
- User Manual & Documentation
- manage.py CLI for VPS/Docker admin management (Feb 13, 2026)
- Accurate pagination count for computed filters (Feb 13, 2026)

## Prioritized Backlog

### P1 - High Priority (Pending)
1. **Team Performance Alerts Verification** - User needs to configure Telegram Bot Token/Chat ID
2. **Phase 5: Monitoring & Reminder Integrity** - Warnings if monitoring not configured for nodes
3. **Bulk Menu Access Control** - Requirements not yet gathered

### P2 - Medium Priority
1. Email Notifications enhancements
2. Advanced Auto-Assign Logic
3. Refactor `v3_router.py` into smaller routers
4. Deep-link Drawer Auto-Open

### P3 - Low Priority
1. API documentation (OpenAPI)
2. Webhook integrations
3. Mobile push notifications
