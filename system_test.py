#!/usr/bin/env python3
"""
UMBRA System Status Check
========================

Test the current implementation and identify what needs attention.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_core_imports():
    """Test if core modules can be imported."""
    print("🔍 Testing Core Imports...")
    
    try:
        from umbra.core.config import config
        print("   ✅ Config module imported")
        
        from umbra.core.logger import get_context_logger
        print("   ✅ Logger module imported")
        
        from umbra.core.permissions import PermissionManager
        print("   ✅ Permissions module imported")
        
        return True
    except Exception as e:
        print(f"   ❌ Core import error: {e}")
        return False

def test_bot_modules():
    """Test bot-related modules."""
    print("\n🤖 Testing Bot Modules...")
    
    try:
        from umbra.bot import UmbraBot
        print("   ✅ Bot module imported")
        
        from umbra.router import UmbraRouter
        print("   ✅ Router module imported")
        
        from umbra.modules.registry import ModuleRegistry
        print("   ✅ Module registry imported")
        
        return True
    except Exception as e:
        print(f"   ❌ Bot module error: {e}")
        return False

def test_ai_modules():
    """Test AI-related modules."""
    print("\n🧠 Testing AI Modules (F3R1)...")
    
    try:
        from umbra.ai.agent import UmbraAIAgent
        print("   ✅ AI agent imported")
        
        from umbra.providers.openrouter import OpenRouterProvider
        print("   ✅ OpenRouter provider imported")
        
        return True
    except Exception as e:
        print(f"   ❌ AI module error: {e}")
        return False

def test_storage_modules():
    """Test storage-related modules."""
    print("\n📦 Testing Storage Modules (F4R2)...")
    
    try:
        from umbra.storage.r2_client import R2Client
        print("   ✅ R2 client imported")
        
        from umbra.storage.objects import ObjectStorage
        print("   ✅ Object storage imported")
        
        from umbra.storage.manifest import ManifestManager
        print("   ✅ Manifest manager imported")
        
        from umbra.storage.search_index import SearchIndex
        print("   ✅ Search index imported")
        
        return True
    except Exception as e:
        print(f"   ❌ Storage module error: {e}")
        return False

def test_mcp_modules():
    """Test MCP modules."""
    print("\n🛠️ Testing MCP Modules...")
    
    modules_tested = 0
    modules_working = 0
    
    module_list = [
        "general_chat_mcp",
        "business_mcp", 
        "concierge_mcp",
        "creator_mcp",
        "finance_mcp",
        "production_mcp"
    ]
    
    for module_name in module_list:
        try:
            module = __import__(f"umbra.modules.{module_name}", fromlist=[module_name])
            print(f"   ✅ {module_name} imported")
            modules_working += 1
        except Exception as e:
            print(f"   ⚠️ {module_name} error: {e}")
        modules_tested += 1
    
    print(f"   📊 MCP Modules: {modules_working}/{modules_tested} working")
    return modules_working > 0

def test_configuration():
    """Test configuration."""
    print("\n⚙️ Testing Configuration...")
    
    try:
        from umbra.core.config import config
        
        status = config.get_status_summary()
        print(f"   📋 Environment: {status['environment']}")
        print(f"   🌍 Locale: {status['locale_tz']}")
        print(f"   🔒 Privacy: {status['privacy_mode']}")
        print(f"   🤖 Bot Token: {status['bot_token']}")
        print(f"   👥 Allowed Users: {status['allowed_users']}")
        print(f"   👑 Admin Users: {status['admin_users']}")
        print(f"   🧠 AI Integration: {status['ai_integration']}")
        print(f"   📦 R2 Storage: {status['r2_storage']}")
        print(f"   🗄️ Storage Backend: {status['storage_backend']}")
        
        return True
    except Exception as e:
        print(f"   ❌ Configuration error: {e}")
        return False

def test_basic_functionality():
    """Test basic functionality."""
    print("\n🧪 Testing Basic Functionality...")
    
    try:
        # Test router
        from umbra.router import UmbraRouter
        router = UmbraRouter()
        
        # Test route patterns
        result = router.route_message("help", user_id=123456789, is_admin=True)
        print(f"   ✅ Router working: matched={result.matched}")
        
        # Test general chat
        from umbra.modules.general_chat_mcp import GeneralChatMCP
        chat = GeneralChatMCP()
        
        # Test calculator
        import asyncio
        calc_result = asyncio.run(chat.execute("calculate", {"expression": "2+2"}))
        print(f"   ✅ Calculator working: {calc_result.get('success', False)}")
        
        return True
    except Exception as e:
        print(f"   ❌ Basic functionality error: {e}")
        return False

def identify_next_steps():
    """Identify what needs to be done next."""
    print("\n🎯 Next Steps Analysis...")
    
    next_steps = []
    
    # Check if bot token is set
    if os.getenv("TELEGRAM_BOT_TOKEN") == "your_bot_token_here":
        next_steps.append("1. Set real TELEGRAM_BOT_TOKEN in .env file")
    
    # Check if user IDs are set
    if os.getenv("ALLOWED_USER_IDS") == "123456789":
        next_steps.append("2. Set real ALLOWED_USER_IDS in .env file")
    
    # Check if OpenRouter is configured
    if not os.getenv("OPENROUTER_API_KEY"):
        next_steps.append("3. (Optional) Set OPENROUTER_API_KEY for AI features")
    
    # Check if R2 is configured
    if not os.getenv("R2_ACCOUNT_ID"):
        next_steps.append("4. (Optional) Set R2 credentials for cloud storage")
    
    if next_steps:
        print("   📝 Required Configuration:")
        for step in next_steps:
            print(f"   {step}")
    else:
        print("   ✅ All basic configuration appears to be set!")
    
    print("\n   💡 Once configured, you can:")
    print("   • Run: python main.py")
    print("   • Test: python f4r2_validate.py")
    print("   • Validate: python f4r2_demo.py")

def main():
    """Main test function."""
    print("🚀 UMBRA System Status Check")
    print("=" * 50)
    
    # Run all tests
    tests = [
        test_core_imports,
        test_bot_modules,
        test_ai_modules,
        test_storage_modules,
        test_mcp_modules,
        test_configuration,
        test_basic_functionality
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"   💥 Test {test_func.__name__} crashed: {e}")
    
    # Summary
    print(f"\n📊 Test Results: {passed}/{total} test groups passed")
    
    if passed == total:
        print("🎉 All systems working! UMBRA is ready for configuration.")
    elif passed >= total * 0.8:
        print("✅ Most systems working! Minor issues detected.")
    elif passed >= total * 0.5:
        print("⚠️ Some systems working, but issues detected.")
    else:
        print("❌ Major issues detected. Check imports and dependencies.")
    
    # Identify next steps
    identify_next_steps()
    
    return 0 if passed >= total * 0.8 else 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(2)
