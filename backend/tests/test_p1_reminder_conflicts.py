"""
Test P1 Features: Reminder System Override & Conflicts Detection
================================================================
Tests:
- GET /api/v3/networks/{id}/reminder-config - Get network reminder config
- PUT /api/v3/networks/{id}/reminder-config - Save network reminder config
- GET /api/v3/reports/conflicts - Get SEO conflicts data
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TEST_NETWORK_ID = "76e067db-60ba-4e3b-a949-b3229dc1c652"


class TestReminderConfigAPI:
    """Test reminder configuration endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login to get token"""
        login_url = f"{BASE_URL}/api/auth/login"
        response = requests.post(
            login_url,
            json={"email": "superadmin@seonoc.com", "password": "SuperAdmin123!"},
        )
        if response.status_code != 200:
            pytest.skip(f"Login failed: {response.status_code}")

        self.token = response.json().get("access_token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def test_get_reminder_config_returns_200(self):
        """GET /api/v3/networks/{id}/reminder-config should return 200"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/reminder-config",
            headers=self.headers,
        )
        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

    def test_get_reminder_config_has_global_default(self):
        """GET reminder-config should include global_default"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/reminder-config",
            headers=self.headers,
        )
        data = response.json()
        assert "global_default" in data, "Response must include global_default"
        assert "interval_days" in data.get(
            "global_default", {}
        ), "global_default must have interval_days"

    def test_get_reminder_config_has_effective_interval(self):
        """GET reminder-config should include effective_interval_days"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/reminder-config",
            headers=self.headers,
        )
        data = response.json()
        assert (
            "effective_interval_days" in data
        ), "Response must include effective_interval_days"
        assert isinstance(
            data["effective_interval_days"], int
        ), "effective_interval_days must be int"

    def test_get_reminder_config_has_network_override(self):
        """GET reminder-config should include network_override field"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/reminder-config",
            headers=self.headers,
        )
        data = response.json()
        assert "network_override" in data, "Response must include network_override"

    def test_put_reminder_config_with_use_global_returns_200(self):
        """PUT reminder-config with use_global=true should return 200"""
        response = requests.put(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/reminder-config",
            headers=self.headers,
            json={"use_global": True},
        )
        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data, "Response should include message"

    def test_put_reminder_config_with_custom_interval_returns_200(self):
        """PUT reminder-config with custom interval_days should return 200"""
        response = requests.put(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/reminder-config",
            headers=self.headers,
            json={"interval_days": 5},
        )
        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert (
            "interval_days" in data or "message" in data
        ), "Response should include interval_days or message"

    def test_put_reminder_config_validates_interval_range(self):
        """PUT reminder-config should validate interval_days between 1-30"""
        # Test interval too high
        response = requests.put(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/reminder-config",
            headers=self.headers,
            json={"interval_days": 99},
        )
        assert (
            response.status_code == 400
        ), f"Expected 400 for invalid interval, got {response.status_code}"

    def test_put_reminder_config_reset_to_global(self):
        """PUT reminder-config with use_global=true resets to global default"""
        # First set custom value
        requests.put(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/reminder-config",
            headers=self.headers,
            json={"interval_days": 7},
        )

        # Reset to global
        response = requests.put(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/reminder-config",
            headers=self.headers,
            json={"use_global": True},
        )
        assert response.status_code == 200

        # Verify reset
        get_response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/reminder-config",
            headers=self.headers,
        )
        data = get_response.json()
        # After reset, network_override should be empty
        assert data.get("network_override") in [
            None,
            {},
        ], "network_override should be empty after reset"


class TestConflictsAPI:
    """Test conflicts detection endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login to get token"""
        login_url = f"{BASE_URL}/api/auth/login"
        response = requests.post(
            login_url,
            json={"email": "superadmin@seonoc.com", "password": "SuperAdmin123!"},
        )
        if response.status_code != 200:
            pytest.skip(f"Login failed: {response.status_code}")

        self.token = response.json().get("access_token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def test_get_conflicts_returns_200(self):
        """GET /api/v3/reports/conflicts should return 200"""
        response = requests.get(
            f"{BASE_URL}/api/v3/reports/conflicts", headers=self.headers
        )
        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

    def test_get_conflicts_has_conflicts_array(self):
        """GET conflicts should return conflicts array"""
        response = requests.get(
            f"{BASE_URL}/api/v3/reports/conflicts", headers=self.headers
        )
        data = response.json()
        assert "conflicts" in data, "Response must include conflicts array"
        assert isinstance(data["conflicts"], list), "conflicts must be a list"

    def test_get_conflicts_has_total_count(self):
        """GET conflicts should return total count"""
        response = requests.get(
            f"{BASE_URL}/api/v3/reports/conflicts", headers=self.headers
        )
        data = response.json()
        assert "total" in data, "Response must include total"
        assert isinstance(data["total"], int), "total must be an integer"

    def test_get_conflicts_has_by_severity_breakdown(self):
        """GET conflicts should return by_severity breakdown"""
        response = requests.get(
            f"{BASE_URL}/api/v3/reports/conflicts", headers=self.headers
        )
        data = response.json()
        assert "by_severity" in data, "Response must include by_severity"
        by_severity = data["by_severity"]
        # Should have severity levels
        for level in ["critical", "high", "medium", "low"]:
            assert level in by_severity, f"by_severity must include {level}"
            assert isinstance(by_severity[level], int), f"{level} count must be int"

    def test_get_conflicts_filtered_by_network(self):
        """GET conflicts with network_id filter should work"""
        response = requests.get(
            f"{BASE_URL}/api/v3/reports/conflicts?network_id={TEST_NETWORK_ID}",
            headers=self.headers,
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "conflicts" in data, "Response must include conflicts"

    def test_get_conflicts_structure_if_any(self):
        """GET conflicts - verify conflict structure if any conflicts exist"""
        response = requests.get(
            f"{BASE_URL}/api/v3/reports/conflicts", headers=self.headers
        )
        data = response.json()
        conflicts = data.get("conflicts", [])

        if len(conflicts) > 0:
            conflict = conflicts[0]
            # Verify conflict has required fields
            assert "conflict_type" in conflict, "Conflict must have conflict_type"
            assert "severity" in conflict, "Conflict must have severity"
            assert (
                "description" in conflict or "message" in conflict
            ), "Conflict must have description or message"
        else:
            print(
                "No conflicts detected - this is expected if networks are configured correctly"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
