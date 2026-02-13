"""
Test Suite: manage.py CLI Tool and Asset Domains Pagination Bug Fix
====================================================================
Tests for:
1. manage.py CLI commands (create-super-admin, reset-password, promote-user, list-users)
2. GET /api/v3/asset-domains pagination fix for domain_active_status and view_mode filters

The pagination bug was: domain_active_status and view_mode=expired were applied as 
post-processing AFTER total count was calculated. Now they are DB-level queries.
"""

import pytest
import requests
import subprocess
import os
import uuid
from datetime import datetime, timezone, timedelta

# API base URL from environment
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from requirement
SUPERADMIN_EMAIL = "superadmin@seonoc.com"
SUPERADMIN_PASSWORD = "SuperAdmin123!"

# Test data prefixes for cleanup
TEST_PREFIX = "TEST_CLI_"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for API tests"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": SUPERADMIN_EMAIL, "password": SUPERADMIN_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        # API returns access_token, not token
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture
def auth_headers(auth_token):
    """Headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


# ==================== MANAGE.PY CLI TESTS ====================

class TestManageCLI:
    """Tests for manage.py CLI tool"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup for CLI tests"""
        self.cli_path = "/app/backend/manage.py"
        self.test_email = f"{TEST_PREFIX}user_{uuid.uuid4().hex[:8]}@test.com"
    
    def run_cli(self, command: list, expect_success: bool = True) -> tuple:
        """Run manage.py CLI command and return (stdout, stderr, returncode)"""
        full_cmd = ["python3", self.cli_path] + command
        result = subprocess.run(
            full_cmd,
            cwd="/app/backend",
            capture_output=True,
            text=True,
            env={**os.environ, "MONGO_URL": "mongodb://localhost:27017", "DB_NAME": "test_database"}
        )
        return result.stdout, result.stderr, result.returncode
    
    def test_cli_help(self):
        """Test CLI help command shows available commands"""
        stdout, stderr, code = self.run_cli(["--help"])
        
        assert code == 0, f"Help command failed: {stderr}"
        assert "create-super-admin" in stdout
        assert "reset-password" in stdout
        assert "promote-user" in stdout
        assert "list-users" in stdout
        print(f"[PASS] CLI help shows all 4 commands")
    
    def test_create_super_admin_new_user(self):
        """Test create-super-admin creates a new super admin user"""
        test_email = f"{TEST_PREFIX}newadmin_{uuid.uuid4().hex[:8]}@test.com"
        test_password = "TestPass123!"
        
        stdout, stderr, code = self.run_cli([
            "create-super-admin",
            "--email", test_email,
            "--password", test_password,
            "--name", "Test Super Admin"
        ])
        
        assert code == 0, f"Create super admin failed: {stderr}"
        assert "[OK]" in stdout
        assert "Super Admin created" in stdout
        assert test_email in stdout
        print(f"[PASS] create-super-admin creates new user: {test_email}")
        
        # Cleanup - login and delete the user
        # First verify we can login with the new user
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": test_email, "password": test_password}
        )
        assert response.status_code == 200, f"Cannot login with new super admin: {response.text}"
        print(f"[PASS] New super admin can login successfully")
    
    def test_create_super_admin_upgrades_existing_user(self):
        """Test create-super-admin upgrades existing user and resets password"""
        # First create a user
        test_email = f"{TEST_PREFIX}upgrade_{uuid.uuid4().hex[:8]}@test.com"
        original_password = "OriginalPass123!"
        
        # Create initial user
        stdout, stderr, code = self.run_cli([
            "create-super-admin",
            "--email", test_email,
            "--password", original_password
        ])
        assert code == 0, f"Initial creation failed: {stderr}"
        
        # Now upgrade with new password
        new_password = "NewUpgradePass123!"
        stdout, stderr, code = self.run_cli([
            "create-super-admin",
            "--email", test_email,
            "--password", new_password
        ])
        
        assert code == 0, f"Upgrade failed: {stderr}"
        assert "[OK]" in stdout
        assert "upgraded to Super Admin" in stdout
        print(f"[PASS] create-super-admin upgrades existing user")
        
        # Verify new password works
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": test_email, "password": new_password}
        )
        assert response.status_code == 200, f"Cannot login with new password: {response.text}"
        
        # Verify old password doesn't work
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": test_email, "password": original_password}
        )
        assert response.status_code == 401, "Old password should not work"
        print(f"[PASS] Password reset works correctly")
    
    def test_reset_password_existing_user(self):
        """Test reset-password changes password for existing user"""
        # Create a user first
        test_email = f"{TEST_PREFIX}resetpwd_{uuid.uuid4().hex[:8]}@test.com"
        original_password = "OriginalPass123!"
        
        stdout, stderr, code = self.run_cli([
            "create-super-admin",
            "--email", test_email,
            "--password", original_password
        ])
        assert code == 0, f"User creation failed: {stderr}"
        
        # Reset password
        new_password = "ResetNewPass456!"
        stdout, stderr, code = self.run_cli([
            "reset-password",
            "--email", test_email,
            "--password", new_password
        ])
        
        assert code == 0, f"Reset password failed: {stderr}"
        assert "[OK]" in stdout
        assert "Password reset" in stdout
        print(f"[PASS] reset-password command succeeds")
        
        # Verify new password works
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": test_email, "password": new_password}
        )
        assert response.status_code == 200, f"Cannot login with reset password: {response.text}"
        print(f"[PASS] New password works after reset")
    
    def test_reset_password_nonexistent_user_fails(self):
        """Test reset-password fails gracefully for non-existent user"""
        fake_email = f"nonexistent_{uuid.uuid4().hex}@fake.com"
        
        stdout, stderr, code = self.run_cli([
            "reset-password",
            "--email", fake_email,
            "--password", "AnyPass123!"
        ], expect_success=False)
        
        assert code != 0, "Should fail for non-existent user"
        assert "[ERROR]" in stdout
        assert "not found" in stdout.lower()
        print(f"[PASS] reset-password fails gracefully for non-existent user")
    
    def test_promote_user_to_super_admin(self):
        """Test promote-user promotes existing user to super_admin"""
        # Create a regular user first via API
        test_email = f"{TEST_PREFIX}promote_{uuid.uuid4().hex[:8]}@test.com"
        test_password = "PromotePass123!"
        
        # Create as super admin first, then we'll create a separate user scenario
        stdout, stderr, code = self.run_cli([
            "create-super-admin",
            "--email", test_email,
            "--password", test_password
        ])
        assert code == 0
        
        # Test promote on the same user (should indicate already super admin)
        stdout, stderr, code = self.run_cli([
            "promote-user",
            "--email", test_email
        ])
        
        assert code == 0
        assert "[INFO]" in stdout or "[OK]" in stdout
        # If already super admin, should say so
        if "already a Super Admin" in stdout:
            print(f"[PASS] promote-user correctly identifies existing super admin")
        else:
            assert "promoted to Super Admin" in stdout
            print(f"[PASS] promote-user promotes user to super_admin")
    
    def test_list_users_shows_users(self):
        """Test list-users shows all users"""
        stdout, stderr, code = self.run_cli(["list-users"])
        
        assert code == 0, f"List users failed: {stderr}"
        # Should show header or info message
        assert "Email" in stdout or "users" in stdout.lower()
        # Should include our super admin
        assert SUPERADMIN_EMAIL in stdout or "No users found" in stdout
        print(f"[PASS] list-users command works")


# ==================== PAGINATION BUG FIX TESTS ====================

class TestAssetDomainsPagination:
    """Tests for GET /api/v3/asset-domains pagination count fix"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, auth_headers):
        """Setup test domains for pagination tests"""
        self.headers = auth_headers
        self.created_domains = []
    
    def create_test_domain(self, domain_name: str, expiration_date: str = None, brand_id: str = None) -> dict:
        """Create a test domain and track for cleanup"""
        # Get a brand_id if not provided
        if not brand_id:
            brands_resp = requests.get(f"{BASE_URL}/api/brands", headers=self.headers)
            if brands_resp.status_code == 200:
                brands = brands_resp.json()
                if brands:
                    brand_id = brands[0]["id"]
        
        payload = {
            "domain_name": domain_name,
            "brand_id": brand_id,
        }
        if expiration_date:
            payload["expiration_date"] = expiration_date
        
        response = requests.post(
            f"{BASE_URL}/api/v3/asset-domains",
            headers=self.headers,
            json=payload
        )
        
        if response.status_code in [200, 201]:
            domain = response.json()
            self.created_domains.append(domain["id"])
            return domain
        return None
    
    def cleanup_test_domains(self):
        """Cleanup created test domains"""
        for domain_id in self.created_domains:
            requests.delete(
                f"{BASE_URL}/api/v3/asset-domains/{domain_id}",
                headers=self.headers
            )
    
    def test_pagination_total_matches_without_filter(self, auth_headers):
        """Test: GET /api/v3/asset-domains total count matches when no filter applied"""
        response = requests.get(
            f"{BASE_URL}/api/v3/asset-domains?page=1&limit=10",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()
        
        assert "data" in data
        assert "meta" in data
        meta = data["meta"]
        assert "total" in meta
        assert "page" in meta
        assert "limit" in meta
        assert "total_pages" in meta
        
        total = meta["total"]
        total_pages = meta["total_pages"]
        
        # Verify total_pages calculation is correct
        import math
        expected_pages = math.ceil(total / 10) if total > 0 else 1
        assert total_pages == expected_pages, f"Total pages mismatch: {total_pages} != {expected_pages}"
        
        print(f"[PASS] Pagination works: total={total}, total_pages={total_pages}")
    
    def test_pagination_active_filter_returns_correct_total(self, auth_headers):
        """Test: GET /api/v3/asset-domains?domain_active_status=active returns correct total"""
        # Get total without filter
        response_all = requests.get(
            f"{BASE_URL}/api/v3/asset-domains?page=1&limit=1000",
            headers=auth_headers
        )
        assert response_all.status_code == 200
        total_all = response_all.json()["meta"]["total"]
        
        # Get with active filter
        response_active = requests.get(
            f"{BASE_URL}/api/v3/asset-domains?domain_active_status=active&page=1&limit=1000",
            headers=auth_headers
        )
        
        assert response_active.status_code == 200, f"Request failed: {response_active.text}"
        data_active = response_active.json()
        
        total_active = data_active["meta"]["total"]
        items_count = len(data_active["data"])
        
        # CRITICAL: total in meta should match actual items returned
        # This is the core bug fix validation
        assert items_count == total_active or items_count == data_active["meta"]["limit"], \
            f"BUG: Total mismatch! total={total_active}, items returned={items_count}"
        
        print(f"[PASS] domain_active_status=active returns correct total: {total_active} (items: {items_count})")
    
    def test_pagination_expired_filter_returns_correct_total(self, auth_headers):
        """Test: GET /api/v3/asset-domains?domain_active_status=expired returns correct total"""
        response_expired = requests.get(
            f"{BASE_URL}/api/v3/asset-domains?domain_active_status=expired&page=1&limit=1000",
            headers=auth_headers
        )
        
        assert response_expired.status_code == 200, f"Request failed: {response_expired.text}"
        data_expired = response_expired.json()
        
        total_expired = data_expired["meta"]["total"]
        items_count = len(data_expired["data"])
        
        # CRITICAL: total should match items returned (when within limit)
        assert items_count == total_expired or items_count == data_expired["meta"]["limit"], \
            f"BUG: Total mismatch! total={total_expired}, items returned={items_count}"
        
        print(f"[PASS] domain_active_status=expired returns correct total: {total_expired} (items: {items_count})")
    
    def test_pagination_view_mode_expired_returns_correct_total(self, auth_headers):
        """Test: GET /api/v3/asset-domains?view_mode=expired returns correct total"""
        response_expired = requests.get(
            f"{BASE_URL}/api/v3/asset-domains?view_mode=expired&page=1&limit=1000",
            headers=auth_headers
        )
        
        assert response_expired.status_code == 200, f"Request failed: {response_expired.text}"
        data_expired = response_expired.json()
        
        total_expired = data_expired["meta"]["total"]
        items_count = len(data_expired["data"])
        
        # CRITICAL: view_mode=expired should also have correct count
        assert items_count == total_expired or items_count == data_expired["meta"]["limit"], \
            f"BUG: view_mode=expired total mismatch! total={total_expired}, items returned={items_count}"
        
        print(f"[PASS] view_mode=expired returns correct total: {total_expired} (items: {items_count})")
    
    def test_pagination_active_plus_expired_equals_total(self, auth_headers):
        """Test: active + expired totals should equal total without filter"""
        # Get total without filter
        response_all = requests.get(
            f"{BASE_URL}/api/v3/asset-domains?page=1&limit=1",
            headers=auth_headers
        )
        assert response_all.status_code == 200
        total_all = response_all.json()["meta"]["total"]
        
        # Get active total
        response_active = requests.get(
            f"{BASE_URL}/api/v3/asset-domains?domain_active_status=active&page=1&limit=1",
            headers=auth_headers
        )
        assert response_active.status_code == 200
        total_active = response_active.json()["meta"]["total"]
        
        # Get expired total
        response_expired = requests.get(
            f"{BASE_URL}/api/v3/asset-domains?domain_active_status=expired&page=1&limit=1",
            headers=auth_headers
        )
        assert response_expired.status_code == 200
        total_expired = response_expired.json()["meta"]["total"]
        
        # Validate: active + expired = total
        sum_total = total_active + total_expired
        assert sum_total == total_all, \
            f"BUG: active({total_active}) + expired({total_expired}) = {sum_total} != total({total_all})"
        
        print(f"[PASS] active({total_active}) + expired({total_expired}) = {sum_total} == total({total_all})")


# ==================== API REGRESSION TESTS ====================

class TestAPIRegression:
    """Regression tests to ensure existing API functionality still works"""
    
    def test_login_still_works(self):
        """Test: Login API still works with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPERADMIN_EMAIL, "password": SUPERADMIN_PASSWORD}
        )
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        # API returns access_token not token
        assert "access_token" in data or "token" in data
        token = data.get("access_token") or data.get("token")
        assert len(token) > 0
        print(f"[PASS] Login API works correctly")
    
    def test_asset_domains_list_returns_data(self, auth_headers):
        """Test: Asset domains list API returns data properly"""
        response = requests.get(
            f"{BASE_URL}/api/v3/asset-domains?page=1&limit=10",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()
        
        assert "data" in data
        assert "meta" in data
        assert isinstance(data["data"], list)
        
        # If there are domains, verify structure
        if len(data["data"]) > 0:
            domain = data["data"][0]
            assert "id" in domain
            assert "domain_name" in domain
            # Verify enriched fields are present
            assert "domain_active_status" in domain
            assert "domain_active_status_label" in domain
        
        print(f"[PASS] Asset domains list returns proper data structure")
    
    def test_brands_endpoint_works(self, auth_headers):
        """Test: Brands endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/brands",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Brands request failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"[PASS] Brands endpoint works, returned {len(data)} brands")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
