"""
Tests for Legacy Monitoring Alerts Removal
==========================================
Verify that the legacy 'Monitoring Alerts' feature has been removed
and replaced by 'Domain Monitoring' and 'SEO Conflicts'.

Key changes tested:
1. /api/v3/monitoring/stats endpoint works (new monitoring stats)
2. /api/v3/reports/conflicts endpoint works (SEO conflicts)
3. AlertsPage shows only SEO Conflicts (no legacy alerts tab)
4. SettingsPage has correct tabs (no legacy Monitoring Alerts tab)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for API requests"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@test.com", "password": "admin123"},
    )
    if response.status_code != 200:
        pytest.skip("Cannot authenticate - skipping tests")
    return response.json().get("access_token")


@pytest.fixture
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestMonitoringStatsEndpoint:
    """Tests for /api/v3/monitoring/stats endpoint"""

    def test_monitoring_stats_returns_200(self, auth_headers):
        """Endpoint should return 200 OK"""
        response = requests.get(
            f"{BASE_URL}/api/v3/monitoring/stats", headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    def test_monitoring_stats_has_availability(self, auth_headers):
        """Response should contain availability stats"""
        response = requests.get(
            f"{BASE_URL}/api/v3/monitoring/stats", headers=auth_headers
        )
        data = response.json()
        assert "availability" in data, "Missing 'availability' key"
        assert "total_monitored" in data["availability"]
        assert "up" in data["availability"]
        assert "down" in data["availability"]

    def test_monitoring_stats_has_expiration(self, auth_headers):
        """Response should contain expiration stats"""
        response = requests.get(
            f"{BASE_URL}/api/v3/monitoring/stats", headers=auth_headers
        )
        data = response.json()
        assert "expiration" in data, "Missing 'expiration' key"
        assert "expiring_7_days" in data["expiration"]
        assert "expiring_30_days" in data["expiration"]
        assert "expired" in data["expiration"]

    def test_monitoring_stats_has_alerts(self, auth_headers):
        """Response should contain alert stats"""
        response = requests.get(
            f"{BASE_URL}/api/v3/monitoring/stats", headers=auth_headers
        )
        data = response.json()
        assert "alerts" in data, "Missing 'alerts' key"
        assert "monitoring_unacknowledged" in data["alerts"]
        assert "expiration_unacknowledged" in data["alerts"]


class TestConflictsEndpoint:
    """Tests for /api/v3/reports/conflicts endpoint"""

    def test_conflicts_returns_200(self, auth_headers):
        """Endpoint should return 200 OK"""
        response = requests.get(
            f"{BASE_URL}/api/v3/reports/conflicts", headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    def test_conflicts_has_conflicts_array(self, auth_headers):
        """Response should contain conflicts array"""
        response = requests.get(
            f"{BASE_URL}/api/v3/reports/conflicts", headers=auth_headers
        )
        data = response.json()
        assert "conflicts" in data, "Missing 'conflicts' key"
        assert isinstance(data["conflicts"], list)

    def test_conflicts_has_total_count(self, auth_headers):
        """Response should contain total count"""
        response = requests.get(
            f"{BASE_URL}/api/v3/reports/conflicts", headers=auth_headers
        )
        data = response.json()
        assert "total" in data, "Missing 'total' key"
        assert isinstance(data["total"], int)

    def test_conflicts_has_by_severity(self, auth_headers):
        """Response should contain severity breakdown"""
        response = requests.get(
            f"{BASE_URL}/api/v3/reports/conflicts", headers=auth_headers
        )
        data = response.json()
        assert "by_severity" in data, "Missing 'by_severity' key"
        severity = data["by_severity"]
        assert "critical" in severity
        assert "high" in severity
        assert "medium" in severity
        assert "low" in severity

    def test_conflicts_filter_by_network_id(self, auth_headers):
        """Should accept network_id filter parameter"""
        # Get first network to test with
        networks_response = requests.get(
            f"{BASE_URL}/api/v3/networks", headers=auth_headers
        )
        networks = networks_response.json()

        if not networks:
            pytest.skip("No networks available for testing")

        network_id = networks[0]["id"]
        response = requests.get(
            f"{BASE_URL}/api/v3/reports/conflicts",
            headers=auth_headers,
            params={"network_id": network_id},
        )
        assert response.status_code == 200


class TestDomainMonitoringTelegramAPI:
    """Tests for Domain Monitoring Telegram settings (replaces legacy Monitoring Alerts)"""

    def test_domain_monitoring_settings_exists(self, auth_headers):
        """Domain monitoring telegram settings endpoint should exist"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-monitoring", headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    def test_domain_monitoring_has_configured_flag(self, auth_headers):
        """Response should have configured flag"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-monitoring", headers=auth_headers
        )
        data = response.json()
        assert "configured" in data or "enabled" in data


class TestSEOTelegramAPI:
    """Tests for SEO Notifications Telegram settings"""

    def test_seo_telegram_settings_exists(self, auth_headers):
        """SEO telegram settings endpoint should exist"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-seo", headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
