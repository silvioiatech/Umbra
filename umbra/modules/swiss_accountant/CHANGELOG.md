# Swiss Accountant Changelog

All notable changes to the Swiss Accountant module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-01

### Added
- **Initial Release** - Complete Swiss tax-compliant expense tracking system
- **OCR Processing** - Automatic text extraction from receipts and invoices
  - Multi-language support (German, French, Italian, English)
  - Support for PDF and image formats (JPG, PNG, TIFF, BMP)
  - Confidence scoring and quality assessment
- **Document Parsing** - Intelligent field extraction from receipts and invoices
  - Automatic merchant name detection and normalization
  - Amount, date, and VAT information extraction
  - Document type classification (receipt, invoice, QR bill, payslip)
- **Bank Statement Import** - Support for major Swiss banks
  - UBS CSV format support
  - Credit Suisse CSV and CAMT formats
  - PostFinance CSV exports
  - Raiffeisen CSV and XML formats
  - Revolut CSV transaction exports
  - Swisscard credit card statements
  - Generic CSV format with smart column detection
- **Merchant Normalization** - Canonical merchant database
  - Pre-populated with major Swiss retailers and services
  - Automatic alias detection and learning
  - Swiss VAT number validation and storage
  - Fuzzy matching for name variations
- **Swiss Tax Category Mapping** - Comprehensive deduction categories
  - Federal tax deduction categories
  - Canton-specific rules and limits (all 26 cantons)
  - Professional expenses optimization
  - Commuting cost calculations (public transport and car)
  - Pillar 3a contribution tracking
  - Health insurance and medical expense thresholds
  - Childcare expense limits per child
  - Charitable donation rules and percentages
  - Home office deduction calculations
- **Transaction Reconciliation** - Automated expense-transaction matching
  - Multiple matching strategies (amount, date, merchant, reference)
  - Configurable confidence thresholds
  - Manual review workflow for uncertain matches
  - Bulk reconciliation with session tracking
- **Tax Optimization** - Swiss compliance and deduction maximization
  - Federal and cantonal limit checking
  - Automatic rule validation with warnings
  - Optimization recommendations with impact analysis
  - Business percentage tracking for mixed-use expenses
- **Export Functionality** - Tax preparation ready formats
  - Excel (.xlsx) exports with formatting
  - CSV exports with Swiss decimal separators
  - JSON exports for data interchange
  - Canton-specific formatting for tax software
  - VAT reporting for business expenses
- **Database Management** - SQLite-based local storage
  - Comprehensive schema with proper relationships
  - User data isolation and security
  - Backup and restore functionality
  - Data integrity validation
- **Command Line Interface** - Full CLI access to all features
  - Receipt processing commands
  - Bank statement import
  - Reconciliation management
  - Tax calculation and optimization
  - Data export and reporting
- **Maintenance Tools** - Database optimization and cleanup
  - Performance analysis and recommendations
  - Data quality assessment
  - Storage optimization (VACUUM, ANALYZE, REINDEX)
  - Old data cleanup with configurable retention
- **Multi-Language Support** - Swiss official languages
  - German (Deutsch) - primary
  - French (Français) - full support
  - Italian (Italiano) - full support
  - English - interface and fallback
- **Documentation** - Comprehensive guides and examples
  - Complete API documentation
  - Usage examples for all major workflows
  - Troubleshooting guide
  - Setup and installation instructions
  - Interactive demo script

### Technical Features
- **Architecture** - Modular, extensible design
  - Plugin-based document parsers
  - Configurable matching strategies
  - Extensible export formats
  - Custom category mapping support
- **Performance** - Optimized for large datasets
  - Efficient SQLite database design with indexes
  - Batch processing capabilities
  - Memory-conscious large file handling
  - Background processing support
- **Security** - Local data storage and privacy
  - No cloud dependencies
  - Encrypted storage options
  - User data isolation
  - GDPR compliance features
- **Quality Assurance** - Comprehensive testing and validation
  - Unit tests for all major components
  - Integration tests for workflows
  - Data validation and integrity checks
  - Performance benchmarking
- **Compliance** - Swiss tax law adherence
  - 2024 tax year rules and limits
  - Federal and cantonal regulation support
  - VAT rate handling (8.1%, 3.8%, 2.6%, 0.0%)
  - Currency support (CHF primary, EUR secondary)

### Swiss-Specific Features
- **Canton Support** - All 26 Swiss cantons
  - AG, AI, AR, BE, BL, BS, FR, GE, GL, GR, JU, LU, NE, NW, OW, SG, SH, SO, SZ, TG, TI, UR, VD, VS, ZG, ZH
  - Canton-specific deduction limits and bonuses
  - Local tax optimization strategies
- **Bank Integration** - Major Swiss financial institutions
  - UBS - Switzerland's largest bank
  - Credit Suisse - Major international bank
  - PostFinance - Swiss postal banking
  - Raiffeisen - Cooperative banking network
  - Cantonal banks - Regional bank support
  - Digital banks - Revolut, Swissquote support
- **Merchant Database** - Swiss retail and service providers
  - Major retailers (Migros, Coop, Denner, Aldi, Lidl, Manor)
  - Transport providers (SBB, PostBus, local transport)
  - Telecommunications (Swisscom, Sunrise, Salt)
  - Financial services (banks, insurance companies)
  - International chains with Swiss presence
- **Tax Categories** - Swiss deduction structure
  - Berufsauslagen (Professional expenses)
  - Fahrtkosten (Commuting costs)
  - Verpflegungskosten (Work meals)
  - Weiterbildung (Professional education)
  - Säule 3a (Pillar 3a contributions)
  - Versicherungsprämien (Insurance premiums)
  - Kinderbetreuung (Childcare costs)
  - Krankheitskosten (Medical expenses)
  - Spenden (Charitable donations)

### Known Limitations
- OCR accuracy depends on image quality and document layout
- Some bank formats may require manual configuration
- Canton-specific rules are based on 2024 regulations
- Large databases (>100k transactions) may require optimization
- Tesseract OCR engine required for document processing

### Dependencies
- Python 3.8+ required
- Pillow >= 9.0.0 (image processing)
- pytesseract >= 0.3.8 (OCR functionality)
- openpyxl >= 3.0.9 (Excel export)
- Tesseract OCR engine with language packs
- SQLite 3.8+ (usually included with Python)

### Installation Requirements
- **Operating Systems:** Windows 10+, macOS 10.14+, Ubuntu 18.04+
- **Memory:** 512MB RAM minimum, 2GB recommended
- **Storage:** 100MB for software, additional space for data
- **Languages:** German, French, Italian, English OCR packs

### Performance Benchmarks
- OCR Processing: ~2-5 seconds per receipt (depending on image quality)
- Statement Import: ~1000 transactions per second
- Reconciliation: ~10,000 comparisons per second
- Database Operations: <100ms for typical queries
- Export Generation: ~1000 records per second

### Future Roadmap
- Integration with Swiss tax preparation software
- Mobile app for receipt capture
- Cloud synchronization options (with privacy controls)
- Advanced analytics and reporting
- Multi-user support for businesses
- API for third-party integrations
- Machine learning for improved categorization
- Real-time bank integration (with user consent)

---

## Version History

### Pre-Release Development
- 2023-12-01: Project initiation and requirements analysis
- 2023-12-15: Core architecture design and database schema
- 2023-12-20: OCR integration and document parsing implementation
- 2024-01-01: **v1.0.0 Release** - Full feature completion

---

*For detailed technical changes and API modifications, see the Git commit history.*
*For upgrade instructions and breaking changes, see the README.md file.*
