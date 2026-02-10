"""
Test Access Summary Panel Feature for SEO Networks
===================================================

Tests P0 Access Summary Panel:
1. Network cards (GroupsPage): managers count, open complaints badge, last optimization date
2. Network detail header (GroupDetailPage): visibility mode, managers, open complaints count, last activity

API Endpoints:
- GET /api/v3/networks - Returns open_complaints_count and last_optimization_at
- GET /api/v3/networks/{id} - Returns open_complaints_count and last_optimization_at
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestAccessSummaryPanelAPI:
    """Test Access Summary Panel fields in network API responses"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test - get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "superadmin@seonoc.com", "password": "SuperAdmin123!"},
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("access_token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def test_networks_list_returns_open_complaints_count(self):
        """Test GET /api/v3/networks returns open_complaints_count field"""
        response = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)

        assert response.status_code == 200, f"API failed: {response.text}"
        networks = response.json()

        assert isinstance(networks, list), "Expected list of networks"
        assert len(networks) > 0, "Expected at least one network"

        # Check that all networks have open_complaints_count field
        for network in networks:
            assert (
                "open_complaints_count" in network
            ), f"Missing open_complaints_count in network {network.get('id')}"
            assert isinstance(
                network["open_complaints_count"], int
            ), "open_complaints_count should be integer"
            print(
                f"Network '{network.get('name')}': open_complaints_count = {network['open_complaints_count']}"
            )

    def test_networks_list_returns_last_optimization_at(self):
        """Test GET /api/v3/networks returns last_optimization_at field"""
        response = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)

        assert response.status_code == 200, f"API failed: {response.text}"
        networks = response.json()

        assert isinstance(networks, list), "Expected list of networks"

        # Check that all networks have last_optimization_at field
        for network in networks:
            assert (
                "last_optimization_at" in network
            ), f"Missing last_optimization_at in network {network.get('id')}"
            # Can be null if no optimizations exist
            if network["last_optimization_at"] is not None:
                assert isinstance(
                    network["last_optimization_at"], str
                ), "last_optimization_at should be string (ISO date)"
            print(
                f"Network '{network.get('name')}': last_optimization_at = {network['last_optimization_at']}"
            )

    def test_network_detail_returns_open_complaints_count(self):
        """Test GET /api/v3/networks/{id} returns open_complaints_count field"""
        # First get list of networks
        list_response = requests.get(
            f"{BASE_URL}/api/v3/networks", headers=self.headers
        )
        assert list_response.status_code == 200
        networks = list_response.json()
        assert len(networks) > 0, "Need at least one network to test"

        # Test the detail endpoint for the first network
        network_id = networks[0]["id"]
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{network_id}", headers=self.headers
        )

        assert response.status_code == 200, f"API failed: {response.text}"
        network = response.json()

        assert (
            "open_complaints_count" in network
        ), "Missing open_complaints_count in network detail"
        assert isinstance(
            network["open_complaints_count"], int
        ), "open_complaints_count should be integer"
        print(
            f"Network detail '{network.get('name')}': open_complaints_count = {network['open_complaints_count']}"
        )

    def test_network_detail_returns_last_optimization_at(self):
        """Test GET /api/v3/networks/{id} returns last_optimization_at field"""
        # First get list of networks
        list_response = requests.get(
            f"{BASE_URL}/api/v3/networks", headers=self.headers
        )
        assert list_response.status_code == 200
        networks = list_response.json()
        assert len(networks) > 0, "Need at least one network to test"

        # Test the detail endpoint for the first network
        network_id = networks[0]["id"]
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{network_id}", headers=self.headers
        )

        assert response.status_code == 200, f"API failed: {response.text}"
        network = response.json()

        assert (
            "last_optimization_at" in network
        ), "Missing last_optimization_at in network detail"
        # Can be null if no optimizations exist
        if network["last_optimization_at"] is not None:
            assert isinstance(
                network["last_optimization_at"], str
            ), "last_optimization_at should be string (ISO date)"
        print(
            f"Network detail '{network.get('name')}': last_optimization_at = {network['last_optimization_at']}"
        )

    def test_network_with_open_complaint_shows_count(self):
        """Test network with ID 76e067db-60ba-4e3b-a949-b3229dc1c652 has open complaint"""
        network_id = "76e067db-60ba-4e3b-a949-b3229dc1c652"
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{network_id}", headers=self.headers
        )

        # This network should exist and have open complaints
        if response.status_code == 200:
            network = response.json()
            print(
                f"Network '{network.get('name')}': open_complaints_count = {network.get('open_complaints_count')}"
            )
            assert (
                network.get("open_complaints_count", 0) >= 1
            ), "Expected at least 1 open complaint"
        elif response.status_code == 404:
            pytest.skip(
                "Network 76e067db-60ba-4e3b-a949-b3229dc1c652 not found - skipping"
            )
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")

    def test_networks_list_includes_manager_summary_cache(self):
        """Test GET /api/v3/networks includes manager_summary_cache for manager badge"""
        response = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)

        assert response.status_code == 200, f"API failed: {response.text}"
        networks = response.json()

        assert isinstance(networks, list), "Expected list of networks"

        # Check that networks have manager_summary_cache field
        for network in networks:
            # This field may be null for networks without managers
            if network.get("visibility_mode") == "restricted":
                # Restricted networks should have manager info
                manager_cache = network.get("manager_summary_cache")
                if manager_cache:
                    assert (
                        "count" in manager_cache
                    ), "manager_summary_cache should have count"
                    assert (
                        "names" in manager_cache
                    ), "manager_summary_cache should have names"
                    print(
                        f"Network '{network.get('name')}' (restricted): {manager_cache['count']} managers: {manager_cache['names']}"
                    )
            else:
                print(
                    f"Network '{network.get('name')}' (brand_based): visibility_mode = {network.get('visibility_mode')}"
                )

    def test_networks_list_includes_visibility_mode(self):
        """Test GET /api/v3/networks includes visibility_mode field"""
        response = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)

        assert response.status_code == 200, f"API failed: {response.text}"
        networks = response.json()

        assert isinstance(networks, list), "Expected list of networks"

        for network in networks:
            # visibility_mode should be present
            visibility_mode = network.get("visibility_mode")
            # Default is brand_based if not set
            if visibility_mode is not None:
                assert visibility_mode in [
                    "brand_based",
                    "restricted",
                ], f"Invalid visibility_mode: {visibility_mode}"
            print(
                f"Network '{network.get('name')}': visibility_mode = {visibility_mode or 'brand_based (default)'}"
            )


class TestNetworkDetailHeaderAccessSummary:
    """Test Access Summary in network detail header"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test - get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "superadmin@seonoc.com", "password": "SuperAdmin123!"},
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("access_token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def test_network_detail_has_all_access_summary_fields(self):
        """Test network detail includes all Access Summary Panel fields"""
        # Get list of networks
        list_response = requests.get(
            f"{BASE_URL}/api/v3/networks", headers=self.headers
        )
        assert list_response.status_code == 200
        networks = list_response.json()
        assert len(networks) > 0, "Need at least one network to test"

        # Test detail for first network
        network_id = networks[0]["id"]
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{network_id}", headers=self.headers
        )

        assert response.status_code == 200, f"API failed: {response.text}"
        network = response.json()

        # All required Access Summary fields
        required_fields = [
            "visibility_mode",
            "manager_summary_cache",
            "open_complaints_count",
            "last_optimization_at",
        ]

        for field in required_fields:
            assert (
                field in network
            ), f"Missing field '{field}' in network detail response"
            print(f"  {field}: {network[field]}")

        print(f"\nNetwork '{network.get('name')}' Access Summary:")
        print(f"  visibility_mode: {network.get('visibility_mode')}")
        print(f"  manager_summary_cache: {network.get('manager_summary_cache')}")
        print(f"  open_complaints_count: {network.get('open_complaints_count')}")
        print(f"  last_optimization_at: {network.get('last_optimization_at')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
