"""
Swiss Accountant - Tax-compliant expense tracking for Switzerland

This module provides comprehensive expense tracking and tax deduction optimization
specifically designed for Swiss tax requirements, supporting multiple cantons
and federal regulations.

Key Features:
- OCR-based receipt processing
- Bank/card statement import and reconciliation
- Swiss-specific merchant normalization
- Tax deduction category mapping
- Canton-specific rules and limits
- Export for tax preparation
- Multi-language support (German, French, Italian, English)

Main Classes:
- SwissAccountant: Main orchestrator class
- DatabaseManager: SQLite database operations
- OCRProcessor: Text extraction from receipts
- DocumentParser: Receipt/invoice parsing
- StatementParser: Bank statement processing
- MerchantNormalizer: Canonical merchant names
- CategoryMapper: Tax deduction mapping
- ExpenseTransactionMatcher: Reconciliation engine
- ExportManager: Data export functionality

Usage:
    from umbra.modules.swiss_accountant import create_swiss_accountant
    
    # Initialize
    sa = create_swiss_accountant(user_id="john", db_path="expenses.db")
    
    # Process receipt
    result = sa.process_receipt("receipt.jpg")
    
    # Import bank statement
    result = sa.process_bank_statement("statement.csv")
    
    # Reconcile expenses
    result = sa.reconcile_expenses(start_date, end_date)
    
    # Calculate tax deductions
    result = sa.calculate_tax_deductions(year=2024, canton="ZH")
    
    # Export tax data
    result = sa.export_tax_data(year=2024, format="xlsx")
"""

__version__ = "1.0.0"
__author__ = "Swiss Accountant Development Team"
__license__ = "MIT"

# Main exports - Temporarily disabled due to missing implementation files
# from .main import (
#     SwissAccountant,
#     create_swiss_accountant,
#     get_default_config,
#     load_config_from_file
# )

# Database
from .database.manager import (
    DatabaseManager,
    create_database_manager
)

# Document processing
from .ingest.ocr import (
    OCRProcessor,
    create_ocr_processor
)

from .ingest.parsers import (
    DocumentParser,
    DocumentType,
    create_document_parser
)

from .ingest.statements import (
    StatementParser,
    StatementFormat,
    create_statement_parser
)

# Normalization
from .normalize.merchants import (
    MerchantNormalizer,
    create_merchant_normalizer
)

from .normalize.categories import (
    CategoryMapper,
    DeductionCategory,
    create_category_mapper
)

# Reconciliation
from .reconcile.matcher import (
    ExpenseTransactionMatcher,
    MatchType,
    MatchStrategy,
    create_expense_transaction_matcher
)

# Export
from .exports.csv_excel import (
    ExportManager,
    ExportFormat,
    create_export_manager
)

# CLI
from .cli import SwissAccountantCLI

# All available classes and functions
__all__ = [
    # Main
    'SwissAccountant',
    'create_swiss_accountant',
    'get_default_config',
    'load_config_from_file',
    
    # Database
    'DatabaseManager',
    'create_database_manager',
    
    # Document processing
    'OCRProcessor',
    'create_ocr_processor',
    'DocumentParser',
    'DocumentType',
    'create_document_parser',
    'StatementParser',
    'StatementFormat',
    'create_statement_parser',
    
    # Normalization
    'MerchantNormalizer',
    'create_merchant_normalizer',
    'CategoryMapper',
    'DeductionCategory',
    'create_category_mapper',
    
    # Reconciliation
    'ExpenseTransactionMatcher',
    'MatchType',
    'MatchStrategy',
    'create_expense_transaction_matcher',
    
    # Export
    'ExportManager',
    'ExportFormat',
    'create_export_manager',
    
    # CLI
    'SwissAccountantCLI'
]

# Version info
VERSION_INFO = {
    'major': 1,
    'minor': 0,
    'patch': 0,
    'release': 'stable'
}

# Configuration constants
DEFAULT_CONFIG = {
    'database_path': 'swiss_accountant.db',
    'log_level': 'INFO',
    'ocr_language': 'deu+fra+ita+eng',
    'default_currency': 'CHF',
    'default_vat_rate': 8.1,
    'reconciliation_auto_accept': True,
    'export_formats': ['csv', 'xlsx', 'json'],
    'supported_cantons': [
        'AG', 'AI', 'AR', 'BE', 'BL', 'BS', 'FR', 'GE', 'GL', 'GR',
        'JU', 'LU', 'NE', 'NW', 'OW', 'SG', 'SH', 'SO', 'SZ', 'TG',
        'TI', 'UR', 'VD', 'VS', 'ZG', 'ZH'
    ]
}

# Supported file formats
SUPPORTED_RECEIPT_FORMATS = ['.jpg', '.jpeg', '.png', '.pdf', '.tiff', '.bmp']
SUPPORTED_STATEMENT_FORMATS = ['.csv', '.xml', '.camt', '.mt940']

# Swiss-specific constants
SWISS_VAT_RATES = [0.0, 2.6, 3.8, 8.1]  # Standard Swiss VAT rates
SWISS_LANGUAGES = ['deu', 'fra', 'ita', 'eng']  # German, French, Italian, English

def get_version() -> str:
    """Get version string."""
    return __version__

def get_supported_formats() -> dict:
    """Get supported file formats."""
    return {
        'receipts': SUPPORTED_RECEIPT_FORMATS,
        'statements': SUPPORTED_STATEMENT_FORMATS
    }

def get_swiss_info() -> dict:
    """Get Swiss-specific information."""
    return {
        'vat_rates': SWISS_VAT_RATES,
        'languages': SWISS_LANGUAGES,
        'cantons': DEFAULT_CONFIG['supported_cantons']
    }

# Quick start function
def quick_start(user_id: str, db_path: str = None) -> SwissAccountant:
    """Quick start with default configuration.
    
    Args:
        user_id: User identifier
        db_path: Optional database path
        
    Returns:
        Configured SwissAccountant instance
    """
    return create_swiss_accountant(
        db_path=db_path,
        user_id=user_id,
        config=get_default_config()
    )

# Example usage
def example_usage():
    """Show example usage."""
    example_code = '''
# Basic usage example
from umbra.modules.swiss_accountant import quick_start

# Initialize
sa = quick_start(user_id="john_doe")

# Process receipt
result = sa.process_receipt("path/to/receipt.jpg")
print(f"Processed expense: CHF {result['parsed_data']['total_amount']:.2f}")

# Import bank statement
result = sa.process_bank_statement("path/to/statement.csv", account_name="UBS Checking")
print(f"Imported {result['transaction_count']} transactions")

# Reconcile for January 2024
from datetime import date
result = sa.reconcile_expenses(
    period_start=date(2024, 1, 1),
    period_end=date(2024, 1, 31)
)
print(f"Found {result['exact_matches']} exact matches")

# Calculate tax deductions
result = sa.calculate_tax_deductions(year=2024, canton="ZH")
print(f"Potential deductions: CHF {result['total_deductible']:.2f}")

# Export for tax preparation
result = sa.export_tax_data(year=2024, format="xlsx")
with open("tax_export_2024.xlsx", "wb") as f:
    f.write(result['content'])
'''
    return example_code

# Module initialization
def _initialize_module():
    """Initialize module with Swiss-specific settings."""
    import logging
    
    # Setup module logger
    logger = logging.getLogger(__name__)
    logger.info(f"Swiss Accountant v{__version__} initialized")
    
    # Log supported features
    logger.debug(f"Supported receipt formats: {SUPPORTED_RECEIPT_FORMATS}")
    logger.debug(f"Supported statement formats: {SUPPORTED_STATEMENT_FORMATS}")
    logger.debug(f"Swiss VAT rates: {SWISS_VAT_RATES}")
    logger.debug(f"Supported cantons: {len(DEFAULT_CONFIG['supported_cantons'])}")

# Initialize on import
_initialize_module()
