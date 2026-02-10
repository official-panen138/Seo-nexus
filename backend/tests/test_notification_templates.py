"""
Test Notification Template System APIs
======================================

Tests for the notification template management system:
- GET /api/v3/settings/notification-templates - list all templates
- GET /api/v3/settings/notification-templates/events - get available event types
- GET /api/v3/settings/notification-templates/variables - get allowed variables
- GET /api/v3/settings/notification-templates/{channel}/{event_type} - get specific template
- PUT /api/v3/settings/notification-templates/{channel}/{event_type} - update template
- POST /api/v3/settings/notification-templates/{channel}/{event_type}/reset - reset to default
- POST /api/v3/settings/notification-templates/{channel}/{event_type}/preview - preview template
- POST /api/v3/settings/notification-templates/validate - validate template body

Permission: Only super_admin can access these APIs
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN = {"email": "admin@test.com", "password": "admin123"}
MANAGER = {"email": "manager@test.com", "password": "manager123"}
VIEWER = {"email": "viewer@test.com", "password": "viewer123"}


@pytest.fixture(scope="module")
def super_admin_token():
    """Get super_admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN)
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Super admin authentication failed")


@pytest.fixture(scope="module")
def manager_token():
    """Get manager authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=MANAGER)
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


@pytest.fixture(scope="module")
def viewer_token():
    """Get viewer authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=VIEWER)
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


def get_headers(token):
    """Helper to create auth headers"""
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


class TestListTemplates:
    """Test GET /api/v3/settings/notification-templates"""
    
    def test_list_templates_super_admin_success(self, super_admin_token):
        """Super admin can list all notification templates"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/notification-templates",
            headers=get_headers(super_admin_token)
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "templates" in data
        templates = data["templates"]
        assert isinstance(templates, list)
        assert len(templates) > 0, "Should have at least one template"
        
        # Verify template structure
        first_template = templates[0]
        assert "channel" in first_template
        assert "event_type" in first_template
        assert "title" in first_template
        assert "template_body" in first_template
        
        print(f"✓ Listed {len(templates)} templates successfully")
    
    def test_list_templates_filter_by_channel(self, super_admin_token):
        """Can filter templates by channel"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/notification-templates?channel=telegram",
            headers=get_headers(super_admin_token)
        )
        
        assert response.status_code == 200
        templates = response.json()["templates"]
        
        # All templates should be telegram channel
        for t in templates:
            assert t["channel"] == "telegram"
        
        print(f"✓ Filtered to {len(templates)} telegram templates")
    
    def test_list_templates_manager_forbidden(self, manager_token):
        """Manager role should get 403"""
        if not manager_token:
            pytest.skip("Manager user not available")
        
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/notification-templates",
            headers=get_headers(manager_token)
        )
        
        assert response.status_code == 403
        print("✓ Manager correctly denied access (403)")
    
    def test_list_templates_viewer_forbidden(self, viewer_token):
        """Viewer role should get 403"""
        if not viewer_token:
            pytest.skip("Viewer user not available")
        
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/notification-templates",
            headers=get_headers(viewer_token)
        )
        
        assert response.status_code == 403
        print("✓ Viewer correctly denied access (403)")


class TestGetTemplateVariables:
    """Test GET /api/v3/settings/notification-templates/variables"""
    
    def test_get_variables_success(self, super_admin_token):
        """Super admin can get allowed template variables"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/notification-templates/variables",
            headers=get_headers(super_admin_token)
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "variables" in data
        variables = data["variables"]
        assert isinstance(variables, dict)
        
        # Check expected variable categories
        expected_categories = ["user", "network", "timestamp"]
        for cat in expected_categories:
            assert cat in variables, f"Missing expected category: {cat}"
        
        print(f"✓ Retrieved {len(variables)} variable categories")
        for cat, vars in variables.items():
            print(f"  - {cat}: {len(vars)} variables")


class TestGetTemplateEvents:
    """Test GET /api/v3/settings/notification-templates/events"""
    
    def test_get_events_success(self, super_admin_token):
        """Super admin can get available event types"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/notification-templates/events",
            headers=get_headers(super_admin_token)
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data
        events = data["events"]
        assert isinstance(events, list)
        assert len(events) > 0
        
        # Check event structure
        first_event = events[0]
        assert "channel" in first_event
        assert "event_type" in first_event
        assert "description" in first_event
        
        # Verify expected event types exist
        event_types = [e["event_type"] for e in events]
        expected = ["seo_change", "seo_optimization", "domain_expiration"]
        for exp in expected:
            assert exp in event_types, f"Missing expected event type: {exp}"
        
        print(f"✓ Retrieved {len(events)} event types")


class TestGetSpecificTemplate:
    """Test GET /api/v3/settings/notification-templates/{channel}/{event_type}"""
    
    def test_get_template_success(self, super_admin_token):
        """Super admin can get a specific template"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/seo_change",
            headers=get_headers(super_admin_token)
        )
        
        assert response.status_code == 200
        template = response.json()
        
        assert template["channel"] == "telegram"
        assert template["event_type"] == "seo_change"
        assert "title" in template
        assert "template_body" in template
        assert "enabled" in template
        
        print(f"✓ Retrieved template: {template['title']}")
    
    def test_get_template_not_found(self, super_admin_token):
        """Non-existent template returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/nonexistent_event",
            headers=get_headers(super_admin_token)
        )
        
        assert response.status_code == 404
        print("✓ Non-existent template correctly returns 404")
    
    def test_get_template_manager_forbidden(self, manager_token):
        """Manager role should get 403 when accessing specific template"""
        if not manager_token:
            pytest.skip("Manager user not available")
        
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/seo_change",
            headers=get_headers(manager_token)
        )
        
        assert response.status_code == 403
        print("✓ Manager correctly denied access to specific template")


class TestUpdateTemplate:
    """Test PUT /api/v3/settings/notification-templates/{channel}/{event_type}"""
    
    def test_update_template_title(self, super_admin_token):
        """Super admin can update template title"""
        # First get original template
        original_response = requests.get(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/test",
            headers=get_headers(super_admin_token)
        )
        
        if original_response.status_code != 200:
            pytest.skip("Test template not available")
        
        original = original_response.json()
        
        # Update title
        new_title = "TEST_Updated Test Notification"
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/test",
            headers=get_headers(super_admin_token),
            json={"title": new_title}
        )
        
        assert response.status_code == 200
        updated = response.json()
        assert updated["title"] == new_title
        
        # Verify persistence
        verify_response = requests.get(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/test",
            headers=get_headers(super_admin_token)
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["title"] == new_title
        
        print(f"✓ Updated template title: {original.get('title')} -> {new_title}")
        
        # Cleanup: restore original
        requests.put(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/test",
            headers=get_headers(super_admin_token),
            json={"title": original.get("title", "Test Notification")}
        )
    
    def test_update_template_enabled_status(self, super_admin_token):
        """Super admin can enable/disable template"""
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/test",
            headers=get_headers(super_admin_token),
            json={"enabled": False}
        )
        
        assert response.status_code == 200
        assert response.json()["enabled"] == False
        
        # Re-enable
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/test",
            headers=get_headers(super_admin_token),
            json={"enabled": True}
        )
        
        assert response.status_code == 200
        assert response.json()["enabled"] == True
        
        print("✓ Template enable/disable works correctly")
    
    def test_update_template_body(self, super_admin_token):
        """Super admin can update template body"""
        new_body = "TEST Body - {{user.display_name}} updated at {{timestamp.gmt7}}"
        
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/test",
            headers=get_headers(super_admin_token),
            json={"template_body": new_body}
        )
        
        assert response.status_code == 200
        updated = response.json()
        assert updated["template_body"] == new_body
        
        print("✓ Template body updated successfully")
    
    def test_update_template_invalid_variables_rejected(self, super_admin_token):
        """Template with invalid variables should be rejected"""
        invalid_body = "Hello {{invalid.variable}} and {{another.bad.var}}"
        
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/test",
            headers=get_headers(super_admin_token),
            json={"template_body": invalid_body}
        )
        
        # Should fail validation
        assert response.status_code == 400
        assert "invalid" in response.json().get("detail", "").lower()
        
        print("✓ Invalid variables correctly rejected")
    
    def test_update_template_manager_forbidden(self, manager_token):
        """Manager role should get 403 when updating template"""
        if not manager_token:
            pytest.skip("Manager user not available")
        
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/test",
            headers=get_headers(manager_token),
            json={"title": "Should Fail"}
        )
        
        assert response.status_code == 403
        print("✓ Manager correctly denied update access")


class TestPreviewTemplate:
    """Test POST /api/v3/settings/notification-templates/{channel}/{event_type}/preview"""
    
    def test_preview_template_success(self, super_admin_token):
        """Super admin can preview a template with sample data"""
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/seo_change/preview",
            headers=get_headers(super_admin_token),
            json={}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "preview" in data
        preview = data["preview"]
        assert isinstance(preview, str)
        assert len(preview) > 0
        
        # Preview should have sample data substituted, not raw variables
        assert "{{user.display_name}}" not in preview
        assert "John Doe" in preview or "john" in preview.lower()
        
        print("✓ Template preview generated with sample data")
        print(f"  Preview length: {len(preview)} characters")
    
    def test_preview_custom_body(self, super_admin_token):
        """Can preview custom template body without saving"""
        custom_body = "Custom preview: {{user.display_name}} at {{timestamp.gmt7}}"
        
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/test/preview",
            headers=get_headers(super_admin_token),
            json={"template_body": custom_body}
        )
        
        assert response.status_code == 200
        preview = response.json()["preview"]
        
        # Should substitute variables
        assert "Custom preview:" in preview
        assert "{{user.display_name}}" not in preview
        assert "{{timestamp.gmt7}}" not in preview
        
        print("✓ Custom body preview works correctly")
    
    def test_preview_template_not_found(self, super_admin_token):
        """Preview for non-existent template returns error"""
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/nonexistent/preview",
            headers=get_headers(super_admin_token),
            json={}
        )
        
        assert response.status_code == 400 or response.status_code == 404
        print("✓ Non-existent template preview correctly fails")


class TestValidateTemplate:
    """Test POST /api/v3/settings/notification-templates/validate"""
    
    def test_validate_valid_template(self, super_admin_token):
        """Valid template body passes validation"""
        valid_body = "Hello {{user.display_name}}, network {{network.name}} updated at {{timestamp.gmt7}}"
        
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/notification-templates/validate",
            headers=get_headers(super_admin_token),
            json={"template_body": valid_body}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] == True
        assert len(data["invalid_variables"]) == 0
        
        print("✓ Valid template passes validation")
    
    def test_validate_invalid_template(self, super_admin_token):
        """Template with invalid variables fails validation"""
        invalid_body = "Hello {{invalid.variable}} and {{unknown.thing}}"
        
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/notification-templates/validate",
            headers=get_headers(super_admin_token),
            json={"template_body": invalid_body}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] == False
        assert "invalid.variable" in data["invalid_variables"]
        assert "unknown.thing" in data["invalid_variables"]
        
        print(f"✓ Invalid variables detected: {data['invalid_variables']}")
    
    def test_validate_mixed_template(self, super_admin_token):
        """Template with mixed valid/invalid variables"""
        mixed_body = "User: {{user.display_name}}, Invalid: {{bad.var}}"
        
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/notification-templates/validate",
            headers=get_headers(super_admin_token),
            json={"template_body": mixed_body}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["valid"] == False
        assert "bad.var" in data["invalid_variables"]
        
        print("✓ Mixed template correctly identifies invalid variables only")
    
    def test_validate_empty_body_rejected(self, super_admin_token):
        """Empty template body should be rejected"""
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/notification-templates/validate",
            headers=get_headers(super_admin_token),
            json={"template_body": ""}
        )
        
        assert response.status_code == 400
        print("✓ Empty template body correctly rejected")


class TestResetTemplate:
    """Test POST /api/v3/settings/notification-templates/{channel}/{event_type}/reset"""
    
    def test_reset_template_to_default(self, super_admin_token):
        """Super admin can reset template to default"""
        # First modify the template
        modified_body = "TEST_Modified body for reset test"
        requests.put(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/test",
            headers=get_headers(super_admin_token),
            json={"template_body": modified_body}
        )
        
        # Verify modification
        verify_response = requests.get(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/test",
            headers=get_headers(super_admin_token)
        )
        assert verify_response.json()["template_body"] == modified_body
        
        # Reset to default
        reset_response = requests.post(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/test/reset",
            headers=get_headers(super_admin_token)
        )
        
        assert reset_response.status_code == 200
        reset_template = reset_response.json()
        
        # Should have default content (not modified)
        assert reset_template["template_body"] != modified_body
        assert "default_template_body" in reset_template or "PESAN TEST" in reset_template["template_body"]
        
        print("✓ Template reset to default successfully")
    
    def test_reset_nonexistent_template_fails(self, super_admin_token):
        """Reset for non-existent event type should fail"""
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/nonexistent_event/reset",
            headers=get_headers(super_admin_token)
        )
        
        assert response.status_code == 400
        print("✓ Reset for non-existent template correctly fails")
    
    def test_reset_template_manager_forbidden(self, manager_token):
        """Manager role should get 403 when resetting template"""
        if not manager_token:
            pytest.skip("Manager user not available")
        
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/notification-templates/telegram/test/reset",
            headers=get_headers(manager_token)
        )
        
        assert response.status_code == 403
        print("✓ Manager correctly denied reset access")


class TestPermissionEnforcement:
    """Test that only super_admin can access template APIs"""
    
    def test_all_endpoints_require_super_admin(self, manager_token, viewer_token):
        """All template endpoints should require super_admin role"""
        endpoints = [
            ("GET", "/api/v3/settings/notification-templates"),
            ("GET", "/api/v3/settings/notification-templates/events"),
            ("GET", "/api/v3/settings/notification-templates/variables"),
            ("GET", "/api/v3/settings/notification-templates/telegram/test"),
            ("PUT", "/api/v3/settings/notification-templates/telegram/test"),
            ("POST", "/api/v3/settings/notification-templates/telegram/test/reset"),
            ("POST", "/api/v3/settings/notification-templates/telegram/test/preview"),
            ("POST", "/api/v3/settings/notification-templates/validate"),
        ]
        
        tokens = []
        if manager_token:
            tokens.append(("manager", manager_token))
        if viewer_token:
            tokens.append(("viewer", viewer_token))
        
        if not tokens:
            pytest.skip("No non-admin tokens available")
        
        for role_name, token in tokens:
            for method, path in endpoints:
                headers = get_headers(token)
                url = f"{BASE_URL}{path}"
                
                if method == "GET":
                    response = requests.get(url, headers=headers)
                elif method == "PUT":
                    response = requests.put(url, headers=headers, json={})
                elif method == "POST":
                    response = requests.post(url, headers=headers, json={"template_body": "test"})
                
                assert response.status_code == 403, f"{role_name} should get 403 for {method} {path}, got {response.status_code}"
        
        print(f"✓ All endpoints correctly restrict access to non-super_admin users")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
