"""
SEO Telegram Notification System Tests
======================================
Tests for iteration 15 - SEO Change Notification via Telegram

Features tested:
- SEO Telegram settings API (GET/PUT)
- Test notification API
- Change note minimum 10 character validation
- Structure entry create/update/delete with change notes
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://domain-oversight.preview.emergentagent.com"

# Test credentials
TEST_EMAIL = "admin@test.com"
TEST_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("access_token")


@pytest.fixture
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestSeoTelegramSettings:
    """Tests for SEO Telegram settings endpoints"""

    def test_get_seo_telegram_settings(self, auth_headers):
        """GET /api/v3/settings/telegram-seo returns settings"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-seo", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # Should have configured flag and enabled flag
        assert "configured" in data or "enabled" in data
        print(f"✓ SEO Telegram settings: {data}")

    def test_update_seo_telegram_settings_enable(self, auth_headers):
        """PUT /api/v3/settings/telegram-seo can enable notifications"""
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-seo",
            headers=auth_headers,
            json={"enabled": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"✓ Enable SEO notifications: {data}")

    def test_update_seo_telegram_settings_disable(self, auth_headers):
        """PUT /api/v3/settings/telegram-seo can disable notifications"""
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-seo",
            headers=auth_headers,
            json={"enabled": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

        # Re-enable for other tests
        requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-seo",
            headers=auth_headers,
            json={"enabled": True},
        )
        print(f"✓ Disable/re-enable SEO notifications: {data}")

    def test_seo_telegram_test_notification(self, auth_headers):
        """POST /api/v3/settings/telegram-seo/test sends test message"""
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/telegram-seo/test", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert (
            "success" in data["message"].lower()
            or "berhasil" in data["message"].lower()
        )
        print(f"✓ Test notification sent: {data}")


class TestChangeNoteValidation:
    """Tests for change_note minimum 10 character validation"""

    def test_create_structure_entry_note_too_short(self, auth_headers):
        """POST /api/v3/structure rejects change_note < 10 chars"""
        # First get a valid network and asset domain
        networks = requests.get(
            f"{BASE_URL}/api/v3/networks", headers=auth_headers
        ).json()

        if not networks:
            pytest.skip("No networks available for testing")

        network = networks[0]

        # Get asset domains
        assets = requests.get(
            f"{BASE_URL}/api/v3/asset-domains", headers=auth_headers
        ).json()

        if not assets:
            pytest.skip("No asset domains available for testing")

        # Find an asset from same brand as network
        suitable_asset = None
        for asset in assets:
            if asset.get("brand_id") == network.get("brand_id"):
                suitable_asset = asset
                break

        if not suitable_asset:
            pytest.skip("No suitable asset domain for testing")

        # Get existing entry to use as target
        entries = requests.get(
            f"{BASE_URL}/api/v3/structure?network_id={network['id']}",
            headers=auth_headers,
        ).json()

        target_entry_id = entries[0]["id"] if entries else None

        # Try to create with short change_note (< 10 chars)
        response = requests.post(
            f"{BASE_URL}/api/v3/structure",
            headers=auth_headers,
            json={
                "asset_domain_id": suitable_asset["id"],
                "network_id": network["id"],
                "domain_role": "supporting",
                "domain_status": "canonical",
                "target_entry_id": target_entry_id,
                "change_note": "short",  # Only 5 chars, should fail
            },
        )

        # Backend should reject with 422 (validation error)
        assert (
            response.status_code == 422
        ), f"Expected 422 for short change_note, got {response.status_code}: {response.text}"
        print(f"✓ Short change_note rejected (422): {response.json()}")

    def test_delete_structure_entry_note_too_short(self, auth_headers):
        """DELETE /api/v3/structure/{id} rejects change_note < 10 chars"""
        # Get an existing entry
        networks = requests.get(
            f"{BASE_URL}/api/v3/networks", headers=auth_headers
        ).json()

        if not networks:
            pytest.skip("No networks available for testing")

        entries = requests.get(
            f"{BASE_URL}/api/v3/structure?network_id={networks[0]['id']}",
            headers=auth_headers,
        ).json()

        if not entries or len(entries) < 2:
            pytest.skip("Not enough entries for delete test")

        # Find a supporting entry (not main)
        supporting_entry = None
        for entry in entries:
            if entry.get("domain_role") != "main":
                supporting_entry = entry
                break

        if not supporting_entry:
            pytest.skip("No supporting entry available for delete test")

        # Try to delete with short change_note
        response = requests.delete(
            f"{BASE_URL}/api/v3/structure/{supporting_entry['id']}",
            headers=auth_headers,
            json={"change_note": "del"},  # Only 3 chars, should fail
        )

        # Should be rejected
        assert (
            response.status_code == 422 or response.status_code == 400
        ), f"Expected 422/400 for short delete note, got {response.status_code}: {response.text}"
        print(f"✓ Short delete change_note rejected: {response.status_code}")

    def test_switch_main_target_note_too_short(self, auth_headers):
        """POST /api/v3/networks/{id}/switch-main-target rejects short note"""
        networks = requests.get(
            f"{BASE_URL}/api/v3/networks", headers=auth_headers
        ).json()

        if not networks:
            pytest.skip("No networks available for testing")

        entries = requests.get(
            f"{BASE_URL}/api/v3/structure?network_id={networks[0]['id']}",
            headers=auth_headers,
        ).json()

        if not entries or len(entries) < 2:
            pytest.skip("Not enough entries for switch main test")

        # Find a supporting entry to try promoting
        supporting_entry = None
        for entry in entries:
            if entry.get("domain_role") != "main":
                supporting_entry = entry
                break

        if not supporting_entry:
            pytest.skip("No supporting entry available for switch main test")

        # Try to switch main with short change_note
        response = requests.post(
            f"{BASE_URL}/api/v3/networks/{networks[0]['id']}/switch-main-target",
            headers=auth_headers,
            json={
                "new_main_entry_id": supporting_entry["id"],
                "change_note": "switch",  # Only 6 chars, should fail (needs 10)
            },
        )

        # Should be rejected
        assert (
            response.status_code == 422
        ), f"Expected 422 for short switch-main note, got {response.status_code}: {response.text}"
        print(f"✓ Short switch-main change_note rejected (422)")


class TestChangeNoteSuccess:
    """Tests for successful operations with valid change notes"""

    def test_create_and_delete_with_valid_note(self, auth_headers):
        """Full flow: create node with valid change_note, then delete"""
        # Get network and domain
        networks = requests.get(
            f"{BASE_URL}/api/v3/networks", headers=auth_headers
        ).json()

        if not networks:
            pytest.skip("No networks available")

        network = networks[0]

        # Get entries for target
        entries = requests.get(
            f"{BASE_URL}/api/v3/structure?network_id={network['id']}",
            headers=auth_headers,
        ).json()

        if not entries:
            pytest.skip("No entries in network")

        main_entry = None
        for entry in entries:
            if entry.get("domain_role") == "main":
                main_entry = entry
                break

        if not main_entry:
            main_entry = entries[0]

        # Get suitable asset
        assets = requests.get(
            f"{BASE_URL}/api/v3/asset-domains?brand_id={network.get('brand_id')}",
            headers=auth_headers,
        ).json()

        if not assets:
            pytest.skip("No asset domains for this brand")

        # Use an asset not already in the network
        used_asset_ids = {e.get("asset_domain_id") for e in entries}
        available_asset = None
        for asset in assets:
            if asset["id"] not in used_asset_ids:
                available_asset = asset
                break

        if not available_asset:
            pytest.skip("No available asset domain for test")

        # Create with valid change_note (>= 10 chars)
        create_response = requests.post(
            f"{BASE_URL}/api/v3/structure",
            headers=auth_headers,
            json={
                "asset_domain_id": available_asset["id"],
                "network_id": network["id"],
                "domain_role": "supporting",
                "domain_status": "canonical",
                "target_entry_id": main_entry["id"],
                "change_note": "Test node creation for SEO telegram notification testing - valid note",
            },
        )

        assert (
            create_response.status_code == 200
        ), f"Create failed: {create_response.text}"
        created_entry = create_response.json()
        print(f"✓ Created entry with valid change_note: {created_entry['id']}")

        # Now delete with valid change_note
        delete_response = requests.delete(
            f"{BASE_URL}/api/v3/structure/{created_entry['id']}",
            headers=auth_headers,
            json={
                "change_note": "Cleanup test entry - removing test node after validation"
            },
        )

        assert (
            delete_response.status_code == 200
        ), f"Delete failed: {delete_response.text}"
        print(f"✓ Deleted entry with valid change_note")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
