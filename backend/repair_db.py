#!/usr/bin/env python3
"""
Database Repair Script for SEO-NOC
Fixes user records and creates a working super admin.

Copy this file to your VPS and run inside Docker:
docker cp repair_db.py seo-noc-backend:/app/repair_db.py
docker exec -it seo-noc-backend python3 /app/repair_db.py
"""

import os
import sys
from datetime import datetime, timezone
import uuid

try:
    from pymongo import MongoClient
    import bcrypt
except ImportError:
    print("Installing required packages...")
    os.system("pip install pymongo bcrypt")
    from pymongo import MongoClient
    import bcrypt

# MongoDB connection - update if needed
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://seonoc_app:5pNGjLPc5h5O@mongodb:27017/seo_noc?authSource=seo_noc")
DB_NAME = "seo_noc"

def repair_database():
    print("=" * 60)
    print("SEO-NOC Database Repair Tool")
    print("=" * 60)
    
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Step 1: Delete all users (fresh start)
    print("\n[Step 1] Clearing all users...")
    result = db.users.delete_many({})
    print(f"Deleted {result.deleted_count} users")
    
    # Step 2: Create fresh super admin
    print("\n[Step 2] Creating Super Admin...")
    
    admin_email = "admin@seonoc.com"
    admin_password = "password123"
    
    password_hash = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    admin_user = {
        "id": str(uuid.uuid4()),
        "email": admin_email,
        "name": "Super Admin",
        "password": password_hash,
        "role": "super_admin",
        "status": "active",
        "brand_scope_ids": None,
        "telegram_username": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "approved_by": "system",
        "approved_at": datetime.now(timezone.utc),
        "menu_permissions": None
    }
    
    db.users.insert_one(admin_user)
    print(f"Created Super Admin: {admin_email}")
    
    # Step 3: Verify
    print("\n[Step 3] Verifying...")
    user = db.users.find_one({"email": admin_email})
    if user:
        # Test password
        test_result = bcrypt.checkpw(admin_password.encode('utf-8'), user['password'].encode('utf-8'))
        print(f"User exists: YES")
        print(f"Password verification: {'PASS' if test_result else 'FAIL'}")
        print(f"User ID: {user.get('id')}")
        print(f"Role: {user.get('role')}")
        print(f"Status: {user.get('status')}")
    
    print("\n" + "=" * 60)
    print("REPAIR COMPLETE!")
    print("=" * 60)
    print(f"\nLogin credentials:")
    print(f"  Email:    {admin_email}")
    print(f"  Password: {admin_password}")
    print("\n" + "=" * 60)
    
    client.close()

if __name__ == "__main__":
    repair_database()
