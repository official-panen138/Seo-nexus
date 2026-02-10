"""
P0 Domain Monitoring V3 Tests
==============================
Tests for the two independent monitoring engines:
1. Domain Expiration Monitoring (daily job)
2. Domain Availability Monitoring (interval-based)

Plus monitoring settings API endpoints.
"""

import pytest
import requests
import os

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://seo-alert-system.preview.emergentagent.com"
)


class TestAuth:
    """Authentication tests"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token for admin user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]

    @pytest.fixture
    def headers(self, auth_token):
        """Auth headers for requests"""
        return {"Authorization": f"Bearer {auth_token}"}

    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "admin@test.com"
        assert data["user"]["role"] == "super_admin"


class TestMonitoringSettings:
    """Tests for monitoring settings API"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
        )
        return response.json()["access_token"]

    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}

    def test_get_monitoring_settings(self, headers):
        """GET /api/v3/monitoring/settings returns expiration and availability settings"""
        response = requests.get(
            f"{BASE_URL}/api/v3/monitoring/settings", headers=headers
        )
        assert response.status_code == 200

        data = response.json()

        # Check expiration settings structure
        assert "expiration" in data
        assert "enabled" in data["expiration"]
        assert "alert_window_days" in data["expiration"]
        assert "alert_thresholds" in data["expiration"]
        assert "include_auto_renew" in data["expiration"]

        # Check availability settings structure
        assert "availability" in data
        assert "enabled" in data["availability"]
        assert "default_interval_seconds" in data["availability"]
        assert "alert_on_down" in data["availability"]
        assert "alert_on_recovery" in data["availability"]
        assert "timeout_seconds" in data["availability"]
        assert "follow_redirects" in data["availability"]

        # Check telegram settings
        assert "telegram" in data
        assert "enabled" in data["telegram"]

    def test_update_monitoring_settings(self, headers):
        """PUT /api/v3/monitoring/settings updates settings (Super Admin only)"""
        # Get current settings first
        get_response = requests.get(
            f"{BASE_URL}/api/v3/monitoring/settings", headers=headers
        )
        original_window = get_response.json()["expiration"]["alert_window_days"]

        # Update to new value
        new_window = 30 if original_window != 30 else 14
        response = requests.put(
            f"{BASE_URL}/api/v3/monitoring/settings",
            headers={**headers, "Content-Type": "application/json"},
            json={"expiration": {"alert_window_days": new_window}},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] == True
        assert data["settings"]["expiration"]["alert_window_days"] == new_window

        # Verify the setting persisted
        verify_response = requests.get(
            f"{BASE_URL}/api/v3/monitoring/settings", headers=headers
        )
        assert verify_response.json()["expiration"]["alert_window_days"] == new_window

        # Restore original value
        requests.put(
            f"{BASE_URL}/api/v3/monitoring/settings",
            headers={**headers, "Content-Type": "application/json"},
            json={"expiration": {"alert_window_days": original_window}},
        )


class TestMonitoringStats:
    """Tests for monitoring stats API"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
        )
        return response.json()["access_token"]

    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}

    def test_get_monitoring_stats(self, headers):
        """GET /api/v3/monitoring/stats returns availability, expiration, alerts counts"""
        response = requests.get(f"{BASE_URL}/api/v3/monitoring/stats", headers=headers)
        assert response.status_code == 200

        data = response.json()

        # Check availability stats
        assert "availability" in data
        assert "total_monitored" in data["availability"]
        assert "up" in data["availability"]
        assert "down" in data["availability"]
        assert "unknown" in data["availability"]

        # Check expiration stats
        assert "expiration" in data
        assert "expiring_7_days" in data["expiration"]
        assert "expiring_30_days" in data["expiration"]
        assert "expired" in data["expiration"]

        # Check alerts stats
        assert "alerts" in data
        assert "monitoring_unacknowledged" in data["alerts"]
        assert "expiration_unacknowledged" in data["alerts"]


class TestExpirationMonitoring:
    """Tests for expiration monitoring endpoints"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
        )
        return response.json()["access_token"]

    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}

    def test_trigger_expiration_check(self, headers):
        """POST /api/v3/monitoring/check-expiration triggers expiration check"""
        response = requests.post(
            f"{BASE_URL}/api/v3/monitoring/check-expiration", headers=headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "running"
        assert "message" in data

    def test_get_expiring_domains(self, headers):
        """GET /api/v3/monitoring/expiring-domains returns domains expiring within N days"""
        response = requests.get(
            f"{BASE_URL}/api/v3/monitoring/expiring-domains?days=30", headers=headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "domains" in data
        assert "total" in data
        assert "query_days" in data
        assert data["query_days"] == 30

        # If there are expiring domains, verify structure
        if data["domains"]:
            domain = data["domains"][0]
            assert "id" in domain
            assert "domain_name" in domain
            assert "expiration_date" in domain
            assert "days_remaining" in domain
            assert "auto_renew" in domain
            assert "status" in domain


class TestAvailabilityMonitoring:
    """Tests for availability monitoring endpoints"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
        )
        return response.json()["access_token"]

    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}

    def test_trigger_availability_check(self, headers):
        """POST /api/v3/monitoring/check-availability triggers availability check"""
        response = requests.post(
            f"{BASE_URL}/api/v3/monitoring/check-availability", headers=headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "running"
        assert "message" in data

    def test_get_down_domains(self, headers):
        """GET /api/v3/monitoring/down-domains returns currently down domains"""
        response = requests.get(
            f"{BASE_URL}/api/v3/monitoring/down-domains", headers=headers
        )
        assert response.status_code == 200

        data = response.json()
        assert "domains" in data
        assert "total" in data

        # If there are down domains, verify structure
        if data["domains"]:
            domain = data["domains"][0]
            assert "id" in domain
            assert "domain_name" in domain
            assert "brand_name" in domain
            # Optional fields - may be null
            assert "last_http_code" in domain
            assert "last_checked_at" in domain


class TestMonitoringRoleRestrictions:
    """Tests for role-based access control on monitoring endpoints"""

    @pytest.fixture(scope="class")
    def super_admin_headers(self):
        """Get headers for super_admin user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
        )
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def test_super_admin_can_update_settings(self, super_admin_headers):
        """Super admin can update monitoring settings"""
        response = requests.put(
            f"{BASE_URL}/api/v3/monitoring/settings",
            headers={**super_admin_headers, "Content-Type": "application/json"},
            json={"expiration": {"enabled": True}},
        )
        assert response.status_code == 200

    def test_get_settings_without_auth_fails(self):
        """Accessing settings without auth should fail"""
        response = requests.get(f"{BASE_URL}/api/v3/monitoring/settings")
        assert response.status_code in [401, 403]


class TestMonitoringFieldsInAssetDomain:
    """Tests for monitoring-related fields in AssetDomainBase model"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
        )
        return response.json()["access_token"]

    @pytest.fixture
    def headers(self, auth_token):
        return {"Authorization": f"Bearer {auth_token}"}

    def test_asset_domain_has_new_monitoring_fields(self, headers):
        """Asset domain response should include new monitoring fields"""
        # Get asset domains
        response = requests.get(f"{BASE_URL}/api/v3/asset-domains", headers=headers)
        assert response.status_code == 200

        domains = response.json()
        if domains:
            # The response model should have these fields available
            domain = domains[0]
            # These fields are in the model, check if they exist
            # They might be None but should be present in schema
            assert (
                "monitoring_enabled" in domain
                or domain.get("monitoring_enabled") is not None
                or domain.get("monitoring_enabled") is False
            )
            assert (
                "monitoring_interval" in domain
                or domain.get("monitoring_interval") is not None
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
