# SEO Domain Network Manager (SEO//NEXUS) - PRD

## Original Problem Statement
Build a full-stack web application to manage, analyze, and visualize a domain network for SEO purposes. The system must replace spreadsheets and provide clear tier-based grouping, status tracking, and visual diagrams.

## User Personas
1. **Super Admin**: Full system access - manages users, roles, brands, domains, groups, relationships, and reports
2. **Admin**: Creates/edits domains, assigns tiers/groups, updates status, views reports and diagrams
3. **Viewer/Analyst**: Read-only access to domain lists, group diagrams, and analysis reports

## Core Requirements (Static)
- Domain management with brands, tiers, status, and index tracking
- Network/Group structure with parent-child relationships
- Tier hierarchy validation (Tier 5 → Tier 4 → Tier 3 → Tier 2 → Tier 1 → LP/Money Site)
- Visual D3.js graph for network visualization
- Color-coded nodes (Green=Indexed, Grey=Noindex, Red=Error/Orphan)
- Role-based access control (RBAC)
- Reports with filters and CSV/JSON export
- Audit logging for data changes

## Tech Stack
- **Backend**: FastAPI (Python) + MongoDB
- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Visualization**: D3.js force-directed graph
- **Auth**: JWT-based authentication
- **Theme**: Dark mode (forced)

## What's Been Implemented (Feb 7, 2026)

### Backend (FastAPI)
- ✅ JWT authentication with bcrypt password hashing
- ✅ Role-based access control (super_admin, admin, viewer)
- ✅ Users CRUD (super_admin only)
- ✅ Brands CRUD with domain association validation
- ✅ Domains CRUD with tier hierarchy validation
- ✅ Groups/Networks CRUD with domain counts
- ✅ Parent-child relationship management
- ✅ Reports: tier distribution, index status, brand health, orphan detection
- ✅ Data export (JSON/CSV)
- ✅ Audit logging for all changes
- ✅ Seed demo data endpoint

### Frontend (React)
- ✅ Login/Register pages with dark theme
- ✅ Dashboard with stats cards and charts (Recharts)
- ✅ Domains page with table, search, and filters
- ✅ Domain CRUD dialog with tier/parent validation
- ✅ Networks/Groups page with cards
- ✅ Network detail page with D3.js visualization
- ✅ Reports page with tier/index charts and export
- ✅ Brands management (super_admin)
- ✅ Users management (super_admin)
- ✅ Audit logs viewer (super_admin)
- ✅ Responsive sidebar layout
- ✅ Toast notifications (Sonner)

### D3.js Network Visualization
- ✅ Force-directed graph layout
- ✅ Tier-based Y-axis positioning
- ✅ Color-coded nodes by tier and index status
- ✅ Zoom, pan, drag interactions
- ✅ Tooltips with domain details
- ✅ Orphan domain highlighting (red glow)
- ✅ Connected link highlighting on hover
- ✅ Tier legend

## Prioritized Backlog

### P0 (Critical - Not Blocking)
- None - MVP complete

### P1 (High Priority - Nice to Have)
- Bulk domain import from CSV
- Domain search with advanced filters
- Network comparison view
- Real-time collaboration indicators

### P2 (Medium Priority - Future)
- Domain health check automation
- SEO metrics integration (Ahrefs, SEMrush)
- Scheduled reports via email
- Multi-language support
- Dark/Light theme toggle

### P3 (Low Priority - Backlog)
- Mobile app version
- API rate limiting
- Redis caching layer
- Webhook notifications
- Team workspaces

## Next Tasks List
1. Add bulk import functionality for domains
2. Implement domain search with regex support
3. Add notification system for tier changes
4. Create printable network diagram export
5. Add domain notes/comments timeline
