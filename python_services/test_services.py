#!/usr/bin/env python3
"""
Test script for Umbra Python services.
Tests basic functionality of each service.
"""

import asyncio
import httpx
import json
import sys
from typing import Dict, Any


class UmbraTestSuite:
    """Test suite for Umbra Python services."""
    
    def __init__(self, base_url: str = "http://localhost"):
        self.base_url = base_url
        self.services = {
            "umbra": 8080,
            "finance": 8081,
        }
        
    async def run_tests(self):
        """Run all tests."""
        print("🧪 Starting Umbra Python Services Test Suite")
        print("=" * 50)
        
        # Test service health
        await self.test_health_checks()
        
        # Test basic functionality
        await self.test_umbra_functionality()
        await self.test_finance_functionality()
        
        print("\n✅ All tests completed!")
    
    async def test_health_checks(self):
        """Test health endpoints for all services."""
        print("\n🏥 Testing Health Checks")
        print("-" * 30)
        
        async with httpx.AsyncClient() as client:
            for service, port in self.services.items():
                try:
                    url = f"{self.base_url}:{port}/health"
                    response = await client.get(url, timeout=5.0)
                    
                    if response.status_code == 200:
                        print(f"✅ {service.title()} service: Healthy")
                    else:
                        print(f"❌ {service.title()} service: Unhealthy ({response.status_code})")
                        
                except Exception as e:
                    print(f"❌ {service.title()} service: Connection failed - {e}")
    
    async def test_umbra_functionality(self):
        """Test Umbra main agent functionality."""
        print("\n🤖 Testing Umbra Main Agent")
        print("-" * 30)
        
        # Test root endpoint
        await self._test_endpoint("umbra", 8080, "/", "GET")
        
        # Test intent classification (would need proper envelope)
        test_envelope = {
            "req_id": "test-001",
            "user_id": "test_user",
            "lang": "EN",
            "timestamp": "2024-01-01T00:00:00Z",
            "payload": {
                "action": "classify",
                "message": "Hello, I need help with my invoice"
            }
        }
        
        print("  Testing intent classification...")
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}:8080/api/v1/classify"
                response = await client.post(
                    url,
                    json=test_envelope,
                    headers={"Content-Type": "application/json"},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    print("  ✅ Intent classification: Working")
                else:
                    print(f"  ⚠️ Intent classification: {response.status_code} (may need auth)")
                    
        except Exception as e:
            print(f"  ❌ Intent classification: {e}")
    
    async def test_finance_functionality(self):
        """Test Finance module functionality."""
        print("\n💰 Testing Finance Module")
        print("-" * 30)
        
        # Test root endpoint
        await self._test_endpoint("finance", 8081, "/", "GET")
        
        # Test OCR endpoint (would need proper envelope)
        test_envelope = {
            "req_id": "test-002",
            "user_id": "test_user",
            "lang": "EN",
            "timestamp": "2024-01-01T00:00:00Z",
            "payload": {
                "action": "ocr",
                "document_url": "https://example.com/invoice.pdf",
                "document_type": "invoice"
            }
        }
        
        print("  Testing OCR processing...")
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}:8081/api/v1/ocr"
                response = await client.post(
                    url,
                    json=test_envelope,
                    headers={"Content-Type": "application/json"},
                    timeout=15.0
                )
                
                if response.status_code == 200:
                    print("  ✅ OCR processing: Working")
                else:
                    print(f"  ⚠️ OCR processing: {response.status_code} (may need auth)")
                    
        except Exception as e:
            print(f"  ❌ OCR processing: {e}")
    
    async def _test_endpoint(self, service: str, port: int, path: str, method: str = "GET"):
        """Test a specific endpoint."""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}:{port}{path}"
                
                if method == "GET":
                    response = await client.get(url, timeout=5.0)
                else:
                    response = await client.post(url, timeout=5.0)
                
                if response.status_code == 200:
                    print(f"  ✅ {service.title()} {path}: Working")
                    return True
                else:
                    print(f"  ❌ {service.title()} {path}: {response.status_code}")
                    return False
                    
        except Exception as e:
            print(f"  ❌ {service.title()} {path}: Connection failed - {e}")
            return False


async def main():
    """Main test function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Umbra Python services")
    parser.add_argument(
        "--base-url",
        default="http://localhost",
        help="Base URL for services (default: http://localhost)"
    )
    
    args = parser.parse_args()
    
    tester = UmbraTestSuite(args.base_url)
    await tester.run_tests()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test suite failed: {e}")
        sys.exit(1)