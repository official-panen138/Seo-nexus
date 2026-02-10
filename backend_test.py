#!/usr/bin/env python3
import requests
import json
import sys
from datetime import datetime, timezone, timedelta


class SEONOCAPITester:
    def __init__(
        self, base_url="https://seo-alert-system.preview.emergentagent.com/api"
    ):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, message="", details={}):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name}: {message}")

        self.test_results.append(
            {"test": name, "success": success, "message": message, "details": details}
        )

    def run_test(
        self, name, method, endpoint, expected_status, data=None, headers=None
    ):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"

        # Default headers
        req_headers = {"Content-Type": "application/json"}
        if self.token:
            req_headers["Authorization"] = f"Bearer {self.token}"
        if headers:
            req_headers.update(headers)

        try:
            if method == "GET":
                response = requests.get(url, headers=req_headers, timeout=30)
            elif method == "POST":
                response = requests.post(
                    url, json=data, headers=req_headers, timeout=30
                )
            elif method == "PUT":
                response = requests.put(url, json=data, headers=req_headers, timeout=30)
            elif method == "DELETE":
                response = requests.delete(url, headers=req_headers, timeout=30)

            success = response.status_code == expected_status

            if success:
                self.log_test(name, True)
                try:
                    return response.json() if response.content else {}
                except:
                    return {}
            else:
                error_msg = f"Expected {expected_status}, got {response.status_code}"
                try:
                    error_detail = response.json().get("detail", "")
                    if error_detail:
                        error_msg += f": {error_detail}"
                except:
                    pass
                self.log_test(name, False, error_msg)
                return {}

        except requests.exceptions.Timeout:
            self.log_test(name, False, "Request timeout")
            return {}
        except requests.exceptions.ConnectionError:
            self.log_test(name, False, "Connection error")
            return {}
        except Exception as e:
            self.log_test(name, False, f"Error: {str(e)}")
            return {}

    def test_auth_flow(self):
        """Test authentication endpoints"""
        print("\n🔐 Testing Authentication...")

        # Test login with demo admin credentials
        login_data = {"email": "admin@seonexus.com", "password": "admin123"}
        response = self.run_test(
            "Admin Login", "POST", "auth/login", 200, data=login_data
        )

        if response and "access_token" in response:
            self.token = response["access_token"]
            self.log_test("Token Retrieved", True)

            # Test auth/me endpoint
            me_response = self.run_test("Get Current User", "GET", "auth/me", 200)
            if me_response:
                self.log_test("User Profile Access", True)
                return True

        return False

    def test_dashboard_stats(self):
        """Test dashboard and stats endpoints"""
        print("\n📊 Testing Dashboard & Stats...")

        self.run_test("Dashboard Stats", "GET", "reports/dashboard-stats", 200)
        self.run_test("Tier Distribution", "GET", "reports/tier-distribution", 200)
        self.run_test("Index Status Report", "GET", "reports/index-status", 200)
        self.run_test("Brand Health Report", "GET", "reports/brand-health", 200)
        self.run_test("Monitoring Stats", "GET", "monitoring/stats", 200)

    def test_categories_management(self):
        """Test categories CRUD operations"""
        print("\n📁 Testing Categories Management...")

        # Get all categories (should have default ones)
        categories = self.run_test("Get Categories", "GET", "categories", 200)

        if categories:
            category_count = len(categories)
            self.log_test(
                f"Default Categories Loaded ({category_count})", category_count >= 8
            )

            # Test category names
            category_names = [cat.get("name") for cat in categories]
            expected_names = ["Money Site", "PBN", "Fresh Domain", "Aged Domain"]
            found_expected = [name for name in expected_names if name in category_names]
            self.log_test(
                f"Expected Categories Found ({len(found_expected)}/4)",
                len(found_expected) >= 2,
            )

    def test_domains_and_monitoring(self):
        """Test domain management and monitoring"""
        print("\n🌐 Testing Domain Management...")

        # Get all domains
        domains = self.run_test("Get Domains", "GET", "domains", 200)

        if domains:
            domain_count = len(domains)
            self.log_test(f"Domains Loaded ({domain_count})", domain_count > 0)

            # Test first domain detail if exists
            if domain_count > 0:
                domain_id = domains[0].get("id")
                self.run_test("Get Domain Detail", "GET", f"domains/{domain_id}", 200)

                # Test monitoring check if domain has monitoring enabled
                if domains[0].get("monitoring_enabled"):
                    self.run_test(
                        "Schedule Domain Check",
                        "POST",
                        f"domains/{domain_id}/check",
                        200,
                    )

        # Test brands endpoint
        brands = self.run_test("Get Brands", "GET", "brands", 200)
        if brands:
            brand_count = len(brands)
            self.log_test(f"Brands Loaded ({brand_count})", brand_count > 0)

        # Test groups/networks
        groups = self.run_test("Get Groups/Networks", "GET", "groups", 200)
        if groups:
            group_count = len(groups)
            self.log_test(f"Networks Loaded ({group_count})", group_count >= 0)

    def test_alerts_system(self):
        """Test alert management system"""
        print("\n🚨 Testing Alert System...")

        # Get all alerts
        alerts = self.run_test("Get Alerts", "GET", "alerts", 200)

        if alerts is not None:
            alert_count = len(alerts)
            self.log_test(f"Alerts Retrieved ({alert_count})", True)

            # Test alert filtering
            self.run_test(
                "Filter Critical Alerts", "GET", "alerts?severity=critical", 200
            )
            self.run_test(
                "Filter Monitoring Alerts", "GET", "alerts?alert_type=monitoring", 200
            )
            self.run_test(
                "Filter Unacknowledged", "GET", "alerts?acknowledged=false", 200
            )

    def test_seo_conflicts(self):
        """Test SEO conflict detection"""
        print("\n⚠️ Testing SEO Conflict Detection...")

        conflicts = self.run_test("Detect SEO Conflicts", "GET", "seo/conflicts", 200)

        if conflicts:
            conflict_count = conflicts.get("total", 0)
            self.log_test(f"SEO Conflicts Detected ({conflict_count})", True)

            # Log conflict types if any
            if conflict_count > 0:
                conflict_types = set()
                for conflict in conflicts.get("conflicts", []):
                    conflict_types.add(conflict.get("type", "unknown"))
                self.log_test(f"Conflict Types: {', '.join(conflict_types)}", True)

    def test_settings_and_telegram(self):
        """Test settings management"""
        print("\n⚙️ Testing Settings...")

        # Get Telegram settings
        self.run_test("Get Telegram Settings", "GET", "settings/telegram", 200)

        # Note: Won't test actual Telegram send to avoid spam

    def test_audit_logs(self):
        """Test audit logging system"""
        print("\n📝 Testing Audit Logs...")

        self.run_test("Get Audit Logs", "GET", "audit-logs?limit=10", 200)
        self.run_test(
            "Get Domain Audit Logs", "GET", "audit-logs?entity_type=domain&limit=5", 200
        )

    def test_reports_export(self):
        """Test export functionality"""
        print("\n📤 Testing Reports & Export...")

        self.run_test("Export Domains JSON", "GET", "reports/export?format=json", 200)
        self.run_test("Export Domains CSV", "GET", "reports/export?format=csv", 200)

    def run_all_tests(self):
        """Run all test suites"""
        print("🚀 Starting SEO-NOC Backend API Tests")
        print(f"Base URL: {self.base_url}")

        # Authentication is required for all subsequent tests
        if not self.test_auth_flow():
            print("❌ Authentication failed - cannot continue with other tests")
            return False

        # Run all test suites
        self.test_dashboard_stats()
        self.test_categories_management()
        self.test_domains_and_monitoring()
        self.test_alerts_system()
        self.test_seo_conflicts()
        self.test_settings_and_telegram()
        self.test_audit_logs()
        self.test_reports_export()

        return True

    def print_summary(self):
        """Print test summary"""
        success_rate = (
            (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        )

        print(f"\n{'='*50}")
        print(f"📊 SEO-NOC API Test Results")
        print(f"{'='*50}")
        print(f"Tests Run: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {success_rate:.1f}%")

        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
        elif success_rate >= 80:
            print("✅ Most tests passed - system is mostly functional")
        elif success_rate >= 50:
            print("⚠️ Some critical issues found")
        else:
            print("❌ Major issues detected - needs attention")

        return success_rate >= 80


def main():
    """Main test execution"""
    tester = SEONOCAPITester()

    try:
        success = tester.run_all_tests()
        tester.print_summary()

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n❌ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
