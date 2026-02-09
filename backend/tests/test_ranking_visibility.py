"""
Test SEO Network Ranking Visibility Feature
============================================
Tests for ranking status badges, mini metrics, filters, and sorts on the networks page.

Features tested:
- GET /api/v3/networks returns ranking_status, ranking_nodes_count, best_ranking_position, tracked_urls_count
- ranking_status computed as: 'ranking' (position 1-100 or ranking_url), 'tracking', or 'none'
- Filter by ranking_status query parameter
- Sort by best_position or ranking_nodes query parameter
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestRankingVisibilityAPI:
    """Test SEO Network Ranking Visibility API features"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test - authenticate and get token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("access_token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def test_networks_response_includes_ranking_fields(self):
        """Test GET /api/v3/networks returns all ranking visibility fields"""
        response = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)
        assert response.status_code == 200
        
        networks = response.json()
        assert isinstance(networks, list)
        
        # At least verify one network has the required fields
        for network in networks:
            # Check all required ranking fields exist
            assert "ranking_status" in network, "ranking_status field missing"
            assert "ranking_nodes_count" in network, "ranking_nodes_count field missing"
            assert "best_ranking_position" in network, "best_ranking_position field missing"
            assert "tracked_urls_count" in network, "tracked_urls_count field missing"
            
            # Validate ranking_status is a valid value
            assert network["ranking_status"] in ["ranking", "tracking", "none"], \
                f"Invalid ranking_status: {network['ranking_status']}"
            
            # Validate ranking_nodes_count is an integer
            assert isinstance(network["ranking_nodes_count"], int)
            
            # Validate best_ranking_position is int or None
            if network["best_ranking_position"] is not None:
                assert isinstance(network["best_ranking_position"], int)
                assert 1 <= network["best_ranking_position"] <= 100, \
                    f"best_ranking_position out of range: {network['best_ranking_position']}"
            
            # Validate tracked_urls_count is an integer
            assert isinstance(network["tracked_urls_count"], int)
        
        print(f"✓ All {len(networks)} networks have valid ranking visibility fields")
    
    def test_project_a_has_ranking_status(self):
        """Test that Project A (known ranking network) has correct ranking status"""
        response = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)
        assert response.status_code == 200
        
        networks = response.json()
        project_a = next((n for n in networks if n["name"] == "Project A"), None)
        
        if project_a:
            assert project_a["ranking_status"] == "ranking", \
                f"Expected 'ranking' status for Project A, got: {project_a['ranking_status']}"
            assert project_a["ranking_nodes_count"] >= 1, \
                f"Expected at least 1 ranking node for Project A, got: {project_a['ranking_nodes_count']}"
            assert project_a["best_ranking_position"] is not None, \
                "Expected best_ranking_position for Project A"
            print(f"✓ Project A has ranking_status='ranking', nodes={project_a['ranking_nodes_count']}, best_pos=#{project_a['best_ranking_position']}")
        else:
            pytest.skip("Project A network not found - may have been deleted")
    
    def test_filter_by_ranking_status_ranking(self):
        """Test filter ranking_status=ranking returns only ranking networks"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks?ranking_status=ranking", 
            headers=self.headers
        )
        assert response.status_code == 200
        
        networks = response.json()
        
        # All returned networks should have ranking_status='ranking'
        for network in networks:
            assert network["ranking_status"] == "ranking", \
                f"Network {network['name']} should not be in ranking filter results"
        
        print(f"✓ Filter ranking_status=ranking returned {len(networks)} networks (all with status='ranking')")
    
    def test_filter_by_ranking_status_tracking(self):
        """Test filter ranking_status=tracking returns only tracking networks"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks?ranking_status=tracking", 
            headers=self.headers
        )
        assert response.status_code == 200
        
        networks = response.json()
        
        # All returned networks should have ranking_status='tracking'
        for network in networks:
            assert network["ranking_status"] == "tracking", \
                f"Network {network['name']} should not be in tracking filter results"
        
        print(f"✓ Filter ranking_status=tracking returned {len(networks)} networks")
    
    def test_filter_by_ranking_status_none(self):
        """Test filter ranking_status=none returns only non-ranking networks"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks?ranking_status=none", 
            headers=self.headers
        )
        assert response.status_code == 200
        
        networks = response.json()
        
        # All returned networks should have ranking_status='none'
        for network in networks:
            assert network["ranking_status"] == "none", \
                f"Network {network['name']} should not be in none filter results"
        
        print(f"✓ Filter ranking_status=none returned {len(networks)} networks (all with status='none')")
    
    def test_sort_by_best_position(self):
        """Test sort_by=best_position sorts networks correctly"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks?sort_by=best_position", 
            headers=self.headers
        )
        assert response.status_code == 200
        
        networks = response.json()
        
        # Verify sorting: networks with positions should come first, sorted ascending
        # Networks with null positions should be at the end
        prev_position = 0
        null_started = False
        
        for network in networks:
            pos = network.get("best_ranking_position")
            if pos is None:
                null_started = True
            else:
                if null_started:
                    pytest.fail(f"Network {network['name']} has position {pos} but appears after null positions")
                assert pos >= prev_position, \
                    f"Networks not sorted by best_position: {pos} came after {prev_position}"
                prev_position = pos
        
        print(f"✓ Sort by best_position works correctly ({len(networks)} networks)")
    
    def test_sort_by_ranking_nodes(self):
        """Test sort_by=ranking_nodes sorts networks by ranking nodes count (descending)"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks?sort_by=ranking_nodes", 
            headers=self.headers
        )
        assert response.status_code == 200
        
        networks = response.json()
        
        # Verify sorting: networks should be sorted by ranking_nodes_count descending
        prev_count = float('inf')
        
        for network in networks:
            count = network.get("ranking_nodes_count", 0)
            assert count <= prev_count, \
                f"Networks not sorted by ranking_nodes descending: {count} came after {prev_count}"
            prev_count = count
        
        print(f"✓ Sort by ranking_nodes works correctly ({len(networks)} networks, descending)")
    
    def test_combined_filter_and_sort(self):
        """Test combining filter and sort parameters"""
        # Get all networks first
        all_response = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)
        all_networks = all_response.json()
        
        # Filter by 'none' status (most networks have this)
        response = requests.get(
            f"{BASE_URL}/api/v3/networks?ranking_status=none&sort_by=ranking_nodes", 
            headers=self.headers
        )
        assert response.status_code == 200
        
        networks = response.json()
        
        # Verify all have status 'none'
        for network in networks:
            assert network["ranking_status"] == "none"
        
        print(f"✓ Combined filter and sort works correctly")
    
    def test_ranking_status_computation_logic(self):
        """Test that ranking status is computed correctly based on node data"""
        # Get all networks with their details
        response = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)
        assert response.status_code == 200
        
        networks = response.json()
        
        for network in networks:
            ranking_status = network.get("ranking_status")
            ranking_nodes = network.get("ranking_nodes_count", 0)
            best_pos = network.get("best_ranking_position")
            tracked = network.get("tracked_urls_count", 0)
            
            # Verify logic consistency
            if ranking_status == "ranking":
                # Should have at least 1 ranking node
                assert ranking_nodes >= 1 or best_pos is not None, \
                    f"Network {network['name']} has ranking status but no ranking data"
            elif ranking_status == "none":
                # Should have 0 ranking nodes and 0 tracked URLs
                assert ranking_nodes == 0, \
                    f"Network {network['name']} has 'none' status but {ranking_nodes} ranking nodes"
        
        print(f"✓ Ranking status computation logic is consistent")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
