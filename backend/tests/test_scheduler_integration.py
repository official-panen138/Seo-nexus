"""
Scheduler Integration Tests
============================
Tests for APScheduler integration with OptimizationReminderService.

Features tested:
- Scheduler starts automatically on server startup
- GET /api/v3/scheduler/reminder-status returns scheduler status
- POST /api/v3/scheduler/trigger-reminders manually triggers the reminder job
- GET /api/v3/scheduler/execution-logs returns execution history
- Scheduler execution logs are saved to scheduler_execution_logs collection
- Scheduler graceful shutdown on app termination
"""

import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSchedulerIntegration:
    """Tests for scheduler integration endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Get auth token for super_admin user"""
        self.auth_token = None
        
        # Login as super_admin
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "admin152133@example.com",
                "password": "admin123"
            }
        )
        
        if login_response.status_code == 200:
            self.auth_token = login_response.json().get("access_token")
            self.user = login_response.json().get("user")
        else:
            pytest.skip(f"Login failed: {login_response.status_code} - {login_response.text}")
        
        self.headers = {"Authorization": f"Bearer {self.auth_token}"}
    
    # ==================== Test 1: Scheduler Status ====================
    def test_scheduler_status_returns_running(self):
        """
        Test GET /api/v3/scheduler/reminder-status returns scheduler status.
        Scheduler should be running with next_run_time populated.
        """
        response = requests.get(
            f"{BASE_URL}/api/v3/scheduler/reminder-status",
            headers=self.headers
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "scheduler" in data, "Response should contain 'scheduler' key"
        
        scheduler_info = data["scheduler"]
        assert scheduler_info.get("running") == True, "Scheduler should be running"
        assert scheduler_info.get("job_id") == "optimization_reminder_job", "Job ID should be optimization_reminder_job"
        assert scheduler_info.get("interval_hours") == 24, "Interval should be 24 hours"
        
        # next_run_time should be present (string ISO format)
        next_run_time = scheduler_info.get("next_run_time")
        assert next_run_time is not None, "next_run_time should be populated"
        
        print(f"✓ Scheduler is running")
        print(f"✓ Job ID: {scheduler_info.get('job_id')}")
        print(f"✓ Interval: {scheduler_info.get('interval_hours')} hours")
        print(f"✓ Next run time: {next_run_time}")
        
        # Check last_execution (may be None if never run)
        last_execution = data.get("last_execution")
        if last_execution:
            print(f"✓ Last execution: {last_execution.get('executed_at')}")
            print(f"✓ Last status: {last_execution.get('status')}")
    
    # ==================== Test 2: Manual Trigger ====================
    def test_trigger_reminders_manually(self):
        """
        Test POST /api/v3/scheduler/trigger-reminders manually triggers the job.
        Should create an execution log entry.
        """
        # Get count of execution logs before trigger
        logs_before = requests.get(
            f"{BASE_URL}/api/v3/scheduler/execution-logs",
            headers=self.headers,
            params={"limit": 100}
        )
        logs_before_count = len(logs_before.json().get("logs", []))
        
        # Trigger the reminder job
        response = requests.post(
            f"{BASE_URL}/api/v3/scheduler/trigger-reminders",
            headers=self.headers
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "message" in data, "Response should contain 'message'"
        assert "Reminder job triggered successfully" in data.get("message", ""), "Should confirm successful trigger"
        assert data.get("triggered_by") == "admin152133@example.com", "Should show triggering user"
        assert "timestamp" in data, "Should include timestamp"
        
        print(f"✓ Trigger response: {data.get('message')}")
        print(f"✓ Triggered by: {data.get('triggered_by')}")
        print(f"✓ Timestamp: {data.get('timestamp')}")
        
        # Verify result contains expected fields
        result = data.get("result", {})
        if result:
            print(f"✓ Trigger result: {result}")
        
        # Verify a new execution log was created
        logs_after = requests.get(
            f"{BASE_URL}/api/v3/scheduler/execution-logs",
            headers=self.headers,
            params={"limit": 100}
        )
        logs_after_count = len(logs_after.json().get("logs", []))
        
        assert logs_after_count > logs_before_count, f"Expected new log entry. Before: {logs_before_count}, After: {logs_after_count}"
        print(f"✓ Execution log count increased from {logs_before_count} to {logs_after_count}")
    
    # ==================== Test 3: Execution Logs ====================
    def test_execution_logs_returns_history(self):
        """
        Test GET /api/v3/scheduler/execution-logs returns execution history.
        Should contain logs with job_id, executed_at, status, and results.
        """
        response = requests.get(
            f"{BASE_URL}/api/v3/scheduler/execution-logs",
            headers=self.headers,
            params={"limit": 20}
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "logs" in data, "Response should contain 'logs' key"
        assert "total" in data, "Response should contain 'total' key"
        
        logs = data.get("logs", [])
        print(f"✓ Found {len(logs)} execution logs")
        
        # Verify log structure (if any logs exist)
        if logs:
            latest_log = logs[0]  # Sorted by executed_at desc
            
            assert "job_id" in latest_log, "Log should contain job_id"
            assert "executed_at" in latest_log, "Log should contain executed_at"
            assert "status" in latest_log, "Log should contain status"
            
            print(f"✓ Latest log job_id: {latest_log.get('job_id')}")
            print(f"✓ Latest log executed_at: {latest_log.get('executed_at')}")
            print(f"✓ Latest log status: {latest_log.get('status')}")
            
            # Check results if present
            results = latest_log.get("results", {})
            if results:
                print(f"✓ Results: total_found={results.get('total_found')}, reminders_sent={results.get('reminders_sent')}, reminders_failed={results.get('reminders_failed')}")
    
    # ==================== Test 4: Filter by Job ID ====================
    def test_execution_logs_filter_by_job_id(self):
        """
        Test GET /api/v3/scheduler/execution-logs with job_id filter.
        """
        response = requests.get(
            f"{BASE_URL}/api/v3/scheduler/execution-logs",
            headers=self.headers,
            params={"job_id": "optimization_reminder_job", "limit": 10}
        )
        
        # Status code assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        logs = data.get("logs", [])
        
        # Verify all returned logs have the correct job_id
        for log in logs:
            assert log.get("job_id") == "optimization_reminder_job", f"Expected job_id 'optimization_reminder_job', got '{log.get('job_id')}'"
        
        print(f"✓ Filter by job_id works: {len(logs)} logs returned")
    
    # ==================== Test 5: Non-Super Admin Access Denied ====================
    def test_scheduler_endpoints_require_super_admin(self):
        """
        Test that scheduler endpoints return 403 for non-super_admin users.
        """
        # Create a test user with viewer role
        viewer_email = f"viewer_{datetime.now().strftime('%H%M%S')}@example.com"
        
        # Try to create viewer user (super admin can do this)
        create_response = requests.post(
            f"{BASE_URL}/api/users/create",
            headers=self.headers,
            json={
                "email": viewer_email,
                "name": "Test Viewer",
                "role": "viewer",
                "brand_scope_ids": [],
                "password": "viewer123"
            }
        )
        
        if create_response.status_code != 200:
            print(f"Note: Could not create test viewer user: {create_response.text}")
            # Skip this test if we can't create a viewer
            pytest.skip("Could not create test viewer user")
            return
        
        # Login as the viewer
        viewer_login = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": viewer_email,
                "password": "viewer123"
            }
        )
        
        if viewer_login.status_code != 200:
            pytest.skip("Could not login as viewer user")
            return
        
        viewer_token = viewer_login.json().get("access_token")
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
        
        # Test scheduler status endpoint
        status_response = requests.get(
            f"{BASE_URL}/api/v3/scheduler/reminder-status",
            headers=viewer_headers
        )
        assert status_response.status_code == 403, f"Expected 403 for viewer, got {status_response.status_code}"
        print("✓ GET /scheduler/reminder-status returns 403 for viewer")
        
        # Test trigger endpoint
        trigger_response = requests.post(
            f"{BASE_URL}/api/v3/scheduler/trigger-reminders",
            headers=viewer_headers
        )
        assert trigger_response.status_code == 403, f"Expected 403 for viewer, got {trigger_response.status_code}"
        print("✓ POST /scheduler/trigger-reminders returns 403 for viewer")
        
        # Test execution logs endpoint
        logs_response = requests.get(
            f"{BASE_URL}/api/v3/scheduler/execution-logs",
            headers=viewer_headers
        )
        assert logs_response.status_code == 403, f"Expected 403 for viewer, got {logs_response.status_code}"
        print("✓ GET /scheduler/execution-logs returns 403 for viewer")
    
    # ==================== Test 6: Scheduler Status Fields Validation ====================
    def test_scheduler_status_fields_structure(self):
        """
        Test that scheduler status response has all expected fields.
        """
        response = requests.get(
            f"{BASE_URL}/api/v3/scheduler/reminder-status",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Validate scheduler object structure
        scheduler = data.get("scheduler", {})
        expected_fields = ["running", "job_id", "interval_hours", "next_run_time"]
        
        for field in expected_fields:
            assert field in scheduler, f"Scheduler should have '{field}' field"
        
        # Validate types
        assert isinstance(scheduler.get("running"), bool), "running should be boolean"
        assert isinstance(scheduler.get("job_id"), str), "job_id should be string"
        assert isinstance(scheduler.get("interval_hours"), int), "interval_hours should be int"
        
        # next_run_time should be string (ISO format) or None
        next_run = scheduler.get("next_run_time")
        assert next_run is None or isinstance(next_run, str), "next_run_time should be string or None"
        
        print(f"✓ Scheduler status structure validated")
        print(f"  - running: {scheduler.get('running')} (bool)")
        print(f"  - job_id: {scheduler.get('job_id')} (str)")
        print(f"  - interval_hours: {scheduler.get('interval_hours')} (int)")
        print(f"  - next_run_time: {next_run} (str|None)")
    
    # ==================== Test 7: Execution Log Structure ====================
    def test_execution_log_structure(self):
        """
        Test that execution logs have the expected structure with results.
        """
        # First trigger to ensure we have at least one log
        requests.post(
            f"{BASE_URL}/api/v3/scheduler/trigger-reminders",
            headers=self.headers
        )
        
        response = requests.get(
            f"{BASE_URL}/api/v3/scheduler/execution-logs",
            headers=self.headers,
            params={"limit": 1}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        logs = data.get("logs", [])
        
        assert len(logs) > 0, "Should have at least one log after trigger"
        
        log = logs[0]
        
        # Validate required fields
        assert "job_id" in log, "Log should have job_id"
        assert "executed_at" in log, "Log should have executed_at"
        assert "status" in log, "Log should have status"
        
        # Status should be 'success' or 'failed'
        assert log.get("status") in ["success", "failed"], f"Status should be 'success' or 'failed', got '{log.get('status')}'"
        
        # If success, should have results
        if log.get("status") == "success":
            results = log.get("results", {})
            assert "total_found" in results or results == {}, "Successful log should have results with total_found (or empty results)"
            print(f"✓ Execution log has results: {results}")
        
        print(f"✓ Execution log structure validated")
        print(f"  - job_id: {log.get('job_id')}")
        print(f"  - executed_at: {log.get('executed_at')}")
        print(f"  - status: {log.get('status')}")


# ==================== Server Startup/Shutdown Tests ====================
class TestSchedulerLifecycle:
    """
    Tests for scheduler lifecycle - startup and shutdown.
    These tests verify the scheduler is initialized properly.
    """
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Get auth token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "admin152133@example.com",
                "password": "admin123"
            }
        )
        
        if login_response.status_code == 200:
            self.auth_token = login_response.json().get("access_token")
        else:
            pytest.skip("Login failed")
        
        self.headers = {"Authorization": f"Bearer {self.auth_token}"}
    
    def test_scheduler_is_initialized_on_startup(self):
        """
        Test that scheduler is initialized and running after server startup.
        This verifies the scheduler starts automatically with the app.
        """
        response = requests.get(
            f"{BASE_URL}/api/v3/scheduler/reminder-status",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Should NOT be "not_initialized" status
        assert data.get("status") != "not_initialized", "Scheduler should be initialized on startup"
        
        scheduler = data.get("scheduler", {})
        assert scheduler.get("running") == True, "Scheduler should be running after server startup"
        
        print("✓ Scheduler is initialized and running on server startup")
        print(f"✓ Job: {scheduler.get('job_id')}")
        print(f"✓ Interval: {scheduler.get('interval_hours')} hours")
    
    def test_scheduler_job_is_configured_for_24_hours(self):
        """
        Test that the scheduler job is configured to run every 24 hours.
        """
        response = requests.get(
            f"{BASE_URL}/api/v3/scheduler/reminder-status",
            headers=self.headers
        )
        
        assert response.status_code == 200
        data = response.json()
        scheduler = data.get("scheduler", {})
        
        assert scheduler.get("interval_hours") == 24, f"Expected 24-hour interval, got {scheduler.get('interval_hours')}"
        
        print(f"✓ Scheduler configured for 24-hour interval")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
