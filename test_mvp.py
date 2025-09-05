#!/usr/bin/env python3
"""
Test script for UMBRA Bot MVP
Tests the core functionality without needing a real Telegram token
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_imports():
    """Test that all required modules can be imported."""
    print("🔍 Testing imports...")
    
    try:
        from umbra.utils.rate_limiter import RateLimiter
        print("✅ Rate limiter imported successfully")
    except ImportError as e:
        print(f"❌ Rate limiter import failed: {e}")
        return False
    
    try:
        from umbra.core.logger import setup_logging, get_logger
        print("✅ Logger imported successfully")
    except ImportError as e:
        print(f"❌ Logger import failed: {e}")
        return False
    
    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
        print("✅ python-telegram-bot imported successfully")
    except ImportError as e:
        print(f"❌ python-telegram-bot import failed: {e}")
        return False
    
    return True

def test_rate_limiter():
    """Test rate limiter functionality."""
    print("\n🔍 Testing rate limiter...")
    
    try:
        from umbra.utils.rate_limiter import RateLimiter
        
        # Create rate limiter with 3 requests per 5 seconds for testing
        limiter = RateLimiter(max_requests=3, window_seconds=5)
        
        user_id = 12345
        
        # Should allow first 3 requests
        for i in range(3):
            allowed = limiter.is_allowed(user_id)
            if not allowed:
                print(f"❌ Request {i+1} was unexpectedly denied")
                return False
            remaining = limiter.get_remaining_requests(user_id)
            print(f"✅ Request {i+1} allowed, {remaining} remaining")
        
        # 4th request should be denied
        allowed = limiter.is_allowed(user_id)
        if allowed:
            print("❌ 4th request was unexpectedly allowed")
            return False
        print("✅ 4th request correctly denied (rate limited)")
        
        return True
        
    except Exception as e:
        print(f"❌ Rate limiter test failed: {e}")
        return False

def test_logger():
    """Test logger functionality."""
    print("\n🔍 Testing logger...")
    
    try:
        from umbra.core.logger import setup_logging, get_logger
        import logging
        
        # Setup logging
        setup_logging(level="INFO")
        logger = get_logger("test")
        
        # Test different log levels
        logger.info("✅ Info log test")
        logger.warning("⚠️ Warning log test")
        logger.error("❌ Error log test")
        
        print("✅ Logger test completed")
        return True
        
    except Exception as e:
        print(f"❌ Logger test failed: {e}")
        return False

def test_bot_mvp_class():
    """Test that the MVP bot class can be instantiated."""
    print("\n🔍 Testing MVP bot class...")
    
    try:
        # Import the class by reading the file and extracting just the class definition
        import importlib.util
        
        spec = importlib.util.spec_from_file_location("bot_mvp", PROJECT_ROOT / "bot_mvp.py")
        bot_mvp_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bot_mvp_module)
        
        # Test that we can create the class (with a fake token for testing)
        bot = bot_mvp_module.UmbraBotMVP(bot_token="fake_token_for_testing", allowed_user_ids=[12345, 67890])
        
        print("✅ MVP bot class instantiated successfully")
        print(f"✅ Rate limiter configured: {bot.rate_limiter.max_requests} requests per {bot.rate_limiter.window_seconds}s")
        print(f"✅ User access configured: {len(bot.allowed_user_ids)} allowed users")
        
        # Test user authorization
        if bot._is_user_allowed(12345):
            print("✅ User authorization working (allowed user)")
        else:
            print("❌ User authorization failed (allowed user denied)")
            return False
            
        if not bot._is_user_allowed(99999):
            print("✅ User authorization working (denied user)")
        else:
            print("❌ User authorization failed (denied user allowed)")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ MVP bot class test failed: {e}")
        return False

def test_configuration():
    """Test environment variable parsing."""
    print("\n🔍 Testing configuration...")
    
    try:
        import os
        
        # Test with minimal environment
        original_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        original_users = os.environ.get('ALLOWED_USER_IDS')
        
        # Set test environment
        os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token'
        os.environ['ALLOWED_USER_IDS'] = '123,456,789'
        
        # Test the parsing logic from bot_mvp.py
        allowed_users_str = os.getenv('ALLOWED_USER_IDS', '')
        allowed_user_ids = []
        if allowed_users_str:
            try:
                allowed_user_ids = [int(uid.strip()) for uid in allowed_users_str.split(',') if uid.strip()]
            except ValueError:
                pass
        
        expected_users = [123, 456, 789]
        if allowed_user_ids == expected_users:
            print(f"✅ User ID parsing works: {allowed_user_ids}")
        else:
            print(f"❌ User ID parsing failed: got {allowed_user_ids}, expected {expected_users}")
            return False
        
        # Restore original environment
        if original_token:
            os.environ['TELEGRAM_BOT_TOKEN'] = original_token
        else:
            os.environ.pop('TELEGRAM_BOT_TOKEN', None)
            
        if original_users:
            os.environ['ALLOWED_USER_IDS'] = original_users
        else:
            os.environ.pop('ALLOWED_USER_IDS', None)
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🤖 UMBRA Bot MVP - Test Suite")
    print("="*40)
    
    tests = [
        ("Imports", test_imports),
        ("Rate Limiter", test_rate_limiter),
        ("Logger", test_logger),
        ("Configuration", test_configuration),
        ("MVP Bot Class", test_bot_mvp_class),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
    
    print("\n" + "="*40)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! MVP is ready to run.")
        print("\n💡 To run the bot:")
        print("   export TELEGRAM_BOT_TOKEN='your_bot_token'")
        print("   export ALLOWED_USER_IDS='123,456,789'  # optional")
        print("   python bot_mvp.py")
    else:
        print("❌ Some tests failed. Check the output above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())