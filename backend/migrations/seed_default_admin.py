"""
Default Super Admin Seeder for SEO-NOC
Run this script during deployment or migration to ensure a default super admin exists.

Usage:
    python migrations/seed_default_admin.py

Environment Variables (optional):
    DEFAULT_ADMIN_EMAIL - Default: admin@seonoc.local
    DEFAULT_ADMIN_PASSWORD - Default: Admin@123!
    DEFAULT_ADMIN_NAME - Default: Super Admin
"""

import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timezone
import uuid
import bcrypt

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load environment variables
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")

# Default Super Admin credentials (can be overridden by environment variables)
DEFAULT_ADMIN_EMAIL = os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@seonoc.com")
DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "Admin@123!")
DEFAULT_ADMIN_NAME = os.environ.get("DEFAULT_ADMIN_NAME", "Super Admin")


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def seed_default_admin():
    """
    Seed default super admin user if no users exist or no super_admin exists.
    This is safe to run multiple times - it won't create duplicates.
    """
    # MongoDB connection
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print(f"=" * 60)
    print("SEO-NOC Default Super Admin Seeder")
    print(f"=" * 60)
    print(f"Database: {db_name}")
    print(f"Default Email: {DEFAULT_ADMIN_EMAIL}")
    print()
    
    try:
        # Check if any super_admin exists
        existing_super_admin = await db.users.find_one({"role": "super_admin"})
        
        if existing_super_admin:
            print(f"[INFO] Super Admin already exists: {existing_super_admin.get('email')}")
            print("[SKIP] No action needed.")
            return True
        
        # Check if the default admin email already exists
        existing_user = await db.users.find_one({"email": DEFAULT_ADMIN_EMAIL})
        
        if existing_user:
            # User exists but is not super_admin - upgrade to super_admin
            print(f"[INFO] User {DEFAULT_ADMIN_EMAIL} exists but is not Super Admin")
            print("[ACTION] Upgrading user to Super Admin role...")
            
            await db.users.update_one(
                {"email": DEFAULT_ADMIN_EMAIL},
                {
                    "$set": {
                        "role": "super_admin",
                        "status": "active",
                        "brand_scope_ids": None,  # Full access
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            print(f"[SUCCESS] User upgraded to Super Admin!")
            return True
        
        # Create new default super admin
        print("[ACTION] Creating default Super Admin user...")
        
        now = datetime.now(timezone.utc).isoformat()
        new_admin = {
            "id": str(uuid.uuid4()),
            "email": DEFAULT_ADMIN_EMAIL,
            "name": DEFAULT_ADMIN_NAME,
            "password": hash_password(DEFAULT_ADMIN_PASSWORD),
            "role": "super_admin",
            "status": "active",
            "brand_scope_ids": None,  # Super Admin has full access
            "telegram_username": None,
            "created_at": now,
            "updated_at": now,
            "approved_by": "system",
            "approved_at": now,
            "menu_permissions": None  # Uses default permissions
        }
        
        await db.users.insert_one(new_admin)
        
        print(f"[SUCCESS] Default Super Admin created!")
        print()
        print(f"{'=' * 60}")
        print("LOGIN CREDENTIALS")
        print(f"{'=' * 60}")
        print(f"Email:    {DEFAULT_ADMIN_EMAIL}")
        print(f"Password: {DEFAULT_ADMIN_PASSWORD}")
        print(f"{'=' * 60}")
        print()
        print("[WARNING] Please change the default password after first login!")
        print()
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to seed default admin: {e}")
        return False
    finally:
        client.close()


async def main():
    """Main entry point"""
    success = await seed_default_admin()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
