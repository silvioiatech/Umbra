# Contributing to Swiss Accountant

Thank you for your interest in contributing to Swiss Accountant! This guide will help you get started with contributing to this Swiss tax-compliant expense tracking system.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Environment](#development-environment)
- [Contributing Guidelines](#contributing-guidelines)
- [Testing](#testing)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)
- [Swiss Tax Compliance](#swiss-tax-compliance)

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you are expected to uphold this code.

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git for version control
- Tesseract OCR with Swiss language packs
- Basic understanding of Swiss tax regulations (helpful but not required)

### Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/UMBRA.git
   cd UMBRA/umbra/modules/swiss_accountant
   ```

2. **Set up development environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Development dependencies
   ```

3. **Install Tesseract OCR:**
   ```bash
   # macOS
   brew install tesseract tesseract-lang
   
   # Ubuntu/Debian
   sudo apt-get install tesseract-ocr tesseract-ocr-deu tesseract-ocr-fra tesseract-ocr-ita
   ```

4. **Run setup script:**
   ```bash
   python setup.py
   ```

5. **Verify installation:**
   ```bash
   python test_swiss_accountant.py
   ```

## Development Environment

### Project Structure

```
swiss_accountant/
├── __init__.py              # Main module exports
├── main.py                  # Core orchestrator class
├── cli.py                   # Command line interface
├── config.json              # Default configuration
├── database/                # Database management
│   ├── manager.py           # Database operations
│   └── schema.py            # Table definitions
├── ingest/                  # Document processing
│   ├── ocr.py               # OCR text extraction
│   ├── parsers.py           # Receipt/invoice parsing
│   └── statements.py        # Bank statement processing
├── normalize/               # Data normalization
│   ├── merchants.py         # Merchant name normalization
│   └── categories.py        # Tax category mapping
├── reconcile/               # Transaction matching
│   └── matcher.py           # Expense-transaction reconciliation
├── exports/                 # Data export functionality
│   └── csv_excel.py         # CSV and Excel exports
├── utils/                   # Utility functions
│   ├── backup.py            # Database backup/restore
│   └── maintenance.py       # Database maintenance
├── examples/                # Usage examples
│   ├── complete_workflow.py
│   ├── receipt_processing.py
│   ├── bank_reconciliation.py
│   └── tax_optimization.py
└── tests/                   # Test suite (to be created)
```

### Code Style

We follow Python PEP 8 style guidelines with some modifications:

- **Line length:** 100 characters maximum
- **Imports:** Group in order: standard library, third-party, local imports
- **Type hints:** Use type annotations for all public functions
- **Docstrings:** Google-style docstrings for all classes and functions
- **Comments:** Swiss tax rule references should include official sources

### Code Formatting

```bash
# Install development tools
pip install black flake8 mypy

# Format code
black --line-length 100 .

# Check style
flake8 --max-line-length 100

# Type checking
mypy .
```

## Contributing Guidelines

### What We're Looking For

**High Priority:**
- Swiss canton-specific tax rule implementations
- Additional bank statement format support
- OCR accuracy improvements for Swiss receipts
- Performance optimizations for large datasets
- Mobile receipt capture integration

**Medium Priority:**
- Additional export formats (e.g., TurboTax, WinBiz)
- Machine learning for better categorization
- UI/UX improvements for CLI
- API endpoint development
- Multi-language documentation

**Low Priority:**
- Support for non-Swiss tax systems
- Cloud storage integrations
- Advanced analytics features

### Swiss Tax Compliance

When contributing tax-related features:

1. **Reference Official Sources:**
   - Include links to official Swiss tax documentation
   - Reference specific articles in tax codes
   - Note canton-specific variations

2. **Validation Required:**
   - All tax calculations must be validated against official examples
   - Include test cases with known correct results
   - Document assumptions and limitations

3. **Canton Support:**
   - Consider impact on all 26 Swiss cantons
   - Test with various cantonal rules
   - Provide fallback to federal rules

### Code Examples

**Good Example - Tax Rule Implementation:**
```python
def calculate_commute_deduction(self, amount: Decimal, canton: str, year: int) -> Dict[str, Any]:
    """Calculate commuting cost deduction following Swiss tax rules.
    
    Args:
        amount: Annual commuting costs in CHF
        canton: Swiss canton code (e.g., 'ZH', 'GE')
        year: Tax year
        
    Returns:
        Dict with deduction amount and applicable rules
        
    References:
        - Federal Tax Law Art. 26 (professional expenses)
        - Circular No. 36 (commuting cost calculation)
        - Canton-specific supplements where applicable
    """
    federal_limit = self._get_federal_commute_limit(year)  # CHF 3000 for 2024
    canton_bonus = self._get_canton_commute_bonus(canton, year)
    
    max_deductible = federal_limit + canton_bonus
    deductible_amount = min(amount, max_deductible)
    
    return {
        'deductible_amount': deductible_amount,
        'federal_limit': federal_limit,
        'canton_bonus': canton_bonus,
        'applicable_rules': [f'Federal Art. 26', f'Canton {canton} supplement'],
        'warnings': self._generate_warnings(amount, max_deductible)
    }
```

**Bad Example:**
```python
def calc_deduction(amount, canton):  # Missing type hints and docstring
    return min(amount, 3000)  # Hard-coded limit, no documentation
```

### Bank Format Support

When adding new bank statement formats:

1. **Create Format Parser:**
   ```python
   def _parse_new_bank_csv(self, csv_content: str) -> Dict[str, Any]:
       """Parse NewBank-specific CSV format."""
       # Implementation with proper error handling
   ```

2. **Add Detection Patterns:**
   ```python
   self.csv_patterns[StatementFormat.CSV_NEWBANK] = [
       r'NewBank specific header pattern',
       r'Alternative pattern for detection'
   ]
   ```

3. **Include Test Data:**
   - Provide anonymized sample statements
   - Include edge cases and error conditions
   - Test with various date formats and currencies

4. **Update Documentation:**
   - Add bank to supported formats list
   - Include setup instructions
   - Document any limitations

## Testing

### Test Structure

```bash
tests/
├── unit/                    # Unit tests for individual components
│   ├── test_database.py
│   ├── test_ocr.py
│   ├── test_parsers.py
│   └── test_categories.py
├── integration/             # Integration tests for workflows
│   ├── test_receipt_workflow.py
│   ├── test_reconciliation.py
│   └── test_export.py
├── fixtures/                # Test data and sample files
│   ├── receipts/
│   ├── statements/
│   └── expected_results/
└── conftest.py              # Pytest configuration
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=swiss_accountant --cov-report=html

# Run specific test categories
pytest tests/unit/
pytest tests/integration/

# Run tests for specific functionality
pytest -k "test_ocr"
pytest -k "test_tax_calculation"
```

### Writing Tests

**Unit Test Example:**
```python
import pytest
from decimal import Decimal
from swiss_accountant.normalize.categories import CategoryMapper

class TestCategoryMapper:
    def test_map_grocery_expense(self):
        """Test grocery expense mapping to non-deductible category."""
        mapper = CategoryMapper(mock_db)
        
        result = mapper.map_expense_to_deduction_category(
            expense_category='groceries',
            merchant_name='Migros Zurich',
            amount=Decimal('45.80'),
            date=date(2024, 1, 15)
        )
        
        assert result['success'] is True
        assert result['deduction_category'] == 'non_deductible'
        assert result['confidence'] > 0.9

    def test_commute_expense_within_limits(self):
        """Test commuting expense within federal limits."""
        # Test implementation
```

**Integration Test Example:**
```python
def test_complete_receipt_workflow(temp_database):
    """Test complete receipt processing workflow."""
    sa = create_swiss_accountant(db_path=temp_database, user_id="test_user")
    
    # Process receipt
    result = sa.process_receipt("tests/fixtures/receipts/migros_receipt.jpg")
    
    assert result['success'] is True
    assert result['expense_id'] is not None
    
    # Verify database storage
    expense = sa.get_expenses(limit=1)[0]
    assert expense['merchant_text'] is not None
    assert expense['amount_chf'] > 0
```

### Test Data

When contributing test data:

1. **Anonymize Real Data:**
   - Remove personal information
   - Use fictional names and addresses
   - Replace real account numbers

2. **Provide Edge Cases:**
   - Unusual receipt layouts
   - Multiple languages on same document
   - Damaged or low-quality images
   - Various date and number formats

3. **Include Expected Results:**
   - Provide expected OCR output
   - Include correct parsed amounts and dates
   - Specify expected tax categories

## Documentation

### Documentation Standards

1. **API Documentation:**
   - Google-style docstrings for all public methods
   - Include parameter types and return values
   - Provide usage examples

2. **Swiss Tax References:**
   - Link to official tax documentation
   - Include article numbers and section references
   - Note year-specific changes

3. **Examples:**
   - Complete working examples
   - Step-by-step explanations
   - Error handling demonstrations

### Documentation Tools

```bash
# Generate API documentation
pip install sphinx sphinx-autodoc-typehints
sphinx-apidoc -o docs/ swiss_accountant/
cd docs && make html

# Check documentation links
linkchecker docs/_build/html/index.html
```

## Submitting Changes

### Pull Request Process

1. **Create Feature Branch:**
   ```bash
   git checkout -b feature/add-new-bank-support
   ```

2. **Make Changes:**
   - Follow coding standards
   - Add comprehensive tests
   - Update documentation

3. **Test Thoroughly:**
   ```bash
   pytest
   python test_swiss_accountant.py
   black --check .
   flake8
   ```

4. **Commit with Clear Messages:**
   ```bash
   git commit -m "feat: Add support for NewBank CSV format
   
   - Implement CSV parser for NewBank statement format
   - Add detection patterns for automatic format recognition
   - Include test cases with sample data
   - Update documentation with setup instructions
   
   Resolves #123"
   ```

5. **Submit Pull Request:**
   - Use the pull request template
   - Include detailed description
   - Reference related issues
   - Add screenshots for UI changes

### Pull Request Template

```markdown
## Description
Brief description of changes and motivation.

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to change)
- [ ] Documentation update
- [ ] Swiss tax rule update

## Swiss Tax Compliance
- [ ] Changes reviewed against official Swiss tax documentation
- [ ] Tested with multiple cantons (if applicable)
- [ ] Validation against known correct calculations
- [ ] Official sources referenced in code/documentation

## Testing
- [ ] Unit tests added/updated and passing
- [ ] Integration tests added/updated and passing
- [ ] Manual testing completed
- [ ] Performance impact assessed

## Documentation
- [ ] Code documentation updated
- [ ] User documentation updated
- [ ] Examples provided for new features
- [ ] CHANGELOG.md updated

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] No unnecessary debug code or console.log statements
```

### Review Process

1. **Automated Checks:**
   - Code style validation
   - Test suite execution
   - Documentation building
   - Type checking

2. **Peer Review:**
   - Code quality assessment
   - Swiss tax compliance verification
   - Test coverage evaluation
   - Documentation completeness

3. **Maintainer Review:**
   - Architecture alignment
   - Performance considerations
   - Security implications
   - Breaking change assessment

## Swiss Tax Expertise

### Learning Resources

If you're new to Swiss tax regulations:

1. **Official Sources:**
   - [Federal Tax Administration (FTA)](https://www.estv.admin.ch/)
   - [Canton tax authorities](https://www.estv.admin.ch/estv/en/home/allgemein/steuerbehoerden-schweiz.html)
   - [Tax law documentation](https://www.fedlex.admin.ch/)

2. **Professional Development:**
   - Swiss tax preparation software documentation
   - Accounting professional guidelines
   - Tax advisor best practices

3. **Community Resources:**
   - Swiss accounting forums
   - Professional associations
   - University tax law courses

### Contributing Without Tax Expertise

You can still contribute valuable improvements:

- **Technical Enhancements:** Performance, code quality, testing
- **User Experience:** CLI improvements, documentation, examples  
- **Integration:** Bank formats, export formats, OCR accuracy
- **Infrastructure:** Database optimization, backup tools, monitoring

## Questions and Support

### Getting Help

- **Technical Questions:** Open a GitHub issue with the `question` label
- **Tax Rule Clarifications:** Consult official Swiss tax documentation first
- **Development Setup:** Check the troubleshooting guide
- **Feature Requests:** Open a GitHub issue with the `enhancement` label

### Communication Channels

- **GitHub Issues:** Bug reports and feature requests
- **GitHub Discussions:** General questions and community support
- **Code Review:** Comments on pull requests
- **Documentation:** Updates via pull requests

## Recognition

Contributors will be recognized in:
- README.md contributors section
- CHANGELOG.md for significant contributions
- Release notes for major features
- Annual contributor recognition

Thank you for contributing to Swiss Accountant! Your efforts help Swiss residents and businesses manage their finances more effectively while staying compliant with tax regulations.
