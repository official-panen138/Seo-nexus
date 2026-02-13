"""
Test Import/Export Asset Domains functionality
Tests the enhanced import with preview/confirm flow and export with filters
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://domain-asset-monitor.preview.emergentagent.com').rstrip('/')


class TestAuth:
    """Authentication for testing"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "superadmin@seonoc.com",
            "password": "SuperAdmin123!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("access_token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}


class TestExportAPI(TestAuth):
    """Test Export Asset Domains API"""
    
    def test_export_json_format(self, auth_headers):
        """Test export returns JSON format with all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/v3/export/asset-domains",
            params={"format": "json"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Export JSON failed: {response.text}"
        
        data = response.json()
        assert "total" in data, "Missing 'total' field in response"
        assert "data" in data, "Missing 'data' field in response"
        assert data["total"] > 0, "No domains exported"
        
        # Verify required fields are present
        first_domain = data["data"][0]
        required_fields = [
            "domain_name", "brand_name", "category_name", 
            "domain_active_status", "monitoring_status", "lifecycle_status",
            "quarantine_category", "seo_networks", "expiration_date", 
            "monitoring_enabled"
        ]
        for field in required_fields:
            assert field in first_domain, f"Missing required field: {field}"
    
    def test_export_csv_format(self, auth_headers):
        """Test export returns CSV format"""
        response = requests.get(
            f"{BASE_URL}/api/v3/export/asset-domains",
            params={"format": "csv"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Export CSV failed: {response.text}"
        assert "text/csv" in response.headers.get("Content-Type", ""), "Response should be CSV"
        
        # Verify CSV content
        content = response.text
        lines = content.strip().split('\n')
        assert len(lines) > 1, "CSV should have header and data rows"
        
        # Check required columns in header
        header = lines[0].lower()
        required_columns = ["domain_name", "brand_name", "monitoring_enabled"]
        for col in required_columns:
            assert col in header, f"Missing required column: {col}"
    
    def test_export_with_filter(self, auth_headers):
        """Test export respects filters"""
        # Export with monitoring_enabled=ON filter
        response = requests.get(
            f"{BASE_URL}/api/v3/export/asset-domains",
            params={"format": "json", "monitoring_enabled": "ON"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Export with filter failed: {response.text}"
        
        data = response.json()
        # Verify all results match filter (if any results returned)
        if data["total"] > 0:
            for domain in data["data"]:
                assert domain["monitoring_enabled"] == "ON", "Filter not applied correctly"


class TestImportPreviewAPI(TestAuth):
    """Test Import Preview API"""
    
    def test_import_preview_new_domain(self, auth_headers):
        """Test import preview with new domain"""
        test_domains = [
            {
                "domain_name": "test-new-domain-123.com",
                "brand_name": "Panen138",
                "category_name": "Money Site",
                "registrar_name": "GoDaddy",
                "expiration_date": "2027-12-31",
                "lifecycle_status": "active",
                "monitoring_enabled": "ON",
                "notes": "Test import"
            }
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/v3/import/domains/preview",
            json={"domains": test_domains},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Preview failed: {response.text}"
        
        data = response.json()
        assert "new_domains" in data, "Missing new_domains in response"
        assert "updated_domains" in data, "Missing updated_domains in response"
        assert "errors" in data, "Missing errors in response"
        assert "summary" in data, "Missing summary in response"
        
        # Verify summary counts
        summary = data["summary"]
        assert summary["new_count"] >= 1, "Should detect new domain"
        assert summary["error_count"] == 0, "Should have no errors for valid data"
    
    def test_import_preview_update_existing(self, auth_headers):
        """Test import preview with existing domain update"""
        test_domains = [
            {
                "domain_name": "moneysite.com",  # Existing domain
                "brand_name": "Panen138",
                "expiration_date": "2028-06-15",
                "lifecycle_status": "released",
                "monitoring_enabled": "OFF",
                "notes": "Update existing"
            }
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/v3/import/domains/preview",
            json={"domains": test_domains},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Preview failed: {response.text}"
        
        data = response.json()
        summary = data["summary"]
        assert summary["update_count"] >= 1, "Should detect domain to update"
    
    def test_import_preview_invalid_data(self, auth_headers):
        """Test import preview with invalid data"""
        test_domains = [
            {
                "domain_name": "",  # Invalid - empty domain name
                "brand_name": "Test"
            }
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/v3/import/domains/preview",
            json={"domains": test_domains},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Preview should handle invalid data: {response.text}"
        
        data = response.json()
        summary = data["summary"]
        # Should report errors for invalid data
        assert summary["error_count"] >= 1, "Should detect invalid domain"
    
    def test_import_preview_mixed_data(self, auth_headers):
        """Test import preview with mix of new, update, and errors"""
        test_domains = [
            {
                "domain_name": "test-brand-new-domain.com",
                "brand_name": "Panen138",
                "expiration_date": "2027-12-31",
                "lifecycle_status": "active",
                "monitoring_enabled": "ON"
            },
            {
                "domain_name": "moneysite.com",  # Existing
                "brand_name": "Panen138",
                "expiration_date": "2028-01-01",
                "lifecycle_status": "released"
            },
            {
                "domain_name": "",  # Invalid
                "brand_name": ""
            }
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/v3/import/domains/preview",
            json={"domains": test_domains},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Preview failed: {response.text}"
        
        data = response.json()
        summary = data["summary"]
        assert summary["total_rows"] == 3, "Should process all 3 rows"
        assert summary["new_count"] >= 1, "Should detect new domain"
        assert summary["update_count"] >= 1, "Should detect update"
        assert summary["error_count"] >= 1, "Should detect error"


class TestImportTemplateAPI(TestAuth):
    """Test Import Template Download API"""
    
    def test_download_template(self, auth_headers):
        """Test template download returns valid CSV"""
        response = requests.get(
            f"{BASE_URL}/api/v3/import/domains/template",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Template download failed: {response.text}"
        
        # Verify it's a CSV
        content = response.text
        lines = content.strip().split('\n')
        assert len(lines) >= 1, "Template should have at least header row"
        
        # Check required columns
        header = lines[0].lower()
        required_columns = ["domain_name", "brand_name", "lifecycle_status", "monitoring_enabled"]
        for col in required_columns:
            assert col in header, f"Template missing required column: {col}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
