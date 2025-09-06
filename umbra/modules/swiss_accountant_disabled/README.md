# Swiss Accountant

A comprehensive expense tracking and tax deduction optimization system specifically designed for Swiss tax requirements. This module provides automated receipt processing, bank statement reconciliation, and tax-compliant categorization with support for all Swiss cantons and federal regulations.

## Features

### 🧾 Document Processing
- **OCR-based receipt processing** with multi-language support (German, French, Italian, English)
- **Invoice and receipt parsing** with automatic field extraction
- **Bank statement import** supporting major Swiss banks (UBS, Credit Suisse, PostFinance, etc.)
- **Multiple format support** including CSV, XML, CAMT, PDF, and image formats

### 🏷️ Smart Categorization
- **Swiss-specific tax category mapping** with canton-specific rules
- **Automatic merchant normalization** with canonical naming
- **Business expense percentage tracking** for mixed-use expenses
- **VAT calculation and breakdown** with Swiss rates (8.1%, 3.8%, 2.6%)

### 🔄 Reconciliation Engine
- **Automatic expense-transaction matching** with configurable strategies
- **High-confidence auto-matching** with manual review for uncertain cases
- **Multiple matching algorithms** including amount, date, merchant, and reference matching
- **Reconciliation sessions** with detailed reporting

### 📊 Tax Optimization
- **Swiss federal and cantonal tax rules** with automatic validation
- **Deduction limit checking** and compliance warnings
- **Annual tax calculation** with potential savings estimation
- **Professional expense optimization** including commute, meals, and equipment

### 📤 Export & Reporting
- **Tax-ready exports** in CSV, Excel, and JSON formats
- **Canton-specific formatting** for tax preparation software
- **VAT reporting** for business expenses
- **Audit-ready documentation** with receipt linking

## Installation

```bash
# Install required dependencies
pip install pillow pytesseract openpyxl
```

For OCR functionality, you'll also need to install Tesseract:

**macOS:**
```bash
brew install tesseract tesseract-lang
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-deu tesseract-ocr-fra tesseract-ocr-ita
```

**Windows:**
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

## Quick Start

### Basic Usage

```python
from umbra.modules.swiss_accountant import quick_start

# Initialize with your user ID
sa = quick_start(user_id="john_doe")

# Process a receipt
result = sa.process_receipt("receipt.jpg")
print(f"Extracted amount: CHF {result['parsed_data']['total_amount']:.2f}")

# Import bank statement
result = sa.process_bank_statement("statement.csv", account_name="UBS Checking")
print(f"Imported {result['transaction_count']} transactions")
```

### Advanced Configuration

```python
from umbra.modules.swiss_accountant import create_swiss_accountant

config = {
    'log_level': 'DEBUG',
    'ocr_language': 'deu+fra+ita+eng',
    'default_vat_rate': 8.1,
    'reconciliation_auto_accept': True
}

sa = create_swiss_accountant(
    db_path="my_expenses.db",
    user_id="john_doe",
    config=config
)
```

## Command Line Interface

The module includes a comprehensive CLI for all operations:

```bash
# Process receipts
swiss-accountant process-receipt receipt.jpg --user-id john

# Import bank statements
swiss-accountant import-statement statement.csv --user-id john --account "UBS Checking"

# List expenses
swiss-accountant list-expenses --start-date 2024-01-01 --end-date 2024-12-31 --user-id john

# Reconcile expenses with transactions
swiss-accountant reconcile --start-date 2024-01-01 --end-date 2024-01-31 --user-id john

# Calculate tax deductions
swiss-accountant tax-calc --year 2024 --canton ZH --user-id john

# Export tax data
swiss-accountant export --year 2024 --format xlsx --user-id john

# View dashboard
swiss-accountant dashboard --user-id john
```

## Workflow Examples

### Complete Monthly Workflow

```python
from datetime import date, datetime
from umbra.modules.swiss_accountant import quick_start

# Initialize
sa = quick_start(user_id="john_doe")

# 1. Process receipts from the month
receipt_files = ["receipt1.jpg", "receipt2.pdf", "invoice1.png"]
for receipt in receipt_files:
    result = sa.process_receipt(receipt)
    if result['success']:
        print(f"✅ Processed {receipt}: CHF {result['parsed_data']['total_amount']:.2f}")

# 2. Import bank statements
statement_result = sa.process_bank_statement("january_statement.csv", account_name="UBS")
print(f"📋 Imported {statement_result['transaction_count']} transactions")

# 3. Reconcile expenses with transactions
reconcile_result = sa.reconcile_expenses(
    period_start=date(2024, 1, 1),
    period_end=date(2024, 1, 31)
)
print(f"🔄 Matched {reconcile_result['exact_matches']} expenses automatically")

# 4. Review unmatched items
pending_matches = sa.transaction_matcher.get_pending_matches("john_doe")
for match in pending_matches:
    print(f"⚠️  Review needed: {match['expense']['merchant']} - CHF {match['expense']['amount']:.2f}")

# 5. Update business percentages for mixed-use expenses
business_expenses = sa.get_expenses(category="professional_equipment")
for expense in business_expenses:
    if expense['amount_chf'] > 100:  # Large purchases
        sa.update_expense_category(
            expense['id'], 
            expense['category_code'], 
            business_percentage=80  # 80% business use
        )
```

### Annual Tax Preparation

```python
# Calculate deductions for the tax year
tax_result = sa.calculate_tax_deductions(year=2024, canton="ZH")

print(f"📊 Tax Summary for 2024:")
print(f"   Total expenses: CHF {tax_result['total_expenses']:,.2f}")
print(f"   Deductible amount: CHF {tax_result['total_deductible']:,.2f}")
print(f"   Estimated tax savings: CHF {tax_result['estimated_tax_savings']:,.2f}")

# Export for tax software
export_result = sa.export_tax_data(year=2024, format="xlsx", canton="ZH")
if export_result['success']:
    with open("tax_export_2024.xlsx", "wb") as f:
        f.write(export_result['content'])
    print(f"📤 Tax export saved: {export_result['record_count']} records")

# Generate VAT report for business expenses
vat_result = sa.export_manager.export_vat_data(
    sa.db, "john_doe", 
    period_start=date(2024, 1, 1),
    period_end=date(2024, 12, 31)
)
```

## Supported Banks and Formats

### Bank Statements
- **UBS**: CSV exports from e-banking
- **Credit Suisse**: CSV and CAMT formats
- **PostFinance**: CSV exports
- **Raiffeisen**: CSV and XML formats
- **Cantonal Banks**: Standard CSV formats
- **Revolut**: CSV transaction exports
- **Swisscard**: Credit card statements

### Receipt Formats
- **Images**: JPG, PNG, TIFF, BMP
- **PDFs**: Searchable and image-based PDFs
- **Languages**: German, French, Italian, English

## Swiss Tax Categories

The system automatically maps expenses to Swiss tax deduction categories:

### Federal Deductions
- **Professional Expenses** (Berufsauslagen)
- **Commuting Costs** (Fahrtkosten)
- **Work Meals** (Verpflegungskosten)
- **Professional Education** (Weiterbildung)
- **Pillar 3a Contributions** (Säule 3a)
- **Insurance Premiums** (Versicherungsprämien)
- **Childcare Costs** (Kinderbetreuung)
- **Medical Expenses** (Krankheitskosten)
- **Charitable Donations** (Spenden)

### Canton-Specific Rules
- Automatic limit checking per canton
- Special deductions (e.g., home office, Fahrkosten)
- Local tax optimization strategies

## Configuration

### Default Configuration
```python
config = {
    'database_path': 'swiss_accountant.db',
    'log_level': 'INFO',
    'ocr_language': 'deu+fra+ita+eng',
    'default_currency': 'CHF',
    'default_vat_rate': 8.1,
    'reconciliation_auto_accept': True,
    'export_formats': ['csv', 'xlsx', 'json']
}
```

### Canton-Specific Settings
```python
# For Zurich canton
zh_config = config.copy()
zh_config.update({
    'canton': 'ZH',
    'commute_limit': 3000,  # CHF
    'home_office_max': 1500,  # CHF
    'childcare_bonus': 2000  # CHF additional
})
```

## Data Privacy and Security

- **Local SQLite database** - no cloud storage
- **Encrypted file storage** options available
- **User-specific data isolation**
- **GDPR compliance** features
- **Swiss data residency** requirements met

## Error Handling

The system provides comprehensive error handling:

```python
result = sa.process_receipt("receipt.jpg")
if not result['success']:
    print(f"❌ Error: {result['error']}")
    if 'suggestions' in result:
        print("💡 Suggestions:")
        for suggestion in result['suggestions']:
            print(f"   - {suggestion}")
```

## Performance and Limits

- **OCR Processing**: ~2-5 seconds per receipt
- **Statement Import**: ~1000 transactions per second
- **Reconciliation**: ~10,000 comparisons per second
- **Database Size**: Optimized for 100k+ transactions
- **Memory Usage**: ~50MB typical working set

## Troubleshooting

### Common Issues

**OCR not working:**
```bash
# Check Tesseract installation
tesseract --version

# Test OCR manually
tesseract receipt.jpg output -l deu+fra+ita+eng
```

**Database locked:**
```python
# Check database file permissions
import os
os.access('swiss_accountant.db', os.W_OK)

# Use backup/restore if needed
sa.db.backup_database('backup.db')
```

**Import failures:**
```python
# Check file format
result = sa.statement_parser.detect_statement_format(content, filename)
print(f"Detected format: {result['format']}")

# Manual format specification
result = sa.statement_parser.parse_statement(content, StatementFormat.CSV_UBS)
```

## Contributing

This module is part of the UMBRA system. For contributions:

1. Follow Swiss tax law requirements
2. Support all official languages
3. Maintain backward compatibility
4. Include comprehensive tests
5. Document canton-specific features

## License

MIT License - See main UMBRA project for details.

## Support

- **Documentation**: Built-in help system
- **Examples**: Comprehensive example code
- **CLI Help**: `swiss-accountant --help`
- **Health Check**: `swiss-accountant health`

## Version History

- **v1.0.0**: Initial release with full Swiss compliance
- Multi-language OCR support
- All major Swiss banks supported
- Complete tax category mapping
- Export functionality for tax software
