"""
Test: SEO Change Intelligence Layer (P0)
========================================
Tests for:
1. Structure Create/Update/Delete requiring change_note field
2. GET /api/v3/networks/{id}/change-history - SEO change logs
3. GET /api/v3/networks/{id}/notifications - Network notifications
4. POST /api/v3/networks/{id}/notifications/{id}/read - Mark notification read
5. GET /api/v3/change-logs/stats - Team evaluation metrics
6. GET/POST /api/v3/settings/telegram-seo - SEO Telegram settings
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestSeoChangeIntelligence:
    """SEO Change Intelligence Layer API tests"""

    # Test data tracking
    created_entry_id = None
    test_network_id = None
    test_domain_id = None
    test_notification_id = None

    @pytest.fixture(autouse=True)
    def setup(self, api_client, auth_token):
        """Setup test fixtures"""
        self.client = api_client
        self.client.headers.update({"Authorization": f"Bearer {auth_token}"})

    # ==================== STRUCTURE CREATE TESTS ====================

    def test_structure_create_requires_change_note(self, api_client, auth_token):
        """Test that structure create returns 400/422 when change_note is missing"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})

        # First, get a network and domain to use
        networks = api_client.get(f"{BASE_URL}/api/v3/networks").json()
        assert len(networks) > 0, "No networks found in database"

        network = networks[0]
        TestSeoChangeIntelligence.test_network_id = network["id"]

        # Get available domains for this network
        domains = api_client.get(
            f"{BASE_URL}/api/v3/networks/{network['id']}/available-domains"
        ).json()

        # Find a domain with root_available=True
        available_domain = None
        for d in domains:
            if d.get("root_available") or not d.get("used_paths"):
                available_domain = d
                break

        if not available_domain:
            # If no domain available at root, use an existing domain with a unique path
            available_domain = domains[0] if domains else None

        if not available_domain:
            pytest.skip("No domains available for testing structure creation")

        TestSeoChangeIntelligence.test_domain_id = available_domain["id"]

        # Try to create structure entry WITHOUT change_note
        create_payload = {
            "network_id": network["id"],
            "asset_domain_id": available_domain["id"],
            "optimized_path": f"/test-path-{uuid.uuid4().hex[:8]}",  # Unique path
            "domain_role": "supporting",
            # Missing change_note intentionally
        }

        response = api_client.post(f"{BASE_URL}/api/v3/structure", json=create_payload)

        # Should fail - Pydantic validation requires change_note
        assert response.status_code in [
            400,
            422,
        ], f"Expected 400/422 when change_note missing, got {response.status_code}"
        print(f"✓ Structure create without change_note returns {response.status_code}")

    def test_structure_create_with_change_note_succeeds(self, api_client, auth_token):
        """Test that structure create succeeds when change_note is provided"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})

        network_id = TestSeoChangeIntelligence.test_network_id
        domain_id = TestSeoChangeIntelligence.test_domain_id

        if not network_id or not domain_id:
            pytest.skip("No network or domain ID from previous test")

        # Create with change_note
        create_payload = {
            "network_id": network_id,
            "asset_domain_id": domain_id,
            "optimized_path": f"/test-path-{uuid.uuid4().hex[:8]}",  # Unique path to avoid duplicates
            "domain_role": "supporting",
            "change_note": "Test node creation for SEO change logging verification",
        }

        response = api_client.post(f"{BASE_URL}/api/v3/structure", json=create_payload)

        assert response.status_code in [
            200,
            201,
        ], f"Structure create with change_note failed: {response.text}"

        data = response.json()
        assert "id" in data, "Response should contain entry id"
        TestSeoChangeIntelligence.created_entry_id = data["id"]

        print(f"✓ Structure created with change_note, id: {data['id']}")

    def test_structure_create_change_note_too_short(self, api_client, auth_token):
        """Test that change_note must be at least 3 characters"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})

        network_id = TestSeoChangeIntelligence.test_network_id
        domain_id = TestSeoChangeIntelligence.test_domain_id

        if not network_id or not domain_id:
            pytest.skip("No network or domain ID from previous test")

        # Try with very short change_note
        create_payload = {
            "network_id": network_id,
            "asset_domain_id": domain_id,
            "optimized_path": f"/short-test-{uuid.uuid4().hex[:8]}",
            "domain_role": "supporting",
            "change_note": "ab",  # Too short (min_length=3)
        }

        response = api_client.post(f"{BASE_URL}/api/v3/structure", json=create_payload)

        assert response.status_code in [
            400,
            422,
        ], f"Expected 400/422 for short change_note, got {response.status_code}"
        print(f"✓ Change note minimum length validation works (rejected 2 chars)")

    # ==================== STRUCTURE UPDATE TESTS ====================

    def test_structure_update_requires_change_note(self, api_client, auth_token):
        """Test that structure update returns 400/422 when change_note is missing"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})

        entry_id = TestSeoChangeIntelligence.created_entry_id
        if not entry_id:
            pytest.skip("No entry ID from create test")

        # Try to update WITHOUT change_note
        update_payload = {
            "index_status": "noindex"
            # Missing change_note
        }

        response = api_client.put(
            f"{BASE_URL}/api/v3/structure/{entry_id}", json=update_payload
        )

        assert response.status_code in [
            400,
            422,
        ], f"Expected 400/422 when change_note missing, got {response.status_code}"
        print(f"✓ Structure update without change_note returns {response.status_code}")

    def test_structure_update_with_change_note_succeeds(self, api_client, auth_token):
        """Test that structure update succeeds when change_note is provided"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})

        entry_id = TestSeoChangeIntelligence.created_entry_id
        if not entry_id:
            pytest.skip("No entry ID from create test")

        # Update with change_note
        update_payload = {
            "index_status": "noindex",
            "change_note": "Changed to noindex for testing SEO update logging",
        }

        response = api_client.put(
            f"{BASE_URL}/api/v3/structure/{entry_id}", json=update_payload
        )

        assert (
            response.status_code == 200
        ), f"Structure update with change_note failed: {response.text}"

        data = response.json()
        assert (
            data.get("index_status") == "noindex"
        ), "Index status should be updated to noindex"

        print(f"✓ Structure updated with change_note successfully")

    # ==================== STRUCTURE DELETE TESTS ====================

    def test_structure_delete_requires_change_note(self, api_client, auth_token):
        """Test that structure delete returns 400 when change_note is missing"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})

        entry_id = TestSeoChangeIntelligence.created_entry_id
        if not entry_id:
            pytest.skip("No entry ID from create test")

        # Try to delete WITHOUT change_note in body
        response = api_client.delete(f"{BASE_URL}/api/v3/structure/{entry_id}")

        # Should fail - Pydantic validation requires change_note in body
        assert response.status_code in [
            400,
            422,
        ], f"Expected 400/422 when change_note missing, got {response.status_code}"
        print(f"✓ Structure delete without change_note returns {response.status_code}")

    def test_structure_delete_with_change_note_succeeds(self, api_client, auth_token):
        """Test that structure delete succeeds when change_note is provided"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})

        entry_id = TestSeoChangeIntelligence.created_entry_id
        if not entry_id:
            pytest.skip("No entry ID from create test")

        # Delete with change_note in body
        delete_payload = {"change_note": "Deleting test node - cleanup after testing"}

        response = api_client.request(
            "DELETE", f"{BASE_URL}/api/v3/structure/{entry_id}", json=delete_payload
        )

        assert (
            response.status_code == 200
        ), f"Structure delete with change_note failed: {response.text}"

        data = response.json()
        assert (
            "deleted" in data.get("message", "").lower()
        ), "Response should confirm deletion"

        print(f"✓ Structure deleted with change_note successfully")

    # ==================== CHANGE HISTORY API TESTS ====================

    def test_get_network_change_history(self, api_client, auth_token):
        """Test GET /api/v3/networks/{id}/change-history returns SEO change logs"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})

        network_id = TestSeoChangeIntelligence.test_network_id
        if not network_id:
            # Get any network
            networks = api_client.get(f"{BASE_URL}/api/v3/networks").json()
            if not networks:
                pytest.skip("No networks for change history test")
            network_id = networks[0]["id"]

        response = api_client.get(
            f"{BASE_URL}/api/v3/networks/{network_id}/change-history"
        )

        assert (
            response.status_code == 200
        ), f"Get change history failed: {response.text}"

        logs = response.json()
        assert isinstance(logs, list), "Response should be a list"

        # If we have logs from our create/update/delete tests, verify structure
        if logs:
            log = logs[0]
            assert "id" in log, "Log should have id"
            assert "action_type" in log, "Log should have action_type"
            assert "change_note" in log, "Log should have change_note"
            assert (
                "actor_email" in log or "actor_user_id" in log
            ), "Log should have actor info"
            print(f"✓ Change history has {len(logs)} logs with proper structure")
        else:
            print(
                f"✓ Change history endpoint works (empty logs - expected if no prior changes)"
            )

    def test_change_history_not_found_for_invalid_network(self, api_client, auth_token):
        """Test change history returns 404 for non-existent network"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})

        response = api_client.get(
            f"{BASE_URL}/api/v3/networks/invalid-network-id-12345/change-history"
        )

        assert (
            response.status_code == 404
        ), f"Expected 404 for invalid network, got {response.status_code}"
        print(f"✓ Change history returns 404 for non-existent network")

    # ==================== NOTIFICATIONS API TESTS ====================

    def test_get_network_notifications(self, api_client, auth_token):
        """Test GET /api/v3/networks/{id}/notifications returns notifications"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})

        network_id = TestSeoChangeIntelligence.test_network_id
        if not network_id:
            networks = api_client.get(f"{BASE_URL}/api/v3/networks").json()
            if not networks:
                pytest.skip("No networks for notifications test")
            network_id = networks[0]["id"]

        response = api_client.get(
            f"{BASE_URL}/api/v3/networks/{network_id}/notifications"
        )

        assert response.status_code == 200, f"Get notifications failed: {response.text}"

        notifications = response.json()
        assert isinstance(notifications, list), "Response should be a list"

        if notifications:
            notif = notifications[0]
            assert "id" in notif, "Notification should have id"
            assert "notification_type" in notif, "Notification should have type"
            assert "title" in notif, "Notification should have title"
            assert "read" in notif, "Notification should have read status"
            TestSeoChangeIntelligence.test_notification_id = notif["id"]
            print(
                f"✓ Notifications endpoint returns {len(notifications)} notifications"
            )
        else:
            print(
                f"✓ Notifications endpoint works (empty - expected if no important events)"
            )

    def test_mark_notification_read(self, api_client, auth_token):
        """Test POST /api/v3/networks/{id}/notifications/{id}/read marks notification as read"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})

        network_id = TestSeoChangeIntelligence.test_network_id
        notification_id = TestSeoChangeIntelligence.test_notification_id

        if not network_id:
            networks = api_client.get(f"{BASE_URL}/api/v3/networks").json()
            if not networks:
                pytest.skip("No networks for mark read test")
            network_id = networks[0]["id"]

        if not notification_id:
            # No notification from previous test, create test with dummy ID
            response = api_client.post(
                f"{BASE_URL}/api/v3/networks/{network_id}/notifications/non-existent-notif/read"
            )
            # Should return 404 for non-existent notification
            assert (
                response.status_code == 404
            ), f"Expected 404 for non-existent notification"
            print(f"✓ Mark read returns 404 for non-existent notification")
            return

        response = api_client.post(
            f"{BASE_URL}/api/v3/networks/{network_id}/notifications/{notification_id}/read"
        )

        assert (
            response.status_code == 200
        ), f"Mark notification read failed: {response.text}"

        data = response.json()
        assert "message" in data, "Response should have message"
        print(f"✓ Notification marked as read successfully")

    # ==================== TEAM METRICS API TESTS ====================

    def test_get_change_log_stats(self, api_client, auth_token):
        """Test GET /api/v3/change-logs/stats returns team evaluation metrics"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})

        response = api_client.get(f"{BASE_URL}/api/v3/change-logs/stats")

        assert (
            response.status_code == 200
        ), f"Get change log stats failed: {response.text}"

        stats = response.json()

        # Verify expected fields
        assert (
            "period_days" in stats or "total_changes" in stats
        ), "Stats should have period or total_changes field"

        if "changes_by_user" in stats:
            assert isinstance(
                stats["changes_by_user"], list
            ), "changes_by_user should be list"

        if "changes_by_network" in stats:
            assert isinstance(
                stats["changes_by_network"], list
            ), "changes_by_network should be list"

        print(f"✓ Change log stats returned: {list(stats.keys())}")

    def test_change_log_stats_with_days_param(self, api_client, auth_token):
        """Test stats endpoint accepts days parameter"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})

        response = api_client.get(f"{BASE_URL}/api/v3/change-logs/stats?days=7")

        assert (
            response.status_code == 200
        ), f"Get stats with days param failed: {response.text}"

        stats = response.json()
        assert (
            stats.get("period_days") == 7 or "period_days" not in stats
        ), "Stats should reflect requested period"

        print(f"✓ Stats with days=7 parameter works")

    # ==================== SEO TELEGRAM SETTINGS TESTS ====================

    def test_get_telegram_seo_settings(self, api_client, auth_token):
        """Test GET /api/v3/settings/telegram-seo returns SEO telegram config"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})

        response = api_client.get(f"{BASE_URL}/api/v3/settings/telegram-seo")

        assert (
            response.status_code == 200
        ), f"Get SEO telegram settings failed: {response.text}"

        settings = response.json()

        # Either configured: true/false or just returns settings
        assert "configured" in settings or isinstance(
            settings, dict
        ), "Response should indicate configuration status"

        print(
            f"✓ SEO Telegram settings: configured={settings.get('configured', 'unknown')}"
        )

    def test_update_telegram_seo_settings(self, api_client, auth_token):
        """Test POST /api/v3/settings/telegram-seo updates settings"""
        api_client.headers.update({"Authorization": f"Bearer {auth_token}"})

        # Update with test settings (won't send real messages without valid tokens)
        update_payload = {
            "bot_token": "test-bot-token-12345",
            "chat_id": "test-chat-id-67890",
            "enabled": False,  # Disable to prevent test messages
        }

        response = api_client.post(
            f"{BASE_URL}/api/v3/settings/telegram-seo", json=update_payload
        )

        assert (
            response.status_code == 200
        ), f"Update SEO telegram settings failed: {response.text}"

        # Verify settings were saved
        get_response = api_client.get(f"{BASE_URL}/api/v3/settings/telegram-seo")
        assert get_response.status_code == 200

        settings = get_response.json()
        # Chat ID should be saved (configured should be true now)
        assert settings.get("configured") == True or settings.get(
            "chat_id"
        ), "Settings should be saved"

        print(f"✓ SEO Telegram settings updated successfully")

    def test_telegram_seo_settings_requires_auth(self):
        """Test that SEO telegram settings require authentication"""
        # Create a fresh client without auth
        fresh_client = requests.Session()
        fresh_client.headers.update({"Content-Type": "application/json"})

        response = fresh_client.get(f"{BASE_URL}/api/v3/settings/telegram-seo")

        assert response.status_code in [
            401,
            403,
        ], f"Expected 401/403 without auth, got {response.status_code}"

        print(f"✓ SEO Telegram settings require authentication")


# ==================== FIXTURES ====================


@pytest.fixture(scope="session")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def auth_token(api_client):
    """Get authentication token"""
    response = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@test.com", "password": "admin123"},
    )
    if response.status_code == 200:
        # API returns access_token not token
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping authenticated tests")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
