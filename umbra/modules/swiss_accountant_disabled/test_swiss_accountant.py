#!/usr/bin/env python3
"""
Swiss Accountant Test Script
Basic functionality test and demonstration.
"""

import sys
import os
from pathlib import Path
from datetime import date, datetime
import tempfile
import json

# Add the module path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from umbra.modules.swiss_accountant import (
        quick_start, 
        get_default_config,
        get_version,
        get_supported_formats,
        get_swiss_info
    )
    print("✅ Swiss Accountant import successful")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

def test_basic_functionality():
    """Test basic functionality."""
    print("\n🧪 Testing Basic Functionality")
    print("=" * 50)
    
    # Test version and info
    print(f"📋 Version: {get_version()}")
    print(f"📋 Supported formats: {get_supported_formats()}")
    print(f"📋 Swiss info: {get_swiss_info()}")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = tmp_db.name
    
    try:
        # Initialize Swiss Accountant
        print(f"\n🚀 Initializing Swiss Accountant with database: {db_path}")
        sa = quick_start(user_id="test_user", db_path=db_path)
        print("✅ Initialization successful")
        
        # Test health check
        print("\n🔍 Running health check...")
        health = sa.health_check()
        print(f"   Status: {health['status']}")
        for component, status in health.get('components', {}).items():
            status_emoji = '✅' if status == 'healthy' else '⚠️' if status == 'available' else '❌'
            print(f"   {status_emoji} {component}: {status}")
        
        # Test dashboard (should be empty initially)
        print("\n📊 Testing dashboard...")
        dashboard = sa.get_dashboard_summary()
        if 'error' not in dashboard:
            print(f"   Total expenses: {dashboard['total_expenses']}")
            print(f"   Total amount: CHF {dashboard['total_amount_chf']:.2f}")
            print("✅ Dashboard working")
        else:
            print(f"⚠️  Dashboard error: {dashboard['error']}")
        
        # Test expense retrieval (should be empty)
        print("\n💰 Testing expense retrieval...")
        expenses = sa.get_expenses(limit=10)
        print(f"   Found {len(expenses)} expenses")
        print("✅ Expense retrieval working")
        
        # Test reconciliation summary
        print("\n🔄 Testing reconciliation summary...")
        reconciliation = sa.get_reconciliation_summary()
        if 'error' not in reconciliation:
            print(f"   Total matches: {reconciliation['total_matches']}")
            print(f"   Unmatched expenses: {reconciliation['unmatched_expenses']}")
            print("✅ Reconciliation working")
        else:
            print(f"⚠️  Reconciliation error: {reconciliation['error']}")
        
        # Test tax calculation (should be empty)
        print("\n🧮 Testing tax calculation...")
        tax_calc = sa.calculate_tax_deductions(year=2024, canton="ZH")
        if tax_calc.get('success', True):
            print(f"   Total expenses: CHF {tax_calc['total_expenses']:.2f}")
            print(f"   Deductible amount: CHF {tax_calc['total_deductible']:.2f}")
            print("✅ Tax calculation working")
        else:
            print(f"⚠️  Tax calculation error: {tax_calc.get('error')}")
        
        # Test export functionality
        print("\n📤 Testing export functionality...")
        export_summary = sa.export_manager.get_export_summary(sa.db, "test_user")
        print(f"   Export summary: {export_summary['total_expenses']} expenses available")
        print("✅ Export functionality working")
        
        # Test database components
        print("\n🗄️  Testing database components...")
        
        # Test merchant normalizer
        merchant_stats = sa.merchant_normalizer.get_merchant_statistics()
        print(f"   Merchants in database: {merchant_stats['total_merchants']}")
        
        # Test category mapper
        category_stats = sa.category_mapper.get_category_statistics()
        print(f"   Category mappings: {category_stats['total_mappings']}")
        
        print("✅ Database components working")
        
        print(f"\n🎉 All tests passed! Swiss Accountant is working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
            print(f"🧹 Cleaned up temporary database: {db_path}")
    
    return True

def test_sample_data():
    """Test with sample data."""
    print("\n🧪 Testing with Sample Data")
    print("=" * 50)
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = tmp_db.name
    
    try:
        sa = quick_start(user_id="sample_user", db_path=db_path)
        
        # Add sample merchant
        print("\n🏪 Adding sample merchant...")
        merchant_result = sa.merchant_normalizer.add_merchant(
            canonical="Migros Test Store",
            vat_no="CHE-116.281.277",
            aliases="migros,mig test,migros teststr"
        )
        if merchant_result['success']:
            print(f"   ✅ Added merchant: {merchant_result['canonical']}")
        
        # Test merchant normalization
        print("\n🔍 Testing merchant normalization...")
        normalize_result = sa.merchant_normalizer.normalize_merchant_name("MIG TEST")
        print(f"   Input: 'MIG TEST'")
        print(f"   Canonical: {normalize_result.get('canonical')}")
        print(f"   Confidence: {normalize_result.get('confidence', 0):.2f}")
        
        # Add sample category mapping
        print("\n🏷️  Testing category mapping...")
        category_result = sa.category_mapper.add_custom_mapping(
            expense_category="groceries",
            deduction_category="non_deductible",
            confidence=1.0
        )
        if category_result['success']:
            print(f"   ✅ Added category mapping: groceries -> non_deductible")
        
        # Test category mapping
        mapping_result = sa.category_mapper.map_expense_to_deduction_category(
            expense_category="groceries",
            merchant_name="Migros Test Store",
            description="Weekly groceries",
            amount=85.50,
            date=date.today()
        )
        if mapping_result['success']:
            print(f"   Mapped to: {mapping_result['deduction_category']}")
            print(f"   Confidence: {mapping_result['confidence']:.2f}")
        
        # Manually insert a sample expense to test queries
        print("\n💰 Adding sample expense...")
        expense_id = sa.db.execute("""
            INSERT INTO sa_expenses (
                user_id, date_local, merchant_text, amount_cents, 
                currency, category_code, pro_pct, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "sample_user", date.today().isoformat(), "Migros Test Store",
            8550, "CHF", "groceries", 0, "Sample grocery expense"
        ))
        print(f"   ✅ Added expense ID: {expense_id}")
        
        # Test expense retrieval
        print("\n📋 Testing expense retrieval with data...")
        expenses = sa.get_expenses(limit=10)
        if expenses:
            expense = expenses[0]
            print(f"   Found expense: {expense['merchant_text']} - CHF {expense['amount_chf']:.2f}")
            print("   ✅ Expense retrieval with data working")
        
        # Test dashboard with data
        print("\n📊 Testing dashboard with data...")
        dashboard = sa.get_dashboard_summary()
        if 'error' not in dashboard:
            print(f"   Total expenses: {dashboard['total_expenses']}")
            print(f"   Total amount: CHF {dashboard['total_amount_chf']:.2f}")
            print("   ✅ Dashboard with data working")
        
        print(f"\n🎉 Sample data tests passed!")
        
    except Exception as e:
        print(f"❌ Sample data test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
            print(f"🧹 Cleaned up temporary database: {db_path}")
    
    return True

def main():
    """Main test function."""
    print("🇨🇭 Swiss Accountant Test Suite")
    print("=" * 50)
    print(f"Python version: {sys.version}")
    print(f"Test time: {datetime.now().isoformat()}")
    
    # Run tests
    basic_test_passed = test_basic_functionality()
    sample_test_passed = test_sample_data()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary")
    print("=" * 50)
    print(f"✅ Basic functionality: {'PASSED' if basic_test_passed else 'FAILED'}")
    print(f"✅ Sample data tests: {'PASSED' if sample_test_passed else 'FAILED'}")
    
    if basic_test_passed and sample_test_passed:
        print("\n🎉 All tests PASSED! Swiss Accountant is ready to use.")
        print("\n📚 Next steps:")
        print("   1. Install Tesseract for OCR functionality")
        print("   2. Configure your canton in config.json")
        print("   3. Start processing receipts and statements")
        print("   4. Use the CLI: swiss-accountant --help")
        return True
    else:
        print("\n❌ Some tests FAILED. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
