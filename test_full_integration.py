#!/usr/bin/env python3
"""
End-to-end test of the integrated AI agent with real module execution.
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

async def test_full_integration():
    """Test full integration with module execution."""
    print("🚀 Full Integration Test\n")
    
    try:
        from umbra.core.config import config
        from umbra.storage.database import DatabaseManager
        from umbra.ai.integrated_agent import IntegratedAIAgent
        
        # Initialize with real database file for testing
        db_manager = DatabaseManager("test_umbra.db")
        agent = IntegratedAIAgent(config, db_manager)
        
        # Initialize
        await agent.initialize()
        
        # Test cases that should work
        test_cases = [
            "check system status",
            "I spent $25 on lunch",
            "help",
            "what modules do you have"
        ]
        
        print("🧪 Testing message processing with module execution:\n")
        
        for message in test_cases:
            print(f"👤 User: {message}")
            response = await agent.process_message(123456789, message, "TestUser")
            print(f"🤖 Bot: {response}")
            print("-" * 60)
        
        # Test health check
        health = await agent.health_check()
        print(f"\n🏥 Health Check:")
        print(f"   Agent Status: {health['agent_status']}")
        print(f"   Modules: {len(health['modules'])}")
        for module_id, status in health['modules'].items():
            print(f"     {module_id}: {status.get('status', 'unknown')}")
        
        print(f"\n✅ Full integration test completed!")
        
        # Clean up test database
        os.unlink("test_umbra.db")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_full_integration())
    sys.exit(0 if success else 1)