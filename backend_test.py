import requests
import json
import sys
from datetime import datetime

class SEONetworkAPITester:
    def __init__(self, base_url="https://network-mapper-pro.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.user = None
        self.tests_run = 0
        self.tests_passed = 0
        self.created_entities = {
            'brands': [],
            'groups': [],
            'domains': [],
            'users': []
        }

    def run_test(self, name, method, endpoint, expected_status, data=None, description=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        if description:
            print(f"   {description}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            print(f"   URL: {url}")
            print(f"   Status: {response.status_code} (expected: {expected_status})")

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ PASSED")
                try:
                    return True, response.json() if response.text else {}
                except:
                    return True, {}
            else:
                print(f"❌ FAILED - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                    return False, error_data
                except:
                    print(f"   Error text: {response.text}")
                    return False, {'error': response.text}

        except Exception as e:
            print(f"❌ FAILED - Exception: {str(e)}")
            return False, {'error': str(e)}

    def test_user_registration(self):
        """Test user registration - first user becomes super_admin"""
        timestamp = datetime.now().strftime('%H%M%S')
        user_data = {
            "email": f"admin{timestamp}@example.com",
            "name": f"Admin User {timestamp}",
            "password": "SecurePass123!"
        }
        
        success, response = self.run_test(
            "User Registration (Super Admin)", 
            "POST", 
            "auth/register", 
            200, 
            user_data,
            "First user should become super_admin"
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user = response['user']
            print(f"   Registered user role: {self.user.get('role')}")
            print(f"   Token obtained: {self.token[:20]}...")
            return True
        return False

    def test_user_login(self):
        """Test user login"""
        if not self.user:
            print("❌ Cannot test login - no user registered")
            return False

        login_data = {
            "email": self.user['email'],
            "password": "SecurePass123!"
        }
        
        success, response = self.run_test(
            "User Login", 
            "POST", 
            "auth/login", 
            200, 
            login_data
        )
        
        if success and 'access_token' in response:
            # Update token in case it's different
            self.token = response['access_token']
            print(f"   Login successful, role: {response['user'].get('role')}")
            return True
        return False

    def test_get_me(self):
        """Test get current user endpoint"""
        success, response = self.run_test(
            "Get Current User", 
            "GET", 
            "auth/me", 
            200
        )
        
        if success:
            print(f"   Current user: {response.get('name')} ({response.get('role')})")
            return True
        return False

    def test_dashboard_stats(self):
        """Test dashboard stats endpoint"""
        success, response = self.run_test(
            "Dashboard Stats", 
            "GET", 
            "reports/dashboard-stats", 
            200
        )
        
        if success:
            stats = response
            print(f"   Total domains: {stats.get('total_domains', 0)}")
            print(f"   Total groups: {stats.get('total_groups', 0)}")
            print(f"   Total brands: {stats.get('total_brands', 0)}")
            return True
        return False

    def test_seed_data(self):
        """Test seeding demo data (super_admin only)"""
        success, response = self.run_test(
            "Seed Demo Data", 
            "POST", 
            "seed-data", 
            200,
            description="Creates sample brands, groups, and domains"
        )
        
        if success:
            print(f"   Seeded: {response.get('message', 'Data seeded successfully')}")
            return True
        return False

    def test_brands_crud(self):
        """Test brands CRUD operations"""
        print("\n📋 Testing Brands CRUD...")
        
        # Get all brands
        success, brands = self.run_test("Get All Brands", "GET", "brands", 200)
        if not success:
            return False
        print(f"   Found {len(brands)} existing brands")
        
        # Create new brand
        brand_data = {
            "name": f"Test Brand {datetime.now().strftime('%H%M%S')}",
            "description": "Test brand for API testing"
        }
        success, brand = self.run_test("Create Brand", "POST", "brands", 200, brand_data)
        if success and 'id' in brand:
            self.created_entities['brands'].append(brand['id'])
            print(f"   Created brand ID: {brand['id']}")
            
            # Update brand
            updated_data = {**brand_data, "description": "Updated test brand description"}
            success, _ = self.run_test(f"Update Brand", "PUT", f"brands/{brand['id']}", 200, updated_data)
            if success:
                print(f"   Brand updated successfully")
                return True
        
        return False

    def test_groups_crud(self):
        """Test groups/networks CRUD operations"""
        print("\n🔗 Testing Groups/Networks CRUD...")
        
        # Get all groups
        success, groups = self.run_test("Get All Groups", "GET", "groups", 200)
        if not success:
            return False
        print(f"   Found {len(groups)} existing groups")
        
        # Create new group
        group_data = {
            "name": f"Test Network {datetime.now().strftime('%H%M%S')}",
            "description": "Test network for API testing"
        }
        success, group = self.run_test("Create Group", "POST", "groups", 200, group_data)
        if success and 'id' in group:
            self.created_entities['groups'].append(group['id'])
            print(f"   Created group ID: {group['id']}")
            
            # Get specific group
            success, group_detail = self.run_test(f"Get Group Detail", "GET", f"groups/{group['id']}", 200)
            if success and 'domains' in group_detail:
                print(f"   Group detail loaded with {len(group_detail['domains'])} domains")
                return True
        
        return False

    def test_domains_crud(self):
        """Test domains CRUD operations"""
        print("\n🌐 Testing Domains CRUD...")
        
        # Get all domains first
        success, domains = self.run_test("Get All Domains", "GET", "domains", 200)
        if not success:
            return False
        print(f"   Found {len(domains)} existing domains")
        
        # Need a brand to create domain
        if not self.created_entities['brands']:
            print("   ❌ Cannot test domain creation - no brands available")
            return False
        
        brand_id = self.created_entities['brands'][0]
        group_id = self.created_entities['groups'][0] if self.created_entities['groups'] else None
        
        # Create domain
        domain_data = {
            "domain_name": f"test{datetime.now().strftime('%H%M%S')}.example.com",
            "brand_id": brand_id,
            "domain_status": "canonical",
            "index_status": "index",
            "tier_level": "tier_3",
            "group_id": group_id,
            "notes": "Test domain for API testing"
        }
        
        success, domain = self.run_test("Create Domain", "POST", "domains", 201, domain_data)
        if success and 'id' in domain:
            self.created_entities['domains'].append(domain['id'])
            print(f"   Created domain ID: {domain['id']}")
            
            # Get specific domain
            success, domain_detail = self.run_test(f"Get Domain Detail", "GET", f"domains/{domain['id']}", 200)
            if success:
                print(f"   Domain detail: {domain_detail.get('domain_name')} ({domain_detail.get('tier_level')})")
                
                # Update domain
                update_data = {"index_status": "noindex", "notes": "Updated test domain"}
                success, _ = self.run_test(f"Update Domain", "PUT", f"domains/{domain['id']}", 200, update_data)
                if success:
                    print(f"   Domain updated successfully")
                    return True
        
        return False

    def test_reports(self):
        """Test various report endpoints"""
        print("\n📊 Testing Reports...")
        
        # Tier distribution
        success, tier_data = self.run_test("Tier Distribution Report", "GET", "reports/tier-distribution", 200)
        if success:
            print(f"   Tier distribution: {len(tier_data)} tier levels")
        
        # Index status report
        success, index_data = self.run_test("Index Status Report", "GET", "reports/index-status", 200)
        if success:
            print(f"   Index status: {len(index_data)} status types")
        
        # Brand health
        success, health_data = self.run_test("Brand Health Report", "GET", "reports/brand-health", 200)
        if success:
            print(f"   Brand health: {len(health_data)} brands analyzed")
        
        # Export data
        success, export_data = self.run_test("Export Domains (JSON)", "GET", "reports/export?format=json", 200)
        if success and 'data' in export_data:
            print(f"   JSON export: {len(export_data['data'])} domains exported")
            return True
        
        return False

    def test_user_management(self):
        """Test user management (super_admin only)"""
        print("\n👥 Testing User Management...")
        
        # Get all users
        success, users = self.run_test("Get All Users", "GET", "users", 200)
        if success:
            print(f"   Found {len(users)} users")
            return True
        
        return False

    def test_audit_logs(self):
        """Test audit logs (super_admin only)"""
        success, logs = self.run_test("Get Audit Logs", "GET", "audit-logs?limit=10", 200)
        if success:
            print(f"   Found {len(logs)} audit log entries")
            return True
        
        return False

    def run_all_tests(self):
        """Run comprehensive test suite"""
        print("🚀 Starting SEO Network Manager API Test Suite")
        print(f"Base URL: {self.base_url}")
        print("=" * 60)
        
        # Authentication tests
        if not self.test_user_registration():
            print("❌ Registration failed - stopping tests")
            return False
        
        if not self.test_user_login():
            print("❌ Login failed - stopping tests")  
            return False
            
        self.test_get_me()
        
        # Dashboard and seed data
        self.test_dashboard_stats()
        self.test_seed_data()
        
        # CRUD operations
        self.test_brands_crud()
        self.test_groups_crud()
        self.test_domains_crud()
        
        # Reports
        self.test_reports()
        
        # Admin functions
        self.test_user_management()
        self.test_audit_logs()
        
        # Final summary
        print("\n" + "=" * 60)
        print(f"📊 TEST SUMMARY")
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        
        if self.created_entities['domains']:
            print(f"Created Domains: {len(self.created_entities['domains'])}")
        if self.created_entities['brands']:
            print(f"Created Brands: {len(self.created_entities['brands'])}")
        if self.created_entities['groups']:
            print(f"Created Groups: {len(self.created_entities['groups'])}")
        
        return self.tests_passed == self.tests_run

def main():
    tester = SEONetworkAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())