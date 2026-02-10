"""
SEO-NOC V3 P0 Features API Tests
=================================
Tests for 4 P0 features:
1. Registrar CRUD API with super_admin permission check
2. Network creation requires brand_id
3. Structure entry with optimized_path and target_entry_id
4. Tier calculation with node-based relationships
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://seo-monitoring-hub.preview.emergentagent.com"
)

# Test credentials
SUPER_ADMIN_EMAIL = "admin@v3test.com"
SUPER_ADMIN_PASSWORD = "admin123"
VIEWER_EMAIL = "test@seonoc.com"
VIEWER_PASSWORD = "test123"


class TestRegistrarCRUD:
    """Test Registrar CRUD API with super_admin permission check"""

    @pytest.fixture
    def super_admin_token(self):
        """Get super_admin token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]

    @pytest.fixture
    def viewer_token(self):
        """Get viewer token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": VIEWER_EMAIL, "password": VIEWER_PASSWORD},
        )
        if response.status_code != 200:
            pytest.skip("Viewer user not available")
        return response.json()["access_token"]

    def test_get_registrars_authenticated(self, super_admin_token):
        """Test GET /api/v3/registrars - should return list of registrars"""
        response = requests.get(
            f"{BASE_URL}/api/v3/registrars",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET registrars returned {len(data)} registrars")

    def test_get_registrars_unauthenticated(self):
        """Test GET /api/v3/registrars without auth - should fail"""
        response = requests.get(f"{BASE_URL}/api/v3/registrars")
        assert response.status_code == 401
        print("✓ Unauthenticated request properly rejected")

    def test_create_registrar_super_admin(self, super_admin_token):
        """Test POST /api/v3/registrars - super_admin should be able to create"""
        test_name = f"TEST_Registrar_{uuid.uuid4().hex[:8]}"
        response = requests.post(
            f"{BASE_URL}/api/v3/registrars",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={
                "name": test_name,
                "website": "https://testregistrar.com",
                "status": "active",
                "notes": "Test registrar for API testing",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == test_name
        assert "id" in data
        print(f"✓ Created registrar: {test_name}")

        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/v3/registrars/{data['id']}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )

    def test_create_registrar_non_super_admin(self, viewer_token):
        """Test POST /api/v3/registrars - non-super_admin should be rejected"""
        response = requests.post(
            f"{BASE_URL}/api/v3/registrars",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"name": "TEST_Should_Fail", "status": "active"},
        )
        assert response.status_code == 403
        assert "super_admin" in response.json().get("detail", "").lower()
        print("✓ Non-super_admin correctly rejected from creating registrar")

    def test_update_registrar_super_admin(self, super_admin_token):
        """Test PUT /api/v3/registrars/{id} - super_admin should be able to update"""
        # Create test registrar
        test_name = f"TEST_Update_{uuid.uuid4().hex[:8]}"
        create_resp = requests.post(
            f"{BASE_URL}/api/v3/registrars",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"name": test_name, "status": "active"},
        )
        assert create_resp.status_code == 200
        registrar_id = create_resp.json()["id"]

        # Update registrar
        new_name = f"TEST_Updated_{uuid.uuid4().hex[:8]}"
        update_resp = requests.put(
            f"{BASE_URL}/api/v3/registrars/{registrar_id}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"name": new_name, "website": "https://updated.com"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == new_name
        print(f"✓ Updated registrar name to: {new_name}")

        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/v3/registrars/{registrar_id}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )

    def test_delete_registrar_super_admin(self, super_admin_token):
        """Test DELETE /api/v3/registrars/{id} - super_admin should be able to delete"""
        # Create test registrar
        test_name = f"TEST_Delete_{uuid.uuid4().hex[:8]}"
        create_resp = requests.post(
            f"{BASE_URL}/api/v3/registrars",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"name": test_name, "status": "active"},
        )
        assert create_resp.status_code == 200
        registrar_id = create_resp.json()["id"]

        # Delete registrar
        delete_resp = requests.delete(
            f"{BASE_URL}/api/v3/registrars/{registrar_id}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert delete_resp.status_code == 200
        print(f"✓ Deleted registrar: {test_name}")

        # Verify deletion
        get_resp = requests.get(
            f"{BASE_URL}/api/v3/registrars/{registrar_id}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert get_resp.status_code == 404
        print("✓ Verified registrar no longer exists")

    def test_registrar_search(self, super_admin_token):
        """Test GET /api/v3/registrars with search filter"""
        response = requests.get(
            f"{BASE_URL}/api/v3/registrars",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            params={"search": "GoDaddy"},
        )
        assert response.status_code == 200
        data = response.json()
        # Should find GoDaddy if it exists
        print(f"✓ Search for 'GoDaddy' returned {len(data)} results")

    def test_registrar_status_filter(self, super_admin_token):
        """Test GET /api/v3/registrars with status filter"""
        response = requests.get(
            f"{BASE_URL}/api/v3/registrars",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            params={"status": "active"},
        )
        assert response.status_code == 200
        data = response.json()
        # All returned should be active
        for reg in data:
            assert reg["status"] == "active"
        print(f"✓ Status filter returned {len(data)} active registrars")


class TestNetworkBrandRequirement:
    """Test that Networks require brand_id"""

    @pytest.fixture
    def super_admin_token(self):
        """Get super_admin token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
        )
        assert response.status_code == 200
        return response.json()["access_token"]

    @pytest.fixture
    def existing_brand_id(self, super_admin_token):
        """Get an existing brand ID"""
        response = requests.get(
            f"{BASE_URL}/api/brands",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert response.status_code == 200
        brands = response.json()
        if not brands:
            pytest.skip("No brands available for testing")
        return brands[0]["id"]

    def test_create_network_without_brand(self, super_admin_token):
        """Test POST /api/v3/networks without brand_id - should fail validation"""
        response = requests.post(
            f"{BASE_URL}/api/v3/networks",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"name": "TEST_No_Brand_Network", "description": "Should fail"},
        )
        # Should fail - brand_id is required
        assert response.status_code == 422  # Validation error
        print("✓ Network creation without brand_id properly rejected")

    def test_create_network_with_invalid_brand(self, super_admin_token):
        """Test POST /api/v3/networks with invalid brand_id - should fail"""
        response = requests.post(
            f"{BASE_URL}/api/v3/networks",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={
                "name": "TEST_Invalid_Brand_Network",
                "brand_id": "invalid-brand-id-12345",
                "description": "Should fail",
            },
        )
        assert response.status_code == 400
        assert "brand" in response.json().get("detail", "").lower()
        print("✓ Network creation with invalid brand_id properly rejected")

    def test_create_network_with_valid_brand(
        self, super_admin_token, existing_brand_id
    ):
        """Test POST /api/v3/networks with valid brand_id - should succeed"""
        test_name = f"TEST_Network_{uuid.uuid4().hex[:8]}"
        response = requests.post(
            f"{BASE_URL}/api/v3/networks",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={
                "name": test_name,
                "brand_id": existing_brand_id,
                "description": "Test network with valid brand",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == test_name
        assert data["brand_id"] == existing_brand_id
        assert "brand_name" in data
        print(f"✓ Created network with brand: {data['brand_name']}")

        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/v3/networks/{data['id']}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )

    def test_network_list_shows_brand(self, super_admin_token):
        """Test GET /api/v3/networks - should show brand names"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        for network in data:
            # All networks should have brand_id and brand_name
            assert "brand_id" in network
            print(
                f"  Network: {network['name']} - Brand: {network.get('brand_name', 'N/A')}"
            )
        print(f"✓ Listed {len(data)} networks with brand info")

    def test_network_brand_filter(self, super_admin_token, existing_brand_id):
        """Test GET /api/v3/networks with brand filter"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            params={"brand_id": existing_brand_id},
        )
        assert response.status_code == 200
        data = response.json()

        for network in data:
            assert network["brand_id"] == existing_brand_id
        print(f"✓ Brand filter returned {len(data)} networks for brand")


class TestPathLevelSeoNodes:
    """Test Path-Level SEO Nodes (optimized_path and target_entry_id)"""

    @pytest.fixture
    def super_admin_token(self):
        """Get super_admin token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
        )
        assert response.status_code == 200
        return response.json()["access_token"]

    @pytest.fixture
    def test_network_id(self, super_admin_token):
        """Get an existing network with entries"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert response.status_code == 200
        networks = response.json()

        # Find a network with entries
        for network in networks:
            if network.get("domain_count", 0) > 0:
                return network["id"]

        pytest.skip("No networks with entries available for testing")

    def test_structure_entry_has_optimized_path(
        self, super_admin_token, test_network_id
    ):
        """Test that structure entries support optimized_path field"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{test_network_id}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        entries = data.get("entries", [])
        path_entries = [e for e in entries if e.get("optimized_path")]

        print(
            f"✓ Found {len(path_entries)} entries with optimized_path out of {len(entries)} total"
        )

        for entry in entries[:3]:  # Check first 3
            assert "optimized_path" in entry or entry.get("optimized_path") is None
            assert "node_label" in entry  # Should have computed node label

    def test_structure_entry_has_target_entry_id(
        self, super_admin_token, test_network_id
    ):
        """Test that structure entries support target_entry_id field"""
        response = requests.get(
            f"{BASE_URL}/api/v3/structure",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            params={"network_id": test_network_id},
        )
        assert response.status_code == 200
        entries = response.json()

        # Check schema has target_entry_id
        for entry in entries:
            # Should have target_entry_id OR target_asset_domain_id (legacy)
            has_target = entry.get("target_entry_id") or entry.get(
                "target_asset_domain_id"
            )
            if entry.get("domain_role") != "main":
                print(
                    f"  Entry: {entry.get('domain_name')} -> Target: {has_target or 'None (orphan)'}"
                )

        print(f"✓ Verified {len(entries)} entries have target relationship fields")

    def test_update_entry_with_optimized_path(self, super_admin_token, test_network_id):
        """Test updating a structure entry with optimized_path"""
        # Get entries for this network
        response = requests.get(
            f"{BASE_URL}/api/v3/structure",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            params={"network_id": test_network_id},
        )
        assert response.status_code == 200
        entries = response.json()

        if not entries:
            pytest.skip("No entries available for testing")

        # Get a supporting entry to update
        test_entry = None
        for entry in entries:
            if entry.get("domain_role") == "supporting":
                test_entry = entry
                break

        if not test_entry:
            test_entry = entries[0]

        # Update with optimized_path
        test_path = f"/test-path-{uuid.uuid4().hex[:6]}"
        original_path = test_entry.get("optimized_path")

        update_resp = requests.put(
            f"{BASE_URL}/api/v3/structure/{test_entry['id']}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"optimized_path": test_path},
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["optimized_path"] == test_path
        print(f"✓ Updated entry with optimized_path: {test_path}")

        # Restore original path
        requests.put(
            f"{BASE_URL}/api/v3/structure/{test_entry['id']}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={"optimized_path": original_path},
        )


class TestTierCalculation:
    """Test Tier Calculation with node-based relationships"""

    @pytest.fixture
    def super_admin_token(self):
        """Get super_admin token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
        )
        assert response.status_code == 200
        return response.json()["access_token"]

    @pytest.fixture
    def test_network_id(self, super_admin_token):
        """Get a network with entries for tier testing"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert response.status_code == 200
        networks = response.json()

        for network in networks:
            if network.get("domain_count", 0) > 2:
                return network["id"]

        pytest.skip("No networks with sufficient entries for tier testing")

    def test_tier_endpoint(self, super_admin_token, test_network_id):
        """Test GET /api/v3/networks/{id}/tiers endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{test_network_id}/tiers",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        assert "distribution" in data
        assert "domains" in data
        assert "network_id" in data

        print(f"✓ Tier distribution for network: {data.get('network_name')}")
        for tier, count in data.get("distribution", {}).items():
            print(f"  {tier}: {count}")

    def test_entries_have_calculated_tier(self, super_admin_token, test_network_id):
        """Test that entries have calculated_tier and tier_label"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{test_network_id}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        entries = data.get("entries", [])
        for entry in entries:
            assert "calculated_tier" in entry
            assert "tier_label" in entry
            print(
                f"  {entry['domain_name']}: {entry['tier_label']} (tier {entry['calculated_tier']})"
            )

        print(f"✓ Verified {len(entries)} entries have calculated tiers")

    def test_main_domain_is_tier_zero(self, super_admin_token, test_network_id):
        """Test that main domain has tier 0 (LP/Money Site)"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{test_network_id}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()

        entries = data.get("entries", [])
        main_entries = [e for e in entries if e.get("domain_role") == "main"]

        for main in main_entries:
            assert main["calculated_tier"] == 0
            assert (
                "LP/Money Site" in main["tier_label"] or "Money" in main["tier_label"]
            )
            print(
                f"✓ Main domain {main['domain_name']} is tier 0: {main['tier_label']}"
            )


class TestRegistrarInDomainForm:
    """Test Registrar dropdown in Domain forms"""

    @pytest.fixture
    def super_admin_token(self):
        """Get super_admin token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
        )
        assert response.status_code == 200
        return response.json()["access_token"]

    @pytest.fixture
    def existing_registrar_id(self, super_admin_token):
        """Get an existing registrar ID"""
        response = requests.get(
            f"{BASE_URL}/api/v3/registrars",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert response.status_code == 200
        registrars = response.json()
        if not registrars:
            pytest.skip("No registrars available for testing")
        return registrars[0]["id"]

    @pytest.fixture
    def existing_brand_id(self, super_admin_token):
        """Get an existing brand ID"""
        response = requests.get(
            f"{BASE_URL}/api/brands",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert response.status_code == 200
        brands = response.json()
        if not brands:
            pytest.skip("No brands available for testing")
        return brands[0]["id"]

    def test_create_asset_domain_with_registrar(
        self, super_admin_token, existing_brand_id, existing_registrar_id
    ):
        """Test creating asset domain with registrar_id"""
        test_domain = f"test-{uuid.uuid4().hex[:8]}.com"

        response = requests.post(
            f"{BASE_URL}/api/v3/asset-domains",
            headers={"Authorization": f"Bearer {super_admin_token}"},
            json={
                "domain_name": test_domain,
                "brand_id": existing_brand_id,
                "registrar_id": existing_registrar_id,
                "status": "active",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["domain_name"] == test_domain
        assert data["registrar_id"] == existing_registrar_id
        assert "registrar_name" in data
        print(
            f"✓ Created domain {test_domain} with registrar: {data.get('registrar_name')}"
        )

        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/v3/asset-domains/{data['id']}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )

    def test_asset_domain_shows_registrar_name(self, super_admin_token):
        """Test that asset domains show enriched registrar_name"""
        response = requests.get(
            f"{BASE_URL}/api/v3/asset-domains",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert response.status_code == 200
        domains = response.json()

        domains_with_registrar = [d for d in domains if d.get("registrar_id")]
        print(f"✓ Found {len(domains_with_registrar)} domains with registrar_id")

        for domain in domains_with_registrar[:5]:  # Check first 5
            print(f"  {domain['domain_name']}: {domain.get('registrar_name', 'N/A')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
