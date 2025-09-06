"""
Command Line Interface for Swiss Accountant
Provides easy command-line access to all Swiss Accountant functionality.
"""
import argparse
import sys
import json
from datetime import datetime, date
from pathlib import Path
import logging
from typing import Dict, Any

from .main import create_swiss_accountant, get_default_config


class SwissAccountantCLI:
    """Command Line Interface for Swiss Accountant."""
    
    def __init__(self):
        """Initialize CLI."""
        self.accountant = None
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging for CLI."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def main(self):
        """Main CLI entry point."""
        parser = self.create_parser()
        args = parser.parse_args()
        
        # Initialize Swiss Accountant
        config = get_default_config()
        if args.config:
            try:
                with open(args.config, 'r') as f:
                    user_config = json.load(f)
                config.update(user_config)
            except Exception as e:
                print(f"Warning: Could not load config file {args.config}: {e}")
        
        self.accountant = create_swiss_accountant(
            db_path=args.database,
            user_id=args.user_id,
            config=config
        )
        
        # Execute command
        try:
            if hasattr(args, 'func'):
                result = args.func(args)
                self.print_result(result)
            else:
                parser.print_help()
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser."""
        parser = argparse.ArgumentParser(
            description='Swiss Accountant - Tax-compliant expense tracking for Switzerland',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Process a receipt
  swiss-accountant process-receipt receipt.jpg --user-id john

  # Import bank statement
  swiss-accountant import-statement statement.csv --user-id john --account "UBS Checking"

  # Reconcile expenses with transactions
  swiss-accountant reconcile --start-date 2024-01-01 --end-date 2024-01-31 --user-id john

  # Calculate tax deductions
  swiss-accountant tax-calc --year 2024 --canton ZH --user-id john

  # Export tax data
  swiss-accountant export --year 2024 --format xlsx --user-id john

  # View dashboard
  swiss-accountant dashboard --user-id john
            """
        )
        
        # Global arguments
        parser.add_argument('--database', '-d', 
                          default='swiss_accountant.db',
                          help='Database file path')
        parser.add_argument('--user-id', '-u',
                          required=True,
                          help='User identifier')
        parser.add_argument('--config', '-c',
                          help='Configuration file path')
        parser.add_argument('--verbose', '-v',
                          action='store_true',
                          help='Verbose output')
        
        # Subcommands
        subparsers = parser.add_subparsers(title='Commands', dest='command')
        
        # Process receipt command
        receipt_parser = subparsers.add_parser('process-receipt', 
                                             help='Process receipt/invoice image or PDF')
        receipt_parser.add_argument('file_path', help='Path to receipt file')
        receipt_parser.set_defaults(func=self.cmd_process_receipt)
        
        # Import statement command
        statement_parser = subparsers.add_parser('import-statement',
                                               help='Import bank/card statement')
        statement_parser.add_argument('file_path', help='Path to statement file')
        statement_parser.add_argument('--account', help='Account name')
        statement_parser.set_defaults(func=self.cmd_import_statement)
        
        # List expenses command
        expenses_parser = subparsers.add_parser('list-expenses',
                                              help='List expenses')
        expenses_parser.add_argument('--start-date', type=self.parse_date,
                                   help='Start date (YYYY-MM-DD)')
        expenses_parser.add_argument('--end-date', type=self.parse_date,
                                   help='End date (YYYY-MM-DD)')
        expenses_parser.add_argument('--category', help='Category filter')
        expenses_parser.add_argument('--limit', type=int, default=50,
                                   help='Maximum results')
        expenses_parser.set_defaults(func=self.cmd_list_expenses)
        
        # Update expense command
        update_parser = subparsers.add_parser('update-expense',
                                            help='Update expense category')
        update_parser.add_argument('expense_id', type=int, help='Expense ID')
        update_parser.add_argument('--category', required=True,
                                 help='New category code')
        update_parser.add_argument('--business-pct', type=int,
                                 help='Business use percentage (0-100)')
        update_parser.set_defaults(func=self.cmd_update_expense)
        
        # Reconcile command
        reconcile_parser = subparsers.add_parser('reconcile',
                                               help='Reconcile expenses with transactions')
        reconcile_parser.add_argument('--start-date', type=self.parse_date,
                                    required=True,
                                    help='Start date (YYYY-MM-DD)')
        reconcile_parser.add_argument('--end-date', type=self.parse_date,
                                    required=True,
                                    help='End date (YYYY-MM-DD)')
        reconcile_parser.add_argument('--no-auto-accept', action='store_true',
                                    help='Disable auto-accept of matches')
        reconcile_parser.set_defaults(func=self.cmd_reconcile)
        
        # Tax calculation command
        tax_parser = subparsers.add_parser('tax-calc',
                                         help='Calculate tax deductions')
        tax_parser.add_argument('--year', type=int, 
                              default=datetime.now().year,
                              help='Tax year')
        tax_parser.add_argument('--canton', help='Swiss canton')
        tax_parser.set_defaults(func=self.cmd_tax_calc)
        
        # Export command
        export_parser = subparsers.add_parser('export',
                                            help='Export data')
        export_parser.add_argument('--year', type=int,
                                 default=datetime.now().year,
                                 help='Year to export')
        export_parser.add_argument('--format', choices=['csv', 'xlsx', 'json'],
                                 default='csv',
                                 help='Export format')
        export_parser.add_argument('--canton', help='Canton filter')
        export_parser.add_argument('--output', '-o', help='Output file path')
        export_parser.set_defaults(func=self.cmd_export)
        
        # Dashboard command
        dashboard_parser = subparsers.add_parser('dashboard',
                                               help='Show dashboard summary')
        dashboard_parser.set_defaults(func=self.cmd_dashboard)
        
        # Health check command
        health_parser = subparsers.add_parser('health',
                                            help='System health check')
        health_parser.set_defaults(func=self.cmd_health)
        
        return parser
    
    def parse_date(self, date_str: str) -> date:
        """Parse date string."""
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")
    
    def print_result(self, result: Any):
        """Print command result."""
        if isinstance(result, dict):
            if result.get('success') is False:
                print(f"❌ Error: {result.get('error', 'Unknown error')}")
                sys.exit(1)
            else:
                print(json.dumps(result, indent=2, default=str))
        else:
            print(result)
    
    # Command implementations
    
    def cmd_process_receipt(self, args) -> Dict[str, Any]:
        """Process receipt command."""
        if not Path(args.file_path).exists():
            return {'success': False, 'error': f'File not found: {args.file_path}'}
        
        print(f"🧾 Processing receipt: {args.file_path}")
        result = self.accountant.process_receipt(args.file_path, args.user_id)
        
        if result.get('success'):
            print(f"✅ Receipt processed successfully!")
            print(f"   Document ID: {result['document_id']}")
            print(f"   Expense ID: {result['expense_id']}")
            print(f"   Merchant: {result['parsed_data'].get('merchant', 'Unknown')}")
            print(f"   Amount: CHF {result['parsed_data'].get('total_amount', 0):.2f}")
            print(f"   Tax Category: {result['tax_category'].get('deduction_category', 'non_deductible')}")
            print(f"   Confidence: {result['overall_confidence']:.2f}")
        
        return result
    
    def cmd_import_statement(self, args) -> Dict[str, Any]:
        """Import statement command."""
        if not Path(args.file_path).exists():
            return {'success': False, 'error': f'File not found: {args.file_path}'}
        
        print(f"🏦 Importing statement: {args.file_path}")
        result = self.accountant.process_bank_statement(
            args.file_path, 
            args.user_id, 
            args.account
        )
        
        if result.get('success'):
            print(f"✅ Statement imported successfully!")
            print(f"   Statement ID: {result['statement_id']}")
            print(f"   Transactions: {result['transaction_count']}")
            print(f"   Format: {result['format']}")
        
        return result
    
    def cmd_list_expenses(self, args) -> Dict[str, Any]:
        """List expenses command."""
        print("💰 Fetching expenses...")
        expenses = self.accountant.get_expenses(
            user_id=args.user_id,
            start_date=args.start_date,
            end_date=args.end_date,
            category=args.category,
            limit=args.limit
        )
        
        if not expenses:
            print("No expenses found.")
            return {'expenses': []}
        
        print(f"\n📋 Found {len(expenses)} expenses:")
        print("-" * 80)
        print(f"{'ID':<5} {'Date':<12} {'Merchant':<25} {'Amount':<12} {'Category':<15}")
        print("-" * 80)
        
        for expense in expenses:
            print(f"{expense['id']:<5} "
                  f"{expense['date_local']:<12} "
                  f"{(expense['merchant_text'] or '')[:24]:<25} "
                  f"CHF {expense['amount_chf']:>8.2f} "
                  f"{expense['category_code']:<15}")
        
        total_amount = sum(e['amount_chf'] for e in expenses)
        print("-" * 80)
        print(f"Total: CHF {total_amount:.2f}")
        
        return {'expenses': expenses, 'total_amount': total_amount}
    
    def cmd_update_expense(self, args) -> Dict[str, Any]:
        """Update expense command."""
        print(f"✏️  Updating expense {args.expense_id}...")
        result = self.accountant.update_expense_category(
            args.expense_id,
            args.category,
            args.business_pct,
            args.user_id
        )
        
        if result.get('success'):
            print(f"✅ Expense updated successfully!")
            print(f"   Category: {args.category}")
            if args.business_pct is not None:
                print(f"   Business %: {args.business_pct}%")
        
        return result
    
    def cmd_reconcile(self, args) -> Dict[str, Any]:
        """Reconcile command."""
        print(f"🔄 Reconciling expenses from {args.start_date} to {args.end_date}...")
        result = self.accountant.reconcile_expenses(
            args.start_date,
            args.end_date,
            args.user_id,
            auto_accept=not args.no_auto_accept
        )
        
        if result.get('success'):
            print(f"✅ Reconciliation completed!")
            print(f"   Exact matches: {result['exact_matches']}")
            print(f"   Probable matches: {result['probable_matches']}")
            print(f"   Needs review: {result['needs_review']}")
            print(f"   Auto-accepted: {result['auto_accepted']}")
            print(f"   Unmatched expenses: {result['unmatched_expenses']}")
            print(f"   Unmatched transactions: {result['unmatched_transactions']}")
        
        return result
    
    def cmd_tax_calc(self, args) -> Dict[str, Any]:
        """Tax calculation command."""
        print(f"🧮 Calculating tax deductions for {args.year}...")
        result = self.accountant.calculate_tax_deductions(
            args.year,
            args.canton,
            args.user_id
        )
        
        if result.get('success'):
            print(f"✅ Tax calculation completed!")
            print(f"   Total expenses: CHF {result['total_expenses']:,.2f}")
            print(f"   Total deductible: CHF {result['total_deductible']:,.2f}")
            print(f"   Estimated tax savings: CHF {result['estimated_tax_savings']:,.2f}")
            print(f"   Number of expenses: {result['expense_count']}")
            
            print("\n📊 Deductions by category:")
            for category, data in result['deductions_by_category'].items():
                print(f"   {category}: CHF {data['deductible_amount']:,.2f} "
                      f"({data['expense_count']} expenses)")
        
        return result
    
    def cmd_export(self, args) -> Dict[str, Any]:
        """Export command."""
        print(f"📤 Exporting tax data for {args.year} in {args.format} format...")
        result = self.accountant.export_tax_data(
            args.year,
            args.format,
            args.canton,
            args.user_id
        )
        
        if result.get('success'):
            filename = args.output or result['filename']
            
            # Write export content to file
            content = result['content']
            if args.format == 'xlsx':
                with open(filename, 'wb') as f:
                    f.write(content)
            else:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            print(f"✅ Export completed!")
            print(f"   File: {filename}")
            print(f"   Records: {result['record_count']}")
            print(f"   Size: {result['size_bytes']:,} bytes")
        
        return result
    
    def cmd_dashboard(self, args) -> Dict[str, Any]:
        """Dashboard command."""
        print("📊 Loading dashboard...")
        result = self.accountant.get_dashboard_summary(args.user_id)
        
        if 'error' not in result:
            print(f"✅ Dashboard for {result['year']}")
            print(f"   Total expenses: {result['total_expenses']}")
            print(f"   Total amount: CHF {result['total_amount_chf']:,.2f}")
            print(f"   Business amount: CHF {result['business_amount_chf']:,.2f}")
            
            print("\n📈 Monthly breakdown:")
            for month_data in result['monthly_breakdown']:
                print(f"   {month_data['month']}: {month_data['count']} expenses, "
                      f"CHF {month_data['amount_chf']:,.2f}")
            
            print("\n🏷️  Top categories:")
            for cat_data in result['top_categories'][:5]:
                print(f"   {cat_data['category']}: {cat_data['count']} expenses, "
                      f"CHF {cat_data['amount_chf']:,.2f}")
            
            reconciliation = result['reconciliation']
            if reconciliation:
                print(f"\n🔄 Reconciliation status:")
                print(f"   Total matches: {reconciliation.get('total_matches', 0)}")
                print(f"   Confirmed: {reconciliation.get('confirmed_matches', 0)}")
                print(f"   Unmatched expenses: {reconciliation.get('unmatched_expenses', 0)}")
        
        return result
    
    def cmd_health(self, args) -> Dict[str, Any]:
        """Health check command."""
        print("🔍 Performing health check...")
        result = self.accountant.health_check()
        
        status_emoji = {
            'healthy': '✅',
            'degraded': '⚠️',
            'unhealthy': '❌'
        }
        
        print(f"{status_emoji.get(result['status'], '❓')} System status: {result['status']}")
        
        if 'components' in result:
            print("\n🔧 Component status:")
            for component, status in result['components'].items():
                component_emoji = '✅' if status == 'healthy' else '❌'
                print(f"   {component_emoji} {component}: {status}")
        
        return result


def main():
    """CLI entry point."""
    cli = SwissAccountantCLI()
    cli.main()


if __name__ == '__main__':
    main()
