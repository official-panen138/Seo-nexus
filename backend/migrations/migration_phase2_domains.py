"""
Migration Script: Phase 2 - Domains to AssetDomains
===================================================
Migrates V2 `domains` collection to V3 `asset_domains` collection.

Features:
- Dry-run mode by default
- legacy_id mapping for traceability
- Activity logging with actor: system:migration_v3
- Validation checks before execution

Usage:
    # Dry run (default)
    python migration_phase2_domains.py
    
    # Execute migration
    python migration_phase2_domains.py --execute
"""

import asyncio
import argparse
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
import os
import sys
import json

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))


MIGRATION_ACTOR = "system:migration_v3"
MIGRATION_PHASE = "phase_2_domains_to_asset_domains"


async def get_db():
    """Get database connection"""
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    client = AsyncIOMotorClient(mongo_url)
    return client[db_name]


def map_asset_status(domain: dict) -> str:
    """Map V2 domain to V3 asset status"""
    ping_status = domain.get("ping_status", "unknown")
    expiration_date = domain.get("expiration_date")
    
    if expiration_date:
        try:
            exp = datetime.fromisoformat(expiration_date.replace("Z", "+00:00"))
            if exp < datetime.now(timezone.utc):
                return "expired"
        except (ValueError, TypeError):
            pass
    
    if ping_status == "down":
        return "inactive"
    
    return "active"


def transform_domain_to_asset(domain: dict) -> dict:
    """
    Transform V2 domain document to V3 asset_domain document.
    
    Extracts only asset/inventory fields, excludes SEO structure fields.
    """
    now = datetime.now(timezone.utc).isoformat()
    
    asset_domain = {
        "id": str(uuid.uuid4()),
        "legacy_id": domain["id"],  # TRACEABILITY
        "domain_name": domain["domain_name"],
        "brand_id": domain.get("brand_id"),
        "category_id": domain.get("category_id"),
        "domain_type_id": None,  # New field, will be populated later if needed
        
        # Asset Management fields
        "registrar": domain.get("registrar"),
        "buy_date": None,  # Not in V2, can be populated later
        "expiration_date": domain.get("expiration_date"),
        "auto_renew": domain.get("auto_renew", False),
        "status": map_asset_status(domain),
        
        # Monitoring fields (preserved)
        "monitoring_enabled": domain.get("monitoring_enabled", False),
        "monitoring_interval": domain.get("monitoring_interval", "1hour"),
        "last_check": domain.get("last_check"),
        "ping_status": domain.get("ping_status", "unknown"),
        "http_status": domain.get("http_status"),
        "http_status_code": domain.get("http_status_code"),
        
        "notes": domain.get("notes", ""),
        "created_at": domain.get("created_at", now),
        "updated_at": now
    }
    
    return asset_domain


async def validate_prerequisites(db) -> Dict[str, Any]:
    """Validate that migration can proceed"""
    issues = []
    
    # Check source collection exists and has data
    source_count = await db.domains.count_documents({})
    if source_count == 0:
        issues.append("Source collection 'domains' is empty")
    
    # Check target collection is empty (or warn if not)
    target_count = await db.asset_domains.count_documents({})
    if target_count > 0:
        issues.append(f"Target collection 'asset_domains' already has {target_count} documents")
    
    # Check for duplicate domain names
    pipeline = [
        {"$group": {"_id": "$domain_name", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}}
    ]
    duplicates = await db.domains.aggregate(pipeline).to_list(100)
    if duplicates:
        issues.append(f"Found {len(duplicates)} duplicate domain names in source")
    
    return {
        "can_proceed": len(issues) == 0,
        "source_count": source_count,
        "target_count": target_count,
        "issues": issues,
        "duplicates": [d["_id"] for d in duplicates]
    }


async def dry_run(db) -> Dict[str, Any]:
    """
    Perform dry run of migration.
    Shows what would be migrated without making changes.
    """
    print("\n" + "="*60)
    print("PHASE 2 MIGRATION - DRY RUN")
    print("="*60)
    
    # Validate
    validation = await validate_prerequisites(db)
    print(f"\n[Validation]")
    print(f"  Source documents: {validation['source_count']}")
    print(f"  Target documents: {validation['target_count']}")
    
    if validation['issues']:
        print(f"\n[Issues Found]")
        for issue in validation['issues']:
            print(f"  ⚠️  {issue}")
    
    if not validation['can_proceed']:
        print(f"\n❌ Migration cannot proceed. Fix issues first.")
        return validation
    
    # Sample transformations
    domains = await db.domains.find({}, {"_id": 0}).to_list(10)
    
    print(f"\n[Sample Transformations] (showing first {len(domains)})")
    print("-"*60)
    
    transformed = []
    for domain in domains:
        asset = transform_domain_to_asset(domain)
        transformed.append(asset)
        
        print(f"\n  V2 Domain: {domain['domain_name']}")
        print(f"    → V3 AssetDomain:")
        print(f"       id: {asset['id']}")
        print(f"       legacy_id: {asset['legacy_id']}")
        print(f"       status: {asset['status']}")
        print(f"       monitoring_enabled: {asset['monitoring_enabled']}")
    
    # Show what will be logged
    print(f"\n[Activity Logs to be Created]")
    print(f"  Actor: {MIGRATION_ACTOR}")
    print(f"  Phase: {MIGRATION_PHASE}")
    print(f"  Entries: {validation['source_count']}")
    
    # Summary
    print(f"\n[Migration Summary]")
    print(f"  Documents to migrate: {validation['source_count']}")
    print(f"  New collection: asset_domains")
    print(f"  Indexes to create: domain_name (unique), legacy_id, brand_id")
    
    print("\n" + "="*60)
    print("DRY RUN COMPLETE - No changes made")
    print("Run with --execute to perform migration")
    print("="*60 + "\n")
    
    return {
        "validation": validation,
        "sample_count": len(transformed),
        "samples": transformed
    }


async def execute_migration(db) -> Dict[str, Any]:
    """
    Execute the actual migration.
    """
    print("\n" + "="*60)
    print("PHASE 2 MIGRATION - EXECUTING")
    print("="*60)
    
    # Validate first
    validation = await validate_prerequisites(db)
    if not validation['can_proceed']:
        print(f"\n❌ Migration cannot proceed. Issues found:")
        for issue in validation['issues']:
            print(f"  ⚠️  {issue}")
        return {"success": False, "validation": validation}
    
    # Get all domains
    domains = await db.domains.find({}, {"_id": 0}).to_list(100000)
    print(f"\n[Step 1] Fetched {len(domains)} domains from source")
    
    # Transform all
    asset_domains = []
    legacy_mapping = {}  # old_id -> new_id
    
    for domain in domains:
        asset = transform_domain_to_asset(domain)
        asset_domains.append(asset)
        legacy_mapping[domain["id"]] = asset["id"]
    
    print(f"[Step 2] Transformed {len(asset_domains)} documents")
    
    # Create indexes on target collection
    print(f"[Step 3] Creating indexes...")
    await db.asset_domains.create_index("domain_name", unique=True)
    await db.asset_domains.create_index("legacy_id")
    await db.asset_domains.create_index("brand_id")
    await db.asset_domains.create_index("status")
    
    # Insert in batches
    batch_size = 100
    inserted_count = 0
    
    print(f"[Step 4] Inserting documents in batches of {batch_size}...")
    
    for i in range(0, len(asset_domains), batch_size):
        batch = asset_domains[i:i+batch_size]
        await db.asset_domains.insert_many(batch)
        inserted_count += len(batch)
        print(f"  Inserted {inserted_count}/{len(asset_domains)}")
    
    # Create activity logs
    print(f"[Step 5] Creating activity logs...")
    activity_logs = []
    now = datetime.now(timezone.utc).isoformat()
    
    for domain, asset in zip(domains, asset_domains):
        log = {
            "id": str(uuid.uuid4()),
            "actor": MIGRATION_ACTOR,
            "action_type": "migrate",
            "entity_type": "asset_domain",
            "entity_id": asset["id"],
            "before_value": domain,
            "after_value": asset,
            "metadata": {
                "migration_phase": MIGRATION_PHASE,
                "legacy_ids": {
                    "v2_domain_id": domain["id"],
                    "v3_asset_domain_id": asset["id"]
                }
            },
            "created_at": now
        }
        activity_logs.append(log)
    
    # Insert activity logs in batches
    for i in range(0, len(activity_logs), batch_size):
        batch = activity_logs[i:i+batch_size]
        await db.activity_logs_v3.insert_many(batch)
    
    print(f"  Created {len(activity_logs)} activity log entries")
    
    # Save mapping file for reference
    mapping_file = f"/app/docs/migration/phase2_legacy_mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
    with open(mapping_file, 'w') as f:
        json.dump(legacy_mapping, f, indent=2)
    print(f"[Step 6] Saved legacy mapping to {mapping_file}")
    
    # Verify
    final_count = await db.asset_domains.count_documents({})
    
    print(f"\n[Verification]")
    print(f"  Source count: {len(domains)}")
    print(f"  Target count: {final_count}")
    print(f"  Match: {'✅' if final_count == len(domains) else '❌'}")
    
    print("\n" + "="*60)
    print("PHASE 2 MIGRATION COMPLETE")
    print("="*60 + "\n")
    
    return {
        "success": True,
        "source_count": len(domains),
        "target_count": final_count,
        "activity_logs_created": len(activity_logs),
        "mapping_file": mapping_file
    }


async def main():
    parser = argparse.ArgumentParser(description="Phase 2 Migration: Domains to AssetDomains")
    parser.add_argument("--execute", action="store_true", help="Execute migration (default is dry-run)")
    args = parser.parse_args()
    
    db = await get_db()
    
    if args.execute:
        result = await execute_migration(db)
    else:
        result = await dry_run(db)
    
    return result


if __name__ == "__main__":
    asyncio.run(main())
