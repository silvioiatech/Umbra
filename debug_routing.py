#!/usr/bin/env python3
"""
Debug intent routing patterns
"""
import asyncio
import os
import sys
import logging
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set minimal required environment variables for testing
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'test_token')
os.environ.setdefault('ALLOWED_USER_IDS', '123456789')
os.environ.setdefault('ALLOWED_ADMIN_IDS', '123456789')

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

async def debug_routing():
    """Debug intent routing."""
    print("🐛 Debug Intent Routing\n")
    
    try:
        from umbra.core.config import config
        from umbra.ai.provider_agnostic import ProviderAgnosticAI
        from umbra.ai.intent_router import IntentRouter
        
        # Initialize components
        ai_provider = ProviderAgnosticAI(config)
        intent_router = IntentRouter(config, ai_provider)
        
        # Test one simple case
        test_message = "I spent $50 on groceries"
        print(f"Testing: '{test_message}'")
        
        intent = await intent_router.route_intent(test_message)
        print(f"Result: {intent.module_id}.{intent.action} (confidence: {intent.confidence})")
        print(f"Reasoning: {intent.reasoning}")
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_routing())