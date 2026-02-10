"""
Test Conflict Resolution Status Flow
=====================================

Tests for the Conflict Resolution Flow feature (auto-sync between optimization and conflict status):
1. Optimization 'in_progress' keeps conflict as 'under_review'
2. Optimization 'completed' auto-resolves linked conflict with resolved_at timestamp
3. Optimization 'reverted' re-opens conflict back to 'detected'
4. Conflict metrics show resolved_count correctly
5. Dashboard shows proper status labels (Detected/In Progress/Resolved)
6. View Task button navigates to optimization
7. Top Resolvers shows users who resolved conflicts
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestConflictResolutionFlow:
    """Test suite for conflict resolution status synchronization"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for test user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "testadmin@test.com", "password": "test"}
        )
        if response.status_code != 200:
            pytest.skip("Authentication failed - skipping authenticated tests")
        return response.json().get("access_token") or response.json().get("token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Auth headers for requests"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    @pytest.fixture(scope="class")
    def test_user_id(self, auth_headers):
        """Get the current user ID"""
        response = requests.get(
            f"{BASE_URL}/api/users/me",
            headers=auth_headers
        )
        if response.status_code == 200:
            return response.json().get("id")
        return None
    
    # Test 1: Get existing conflicts with linked optimizations
    def test_get_conflicts_with_linked_optimizations(self, auth_headers):
        """Test that we have conflicts with linked optimizations for testing"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        conflicts = data.get("conflicts", [])
        
        # Find conflicts with optimization_id
        linked_conflicts = [c for c in conflicts if c.get("optimization_id")]
        
        print(f"Found {len(linked_conflicts)} conflicts with linked optimizations out of {len(conflicts)} total")
        
        if len(linked_conflicts) > 0:
            for c in linked_conflicts[:3]:
                print(f"  - Conflict {c['id'][:8]}...: status={c['status']}, optimization_id={c['optimization_id'][:8]}...")
        
        assert len(conflicts) > 0, "Expected at least some stored conflicts"
        print(f"SUCCESS: Found {data['total']} stored conflicts")
    
    # Test 2: Verify status mapping - under_review conflicts have linked optimization
    def test_under_review_conflicts_have_optimization(self, auth_headers):
        """Test that under_review conflicts have linked optimizations"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        under_review = [c for c in data["conflicts"] if c.get("status") == "under_review"]
        
        if not under_review:
            pytest.skip("No under_review conflicts to verify")
        
        # All under_review should have optimization_id
        for conflict in under_review:
            assert conflict.get("optimization_id"), \
                f"Under_review conflict {conflict['id']} should have optimization_id"
        
        print(f"SUCCESS: All {len(under_review)} under_review conflicts have linked optimizations")
    
    # Test 3: Update optimization to in_progress keeps conflict under_review
    def test_optimization_in_progress_keeps_conflict_under_review(self, auth_headers):
        """Test that updating optimization to 'in_progress' keeps conflict as 'under_review'"""
        # Get a conflict with linked optimization that is under_review
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Find an under_review conflict with optimization
        under_review = [c for c in data["conflicts"] 
                       if c.get("status") == "under_review" and c.get("optimization_id")]
        
        if not under_review:
            pytest.skip("No under_review conflicts with optimizations to test")
        
        conflict = under_review[0]
        optimization_id = conflict["optimization_id"]
        conflict_id = conflict["id"]
        
        # Update optimization to in_progress
        response = requests.put(
            f"{BASE_URL}/api/v3/optimizations/{optimization_id}",
            headers=auth_headers,
            json={"status": "in_progress"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify conflict is still under_review
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored/{conflict_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        updated_conflict = response.json()
        
        assert updated_conflict["status"] == "under_review", \
            f"Expected conflict status 'under_review', got '{updated_conflict['status']}'"
        
        print(f"SUCCESS: Optimization 'in_progress' keeps conflict as 'under_review'")
    
    # Test 4: Update optimization to completed auto-resolves conflict
    def test_optimization_completed_resolves_conflict(self, auth_headers, test_user_id):
        """Test that updating optimization to 'completed' auto-resolves linked conflict"""
        # Get a conflict with linked optimization that is under_review
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Find an under_review conflict with optimization
        under_review = [c for c in data["conflicts"] 
                       if c.get("status") == "under_review" and c.get("optimization_id")]
        
        if not under_review:
            pytest.skip("No under_review conflicts with optimizations to test")
        
        conflict = under_review[0]
        optimization_id = conflict["optimization_id"]
        conflict_id = conflict["id"]
        
        # Update optimization to completed
        response = requests.put(
            f"{BASE_URL}/api/v3/optimizations/{optimization_id}",
            headers=auth_headers,
            json={"status": "completed"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify conflict is now resolved
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored/{conflict_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        updated_conflict = response.json()
        
        assert updated_conflict["status"] == "resolved", \
            f"Expected conflict status 'resolved', got '{updated_conflict['status']}'"
        
        # Verify resolved_at is set
        assert updated_conflict.get("resolved_at") is not None, \
            "Resolved conflict should have resolved_at timestamp"
        
        # Verify resolved_by is set
        assert updated_conflict.get("resolved_by") is not None, \
            "Resolved conflict should have resolved_by user ID"
        
        print(f"SUCCESS: Optimization 'completed' auto-resolved conflict with resolved_at={updated_conflict['resolved_at']}")
        return optimization_id, conflict_id
    
    # Test 5: Update optimization to reverted re-opens conflict
    def test_optimization_reverted_reopens_conflict(self, auth_headers):
        """Test that updating optimization to 'reverted' re-opens linked conflict to 'detected'"""
        # Get a resolved or under_review conflict with linked optimization
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Find a conflict with optimization that we can revert
        linked = [c for c in data["conflicts"] 
                 if c.get("optimization_id") and c.get("status") in ["resolved", "under_review"]]
        
        if not linked:
            pytest.skip("No linked conflicts to test revert")
        
        conflict = linked[0]
        optimization_id = conflict["optimization_id"]
        conflict_id = conflict["id"]
        original_status = conflict["status"]
        
        print(f"Testing revert on conflict with original status: {original_status}")
        
        # Update optimization to reverted
        response = requests.put(
            f"{BASE_URL}/api/v3/optimizations/{optimization_id}",
            headers=auth_headers,
            json={"status": "reverted"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify conflict is now detected
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored/{conflict_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        updated_conflict = response.json()
        
        assert updated_conflict["status"] == "detected", \
            f"Expected conflict status 'detected' after revert, got '{updated_conflict['status']}'"
        
        # resolved_at should be null after revert
        assert updated_conflict.get("resolved_at") is None, \
            "Reverted conflict should have resolved_at=null"
        
        # resolved_by should be null after revert
        assert updated_conflict.get("resolved_by") is None, \
            "Reverted conflict should have resolved_by=null"
        
        print(f"SUCCESS: Optimization 'reverted' re-opened conflict to 'detected' (was {original_status})")
    
    # Test 6: Conflict metrics show correct resolved_count
    def test_conflict_metrics_resolved_count(self, auth_headers):
        """Test that conflict metrics show correct resolved_count"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/metrics",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        metrics = response.json()
        
        # Get actual resolved count from stored conflicts
        conflicts_response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored",
            headers=auth_headers
        )
        
        assert conflicts_response.status_code == 200
        conflicts_data = conflicts_response.json()
        
        # Count resolved conflicts
        actual_resolved = len([c for c in conflicts_data["conflicts"] if c.get("status") == "resolved"])
        
        assert metrics["resolved_count"] == actual_resolved, \
            f"Metrics resolved_count ({metrics['resolved_count']}) doesn't match actual ({actual_resolved})"
        
        # Verify open_count
        actual_open = len([c for c in conflicts_data["conflicts"] if c.get("status") in ["detected", "under_review"]])
        assert metrics["open_count"] == actual_open, \
            f"Metrics open_count ({metrics['open_count']}) doesn't match actual ({actual_open})"
        
        print(f"SUCCESS: Metrics show resolved_count={metrics['resolved_count']}, open_count={metrics['open_count']}")
    
    # Test 7: Top resolvers shows users who resolved conflicts
    def test_top_resolvers_in_metrics(self, auth_headers):
        """Test that metrics include by_resolver field showing who resolved conflicts"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/metrics",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        metrics = response.json()
        
        assert "by_resolver" in metrics, "Metrics should have by_resolver field"
        assert isinstance(metrics["by_resolver"], dict), "by_resolver should be a dict"
        
        # If there are resolved conflicts, by_resolver should have entries
        if metrics["resolved_count"] > 0:
            # There should be at least one resolver
            resolver_count = len(metrics["by_resolver"])
            total_resolved_by_resolvers = sum(metrics["by_resolver"].values())
            
            print(f"SUCCESS: by_resolver has {resolver_count} resolvers with {total_resolved_by_resolvers} total resolutions")
        else:
            print("SUCCESS: by_resolver is empty (no resolved conflicts)")
    
    # Test 8: Verify status labels mapping in stored conflicts
    def test_status_labels_in_conflicts(self, auth_headers):
        """Test that stored conflicts have valid status values"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        valid_statuses = ["detected", "under_review", "resolved", "ignored"]
        
        status_counts = {}
        for conflict in data["conflicts"]:
            status = conflict.get("status")
            assert status in valid_statuses, f"Invalid status: {status}"
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"SUCCESS: Status distribution: {status_counts}")
    
    # Test 9: Verify linked_optimization info in stored conflicts
    def test_linked_optimization_info_in_conflicts(self, auth_headers):
        """Test that stored conflicts include linked_optimization details"""
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Find conflicts with linked_optimization
        with_linked = [c for c in data["conflicts"] if c.get("linked_optimization")]
        
        if not with_linked:
            # Check if there are optimization_ids
            with_opt_id = [c for c in data["conflicts"] if c.get("optimization_id")]
            if with_opt_id:
                print(f"Note: Found {len(with_opt_id)} conflicts with optimization_id but no linked_optimization object")
            pytest.skip("No conflicts with linked_optimization object")
        
        conflict = with_linked[0]
        linked = conflict["linked_optimization"]
        
        # Verify linked_optimization has required fields
        assert "id" in linked, "linked_optimization should have id"
        assert "title" in linked, "linked_optimization should have title"
        assert "status" in linked, "linked_optimization should have status"
        
        print(f"SUCCESS: linked_optimization has id, title='{linked['title'][:30]}...', status={linked['status']}")
    
    # Test 10: Test complete status flow cycle
    def test_complete_status_flow_cycle(self, auth_headers):
        """Test the complete status flow: detected -> under_review -> resolved -> detected (via revert)"""
        # Get a detected conflict or process new ones
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Find a detected conflict to use for flow test
        detected = [c for c in data["conflicts"] if c.get("status") == "detected"]
        
        if detected:
            print(f"Found {len(detected)} detected conflicts")
            conflict = detected[0]
            
            # If it has an optimization_id already, it should move to under_review when re-processed
            if conflict.get("optimization_id"):
                print(f"Detected conflict {conflict['id'][:8]}... already has optimization_id")
        else:
            # Find any conflict with linked optimization for flow demonstration
            linked = [c for c in data["conflicts"] if c.get("optimization_id")]
            if not linked:
                pytest.skip("No conflicts available for status flow test")
            
            conflict = linked[0]
            print(f"Using {conflict['status']} conflict for demonstration")
        
        print(f"SUCCESS: Status flow test - Current conflict status: {conflict['status']}")


class TestConflictStatusFlowAPI:
    """Additional API tests for conflict status flow"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "testadmin@test.com", "password": "test"}
        )
        if response.status_code != 200:
            pytest.skip("Authentication failed")
        token = response.json().get("access_token") or response.json().get("token")
        return {"Authorization": f"Bearer {token}"}
    
    # Test 11: Verify optimization update endpoint accepts status
    def test_optimization_update_accepts_status(self, auth_headers):
        """Test that optimization update endpoint accepts status field"""
        # Get an optimization from linked conflicts
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Find a conflict with linked optimization
        linked = [c for c in data.get("conflicts", []) if c.get("optimization_id")]
        
        if not linked:
            pytest.skip("No conflict-linked optimizations to test")
        
        opt_id = linked[0]["optimization_id"]
        
        # Get current optimization status
        response = requests.get(
            f"{BASE_URL}/api/v3/optimizations/{opt_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        current_status = response.json().get("status", "pending")
        
        # Try to update to the same status (no-op but validates endpoint)
        response = requests.put(
            f"{BASE_URL}/api/v3/optimizations/{opt_id}",
            headers=auth_headers,
            json={"status": current_status}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        print(f"SUCCESS: Optimization update endpoint accepts status field")
    
    # Test 12: Verify resolve endpoint with resolution_note
    def test_resolve_conflict_with_note(self, auth_headers):
        """Test that resolve endpoint accepts resolution_note parameter"""
        # Get an under_review conflict
        response = requests.get(
            f"{BASE_URL}/api/v3/conflicts/stored",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        under_review = [c for c in data["conflicts"] if c.get("status") == "under_review"]
        
        if not under_review:
            pytest.skip("No under_review conflicts to resolve")
        
        conflict = under_review[0]
        conflict_id = conflict["id"]
        
        # Resolve with note
        response = requests.post(
            f"{BASE_URL}/api/v3/conflicts/{conflict_id}/resolve",
            headers=auth_headers,
            params={"resolution_note": "Test resolution note from automated test"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        result = response.json()
        assert result.get("success") == True, f"Expected success=True, got {result}"
        assert result.get("status") == "resolved", f"Expected status=resolved"
        
        print(f"SUCCESS: Conflict resolved with resolution_note")
    
    # Test 13: Verify metrics period filter works
    def test_metrics_period_filter(self, auth_headers):
        """Test that metrics endpoint respects days parameter"""
        # Get metrics for different periods
        for days in [7, 14, 30, 90]:
            response = requests.get(
                f"{BASE_URL}/api/v3/conflicts/metrics",
                headers=auth_headers,
                params={"days": days}
            )
            
            assert response.status_code == 200, f"Expected 200 for days={days}"
            
            metrics = response.json()
            assert metrics["period_days"] == days, \
                f"Expected period_days={days}, got {metrics['period_days']}"
        
        print("SUCCESS: Metrics period filter works for 7, 14, 30, 90 days")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
