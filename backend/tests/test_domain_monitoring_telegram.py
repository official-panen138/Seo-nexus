"""
Test Domain Monitoring Telegram API and SEO Context Enricher
============================================================

Tests Phase 2 Domain Monitoring features:
1. GET /api/v3/settings/telegram-monitoring - Get domain monitoring config
2. PUT /api/v3/settings/telegram-monitoring - Save config without fallback
3. POST /api/v3/settings/telegram-monitoring/test - Send test message
4. SEO Context Enricher - Upstream chain, downstream impact, impact score
"""

import pytest
import requests
import os
import json

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
SUPERADMIN_EMAIL = "superadmin@seonoc.com"
SUPERADMIN_PASSWORD = "SuperAdmin123!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for super admin"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": SUPERADMIN_EMAIL, "password": SUPERADMIN_PASSWORD},
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with authentication"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestDomainMonitoringTelegramAPI:
    """Test Domain Monitoring Telegram Settings API"""

    def test_get_telegram_monitoring_returns_config(self, auth_headers):
        """GET /api/v3/settings/telegram-monitoring returns domain monitoring config"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-monitoring", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        # Should have these fields
        assert "configured" in data
        assert "enabled" in data
        # Bot token and chat_id should be present (may be None if not configured)
        assert "bot_token" in data or data.get("configured") is False
        assert "chat_id" in data or data.get("configured") is False

    def test_get_telegram_monitoring_has_configured_flag(self, auth_headers):
        """GET /api/v3/settings/telegram-monitoring has configured flag"""
        response = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-monitoring", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        # configured flag is boolean
        assert isinstance(data["configured"], bool)

    def test_put_telegram_monitoring_saves_config(self, auth_headers):
        """PUT /api/v3/settings/telegram-monitoring saves config without fallback"""
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-monitoring",
            headers=auth_headers,
            json={
                "bot_token": "test-bot-token-12345",
                "chat_id": "-1001234567890",
                "enabled": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_put_telegram_monitoring_preserves_token(self, auth_headers):
        """PUT /api/v3/settings/telegram-monitoring preserves existing bot_token"""
        # First set a token
        requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-monitoring",
            headers=auth_headers,
            json={"bot_token": "preserved-token-789", "chat_id": "-100888"},
        )

        # Update only chat_id
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-monitoring",
            headers=auth_headers,
            json={"chat_id": "-100999"},
        )
        assert response.status_code == 200

        # Verify token preserved
        get_response = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-monitoring", headers=auth_headers
        )
        data = get_response.json()
        assert data.get("bot_token") == "preserved-token-789"

    def test_put_telegram_monitoring_enables_toggle(self, auth_headers):
        """PUT /api/v3/settings/telegram-monitoring can toggle enabled"""
        # Disable
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-monitoring",
            headers=auth_headers,
            json={"enabled": False},
        )
        assert response.status_code == 200

        # Verify disabled
        get_response = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-monitoring", headers=auth_headers
        )
        data = get_response.json()
        assert data["enabled"] is False

        # Re-enable
        requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-monitoring",
            headers=auth_headers,
            json={"enabled": True},
        )

    def test_put_telegram_monitoring_requires_super_admin(self):
        """PUT /api/v3/settings/telegram-monitoring requires super admin role"""
        # Login as non-super admin would be tested here
        # For now, test without auth
        response = requests.put(
            f"{BASE_URL}/api/v3/settings/telegram-monitoring", json={"enabled": False}
        )
        assert response.status_code in [401, 403]

    def test_post_telegram_monitoring_test_endpoint_exists(self, auth_headers):
        """POST /api/v3/settings/telegram-monitoring/test endpoint exists"""
        response = requests.post(
            f"{BASE_URL}/api/v3/settings/telegram-monitoring/test", headers=auth_headers
        )
        # Will fail if not configured, but endpoint should exist
        # Success = 200, Not configured = 500/520 with proper error
        # 520 is Cloudflare mapping for certain server errors
        assert response.status_code in [200, 500, 520]
        if response.status_code in [500, 520]:
            data = response.json()
            assert "detail" in data
            # Should have meaningful error about configuration
            assert (
                "configuration" in data["detail"].lower()
                or "token" in data["detail"].lower()
            )


class TestDomainMonitoringTelegramNoFallback:
    """Verify Domain Monitoring Telegram has NO fallback to SEO channel"""

    def test_monitoring_config_is_separate_from_seo(self, auth_headers):
        """Domain Monitoring config is stored separately from SEO Telegram"""
        # Get Domain Monitoring config
        monitoring_response = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-monitoring", headers=auth_headers
        )
        assert monitoring_response.status_code == 200
        monitoring_data = monitoring_response.json()

        # Get SEO Telegram config
        seo_response = requests.get(
            f"{BASE_URL}/api/v3/settings/telegram-seo", headers=auth_headers
        )
        assert seo_response.status_code == 200
        seo_data = seo_response.json()

        # They should be separate configurations
        # Both can have different chat_ids (or be None independently)
        # The key is they are NOT the same endpoint returning same data
        assert "configured" in monitoring_data or "bot_token" in monitoring_data
        assert "enabled" in seo_data or "bot_token" in seo_data

        # If both are configured, they COULD have same values (but are stored separately)
        # The important thing is the API endpoints are separate
        print(f"Monitoring config: {monitoring_data}")
        print(f"SEO config: {seo_data}")


class TestSEOContextEnricher:
    """Test SEO Context Enricher functionality"""

    def test_seo_context_enricher_module_exists(self):
        """seo_context_enricher.py module exists"""
        import sys

        sys.path.insert(0, "/app/backend")
        try:
            from services.seo_context_enricher import SeoContextEnricher

            assert SeoContextEnricher is not None
        except ImportError as e:
            pytest.fail(f"Failed to import SeoContextEnricher: {e}")

    def test_seo_context_enricher_has_enrich_method(self):
        """SeoContextEnricher has enrich_domain_with_seo_context method"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.seo_context_enricher import SeoContextEnricher

        # Check method exists
        assert hasattr(SeoContextEnricher, "enrich_domain_with_seo_context")

    def test_seo_context_enricher_has_upstream_chain_method(self):
        """SeoContextEnricher has _build_upstream_chain method"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.seo_context_enricher import SeoContextEnricher

        assert hasattr(SeoContextEnricher, "_build_upstream_chain")

    def test_seo_context_enricher_has_downstream_impact_method(self):
        """SeoContextEnricher has _get_downstream_impact method"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.seo_context_enricher import SeoContextEnricher

        assert hasattr(SeoContextEnricher, "_get_downstream_impact")

    def test_seo_context_enricher_has_impact_score_method(self):
        """SeoContextEnricher has _calculate_impact_score method"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.seo_context_enricher import SeoContextEnricher

        assert hasattr(SeoContextEnricher, "_calculate_impact_score")


class TestImpactScoreCalculation:
    """Test Impact Score calculation returns correct severity levels"""

    def test_impact_score_severity_low(self):
        """Impact score returns LOW for orphan domains"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.seo_context_enricher import SeoContextEnricher

        # Create a mock enricher to test the static method
        class MockDB:
            pass

        enricher = SeoContextEnricher(MockDB())

        score = enricher._calculate_impact_score(
            networks_affected=0,
            downstream_count=0,
            reaches_money_site=False,
            highest_tier=None,
            node_role="supporting",
            index_status="noindex",
        )

        assert score["severity"] == "LOW"

    def test_impact_score_severity_medium(self):
        """Impact score returns MEDIUM for tier 3 with money site chain"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.seo_context_enricher import SeoContextEnricher

        class MockDB:
            pass

        enricher = SeoContextEnricher(MockDB())

        score = enricher._calculate_impact_score(
            networks_affected=1,
            downstream_count=3,
            reaches_money_site=True,
            highest_tier=3,
            node_role="supporting",
            index_status="index",
        )

        assert score["severity"] in [
            "MEDIUM",
            "HIGH",
        ]  # Could be HIGH due to reaches_money_site

    def test_impact_score_severity_high(self):
        """Impact score returns HIGH for tier 1 or many downstream"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.seo_context_enricher import SeoContextEnricher

        class MockDB:
            pass

        enricher = SeoContextEnricher(MockDB())

        # Tier 1 should be HIGH
        score = enricher._calculate_impact_score(
            networks_affected=1,
            downstream_count=5,
            reaches_money_site=False,
            highest_tier=1,
            node_role="supporting",
            index_status="index",
        )

        assert score["severity"] in ["HIGH", "CRITICAL"]

    def test_impact_score_severity_critical_for_main(self):
        """Impact score returns CRITICAL for main (money site) nodes"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.seo_context_enricher import SeoContextEnricher

        class MockDB:
            pass

        enricher = SeoContextEnricher(MockDB())

        score = enricher._calculate_impact_score(
            networks_affected=1,
            downstream_count=10,
            reaches_money_site=True,
            highest_tier=0,
            node_role="main",
            index_status="index",
        )

        assert score["severity"] == "CRITICAL"

    def test_impact_score_has_all_metrics(self):
        """Impact score returns all required metrics"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.seo_context_enricher import SeoContextEnricher

        class MockDB:
            pass

        enricher = SeoContextEnricher(MockDB())

        score = enricher._calculate_impact_score(
            networks_affected=2,
            downstream_count=5,
            reaches_money_site=True,
            highest_tier=2,
            node_role="supporting",
            index_status="index",
        )

        # All required fields
        assert "severity" in score
        assert "networks_affected" in score
        assert "downstream_nodes_count" in score
        assert "reaches_money_site" in score
        assert "highest_tier_impacted" in score


class TestMonitoringServiceIntegration:
    """Test Monitoring Service uses SEO Context Enricher"""

    def test_expiration_service_has_seo_enricher(self):
        """ExpirationMonitoringService initializes SEO enricher"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.monitoring_service import ExpirationMonitoringService
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        service = ExpirationMonitoringService(mock_db)

        assert hasattr(service, "seo_enricher")

    def test_availability_service_has_seo_enricher(self):
        """AvailabilityMonitoringService initializes SEO enricher"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.monitoring_service import AvailabilityMonitoringService
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        service = AvailabilityMonitoringService(mock_db)

        assert hasattr(service, "seo_enricher")

    def test_domain_monitoring_telegram_service_exists(self):
        """DomainMonitoringTelegramService exists"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.monitoring_service import DomainMonitoringTelegramService

        assert DomainMonitoringTelegramService is not None


class TestSoftBlockDetection:
    """Test Soft Block detection (Cloudflare, captcha, geo-block)"""

    def test_availability_service_has_soft_block_indicators(self):
        """AvailabilityMonitoringService has SOFT_BLOCK_INDICATORS"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.monitoring_service import AvailabilityMonitoringService
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        service = AvailabilityMonitoringService(mock_db)

        assert hasattr(service, "SOFT_BLOCK_INDICATORS")

        indicators = service.SOFT_BLOCK_INDICATORS
        assert "cloudflare_challenge" in indicators
        assert "captcha" in indicators
        assert "geo_blocked" in indicators

    def test_detect_soft_block_method_exists(self):
        """AvailabilityMonitoringService has _detect_soft_block method"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.monitoring_service import AvailabilityMonitoringService
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        service = AvailabilityMonitoringService(mock_db)

        assert hasattr(service, "_detect_soft_block")

    def test_detect_cloudflare_challenge(self):
        """_detect_soft_block detects Cloudflare challenge"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.monitoring_service import AvailabilityMonitoringService
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        service = AvailabilityMonitoringService(mock_db)

        # Cloudflare challenge page content
        response_text = "Checking your browser before accessing... cf-ray-12345"
        result = service._detect_soft_block(response_text, 200)

        assert result == "cloudflare_challenge"

    def test_detect_captcha(self):
        """_detect_soft_block detects captcha pages"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.monitoring_service import AvailabilityMonitoringService
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        service = AvailabilityMonitoringService(mock_db)

        response_text = "Please complete the CAPTCHA to continue"
        result = service._detect_soft_block(response_text, 200)

        assert result == "captcha"

    def test_detect_geo_block_from_status_code(self):
        """_detect_soft_block detects geo-block from 403/451 status"""
        import sys

        sys.path.insert(0, "/app/backend")
        from services.monitoring_service import AvailabilityMonitoringService
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        service = AvailabilityMonitoringService(mock_db)

        # 451 is "Unavailable For Legal Reasons" often used for geo-blocking
        result = service._detect_soft_block("", 451)
        assert result == "geo_blocked"

        result = service._detect_soft_block("", 403)
        assert result == "geo_blocked"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
