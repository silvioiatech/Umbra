#!/usr/bin/env python3
"""
Test intent routing specifically to verify deterministic routing works.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set minimal required environment variables for testing
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'test_token')
os.environ.setdefault('ALLOWED_USER_IDS', '123456789')
os.environ.setdefault('ALLOWED_ADMIN_IDS', '123456789')

async def test_intent_routing():
    """Test intent routing with various messages."""
    print("🧭 Testing Intent Routing\n")
    
    try:
        from umbra.core.config import config
        from umbra.storage.database import DatabaseManager
        from umbra.ai.provider_agnostic import ProviderAgnosticAI
        from umbra.ai.intent_router import IntentRouter
        from umbra.core.module_registry import ModuleRegistry
        
        # Initialize components
        db_manager = DatabaseManager(":memory:")
        ai_provider = ProviderAgnosticAI(config)
        module_registry = ModuleRegistry(config, db_manager)
        
        # Discover modules to get capabilities
        await module_registry.discover_modules()
        capabilities = module_registry.get_module_capabilities()
        
        # Initialize intent router
        intent_router = IntentRouter(config, ai_provider)
        intent_router.set_module_capabilities(capabilities)
        
        print(f"📦 Modules discovered: {list(capabilities.keys())}")
        print(f"🧠 AI available: {ai_provider.is_ai_available()}")
        print(f"🎯 Testing deterministic routing...\n")
        
        # Test messages that should trigger deterministic routing
        test_cases = [
            ("I spent $50 on groceries", "finance", "track_expense"),
            ("check system status", "concierge", "system_status"),
            ("create a client instance", "business", "create_client_instance"),
            ("generate financial report", "finance", "monthly_report"),
            ("docker status", "concierge", "docker_status"),
            ("help me", "help", "show_capabilities"),
            ("what can you do", "help", "show_capabilities"),
            ("backup the system", "concierge", "backup_system"),
            ("create workflow", "production", "create_workflow"),
            ("generate image", "creator", "generate_content"),
        ]
        
        for message, expected_module, expected_action in test_cases:
            intent = await intent_router.route_intent(message)
            
            confidence_indicator = "🎯" if intent.confidence >= 0.8 else "🔍" if intent.confidence >= 0.5 else "❓"
            match_indicator = "✅" if (intent.module_id == expected_module and intent.action == expected_action) else "❌"
            
            print(f"{match_indicator} {confidence_indicator} '{message}'")
            print(f"   Expected: {expected_module}.{expected_action}")
            print(f"   Got:      {intent.module_id}.{intent.action} (confidence: {intent.confidence:.2f})")
            if intent.params:
                print(f"   Params:   {intent.params}")
            print(f"   Reason:   {intent.reasoning}")
            print()
        
        print("✅ Intent routing test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_intent_routing())
    sys.exit(0 if success else 1)