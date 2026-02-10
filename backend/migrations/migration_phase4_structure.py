"""
Migration Script: Phase 4 - SEO Structure Entries
=================================================
Creates `seo_structure_entries` collection from V2 domains' SEO relationships.

This is the most complex migration phase as it:
- Extracts SEO structure from domains
- Maps to new V3 asset_domain_ids and network_ids
- Determines domain_role (main vs supporting)
- Sets up target relationships

Features:
- Dry-run mode by default
- legacy_id mapping for traceability
- Activity logging with actor: system:migration_v3
- Validation checks before execution

Usage:
    # Dry run (default)
    python migration_phase4_structure.py

    # Execute migration
    python migration_phase4_structure.py --execute
"""

import asyncio
import argparse
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
import os
import sys
import json

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


MIGRATION_ACTOR = "system:migration_v3"
MIGRATION_PHASE = "phase_4_seo_structure_entries"


async def get_db():
    """Get database connection"""
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    return client[db_name]


async def load_mappings(db) -> Dict[str, Dict[str, str]]:
    """
    Load legacy ID mappings from previous phases.
    Returns: {
        "domains": {v2_id: v3_asset_domain_id},
        "groups": {v2_id: v3_seo_network_id}
    }
    """
    mappings = {"domains": {}, "groups": {}}

    # Load domain mappings from asset_domains
    assets = await db.asset_domains.find(
        {}, {"_id": 0, "id": 1, "legacy_id": 1}
    ).to_list(100000)
    for asset in assets:
        if asset.get("legacy_id"):
            mappings["domains"][asset["legacy_id"]] = asset["id"]

    # Load network mappings from seo_networks
    networks = await db.seo_networks.find(
        {}, {"_id": 0, "id": 1, "legacy_id": 1}
    ).to_list(10000)
    for network in networks:
        if network.get("legacy_id"):
            mappings["groups"][network["legacy_id"]] = network["id"]

    return mappings


def determine_domain_role(domain: dict) -> str:
    """
    Determine if domain is main (money site) or supporting.

    Rules:
    - tier_level = "lp_money_site" -> main
    - No parent_domain_id and in a network -> could be main
    - Has parent_domain_id -> supporting
    """
    tier = domain.get("tier_level", "")

    if tier == "lp_money_site":
        return "main"

    # If no parent and is the root of hierarchy, could be main
    # But for safety, we mark as supporting unless explicitly LP
    return "supporting"


def map_domain_status(v2_status: str) -> str:
    """Map V2 domain_status to V3 seo_status"""
    mapping = {
        "canonical": "canonical",
        "301_redirect": "301_redirect",
        "302_redirect": "302_redirect",
        "restore": "restore",
    }
    return mapping.get(v2_status, "canonical")


async def transform_domain_to_structure_entry(
    domain: dict, mappings: Dict[str, Dict[str, str]]
) -> Optional[dict]:
    """
    Transform V2 domain's SEO fields to V3 seo_structure_entry.

    Only creates entry if domain is assigned to a network (group).
    """
    # Skip if not in a network
    if not domain.get("group_id"):
        return None

    # Get new IDs from mappings
    v3_asset_id = mappings["domains"].get(domain["id"])
    v3_network_id = mappings["groups"].get(domain["group_id"])

    if not v3_asset_id or not v3_network_id:
        return None

    # Map parent domain to target
    v3_target_id = None
    if domain.get("parent_domain_id"):
        v3_target_id = mappings["domains"].get(domain["parent_domain_id"])

    now = datetime.now(timezone.utc).isoformat()

    structure_entry = {
        "id": str(uuid.uuid4()),
        "legacy_domain_id": domain["id"],  # TRACEABILITY
        "asset_domain_id": v3_asset_id,
        "network_id": v3_network_id,
        # Domain Role
        "domain_role": determine_domain_role(domain),
        "domain_status": map_domain_status(domain.get("domain_status", "canonical")),
        "index_status": domain.get("index_status", "index"),
        # Relationship
        "target_asset_domain_id": v3_target_id,
        # Ranking & Path Tracking (NEW - empty for migration)
        "ranking_url": None,
        "primary_keyword": None,
        "ranking_position": None,
        "last_rank_check": None,
        "notes": "",  # SEO-specific notes can be added later
        "created_at": domain.get("created_at", now),
        "updated_at": now,
    }

    return structure_entry


async def validate_prerequisites(db) -> Dict[str, Any]:
    """Validate that migration can proceed"""
    issues = []
    warnings = []

    # Check Phase 2 completed
    asset_count = await db.asset_domains.count_documents({})
    if asset_count == 0:
        issues.append("Phase 2 not completed: 'asset_domains' collection is empty")

    # Check Phase 3 completed
    network_count = await db.seo_networks.count_documents({})
    if network_count == 0:
        warnings.append("Phase 3 shows no networks (may be OK if no groups existed)")

    # Check target collection is empty
    target_count = await db.seo_structure_entries.count_documents({})
    if target_count > 0:
        issues.append(
            f"Target collection 'seo_structure_entries' already has {target_count} documents"
        )

    # Count domains with group assignments
    domains_in_groups = await db.domains.count_documents({"group_id": {"$ne": None}})

    # Check for orphan references
    domains = await db.domains.find(
        {"parent_domain_id": {"$ne": None}}, {"_id": 0, "id": 1, "parent_domain_id": 1}
    ).to_list(100000)

    all_domain_ids = set(
        d["id"] for d in await db.domains.find({}, {"_id": 0, "id": 1}).to_list(100000)
    )

    orphan_refs = []
    for d in domains:
        if d["parent_domain_id"] not in all_domain_ids:
            orphan_refs.append(d["id"])

    if orphan_refs:
        warnings.append(
            f"Found {len(orphan_refs)} domains with invalid parent references"
        )

    return {
        "can_proceed": len(issues) == 0,
        "asset_domains_count": asset_count,
        "seo_networks_count": network_count,
        "target_count": target_count,
        "domains_in_groups": domains_in_groups,
        "orphan_references": len(orphan_refs),
        "issues": issues,
        "warnings": warnings,
    }


async def dry_run(db) -> Dict[str, Any]:
    """
    Perform dry run of migration.
    Shows what would be migrated without making changes.
    """
    print("\n" + "=" * 60)
    print("PHASE 4 MIGRATION - DRY RUN")
    print("=" * 60)

    # Validate
    validation = await validate_prerequisites(db)
    print("\n[Validation]")
    print(f"  Asset domains (Phase 2): {validation['asset_domains_count']}")
    print(f"  SEO networks (Phase 3): {validation['seo_networks_count']}")
    print(f"  Domains in groups: {validation['domains_in_groups']}")
    print(f"  Target collection: {validation['target_count']} existing")

    if validation["issues"]:
        print("\n[Issues Found]")
        for issue in validation["issues"]:
            print(f"  ❌ {issue}")

    if validation["warnings"]:
        print("\n[Warnings]")
        for warning in validation["warnings"]:
            print(f"  ⚠️  {warning}")

    if not validation["can_proceed"]:
        print("\n❌ Migration cannot proceed. Fix issues first.")
        return validation

    # Load mappings
    print("\n[Loading ID Mappings]...")
    mappings = await load_mappings(db)
    print(f"  Domain mappings: {len(mappings['domains'])}")
    print(f"  Network mappings: {len(mappings['groups'])}")

    # Sample transformations
    domains = await db.domains.find({"group_id": {"$ne": None}}, {"_id": 0}).to_list(10)

    print(
        f"\n[Sample Transformations] (showing first {len(domains)} of {validation['domains_in_groups']})"
    )
    print("-" * 60)

    transformed = []
    main_count = 0
    supporting_count = 0

    for domain in domains:
        entry = await transform_domain_to_structure_entry(domain, mappings)

        if entry:
            transformed.append(entry)

            if entry["domain_role"] == "main":
                main_count += 1
            else:
                supporting_count += 1

            # Get names for display
            asset = await db.asset_domains.find_one(
                {"id": entry["asset_domain_id"]}, {"_id": 0, "domain_name": 1}
            )
            network = await db.seo_networks.find_one(
                {"id": entry["network_id"]}, {"_id": 0, "name": 1}
            )

            print(f"\n  V2 Domain: {domain['domain_name']}")
            print("    → V3 SeoStructureEntry:")
            print(f"       id: {entry['id']}")
            print(f"       legacy_domain_id: {entry['legacy_domain_id']}")
            print(f"       asset_domain: {asset['domain_name'] if asset else 'N/A'}")
            print(f"       network: {network['name'] if network else 'N/A'}")
            print(f"       role: {entry['domain_role']}")
            print(f"       status: {entry['domain_status']}")
            print(f"       index: {entry['index_status']}")
            print(
                f"       has_target: {'Yes' if entry['target_asset_domain_id'] else 'No'}"
            )

    # Process all to get counts
    all_domains = await db.domains.find(
        {"group_id": {"$ne": None}}, {"_id": 0}
    ).to_list(100000)

    total_main = 0
    total_supporting = 0
    skipped = 0

    for domain in all_domains:
        entry = await transform_domain_to_structure_entry(domain, mappings)
        if entry:
            if entry["domain_role"] == "main":
                total_main += 1
            else:
                total_supporting += 1
        else:
            skipped += 1

    # Show what will be logged
    print("\n[Activity Logs to be Created]")
    print(f"  Actor: {MIGRATION_ACTOR}")
    print(f"  Phase: {MIGRATION_PHASE}")
    print(f"  Entries: {total_main + total_supporting}")

    # Summary
    print("\n[Migration Summary]")
    print(f"  Entries to create: {total_main + total_supporting}")
    print(f"    - Main domains: {total_main}")
    print(f"    - Supporting domains: {total_supporting}")
    print(f"  Skipped (no mapping): {skipped}")
    print("  New collection: seo_structure_entries")
    print("  Indexes: asset_domain_id, network_id, legacy_domain_id, domain_role")

    print("\n" + "=" * 60)
    print("DRY RUN COMPLETE - No changes made")
    print("Run with --execute to perform migration")
    print("=" * 60 + "\n")

    return {
        "validation": validation,
        "sample_count": len(transformed),
        "total_main": total_main,
        "total_supporting": total_supporting,
        "skipped": skipped,
    }


async def execute_migration(db) -> Dict[str, Any]:
    """
    Execute the actual migration.
    """
    print("\n" + "=" * 60)
    print("PHASE 4 MIGRATION - EXECUTING")
    print("=" * 60)

    # Validate first
    validation = await validate_prerequisites(db)
    if not validation["can_proceed"]:
        print("\n❌ Migration cannot proceed. Issues found:")
        for issue in validation["issues"]:
            print(f"  ❌ {issue}")
        return {"success": False, "validation": validation}

    # Load mappings
    print("\n[Step 1] Loading ID mappings...")
    mappings = await load_mappings(db)
    print(f"  Domain mappings: {len(mappings['domains'])}")
    print(f"  Network mappings: {len(mappings['groups'])}")

    # Get all domains in groups
    domains = await db.domains.find({"group_id": {"$ne": None}}, {"_id": 0}).to_list(
        100000
    )
    print(f"\n[Step 2] Fetched {len(domains)} domains with group assignments")

    # Transform all
    structure_entries = []
    legacy_mapping = {}
    skipped = 0

    for domain in domains:
        entry = await transform_domain_to_structure_entry(domain, mappings)
        if entry:
            structure_entries.append(entry)
            legacy_mapping[domain["id"]] = entry["id"]
        else:
            skipped += 1

    print(
        f"[Step 3] Transformed {len(structure_entries)} documents (skipped {skipped})"
    )

    # Create indexes
    print("[Step 4] Creating indexes...")
    await db.seo_structure_entries.create_index("asset_domain_id")
    await db.seo_structure_entries.create_index("network_id")
    await db.seo_structure_entries.create_index("legacy_domain_id")
    await db.seo_structure_entries.create_index("domain_role")
    await db.seo_structure_entries.create_index("target_asset_domain_id")
    await db.seo_structure_entries.create_index([("network_id", 1), ("domain_role", 1)])

    # Insert in batches
    batch_size = 100
    inserted_count = 0

    print(f"[Step 5] Inserting documents in batches of {batch_size}...")

    for i in range(0, len(structure_entries), batch_size):
        batch = structure_entries[i : i + batch_size]
        await db.seo_structure_entries.insert_many(batch)
        inserted_count += len(batch)
        print(f"  Inserted {inserted_count}/{len(structure_entries)}")

    # Create activity logs
    print("[Step 6] Creating activity logs...")
    activity_logs = []
    now = datetime.now(timezone.utc).isoformat()

    # Create a domain lookup for before values
    domain_lookup = {d["id"]: d for d in domains}

    for entry in structure_entries:
        v2_domain = domain_lookup.get(entry["legacy_domain_id"], {})

        log = {
            "id": str(uuid.uuid4()),
            "actor": MIGRATION_ACTOR,
            "action_type": "migrate",
            "entity_type": "seo_structure_entry",
            "entity_id": entry["id"],
            "before_value": {
                "domain_id": entry["legacy_domain_id"],
                "group_id": v2_domain.get("group_id"),
                "tier_level": v2_domain.get("tier_level"),
                "domain_status": v2_domain.get("domain_status"),
                "index_status": v2_domain.get("index_status"),
                "parent_domain_id": v2_domain.get("parent_domain_id"),
            },
            "after_value": entry,
            "metadata": {
                "migration_phase": MIGRATION_PHASE,
                "legacy_ids": {
                    "v2_domain_id": entry["legacy_domain_id"],
                    "v2_group_id": v2_domain.get("group_id"),
                    "v3_seo_structure_entry_id": entry["id"],
                    "v3_asset_domain_id": entry["asset_domain_id"],
                    "v3_network_id": entry["network_id"],
                },
            },
            "created_at": now,
        }
        activity_logs.append(log)

    # Insert activity logs in batches
    for i in range(0, len(activity_logs), batch_size):
        batch = activity_logs[i : i + batch_size]
        await db.activity_logs_v3.insert_many(batch)

    print(f"  Created {len(activity_logs)} activity log entries")

    # Save mapping file
    mapping_file = f"/app/docs/migration/phase4_legacy_mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
    with open(mapping_file, "w") as f:
        json.dump(legacy_mapping, f, indent=2)
    print(f"[Step 7] Saved legacy mapping to {mapping_file}")

    # Verify
    final_count = await db.seo_structure_entries.count_documents({})
    main_count = await db.seo_structure_entries.count_documents({"domain_role": "main"})
    supporting_count = await db.seo_structure_entries.count_documents(
        {"domain_role": "supporting"}
    )

    print("\n[Verification]")
    print(f"  Expected: {len(structure_entries)}")
    print(f"  Actual: {final_count}")
    print(f"  Main domains: {main_count}")
    print(f"  Supporting domains: {supporting_count}")
    print(f"  Match: {'✅' if final_count == len(structure_entries) else '❌'}")

    print("\n" + "=" * 60)
    print("PHASE 4 MIGRATION COMPLETE")
    print("=" * 60 + "\n")

    return {
        "success": True,
        "entries_created": final_count,
        "main_domains": main_count,
        "supporting_domains": supporting_count,
        "skipped": skipped,
        "activity_logs_created": len(activity_logs),
        "mapping_file": mapping_file,
    }


async def main():
    parser = argparse.ArgumentParser(
        description="Phase 4 Migration: SEO Structure Entries"
    )
    parser.add_argument(
        "--execute", action="store_true", help="Execute migration (default is dry-run)"
    )
    args = parser.parse_args()

    db = await get_db()

    if args.execute:
        result = await execute_migration(db)
    else:
        result = await dry_run(db)

    return result


if __name__ == "__main__":
    asyncio.run(main())
