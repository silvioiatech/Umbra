#!/usr/bin/env python3
"""
Test script for BUS1: Business Instance Gateway

Tests the Business module functionality to ensure:
- Proper pass-through to Concierge module
- Validation of client IDs and parameters
- Correct formatting for Telegram responses
- Error handling and propagation
"""
import sys
import os
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from umbra.core.config import config
from umbra.storage.database import DatabaseManager
from umbra.modules.business_mcp import BusinessMCP, InstanceSummary, InstanceDetails, DeletionResult
from umbra.modules.business.concierge_client import ConciergeBridge
from umbra.modules.business.formatters import InstanceFormatter

class MockConciergeMCP:
    """Mock Concierge module for testing."""
    
    def __init__(self):
        self.instances_db = {}
        self.next_port = 20000
        self.audit_counter = 1000
    
    async def execute(self, action: str, params: dict, user_id: int, is_admin: bool = False) -> dict:
        """Mock execute method that simulates Concierge behavior."""
        
        if action == "instances.create":
            client = params.get("client")
            name = params.get("name", f"n8n-{client}")
            port = params.get("port", self.next_port)
            
            if client in self.instances_db:
                return {
                    "success": False,
                    "error": f"Instance already exists for client: {client}"
                }
            
            if port == self.next_port:
                self.next_port += 1
            
            instance = {
                "client_id": client,
                "display_name": name,
                "url": f"http://localhost:{port}",
                "port": port,
                "data_dir": f"/srv/n8n-clients/{client}",
                "status": "running",
                "created_at": "2024-01-01 10:00:00",
                "updated_at": "2024-01-01 10:00:00"
            }
            
            self.instances_db[client] = instance
            audit_id = f"inst_{self.audit_counter}_{client}"
            self.audit_counter += 1
            
            return {
                "success": True,
                "instance": instance,
                "audit_id": audit_id,
                "message": f"Instance created successfully: {client}"
            }
        
        elif action == "instances.list":
            client_filter = params.get("client")
            
            if client_filter:
                if client_filter in self.instances_db:
                    return {
                        "success": True,
                        "instances": [self.instances_db[client_filter]]
                    }
                else:
                    return {
                        "success": True,
                        "instances": []
                    }
            else:
                return {
                    "success": True,
                    "instances": list(self.instances_db.values()),
                    "count": len(self.instances_db)
                }
        
        elif action == "instances.delete":
            client = params.get("client")
            mode = params.get("mode", "keep")
            
            if client not in self.instances_db:
                return {
                    "success": False,
                    "error": f"Instance not found: {client}"
                }
            
            if mode == "wipe":
                del self.instances_db[client]
            else:  # keep
                self.instances_db[client]["status"] = "archived"
                self.instances_db[client]["reserved"] = True
            
            audit_id = f"inst_{self.audit_counter}_{client}"
            self.audit_counter += 1
            
            return {
                "success": True,
                "message": f"Instance {client} deleted successfully (mode: {mode})",
                "audit_id": audit_id
            }
        
        elif action == "instances.stats":
            total_instances = len(self.instances_db)
            by_status = {}
            for instance in self.instances_db.values():
                status = instance.get("status", "unknown")
                by_status[status] = by_status.get(status, 0) + 1
            
            return {
                "success": True,
                "port_usage": {
                    "total_ports": 1000,
                    "used_ports": total_instances,
                    "available_ports": 1000 - total_instances,
                    "utilization_percent": (total_instances / 1000) * 100,
                    "port_range": "20000-21000"
                },
                "instance_counts": {
                    "total": total_instances,
                    "by_status": by_status
                }
            }
        
        else:
            return {
                "success": False,
                "error": f"Unknown action: {action}"
            }

class TestBUS1Implementation:
    """Test suite for BUS1 Business module functionality."""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="umbra_test_bus1_")
        self.test_db_path = os.path.join(self.temp_dir, "test.db")
        
        print(f"🧪 Test environment: {self.temp_dir}")
        
        # Create test database manager
        self.db_manager = DatabaseManager(self.test_db_path)
        
        # Create test configuration
        self.test_config = type('TestConfig', (), {
            'CLIENT_PORT_RANGE': '20000-21000'
        })()
        
        # Create mock Concierge module
        self.mock_concierge = MockConciergeMCP()
        
        # Create Business module with mock Concierge
        self.business = BusinessMCP(
            self.test_config, 
            self.db_manager, 
            concierge_module=self.mock_concierge
        )
        
        print("✅ Test environment initialized")
    
    async def test_client_id_validation(self):
        """Test client ID validation logic."""
        print("\n🔍 Testing client ID validation...")
        
        # Valid client IDs
        valid_ids = ["client1", "test-client", "a", "client-123", "x" * 32]
        for client_id in valid_ids:
            error = self.business._validate_client_id(client_id)
            assert error is None, f"Valid client ID '{client_id}' was rejected: {error}"
        
        print(f"  ✅ Valid client IDs accepted: {len(valid_ids)}")
        
        # Invalid client IDs
        invalid_ids = [
            ("", "empty string"),
            ("Client1", "uppercase"),
            ("client_1", "underscore"),
            ("client.1", "dot"),
            ("client 1", "space"),
            ("x" * 33, "too long"),
            ("123client", "starts with number is ok, but let's test"),
            ("client!", "special character")
        ]
        
        valid_rejections = 0
        for client_id, reason in invalid_ids:
            error = self.business._validate_client_id(client_id)
            if client_id == "123client":
                # This should actually be valid
                if error is None:
                    continue
            assert error is not None, f"Invalid client ID '{client_id}' ({reason}) was accepted"
            valid_rejections += 1
        
        print(f"  ✅ Invalid client IDs rejected: {valid_rejections}")
        
        print("✅ Client ID validation tests passed")
    
    async def test_port_validation(self):
        """Test port validation logic."""
        print("\n🔍 Testing port validation...")
        
        # Valid ports
        valid_ports = [20000, 20500, 21000]
        for port in valid_ports:
            error = self.business._validate_port(port)
            assert error is None, f"Valid port {port} was rejected: {error}"
        
        print(f"  ✅ Valid ports accepted: {len(valid_ports)}")
        
        # Invalid ports
        invalid_ports = [19999, 21001, 80, 65536, -1, "20000"]
        valid_rejections = 0
        for port in invalid_ports:
            error = self.business._validate_port(port)
            assert error is not None, f"Invalid port {port} was accepted"
            valid_rejections += 1
        
        print(f"  ✅ Invalid ports rejected: {valid_rejections}")
        
        print("✅ Port validation tests passed")
    
    async def test_instance_creation(self):
        """Test instance creation workflow."""
        print("\n🔍 Testing instance creation...")
        
        # Test basic instance creation
        result = await self.business.execute(
            "create_instance",
            {"client": "test-client-1", "name": "Test Instance 1"},
            user_id=123,
            is_admin=True
        )
        
        assert result.get("success"), f"Instance creation failed: {result.get('error')}"
        assert "instance" in result, "Instance data not returned"
        assert "formatted" in result, "Formatted output not returned"
        assert result["instance"]["client_id"] == "test-client-1", "Wrong client ID"
        
        print(f"  ✅ Instance created: {result['instance']['client_id']}")
        
        # Test creation with specific port
        result2 = await self.business.execute(
            "create_instance",
            {"client": "test-client-2", "port": 20005},
            user_id=123,
            is_admin=True
        )
        
        assert result2.get("success"), f"Port-specific creation failed: {result2.get('error')}"
        assert result2["instance"]["port"] == 20005, "Wrong port assigned"
        
        print(f"  ✅ Instance with specific port created: port {result2['instance']['port']}")
        
        # Test duplicate creation (should fail)
        duplicate_result = await self.business.execute(
            "create_instance",
            {"client": "test-client-1"},
            user_id=123,
            is_admin=True
        )
        
        assert not duplicate_result.get("success"), "Duplicate creation should fail"
        assert "already exists" in duplicate_result.get("error", "").lower(), "Wrong error message"
        
        print("  ✅ Duplicate creation correctly rejected")
        
        # Test validation errors
        invalid_result = await self.business.execute(
            "create_instance",
            {"client": "Invalid Client!"},
            user_id=123,
            is_admin=True
        )
        
        assert not invalid_result.get("success"), "Invalid client ID should be rejected"
        
        print("  ✅ Invalid client ID correctly rejected")
        
        print("✅ Instance creation tests passed")
    
    async def test_instance_listing(self):
        """Test instance listing functionality."""
        print("\n🔍 Testing instance listing...")
        
        # List all instances
        list_result = await self.business.execute(
            "list_instances",
            {},
            user_id=123,
            is_admin=False
        )
        
        assert list_result.get("success"), f"Instance listing failed: {list_result.get('error')}"
        assert "instances" in list_result, "Instances list not returned"
        assert list_result["count"] >= 2, f"Expected at least 2 instances, got {list_result['count']}"
        assert "formatted" in list_result, "Formatted output not returned"
        
        print(f"  ✅ Listed {list_result['count']} instances")
        
        # List specific instance
        specific_result = await self.business.execute(
            "list_instances",
            {"client": "test-client-1"},
            user_id=123,
            is_admin=False
        )
        
        assert specific_result.get("success"), f"Specific listing failed: {specific_result.get('error')}"
        assert "instance" in specific_result, "Single instance not returned"
        assert specific_result["instance"]["client_id"] == "test-client-1", "Wrong instance returned"
        
        print("  ✅ Specific instance listing works")
        
        # Test non-existent instance
        missing_result = await self.business.execute(
            "list_instances",
            {"client": "non-existent"},
            user_id=123,
            is_admin=False
        )
        
        # Should succeed but return empty list
        assert missing_result.get("success"), "Missing instance query should succeed"
        
        print("  ✅ Non-existent instance handled correctly")
        
        print("✅ Instance listing tests passed")
    
    async def test_instance_deletion(self):
        """Test instance deletion functionality."""
        print("\n🔍 Testing instance deletion...")
        
        # Test deletion with 'keep' mode
        keep_result = await self.business.execute(
            "delete_instance",
            {"client": "test-client-1", "mode": "keep"},
            user_id=123,
            is_admin=True
        )
        
        assert keep_result.get("success"), f"Keep deletion failed: {keep_result.get('error')}"
        assert "result" in keep_result, "Deletion result not returned"
        assert keep_result["result"]["mode"] == "keep", "Wrong deletion mode"
        assert "audit_id" in keep_result, "Audit ID not returned"
        
        print("  ✅ Instance deleted with 'keep' mode")
        
        # Test deletion with 'wipe' mode
        wipe_result = await self.business.execute(
            "delete_instance",
            {"client": "test-client-2", "mode": "wipe"},
            user_id=123,
            is_admin=True
        )
        
        assert wipe_result.get("success"), f"Wipe deletion failed: {wipe_result.get('error')}"
        assert wipe_result["result"]["mode"] == "wipe", "Wrong deletion mode"
        
        print("  ✅ Instance deleted with 'wipe' mode")
        
        # Test deletion of non-existent instance
        missing_delete_result = await self.business.execute(
            "delete_instance",
            {"client": "non-existent", "mode": "keep"},
            user_id=123,
            is_admin=True
        )
        
        assert not missing_delete_result.get("success"), "Non-existent deletion should fail"
        assert "not found" in missing_delete_result.get("error", "").lower(), "Wrong error message"
        
        print("  ✅ Non-existent instance deletion correctly rejected")
        
        # Test invalid mode
        invalid_mode_result = await self.business.execute(
            "delete_instance",
            {"client": "test-client-1", "mode": "invalid"},
            user_id=123,
            is_admin=True
        )
        
        assert not invalid_mode_result.get("success"), "Invalid mode should be rejected"
        
        print("  ✅ Invalid deletion mode correctly rejected")
        
        print("✅ Instance deletion tests passed")
    
    async def test_formatting(self):
        """Test formatter functionality."""
        print("\n🔍 Testing formatting...")
        
        formatter = InstanceFormatter()
        
        # Test instance list formatting
        instances = [
            {
                "client_id": "client1",
                "display_name": "Client 1",
                "url": "http://localhost:20001",
                "port": 20001,
                "status": "running"
            },
            {
                "client_id": "client2", 
                "display_name": "Client 2",
                "url": "http://localhost:20002",
                "port": 20002,
                "status": "stopped"
            }
        ]
        
        list_formatted = formatter.format_instances_list(instances)
        assert "Client Instances" in list_formatted, "Missing header"
        assert "client1" in list_formatted, "Missing instance 1"
        assert "client2" in list_formatted, "Missing instance 2"
        assert "🟢" in list_formatted, "Missing running status emoji"
        assert "🔴" in list_formatted, "Missing stopped status emoji"
        
        print("  ✅ Instance list formatting works")
        
        # Test detailed formatting
        instance_details = {
            "client_id": "client1",
            "display_name": "Client 1",
            "url": "http://localhost:20001",
            "port": 20001,
            "status": "running",
            "data_dir": "/srv/n8n-clients/client1",
            "reserved": False,
            "created_at": "2024-01-01 10:00:00",
            "updated_at": "2024-01-01 10:00:00"
        }
        
        details_formatted = formatter.format_instance_details(instance_details)
        assert "Client 1" in details_formatted, "Missing display name"
        assert "Data Directory" in details_formatted, "Missing data directory"
        assert "Open n8n Interface" in details_formatted, "Missing access link"
        
        print("  ✅ Instance details formatting works")
        
        # Test stats formatting
        stats = {
            "port_usage": {
                "total_ports": 1000,
                "used_ports": 2,
                "available_ports": 998,
                "utilization_percent": 0.2,
                "port_range": "20000-21000"
            },
            "instance_counts": {
                "total": 2,
                "by_status": {"running": 1, "stopped": 1}
            }
        }
        
        stats_formatted = formatter.format_instance_stats(stats)
        assert "Instance Registry Statistics" in stats_formatted, "Missing stats header"
        assert "20000-21000" in stats_formatted, "Missing port range"
        assert "2/1000" in stats_formatted, "Missing usage info"
        
        print("  ✅ Statistics formatting works")
        
        print("✅ Formatting tests passed")
    
    async def test_admin_permissions(self):
        """Test admin permission enforcement."""
        print("\n🔍 Testing admin permissions...")
        
        # Non-admin should not be able to create instances
        create_result = await self.business.execute(
            "create_instance",
            {"client": "test-admin"},
            user_id=456,
            is_admin=False
        )
        
        assert not create_result.get("success"), "Non-admin should not be able to create instances"
        assert "admin" in create_result.get("error", "").lower(), "Wrong error message"
        
        print("  ✅ Non-admin create correctly blocked")
        
        # Non-admin should not be able to delete instances
        delete_result = await self.business.execute(
            "delete_instance",
            {"client": "test-admin", "mode": "keep"},
            user_id=456,
            is_admin=False
        )
        
        assert not delete_result.get("success"), "Non-admin should not be able to delete instances"
        assert "admin" in delete_result.get("error", "").lower(), "Wrong error message"
        
        print("  ✅ Non-admin delete correctly blocked")
        
        # Non-admin should be able to list instances
        list_result = await self.business.execute(
            "list_instances",
            {},
            user_id=456,
            is_admin=False
        )
        
        assert list_result.get("success"), "Non-admin should be able to list instances"
        
        print("  ✅ Non-admin list correctly allowed")
        
        print("✅ Admin permission tests passed")
    
    async def test_health_check(self):
        """Test health check functionality."""
        print("\n🔍 Testing health check...")
        
        health = await self.business.health_check()
        
        assert "status" in health, "Missing health status"
        assert "checks" in health, "Missing health checks"
        assert "mode" in health, "Missing mode info"
        
        checks = health["checks"]
        assert "concierge_bridge" in checks, "Missing concierge bridge check"
        assert "configuration" in checks, "Missing configuration check"
        
        print(f"  ✅ Health status: {health['status']}")
        print(f"  ✅ Checks performed: {list(checks.keys())}")
        
        print("✅ Health check tests passed")
    
    async def run_all_tests(self):
        """Run all tests."""
        print("🚀 Starting BUS1 Business Module Tests")
        print("=" * 50)
        
        try:
            await self.test_client_id_validation()
            await self.test_port_validation()
            await self.test_instance_creation()
            await self.test_instance_listing()
            await self.test_instance_deletion()
            await self.test_formatting()
            await self.test_admin_permissions()
            await self.test_health_check()
            
            print("\n" + "=" * 50)
            print("🎉 ALL TESTS PASSED!")
            print("✅ BUS1 Business module implementation is working correctly")
            return True
            
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            # Cleanup
            try:
                await self.db_manager.close()
                import shutil
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                print(f"🧹 Test environment cleaned up: {self.temp_dir}")
            except Exception as e:
                print(f"⚠️ Cleanup warning: {e}")

async def main():
    """Main test function."""
    print("🤖 Umbra BUS1: Business Instance Gateway Test")
    print("Testing implementation of BUS1 features...")
    print()
    
    tester = TestBUS1Implementation()
    success = await tester.run_all_tests()
    
    if success:
        print("\n📋 **Summary**: BUS1 implementation is ready!")
        print("   • Instance gateway to Concierge ✅")
        print("   • Client ID and port validation ✅")
        print("   • Pass-through operations ✅")
        print("   • Telegram formatting ✅")
        print("   • Admin permission enforcement ✅")
        print("   • Error handling and propagation ✅")
        print()
        print("🚀 **Next Steps**:")
        print("   • Integrate with main module registry")
        print("   • Test with real Concierge module")
        print("   • Add Telegram command handlers")
        print("   • Set up production configuration")
        return 0
    else:
        print("\n❌ BUS1 implementation has issues that need to be fixed.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
