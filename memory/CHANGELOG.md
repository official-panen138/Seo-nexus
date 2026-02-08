# SEO-NOC Changelog

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
