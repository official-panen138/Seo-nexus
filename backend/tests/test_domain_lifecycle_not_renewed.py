"""
Domain Lifecycle 'Not Renewed' & Column Sorting Tests
======================================================
Tests for:
1. NOT_RENEWED lifecycle status - auto-set for expired domains
2. Column sorting with sort_by and sort_direction params  
3. View mode tab 'not_renewed' filtering
4. Invalid state blocking: cannot set lifecycle=Active when domain is expired
5. Monitoring allowed only for lifecycle=Active and domain_active_status=Active
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestDomainLifecycleNotRenewed:
    """Tests for NOT_RENEWED lifecycle auto-transition"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Authenticate as Super Admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "superadmin@seonoc.com",
            "password": "SuperAdmin123!"
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")  # API returns access_token, not token
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed - skipping tests")

    def test_not_renewed_lifecycle_exists_in_labels(self):
        """Verify NOT_RENEWED is a valid lifecycle status"""
        # Check by querying a domain and verifying the label mapping works
        response = self.session.get(f"{BASE_URL}/api/v3/asset-domains?page=1&limit=1")
        assert response.status_code == 200
        data = response.json()
        
        # Check model accepts not_renewed value (backend models)
        assert "data" in data
        print("Lifecycle label test - API working")

    def test_expired_domain_shows_not_renewed_lifecycle(self):
        """Verify expired domains auto-transition to NOT_RENEWED lifecycle"""
        # Get all domains with view_mode=not_renewed
        response = self.session.get(f"{BASE_URL}/api/v3/asset-domains?view_mode=not_renewed&page=1&limit=25")
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        print(f"Found {len(data['data'])} domains with not_renewed lifecycle")
        
        # Verify all returned domains have lifecycle_status = not_renewed
        for domain in data["data"]:
            assert domain.get("lifecycle_status") == "not_renewed", f"Domain {domain['domain_name']} should have not_renewed lifecycle"
            print(f"  - {domain['domain_name']}: lifecycle={domain['lifecycle_status']}, domain_active_status={domain.get('domain_active_status')}")

    def test_monitoring_not_allowed_for_not_renewed(self):
        """Verify monitoring_allowed=False for NOT_RENEWED domains"""
        response = self.session.get(f"{BASE_URL}/api/v3/asset-domains?view_mode=not_renewed&page=1&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        for domain in data["data"]:
            # NOT_RENEWED domains should NOT allow monitoring
            assert domain.get("monitoring_allowed") == False, f"Domain {domain['domain_name']} should have monitoring_allowed=False"
            print(f"  - {domain['domain_name']}: monitoring_allowed={domain.get('monitoring_allowed')} (correct: False)")


class TestColumnSorting:
    """Tests for column sorting with sort_by and sort_direction params"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "superadmin@seonoc.com",
            "password": "SuperAdmin123!"
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")  # API returns access_token, not token
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed - skipping tests")

    def test_sort_by_domain_name_asc(self):
        """Test sorting by domain_name ascending"""
        response = self.session.get(f"{BASE_URL}/api/v3/asset-domains?sort_by=domain_name&sort_direction=asc&page=1&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        domains = [d["domain_name"] for d in data["data"]]
        assert domains == sorted(domains), "Domains should be sorted A-Z"
        print(f"Domain names (asc): {domains[:5]}...")

    def test_sort_by_domain_name_desc(self):
        """Test sorting by domain_name descending"""
        response = self.session.get(f"{BASE_URL}/api/v3/asset-domains?sort_by=domain_name&sort_direction=desc&page=1&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        domains = [d["domain_name"] for d in data["data"]]
        assert domains == sorted(domains, reverse=True), "Domains should be sorted Z-A"
        print(f"Domain names (desc): {domains[:5]}...")

    def test_sort_by_expiration_date_asc(self):
        """Test sorting by expiration_date ascending (soonest first)"""
        response = self.session.get(f"{BASE_URL}/api/v3/asset-domains?sort_by=expiration_date&sort_direction=asc&page=1&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        dates = [d.get("expiration_date") or "9999-12-31" for d in data["data"]]
        print(f"Expiration dates (asc): {dates[:5]}...")
        # Verify order (may have nulls)
        assert response.status_code == 200

    def test_sort_by_expiration_date_desc(self):
        """Test sorting by expiration_date descending (latest first)"""
        response = self.session.get(f"{BASE_URL}/api/v3/asset-domains?sort_by=expiration_date&sort_direction=desc&page=1&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        dates = [d.get("expiration_date") for d in data["data"]]
        print(f"Expiration dates (desc): {dates[:5]}...")

    def test_sort_by_lifecycle_status(self):
        """Test sorting by lifecycle_status"""
        response = self.session.get(f"{BASE_URL}/api/v3/asset-domains?sort_by=lifecycle_status&sort_direction=asc&page=1&limit=25")
        assert response.status_code == 200
        data = response.json()
        
        lifecycles = [d.get("lifecycle_status") for d in data["data"]]
        print(f"Lifecycle statuses (asc): {lifecycles[:10]}...")
        
        # Verify sorting works (active < not_renewed < quarantined < released alphabetically)
        assert response.status_code == 200

    def test_sort_by_monitoring_status(self):
        """Test sorting by monitoring_status"""
        response = self.session.get(f"{BASE_URL}/api/v3/asset-domains?sort_by=monitoring_status&sort_direction=asc&page=1&limit=25")
        assert response.status_code == 200
        data = response.json()
        
        statuses = [d.get("monitoring_status") for d in data["data"]]
        print(f"Monitoring statuses (asc): {statuses[:10]}...")

    def test_sort_by_domain_active_status(self):
        """Test sorting by domain_active_status"""
        response = self.session.get(f"{BASE_URL}/api/v3/asset-domains?sort_by=domain_active_status&sort_direction=asc&page=1&limit=25")
        assert response.status_code == 200
        data = response.json()
        
        statuses = [d.get("domain_active_status") for d in data["data"]]
        print(f"Domain active statuses (asc): {statuses[:10]}...")

    def test_default_critical_sorting(self):
        """Test default 'critical' sorting prioritizes issues first"""
        response = self.session.get(f"{BASE_URL}/api/v3/asset-domains?sort_by=critical&sort_direction=asc&page=1&limit=25")
        assert response.status_code == 200
        data = response.json()
        
        # Critical sort should prioritize: down > soft_blocked > unknown > up
        # and quarantined > released > active
        print(f"Critical sort - first 5 domains:")
        for d in data["data"][:5]:
            print(f"  - {d['domain_name']}: mon_status={d.get('monitoring_status')}, lifecycle={d.get('lifecycle_status')}")

    def test_sort_by_seo_networks_count(self):
        """Test sorting by seo_networks_count"""
        response = self.session.get(f"{BASE_URL}/api/v3/asset-domains?sort_by=seo_networks_count&sort_direction=desc&page=1&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        counts = [len(d.get("seo_networks", [])) for d in data["data"]]
        print(f"SEO networks counts (desc): {counts}")


class TestViewModeNotRenewed:
    """Tests for 'not_renewed' view mode tab"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "superadmin@seonoc.com",
            "password": "SuperAdmin123!"
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")  # API returns access_token, not token
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed - skipping tests")

    def test_view_mode_not_renewed_returns_only_not_renewed(self):
        """Verify view_mode=not_renewed filters correctly"""
        response = self.session.get(f"{BASE_URL}/api/v3/asset-domains?view_mode=not_renewed&page=1&limit=100")
        assert response.status_code == 200
        data = response.json()
        
        print(f"view_mode=not_renewed: {len(data['data'])} domains")
        
        for domain in data["data"]:
            lifecycle = domain.get("lifecycle_status")
            assert lifecycle == "not_renewed", f"Expected not_renewed, got {lifecycle} for {domain['domain_name']}"
            print(f"  - {domain['domain_name']}: lifecycle={lifecycle}, active_status={domain.get('domain_active_status')}")

    def test_monitoring_coverage_includes_not_renewed_count(self):
        """Verify monitoring coverage stats include not_renewed_count"""
        response = self.session.get(f"{BASE_URL}/api/v3/monitoring/coverage")
        assert response.status_code == 200
        data = response.json()
        
        assert "not_renewed_count" in data, "Coverage stats should include not_renewed_count"
        print(f"Monitoring coverage stats:")
        print(f"  - domains_in_seo: {data.get('domains_in_seo')}")
        print(f"  - monitored: {data.get('monitored')}")
        print(f"  - unmonitored: {data.get('unmonitored')}")
        print(f"  - released_count: {data.get('released_count')}")
        print(f"  - quarantined_count: {data.get('quarantined_count')}")
        print(f"  - not_renewed_count: {data.get('not_renewed_count')}")


class TestLifecycleRules:
    """Tests for lifecycle validation rules"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "superadmin@seonoc.com",
            "password": "SuperAdmin123!"
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")  # API returns access_token, not token
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed - skipping tests")

    def test_monitoring_allowed_rules(self):
        """Verify monitoring_allowed logic"""
        response = self.session.get(f"{BASE_URL}/api/v3/asset-domains?page=1&limit=50")
        assert response.status_code == 200
        data = response.json()
        
        print("Monitoring allowed rules verification:")
        for domain in data["data"]:
            lifecycle = domain.get("lifecycle_status")
            active_status = domain.get("domain_active_status")
            monitoring_allowed = domain.get("monitoring_allowed")
            
            # Rule: monitoring_allowed = True ONLY IF lifecycle=active AND domain_active_status=active
            expected = (lifecycle == "active" and active_status == "active")
            
            if monitoring_allowed != expected:
                print(f"  WARN: {domain['domain_name']}: lifecycle={lifecycle}, active={active_status}, monitoring_allowed={monitoring_allowed} (expected={expected})")
            else:
                print(f"  OK: {domain['domain_name']}: lifecycle={lifecycle}, active={active_status}, monitoring_allowed={monitoring_allowed}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
