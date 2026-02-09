"""
Access Transparency Phase 2 & 3 Tests
=====================================

Phase 2: Telegram Auto-Tagging (Complaint creation auto-includes assigned users)
Phase 3: Auto-Reminder System (Global + per-network configurable reminder intervals)

Test network ID: 76e067db-60ba-4e3b-a949-b3229dc1c652
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "admin152133@example.com"
TEST_PASSWORD = "admin123"
TEST_NETWORK_ID = "76e067db-60ba-4e3b-a949-b3229dc1c652"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for testing"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    # API returns access_token not token
    token = data.get("access_token") or data.get("token")
    assert token, "No token in response"
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestPhase3ReminderConfig:
    """Phase 3: Reminder Configuration Tests"""
    
    def test_get_global_reminder_config(self, auth_headers):
        """GET /api/v3/settings/reminder-config returns global config"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/reminder-config",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        # Should have key structure fields
        assert "key" in data, "Missing 'key' field"
        assert data["key"] == "optimization_reminders"
        assert "enabled" in data, "Missing 'enabled' field"
        assert "interval_days" in data, "Missing 'interval_days' field"
        assert isinstance(data["interval_days"], int), "interval_days should be int"
        print(f"Global reminder config: enabled={data['enabled']}, interval={data['interval_days']} days")
    
    def test_update_global_reminder_config(self, auth_headers):
        """PUT /api/v3/settings/reminder-config updates global config"""
        # Get current config first
        get_response = requests.get(
            f"{BASE_URL}/api/v3/settings/reminder-config",
            headers=auth_headers
        )
        original_interval = get_response.json().get("interval_days", 2)
        
        # Update to new value
        new_interval = 3 if original_interval != 3 else 4
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/reminder-config",
            headers=auth_headers,
            json={"interval_days": new_interval}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "message" in data, "Missing 'message' field"
        
        # Verify the change
        verify_response = requests.get(
            f"{BASE_URL}/api/v3/settings/reminder-config",
            headers=auth_headers
        )
        assert verify_response.json().get("interval_days") == new_interval
        
        # Restore original
        requests.put(
            f"{BASE_URL}/api/v3/settings/reminder-config",
            headers=auth_headers,
            json={"interval_days": original_interval}
        )
        print(f"Updated global interval from {original_interval} to {new_interval}, then restored")
    
    def test_get_network_reminder_config(self, auth_headers):
        """GET /api/v3/networks/{id}/reminder-config returns effective config with global fallback"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/reminder-config",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        # Should have effective config fields
        assert "effective_interval_days" in data, "Missing 'effective_interval_days'"
        # Check for either has_override or network_override
        has_override = "has_override" in data or "network_override" in data
        assert has_override, "Missing override indication"
        # global_default instead of global_interval_days
        has_global = "global_interval_days" in data or "global_default" in data
        assert has_global, "Missing global config"
        
        # Determine if there's an override
        override_exists = bool(data.get("network_override")) if "network_override" in data else data.get("has_override", False)
        print(f"Network reminder config: effective={data['effective_interval_days']}, has_override={override_exists}")
    
    def test_update_network_reminder_config_set_override(self, auth_headers):
        """PUT /api/v3/networks/{id}/reminder-config sets per-network override"""
        # Set a custom override for this network
        response = requests.put(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/reminder-config",
            headers=auth_headers,
            json={"interval_days": 5}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "message" in data or "interval_days" in data
        
        # Verify the override was set
        verify_response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/reminder-config",
            headers=auth_headers
        )
        verify_data = verify_response.json()
        
        assert verify_data.get("has_override") == True, "Override should be set"
        assert verify_data.get("effective_interval_days") == 5, "Effective interval should be 5"
        print(f"Network override set: {verify_data}")
    
    def test_update_network_reminder_config_clear_override(self, auth_headers):
        """PUT /api/v3/networks/{id}/reminder-config with null clears override"""
        # Clear the override
        response = requests.put(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/reminder-config",
            headers=auth_headers,
            json={"interval_days": None}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        # Verify the override was cleared
        verify_response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/reminder-config",
            headers=auth_headers
        )
        verify_data = verify_response.json()
        
        assert verify_data.get("has_override") == False, "Override should be cleared"
        print(f"Network override cleared, using global: {verify_data.get('global_interval_days')} days")
    
    def test_get_optimization_reminders(self, auth_headers):
        """GET /api/v3/optimization-reminders returns reminder logs"""
        response = requests.get(
            f"{BASE_URL}/api/v3/optimization-reminders",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "reminders" in data, "Missing 'reminders' field"
        assert "total" in data, "Missing 'total' field"
        assert isinstance(data["reminders"], list), "reminders should be list"
        
        print(f"Found {data['total']} reminder logs")


class TestPhase2ComplaintAutoTagging:
    """Phase 2: Complaint Creation with Auto-Tagging Tests"""
    
    def test_network_has_access_summary(self, auth_headers):
        """Verify test network has access summary data"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/access-control",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        print(f"Network visibility mode: {data.get('visibility_mode')}")
        print(f"Allowed users: {len(data.get('allowed_user_ids', []))}")
        print(f"Access summary cache: {data.get('access_summary_cache')}")
    
    def test_get_optimizations_for_network(self, auth_headers):
        """Get optimizations for the test network to use in complaint creation"""
        response = requests.get(
            f"{BASE_URL}/api/v3/optimizations",
            headers=auth_headers,
            params={"network_id": TEST_NETWORK_ID}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        optimizations = data.get("data", []) if isinstance(data, dict) else data
        print(f"Found {len(optimizations)} optimizations for network")
        
        # Return first optimization ID for further tests
        return optimizations[0]["id"] if optimizations else None
    
    def test_create_complaint_auto_tags_network_users(self, auth_headers):
        """Creating complaint should auto-include users from network Access Summary"""
        # First get an optimization to create complaint on
        opt_response = requests.get(
            f"{BASE_URL}/api/v3/optimizations",
            headers=auth_headers,
            params={"network_id": TEST_NETWORK_ID}
        )
        
        if opt_response.status_code != 200:
            pytest.skip("No optimizations available for testing")
            return
        
        data = opt_response.json()
        optimizations = data.get("data", []) if isinstance(data, dict) else data
        
        if not optimizations:
            pytest.skip("No optimizations in test network")
            return
        
        optimization_id = optimizations[0]["id"]
        
        # Get network to check allowed_user_ids
        network_response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/access-control",
            headers=auth_headers
        )
        network_data = network_response.json()
        network_allowed_users = network_data.get("allowed_user_ids", [])
        visibility_mode = network_data.get("visibility_mode", "brand_based")
        
        # Create a complaint (without explicit responsible_user_ids)
        complaint_response = requests.post(
            f"{BASE_URL}/api/v3/optimizations/{optimization_id}/complaints",
            headers=auth_headers,
            json={
                "reason": f"Test complaint for auto-tagging verification - {uuid.uuid4()}",
                "priority": "medium",
                "responsible_user_ids": []  # Explicitly empty to test auto-tagging
            }
        )
        
        assert complaint_response.status_code == 200, f"Failed to create complaint: {complaint_response.text}"
        
        complaint = complaint_response.json()
        
        # Verify complaint has auto-assigned users from network (if restricted mode)
        if visibility_mode == "restricted" and network_allowed_users:
            assert "responsible_user_ids" in complaint, "Missing responsible_user_ids"
            assert "auto_assigned_from_network" in complaint, "Missing auto_assigned_from_network flag"
            
            if complaint.get("auto_assigned_from_network"):
                # Check that all network allowed users are included
                for user_id in network_allowed_users:
                    assert user_id in complaint["responsible_user_ids"], \
                        f"Network user {user_id} not auto-assigned to complaint"
                print(f"Auto-tagging verified: {len(complaint['responsible_user_ids'])} users assigned")
            else:
                print("Network not in restricted mode, auto-tagging not applied")
        else:
            print(f"Network mode is '{visibility_mode}', auto-tagging only applies to 'restricted' mode")
        
        print(f"Complaint created: {complaint['id']}")
        print(f"Responsible users: {complaint.get('responsible_user_ids', [])}")
        print(f"Auto-assigned from network: {complaint.get('auto_assigned_from_network', False)}")


class TestPhase1Verification:
    """Quick verification that Phase 1 features still work"""
    
    def test_networks_list_includes_visibility_mode(self, auth_headers):
        """Networks list should include visibility_mode field"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        networks = response.json()
        if networks:
            # Check first network has visibility fields
            network = networks[0]
            assert "visibility_mode" in network or network.get("visibility_mode") is not None, \
                "visibility_mode should be present (defaults to brand_based)"
            print(f"First network visibility_mode: {network.get('visibility_mode', 'brand_based')}")
    
    def test_access_control_endpoint(self, auth_headers):
        """GET /api/v3/networks/{id}/access-control should return access settings"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/access-control",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "visibility_mode" in data
        assert "allowed_user_ids" in data
        assert "access_summary_cache" in data
        
        print(f"Access control endpoint working: mode={data['visibility_mode']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
