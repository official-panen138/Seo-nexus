"""
P0 Bug Fix Tests: Node-to-Node Linking
======================================
Tests the critical bug fix for node-to-node linking in the UI and graph visualization.

Key features tested:
1. V3 Networks API returns node_label and entry.id
2. Available targets API returns nodes with node_label
3. Target Node dropdown populated from structure entries (not domains)
4. Tier calculation works correctly (main = 0, supporting = higher)
5. Orphan detection works correctly
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test network from context
TEST_NETWORK_ID = "a8ea05d6-6d3a-4a5d-86c6-5d9c0be8dc21"
MAIN_ENTRY_ID = "210a8a26-a296-42bc-b1c0-afeaf6b43299"
SUPPORTING_ENTRY_ID = "b8bbeef6-ec17-4565-896f-97811340d5e0"


class TestAuthentication:
    """Test authentication with provided credentials"""
    
    def test_login_success(self):
        """Test login with admin@test.com / admin123"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@test.com", "password": "admin123"}
        )
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        assert "access_token" in data, "Missing access_token in response"
        assert data["user"]["email"] == "admin@test.com"
        assert data["user"]["role"] == "super_admin"
        print(f"Login SUCCESS: Got token for {data['user']['email']}")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@test.com", "password": "admin123"}
    )
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.text}")
    return response.json().get("access_token")


@pytest.fixture
def api_client(auth_token):
    """Authenticated API client"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestV3NetworksAPINodeLabel:
    """Test that V3 Networks API returns correct structure with node_label and entry.id"""
    
    def test_network_returns_entries_with_node_label(self, api_client):
        """V3 Networks API returns entries with node_label"""
        response = api_client.get(f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}")
        
        assert response.status_code == 200, f"API failed: {response.text}"
        data = response.json()
        
        assert "entries" in data, "Missing entries in network response"
        assert len(data["entries"]) >= 2, "Expected at least 2 entries"
        
        for entry in data["entries"]:
            assert "id" in entry, "Missing id in entry"
            assert "node_label" in entry, "Missing node_label in entry"
            assert "domain_name" in entry, "Missing domain_name in entry"
            assert entry["node_label"], "node_label should not be empty"
            print(f"Entry: {entry['node_label']} (id: {entry['id']})")
    
    def test_network_entries_have_tier_info(self, api_client):
        """V3 entries have calculated_tier and tier_label"""
        response = api_client.get(f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        for entry in data["entries"]:
            assert "calculated_tier" in entry, f"Missing calculated_tier in entry {entry['id']}"
            assert "tier_label" in entry, f"Missing tier_label in entry {entry['id']}"
            assert entry["calculated_tier"] is not None, "calculated_tier should not be None"
            print(f"{entry['node_label']}: {entry['tier_label']} (tier {entry['calculated_tier']})")


class TestAvailableTargetsAPI:
    """Test available targets API returns nodes with node_label"""
    
    def test_available_targets_returns_nodes(self, api_client):
        """Available targets API returns nodes from structure entries"""
        response = api_client.get(f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/available-targets")
        
        assert response.status_code == 200, f"API failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Expected list of available targets"
        assert len(data) >= 1, "Expected at least 1 available target"
        
        for target in data:
            assert "id" in target, "Missing id in target"
            assert "node_label" in target, "Missing node_label in target"
            assert "domain_name" in target, "Missing domain_name in target"
            assert "domain_role" in target, "Missing domain_role in target"
            print(f"Available target: {target['node_label']} (id: {target['id']}, role: {target['domain_role']})")
    
    def test_available_targets_excludes_self(self, api_client):
        """Available targets API excludes the current entry"""
        response = api_client.get(
            f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/available-targets",
            params={"exclude_entry_id": SUPPORTING_ENTRY_ID}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # The excluded entry should not be in results
        ids = [t["id"] for t in data]
        assert SUPPORTING_ENTRY_ID not in ids, "Excluded entry should not be in results"
        
        # Main entry should still be available
        assert any(t["id"] == MAIN_ENTRY_ID for t in data), "Main entry should be available"
        print("Excludes self: PASS")
    
    def test_available_targets_has_correct_structure(self, api_client):
        """Targets have entry.id as value and node_label for display"""
        response = api_client.get(f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/available-targets")
        
        assert response.status_code == 200
        data = response.json()
        
        for target in data:
            # ID should be entry.id (UUID format)
            assert len(target["id"]) == 36, f"ID should be UUID: {target['id']}"
            # node_label should be displayable
            assert target["node_label"], "node_label should be displayable"
            print(f"Target dropdown: value={target['id'][:8]}..., label={target['node_label']}")


class TestTierCalculation:
    """Test tier calculation for nodes"""
    
    def test_main_node_is_tier_0(self, api_client):
        """Main node (LP/Money Site) should be tier 0"""
        response = api_client.get(f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        main_entries = [e for e in data["entries"] if e["domain_role"] == "main"]
        assert len(main_entries) >= 1, "Should have at least one main entry"
        
        for main in main_entries:
            assert main["calculated_tier"] == 0, f"Main node should be tier 0, got {main['calculated_tier']}"
            assert main["tier_label"] == "LP/Money Site", f"Main should be LP/Money Site, got {main['tier_label']}"
            print(f"Main node {main['node_label']}: tier={main['calculated_tier']} ({main['tier_label']})")
    
    def test_supporting_node_is_higher_tier(self, api_client):
        """Supporting node should be tier 1 or higher"""
        response = api_client.get(f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        supporting_entries = [e for e in data["entries"] if e["domain_role"] == "supporting"]
        
        for entry in supporting_entries:
            # Supporting nodes should have tier >= 1
            assert entry["calculated_tier"] >= 1, f"Supporting should be tier >= 1, got {entry['calculated_tier']}"
            
            # If it has a target, it should be calculated from the target
            if entry.get("target_entry_id"):
                print(f"Supporting {entry['node_label']}: tier={entry['calculated_tier']} targets={entry.get('target_domain_name')}")
            else:
                # Orphan (no target) should be tier 5+
                print(f"Orphan {entry['node_label']}: tier={entry['calculated_tier']}")


class TestTargetNodeRelationship:
    """Test target node relationships"""
    
    def test_supporting_node_has_target(self, api_client):
        """Supporting node should have target_entry_id"""
        response = api_client.get(f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Find the supporting node
        supporting = next((e for e in data["entries"] if e["id"] == SUPPORTING_ENTRY_ID), None)
        assert supporting, f"Supporting entry {SUPPORTING_ENTRY_ID} not found"
        
        assert supporting["target_entry_id"], "Supporting should have target_entry_id"
        assert supporting["target_entry_id"] == MAIN_ENTRY_ID, "Supporting should target main entry"
        assert supporting["target_domain_name"] == "moneysite.com", "Target domain name should be moneysite.com"
        
        print(f"Supporting node targets: {supporting['target_domain_name']} (entry_id: {supporting['target_entry_id'][:8]}...)")
    
    def test_main_node_has_no_target(self, api_client):
        """Main node should not have target_entry_id"""
        response = api_client.get(f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Find the main node
        main = next((e for e in data["entries"] if e["id"] == MAIN_ENTRY_ID), None)
        assert main, f"Main entry {MAIN_ENTRY_ID} not found"
        
        assert main["target_entry_id"] is None, "Main should not have target_entry_id"
        print(f"Main node has no target: PASS")


class TestGraphVisualizationLinks:
    """Test that graph visualization can build links correctly"""
    
    def test_entries_have_link_data(self, api_client):
        """Entries have source/target data for graph links"""
        response = api_client.get(f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Build links like D3 would
        entry_map = {e["id"]: e for e in data["entries"]}
        links = []
        
        for entry in data["entries"]:
            if entry.get("target_entry_id") and entry["target_entry_id"] in entry_map:
                links.append({
                    "source": entry["id"],  # e.id
                    "target": entry["target_entry_id"]  # e.target_entry_id
                })
        
        # TESTER2 should have 1 link: tier1-site1.com -> moneysite.com
        assert len(links) == 1, f"Expected 1 link, got {len(links)}"
        
        link = links[0]
        assert link["source"] == SUPPORTING_ENTRY_ID, "Source should be supporting entry"
        assert link["target"] == MAIN_ENTRY_ID, "Target should be main entry"
        
        print(f"Graph link: {entry_map[link['source']]['node_label']} -> {entry_map[link['target']]['node_label']}")


class TestOrphanDetection:
    """Test orphan node detection"""
    
    def test_network_tier_issues_endpoint(self, api_client):
        """Tiers endpoint reports orphans"""
        response = api_client.get(f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}/tiers")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "issues" in data, "Tiers should report issues"
        assert "orphans" in data["issues"], "Issues should include orphans"
        
        # TESTER2 should have no orphans (all supporting nodes have targets)
        print(f"Orphans in TESTER2: {len(data['issues']['orphans'])}")
    
    def test_orphan_is_node_without_target_except_main(self, api_client):
        """Orphan = supporting node without target_entry_id"""
        response = api_client.get(f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        orphans = []
        for entry in data["entries"]:
            # Orphan: not main AND no target_entry_id
            if entry["domain_role"] != "main" and not entry.get("target_entry_id"):
                orphans.append(entry)
        
        # TESTER2 should have no orphans
        assert len(orphans) == 0, f"Expected 0 orphans in TESTER2, got {len(orphans)}"
        print("Orphan detection: PASS (0 orphans)")


class TestPathNormalization:
    """Test path normalization for empty/null paths"""
    
    def test_structure_entry_accepts_empty_path(self, api_client):
        """Empty path is normalized correctly"""
        response = api_client.get(f"{BASE_URL}/api/v3/networks/{TEST_NETWORK_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        for entry in data["entries"]:
            # optimized_path should be None or empty string for domain root
            path = entry.get("optimized_path")
            if path:
                # If path exists, it should start with /
                assert path.startswith("/"), f"Path should start with /: {path}"
            
            # node_label should be domain + path or just domain
            node_label = entry.get("node_label")
            assert node_label, "node_label should exist"
            
            if path:
                assert path in node_label, f"node_label should include path: {node_label}"
            else:
                assert entry["domain_name"] == node_label, f"node_label should be domain_name when no path"
            
            print(f"Path normalization: {entry['domain_name']} + '{path or ''}' = {node_label}")


class TestUpdateStructureEntry:
    """Test updating structure entry with target_entry_id"""
    
    def test_update_target_entry_id(self, api_client):
        """Can update target_entry_id on a structure entry"""
        # First get current state
        response = api_client.get(f"{BASE_URL}/api/v3/structure/{SUPPORTING_ENTRY_ID}")
        assert response.status_code == 200
        original = response.json()
        original_target = original.get("target_entry_id")
        
        # Update with same target (no-op but tests API)
        update_response = api_client.put(
            f"{BASE_URL}/api/v3/structure/{SUPPORTING_ENTRY_ID}",
            json={"target_entry_id": MAIN_ENTRY_ID}
        )
        
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        updated = update_response.json()
        
        assert updated["target_entry_id"] == MAIN_ENTRY_ID, "target_entry_id should be updated"
        print(f"Update target_entry_id: PASS")
    
    def test_cannot_target_self(self, api_client):
        """Cannot set target_entry_id to self"""
        response = api_client.put(
            f"{BASE_URL}/api/v3/structure/{SUPPORTING_ENTRY_ID}",
            json={"target_entry_id": SUPPORTING_ENTRY_ID}
        )
        
        assert response.status_code == 400, f"Should reject self-target: {response.text}"
        assert "cannot target itself" in response.text.lower() or "self" in response.text.lower()
        print("Cannot target self: PASS")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
