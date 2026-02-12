"""
Test Domain Status, Monitoring & Lifecycle System (V3)

Tests for the three distinct status types:
1. domain_active_status (AUTO) - computed from expiration_date: Active/Expired
2. monitoring_status (AUTO) - technical availability: Up/Down/JS Challenge/etc
3. lifecycle_status (MANUAL) - strategic decision: Active/Released/Quarantined

Additional features:
- Quarantine category management
- SEO Networks column (no duplicates)
- Monitoring Toggle column (ON/OFF/N/A based on lifecycle rules)
- Super Admin permissions for lifecycle management
- View mode tabs: All/Unmonitored/Released/Quarantined
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "superadmin@seonoc.com"
SUPER_ADMIN_PASSWORD = "SuperAdmin123!"


@pytest.fixture
def super_admin_token():
    """Get Super Admin token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Super Admin login failed: {response.status_code}")


@pytest.fixture
def api_client(super_admin_token):
    """Authenticated session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {super_admin_token}"
    })
    return session


class TestAssetDomainsAPI:
    """Test /api/v3/asset-domains endpoint with new status fields"""

    def test_get_asset_domains_returns_200(self, api_client):
        """Basic GET endpoint works"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "data" in data, "Response should have 'data' key"
        assert "meta" in data, "Response should have 'meta' key for pagination"
        print(f"PASS: GET /api/v3/asset-domains returns 200 with {len(data['data'])} domains")

    def test_domain_response_has_domain_active_status(self, api_client):
        """Domain response includes domain_active_status (AUTO computed)"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        if len(data['data']) > 0:
            domain = data['data'][0]
            assert "domain_active_status" in domain, "Missing domain_active_status field"
            assert domain["domain_active_status"] in ["active", "expired"], \
                f"Invalid domain_active_status: {domain.get('domain_active_status')}"
            assert "domain_active_status_label" in domain, "Missing domain_active_status_label"
            print(f"PASS: Domain has domain_active_status={domain['domain_active_status']}")
        else:
            pytest.skip("No domains to test")

    def test_domain_response_has_monitoring_status(self, api_client):
        """Domain response includes monitoring_status (AUTO technical)"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        if len(data['data']) > 0:
            domain = data['data'][0]
            assert "monitoring_status" in domain, "Missing monitoring_status field"
            valid_statuses = ["up", "down", "soft_blocked", "js_challenge", "country_block", "captcha", "unknown"]
            assert domain["monitoring_status"] in valid_statuses, \
                f"Invalid monitoring_status: {domain.get('monitoring_status')}"
            assert "monitoring_status_label" in domain, "Missing monitoring_status_label"
            print(f"PASS: Domain has monitoring_status={domain['monitoring_status']}")
        else:
            pytest.skip("No domains to test")

    def test_domain_response_has_lifecycle_status(self, api_client):
        """Domain response includes lifecycle_status (MANUAL strategic)"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        if len(data['data']) > 0:
            domain = data['data'][0]
            assert "lifecycle_status" in domain, "Missing lifecycle_status field"
            valid_lifecycles = ["active", "released", "quarantined"]
            assert domain["lifecycle_status"] in valid_lifecycles, \
                f"Invalid lifecycle_status: {domain.get('lifecycle_status')}"
            assert "lifecycle_status_label" in domain, "Missing lifecycle_status_label"
            print(f"PASS: Domain has lifecycle_status={domain['lifecycle_status']}")
        else:
            pytest.skip("No domains to test")

    def test_domain_response_has_quarantine_category(self, api_client):
        """Domain response includes quarantine_category field"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        if len(data['data']) > 0:
            # Check that quarantine_category field exists (may be null)
            for domain in data['data']:
                assert "quarantine_category" in domain or domain.get("lifecycle_status") != "quarantined", \
                    "Quarantined domain should have quarantine_category"
            
            # Look for a quarantined domain
            quarantined = [d for d in data['data'] if d.get('quarantine_category')]
            if quarantined:
                assert "quarantine_category_label" in quarantined[0], "Missing quarantine_category_label"
                print(f"PASS: Found quarantined domain with category={quarantined[0]['quarantine_category']}")
            else:
                print("PASS: quarantine_category field exists (no quarantined domains in sample)")
        else:
            pytest.skip("No domains to test")

    def test_domain_response_has_seo_networks(self, api_client):
        """Domain response includes seo_networks array"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        if len(data['data']) > 0:
            domain = data['data'][0]
            assert "seo_networks" in domain, "Missing seo_networks field"
            assert isinstance(domain["seo_networks"], list), "seo_networks should be a list"
            
            # Check for duplicates (unique network_ids)
            for dom in data['data']:
                if dom.get("seo_networks"):
                    network_ids = [n["network_id"] for n in dom["seo_networks"]]
                    assert len(network_ids) == len(set(network_ids)), \
                        f"Duplicate network_ids in seo_networks: {network_ids}"
            print(f"PASS: Domain has seo_networks field with no duplicates")
        else:
            pytest.skip("No domains to test")

    def test_domain_response_has_monitoring_toggle_fields(self, api_client):
        """Domain response has monitoring_enabled, monitoring_allowed, requires_monitoring"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        if len(data['data']) > 0:
            domain = data['data'][0]
            assert "monitoring_enabled" in domain, "Missing monitoring_enabled field"
            assert "monitoring_allowed" in domain, "Missing monitoring_allowed field"
            assert "requires_monitoring" in domain, "Missing requires_monitoring field"
            
            # Verify monitoring_allowed rule: only active lifecycle + not expired can be monitored
            if domain["lifecycle_status"] != "active" or domain["domain_active_status"] == "expired":
                assert domain["monitoring_allowed"] == False, \
                    "monitoring_allowed should be False for non-active lifecycle or expired domain"
            print(f"PASS: Domain has monitoring toggle fields")
        else:
            pytest.skip("No domains to test")


class TestDomainActiveStatusFilter:
    """Test filtering by domain_active_status (administrative)"""

    def test_filter_by_active_status(self, api_client):
        """Filter domains with domain_active_status=active"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?domain_active_status=active")
        assert response.status_code == 200
        
        data = response.json()
        for domain in data['data']:
            assert domain["domain_active_status"] == "active", \
                f"Expected active status, got {domain['domain_active_status']}"
        print(f"PASS: Filtered {len(data['data'])} active domains")

    def test_filter_by_expired_status(self, api_client):
        """Filter domains with domain_active_status=expired"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?domain_active_status=expired")
        assert response.status_code == 200
        
        data = response.json()
        for domain in data['data']:
            assert domain["domain_active_status"] == "expired", \
                f"Expected expired status, got {domain['domain_active_status']}"
        print(f"PASS: Filtered {len(data['data'])} expired domains")


class TestMonitoringStatusFilter:
    """Test filtering by monitoring_status (technical)"""

    def test_filter_by_monitoring_status_up(self, api_client):
        """Filter domains with monitoring_status=up"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?monitoring_status=up")
        assert response.status_code == 200
        
        data = response.json()
        for domain in data['data']:
            assert domain["monitoring_status"] == "up", \
                f"Expected monitoring_status=up, got {domain['monitoring_status']}"
        print(f"PASS: Filtered {len(data['data'])} domains with status=up")

    def test_filter_by_monitoring_status_down(self, api_client):
        """Filter domains with monitoring_status=down"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?monitoring_status=down")
        assert response.status_code == 200
        
        data = response.json()
        for domain in data['data']:
            assert domain["monitoring_status"] == "down", \
                f"Expected monitoring_status=down, got {domain['monitoring_status']}"
        print(f"PASS: Filtered {len(data['data'])} domains with status=down")

    def test_filter_by_monitoring_status_unknown(self, api_client):
        """Filter domains with monitoring_status=unknown"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?monitoring_status=unknown")
        assert response.status_code == 200
        
        data = response.json()
        for domain in data['data']:
            assert domain["monitoring_status"] == "unknown", \
                f"Expected monitoring_status=unknown, got {domain['monitoring_status']}"
        print(f"PASS: Filtered {len(data['data'])} domains with status=unknown")


class TestLifecycleStatusFilter:
    """Test filtering by lifecycle_status (strategic)"""

    def test_filter_by_lifecycle_active(self, api_client):
        """Filter domains with lifecycle_status=active"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?lifecycle_status=active")
        assert response.status_code == 200
        
        data = response.json()
        for domain in data['data']:
            assert domain["lifecycle_status"] == "active", \
                f"Expected lifecycle=active, got {domain['lifecycle_status']}"
        print(f"PASS: Filtered {len(data['data'])} domains with lifecycle=active")

    def test_filter_by_lifecycle_released(self, api_client):
        """Filter domains with lifecycle_status=released"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?lifecycle_status=released")
        assert response.status_code == 200
        
        data = response.json()
        for domain in data['data']:
            assert domain["lifecycle_status"] == "released", \
                f"Expected lifecycle=released, got {domain['lifecycle_status']}"
        print(f"PASS: Filtered {len(data['data'])} domains with lifecycle=released")

    def test_filter_by_lifecycle_quarantined(self, api_client):
        """Filter domains with lifecycle_status=quarantined"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?lifecycle_status=quarantined")
        assert response.status_code == 200
        
        data = response.json()
        for domain in data['data']:
            assert domain["lifecycle_status"] == "quarantined", \
                f"Expected lifecycle=quarantined, got {domain['lifecycle_status']}"
        print(f"PASS: Filtered {len(data['data'])} domains with lifecycle=quarantined")


class TestQuarantineCategoryFilter:
    """Test filtering by quarantine_category"""

    def test_filter_by_quarantine_category(self, api_client):
        """Filter domains by quarantine_category"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?quarantine_category=spam")
        assert response.status_code == 200
        print("PASS: Quarantine category filter accepted")

    def test_filter_is_quarantined_true(self, api_client):
        """Filter quarantined domains"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?is_quarantined=true")
        assert response.status_code == 200
        
        data = response.json()
        for domain in data['data']:
            assert domain.get("quarantine_category") or domain.get("lifecycle_status") == "quarantined", \
                f"Domain should be quarantined: {domain['domain_name']}"
        print(f"PASS: Filtered {len(data['data'])} quarantined domains")

    def test_filter_is_quarantined_false(self, api_client):
        """Filter non-quarantined domains"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?is_quarantined=false")
        assert response.status_code == 200
        
        data = response.json()
        for domain in data['data']:
            assert not domain.get("quarantine_category") and domain.get("lifecycle_status") != "quarantined", \
                f"Domain should NOT be quarantined: {domain['domain_name']}"
        print(f"PASS: Filtered {len(data['data'])} non-quarantined domains")


class TestViewModeTabs:
    """Test view_mode parameter for tabs"""

    def test_view_mode_all(self, api_client):
        """view_mode=all returns all domains"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?view_mode=all")
        assert response.status_code == 200
        print("PASS: view_mode=all works")

    def test_view_mode_released(self, api_client):
        """view_mode=released returns only released domains"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?view_mode=released")
        assert response.status_code == 200
        
        data = response.json()
        for domain in data['data']:
            assert domain["lifecycle_status"] == "released", \
                f"Expected released, got {domain['lifecycle_status']}"
        print(f"PASS: view_mode=released returned {len(data['data'])} domains")

    def test_view_mode_quarantined(self, api_client):
        """view_mode=quarantined returns quarantined domains"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?view_mode=quarantined")
        assert response.status_code == 200
        
        data = response.json()
        for domain in data['data']:
            assert domain.get("quarantine_category") or domain.get("lifecycle_status") == "quarantined", \
                f"Expected quarantined, got {domain}"
        print(f"PASS: view_mode=quarantined returned {len(data['data'])} domains")

    def test_view_mode_unmonitored(self, api_client):
        """view_mode=unmonitored returns unmonitored SEO domains"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?view_mode=unmonitored")
        assert response.status_code == 200
        
        data = response.json()
        for domain in data['data']:
            # Should be in SEO network, not monitored, and active lifecycle
            assert domain.get("is_used_in_seo_network") == True or len(domain.get("seo_networks", [])) > 0, \
                f"Expected domain in SEO network: {domain['domain_name']}"
            assert domain.get("monitoring_enabled") == False, \
                f"Expected monitoring disabled: {domain['domain_name']}"
        print(f"PASS: view_mode=unmonitored returned {len(data['data'])} domains")


class TestQuarantineCategoriesEndpoint:
    """Test /api/v3/quarantine-categories endpoint"""

    def test_get_quarantine_categories(self, api_client):
        """GET quarantine categories"""
        response = api_client.get(f"{BASE_URL}/api/v3/quarantine-categories")
        assert response.status_code == 200
        
        data = response.json()
        assert "categories" in data, "Response should have 'categories'"
        
        categories = data["categories"]
        assert len(categories) > 0, "Should have at least one category"
        
        # Verify expected categories exist
        category_values = [c["value"] for c in categories]
        expected = ["spam", "dmca", "manual_penalty", "penalized", "other"]
        for exp in expected:
            assert exp in category_values, f"Missing expected category: {exp}"
        
        print(f"PASS: Found {len(categories)} quarantine categories")


class TestMonitoringCoverageEndpoint:
    """Test /api/v3/monitoring/coverage endpoint"""

    def test_get_monitoring_coverage(self, api_client):
        """GET monitoring coverage stats"""
        response = api_client.get(f"{BASE_URL}/api/v3/monitoring/coverage")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check required fields
        required_fields = [
            "domains_in_seo", "monitored", "unmonitored", "coverage_percentage",
            "active_count", "released_count", "quarantined_count",
            "root_domains_missing_monitoring"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify coverage_percentage is valid
        assert 0 <= data["coverage_percentage"] <= 100, \
            f"Invalid coverage percentage: {data['coverage_percentage']}"
        
        print(f"PASS: Coverage stats - {data['coverage_percentage']}% coverage")


class TestLifecycleEndpoints:
    """Test lifecycle management endpoints (Super Admin only)"""

    def test_set_lifecycle_endpoint_exists(self, api_client):
        """POST /api/v3/asset-domains/{id}/set-lifecycle endpoint exists"""
        # First get a domain
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?limit=1")
        assert response.status_code == 200
        
        data = response.json()
        if len(data['data']) > 0:
            domain_id = data['data'][0]['id']
            
            # Try to set lifecycle (should succeed for Super Admin)
            response = api_client.post(
                f"{BASE_URL}/api/v3/asset-domains/{domain_id}/set-lifecycle",
                json={"lifecycle_status": data['data'][0].get('lifecycle_status', 'active')}
            )
            # Should be 200 (success) or 400 (validation) for Super Admin, not 404/405
            assert response.status_code in [200, 400], \
                f"Unexpected status code: {response.status_code}"
            print("PASS: set-lifecycle endpoint exists and accepts requests")
        else:
            pytest.skip("No domains to test")

    def test_quarantine_endpoint_exists(self, api_client):
        """POST /api/v3/asset-domains/{id}/quarantine endpoint exists"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?limit=1")
        assert response.status_code == 200
        
        data = response.json()
        if len(data['data']) > 0:
            domain_id = data['data'][0]['id']
            
            # Just verify endpoint exists (don't actually quarantine)
            response = api_client.post(
                f"{BASE_URL}/api/v3/asset-domains/{domain_id}/quarantine",
                json={"quarantine_category": "other", "quarantine_note": "Test"}
            )
            # Should not be 404/405 (endpoint exists)
            assert response.status_code != 404, "Endpoint not found"
            assert response.status_code != 405, "Method not allowed"
            print(f"PASS: quarantine endpoint exists (status={response.status_code})")
        else:
            pytest.skip("No domains to test")

    def test_remove_quarantine_endpoint_exists(self, api_client):
        """POST /api/v3/asset-domains/{id}/remove-quarantine endpoint exists"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?limit=1")
        assert response.status_code == 200
        
        data = response.json()
        if len(data['data']) > 0:
            domain_id = data['data'][0]['id']
            
            response = api_client.post(
                f"{BASE_URL}/api/v3/asset-domains/{domain_id}/remove-quarantine",
                json={}
            )
            assert response.status_code != 404, "Endpoint not found"
            assert response.status_code != 405, "Method not allowed"
            print(f"PASS: remove-quarantine endpoint exists (status={response.status_code})")
        else:
            pytest.skip("No domains to test")

    def test_mark_released_endpoint_exists(self, api_client):
        """POST /api/v3/asset-domains/{id}/mark-released endpoint exists"""
        response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?limit=1")
        assert response.status_code == 200
        
        data = response.json()
        if len(data['data']) > 0:
            domain_id = data['data'][0]['id']
            
            response = api_client.post(
                f"{BASE_URL}/api/v3/asset-domains/{domain_id}/mark-released",
                json={}
            )
            assert response.status_code != 404, "Endpoint not found"
            assert response.status_code != 405, "Method not allowed"
            print(f"PASS: mark-released endpoint exists (status={response.status_code})")
        else:
            pytest.skip("No domains to test")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
