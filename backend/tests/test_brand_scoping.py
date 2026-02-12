"""
Test suite for Multi-Brand Support
===================================
Tests brand as root entity with complete data isolation:
- Brand model with slug, status, archive functionality
- User model with brand_scope_ids (NULL for Super Admin = all brands)
- Backend enforcement - all APIs filter by brand_scope_ids
- 403 for unauthorized brand access
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://domain-monitor-3.preview.emergentagent.com"
)


class TestBrandScoping:
    """Brand Scoping API Tests"""

    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get super admin token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]

    @pytest.fixture(scope="class")
    def admin_headers(self, admin_token):
        return {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
        }

    @pytest.fixture(scope="class")
    def brands(self, admin_headers):
        """Get all brands"""
        response = requests.get(f"{BASE_URL}/api/brands", headers=admin_headers)
        assert response.status_code == 200
        return response.json()

    # ==================== SUPER ADMIN TESTS ====================

    def test_super_admin_has_null_brand_scope_ids(self, admin_headers):
        """Super Admin should have NULL brand_scope_ids (full access)"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "super_admin"
        assert (
            data["brand_scope_ids"] is None
        ), "Super Admin must have null brand_scope_ids"

    def test_super_admin_sees_all_brands(self, admin_headers):
        """Super Admin should see all brands"""
        response = requests.get(f"{BASE_URL}/api/brands", headers=admin_headers)
        assert response.status_code == 200
        brands = response.json()
        assert len(brands) >= 1, "Should have at least 1 brand"

    def test_super_admin_can_access_any_brand(self, admin_headers, brands):
        """Super Admin can access any brand directly"""
        for brand in brands[:2]:
            response = requests.get(
                f"{BASE_URL}/api/brands/{brand['id']}", headers=admin_headers
            )
            assert response.status_code == 200

    # ==================== BRAND MODEL TESTS ====================

    def test_brand_has_required_fields(self, admin_headers, brands):
        """Brand model should have slug, status, and archive fields"""
        brand = brands[0]
        assert "id" in brand
        assert "name" in brand
        assert "slug" in brand
        assert "status" in brand
        assert brand["status"] in ["active", "archived"]

    def test_brand_archive_functionality(self, admin_headers, brands):
        """Test brand archive and unarchive"""
        # Find a brand to archive (use last one to minimize impact)
        test_brand = brands[-1]
        brand_id = test_brand["id"]

        # Archive brand
        response = requests.post(
            f"{BASE_URL}/api/brands/{brand_id}/archive", headers=admin_headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "archived"

        # Verify archived
        response = requests.get(
            f"{BASE_URL}/api/brands/{brand_id}", headers=admin_headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "archived"

        # Unarchive brand
        response = requests.post(
            f"{BASE_URL}/api/brands/{brand_id}/unarchive", headers=admin_headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "active"

    def test_cannot_archive_already_archived_brand(self, admin_headers, brands):
        """Cannot archive a brand that is already archived"""
        test_brand = brands[-1]
        brand_id = test_brand["id"]

        # Archive first
        requests.post(
            f"{BASE_URL}/api/brands/{brand_id}/archive", headers=admin_headers
        )

        # Try to archive again
        response = requests.post(
            f"{BASE_URL}/api/brands/{brand_id}/archive", headers=admin_headers
        )
        assert response.status_code == 400

        # Cleanup: Unarchive
        requests.post(
            f"{BASE_URL}/api/brands/{brand_id}/unarchive", headers=admin_headers
        )

    # ==================== USER BRAND SCOPE TESTS ====================

    def test_admin_viewer_must_have_brands(self, admin_headers):
        """Admin and Viewer users must have at least one brand assigned"""
        # Get a non-super-admin user
        response = requests.get(f"{BASE_URL}/api/users", headers=admin_headers)
        assert response.status_code == 200
        users = response.json()

        non_super_admins = [u for u in users if u["role"] != "super_admin"]
        if non_super_admins:
            user = non_super_admins[0]
            # Try to set empty brand_scope_ids
            response = requests.put(
                f"{BASE_URL}/api/users/{user['id']}",
                headers=admin_headers,
                json={"role": "admin", "brand_scope_ids": []},
            )
            assert response.status_code == 400
            assert "at least one brand" in response.json()["detail"].lower()

    def test_super_admin_gets_null_brand_scope_on_update(self, admin_headers, brands):
        """When updating to super_admin role, brand_scope_ids becomes null"""
        # Create a test user
        test_email = f"test-super-{int(time.time())}@test.com"
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": test_email,
                "name": "Test",
                "password": "test123",
                "role": "viewer",
            },
        )
        assert response.status_code == 200
        user_id = response.json()["user"]["id"]

        try:
            # Set to admin with brands
            response = requests.put(
                f"{BASE_URL}/api/users/{user_id}",
                headers=admin_headers,
                json={"role": "admin", "brand_scope_ids": [brands[0]["id"]]},
            )
            assert response.status_code == 200

            # Update to super_admin
            response = requests.put(
                f"{BASE_URL}/api/users/{user_id}",
                headers=admin_headers,
                json={"role": "super_admin"},
            )
            assert response.status_code == 200
            assert response.json()["brand_scope_ids"] is None
        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=admin_headers)

    # ==================== BRAND FILTERING TESTS (V3 APIs) ====================

    def test_v3_asset_domains_filtered_by_brand_scope(self, admin_headers, brands):
        """GET /api/v3/asset-domains filters by user's brand scope"""
        # Super admin should see all
        response = requests.get(
            f"{BASE_URL}/api/v3/asset-domains", headers=admin_headers
        )
        assert response.status_code == 200
        assets = response.json()

        # Verify assets have brand info
        if assets:
            for asset in assets[:3]:
                assert "brand_id" in asset
                assert "brand_name" in asset

    def test_v3_networks_filtered_by_brand_scope(self, admin_headers, brands):
        """GET /api/v3/networks filters by user's brand scope"""
        response = requests.get(f"{BASE_URL}/api/v3/networks", headers=admin_headers)
        assert response.status_code == 200
        networks = response.json()

        # Verify networks have brand info
        if networks:
            for network in networks[:3]:
                assert "brand_id" in network
                assert "brand_name" in network

    # ==================== BRAND ACCESS VALIDATION TESTS ====================

    def test_create_asset_domain_requires_valid_brand(self, admin_headers):
        """POST /api/v3/asset-domains requires valid brand_id"""
        response = requests.post(
            f"{BASE_URL}/api/v3/asset-domains",
            headers=admin_headers,
            json={
                "domain_name": "test-invalid-brand.com",
                "brand_id": "invalid-brand-id",
            },
        )
        assert response.status_code == 400
        assert "brand not found" in response.json()["detail"].lower()

    def test_create_asset_domain_with_valid_brand(self, admin_headers, brands):
        """POST /api/v3/asset-domains succeeds with valid brand_id"""
        domain_name = f"test-valid-brand-{int(time.time())}.com"
        response = requests.post(
            f"{BASE_URL}/api/v3/asset-domains",
            headers=admin_headers,
            json={"domain_name": domain_name, "brand_id": brands[0]["id"]},
        )
        assert response.status_code == 200
        assert response.json()["brand_id"] == brands[0]["id"]
        assert response.json()["brand_name"] == brands[0]["name"]

        # Cleanup
        asset_id = response.json()["id"]
        requests.delete(
            f"{BASE_URL}/api/v3/asset-domains/{asset_id}", headers=admin_headers
        )

    # ==================== 403 UNAUTHORIZED ACCESS TESTS ====================

    def test_limited_user_403_for_unauthorized_brand(self, admin_headers, brands):
        """Limited user gets 403 when accessing unauthorized brand"""
        if len(brands) < 2:
            pytest.skip("Need at least 2 brands for this test")

        brand_1 = brands[0]["id"]
        brand_2 = brands[1]["id"]

        # Create limited user
        test_email = f"limited-{int(time.time())}@test.com"
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": test_email,
                "name": "Limited",
                "password": "test123",
                "role": "viewer",
            },
        )
        assert response.status_code == 200
        user_id = response.json()["user"]["id"]

        try:
            # Update to have only brand_1 access
            requests.put(
                f"{BASE_URL}/api/users/{user_id}",
                headers=admin_headers,
                json={"role": "viewer", "brand_scope_ids": [brand_1]},
            )

            # Login as limited user
            response = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": test_email, "password": "test123"},
            )
            limited_token = response.json()["access_token"]
            limited_headers = {
                "Authorization": f"Bearer {limited_token}",
                "Content-Type": "application/json",
            }

            # Limited user should only see brand_1
            response = requests.get(f"{BASE_URL}/api/brands", headers=limited_headers)
            assert response.status_code == 200
            brand_ids = [b["id"] for b in response.json()]
            assert brand_1 in brand_ids
            assert brand_2 not in brand_ids

            # Limited user should get 403 when accessing brand_2
            response = requests.get(
                f"{BASE_URL}/api/brands/{brand_2}", headers=limited_headers
            )
            assert response.status_code == 403
            assert "access denied" in response.json()["detail"].lower()

            # Limited user should get 403 when creating asset in brand_2
            response = requests.post(
                f"{BASE_URL}/api/v3/asset-domains",
                headers=limited_headers,
                json={"domain_name": "forbidden.com", "brand_id": brand_2},
            )
            assert response.status_code == 403

        finally:
            # Cleanup
            requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=admin_headers)

    def test_limited_user_sees_only_scoped_assets(self, admin_headers, brands):
        """Limited user only sees assets from their brand scope"""
        if len(brands) < 2:
            pytest.skip("Need at least 2 brands for this test")

        brand_1 = brands[0]["id"]

        # Create limited user
        test_email = f"limited-assets-{int(time.time())}@test.com"
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": test_email,
                "name": "Limited",
                "password": "test123",
                "role": "viewer",
            },
        )
        user_id = response.json()["user"]["id"]

        try:
            # Update to have only brand_1 access
            requests.put(
                f"{BASE_URL}/api/users/{user_id}",
                headers=admin_headers,
                json={"role": "viewer", "brand_scope_ids": [brand_1]},
            )

            # Login as limited user
            response = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": test_email, "password": "test123"},
            )
            limited_headers = {
                "Authorization": f"Bearer {response.json()['access_token']}"
            }

            # Get asset domains - should only return brand_1 assets
            response = requests.get(
                f"{BASE_URL}/api/v3/asset-domains", headers=limited_headers
            )
            assert response.status_code == 200
            assets = response.json()

            # Verify all returned assets are from brand_1
            for asset in assets:
                assert (
                    asset["brand_id"] == brand_1
                ), f"Asset {asset['domain_name']} should be from brand {brand_1}"

            # Get networks - should only return brand_1 networks
            response = requests.get(
                f"{BASE_URL}/api/v3/networks", headers=limited_headers
            )
            assert response.status_code == 200
            networks = response.json()

            for network in networks:
                assert (
                    network["brand_id"] == brand_1
                ), f"Network {network['name']} should be from brand {brand_1}"

        finally:
            requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=admin_headers)
