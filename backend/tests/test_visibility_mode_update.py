"""
SEO Network Visibility Mode Update Tests
=========================================
Tests the visibility mode update:
- 'public' mode is removed (should be rejected by API)
- Only 'brand_based' and 'restricted' modes are valid
- Restricted mode description: 'Only managers and Super Admins can view this network'

Ref: Main agent updated to remove Public (Super Admin) visibility option
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://eval-metrics-2.preview.emergentagent.com')

# Test credentials from review request
SUPER_ADMIN_EMAIL = "superadmin@seonoc.com"
SUPER_ADMIN_PASSWORD = "SuperAdmin123!"

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def super_admin_token(api_client):
    """Get Super Admin authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data["access_token"]


@pytest.fixture(scope="module")
def authenticated_client(api_client, super_admin_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {super_admin_token}"})
    return api_client


@pytest.fixture(scope="module")
def test_network_id(authenticated_client):
    """Get a valid network ID for testing"""
    response = authenticated_client.get(f"{BASE_URL}/api/v3/networks")
    assert response.status_code == 200, f"Failed to get networks: {response.text}"
    networks = response.json()
    assert len(networks) > 0, "No networks found for testing"
    return networks[0]["id"]


class TestVisibilityModeValidation:
    """Tests for visibility mode enum validation"""
    
    def test_api_accepts_brand_based_mode(self, authenticated_client, test_network_id):
        """PUT /managers should accept 'brand_based' visibility mode"""
        response = authenticated_client.put(
            f"{BASE_URL}/api/v3/networks/{test_network_id}/managers",
            json={"visibility_mode": "brand_based", "manager_ids": []}
        )
        
        assert response.status_code == 200, f"brand_based mode should be accepted: {response.text}"
        
        # Verify the change was saved
        get_response = authenticated_client.get(f"{BASE_URL}/api/v3/networks/{test_network_id}/managers")
        assert get_response.status_code == 200
        assert get_response.json()["visibility_mode"] == "brand_based"
    
    def test_api_accepts_restricted_mode(self, authenticated_client, test_network_id):
        """PUT /managers should accept 'restricted' visibility mode"""
        response = authenticated_client.put(
            f"{BASE_URL}/api/v3/networks/{test_network_id}/managers",
            json={"visibility_mode": "restricted", "manager_ids": []}
        )
        
        assert response.status_code == 200, f"restricted mode should be accepted: {response.text}"
        
        # Verify the change was saved
        get_response = authenticated_client.get(f"{BASE_URL}/api/v3/networks/{test_network_id}/managers")
        assert get_response.status_code == 200
        assert get_response.json()["visibility_mode"] == "restricted"
    
    def test_api_rejects_public_mode(self, authenticated_client, test_network_id):
        """PUT /managers should REJECT 'public' visibility mode (removed feature)"""
        response = authenticated_client.put(
            f"{BASE_URL}/api/v3/networks/{test_network_id}/managers",
            json={"visibility_mode": "public", "manager_ids": []}
        )
        
        # The API should reject 'public' mode since it's no longer in the enum
        # Pydantic validation should return 422 Unprocessable Entity
        assert response.status_code == 422, f"public mode should be rejected with 422, got {response.status_code}: {response.text}"
        
        # Verify error message mentions the invalid value
        error_data = response.json()
        assert "detail" in error_data, "Response should contain error detail"
        
    def test_api_rejects_invalid_mode(self, authenticated_client, test_network_id):
        """PUT /managers should reject invalid visibility modes"""
        response = authenticated_client.put(
            f"{BASE_URL}/api/v3/networks/{test_network_id}/managers",
            json={"visibility_mode": "invalid_mode_xyz", "manager_ids": []}
        )
        
        # Should return 422 Unprocessable Entity for invalid enum value
        assert response.status_code == 422, f"Invalid mode should be rejected with 422, got {response.status_code}"


class TestGetManagersVisibilityModes:
    """Test GET endpoint returns only valid visibility modes"""
    
    def test_get_managers_returns_valid_mode(self, authenticated_client, test_network_id):
        """GET /managers should return a valid visibility_mode (brand_based or restricted)"""
        response = authenticated_client.get(f"{BASE_URL}/api/v3/networks/{test_network_id}/managers")
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify visibility_mode is one of the valid options (NOT 'public')
        assert "visibility_mode" in data, "Missing visibility_mode field"
        valid_modes = ["brand_based", "restricted"]
        assert data["visibility_mode"] in valid_modes, \
            f"visibility_mode '{data['visibility_mode']}' is not in valid modes {valid_modes}"


class TestManagerSearch:
    """Test manager user search functionality"""
    
    def test_user_search_endpoint(self, authenticated_client, test_network_id):
        """GET /users/search should return users for manager selection"""
        response = authenticated_client.get(
            f"{BASE_URL}/api/v3/users/search",
            params={"q": "admin", "network_id": test_network_id}
        )
        
        assert response.status_code == 200, f"User search failed: {response.text}"
        data = response.json()
        
        assert "results" in data, "Missing results field in search response"
        assert isinstance(data["results"], list), "results should be a list"
        
        # If results exist, verify structure
        if len(data["results"]) > 0:
            user = data["results"][0]
            assert "id" in user, "User should have id"
            assert "email" in user, "User should have email"
    
    def test_user_search_minimum_query_length(self, authenticated_client, test_network_id):
        """User search should reject queries less than 2 characters"""
        response = authenticated_client.get(
            f"{BASE_URL}/api/v3/users/search",
            params={"q": "a", "network_id": test_network_id}
        )
        
        # Should return 422 for query length less than 2 characters
        assert response.status_code == 422, f"Short query should be rejected with 422, got {response.status_code}"


class TestAddRemoveManagers:
    """Test adding and removing managers"""
    
    def test_add_manager_to_network(self, authenticated_client, test_network_id):
        """PUT /managers should add a manager successfully"""
        # First, search for a user to add
        search_response = authenticated_client.get(
            f"{BASE_URL}/api/v3/users/search",
            params={"q": "admin", "network_id": test_network_id}
        )
        
        assert search_response.status_code == 200
        users = search_response.json().get("results", [])
        
        if len(users) > 0:
            user_id = users[0]["id"]
            
            # Add the user as manager
            response = authenticated_client.put(
                f"{BASE_URL}/api/v3/networks/{test_network_id}/managers",
                json={"visibility_mode": "brand_based", "manager_ids": [user_id]}
            )
            
            assert response.status_code == 200, f"Add manager failed: {response.text}"
            
            # Verify manager was added
            get_response = authenticated_client.get(f"{BASE_URL}/api/v3/networks/{test_network_id}/managers")
            assert user_id in get_response.json()["manager_ids"], "Manager should be in list"
        else:
            pytest.skip("No users found to test manager addition")
    
    def test_remove_all_managers(self, authenticated_client, test_network_id):
        """PUT /managers with empty list should remove all managers"""
        response = authenticated_client.put(
            f"{BASE_URL}/api/v3/networks/{test_network_id}/managers",
            json={"visibility_mode": "brand_based", "manager_ids": []}
        )
        
        assert response.status_code == 200, f"Remove managers failed: {response.text}"
        
        # Verify managers were removed
        get_response = authenticated_client.get(f"{BASE_URL}/api/v3/networks/{test_network_id}/managers")
        assert get_response.json()["manager_ids"] == [], "Manager list should be empty"


class TestManagerSummaryCache:
    """Test manager_summary_cache on network cards"""
    
    def test_network_list_includes_visibility_mode(self, authenticated_client):
        """GET /networks should include visibility_mode for badge display"""
        response = authenticated_client.get(f"{BASE_URL}/api/v3/networks")
        
        assert response.status_code == 200
        networks = response.json()
        
        if len(networks) > 0:
            network = networks[0]
            # visibility_mode should be present for badge rendering
            # If not present, default is brand_based
            if "visibility_mode" in network:
                valid_modes = ["brand_based", "restricted"]
                assert network["visibility_mode"] in valid_modes, \
                    f"Network visibility_mode '{network['visibility_mode']}' should be brand_based or restricted"
    
    def test_network_has_manager_summary_cache(self, authenticated_client):
        """Networks should have manager_summary_cache for UI display"""
        response = authenticated_client.get(f"{BASE_URL}/api/v3/networks")
        
        assert response.status_code == 200
        networks = response.json()
        
        if len(networks) > 0:
            network = networks[0]
            # manager_summary_cache may not be present on all networks
            if "manager_summary_cache" in network and network["manager_summary_cache"]:
                cache = network["manager_summary_cache"]
                assert "count" in cache, "manager_summary_cache should have count"
                assert "names" in cache, "manager_summary_cache should have names"


# Cleanup: Reset to brand_based mode after tests
@pytest.fixture(scope="module", autouse=True)
def cleanup_after_tests(authenticated_client, test_network_id):
    """Reset network to brand_based mode after all tests"""
    yield
    
    try:
        authenticated_client.put(
            f"{BASE_URL}/api/v3/networks/{test_network_id}/managers",
            json={"visibility_mode": "brand_based", "manager_ids": []}
        )
    except:
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
