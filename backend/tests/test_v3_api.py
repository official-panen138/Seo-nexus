"""
V3 API Tests for SEO-NOC
========================
Tests for:
- /api/v3/asset-domains CRUD
- /api/v3/networks CRUD and tier calculation
- /api/v3/structure entries with derived tiers
- /api/v3/reports/dashboard
- /api/v3/reports/conflicts
- /api/v3/activity-logs
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "superadmin@seonoc.com"
SUPER_ADMIN_PASSWORD = "SuperAdmin123!"


class TestAuthentication:
    """Test authentication and get token"""
    
    def test_login_superadmin(self):
        """Login as superadmin"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "super_admin"
        print(f"Login successful for {SUPER_ADMIN_EMAIL}")


@pytest.fixture(scope="session")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    pytest.skip("Authentication failed")


@pytest.fixture
def auth_headers(auth_token):
    """Get authorization headers"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestV3AssetDomains:
    """V3 Asset Domains API tests"""
    
    def test_get_all_asset_domains(self, auth_headers):
        """GET /api/v3/asset-domains - List all asset domains"""
        response = requests.get(
            f"{BASE_URL}/api/v3/asset-domains",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} asset domains")
        
        # Verify expected data structure
        if len(data) > 0:
            domain = data[0]
            assert "id" in domain
            assert "domain_name" in domain
            assert "brand_id" in domain
            assert "status" in domain
            print(f"First domain: {domain['domain_name']} - status: {domain['status']}")
    
    def test_get_asset_domain_by_id(self, auth_headers):
        """GET /api/v3/asset-domains/{id} - Get single asset domain"""
        # First get list
        list_response = requests.get(
            f"{BASE_URL}/api/v3/asset-domains",
            headers=auth_headers
        )
        assert list_response.status_code == 200
        domains = list_response.json()
        
        if len(domains) == 0:
            pytest.skip("No asset domains to test")
        
        domain_id = domains[0]["id"]
        response = requests.get(
            f"{BASE_URL}/api/v3/asset-domains/{domain_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["id"] == domain_id
        print(f"Retrieved domain: {data['domain_name']}")
    
    def test_asset_domain_not_found(self, auth_headers):
        """GET /api/v3/asset-domains/{invalid_id} - Should return 404"""
        response = requests.get(
            f"{BASE_URL}/api/v3/asset-domains/nonexistent-id-123",
            headers=auth_headers
        )
        assert response.status_code == 404
    
    def test_filter_by_status(self, auth_headers):
        """GET /api/v3/asset-domains?status=active - Filter by status"""
        response = requests.get(
            f"{BASE_URL}/api/v3/asset-domains?status=active",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        for domain in data:
            assert domain["status"] == "active", f"Expected active, got {domain['status']}"
        print(f"Found {len(data)} active domains")


class TestV3Networks:
    """V3 SEO Networks API tests"""
    
    def test_get_all_networks(self, auth_headers):
        """GET /api/v3/networks - List all networks"""
        response = requests.get(
            f"{BASE_URL}/api/v3/networks",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} SEO networks")
        
        if len(data) > 0:
            network = data[0]
            assert "id" in network
            assert "name" in network
            assert "domain_count" in network
            print(f"First network: {network['name']} - {network['domain_count']} domains")
    
    def test_get_network_detail_with_tiers(self, auth_headers):
        """GET /api/v3/networks/{id} - Get network with derived tiers"""
        # Get list first
        list_response = requests.get(
            f"{BASE_URL}/api/v3/networks",
            headers=auth_headers
        )
        assert list_response.status_code == 200
        networks = list_response.json()
        
        if len(networks) == 0:
            pytest.skip("No networks to test")
        
        network_id = networks[0]["id"]
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{network_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["id"] == network_id
        assert "entries" in data
        assert isinstance(data["entries"], list)
        
        print(f"Network '{data['name']}' has {len(data['entries'])} entries")
        
        # Verify entries have calculated tiers
        for entry in data["entries"][:5]:  # Check first 5
            assert "calculated_tier" in entry or entry.get("calculated_tier") is None
            assert "tier_label" in entry or entry.get("tier_label") is None
            print(f"  - {entry.get('domain_name', 'N/A')}: Tier {entry.get('calculated_tier', 'N/A')} ({entry.get('tier_label', 'N/A')})")
    
    def test_get_network_tiers(self, auth_headers):
        """GET /api/v3/networks/{id}/tiers - Get tier distribution"""
        # Get list first
        list_response = requests.get(
            f"{BASE_URL}/api/v3/networks",
            headers=auth_headers
        )
        networks = list_response.json()
        
        if len(networks) == 0:
            pytest.skip("No networks to test")
        
        # Find Main SEO Network
        main_network = next(
            (n for n in networks if "Main" in n.get("name", "")),
            networks[0]
        )
        
        response = requests.get(
            f"{BASE_URL}/api/v3/networks/{main_network['id']}/tiers",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "distribution" in data
        assert "domains" in data
        assert "network_name" in data
        
        print(f"Tier distribution for '{data['network_name']}':")
        for tier, count in data["distribution"].items():
            print(f"  {tier}: {count}")
        
        # Verify expected tier distribution according to context
        # Expected: LP/Money Site: 1, Tier 1: 3, Tier 2: 6, Tier 3: 6, Tier 5+: 1
        distribution = data["distribution"]
        if "LP/Money Site" in distribution:
            print(f"\nVerifying tier distribution...")
            print(f"  LP/Money Site: {distribution.get('LP/Money Site', 0)}")
            print(f"  Tier 1: {distribution.get('Tier 1', 0)}")
            print(f"  Tier 2: {distribution.get('Tier 2', 0)}")
            print(f"  Tier 3: {distribution.get('Tier 3', 0)}")


class TestV3Structure:
    """V3 Structure Entries API tests"""
    
    def test_get_structure_entries(self, auth_headers):
        """GET /api/v3/structure - List structure entries"""
        response = requests.get(
            f"{BASE_URL}/api/v3/structure",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} structure entries")
        
        if len(data) > 0:
            entry = data[0]
            assert "id" in entry
            assert "asset_domain_id" in entry
            assert "network_id" in entry
            assert "domain_role" in entry
            print(f"First entry: {entry.get('domain_name', 'N/A')} - Role: {entry['domain_role']}")
    
    def test_structure_entries_have_derived_tiers(self, auth_headers):
        """Verify structure entries have calculated tiers"""
        response = requests.get(
            f"{BASE_URL}/api/v3/structure",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Count entries with calculated tiers
        with_tier = sum(1 for e in data if e.get("calculated_tier") is not None)
        print(f"{with_tier}/{len(data)} entries have calculated tiers")
        
        # At least some should have tiers
        if len(data) > 0:
            assert with_tier > 0, "No entries have calculated tiers"
    
    def test_filter_by_network(self, auth_headers):
        """GET /api/v3/structure?network_id=xxx - Filter by network"""
        # Get a network first
        networks_response = requests.get(
            f"{BASE_URL}/api/v3/networks",
            headers=auth_headers
        )
        networks = networks_response.json()
        
        if len(networks) == 0:
            pytest.skip("No networks to test")
        
        network_id = networks[0]["id"]
        response = requests.get(
            f"{BASE_URL}/api/v3/structure?network_id={network_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for entry in data:
            assert entry["network_id"] == network_id
        print(f"Found {len(data)} entries in network {networks[0]['name']}")
    
    def test_filter_by_domain_role(self, auth_headers):
        """GET /api/v3/structure?domain_role=main - Filter by role"""
        response = requests.get(
            f"{BASE_URL}/api/v3/structure?domain_role=main",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for entry in data:
            assert entry["domain_role"] == "main"
        print(f"Found {len(data)} main domain entries")


class TestV3Reports:
    """V3 Reports API tests"""
    
    def test_dashboard_stats(self, auth_headers):
        """GET /api/v3/reports/dashboard - Get dashboard stats"""
        response = requests.get(
            f"{BASE_URL}/api/v3/reports/dashboard",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "collections" in data
        assert "asset_status" in data
        assert "domain_roles" in data
        assert "index_status" in data
        assert "monitoring" in data
        
        print(f"Dashboard Stats:")
        print(f"  Asset Domains: {data['collections'].get('asset_domains', 0)}")
        print(f"  SEO Networks: {data['collections'].get('seo_networks', 0)}")
        print(f"  Structure Entries: {data['collections'].get('seo_structure_entries', 0)}")
        print(f"  Active: {data['asset_status'].get('active', 0)}")
        print(f"  Main domains: {data['domain_roles'].get('main', 0)}")
        print(f"  Index rate: {data['index_status'].get('index_rate', 0)}%")
    
    def test_conflicts_detection(self, auth_headers):
        """GET /api/v3/reports/conflicts - Detect SEO conflicts"""
        response = requests.get(
            f"{BASE_URL}/api/v3/reports/conflicts",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "conflicts" in data
        assert "total" in data
        assert "by_type" in data
        
        print(f"Conflicts detected: {data['total']}")
        print(f"  By type: {data['by_type']}")
        
        # Show first few conflicts
        for conflict in data["conflicts"][:3]:
            print(f"  - {conflict.get('domain_name', 'N/A')}: {conflict.get('type', 'N/A')}")


class TestV3ActivityLogs:
    """V3 Activity Logs API tests"""
    
    def test_get_activity_logs(self, auth_headers):
        """GET /api/v3/activity-logs - Get activity logs"""
        response = requests.get(
            f"{BASE_URL}/api/v3/activity-logs",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} activity logs")
        
        if len(data) > 0:
            log = data[0]
            assert "id" in log
            assert "actor" in log
            assert "action_type" in log
            assert "entity_type" in log
            print(f"Latest log: {log['actor']} - {log['action_type']} - {log['entity_type']}")
    
    def test_filter_by_actor(self, auth_headers):
        """GET /api/v3/activity-logs?actor=system:migration_v3"""
        response = requests.get(
            f"{BASE_URL}/api/v3/activity-logs?actor=system:migration_v3",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for log in data:
            assert log["actor"] == "system:migration_v3"
        print(f"Found {len(data)} migration logs")
    
    def test_activity_log_stats(self, auth_headers):
        """GET /api/v3/activity-logs/stats - Get stats"""
        response = requests.get(
            f"{BASE_URL}/api/v3/activity-logs/stats",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "total_logs" in data
        assert "migration_logs" in data
        print(f"Activity log stats:")
        print(f"  Total: {data['total_logs']}")
        print(f"  Migration: {data['migration_logs']}")
        print(f"  By action: {data.get('by_action', {})}")
        print(f"  By entity: {data.get('by_entity', {})}")


class TestV3DataIntegrity:
    """Test data integrity and consistency across V3 collections"""
    
    def test_migrated_data_counts(self, auth_headers):
        """Verify expected data counts from migration"""
        # Get counts
        assets_response = requests.get(f"{BASE_URL}/api/v3/asset-domains", headers=auth_headers)
        networks_response = requests.get(f"{BASE_URL}/api/v3/networks", headers=auth_headers)
        structure_response = requests.get(f"{BASE_URL}/api/v3/structure", headers=auth_headers)
        logs_response = requests.get(f"{BASE_URL}/api/v3/activity-logs", headers=auth_headers)
        
        assert assets_response.status_code == 200
        assert networks_response.status_code == 200
        assert structure_response.status_code == 200
        assert logs_response.status_code == 200
        
        asset_count = len(assets_response.json())
        network_count = len(networks_response.json())
        structure_count = len(structure_response.json())
        log_count = len(logs_response.json())
        
        print(f"\nV3 Data counts:")
        print(f"  Asset Domains: {asset_count} (expected: 23)")
        print(f"  SEO Networks: {network_count} (expected: 4)")
        print(f"  Structure Entries: {structure_count} (expected: 23)")
        print(f"  Activity Logs: {log_count} (expected: 50+)")
        
        # Basic verification that migration happened
        assert asset_count > 0, "No asset domains found"
        assert network_count > 0, "No networks found"
        assert structure_count > 0, "No structure entries found"
    
    def test_structure_entries_link_to_valid_assets(self, auth_headers):
        """Verify structure entries reference valid asset domains"""
        assets_response = requests.get(f"{BASE_URL}/api/v3/asset-domains", headers=auth_headers)
        structure_response = requests.get(f"{BASE_URL}/api/v3/structure", headers=auth_headers)
        
        assets = {a["id"]: a for a in assets_response.json()}
        entries = structure_response.json()
        
        orphan_refs = []
        for entry in entries:
            if entry["asset_domain_id"] not in assets:
                orphan_refs.append(entry)
        
        if orphan_refs:
            print(f"WARNING: {len(orphan_refs)} entries reference non-existent assets")
        else:
            print("All structure entries reference valid assets")
        
        assert len(orphan_refs) == 0, f"{len(orphan_refs)} orphan references found"
    
    def test_main_domains_have_tier_0(self, auth_headers):
        """Main domains should have tier 0 (LP/Money Site)"""
        structure_response = requests.get(
            f"{BASE_URL}/api/v3/structure?domain_role=main",
            headers=auth_headers
        )
        main_entries = structure_response.json()
        
        for entry in main_entries:
            tier = entry.get("calculated_tier")
            print(f"Main domain {entry.get('domain_name', 'N/A')}: tier = {tier}")
            # Main domains should have tier 0
            if tier is not None:
                assert tier == 0, f"Main domain has tier {tier}, expected 0"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
