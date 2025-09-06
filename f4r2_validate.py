#!/usr/bin/env python3
"""
F4R2 Quick Validation Script
============================

Quick health check for F4R2 R2 Object Storage components.
This script verifies that F4R2 is properly configured and functional.

Usage:
    python f4r2_validate.py
    
Exit codes:
    0: All F4R2 components working
    1: Configuration issues
    2: Connection/API issues
    3: Feature limitations
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_imports():
    """Check if all F4R2 modules can be imported."""
    print("🔍 Checking F4R2 imports...")
    
    try:
        from umbra.storage import (
            R2Client, ObjectStorage, ManifestManager, SearchIndex,
            PARQUET_AVAILABLE, get_storage_info
        )
        print("   ✅ All F4R2 modules imported successfully")
        return True, locals()
    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        return False, None

def check_configuration():
    """Check R2 configuration."""
    print("\n🔧 Checking R2 configuration...")
    
    required_vars = [
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID", 
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"   ❌ Missing environment variables: {', '.join(missing_vars)}")
        print("   💡 Set these variables in your .env file or environment")
        return False
    else:
        print("   ✅ All required R2 environment variables present")
        
        # Show configuration (safely)
        account_id = os.getenv("R2_ACCOUNT_ID", "")
        bucket = os.getenv("R2_BUCKET", "")
        endpoint = os.getenv("R2_ENDPOINT", f"https://{account_id}.r2.cloudflarestorage.com")
        
        print(f"   📋 Account ID: {account_id[:8]}..." if account_id else "   📋 Account ID: Not set")
        print(f"   🪣 Bucket: {bucket}")
        print(f"   🌐 Endpoint: {endpoint}")
        
        return True

def check_r2_connection(modules):
    """Check R2 client connection."""
    print("\n🌐 Testing R2 connection...")
    
    try:
        from umbra.core.config import config
        r2_client = modules["R2Client"](config)
        
        print(f"   🔧 R2 configured: {'✅' if r2_client.is_configured() else '❌'}")
        print(f"   🌐 R2 available: {'✅' if r2_client.is_available() else '❌'}")
        
        if r2_client.is_available():
            client_info = r2_client.get_client_info()
            print(f"   🪣 Bucket: {client_info['bucket']}")
            print(f"   🔗 Endpoint: {client_info['endpoint']}")
            return True
        else:
            print("   ❌ R2 client not available - check credentials and network")
            return False
            
    except Exception as e:
        print(f"   ❌ R2 connection failed: {e}")
        return False

def check_storage_stack(modules):
    """Check the complete storage stack."""
    print("\n📦 Testing storage stack...")
    
    try:
        # Initialize components
        storage = modules["ObjectStorage"]()
        manifests = modules["ManifestManager"](storage) 
        search = modules["SearchIndex"](storage)
        
        # Check availability
        storage_ok = storage.is_available()
        manifests_ok = manifests.is_available()
        search_ok = search.is_available()
        
        print(f"   📄 Object Storage: {'✅' if storage_ok else '❌'}")
        print(f"   📝 Manifest Manager: {'✅' if manifests_ok else '❌'}")
        print(f"   🔍 Search Index: {'✅' if search_ok else '❌'}")
        
        return storage_ok and manifests_ok and search_ok
        
    except Exception as e:
        print(f"   ❌ Storage stack initialization failed: {e}")
        return False

def check_features(modules):
    """Check optional features."""
    print("\n✨ Checking optional features...")
    
    # Parquet support
    parquet_available = modules["PARQUET_AVAILABLE"]
    print(f"   🐼 Parquet support: {'✅' if parquet_available else '⚠️  CSV fallback'}")
    
    if not parquet_available:
        print("   💡 Install pyarrow for Parquet support: pip install pyarrow==15.0.2")
    
    # Get storage info
    try:
        storage_info = modules["get_storage_info"]()
        print(f"   📊 F4R2 Version: {storage_info['version']}")
        
        for component, status in storage_info["components"].items():
            print(f"   🔧 {component}: {status}")
            
    except Exception as e:
        print(f"   ⚠️  Could not get storage info: {e}")
    
    return True

def quick_functionality_test(modules):
    """Quick test of basic functionality."""
    print("\n🧪 Quick functionality test...")
    
    try:
        storage = modules["ObjectStorage"]()
        
        if not storage.is_available():
            print("   ⏭️  Skipping functionality test - R2 not available")
            return True
        
        # Test basic object operations (non-destructive)
        print("   🔍 Testing object listing...")
        
        try:
            objects = storage.list_objects(prefix="f4r2_validate_test/", max_keys=1)
            print(f"   ✅ Object listing works ({objects['key_count']} objects found)")
        except Exception as e:
            print(f"   ⚠️  Object listing failed: {e}")
            return False
        
        # Test presigned URL generation (non-destructive)
        print("   🔗 Testing presigned URL generation...")
        
        try:
            url = storage.generate_presigned_url(
                key="f4r2_validate_test/test.txt",
                expiration=300,
                method="upload"
            )
            print("   ✅ Presigned URL generation works")
        except Exception as e:
            print(f"   ⚠️  Presigned URL generation failed: {e}")
            return False
        
        print("   ✅ Basic functionality test passed")
        return True
        
    except Exception as e:
        print(f"   ❌ Functionality test failed: {e}")
        return False

def main():
    """Main validation function."""
    print("🚀 F4R2 Quick Validation")
    print("=" * 40)
    
    # Check imports
    imports_ok, modules = check_imports()
    if not imports_ok:
        print("\n❌ F4R2 validation failed: Import errors")
        return 1
    
    # Check configuration
    config_ok = check_configuration()
    if not config_ok:
        print("\n❌ F4R2 validation failed: Configuration issues")
        return 1
    
    # Check R2 connection
    connection_ok = check_r2_connection(modules)
    if not connection_ok:
        print("\n❌ F4R2 validation failed: Connection issues")
        return 2
    
    # Check storage stack
    stack_ok = check_storage_stack(modules)
    if not stack_ok:
        print("\n❌ F4R2 validation failed: Storage stack issues")
        return 2
    
    # Check features
    features_ok = check_features(modules)
    
    # Quick functionality test
    func_ok = quick_functionality_test(modules)
    if not func_ok:
        print("\n❌ F4R2 validation failed: Functionality issues")
        return 2
    
    # Final summary
    print("\n🎉 F4R2 Validation Summary")
    print("=" * 40)
    print("✅ All F4R2 components working correctly!")
    print("✅ R2 connection established")
    print("✅ Storage stack functional")
    print("✅ Basic operations tested")
    
    if not modules["PARQUET_AVAILABLE"]:
        print("⚠️  Parquet support not available (using CSV fallback)")
        print("💡 Consider: pip install pyarrow==15.0.2")
        return 3
    
    print("\n🚀 F4R2 ready for production use!")
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⏹️  Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Unexpected error during validation: {e}")
        sys.exit(2)
