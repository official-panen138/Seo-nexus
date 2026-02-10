"""
Test Domain Save and Role-Based Access Control
==============================================
Tests for:
1. POST /api/v3/asset-domains - Domain creation with domain_name and brand_id
2. GET /api/v3/networks - Manager should only see networks for their brand_scope_ids
3. GET /api/v3/networks - Super admin should see all networks
4. Manager login (manager role in UserRole enum)
5. Domain list access filtering by brand
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

# Base URL from environment
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
SUPER_ADMIN_CREDS = {"email": "admin@test.com", "password": "admin123"}
MANAGER_CREDS = {"email": "manager@test.com", "password": "manager123"}

# Manager's brand_id (Panen138)
MANAGER_BRAND_ID = "a34a960f-feb3-4d1b-a231-4611ac7ecdb0"


class TestAuthentication:
    """Test authentication for manager and super admin roles"""

    def test_manager_login_success(self):
        """Manager should be able to login with manager role"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=MANAGER_CREDS)
        assert response.status_code == 200, f"Manager login failed: {response.text}"

        data = response.json()
        assert "access_token" in data, "No access token returned"
        assert "user" in data, "No user data returned"
        assert (
            data["user"]["role"] == "manager"
        ), f"Expected manager role, got {data['user']['role']}"
        assert (
            data["user"]["brand_scope_ids"] is not None
        ), "Manager should have brand_scope_ids"
        assert (
            MANAGER_BRAND_ID in data["user"]["brand_scope_ids"]
        ), "Manager should have Panen138 brand access"
        print(f"✓ Manager login successful with role: {data['user']['role']}")
        print(f"✓ Manager brand_scope_ids: {data['user']['brand_scope_ids']}")

    def test_super_admin_login_success(self):
        """Super admin should be able to login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN_CREDS)
        assert response.status_code == 200, f"Super admin login failed: {response.text}"

        data = response.json()
        assert data["user"]["role"] == "super_admin"
        assert (
            data["user"]["brand_scope_ids"] is None
        ), "Super admin should have NULL brand_scope_ids (full access)"
        print(f"✓ Super admin login successful with full access")


class TestNetworkRBAC:
    """Test network access based on role and brand scope"""

    @pytest.fixture
    def manager_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=MANAGER_CREDS)
        return response.json().get("access_token")

    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN_CREDS)
        return response.json().get("access_token")

    def test_manager_sees_only_their_brand_networks(self, manager_token):
        """Manager should only see networks for their brand_scope_ids"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert response.status_code == 200

        networks = response.json()
        assert isinstance(networks, list)

        # Manager should see 3 networks (Panen138 brand only)
        print(f"✓ Manager sees {len(networks)} networks")

        # Verify all networks belong to manager's brand
        for network in networks:
            assert (
                network.get("brand_id") == MANAGER_BRAND_ID
            ), f"Manager sees network from unauthorized brand: {network.get('brand_name')}"
        print(f"✓ All {len(networks)} networks belong to manager's brand (Panen138)")

    def test_super_admin_sees_all_networks(self, admin_token):
        """Super admin should see all networks"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

        networks = response.json()
        assert isinstance(networks, list)

        # Super admin should see more networks than manager (5 total)
        print(f"✓ Super admin sees {len(networks)} networks (all brands)")
        assert (
            len(networks) >= 3
        ), "Super admin should see at least as many networks as manager"

    def test_manager_vs_admin_network_count(self, manager_token, admin_token):
        """Super admin should see more or equal networks than manager"""
        manager_response = requests.get(
            f"{BASE_URL}/api/v3/networks",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        admin_response = requests.get(
            f"{BASE_URL}/api/v3/networks",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        manager_count = len(manager_response.json())
        admin_count = len(admin_response.json())

        print(f"✓ Manager: {manager_count} networks, Admin: {admin_count} networks")
        assert (
            admin_count >= manager_count
        ), "Super admin should see at least as many networks as manager"


class TestDomainRBAC:
    """Test domain access based on role and brand scope"""

    @pytest.fixture
    def manager_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=MANAGER_CREDS)
        return response.json().get("access_token")

    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN_CREDS)
        return response.json().get("access_token")

    def test_manager_sees_only_their_brand_domains(self, manager_token):
        """Manager should only see domains for their brand_scope_ids"""
        response = requests.get(
            f"{BASE_URL}/api/v3/asset-domains",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert response.status_code == 200

        data = response.json()
        assert "data" in data, "Response should have 'data' field"
        assert "meta" in data, "Response should have 'meta' field"

        domains = data["data"]
        total = data["meta"]["total"]

        print(f"✓ Manager sees {total} total domains ({len(domains)} on this page)")

        # Verify all domains belong to manager's brand
        for domain in domains:
            assert (
                domain.get("brand_id") == MANAGER_BRAND_ID
            ), f"Manager sees domain from unauthorized brand: {domain.get('brand_name')}"
        print(f"✓ All domains belong to manager's brand (Panen138)")

    def test_super_admin_sees_all_domains(self, admin_token):
        """Super admin should see all domains"""
        response = requests.get(
            f"{BASE_URL}/api/v3/asset-domains",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

        data = response.json()
        total = data["meta"]["total"]
        print(f"✓ Super admin sees {total} total domains (all brands)")


class TestDomainSave:
    """Test domain creation (save) functionality"""

    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN_CREDS)
        return response.json().get("access_token")

    @pytest.fixture
    def manager_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=MANAGER_CREDS)
        return response.json().get("access_token")

    def test_create_domain_with_brand_id(self, admin_token):
        """Create a new domain with domain_name and brand_id"""
        domain_name = f"test-domain-{uuid.uuid4().hex[:8]}.com"

        response = requests.post(
            f"{BASE_URL}/api/v3/asset-domains",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"domain_name": domain_name, "brand_id": MANAGER_BRAND_ID},
        )

        assert response.status_code == 200, f"Domain creation failed: {response.text}"

        data = response.json()
        assert data["domain_name"] == domain_name
        assert data["brand_id"] == MANAGER_BRAND_ID
        assert "id" in data
        print(f"✓ Domain created: {domain_name} (ID: {data['id']})")

        # Verify domain persisted by fetching it
        get_response = requests.get(
            f"{BASE_URL}/api/v3/asset-domains/{data['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["domain_name"] == domain_name
        print(f"✓ Domain fetch verified")

        # Cleanup
        delete_response = requests.delete(
            f"{BASE_URL}/api/v3/asset-domains/{data['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert delete_response.status_code == 200
        print(f"✓ Domain deleted (cleanup)")

    def test_create_domain_requires_brand_id(self, admin_token):
        """Creating domain without brand_id should fail"""
        response = requests.post(
            f"{BASE_URL}/api/v3/asset-domains",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"domain_name": "test-no-brand.com"},
        )

        # Should fail because brand_id is required
        assert response.status_code in [
            400,
            422,
        ], f"Expected 400/422, got {response.status_code}"
        print(f"✓ Domain creation without brand_id correctly rejected")

    def test_manager_can_create_domain_for_their_brand(self, manager_token):
        """Manager should be able to create domain for their own brand"""
        domain_name = f"manager-test-{uuid.uuid4().hex[:8]}.com"

        response = requests.post(
            f"{BASE_URL}/api/v3/asset-domains",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "domain_name": domain_name,
                "brand_id": MANAGER_BRAND_ID,  # Manager's own brand
            },
        )

        assert (
            response.status_code == 200
        ), f"Manager domain creation failed: {response.text}"
        data = response.json()
        print(f"✓ Manager created domain: {domain_name}")

        # Cleanup
        admin_token = (
            requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN_CREDS)
            .json()
            .get("access_token")
        )
        requests.delete(
            f"{BASE_URL}/api/v3/asset-domains/{data['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    def test_manager_cannot_create_domain_for_other_brand(self, manager_token):
        """Manager should NOT be able to create domain for another brand"""
        # Use a different brand ID
        other_brand_id = "fc568195-4600-4e10-8fd9-407864f79275"  # PANEN77

        response = requests.post(
            f"{BASE_URL}/api/v3/asset-domains",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={
                "domain_name": f"manager-other-{uuid.uuid4().hex[:8]}.com",
                "brand_id": other_brand_id,
            },
        )

        assert (
            response.status_code == 403
        ), f"Expected 403, got {response.status_code}: {response.text}"
        print(f"✓ Manager correctly denied creating domain for other brand")


class TestDomainListFiltering:
    """Test domain list page filtering by brand"""

    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN_CREDS)
        return response.json().get("access_token")

    def test_domain_list_filtered_by_brand_id(self, admin_token):
        """Domain list can be filtered by brand_id"""
        response = requests.get(
            f"{BASE_URL}/api/v3/asset-domains",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"brand_id": MANAGER_BRAND_ID},
        )

        assert response.status_code == 200
        data = response.json()

        # All returned domains should be from the specified brand
        for domain in data["data"]:
            assert (
                domain.get("brand_id") == MANAGER_BRAND_ID
            ), f"Domain from wrong brand in filtered results"

        print(
            f"✓ Domain list correctly filtered by brand_id ({data['meta']['total']} domains)"
        )


class TestManagerDashboard:
    """Test manager dashboard shows only their brand's data"""

    @pytest.fixture
    def manager_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json=MANAGER_CREDS)
        return response.json().get("access_token")

    def test_manager_brands_list_restricted(self, manager_token):
        """Manager should only see their assigned brands"""
        response = requests.get(
            f"{BASE_URL}/api/brands",
            headers={"Authorization": f"Bearer {manager_token}"},
        )

        assert response.status_code == 200
        brands = response.json()

        # Manager should only see their assigned brand
        print(f"✓ Manager sees {len(brands)} brand(s)")
        for brand in brands:
            assert (
                brand["id"] == MANAGER_BRAND_ID
            ), f"Manager sees unauthorized brand: {brand['name']}"
        print(f"✓ Manager only sees Panen138 brand (restricted access)")


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
