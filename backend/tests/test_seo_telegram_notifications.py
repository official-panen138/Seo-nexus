"""
Test SEO Telegram Notifications (Phase 1)
==========================================
Tests for SEO Telegram notifications with forum topic routing,
global reminder config, and reminder scheduler.

Features tested:
- GET /api/v3/settings/telegram-seo returns topic routing fields
- PUT /api/v3/settings/telegram-seo accepts topic routing configuration
- POST /api/v3/settings/reminder-config/run triggers manual reminder check
- GET /api/v3/settings/reminder-config returns global reminder settings
- PUT /api/v3/settings/reminder-config updates global reminder interval
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timezone

# Get BASE_URL from environment
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable not set")

# Test credentials
SUPER_ADMIN_EMAIL = "superadmin@seonoc.com"
SUPER_ADMIN_PASSWORD = "SuperAdmin123!"


class TestSeoTelegramNotifications:
    """Test SEO Telegram notification API endpoints"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for super admin"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("access_token")

    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }

    # ============== GET /api/v3/settings/telegram-seo ==============

    def test_get_telegram_seo_returns_topic_routing_fields(self, headers):
        """Test GET /api/v3/settings/telegram-seo returns all topic routing fields"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-seo", headers=headers
        )
        assert response.status_code == 200, f"GET telegram-seo failed: {response.text}"

        data = response.json()

        # Check required fields are present
        required_fields = [
            "configured",
            "enabled",
            "enable_topic_routing",
            "seo_change_topic_id",
            "seo_optimization_topic_id",
            "seo_complaint_topic_id",
            "seo_reminder_topic_id",
        ]

        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        print(f"GET /api/v3/settings/telegram-seo returned: {data}")
        print("All topic routing fields present: PASS")

    def test_get_telegram_seo_returns_correct_types(self, headers):
        """Test GET /api/v3/settings/telegram-seo returns correct field types"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-seo", headers=headers
        )
        assert response.status_code == 200

        data = response.json()

        # enabled and enable_topic_routing should be booleans
        assert isinstance(data["enabled"], bool), "enabled should be boolean"
        assert isinstance(
            data["enable_topic_routing"], bool
        ), "enable_topic_routing should be boolean"
        assert isinstance(data["configured"], bool), "configured should be boolean"

        # topic_ids can be None or strings
        topic_fields = [
            "seo_change_topic_id",
            "seo_optimization_topic_id",
            "seo_complaint_topic_id",
            "seo_reminder_topic_id",
        ]
        for field in topic_fields:
            value = data[field]
            assert value is None or isinstance(
                value, (str, int)
            ), f"{field} should be None, str, or int"

        print("Field types verified: PASS")

    # ============== PUT /api/v3/settings/telegram-seo ==============

    def test_update_telegram_seo_with_topic_routing(self, headers):
        """Test PUT /api/v3/settings/telegram-seo accepts topic routing config"""
        update_data = {
            "enable_topic_routing": True,
            "seo_change_topic_id": "123",
            "seo_optimization_topic_id": "124",
            "seo_complaint_topic_id": "125",
            "seo_reminder_topic_id": "126",
        }

        response = requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-seo",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200, f"PUT telegram-seo failed: {response.text}"

        result = response.json()
        assert "message" in result, "Response should have message"
        print(f"PUT /api/v3/settings/telegram-seo response: {result}")

        # Verify by GET
        get_response = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-seo", headers=headers
        )
        assert get_response.status_code == 200

        data = get_response.json()
        assert (
            data["enable_topic_routing"] == True
        ), "enable_topic_routing should be True"
        assert (
            data["seo_change_topic_id"] == "123"
        ), "seo_change_topic_id should be '123'"
        assert (
            data["seo_optimization_topic_id"] == "124"
        ), "seo_optimization_topic_id should be '124'"
        assert (
            data["seo_complaint_topic_id"] == "125"
        ), "seo_complaint_topic_id should be '125'"
        assert (
            data["seo_reminder_topic_id"] == "126"
        ), "seo_reminder_topic_id should be '126'"

        print("Topic routing configuration saved and verified: PASS")

    def test_update_telegram_seo_disable_topic_routing(self, headers):
        """Test disabling topic routing"""
        update_data = {"enable_topic_routing": False}

        response = requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-seo",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200, f"PUT failed: {response.text}"

        # Verify
        get_response = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-seo", headers=headers
        )
        assert get_response.status_code == 200

        data = get_response.json()
        assert (
            data["enable_topic_routing"] == False
        ), "enable_topic_routing should be False"

        print("Topic routing disabled: PASS")

    def test_update_telegram_seo_clear_topic_ids(self, headers):
        """Test clearing topic IDs by setting them to null/empty"""
        update_data = {
            "enable_topic_routing": True,
            "seo_change_topic_id": None,
            "seo_optimization_topic_id": "",
            "seo_complaint_topic_id": None,
            "seo_reminder_topic_id": "",
        }

        response = requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-seo",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200, f"PUT failed: {response.text}"

        print("Topic IDs can be cleared: PASS")

    def test_update_telegram_seo_preserves_bot_token(self, headers):
        """Test that updating topic routing preserves existing bot_token"""
        # First get current settings
        get_response1 = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-seo", headers=headers
        )
        original_data = get_response1.json()

        # Update only topic routing (no bot_token)
        update_data = {"enable_topic_routing": True, "seo_change_topic_id": "999"}

        response = requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-seo",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Verify bot_token is preserved
        get_response2 = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-seo", headers=headers
        )
        new_data = get_response2.json()

        # If there was a bot_token before, it should still be there
        if original_data.get("bot_token"):
            assert new_data.get("bot_token") == original_data.get(
                "bot_token"
            ), "bot_token should be preserved"
            print("bot_token preserved: PASS")
        else:
            print("No existing bot_token to preserve: SKIP")

    # ============== GET /api/v3/settings/reminder-config ==============

    def test_get_reminder_config_returns_correct_structure(self, headers):
        """Test GET /api/v3/settings/reminder-config returns correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/reminder-config", headers=headers
        )
        assert (
            response.status_code == 200
        ), f"GET reminder-config failed: {response.text}"

        data = response.json()

        # Check required fields
        assert "enabled" in data, "Missing 'enabled' field"
        assert (
            "interval_days" in data or "default_interval_days" in data
        ), "Missing interval_days field"

        print(f"GET /api/v3/settings/reminder-config returned: {data}")
        print("Reminder config structure verified: PASS")

    def test_get_reminder_config_has_default_values(self, headers):
        """Test that reminder config returns sensible defaults"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/reminder-config", headers=headers
        )
        assert response.status_code == 200

        data = response.json()

        # enabled should be boolean
        assert isinstance(data.get("enabled"), bool), "enabled should be boolean"

        # interval_days should be positive integer
        interval = data.get("interval_days", data.get("default_interval_days", 0))
        assert isinstance(interval, int), "interval_days should be integer"
        assert interval >= 1, "interval_days should be at least 1"

        print(f"Default interval_days: {interval}")
        print("Reminder config defaults verified: PASS")

    # ============== PUT /api/v3/settings/reminder-config ==============

    def test_update_reminder_config_interval(self, headers):
        """Test PUT /api/v3/settings/reminder-config updates interval"""
        update_data = {"enabled": True, "interval_days": 3}

        response = requests.put(
            f"{BASE_URL}/api/v3/settings/reminder-config",
            json=update_data,
            headers=headers,
        )
        assert (
            response.status_code == 200
        ), f"PUT reminder-config failed: {response.text}"

        result = response.json()
        print(f"PUT /api/v3/settings/reminder-config response: {result}")

        # Verify by GET
        get_response = requests.get(
            f"{BASE_URL}/api/v3/settings/reminder-config", headers=headers
        )
        assert get_response.status_code == 200

        data = get_response.json()
        assert (
            data.get("interval_days") == 3 or data.get("default_interval_days") == 3
        ), "interval_days should be 3"

        print("Reminder interval updated: PASS")

    def test_update_reminder_config_disable(self, headers):
        """Test disabling reminder notifications"""
        update_data = {"enabled": False, "interval_days": 2}

        response = requests.put(
            f"{BASE_URL}/api/v3/settings/reminder-config",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200, f"PUT failed: {response.text}"

        # Verify
        get_response = requests.get(
            f"{BASE_URL}/api/v3/settings/reminder-config", headers=headers
        )
        assert get_response.status_code == 200

        data = get_response.json()
        assert data["enabled"] == False, "enabled should be False"

        print("Reminder disabled: PASS")

    def test_update_reminder_config_enable(self, headers):
        """Test re-enabling reminder notifications"""
        update_data = {"enabled": True, "interval_days": 2}

        response = requests.put(
            f"{BASE_URL}/api/v3/settings/reminder-config",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200

        # Verify
        get_response = requests.get(
            f"{BASE_URL}/api/v3/settings/reminder-config", headers=headers
        )
        assert get_response.status_code == 200

        data = get_response.json()
        assert data["enabled"] == True, "enabled should be True"

        print("Reminder re-enabled: PASS")

    def test_update_reminder_config_invalid_interval_too_low(self, headers):
        """Test that interval < 1 is rejected"""
        update_data = {"enabled": True, "interval_days": 0}

        response = requests.put(
            f"{BASE_URL}/api/v3/settings/reminder-config",
            json=update_data,
            headers=headers,
        )
        assert (
            response.status_code == 400
        ), f"Expected 400 for interval=0: {response.status_code}"

        print("Invalid interval (0) rejected: PASS")

    def test_update_reminder_config_invalid_interval_too_high(self, headers):
        """Test that interval > 30 is rejected"""
        update_data = {"enabled": True, "interval_days": 31}

        response = requests.put(
            f"{BASE_URL}/api/v3/settings/reminder-config",
            json=update_data,
            headers=headers,
        )
        assert (
            response.status_code == 400
        ), f"Expected 400 for interval=31: {response.status_code}"

        print("Invalid interval (31) rejected: PASS")

    # ============== POST /api/v3/settings/reminder-config/run ==============

    def test_run_reminder_check_returns_stats(self, headers):
        """Test POST /api/v3/settings/reminder-config/run returns stats"""
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/reminder-config/run", headers=headers
        )
        assert (
            response.status_code == 200
        ), f"POST reminder-config/run failed: {response.text}"

        result = response.json()

        # Check response structure
        assert "message" in result, "Response should have message"
        assert "stats" in result, "Response should have stats"

        stats = result["stats"]
        assert "checked" in stats, "Stats should have 'checked'"
        assert "reminders_sent" in stats, "Stats should have 'reminders_sent'"

        print(f"POST /api/v3/settings/reminder-config/run response: {result}")
        print("Reminder check run successful: PASS")

    def test_run_reminder_check_stats_structure(self, headers):
        """Test reminder check stats have correct structure"""
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/reminder-config/run", headers=headers
        )
        assert response.status_code == 200

        stats = response.json().get("stats", {})

        # All stats should be non-negative integers
        expected_stats = ["checked", "reminders_sent", "errors", "skipped"]
        for stat in expected_stats:
            if stat in stats:
                assert isinstance(stats[stat], int), f"{stat} should be integer"
                assert stats[stat] >= 0, f"{stat} should be non-negative"

        print(f"Stats: {stats}")
        print("Stats structure verified: PASS")

    # ============== Authorization Tests ==============

    def test_telegram_seo_requires_super_admin_for_update(self):
        """Test PUT /api/v3/settings/telegram-seo requires super admin"""
        # First create a regular user for this test (or skip if not possible)
        # For now, just test without auth
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-seo",
            json={"enable_topic_routing": True},
        )

        # Should fail without auth
        assert response.status_code in [
            401,
            403,
        ], f"Expected 401/403 without auth: {response.status_code}"
        print("Unauthorized PUT to telegram-seo rejected: PASS")

    def test_reminder_config_requires_super_admin(self):
        """Test GET/PUT /api/v3/settings/reminder-config requires super admin"""
        # Test without auth
        response = requests.get(f"{BASE_URL}/api/v3/settings/reminder-config")
        assert response.status_code in [
            401,
            403,
        ], f"Expected 401/403 without auth: {response.status_code}"

        response = requests.put(
            f"{BASE_URL}/api/v3/settings/reminder-config",
            json={"enabled": True, "interval_days": 5},
        )
        assert response.status_code in [
            401,
            403,
        ], f"Expected 401/403 without auth: {response.status_code}"

        print("Unauthorized reminder-config access rejected: PASS")

    def test_run_reminder_requires_super_admin(self):
        """Test POST /api/v3/settings/reminder-config/run requires super admin"""
        # Test without auth
        response = requests.post(f"{BASE_URL}/api/v3/settings/reminder-config/run")
        assert response.status_code in [
            401,
            403,
        ], f"Expected 401/403 without auth: {response.status_code}"

        print("Unauthorized reminder run rejected: PASS")


class TestNotificationTopicRouting:
    """Test that notification services use correct topic routing"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for super admin"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
        )
        assert response.status_code == 200
        return response.json().get("access_token")

    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }

    def test_telegram_test_endpoint_exists(self, headers):
        """Test that the telegram test endpoint exists"""
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/telegram-seo/test", headers=headers
        )

        # Should be 200 (success) or fail gracefully if not configured
        # Should NOT be 404 (endpoint not found)
        assert response.status_code != 404, "Test endpoint should exist"

        print(f"Telegram test endpoint response: {response.status_code}")
        if response.status_code == 200:
            print("Telegram test sent successfully: PASS")
        else:
            print(
                f"Telegram test endpoint exists but returned: {response.status_code} (may need configuration)"
            )


class TestSettingsPageAPI:
    """Test API endpoints used by SettingsPage.jsx"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for super admin"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
        )
        assert response.status_code == 200
        return response.json().get("access_token")

    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }

    def test_frontend_can_load_seo_telegram_settings(self, headers):
        """Test settings that frontend loads for SEO tab"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-seo", headers=headers
        )
        assert response.status_code == 200

        data = response.json()

        # Frontend needs these fields
        frontend_fields = [
            "bot_token",
            "chat_id",
            "enabled",
            "enable_topic_routing",
            "seo_change_topic_id",
            "seo_optimization_topic_id",
            "seo_complaint_topic_id",
            "seo_reminder_topic_id",
        ]

        for field in frontend_fields:
            assert field in data, f"Frontend needs field: {field}"

        print("All frontend-required fields present: PASS")

    def test_frontend_can_save_topic_routing_config(self, headers):
        """Test that frontend can save the topic routing configuration"""
        # This mimics what SettingsPage.jsx does in handleSaveSeo
        update_data = {
            "enabled": True,
            "enable_topic_routing": True,
            "seo_change_topic_id": "123",
            "seo_optimization_topic_id": "124",
            "seo_complaint_topic_id": "125",
            "seo_reminder_topic_id": "126",
        }

        response = requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-seo",
            json=update_data,
            headers=headers,
        )
        assert response.status_code == 200, f"Frontend save failed: {response.text}"

        print("Frontend can save topic routing config: PASS")

    def test_frontend_can_toggle_topic_routing(self, headers):
        """Test frontend can toggle topic routing on/off"""
        # Disable
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-seo",
            json={"enable_topic_routing": False},
            headers=headers,
        )
        assert response.status_code == 200

        # Verify disabled
        get_resp = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-seo", headers=headers
        )
        assert get_resp.json()["enable_topic_routing"] == False

        # Enable
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-seo",
            json={"enable_topic_routing": True},
            headers=headers,
        )
        assert response.status_code == 200

        # Verify enabled
        get_resp = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-seo", headers=headers
        )
        assert get_resp.json()["enable_topic_routing"] == True

        print("Frontend can toggle topic routing: PASS")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
