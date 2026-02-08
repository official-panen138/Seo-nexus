# SEO-NOC V3 Migration Plan

## Overview
Migration from V2 (mixed asset/structure data) to V3 (separated concerns architecture).

## Migration Timestamp
Started: 2026-02-08

## Pre-Migration Backup
- **Location**: `/app/backups/v2_backup_20260208_085617`
- **Database**: `test_database`
- **Collections Backed Up**:
  - `domains` (23 documents)
  - `users` (7 documents)
  - `categories` (8 documents)
  - `brands` (4 documents)
  - `groups` (4 documents)
  - `audit_logs` (15 documents)
  - `settings` (1 document)

## Restoration Command
```bash
mongorestore --uri="mongodb://localhost:27017" --db="test_database" --drop /app/backups/v2_backup_20260208_085617/test_database
```

---

## V2 Schema (Current - Legacy)

### `domains` Collection
Mixed asset inventory and SEO structure data:
```json
{
  "id": "uuid",
  "domain_name": "string",
  "brand_id": "uuid",
  "category_id": "uuid",
  
  // SEO Structure (TO BE MOVED)
  "domain_status": "canonical|301_redirect|302_redirect|restore",
  "index_status": "index|noindex",
  "tier_level": "tier_5|tier_4|tier_3|tier_2|tier_1|lp_money_site",  // TO BE DERIVED
  "group_id": "uuid",
  "parent_domain_id": "uuid",
  
  // Asset Management (TO REMAIN)
  "registrar": "string",
  "expiration_date": "ISO datetime",
  "auto_renew": "boolean",
  
  // Monitoring (TO REMAIN)
  "monitoring_enabled": "boolean",
  "monitoring_interval": "5min|15min|1hour|daily",
  "last_check": "ISO datetime",
  "ping_status": "up|down|unknown",
  "http_status": "string",
  "http_status_code": "integer",
  
  "notes": "string",
  "created_at": "ISO datetime",
  "updated_at": "ISO datetime"
}
```

### `groups` Collection
Network containers:
```json
{
  "id": "uuid",
  "name": "string",
  "description": "string",
  "created_at": "ISO datetime",
  "updated_at": "ISO datetime"
}
```

---

## V3 Schema (Target)

### `asset_domains` Collection (NEW)
Pure inventory - no SEO structure data:
```json
{
  "id": "uuid",
  "legacy_id": "uuid (from V2 domains.id)",  // TRACEABILITY
  "domain_name": "string (unique)",
  "brand_id": "uuid",
  "category_id": "uuid",
  "domain_type_id": "uuid (optional)",
  
  // Asset Management
  "registrar": "string",
  "buy_date": "ISO datetime",
  "expiration_date": "ISO datetime",
  "auto_renew": "boolean",
  "status": "active|inactive|pending|expired",
  
  // Monitoring
  "monitoring_enabled": "boolean",
  "monitoring_interval": "5min|15min|1hour|daily",
  "last_check": "ISO datetime",
  "ping_status": "up|down|unknown",
  "http_status": "string",
  "http_status_code": "integer",
  
  "notes": "string",
  "created_at": "ISO datetime",
  "updated_at": "ISO datetime"
}
```

### `seo_networks` Collection (NEW - replaces groups)
Strategy containers:
```json
{
  "id": "uuid",
  "legacy_id": "uuid (from V2 groups.id)",  // TRACEABILITY
  "name": "string",
  "brand_id": "uuid",
  "description": "string",
  "status": "active|inactive|archived",
  "created_at": "ISO datetime",
  "updated_at": "ISO datetime"
}
```

### `seo_structure_entries` Collection (NEW)
Relationship layer linking assets to networks:
```json
{
  "id": "uuid",
  "legacy_domain_id": "uuid (from V2 domains.id)",  // TRACEABILITY
  "asset_domain_id": "uuid (FK to asset_domains)",
  "network_id": "uuid (FK to seo_networks)",
  
  // Domain Role in Network
  "domain_role": "main|supporting",
  "domain_status": "canonical|301_redirect|302_redirect|restore",
  "index_status": "index|noindex",
  
  // Relationship
  "target_asset_domain_id": "uuid (FK to asset_domains, nullable)",
  
  // Ranking & Path Tracking (NEW FIELDS)
  "ranking_url": "string (specific path that ranks)",
  "primary_keyword": "string",
  "ranking_position": "integer",
  "last_rank_check": "ISO datetime",
  
  "notes": "string",
  "created_at": "ISO datetime",
  "updated_at": "ISO datetime"
}
```

### `activity_logs` Collection (NEW - enhanced audit)
Detailed change tracking:
```json
{
  "id": "uuid",
  "actor": "string (user email or system:migration_v3)",
  "action_type": "create|update|delete|migrate",
  "entity_type": "asset_domain|seo_network|seo_structure_entry",
  "entity_id": "uuid",
  "before_value": "object (snapshot before change)",
  "after_value": "object (snapshot after change)",
  "metadata": {
    "migration_phase": "string (if migration)",
    "legacy_ids": "object (traceability)"
  },
  "created_at": "ISO datetime"
}
```

---

## Tier Derivation Logic (NOT STORED)

Tiers are calculated dynamically based on graph distance from the main/money domain:

```
Main Domain (domain_role = "main") = Tier 0 (LP/Money Site)
1 hop away = Tier 1
2 hops away = Tier 2
3 hops away = Tier 3
4 hops away = Tier 4
5+ hops away = Tier 5
```

**Algorithm**: BFS from main domain, counting edges.

---

## Migration Phases

### Phase 0: Preparation (COMPLETED)
- [x] Full database backup
- [x] Document current schema
- [x] Create migration plan

### Phase 1: Create New Schema (COMPLETED)
- [x] Define V3 Pydantic models (`/app/backend/models_v3.py`)
- [x] Implement ActivityLog service (`/app/backend/services/activity_log_service.py`)
- [x] Implement Tier Calculation service (`/app/backend/services/tier_service.py`)
- [x] Create dry-run migration scripts (Phase 2, 3, 4)
- [x] Validate migration scripts

### Phase 2: Migrate Domains → AssetDomains (COMPLETED)
- [x] Create dry-run migration script (`/app/backend/migrations/migration_phase2_domains.py`)
- [x] Review and validate script
- [x] Execute migration with logging
- [x] Verify data integrity
- **Result**: 23 domains → 23 asset_domains
- **Mapping**: `/app/docs/migration/phase2_legacy_mapping_20260208_104720.json`

### Phase 3: Migrate Networks (COMPLETED)
- [x] Create dry-run migration script (`/app/backend/migrations/migration_phase3_networks.py`)
- [x] Review and validate script
- [x] Execute migration with logging
- [x] Verify data integrity
- **Result**: 4 groups → 4 seo_networks
- **Mapping**: `/app/docs/migration/phase3_legacy_mapping_20260208_104727.json`

### Phase 4: Migrate SEO Structure (COMPLETED)
- [x] Create dry-run migration script (`/app/backend/migrations/migration_phase4_structure.py`)
- [x] Implement main/supporting domain logic
- [x] Review and validate script
- [x] Execute migration with logging
- [x] Verify data integrity
- **Result**: 23 seo_structure_entries (3 main, 20 supporting)
- **Mapping**: `/app/docs/migration/phase4_legacy_mapping_20260208_104731.json`

### Phase 5: Implement Auto-Calculated Tiers (COMPLETED)
- [x] Create tier calculation service (`/app/backend/services/tier_service.py`)
- [x] BFS algorithm from main domain implemented
- [x] Tier distribution verified per network

### Phase 6: Refactor Backend API
- [ ] Create new endpoints for V3 collections
- [ ] Update existing endpoints
- [ ] Maintain backward compatibility (optional)

### Phase 7: Refactor Frontend
- [ ] Update API service layer
- [ ] Update components for new data structures
- [ ] Adapt D3 visualization for derived tiers

### Phase 8: Validation & Switch
- [ ] Run dual-system validation
- [ ] User acceptance testing
- [ ] Full switch to V3
- [ ] Deprecate V2 code paths

---

## Rollback Plan

If migration fails at any phase:
1. Stop all services
2. Run restoration command above
3. Restart services
4. Review logs to identify failure cause

---

## Activity Log Actor Convention

- User actions: `user@email.com`
- Migration actions: `system:migration_v3`
- System actions: `system:scheduler`, `system:monitoring`
