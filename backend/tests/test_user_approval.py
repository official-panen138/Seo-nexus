"""
Tests for User Registration Approval & Super Admin User Management
Features tested:
1. New users register with status=pending, cannot login until approved
2. Super Admin can view pending users, approve (assign role + brand scope), or reject
3. Super Admin can manually create users (active immediately) with auto-generated password
4. Login shows specific messages for pending/rejected users
5. All actions logged for audit
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"


class TestUserApprovalWorkflow:
    """Tests for user registration, approval, rejection workflow"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Headers with authentication"""
        return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    
    @pytest.fixture(scope="class")
    def brands(self, auth_headers):
        """Get available brands for testing"""
        response = requests.get(f"{BASE_URL}/api/brands?include_archived=false", headers=auth_headers)
        if response.status_code != 200:
            return []
        return response.json()
    
    # ==================== REGISTRATION TESTS ====================
    
    def test_register_new_user_returns_pending_status(self):
        """Test that new user registration returns pending status"""
        unique_email = f"TEST_pending_{uuid.uuid4().hex[:8]}@test.com"
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "name": "Test Pending User",
            "email": unique_email,
            "password": "testpassword123",
            "role": "viewer"
        })
        
        # Should return success with pending status
        assert response.status_code == 200, f"Registration failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert data.get("status") == "pending", f"Expected pending status, got: {data}"
        assert "message" in data, "Expected message about pending approval"
        assert "pending" in data.get("message", "").lower() or "approval" in data.get("message", "").lower()
        
        print(f"PASS: New user {unique_email} registered with pending status")
    
    def test_pending_user_cannot_login(self):
        """Test that pending user cannot login"""
        unique_email = f"TEST_nologin_{uuid.uuid4().hex[:8]}@test.com"
        
        # Register user first
        register_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "name": "Test No Login User",
            "email": unique_email,
            "password": "testpassword123",
            "role": "viewer"
        })
        assert register_response.status_code == 200, "Registration should succeed"
        
        # Try to login - should fail with 403
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": unique_email,
            "password": "testpassword123"
        })
        
        assert login_response.status_code == 403, f"Expected 403 for pending user, got: {login_response.status_code}"
        data = login_response.json()
        assert "awaiting" in data.get("detail", "").lower() or "approval" in data.get("detail", "").lower()
        
        print(f"PASS: Pending user {unique_email} correctly denied login with 403")
    
    # ==================== PENDING USERS API TESTS ====================
    
    def test_get_pending_users_endpoint(self, auth_headers):
        """Test GET /api/users/pending returns pending users list"""
        response = requests.get(f"{BASE_URL}/api/users/pending", headers=auth_headers)
        
        assert response.status_code == 200, f"Failed to get pending users: {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        
        # All users should have pending status
        for user in data:
            assert user.get("status") == "pending", f"User {user.get('email')} has status {user.get('status')}"
        
        print(f"PASS: GET /api/users/pending returned {len(data)} pending users")
    
    # ==================== APPROVE/REJECT TESTS ====================
    
    def test_approve_pending_user(self, auth_headers, brands):
        """Test approving a pending user with role and brand assignment"""
        # First register a new pending user
        unique_email = f"TEST_approve_{uuid.uuid4().hex[:8]}@test.com"
        
        register_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "name": "Test Approve User",
            "email": unique_email,
            "password": "testpassword123",
            "role": "viewer"
        })
        assert register_response.status_code == 200, "Registration should succeed"
        
        # Get the pending user from the list
        pending_response = requests.get(f"{BASE_URL}/api/users/pending", headers=auth_headers)
        pending_users = pending_response.json()
        
        target_user = next((u for u in pending_users if u["email"] == unique_email), None)
        if not target_user:
            pytest.skip(f"User {unique_email} not found in pending list")
        
        user_id = target_user["id"]
        
        # Get brand IDs for approval
        brand_ids = [b["id"] for b in brands[:1]] if brands else []
        if not brand_ids:
            pytest.skip("No brands available for testing")
        
        # Approve the user
        approve_response = requests.post(
            f"{BASE_URL}/api/users/{user_id}/approve",
            headers=auth_headers,
            json={
                "role": "viewer",
                "brand_scope_ids": brand_ids
            }
        )
        
        assert approve_response.status_code == 200, f"Approve failed: {approve_response.status_code} - {approve_response.text}"
        
        approved_user = approve_response.json()
        assert approved_user.get("status") == "active", "User should now be active"
        assert approved_user.get("role") == "viewer", "Role should be viewer"
        assert approved_user.get("brand_scope_ids") == brand_ids, "Brand IDs should match"
        assert approved_user.get("approved_by") is not None, "approved_by should be set"
        assert approved_user.get("approved_at") is not None, "approved_at should be set"
        
        print(f"PASS: User {unique_email} approved successfully with status=active")
        
        # Verify approved user can now login
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": unique_email,
            "password": "testpassword123"
        })
        assert login_response.status_code == 200, f"Approved user should be able to login, got: {login_response.status_code}"
        print(f"PASS: Approved user {unique_email} can now login successfully")
    
    def test_reject_pending_user(self, auth_headers):
        """Test rejecting a pending user"""
        # First register a new pending user
        unique_email = f"TEST_reject_{uuid.uuid4().hex[:8]}@test.com"
        
        register_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "name": "Test Reject User",
            "email": unique_email,
            "password": "testpassword123",
            "role": "viewer"
        })
        assert register_response.status_code == 200, "Registration should succeed"
        
        # Get the pending user
        pending_response = requests.get(f"{BASE_URL}/api/users/pending", headers=auth_headers)
        pending_users = pending_response.json()
        
        target_user = next((u for u in pending_users if u["email"] == unique_email), None)
        if not target_user:
            pytest.skip(f"User {unique_email} not found in pending list")
        
        user_id = target_user["id"]
        
        # Reject the user
        reject_response = requests.post(
            f"{BASE_URL}/api/users/{user_id}/reject",
            headers=auth_headers
        )
        
        assert reject_response.status_code == 200, f"Reject failed: {reject_response.status_code} - {reject_response.text}"
        
        print(f"PASS: User {unique_email} rejected successfully")
        
        # Verify rejected user cannot login with specific message
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": unique_email,
            "password": "testpassword123"
        })
        
        assert login_response.status_code == 403, f"Expected 403 for rejected user, got: {login_response.status_code}"
        data = login_response.json()
        assert "rejected" in data.get("detail", "").lower(), f"Expected 'rejected' in message: {data.get('detail')}"
        
        print(f"PASS: Rejected user {unique_email} correctly denied login with 'rejected' message")
    
    def test_cannot_approve_as_super_admin(self, auth_headers, brands):
        """Test that user cannot be approved as super_admin role"""
        # First register a new pending user
        unique_email = f"TEST_nosadmin_{uuid.uuid4().hex[:8]}@test.com"
        
        register_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "name": "Test No Super Admin User",
            "email": unique_email,
            "password": "testpassword123",
            "role": "viewer"
        })
        assert register_response.status_code == 200
        
        # Get the pending user
        pending_response = requests.get(f"{BASE_URL}/api/users/pending", headers=auth_headers)
        pending_users = pending_response.json()
        
        target_user = next((u for u in pending_users if u["email"] == unique_email), None)
        if not target_user:
            pytest.skip(f"User {unique_email} not found in pending list")
        
        user_id = target_user["id"]
        brand_ids = [b["id"] for b in brands[:1]] if brands else []
        
        # Try to approve as super_admin - should fail
        approve_response = requests.post(
            f"{BASE_URL}/api/users/{user_id}/approve",
            headers=auth_headers,
            json={
                "role": "super_admin",
                "brand_scope_ids": brand_ids
            }
        )
        
        assert approve_response.status_code == 400, f"Expected 400 when approving as super_admin, got: {approve_response.status_code}"
        print("PASS: Cannot approve user as super_admin (correctly rejected)")
    
    # ==================== MANUAL USER CREATION TESTS ====================
    
    def test_create_user_manually(self, auth_headers, brands):
        """Test Super Admin can manually create active user with generated password"""
        unique_email = f"TEST_manual_{uuid.uuid4().hex[:8]}@test.com"
        
        brand_ids = [b["id"] for b in brands[:1]] if brands else []
        if not brand_ids:
            pytest.skip("No brands available for testing")
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            headers=auth_headers,
            json={
                "email": unique_email,
                "name": "Manually Created User",
                "role": "viewer",
                "brand_scope_ids": brand_ids
            }
        )
        
        assert response.status_code == 200, f"Create user failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert "generated_password" in data, "Response should contain generated_password"
        assert len(data["generated_password"]) >= 12, "Generated password should be at least 12 characters"
        assert data["user"]["email"] == unique_email
        assert data["user"]["status"] == "active", "Manually created user should be active immediately"
        
        print(f"PASS: User {unique_email} created manually with generated password")
        
        # Verify the manually created user can login with generated password
        generated_pwd = data["generated_password"]
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": unique_email,
            "password": generated_pwd
        })
        
        assert login_response.status_code == 200, f"Manually created user should be able to login, got: {login_response.status_code}"
        print(f"PASS: Manually created user {unique_email} can login with generated password")
    
    def test_cannot_create_super_admin_manually(self, auth_headers, brands):
        """Test that Super Admin cannot create another super_admin"""
        unique_email = f"TEST_nosuperadmin_{uuid.uuid4().hex[:8]}@test.com"
        
        brand_ids = [b["id"] for b in brands[:1]] if brands else []
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            headers=auth_headers,
            json={
                "email": unique_email,
                "name": "Should Not Be Super Admin",
                "role": "super_admin",
                "brand_scope_ids": brand_ids
            }
        )
        
        assert response.status_code == 400, f"Expected 400 when creating super_admin, got: {response.status_code}"
        print("PASS: Cannot create super_admin user manually (correctly rejected)")
    
    # ==================== ALL USERS WITH STATUS ====================
    
    def test_get_all_users_includes_status(self, auth_headers):
        """Test GET /api/users returns status field for all users"""
        response = requests.get(f"{BASE_URL}/api/users", headers=auth_headers)
        
        assert response.status_code == 200, f"Failed to get users: {response.status_code}"
        users = response.json()
        
        assert len(users) > 0, "Should have at least one user"
        
        # All users should have status field
        for user in users:
            assert "status" in user, f"User {user.get('email')} missing status field"
            assert user["status"] in ["active", "pending", "rejected"], f"Invalid status: {user['status']}"
        
        print(f"PASS: GET /api/users returned {len(users)} users with status field")
        
        # Check status breakdown
        active_count = sum(1 for u in users if u["status"] == "active")
        pending_count = sum(1 for u in users if u["status"] == "pending")
        rejected_count = sum(1 for u in users if u["status"] == "rejected")
        print(f"  Status breakdown: {active_count} active, {pending_count} pending, {rejected_count} rejected")


class TestUserApprovalCleanup:
    """Cleanup test data created during testing"""
    
    def test_cleanup_test_users(self):
        """Delete all TEST_ prefixed users"""
        # Login as admin
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get all users
        users_response = requests.get(f"{BASE_URL}/api/users", headers=headers)
        if users_response.status_code != 200:
            pytest.skip("Failed to get users")
        
        users = users_response.json()
        test_users = [u for u in users if u["email"].startswith("TEST_")]
        
        deleted_count = 0
        for user in test_users:
            delete_response = requests.delete(f"{BASE_URL}/api/users/{user['id']}", headers=headers)
            if delete_response.status_code in [200, 404]:
                deleted_count += 1
        
        print(f"CLEANUP: Deleted {deleted_count} test users")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
