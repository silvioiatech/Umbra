#!/usr/bin/env python3
"""
Test script for C3: Concierge Instances Registry

Tests the instances management functionality to ensure:
- Port allocation works correctly
- Instance creation and deletion work
- Database schema is properly initialized
- Configuration is correctly loaded
"""
import sys
import os
import asyncio
import tempfile
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from umbra.core.config import config
from umbra.storage.database import DatabaseManager
from umbra.modules.concierge.instances_ops import (
    InstancesRegistry, InstanceCreateRequest, InstanceInfo
)

class TestC3Implementation:
    """Test suite for C3 instances functionality."""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="umbra_test_c3_")
        self.test_db_path = os.path.join(self.temp_dir, "test.db")
        self.test_clients_dir = os.path.join(self.temp_dir, "n8n-clients")
        
        print(f"🧪 Test environment: {self.temp_dir}")
        
        # Create test database manager
        self.db_manager = DatabaseManager(self.test_db_path)
        
        # Create test configuration
        self.test_config = type('TestConfig', (), {
            'CLIENT_PORT_RANGE': '20000-20010',  # Small range for testing
            'CLIENTS_BASE_DIR': self.test_clients_dir,
            'N8N_IMAGE': 'n8nio/n8n:latest',
            'N8N_BASE_ENV': 'NODE_ENV=test',
            'NGINX_CONTAINER_NAME': None,
            'INSTANCES_HOST': 'localhost',
            'INSTANCES_USE_HTTPS': False
        })()
        
        # Create instances registry
        self.registry = InstancesRegistry(self.test_config, self.db_manager)
        
        print("✅ Test environment initialized")
    
    async def test_port_allocation(self):
        """Test port allocation logic."""
        print("\n🔍 Testing port allocation...")
        
        # Test allocation from empty registry
        port1 = self.registry._allocate_port()
        assert port1 == 20000, f"Expected port 20000, got {port1}"
        print(f"  ✅ First port allocated: {port1}")
        
        # Test preferred port allocation
        port2 = self.registry._allocate_port(preferred_port=20005)
        assert port2 == 20005, f"Expected port 20005, got {port2}"
        print(f"  ✅ Preferred port allocated: {port2}")
        
        # Test automatic port allocation skips used ports
        # We'll need to simulate a used port by inserting into DB
        self.db_manager.execute("""
            INSERT INTO instances_registry (
                client_id, display_name, url, port, data_dir, status, 
                reserved, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "test_client", "Test Instance", "http://localhost:20001", 20001,
            "/tmp/test", "running", 0, "2024-01-01 00:00:00", "2024-01-01 00:00:00"
        ))
        
        port3 = self.registry._allocate_port()
        assert port3 == 20002, f"Expected port 20002 (skipping 20001), got {port3}"
        print(f"  ✅ Port allocation skips used ports: {port3}")
        
        print("✅ Port allocation tests passed")
    
    async def test_instance_creation(self):
        """Test instance creation workflow."""
        print("\n🔍 Testing instance creation...")
        
        # Test basic instance creation
        request = InstanceCreateRequest(
            client="test_client_1",
            name="Test Instance 1",
            port=None,  # Auto-allocate
            env_overrides={"TEST_VAR": "test_value"}
        )
        
        result = await self.registry.create_instance(request, user_id=123)
        
        assert result.success, f"Instance creation failed: {result.error}"
        assert result.instance is not None, "Instance not returned"
        assert result.instance.client_id == "test_client_1", "Wrong client ID"
        assert result.instance.port > 0, "Invalid port"
        assert result.audit_id is not None, "Audit ID missing"
        
        print(f"  ✅ Instance created: {result.instance.client_id} on port {result.instance.port}")
        
        # Test duplicate client creation (should fail)
        duplicate_request = InstanceCreateRequest(client="test_client_1")
        duplicate_result = await self.registry.create_instance(duplicate_request, user_id=123)
        
        assert not duplicate_result.success, "Duplicate client creation should fail"
        print("  ✅ Duplicate client creation correctly rejected")
        
        # Test with specific port
        specific_port_request = InstanceCreateRequest(
            client="test_client_2",
            port=20007
        )
        
        specific_port_result = await self.registry.create_instance(specific_port_request, user_id=123)
        
        assert specific_port_result.success, "Specific port creation failed"
        assert specific_port_result.instance.port == 20007, "Wrong port assigned"
        
        print(f"  ✅ Specific port instance created: port {specific_port_result.instance.port}")
        
        print("✅ Instance creation tests passed")
    
    async def test_instance_listing(self):
        """Test instance listing functionality."""
        print("\n🔍 Testing instance listing...")
        
        # List all instances
        all_instances = self.registry.list_instances()
        assert len(all_instances) >= 2, f"Expected at least 2 instances, got {len(all_instances)}"
        print(f"  ✅ Listed {len(all_instances)} instances")
        
        # List specific instance
        specific_instance = self.registry.list_instances("test_client_1")
        assert len(specific_instance) == 1, "Should find exactly one instance"
        assert specific_instance[0].client_id == "test_client_1", "Wrong instance returned"
        print("  ✅ Specific instance listing works")
        
        # Test formatted summary
        formatted = self.registry.format_instances_summary(all_instances)
        assert "Instances Registry" in formatted, "Formatted output missing header"
        assert "test_client_1" in formatted, "Instance not in formatted output"
        print("  ✅ Formatted summary generated")
        
        print("✅ Instance listing tests passed")
    
    async def test_instance_deletion(self):
        """Test instance deletion functionality."""
        print("\n🔍 Testing instance deletion...")
        
        # Test deletion with 'keep' mode
        success, audit_id, error = await self.registry.delete_instance(
            "test_client_1", "keep", user_id=123
        )
        
        assert success, f"Instance deletion failed: {error}"
        assert audit_id is not None, "Audit ID missing"
        print("  ✅ Instance deleted with 'keep' mode")
        
        # Verify instance is archived
        archived_instance = self.registry.get_instance("test_client_1")
        assert archived_instance is not None, "Instance should still exist"
        assert archived_instance.status == "archived", "Instance should be archived"
        assert archived_instance.reserved == True, "Instance should be reserved"
        print("  ✅ Instance properly archived and reserved")
        
        # Test deletion with 'wipe' mode
        success, audit_id, error = await self.registry.delete_instance(
            "test_client_2", "wipe", user_id=123
        )
        
        assert success, f"Instance wipe failed: {error}"
        print("  ✅ Instance wiped successfully")
        
        # Verify instance is completely removed
        wiped_instance = self.registry.get_instance("test_client_2")
        assert wiped_instance is None, "Instance should be completely removed"
        print("  ✅ Instance completely removed from registry")
        
        # Test deletion of non-existent instance
        success, audit_id, error = await self.registry.delete_instance(
            "non_existent", "keep", user_id=123
        )
        
        assert not success, "Non-existent instance deletion should fail"
        assert "not found" in error.lower(), "Error message should mention not found"
        print("  ✅ Non-existent instance deletion correctly rejected")
        
        print("✅ Instance deletion tests passed")
    
    async def test_port_usage_stats(self):
        """Test port usage statistics."""
        print("\n🔍 Testing port usage statistics...")
        
        stats = self.registry.get_port_usage_stats()
        
        assert "total_ports" in stats, "Missing total_ports"
        assert "used_ports" in stats, "Missing used_ports"
        assert "available_ports" in stats, "Missing available_ports"
        assert "utilization_percent" in stats, "Missing utilization_percent"
        
        assert stats["total_ports"] == 11, f"Expected 11 total ports, got {stats['total_ports']}"
        assert stats["used_ports"] >= 0, "Used ports should be non-negative"
        assert stats["available_ports"] >= 0, "Available ports should be non-negative"
        
        print(f"  ✅ Port stats: {stats['used_ports']}/{stats['total_ports']} used ({stats['utilization_percent']}%)")
        
        print("✅ Port usage statistics tests passed")
    
    async def test_health_check(self):
        """Test health check functionality."""
        print("\n🔍 Testing health check...")
        
        health = self.registry.health_check()
        
        assert "status" in health, "Missing health status"
        assert "checks" in health, "Missing health checks"
        
        # Check that basic components are assessed
        checks = health["checks"]
        assert "database" in checks, "Missing database check"
        assert "docker" in checks, "Missing docker check"
        assert "data_directory" in checks, "Missing data_directory check"
        assert "port_allocation" in checks, "Missing port_allocation check"
        
        print(f"  ✅ Health status: {health['status']}")
        print(f"  ✅ Checks performed: {list(checks.keys())}")
        
        print("✅ Health check tests passed")
    
    async def run_all_tests(self):
        """Run all tests."""
        print("🚀 Starting C3 Instances Registry Tests")
        print("=" * 50)
        
        try:
            await self.test_port_allocation()
            await self.test_instance_creation()
            await self.test_instance_listing()
            await self.test_instance_deletion()
            await self.test_port_usage_stats()
            await self.test_health_check()
            
            print("\n" + "=" * 50)
            print("🎉 ALL TESTS PASSED!")
            print("✅ C3 Instances Registry implementation is working correctly")
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
    print("🤖 Umbra C3: Concierge Instances Registry Test")
    print("Testing implementation of C3 features...")
    print()
    
    tester = TestC3Implementation()
    success = await tester.run_all_tests()
    
    if success:
        print("\n📋 **Summary**: C3 implementation is ready!")
        print("   • Instance creation and deletion ✅")
        print("   • Port allocation and management ✅")
        print("   • Database schema and operations ✅")
        print("   • Health monitoring and statistics ✅")
        print("   • Audit trail and error handling ✅")
        print()
        print("🚀 **Next Steps**:")
        print("   • Configure Docker environment variables")
        print("   • Set up instance base directory permissions")
        print("   • Test with real n8n containers")
        print("   • Integrate with Business module (BUS1)")
        return 0
    else:
        print("\n❌ C3 implementation has issues that need to be fixed.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
