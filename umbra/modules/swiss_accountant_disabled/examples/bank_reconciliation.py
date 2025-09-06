#!/usr/bin/env python3
"""
Swiss Accountant Bank Statement Processing Example
Demonstrates bank statement import and transaction reconciliation.
"""

import os
import sys
from pathlib import Path
from datetime import date, datetime, timedelta
import tempfile
import csv
from io import StringIO

# Add the module path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from umbra.modules.swiss_accountant import create_swiss_accountant, get_default_config

def create_sample_bank_statement_csv(filename: str, account_type: str = "ubs") -> bool:
    """Create sample bank statement CSV file for testing."""
    try:
        if account_type == "ubs":
            # UBS-style CSV format
            header = [
                "Trade Date", "Valuta Date", "Description", "Reference", 
                "Debit", "Credit", "Currency", "Balance"
            ]
            
            transactions = [
                ["15.01.2024", "15.01.2024", "MIGROS ZURICH HB", "REF123456", "45.80", "", "CHF", "2954.20"],
                ["10.01.2024", "10.01.2024", "APPLE STORE ZURICH", "REF123457", "1668.00", "", "CHF", "3000.00"],
                ["08.01.2024", "08.01.2024", "SBB ONLINE TICKET", "REF123458", "24.00", "", "CHF", "4668.00"],
                ["05.01.2024", "05.01.2024", "SALARY TRANSFER", "SAL202401", "", "4500.00", "CHF", "4692.00"],
                ["03.01.2024", "03.01.2024", "COOP BASEL CITY", "REF123459", "89.90", "", "CHF", "192.00"],
                ["02.01.2024", "02.01.2024", "RESTAURANT ZEUGHAUSKELLER", "REF123460", "85.50", "", "CHF", "281.90"],
            ]
            
        elif account_type == "postfinance":
            # PostFinance-style CSV format
            header = [
                "Datum", "Beschreibung", "Auftraggeber/Zahlungsempfänger", 
                "Gutschrift", "Belastung", "Saldo", "Währung"
            ]
            
            transactions = [
                ["15.01.2024", "Kartenzahlung", "MIGROS ZURICH HB", "", "45.80", "2954.20", "CHF"],
                ["10.01.2024", "Kartenzahlung", "APPLE STORE ZURICH", "", "1668.00", "3000.00", "CHF"],
                ["08.01.2024", "Online-Zahlung", "SBB CFF FFS", "", "24.00", "4668.00", "CHF"],
                ["05.01.2024", "Lohnzahlung", "EMPLOYER AG", "4500.00", "", "4692.00", "CHF"],
                ["03.01.2024", "Kartenzahlung", "COOP SCHWEIZ", "", "89.90", "192.00", "CHF"],
                ["02.01.2024", "Kartenzahlung", "RESTAURANT ZEUGHAUSKELLER", "", "85.50", "281.90", "CHF"],
            ]
        
        elif account_type == "revolut":
            # Revolut-style CSV format
            header = [
                "Type", "Product", "Started Date", "Completed Date", "Description", 
                "Amount", "Fee", "Currency", "State", "Balance"
            ]
            
            transactions = [
                ["CARD_PAYMENT", "Current", "2024-01-15 10:30:00", "2024-01-15 10:30:00", "MIGROS ZURICH HB", "-45.80", "0", "CHF", "COMPLETED", "2954.20"],
                ["CARD_PAYMENT", "Current", "2024-01-10 14:20:00", "2024-01-10 14:20:00", "APPLE STORE ZURICH", "-1668.00", "0", "CHF", "COMPLETED", "3000.00"],
                ["TRANSFER", "Current", "2024-01-08 09:15:00", "2024-01-08 09:15:00", "SBB Online Payment", "-24.00", "0", "CHF", "COMPLETED", "4668.00"],
                ["TRANSFER", "Current", "2024-01-05 08:00:00", "2024-01-05 08:00:00", "Salary Payment", "4500.00", "0", "CHF", "COMPLETED", "4692.00"],
                ["CARD_PAYMENT", "Current", "2024-01-03 16:45:00", "2024-01-03 16:45:00", "COOP BASEL CITY", "-89.90", "0", "CHF", "COMPLETED", "192.00"],
                ["CARD_PAYMENT", "Current", "2024-01-02 19:30:00", "2024-01-02 19:30:00", "RESTAURANT ZEUGHAUSKELLER", "-85.50", "0", "CHF", "COMPLETED", "281.90"],
            ]
        
        # Write CSV file
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            if account_type in ["ubs", "postfinance"]:
                delimiter = ';'
            else:
                delimiter = ','
            
            writer = csv.writer(csvfile, delimiter=delimiter)
            writer.writerow(header)
            writer.writerows(transactions)
        
        return True
        
    except Exception as e:
        print(f"Failed to create sample bank statement: {e}")
        return False

def bank_statement_processing_example():
    """Demonstrate bank statement processing and reconciliation."""
    print("🏦 Swiss Accountant - Bank Statement Processing Example")
    print("=" * 65)
    
    # Configuration
    config = get_default_config()
    config.update({
        'canton': 'ZH',
        'log_level': 'INFO',
        'reconciliation_auto_accept': True
    })
    
    # Initialize with temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = tmp_db.name
    
    try:
        # Initialize Swiss Accountant
        print("\n📱 Initialize Swiss Accountant")
        print("-" * 40)
        
        sa = create_swiss_accountant(
            db_path=db_path,
            user_id="bank_demo_user",
            config=config
        )
        print("✅ Swiss Accountant initialized for bank statement processing")
        
        # Step 1: Create sample expenses (simulating previous receipt processing)
        print("\n🧾 Step 1: Create Sample Expenses")
        print("-" * 40)
        
        sample_expenses = [
            {
                'date': '2024-01-15',
                'merchant': 'Migros Zurich HB',
                'amount': 45.80,
                'category': 'groceries',
                'business_pct': 0
            },
            {
                'date': '2024-01-10',
                'merchant': 'Apple Store Zurich',
                'amount': 1668.00,
                'category': 'professional_equipment',
                'business_pct': 80
            },
            {
                'date': '2024-01-08',
                'merchant': 'SBB CFF FFS',
                'amount': 24.00,
                'category': 'commute_public_transport',
                'business_pct': 100
            },
            {
                'date': '2024-01-03',
                'merchant': 'Coop Basel City',
                'amount': 89.90,
                'category': 'groceries',
                'business_pct': 0
            },
            {
                'date': '2024-01-02',
                'merchant': 'Restaurant Zeughauskeller',
                'amount': 85.50,
                'category': 'meals_work',
                'business_pct': 100
            }
        ]
        
        expense_ids = []
        for expense in sample_expenses:
            expense_id = sa.db.execute("""
                INSERT INTO sa_expenses (
                    user_id, date_local, merchant_text, amount_cents,
                    currency, category_code, pro_pct, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "bank_demo_user",
                expense['date'],
                expense['merchant'],
                int(expense['amount'] * 100),
                'CHF',
                expense['category'],
                expense['business_pct'],
                f"Sample expense for reconciliation testing"
            ))
            expense_ids.append(expense_id)
            
            business_marker = "💼" if expense['business_pct'] > 0 else "👤"
            print(f"   {business_marker} {expense['merchant']:<30} CHF {expense['amount']:>8.2f}")
        
        print(f"✅ Created {len(sample_expenses)} sample expenses")
        
        # Step 2: Process different bank statement formats
        bank_formats = ["ubs", "postfinance", "revolut"]
        
        for bank_format in bank_formats:
            print(f"\n🏦 Step 2.{bank_formats.index(bank_format)+1}: Process {bank_format.upper()} Statement")
            print("-" * 40)
            
            # Create sample statement file
            statement_filename = f"sample_statement_{bank_format}.csv"
            if create_sample_bank_statement_csv(statement_filename, bank_format):
                print(f"   ✅ Created sample {bank_format.upper()} statement: {statement_filename}")
                
                # Process the statement
                statement_result = sa.process_bank_statement(
                    statement_filename, 
                    account_name=f"{bank_format.upper()} Checking Account"
                )
                
                if statement_result['success']:
                    print(f"   📋 Statement processed successfully:")
                    print(f"      Statement ID: {statement_result['statement_id']}")
                    print(f"      Transactions: {statement_result['transaction_count']}")
                    print(f"      Format: {statement_result['format']}")
                    print(f"      Account: {statement_result.get('account_info', {}).get('bank', bank_format.upper())}")
                    
                    # Show transaction details
                    transactions = sa.db.query_all("""
                        SELECT * FROM sa_transactions 
                        WHERE statement_id = ? 
                        ORDER BY booking_date DESC
                    """, (statement_result['statement_id'],))
                    
                    print(f"\n   📊 Transaction Details:")
                    for trans in transactions[:5]:  # Show first 5
                        amount = trans['amount_cents'] / 100
                        direction = "💳" if amount < 0 else "💰"
                        print(f"      {direction} {trans['counterparty']:<25} CHF {amount:>8.2f} ({trans['booking_date']})")
                
                else:
                    print(f"   ❌ Statement processing failed: {statement_result.get('error')}")
                
                # Cleanup statement file
                if os.path.exists(statement_filename):
                    os.unlink(statement_filename)
            
            else:
                print(f"   ❌ Failed to create sample {bank_format.upper()} statement")
        
        # Step 3: Perform reconciliation
        print(f"\n🔄 Step 3: Reconcile Expenses with Transactions")
        print("-" * 40)
        
        print("   🔍 Starting reconciliation process...")
        reconcile_result = sa.reconcile_expenses(
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            auto_accept=True
        )
        
        if reconcile_result['success']:
            print(f"   ✅ Reconciliation completed successfully!")
            print(f"      Session ID: {reconcile_result['session_id']}")
            print(f"      Strategy: {reconcile_result['strategy']}")
            print(f"      Total expenses: {reconcile_result['total_expenses']}")
            print(f"      Total transactions: {reconcile_result['total_transactions']}")
            
            print(f"\n   📊 Matching Results:")
            print(f"      🎯 Exact matches: {reconcile_result['exact_matches']}")
            print(f"      🎲 Probable matches: {reconcile_result['probable_matches']}")
            print(f"      ⚠️  Needs review: {reconcile_result['needs_review']}")
            print(f"      ✅ Auto-accepted: {reconcile_result['auto_accepted']}")
            print(f"      ❓ Unmatched expenses: {reconcile_result['unmatched_expenses']}")
            print(f"      ❓ Unmatched transactions: {reconcile_result['unmatched_transactions']}")
            
            # Show match details
            if reconcile_result.get('matches'):
                print(f"\n   🔗 Match Details:")
                for match in reconcile_result['matches'][:5]:  # Show first 5
                    confidence_emoji = "🎯" if match['confidence'] > 0.9 else "🎲" if match['confidence'] > 0.7 else "⚠️"
                    print(f"      {confidence_emoji} {match['merchant']:<25} ↔ {match['counterparty']:<25}")
                    print(f"         Expense: CHF {match['expense_amount']:>8.2f} | Transaction: CHF {abs(match['transaction_amount']):>8.2f}")
                    print(f"         Confidence: {match['confidence']:.3f} | Status: {match['match_type']}")
        
        else:
            print(f"   ❌ Reconciliation failed: {reconcile_result.get('error')}")
        
        # Step 4: Review pending matches
        print(f"\n⚠️  Step 4: Review Pending Matches")
        print("-" * 40)
        
        pending_matches = sa.transaction_matcher.get_pending_matches("bank_demo_user")
        
        if pending_matches:
            print(f"   Found {len(pending_matches)} matches needing review:")
            
            for i, match in enumerate(pending_matches[:3]):  # Show first 3
                print(f"\n   📋 Match {i+1} (ID: {match['match_id']}):")
                print(f"      Expense: {match['expense']['merchant']} - CHF {match['expense']['amount']:.2f}")
                print(f"      Transaction: {match['transaction']['counterparty']} - CHF {abs(match['transaction']['amount']):.2f}")
                print(f"      Confidence: {match['confidence']:.3f}")
                print(f"      Dates: {match['expense']['date']} ↔ {match['transaction']['date']}")
                
                # Simulate user decision (auto-confirm high confidence matches)
                if match['confidence'] > 0.8:
                    confirm_result = sa.transaction_matcher.confirm_match(
                        match['match_id'], 
                        "bank_demo_user"
                    )
                    if confirm_result['success']:
                        print(f"      ✅ Auto-confirmed (high confidence)")
                    else:
                        print(f"      ❌ Confirmation failed: {confirm_result.get('error')}")
                else:
                    print(f"      ⏸️  Pending manual review (low confidence)")
        
        else:
            print(f"   ✅ No matches need manual review!")
        
        # Step 5: Generate reconciliation report
        print(f"\n📊 Step 5: Reconciliation Summary Report")
        print("-" * 40)
        
        reconciliation_summary = sa.get_reconciliation_summary()
        
        if 'error' not in reconciliation_summary:
            print(f"   📈 Overall Reconciliation Statistics:")
            print(f"      Total matches: {reconciliation_summary['total_matches']}")
            print(f"      Exact matches: {reconciliation_summary['exact_matches']}")
            print(f"      Probable matches: {reconciliation_summary['probable_matches']}")
            print(f"      Needs review: {reconciliation_summary['needs_review']}")
            print(f"      Confirmed by user: {reconciliation_summary['confirmed_matches']}")
            print(f"      Rejected by user: {reconciliation_summary['rejected_matches']}")
            print(f"      Average confidence: {reconciliation_summary['avg_confidence']:.3f}")
            print(f"      Unmatched expenses: {reconciliation_summary['unmatched_expenses']}")
            print(f"      Unmatched transactions: {reconciliation_summary['unmatched_transactions']}")
            
            # Show recent sessions
            if reconciliation_summary.get('recent_sessions'):
                print(f"\n   📋 Recent Reconciliation Sessions:")
                for session in reconciliation_summary['recent_sessions'][:3]:
                    print(f"      Session {session['id']}: {session['strategy']}")
                    print(f"         Period: {session['period_start']} to {session['period_end']}")
                    print(f"         Results: {session['exact_matches']} exact, {session['probable_matches']} probable")
        
        else:
            print(f"   ❌ Failed to get reconciliation summary: {reconciliation_summary['error']}")
        
        # Step 6: Export reconciliation data
        print(f"\n📤 Step 6: Export Reconciliation Data")
        print("-" * 40)
        
        export_result = sa.export_manager.export_reconciliation_data(
            sa.db, 
            "bank_demo_user", 
            format='csv'
        )
        
        if export_result['success']:
            print(f"   ✅ Reconciliation export generated:")
            print(f"      Records: {export_result['record_count']}")
            print(f"      Size: {export_result['size_bytes']:,} bytes")
            
            # Save to file for demonstration
            export_filename = f"reconciliation_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(export_filename, 'w', encoding='utf-8') as f:
                f.write(export_result['content'])
            print(f"      Saved to: {export_filename}")
            
            # Show sample of export content
            lines = export_result['content'].split('\n')
            print(f"\n   📋 Export Sample (first 3 lines):")
            for line in lines[:3]:
                if line.strip():
                    print(f"      {line}")
        
        else:
            print(f"   ❌ Export failed: {export_result.get('error')}")
        
        print(f"\n🎉 Bank Statement Processing Complete!")
        print("=" * 65)
        print(f"✅ Successfully processed multiple bank statement formats")
        print(f"✅ Reconciled expenses with transactions automatically")
        print(f"✅ Reviewed and confirmed uncertain matches")
        print(f"✅ Generated comprehensive reconciliation reports")
        print(f"✅ Exported data for audit and tax preparation")
        
        print(f"\n💡 Key Benefits Demonstrated:")
        print(f"   🏦 Multi-bank support (UBS, PostFinance, Revolut, etc.)")
        print(f"   🤖 Automated matching with high accuracy")
        print(f"   🎯 Configurable matching strategies and thresholds")
        print(f"   👤 Human oversight for uncertain matches")
        print(f"   📊 Detailed reporting and audit trails")
        print(f"   📤 Export compatibility with tax software")
        
        print(f"\n🚀 Next Steps in Real Usage:")
        print(f"   1. Import actual bank statement files")
        print(f"   2. Fine-tune matching strategies for your patterns")
        print(f"   3. Set up automated monthly reconciliation")
        print(f"   4. Review and approve pending matches")
        print(f"   5. Export reconciled data for tax preparation")
        
        return True
        
    except Exception as e:
        print(f"❌ Bank statement processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        try:
            # Clean up any remaining files
            for filename in ["sample_statement_ubs.csv", "sample_statement_postfinance.csv", 
                           "sample_statement_revolut.csv", "reconciliation_export*.csv"]:
                if '*' in filename:
                    # Handle wildcard
                    import glob
                    for file in glob.glob(filename):
                        if os.path.exists(file):
                            os.unlink(file)
                else:
                    if os.path.exists(filename):
                        os.unlink(filename)
            
            if os.path.exists(db_path):
                os.unlink(db_path)
                print(f"\n🧹 Cleaned up demo files and database")
        except:
            pass

if __name__ == "__main__":
    success = bank_statement_processing_example()
    sys.exit(0 if success else 1)
