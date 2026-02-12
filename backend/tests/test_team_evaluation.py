"""
Backend tests for Team Evaluation Dashboard and related features.
Tests:
1. Team Evaluation Summary API
2. Activity Types API
3. Optimizations with reason_note field
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://asset-monitor-58.preview.emergentagent.com"
)


class TestTeamEvaluationAPI:
    """Tests for team evaluation endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get token"""
        # Login as super admin
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "superadmin@seonoc.com", "password": "SuperAdmin123!"},
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data["access_token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def test_team_evaluation_summary_returns_200(self):
        """Test that team evaluation summary API returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/v3/team-evaluation/summary", headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        print("✓ Team evaluation summary returns 200")

    def test_team_evaluation_summary_has_required_fields(self):
        """Test that team evaluation summary has all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/v3/team-evaluation/summary", headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()

        # Check required fields
        required_fields = [
            "period_start",
            "period_end",
            "total_optimizations",
            "by_status",
            "by_activity_type",
            "by_observed_impact",
            "total_complaints",
            "top_contributors",
            "most_complained_users",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        # Verify by_status has correct keys
        assert "completed" in data["by_status"]
        assert "planned" in data["by_status"]
        assert "reverted" in data["by_status"]

        print("✓ Team evaluation summary has all required fields")

    def test_team_evaluation_summary_top_contributors_have_score(self):
        """Test that top contributors have score field"""
        response = requests.get(
            f"{BASE_URL}/api/v3/team-evaluation/summary", headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()

        if data["top_contributors"]:
            contributor = data["top_contributors"][0]
            assert "score" in contributor
            assert "user_name" in contributor
            assert "user_email" in contributor
            assert "total_optimizations" in contributor
            assert "complaint_count" in contributor
            assert isinstance(contributor["score"], (int, float))
            assert 0 <= contributor["score"] <= 5, "Score should be between 0 and 5"
            print(
                f"✓ Top contributor '{contributor['user_name']}' has score {contributor['score']}"
            )
        else:
            print("✓ No contributors yet (empty list is valid)")

    def test_team_evaluation_with_date_filter(self):
        """Test team evaluation summary with date filter"""
        end_date = datetime.utcnow().isoformat()
        start_date = (datetime.utcnow() - timedelta(days=7)).isoformat()

        response = requests.get(
            f"{BASE_URL}/api/v3/team-evaluation/summary",
            headers=self.headers,
            params={"start_date": start_date, "end_date": end_date},
        )
        assert response.status_code == 200
        data = response.json()
        assert "period_start" in data
        assert "period_end" in data
        print(
            f"✓ Team evaluation with date filter works (period: {data['period_start'][:10]} to {data['period_end'][:10]})"
        )


class TestActivityTypesAPI:
    """Tests for optimization activity types API"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "superadmin@seonoc.com", "password": "SuperAdmin123!"},
        )
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def test_get_activity_types_returns_200(self):
        """Test that activity types API returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/v3/optimization-activity-types", headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        print("✓ Activity types API returns 200")

    def test_activity_types_returns_list(self):
        """Test that activity types returns a list"""
        response = requests.get(
            f"{BASE_URL}/api/v3/optimization-activity-types", headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should have at least one activity type"
        print(f"✓ Activity types returns list with {len(data)} items")

    def test_activity_types_have_required_fields(self):
        """Test that activity types have required fields"""
        response = requests.get(
            f"{BASE_URL}/api/v3/optimization-activity-types", headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()

        for activity_type in data:
            assert "id" in activity_type
            assert "name" in activity_type
            assert "is_default" in activity_type or "usage_count" in activity_type

        print(f"✓ All activity types have required fields")

    def test_default_activity_types_exist(self):
        """Test that default activity types are present"""
        response = requests.get(
            f"{BASE_URL}/api/v3/optimization-activity-types", headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()

        names = [t["name"] for t in data]
        expected_types = [
            "Backlink Campaign",
            "On-Page Optimization",
            "Content Update",
            "Technical SEO",
        ]

        for expected in expected_types:
            assert expected in names, f"Missing default type: {expected}"

        print("✓ All default activity types are present")


class TestOptimizationsWithReasonNote:
    """Tests for optimizations with reason_note field"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "superadmin@seonoc.com", "password": "SuperAdmin123!"},
        )
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        # Get first network
        networks_response = requests.get(
            f"{BASE_URL}/api/v3/networks", headers=self.headers
        )
        if networks_response.status_code == 200 and networks_response.json():
            self.network_id = networks_response.json()[0]["id"]
        else:
            self.network_id = None

    def test_create_optimization_without_reason_note_fails(self):
        """Test that creating optimization without reason_note fails"""
        if not self.network_id:
            pytest.skip("No network available for testing")

        # Try to create optimization without reason_note
        response = requests.post(
            f"{BASE_URL}/api/v3/networks/{self.network_id}/optimizations",
            headers=self.headers,
            json={
                "activity_type": "backlink",
                "title": "Test Optimization",
                "description": "Test description for the optimization",
                "status": "planned",
                # Missing reason_note
            },
        )

        # Should fail with 400 or 422 (validation error)
        assert response.status_code in [
            400,
            422,
        ], f"Expected 400/422 but got {response.status_code}: {response.text}"
        print("✓ Creating optimization without reason_note correctly fails")

    def test_create_optimization_with_short_reason_note_fails(self):
        """Test that creating optimization with short reason_note fails"""
        if not self.network_id:
            pytest.skip("No network available for testing")

        # Try to create optimization with too short reason_note (<20 chars)
        response = requests.post(
            f"{BASE_URL}/api/v3/networks/{self.network_id}/optimizations",
            headers=self.headers,
            json={
                "activity_type": "backlink",
                "title": "Test Optimization",
                "description": "Test description for the optimization",
                "reason_note": "Too short",  # Less than 20 chars
                "status": "planned",
            },
        )

        # Should fail with 400 or 422
        assert response.status_code in [
            400,
            422,
        ], f"Expected 400/422 but got {response.status_code}: {response.text}"
        print("✓ Creating optimization with short reason_note correctly fails")

    def test_create_optimization_with_valid_reason_note_succeeds(self):
        """Test that creating optimization with valid reason_note succeeds"""
        if not self.network_id:
            pytest.skip("No network available for testing")

        # Create optimization with valid reason_note (20+ chars)
        response = requests.post(
            f"{BASE_URL}/api/v3/networks/{self.network_id}/optimizations",
            headers=self.headers,
            json={
                "activity_type": "backlink",
                "title": "TEST_Valid Optimization",
                "description": "Test description for the optimization with valid reason",
                "reason_note": "This is a valid reason note that explains why we are doing this optimization for better SEO results",
                "status": "planned",
            },
        )

        assert (
            response.status_code == 200
        ), f"Failed to create optimization: {response.text}"
        data = response.json()
        assert data["reason_note"] is not None
        assert len(data["reason_note"]) >= 20

        # Cleanup - delete the test optimization
        opt_id = data["id"]
        delete_response = requests.delete(
            f"{BASE_URL}/api/v3/optimizations/{opt_id}", headers=self.headers
        )

        print(f"✓ Creating optimization with valid reason_note succeeds (ID: {opt_id})")

    def test_get_optimizations_includes_reason_note(self):
        """Test that getting optimizations includes reason_note field"""
        if not self.network_id:
            pytest.skip("No network available for testing")

        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{self.network_id}/optimizations",
            headers=self.headers,
        )

        assert response.status_code == 200
        data = response.json()

        if data.get("data") and len(data["data"]) > 0:
            opt = data["data"][0]
            assert (
                "reason_note" in opt
            ), "reason_note field should be in optimization response"
            print(
                f"✓ Optimization includes reason_note: {opt.get('reason_note', 'null')[:50] if opt.get('reason_note') else 'null'}..."
            )
        else:
            print("✓ No optimizations found but API structure is correct")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
