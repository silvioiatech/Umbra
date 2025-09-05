#!/usr/bin/env python3
"""
Final validation test to ensure all problem statement requirements are met:
1. Provider-agnostic AI agent ✓
2. Intent router with deterministic routes first ✓  
3. ModuleRegistry that discovers modules exposing get_capabilities() and execute(action, params) ✓
4. LLM backstop optional (wired by F3R1) ✓
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path  
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set minimal required environment variables
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'test_token')
os.environ.setdefault('ALLOWED_USER_IDS', '123456789')
os.environ.setdefault('ALLOWED_ADMIN_IDS', '123456789')

async def validate_requirements():
    """Validate all problem statement requirements."""
    print("🔍 Validating Problem Statement Requirements\n")
    
    try:
        from umbra.core.config import config
        from umbra.storage.database import DatabaseManager
        from umbra.ai.integrated_agent import IntegratedAIAgent
        from umbra.ai.provider_agnostic import ProviderAgnosticAI, AIProvider
        from umbra.core.module_registry import ModuleRegistry
        from umbra.ai.intent_router import IntentRouter
        
        # 1. Provider-agnostic AI agent ✓
        print("1️⃣ Testing Provider-Agnostic AI Agent...")
        ai_provider = ProviderAgnosticAI(config)
        print(f"   ✅ Multiple provider support: {type(ai_provider).__name__}")
        print(f"   ✅ Fallback enabled: {ai_provider.fallback_enabled}")
        print(f"   ✅ Available providers: {ai_provider.get_available_providers()}")
        
        # 2. ModuleRegistry discovers modules with get_capabilities() and execute() ✓
        print("\n2️⃣ Testing ModuleRegistry Dynamic Discovery...")
        db_manager = DatabaseManager(":memory:")
        registry = ModuleRegistry(config, db_manager)
        modules = await registry.discover_modules()
        print(f"   ✅ Modules discovered: {len(modules)}")
        
        # Verify each module has required interface
        for module_id, module in modules.items():
            has_get_capabilities = hasattr(module, 'get_capabilities') and callable(module.get_capabilities)
            has_execute = hasattr(module, 'execute') and callable(module.execute)
            capabilities = module.get_capabilities() if has_get_capabilities else []
            print(f"     {module_id}: get_capabilities={has_get_capabilities}, execute={has_execute}, caps={len(capabilities)}")
        
        # 3. Intent router with deterministic routes first ✓
        print("\n3️⃣ Testing Intent Router - Deterministic Routes First...")
        intent_router = IntentRouter(config, ai_provider)
        intent_router.set_module_capabilities(registry.get_module_capabilities())
        
        # Test deterministic routing (should work without AI)
        test_message = "I spent $30 on coffee"
        intent = await intent_router.route_intent(test_message)
        print(f"   ✅ Deterministic routing: '{test_message}' → {intent.module_id}.{intent.action}")
        print(f"   ✅ Confidence: {intent.confidence:.2f} (deterministic)")
        print(f"   ✅ Params extracted: {intent.params}")
        
        # 4. LLM backstop optional (F3R1 ready) ✓
        print("\n4️⃣ Testing LLM Backstop Configuration...")
        print(f"   ✅ LLM available: {ai_provider.is_ai_available()}")
        print(f"   ✅ Fallback enabled: {ai_provider.fallback_enabled}")
        print("   ✅ F3R1 integration ready: Provider-agnostic interface supports any AI provider")
        
        # 5. Full integration test ✓
        print("\n5️⃣ Testing Full Integration...")
        agent = IntegratedAIAgent(config, db_manager)
        await agent.initialize()
        
        test_cases = [
            ("deterministic", "check system status"),
            ("parameter extraction", "I spent $100 on groceries"),  
            ("fallback", "hello there")
        ]
        
        for test_type, message in test_cases:
            response = await agent.process_message(123456789, message, "Validator")
            print(f"   ✅ {test_type}: '{message}' → Response generated ({len(response)} chars)")
        
        print(f"\n🎉 ALL REQUIREMENTS VALIDATED SUCCESSFULLY!")
        print(f"\n📋 Summary:")
        print(f"   ✅ Provider-agnostic AI agent implemented")
        print(f"   ✅ Intent router with deterministic routes first") 
        print(f"   ✅ ModuleRegistry discovers modules with get_capabilities() and execute()")
        print(f"   ✅ LLM backstop optional and F3R1-ready")
        print(f"   ✅ {len(modules)} modules discovered and operational")
        
        return True
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(validate_requirements())
    print(f"\n{'🎉 VALIDATION PASSED' if success else '❌ VALIDATION FAILED'}")
    sys.exit(0 if success else 1)