#!/usr/bin/env python3
"""
Test script for PR F1 - Core Railway Runtime
Validates configuration, HTTP health server, JSON logging, and permissions.
"""
import os
import sys
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any
import tempfile

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

class F1TestSuite:
    """Test suite for PR F1 Core Railway Runtime."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.test_results = []
    
    def run_test(self, test_name: str, test_func):
        """Run a single test and record results."""
        try:
            result = test_func()
            if result:
                print(f"✅ {test_name}")
                self.passed += 1
                self.test_results.append({"test": test_name, "result": "PASS"})
            else:
                print(f"❌ {test_name}")
                self.failed += 1
                self.test_results.append({"test": test_name, "result": "FAIL"})
        except Exception as e:
            print(f"❌ {test_name} (Exception: {e})")
            self.failed += 1
            self.test_results.append({"test": test_name, "result": "ERROR", "error": str(e)})
    
    async def run_async_test(self, test_name: str, test_func):
        """Run a single async test and record results."""
        try:
            result = await test_func()
            if result:
                print(f"✅ {test_name}")
                self.passed += 1
                self.test_results.append({"test": test_name, "result": "PASS"})
            else:
                print(f"❌ {test_name}")
                self.failed += 1
                self.test_results.append({"test": test_name, "result": "FAIL"})
        except Exception as e:
            print(f"❌ {test_name} (Exception: {e})")
            self.failed += 1
            self.test_results.append({"test": test_name, "result": "ERROR", "error": str(e)})
    
    def test_config_loading(self) -> bool:
        """Test UmbraConfig loads without required env vars set."""
        # Temporarily skip validation
        os.environ['UMBRA_SKIP_VALIDATION'] = 'true'
        
        try:
            from umbra.core.config import UmbraConfig
            config = UmbraConfig()
            
            # Check basic properties exist
            required_attrs = [
                'TELEGRAM_BOT_TOKEN', 'ALLOWED_USER_IDS', 'ALLOWED_ADMIN_IDS',
                'PORT', 'LOCALE_TZ', 'PRIVACY_MODE', 'RATE_LIMIT_PER_MIN',
                'R2_ACCOUNT_ID', 'OPENROUTER_API_KEY', 'OPENROUTER_DEFAULT_MODEL'
            ]
            
            for attr in required_attrs:
                if not hasattr(config, attr):
                    return False
            
            # Check default values
            if config.PORT != 8000:  # Default port
                return False
            if config.LOCALE_TZ != 'Europe/Zurich':
                return False
            if config.PRIVACY_MODE != 'strict':
                return False
            
            return True
            
        finally:
            if 'UMBRA_SKIP_VALIDATION' in os.environ:
                del os.environ['UMBRA_SKIP_VALIDATION']
    
    def test_config_validation(self) -> bool:
        """Test config validation fails with missing required vars."""
        # Clear any existing required env vars
        backup_vars = {}
        required_vars = ['TELEGRAM_BOT_TOKEN', 'ALLOWED_USER_IDS', 'ALLOWED_ADMIN_IDS']
        
        for var in required_vars:
            if var in os.environ:
                backup_vars[var] = os.environ[var]
                del os.environ[var]
        
        try:
            from umbra.core.config import UmbraConfig
            
            # This should raise ValueError
            try:
                config = UmbraConfig()
                return False  # Should have failed
            except ValueError:
                return True  # Expected failure
            
        finally:
            # Restore environment
            for var, value in backup_vars.items():
                os.environ[var] = value
    
    def test_json_logging(self) -> bool:
        """Test JSON logging setup and functionality."""
        from umbra.core.logger import setup_logging, get_context_logger, set_request_context
        
        # Create temporary log file
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.log', delete=False) as f:
            log_file = f.name
        
        try:
            # Setup logging with file output
            setup_logging("INFO", log_file)
            
            # Test context logging
            logger = get_context_logger("test")
            set_request_context(
                request_id="test-123",
                user_id=123456,
                module="test_module",
                action="test_action"
            )
            
            logger.info("Test log message")
            
            # Read and parse log file
            with open(log_file, 'r') as f:
                log_content = f.read().strip()
            
            if not log_content:
                return False
            
            # Parse JSON log entry
            log_entry = json.loads(log_content.split('\n')[-1])
            
            # Verify required fields
            required_fields = ['ts', 'level', 'msg', 'logger']
            for field in required_fields:
                if field not in log_entry:
                    return False
            
            # Verify context fields
            if log_entry.get('request_id') != 'test-123':
                return False
            if log_entry.get('user_id') != 123456:
                return False
            if log_entry.get('umbra_module') != 'test_module':
                return False
            if log_entry.get('action') != 'test_action':
                return False
            
            return True
            
        finally:
            # Cleanup
            if os.path.exists(log_file):
                os.unlink(log_file)
    
    def test_permissions_manager(self) -> bool:
        """Test PermissionManager functionality."""
        # Set test environment
        os.environ['ALLOWED_USER_IDS'] = '123,456'
        os.environ['ALLOWED_ADMIN_IDS'] = '123'
        os.environ['UMBRA_SKIP_VALIDATION'] = 'true'
        
        try:
            # Create a test config with the new values
            from umbra.core.config import UmbraConfig
            test_config = UmbraConfig()
            
            # Manually create PermissionManager with test data
            from umbra.core.permissions import PermissionManager
            pm = PermissionManager()
            
            # Override the sets directly for testing
            pm.allowed_users = {123, 456}
            pm.admin_users = {123}
            
            # Test allowed user
            if not pm.is_user_allowed(123):
                return False
            if not pm.is_user_allowed(456):
                return False
            if pm.is_user_allowed(789):  # Not in list
                return False
            
            # Test admin user
            if not pm.is_user_admin(123):
                return False
            if pm.is_user_admin(456):  # Not admin
                return False
            
            # Test legacy method names
            if not pm.is_allowed(123):
                return False
            if not pm.is_admin(123):
                return False
            
            return True
            
        finally:
            # Cleanup
            for var in ['ALLOWED_USER_IDS', 'ALLOWED_ADMIN_IDS', 'UMBRA_SKIP_VALIDATION']:
                if var in os.environ:
                    del os.environ[var]
    
    async def test_health_app_creation(self) -> bool:
        """Test health app creation and basic functionality."""
        os.environ['UMBRA_SKIP_VALIDATION'] = 'true'
        
        try:
            from umbra.http.health import create_health_app, check_service_health
            
            # Create app
            app = create_health_app()
            
            # Check routes exist
            routes = list(app.router.routes())
            route_paths = [route.resource.canonical for route in routes]
            
            if '/' not in route_paths:
                return False
            if '/health' not in route_paths:
                return False
            
            # Test health check function
            health_result = await check_service_health()
            
            if not isinstance(health_result, dict):
                return False
            if 'healthy' not in health_result:
                return False
            if 'checks' not in health_result:
                return False
            
            return True
            
        finally:
            if 'UMBRA_SKIP_VALIDATION' in os.environ:
                del os.environ['UMBRA_SKIP_VALIDATION']
    
    def test_module_imports(self) -> bool:
        """Test all core modules can be imported."""
        modules_to_test = [
            'umbra.core.config',
            'umbra.core.logger', 
            'umbra.core.permissions',
            'umbra.http.health'
        ]
        
        for module_name in modules_to_test:
            try:
                __import__(module_name)
            except ImportError:
                return False
        
        return True
    
    def test_environment_parsing(self) -> bool:
        """Test environment variable parsing."""
        # Test boolean parsing
        test_cases = [
            ('true', True),
            ('1', True),
            ('yes', True),
            ('on', True),
            ('false', False),
            ('0', False),
            ('no', False),
            ('off', False),
            ('invalid', False)  # Default
        ]
        
        os.environ['UMBRA_SKIP_VALIDATION'] = 'true'
        
        try:
            from umbra.core.config import UmbraConfig
            
            for env_value, expected in test_cases:
                os.environ['TEST_BOOL'] = env_value
                config = UmbraConfig()
                result = config._parse_bool('TEST_BOOL', default=False)
                if result != expected:
                    return False
            
            # Test user ID parsing
            os.environ['TEST_USER_IDS'] = '123,456,789'
            config = UmbraConfig()
            user_ids = config._parse_user_ids(os.environ['TEST_USER_IDS'])
            if user_ids != [123, 456, 789]:
                return False
            
            return True
            
        finally:
            for var in ['TEST_BOOL', 'TEST_USER_IDS', 'UMBRA_SKIP_VALIDATION']:
                if var in os.environ:
                    del os.environ[var]
    
    async def run_all_tests(self):
        """Run all tests in the suite."""
        print("🔍 Running PR F1 Core Railway Runtime Tests\n")
        
        # Synchronous tests
        self.run_test("Config Loading", self.test_config_loading)
        self.run_test("Config Validation", self.test_config_validation)
        self.run_test("JSON Logging", self.test_json_logging)
        self.run_test("Permissions Manager", self.test_permissions_manager)
        self.run_test("Module Imports", self.test_module_imports)
        self.run_test("Environment Parsing", self.test_environment_parsing)
        
        # Async tests
        await self.run_async_test("Health App Creation", self.test_health_app_creation)
        
        # Print summary
        print(f"\n📊 Test Results:")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"📈 Success Rate: {self.passed / (self.passed + self.failed) * 100:.1f}%")
        
        if self.failed == 0:
            print("\n🎉 All tests passed! PR F1 implementation is ready.")
            return True
        else:
            print(f"\n⚠️  {self.failed} tests failed. Check implementation.")
            return False

async def main():
    """Main test function."""
    print("="*60)
    print("🧪 Umbra MCP - PR F1 Test Suite")
    print("🏭 Testing Core Railway Runtime Implementation")
    print("="*60)
    print()
    
    test_suite = F1TestSuite()
    success = await test_suite.run_all_tests()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
