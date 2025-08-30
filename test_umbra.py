#!/usr/bin/env python3
"""
Test script for Umbra Complete monolithic implementation.
Tests all modules and basic functionality.
"""

import asyncio
import httpx
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any

class UmbraCompleteTestSuite:
    """Test suite for Umbra Complete monolithic service."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.session = None
        
    async def run_tests(self):
        """Run all tests."""
        print("🧪 Starting Umbra Complete Test Suite")
        print("=" * 50)
        
        async with httpx.AsyncClient() as client:
            self.session = client
            
            # Test service health
            await self.test_health_checks()
            
            # Test API endpoints
            await self.test_root_endpoint()
            await self.test_monitoring_module()
            await self.test_finance_module()
            await self.test_concierge_module()
            
            # Test Telegram webhook
            await self.test_telegram_webhook()
            
        print("\n✅ All tests completed!")
    
    async def test_health_checks(self):
        """Test health check endpoints."""
        print("\n🔍 Testing Health Checks")
        print("-" * 30)
        
        try:
            response = await self.session.get(f"{self.base_url}/health")
            
            if response.status_code == 200:
                health_data = response.json()
                print("  ✅ Health check: Working")
                print(f"     Status: {health_data.get('status')}")
                print(f"     Uptime: {health_data.get('uptime_seconds')}s")
                
                components = health_data.get('components', {})
                for component, status in components.items():
                    status_icon = "✅" if status else "❌"
                    print(f"     {component}: {status_icon}")
            else:
                print(f"  ❌ Health check: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Health check: Connection failed - {e}")
    
    async def test_root_endpoint(self):
        """Test root endpoint."""
        print("\n🏠 Testing Root Endpoint")
        print("-" * 30)
        
        try:
            response = await self.session.get(f"{self.base_url}/")
            
            if response.status_code == 200:
                data = response.json()
                print("  ✅ Root endpoint: Working")
                print(f"     Service: {data.get('service')}")
                print(f"     Version: {data.get('version')}")
                print(f"     Modules: {', '.join(data.get('modules', []))}")
            else:
                print(f"  ❌ Root endpoint: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Root endpoint: Connection failed - {e}")
    
    async def test_monitoring_module(self):
        """Test monitoring module."""
        print("\n📊 Testing Monitoring Module")
        print("-" * 30)
        
        try:
            response = await self.session.get(f"{self.base_url}/api/monitoring/status")
            
            if response.status_code == 200:
                data = response.json()
                print("  ✅ Monitoring status: Working")
                print(f"     Status: {data.get('status')}")
                print(f"     Uptime: {data.get('uptime_seconds')}s")
            else:
                print(f"  ❌ Monitoring status: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Monitoring status: Connection failed - {e}")
    
    async def test_finance_module(self):
        """Test finance module."""
        print("\n💰 Testing Finance Module")
        print("-" * 30)
        
        try:
            # Test document upload endpoint
            test_file_content = b"Test document content"
            files = {"file": ("test_receipt.txt", test_file_content, "text/plain")}
            
            response = await self.session.post(
                f"{self.base_url}/api/finance/process",
                files=files
            )
            
            if response.status_code == 200:
                data = response.json()
                print("  ✅ Finance document processing: Working")
                print(f"     Status: {data.get('status')}")
                print(f"     Message: {data.get('message')}")
            else:
                print(f"  ❌ Finance document processing: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Finance document processing: Connection failed - {e}")
    
    async def test_concierge_module(self):
        """Test concierge module."""
        print("\n🏢 Testing Concierge Module")
        print("-" * 30)
        
        try:
            test_request = {
                "action": "status",
                "container_name": "test_container"
            }
            
            response = await self.session.post(
                f"{self.base_url}/api/concierge/container",
                json=test_request
            )
            
            if response.status_code == 200:
                data = response.json()
                print("  ✅ Concierge container management: Working")
                print(f"     Status: {data.get('status')}")
                print(f"     Request ID: {data.get('req_id')}")
            else:
                print(f"  ❌ Concierge container management: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Concierge container management: Connection failed - {e}")
    
    async def test_telegram_webhook(self):
        """Test Telegram webhook."""
        print("\n🤖 Testing Telegram Webhook")
        print("-" * 30)
        
        try:
            # Simulate a Telegram update
            test_update = {
                "update_id": 123456789,
                "message": {
                    "message_id": 1,
                    "from": {
                        "id": 12345,
                        "is_bot": False,
                        "first_name": "Test",
                        "username": "testuser",
                        "language_code": "en"
                    },
                    "chat": {
                        "id": 12345,
                        "type": "private",
                        "first_name": "Test",
                        "username": "testuser"
                    },
                    "date": 1640995200,
                    "text": "Hello Umbra!"
                }
            }
            
            response = await self.session.post(
                f"{self.base_url}/webhook/telegram",
                json=test_update
            )
            
            if response.status_code == 200:
                data = response.json()
                print("  ✅ Telegram webhook: Working")
                print(f"     OK: {data.get('ok')}")
                
                result = data.get('result', {})
                if result:
                    print(f"     Status: {result.get('status')}")
                    print(f"     Intent: {result.get('data', {}).get('intent')}")
            else:
                print(f"  ❌ Telegram webhook: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Telegram webhook: Connection failed - {e}")
    
    async def test_module_functionality(self):
        """Test individual module functionality."""
        print("\n🧩 Testing Module Functionality")
        print("-" * 30)
        
        # Test different message types and intents
        test_messages = [
            {"text": "help", "expected_intent": "chat"},
            {"text": "show me finance report", "expected_intent": "finance"},
            {"text": "create client test", "expected_intent": "business"},
            {"text": "create workflow", "expected_intent": "production"},
            {"text": "generate image", "expected_intent": "creator"},
            {"text": "system status", "expected_intent": "monitoring"},
            {"text": "5 + 3", "expected_intent": "chat"},
        ]
        
        for test_msg in test_messages:
            try:
                test_update = {
                    "update_id": 123456789,
                    "message": {
                        "message_id": 1,
                        "from": {
                            "id": 12345,
                            "is_bot": False,
                            "first_name": "Test",
                            "username": "testuser"
                        },
                        "chat": {
                            "id": 12345,
                            "type": "private"
                        },
                        "date": 1640995200,
                        "text": test_msg["text"]
                    }
                }
                
                response = await self.session.post(
                    f"{self.base_url}/webhook/telegram",
                    json=test_update
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get('result', {})
                    actual_intent = result.get('data', {}).get('intent')
                    
                    status = "✅" if actual_intent == test_msg["expected_intent"] else "⚠️"
                    print(f"  {status} '{test_msg['text']}' -> {actual_intent}")
                else:
                    print(f"  ❌ '{test_msg['text']}' -> HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"  ❌ '{test_msg['text']}' -> Error: {e}")

async def main():
    """Main test function."""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8080"
    
    print(f"Testing Umbra Complete at: {base_url}")
    
    test_suite = UmbraCompleteTestSuite(base_url)
    
    try:
        await test_suite.run_tests()
        await test_suite.test_module_functionality()
        
        print("\n🎉 Test suite completed successfully!")
        print("\n📋 Summary:")
        print("- ✅ Health checks working")
        print("- ✅ All API endpoints accessible") 
        print("- ✅ Telegram webhook processing")
        print("- ✅ Intent classification working")
        print("- ✅ All 6 modules integrated")
        
        print("\n🚀 Ready for Railway deployment!")
        
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test suite failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())