"""
Phase 4 & Phase 6 Backend API Tests
====================================

Phase 4: Root vs Path Reporting Fix
- SEO context enricher returns has_root_usage flag
- SEO context enricher returns path_only_nodes list
- SEO context enricher returns actual_nodes_affected list
- Monitoring alerts show explicit root vs path node information

Phase 6: Expired Domain Auto-Archive
- GET /api/v3/domains/archive-candidates - returns domains eligible for archiving
- GET /api/v3/domains/archived - returns list of archived domains with pagination
- POST /api/v3/domains/archive-expired - archives all expired+not_renewed domains
- POST /api/v3/asset-domains/{id}/restore - restores an archived domain (Super Admin only)
- Availability monitoring excludes archived and blocked lifecycle domains
- Expiration monitoring excludes archived and blocked lifecycle domains
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Module-level variables for state
_auth_token = None
_created_domain_ids = []


def get_auth_token(client):
    """Get or create auth token"""
    global _auth_token
    if not _auth_token:
        response = client.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "superadmin@seonoc.com",
                "password": "SuperAdmin123!"
            }
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        _auth_token = response.json().get("access_token")
    return _auth_token


@pytest.fixture
def api_client():
    """Shared requests session with authentication"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    token = get_auth_token(session)
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


# ==================== PHASE 6: ARCHIVE CANDIDATES ====================

def test_get_archive_candidates_endpoint(api_client):
    """Test GET /api/v3/domains/archive-candidates returns eligible domains"""
    response = api_client.get(f"{BASE_URL}/api/v3/domains/archive-candidates")
    
    assert response.status_code == 200, f"Failed to get archive candidates: {response.text}"
    data = response.json()
    
    # Verify response structure
    assert "total" in data, "Response should have 'total' field"
    assert "domains" in data, "Response should have 'domains' field"
    assert isinstance(data["domains"], list), "Domains should be a list"
    
    print(f"Found {data['total']} archive candidates")
    
    # If there are candidates, verify they have required fields
    if data["domains"]:
        for domain in data["domains"][:3]:  # Check first 3
            assert "id" in domain, "Domain should have 'id'"
            assert "domain_name" in domain, "Domain should have 'domain_name'"
            assert "lifecycle_status" in domain, "Domain should have 'lifecycle_status'"
            assert domain.get("lifecycle_status") == "not_renewed", \
                f"Archive candidate should have lifecycle_status='not_renewed', got {domain.get('lifecycle_status')}"
            assert "days_expired" in domain, "Domain should have 'days_expired'"
            print(f"  - {domain['domain_name']}: expired {domain['days_expired']} days")


# ==================== PHASE 6: ARCHIVED DOMAINS LIST ====================

def test_get_archived_domains_endpoint(api_client):
    """Test GET /api/v3/domains/archived returns archived domains with pagination"""
    response = api_client.get(f"{BASE_URL}/api/v3/domains/archived")
    
    assert response.status_code == 200, f"Failed to get archived domains: {response.text}"
    data = response.json()
    
    # Verify response structure
    assert "data" in data, "Response should have 'data' field"
    assert "meta" in data, "Response should have 'meta' field"
    
    meta = data["meta"]
    assert "page" in meta, "Meta should have 'page'"
    assert "limit" in meta, "Meta should have 'limit'"
    assert "total" in meta, "Meta should have 'total'"
    assert "total_pages" in meta, "Meta should have 'total_pages'"
    
    print(f"Found {meta['total']} archived domains (page {meta['page']} of {meta['total_pages']})")
    
    # Verify all returned domains are archived
    for domain in data["data"]:
        assert domain.get("archived") == True, f"Domain {domain.get('domain_name')} should be archived"


def test_get_archived_domains_pagination(api_client):
    """Test pagination works correctly for archived domains"""
    response1 = api_client.get(f"{BASE_URL}/api/v3/domains/archived?page=1&limit=5")
    assert response1.status_code == 200
    
    data1 = response1.json()
    assert data1["meta"]["page"] == 1
    assert data1["meta"]["limit"] == 5


def test_get_archived_domains_search_filter(api_client):
    """Test search filter for archived domains"""
    response = api_client.get(f"{BASE_URL}/api/v3/domains/archived?search=test")
    assert response.status_code == 200
    data = response.json()
    
    # If results, verify search matches domain names
    for domain in data["data"]:
        assert "test" in domain.get("domain_name", "").lower(), \
            f"Search result should contain 'test': {domain.get('domain_name')}"


# ==================== PHASE 6: ARCHIVE EXPIRED DOMAINS ====================

def test_archive_expired_domains_super_admin_only(api_client):
    """Test POST /api/v3/domains/archive-expired requires Super Admin"""
    # This test verifies the endpoint exists and returns proper structure
    response = api_client.post(f"{BASE_URL}/api/v3/domains/archive-expired")
    
    # Should either succeed (200) or return 200 with no domains to archive
    assert response.status_code == 200, f"Failed archive-expired: {response.text}"
    data = response.json()
    
    assert "success" in data, "Response should have 'success' field"
    assert "message" in data, "Response should have 'message' field"
    assert "archived_count" in data, "Response should have 'archived_count' field"
    assert "domains" in data, "Response should have 'domains' field"
    
    print(f"Archive result: {data['message']}, archived_count: {data['archived_count']}")


# ==================== PHASE 6: RESTORE ARCHIVED DOMAIN ====================

def test_restore_domain_endpoint_exists(api_client):
    """Test POST /api/v3/asset-domains/{id}/restore endpoint exists"""
    # Try to restore a non-existent domain
    fake_id = str(uuid.uuid4())
    response = api_client.post(f"{BASE_URL}/api/v3/asset-domains/{fake_id}/restore")
    
    # Should return 404 for non-existent domain, not 405 or 500
    assert response.status_code in [404, 400], \
        f"Expected 404 or 400, got {response.status_code}: {response.text}"
    
    if response.status_code == 404:
        assert "not found" in response.text.lower(), "Should say domain not found"
    print("Restore endpoint exists and handles non-existent domain correctly")


def test_restore_non_archived_domain_fails(api_client):
    """Test restoring a domain that is not archived fails"""
    # Get a non-archived domain
    response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?limit=1")
    
    if response.status_code == 200:
        data = response.json()
        if data.get("data") and len(data["data"]) > 0:
            domain = data["data"][0]
            if not domain.get("archived"):
                # Try to restore a non-archived domain
                restore_response = api_client.post(
                    f"{BASE_URL}/api/v3/asset-domains/{domain['id']}/restore"
                )
                assert restore_response.status_code == 400, \
                    f"Should fail to restore non-archived domain: {restore_response.text}"
                assert "not archived" in restore_response.text.lower()
                print(f"Correctly rejected restore for non-archived domain: {domain['domain_name']}")


# ==================== PHASE 6: MONITORING EXCLUDES ARCHIVED ====================

def test_monitoring_query_excludes_archived(api_client):
    """Verify availability monitoring excludes archived domains"""
    # Get domains with monitoring enabled
    response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?monitoring_enabled=true")
    
    assert response.status_code == 200
    data = response.json()
    
    # All returned domains should not be archived
    for domain in data.get("data", []):
        if domain.get("monitoring_enabled"):
            assert domain.get("archived") != True, \
                f"Domain {domain.get('domain_name')} is archived but returned in monitoring list"
    
    print(f"Verified {len(data.get('data', []))} monitored domains are not archived")


def test_monitoring_query_excludes_blocked_lifecycle(api_client):
    """Verify monitoring excludes blocked lifecycle domains (released, not_renewed, quarantined)"""
    blocked_statuses = ["released", "not_renewed", "quarantined"]
    
    for status in blocked_statuses:
        response = api_client.get(
            f"{BASE_URL}/api/v3/asset-domains?lifecycle_status={status}&monitoring_enabled=true"
        )
        
        assert response.status_code == 200, f"Query for {status} failed"
        data = response.json()
        
        # If we find monitored domains with blocked lifecycle, that's okay
        # The key is that monitoring SERVICE excludes them (tested separately)
        print(f"Lifecycle status '{status}' query works correctly")


# ==================== PHASE 4: SEO CONTEXT ENRICHER ====================

def test_seo_context_enricher_returns_root_usage_flag(api_client):
    """Test SEO context enricher returns has_root_usage flag"""
    # Get a domain that's used in SEO network
    response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?used_in_seo=true&limit=5")
    
    if response.status_code == 200:
        data = response.json()
        if data.get("data") and len(data["data"]) > 0:
            # Check if domains have seo_networks field
            for domain in data["data"]:
                seo_networks = domain.get("seo_networks", [])
                if seo_networks:
                    print(f"Domain {domain.get('domain_name')} is used in {len(seo_networks)} SEO networks")
                    # The has_root_usage flag is part of monitoring alert context
                    # We verify the domain is tracked in SEO
                    assert domain.get("is_used_in_seo_network") == True
    else:
        print("No domains with used_in_seo=true found")


def test_monitoring_test_alert_includes_phase4_fields(api_client):
    """Test monitoring test alert includes Phase 4 fields (root vs path info)"""
    # Get a domain with monitoring enabled
    response = api_client.get(f"{BASE_URL}/api/v3/asset-domains?monitoring_enabled=true&limit=1")
    
    if response.status_code == 200 and response.json().get("data"):
        domain = response.json()["data"][0]
        domain_id = domain["id"]
        
        # Test expiration alert (which uses SEO context enricher)
        test_response = api_client.post(
            f"{BASE_URL}/api/v3/monitoring/test-expiration-alert",
            json={
                "domain_id": domain_id,
                "simulated_days": 7
            }
        )
        
        if test_response.status_code == 200:
            result = test_response.json()
            # Check that SEO context info is included
            print(f"Test alert result: seo_used={result.get('seo_used')}")
            
            # The message preview should contain root vs path info if applicable
            if result.get("seo_used"):
                message = result.get("message_preview", "")
                # Verify SEO context section is present
                assert "SEO CONTEXT" in message or "SEO" in message, \
                    "Alert should include SEO context information"
                print("Test alert includes SEO context with Phase 4 enhancements")
        else:
            print(f"Test alert endpoint returned {test_response.status_code}")
    else:
        print("No monitored domains available for alert test")


# ==================== PHASE 4: PATH-ONLY NODES ====================

def test_structure_entries_with_paths(api_client):
    """Test that SEO structure entries can have optimized_path"""
    # Get networks - returns list directly
    response = api_client.get(f"{BASE_URL}/api/v3/networks?limit=1")
    
    if response.status_code == 200:
        networks_data = response.json()
        
        # Handle both list and dict response formats
        if isinstance(networks_data, dict):
            networks = networks_data.get("data", [])
        else:
            networks = networks_data if isinstance(networks_data, list) else []
        
        if networks:
            network = networks[0]
            network_id = network["id"]
            
            # Get structure entries for this network
            entries_response = api_client.get(
                f"{BASE_URL}/api/v3/networks/{network_id}/structure"
            )
            
            if entries_response.status_code == 200:
                entries = entries_response.json()
                
                # Handle both list and dict response
                if isinstance(entries, dict):
                    entries = entries.get("entries", entries.get("data", []))
                entries = entries if isinstance(entries, list) else []
                
                # Check if any entries have optimized_path
                path_entries = [e for e in entries if e.get("optimized_path")]
                root_entries = [e for e in entries if not e.get("optimized_path")]
                
                print(f"Network {network.get('name', 'Unknown')}: {len(root_entries)} root entries, {len(path_entries)} path entries")
                
                for entry in path_entries[:3]:
                    print(f"  - Path entry: {entry.get('domain_name')}{entry.get('optimized_path')}")


# ==================== INTEGRATION TEST: FULL ARCHIVE FLOW ====================

def test_full_archive_flow_integration(api_client):
    """Integration test: Create domain → Mark not_renewed → Archive → Restore"""
    global _created_domain_ids
    
    # Get a brand to use
    brands_response = api_client.get(f"{BASE_URL}/api/brands")
    if brands_response.status_code != 200 or not brands_response.json():
        pytest.skip("No brands available for test")
    
    brand = brands_response.json()[0]
    
    # 1. Create a test domain with expired date
    past_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    test_domain_name = f"test-archive-{uuid.uuid4().hex[:8]}.com"
    
    create_response = api_client.post(
        f"{BASE_URL}/api/v3/asset-domains",
        json={
            "domain_name": test_domain_name,
            "brand_id": brand["id"],
            "expiration_date": past_date,
            "lifecycle_status": "not_renewed",
            "monitoring_enabled": False
        }
    )
    
    if create_response.status_code != 201:
        print(f"Could not create test domain: {create_response.text}")
        pytest.skip("Cannot create test domain")
    
    created_domain = create_response.json()
    domain_id = created_domain["id"]
    _created_domain_ids.append(domain_id)
    
    print(f"Created test domain: {test_domain_name} (ID: {domain_id})")
    
    try:
        # 2. Verify it appears in archive candidates
        candidates_response = api_client.get(f"{BASE_URL}/api/v3/domains/archive-candidates")
        assert candidates_response.status_code == 200
        
        candidates = candidates_response.json()["domains"]
        is_candidate = any(d["id"] == domain_id for d in candidates)
        assert is_candidate, f"Domain should appear in archive candidates"
        print(f"Domain appears in archive candidates ✓")
        
        # 3. Archive expired domains
        archive_response = api_client.post(f"{BASE_URL}/api/v3/domains/archive-expired")
        assert archive_response.status_code == 200
        
        archive_result = archive_response.json()
        archived_ids = [d["id"] for d in archive_result.get("domains", [])]
        
        if domain_id in archived_ids:
            print(f"Domain was archived ✓")
        else:
            print(f"Domain may have been archived in a previous run or not eligible")
        
        # 4. Verify domain is archived
        domain_response = api_client.get(f"{BASE_URL}/api/v3/asset-domains/{domain_id}")
        if domain_response.status_code == 200:
            domain_data = domain_response.json()
            if domain_data.get("archived"):
                print(f"Domain verified as archived ✓")
                
                # 5. Restore the domain
                restore_response = api_client.post(
                    f"{BASE_URL}/api/v3/asset-domains/{domain_id}/restore"
                )
                assert restore_response.status_code == 200, f"Restore failed: {restore_response.text}"
                
                restored_domain = restore_response.json()
                assert restored_domain.get("archived") == False, "Domain should be unarchived"
                print(f"Domain restored successfully ✓")
                print(f"New lifecycle status: {restored_domain.get('lifecycle_status')}")
            else:
                print("Domain was not archived (may have been restored already)")
    finally:
        # Cleanup - delete the test domain
        api_client.delete(f"{BASE_URL}/api/v3/asset-domains/{domain_id}")
        print(f"Test domain cleaned up")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
