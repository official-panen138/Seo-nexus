#!/usr/bin/env python3
"""
Database Performance Optimization Script for SEO-NOC
Run this script after deployment to create all necessary indexes.

Usage on VPS:
docker cp optimize_db.py seo-noc-backend:/app/optimize_db.py
docker exec -it seo-noc-backend python3 /app/optimize_db.py
"""

import os
from pymongo import MongoClient, ASCENDING, DESCENDING

# MongoDB connection - update if needed
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://seonoc_app:5pNGjLPc5h5O@mongodb:27017/seo_noc?authSource=seo_noc")

def create_indexes():
    print("=" * 60)
    print("SEO-NOC Database Performance Optimizer")
    print("=" * 60)
    
    client = MongoClient(MONGO_URL)
    db = client.get_database()
    
    print(f"\nConnected to: {db.name}")
    print("\nCreating indexes...")
    
    # Users indexes
    print("\n[1/10] Users collection...")
    db.users.create_index("email", unique=True, background=True)
    db.users.create_index("id", unique=True, background=True)
    db.users.create_index("role", background=True)
    db.users.create_index("status", background=True)
    print("  ✓ Users indexes created")

    # Brands indexes
    print("[2/10] Brands collection...")
    db.brands.create_index("id", unique=True, background=True)
    db.brands.create_index("status", background=True)
    db.brands.create_index("name", background=True)
    print("  ✓ Brands indexes created")

    # Asset domains indexes
    print("[3/10] Asset domains collection...")
    db.asset_domains.create_index("id", unique=True, background=True)
    db.asset_domains.create_index("domain_name", background=True)
    db.asset_domains.create_index("brand_id", background=True)
    db.asset_domains.create_index("category_id", background=True)
    db.asset_domains.create_index("registrar_id", background=True)
    db.asset_domains.create_index("status", background=True)
    db.asset_domains.create_index("lifecycle_status", background=True)
    db.asset_domains.create_index("monitoring_status", background=True)
    db.asset_domains.create_index("monitoring_enabled", background=True)
    db.asset_domains.create_index("domain_active_status", background=True)
    db.asset_domains.create_index("created_at", background=True)
    db.asset_domains.create_index("expiration_date", background=True)
    db.asset_domains.create_index([("brand_id", ASCENDING), ("domain_name", ASCENDING)], background=True)
    db.asset_domains.create_index([("brand_id", ASCENDING), ("created_at", DESCENDING)], background=True)
    db.asset_domains.create_index([("lifecycle_status", ASCENDING), ("monitoring_status", ASCENDING)], background=True)
    print("  ✓ Asset domains indexes created")

    # SEO Networks indexes
    print("[4/10] SEO Networks collection...")
    db.seo_networks.create_index("id", unique=True, background=True)
    db.seo_networks.create_index("brand_id", background=True)
    db.seo_networks.create_index("name", background=True)
    db.seo_networks.create_index("status", background=True)
    db.seo_networks.create_index("created_at", background=True)
    db.seo_networks.create_index([("brand_id", ASCENDING), ("created_at", DESCENDING)], background=True)
    print("  ✓ SEO Networks indexes created")

    # SEO Structure entries indexes
    print("[5/10] SEO Structure entries collection...")
    db.seo_structure_entries.create_index("id", unique=True, background=True)
    db.seo_structure_entries.create_index("network_id", background=True)
    db.seo_structure_entries.create_index("asset_domain_id", background=True)
    db.seo_structure_entries.create_index("tier", background=True)
    db.seo_structure_entries.create_index("domain_role", background=True)
    db.seo_structure_entries.create_index([("network_id", ASCENDING), ("asset_domain_id", ASCENDING)], background=True)
    db.seo_structure_entries.create_index([("network_id", ASCENDING), ("domain_role", ASCENDING)], background=True)
    print("  ✓ SEO Structure entries indexes created")

    # SEO Optimizations indexes
    print("[6/10] SEO Optimizations collection...")
    db.seo_optimizations.create_index("id", unique=True, background=True)
    db.seo_optimizations.create_index("network_id", background=True)
    db.seo_optimizations.create_index("brand_id", background=True)
    db.seo_optimizations.create_index("status", background=True)
    db.seo_optimizations.create_index("created_at", background=True)
    db.seo_optimizations.create_index([("network_id", ASCENDING), ("created_at", DESCENDING)], background=True)
    db.seo_optimizations.create_index([("brand_id", ASCENDING), ("status", ASCENDING)], background=True)
    print("  ✓ SEO Optimizations indexes created")

    # SEO Conflicts indexes
    print("[7/10] SEO Conflicts collection...")
    db.seo_conflicts.create_index("id", unique=True, background=True)
    db.seo_conflicts.create_index("network_id", background=True)
    db.seo_conflicts.create_index("status", background=True)
    db.seo_conflicts.create_index("severity", background=True)
    db.seo_conflicts.create_index("detected_at", background=True)
    db.seo_conflicts.create_index("created_at", background=True)
    db.seo_conflicts.create_index([("network_id", ASCENDING), ("status", ASCENDING)], background=True)
    db.seo_conflicts.create_index([("status", ASCENDING), ("severity", ASCENDING)], background=True)
    print("  ✓ SEO Conflicts indexes created")

    # Activity logs indexes
    print("[8/10] Activity logs collection...")
    db.activity_logs.create_index("created_at", background=True)
    db.activity_logs.create_index("user_id", background=True)
    db.activity_logs.create_index("entity_type", background=True)
    db.activity_logs.create_index("action", background=True)
    db.activity_logs.create_index([("created_at", DESCENDING)], background=True)
    print("  ✓ Activity logs indexes created")

    # Audit logs indexes
    print("[9/10] Audit logs collection...")
    db.audit_logs.create_index("timestamp", background=True)
    db.audit_logs.create_index("user_id", background=True)
    db.audit_logs.create_index([("timestamp", DESCENDING)], background=True)
    print("  ✓ Audit logs indexes created")

    # Categories and Registrars indexes
    print("[10/10] Categories & Registrars collections...")
    db.categories.create_index("id", unique=True, background=True)
    db.categories.create_index("name", background=True)
    db.registrars.create_index("id", unique=True, background=True)
    db.registrars.create_index("name", background=True)
    print("  ✓ Categories & Registrars indexes created")

    print("\n" + "=" * 60)
    print("✅ ALL INDEXES CREATED SUCCESSFULLY!")
    print("=" * 60)
    
    # Show collection statistics
    print("\n📊 Collection Statistics:")
    collections = ['users', 'brands', 'asset_domains', 'seo_networks', 
                   'seo_structure_entries', 'seo_optimizations', 'seo_conflicts']
    for coll_name in collections:
        count = db[coll_name].count_documents({})
        indexes = len(list(db[coll_name].list_indexes()))
        print(f"  {coll_name}: {count} docs, {indexes} indexes")
    
    client.close()
    print("\n✅ Done!")

if __name__ == "__main__":
    create_indexes()
