#!/usr/bin/env python3
"""
Test script for the new integrated AI agent and module discovery.
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

async def test_components():
    """Test the new components."""
    print("🧪 Testing UMBRA Integrated AI Agent Components\n")
    
    try:
        # Import components
        from umbra.core.config import config
        from umbra.storage.database import DatabaseManager
        from umbra.ai.integrated_agent import IntegratedAIAgent
        
        print("✅ Successfully imported components")
        
        # Initialize database
        db_manager = DatabaseManager(":memory:")  # In-memory for testing
        print("✅ Database manager initialized")
        
        # Initialize AI agent
        agent = IntegratedAIAgent(config, db_manager)
        print("✅ Integrated AI agent created")
        
        # Initialize and discover modules
        success = await agent.initialize()
        print(f"✅ Agent initialization: {'Success' if success else 'Failed'}")
        
        # Get status
        status = agent.get_status()
        print(f"\n📊 Agent Status:")
        print(f"   Initialized: {status['initialized']}")
        print(f"   Modules: {status['modules']['total_modules']}")
        print(f"   AI Providers: {status['ai_providers']}")
        
        # Test some messages
        test_messages = [
            "hello",
            "check system status", 
            "help",
            "what modules do you have",
            "I spent $50 on groceries"
        ]
        
        print(f"\n🧪 Testing message processing:")
        for message in test_messages:
            print(f"\n   User: {message}")
            response = await agent.process_message(123456789, message, "TestUser")
            print(f"   Bot: {response[:100]}{'...' if len(response) > 100 else ''}")
        
        # Health check
        health = await agent.health_check()
        print(f"\n🏥 Health check completed: {len(health['modules'])} modules checked")
        
        print(f"\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_components())
    sys.exit(0 if success else 1)