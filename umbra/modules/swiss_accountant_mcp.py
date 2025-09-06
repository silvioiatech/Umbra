"""
Swiss Accountant v1.5 - File-first Swiss tax/VAT assistant
Privacy-first, file-first Swiss personal/business tax helper with OCR, QR-bills, reconciliation, and reports.
"""
import os
import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal
from pathlib import Path

from ..core.config import get_config
from ..storage.database import get_database
from ..utils.logger import get_logger

# Swiss Accountant components
from .swiss_accountant.ingest.ocr import OCRPipeline
from .swiss_accountant.ingest.parsers import DocumentParser
from .swiss_accountant.ingest.qr_bill import QRBillParser
from .swiss_accountant.ingest.statements import StatementParser
from .swiss_accountant.normalize.merchants import MerchantNormalizer
from .swiss_accountant.normalize.categories import CategoryMapper
from .swiss_accountant.reconcile.matcher import ExpenseTransactionMatcher
from .swiss_accountant.rules.vat_engine import VATEngine
from .swiss_accountant.rules.tax_profiles import TaxProfileManager
from .swiss_accountant.exports.csv_excel import ExportManager
from .swiss_accountant.exports.evidence_pack import EvidencePackGenerator
from .swiss_accountant.ai.helpers import AIHelpers


class SwissAccountantMCP:
    """Swiss Accountant v1.5 - File-first Swiss tax/VAT assistant."""

    def __init__(self):
        """Initialize the Swiss Accountant module."""
        self.config = get_config()
        self.db = get_database()
        self.logger = get_logger(__name__)
        
        # Configuration
        self.locale_tz = os.getenv('LOCALE_TZ', 'Europe/Zurich')
        self.ai_policy = os.getenv('AI_POLICY', 'sparring')  # sparring|always|never
        self.ai_daily_cost_cap_chf = float(os.getenv('AI_DAILY_COST_CAP_CHF', '5.0'))
        self.ai_timeout_ms = int(os.getenv('AI_TIMEOUT_MS', '10000'))
        self.ocr_engine = os.getenv('OCR_ENGINE', 'tesseract')
        self.ocr_langs = os.getenv('OCR_LANGS', 'deu+fra+ita+eng')
        self.max_doc_size_mb = int(os.getenv('MAX_DOC_SIZE_MB', '20'))
        self.allowed_doc_types = os.getenv('ALLOWED_DOC_TYPES', 'pdf,jpg,jpeg,png,xml,csv,xlsx').split(',')
        self.export_password_required = os.getenv('EXPORT_PASSWORD_REQUIRED', 'false').lower() == 'true'
        self.privacy_mode = os.getenv('PRIVACY_MODE', 'strict')
        
        # Initialize components
        self.ocr_pipeline = OCRPipeline(self.ocr_engine, self.ocr_langs)
        self.document_parser = DocumentParser()
        self.qr_bill_parser = QRBillParser()
        self.statement_parser = StatementParser()
        self.merchant_normalizer = MerchantNormalizer(self.db)
        self.category_mapper = CategoryMapper(self.db)
        self.expense_matcher = ExpenseTransactionMatcher(self.db)
        self.vat_engine = VATEngine()
        self.tax_profile_manager = TaxProfileManager(self.db)
        self.export_manager = ExportManager()
        self.evidence_pack_generator = EvidencePackGenerator()
        self.ai_helpers = AIHelpers(self.ai_policy, self.privacy_mode)
        
        # Initialize database
        self._init_database()

    def get_capabilities(self) -> Dict[str, Any]:
        """Get module capabilities."""
        return {
            "name": "swiss_accountant",
            "version": "1.5.0",
            "description": "File-first Swiss tax/VAT assistant",
            "actions": [
                "ingest_document",
                "infer_document", 
                "import_statement",
                "parse_qr_bill",
                "add_expense",
                "list_expenses",
                "reconcile",
                "monthly_report",
                "set_tax_profile",
                "yearly_tax_report",
                "tva_ledger",
                "export_tax_csv",
                "export_excel",
                "evidence_pack",
                "add_rule",
                "list_rules",
                "delete_rule",
                "update_rates",
                "ai_set_policy",
                "delete_document",
                "delete_expense",
                "rename_category",
                "upsert_alias"
            ],
            "config": {
                "locale_tz": self.locale_tz,
                "ai_policy": self.ai_policy,
                "privacy_mode": self.privacy_mode,
                "ocr_engine": self.ocr_engine,
                "supported_languages": self.ocr_langs.split('+')
            }
        }

    async def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action."""
        try:
            user_id = params.get('user_id', 'system')
            
            # Map actions to methods
            action_map = {
                'ingest_document': self._ingest_document,
                'infer_document': self._infer_document,
                'import_statement': self._import_statement,
                'parse_qr_bill': self._parse_qr_bill,
                'add_expense': self._add_expense,
                'list_expenses': self._list_expenses,
                'reconcile': self._reconcile,
                'monthly_report': self._monthly_report,
                'set_tax_profile': self._set_tax_profile,
                'yearly_tax_report': self._yearly_tax_report,
                'tva_ledger': self._tva_ledger,
                'export_tax_csv': self._export_tax_csv,
                'export_excel': self._export_excel,
                'evidence_pack': self._evidence_pack,
                'add_rule': self._add_rule,
                'list_rules': self._list_rules,
                'delete_rule': self._delete_rule,
                'update_rates': self._update_rates,
                'ai_set_policy': self._ai_set_policy,
                'delete_document': self._delete_document,
                'delete_expense': self._delete_expense,
                'rename_category': self._rename_category,
                'upsert_alias': self._upsert_alias
            }

            if action not in action_map:
                return {
                    'success': False,
                    'error': f'Unknown action: {action}',
                    'available_actions': list(action_map.keys())
                }

            result = await action_map[action](params)
            return {
                'success': True,
                'action': action,
                'result': result,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            self.logger.error(f"Swiss Accountant action '{action}' failed", error=str(e))
            return {
                'success': False,
                'action': action,
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

    def _init_database(self):
        """Initialize Swiss Accountant database tables."""
        try:
            # Documents table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sa_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    sha256 TEXT UNIQUE NOT NULL,
                    mime TEXT NOT NULL,
                    name TEXT NOT NULL,
                    received_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ocr_text TEXT,
                    meta_json TEXT,
                    file_size INTEGER,
                    file_path TEXT
                )
            """)

            # Expenses table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sa_expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    doc_id INTEGER,
                    amount_cents INTEGER NOT NULL,
                    currency TEXT DEFAULT 'CHF',
                    date_local DATE NOT NULL,
                    tz TEXT DEFAULT 'Europe/Zurich',
                    merchant_id INTEGER,
                    merchant_text TEXT,
                    category_code TEXT,
                    vat_breakdown_json TEXT,
                    tip_cents INTEGER DEFAULT 0,
                    payment_method TEXT,
                    account_ref TEXT,
                    pro_pct REAL DEFAULT 0,
                    notes TEXT,
                    created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (doc_id) REFERENCES sa_documents (id),
                    FOREIGN KEY (merchant_id) REFERENCES sa_merchants (id)
                )
            """)

            # Expense lines table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sa_expense_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expense_id INTEGER NOT NULL,
                    desc TEXT,
                    qty REAL DEFAULT 1,
                    unit_cents INTEGER,
                    vat_rate REAL,
                    vat_cents INTEGER,
                    category_code TEXT,
                    FOREIGN KEY (expense_id) REFERENCES sa_expenses (id)
                )
            """)

            # Merchants table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sa_merchants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical TEXT UNIQUE NOT NULL,
                    vat_no TEXT,
                    aliases TEXT
                )
            """)

            # Payslips table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sa_payslips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id INTEGER NOT NULL,
                    period TEXT,
                    gross_cents INTEGER,
                    thirteenth_cents INTEGER DEFAULT 0,
                    holiday_cents INTEGER DEFAULT 0,
                    ahv_iv_eo_cents INTEGER DEFAULT 0,
                    alv_cents INTEGER DEFAULT 0,
                    bvg_employee_cents INTEGER DEFAULT 0,
                    nbu_cents INTEGER DEFAULT 0,
                    uvg_cents INTEGER DEFAULT 0,
                    ktg_cents INTEGER DEFAULT 0,
                    qst_cents INTEGER DEFAULT 0,
                    net_cents INTEGER,
                    employer TEXT,
                    employee TEXT,
                    canton TEXT,
                    comments TEXT,
                    FOREIGN KEY (doc_id) REFERENCES sa_documents (id)
                )
            """)

            # Statements table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sa_statements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    account_ref TEXT,
                    period_start DATE,
                    period_end DATE,
                    raw_ref TEXT,
                    meta_json TEXT,
                    processed_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Transactions table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sa_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    statement_id INTEGER,
                    booking_date DATE,
                    value_date DATE,
                    amount_cents INTEGER,
                    currency TEXT DEFAULT 'CHF',
                    counterparty TEXT,
                    reference TEXT,
                    card_last4 TEXT,
                    mcc TEXT,
                    fx_rate REAL,
                    orig_amount_cents INTEGER,
                    orig_currency TEXT,
                    raw_desc TEXT,
                    matched_expense_id INTEGER,
                    FOREIGN KEY (statement_id) REFERENCES sa_statements (id),
                    FOREIGN KEY (matched_expense_id) REFERENCES sa_expenses (id)
                )
            """)

            # VAT rates table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sa_vat_rates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rate_type TEXT NOT NULL,
                    rate REAL NOT NULL,
                    effective_from DATE NOT NULL,
                    source_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Social rates table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sa_social_rates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value REAL NOT NULL,
                    source_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # FX rates table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sa_fx_rates (
                    source TEXT NOT NULL,
                    base TEXT NOT NULL,
                    quote TEXT NOT NULL,
                    rate REAL NOT NULL,
                    as_of DATE NOT NULL,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (source, base, quote, as_of)
                )
            """)

            # Aliases table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sa_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    alias TEXT NOT NULL,
                    canonical TEXT NOT NULL,
                    UNIQUE(kind, alias)
                )
            """)

            # User rules table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sa_user_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    rule_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # AI inferences table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sa_ai_inferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    model TEXT,
                    confidence REAL,
                    features_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (doc_id) REFERENCES sa_documents (id)
                )
            """)

            # Create indexes
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_sa_expenses_user_date ON sa_expenses (user_id, date_local)")
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_sa_expenses_merchant ON sa_expenses (merchant_text)")
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_sa_expenses_category ON sa_expenses (category_code)")
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_sa_transactions_amount_date ON sa_transactions (amount_cents, value_date)")
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_sa_transactions_reference ON sa_transactions (reference)")
            
            # Create FTS index for document search
            self.db.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS sa_documents_fts USING fts5(
                    content='sa_documents',
                    content_rowid='id',
                    ocr_text
                )
            """)

            # Insert default Swiss VAT rates
            self._insert_default_vat_rates()
            
            # Insert default Swiss tax categories
            self._insert_default_tax_categories()

            self.logger.info("✅ Swiss Accountant database initialized")

        except Exception as e:
            self.logger.error(f"Swiss Accountant database initialization failed: {e}")
            raise

    def _insert_default_vat_rates(self):
        """Insert default Swiss VAT rates."""
        try:
            # Current Swiss VAT rates (as of 2024)
            vat_rates = [
                ('standard', 8.1, '2024-01-01'),
                ('reduced', 2.6, '2024-01-01'), 
                ('special', 3.8, '2024-01-01'),  # Hotels, accommodation
                ('zero', 0.0, '2024-01-01')
            ]
            
            for rate_type, rate, effective_from in vat_rates:
                existing = self.db.query_one(
                    "SELECT id FROM sa_vat_rates WHERE rate_type = ? AND effective_from = ?",
                    (rate_type, effective_from)
                )
                
                if not existing:
                    self.db.execute(
                        "INSERT INTO sa_vat_rates (rate_type, rate, effective_from, source_url) VALUES (?, ?, ?, ?)",
                        (rate_type, rate, effective_from, 'https://www.estv.admin.ch/estv/de/home/mehrwertsteuer/dienstleistungsunternehmen/abrechnung/steuersaetze.html')
                    )
                    
        except Exception as e:
            self.logger.warning(f"Failed to insert default VAT rates: {e}")

    def _insert_default_tax_categories(self):
        """Insert default Swiss tax categories."""
        try:
            categories = [
                ('professional_expenses', 'Berufsauslagen'),
                ('commute_public', 'ÖV-Abonnement'),
                ('commute_car', 'Fahrtkosten Auto'),
                ('meals_work', 'Verpflegung bei Arbeit'),
                ('education', 'Weiterbildung'),
                ('insurance_pillar3a', 'Säule 3a'),
                ('insurance_health', 'Krankenkasse'),
                ('childcare', 'Kinderbetreuung'),
                ('donations', 'Spenden'),
                ('home_office', 'Homeoffice'),
                ('other_deductions', 'Weitere Abzüge')
            ]
            
            for code, description in categories:
                existing = self.db.query_one(
                    "SELECT id FROM sa_aliases WHERE kind = 'tax_category' AND alias = ?",
                    (code,)
                )
                
                if not existing:
                    self.db.execute(
                        "INSERT INTO sa_aliases (kind, alias, canonical) VALUES (?, ?, ?)",
                        ('tax_category', code, description)
                    )
                    
        except Exception as e:
            self.logger.warning(f"Failed to insert default tax categories: {e}")

    # Action implementations (placeholders for now)
    async def _ingest_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Ingest and parse a document."""
        return {"status": "placeholder", "message": "Document ingestion not yet implemented"}

    async def _infer_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Infer document type and extract fields."""
        return {"status": "placeholder", "message": "Document inference not yet implemented"}

    async def _import_statement(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Import bank/card statement."""
        return {"status": "placeholder", "message": "Statement import not yet implemented"}

    async def _parse_qr_bill(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Swiss QR-bill."""
        return {"status": "placeholder", "message": "QR-bill parsing not yet implemented"}

    async def _add_expense(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add expense manually."""
        return {"status": "placeholder", "message": "Add expense not yet implemented"}

    async def _list_expenses(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List expenses with filters."""
        return {"status": "placeholder", "message": "List expenses not yet implemented"}

    async def _reconcile(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Reconcile expenses with transactions."""
        return {"status": "placeholder", "message": "Reconciliation not yet implemented"}

    async def _monthly_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate monthly report."""
        return {"status": "placeholder", "message": "Monthly report not yet implemented"}

    async def _set_tax_profile(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set tax profile for canton/year."""
        return {"status": "placeholder", "message": "Tax profile setting not yet implemented"}

    async def _yearly_tax_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate yearly tax report."""
        return {"status": "placeholder", "message": "Yearly tax report not yet implemented"}

    async def _tva_ledger(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate TVA/VAT ledger."""
        return {"status": "placeholder", "message": "TVA ledger not yet implemented"}

    async def _export_tax_csv(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Export tax data as CSV."""
        return {"status": "placeholder", "message": "Tax CSV export not yet implemented"}

    async def _export_excel(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Export data as Excel."""
        return {"status": "placeholder", "message": "Excel export not yet implemented"}

    async def _evidence_pack(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate evidence pack ZIP."""
        return {"status": "placeholder", "message": "Evidence pack not yet implemented"}

    async def _add_rule(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add user rule (admin only)."""
        return {"status": "placeholder", "message": "Add rule not yet implemented"}

    async def _list_rules(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List user rules."""
        return {"status": "placeholder", "message": "List rules not yet implemented"}

    async def _delete_rule(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete rule (admin only)."""
        return {"status": "placeholder", "message": "Delete rule not yet implemented"}

    async def _update_rates(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update rates (VAT, FX, social)."""
        return {"status": "placeholder", "message": "Update rates not yet implemented"}

    async def _ai_set_policy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set AI policy."""
        return {"status": "placeholder", "message": "AI policy setting not yet implemented"}

    async def _delete_document(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete document (admin only)."""
        return {"status": "placeholder", "message": "Delete document not yet implemented"}

    async def _delete_expense(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete expense (admin only)."""
        return {"status": "placeholder", "message": "Delete expense not yet implemented"}

    async def _rename_category(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Rename category (admin only)."""
        return {"status": "placeholder", "message": "Rename category not yet implemented"}

    async def _upsert_alias(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert alias (admin only)."""
        return {"status": "placeholder", "message": "Upsert alias not yet implemented"}


# Module instance for registration
swiss_accountant_mcp = SwissAccountantMCP()
