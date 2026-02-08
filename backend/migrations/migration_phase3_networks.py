"""
Migration Script: Phase 3 - Groups to SeoNetworks
=================================================
Migrates V2 `groups` collection to V3 `seo_networks` collection.

Features:
- Dry-run mode by default
- legacy_id mapping for traceability
- Activity logging with actor: system:migration_v3
- Validation checks before execution

Usage:
    # Dry run (default)
    python migration_phase3_networks.py
    
    # Execute migration
    python migration_phase3_networks.py --execute
"""

import asyncio
import argparse
import uuid
from datetime import datetime, timezone
from typing import Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
import os
import sys
import json

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))


MIGRATION_ACTOR = "system:migration_v3"
MIGRATION_PHASE = "phase_3_groups_to_seo_networks"


async def get_db():
    """Get database connection"""
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    client = AsyncIOMotorClient(mongo_url)
    return client[db_name]


def transform_group_to_network(group: dict) -> dict:
    """
    Transform V2 group document to V3 seo_network document.
    """
    now = datetime.now(timezone.utc).isoformat()
    
    # Try to find brand_id from associated domains (if any)
    # This will be populated during execution with actual data
    brand_id = None
    
    seo_network = {
        "id": str(uuid.uuid4()),
        "legacy_id": group["id"],  # TRACEABILITY
        "name": group["name"],
        "brand_id": brand_id,  # Will be determined from domain associations
        "description": group.get("description", ""),
        "status": "active",  # All migrated networks start as active
        "created_at": group.get("created_at", now),
        "updated_at": now
    }
    
    return seo_network


async def determine_network_brand(db, group_id: str) -> str:
    """
    Determine the brand for a network based on its domains.
    Uses majority vote from associated domains.
    """
    pipeline = [
        {"$match": {"group_id": group_id}},
        {"$group": {"_id": "$brand_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 1}
    ]
    
    result = await db.domains.aggregate(pipeline).to_list(1)
    if result:
        return result[0]["_id"]
    return None


async def validate_prerequisites(db) -> Dict[str, Any]:
    """Validate that migration can proceed"""
    issues = []
    
    # Check source collection exists and has data
    source_count = await db.groups.count_documents({})
    if source_count == 0:
        issues.append("Source collection 'groups' is empty (may be OK if no networks exist)")
    
    # Check target collection is empty (or warn if not)
    target_count = await db.seo_networks.count_documents({})
    if target_count > 0:
        issues.append(f"Target collection 'seo_networks' already has {target_count} documents")
    
    # Check Phase 2 was completed (asset_domains exists)
    asset_count = await db.asset_domains.count_documents({})
    if asset_count == 0:
        issues.append("Phase 2 not completed: 'asset_domains' collection is empty")
    
    return {
        "can_proceed": len([i for i in issues if "empty (may be OK)" not in i]) == 0,
        "source_count": source_count,
        "target_count": target_count,
        "asset_domains_count": asset_count,
        "issues": issues
    }


async def dry_run(db) -> Dict[str, Any]:
    """
    Perform dry run of migration.
    Shows what would be migrated without making changes.
    """
    print("\n" + "="*60)
    print("PHASE 3 MIGRATION - DRY RUN")
    print("="*60)
    
    # Validate
    validation = await validate_prerequisites(db)
    print(f"\n[Validation]")
    print(f"  Source documents (groups): {validation['source_count']}")
    print(f"  Target documents: {validation['target_count']}")
    print(f"  Asset domains (from Phase 2): {validation['asset_domains_count']}")
    
    if validation['issues']:
        print(f"\n[Issues Found]")
        for issue in validation['issues']:
            print(f"  ⚠️  {issue}")
    
    if not validation['can_proceed']:
        print(f"\n❌ Migration cannot proceed. Fix issues first.")
        return validation
    
    # Sample transformations
    groups = await db.groups.find({}, {"_id": 0}).to_list(10)
    
    print(f"\n[Sample Transformations] (showing all {len(groups)} groups)")
    print("-"*60)
    
    transformed = []
    for group in groups:
        network = transform_group_to_network(group)
        
        # Determine brand from domains
        brand_id = await determine_network_brand(db, group["id"])
        network["brand_id"] = brand_id
        
        # Get brand name for display
        brand_name = None
        if brand_id:
            brand = await db.brands.find_one({"id": brand_id}, {"_id": 0, "name": 1})
            brand_name = brand["name"] if brand else None
        
        # Count domains in this network
        domain_count = await db.domains.count_documents({"group_id": group["id"]})
        
        transformed.append(network)
        
        print(f"\n  V2 Group: {group['name']}")
        print(f"    → V3 SeoNetwork:")
        print(f"       id: {network['id']}")
        print(f"       legacy_id: {network['legacy_id']}")
        print(f"       brand: {brand_name or 'None'}")
        print(f"       status: {network['status']}")
        print(f"       domains in network: {domain_count}")
    
    # Show what will be logged
    print(f"\n[Activity Logs to be Created]")
    print(f"  Actor: {MIGRATION_ACTOR}")
    print(f"  Phase: {MIGRATION_PHASE}")
    print(f"  Entries: {validation['source_count']}")
    
    # Summary
    print(f"\n[Migration Summary]")
    print(f"  Documents to migrate: {validation['source_count']}")
    print(f"  New collection: seo_networks")
    print(f"  Indexes to create: name, legacy_id, brand_id, status")
    
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
    print("PHASE 3 MIGRATION - EXECUTING")
    print("="*60)
    
    # Validate first
    validation = await validate_prerequisites(db)
    if not validation['can_proceed']:
        print(f"\n❌ Migration cannot proceed. Issues found:")
        for issue in validation['issues']:
            print(f"  ⚠️  {issue}")
        return {"success": False, "validation": validation}
    
    # Get all groups
    groups = await db.groups.find({}, {"_id": 0}).to_list(10000)
    print(f"\n[Step 1] Fetched {len(groups)} groups from source")
    
    # Transform all
    seo_networks = []
    legacy_mapping = {}  # old_id -> new_id
    
    for group in groups:
        network = transform_group_to_network(group)
        
        # Determine brand from domains
        brand_id = await determine_network_brand(db, group["id"])
        network["brand_id"] = brand_id
        
        seo_networks.append(network)
        legacy_mapping[group["id"]] = network["id"]
    
    print(f"[Step 2] Transformed {len(seo_networks)} documents")
    
    # Create indexes on target collection
    print(f"[Step 3] Creating indexes...")
    await db.seo_networks.create_index("name")
    await db.seo_networks.create_index("legacy_id")
    await db.seo_networks.create_index("brand_id")
    await db.seo_networks.create_index("status")
    
    # Insert all networks
    if seo_networks:
        print(f"[Step 4] Inserting documents...")
        await db.seo_networks.insert_many(seo_networks)
        print(f"  Inserted {len(seo_networks)} networks")
    else:
        print(f"[Step 4] No networks to insert")
    
    # Create activity logs
    print(f"[Step 5] Creating activity logs...")
    activity_logs = []
    now = datetime.now(timezone.utc).isoformat()
    
    for group, network in zip(groups, seo_networks):
        log = {
            "id": str(uuid.uuid4()),
            "actor": MIGRATION_ACTOR,
            "action_type": "migrate",
            "entity_type": "seo_network",
            "entity_id": network["id"],
            "before_value": group,
            "after_value": network,
            "metadata": {
                "migration_phase": MIGRATION_PHASE,
                "legacy_ids": {
                    "v2_group_id": group["id"],
                    "v3_seo_network_id": network["id"]
                }
            },
            "created_at": now
        }
        activity_logs.append(log)
    
    if activity_logs:
        await db.activity_logs_v3.insert_many(activity_logs)
        print(f"  Created {len(activity_logs)} activity log entries")
    
    # Save mapping file for reference
    mapping_file = f"/app/docs/migration/phase3_legacy_mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
    with open(mapping_file, 'w') as f:
        json.dump(legacy_mapping, f, indent=2)
    print(f"[Step 6] Saved legacy mapping to {mapping_file}")
    
    # Verify
    final_count = await db.seo_networks.count_documents({})
    
    print(f"\n[Verification]")
    print(f"  Source count: {len(groups)}")
    print(f"  Target count: {final_count}")
    print(f"  Match: {'✅' if final_count == len(groups) else '❌'}")
    
    print("\n" + "="*60)
    print("PHASE 3 MIGRATION COMPLETE")
    print("="*60 + "\n")
    
    return {
        "success": True,
        "source_count": len(groups),
        "target_count": final_count,
        "activity_logs_created": len(activity_logs),
        "mapping_file": mapping_file
    }


async def main():
    parser = argparse.ArgumentParser(description="Phase 3 Migration: Groups to SeoNetworks")
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
