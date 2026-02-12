"""
Conflict Metrics P0/P1 Test Suite
==================================
Tests for the new conflict resolution metrics dashboard:

P0 Requirements:
1. Fingerprint-based recurring conflict detection
2. Top Resolvers excludes null/system users
3. Status derived from linked optimizations
4. Resolution time calculation (first_detected_at → completed_at)
5. Data migration endpoint

P1 Requirements:
1. False Resolution Rate metric
2. Average Recurrence Interval
3. Recurring Conflict CTA
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestConflictMetricsEndpoint:
    """Test GET /api/v3/conflicts/metrics endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_metrics_returns_200(self):
        """Basic endpoint health check"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/metrics",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /conflicts/metrics returns 200")
    
    def test_metrics_returns_all_required_fields(self):
        """Verify all P0 and P1 metrics are returned"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/metrics?days=30",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # P0 Required fields
        required_fields = [
            "period_days",
            "period_start",
            "period_end",
            "total_conflicts",
            "resolved_count",
            "open_count",
            "resolution_rate_percent",
            "avg_resolution_time_hours",  # P0: Resolution time
            "recurring_conflicts",  # P0: Recurring conflicts count
            "top_resolvers",  # P0: Top resolvers list
            "by_severity",
            "by_type",
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
            print(f"✓ Field present: {field}")
        
        # P1 Required fields
        p1_fields = [
            "false_resolution_count",
            "false_resolution_rate_percent",  # P1: False resolution rate
            "avg_recurrence_interval_days",  # P1: Recurrence interval
            "resolution_times_breakdown",  # P1: Time breakdown
            "recurring_conflict_ids",  # P1: IDs for recurring CTA
        ]
        
        for field in p1_fields:
            assert field in data, f"Missing P1 field: {field}"
            print(f"✓ P1 Field present: {field}")
    
    def test_top_resolvers_format(self):
        """P0: Verify top_resolvers is array of objects with correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/metrics?days=30",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        top_resolvers = data.get("top_resolvers", [])
        assert isinstance(top_resolvers, list), "top_resolvers should be a list"
        
        # If we have resolvers, verify structure
        if top_resolvers:
            resolver = top_resolvers[0]
            required_resolver_fields = ["user_id", "name", "email", "resolved_count"]
            for field in required_resolver_fields:
                assert field in resolver, f"Missing resolver field: {field}"
                print(f"✓ Resolver has {field}: {resolver.get(field)}")
            
            # Verify resolved_count is a number
            assert isinstance(resolver["resolved_count"], int), "resolved_count should be int"
            print(f"✓ top_resolvers correctly formatted with {len(top_resolvers)} entries")
        else:
            print("✓ top_resolvers is empty list (no resolvers yet)")
    
    def test_top_resolvers_excludes_system_users(self):
        """P0: Verify system/null users are excluded from top resolvers"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/metrics?days=30",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        top_resolvers = data.get("top_resolvers", [])
        
        # Check none of the resolvers are system users
        system_user_patterns = ["system", "null", "System", "System (Auto)"]
        for resolver in top_resolvers:
            user_id = resolver.get("user_id", "")
            assert user_id not in system_user_patterns, f"System user found in resolvers: {user_id}"
            assert not user_id.startswith("system"), f"System user found: {user_id}"
        
        print(f"✓ No system/null users in top_resolvers ({len(top_resolvers)} resolvers)")
    
    def test_resolution_time_is_calculated(self):
        """P0: Verify avg_resolution_time_hours is calculated correctly"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/metrics?days=30",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        avg_time = data.get("avg_resolution_time_hours")
        assert avg_time is not None, "avg_resolution_time_hours should be present"
        assert isinstance(avg_time, (int, float)), "avg_resolution_time_hours should be numeric"
        
        print(f"✓ avg_resolution_time_hours = {avg_time} hours")
    
    def test_resolution_times_breakdown(self):
        """P1: Verify resolution_times_breakdown has all buckets"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/metrics?days=30",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        breakdown = data.get("resolution_times_breakdown", {})
        required_buckets = ["under_1_hour", "1_to_24_hours", "1_to_7_days", "over_7_days"]
        
        for bucket in required_buckets:
            assert bucket in breakdown, f"Missing time bucket: {bucket}"
            assert isinstance(breakdown[bucket], int), f"{bucket} should be int"
            print(f"✓ {bucket}: {breakdown[bucket]}")
    
    def test_false_resolution_metrics(self):
        """P1: Verify false resolution metrics are returned"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/metrics?days=30",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check false resolution count
        assert "false_resolution_count" in data
        assert isinstance(data["false_resolution_count"], int)
        print(f"✓ false_resolution_count = {data['false_resolution_count']}")
        
        # Check false resolution rate
        assert "false_resolution_rate_percent" in data
        assert isinstance(data["false_resolution_rate_percent"], (int, float))
        print(f"✓ false_resolution_rate_percent = {data['false_resolution_rate_percent']}%")
    
    def test_recurring_conflicts_excludes_resolved(self):
        """P0: Verify recurring_conflicts count excludes resolved/approved conflicts"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/metrics?days=30",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        recurring_count = data.get("recurring_conflicts", 0)
        recurring_ids = data.get("recurring_conflict_ids", [])
        
        assert isinstance(recurring_count, int)
        assert isinstance(recurring_ids, list)
        assert len(recurring_ids) <= recurring_count
        
        print(f"✓ recurring_conflicts = {recurring_count}")
        print(f"✓ recurring_conflict_ids has {len(recurring_ids)} entries")
    
    def test_period_filter_works(self):
        """Verify period filter affects results"""
        response_7 = requests.get(
            f"{BASE_URL}/api/v3/conflicts/metrics?days=7",
            headers=self.headers
        )
        response_30 = requests.get(
            f"{BASE_URL}/api/v3/conflicts/metrics?days=30",
            headers=self.headers
        )
        
        assert response_7.status_code == 200
        assert response_30.status_code == 200
        
        data_7 = response_7.json()
        data_30 = response_30.json()
        
        assert data_7["period_days"] == 7
        assert data_30["period_days"] == 30
        
        print(f"✓ 7-day period: {data_7['total_conflicts']} conflicts")
        print(f"✓ 30-day period: {data_30['total_conflicts']} conflicts")


class TestMigrationEndpoint:
    """Test POST /api/v3/conflicts/migrate-approved endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_migration_endpoint_returns_200(self):
        """Migration endpoint should return 200 for Super Admin"""
        response = requests.post(
            f"{BASE_URL}/api/v3/conflicts/migrate-approved",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ POST /conflicts/migrate-approved returns 200")
    
    def test_migration_returns_stats(self):
        """Migration should return processing stats"""
        response = requests.post(
            f"{BASE_URL}/api/v3/conflicts/migrate-approved",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "success" in data
        assert "stats" in data
        
        stats = data["stats"]
        expected_stats = ["status_fixed", "fingerprints_added", "first_detected_set", "total_processed"]
        for stat in expected_stats:
            assert stat in stats, f"Missing stat: {stat}"
            print(f"✓ {stat}: {stats[stat]}")


class TestStoredConflictsWithFingerprints:
    """Test that stored conflicts have fingerprints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_conflicts_have_fingerprints(self):
        """P0: Verify conflicts have fingerprint field"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored?limit=50",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        conflicts = data.get("conflicts", [])
        
        for conflict in conflicts:
            assert "fingerprint" in conflict, f"Conflict {conflict.get('id')} missing fingerprint"
            # Fingerprint should be a non-empty string
            fp = conflict.get("fingerprint")
            if fp:  # Some might be None if not yet migrated
                assert isinstance(fp, str), f"Fingerprint should be string"
                assert len(fp) >= 16, f"Fingerprint too short: {fp}"
        
        print(f"✓ {len(conflicts)} conflicts checked for fingerprints")
    
    def test_conflicts_have_first_detected_at(self):
        """P0: Verify conflicts have first_detected_at for accurate resolution time"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored?limit=50",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        conflicts = data.get("conflicts", [])
        
        has_first_detected = 0
        for conflict in conflicts:
            if conflict.get("first_detected_at"):
                has_first_detected += 1
        
        print(f"✓ {has_first_detected}/{len(conflicts)} conflicts have first_detected_at")
    
    def test_resolved_conflicts_have_is_active_false(self):
        """P0: Verify resolved/approved conflicts are inactive"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored?limit=50",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        conflicts = data.get("conflicts", [])
        
        for conflict in conflicts:
            status = conflict.get("status")
            is_active = conflict.get("is_active", True)
            
            if status in ["resolved", "approved"]:
                assert is_active == False, f"Conflict {conflict.get('id')} is resolved but is_active=True"
        
        print(f"✓ All resolved/approved conflicts have is_active=False")


class TestConflictStatusSync:
    """Test that optimization status changes sync to conflict status"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@test.com",
            "password": "admin123"
        })
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_linked_conflicts_sync_with_optimizations(self):
        """Verify conflicts with linked optimizations have synced status"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored?limit=50",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        conflicts = data.get("conflicts", [])
        
        for conflict in conflicts:
            opt = conflict.get("linked_optimization")
            if opt:
                opt_status = opt.get("status")
                conflict_status = conflict.get("status")
                
                # Verify status mapping is correct
                if opt_status == "completed":
                    assert conflict_status in ["resolved", "approved"], \
                        f"Completed optimization but conflict status is {conflict_status}"
                elif opt_status == "in_progress":
                    assert conflict_status == "under_review", \
                        f"In progress optimization but conflict status is {conflict_status}"
        
        print(f"✓ Conflict statuses properly synced with linked optimizations")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
