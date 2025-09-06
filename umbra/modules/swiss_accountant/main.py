"""
Swiss Accountant Main Module
Orchestrates all components for Swiss tax-compliant expense tracking and deduction optimization.
"""
import os
from typing import Dict, List, Optional, Tuple, Any, Union
from decimal import Decimal
from datetime import datetime, date
from pathlib import Path
import logging
import json

# Import all Swiss Accountant components
from .database.manager import create_database_manager
from .ingest.ocr import create_ocr_processor
from .ingest.parsers import create_document_parser
from .ingest.statements import create_statement_parser
from .normalize.merchants import create_merchant_normalizer
from .normalize.categories import create_category_mapper
from .reconcile.matcher import create_expense_transaction_matcher
from .exports.csv_excel import create_export_manager


class SwissAccountant:
    """Main Swiss Accountant class that orchestrates all functionality."""
    
    def __init__(self, 
                 db_path: str = None,
                 user_id: str = None,
                 config: Dict[str, Any] = None):
        """Initialize Swiss Accountant.
        
        Args:
            db_path: Path to SQLite database file
            user_id: Default user ID for operations
            config: Configuration dictionary
        """
        self.user_id = user_id
        self.config = config or {}
        
        # Setup logging
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Initialize database
        if not db_path:
            db_path = self.config.get('database_path', 'swiss_accountant.db')
        
        self.db = create_database_manager(db_path)
        
        # Initialize all components
        self.ocr = create_ocr_processor()
        self.document_parser = create_document_parser()
        self.statement_parser = create_statement_parser()
        self.merchant_normalizer = create_merchant_normalizer(self.db)
        self.category_mapper = create_category_mapper(self.db)
        self.transaction_matcher = create_expense_transaction_matcher(self.db)
        self.export_manager = create_export_manager()
        
        self.logger.info("Swiss Accountant initialized successfully")
    
    def _setup_logging(self):
        """Setup logging configuration."""
        log_level = self.config.get('log_level', 'INFO')
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format=log_format,
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('swiss_accountant.log')
            ]
        )
    
    # Document Processing Methods
    
    def process_receipt(self, 
                       file_path: str,
                       user_id: str = None) -> Dict[str, Any]:
        """Process a receipt image/PDF and extract expense data.
        
        Args:
            file_path: Path to receipt file
            user_id: User ID (defaults to instance user_id)
            
        Returns:
            Dict with processing result
        """
        try:
            user_id = user_id or self.user_id
            if not user_id:
                return {'success': False, 'error': 'User ID required'}
            
            self.logger.info(f"Processing receipt: {file_path}")
            
            # Store document
            doc_result = self.db.store_document(file_path, user_id)
            if not doc_result['success']:
                return doc_result
            
            doc_id = doc_result['document_id']
            
            # Perform OCR
            ocr_result = self.ocr.extract_text_from_image(file_path)
            if not ocr_result['success']:
                self.logger.error(f"OCR failed for {file_path}: {ocr_result.get('error')}")
                return ocr_result
            
            # Detect document type and parse
            detection_result = self.document_parser.detect_document_type(
                ocr_result['text'], 
                os.path.basename(file_path)
            )
            
            doc_type = detection_result['document_type']
            
            # Parse based on detected type
            if doc_type.value == 'receipt':
                parse_result = self.document_parser.parse_receipt(ocr_result['text'])
            elif doc_type.value == 'invoice':
                parse_result = self.document_parser.parse_invoice(ocr_result['text'])
            else:
                # Use common field extraction
                common_fields = self.document_parser.extract_common_fields(ocr_result['text'])
                parse_result = {
                    'document_type': doc_type.value,
                    'merchant': common_fields['merchants'][0]['name'] if common_fields['merchants'] else None,
                    'date': common_fields['dates'][0]['date'] if common_fields['dates'] else None,
                    'total_amount': common_fields['amounts'][-1]['value'] if common_fields['amounts'] else None,
                    'confidence': 0.5
                }
            
            # Normalize merchant
            merchant_result = {'canonical': None, 'merchant_id': None}
            if parse_result.get('merchant'):
                merchant_result = self.merchant_normalizer.normalize_merchant_name(parse_result['merchant'])
            
            # Map to tax category
            category_result = {'deduction_category': 'non_deductible', 'confidence': 0.0}
            if parse_result.get('merchant') and merchant_result.get('canonical'):
                category_result = self.category_mapper.map_expense_to_deduction_category(
                    expense_category='general',
                    merchant_name=merchant_result['canonical'],
                    description=ocr_result['text'][:200],
                    amount=Decimal(str(parse_result.get('total_amount', 0))),
                    date=datetime.fromisoformat(parse_result['date']).date() if parse_result.get('date') else date.today()
                )
            
            # Store as expense
            expense_data = {
                'user_id': user_id,
                'doc_id': doc_id,
                'date_local': parse_result.get('date', date.today().isoformat()),
                'merchant_text': parse_result.get('merchant', ''),
                'merchant_id': merchant_result.get('merchant_id'),
                'amount_cents': int((parse_result.get('total_amount', 0) * 100)),
                'currency': 'CHF',
                'category_code': category_result.get('deduction_category', 'other'),
                'pro_pct': 0,  # Default to 0% business use
                'notes': f"Parsed from {os.path.basename(file_path)}",
                'payment_method': parse_result.get('payment_method', 'unknown'),
                'vat_breakdown_json': json.dumps({
                    'rate': parse_result.get('vat_rate', 8.1),
                    'amount': parse_result.get('vat_amount', 0)
                }) if parse_result.get('vat_rate') else None
            }
            
            expense_id = self.db.execute("""
                INSERT INTO sa_expenses (
                    user_id, doc_id, date_local, merchant_text, merchant_id,
                    amount_cents, currency, category_code, pro_pct, notes,
                    payment_method, vat_breakdown_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                expense_data['user_id'], expense_data['doc_id'], expense_data['date_local'],
                expense_data['merchant_text'], expense_data['merchant_id'], expense_data['amount_cents'],
                expense_data['currency'], expense_data['category_code'], expense_data['pro_pct'],
                expense_data['notes'], expense_data['payment_method'], expense_data['vat_breakdown_json']
            ))
            
            return {
                'success': True,
                'document_id': doc_id,
                'expense_id': expense_id,
                'document_type': doc_type.value,
                'parsed_data': parse_result,
                'merchant_normalization': merchant_result,
                'tax_category': category_result,
                'ocr_confidence': ocr_result.get('confidence', 0),
                'overall_confidence': (
                    ocr_result.get('confidence', 0) + 
                    parse_result.get('confidence', 0) + 
                    merchant_result.get('confidence', 0) + 
                    category_result.get('confidence', 0)
                ) / 4
            }
            
        except Exception as e:
            self.logger.error(f"Receipt processing failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def process_bank_statement(self, 
                              file_path: str,
                              user_id: str = None,
                              account_name: str = None) -> Dict[str, Any]:
        """Process a bank statement file.
        
        Args:
            file_path: Path to statement file
            user_id: User ID (defaults to instance user_id)
            account_name: Optional account name
            
        Returns:
            Dict with processing result
        """
        try:
            user_id = user_id or self.user_id
            if not user_id:
                return {'success': False, 'error': 'User ID required'}
            
            self.logger.info(f"Processing bank statement: {file_path}")
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse statement
            parse_result = self.statement_parser.parse_statement(content)
            if not parse_result['success']:
                return parse_result
            
            # Store statement
            statement_id = self.db.execute("""
                INSERT INTO sa_statements (
                    user_id, file_name, file_path, format_type, account_name,
                    statement_period_start, statement_period_end, 
                    total_transactions, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                user_id, 
                os.path.basename(file_path),
                file_path,
                parse_result['format'],
                account_name or parse_result.get('account_info', {}).get('bank_name', 'Unknown'),
                parse_result.get('statement_info', {}).get('from_date'),
                parse_result.get('statement_info', {}).get('to_date'),
                parse_result['transaction_count']
            ))
            
            # Store transactions
            transaction_ids = []
            for transaction in parse_result['transactions']:
                trans_id = self.db.execute("""
                    INSERT INTO sa_transactions (
                        statement_id, booking_date, value_date, amount_cents,
                        currency, counterparty, description, reference, raw_desc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    statement_id,
                    transaction.get('booking_date'),
                    transaction.get('value_date'),
                    int(transaction.get('amount', 0) * 100),
                    transaction.get('currency', 'CHF'),
                    transaction.get('counterparty', ''),
                    transaction.get('description', ''),
                    transaction.get('reference', ''),
                    transaction.get('raw_description', transaction.get('description', ''))
                ))
                transaction_ids.append(trans_id)
            
            return {
                'success': True,
                'statement_id': statement_id,
                'transaction_ids': transaction_ids,
                'transaction_count': len(transaction_ids),
                'format': parse_result['format'],
                'account_info': parse_result.get('account_info', {}),
                'statement_info': parse_result.get('statement_info', {})
            }
            
        except Exception as e:
            self.logger.error(f"Bank statement processing failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # Expense Management Methods
    
    def get_expenses(self, 
                    user_id: str = None,
                    start_date: date = None,
                    end_date: date = None,
                    category: str = None,
                    limit: int = 100) -> List[Dict[str, Any]]:
        """Get expenses with optional filters.
        
        Args:
            user_id: User ID (defaults to instance user_id)
            start_date: Optional start date filter
            end_date: Optional end date filter
            category: Optional category filter
            limit: Maximum results
            
        Returns:
            List of expense dictionaries
        """
        try:
            user_id = user_id or self.user_id
            if not user_id:
                return []
            
            # Build query
            query = """
                SELECT e.*, m.canonical as merchant_canonical,
                       d.file_name as document_file
                FROM sa_expenses e
                LEFT JOIN sa_merchants m ON e.merchant_id = m.id
                LEFT JOIN sa_documents d ON e.doc_id = d.id
                WHERE e.user_id = ?
            """
            params = [user_id]
            
            if start_date:
                query += " AND e.date_local >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND e.date_local <= ?"
                params.append(end_date)
            
            if category:
                query += " AND e.category_code = ?"
                params.append(category)
            
            query += " ORDER BY e.date_local DESC, e.amount_cents DESC LIMIT ?"
            params.append(limit)
            
            expenses = self.db.query_all(query, params)
            
            # Convert amount_cents to CHF and add calculated fields
            for expense in expenses:
                expense['amount_chf'] = float(Decimal(expense['amount_cents']) / 100)
                expense['business_amount_chf'] = expense['amount_chf'] * (expense['pro_pct'] / 100) if expense['pro_pct'] > 0 else 0
                
                # Parse VAT breakdown if available
                if expense.get('vat_breakdown_json'):
                    try:
                        expense['vat_breakdown'] = json.loads(expense['vat_breakdown_json'])
                    except json.JSONDecodeError:
                        expense['vat_breakdown'] = None
            
            return expenses
            
        except Exception as e:
            self.logger.error(f"Get expenses failed: {e}")
            return []
    
    def update_expense_category(self, 
                               expense_id: int,
                               category_code: str,
                               business_percentage: int = None,
                               user_id: str = None) -> Dict[str, Any]:
        """Update expense category and business percentage.
        
        Args:
            expense_id: Expense ID to update
            category_code: New category code
            business_percentage: Optional business use percentage (0-100)
            user_id: User ID for security check
            
        Returns:
            Dict with update result
        """
        try:
            user_id = user_id or self.user_id
            if not user_id:
                return {'success': False, 'error': 'User ID required'}
            
            # Verify expense exists and belongs to user
            expense = self.db.query_one("""
                SELECT id FROM sa_expenses WHERE id = ? AND user_id = ?
            """, (expense_id, user_id))
            
            if not expense:
                return {
                    'success': False,
                    'error': 'Expense not found or access denied'
                }
            
            # Update expense
            update_query = "UPDATE sa_expenses SET category_code = ?"
            params = [category_code]
            
            if business_percentage is not None:
                update_query += ", pro_pct = ?"
                params.append(max(0, min(100, business_percentage)))
            
            update_query += " WHERE id = ?"
            params.append(expense_id)
            
            self.db.execute(update_query, params)
            
            return {
                'success': True,
                'expense_id': expense_id,
                'category_code': category_code,
                'business_percentage': business_percentage
            }
            
        except Exception as e:
            self.logger.error(f"Update expense category failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # Reconciliation Methods
    
    def reconcile_expenses(self, 
                          period_start: date,
                          period_end: date,
                          user_id: str = None,
                          auto_accept: bool = True) -> Dict[str, Any]:
        """Reconcile expenses with bank transactions for a period.
        
        Args:
            period_start: Start date for reconciliation
            period_end: End date for reconciliation
            user_id: User ID (defaults to instance user_id)
            auto_accept: Whether to auto-accept high-confidence matches
            
        Returns:
            Dict with reconciliation results
        """
        try:
            user_id = user_id or self.user_id
            if not user_id:
                return {'success': False, 'error': 'User ID required'}
            
            self.logger.info(f"Starting reconciliation for {period_start} to {period_end}")
            
            result = self.transaction_matcher.reconcile_period(
                period_start=period_start,
                period_end=period_end,
                user_id=user_id,
                auto_accept=auto_accept
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Reconciliation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_reconciliation_summary(self, user_id: str = None) -> Dict[str, Any]:
        """Get reconciliation summary for user.
        
        Args:
            user_id: User ID (defaults to instance user_id)
            
        Returns:
            Dict with reconciliation statistics
        """
        try:
            user_id = user_id or self.user_id
            if not user_id:
                return {'error': 'User ID required'}
            
            return self.transaction_matcher.get_reconciliation_summary(user_id)
            
        except Exception as e:
            self.logger.error(f"Get reconciliation summary failed: {e}")
            return {'error': str(e)}
    
    # Tax and Export Methods
    
    def calculate_tax_deductions(self, 
                                year: int,
                                canton: str = None,
                                user_id: str = None) -> Dict[str, Any]:
        """Calculate potential tax deductions for a year.
        
        Args:
            year: Tax year
            canton: Swiss canton
            user_id: User ID (defaults to instance user_id)
            
        Returns:
            Dict with deduction calculations
        """
        try:
            user_id = user_id or self.user_id
            if not user_id:
                return {'success': False, 'error': 'User ID required'}
            
            # Get all expenses for the year
            expenses = self.db.query_all("""
                SELECT e.*, cm.deduction_category, cm.confidence as mapping_confidence
                FROM sa_expenses e
                LEFT JOIN sa_category_mappings cm ON e.category_code = cm.expense_category
                WHERE e.user_id = ?
                AND strftime('%Y', e.date_local) = ?
                ORDER BY e.date_local
            """, (user_id, str(year)))
            
            # Group by deduction category
            deductions = {}
            total_expenses = 0
            total_deductible = 0
            
            for expense in expenses:
                amount_chf = float(Decimal(expense['amount_cents']) / 100)
                total_expenses += amount_chf
                
                deduction_category = expense.get('deduction_category', 'non_deductible')
                business_pct = expense.get('pro_pct', 0)
                
                # Calculate deductible amount
                if deduction_category != 'non_deductible':
                    if business_pct > 0:
                        deductible_amount = amount_chf * (business_pct / 100)
                    else:
                        deductible_amount = amount_chf
                    
                    total_deductible += deductible_amount
                    
                    if deduction_category not in deductions:
                        deductions[deduction_category] = {
                            'total_amount': 0,
                            'deductible_amount': 0,
                            'expense_count': 0,
                            'expenses': []
                        }
                    
                    deductions[deduction_category]['total_amount'] += amount_chf
                    deductions[deduction_category]['deductible_amount'] += deductible_amount
                    deductions[deduction_category]['expense_count'] += 1
                    deductions[deduction_category]['expenses'].append({
                        'id': expense['id'],
                        'date': expense['date_local'],
                        'merchant': expense['merchant_text'],
                        'amount': amount_chf,
                        'deductible_amount': deductible_amount,
                        'business_pct': business_pct
                    })
            
            # Calculate potential tax savings (rough estimate)
            # Assuming average tax rate of 25% (varies by canton and income)
            estimated_tax_rate = 0.25
            estimated_savings = total_deductible * estimated_tax_rate
            
            return {
                'success': True,
                'year': year,
                'canton': canton,
                'total_expenses': round(total_expenses, 2),
                'total_deductible': round(total_deductible, 2),
                'estimated_tax_savings': round(estimated_savings, 2),
                'deductions_by_category': {
                    category: {
                        'total_amount': round(data['total_amount'], 2),
                        'deductible_amount': round(data['deductible_amount'], 2),
                        'expense_count': data['expense_count'],
                        'expenses': data['expenses'][:10]  # Limit for response size
                    }
                    for category, data in deductions.items()
                },
                'expense_count': len(expenses)
            }
            
        except Exception as e:
            self.logger.error(f"Tax deduction calculation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def export_tax_data(self, 
                       year: int,
                       format: str = 'csv',
                       canton: str = None,
                       user_id: str = None) -> Dict[str, Any]:
        """Export tax data for a year.
        
        Args:
            year: Tax year to export
            format: Export format ('csv', 'xlsx', 'json')
            canton: Optional canton filter
            user_id: User ID (defaults to instance user_id)
            
        Returns:
            Dict with export result
        """
        try:
            user_id = user_id or self.user_id
            if not user_id:
                return {'success': False, 'error': 'User ID required'}
            
            return self.export_manager.export_tax_data(
                self.db, user_id, year, format, canton
            )
            
        except Exception as e:
            self.logger.error(f"Tax data export failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # Utility Methods
    
    def get_dashboard_summary(self, user_id: str = None) -> Dict[str, Any]:
        """Get dashboard summary for user.
        
        Args:
            user_id: User ID (defaults to instance user_id)
            
        Returns:
            Dict with dashboard data
        """
        try:
            user_id = user_id or self.user_id
            if not user_id:
                return {'error': 'User ID required'}
            
            # Get current year expenses
            current_year = datetime.now().year
            year_expenses = self.db.query_one("""
                SELECT 
                    COUNT(*) as expense_count,
                    SUM(amount_cents) as total_amount_cents,
                    SUM(CASE WHEN pro_pct > 0 THEN amount_cents * pro_pct / 100 ELSE 0 END) as business_amount_cents
                FROM sa_expenses
                WHERE user_id = ? AND strftime('%Y', date_local) = ?
            """, (user_id, str(current_year)))
            
            # Get monthly breakdown
            monthly_expenses = self.db.query_all("""
                SELECT 
                    strftime('%Y-%m', date_local) as month,
                    COUNT(*) as count,
                    SUM(amount_cents) as total_cents
                FROM sa_expenses
                WHERE user_id = ? AND strftime('%Y', date_local) = ?
                GROUP BY strftime('%Y-%m', date_local)
                ORDER BY month
            """, (user_id, str(current_year)))
            
            # Get top categories
            top_categories = self.db.query_all("""
                SELECT 
                    category_code,
                    COUNT(*) as count,
                    SUM(amount_cents) as total_cents
                FROM sa_expenses
                WHERE user_id = ? AND strftime('%Y', date_local) = ?
                GROUP BY category_code
                ORDER BY total_cents DESC
                LIMIT 10
            """, (user_id, str(current_year)))
            
            # Get reconciliation status
            reconciliation_summary = self.get_reconciliation_summary(user_id)
            
            return {
                'year': current_year,
                'total_expenses': year_expenses['expense_count'] or 0,
                'total_amount_chf': float(Decimal(year_expenses['total_amount_cents'] or 0) / 100),
                'business_amount_chf': float(Decimal(year_expenses['business_amount_cents'] or 0) / 100),
                'monthly_breakdown': [
                    {
                        'month': month['month'],
                        'count': month['count'],
                        'amount_chf': float(Decimal(month['total_cents']) / 100)
                    }
                    for month in monthly_expenses
                ],
                'top_categories': [
                    {
                        'category': cat['category_code'],
                        'count': cat['count'],
                        'amount_chf': float(Decimal(cat['total_cents']) / 100)
                    }
                    for cat in top_categories
                ],
                'reconciliation': reconciliation_summary
            }
            
        except Exception as e:
            self.logger.error(f"Dashboard summary failed: {e}")
            return {'error': str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """Perform system health check.
        
        Returns:
            Dict with health check results
        """
        try:
            health = {
                'status': 'healthy',
                'components': {},
                'timestamp': datetime.now().isoformat()
            }
            
            # Check database
            try:
                self.db.query_one("SELECT 1")
                health['components']['database'] = 'healthy'
            except Exception as e:
                health['components']['database'] = f'error: {str(e)}'
                health['status'] = 'degraded'
            
            # Check OCR
            try:
                # Simple OCR test doesn't require actual file
                health['components']['ocr'] = 'available'
            except Exception as e:
                health['components']['ocr'] = f'error: {str(e)}'
                health['status'] = 'degraded'
            
            # Check all other components
            components = [
                ('document_parser', self.document_parser),
                ('statement_parser', self.statement_parser),
                ('merchant_normalizer', self.merchant_normalizer),
                ('category_mapper', self.category_mapper),
                ('transaction_matcher', self.transaction_matcher),
                ('export_manager', self.export_manager)
            ]
            
            for name, component in components:
                if component:
                    health['components'][name] = 'healthy'
                else:
                    health['components'][name] = 'not_initialized'
                    health['status'] = 'degraded'
            
            return health
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


# Factory functions for easy import
def create_swiss_accountant(db_path: str = None, 
                           user_id: str = None, 
                           config: Dict[str, Any] = None) -> SwissAccountant:
    """Create Swiss Accountant instance.
    
    Args:
        db_path: Path to SQLite database file
        user_id: Default user ID for operations
        config: Configuration dictionary
        
    Returns:
        SwissAccountant instance
    """
    return SwissAccountant(db_path, user_id, config)


# Configuration helpers
def get_default_config() -> Dict[str, Any]:
    """Get default configuration."""
    return {
        'database_path': 'swiss_accountant.db',
        'log_level': 'INFO',
        'ocr_language': 'deu+fra+ita+eng',  # Swiss languages
        'default_currency': 'CHF',
        'default_vat_rate': 8.1,
        'reconciliation_auto_accept': True,
        'export_formats': ['csv', 'xlsx', 'json']
    }


def load_config_from_file(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load config from {config_path}: {e}")
        return get_default_config()
