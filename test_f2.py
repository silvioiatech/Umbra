#!/usr/bin/env python3
"""
Test script for PR F2 - Telegram Bot MVP (Railway)
Validates bot initialization, rate limiting, permissions, handlers, and basic responses.
"""
import os
import sys
import asyncio
import time
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

class F2TestSuite:
    """Test suite for PR F2 Telegram Bot MVP."""
    
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
    
    def test_rate_limiter_imports(self) -> bool:
        """Test rate limiter can be imported and initialized."""
        try:
            from umbra.utils.rate_limiter import RateLimiter, rate_limiter, rate_limit_check
            
            # Test basic functionality
            test_limiter = RateLimiter()
            
            # Test rate limiting logic
            user_id = 12345
            
            # Should allow first requests
            for i in range(5):
                if not test_limiter.is_allowed(user_id):
                    return False
            
            # Test stats
            stats = test_limiter.get_stats()
            if not isinstance(stats, dict):
                return False
            
            required_stats = ['enabled', 'limit_per_minute', 'window_seconds', 'active_users']
            for stat in required_stats:
                if stat not in stats:
                    return False
            
            return True
            
        except Exception:
            return False
    
    def test_bot_imports_and_initialization(self) -> bool:
        """Test bot can be imported and initialized."""
        # Set test environment
        os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        os.environ['ALLOWED_USER_IDS'] = '123,456'
        os.environ['ALLOWED_ADMIN_IDS'] = '123'
        os.environ['UMBRA_SKIP_VALIDATION'] = 'true'
        
        try:
            from umbra.bot import UmbraBot, UmbraAIAgent
            from umbra.core.config import UmbraConfig
            
            # Test config creation
            test_config = UmbraConfig()
            
            # Test bot initialization (without actually starting)
            bot = UmbraBot(test_config)
            
            # Check essential attributes
            required_attrs = [
                'config', 'permission_manager', 'db_manager', 'conversation_manager',
                'application', '_shutdown_event', 'start_time'
            ]
            
            for attr in required_attrs:
                if not hasattr(bot, attr):
                    return False
            
            # Test legacy alias
            legacy_bot = UmbraAIAgent(test_config)
            if type(legacy_bot).__name__ != 'UmbraBot':
                return False
            
            return True
            
        except Exception:
            return False
        finally:
            # Cleanup
            for var in ['TELEGRAM_BOT_TOKEN', 'ALLOWED_USER_IDS', 'ALLOWED_ADMIN_IDS', 'UMBRA_SKIP_VALIDATION']:
                if var in os.environ:
                    del os.environ[var]
    
    def test_permission_integration(self) -> bool:
        """Test bot permission integration."""
        os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        os.environ['ALLOWED_USER_IDS'] = '123,456'
        os.environ['ALLOWED_ADMIN_IDS'] = '123'
        os.environ['UMBRA_SKIP_VALIDATION'] = 'true'
        
        try:
            from umbra.bot import UmbraBot
            from umbra.core.config import UmbraConfig
            
            test_config = UmbraConfig()
            bot = UmbraBot(test_config)
            
            # Override permission manager for testing
            bot.permission_manager.allowed_users = {123, 456}
            bot.permission_manager.admin_users = {123}
            
            # Test permission checks
            if not bot.permission_manager.is_user_allowed(123):
                return False
            if not bot.permission_manager.is_user_allowed(456):
                return False
            if bot.permission_manager.is_user_allowed(789):
                return False
            
            # Test admin checks
            if not bot.permission_manager.is_user_admin(123):
                return False
            if bot.permission_manager.is_user_admin(456):
                return False
            
            return True
            
        except Exception:
            return False
        finally:
            for var in ['TELEGRAM_BOT_TOKEN', 'ALLOWED_USER_IDS', 'ALLOWED_ADMIN_IDS', 'UMBRA_SKIP_VALIDATION']:
                if var in os.environ:
                    del os.environ[var]
    
    def test_simple_response_generation(self) -> bool:
        """Test bot's simple response generation."""
        os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        os.environ['ALLOWED_USER_IDS'] = '123'
        os.environ['ALLOWED_ADMIN_IDS'] = '123'
        os.environ['UMBRA_SKIP_VALIDATION'] = 'true'
        
        try:
            from umbra.bot import UmbraBot
            from umbra.core.config import UmbraConfig
            
            test_config = UmbraConfig()
            bot = UmbraBot(test_config)
            
            # Create a mock user
            mock_user = Mock()
            mock_user.first_name = 'TestUser'
            mock_user.id = 123
            
            # Test greeting responses
            response = bot._generate_simple_response('hello', mock_user)
            if 'Hello TestUser' not in response:
                return False
            
            # Test help responses
            response = bot._generate_simple_response('help me', mock_user)
            if 'help' not in response.lower():
                return False
            
            # Test capability responses
            response = bot._generate_simple_response('what can you do', mock_user)
            if 'capabilities' not in response.lower() and 'umbra' not in response.lower():
                return False
            
            # Test default response
            response = bot._generate_simple_response('random message', mock_user)
            if 'F2 mode' not in response:
                return False
            
            return True
            
        except Exception:
            return False
        finally:
            for var in ['TELEGRAM_BOT_TOKEN', 'ALLOWED_USER_IDS', 'ALLOWED_ADMIN_IDS', 'UMBRA_SKIP_VALIDATION']:
                if var in os.environ:
                    del os.environ[var]
    
    def test_bot_status_method(self) -> bool:
        """Test bot status method."""
        os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token_123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        os.environ['ALLOWED_USER_IDS'] = '123'
        os.environ['ALLOWED_ADMIN_IDS'] = '123'
        os.environ['UMBRA_SKIP_VALIDATION'] = 'true'
        
        try:
            from umbra.bot import UmbraBot
            from umbra.core.config import UmbraConfig
            
            test_config = UmbraConfig()
            bot = UmbraBot(test_config)
            
            # Test status method
            status = bot.get_status()
            
            required_fields = [
                'running', 'polling', 'uptime_seconds', 'rate_limiter',
                'permissions', 'modules_loaded', 'ai_agent_available', 'database_connected'
            ]
            
            for field in required_fields:
                if field not in status:
                    return False
            
            # Check specific values
            if not isinstance(status['uptime_seconds'], (int, float)):
                return False
            
            if not isinstance(status['rate_limiter'], dict):
                return False
            
            if not isinstance(status['permissions'], dict):
                return False
            
            return True
            
        except Exception:
            return False
        finally:
            for var in ['TELEGRAM_BOT_TOKEN', 'ALLOWED_USER_IDS', 'ALLOWED_ADMIN_IDS', 'UMBRA_SKIP_VALIDATION']:
                if var in os.environ:
                    del os.environ[var]
    
    def test_rate_limiter_advanced(self) -> bool:
        """Test advanced rate limiter functionality."""
        try:
            from umbra.utils.rate_limiter import RateLimiter
            
            # Create test rate limiter with low limits
            test_limiter = RateLimiter()
            user_id = 99999
            
            # Fill up the rate limit
            allowed_count = 0
            for i in range(25):  # Try more than the limit
                if test_limiter.is_allowed(user_id):
                    allowed_count += 1
                else:
                    break
            
            # Should stop allowing at some point
            if allowed_count >= 25:
                return False  # Rate limiter not working
            
            # Test remaining requests
            remaining = test_limiter.get_remaining_requests(user_id)
            if remaining < 0:
                return False
            
            # Test reset time
            reset_time = test_limiter.get_reset_time(user_id)
            if reset_time is not None and reset_time <= time.time():
                return False
            
            return True
            
        except Exception:
            return False
    
    async def run_all_tests(self):
        """Run all tests in the suite."""
        print("🔍 Running PR F2 Telegram Bot MVP Tests\n")
        
        # Synchronous tests
        self.run_test("Rate Limiter Imports", self.test_rate_limiter_imports)
        self.run_test("Bot Imports and Initialization", self.test_bot_imports_and_initialization)
        self.run_test("Permission Integration", self.test_permission_integration)
        self.run_test("Simple Response Generation", self.test_simple_response_generation)
        self.run_test("Bot Status Method", self.test_bot_status_method)
        self.run_test("Rate Limiter Advanced", self.test_rate_limiter_advanced)
        
        # Print summary
        print(f"\n📊 Test Results:")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"📈 Success Rate: {self.passed / (self.passed + self.failed) * 100:.1f}%")
        
        if self.failed == 0:
            print("\n🎉 All tests passed! PR F2 implementation is ready.")
            return True
        else:
            print(f"\n⚠️  {self.failed} tests failed. Check implementation.")
            return False

async def main():
    """Main test function."""
    print("="*60)
    print("🧪 Umbra MCP - PR F2 Test Suite")
    print("🤖 Testing Telegram Bot MVP with Railway Polling")
    print("="*60)
    print()
    
    test_suite = F2TestSuite()
    success = await test_suite.run_all_tests()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
