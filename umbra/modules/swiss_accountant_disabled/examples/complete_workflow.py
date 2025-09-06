#!/usr/bin/env python3
"""
Swiss Accountant Complete Workflow Example
Demonstrates a typical monthly expense processing workflow.
"""

import os
import sys
from pathlib import Path
from datetime import date, datetime, timedelta
from decimal import Decimal
import tempfile
import json

# Add the module path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from umbra.modules.swiss_accountant import (
    create_swiss_accountant,
    get_default_config,
    load_config_from_file
)

def complete_workflow_example():
    """Demonstrate a complete monthly workflow."""
    print("🇨🇭 Swiss Accountant - Complete Workflow Example")
    print("=" * 60)
    
    # Configuration
    config = get_default_config()
    config.update({
        'canton': 'ZH',  # Zurich canton
        'log_level': 'DEBUG'
    })
    
    # Initialize with temporary database for demo
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = tmp_db.name
    
    try:
        # Step 1: Initialize Swiss Accountant
        print("\n📱 Step 1: Initialize Swiss Accountant")
        print("-" * 40)
        
        sa = create_swiss_accountant(
            db_path=db_path,
            user_id="demo_user",
            config=config
        )
        print("✅ Swiss Accountant initialized")
        print(f"   Database: {db_path}")
        print(f"   User ID: demo_user")
        print(f"   Canton: {config['canton']}")
        
        # Step 2: Setup sample data (simulating real receipts and transactions)
        print("\n🧾 Step 2: Process Sample Receipts")
        print("-" * 40)
        
        # Simulate processing receipts
        sample_receipts = [
            {
                'merchant': 'Migros Zurich HB',
                'amount': 45.80,
                'date': '2024-01-15',
                'category': 'groceries',
                'items': ['Bread', 'Milk', 'Eggs', 'Vegetables'],
                'vat_rate': 2.6,
                'payment_method': 'card'
            },
            {
                'merchant': 'SBB CFF FFS',
                'amount': 125.00,
                'date': '2024-01-03',
                'category': 'public_transport',
                'items': ['Monthly GA Pass'],
                'vat_rate': 8.1,
                'payment_method': 'card'
            },
            {
                'merchant': 'Digitec Galaxus AG',
                'amount': 1250.00,
                'date': '2024-01-10',
                'category': 'professional_equipment',
                'items': ['MacBook Pro M3'],
                'vat_rate': 8.1,
                'payment_method': 'card',
                'business_percentage': 80
            },
            {
                'merchant': 'Starbucks Switzerland',
                'amount': 6.50,
                'date': '2024-01-18',
                'category': 'meals_work',
                'items': ['Coffee', 'Sandwich'],
                'vat_rate': 8.1,
                'payment_method': 'cash'
            },
            {
                'merchant': 'Coop City Zurich',
                'amount': 89.90,
                'date': '2024-01-22',
                'category': 'groceries',
                'items': ['Weekly shopping'],
                'vat_rate': 2.6,
                'payment_method': 'card'
            }
        ]
        
        expense_ids = []
        for i, receipt in enumerate(sample_receipts):
            print(f"\n   Processing receipt {i+1}: {receipt['merchant']}")
            
            # Calculate VAT breakdown
            gross_amount = receipt['amount']
            vat_rate = receipt['vat_rate']
            net_amount = gross_amount / (1 + vat_rate / 100)
            vat_amount = gross_amount - net_amount
            
            # Store expense manually (simulating OCR + parsing)
            expense_id = sa.db.execute("""
                INSERT INTO sa_expenses (
                    user_id, date_local, merchant_text, amount_cents,
                    currency, category_code, pro_pct, notes,
                    payment_method, vat_breakdown_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "demo_user",
                receipt['date'],
                receipt['merchant'],
                int(receipt['amount'] * 100),
                "CHF",
                receipt['category'],
                receipt.get('business_percentage', 0),
                f"Items: {', '.join(receipt['items'])}",
                receipt['payment_method'],
                json.dumps({
                    'rate': vat_rate,
                    'net_amount': round(net_amount, 2),
                    'vat_amount': round(vat_amount, 2),
                    'gross_amount': gross_amount
                })
            ))
            expense_ids.append(expense_id)
            
            print(f"   ✅ Added expense ID {expense_id}: CHF {receipt['amount']:.2f}")
            if receipt.get('business_percentage', 0) > 0:
                business_amount = receipt['amount'] * receipt['business_percentage'] / 100
                print(f"      Business portion: CHF {business_amount:.2f} ({receipt['business_percentage']}%)")
        
        print(f"\n✅ Processed {len(sample_receipts)} receipts")
        
        # Step 3: Import bank statement (simulated)
        print("\n🏦 Step 3: Import Bank Statement")
        print("-" * 40)
        
        # Create sample bank transactions
        sample_transactions = [
            {
                'date': '2024-01-15',
                'amount': -45.80,
                'counterparty': 'MIGROS ZURICH HB',
                'description': 'Card payment',
                'reference': 'TXN202401150001'
            },
            {
                'date': '2024-01-03',
                'amount': -125.00,
                'counterparty': 'SBB AG',
                'description': 'GA Monthly Pass',
                'reference': 'TXN202401030001'
            },
            {
                'date': '2024-01-10',
                'amount': -1250.00,
                'counterparty': 'DIGITEC GALAXUS AG',
                'description': 'Online purchase',
                'reference': 'TXN202401100001'
            },
            {
                'date': '2024-01-22',
                'amount': -89.90,
                'counterparty': 'COOP SCHWEIZ',
                'description': 'Card payment',
                'reference': 'TXN202401220001'
            },
            {
                'date': '2024-01-25',
                'amount': 3500.00,
                'counterparty': 'EMPLOYER SALARY',
                'description': 'Monthly salary',
                'reference': 'SAL202401250001'
            }
        ]
        
        # Store statement
        statement_id = sa.db.execute("""
            INSERT INTO sa_statements (
                user_id, file_name, format_type, account_name,
                total_transactions, processed_at
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            "demo_user", "demo_statement_jan2024.csv", "csv_generic",
            "UBS Checking Account", len(sample_transactions)
        ))
        
        transaction_ids = []
        for transaction in sample_transactions:
            trans_id = sa.db.execute("""
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
            
            print(f"   📋 Transaction: {transaction['counterparty']} - CHF {transaction['amount']:>8.2f}")
        
        print(f"✅ Imported {len(sample_transactions)} transactions")
        
        # Step 4: Reconcile expenses with transactions
        print("\n🔄 Step 4: Reconcile Expenses with Transactions")
        print("-" * 40)
        
        reconcile_result = sa.reconcile_expenses(
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            auto_accept=True
        )
        
        if reconcile_result['success']:
            print(f"✅ Reconciliation completed:")
            print(f"   Exact matches: {reconcile_result['exact_matches']}")
            print(f"   Probable matches: {reconcile_result['probable_matches']}")
            print(f"   Needs review: {reconcile_result['needs_review']}")
            print(f"   Auto-accepted: {reconcile_result['auto_accepted']}")
            print(f"   Unmatched expenses: {reconcile_result['unmatched_expenses']}")
            print(f"   Unmatched transactions: {reconcile_result['unmatched_transactions']}")
            
            # Show match details
            if reconcile_result['matches']:
                print(f"\n   📊 Match details:")
                for match in reconcile_result['matches'][:3]:  # Show first 3
                    print(f"      {match['merchant']} ↔ {match['counterparty']}")
                    print(f"      CHF {match['expense_amount']:.2f} | Confidence: {match['confidence']:.2f}")
        else:
            print(f"❌ Reconciliation failed: {reconcile_result.get('error')}")
        
        # Step 5: Update business expense categories
        print("\n🏷️  Step 5: Update Business Expense Categories")
        print("-" * 40)
        
        # Update the MacBook to 80% business use
        for expense_id in expense_ids:
            expense = sa.db.query_one("SELECT * FROM sa_expenses WHERE id = ?", (expense_id,))
            if expense and expense['merchant_text'] == 'Digitec Galaxus AG':
                update_result = sa.update_expense_category(
                    expense_id=expense_id,
                    category_code='professional_equipment',
                    business_percentage=80
                )
                if update_result['success']:
                    print(f"   ✅ Updated {expense['merchant_text']}: 80% business use")
                break
        
        # Step 6: Calculate tax deductions
        print("\n🧮 Step 6: Calculate Tax Deductions")
        print("-" * 40)
        
        tax_result = sa.calculate_tax_deductions(year=2024, canton="ZH")
        
        if tax_result.get('success'):
            print(f"✅ Tax calculation for 2024 (Canton ZH):")
            print(f"   Total expenses: CHF {tax_result['total_expenses']:>8.2f}")
            print(f"   Total deductible: CHF {tax_result['total_deductible']:>8.2f}")
            print(f"   Estimated tax savings: CHF {tax_result['estimated_tax_savings']:>8.2f}")
            print(f"   Number of expenses: {tax_result['expense_count']}")
            
            print(f"\n   📊 Deductions by category:")
            for category, data in tax_result['deductions_by_category'].items():
                if data['deductible_amount'] > 0:
                    print(f"      {category:<25}: CHF {data['deductible_amount']:>8.2f} ({data['expense_count']} items)")
        else:
            print(f"❌ Tax calculation failed: {tax_result.get('error')}")
        
        # Step 7: Generate reports and exports
        print("\n📤 Step 7: Generate Reports and Exports")
        print("-" * 40)
        
        # Dashboard summary
        dashboard = sa.get_dashboard_summary()
        if 'error' not in dashboard:
            print(f"📊 Dashboard Summary:")
            print(f"   Year: {dashboard['year']}")
            print(f"   Total expenses: {dashboard['total_expenses']}")
            print(f"   Total amount: CHF {dashboard['total_amount_chf']:,.2f}")
            print(f"   Business amount: CHF {dashboard['business_amount_chf']:,.2f}")
            
            print(f"\n   📈 Top categories:")
            for cat in dashboard['top_categories'][:3]:
                print(f"      {cat['category']:<20}: CHF {cat['amount_chf']:>8.2f} ({cat['count']} items)")
        
        # Export tax data
        print(f"\n📄 Exporting tax data...")
        export_result = sa.export_tax_data(year=2024, format='csv', canton='ZH')
        
        if export_result['success']:
            print(f"   ✅ Export generated:")
            print(f"      Records: {export_result['record_count']}")
            print(f"      Size: {export_result['size_bytes']:,} bytes")
            print(f"      Format: {export_result.get('format', 'csv')}")
            
            # Save export to file
            export_filename = f"demo_tax_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(export_filename, 'w', encoding='utf-8') as f:
                f.write(export_result['content'])
            print(f"      Saved to: {export_filename}")
        else:
            print(f"   ❌ Export failed: {export_result.get('error')}")
        
        # Step 8: Generate reconciliation report
        print(f"\n🔍 Step 8: Reconciliation Report")
        print("-" * 40)
        
        reconciliation_summary = sa.get_reconciliation_summary()
        if 'error' not in reconciliation_summary:
            print(f"📋 Reconciliation Summary:")
            print(f"   Total matches: {reconciliation_summary['total_matches']}")
            print(f"   Exact matches: {reconciliation_summary['exact_matches']}")
            print(f"   Probable matches: {reconciliation_summary['probable_matches']}")
            print(f"   Needs review: {reconciliation_summary['needs_review']}")
            print(f"   Confirmed matches: {reconciliation_summary['confirmed_matches']}")
            print(f"   Unmatched expenses: {reconciliation_summary['unmatched_expenses']}")
            print(f"   Average confidence: {reconciliation_summary['avg_confidence']:.2f}")
        
        print(f"\n🎉 Workflow Complete!")
        print("=" * 60)
        print(f"✅ Successfully processed monthly expenses")
        print(f"✅ Imported and reconciled bank transactions")
        print(f"✅ Calculated tax deductions for Swiss compliance")
        print(f"✅ Generated export ready for tax software")
        print(f"✅ All data stored in structured database")
        
        print(f"\n💡 Next steps in real usage:")
        print(f"   1. Process actual receipt images with OCR")
        print(f"   2. Import real bank statement files")
        print(f"   3. Review and confirm uncertain matches")
        print(f"   4. Fine-tune business expense percentages")
        print(f"   5. Export final data for tax preparation")
        
        return True
        
    except Exception as e:
        print(f"❌ Workflow failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
                print(f"\n🧹 Cleaned up demo database: {db_path}")
        except:
            pass

if __name__ == "__main__":
    success = complete_workflow_example()
    sys.exit(0 if success else 1)
