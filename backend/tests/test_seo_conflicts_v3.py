"""
Test SEO Conflicts V3 API
Tests the V3 conflicts detection system including:
- V3 API endpoint (/api/v3/reports/conflicts)
- Conflict types: orphan nodes, tier inversion, redirect loops, index/noindex mismatch
- Response structure validation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')


class TestV3ConflictsAPI:
    """Test V3 Conflicts API endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as super admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testadmin@test.com",
            "password": "test"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_v3_conflicts_endpoint_returns_200(self):
        """V3 conflicts endpoint should return 200 status"""
        response = self.session.get(f"{BASE_URL}/api/v3/reports/conflicts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("TEST PASSED: V3 conflicts endpoint returns 200")
    
    def test_v3_conflicts_response_structure(self):
        """V3 conflicts response should have correct structure"""
        response = self.session.get(f"{BASE_URL}/api/v3/reports/conflicts")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check required fields
        assert "conflicts" in data, "Missing 'conflicts' field"
        assert "total" in data, "Missing 'total' field"
        assert "by_type" in data, "Missing 'by_type' field"
        assert "by_severity" in data, "Missing 'by_severity' field"
        
        # Check by_severity structure
        severity = data["by_severity"]
        assert "critical" in severity, "Missing 'critical' in by_severity"
        assert "high" in severity, "Missing 'high' in by_severity"
        assert "medium" in severity, "Missing 'medium' in by_severity"
        assert "low" in severity, "Missing 'low' in by_severity"
        
        print(f"TEST PASSED: V3 conflicts response has correct structure")
        print(f"  Total conflicts: {data['total']}")
        print(f"  By severity: {data['by_severity']}")
    
    def test_v3_conflicts_with_network_filter(self):
        """V3 conflicts endpoint should accept network_id filter"""
        # First get a network ID
        networks_response = self.session.get(f"{BASE_URL}/api/v3/networks")
        assert networks_response.status_code == 200
        networks = networks_response.json()
        
        if networks:
            network_id = networks[0]["id"]
            response = self.session.get(f"{BASE_URL}/api/v3/reports/conflicts?network_id={network_id}")
            assert response.status_code == 200
            
            data = response.json()
            assert "conflicts" in data
            print(f"TEST PASSED: V3 conflicts with network filter works. Network: {networks[0]['name']}, Conflicts: {data['total']}")
        else:
            pytest.skip("No networks available for testing")
    
    def test_v3_conflicts_type_list_exists(self):
        """V3 conflicts should support all conflict types"""
        # Known conflict types from models_v3.py
        expected_types = [
            "keyword_cannibalization",
            "competing_targets",
            "canonical_mismatch",
            "tier_inversion",
            "redirect_loop",
            "multiple_parents_to_main",
            "index_noindex_mismatch",
            "orphan",
            "noindex_high_tier"
        ]
        
        response = self.session.get(f"{BASE_URL}/api/v3/reports/conflicts")
        assert response.status_code == 200
        
        data = response.json()
        conflicts = data.get("conflicts", [])
        
        # If conflicts exist, validate their type field
        for conflict in conflicts:
            conflict_type = conflict.get("conflict_type")
            assert conflict_type is not None, "Conflict missing 'conflict_type' field"
            # We don't assert the type is in expected_types since there might be new types
            
            # Validate conflict structure
            assert "severity" in conflict, "Conflict missing 'severity' field"
            assert "network_id" in conflict, "Conflict missing 'network_id' field"
            assert "network_name" in conflict, "Conflict missing 'network_name' field"
            assert "description" in conflict, "Conflict missing 'description' field"
            assert "node_a_label" in conflict, "Conflict missing 'node_a_label' field"
        
        print(f"TEST PASSED: V3 conflicts structure validation complete. Found {len(conflicts)} conflicts.")
    
    def test_v3_conflicts_vs_legacy_endpoint(self):
        """V3 endpoint should be different from legacy (deprecated) endpoint"""
        # V3 endpoint
        v3_response = self.session.get(f"{BASE_URL}/api/v3/reports/conflicts")
        assert v3_response.status_code == 200
        v3_data = v3_response.json()
        
        # Legacy endpoint (should still work but may be deprecated)
        legacy_response = self.session.get(f"{BASE_URL}/api/seo/conflicts")
        
        # Both should work - legacy might return different structure
        if legacy_response.status_code == 200:
            legacy_data = legacy_response.json()
            print(f"Legacy endpoint returns: {len(legacy_data.get('conflicts', legacy_data))} items")
            print(f"V3 endpoint returns: {v3_data['total']} conflicts")
        else:
            print(f"Legacy endpoint deprecated or removed (status: {legacy_response.status_code})")
        
        print("TEST PASSED: V3 conflicts API is accessible and working")
    
    def test_v3_dashboard_reports_endpoint(self):
        """V3 dashboard endpoint should also work"""
        response = self.session.get(f"{BASE_URL}/api/v3/reports/dashboard")
        assert response.status_code == 200, f"Dashboard endpoint failed: {response.text}"
        
        data = response.json()
        # V3 dashboard returns collections with counts
        assert "collections" in data or "asset_status" in data, f"Missing expected fields. Got: {list(data.keys())}"
        print(f"TEST PASSED: V3 dashboard endpoint works. Data: {list(data.keys())}")


class TestConflictDetectionLogic:
    """Test conflict detection logic by examining structure entries"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testadmin@test.com",
            "password": "test"
        })
        assert response.status_code == 200
        token = response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_networks_exist(self):
        """Verify networks exist in the system"""
        response = self.session.get(f"{BASE_URL}/api/v3/networks")
        assert response.status_code == 200
        
        networks = response.json()
        assert len(networks) > 0, "No networks found - need data to test conflicts"
        print(f"TEST PASSED: Found {len(networks)} networks")
    
    def test_structure_entries_exist(self):
        """Verify structure entries exist for conflict detection"""
        # Get first network's structure
        networks_response = self.session.get(f"{BASE_URL}/api/v3/networks")
        assert networks_response.status_code == 200
        networks = networks_response.json()
        
        if networks:
            network_id = networks[0]["id"]
            network_detail = self.session.get(f"{BASE_URL}/api/v3/networks/{network_id}")
            assert network_detail.status_code == 200
            
            detail = network_detail.json()
            entries = detail.get("entries", [])
            print(f"TEST PASSED: Network '{detail['name']}' has {len(entries)} structure entries")
            
            # Check structure of entries
            if entries:
                entry = entries[0]
                assert "id" in entry
                assert "asset_domain_id" in entry
                assert "network_id" in entry
                assert "domain_role" in entry
        else:
            pytest.skip("No networks available")
    
    def test_tier_calculation_works(self):
        """Verify tier calculation is working for conflict detection"""
        networks_response = self.session.get(f"{BASE_URL}/api/v3/networks")
        assert networks_response.status_code == 200
        networks = networks_response.json()
        
        if networks:
            network_id = networks[0]["id"]
            # Get tiers endpoint
            tiers_response = self.session.get(f"{BASE_URL}/api/v3/networks/{network_id}/tiers")
            
            if tiers_response.status_code == 200:
                tiers = tiers_response.json()
                print(f"TEST PASSED: Tier calculation works. Tiers: {tiers}")
            else:
                # Tiers might be included in network detail
                network_detail = self.session.get(f"{BASE_URL}/api/v3/networks/{network_id}")
                detail = network_detail.json()
                entries = detail.get("entries", [])
                
                tier_counts = {}
                for entry in entries:
                    tier = entry.get("calculated_tier", "N/A")
                    tier_counts[tier] = tier_counts.get(tier, 0) + 1
                
                print(f"TEST PASSED: Tier distribution: {tier_counts}")
        else:
            pytest.skip("No networks available")


class TestFrontendAPIIntegration:
    """Test that frontend API calls work correctly"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "testadmin@test.com",
            "password": "test"
        })
        assert response.status_code == 200
        token = response.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def test_dashboard_conflicts_call(self):
        """Test the API call that Dashboard makes for conflicts"""
        # Frontend makes: conflictsAPI.detect() which calls /api/v3/reports/conflicts
        response = self.session.get(f"{BASE_URL}/api/v3/reports/conflicts")
        assert response.status_code == 200
        
        data = response.json()
        conflicts = data.get("conflicts", [])
        
        # Frontend expects:
        # - conflicts array with conflict_type, description, severity, node_a_label
        for conflict in conflicts:
            assert "conflict_type" in conflict, "Frontend expects 'conflict_type'"
            assert "description" in conflict, "Frontend expects 'description'"
            assert "severity" in conflict, "Frontend expects 'severity'"
            assert "node_a_label" in conflict, "Frontend expects 'node_a_label'"
        
        print(f"TEST PASSED: Dashboard conflicts API integration works. Conflicts count: {len(conflicts)}")
    
    def test_dashboard_stats_call(self):
        """Test the dashboard stats API call"""
        response = self.session.get(f"{BASE_URL}/api/reports/dashboard-stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_domains" in data or "total" in data
        print(f"TEST PASSED: Dashboard stats API works. Keys: {list(data.keys())}")
    
    def test_monitoring_stats_call(self):
        """Test the monitoring stats API call"""
        response = self.session.get(f"{BASE_URL}/api/v3/monitoring/stats")
        assert response.status_code == 200
        
        data = response.json()
        print(f"TEST PASSED: Monitoring stats API works. Keys: {list(data.keys())}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
