"""
Test Suite for Domain Lifecycle & Quarantine Features
=====================================================
Tests the new V3 features:
1. Domain Lifecycle Status management (active, expired_pending, expired_released, inactive, archived)
2. Domain Quarantine management (spam_murni, dmca, penalized, etc.)
3. SEO Monitoring Coverage stats
4. Filter and view mode capabilities
5. Permission checks (Super Admin only for lifecycle/quarantine)
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Credentials
SUPER_ADMIN_CREDS = {"email": "superadmin@seonoc.com", "password": "SuperAdmin123!"}
REGULAR_ADMIN_CREDS = {"email": "admin@seonoc.com", "password": "Admin123!"}


@pytest.fixture(scope="module")
def super_admin_token():
    """Get Super Admin authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json=SUPER_ADMIN_CREDS
    )
    if response.status_code != 200:
        pytest.skip(f"Super Admin login failed: {response.text}")
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def regular_admin_token():
    """Get Regular Admin authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json=REGULAR_ADMIN_CREDS
    )
    if response.status_code != 200:
        pytest.skip(f"Regular Admin login failed: {response.text}")
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def super_admin_client(super_admin_token):
    """Session with Super Admin auth"""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {super_admin_token}",
        "Content-Type": "application/json"
    })
    return session


@pytest.fixture(scope="module")
def regular_admin_client(regular_admin_token):
    """Session with Regular Admin auth"""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {regular_admin_token}",
        "Content-Type": "application/json"
    })
    return session


class TestQuarantineCategories:
    """Test GET /api/v3/quarantine-categories"""
    
    def test_get_quarantine_categories_returns_200(self, super_admin_client):
        """Verify quarantine categories endpoint returns 200"""
        response = super_admin_client.get(f"{BASE_URL}/api/v3/quarantine-categories")
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.json()}")
        assert response.status_code == 200
        
    def test_quarantine_categories_contains_expected_categories(self, super_admin_client):
        """Verify all expected quarantine categories are returned"""
        response = super_admin_client.get(f"{BASE_URL}/api/v3/quarantine-categories")
        assert response.status_code == 200
        
        data = response.json()
        assert "categories" in data
        
        categories = data["categories"]
        expected_values = ["spam_murni", "dmca", "rollback_restore", "penalized", "manual_review", "custom"]
        
        category_values = [cat.get("value") for cat in categories]
        for expected in expected_values:
            assert expected in category_values, f"Missing category: {expected}"
        
        print(f"Found categories: {category_values}")


class TestSeoMonitoringCoverage:
    """Test GET /api/v3/monitoring/coverage"""
    
    def test_monitoring_coverage_returns_200(self, super_admin_client):
        """Verify monitoring coverage endpoint returns 200"""
        response = super_admin_client.get(f"{BASE_URL}/api/v3/monitoring/coverage")
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.json()}")
        assert response.status_code == 200
        
    def test_monitoring_coverage_contains_required_fields(self, super_admin_client):
        """Verify all required coverage stats fields are present"""
        response = super_admin_client.get(f"{BASE_URL}/api/v3/monitoring/coverage")
        assert response.status_code == 200
        
        data = response.json()
        
        # Required fields from SeoMonitoringCoverageStats model
        required_fields = [
            "domains_in_seo",
            "monitored",
            "unmonitored",
            "coverage_percentage",
            "active_monitored",
            "active_unmonitored",
            "expired_pending_count",
            "expired_released_count",
            "quarantined_count",
            "root_domains_missing_monitoring"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
            print(f"  {field}: {data[field]}")
        
    def test_coverage_percentage_is_valid(self, super_admin_client):
        """Verify coverage percentage is between 0 and 100"""
        response = super_admin_client.get(f"{BASE_URL}/api/v3/monitoring/coverage")
        assert response.status_code == 200
        
        data = response.json()
        coverage = data["coverage_percentage"]
        
        assert isinstance(coverage, (int, float)), "coverage_percentage should be numeric"
        assert 0 <= coverage <= 100, f"coverage_percentage should be 0-100, got {coverage}"


class TestAssetDomainsFilters:
    """Test GET /api/v3/asset-domains with new filters"""
    
    def test_filter_by_lifecycle_status(self, super_admin_client):
        """Test filtering by lifecycle_status parameter"""
        # Test active filter
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"lifecycle_status": "active", "limit": 5}
        )
        assert response.status_code == 200
        print(f"Active lifecycle filter: {response.json().get('meta', {}).get('total', 0)} domains")
        
    def test_filter_by_quarantine_category(self, super_admin_client):
        """Test filtering by quarantine_category parameter"""
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"quarantine_category": "spam_murni", "limit": 5}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"Spam Murni quarantine filter: {data.get('meta', {}).get('total', 0)} domains")
        
        # Verify all returned domains have the correct quarantine category
        for domain in data.get("data", []):
            if domain.get("quarantine_category"):
                assert domain["quarantine_category"] == "spam_murni"
                
    def test_filter_is_quarantined_true(self, super_admin_client):
        """Test filtering by is_quarantined=true"""
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"is_quarantined": True, "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"Quarantined domains: {data.get('meta', {}).get('total', 0)}")
        
        # Verify all returned domains are quarantined
        for domain in data.get("data", []):
            assert domain.get("quarantine_category") is not None, f"Domain {domain['domain_name']} should be quarantined"
            
    def test_filter_is_quarantined_false(self, super_admin_client):
        """Test filtering by is_quarantined=false"""
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"is_quarantined": False, "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"Non-quarantined domains: {data.get('meta', {}).get('total', 0)}")
        
    def test_filter_used_in_seo_true(self, super_admin_client):
        """Test filtering by used_in_seo=true"""
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"used_in_seo": True, "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"Domains used in SEO: {data.get('meta', {}).get('total', 0)}")
        
        # Verify all returned domains are used in SEO networks
        for domain in data.get("data", []):
            assert domain.get("is_used_in_seo_network") == True


class TestViewModes:
    """Test view_mode parameter for special views"""
    
    def test_view_mode_released(self, super_admin_client):
        """Test view_mode=released filter"""
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"view_mode": "released", "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"Released domains: {data.get('meta', {}).get('total', 0)}")
        
        # Verify all returned domains have expired_released lifecycle
        for domain in data.get("data", []):
            assert domain.get("domain_lifecycle_status") == "expired_released", \
                f"Domain {domain['domain_name']} should have expired_released status"
                
    def test_view_mode_quarantined(self, super_admin_client):
        """Test view_mode=quarantined filter"""
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"view_mode": "quarantined", "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"Quarantined domains: {data.get('meta', {}).get('total', 0)}")
        
        # Verify all returned domains are quarantined
        for domain in data.get("data", []):
            assert domain.get("quarantine_category") is not None
            
    def test_view_mode_unmonitored(self, super_admin_client):
        """Test view_mode=unmonitored filter"""
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"view_mode": "unmonitored", "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"Unmonitored in SEO domains: {data.get('meta', {}).get('total', 0)}")


class TestDomainQuarantineManagement:
    """Test quarantine management endpoints"""
    
    @pytest.fixture(scope="class")
    def test_domain(self, super_admin_client):
        """Get a domain for testing - preferring non-quarantined first"""
        # First try to find a non-quarantined domain
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"is_quarantined": False, "limit": 1}
        )
        if response.status_code == 200 and response.json().get("data"):
            return response.json()["data"][0]
        
        # Fallback to any domain
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"limit": 1}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data.get("data", [])) > 0, "No domains found for testing"
        return data["data"][0]
    
    def test_quarantine_domain_super_admin(self, super_admin_client, test_domain):
        """Super Admin can quarantine a domain"""
        domain_id = test_domain["id"]
        
        # Skip if already quarantined
        if test_domain.get("quarantine_category"):
            pytest.skip("Test domain is already quarantined")
        
        response = super_admin_client.post(
            f"{BASE_URL}/api/v3/asset-domains/{domain_id}/quarantine",
            json={
                "quarantine_category": "manual_review",
                "quarantine_note": "Test quarantine for testing purposes"
            }
        )
        print(f"Quarantine response: {response.status_code}")
        print(f"Response body: {response.json()}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["quarantine_category"] == "manual_review"
        assert data["quarantine_note"] == "Test quarantine for testing purposes"
        assert data.get("quarantined_at") is not None
        
    def test_quarantine_domain_regular_admin_forbidden(self, regular_admin_client, test_domain):
        """Regular Admin cannot quarantine a domain"""
        domain_id = test_domain["id"]
        
        response = regular_admin_client.post(
            f"{BASE_URL}/api/v3/asset-domains/{domain_id}/quarantine",
            json={
                "quarantine_category": "spam_murni"
            }
        )
        print(f"Regular admin quarantine response: {response.status_code}")
        
        assert response.status_code == 403
        
    def test_remove_quarantine_super_admin(self, super_admin_client, test_domain):
        """Super Admin can remove quarantine from a domain"""
        domain_id = test_domain["id"]
        
        # First ensure domain is quarantined
        check_response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains/{domain_id}"
        )
        if check_response.status_code == 200:
            domain_data = check_response.json()
            if not domain_data.get("quarantine_category"):
                # Quarantine it first
                super_admin_client.post(
                    f"{BASE_URL}/api/v3/asset-domains/{domain_id}/quarantine",
                    json={"quarantine_category": "manual_review"}
                )
        
        response = super_admin_client.post(
            f"{BASE_URL}/api/v3/asset-domains/{domain_id}/remove-quarantine",
            json={"reason": "Test completed"}
        )
        print(f"Remove quarantine response: {response.status_code}")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("quarantine_category") is None
        
    def test_remove_quarantine_regular_admin_forbidden(self, regular_admin_client):
        """Regular Admin cannot remove quarantine"""
        # Get a quarantined domain first
        response = regular_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"is_quarantined": True, "limit": 1}
        )
        if response.status_code != 200 or not response.json().get("data"):
            pytest.skip("No quarantined domains to test")
        
        domain_id = response.json()["data"][0]["id"]
        
        response = regular_admin_client.post(
            f"{BASE_URL}/api/v3/asset-domains/{domain_id}/remove-quarantine",
            json={}
        )
        print(f"Regular admin remove quarantine response: {response.status_code}")
        
        assert response.status_code == 403


class TestDomainLifecycleManagement:
    """Test lifecycle management endpoints"""
    
    @pytest.fixture(scope="class")
    def test_domain_for_lifecycle(self, super_admin_client):
        """Get a domain for lifecycle testing"""
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"lifecycle_status": "active", "limit": 1}
        )
        if response.status_code == 200 and response.json().get("data"):
            return response.json()["data"][0]
        
        # Fallback
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"limit": 1}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data.get("data", [])) > 0, "No domains found for testing"
        return data["data"][0]
        
    def test_mark_released_super_admin(self, super_admin_client):
        """Super Admin can mark domain as released"""
        # Get a domain that isn't already released
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"lifecycle_status": "active", "limit": 1}
        )
        if response.status_code != 200 or not response.json().get("data"):
            pytest.skip("No active domains available for testing")
        
        domain = response.json()["data"][0]
        domain_id = domain["id"]
        original_status = domain.get("domain_lifecycle_status")
        
        response = super_admin_client.post(
            f"{BASE_URL}/api/v3/asset-domains/{domain_id}/mark-released",
            json={"reason": "Test release for testing"}
        )
        print(f"Mark released response: {response.status_code}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["domain_lifecycle_status"] == "expired_released"
        assert data["monitoring_enabled"] == False
        assert data.get("released_at") is not None
        
        # Restore original status
        if original_status and original_status != "expired_released":
            super_admin_client.post(
                f"{BASE_URL}/api/v3/asset-domains/{domain_id}/set-lifecycle",
                json={"lifecycle_status": original_status}
            )
            
    def test_mark_released_regular_admin_forbidden(self, regular_admin_client):
        """Regular Admin cannot mark domain as released"""
        # Get any domain
        response = regular_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"limit": 1}
        )
        if response.status_code != 200 or not response.json().get("data"):
            pytest.skip("No domains available for testing")
        
        domain_id = response.json()["data"][0]["id"]
        
        response = regular_admin_client.post(
            f"{BASE_URL}/api/v3/asset-domains/{domain_id}/mark-released",
            json={}
        )
        print(f"Regular admin mark released response: {response.status_code}")
        
        assert response.status_code == 403
        
    def test_set_lifecycle_super_admin(self, super_admin_client):
        """Super Admin can change domain lifecycle status"""
        # Get a domain
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"limit": 1}
        )
        assert response.status_code == 200
        
        domain = response.json()["data"][0]
        domain_id = domain["id"]
        original_status = domain.get("domain_lifecycle_status", "active")
        
        # Change to inactive
        response = super_admin_client.post(
            f"{BASE_URL}/api/v3/asset-domains/{domain_id}/set-lifecycle",
            json={
                "lifecycle_status": "inactive",
                "reason": "Test lifecycle change"
            }
        )
        print(f"Set lifecycle response: {response.status_code}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["domain_lifecycle_status"] == "inactive"
        
        # Restore original status
        super_admin_client.post(
            f"{BASE_URL}/api/v3/asset-domains/{domain_id}/set-lifecycle",
            json={"lifecycle_status": original_status}
        )
        
    def test_set_lifecycle_regular_admin_forbidden(self, regular_admin_client):
        """Regular Admin cannot change lifecycle status"""
        # Get any domain
        response = regular_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"limit": 1}
        )
        if response.status_code != 200 or not response.json().get("data"):
            pytest.skip("No domains available for testing")
        
        domain_id = response.json()["data"][0]["id"]
        
        response = regular_admin_client.post(
            f"{BASE_URL}/api/v3/asset-domains/{domain_id}/set-lifecycle",
            json={"lifecycle_status": "inactive"}
        )
        print(f"Regular admin set lifecycle response: {response.status_code}")
        
        assert response.status_code == 403


class TestDomainResponseEnrichment:
    """Test that domain responses include new lifecycle/quarantine fields"""
    
    def test_domain_response_includes_lifecycle_fields(self, super_admin_client):
        """Verify domain response includes lifecycle status fields"""
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"limit": 5}
        )
        assert response.status_code == 200
        
        domains = response.json().get("data", [])
        assert len(domains) > 0
        
        for domain in domains:
            # Lifecycle fields
            assert "domain_lifecycle_status" in domain
            assert domain["domain_lifecycle_status"] in ["active", "expired_pending", "expired_released", "inactive", "archived"]
            
            # Monitoring requirement fields
            assert "is_used_in_seo_network" in domain
            assert "requires_monitoring" in domain
            
            print(f"Domain {domain['domain_name']}: lifecycle={domain['domain_lifecycle_status']}, in_seo={domain['is_used_in_seo_network']}")
            
    def test_quarantined_domain_has_label(self, super_admin_client):
        """Verify quarantined domains have category label"""
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"is_quarantined": True, "limit": 5}
        )
        assert response.status_code == 200
        
        domains = response.json().get("data", [])
        
        for domain in domains:
            if domain.get("quarantine_category"):
                assert "quarantine_category_label" in domain
                assert domain["quarantine_category_label"] is not None
                print(f"Domain {domain['domain_name']}: quarantine={domain['quarantine_category']}, label={domain['quarantine_category_label']}")


class TestExistingQuarantinedDomains:
    """Test with existing quarantined domains mentioned in the request"""
    
    def test_domaina_is_quarantined(self, super_admin_client):
        """Verify domaina.com is quarantined"""
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"search": "domaina.com", "limit": 5}
        )
        assert response.status_code == 200
        
        domains = response.json().get("data", [])
        matching = [d for d in domains if "domaina" in d["domain_name"].lower()]
        
        if matching:
            domain = matching[0]
            print(f"Found domain: {domain['domain_name']}, quarantine_category: {domain.get('quarantine_category')}")
            # According to request, domaina.com should be quarantined
            assert domain.get("quarantine_category") is not None, "domaina.com should be quarantined"
        else:
            pytest.skip("domaina.com not found in database")
            
    def test_expiring_7days_test_is_released(self, super_admin_client):
        """Verify expiring-7days-test.com is marked as released"""
        response = super_admin_client.get(
            f"{BASE_URL}/api/v3/asset-domains",
            params={"search": "expiring-7days-test", "limit": 5}
        )
        assert response.status_code == 200
        
        domains = response.json().get("data", [])
        matching = [d for d in domains if "expiring-7days-test" in d["domain_name"].lower()]
        
        if matching:
            domain = matching[0]
            print(f"Found domain: {domain['domain_name']}, lifecycle: {domain.get('domain_lifecycle_status')}")
            # According to request, this should be expired_released
            assert domain.get("domain_lifecycle_status") == "expired_released", "expiring-7days-test.com should be released"
        else:
            pytest.skip("expiring-7days-test.com not found in database")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
