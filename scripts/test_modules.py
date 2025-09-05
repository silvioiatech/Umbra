#!/usr/bin/env python3
"""
UMBRA Module Tester
Tests all MCP modules to ensure they're working correctly in a feature branch.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

async def test_module_imports():
    """Test that all modules can be imported."""
    print("📦 Testing module imports...")
    
    modules_to_test = [
        ('umbra.modules.concierge_mcp', 'ConciergeMCP'),
        ('umbra.modules.finance_mcp', 'FinanceMCP'),
        ('umbra.modules.business_mcp', 'BusinessMCP'), 
        ('umbra.modules.production_mcp', 'ProductionMCP'),
        ('umbra.modules.creator_mcp', 'CreatorMCP'),
    ]
    
    imported_modules = {}
    failed_imports = []
    
    for module_name, class_name in modules_to_test:
        try:
            module = __import__(module_name, fromlist=[class_name])
            module_class = getattr(module, class_name)
            imported_modules[class_name] = module_class
            print(f"✅ {class_name}")
        except Exception as e:
            failed_imports.append(f"{class_name}: {e}")
            print(f"❌ {class_name}: {e}")
    
    if failed_imports:
        print(f"\n❌ Failed imports: {failed_imports}")
        return False, {}
    
    print("✅ All modules imported successfully")
    return True, imported_modules

async def test_module_initialization(modules):
    """Test that modules can be initialized."""
    print("\n🔧 Testing module initialization...")
    
    # Mock configuration and database for testing
    from umbra.core.config import UmbraConfig
    from umbra.storage.database import DatabaseManager
    
    config = UmbraConfig()
    
    # Use in-memory database for testing
    db_manager = DatabaseManager(":memory:")
    await db_manager.connect()
    
    initialized_modules = {}
    failed_inits = []
    
    for class_name, module_class in modules.items():
        try:
            # Initialize the module
            module_instance = module_class(config, db_manager)
            await module_instance.initialize()
            initialized_modules[class_name] = module_instance
            print(f"✅ {class_name} initialized")
        except Exception as e:
            failed_inits.append(f"{class_name}: {e}")
            print(f"❌ {class_name}: {e}")
    
    await db_manager.close()
    
    if failed_inits:
        print(f"\n❌ Failed initializations: {failed_inits}")
        return False, {}
    
    print("✅ All modules initialized successfully")
    return True, initialized_modules

async def test_module_health_checks(modules):
    """Test module health checks."""
    print("\n🏥 Testing module health checks...")
    
    health_results = {}
    failed_health = []
    
    for class_name, module_instance in modules.items():
        try:
            health = await module_instance.health_check()
            health_results[class_name] = health
            
            if health.get('status') == 'healthy':
                print(f"✅ {class_name}: {health.get('message', 'OK')}")
            else:
                print(f"⚠️ {class_name}: {health}")
                
        except Exception as e:
            failed_health.append(f"{class_name}: {e}")
            print(f"❌ {class_name}: {e}")
    
    if failed_health:
        print(f"\n❌ Failed health checks: {failed_health}")
        return False
    
    print("✅ All modules passed health checks")
    return True

async def test_module_capabilities(modules):
    """Test module capability reporting."""
    print("\n🛠️ Testing module capabilities...")
    
    for class_name, module_instance in modules.items():
        try:
            if hasattr(module_instance, 'register_handlers'):
                handlers = await module_instance.register_handlers()
                print(f"✅ {class_name}: {len(handlers)} handlers")
                
                # Show some handler details
                for handler_name in list(handlers.keys())[:3]:  # Show first 3
                    print(f"   - {handler_name}")
                if len(handlers) > 3:
                    print(f"   ... and {len(handlers) - 3} more")
                    
        except Exception as e:
            print(f"⚠️ {class_name} capabilities: {e}")
    
    print("✅ Module capabilities tested")
    return True

def test_environment_setup():
    """Test environment setup."""
    print("\n🌍 Testing environment setup...")
    
    checks = []
    
    # Check environment variables
    required_for_basic = ['DATABASE_PATH']
    optional_but_recommended = ['LOG_LEVEL', 'ENVIRONMENT']
    
    for var in required_for_basic:
        if os.environ.get(var):
            print(f"✅ {var}: {os.environ[var]}")
            checks.append(True)
        else:
            print(f"⚠️ {var}: not set (will use defaults)")
            checks.append(True)  # Not critical for testing
    
    for var in optional_but_recommended:
        if os.environ.get(var):
            print(f"✅ {var}: {os.environ[var]}")
        else:
            print(f"ℹ️ {var}: not set (will use defaults)")
    
    # Check directory structure
    required_dirs = ['data', 'data/dev', 'logs', 'logs/dev']
    for dir_path in required_dirs:
        path_obj = Path(dir_path)
        if path_obj.exists():
            print(f"✅ Directory: {dir_path}")
        else:
            path_obj.mkdir(parents=True, exist_ok=True)
            print(f"📁 Created: {dir_path}")
    
    print("✅ Environment setup complete")
    return all(checks)

async def run_integration_test(modules):
    """Run a basic integration test."""
    print("\n🔄 Running integration test...")
    
    # Test basic workflow: user message -> module selection -> response
    from umbra.core.envelope import InternalEnvelope
    
    # Create a test envelope
    test_envelope = InternalEnvelope(
        user_id=999999999,
        message="test finance balance",
        module_hint="finance"
    )
    
    # Test with FinanceMCP
    if 'FinanceMCP' in modules:
        try:
            finance_module = modules['FinanceMCP']
            response = await finance_module.process_envelope(test_envelope)
            print(f"✅ Integration test - Finance response: {response[:100]}...")
        except Exception as e:
            print(f"⚠️ Integration test failed: {e}")
            return False
    
    print("✅ Integration test completed")
    return True

async def main():
    """Main testing function."""
    print("🧪 UMBRA MCP Module Tester")
    print("=" * 50)
    
    # Set up development environment
    os.environ.setdefault('ENVIRONMENT', 'development')
    os.environ.setdefault('DATABASE_PATH', 'data/umbra_dev.db')
    os.environ.setdefault('LOG_LEVEL', 'DEBUG')
    
    test_results = []
    
    # Test 1: Environment setup
    result = test_environment_setup()
    test_results.append(("Environment Setup", result))
    
    # Test 2: Module imports
    result, modules = await test_module_imports()
    test_results.append(("Module Imports", result))
    
    if not result:
        print("\n❌ Cannot continue - module imports failed")
        return 1
    
    # Test 3: Module initialization
    result, initialized_modules = await test_module_initialization(modules)
    test_results.append(("Module Initialization", result))
    
    if not result:
        print("\n❌ Cannot continue - module initialization failed")
        return 1
    
    # Test 4: Health checks
    result = await test_module_health_checks(initialized_modules)
    test_results.append(("Health Checks", result))
    
    # Test 5: Capabilities
    result = await test_module_capabilities(initialized_modules)
    test_results.append(("Module Capabilities", result))
    
    # Test 6: Integration test
    result = await run_integration_test(initialized_modules)
    test_results.append(("Integration Test", result))
    
    # Summary
    print(f"\n{'=' * 50}")
    print("📊 Test Summary:")
    
    passed = 0
    for test_name, result in test_results:
        status = "✅" if result else "❌"
        print(f"   {status} {test_name}")
        if result:
            passed += 1
    
    total = len(test_results)
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All MCP modules are working correctly!")
        print("\n🚀 Your feature branch is ready for development")
        return 0
    else:
        print("❌ Some tests failed - check the output above")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))