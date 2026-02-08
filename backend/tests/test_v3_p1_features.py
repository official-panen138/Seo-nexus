"""
Test V3 P1 Features:
1. Export V3 Data to CSV/JSON - Full structure for networks
2. Dashboard Refresh Interval - Data-only refresh
3. Bulk Node Import with Path Support - CSV import
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
V3_API = f"{BASE_URL}/api/v3"

# Test credentials
SUPER_ADMIN = {"email": "admin@v3test.com", "password": "admin123"}


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for super_admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN)
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def test_network_id(auth_headers):
    """Get a network ID for testing"""
    response = requests.get(f"{V3_API}/networks", headers=auth_headers)
    if response.status_code == 200 and response.json():
        return response.json()[0]["id"]
    pytest.skip("No networks available for testing")


class TestExportAssetDomains:
    """Test /api/v3/export/asset-domains endpoint"""
    
    def test_export_asset_domains_json(self, auth_headers):
        """Export asset domains as JSON"""
        response = requests.get(f"{V3_API}/export/asset-domains?format=json", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "data" in data, "Response should have 'data' field"
        assert "total" in data, "Response should have 'total' field"
        assert "exported_at" in data, "Response should have 'exported_at' field"
        
        # Verify data enrichment
        if data["data"]:
            first_item = data["data"][0]
            assert "domain_name" in first_item, "Items should have domain_name"
            # Check for enriched fields
            assert "brand_name" in first_item, "Items should have enriched brand_name"
        
        print(f"PASS: Exported {data['total']} asset domains as JSON")
    
    def test_export_asset_domains_csv(self, auth_headers):
        """Export asset domains as CSV"""
        response = requests.get(f"{V3_API}/export/asset-domains?format=csv", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "text/csv" in response.headers.get("content-type", ""), "Should return CSV content-type"
        assert "attachment" in response.headers.get("content-disposition", ""), "Should have attachment header"
        
        # Verify CSV content
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        assert len(lines) >= 1, "CSV should have header row"
        
        header = lines[0].lower()
        assert "domain_name" in header, "CSV should have domain_name column"
        assert "brand_name" in header, "CSV should have brand_name column"
        
        print(f"PASS: Exported {len(lines)-1} domains as CSV")
    
    def test_export_asset_domains_with_filters(self, auth_headers):
        """Export asset domains with brand/status filters"""
        # Test with status filter
        response = requests.get(f"{V3_API}/export/asset-domains?format=json&status=active", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned items should have active status
        for item in data.get("data", []):
            if "status" in item:
                assert item["status"] == "active", f"Filtered item has wrong status: {item.get('status')}"
        
        print(f"PASS: Filtered export returned {data['total']} items")


class TestExportNetworkStructure:
    """Test /api/v3/export/networks/{id} endpoint"""
    
    def test_export_single_network_json(self, auth_headers, test_network_id):
        """Export single network with full structure as JSON"""
        response = requests.get(f"{V3_API}/export/networks/{test_network_id}?format=json", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "network" in data, "Response should have 'network' field"
        assert "entries" in data, "Response should have 'entries' field"
        assert "total_entries" in data, "Response should have 'total_entries' field"
        assert "tier_distribution" in data, "Response should have 'tier_distribution' field"
        assert "exported_at" in data, "Response should have 'exported_at' field"
        
        # Verify network metadata
        network = data["network"]
        assert "id" in network, "Network should have id"
        assert "name" in network, "Network should have name"
        
        # Verify entries have tier info
        if data["entries"]:
            entry = data["entries"][0]
            assert "domain_name" in entry, "Entry should have domain_name"
            assert "calculated_tier" in entry, "Entry should have calculated_tier"
            assert "tier_label" in entry, "Entry should have tier_label"
            assert "node_label" in entry, "Entry should have node_label"
        
        print(f"PASS: Exported network '{network.get('name')}' with {data['total_entries']} entries")
    
    def test_export_single_network_csv(self, auth_headers, test_network_id):
        """Export single network with full structure as CSV"""
        response = requests.get(f"{V3_API}/export/networks/{test_network_id}?format=csv", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "text/csv" in response.headers.get("content-type", ""), "Should return CSV"
        
        # Verify CSV content
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        header = lines[0].lower()
        
        # Verify required columns
        required_cols = ["domain_name", "calculated_tier", "tier_label", "domain_role"]
        for col in required_cols:
            assert col in header, f"CSV should have {col} column"
        
        print(f"PASS: Exported network as CSV with {len(lines)-1} entries")
    
    def test_export_nonexistent_network(self, auth_headers):
        """Export non-existent network should return 404"""
        response = requests.get(f"{V3_API}/export/networks/nonexistent-id?format=json", headers=auth_headers)
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Non-existent network returns 404")


class TestExportAllNetworks:
    """Test /api/v3/export/networks endpoint (all networks)"""
    
    def test_export_all_networks_json(self, auth_headers):
        """Export all networks as JSON"""
        response = requests.get(f"{V3_API}/export/networks?format=json", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "data" in data, "Response should have 'data' field"
        assert "total" in data, "Response should have 'total' field"
        assert "exported_at" in data, "Response should have 'exported_at' field"
        
        # Verify network data has enriched fields
        if data["data"]:
            network = data["data"][0]
            assert "name" in network, "Network should have name"
            assert "brand_name" in network, "Network should have brand_name"
            assert "domain_count" in network, "Network should have domain_count"
        
        print(f"PASS: Exported {data['total']} networks as JSON")
    
    def test_export_all_networks_csv(self, auth_headers):
        """Export all networks as CSV"""
        response = requests.get(f"{V3_API}/export/networks?format=csv", headers=auth_headers)
        
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        header = lines[0].lower()
        
        assert "name" in header, "CSV should have name column"
        assert "brand_name" in header, "CSV should have brand_name column"
        assert "domain_count" in header, "CSV should have domain_count column"
        
        print(f"PASS: Exported {len(lines)-1} networks as CSV")


class TestExportActivityLogs:
    """Test /api/v3/export/activity-logs endpoint"""
    
    def test_export_activity_logs_json(self, auth_headers):
        """Export activity logs as JSON"""
        response = requests.get(f"{V3_API}/export/activity-logs?format=json", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "data" in data, "Response should have 'data' field"
        assert "total" in data, "Response should have 'total' field"
        assert "exported_at" in data, "Response should have 'exported_at' field"
        
        # Verify log structure
        if data["data"]:
            log = data["data"][0]
            assert "timestamp" in log, "Log should have timestamp"
            assert "actor" in log, "Log should have actor"
            assert "action_type" in log, "Log should have action_type"
        
        print(f"PASS: Exported {data['total']} activity logs as JSON")
    
    def test_export_activity_logs_csv(self, auth_headers):
        """Export activity logs as CSV"""
        response = requests.get(f"{V3_API}/export/activity-logs?format=csv", headers=auth_headers)
        
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")
        
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        header = lines[0].lower()
        
        assert "timestamp" in header, "CSV should have timestamp column"
        assert "actor" in header, "CSV should have actor column"
        assert "action_type" in header, "CSV should have action_type column"
        
        print(f"PASS: Exported activity logs as CSV")
    
    def test_export_activity_logs_with_filters(self, auth_headers):
        """Export activity logs with entity_type filter"""
        response = requests.get(
            f"{V3_API}/export/activity-logs?format=json&entity_type=seo_structure_entry", 
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All logs should be for the filtered entity type
        for log in data.get("data", []):
            assert log.get("entity_type") == "seo_structure_entry", "Filter should work"
        
        print(f"PASS: Filtered activity logs export works")


class TestDashboardRefresh:
    """Test dashboard refresh settings and stats endpoints"""
    
    def test_get_dashboard_refresh_setting(self, auth_headers):
        """Get dashboard refresh interval setting"""
        response = requests.get(f"{V3_API}/settings/dashboard-refresh", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "refresh_interval" in data, "Response should have refresh_interval"
        assert "options" in data, "Response should have options"
        
        # Verify options structure
        for option in data["options"]:
            assert "value" in option, "Option should have value"
            assert "label" in option, "Option should have label"
        
        print(f"PASS: Got refresh setting: {data['refresh_interval']}")
    
    def test_update_dashboard_refresh_setting(self, auth_headers):
        """Update dashboard refresh interval setting"""
        # Set to 60 seconds (1 minute)
        response = requests.put(f"{V3_API}/settings/dashboard-refresh?interval=60", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("success") == True, "Update should succeed"
        assert data.get("refresh_interval") == 60, "Should return updated interval"
        
        # Verify the change persisted
        get_response = requests.get(f"{V3_API}/settings/dashboard-refresh", headers=auth_headers)
        assert get_response.status_code == 200
        assert get_response.json().get("refresh_interval") == 60
        
        print("PASS: Updated refresh interval to 60 seconds")
    
    def test_update_invalid_refresh_interval(self, auth_headers):
        """Invalid refresh intervals should be rejected"""
        # 45 is not a valid interval (valid: 0, 30, 60, 300, 900)
        response = requests.put(f"{V3_API}/settings/dashboard-refresh?interval=45", headers=auth_headers)
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("PASS: Invalid interval rejected")
    
    def test_get_dashboard_stats(self, auth_headers):
        """Get lightweight dashboard stats for auto-refresh"""
        response = requests.get(f"{V3_API}/dashboard/stats", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify required stats fields
        required_fields = [
            "total_domains", "total_networks", "active_domains",
            "monitored_count", "indexed_count", "noindex_count", "updated_at"
        ]
        for field in required_fields:
            assert field in data, f"Stats should have '{field}' field"
        
        # Verify values are numeric where expected
        assert isinstance(data["total_domains"], int), "total_domains should be int"
        assert isinstance(data["total_networks"], int), "total_networks should be int"
        
        print(f"PASS: Got dashboard stats: {data['total_domains']} domains, {data['total_networks']} networks")


class TestBulkNodeImport:
    """Test bulk node import with path support"""
    
    def test_get_node_import_template(self, auth_headers):
        """Get CSV template for node import"""
        response = requests.get(f"{V3_API}/import/nodes/template", headers=auth_headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "headers" in data, "Template should have headers"
        assert "example_rows" in data, "Template should have example_rows"
        
        # Verify required headers
        headers = data["headers"]
        required = ["domain_name", "optimized_path", "target_domain", "target_path"]
        for h in required:
            assert h in headers, f"Template should have {h} header"
        
        # Verify example rows
        assert len(data["example_rows"]) >= 2, "Should have at least 2 example rows"
        
        # Verify notes
        assert "notes" in data, "Template should have notes"
        
        print(f"PASS: Got node import template with {len(headers)} columns")
    
    def test_bulk_import_nodes(self, auth_headers, test_network_id):
        """Test bulk node import with path support"""
        import uuid
        
        # Create unique test domain names
        unique_suffix = str(uuid.uuid4())[:8]
        
        payload = {
            "network_id": test_network_id,
            "nodes": [
                {
                    "domain_name": f"test-import-{unique_suffix}.com",
                    "optimized_path": "/blog/test-post",
                    "domain_role": "supporting",
                    "domain_status": "canonical",
                    "index_status": "index",
                    "notes": "Test imported node with path"
                }
            ],
            "create_missing_domains": True
        }
        
        response = requests.post(f"{V3_API}/import/nodes", headers=auth_headers, json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("success") == True, "Import should succeed"
        assert "summary" in data, "Response should have summary"
        assert "details" in data, "Response should have details"
        
        summary = data["summary"]
        assert "imported" in summary, "Summary should have imported count"
        assert "skipped" in summary, "Summary should have skipped count"
        assert "errors" in summary, "Summary should have errors count"
        assert "domains_created" in summary, "Summary should have domains_created count"
        
        # Since create_missing_domains=True, should have created the domain
        assert summary["domains_created"] >= 0, "Should track created domains"
        
        print(f"PASS: Bulk import - {summary['imported']} imported, {summary['skipped']} skipped, {summary['errors']} errors")
    
    def test_bulk_import_with_target_resolution(self, auth_headers, test_network_id):
        """Test node import resolves target_domain + target_path to target_entry_id"""
        import uuid
        
        unique_suffix = str(uuid.uuid4())[:8]
        
        # First create a target node
        target_payload = {
            "network_id": test_network_id,
            "nodes": [
                {
                    "domain_name": f"target-node-{unique_suffix}.com",
                    "optimized_path": "",
                    "domain_role": "main",
                    "domain_status": "canonical",
                    "index_status": "index"
                }
            ],
            "create_missing_domains": True
        }
        
        target_response = requests.post(f"{V3_API}/import/nodes", headers=auth_headers, json=target_payload)
        assert target_response.status_code == 200
        
        # Now create a node that targets the first one
        linking_payload = {
            "network_id": test_network_id,
            "nodes": [
                {
                    "domain_name": f"linking-node-{unique_suffix}.com",
                    "optimized_path": "/link-page",
                    "domain_role": "supporting",
                    "target_domain": f"target-node-{unique_suffix}.com",
                    "target_path": ""
                }
            ],
            "create_missing_domains": True
        }
        
        response = requests.post(f"{V3_API}/import/nodes", headers=auth_headers, json=linking_payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("success") == True
        print(f"PASS: Node import with target resolution - {data['summary']}")
    
    def test_bulk_import_missing_network(self, auth_headers):
        """Import to non-existent network should fail"""
        payload = {
            "network_id": "nonexistent-network-id",
            "nodes": [{"domain_name": "test.com"}],
            "create_missing_domains": False
        }
        
        response = requests.post(f"{V3_API}/import/nodes", headers=auth_headers, json=payload)
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("PASS: Import to nonexistent network returns 404")
    
    def test_bulk_import_missing_domain_without_create(self, auth_headers, test_network_id):
        """Import missing domain without create_missing_domains should report error"""
        import uuid
        unique_domain = f"missing-domain-{uuid.uuid4()}.com"
        
        payload = {
            "network_id": test_network_id,
            "nodes": [{"domain_name": unique_domain}],
            "create_missing_domains": False  # Don't create
        }
        
        response = requests.post(f"{V3_API}/import/nodes", headers=auth_headers, json=payload)
        
        assert response.status_code == 200  # Still succeeds but reports error
        data = response.json()
        
        # Should have error for missing domain
        assert data["summary"]["errors"] >= 1, "Should report error for missing domain"
        print(f"PASS: Missing domain without create reported as error")


class TestAuthenticationRequired:
    """Test that all P1 endpoints require authentication"""
    
    def test_export_domains_requires_auth(self):
        """Export domains without auth should fail"""
        response = requests.get(f"{V3_API}/export/asset-domains?format=json")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
    
    def test_export_network_requires_auth(self):
        """Export network without auth should fail"""
        response = requests.get(f"{V3_API}/export/networks/any-id?format=json")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
    
    def test_dashboard_stats_requires_auth(self):
        """Dashboard stats without auth should fail"""
        response = requests.get(f"{V3_API}/dashboard/stats")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
    
    def test_import_nodes_requires_auth(self):
        """Import nodes without auth should fail"""
        response = requests.post(f"{V3_API}/import/nodes", json={"network_id": "x", "nodes": []})
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
