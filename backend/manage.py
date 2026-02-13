#!/usr/bin/env python3
"""
SEO-NOC Management CLI
======================
Admin management tool for Docker/VPS deployments.

Usage inside Docker:
  docker exec -it <container_name> python3 manage.py create-super-admin --email admin@example.com --password MyPass123!
  docker exec -it <container_name> python3 manage.py reset-password --email admin@example.com --password NewPass123!
  docker exec -it <container_name> python3 manage.py promote-user --email user@example.com
  docker exec -it <container_name> python3 manage.py list-users

Usage locally:
  python3 manage.py create-super-admin --email admin@example.com --password MyPass123!
"""

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone

from pymongo import MongoClient
import bcrypt

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def get_db():
    client = MongoClient(MONGO_URL)
    return client, client[DB_NAME]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def cmd_create_super_admin(args):
    """Create a new Super Admin or upgrade existing user."""
    client, db = get_db()
    try:
        email = args.email
        password = args.password or "Admin@123!"
        name = args.name or "Super Admin"

        existing = db.users.find_one({"email": email})
        now = datetime.now(timezone.utc).isoformat()

        if existing:
            db.users.update_one(
                {"email": email},
                {"$set": {
                    "role": "super_admin",
                    "status": "active",
                    "password": hash_password(password),
                    "brand_scope_ids": None,
                    "updated_at": now,
                }},
            )
            print(f"[OK] User '{email}' upgraded to Super Admin with new password.")
        else:
            db.users.insert_one({
                "id": str(uuid.uuid4()),
                "email": email,
                "name": name,
                "password": hash_password(password),
                "role": "super_admin",
                "status": "active",
                "brand_scope_ids": None,
                "telegram_username": None,
                "created_at": now,
                "updated_at": now,
                "approved_by": "system:manage_cli",
                "approved_at": now,
                "menu_permissions": None,
            })
            print(f"[OK] Super Admin created: {email}")

        print(f"  Email:    {email}")
        print(f"  Password: {password}")
    finally:
        client.close()


def cmd_reset_password(args):
    """Reset a user's password."""
    client, db = get_db()
    try:
        email = args.email
        password = args.password

        user = db.users.find_one({"email": email})
        if not user:
            print(f"[ERROR] User '{email}' not found.")
            sys.exit(1)

        db.users.update_one(
            {"email": email},
            {"$set": {
                "password": hash_password(password),
                "status": "active",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        print(f"[OK] Password reset for '{email}'. Status set to active.")
        print(f"  New Password: {password}")
    finally:
        client.close()


def cmd_promote_user(args):
    """Promote an existing user to Super Admin."""
    client, db = get_db()
    try:
        email = args.email
        user = db.users.find_one({"email": email})
        if not user:
            print(f"[ERROR] User '{email}' not found.")
            sys.exit(1)

        if user.get("role") == "super_admin":
            print(f"[INFO] '{email}' is already a Super Admin.")
            return

        db.users.update_one(
            {"email": email},
            {"$set": {
                "role": "super_admin",
                "status": "active",
                "brand_scope_ids": None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        print(f"[OK] '{email}' promoted to Super Admin.")
    finally:
        client.close()


def cmd_list_users(args):
    """List all users with their roles and statuses."""
    client, db = get_db()
    try:
        users = list(db.users.find({}, {"_id": 0, "password": 0}).sort("role", 1))
        if not users:
            print("[INFO] No users found.")
            return

        print(f"\n{'Email':<35} {'Role':<15} {'Status':<12} {'Name'}")
        print("-" * 90)
        for u in users:
            print(f"{u.get('email',''):<35} {u.get('role',''):<15} {u.get('status','active'):<12} {u.get('name','')}")
        print(f"\nTotal: {len(users)} users")
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(
        prog="manage.py",
        description="SEO-NOC Management CLI for Docker/VPS deployments",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # create-super-admin
    p_create = subparsers.add_parser("create-super-admin", help="Create or reset a Super Admin account")
    p_create.add_argument("--email", required=True, help="Email address")
    p_create.add_argument("--password", default=None, help="Password (default: Admin@123!)")
    p_create.add_argument("--name", default=None, help="Display name (default: Super Admin)")
    p_create.set_defaults(func=cmd_create_super_admin)

    # reset-password
    p_reset = subparsers.add_parser("reset-password", help="Reset a user's password")
    p_reset.add_argument("--email", required=True, help="Email address")
    p_reset.add_argument("--password", required=True, help="New password")
    p_reset.set_defaults(func=cmd_reset_password)

    # promote-user
    p_promote = subparsers.add_parser("promote-user", help="Promote a user to Super Admin")
    p_promote.add_argument("--email", required=True, help="Email to promote")
    p_promote.set_defaults(func=cmd_promote_user)

    # list-users
    p_list = subparsers.add_parser("list-users", help="List all users")
    p_list.set_defaults(func=cmd_list_users)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
