"""
Weekly Digest Email API Tests
=============================
Tests for the weekly digest email feature:
- GET /api/v3/settings/weekly-digest - Get digest settings
- PUT /api/v3/settings/weekly-digest - Update digest settings  
- GET /api/v3/settings/weekly-digest/preview - Preview digest data
- POST /api/v3/settings/weekly-digest/send - Send digest (will fail without API key)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable not set")
BASE_URL = BASE_URL.rstrip('/')

# Test credentials
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for super admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.text}")
    return response.json().get("token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for API requests"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestWeeklyDigestGetSettings:
    """Test GET /api/v3/settings/weekly-digest"""
    
    def test_get_digest_settings_success(self, auth_headers):
        """Should return digest settings with correct structure"""
        response = requests.get(f"{BASE_URL}/api/v3/settings/weekly-digest", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "enabled" in data
        assert "schedule_day" in data
        assert "schedule_hour" in data
        assert "include_expiring_domains" in data
        assert "include_down_domains" in data
        assert "include_soft_blocked" in data
        assert "expiring_days_threshold" in data
        
        # Verify data types
        assert isinstance(data["enabled"], bool)
        assert isinstance(data["schedule_day"], str)
        assert isinstance(data["schedule_hour"], int)
        assert isinstance(data["include_expiring_domains"], bool)
        assert isinstance(data["include_down_domains"], bool)
        assert isinstance(data["include_soft_blocked"], bool)
        assert isinstance(data["expiring_days_threshold"], int)
        
        print(f"✓ GET digest settings returned: enabled={data['enabled']}, schedule_day={data['schedule_day']}")
    
    def test_get_digest_settings_unauthorized(self):
        """Should return 401/403 without auth"""
        response = requests.get(f"{BASE_URL}/api/v3/settings/weekly-digest")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Unauthorized request properly rejected")


class TestWeeklyDigestUpdateSettings:
    """Test PUT /api/v3/settings/weekly-digest"""
    
    def test_update_enabled_status(self, auth_headers):
        """Should update enabled toggle"""
        # Get current state
        current = requests.get(f"{BASE_URL}/api/v3/settings/weekly-digest", headers=auth_headers).json()
        
        # Toggle enabled
        new_enabled = not current.get("enabled", False)
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/weekly-digest",
            headers=auth_headers,
            json={"enabled": new_enabled}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["enabled"] == new_enabled
        print(f"✓ Updated enabled to {new_enabled}")
        
        # Restore original state
        requests.put(
            f"{BASE_URL}/api/v3/settings/weekly-digest",
            headers=auth_headers,
            json={"enabled": current.get("enabled", False)}
        )
    
    def test_update_schedule_day(self, auth_headers):
        """Should update schedule_day"""
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/weekly-digest",
            headers=auth_headers,
            json={"schedule_day": "tuesday"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["schedule_day"] == "tuesday"
        print("✓ Updated schedule_day to tuesday")
        
        # Restore to monday
        requests.put(
            f"{BASE_URL}/api/v3/settings/weekly-digest",
            headers=auth_headers,
            json={"schedule_day": "monday"}
        )
    
    def test_update_schedule_hour(self, auth_headers):
        """Should update schedule_hour"""
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/weekly-digest",
            headers=auth_headers,
            json={"schedule_hour": 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["schedule_hour"] == 10
        print("✓ Updated schedule_hour to 10")
        
        # Restore to 9
        requests.put(
            f"{BASE_URL}/api/v3/settings/weekly-digest",
            headers=auth_headers,
            json={"schedule_hour": 9}
        )
    
    def test_update_expiring_threshold(self, auth_headers):
        """Should update expiring_days_threshold"""
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/weekly-digest",
            headers=auth_headers,
            json={"expiring_days_threshold": 14}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["expiring_days_threshold"] == 14
        print("✓ Updated expiring_days_threshold to 14")
        
        # Restore to 30
        requests.put(
            f"{BASE_URL}/api/v3/settings/weekly-digest",
            headers=auth_headers,
            json={"expiring_days_threshold": 30}
        )
    
    def test_update_include_toggles(self, auth_headers):
        """Should update include_* toggles"""
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/weekly-digest",
            headers=auth_headers,
            json={
                "include_expiring_domains": False,
                "include_down_domains": False,
                "include_soft_blocked": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["include_expiring_domains"] == False
        assert data["include_down_domains"] == False
        assert data["include_soft_blocked"] == False
        print("✓ Updated all include toggles to False")
        
        # Restore to True
        requests.put(
            f"{BASE_URL}/api/v3/settings/weekly-digest",
            headers=auth_headers,
            json={
                "include_expiring_domains": True,
                "include_down_domains": True,
                "include_soft_blocked": True
            }
        )
    
    def test_invalid_schedule_day(self, auth_headers):
        """Should reject invalid schedule_day"""
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/weekly-digest",
            headers=auth_headers,
            json={"schedule_day": "invalid_day"}
        )
        
        assert response.status_code == 400
        print("✓ Invalid schedule_day rejected with 400")
    
    def test_invalid_expiring_threshold_low(self, auth_headers):
        """Should reject expiring_days_threshold below 7"""
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/weekly-digest",
            headers=auth_headers,
            json={"expiring_days_threshold": 3}
        )
        
        assert response.status_code == 400
        print("✓ expiring_days_threshold < 7 rejected")
    
    def test_invalid_expiring_threshold_high(self, auth_headers):
        """Should reject expiring_days_threshold above 90"""
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/weekly-digest",
            headers=auth_headers,
            json={"expiring_days_threshold": 100}
        )
        
        assert response.status_code == 400
        print("✓ expiring_days_threshold > 90 rejected")
    
    def test_update_unauthorized(self):
        """Should reject update without auth"""
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/weekly-digest",
            json={"enabled": True}
        )
        assert response.status_code in [401, 403]
        print("✓ Unauthorized update rejected")


class TestWeeklyDigestPreview:
    """Test GET /api/v3/settings/weekly-digest/preview"""
    
    def test_preview_success(self, auth_headers):
        """Should return preview data with counts"""
        response = requests.get(f"{BASE_URL}/api/v3/settings/weekly-digest/preview", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "subject" in data
        assert "expiring_domains" in data or "down_domains_count" in data
        assert "total_issues" in data
        
        # Verify data types
        assert isinstance(data["subject"], str)
        assert isinstance(data["total_issues"], int)
        
        print(f"✓ Preview returned: subject='{data['subject'][:50]}...', total_issues={data['total_issues']}")
    
    def test_preview_expiring_domains_structure(self, auth_headers):
        """Should return expiring_domains with urgency groups"""
        response = requests.get(f"{BASE_URL}/api/v3/settings/weekly-digest/preview", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        if "expiring_domains" in data and data["expiring_domains"]:
            expiring = data["expiring_domains"]
            # Check for urgency groups
            assert "critical" in expiring or "high" in expiring or "medium" in expiring
            print(f"✓ expiring_domains has urgency groups: critical={len(expiring.get('critical', []))}, high={len(expiring.get('high', []))}, medium={len(expiring.get('medium', []))}")
        else:
            print("✓ No expiring domains in preview (OK - empty data)")
    
    def test_preview_unauthorized(self):
        """Should reject preview without auth"""
        response = requests.get(f"{BASE_URL}/api/v3/settings/weekly-digest/preview")
        assert response.status_code in [401, 403]
        print("✓ Unauthorized preview rejected")


class TestWeeklyDigestSend:
    """Test POST /api/v3/settings/weekly-digest/send"""
    
    def test_send_returns_error_without_api_key(self, auth_headers):
        """Should return error when Resend API key not configured"""
        response = requests.post(f"{BASE_URL}/api/v3/settings/weekly-digest/send", headers=auth_headers)
        
        # Expected to fail since Resend API key is not configured
        # Should return 500 with a meaningful error message
        # The endpoint should still exist and return a proper error
        assert response.status_code in [500, 400], f"Expected 500 or 400, got {response.status_code}: {response.text}"
        
        # Check error message mentions the issue
        error_data = response.json()
        assert "detail" in error_data or "error" in error_data
        print(f"✓ Send endpoint returns proper error without API key: {error_data.get('detail', error_data.get('error', 'N/A'))}")
    
    def test_send_unauthorized(self):
        """Should reject send without auth"""
        response = requests.post(f"{BASE_URL}/api/v3/settings/weekly-digest/send")
        assert response.status_code in [401, 403]
        print("✓ Unauthorized send rejected")


class TestWeeklyDigestFullFlow:
    """Test complete flow of digest settings"""
    
    def test_get_update_get_flow(self, auth_headers):
        """Test GET → UPDATE → GET flow preserves changes"""
        # Step 1: Get original settings
        get1 = requests.get(f"{BASE_URL}/api/v3/settings/weekly-digest", headers=auth_headers)
        assert get1.status_code == 200
        original = get1.json()
        print(f"✓ Step 1: Got original settings")
        
        # Step 2: Update multiple fields
        update_data = {
            "schedule_day": "wednesday",
            "schedule_hour": 14,
            "expiring_days_threshold": 60
        }
        update_resp = requests.put(
            f"{BASE_URL}/api/v3/settings/weekly-digest",
            headers=auth_headers,
            json=update_data
        )
        assert update_resp.status_code == 200
        print(f"✓ Step 2: Updated settings")
        
        # Step 3: Get updated settings
        get2 = requests.get(f"{BASE_URL}/api/v3/settings/weekly-digest", headers=auth_headers)
        assert get2.status_code == 200
        updated = get2.json()
        
        # Verify changes persisted
        assert updated["schedule_day"] == "wednesday"
        assert updated["schedule_hour"] == 14
        assert updated["expiring_days_threshold"] == 60
        print(f"✓ Step 3: Verified changes persisted")
        
        # Step 4: Restore original
        restore_data = {
            "schedule_day": original.get("schedule_day", "monday"),
            "schedule_hour": original.get("schedule_hour", 9),
            "expiring_days_threshold": original.get("expiring_days_threshold", 30)
        }
        requests.put(
            f"{BASE_URL}/api/v3/settings/weekly-digest",
            headers=auth_headers,
            json=restore_data
        )
        print(f"✓ Step 4: Restored original settings")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
