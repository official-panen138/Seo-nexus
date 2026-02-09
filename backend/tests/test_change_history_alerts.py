"""
Test Suite for P0 Change History and Alerts Features
=====================================================
Tests the Change History tab and Alerts panel functionality in Network Detail page.
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://seo-noc-preview.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "admin123"

# Known test network with change history data
TEST_NETWORK_ID = "a8ea05d6-6d3a-4a5d-86c6-5d9c0be8dc21"  # TESTER2


@pytest.fixture(scope="module")
def auth_token():
    """Authenticate and get JWT token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def headers(auth_token):
    """Request headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestChangeHistoryAPI:
    """Test GET /api/v3/networks/{id}/change-history endpoint"""
    
    def test_get_change_history_returns_list(self, headers):
        """Change history endpoint returns list of logs"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/change-history?limit=100",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Change history contains {len(data)} records")
    
    def test_change_log_has_required_fields(self, headers):
        """Each change log has required fields for UI display"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/change-history?limit=10",
            headers=headers
        )
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 0:
            log = data[0]
            
            # Required fields for table columns
            required_fields = [
                "id",
                "created_at",        # Date column
                "actor_email",       # User column
                "affected_node",     # Domain/Path column
                "action_type",       # Action column
                "change_note",       # Note column
            ]
            
            for field in required_fields:
                assert field in log, f"Missing required field: {field}"
            
            print(f"Change log {log['id']} has all required fields")
            print(f"  - Date: {log['created_at']}")
            print(f"  - User: {log['actor_email']}")
            print(f"  - Affected Node: {log['affected_node']}")
            print(f"  - Action: {log['action_type']}")
            print(f"  - Note: {log['change_note'][:50]}...")
    
    def test_change_log_has_snapshots(self, headers):
        """Change logs have before/after snapshots for detail drawer"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/change-history?limit=5",
            headers=headers
        )
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 0:
            log = data[0]
            
            # Check for snapshot fields (may be null for create/delete)
            assert "before_snapshot" in log, "Missing before_snapshot field"
            assert "after_snapshot" in log, "Missing after_snapshot field"
            
            # For update actions, both should have data
            if log.get("action_type") in ["update_node", "relink_node", "change_role"]:
                assert log["before_snapshot"] is not None, "Update should have before_snapshot"
                assert log["after_snapshot"] is not None, "Update should have after_snapshot"
            
            print(f"Snapshot data present for log: {log['action_type']}")
    
    def test_change_log_has_entry_id_for_graph_highlight(self, headers):
        """Change logs have entry_id for 'View Node in Graph' feature"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/change-history?limit=5",
            headers=headers
        )
        assert response.status_code == 200
        
        data = response.json()
        # entry_id is typically in after_snapshot for created entries
        # or directly on the log for lookup
        if len(data) > 0:
            log = data[0]
            # The entry_id is stored in the after_snapshot.id
            if log.get("after_snapshot"):
                assert "id" in log["after_snapshot"], "after_snapshot should have entry id"
                print(f"Entry ID for graph highlight: {log['after_snapshot']['id']}")
    
    def test_change_history_404_for_invalid_network(self, headers):
        """Invalid network ID returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/invalid-network-id-123/change-history?limit=10",
            headers=headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestNotificationsAPI:
    """Test GET /api/v3/networks/{id}/notifications endpoint"""
    
    def test_get_notifications_returns_list(self, headers):
        """Notifications endpoint returns list"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/notifications?limit=50",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Notifications contains {len(data)} alerts")
    
    def test_notification_has_required_fields(self, headers):
        """Each notification has required fields for alerts panel"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/notifications?limit=10",
            headers=headers
        )
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 0:
            notif = data[0]
            
            # Required fields for alerts UI
            required_fields = [
                "id",
                "notification_type",  # For badge/label
                "title",              # Alert title
                "message",            # Alert message
                "read",               # Read/unread state
                "created_at",         # Timestamp
            ]
            
            for field in required_fields:
                assert field in notif, f"Missing required field: {field}"
            
            print(f"Notification {notif['id']} has all required fields")
            print(f"  - Type: {notif['notification_type']}")
            print(f"  - Title: {notif['title']}")
            print(f"  - Read: {notif['read']}")
    
    def test_notification_has_change_log_link(self, headers):
        """Notifications link to related change history entry"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/notifications?limit=10",
            headers=headers
        )
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 0:
            notif = data[0]
            # change_log_id links notification to change history
            assert "change_log_id" in notif, "Missing change_log_id field"
            print(f"Notification links to change log: {notif.get('change_log_id')}")
    
    def test_notification_has_affected_node(self, headers):
        """Notifications include affected node info"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/notifications?limit=10",
            headers=headers
        )
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 0:
            notif = data[0]
            assert "affected_node" in notif, "Missing affected_node field"
            print(f"Affected node: {notif.get('affected_node')}")


class TestMarkNotificationsReadAPI:
    """Test mark notifications read endpoints"""
    
    def test_mark_single_notification_read(self, headers):
        """POST /api/v3/networks/{id}/notifications/{notif_id}/read marks as read"""
        # First get notifications
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/notifications?limit=1",
            headers=headers
        )
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 0:
            notif_id = data[0]["id"]
            
            # Mark as read
            mark_response = requests.post(
                f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/notifications/{notif_id}/read",
                headers=headers
            )
            assert mark_response.status_code == 200, f"Failed: {mark_response.text}"
            print(f"Successfully marked notification {notif_id} as read")
    
    def test_mark_all_notifications_read(self, headers):
        """POST /api/v3/networks/{id}/notifications/read-all marks all as read"""
        response = requests.post(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/notifications/read-all",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "count" in data or "message" in data, "Response should have count or message"
        print(f"Mark all read response: {data}")


class TestChangeHistoryIntegration:
    """Integration tests for change history + notifications flow"""
    
    def test_network_detail_loads_with_history_tab(self, headers):
        """Network detail endpoint returns data needed for history tab"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}",
            headers=headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "entries" in data
        print(f"Network '{data['name']}' has {len(data.get('entries', []))} entries")
    
    def test_change_log_action_types_are_valid(self, headers):
        """Action types match expected values for UI badges"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/change-history?limit=20",
            headers=headers
        )
        assert response.status_code == 200
        
        data = response.json()
        valid_action_types = [
            "create_node", "update_node", "delete_node", 
            "relink_node", "change_role", "change_path"
        ]
        
        for log in data:
            action = log.get("action_type")
            assert action in valid_action_types, f"Unknown action type: {action}"
        
        action_counts = {}
        for log in data:
            action = log.get("action_type")
            action_counts[action] = action_counts.get(action, 0) + 1
        
        print(f"Action type distribution: {action_counts}")
    
    def test_notification_types_are_valid(self, headers):
        """Notification types match expected values for UI display"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/notifications?limit=20",
            headers=headers
        )
        assert response.status_code == 200
        
        data = response.json()
        valid_notif_types = [
            "main_domain_change", "node_deleted", "target_relinked",
            "orphan_detected", "seo_conflict", "high_tier_noindex"
        ]
        
        for notif in data:
            notif_type = notif.get("notification_type")
            assert notif_type in valid_notif_types, f"Unknown notification type: {notif_type}"
        
        type_counts = {}
        for notif in data:
            ntype = notif.get("notification_type")
            type_counts[ntype] = type_counts.get(ntype, 0) + 1
        
        print(f"Notification type distribution: {type_counts}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
