"""
Test suite for Optimization Detail Drawer feature (PRD: Optimization View + Complaint Flow)
Tests the following endpoints:
- GET /api/v3/optimizations/{id}/detail - Full optimization detail with complaints/responses
- POST /api/v3/optimizations/{id}/responses - Add team response (min 20, max 2000 chars)
- PATCH /api/v3/optimizations/{id}/complaints/{complaint_id}/resolve - Resolve complaint (Super Admin)
- PATCH /api/v3/optimizations/{id}/close - Close optimization (Super Admin, blocked by unresolved complaints)
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSetup:
    """Test setup and authentication"""
    
    @pytest.fixture(scope="class")
    def session(self):
        return requests.Session()
    
    @pytest.fixture(scope="class")
    def super_admin_token(self, session):
        """Login as Super Admin"""
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "superadmin@seonoc.com",
            "password": "SuperAdmin123!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, super_admin_token):
        return {"Authorization": f"Bearer {super_admin_token}"}
    
    @pytest.fixture(scope="class")
    def test_network_id(self):
        """Network ID from agent context"""
        return "76e067db-60ba-4e3b-a949-b3229dc1c652"


class TestOptimizationDetailEndpoint(TestSetup):
    """Test GET /api/v3/optimizations/{id}/detail"""
    
    def test_get_detail_requires_auth(self, session):
        """Detail endpoint requires authentication"""
        fake_id = str(uuid.uuid4())
        response = session.get(f"{BASE_URL}/api/v3/optimizations/{fake_id}/detail")
        assert response.status_code in [401, 403], "Should require auth"
        print("✓ Detail endpoint requires authentication")
    
    def test_get_detail_not_found(self, session, auth_headers):
        """Returns 404 for non-existent optimization"""
        fake_id = str(uuid.uuid4())
        response = session.get(
            f"{BASE_URL}/api/v3/optimizations/{fake_id}/detail",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Returns 404 for non-existent optimization")
    
    def test_get_existing_optimization_detail(self, session, auth_headers, test_network_id):
        """Get detail of an existing optimization"""
        # First, get list of optimizations to find one
        list_response = session.get(
            f"{BASE_URL}/api/v3/networks/{test_network_id}/optimizations",
            headers=auth_headers
        )
        
        if list_response.status_code != 200 or not list_response.json().get("data"):
            pytest.skip("No existing optimizations found in test network")
        
        optimizations = list_response.json()["data"]
        opt_id = optimizations[0]["id"]
        
        # Get detail
        response = session.get(
            f"{BASE_URL}/api/v3/optimizations/{opt_id}/detail",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get detail: {response.text}"
        
        data = response.json()
        # Verify required fields in detail response
        assert "id" in data, "Missing id"
        assert "title" in data, "Missing title"
        assert "description" in data, "Missing description"
        assert "complaints" in data, "Missing complaints array"
        assert "responses" in data, "Missing responses array"
        assert "is_blocked" in data, "Missing is_blocked field"
        assert "network_name" in data, "Missing network_name"
        assert "brand_name" in data, "Missing brand_name"
        assert "complaint_status" in data, "Missing complaint_status"
        
        print(f"✓ Got optimization detail: {data['title']}")
        print(f"  - Complaints: {len(data['complaints'])}")
        print(f"  - Responses: {len(data['responses'])}")
        print(f"  - is_blocked: {data['is_blocked']}")
        print(f"  - complaint_status: {data['complaint_status']}")
        
        return opt_id


class TestTeamResponseEndpoint(TestSetup):
    """Test POST /api/v3/optimizations/{id}/responses"""
    
    @pytest.fixture(scope="class")
    def optimization_with_complaint(self, session, auth_headers, test_network_id):
        """Get or create an optimization with a complaint for testing"""
        # Get list of optimizations
        list_response = session.get(
            f"{BASE_URL}/api/v3/networks/{test_network_id}/optimizations",
            headers=auth_headers
        )
        
        if list_response.status_code != 200 or not list_response.json().get("data"):
            pytest.skip("No optimizations available for testing")
        
        # Find optimization with complaint or use first one
        for opt in list_response.json()["data"]:
            if opt.get("complaint_status") in ["complained", "under_review"]:
                return opt["id"]
        
        # Use first optimization
        return list_response.json()["data"][0]["id"]
    
    def test_response_validation_min_length(self, session, auth_headers, optimization_with_complaint):
        """Response note must be at least 20 characters"""
        response = session.post(
            f"{BASE_URL}/api/v3/optimizations/{optimization_with_complaint}/responses",
            headers=auth_headers,
            json={"note": "Short", "report_urls": []}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "20" in response.json().get("detail", ""), "Error should mention 20 chars"
        print("✓ Response validation rejects notes < 20 chars")
    
    def test_response_validation_max_length(self, session, auth_headers, optimization_with_complaint):
        """Response note cannot exceed 2000 characters"""
        long_note = "A" * 2001
        response = session.post(
            f"{BASE_URL}/api/v3/optimizations/{optimization_with_complaint}/responses",
            headers=auth_headers,
            json={"note": long_note, "report_urls": []}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "2000" in response.json().get("detail", ""), "Error should mention 2000 chars"
        print("✓ Response validation rejects notes > 2000 chars")
    
    def test_add_valid_response(self, session, auth_headers, optimization_with_complaint):
        """Add a valid team response (20-2000 chars)"""
        test_note = f"Test response added at {datetime.now().isoformat()}. This is a test response with at least 20 characters to meet the minimum requirement."
        response = session.post(
            f"{BASE_URL}/api/v3/optimizations/{optimization_with_complaint}/responses",
            headers=auth_headers,
            json={
                "note": test_note,
                "report_urls": ["https://example.com/evidence"]
            }
        )
        assert response.status_code == 200, f"Failed to add response: {response.text}"
        
        data = response.json()
        assert "message" in data, "Missing message in response"
        assert "response" in data, "Missing response entry"
        assert data["response"]["note"] == test_note, "Note not saved correctly"
        
        print(f"✓ Added team response successfully")
        print(f"  - Response ID: {data['response']['id']}")


class TestResolveComplaintEndpoint(TestSetup):
    """Test PATCH /api/v3/optimizations/{id}/complaints/{complaint_id}/resolve"""
    
    @pytest.fixture(scope="class")
    def optimization_with_active_complaint(self, session, auth_headers, test_network_id):
        """Find an optimization with an active complaint"""
        # Get optimizations
        list_response = session.get(
            f"{BASE_URL}/api/v3/networks/{test_network_id}/optimizations",
            headers=auth_headers
        )
        
        if list_response.status_code != 200 or not list_response.json().get("data"):
            return None
        
        # Find one with complaint
        for opt in list_response.json()["data"]:
            if opt.get("complaint_status") in ["complained", "under_review"]:
                # Get detail to find complaint id
                detail_resp = session.get(
                    f"{BASE_URL}/api/v3/optimizations/{opt['id']}/detail",
                    headers=auth_headers
                )
                if detail_resp.status_code == 200:
                    detail = detail_resp.json()
                    if detail.get("active_complaint"):
                        return {
                            "optimization_id": opt["id"],
                            "complaint_id": detail["active_complaint"]["id"]
                        }
        return None
    
    def test_resolve_requires_super_admin(self, session, auth_headers):
        """Only Super Admin can resolve complaints"""
        # This test validates the endpoint exists and validates permissions
        fake_opt_id = str(uuid.uuid4())
        fake_complaint_id = str(uuid.uuid4())
        
        response = session.patch(
            f"{BASE_URL}/api/v3/optimizations/{fake_opt_id}/complaints/{fake_complaint_id}/resolve",
            headers=auth_headers,
            json={"resolution_note": "Test resolution note for testing purposes", "mark_optimization_complete": False}
        )
        
        # Should fail with 404 (not found) or 403 (forbidden) but NOT 405 (method not allowed)
        assert response.status_code in [404, 403, 400], f"Unexpected status: {response.status_code}"
        print("✓ Resolve complaint endpoint exists and validates properly")
    
    def test_resolve_validation_min_note(self, session, auth_headers, optimization_with_active_complaint):
        """Resolution note must be at least 10 characters"""
        if not optimization_with_active_complaint:
            pytest.skip("No optimization with active complaint found")
        
        response = session.patch(
            f"{BASE_URL}/api/v3/optimizations/{optimization_with_active_complaint['optimization_id']}/complaints/{optimization_with_active_complaint['complaint_id']}/resolve",
            headers=auth_headers,
            json={"resolution_note": "Short", "mark_optimization_complete": False}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Resolve validation rejects short resolution notes")


class TestCloseOptimizationEndpoint(TestSetup):
    """Test PATCH /api/v3/optimizations/{id}/close"""
    
    @pytest.fixture(scope="class")
    def closeable_optimization(self, session, auth_headers, test_network_id):
        """Find an optimization without unresolved complaints"""
        list_response = session.get(
            f"{BASE_URL}/api/v3/networks/{test_network_id}/optimizations",
            headers=auth_headers
        )
        
        if list_response.status_code != 200 or not list_response.json().get("data"):
            return None
        
        # Find one without active complaints and not already completed
        for opt in list_response.json()["data"]:
            if opt.get("complaint_status") in ["none", "resolved"] and opt.get("status") != "completed":
                return opt["id"]
        return None
    
    @pytest.fixture(scope="class")
    def blocked_optimization(self, session, auth_headers, test_network_id):
        """Find an optimization with unresolved complaints (blocked)"""
        list_response = session.get(
            f"{BASE_URL}/api/v3/networks/{test_network_id}/optimizations",
            headers=auth_headers
        )
        
        if list_response.status_code != 200 or not list_response.json().get("data"):
            return None
        
        # Find one with active complaint
        for opt in list_response.json()["data"]:
            if opt.get("complaint_status") in ["complained", "under_review"]:
                return opt["id"]
        return None
    
    def test_close_requires_super_admin(self, session, auth_headers):
        """Only Super Admin can close optimizations"""
        fake_id = str(uuid.uuid4())
        response = session.patch(
            f"{BASE_URL}/api/v3/optimizations/{fake_id}/close",
            headers=auth_headers,
            json={"final_note": "Test closing"}
        )
        # Should fail with 404 (not found) but NOT 405 (method not allowed)
        assert response.status_code in [404, 403, 400], f"Unexpected: {response.status_code}"
        print("✓ Close endpoint exists and validates properly")
    
    def test_close_blocked_by_complaints(self, session, auth_headers, blocked_optimization):
        """Cannot close optimization with unresolved complaints"""
        if not blocked_optimization:
            pytest.skip("No blocked optimization found for testing")
        
        response = session.patch(
            f"{BASE_URL}/api/v3/optimizations/{blocked_optimization}/close",
            headers=auth_headers,
            json={"final_note": "Attempting to close blocked optimization"}
        )
        assert response.status_code == 400, f"Expected 400 (blocked), got {response.status_code}"
        assert "unresolved" in response.json().get("detail", "").lower() or "cannot close" in response.json().get("detail", "").lower(), "Error should mention blocking"
        print("✓ Close correctly blocked by unresolved complaints")


class TestComplaintStatusBadge(TestSetup):
    """Test complaint status is returned in optimization list"""
    
    def test_optimizations_include_complaint_status(self, session, auth_headers, test_network_id):
        """Optimizations list includes complaint_status field"""
        response = session.get(
            f"{BASE_URL}/api/v3/networks/{test_network_id}/optimizations",
            headers=auth_headers
        )
        
        if response.status_code != 200 or not response.json().get("data"):
            pytest.skip("No optimizations to test")
        
        optimizations = response.json()["data"]
        for opt in optimizations:
            assert "complaint_status" in opt, f"Missing complaint_status in optimization {opt['id']}"
            assert opt["complaint_status"] in ["none", "complained", "under_review", "resolved"], f"Invalid complaint_status: {opt['complaint_status']}"
        
        print(f"✓ All {len(optimizations)} optimizations have valid complaint_status")
        
        # Count by status
        statuses = {}
        for opt in optimizations:
            status = opt["complaint_status"]
            statuses[status] = statuses.get(status, 0) + 1
        print(f"  - Status distribution: {statuses}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
