# Swiss Accountant Troubleshooting Guide

This guide helps you diagnose and resolve common issues with Swiss Accountant.

## Installation Issues

### 1. Python Dependencies

**Problem:** `ImportError: No module named 'PIL'`
```bash
# Solution: Install required packages
pip install Pillow>=9.0.0 pytesseract>=0.3.8 openpyxl>=3.0.9
```

**Problem:** `ModuleNotFoundError: No module named 'umbra'`
```python
# Solution: Add to Python path or install module
import sys
sys.path.insert(0, '/path/to/UMBRA')
```

### 2. Tesseract OCR Issues

**Problem:** `TesseractNotFoundError`
```bash
# macOS
brew install tesseract tesseract-lang

# Ubuntu/Debian  
sudo apt-get install tesseract-ocr tesseract-ocr-deu tesseract-ocr-fra tesseract-ocr-ita

# Windows
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
```

**Problem:** OCR returns gibberish or empty text
```python
# Check language packs
tesseract --list-langs

# Test OCR manually
tesseract image.jpg output -l deu+fra+ita+eng

# Solution: Install missing language packs
```

### 3. Database Issues

**Problem:** `sqlite3.OperationalError: database is locked`
```python
# Solution: Check for other connections
import sqlite3
conn = sqlite3.connect('swiss_accountant.db')
conn.close()

# Or restart the application
```

**Problem:** Database corruption
```python
# Check integrity
from umbra.modules.swiss_accountant.utils import MaintenanceManager
maintenance = MaintenanceManager('swiss_accountant.db')
result = maintenance.validate_data_integrity()

# Restore from backup if corrupted
from umbra.modules.swiss_accountant.utils import BackupManager
backup = BackupManager('swiss_accountant.db')
backup.restore_backup('backup_file.sql.gz')
```

## OCR and Document Processing

### 1. Poor OCR Accuracy

**Symptoms:**
- Incorrect amounts extracted
- Wrong merchant names
- Missing text

**Solutions:**
```python
# 1. Check image quality
# - Ensure good lighting
# - Avoid shadows and glare
# - Use high resolution (300+ DPI)

# 2. Preprocess images
from PIL import Image, ImageEnhance
img = Image.open('receipt.jpg')
# Increase contrast
enhancer = ImageEnhance.Contrast(img)
img = enhancer.enhance(2.0)
# Convert to grayscale
img = img.convert('L')
img.save('receipt_processed.jpg')

# 3. Try different OCR languages
sa.ocr.extract_text_from_image('receipt.jpg', languages='deu')  # German only
sa.ocr.extract_text_from_image('receipt.jpg', languages='fra')  # French only
```

### 2. Document Type Detection Fails

**Problem:** Documents classified as wrong type
```python
# Manual override
result = sa.document_parser.parse_receipt(ocr_text)  # Force receipt parsing
result = sa.document_parser.parse_invoice(ocr_text)  # Force invoice parsing

# Check detection confidence
detection = sa.document_parser.detect_document_type(ocr_text, filename)
print(f"Confidence: {detection['confidence']}")
print(f"Matches: {detection['matches']}")
```

### 3. Amount Extraction Issues

**Problem:** Wrong amounts detected
```python
# Debug amount extraction
common_fields = sa.document_parser.extract_common_fields(ocr_text)
print("Detected amounts:", common_fields['amounts'])

# Manual verification
import re
amounts = re.findall(r'([0-9]{1,6}[.,]\d{2})', ocr_text)
print("Raw amounts found:", amounts)
```

## Bank Statement Processing

### 1. Statement Format Not Recognized

**Problem:** `Unknown statement format`
```python
# Check format detection
detection = sa.statement_parser.detect_statement_format(content, filename)
print(f"Detected format: {detection['format']}")
print(f"Confidence: {detection['confidence']}")

# Manual format specification
from umbra.modules.swiss_accountant.ingest.statements import StatementFormat
result = sa.statement_parser.parse_statement(content, StatementFormat.CSV_UBS)
```

### 2. CSV Parsing Errors

**Problem:** Incorrect column mapping
```python
# Check CSV structure
import csv
with open('statement.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f, delimiter=';')  # Try different delimiters: ';', ',', '\t'
    header = next(reader)
    print("CSV Header:", header)
    
    # Check first few rows
    for i, row in enumerate(reader):
        if i < 3:
            print(f"Row {i+1}:", row)
```

### 3. Transaction Import Failures

**Problem:** No transactions imported
```python
# Debug step by step
content = open('statement.csv', 'r', encoding='utf-8').read()
print("Content preview:", content[:500])

# Try different encodings
encodings = ['utf-8', 'latin1', 'cp1252']
for encoding in encodings:
    try:
        with open('statement.csv', 'r', encoding=encoding) as f:
            content = f.read()
        print(f"Successfully read with {encoding}")
        break
    except UnicodeDecodeError:
        continue
```

## Reconciliation Issues

### 1. Low Match Rate

**Problem:** Few expenses match transactions
```python
# Check match criteria
reconcile_result = sa.reconcile_expenses(
    period_start=date(2024, 1, 1),
    period_end=date(2024, 1, 31),
    auto_accept=False  # Review all matches manually
)

# Adjust matching strategy
from umbra.modules.swiss_accountant.reconcile.matcher import MatchStrategy
reconcile_result = sa.transaction_matcher.reconcile_period(
    period_start=date(2024, 1, 1),
    period_end=date(2024, 1, 31),
    user_id="your_user_id",
    strategy=MatchStrategy.AMOUNT_DATE_ONLY,  # More lenient matching
    auto_accept=False
)
```

### 2. False Positive Matches

**Problem:** Wrong expenses matched to transactions
```python
# Review pending matches
pending = sa.transaction_matcher.get_pending_matches("user_id")
for match in pending:
    print(f"Expense: {match['expense']['merchant']} - CHF {match['expense']['amount']}")
    print(f"Transaction: {match['transaction']['counterparty']} - CHF {match['transaction']['amount']}")
    print(f"Confidence: {match['confidence']}")
    
    # Reject incorrect matches
    sa.transaction_matcher.reject_match(match['match_id'], "user_id")
```

### 3. Missing Transactions

**Problem:** Bank transactions not imported
```python
# Check statement processing
statements = sa.db.query_all("SELECT * FROM sa_statements WHERE user_id = ?", ("user_id",))
for stmt in statements:
    print(f"Statement: {stmt['file_name']} - {stmt['total_transactions']} transactions")

# Check transaction date ranges
transactions = sa.db.query_all("""
    SELECT MIN(booking_date) as earliest, MAX(booking_date) as latest, COUNT(*) as count
    FROM sa_transactions t
    JOIN sa_statements s ON t.statement_id = s.id
    WHERE s.user_id = ?
""", ("user_id",))
print("Transaction date range:", transactions[0] if transactions else "No transactions")
```

## Tax Calculation Issues

### 1. Incorrect Deduction Categories

**Problem:** Expenses categorized wrongly
```python
# Review category mappings
mappings = sa.category_mapper.get_category_statistics()
print("Category mappings:", mappings)

# Update incorrect categories
sa.update_expense_category(
    expense_id=123,
    category_code='commute_public_transport',
    business_percentage=100
)

# Add custom mapping
sa.category_mapper.add_custom_mapping(
    expense_category='train_tickets',
    deduction_category='commute_public_transport',
    confidence=1.0
)
```

### 2. Business Percentage Issues

**Problem:** Wrong business use percentages
```python
# Review business expenses
business_expenses = sa.get_expenses(limit=100)
for expense in business_expenses:
    if expense['pro_pct'] > 0:
        print(f"{expense['merchant_text']}: {expense['pro_pct']}% business")

# Update business percentages
sa.update_expense_category(
    expense_id=123,
    category_code=expense['category_code'],
    business_percentage=80  # 80% business use
)
```

### 3. Deduction Limits Exceeded

**Problem:** Deductions exceed Swiss limits
```python
# Check tax calculation details
tax_result = sa.calculate_tax_deductions(year=2024, canton="ZH")
for category, data in tax_result['deductions_by_category'].items():
    print(f"{category}: CHF {data['deductible_amount']:.2f}")

# Review limit warnings
if 'notes' in tax_result:
    for note in tax_result['notes']:
        print(f"Warning: {note}")
```

## Performance Issues

### 1. Slow Database Operations

**Problem:** Queries take too long
```python
# Analyze database performance
from umbra.modules.swiss_accountant.utils import MaintenanceManager
maintenance = MaintenanceManager('swiss_accountant.db')

# Check for missing indexes
analysis = maintenance.analyze_database()
performance = analysis['analysis']['performance_metrics']
if performance['missing_indexes']:
    print("Missing indexes:", performance['missing_indexes'])

# Optimize database
maintenance.optimize_database(['vacuum', 'analyze', 'reindex', 'create_indexes'])
```

### 2. Large Database Size

**Problem:** Database file growing too large
```python
# Analyze storage usage
analysis = maintenance.analyze_database()
storage = analysis['analysis']['storage_analysis']
print(f"Unused space: {storage['unused_mb']:.1f} MB")

# Clean old data (dry run first)
cleanup = maintenance.clean_old_data(days_old=365, dry_run=True)
print("Items to clean:", cleanup['items_to_clean'])

# Actually clean (if satisfied with dry run)
cleanup = maintenance.clean_old_data(days_old=365, dry_run=False)
```

### 3. Memory Usage

**Problem:** High memory consumption
```python
# Process files in batches
import os
receipt_files = [f for f in os.listdir('.') if f.endswith('.jpg')]

# Process in batches of 10
batch_size = 10
for i in range(0, len(receipt_files), batch_size):
    batch = receipt_files[i:i+batch_size]
    for receipt_file in batch:
        result = sa.process_receipt(receipt_file)
        print(f"Processed: {receipt_file}")
    
    # Optional: Force garbage collection
    import gc
    gc.collect()
```

## Data Export Issues

### 1. Export Format Problems

**Problem:** Excel export fails
```python
# Check if openpyxl is installed
try:
    import openpyxl
    print("openpyxl available")
except ImportError:
    print("Install openpyxl: pip install openpyxl>=3.0.9")

# Fallback to CSV
export_result = sa.export_tax_data(year=2024, format='csv')
```

### 2. Missing Data in Export

**Problem:** Export missing some expenses
```python
# Check export filters
export_summary = sa.export_manager.get_export_summary(sa.db, "user_id")
print(f"Available expenses: {export_summary['total_expenses']}")
print(f"Date range: {export_summary['earliest_date']} to {export_summary['latest_date']}")

# Export specific year/canton
export_result = sa.export_tax_data(
    year=2024,
    format='xlsx',
    canton='ZH'  # Specific canton only
)
```

## Diagnostic Commands

### Health Check
```python
# Comprehensive system check
health = sa.health_check()
print("System status:", health['status'])
for component, status in health['components'].items():
    print(f"  {component}: {status}")
```

### Database Analysis
```python
# Full database analysis
from umbra.modules.swiss_accountant.utils import MaintenanceManager
maintenance = MaintenanceManager('swiss_accountant.db')
analysis = maintenance.analyze_database()

if analysis['success']:
    print("Database size:", analysis['analysis']['database_info']['size_mb'], "MB")
    print("Data quality issues:", len(analysis['analysis']['data_quality']['issues']))
    for rec in analysis['analysis']['recommendations']:
        print(f"Recommendation: {rec['description']}")
```

### Data Validation
```python
# Check data integrity
validation = maintenance.validate_data_integrity()
print(f"Integrity score: {validation['summary']['integrity_score']}%")
for issue in validation['issues_found']:
    print(f"Issue: {issue['type']} - {issue.get('count', 'Multiple')}")
```

## Getting Help

### Log Files
Check the log file for detailed error information:
```bash
tail -f swiss_accountant.log
```

### Debug Mode
Enable debug logging:
```python
config = get_default_config()
config['log_level'] = 'DEBUG'
sa = create_swiss_accountant(config=config)
```

### Test Installation
```bash
python test_swiss_accountant.py
```

### Contact Support
If issues persist:
1. Check the GitHub issues page
2. Create a minimal reproducible example
3. Include error messages and log files
4. Specify your environment (OS, Python version, etc.)

## Common Error Messages

### `sqlite3.IntegrityError: FOREIGN KEY constraint failed`
**Cause:** Trying to reference non-existent record
**Solution:** Check data consistency, run validation

### `TesseractError: (1, 'Error opening data file')`
**Cause:** Tesseract language pack missing
**Solution:** Install required language packs

### `UnicodeDecodeError: 'utf-8' codec can't decode`
**Cause:** File encoding mismatch
**Solution:** Try different encodings (latin1, cp1252)

### `PermissionError: [Errno 13] Permission denied`
**Cause:** Insufficient file permissions
**Solution:** Check file/directory permissions

### `ValueError: Invalid Swiss VAT number format`
**Cause:** VAT number doesn't match CHE-XXX.XXX.XXX format
**Solution:** Verify VAT number format

## Performance Optimization Tips

1. **Regular Maintenance:**
   ```bash
   python utils/maintenance.py -d swiss_accountant.db optimize
   ```

2. **Batch Processing:**
   - Process receipts in small batches
   - Import statements separately from reconciliation

3. **Database Optimization:**
   - Regular VACUUM operations
   - Create appropriate indexes
   - Clean old data periodically

4. **Memory Management:**
   - Close database connections properly
   - Process large files in chunks
   - Use generators for large datasets

5. **OCR Optimization:**
   - Preprocess images for better quality
   - Use appropriate language combinations
   - Cache OCR results when possible
