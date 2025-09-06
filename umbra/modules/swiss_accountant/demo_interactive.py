#!/usr/bin/env python3
"""
Swiss Accountant Interactive Demo
Interactive demonstration of all Swiss Accountant features.
"""

import os
import sys
from pathlib import Path
from datetime import date, datetime
import tempfile
import json
import time

# Add the module path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from umbra.modules.swiss_accountant import (
    create_swiss_accountant,
    get_default_config,
    get_version,
    get_supported_formats,
    get_swiss_info
)

class InteractiveDemo:
    """Interactive demonstration of Swiss Accountant features."""
    
    def __init__(self):
        """Initialize demo."""
        self.sa = None
        self.db_path = None
        self.user_id = "demo_user"
    
    def clear_screen(self):
        """Clear terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def wait_for_enter(self, message="Press Enter to continue..."):
        """Wait for user input."""
        input(f"\n{message}")
    
    def print_header(self, title: str):
        """Print section header."""
        print("\n" + "=" * 60)
        print(f"🇨🇭 {title}")
        print("=" * 60)
    
    def print_step(self, step: str, description: str):
        """Print step information."""
        print(f"\n📋 {step}")
        print("-" * 40)
        print(f"{description}")
    
    def show_welcome(self):
        """Show welcome screen."""
        self.clear_screen()
        print("🇨🇭 Swiss Accountant Interactive Demo")
        print("=" * 60)
        print(f"Version: {get_version()}")
        print(f"Platform: Swiss tax-compliant expense tracking")
        print(f"Features: OCR, Bank reconciliation, Tax optimization")
        print("")
        print("This interactive demo will showcase:")
        print("• Receipt processing with OCR")
        print("• Bank statement import and reconciliation")
        print("• Swiss tax category mapping")
        print("• Deduction calculation and optimization")
        print("• Export functionality for tax preparation")
        print("")
        print("The demo uses sample data and temporary storage.")
        print("No real files or data will be affected.")
        
        self.wait_for_enter("Press Enter to start the demo...")
    
    def setup_demo(self):
        """Set up demo environment."""
        self.print_header("Demo Setup")
        
        print("Setting up temporary demo environment...")
        
        # Create temporary database
        tmp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = tmp_db.name
        tmp_db.close()
        
        # Configuration
        config = get_default_config()
        config.update({
            'canton': 'ZH',
            'log_level': 'INFO'
        })
        
        # Initialize Swiss Accountant
        print("📱 Initializing Swiss Accountant...")
        self.sa = create_swiss_accountant(
            db_path=self.db_path,
            user_id=self.user_id,
            config=config
        )
        
        print("✅ Demo environment ready!")
        print(f"   Database: {self.db_path}")
        print(f"   User ID: {self.user_id}")
        print(f"   Canton: Zurich (ZH)")
        
        # Show system info
        print(f"\n📊 System Information:")
        swiss_info = get_swiss_info()
        print(f"   Supported VAT rates: {swiss_info['vat_rates']}")
        print(f"   Languages: {swiss_info['languages']}")
        print(f"   Cantons: {len(swiss_info['cantons'])} supported")
        
        formats = get_supported_formats()
        print(f"\n📄 Supported Formats:")
        print(f"   Receipts: {', '.join(formats['receipts'])}")
        print(f"   Statements: {', '.join(formats['statements'])}")
        
        self.wait_for_enter()
    
    def demo_receipt_processing(self):
        """Demonstrate receipt processing."""
        self.print_header("Receipt Processing Demo")
        
        self.print_step("Step 1", "Simulating OCR-based receipt processing")
        
        # Sample receipts with different scenarios
        sample_receipts = [
            {
                'name': 'Grocery Receipt (Migros)',
                'merchant': 'Migros Zürich Bahnhof',
                'amount': 45.80,
                'date': '2024-01-15',
                'category': 'groceries',
                'business_pct': 0,
                'vat_rate': 2.6,
                'description': 'Personal grocery shopping'
            },
            {
                'name': 'Business Laptop (Apple)',
                'merchant': 'Apple Store Zurich',
                'amount': 2499.00,
                'date': '2024-01-10',
                'category': 'professional_equipment',
                'business_pct': 85,
                'vat_rate': 8.1,
                'description': 'MacBook Pro for work (85% business use)'
            },
            {
                'name': 'Public Transport (SBB)',
                'merchant': 'SBB CFF FFS',
                'amount': 125.00,
                'date': '2024-01-05',
                'category': 'commute_public_transport',
                'business_pct': 100,
                'vat_rate': 8.1,
                'description': 'Monthly GA pass for commuting'
            },
            {
                'name': 'Business Meal',
                'merchant': 'Restaurant Kronenhalle',
                'amount': 89.50,
                'date': '2024-01-12',
                'category': 'meals_work',
                'business_pct': 100,
                'vat_rate': 8.1,
                'description': 'Client lunch meeting'
            }
        ]
        
        processed_receipts = []
        
        for i, receipt in enumerate(sample_receipts, 1):
            print(f"\n🧾 Processing Receipt {i}: {receipt['name']}")
            print(f"   Merchant: {receipt['merchant']}")
            print(f"   Amount: CHF {receipt['amount']:.2f}")
            print(f"   Business use: {receipt['business_pct']}%")
            
            # Simulate processing delay
            print("   🔍 Performing OCR...")
            time.sleep(0.5)
            print("   📄 Analyzing document type...")
            time.sleep(0.3)
            print("   🏪 Normalizing merchant name...")
            time.sleep(0.3)
            print("   🏷️  Mapping tax category...")
            time.sleep(0.3)
            
            # Store expense
            expense_id = self.sa.db.execute("""
                INSERT INTO sa_expenses (
                    user_id, date_local, merchant_text, amount_cents,
                    currency, category_code, pro_pct, notes, vat_breakdown_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.user_id,
                receipt['date'],
                receipt['merchant'],
                int(receipt['amount'] * 100),
                'CHF',
                receipt['category'],
                receipt['business_pct'],
                receipt['description'],
                json.dumps({'rate': receipt['vat_rate'], 'amount': receipt['amount'] * receipt['vat_rate'] / (100 + receipt['vat_rate'])})
            ))
            
            business_amount = receipt['amount'] * receipt['business_pct'] / 100
            tax_deductible = receipt['business_pct'] > 0 or receipt['category'] in ['commute_public_transport', 'meals_work']
            
            print(f"   ✅ Processed successfully!")
            print(f"      Expense ID: {expense_id}")
            print(f"      Tax deductible: {'Yes' if tax_deductible else 'No'}")
            if business_amount > 0:
                print(f"      Business amount: CHF {business_amount:.2f}")
            
            processed_receipts.append({
                'expense_id': expense_id,
                'receipt': receipt,
                'business_amount': business_amount,
                'tax_deductible': tax_deductible
            })
        
        # Summary
        total_amount = sum(r['receipt']['amount'] for r in processed_receipts)
        total_business = sum(r['business_amount'] for r in processed_receipts)
        deductible_count = sum(1 for r in processed_receipts if r['tax_deductible'])
        
        print(f"\n📊 Processing Summary:")
        print(f"   Receipts processed: {len(processed_receipts)}")
        print(f"   Total amount: CHF {total_amount:,.2f}")
        print(f"   Business amount: CHF {total_business:,.2f}")
        print(f"   Tax deductible: {deductible_count}/{len(processed_receipts)} receipts")
        
        self.wait_for_enter()
    
    def demo_bank_reconciliation(self):
        """Demonstrate bank statement processing and reconciliation."""
        self.print_header("Bank Statement & Reconciliation Demo")
        
        self.print_step("Step 1", "Importing bank statement transactions")
        
        # Sample bank transactions
        bank_transactions = [
            {
                'date': '2024-01-15',
                'amount': -45.80,
                'counterparty': 'MIGROS ZURICH BAHNHOF',
                'description': 'Card payment',
                'reference': 'TXN202401150001'
            },
            {
                'date': '2024-01-10',
                'amount': -2499.00,
                'counterparty': 'APPLE STORE ZURICH',
                'description': 'Online purchase',
                'reference': 'TXN202401100001'
            },
            {
                'date': '2024-01-05',
                'amount': -125.00,
                'counterparty': 'SBB AG',
                'description': 'Monthly pass',
                'reference': 'TXN202401050001'
            },
            {
                'date': '2024-01-12',
                'amount': -89.50,
                'counterparty': 'RESTAURANT KRONENHALLE',
                'description': 'Card payment',
                'reference': 'TXN202401120001'
            },
            {
                'date': '2024-01-31',
                'amount': 4500.00,
                'counterparty': 'EMPLOYER SALARY',
                'description': 'Monthly salary',
                'reference': 'SAL202401310001'
            }
        ]
        
        # Store statement
        statement_id = self.sa.db.execute("""
            INSERT INTO sa_statements (
                user_id, file_name, format_type, account_name,
                total_transactions, processed_at
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            self.user_id, "demo_statement_jan2024.csv", "csv_ubs",
            "UBS Checking Account", len(bank_transactions)
        ))
        
        transaction_ids = []
        for transaction in bank_transactions:
            print(f"   📋 {transaction['counterparty']:<30} CHF {transaction['amount']:>8.2f}")
            
            trans_id = self.sa.db.execute("""
                INSERT INTO sa_transactions (
                    statement_id, booking_date, value_date, amount_cents,
                    currency, counterparty, description, reference
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                statement_id,
                transaction['date'],
                transaction['date'],
                int(transaction['amount'] * 100),
                'CHF',
                transaction['counterparty'],
                transaction['description'],
                transaction['reference']
            ))
            transaction_ids.append(trans_id)
        
        print(f"\n✅ Imported {len(bank_transactions)} transactions")
        
        self.print_step("Step 2", "Performing automatic reconciliation")
        
        print("🔍 Analyzing expenses and transactions...")
        print("⚖️  Matching by amount, date, and merchant...")
        time.sleep(1)
        
        # Perform reconciliation
        reconcile_result = self.sa.reconcile_expenses(
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            auto_accept=True
        )
        
        if reconcile_result['success']:
            print(f"✅ Reconciliation completed!")
            print(f"   🎯 Exact matches: {reconcile_result['exact_matches']}")
            print(f"   🎲 Probable matches: {reconcile_result['probable_matches']}")
            print(f"   ⚠️  Needs review: {reconcile_result['needs_review']}")
            print(f"   ✅ Auto-accepted: {reconcile_result['auto_accepted']}")
            print(f"   ❓ Unmatched expenses: {reconcile_result['unmatched_expenses']}")
            print(f"   ❓ Unmatched transactions: {reconcile_result['unmatched_transactions']}")
            
            if reconcile_result.get('matches'):
                print(f"\n🔗 Sample matches:")
                for match in reconcile_result['matches'][:3]:
                    print(f"   {match['merchant']:<25} ↔ {match['counterparty']:<25} (confidence: {match['confidence']:.2f})")
        
        else:
            print(f"❌ Reconciliation failed: {reconcile_result.get('error')}")
        
        self.wait_for_enter()
    
    def demo_tax_optimization(self):
        """Demonstrate tax deduction calculation and optimization."""
        self.print_header("Swiss Tax Optimization Demo")
        
        self.print_step("Step 1", "Calculating tax deductions for 2024")
        
        print("🧮 Analyzing expenses for Swiss tax compliance...")
        print("📋 Applying federal and cantonal rules...")
        print("⚖️  Calculating deduction limits...")
        time.sleep(1)
        
        # Calculate tax deductions
        tax_result = self.sa.calculate_tax_deductions(year=2024, canton="ZH")
        
        if tax_result.get('success'):
            print(f"✅ Tax calculation completed!")
            print(f"\n📊 Tax Year 2024 Summary (Canton Zurich):")
            print(f"   Total expenses: CHF {tax_result['total_expenses']:>12,.2f}")
            print(f"   Total deductible: CHF {tax_result['total_deductible']:>12,.2f}")
            print(f"   Estimated tax savings: CHF {tax_result['estimated_tax_savings']:>12,.2f}")
            print(f"   Number of expenses: {tax_result['expense_count']:>15,}")
            
            print(f"\n🏷️  Deduction Categories:")
            for category, data in tax_result['deductions_by_category'].items():
                if data['deductible_amount'] > 0:
                    print(f"   {category:<30}: CHF {data['deductible_amount']:>8,.2f} ({data['expense_count']} items)")
        
        else:
            print(f"❌ Tax calculation failed: {tax_result.get('error')}")
        
        self.print_step("Step 2", "Optimization recommendations")
        
        print("💡 Analyzing optimization opportunities...")
        time.sleep(0.5)
        
        # Generate recommendations
        recommendations = [
            {
                'category': 'Professional Expenses',
                'current': 3500.00,
                'limit': 4000.00,
                'recommendation': 'Add CHF 500 in professional expenses or use flat rate',
                'impact': 'CHF 125 additional tax savings'
            },
            {
                'category': 'Pillar 3a',
                'current': 0.00,
                'limit': 7056.00,
                'recommendation': 'Maximize pillar 3a contributions',
                'impact': 'CHF 1,764 potential tax savings'
            },
            {
                'category': 'Home Office',
                'current': 360.00,
                'limit': 1500.00,
                'recommendation': 'Claim additional home office costs',
                'impact': 'CHF 285 potential tax savings'
            }
        ]
        
        print(f"🎯 Optimization Recommendations:")
        for i, rec in enumerate(recommendations, 1):
            utilization = (rec['current'] / rec['limit'] * 100) if rec['limit'] > 0 else 0
            print(f"\n   {i}. {rec['category']}")
            print(f"      Current: CHF {rec['current']:,.2f} / CHF {rec['limit']:,.2f} ({utilization:.0f}%)")
            print(f"      Action: {rec['recommendation']}")
            print(f"      Impact: {rec['impact']}")
        
        total_potential = sum(float(rec['impact'].split()[1].replace(',', '')) for rec in recommendations)
        print(f"\n💰 Total optimization potential: CHF {total_potential:,.2f}")
        
        self.wait_for_enter()
    
    def demo_export_functionality(self):
        """Demonstrate export functionality."""
        self.print_header("Export & Reporting Demo")
        
        self.print_step("Step 1", "Generating tax-ready export")
        
        print("📤 Preparing tax export for 2024...")
        print("📋 Formatting for Swiss tax software...")
        print("🏷️  Including all deductible categories...")
        time.sleep(1)
        
        # Generate export
        export_result = self.sa.export_tax_data(year=2024, format='csv', canton='ZH')
        
        if export_result['success']:
            print(f"✅ Export generated successfully!")
            print(f"   Format: CSV")
            print(f"   Records: {export_result['record_count']:,}")
            print(f"   Size: {export_result['size_bytes']:,} bytes")
            
            # Show sample export content
            lines = export_result['content'].split('\n')
            print(f"\n📋 Export Sample (first 3 lines):")
            for line in lines[:3]:
                if line.strip():
                    print(f"   {line}")
            
            print(f"\n💾 Export includes:")
            print(f"   • All expenses with tax categories")
            print(f"   • Business percentage calculations")
            print(f"   • VAT breakdown and rates")
            print(f"   • Deduction eligibility flags")
            print(f"   • Canton-specific formatting")
        
        else:
            print(f"❌ Export failed: {export_result.get('error')}")
        
        self.print_step("Step 2", "Dashboard and analytics")
        
        # Show dashboard
        dashboard = self.sa.get_dashboard_summary()
        
        if 'error' not in dashboard:
            print(f"📊 Dashboard Overview:")
            print(f"   Year: {dashboard['year']}")
            print(f"   Total expenses: {dashboard['total_expenses']:,}")
            print(f"   Total amount: CHF {dashboard['total_amount_chf']:,.2f}")
            print(f"   Business amount: CHF {dashboard['business_amount_chf']:,.2f}")
            
            if dashboard.get('monthly_breakdown'):
                print(f"\n📈 Monthly Activity:")
                for month in dashboard['monthly_breakdown'][-3:]:  # Last 3 months
                    print(f"   {month['month']}: {month['count']} expenses, CHF {month['amount_chf']:,.2f}")
            
            if dashboard.get('top_categories'):
                print(f"\n🏷️  Top Categories:")
                for cat in dashboard['top_categories'][:3]:
                    print(f"   {cat['category']:<20}: CHF {cat['amount_chf']:>8,.2f}")
        
        self.wait_for_enter()
    
    def demo_reconciliation_review(self):
        """Demonstrate reconciliation review process."""
        self.print_header("Reconciliation Review Demo")
        
        self.print_step("Step 1", "Reviewing reconciliation results")
        
        # Get reconciliation summary
        reconciliation_summary = self.sa.get_reconciliation_summary()
        
        if 'error' not in reconciliation_summary:
            print(f"📊 Reconciliation Status:")
            print(f"   Total matches: {reconciliation_summary['total_matches']}")
            print(f"   Exact matches: {reconciliation_summary['exact_matches']}")
            print(f"   Probable matches: {reconciliation_summary['probable_matches']}")
            print(f"   Needs review: {reconciliation_summary['needs_review']}")
            print(f"   Confirmed: {reconciliation_summary['confirmed_matches']}")
            print(f"   Average confidence: {reconciliation_summary['avg_confidence']:.2f}")
            
            # Show recent sessions
            if reconciliation_summary.get('recent_sessions'):
                print(f"\n📋 Recent Sessions:")
                for session in reconciliation_summary['recent_sessions'][:2]:
                    print(f"   Session {session['id']}: {session['strategy']}")
                    print(f"      Period: {session['period_start']} to {session['period_end']}")
                    print(f"      Results: {session['exact_matches']} exact, {session['probable_matches']} probable")
        
        else:
            print(f"❌ Reconciliation summary failed: {reconciliation_summary['error']}")
        
        self.print_step("Step 2", "Data completeness check")
        
        # Show data completeness
        expenses = self.sa.get_expenses(limit=100)
        total_expenses = len(expenses)
        
        matched_expenses = len([e for e in expenses if e.get('matched_transaction_id')])
        categorized_expenses = len([e for e in expenses if e.get('category_code') != 'other'])
        business_expenses = len([e for e in expenses if e.get('pro_pct', 0) > 0])
        
        print(f"📈 Data Quality Metrics:")
        print(f"   Total expenses: {total_expenses}")
        print(f"   Matched with transactions: {matched_expenses} ({matched_expenses/total_expenses*100 if total_expenses > 0 else 0:.0f}%)")
        print(f"   Properly categorized: {categorized_expenses} ({categorized_expenses/total_expenses*100 if total_expenses > 0 else 0:.0f}%)")
        print(f"   Business use defined: {business_expenses} ({business_expenses/total_expenses*100 if total_expenses > 0 else 0:.0f}%)")
        
        quality_score = (matched_expenses + categorized_expenses + business_expenses) / (total_expenses * 3) * 100 if total_expenses > 0 else 0
        quality_emoji = "🟢" if quality_score > 80 else "🟡" if quality_score > 60 else "🔴"
        
        print(f"\n{quality_emoji} Overall Data Quality: {quality_score:.0f}%")
        
        self.wait_for_enter()
    
    def show_summary(self):
        """Show demo summary."""
        self.print_header("Demo Complete - Summary")
        
        print("🎉 Congratulations! You've completed the Swiss Accountant demo.")
        print("")
        print("📋 What you've seen:")
        print("✅ OCR-based receipt processing with automatic categorization")
        print("✅ Bank statement import and intelligent reconciliation")
        print("✅ Swiss tax compliance with federal and cantonal rules")
        print("✅ Deduction optimization with actionable recommendations")
        print("✅ Tax-ready exports for preparation software")
        print("✅ Comprehensive reporting and analytics")
        print("")
        print("💡 Key Benefits:")
        print("• Automated expense processing saves hours of manual work")
        print("• Swiss-specific tax rules ensure compliance and maximize deductions")
        print("• Intelligent reconciliation reduces errors and improves accuracy")
        print("• Professional exports integrate with tax preparation workflows")
        print("• Multi-language support covers all Swiss official languages")
        print("")
        print("🚀 Ready to get started with your own data?")
        print("")
        print("Next steps:")
        print("1. Run the setup script: python setup.py")
        print("2. Configure your canton in config.json")
        print("3. Start processing receipts: sa.process_receipt('receipt.jpg')")
        print("4. Import bank statements: sa.process_bank_statement('statement.csv')")
        print("5. Review and reconcile: sa.reconcile_expenses(start_date, end_date)")
        print("6. Calculate deductions: sa.calculate_tax_deductions(year, canton)")
        print("7. Export for taxes: sa.export_tax_data(year, format='xlsx')")
        print("")
        print("📚 Resources:")
        print("• README.md - Complete documentation")
        print("• examples/ - Code examples for all features")
        print("• CLI help: python -m swiss_accountant.cli --help")
        print("• Test script: python test_swiss_accountant.py")
    
    def cleanup(self):
        """Clean up demo environment."""
        try:
            if self.db_path and os.path.exists(self.db_path):
                os.unlink(self.db_path)
                print(f"\n🧹 Cleaned up demo database")
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")
    
    def run(self):
        """Run the interactive demo."""
        try:
            self.show_welcome()
            self.setup_demo()
            self.demo_receipt_processing()
            self.demo_bank_reconciliation()
            self.demo_tax_optimization()
            self.demo_export_functionality()
            self.demo_reconciliation_review()
            self.show_summary()
            
            print(f"\nThank you for trying Swiss Accountant! 🇨🇭")
            
        except KeyboardInterrupt:
            print(f"\n\n⏹️  Demo interrupted by user")
        except Exception as e:
            print(f"\n❌ Demo failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()

def main():
    """Main demo function."""
    demo = InteractiveDemo()
    demo.run()

if __name__ == "__main__":
    main()
