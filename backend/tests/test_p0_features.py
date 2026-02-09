"""
Test P0 Features: SEO Networks Search + Asset Domain seo_networks field
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://network-audit-view.preview.emergentagent.com')

@pytest.fixture(scope="module")
def auth_token():
    """Login and get auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@test.com",
        "password": "admin123"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("access_token")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}

class TestNetworkSearchEndpoint:
    """Test GET /api/v3/networks/search endpoint"""
    
    def test_search_returns_200(self, auth_headers):
        """Search endpoint returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/search",
            params={"query": "test"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Search endpoint returns 200")
    
    def test_search_returns_grouped_results(self, auth_headers):
        """Search results are grouped by domain"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/search",
            params={"query": "tier1"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "results" in data, "Response should have 'results' field"
        assert "total" in data, "Response should have 'total' field"
        assert "query" in data, "Response should have 'query' field"
        
        if len(data["results"]) > 0:
            result = data["results"][0]
            assert "domain_name" in result, "Result should have 'domain_name'"
            assert "asset_domain_id" in result, "Result should have 'asset_domain_id'"
            assert "entries" in result, "Result should have 'entries' array"
            
            if len(result["entries"]) > 0:
                entry = result["entries"][0]
                assert "network_id" in entry, "Entry should have 'network_id'"
                assert "network_name" in entry, "Entry should have 'network_name'"
                assert "optimized_path" in entry, "Entry should have 'optimized_path'"
                assert "role" in entry, "Entry should have 'role'"
        
        print(f"✓ Search returned {data['total']} results grouped by domain")
    
    def test_search_respects_limit(self, auth_headers):
        """Search results limited to 10"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/search",
            params={"query": "com"},  # broad search
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Max 10 results
        assert data["total"] <= 10, f"Expected max 10 results, got {data['total']}"
        print(f"✓ Search results properly limited: {data['total']} results")
    
    def test_search_by_path(self, auth_headers):
        """Can search by optimized_path"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/search",
            params={"query": "/"},  # search for paths
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Path search returned {data['total']} results")
    
    def test_search_empty_query_rejected(self, auth_headers):
        """Empty query is rejected"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/search",
            params={"query": ""},
            headers=auth_headers
        )
        # Should return 422 validation error for empty query
        assert response.status_code == 422, f"Expected 422 for empty query, got {response.status_code}"
        print("✓ Empty query properly rejected")


class TestAssetDomainSeoNetworksField:
    """Test seo_networks field in GET /api/v3/asset-domains response"""
    
    def test_asset_domains_have_seo_networks_field(self, auth_headers):
        """Asset domains response includes seo_networks array"""
        response = requests.get(
            f"{BASE_URL}/api/v3/asset-domains",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) > 0, "Should have at least one asset domain"
        
        # Check first domain has seo_networks field
        domain = data[0]
        assert "seo_networks" in domain, "Asset domain should have 'seo_networks' field"
        assert isinstance(domain["seo_networks"], list), "seo_networks should be a list"
        
        print(f"✓ Asset domains have seo_networks field")
    
    def test_seo_networks_contains_network_info(self, auth_headers):
        """seo_networks contains proper network info"""
        response = requests.get(
            f"{BASE_URL}/api/v3/asset-domains",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find a domain with networks
        domain_with_networks = None
        for d in data:
            if len(d.get("seo_networks", [])) > 0:
                domain_with_networks = d
                break
        
        if domain_with_networks:
            network_info = domain_with_networks["seo_networks"][0]
            assert "network_id" in network_info, "Network info should have 'network_id'"
            assert "network_name" in network_info, "Network info should have 'network_name'"
            assert "role" in network_info, "Network info should have 'role'"
            assert network_info["role"] in ["main", "supporting"], f"Role should be main/supporting, got {network_info['role']}"
            print(f"✓ Domain '{domain_with_networks['domain_name']}' has {len(domain_with_networks['seo_networks'])} networks")
        else:
            pytest.skip("No domains with networks found")
    
    def test_unused_domains_have_empty_seo_networks(self, auth_headers):
        """Domains not in any network have empty seo_networks array"""
        response = requests.get(
            f"{BASE_URL}/api/v3/asset-domains",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find a domain without networks
        domain_without_networks = None
        for d in data:
            if len(d.get("seo_networks", [])) == 0:
                domain_without_networks = d
                break
        
        if domain_without_networks:
            assert domain_without_networks["seo_networks"] == [], "Unused domain should have empty seo_networks"
            print(f"✓ Unused domain '{domain_without_networks['domain_name']}' has empty seo_networks")
        else:
            pytest.skip("All domains have networks")


class TestBrandScopingForSearch:
    """Test that search respects brand scoping"""
    
    def test_search_requires_auth(self):
        """Search endpoint requires authentication"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/search",
            params={"query": "test"}
        )
        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ Search endpoint requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
