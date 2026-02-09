"""
Test suite for Change Note UX, Main Node Logic, and Switch Main Target features
Tests the three major features from the latest implementation.
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestChangeNoteMainNodeSwitch:
    """Tests for Change Note, Main Node Validation, and Switch Main Target"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test - get auth token"""
        self.auth_token = self._get_auth_token()
        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }
        
    def _get_auth_token(self):
        """Get auth token for admin user"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "admin123"}
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip(f"Auth failed: {response.status_code}")
    
    # ===== MAIN NODE VALIDATION TESTS =====
    
    def test_main_node_validation_no_target_entry_id(self):
        """Main nodes MUST NOT have target_entry_id"""
        # First get a network with an existing main node
        networks_resp = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)
        assert networks_resp.status_code == 200, f"Failed to get networks: {networks_resp.text}"
        
        networks = networks_resp.json()
        if not networks:
            pytest.skip("No networks available for testing")
        
        # Get network details with entries
        network = networks[0]
        network_resp = requests.get(f"{BASE_URL}/api/v3/networks/{network['id']}", headers=self.headers)
        assert network_resp.status_code == 200
        network_data = network_resp.json()
        
        # Find any non-main entry to use as a target
        entries = network_data.get('entries', [])
        if len(entries) < 2:
            pytest.skip("Need at least 2 entries to test target validation")
        
        supporting_entry = next((e for e in entries if e['domain_role'] != 'main'), None)
        if not supporting_entry:
            pytest.skip("No supporting entry found")
        
        # Get available domains
        avail_resp = requests.get(
            f"{BASE_URL}/api/v3/networks/{network['id']}/available-domains",
            headers=self.headers
        )
        if avail_resp.status_code != 200 or not avail_resp.json():
            pytest.skip("No available domains for testing")
        
        avail_domains = [d for d in avail_resp.json() if d.get('root_available')]
        if not avail_domains:
            pytest.skip("No available root domains for testing")
        
        # Try to create a main node with target_entry_id - should fail
        create_resp = requests.post(
            f"{BASE_URL}/api/v3/structure",
            headers=self.headers,
            json={
                "asset_domain_id": avail_domains[0]['id'],
                "network_id": network['id'],
                "domain_role": "main",
                "domain_status": "primary",
                "target_entry_id": supporting_entry['id'],  # This should fail
                "change_note": "Test main node with target should fail"
            }
        )
        
        assert create_resp.status_code == 400, f"Should reject main with target_entry_id: {create_resp.text}"
        error = create_resp.json()
        assert "target" in error.get('detail', '').lower() or "main" in error.get('detail', '').lower(), \
            f"Error should mention target or main: {error}"
        print("✓ Main node correctly rejects target_entry_id")
    
    def test_main_node_validation_rejects_canonical_status(self):
        """Main nodes MUST have PRIMARY status, not canonical/redirect"""
        networks_resp = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)
        assert networks_resp.status_code == 200
        
        networks = networks_resp.json()
        if not networks:
            pytest.skip("No networks available")
        
        network = networks[0]
        
        # Get available domains
        avail_resp = requests.get(
            f"{BASE_URL}/api/v3/networks/{network['id']}/available-domains",
            headers=self.headers
        )
        if avail_resp.status_code != 200 or not avail_resp.json():
            pytest.skip("No available domains")
        
        avail_domains = [d for d in avail_resp.json() if d.get('root_available')]
        if not avail_domains:
            pytest.skip("No available root domains")
        
        # Try to create a main node with canonical status - should fail
        create_resp = requests.post(
            f"{BASE_URL}/api/v3/structure",
            headers=self.headers,
            json={
                "asset_domain_id": avail_domains[0]['id'],
                "network_id": network['id'],
                "domain_role": "main",
                "domain_status": "canonical",  # Should fail - main needs primary
                "change_note": "Test main node with canonical should fail"
            }
        )
        
        assert create_resp.status_code == 400, f"Should reject main with canonical: {create_resp.text}"
        error = create_resp.json()
        assert "primary" in error.get('detail', '').lower() or "main" in error.get('detail', '').lower(), \
            f"Error should mention primary status: {error}"
        print("✓ Main node correctly rejects canonical status")
    
    def test_main_node_validation_rejects_redirect_status(self):
        """Main nodes MUST NOT have redirect status"""
        networks_resp = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)
        assert networks_resp.status_code == 200
        
        networks = networks_resp.json()
        if not networks:
            pytest.skip("No networks available")
        
        network = networks[0]
        
        avail_resp = requests.get(
            f"{BASE_URL}/api/v3/networks/{network['id']}/available-domains",
            headers=self.headers
        )
        if avail_resp.status_code != 200 or not avail_resp.json():
            pytest.skip("No available domains")
        
        avail_domains = [d for d in avail_resp.json() if d.get('root_available')]
        if not avail_domains:
            pytest.skip("No available root domains")
        
        # Try to create a main node with 301_redirect status - should fail
        create_resp = requests.post(
            f"{BASE_URL}/api/v3/structure",
            headers=self.headers,
            json={
                "asset_domain_id": avail_domains[0]['id'],
                "network_id": network['id'],
                "domain_role": "main",
                "domain_status": "301_redirect",  # Should fail
                "change_note": "Test main node with 301 redirect should fail"
            }
        )
        
        assert create_resp.status_code == 400, f"Should reject main with redirect: {create_resp.text}"
        print("✓ Main node correctly rejects redirect status")
    
    # ===== SWITCH MAIN TARGET TESTS =====
    
    def test_switch_main_target_api_exists(self):
        """Switch Main Target endpoint exists"""
        networks_resp = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)
        assert networks_resp.status_code == 200
        
        networks = networks_resp.json()
        if not networks:
            pytest.skip("No networks available")
        
        network = networks[0]
        
        # Verify endpoint exists (even with invalid payload)
        resp = requests.post(
            f"{BASE_URL}/api/v3/networks/{network['id']}/switch-main-target",
            headers=self.headers,
            json={
                "new_main_entry_id": "invalid-id",
                "change_note": "Test endpoint exists"
            }
        )
        
        # Should return 404 (entry not found) or 400 (validation error), not 405 (method not allowed)
        assert resp.status_code in [400, 404], f"Switch endpoint should exist: {resp.status_code} {resp.text}"
        print("✓ Switch Main Target endpoint exists")
    
    def test_switch_main_target_validates_change_note(self):
        """Switch Main Target requires change_note"""
        networks_resp = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)
        assert networks_resp.status_code == 200
        
        networks = networks_resp.json()
        if not networks:
            pytest.skip("No networks available")
        
        network = networks[0]
        network_detail = requests.get(
            f"{BASE_URL}/api/v3/networks/{network['id']}",
            headers=self.headers
        ).json()
        
        entries = network_detail.get('entries', [])
        supporting_entry = next((e for e in entries if e['domain_role'] != 'main'), None)
        if not supporting_entry:
            pytest.skip("No supporting entry to promote")
        
        # Try without change_note
        resp = requests.post(
            f"{BASE_URL}/api/v3/networks/{network['id']}/switch-main-target",
            headers=self.headers,
            json={
                "new_main_entry_id": supporting_entry['id']
                # Missing change_note
            }
        )
        
        assert resp.status_code == 422, f"Should require change_note: {resp.status_code}"
        print("✓ Switch Main Target validates change_note is required")
    
    def test_switch_main_target_validates_min_chars(self):
        """Switch Main Target requires minimum 3 chars in change_note"""
        networks_resp = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)
        assert networks_resp.status_code == 200
        
        networks = networks_resp.json()
        if not networks:
            pytest.skip("No networks available")
        
        network = networks[0]
        network_detail = requests.get(
            f"{BASE_URL}/api/v3/networks/{network['id']}",
            headers=self.headers
        ).json()
        
        entries = network_detail.get('entries', [])
        supporting_entry = next((e for e in entries if e['domain_role'] != 'main'), None)
        if not supporting_entry:
            pytest.skip("No supporting entry to promote")
        
        # Try with too short change_note
        resp = requests.post(
            f"{BASE_URL}/api/v3/networks/{network['id']}/switch-main-target",
            headers=self.headers,
            json={
                "new_main_entry_id": supporting_entry['id'],
                "change_note": "ab"  # Too short
            }
        )
        
        assert resp.status_code == 422, f"Should reject short change_note: {resp.status_code}"
        print("✓ Switch Main Target validates min 3 chars")
    
    def test_switch_main_target_success_verifies_tier_recalculation(self):
        """Switch Main Target successfully swaps roles and recalculates tiers"""
        # Get TESTER2 network specifically as it was used in prior tests
        networks_resp = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)
        assert networks_resp.status_code == 200
        
        networks = networks_resp.json()
        test_network = next((n for n in networks if 'TESTER' in n.get('name', '')), None)
        if not test_network:
            pytest.skip("No TESTER network available")
        
        network_detail = requests.get(
            f"{BASE_URL}/api/v3/networks/{test_network['id']}",
            headers=self.headers
        ).json()
        
        entries = network_detail.get('entries', [])
        main_entry = next((e for e in entries if e['domain_role'] == 'main'), None)
        supporting_entry = next((e for e in entries if e['domain_role'] != 'main'), None)
        
        if not main_entry or not supporting_entry:
            pytest.skip("Need both main and supporting entries")
        
        # Record current state
        old_main_id = main_entry['id']
        new_main_id = supporting_entry['id']
        
        # Perform switch
        resp = requests.post(
            f"{BASE_URL}/api/v3/networks/{test_network['id']}/switch-main-target",
            headers=self.headers,
            json={
                "new_main_entry_id": new_main_id,
                "change_note": "Testing Switch Main Target for tier recalculation verification"
            }
        )
        
        assert resp.status_code == 200, f"Switch failed: {resp.status_code} {resp.text}"
        result = resp.json()
        
        # Verify response
        assert result.get('new_main_entry_id') == new_main_id
        assert result.get('previous_main_entry_id') == old_main_id
        assert result.get('tiers_recalculated') == True
        
        # Verify state change
        updated_network = requests.get(
            f"{BASE_URL}/api/v3/networks/{test_network['id']}",
            headers=self.headers
        ).json()
        
        updated_entries = updated_network.get('entries', [])
        
        # New main should have main role, primary status, no target
        new_main = next((e for e in updated_entries if e['id'] == new_main_id), None)
        assert new_main is not None
        assert new_main['domain_role'] == 'main', f"New main should have main role: {new_main['domain_role']}"
        assert new_main['domain_status'] == 'primary', f"New main should have primary status: {new_main['domain_status']}"
        assert new_main.get('target_entry_id') is None, f"New main should have no target"
        
        # Old main should be supporting, canonical, targeting new main
        old_main = next((e for e in updated_entries if e['id'] == old_main_id), None)
        assert old_main is not None
        assert old_main['domain_role'] == 'supporting', f"Old main should be supporting: {old_main['domain_role']}"
        assert old_main['domain_status'] == 'canonical', f"Old main should be canonical: {old_main['domain_status']}"
        assert old_main.get('target_entry_id') == new_main_id, f"Old main should target new main"
        
        # Verify tier recalculation - new main should be tier 0
        assert new_main.get('calculated_tier') == 0, f"New main should be tier 0: {new_main.get('calculated_tier')}"
        
        print("✓ Switch Main Target success: roles swapped, tiers recalculated")
        
        # Switch back for idempotency
        requests.post(
            f"{BASE_URL}/api/v3/networks/{test_network['id']}/switch-main-target",
            headers=self.headers,
            json={
                "new_main_entry_id": old_main_id,
                "change_note": "Reverting switch for test cleanup"
            }
        )
    
    # ===== CHANGE NOTE UX TESTS (API level) =====
    
    def test_change_note_max_length_2000(self):
        """Change note accepts up to 2000 characters"""
        networks_resp = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)
        assert networks_resp.status_code == 200
        
        networks = networks_resp.json()
        if not networks:
            pytest.skip("No networks available")
        
        network = networks[0]
        network_detail = requests.get(
            f"{BASE_URL}/api/v3/networks/{network['id']}",
            headers=self.headers
        ).json()
        
        entries = network_detail.get('entries', [])
        if not entries:
            pytest.skip("No entries to update")
        
        entry = entries[0]
        
        # Create a 2000 character note
        long_note = "A" * 2000
        
        resp = requests.put(
            f"{BASE_URL}/api/v3/structure/{entry['id']}",
            headers=self.headers,
            json={
                "notes": entry.get('notes', '') + " (test)",
                "change_note": long_note
            }
        )
        
        # Should accept 2000 chars
        assert resp.status_code == 200, f"Should accept 2000 char note: {resp.status_code}"
        print("✓ Change note accepts 2000 characters")
    
    def test_change_note_rejects_over_2000(self):
        """Change note rejects over 2000 characters"""
        networks_resp = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)
        assert networks_resp.status_code == 200
        
        networks = networks_resp.json()
        if not networks:
            pytest.skip("No networks available")
        
        network = networks[0]
        network_detail = requests.get(
            f"{BASE_URL}/api/v3/networks/{network['id']}",
            headers=self.headers
        ).json()
        
        entries = network_detail.get('entries', [])
        if not entries:
            pytest.skip("No entries to update")
        
        entry = entries[0]
        
        # Create a 2001 character note
        too_long_note = "B" * 2001
        
        resp = requests.put(
            f"{BASE_URL}/api/v3/structure/{entry['id']}",
            headers=self.headers,
            json={
                "notes": entry.get('notes', '') + " (test2)",
                "change_note": too_long_note
            }
        )
        
        # Should reject > 2000 chars
        assert resp.status_code == 422, f"Should reject > 2000 char note: {resp.status_code}"
        print("✓ Change note rejects over 2000 characters")
    
    def test_structure_create_requires_change_note(self):
        """Creating structure entry requires change_note"""
        networks_resp = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)
        assert networks_resp.status_code == 200
        
        networks = networks_resp.json()
        if not networks:
            pytest.skip("No networks available")
        
        network = networks[0]
        
        avail_resp = requests.get(
            f"{BASE_URL}/api/v3/networks/{network['id']}/available-domains",
            headers=self.headers
        )
        if avail_resp.status_code != 200 or not avail_resp.json():
            pytest.skip("No available domains")
        
        avail_domains = [d for d in avail_resp.json() if d.get('root_available')]
        if not avail_domains:
            pytest.skip("No available root domains")
        
        # Try to create without change_note
        resp = requests.post(
            f"{BASE_URL}/api/v3/structure",
            headers=self.headers,
            json={
                "asset_domain_id": avail_domains[0]['id'],
                "network_id": network['id'],
                "domain_role": "supporting",
                "domain_status": "canonical"
                # Missing change_note
            }
        )
        
        assert resp.status_code == 422, f"Should require change_note: {resp.status_code}"
        print("✓ Structure create requires change_note")
    
    def test_structure_update_requires_change_note(self):
        """Updating structure entry requires change_note"""
        networks_resp = requests.get(f"{BASE_URL}/api/v3/networks", headers=self.headers)
        assert networks_resp.status_code == 200
        
        networks = networks_resp.json()
        if not networks:
            pytest.skip("No networks available")
        
        network = networks[0]
        network_detail = requests.get(
            f"{BASE_URL}/api/v3/networks/{network['id']}",
            headers=self.headers
        ).json()
        
        entries = network_detail.get('entries', [])
        if not entries:
            pytest.skip("No entries to update")
        
        entry = entries[0]
        
        # Try to update without change_note
        resp = requests.put(
            f"{BASE_URL}/api/v3/structure/{entry['id']}",
            headers=self.headers,
            json={
                "notes": "Updated note"
                # Missing change_note
            }
        )
        
        assert resp.status_code == 422, f"Should require change_note: {resp.status_code}"
        print("✓ Structure update requires change_note")


class TestMainNodeStatuses:
    """Test MAIN_NODE_ALLOWED_STATUSES validation"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup auth"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "admin123"}
        )
        if response.status_code == 200:
            self.auth_token = response.json().get("access_token")
            self.headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json"
            }
        else:
            pytest.skip("Auth failed")
    
    def test_models_define_main_node_allowed_statuses(self):
        """Verify MAIN_NODE_ALLOWED_STATUSES includes only PRIMARY"""
        # Import from models to verify definition
        import sys
        sys.path.insert(0, '/app/backend')
        from models_v3 import MAIN_NODE_ALLOWED_STATUSES, SeoStatus
        
        assert SeoStatus.PRIMARY in MAIN_NODE_ALLOWED_STATUSES
        assert len(MAIN_NODE_ALLOWED_STATUSES) == 1, "Main nodes should only allow PRIMARY"
        print("✓ MAIN_NODE_ALLOWED_STATUSES correctly defined as [PRIMARY]")
    
    def test_models_define_supporting_node_statuses(self):
        """Verify SUPPORTING_NODE_ALLOWED_STATUSES includes canonical/redirect"""
        import sys
        sys.path.insert(0, '/app/backend')
        from models_v3 import SUPPORTING_NODE_ALLOWED_STATUSES, SeoStatus
        
        assert SeoStatus.CANONICAL in SUPPORTING_NODE_ALLOWED_STATUSES
        assert SeoStatus.REDIRECT_301 in SUPPORTING_NODE_ALLOWED_STATUSES
        assert SeoStatus.REDIRECT_302 in SUPPORTING_NODE_ALLOWED_STATUSES
        assert SeoStatus.RESTORE in SUPPORTING_NODE_ALLOWED_STATUSES
        assert SeoStatus.PRIMARY not in SUPPORTING_NODE_ALLOWED_STATUSES
        print("✓ SUPPORTING_NODE_ALLOWED_STATUSES correctly defined")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
