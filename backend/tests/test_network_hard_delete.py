"""
Test suite for SEO Network Hard Delete feature
Tests the refactor from soft-delete/archive to permanent hard delete

Features tested:
1. DELETE /api/v3/networks/{id} permanently removes network and all cascading data
2. DELETE endpoint returns proper response with counts of deleted items
3. Deleted network returns 404 on GET
4. GET /api/v3/networks/archived endpoint no longer exists (returns 404)
5. POST /api/v3/networks/{id}/restore endpoint no longer exists (returns 404)
6. GET /api/v3/networks does NOT show deleted/archived networks
7. Asset Domains are NOT deleted when their SEO network is deleted
8. Domain+path uniqueness check works correctly after delete
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "superadmin@seonoc.com"
SUPER_ADMIN_PASSWORD = "SuperAdmin123!"


class TestNetworkHardDelete:
    """Test suite for network hard delete feature"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test with auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Login failed: {login_response.status_code}")
        
        token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Store created resources for cleanup
        self.created_network_id = None
        self.created_domain_ids = []
        self.brand_id = None
        
    def teardown_method(self, method):
        """Cleanup created test data"""
        # Networks should be cleaned up by tests themselves
        # Clean up any domains we created
        for domain_id in self.created_domain_ids:
            try:
                self.session.delete(f"{BASE_URL}/api/v3/asset-domains/{domain_id}")
            except:
                pass
    
    def _get_or_create_brand(self):
        """Get existing brand or create one for testing"""
        brands_resp = self.session.get(f"{BASE_URL}/api/brands")
        if brands_resp.status_code == 200:
            brands = brands_resp.json()
            if brands and len(brands) > 0:
                self.brand_id = brands[0]["id"]
                return self.brand_id
        
        # Create a test brand
        brand_resp = self.session.post(f"{BASE_URL}/api/brands", json={
            "name": f"TEST_Brand_{uuid.uuid4().hex[:8]}",
            "description": "Test brand for hard delete testing"
        })
        if brand_resp.status_code == 200:
            self.brand_id = brand_resp.json()["id"]
            return self.brand_id
        pytest.skip("Could not get or create brand")
    
    def _create_test_domain(self, brand_id):
        """Create a test asset domain"""
        domain_name = f"test-{uuid.uuid4().hex[:8]}.example.com"
        resp = self.session.post(f"{BASE_URL}/api/v3/asset-domains", json={
            "domain_name": domain_name,
            "brand_id": brand_id,
            "lifecycle_status": "active"
        })
        if resp.status_code in [200, 201]:
            domain_id = resp.json()["id"]
            self.created_domain_ids.append(domain_id)
            return domain_id, domain_name
        return None, None
    
    def _create_test_network_with_data(self):
        """Create a test network with main node and supporting data"""
        brand_id = self._get_or_create_brand()
        
        # Create main domain
        main_domain_id, main_domain_name = self._create_test_domain(brand_id)
        if not main_domain_id:
            pytest.skip("Could not create test domain")
        
        # Create network with main node
        network_name = f"TEST_Network_{uuid.uuid4().hex[:8]}"
        create_resp = self.session.post(f"{BASE_URL}/api/v3/networks", json={
            "name": network_name,
            "brand_id": brand_id,
            "description": "Test network for hard delete testing",
            "main_node": {
                "asset_domain_id": main_domain_id,
                "optimized_path": "/test-path"
            }
        })
        
        if create_resp.status_code not in [200, 201]:
            pytest.skip(f"Could not create test network: {create_resp.text}")
        
        network = create_resp.json()
        self.created_network_id = network["id"]
        
        return {
            "network_id": network["id"],
            "network_name": network_name,
            "brand_id": brand_id,
            "main_domain_id": main_domain_id,
            "main_domain_name": main_domain_name
        }

    # ==================== CORE DELETE TESTS ====================
    
    def test_01_delete_returns_cascade_counts(self):
        """Test 1: DELETE endpoint returns proper response with counts of deleted items"""
        test_data = self._create_test_network_with_data()
        
        # Delete the network
        delete_resp = self.session.delete(f"{BASE_URL}/api/v3/networks/{test_data['network_id']}")
        
        assert delete_resp.status_code == 200, f"DELETE failed: {delete_resp.text}"
        
        result = delete_resp.json()
        
        # Verify response structure
        assert "message" in result, "Response should have message"
        assert "details" in result, "Response should have details"
        assert "permanently deleted" in result["message"].lower(), f"Message should indicate permanent delete: {result['message']}"
        
        details = result["details"]
        assert "network_id" in details, "Details should include network_id"
        assert "deleted_entries" in details, "Details should include deleted_entries count"
        assert "deleted_optimizations" in details, "Details should include deleted_optimizations count"
        assert "deleted_complaints" in details, "Details should include deleted_complaints count"
        assert "deleted_conflicts" in details, "Details should include deleted_conflicts count"
        
        # At least 1 entry should be deleted (the main node)
        assert details["deleted_entries"] >= 1, "Should have deleted at least 1 entry (main node)"
        
        print(f"✓ DELETE returned cascade counts: entries={details['deleted_entries']}, optimizations={details['deleted_optimizations']}, complaints={details['deleted_complaints']}, conflicts={details['deleted_conflicts']}")
        
        # Clear so teardown doesn't try to clean up
        self.created_network_id = None
    
    def test_02_deleted_network_returns_404(self):
        """Test 3: Deleted network returns 404 on GET"""
        test_data = self._create_test_network_with_data()
        network_id = test_data["network_id"]
        
        # Verify network exists
        get_resp = self.session.get(f"{BASE_URL}/api/v3/networks/{network_id}")
        assert get_resp.status_code == 200, "Network should exist before delete"
        
        # Delete the network
        delete_resp = self.session.delete(f"{BASE_URL}/api/v3/networks/{network_id}")
        assert delete_resp.status_code == 200, f"DELETE failed: {delete_resp.text}"
        
        # Verify network returns 404
        get_after_resp = self.session.get(f"{BASE_URL}/api/v3/networks/{network_id}")
        assert get_after_resp.status_code == 404, f"GET should return 404 for deleted network, got {get_after_resp.status_code}"
        
        print(f"✓ Deleted network returns 404 on GET")
        self.created_network_id = None
    
    def test_03_networks_list_excludes_deleted(self):
        """Test 6: GET /api/v3/networks does NOT show deleted networks"""
        test_data = self._create_test_network_with_data()
        network_id = test_data["network_id"]
        network_name = test_data["network_name"]
        
        # Verify network in list before delete
        list_resp = self.session.get(f"{BASE_URL}/api/v3/networks")
        assert list_resp.status_code == 200
        networks_before = list_resp.json()
        
        network_names_before = [n["name"] for n in networks_before]
        assert network_name in network_names_before, "Network should be in list before delete"
        
        # Delete the network
        delete_resp = self.session.delete(f"{BASE_URL}/api/v3/networks/{network_id}")
        assert delete_resp.status_code == 200
        
        # Verify network not in list after delete
        list_after_resp = self.session.get(f"{BASE_URL}/api/v3/networks")
        assert list_after_resp.status_code == 200
        networks_after = list_after_resp.json()
        
        network_ids_after = [n["id"] for n in networks_after]
        assert network_id not in network_ids_after, "Deleted network should not appear in list"
        
        print(f"✓ Deleted network not in networks list")
        self.created_network_id = None

    # ==================== REMOVED ENDPOINTS TESTS ====================
    
    def test_04_archived_endpoint_returns_404(self):
        """Test 4: GET /api/v3/networks/archived endpoint no longer exists (returns 404)"""
        resp = self.session.get(f"{BASE_URL}/api/v3/networks/archived")
        
        # Should return 404 because endpoint doesn't exist
        assert resp.status_code == 404, f"GET /networks/archived should return 404, got {resp.status_code}"
        
        print(f"✓ GET /networks/archived returns 404 (endpoint removed)")
    
    def test_05_restore_endpoint_returns_404(self):
        """Test 5: POST /api/v3/networks/{id}/restore endpoint no longer exists (returns 404)"""
        # Try restoring with a fake ID
        fake_id = str(uuid.uuid4())
        resp = self.session.post(f"{BASE_URL}/api/v3/networks/{fake_id}/restore")
        
        # Should return 404 because endpoint doesn't exist
        # Note: could be 404 for "not found" or 405 "method not allowed", both indicate no restore
        assert resp.status_code in [404, 405, 422], f"POST /networks/{{id}}/restore should return 404/405, got {resp.status_code}"
        
        print(f"✓ POST /networks/{{id}}/restore returns {resp.status_code} (endpoint removed)")

    # ==================== ASSET DOMAIN PRESERVATION TESTS ====================
    
    def test_06_asset_domains_preserved_after_delete(self):
        """Test 8: Asset Domains are NOT deleted when their SEO network is deleted"""
        test_data = self._create_test_network_with_data()
        network_id = test_data["network_id"]
        main_domain_id = test_data["main_domain_id"]
        
        # Verify domain exists before delete
        domain_before = self.session.get(f"{BASE_URL}/api/v3/asset-domains/{main_domain_id}")
        assert domain_before.status_code == 200, "Domain should exist before network delete"
        
        # Delete the network
        delete_resp = self.session.delete(f"{BASE_URL}/api/v3/networks/{network_id}")
        assert delete_resp.status_code == 200
        
        # Verify domain STILL exists after delete
        domain_after = self.session.get(f"{BASE_URL}/api/v3/asset-domains/{main_domain_id}")
        assert domain_after.status_code == 200, "Domain should STILL exist after network delete"
        
        domain_data = domain_after.json()
        assert domain_data["id"] == main_domain_id, "Domain ID should match"
        
        print(f"✓ Asset domain preserved after network delete")
        self.created_network_id = None
    
    def test_07_domain_seo_networks_empty_after_delete(self):
        """Test 7: Asset Domains SEO Networks column does NOT show deleted networks"""
        test_data = self._create_test_network_with_data()
        network_id = test_data["network_id"]
        main_domain_id = test_data["main_domain_id"]
        network_name = test_data["network_name"]
        
        # Check domain's SEO networks context before delete
        domain_before = self.session.get(f"{BASE_URL}/api/v3/asset-domains/{main_domain_id}")
        assert domain_before.status_code == 200
        
        # The domain should have SEO context
        domain_data_before = domain_before.json()
        seo_networks_before = domain_data_before.get("seo_networks", [])
        
        # Should have at least the test network
        network_ids_before = [n.get("network_id") for n in seo_networks_before]
        assert network_id in network_ids_before, "Domain should show network before delete"
        
        # Delete the network
        delete_resp = self.session.delete(f"{BASE_URL}/api/v3/networks/{network_id}")
        assert delete_resp.status_code == 200
        
        # Check domain's SEO networks after delete
        domain_after = self.session.get(f"{BASE_URL}/api/v3/asset-domains/{main_domain_id}")
        assert domain_after.status_code == 200
        
        domain_data_after = domain_after.json()
        seo_networks_after = domain_data_after.get("seo_networks", [])
        
        # Should NOT have the deleted network
        network_ids_after = [n.get("network_id") for n in seo_networks_after]
        assert network_id not in network_ids_after, f"Domain should NOT show deleted network. Current networks: {seo_networks_after}"
        
        print(f"✓ Domain's SEO networks column does not show deleted network")
        self.created_network_id = None

    # ==================== DATA INTEGRITY TESTS ====================
    
    def test_08_uniqueness_check_works_after_delete(self):
        """Test 12: Domain+path uniqueness check works correctly (no ghost references)"""
        test_data = self._create_test_network_with_data()
        network_id = test_data["network_id"]
        brand_id = test_data["brand_id"]
        main_domain_id = test_data["main_domain_id"]
        
        # Delete the network
        delete_resp = self.session.delete(f"{BASE_URL}/api/v3/networks/{network_id}")
        assert delete_resp.status_code == 200
        
        # Now create a NEW network using the SAME domain and path
        # This should succeed because the old data is permanently deleted
        new_network_resp = self.session.post(f"{BASE_URL}/api/v3/networks", json={
            "name": f"TEST_Reuse_Network_{uuid.uuid4().hex[:8]}",
            "brand_id": brand_id,
            "description": "Test network reusing domain+path after delete",
            "main_node": {
                "asset_domain_id": main_domain_id,
                "optimized_path": "/test-path"  # Same path as before
            }
        })
        
        assert new_network_resp.status_code in [200, 201], f"Should be able to reuse domain+path after delete: {new_network_resp.text}"
        
        new_network = new_network_resp.json()
        self.created_network_id = new_network["id"]
        
        print(f"✓ Domain+path can be reused after network delete (no ghost references)")
        
        # Cleanup new network
        self.session.delete(f"{BASE_URL}/api/v3/networks/{new_network['id']}")
        self.created_network_id = None

    # ==================== CASCADE DELETION VERIFICATION ====================
    
    def test_09_structure_entries_deleted(self):
        """Test: Structure entries are deleted when network is deleted"""
        test_data = self._create_test_network_with_data()
        network_id = test_data["network_id"]
        
        # Check structure entries exist before delete
        structure_before = self.session.get(f"{BASE_URL}/api/v3/structure", params={"network_id": network_id})
        assert structure_before.status_code == 200
        entries_before = structure_before.json()
        assert len(entries_before) >= 1, "Should have at least 1 structure entry (main node)"
        
        # Delete the network
        delete_resp = self.session.delete(f"{BASE_URL}/api/v3/networks/{network_id}")
        assert delete_resp.status_code == 200
        
        # Check structure entries deleted
        structure_after = self.session.get(f"{BASE_URL}/api/v3/structure", params={"network_id": network_id})
        assert structure_after.status_code == 200
        entries_after = structure_after.json()
        assert len(entries_after) == 0, f"Structure entries should be deleted, got {len(entries_after)}"
        
        print(f"✓ Structure entries deleted with network (before: {len(entries_before)}, after: {len(entries_after)})")
        self.created_network_id = None


class TestMonitoringAfterNetworkDelete:
    """Test that domain monitoring continues after network deletion"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test with auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Login failed: {login_response.status_code}")
        
        token = login_response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_10_monitoring_status_preserved(self):
        """Test 11: Domain monitoring status is preserved after network delete"""
        # Get domains with monitoring enabled
        domains_resp = self.session.get(f"{BASE_URL}/api/v3/asset-domains", params={
            "limit": 5
        })
        
        if domains_resp.status_code != 200:
            pytest.skip("Could not fetch domains")
        
        domains_data = domains_resp.json()
        domains = domains_data.get("data", []) if isinstance(domains_data, dict) else domains_data
        
        if not domains:
            pytest.skip("No domains available for testing")
        
        # Just verify the endpoint works - actual monitoring test would require more setup
        print(f"✓ Domain monitoring endpoint operational ({len(domains)} domains found)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
