"""
Data Migration Script: Conflict Fingerprints & Status Cleanup
==============================================================

This script performs the following P0 migrations:

1. Backfill fingerprints for all existing conflicts
2. Set is_active = false for all 'approved' or 'resolved' conflicts  
3. Set first_detected_at from detected_at if missing
4. Initialize recurrence tracking fields

Run this once to fix historical data integrity issues.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_conflict_fingerprint(
    network_id: str,
    conflict_type: str,
    domain_id: str,
    node_path: str,
    tier: int,
    target_path: str
) -> str:
    """Generate unique fingerprint for conflict recurrence detection."""
    normalized_path = ""
    if node_path:
        normalized_path = node_path.lower().strip("/")
    
    normalized_target = ""
    if target_path:
        normalized_target = target_path.lower().strip("/")
    
    fingerprint_parts = [
        network_id or "",
        conflict_type or "",
        domain_id or "",
        normalized_path,
        str(tier) if tier is not None else "",
        normalized_target
    ]
    
    fingerprint_string = "|".join(fingerprint_parts)
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:32]


async def run_migration():
    """Execute the migration."""
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "seo_noc")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    logger.info("Starting conflict data migration...")
    
    # Stats
    stats = {
        "total_conflicts": 0,
        "fingerprints_added": 0,
        "status_fixed": 0,
        "first_detected_set": 0,
        "recurrence_reset": 0,
        "errors": 0
    }
    
    try:
        # Get all conflicts
        conflicts = await db.seo_conflicts.find({}, {"_id": 0}).to_list(10000)
        stats["total_conflicts"] = len(conflicts)
        
        logger.info(f"Found {len(conflicts)} conflicts to process")
        
        for conflict in conflicts:
            conflict_id = conflict.get("id")
            if not conflict_id:
                continue
            
            update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
            needs_update = False
            
            try:
                # 1. Generate and set fingerprint if missing
                if not conflict.get("fingerprint"):
                    fingerprint = generate_conflict_fingerprint(
                        network_id=conflict.get("network_id", ""),
                        conflict_type=conflict.get("conflict_type", ""),
                        domain_id=conflict.get("domain_id") or conflict.get("node_a_id", ""),
                        node_path=conflict.get("node_a_path", ""),
                        tier=conflict.get("node_a_tier"),
                        target_path=conflict.get("target_path") or conflict.get("node_b_path", "")
                    )
                    update_data["fingerprint"] = fingerprint
                    stats["fingerprints_added"] += 1
                    needs_update = True
                
                # 2. Fix is_active for resolved/approved conflicts
                status = conflict.get("status", "")
                is_active = conflict.get("is_active")
                
                if status in ("resolved", "approved") and is_active != False:
                    update_data["is_active"] = False
                    stats["status_fixed"] += 1
                    needs_update = True
                
                # 3. Set first_detected_at from detected_at if missing
                if not conflict.get("first_detected_at") and conflict.get("detected_at"):
                    update_data["first_detected_at"] = conflict.get("detected_at")
                    stats["first_detected_set"] += 1
                    needs_update = True
                
                # 4. Reset recurrence_count for resolved/approved conflicts
                if status in ("resolved", "approved") and conflict.get("recurrence_count", 0) > 0:
                    update_data["recurrence_count"] = 0
                    stats["recurrence_reset"] += 1
                    needs_update = True
                
                # 5. Initialize new fields with defaults if missing
                if conflict.get("is_false_resolution") is None:
                    update_data["is_false_resolution"] = False
                    needs_update = True
                
                if conflict.get("recurrence_history") is None:
                    update_data["recurrence_history"] = []
                    needs_update = True
                
                # Apply update if needed
                if needs_update:
                    await db.seo_conflicts.update_one(
                        {"id": conflict_id},
                        {"$set": update_data}
                    )
                    
            except Exception as e:
                logger.error(f"Error processing conflict {conflict_id}: {e}")
                stats["errors"] += 1
        
        logger.info("Migration completed successfully!")
        logger.info(f"Statistics: {stats}")
        
        return stats
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        client.close()


async def verify_migration():
    """Verify the migration was successful."""
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "seo_noc")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    try:
        # Check for conflicts without fingerprints
        no_fingerprint = await db.seo_conflicts.count_documents(
            {"fingerprint": {"$in": [None, ""]}}
        )
        
        # Check for resolved/approved conflicts that are still active
        still_active = await db.seo_conflicts.count_documents({
            "status": {"$in": ["resolved", "approved"]},
            "is_active": True
        })
        
        # Check for conflicts without first_detected_at
        no_first_detected = await db.seo_conflicts.count_documents({
            "first_detected_at": {"$in": [None, ""]},
            "detected_at": {"$exists": True}
        })
        
        logger.info("=== Migration Verification ===")
        logger.info(f"Conflicts without fingerprint: {no_fingerprint}")
        logger.info(f"Resolved/approved but still active: {still_active}")
        logger.info(f"Missing first_detected_at: {no_first_detected}")
        
        if no_fingerprint == 0 and still_active == 0 and no_first_detected == 0:
            logger.info("✅ Migration verified successfully!")
            return True
        else:
            logger.warning("⚠️ Migration incomplete - please run again")
            return False
            
    finally:
        client.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        asyncio.run(verify_migration())
    else:
        asyncio.run(run_migration())
        asyncio.run(verify_migration())
