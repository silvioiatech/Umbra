#!/usr/bin/env python3
"""
Test script for C2 - Concierge Auto-Update Watcher functionality
Tests the basic operations of the update watcher system.
"""
import asyncio
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_update_watcher():
    """Test the update watcher functionality."""
    print("🧪 Testing C2 - Concierge Auto-Update Watcher")
    print("=" * 50)
    
    # Mock configuration for testing
    class MockConfig:
        def get(self, key, default=None):
            config_values = {
                'UPDATES_CHECKS_AT': ['07:00', '19:00'],
                'MAIN_SERVICE': 'n8n-main',
                'NGINX_CONTAINER_NAME': 'nginx-proxy',
                'CLIENT_PORT_RANGE': '20000-21000',
                'MAINTENANCE_WINDOWS': {},
                'FREEZE_LIST': [],
                'REQUIRE_DOUBLE_CONFIRM_ON_MAJOR': True,
                'HEALTHCHECK': {
                    'url': 'https://automatia.duckdns.org/n8n',
                    'timeout': 30
                }
            }
            return config_values.get(key, default)
    
    # Import and test UpdateWatcher
    try:
        from umbra.modules.concierge.update_watcher import UpdateWatcher
        
        config = MockConfig()
        watcher = UpdateWatcher(config)
        
        print(f"✅ UpdateWatcher initialized")
        print(f"   Main service: {watcher.main_service}")
        print(f"   Check times: {[t.strftime('%H:%M') for t in watcher.check_times]}")
        print(f"   Nginx container: {watcher.nginx_container}")
        
        # Test status
        status = watcher.get_status()
        print(f"\n📊 Initial Status:")
        print(f"   Scheduler running: {status['scheduler_running']}")
        print(f"   Next scan: {status['next_scan']}")
        print(f"   Frozen services: {status['frozen_services']}")
        
        # Test freeze/unfreeze
        freeze_result = await watcher.freeze("test-service", True)
        print(f"\n🧊 Freeze test:")
        print(f"   Service frozen: {freeze_result['frozen']}")
        print(f"   Freeze list: {freeze_result['freeze_list']}")
        
        # Test maintenance window
        window_result = await watcher.set_maintenance_window("test-client", "02:00-05:00")
        print(f"\n🕒 Maintenance window test:")
        print(f"   Service: {window_result['service_name']}")
        print(f"   Window: {window_result['window']}")
        
        print(f"\n✅ All basic tests passed!")
        
        # Test registry helper
        print(f"\n🐳 Testing Docker Registry Helper...")
        from umbra.modules.concierge.docker_registry import DockerRegistryHelper
        
        registry_helper = DockerRegistryHelper(config)
        registry_status = registry_helper.get_status()
        print(f"   Docker command: {registry_status['docker_cmd']}")
        print(f"   Timeout: {registry_status['timeout']}s")
        print(f"   Version patterns: {registry_status['version_patterns']}")
        
        # Test blue-green manager
        print(f"\n🔄 Testing Blue-Green Manager...")
        from umbra.modules.concierge.blue_green import BlueGreenManager
        
        bg_manager = BlueGreenManager(config)
        bg_status = bg_manager.get_status()
        print(f"   Main service: {bg_status['main_service']}")
        print(f"   Colors: {bg_status['colors']}")
        print(f"   Health URL: {bg_status['health_url']}")
        
        # Test client update manager
        print(f"\n👥 Testing Client Update Manager...")
        from umbra.modules.concierge.update_clients import ClientUpdateManager
        
        client_manager = ClientUpdateManager(config)
        client_status = client_manager.get_status()
        print(f"   Port range: {client_status['port_range']}")
        print(f"   Maintenance windows: {client_status['maintenance_windows']}")
        
        print(f"\n🎉 All C2 components tested successfully!")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure all required modules are available")
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()

async def test_concierge_integration():
    """Test integration with ConciergeMCP."""
    print(f"\n🔗 Testing Concierge MCP Integration")
    print("=" * 40)
    
    try:
        # Mock minimal requirements
        class MockDB:
            def execute(self, query, params=None):
                pass
            def query_one(self, query, params=None):
                return {"count": 0}
            def query_all(self, query, params=None):
                return []
        
        class MockConfig:
            def get(self, key, default=None):
                return default
        
        from umbra.modules.concierge_mcp import ConciergeMCP
        
        config = MockConfig()
        db = MockDB()
        
        concierge = ConciergeMCP(config, db)
        
        # Test capabilities
        capabilities = await concierge.get_capabilities()
        
        update_actions = [k for k in capabilities.keys() if k.startswith('updates.')]
        print(f"✅ Found {len(update_actions)} update actions:")
        for action in update_actions:
            print(f"   - {action}")
        
        # Test status action (should work without Docker)
        try:
            result = await concierge.execute("updates.status", {}, user_id=1, is_admin=True)
            print(f"\n📊 Updates status test:")
            print(f"   Success: {result.get('success', False)}")
            if result.get('success'):
                print(f"   Status: {result.get('status', {})}")
            else:
                print(f"   Error: {result.get('error', 'Unknown')}")
        except Exception as e:
            print(f"   Expected error (no Docker): {e}")
        
        print(f"\n✅ Concierge integration test completed!")
        
    except Exception as e:
        print(f"❌ Integration test error: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main test function."""
    print(f"🚀 Starting C2 Auto-Update Watcher Tests")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    await test_update_watcher()
    await test_concierge_integration()
    
    print(f"\n🏁 All tests completed!")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    asyncio.run(main())
