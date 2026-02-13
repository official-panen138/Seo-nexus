#!/usr/bin/env python3
"""
Quick Super Admin Creator for SEO-NOC
Run: python3 create_superadmin.py

This script creates or upgrades a user to Super Admin.
"""

import os
import sys

# Check if pymongo is installed
try:
    from pymongo import MongoClient
except ImportError:
    print("Installing pymongo...")
    os.system("pip3 install pymongo")
    from pymongo import MongoClient

try:
    import bcrypt
except ImportError:
    print("Installing bcrypt...")
    os.system("pip3 install bcrypt")
    import bcrypt

from datetime import datetime, timezone
import uuid

def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def main():
    # Configuration
    MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    DB_NAME = os.environ.get("DB_NAME", "test_database")
    
    print("=" * 50)
    print("SEO-NOC Super Admin Creator")
    print("=" * 50)
    
    # Get email from user
    email = input("Enter email for Super Admin: ").strip()
    if not email:
        print("Error: Email is required!")
        sys.exit(1)
    
    password = input("Enter password (or press Enter for 'Admin@123!'): ").strip()
    if not password:
        password = "Admin@123!"
    
    name = input("Enter name (or press Enter for 'Super Admin'): ").strip()
    if not name:
        name = "Super Admin"
    
    # Connect to MongoDB
    print(f"\nConnecting to MongoDB: {MONGO_URL}")
    print(f"Database: {DB_NAME}")
    
    try:
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        
        # Check if user exists
        existing = db.users.find_one({"email": email})
        
        if existing:
            print(f"\nUser '{email}' already exists.")
            print("Upgrading to Super Admin...")
            
            result = db.users.update_one(
                {"email": email},
                {"$set": {
                    "role": "super_admin",
                    "status": "active",
                    "brand_scope_ids": None,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            
            if result.modified_count > 0:
                print("SUCCESS! User upgraded to Super Admin.")
            else:
                print("User already is Super Admin (no changes needed).")
        else:
            print(f"\nCreating new Super Admin user...")
            
            new_user = {
                "id": str(uuid.uuid4()),
                "email": email,
                "name": name,
                "password": hash_password(password),
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
            
            db.users.insert_one(new_user)
            print("SUCCESS! Super Admin created.")
        
        print("\n" + "=" * 50)
        print("LOGIN CREDENTIALS")
        print("=" * 50)
        print(f"Email:    {email}")
        print(f"Password: {password}")
        print("=" * 50)
        print("\nYou can now login to the website!")
        
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    main()
