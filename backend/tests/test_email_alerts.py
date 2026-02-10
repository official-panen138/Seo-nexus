"""
Test suite for Email Alerts API endpoints
=========================================

Tests the email alert settings functionality for domain monitoring.
These endpoints allow configuring Resend email notifications for HIGH/CRITICAL alerts.

Features tested:
1. GET /api/v3/settings/email-alerts - Get email alert settings
2. PUT /api/v3/settings/email-alerts - Update email alert settings
3. POST /api/v3/settings/email-alerts/test - Send test email
"""

import pytest
import requests
import os

# Get BASE_URL from environment
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://msg-engine.preview.emergentagent.com"


class TestEmailAlertsAPI:
    """Email Alerts API endpoints tests"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for super_admin"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        # API returns access_token, not token
        token = data.get("access_token") or data.get("token")
        assert token, f"No token in response: {data}"
        return token

    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Headers with authorization"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }

    # ==================== GET SETTINGS ====================

    def test_get_email_alert_settings_returns_200(self, headers):
        """GET /api/v3/settings/email-alerts should return 200"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/email-alerts", headers=headers
        )
        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ GET /api/v3/settings/email-alerts returns 200")

    def test_get_email_alert_settings_structure(self, headers):
        """GET /api/v3/settings/email-alerts should return correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/email-alerts", headers=headers
        )
        assert response.status_code == 200
        data = response.json()

        # Verify required fields exist
        assert "enabled" in data, "Missing 'enabled' field"
        assert "configured" in data, "Missing 'configured' field"
        assert "global_admin_emails" in data, "Missing 'global_admin_emails' field"
        assert "severity_threshold" in data, "Missing 'severity_threshold' field"
        assert (
            "include_network_managers" in data
        ), "Missing 'include_network_managers' field"

        # Verify types
        assert isinstance(data["enabled"], bool), "enabled should be boolean"
        assert isinstance(data["configured"], bool), "configured should be boolean"
        assert isinstance(
            data["global_admin_emails"], list
        ), "global_admin_emails should be list"
        assert isinstance(
            data["include_network_managers"], bool
        ), "include_network_managers should be boolean"

        print(f"✓ Response structure is correct: {data}")

    def test_get_email_alert_settings_unauthorized(self):
        """GET /api/v3/settings/email-alerts without auth should return 401 or 403"""
        response = requests.get(f"{BASE_URL}/api/v3/settings/email-alerts")
        assert response.status_code in [
            401,
            403,
        ], f"Expected 401/403, got {response.status_code}"
        print(f"✓ Unauthorized access correctly rejected with {response.status_code}")

    # ==================== UPDATE SETTINGS ====================

    def test_update_email_alert_settings_enabled(self, headers):
        """PUT /api/v3/settings/email-alerts should update enabled status"""
        # First get current settings
        get_response = requests.get(
            f"{BASE_URL}/api/v3/settings/email-alerts", headers=headers
        )
        current_enabled = get_response.json().get("enabled", False)

        # Update to opposite value
        new_enabled = not current_enabled
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/email-alerts",
            headers=headers,
            json={"enabled": new_enabled},
        )
        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert (
            data["enabled"] == new_enabled
        ), f"Expected enabled={new_enabled}, got {data['enabled']}"
        print(f"✓ Updated enabled to {new_enabled}")

        # Restore original value
        requests.put(
            f"{BASE_URL}/api/v3/settings/email-alerts",
            headers=headers,
            json={"enabled": current_enabled},
        )

    def test_update_email_alert_settings_severity_threshold(self, headers):
        """PUT /api/v3/settings/email-alerts should update severity threshold"""
        # Test setting to 'critical'
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/email-alerts",
            headers=headers,
            json={"severity_threshold": "critical"},
        )
        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert (
            data["severity_threshold"] == "critical"
        ), f"Expected 'critical', got {data['severity_threshold']}"
        print(f"✓ Updated severity_threshold to 'critical'")

        # Test setting back to 'high'
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/email-alerts",
            headers=headers,
            json={"severity_threshold": "high"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["severity_threshold"] == "high"
        print(f"✓ Updated severity_threshold back to 'high'")

    def test_update_email_alert_settings_invalid_threshold(self, headers):
        """PUT /api/v3/settings/email-alerts with invalid threshold should return 400"""
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/email-alerts",
            headers=headers,
            json={"severity_threshold": "invalid_value"},
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"✓ Invalid severity_threshold correctly rejected with 400")

    def test_update_email_alert_settings_include_managers(self, headers):
        """PUT /api/v3/settings/email-alerts should update include_network_managers"""
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/email-alerts",
            headers=headers,
            json={"include_network_managers": True},
        )
        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["include_network_managers"] == True
        print(f"✓ Updated include_network_managers to True")

    def test_update_email_alert_settings_admin_emails(self, headers):
        """PUT /api/v3/settings/email-alerts should update global admin emails"""
        test_emails = ["test_admin1@example.com", "test_admin2@example.com"]

        response = requests.put(
            f"{BASE_URL}/api/v3/settings/email-alerts",
            headers=headers,
            json={"global_admin_emails": test_emails},
        )
        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert set(data["global_admin_emails"]) == set(
            test_emails
        ), f"Expected {test_emails}, got {data['global_admin_emails']}"
        print(f"✓ Updated global_admin_emails to {test_emails}")

        # Clean up - remove test emails
        requests.put(
            f"{BASE_URL}/api/v3/settings/email-alerts",
            headers=headers,
            json={"global_admin_emails": []},
        )

    def test_update_email_alert_settings_invalid_email(self, headers):
        """PUT /api/v3/settings/email-alerts with invalid email should return 400"""
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/email-alerts",
            headers=headers,
            json={"global_admin_emails": ["invalid_email_no_at_sign"]},
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"✓ Invalid email format correctly rejected with 400")

    def test_update_email_alert_settings_sender_email(self, headers):
        """PUT /api/v3/settings/email-alerts should update sender email"""
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/email-alerts",
            headers=headers,
            json={"sender_email": "alerts@test-domain.com"},
        )
        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("sender_email") == "alerts@test-domain.com"
        print(f"✓ Updated sender_email to 'alerts@test-domain.com'")

    # ==================== TEST EMAIL ENDPOINT ====================

    def test_email_alerts_test_endpoint_exists(self, headers):
        """POST /api/v3/settings/email-alerts/test endpoint should exist"""
        # Test with a valid email - it will fail because no API key configured
        # but the endpoint should return proper error message
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/email-alerts/test",
            headers=headers,
            params={"recipient_email": "test@example.com"},
        )

        # Expect 500/520 (API key not configured) or 200 (if configured)
        # Both indicate the endpoint exists and works
        assert response.status_code in [
            200,
            500,
            520,
        ], f"Expected 200, 500 or 520, got {response.status_code}: {response.text}"

        if response.status_code in [500, 520]:
            # Should have proper error message about missing configuration
            data = response.json()
            assert "detail" in data, "Error response should have 'detail'"
            print(
                f"✓ Test endpoint exists, returns proper error (no API key): {data.get('detail')}"
            )
        else:
            print(f"✓ Test email sent successfully")

    def test_email_alerts_test_invalid_email(self, headers):
        """POST /api/v3/settings/email-alerts/test with invalid email should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/email-alerts/test",
            headers=headers,
            params={"recipient_email": "invalid_email"},
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"✓ Invalid recipient email correctly rejected with 400")

    def test_email_alerts_test_missing_email(self, headers):
        """POST /api/v3/settings/email-alerts/test without email should return 422"""
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/email-alerts/test", headers=headers
        )
        # FastAPI returns 422 for missing required query params
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print(f"✓ Missing recipient_email correctly rejected with 422")

    def test_email_alerts_test_unauthorized(self):
        """POST /api/v3/settings/email-alerts/test without auth should return 401/403"""
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/email-alerts/test",
            params={"recipient_email": "test@example.com"},
        )
        assert response.status_code in [
            401,
            403,
        ], f"Expected 401/403, got {response.status_code}"
        print(f"✓ Unauthorized test email request correctly rejected")


class TestEmailAlertServiceIntegration:
    """Integration tests for email alert service (if Resend is configured)"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for super_admin"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
        )
        assert response.status_code == 200
        data = response.json()
        return data.get("access_token") or data.get("token")

    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Headers with authorization"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }

    def test_full_settings_update_flow(self, headers):
        """Test complete settings update flow"""
        # Get initial settings
        get_response = requests.get(
            f"{BASE_URL}/api/v3/settings/email-alerts", headers=headers
        )
        assert get_response.status_code == 200
        initial_settings = get_response.json()
        print(f"Initial settings: {initial_settings}")

        # Update multiple settings at once
        update_data = {
            "enabled": True,
            "severity_threshold": "high",
            "include_network_managers": True,
            "global_admin_emails": ["admin@test-company.com"],
        }

        update_response = requests.put(
            f"{BASE_URL}/api/v3/settings/email-alerts",
            headers=headers,
            json=update_data,
        )
        assert update_response.status_code == 200
        updated_settings = update_response.json()

        # Verify all updates applied
        assert updated_settings["enabled"] == True
        assert updated_settings["severity_threshold"] == "high"
        assert updated_settings["include_network_managers"] == True
        assert "admin@test-company.com" in updated_settings["global_admin_emails"]

        print(f"✓ Full settings update flow successful")
        print(f"Updated settings: {updated_settings}")

        # Clean up - restore initial state
        cleanup_data = {
            "enabled": initial_settings.get("enabled", False),
            "global_admin_emails": initial_settings.get("global_admin_emails", []),
        }
        requests.put(
            f"{BASE_URL}/api/v3/settings/email-alerts",
            headers=headers,
            json=cleanup_data,
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
