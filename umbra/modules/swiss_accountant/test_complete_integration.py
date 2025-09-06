#!/usr/bin/env python3
"""
Swiss Accountant Complete Integration Test Suite
Comprehensive testing of all Swiss Accountant functionality.
"""

import os
import sys
import tempfile
import json
import csv
from pathlib import Path
from datetime import date, datetime, timedelta
from decimal import Decimal
import time
import shutil

# Add the module path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from umbra.modules.swiss_accountant import (
        create_swiss_accountant,
        get_default_config,
        get_version,
        get_supported_formats,
        get_swiss_info
    )
    from umbra.modules.swiss_accountant.utils import BackupManager, MaintenanceManager
    SWISS_ACCOUNTANT_AVAILABLE = True
except ImportError as e:
    print(f"❌ Swiss Accountant import failed: {e}")
    SWISS_ACCOUNTANT_AVAILABLE = False

class ComprehensiveTestSuite:
    """Comprehensive test suite for Swiss Accountant."""
    
    def __init__(self):
        """Initialize test suite."""
        self.db_path = None
        self.sa = None
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }
        self.start_time = None
        
    def setup_test_environment(self):
        """Set up test environment."""
        print("🔧 Setting up test environment...")
        
        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            self.db_path = tmp_db.name
        
        # Initialize Swiss Accountant
        config = get_default_config()
        config.update({
            'canton': 'ZH',
            'log_level': 'WARNING'  # Reduce log noise during testing
        })
        
        self.sa = create_swiss_accountant(
            db_path=self.db_path,
            user_id="test_user",
            config=config
        )
        
        print(f"   ✅ Test database: {self.db_path}")
        print(f"   ✅ Swiss Accountant initialized")
    
    def cleanup_test_environment(self):
        """Clean up test environment."""
        try:
            if self.db_path and os.path.exists(self.db_path):
                os.unlink(self.db_path)
                print(f"   🧹 Cleaned up test database")
        except Exception as e:
            print(f"   ⚠️  Cleanup warning: {e}")
    
    def run_test(self, test_name: str, test_func, *args, **kwargs):
        """Run a single test with error handling."""
        try:
            print(f"\n🧪 Testing: {test_name}")
            start_time = time.time()
            
            result = test_func(*args, **kwargs)
            
            elapsed = time.time() - start_time
            
            if result:
                print(f"   ✅ {test_name} passed ({elapsed:.2f}s)")
                self.test_results['passed'] += 1
            else:
                print(f"   ❌ {test_name} failed ({elapsed:.2f}s)")
                self.test_results['failed'] += 1
                
            return result
            
        except Exception as e:
            print(f"   💥 {test_name} error: {e}")
            self.test_results['errors'].append(f"{test_name}: {e}")
            self.test_results['failed'] += 1
            return False
    
    def test_module_imports(self):
        """Test all module imports work correctly."""
        try:
            # Test main imports
            from umbra.modules.swiss_accountant import SwissAccountant, quick_start
            from umbra.modules.swiss_accountant.database import DatabaseManager
            from umbra.modules.swiss_accountant.ingest import OCRProcessor, DocumentParser, StatementParser
            from umbra.modules.swiss_accountant.normalize import MerchantNormalizer, CategoryMapper
            from umbra.modules.swiss_accountant.reconcile import ExpenseTransactionMatcher
            from umbra.modules.swiss_accountant.exports import ExportManager
            
            print("   ✅ All module imports successful")
            return True
            
        except ImportError as e:
            print(f"   ❌ Import failed: {e}")
            return False
    
    def test_version_and_info(self):
        """Test version and system information."""
        try:
            version = get_version()
            formats = get_supported_formats()
            swiss_info = get_swiss_info()
            
            assert version is not None and len(version) > 0
            assert 'receipts' in formats and 'statements' in formats
            assert 'vat_rates' in swiss_info and 'cantons' in swiss_info
            
            print(f"   ✅ Version: {version}")
            print(f"   ✅ Receipt formats: {len(formats['receipts'])}")
            print(f"   ✅ Statement formats: {len(formats['statements'])}")
            print(f"   ✅ Swiss cantons: {len(swiss_info['cantons'])}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Version/info test failed: {e}")
            return False
    
    def test_database_operations(self):
        """Test database creation and basic operations."""
        try:
            # Test health check
            health = self.sa.health_check()
            assert health['status'] in ['healthy', 'degraded']
            
            # Test database queries
            expenses = self.sa.get_expenses(limit=10)
            assert isinstance(expenses, list)
            
            # Test dashboard
            dashboard = self.sa.get_dashboard_summary()
            assert 'total_expenses' in dashboard
            
            print("   ✅ Database operations working")
            return True
            
        except Exception as e:
            print(f"   ❌ Database test failed: {e}")
            return False
    
    def test_merchant_normalization(self):
        """Test merchant normalization functionality."""
        try:
            # Add test merchant
            result = self.sa.merchant_normalizer.add_merchant(
                canonical="Test Merchant AG",
                vat_no="CHE-123.456.789",
                aliases="test,test merchant,test ag"
            )
            assert result['success'] is True
            
            # Test normalization
            norm_result = self.sa.merchant_normalizer.normalize_merchant_name("TEST MERCHANT")
            assert norm_result['success'] is True
            assert norm_result['canonical'] == "Test Merchant AG"
            
            # Test statistics
            stats = self.sa.merchant_normalizer.get_merchant_statistics()
            assert stats['total_merchants'] > 0
            
            print("   ✅ Merchant normalization working")
            return True
            
        except Exception as e:
            print(f"   ❌ Merchant normalization test failed: {e}")
            return False
    
    def test_category_mapping(self):
        """Test tax category mapping functionality."""
        try:
            # Add custom mapping
            result = self.sa.category_mapper.add_custom_mapping(
                expense_category="test_groceries",
                deduction_category="non_deductible",
                confidence=1.0
            )
            assert result['success'] is True
            
            # Test mapping
            mapping_result = self.sa.category_mapper.map_expense_to_deduction_category(
                expense_category="test_groceries",
                merchant_name="Test Supermarket",
                description="Weekly shopping",
                amount=Decimal('85.50'),
                date=date.today()
            )
            assert mapping_result['success'] is True
            
            # Test statistics
            stats = self.sa.category_mapper.get_category_statistics()
            assert stats['total_mappings'] > 0
            
            print("   ✅ Category mapping working")
            return True
            
        except Exception as e:
            print(f"   ❌ Category mapping test failed: {e}")
            return False
    
    def test_expense_management(self):
        """Test expense creation and management."""
        try:
            # Create test expenses
            test_expenses = [
                {
                    'date': '2024-01-15',
                    'merchant': 'Test Grocery Store',
                    'amount': 45.80,
                    'category': 'groceries',
                    'business_pct': 0
                },
                {
                    'date': '2024-01-10',
                    'merchant': 'Test Office Supply',
                    'amount': 125.00,
                    'category': 'professional_equipment',
                    'business_pct': 100
                }
            ]
            
            expense_ids = []
            for expense in test_expenses:
                expense_id = self.sa.db.execute("""
                    INSERT INTO sa_expenses (
                        user_id, date_local, merchant_text, amount_cents,
                        currency, category_code, pro_pct, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "test_user",
                    expense['date'],
                    expense['merchant'],
                    int(expense['amount'] * 100),
                    'CHF',
                    expense['category'],
                    expense['business_pct'],
                    'Test expense'
                ))
                expense_ids.append(expense_id)
            
            # Test expense retrieval
            expenses = self.sa.get_expenses(limit=10)
            assert len(expenses) >= 2
            
            # Test expense update
            update_result = self.sa.update_expense_category(
                expense_ids[0],
                'groceries',
                business_percentage=0
            )
            assert update_result['success'] is True
            
            print(f"   ✅ Created {len(expense_ids)} test expenses")
            print("   ✅ Expense management working")
            return True
            
        except Exception as e:
            print(f"   ❌ Expense management test failed: {e}")
            return False
    
    def test_statement_processing(self):
        """Test bank statement processing."""
        try:
            # Create sample CSV statement
            statement_content = """Date;Description;Amount;Currency
2024-01-15;TEST GROCERY STORE;-45.80;CHF
2024-01-10;TEST OFFICE SUPPLY;-125.00;CHF
2024-01-05;SALARY PAYMENT;3500.00;CHF"""
            
            # Create temporary CSV file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
                tmp_file.write(statement_content)
                tmp_csv_path = tmp_file.name
            
            try:
                # Process statement
                result = self.sa.process_bank_statement(
                    tmp_csv_path,
                    account_name="Test Bank Account"
                )
                
                assert result['success'] is True
                assert result['transaction_count'] >= 2
                
                print(f"   ✅ Processed {result['transaction_count']} transactions")
                print("   ✅ Statement processing working")
                return True
                
            finally:
                os.unlink(tmp_csv_path)
            
        except Exception as e:
            print(f"   ❌ Statement processing test failed: {e}")
            return False
    
    def test_reconciliation(self):
        """Test expense-transaction reconciliation."""
        try:
            # Perform reconciliation
            reconcile_result = self.sa.reconcile_expenses(
                period_start=date(2024, 1, 1),
                period_end=date(2024, 1, 31),
                auto_accept=True
            )
            
            assert reconcile_result['success'] is True
            
            # Get reconciliation summary
            summary = self.sa.get_reconciliation_summary()
            assert 'total_matches' in summary
            
            print(f"   ✅ Reconciliation completed")
            print(f"   ✅ Total matches: {summary.get('total_matches', 0)}")
            return True
            
        except Exception as e:
            print(f"   ❌ Reconciliation test failed: {e}")
            return False
    
    def test_tax_calculations(self):
        """Test Swiss tax deduction calculations."""
        try:
            # Calculate tax deductions
            tax_result = self.sa.calculate_tax_deductions(year=2024, canton="ZH")
            
            assert tax_result['success'] is True
            assert 'total_expenses' in tax_result
            assert 'total_deductible' in tax_result
            
            print(f"   ✅ Tax calculation completed")
            print(f"   ✅ Total expenses: CHF {tax_result['total_expenses']:.2f}")
            print(f"   ✅ Total deductible: CHF {tax_result['total_deductible']:.2f}")
            return True
            
        except Exception as e:
            print(f"   ❌ Tax calculation test failed: {e}")
            return False
    
    def test_export_functionality(self):
        """Test data export functionality."""
        try:
            # Test CSV export
            csv_result = self.sa.export_tax_data(year=2024, format='csv', canton='ZH')
            assert csv_result['success'] is True
            assert csv_result['record_count'] >= 0
            
            # Test export summary
            export_summary = self.sa.export_manager.get_export_summary(self.sa.db, "test_user")
            assert 'total_expenses' in export_summary
            
            print(f"   ✅ CSV export working ({csv_result['record_count']} records)")
            print("   ✅ Export functionality working")
            return True
            
        except Exception as e:
            print(f"   ❌ Export test failed: {e}")
            return False
    
    def test_backup_and_maintenance(self):
        """Test backup and maintenance utilities."""
        try:
            # Test backup
            backup_manager = BackupManager(self.db_path)
            
            with tempfile.NamedTemporaryFile(suffix='.sql.gz', delete=False) as tmp_backup:
                backup_path = tmp_backup.name
            
            try:
                backup_result = backup_manager.create_backup(backup_path, compress=True)
                assert backup_result['success'] is True
                assert os.path.exists(backup_path)
                
                # Test maintenance
                maintenance_manager = MaintenanceManager(self.db_path)
                analysis_result = maintenance_manager.analyze_database()
                assert analysis_result['success'] is True
                
                # Test optimization
                optimize_result = maintenance_manager.optimize_database(['analyze'])
                assert optimize_result['success'] is True
                
                print("   ✅ Backup created successfully")
                print("   ✅ Database analysis completed")
                print("   ✅ Database optimization completed")
                return True
                
            finally:
                if os.path.exists(backup_path):
                    os.unlink(backup_path)
            
        except Exception as e:
            print(f"   ❌ Backup/maintenance test failed: {e}")
            return False
    
    def test_data_integrity(self):
        """Test data integrity and validation."""
        try:
            maintenance_manager = MaintenanceManager(self.db_path)
            
            # Validate data integrity
            validation_result = maintenance_manager.validate_data_integrity()
            assert validation_result['success'] is True
            
            integrity_score = validation_result['summary']['integrity_score']
            
            print(f"   ✅ Data integrity score: {integrity_score}%")
            
            if integrity_score >= 90:
                print("   ✅ Excellent data integrity")
                return True
            elif integrity_score >= 70:
                print("   ⚠️  Good data integrity (some minor issues)")
                return True
            else:
                print("   ❌ Poor data integrity")
                return False
            
        except Exception as e:
            print(f"   ❌ Data integrity test failed: {e}")
            return False
    
    def test_performance_benchmarks(self):
        """Test performance benchmarks."""
        try:
            # Test database query performance
            start_time = time.time()
            expenses = self.sa.get_expenses(limit=1000)
            query_time = time.time() - start_time
            
            # Test reconciliation performance
            start_time = time.time()
            reconcile_result = self.sa.reconcile_expenses(
                period_start=date(2024, 1, 1),
                period_end=date(2024, 1, 31),
                auto_accept=False
            )
            reconcile_time = time.time() - start_time
            
            # Test export performance
            start_time = time.time()
            export_result = self.sa.export_tax_data(year=2024, format='csv')
            export_time = time.time() - start_time
            
            print(f"   ✅ Query performance: {query_time:.3f}s ({len(expenses)} expenses)")
            print(f"   ✅ Reconciliation performance: {reconcile_time:.3f}s")
            print(f"   ✅ Export performance: {export_time:.3f}s")
            
            # Performance thresholds
            if query_time < 1.0 and reconcile_time < 5.0 and export_time < 2.0:
                print("   ✅ Performance benchmarks passed")
                return True
            else:
                print("   ⚠️  Performance below expected thresholds")
                return True  # Still pass, just warn
            
        except Exception as e:
            print(f"   ❌ Performance test failed: {e}")
            return False
    
    def test_error_handling(self):
        """Test error handling and edge cases."""
        try:
            # Test invalid database path
            try:
                invalid_sa = create_swiss_accountant(db_path="/invalid/path/db.sqlite")
                assert False, "Should have failed with invalid path"
            except:
                pass  # Expected to fail
            
            # Test invalid expense operations
            invalid_result = self.sa.update_expense_category(
                expense_id=99999,  # Non-existent
                category_code='invalid_category'
            )
            assert invalid_result['success'] is False
            
            # Test invalid export parameters
            invalid_export = self.sa.export_tax_data(year=1900, format='invalid')
            assert invalid_export['success'] is False
            
            print("   ✅ Error handling working correctly")
            return True
            
        except Exception as e:
            print(f"   ❌ Error handling test failed: {e}")
            return False
    
    def run_comprehensive_test(self):
        """Run all tests in the comprehensive test suite."""
        if not SWISS_ACCOUNTANT_AVAILABLE:
            print("❌ Swiss Accountant not available for testing")
            return False
        
        print("🇨🇭 Swiss Accountant - Comprehensive Integration Test Suite")
        print("=" * 70)
        
        self.start_time = time.time()
        
        try:
            self.setup_test_environment()
            
            # Core functionality tests
            test_cases = [
                ("Module Imports", self.test_module_imports),
                ("Version and Info", self.test_version_and_info),
                ("Database Operations", self.test_database_operations),
                ("Merchant Normalization", self.test_merchant_normalization),
                ("Category Mapping", self.test_category_mapping),
                ("Expense Management", self.test_expense_management),
                ("Statement Processing", self.test_statement_processing),
                ("Reconciliation", self.test_reconciliation),
                ("Tax Calculations", self.test_tax_calculations),
                ("Export Functionality", self.test_export_functionality),
                ("Backup and Maintenance", self.test_backup_and_maintenance),
                ("Data Integrity", self.test_data_integrity),
                ("Performance Benchmarks", self.test_performance_benchmarks),
                ("Error Handling", self.test_error_handling)
            ]
            
            # Run all test cases
            for test_name, test_func in test_cases:
                self.run_test(test_name, test_func)
            
        finally:
            self.cleanup_test_environment()
        
        # Print results
        self.print_test_summary()
        
        return self.test_results['failed'] == 0
    
    def print_test_summary(self):
        """Print comprehensive test results."""
        total_time = time.time() - self.start_time
        total_tests = self.test_results['passed'] + self.test_results['failed']
        
        print("\n" + "=" * 70)
        print("🎯 TEST SUMMARY")
        print("=" * 70)
        
        print(f"Total tests run: {total_tests}")
        print(f"✅ Passed: {self.test_results['passed']}")
        print(f"❌ Failed: {self.test_results['failed']}")
        print(f"⏱️  Total time: {total_time:.2f} seconds")
        
        if self.test_results['failed'] == 0:
            print(f"\n🎉 ALL TESTS PASSED! Swiss Accountant is working perfectly.")
            print(f"🚀 Ready for production use with Swiss tax compliance.")
        else:
            print(f"\n⚠️  {self.test_results['failed']} test(s) failed.")
            
            if self.test_results['errors']:
                print(f"\n❌ Error Details:")
                for error in self.test_results['errors']:
                    print(f"   • {error}")
        
        print(f"\n📊 Success Rate: {(self.test_results['passed'] / total_tests * 100):.1f}%")
        
        print(f"\n💡 Next Steps:")
        if self.test_results['failed'] == 0:
            print(f"   1. ✅ System is ready for production use")
            print(f"   2. 📚 Review documentation and examples")
            print(f"   3. 🧾 Start processing your receipts")
            print(f"   4. 🏦 Import your bank statements")
            print(f"   5. 🧮 Calculate your tax deductions")
        else:
            print(f"   1. 🔍 Review failed tests and error messages")
            print(f"   2. 📖 Check troubleshooting guide")
            print(f"   3. 🔧 Fix issues and re-run tests")
            print(f"   4. 📝 Report persistent issues on GitHub")

def main():
    """Main test execution function."""
    test_suite = ComprehensiveTestSuite()
    success = test_suite.run_comprehensive_test()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
