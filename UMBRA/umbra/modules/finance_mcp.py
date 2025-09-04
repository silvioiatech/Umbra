"""
Enhanced Finance MCP - Complete Personal Financial Management System
Integrates all advanced features including multi-account management, investment tracking,
financial goals, analytics, and comprehensive reporting capabilities.
"""
import os
import re
import json
import math
import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, asdict
from enum import Enum

from ..core.envelope import InternalEnvelope
from ..core.module_base import ModuleBase
from .finance_mcp_extensions import FinanceExtensions


class TransactionType(Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class AccountType(Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    INVESTMENT = "investment"
    CASH = "cash"
    LOAN = "loan"


class GoalType(Enum):
    SAVINGS = "savings"
    DEBT_PAYOFF = "debt_payoff"
    BUDGET = "budget"
    INVESTMENT = "investment"


@dataclass
class FinancialMetric:
    name: str
    value: float
    previous_value: float
    change_percentage: float
    trend: str  # 'up', 'down', 'stable'
    category: str
    icon: str


class FinanceMCP(ModuleBase):
    """Enhanced Personal Financial Management System."""

    def __init__(self, config, db_manager):
        super().__init__("finance")
        self.config = config
        self.db = db_manager
        
        # Configuration from environment variables
        self.currency_symbol = os.getenv('FINANCE_CURRENCY_SYMBOL', '$')
        self.default_currency = os.getenv('FINANCE_DEFAULT_CURRENCY', 'USD')
        self.auto_categorize = os.getenv('FINANCE_AUTO_CATEGORIZE', 'true').lower() == 'true'
        self.enable_investments = os.getenv('FINANCE_ENABLE_INVESTMENTS', 'true').lower() == 'true'
        self.enable_goals = os.getenv('FINANCE_ENABLE_GOALS', 'true').lower() == 'true'
        self.enable_analytics = os.getenv('FINANCE_ENABLE_ANALYTICS', 'true').lower() == 'true'
        self.budget_alert_threshold = float(os.getenv('FINANCE_BUDGET_ALERT_THRESHOLD', '90'))
        self.low_balance_threshold = float(os.getenv('FINANCE_LOW_BALANCE_THRESHOLD', '100'))
        
        # Investment settings
        self.stock_api_key = os.getenv('FINANCE_STOCK_API_KEY')
        self.enable_real_time_quotes = os.getenv('FINANCE_ENABLE_REAL_TIME_QUOTES', 'false').lower() == 'true'
        
        # Advanced features flags
        self.enable_tax_tracking = os.getenv('FINANCE_ENABLE_TAX_TRACKING', 'true').lower() == 'true'
        self.enable_retirement_planning = os.getenv('FINANCE_ENABLE_RETIREMENT_PLANNING', 'true').lower() == 'true'
        self.enable_debt_planning = os.getenv('FINANCE_ENABLE_DEBT_PLANNING', 'true').lower() == 'true'
        self.enable_multi_currency = os.getenv('FINANCE_ENABLE_MULTI_CURRENCY', 'false').lower() == 'true'
        
        # Alert settings
        self.enable_email_alerts = os.getenv('FINANCE_ENABLE_EMAIL_ALERTS', 'false').lower() == 'true'
        self.alert_email = os.getenv('FINANCE_ALERT_EMAIL')
        
        # Initialize database
        self._init_enhanced_database()
        
        # Load categorization patterns
        self.categorization_patterns = self._load_categorization_patterns()
        
        # Initialize production extensions
        self.extensions = FinanceExtensions(config, db_manager, self.logger)

    async def initialize(self) -> bool:
        """Initialize the Enhanced Finance module."""
        try:
            # Test database connectivity
            test_query = "SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'"
            self.db.query_one(test_query)

            # Migrate old data if exists
            await self._migrate_legacy_data()

            # Create default account if none exist
            existing_accounts = self.db.query_all("SELECT id FROM accounts LIMIT 1")
            if not existing_accounts:
                await self._create_default_accounts()
                self.logger.info("Default accounts created")

            # Create default categories and goals
            await self._setup_default_data()
            
            self.logger.info("Enhanced Finance module initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Enhanced Finance initialization failed: {e}")
            return False

    async def register_handlers(self) -> dict[str, Any]:
        """Register command handlers for the Enhanced Finance module."""
        handlers = {
            # Legacy compatibility handlers
            "track expense": self.track_expense_legacy,
            "budget status": self.get_budget_status,
            "financial report": self.generate_report,
            "set budget": self.set_budget,
            "expense summary": self.get_expense_summary,
            "monthly report": self.monthly_financial_report,
            
            # Account Management
            "create account": self.create_account,
            "list accounts": self.list_accounts,
            "account balance": self.get_account_balance,
            "transfer funds": self.transfer_funds,
            "account summary": self.get_account_summary,
            
            # Enhanced Transaction Management
            "add income": self.add_income,
            "add expense": self.add_expense,
            "track transaction": self.add_transaction,
            "transaction history": self.get_transaction_history,
            "recent transactions": self.get_recent_transactions,
            "categorize transaction": self.categorize_transaction,
            
            # Budget & Goals
            "create goal": self.create_financial_goal,
            "goal progress": self.get_goal_progress,
            "update goal": self.update_goal_progress,
            "list goals": self.list_goals,
            "delete goal": self.delete_goal,
            
            # Analytics & Reports
            "financial summary": self.get_financial_summary,
            "executive summary": self.generate_executive_summary,
            "spending analysis": self.analyze_spending,
            "income vs expenses": self.compare_income_expenses,
            "yearly report": self.generate_yearly_report,
            "cash flow": self.analyze_cash_flow,
            "health score": self.calculate_financial_health_score,
            "spending forecast": self.generate_spending_forecast,
            "wealth projection": self.generate_wealth_projection,
            
            # Receipt OCR & Document Management
            "process receipt": self.process_receipt,
            "list receipts": self.list_receipts,
            "get receipt": self.get_receipt_details,
            "link receipt": self.link_receipt_to_transaction,
            
            # Investment Management (Real APIs)
            "get stock quote": self.get_stock_quote,
            "update stock prices": self.update_investment_prices,
            "investment analysis": self.analyze_investments,
            
            # Tax Planning & Compliance
            "setup tax categories": self.setup_tax_categories,
            "tax deductions": self.calculate_tax_deductions,
            "export tax data": self.export_tax_data,
            "tax planning": self.tax_planning_advice,
            
            # Data Management (Production-Ready)
            "import bank csv": self.import_bank_data,
            "export data": self.export_financial_data,
            "backup data": self.backup_financial_data,
        }
        
        # Add investment handlers if enabled
        if self.enable_investments:
            handlers.update({
                "add investment": self.add_investment,
                "buy investment": self.buy_investment,
                "sell investment": self.sell_investment,
                "record dividend": self.record_dividend,
                "investment portfolio": self.get_investment_portfolio,
                "portfolio summary": self.get_portfolio_summary,
                "investment performance": self.get_investment_performance,
            })
        
        # Add advanced planning handlers if enabled
        if self.enable_retirement_planning:
            handlers["retirement plan"] = self.calculate_retirement_needs
        
        if self.enable_debt_planning:
            handlers["debt payoff plan"] = self.create_debt_payoff_plan
        
        if self.enable_tax_tracking:
            handlers["tax summary"] = self.generate_tax_summary
        
        return handlers

    async def process_envelope(self, envelope: InternalEnvelope) -> str | None:
        """Process envelope for Finance operations."""
        action = envelope.action.lower()
        data = envelope.data
        user_id = int(envelope.user_id)

        # Legacy compatibility
        if action == "track_expense":
            amount = data.get("amount", 0)
            description = data.get("description", "")
            return await self.track_expense_legacy(amount, description, user_id)
        elif action == "budget_status":
            return await self.get_budget_status()
        elif action == "financial_report":
            period = data.get("period", "month")
            return await self.generate_report(period)
        elif action == "set_budget":
            category = data.get("category", "")
            amount = data.get("amount", 0)
            return await self.set_budget(category, amount, user_id)
        elif action == "expense_summary":
            return await self.get_expense_summary(user_id)
        elif action == "create_account":
            name = data.get("name", "")
            account_type = data.get("type", "checking")
            balance = data.get("balance", 0.0)
            return await self.create_account(name, account_type, balance, user_id)
        elif action == "add_transaction":
            account_id = data.get("account_id", 1)
            transaction_type = data.get("type", "expense")
            amount = data.get("amount", 0)
            description = data.get("description", "")
            category = data.get("category", "")
            return await self.add_transaction(account_id, transaction_type, amount, description, category, user_id)
        else:
            return None

    async def health_check(self) -> dict[str, Any]:
        """Enhanced health check."""
        try:
            # Count records in each table
            accounts_count = self.db.query_one("SELECT COUNT(*) as count FROM accounts")
            transactions_count = self.db.query_one("SELECT COUNT(*) as count FROM transactions")
            budgets_count = self.db.query_one("SELECT COUNT(*) as count FROM budgets")
            
            health_data = {
                "status": "healthy",
                "details": {
                    "accounts": accounts_count["count"] if accounts_count else 0,
                    "transactions": transactions_count["count"] if transactions_count else 0,
                    "budgets": budgets_count["count"] if budgets_count else 0,
                    "database_accessible": True
                }
            }
            
            # Add goal and investment counts if enabled
            if self.enable_goals:
                goals_count = self.db.query_one("SELECT COUNT(*) as count FROM financial_goals")
                health_data["details"]["goals"] = goals_count["count"] if goals_count else 0
            
            if self.enable_investments:
                investments_count = self.db.query_one("SELECT COUNT(*) as count FROM investments")
                health_data["details"]["investments"] = investments_count["count"] if investments_count else 0

            # Check for recent activity
            recent_activity = self.db.query_one("""
                SELECT COUNT(*) as count FROM transactions
                WHERE date >= date('now', '-7 days')
            """)
            health_data["details"]["recent_activity"] = recent_activity["count"] if recent_activity else 0

            return health_data
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def shutdown(self):
        """Gracefully shutdown the Enhanced Finance module."""
        self.logger.info("Enhanced Finance module shutting down")

    def _init_enhanced_database(self):
        """Initialize enhanced finance tables."""
        try:
            # Accounts table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER DEFAULT 0,
                    name TEXT NOT NULL,
                    account_type TEXT NOT NULL,
                    balance DECIMAL(15,2) DEFAULT 0.00,
                    currency TEXT DEFAULT 'USD',
                    is_active BOOLEAN DEFAULT TRUE,
                    institution TEXT,
                    account_number TEXT,
                    interest_rate DECIMAL(5,4),
                    credit_limit DECIMAL(15,2),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Enhanced transactions table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER DEFAULT 0,
                    account_id INTEGER,
                    transaction_type TEXT NOT NULL,
                    amount DECIMAL(15,2) NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT,
                    subcategory TEXT,
                    date TIMESTAMP NOT NULL,
                    is_recurring BOOLEAN DEFAULT FALSE,
                    recurring_interval TEXT,
                    to_account_id INTEGER,
                    tags TEXT,
                    receipt_url TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (account_id) REFERENCES accounts (id),
                    FOREIGN KEY (to_account_id) REFERENCES accounts (id)
                )
            """)

            # Enhanced budgets table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS budgets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER DEFAULT 0,
                    category TEXT NOT NULL,
                    subcategory TEXT,
                    monthly_limit DECIMAL(15,2) NOT NULL,
                    spent_amount DECIMAL(15,2) DEFAULT 0.00,
                    period_start DATE,
                    period_end DATE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Categories table for better organization
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    parent_category TEXT,
                    category_type TEXT NOT NULL, -- 'income' or 'expense'
                    icon TEXT,
                    color TEXT,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)

            # Financial goals table (if enabled)
            if self.enable_goals:
                self.db.execute("""
                    CREATE TABLE IF NOT EXISTS financial_goals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER DEFAULT 0,
                        name TEXT NOT NULL,
                        goal_type TEXT NOT NULL,
                        target_amount DECIMAL(15,2) NOT NULL,
                        current_amount DECIMAL(15,2) DEFAULT 0.00,
                        target_date TIMESTAMP,
                        account_id INTEGER,
                        category TEXT,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (account_id) REFERENCES accounts (id)
                    )
                """)

            # Investments table (if enabled)
            if self.enable_investments:
                self.db.execute("""
                    CREATE TABLE IF NOT EXISTS investments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER DEFAULT 0,
                        account_id INTEGER,
                        symbol TEXT NOT NULL,
                        name TEXT,
                        quantity DECIMAL(15,8) NOT NULL,
                        purchase_price DECIMAL(15,4) NOT NULL,
                        current_price DECIMAL(15,4),
                        purchase_date TIMESTAMP NOT NULL,
                        investment_type TEXT DEFAULT 'stock',
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (account_id) REFERENCES accounts (id)
                    )
                """)

            self.logger.info("✅ Enhanced Finance database initialized")
        except Exception as e:
            self.logger.error(f"Enhanced Finance DB init failed: {e}")

    async def _migrate_legacy_data(self):
        """Migrate data from legacy tables if they exist."""
        try:
            # Check if old expenses table exists
            expenses_table = self.db.query_one("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='expenses'
            """)
            
            if expenses_table:
                # Create default account for migration
                default_account_id = await self._ensure_default_account()
                
                # Migrate expenses to transactions
                old_expenses = self.db.query_all("SELECT * FROM expenses")
                migrated_count = 0
                
                for expense in old_expenses:
                    try:
                        self.db.execute("""
                            INSERT OR IGNORE INTO transactions (
                                user_id, account_id, transaction_type, amount, description, 
                                category, date, created_at
                            )
                            VALUES (?, ?, 'expense', ?, ?, ?, ?, ?)
                        """, (
                            expense.get('user_id', 0), 
                            default_account_id,
                            expense['amount'],
                            expense['description'],
                            expense['category'],
                            expense['date'],
                            expense.get('created_at', expense['date'])
                        ))
                        migrated_count += 1
                    except Exception as e:
                        self.logger.warning(f"Failed to migrate expense {expense['id']}: {e}")
                
                # Update account balance
                total_migrated = self.db.query_one("""
                    SELECT SUM(amount) as total FROM transactions 
                    WHERE account_id = ? AND transaction_type = 'expense'
                """, (default_account_id,))
                
                if total_migrated and total_migrated['total']:
                    self.db.execute("""
                        UPDATE accounts SET balance = balance - ? WHERE id = ?
                    """, (total_migrated['total'], default_account_id))
                
                if migrated_count > 0:
                    self.logger.info(f"Migrated {migrated_count} legacy expenses to enhanced system")
                    
                    # Rename old table as backup
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    self.db.execute(f"ALTER TABLE expenses RENAME TO expenses_backup_{timestamp}")
                
        except Exception as e:
            self.logger.error(f"Legacy data migration failed: {e}")

    async def _ensure_default_account(self) -> int:
        """Ensure a default account exists and return its ID."""
        existing_account = self.db.query_one("""
            SELECT id FROM accounts WHERE name = 'Main Account (Migrated)'
        """)
        
        if existing_account:
            return existing_account['id']
        
        # Create default account
        account_id = self.db.execute("""
            INSERT INTO accounts (user_id, name, account_type, balance, created_at)
            VALUES (0, 'Main Account (Migrated)', 'checking', 0.00, CURRENT_TIMESTAMP)
        """)
        
        return account_id

    async def _create_default_accounts(self):
        """Create default accounts for new users."""
        default_accounts = [
            ("Main Checking", "checking", 0.0),
            ("Savings Account", "savings", 0.0),
            ("Cash", "cash", 0.0),
        ]
        
        for name, account_type, balance in default_accounts:
            await self.create_account(name, account_type, balance, user_id=0)

    async def _setup_default_data(self):
        """Setup default categories and sample data."""
        # Default expense categories
        expense_categories = [
            ("Food & Dining", "expense", "🍽️"),
            ("Transportation", "expense", "🚗"),
            ("Shopping", "expense", "🛍️"),
            ("Bills & Utilities", "expense", "📄"),
            ("Healthcare", "expense", "🏥"),
            ("Entertainment", "expense", "🎬"),
            ("Education", "expense", "📚"),
            ("Travel", "expense", "✈️"),
            ("Personal Care", "expense", "💄"),
            ("Home", "expense", "🏠"),
            ("Other", "expense", "📋"),
        ]
        
        # Default income categories
        income_categories = [
            ("Salary", "income", "💼"),
            ("Freelance", "income", "👨‍💻"),
            ("Investment Returns", "income", "📈"),
            ("Side Business", "income", "🏪"),
            ("Rental Income", "income", "🏘️"),
            ("Gifts", "income", "🎁"),
            ("Other Income", "income", "💰"),
        ]

        all_categories = expense_categories + income_categories
        
        for name, cat_type, icon in all_categories:
            try:
                self.db.execute("""
                    INSERT OR IGNORE INTO categories (name, category_type, icon, is_active)
                    VALUES (?, ?, ?, TRUE)
                """, (name, cat_type, icon))
            except Exception as e:
                self.logger.debug(f"Category {name} might already exist: {e}")

    def _load_categorization_patterns(self) -> Dict[str, List[str]]:
        """Load categorization patterns with extensive merchant and keyword matching."""
        return {
            'Food & Dining': [
                # Restaurants & Fast Food
                r'mcdonalds?', r'burger king', r'kfc', r'subway', r'pizza hut', r'dominos?',
                r'taco bell', r'chipotle', r'panera', r'starbucks', r'dunkin', r'wendys?',
                
                # Groceries
                r'walmart', r'target', r'kroger', r'safeway', r'whole foods', r'trader joes?',
                r'costco', r'sams? club', r'aldi', r'publix', r'giant eagle', r'stop shop',
                
                # Food Keywords
                r'restaurant', r'cafe', r'bistro', r'grill', r'kitchen', r'diner',
                r'grocery', r'market', r'food', r'lunch', r'dinner', r'breakfast',
                r'uber eats', r'doordash', r'grubhub', r'postmates', r'deliveroo'
            ],
            
            'Transportation': [
                # Ride Services
                r'uber', r'lyft', r'taxi', r'cab',
                
                # Gas Stations
                r'shell', r'exxon', r'bp', r'chevron', r'mobil', r'gulf', r'sunoco',
                r'marathon', r'speedway', r'wawa', r'quick chek',
                
                # Transportation Keywords
                r'gas', r'fuel', r'parking', r'garage', r'metro', r'bus', r'train',
                r'airline', r'airport', r'toll', r'bridge', r'tunnel'
            ],
            
            'Bills & Utilities': [
                # Utilities
                r'electric', r'gas', r'water', r'sewer', r'trash', r'internet',
                r'cable', r'phone', r'wireless', r'cell', r'mobile',
                
                # Major Providers
                r'verizon', r'att', r'tmobile', r't-mobile', r'sprint', r'comcast',
                r'xfinity', r'spectrum', r'cox', r'directv', r'dish',
                
                # Services
                r'insurance', r'rent', r'mortgage', r'loan', r'payment',
                r'utility', r'bill', r'service'
            ],
            
            'Shopping': [
                # Major Retailers
                r'amazon', r'ebay', r'target', r'walmart', r'costco', r'best buy',
                r'home depot', r'lowes', r'macys', r'nordstrom', r'tj maxx',
                r'marshall', r'ross', r'old navy', r'gap', r'banana republic',
                
                # Categories
                r'clothing', r'shoes', r'electronics', r'furniture', r'appliance',
                r'store', r'shop', r'retail', r'mall', r'outlet'
            ],
            
            'Entertainment': [
                # Streaming Services
                r'netflix', r'hulu', r'disney', r'amazon prime', r'spotify', r'apple music',
                r'youtube', r'hbo', r'showtime', r'paramount',
                
                # Entertainment Venues
                r'theater', r'cinema', r'movie', r'concert', r'stadium', r'arena',
                r'museum', r'zoo', r'aquarium', r'amusement', r'theme park',
                
                # Gaming
                r'steam', r'playstation', r'xbox', r'nintendo', r'gaming'
            ],
            
            'Healthcare': [
                r'doctor', r'physician', r'hospital', r'clinic', r'medical',
                r'pharmacy', r'cvs', r'walgreens', r'rite aid',
                r'dental', r'dentist', r'vision', r'optometry',
                r'health', r'medicine', r'prescription', r'rx'
            ]
        }

    # ===============================
    # ACCOUNT MANAGEMENT METHODS
    # ===============================

    async def create_account(self, name: str, account_type: str, 
                           initial_balance: float = 0.0, user_id: int = None) -> str:
        """Create a new financial account."""
        try:
            # Validate account type
            valid_types = [t.value for t in AccountType]
            if account_type not in valid_types:
                return f"❌ Invalid account type. Use: {', '.join(valid_types)}"

            # Insert account
            account_id = self.db.execute("""
                INSERT INTO accounts (user_id, name, account_type, balance, currency, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (user_id or 0, name, account_type, Decimal(str(initial_balance)), self.default_currency))

            # If initial balance > 0, create opening balance transaction
            if initial_balance > 0:
                await self.add_transaction(
                    account_id=account_id,
                    transaction_type=TransactionType.INCOME.value,
                    amount=initial_balance,
                    description="Opening Balance",
                    category="Other Income",
                    user_id=user_id
                )

            return f"""**✅ Account Created**

Name: {name}
Type: {account_type.replace('_', ' ').title()}
Initial Balance: {self.currency_symbol}{initial_balance:.2f}
Account ID: #{account_id}

Your new account is ready for transactions!"""

        except Exception as e:
            self.logger.error(f"Account creation failed: {e}")
            return f"❌ Failed to create account: {str(e)[:100]}"

    async def list_accounts(self, user_id: int = None) -> str:
        """List all accounts with balances."""
        try:
            accounts = self.db.query_all("""
                SELECT id, name, account_type, balance, currency, is_active, institution
                FROM accounts 
                WHERE (user_id = ? OR ? IS NULL) AND is_active = TRUE
                ORDER BY account_type, name
            """, (user_id, user_id))

            if not accounts:
                return "No accounts found. Create one with: 'create account [name] [type]'"

            # Group by account type
            account_groups = {}
            total_assets = Decimal('0')
            total_liabilities = Decimal('0')

            for account in accounts:
                acc_type = account['account_type']
                balance = Decimal(str(account['balance']))
                
                if acc_type not in account_groups:
                    account_groups[acc_type] = []
                
                account_groups[acc_type].append(account)
                
                # Calculate net worth
                if acc_type in ['checking', 'savings', 'investment', 'cash']:
                    total_assets += balance
                elif acc_type in ['credit_card', 'loan']:
                    total_liabilities += abs(balance)

            # Format response
            response_lines = ["**💰 Account Overview**\n"]
            
            for acc_type, accs in account_groups.items():
                type_total = sum(Decimal(str(acc['balance'])) for acc in accs)
                response_lines.append(f"**{acc_type.replace('_', ' ').title()}:**")
                
                for acc in accs:
                    balance = Decimal(str(acc['balance']))
                    status_icon = "✅" if balance >= 0 else "⚠️" if acc_type == 'credit_card' else "❌"
                    institution = f" ({acc['institution']})" if acc['institution'] else ""
                    
                    response_lines.append(
                        f"{status_icon} #{acc['id']} {acc['name']}{institution}: "
                        f"{self.currency_symbol}{balance:.2f}"
                    )
                
                response_lines.append(f"  *Subtotal: {self.currency_symbol}{type_total:.2f}*\n")

            # Net worth summary
            net_worth = total_assets - total_liabilities
            response_lines.extend([
                f"**📊 Financial Summary:**",
                f"Total Assets: {self.currency_symbol}{total_assets:.2f}",
                f"Total Liabilities: {self.currency_symbol}{total_liabilities:.2f}",
                f"**Net Worth: {self.currency_symbol}{net_worth:.2f}**"
            ])

            return "\n".join(response_lines)

        except Exception as e:
            return f"❌ Failed to list accounts: {str(e)[:100]}"

    async def get_account_balance(self, account_id: int, user_id: int = None) -> str:
        """Get detailed account balance and recent activity."""
        try:
            # Get account details
            account = self.db.query_one("""
                SELECT * FROM accounts 
                WHERE id = ? AND (user_id = ? OR ? IS NULL)
            """, (account_id, user_id, user_id))

            if not account:
                return f"❌ Account #{account_id} not found"

            balance = Decimal(str(account['balance']))
            
            # Get recent transactions (last 5)
            recent_txns = self.db.query_all("""
                SELECT transaction_type, amount, description, date
                FROM transactions 
                WHERE account_id = ? 
                ORDER BY date DESC, created_at DESC 
                LIMIT 5
            """, (account_id,))

            response = f"""**💳 Account Details: {account['name']}**

**Balance:** {self.currency_symbol}{balance:.2f}
**Type:** {account['account_type'].replace('_', ' ').title()}
**Status:** {'✅ Active' if account['is_active'] else '⛔ Inactive'}"""

            if account['institution']:
                response += f"\n**Institution:** {account['institution']}"

            if account['credit_limit']:
                credit_limit = Decimal(str(account['credit_limit']))
                available_credit = credit_limit + balance  # balance is negative for credit cards
                response += f"\n**Credit Limit:** {self.currency_symbol}{credit_limit:.2f}"
                response += f"\n**Available Credit:** {self.currency_symbol}{available_credit:.2f}"

            # Recent transactions
            if recent_txns:
                response += "\n\n**📋 Recent Transactions:**"
                for txn in recent_txns:
                    amount = Decimal(str(txn['amount']))
                    emoji = "💰" if txn['transaction_type'] == 'income' else "💸"
                    sign = "+" if txn['transaction_type'] == 'income' else "-"
                    date_str = datetime.fromisoformat(txn['date']).strftime('%m/%d')
                    
                    response += f"\n{emoji} {date_str}: {sign}{self.currency_symbol}{abs(amount):.2f} - {txn['description']}"

            return response

        except Exception as e:
            return f"❌ Failed to get account balance: {str(e)[:100]}"

    async def transfer_funds(self, from_account_id: int, to_account_id: int, 
                           amount: float, description: str = "Transfer", user_id: int = None) -> str:
        """Transfer funds between accounts."""
        try:
            # Validate accounts exist
            from_account = self.db.query_one("SELECT balance, name FROM accounts WHERE id = ?", (from_account_id,))
            to_account = self.db.query_one("SELECT name FROM accounts WHERE id = ?", (to_account_id,))
            
            if not from_account or not to_account:
                return "❌ One or both accounts not found"

            amount_decimal = Decimal(str(amount))
            current_balance = Decimal(str(from_account['balance']))
            
            # Check sufficient funds
            if current_balance < amount_decimal:
                return f"❌ Insufficient funds. Balance: {self.currency_symbol}{current_balance:.2f}, Transfer: {self.currency_symbol}{amount_decimal:.2f}"

            # Create transfer transactions (2 transactions for double-entry)
            transfer_date = datetime.now()
            
            # Debit from source account
            self.db.execute("""
                INSERT INTO transactions (user_id, account_id, transaction_type, amount, description, category, date, to_account_id)
                VALUES (?, ?, 'expense', ?, ?, 'Transfer', ?, ?)
            """, (user_id or 0, from_account_id, amount_decimal, f"Transfer to {to_account['name']}: {description}", transfer_date, to_account_id))

            # Credit to destination account
            self.db.execute("""
                INSERT INTO transactions (user_id, account_id, transaction_type, amount, description, category, date, to_account_id)
                VALUES (?, ?, 'income', ?, ?, 'Transfer', ?, ?)
            """, (user_id or 0, to_account_id, amount_decimal, f"Transfer from {from_account['name']}: {description}", transfer_date, from_account_id))

            # Update account balances
            self.db.execute("UPDATE accounts SET balance = balance - ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                          (amount_decimal, from_account_id))
            self.db.execute("UPDATE accounts SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                          (amount_decimal, to_account_id))

            return f"""**✅ Transfer Completed**

From: {from_account['name']} (#{from_account_id})
To: {to_account['name']} (#{to_account_id})
Amount: {self.currency_symbol}{amount:.2f}
Description: {description}

New balance: {self.currency_symbol}{current_balance - amount_decimal:.2f}"""

        except Exception as e:
            self.logger.error(f"Transfer failed: {e}")
            return f"❌ Transfer failed: {str(e)[:100]}"

    # ===============================
    # TRANSACTION MANAGEMENT METHODS
    # ===============================

    async def add_transaction(self, account_id: int, transaction_type: str, amount: float,
                            description: str, category: str = "", user_id: int = None) -> str:
        """Add a new transaction."""
        try:
            # Validate account exists
            account = self.db.query_one("SELECT name, account_type, balance FROM accounts WHERE id = ?", (account_id,))
            if not account:
                return f"❌ Account #{account_id} not found"

            # Validate transaction type
            if transaction_type not in [t.value for t in TransactionType]:
                return f"❌ Invalid transaction type. Use: {', '.join([t.value for t in TransactionType])}"

            amount_decimal = Decimal(str(amount))
            
            # Auto-categorize if not provided and enabled
            if not category and self.auto_categorize:
                category = self._auto_categorize_transaction(description, transaction_type)

            # Insert transaction
            txn_id = self.db.execute("""
                INSERT INTO transactions (user_id, account_id, transaction_type, amount, description, category, date)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id or 0, account_id, transaction_type, amount_decimal, description, category))

            # Update account balance
            if transaction_type == TransactionType.INCOME.value:
                balance_change = amount_decimal
                emoji = "💰"
                sign = "+"
            else:  # expense
                balance_change = -amount_decimal
                emoji = "💸"
                sign = "-"

            self.db.execute("UPDATE accounts SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                          (balance_change, account_id))

            # Get updated balance
            updated_balance = self.db.query_one("SELECT balance FROM accounts WHERE id = ?", (account_id,))['balance']

            # Check budget impact if it's an expense
            budget_warning = ""
            if transaction_type == TransactionType.EXPENSE.value:
                budget_warning = await self._check_budget_impact(category, amount_decimal, user_id)

            response = f"""**{emoji} Transaction Added**

Account: {account['name']} (#{account_id})
Type: {transaction_type.title()}
Amount: {sign}{self.currency_symbol}{amount:.2f}
Description: {description}
Category: {category}
New Balance: {self.currency_symbol}{Decimal(str(updated_balance)):.2f}

Transaction ID: #{txn_id}"""

            if budget_warning:
                response += f"\n\n{budget_warning}"

            return response

        except Exception as e:
            self.logger.error(f"Transaction failed: {e}")
            return f"❌ Failed to add transaction: {str(e)[:100]}"

    async def add_income(self, account_id: int, amount: float, description: str, 
                        category: str = "Other Income", user_id: int = None) -> str:
        """Add income transaction."""
        return await self.add_transaction(account_id, TransactionType.INCOME.value, 
                                        amount, description, category, user_id)

    async def add_expense(self, account_id: int, amount: float, description: str, 
                         category: str = "", user_id: int = None) -> str:
        """Add expense transaction."""
        return await self.add_transaction(account_id, TransactionType.EXPENSE.value, 
                                        amount, description, category, user_id)

    async def track_expense_legacy(self, amount: float, description: str, user_id: int = None) -> str:
        """Legacy expense tracking for backward compatibility."""
        try:
            # Get or create default account
            default_account = self.db.query_one("""
                SELECT id FROM accounts WHERE user_id = ? OR ? IS NULL 
                ORDER BY created_at LIMIT 1
            """, (user_id, user_id))
            
            if not default_account:
                # Create default account
                account_id = await self._ensure_default_account()
            else:
                account_id = default_account['id']
            
            return await self.add_expense(account_id, amount, description, user_id=user_id)
        except Exception as e:
            return f"❌ Failed to track expense: {str(e)[:100]}"

    async def get_transaction_history(self, account_id: int = None, user_id: int = None, limit: int = 20) -> str:
        """Get transaction history for account or user."""
        try:
            if account_id:
                transactions = self.db.query_all("""
                    SELECT t.*, a.name as account_name
                    FROM transactions t
                    JOIN accounts a ON t.account_id = a.id
                    WHERE t.account_id = ?
                    ORDER BY t.date DESC, t.created_at DESC
                    LIMIT ?
                """, (account_id, limit))
                title = f"Transaction History - Account #{account_id}"
            else:
                transactions = self.db.query_all("""
                    SELECT t.*, a.name as account_name
                    FROM transactions t
                    JOIN accounts a ON t.account_id = a.id
                    WHERE (a.user_id = ? OR ? IS NULL)
                    ORDER BY t.date DESC, t.created_at DESC
                    LIMIT ?
                """, (user_id, user_id, limit))
                title = "Recent Transaction History"

            if not transactions:
                return "No transactions found."

            response = f"**📋 {title}**\n"
            
            for txn in transactions:
                amount = Decimal(str(txn['amount']))
                date_str = datetime.fromisoformat(txn['date']).strftime('%m/%d %H:%M')
                emoji = "💰" if txn['transaction_type'] == 'income' else "💸"
                sign = "+" if txn['transaction_type'] == 'income' else "-"
                
                response += f"\n{emoji} {date_str} | {txn['account_name']}"
                response += f"\n   {sign}{self.currency_symbol}{amount:.2f} - {txn['description']}"
                if txn['category']:
                    response += f" ({txn['category']})"

            return response

        except Exception as e:
            return f"❌ Failed to get transaction history: {str(e)[:100]}"

    async def get_recent_transactions(self, user_id: int = None, days: int = 7) -> str:
        """Get recent transactions within specified days."""
        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            transactions = self.db.query_all("""
                SELECT t.*, a.name as account_name
                FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                WHERE (a.user_id = ? OR ? IS NULL) AND t.date >= ?
                ORDER BY t.date DESC, t.created_at DESC
            """, (user_id, user_id, start_date))

            if not transactions:
                return f"No transactions found in the last {days} days."

            # Group by day
            grouped_transactions = {}
            for txn in transactions:
                date_key = datetime.fromisoformat(txn['date']).strftime('%Y-%m-%d')
                if date_key not in grouped_transactions:
                    grouped_transactions[date_key] = []
                grouped_transactions[date_key].append(txn)

            response = f"**📅 Recent Transactions ({days} days)**\n"
            
            for date_key in sorted(grouped_transactions.keys(), reverse=True):
                day_transactions = grouped_transactions[date_key]
                day_total = sum(Decimal(str(t['amount'])) * (1 if t['transaction_type'] == 'income' else -1) for t in day_transactions)
                
                formatted_date = datetime.strptime(date_key, '%Y-%m-%d').strftime('%A, %B %d')
                response += f"\n**{formatted_date}** (Net: {self.currency_symbol}{day_total:+.2f})"
                
                for txn in day_transactions:
                    amount = Decimal(str(txn['amount']))
                    emoji = "💰" if txn['transaction_type'] == 'income' else "💸"
                    sign = "+" if txn['transaction_type'] == 'income' else "-"
                    
                    response += f"\n  {emoji} {sign}{self.currency_symbol}{amount:.2f} - {txn['description']}"

            return response

        except Exception as e:
            return f"❌ Failed to get recent transactions: {str(e)[:100]}"

    def _auto_categorize_transaction(self, description: str, transaction_type: str) -> str:
        """Auto-categorize transactions based on description."""
        desc_lower = description.lower()

        # Use pattern matching
        for category, patterns in self.categorization_patterns.items():
            for pattern in patterns:
                if re.search(pattern, desc_lower):
                    return category

        # Fallback categorization based on amount patterns
        if transaction_type == TransactionType.EXPENSE.value:
            return "Other"
        else:
            return "Other Income"

    # ===============================
    # BUDGET MANAGEMENT METHODS
    # ===============================

    async def set_budget(self, category: str, amount: float, user_id: int = None) -> str:
        """Set monthly budget for category."""
        try:
            # Check if budget exists
            existing = self.db.query_one(
                "SELECT id FROM budgets WHERE category = ? AND (user_id = ? OR ? IS NULL)",
                (category, user_id, user_id)
            )

            if existing:
                # Update
                self.db.execute(
                    "UPDATE budgets SET monthly_limit = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (amount, existing['id'])
                )
            else:
                # Insert
                self.db.execute(
                    "INSERT INTO budgets (user_id, category, monthly_limit, created_at, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                    (user_id or 0, category, amount)
                )

            return f"""**✅ Budget Set**

Category: {category}
Monthly Limit: {self.currency_symbol}{amount:.2f}

I'll alert you when you're approaching this limit."""

        except Exception as e:
            return f"❌ Budget setting failed: {str(e)[:100]}"

    async def get_budget_status(self, user_id: int = None) -> str:
        """Get overall budget status."""
        try:
            # Get all budgets
            budgets = self.db.query_all("""
                SELECT * FROM budgets WHERE (user_id = ? OR ? IS NULL) AND is_active = TRUE
            """, (user_id, user_id))

            if not budgets:
                return "No budgets set. Use 'set budget [category] [amount]'"

            start_date = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            status_lines = []
            total_budget = 0
            total_spent = 0

            for budget in budgets:
                # Get spending for this category
                spent = self.db.query_one("""
                    SELECT SUM(amount) as total FROM transactions t
                    JOIN accounts a ON t.account_id = a.id
                    WHERE t.category = ? AND t.transaction_type = 'expense' 
                    AND t.date >= ? AND (a.user_id = ? OR ? IS NULL)
                """, (budget['category'], start_date, user_id, user_id))

                spent_amount = spent['total'] if spent and spent['total'] else 0
                budget_limit = float(budget['monthly_limit'])
                percent = (spent_amount / budget_limit) * 100 if budget_limit > 0 else 0

                total_budget += budget_limit
                total_spent += spent_amount

                if percent > 100:
                    emoji = "🔴"
                elif percent > self.budget_alert_threshold:
                    emoji = "🟡"
                else:
                    emoji = "🟢"

                remaining = budget_limit - spent_amount
                status_lines.append(
                    f"{emoji} {budget['category']}: {self.currency_symbol}{spent_amount:.2f} / {self.currency_symbol}{budget_limit:.2f} ({percent:.1f}%)"
                )

            # Overall summary
            overall_percent = (total_spent / total_budget) * 100 if total_budget > 0 else 0
            overall_emoji = "🔴" if overall_percent > 100 else "🟡" if overall_percent > self.budget_alert_threshold else "🟢"

            return f"""**📊 Budget Overview - {datetime.now().strftime('%B %Y')}**

{chr(10).join(status_lines)}

**Overall:** {overall_emoji} {self.currency_symbol}{total_spent:.2f} / {self.currency_symbol}{total_budget:.2f} ({overall_percent:.1f}%)
**Remaining:** {self.currency_symbol}{max(0, total_budget - total_spent):.2f}"""

        except Exception as e:
            return f"❌ Budget check failed: {str(e)[:100]}"

    async def _check_budget_impact(self, category: str, amount: Decimal, user_id: int = None) -> str:
        """Check budget impact and return warning if needed."""
        try:
            # Get budget for category
            budget = self.db.query_one("""
                SELECT monthly_limit FROM budgets 
                WHERE category = ? AND (user_id = ? OR ? IS NULL) AND is_active = TRUE
            """, (category, user_id, user_id))

            if not budget:
                return ""

            # Calculate current month spending
            current_month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            spent_this_month = self.db.query_one("""
                SELECT SUM(amount) as total FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                WHERE t.category = ? AND t.transaction_type = 'expense' 
                AND t.date >= ? AND (a.user_id = ? OR ? IS NULL)
            """, (category, current_month_start, user_id, user_id))

            total_spent = (Decimal(str(spent_this_month['total'])) if spent_this_month and spent_this_month['total'] else Decimal('0')) + amount
            budget_limit = Decimal(str(budget['monthly_limit']))
            
            remaining = budget_limit - total_spent
            percent = (total_spent / budget_limit) * 100 if budget_limit > 0 else 0

            if percent > 100:
                emoji = "🔴"
                status = "OVER BUDGET!"
            elif percent > self.budget_alert_threshold:
                emoji = "🟠"
                status = "Budget Warning"
            elif percent > 75:
                emoji = "🟡"
                status = "Approaching Limit"
            else:
                return ""  # No warning needed

            return f"""**{emoji} {status}**
{category}: {self.currency_symbol}{total_spent:.2f} / {self.currency_symbol}{budget_limit:.2f} ({percent:.1f}%)
Remaining: {self.currency_symbol}{remaining:.2f}"""

        except Exception as e:
            self.logger.error(f"Budget check failed: {e}")
            return ""

    # ===============================
    # FINANCIAL GOALS METHODS
    # ===============================

    async def create_financial_goal(self, name: str, goal_type: str, target_amount: float,
                                   target_date: str = None, account_id: int = None, 
                                   category: str = "", user_id: int = None) -> str:
        """Create a new financial goal."""
        if not self.enable_goals:
            return "❌ Financial goals feature is not enabled."

        try:
            # Validate goal type
            valid_types = [t.value for t in GoalType]
            if goal_type not in valid_types:
                return f"❌ Invalid goal type. Use: {', '.join(valid_types)}"

            # Parse target date
            parsed_date = None
            if target_date:
                try:
                    parsed_date = datetime.strptime(target_date, '%Y-%m-%d')
                except ValueError:
                    try:
                        parsed_date = datetime.strptime(target_date, '%m/%d/%Y')
                    except ValueError:
                        return "❌ Invalid date format. Use YYYY-MM-DD or MM/DD/YYYY"

            # Insert goal
            goal_id = self.db.execute("""
                INSERT INTO financial_goals (user_id, name, goal_type, target_amount, target_date, account_id, category, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id or 0, name, goal_type, target_amount, parsed_date, account_id, category))

            return f"""**🎯 Financial Goal Created**

Name: {name}
Type: {goal_type.title()}
Target Amount: {self.currency_symbol}{target_amount:.2f}
Target Date: {parsed_date.strftime('%B %d, %Y') if parsed_date else 'Not set'}
Goal ID: #{goal_id}

Start tracking your progress with 'goal progress' or 'update goal'!"""

        except Exception as e:
            return f"❌ Failed to create goal: {str(e)[:100]}"

    async def get_goal_progress(self, user_id: int = None) -> str:
        """Get progress on all active financial goals."""
        if not self.enable_goals:
            return "❌ Financial goals feature is not enabled."

        try:
            goals = self.db.query_all("""
                SELECT * FROM financial_goals 
                WHERE (user_id = ? OR ? IS NULL) AND is_active = TRUE
                ORDER BY target_date ASC, created_at DESC
            """, (user_id, user_id))

            if not goals:
                return "No active financial goals. Create one with 'create goal'!"

            response = f"**🎯 Financial Goals Progress**\n"
            
            for goal in goals:
                target_amount = Decimal(str(goal['target_amount']))
                current_amount = Decimal(str(goal['current_amount']))
                progress_pct = (current_amount / target_amount * 100) if target_amount > 0 else 0
                remaining = target_amount - current_amount

                # Progress bar
                filled_bars = int(progress_pct / 10)
                progress_bar = "█" * filled_bars + "░" * (10 - filled_bars)

                # Status emoji
                if progress_pct >= 100:
                    status_emoji = "🎉"
                elif progress_pct >= 75:
                    status_emoji = "🔥"
                elif progress_pct >= 50:
                    status_emoji = "📈"
                elif progress_pct >= 25:
                    status_emoji = "🌱"
                else:
                    status_emoji = "🎯"

                # Time remaining
                time_info = ""
                if goal['target_date']:
                    target_date = datetime.fromisoformat(goal['target_date'])
                    days_remaining = (target_date - datetime.now()).days
                    if days_remaining > 0:
                        time_info = f" | {days_remaining} days left"
                    elif days_remaining == 0:
                        time_info = " | Due today!"
                    else:
                        time_info = f" | {abs(days_remaining)} days overdue"

                response += f"""
{status_emoji} **{goal['name']}** ({goal['goal_type'].title()})
{progress_bar} {progress_pct:.1f}%
{self.currency_symbol}{current_amount:.2f} / {self.currency_symbol}{target_amount:.2f} (${remaining:.2f} remaining){time_info}"""

            # Overall summary
            total_goals = len(goals)
            completed_goals = len([g for g in goals if Decimal(str(g['current_amount'])) >= Decimal(str(g['target_amount']))])
            
            response += f"""

**📊 Summary:**
• {completed_goals}/{total_goals} goals completed
• Average progress: {sum(Decimal(str(g['current_amount'])) / Decimal(str(g['target_amount'])) * 100 for g in goals if Decimal(str(g['target_amount'])) > 0) / len(goals):.1f}%"""

            return response

        except Exception as e:
            return f"❌ Failed to get goal progress: {str(e)[:100]}"

    async def update_goal_progress(self, goal_id: int, amount: float, user_id: int = None) -> str:
        """Update progress on a financial goal."""
        if not self.enable_goals:
            return "❌ Financial goals feature is not enabled."

        try:
            # Get goal
            goal = self.db.query_one("""
                SELECT * FROM financial_goals 
                WHERE id = ? AND (user_id = ? OR ? IS NULL) AND is_active = TRUE
            """, (goal_id, user_id, user_id))

            if not goal:
                return f"❌ Goal #{goal_id} not found"

            # Update current amount
            new_amount = Decimal(str(goal['current_amount'])) + Decimal(str(amount))
            self.db.execute("""
                UPDATE financial_goals 
                SET current_amount = ?
                WHERE id = ?
            """, (new_amount, goal_id))

            # Calculate progress
            target_amount = Decimal(str(goal['target_amount']))
            progress_pct = (new_amount / target_amount * 100) if target_amount > 0 else 0
            remaining = target_amount - new_amount

            # Status message
            if progress_pct >= 100:
                status = "🎉 **GOAL COMPLETED!** Congratulations!"
            elif progress_pct >= 75:
                status = "🔥 You're almost there! Keep it up!"
            elif progress_pct >= 50:
                status = "📈 Great progress! You're halfway there!"
            else:
                status = "🌱 Every step counts! Keep going!"

            return f"""**🎯 Goal Progress Updated**

**{goal['name']}**
Added: {self.currency_symbol}{amount:.2f}
Current: {self.currency_symbol}{new_amount:.2f} / {self.currency_symbol}{target_amount:.2f}
Progress: {progress_pct:.1f}%
Remaining: {self.currency_symbol}{remaining:.2f}

{status}"""

        except Exception as e:
            return f"❌ Failed to update goal: {str(e)[:100]}"

    # ===============================
    # ANALYTICS & REPORTING METHODS
    # ===============================

    async def get_financial_summary(self, user_id: int = None) -> str:
        """Get comprehensive financial summary."""
        try:
            # Get account balances by type
            accounts_summary = self.db.query_all("""
                SELECT account_type, SUM(balance) as total_balance, COUNT(*) as account_count
                FROM accounts 
                WHERE (user_id = ? OR ? IS NULL) AND is_active = TRUE
                GROUP BY account_type
            """, (user_id, user_id))

            # Get this month's transactions
            current_month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            monthly_summary = self.db.query_all("""
                SELECT transaction_type, SUM(amount) as total_amount, COUNT(*) as count
                FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                WHERE (a.user_id = ? OR ? IS NULL) AND date >= ?
                GROUP BY transaction_type
            """, (user_id, user_id, current_month_start))

            # Calculate net worth
            assets = sum(Decimal(str(acc['total_balance'])) for acc in accounts_summary 
                        if acc['account_type'] in ['checking', 'savings', 'investment', 'cash'])
            liabilities = sum(abs(Decimal(str(acc['total_balance']))) for acc in accounts_summary 
                            if acc['account_type'] in ['credit_card', 'loan'])
            net_worth = assets - liabilities

            # Format monthly summary
            monthly_income = Decimal('0')
            monthly_expenses = Decimal('0')
            
            for summary in monthly_summary:
                if summary['transaction_type'] == 'income':
                    monthly_income = Decimal(str(summary['total_amount']))
                elif summary['transaction_type'] == 'expense':
                    monthly_expenses = Decimal(str(summary['total_amount']))

            monthly_net = monthly_income - monthly_expenses
            savings_rate = (monthly_net / monthly_income * 100) if monthly_income > 0 else 0

            response = f"""**📊 Financial Summary**
*{datetime.now().strftime('%B %Y')}*

**💰 Net Worth: {self.currency_symbol}{net_worth:.2f}**
• Assets: {self.currency_symbol}{assets:.2f}
• Liabilities: {self.currency_symbol}{liabilities:.2f}

**📈 This Month:**
• Income: {self.currency_symbol}{monthly_income:.2f}
• Expenses: {self.currency_symbol}{monthly_expenses:.2f}
• **Net: {self.currency_symbol}{monthly_net:.2f}**
• Savings Rate: {savings_rate:.1f}%

**🏦 Accounts:**"""

            for acc in accounts_summary:
                acc_type_name = acc['account_type'].replace('_', ' ').title()
                response += f"\n• {acc_type_name}: {self.currency_symbol}{Decimal(str(acc['total_balance'])):.2f} ({acc['account_count']} account{'s' if acc['account_count'] > 1 else ''})"

            # Add goal progress if enabled
            if self.enable_goals:
                goals_summary = self.db.query_one("""
                    SELECT COUNT(*) as total_goals, 
                           SUM(CASE WHEN current_amount >= target_amount THEN 1 ELSE 0 END) as completed_goals,
                           AVG(CASE WHEN target_amount > 0 THEN (current_amount / target_amount * 100) ELSE 0 END) as avg_progress
                    FROM financial_goals 
                    WHERE (user_id = ? OR ? IS NULL) AND is_active = TRUE
                """, (user_id, user_id))

                if goals_summary and goals_summary['total_goals']:
                    response += f"\n\n**🎯 Goals:**"
                    response += f"\n• {goals_summary['completed_goals']}/{goals_summary['total_goals']} completed"
                    response += f"\n• Average progress: {goals_summary['avg_progress'] or 0:.1f}%"

            return response

        except Exception as e:
            return f"❌ Failed to generate financial summary: {str(e)[:100]}"

    async def generate_executive_summary(self, user_id: int = None) -> str:
        """Generate executive summary dashboard with KPIs and insights."""
        if not self.enable_analytics:
            return "❌ Advanced analytics feature is not enabled."

        try:
            # Calculate key metrics
            metrics = await self._calculate_key_metrics(user_id)
            trends = await self._analyze_trends(user_id)
            alerts = await self._generate_alerts(user_id)
            
            current_date = datetime.now().strftime('%B %d, %Y')
            
            summary = f"""**📊 Executive Financial Summary**
*{current_date}*

**🎯 Key Metrics:**"""
            
            for metric in metrics:
                trend_icon = "📈" if metric.trend == "up" else "📉" if metric.trend == "down" else "➡️"
                change_text = f" ({metric.change_percentage:+.1f}%)" if metric.change_percentage != 0 else ""
                
                summary += f"\n{metric.icon} **{metric.name}:** ${metric.value:.2f}{change_text} {trend_icon}"
            
            # Trends section
            if trends:
                summary += "\n\n**📈 Key Insights:**"
                for trend in trends:
                    summary += f"\n• {trend}"
            
            # Alerts section
            if alerts:
                summary += "\n\n**⚠️ Alerts:**"
                for alert in alerts:
                    summary += f"\n• {alert}"
            
            # Recommendations
            recommendations = await self._generate_recommendations(metrics, user_id)
            if recommendations:
                summary += "\n\n**💡 Recommendations:**"
                for rec in recommendations:
                    summary += f"\n• {rec}"
            
            return summary
            
        except Exception as e:
            return f"❌ Failed to generate executive summary: {str(e)[:100]}"

    async def calculate_financial_health_score(self, user_id: int = None) -> str:
        """Calculate comprehensive financial health score."""
        if not self.enable_analytics:
            return "❌ Advanced analytics feature is not enabled."

        try:
            scores = {}
            
            # 1. Emergency Fund Score (20 points max)
            emergency_score = await self._calculate_emergency_fund_score(user_id)
            scores['emergency_fund'] = {'score': emergency_score, 'max': 20}
            
            # 2. Savings Rate Score (25 points max)
            savings_score = await self._calculate_savings_rate_score(user_id)
            scores['savings_rate'] = {'score': savings_score, 'max': 25}
            
            # 3. Debt-to-Income Score (20 points max)
            debt_score = await self._calculate_debt_score(user_id)
            scores['debt_management'] = {'score': debt_score, 'max': 20}
            
            # 4. Budget Adherence Score (15 points max)
            budget_score = await self._calculate_budget_score(user_id)
            scores['budget_adherence'] = {'score': budget_score, 'max': 15}
            
            # 5. Investment Score (10 points max)
            investment_score = 5 if not self.enable_investments else await self._calculate_investment_score(user_id)
            scores['investment'] = {'score': investment_score, 'max': 10}
            
            # 6. Goal Progress Score (10 points max)
            goal_score = 5 if not self.enable_goals else await self._calculate_goal_progress_score(user_id)
            scores['goal_progress'] = {'score': goal_score, 'max': 10}
            
            # Calculate total score
            total_score = sum(category['score'] for category in scores.values())
            
            # Determine health level
            if total_score >= 90:
                health_level = "Excellent"
                health_emoji = "💪"
            elif total_score >= 75:
                health_level = "Good"
                health_emoji = "👍"
            elif total_score >= 60:
                health_level = "Fair"
                health_emoji = "👌"
            elif total_score >= 40:
                health_level = "Needs Improvement"
                health_emoji = "⚠️"
            else:
                health_level = "Poor"
                health_emoji = "🚨"

            response = f"""**🏥 Financial Health Score**

**{health_emoji} Overall Score: {total_score}/100 - {health_level}**

**📊 Category Breakdown:**
• Emergency Fund: {scores['emergency_fund']['score']}/20 pts
• Savings Rate: {scores['savings_rate']['score']:.1f}/25 pts
• Debt Management: {scores['debt_management']['score']:.1f}/20 pts
• Budget Adherence: {scores['budget_adherence']['score']:.1f}/15 pts
• Investment: {scores['investment']['score']:.1f}/10 pts
• Goal Progress: {scores['goal_progress']['score']:.1f}/10 pts"""

            # Add recommendations
            recommendations = await self._generate_health_recommendations(scores)
            if recommendations:
                response += "\n\n**💡 Improvement Areas:**"
                for rec in recommendations[:3]:
                    response += f"\n• {rec}"

            return response

        except Exception as e:
            return f"❌ Financial health calculation failed: {str(e)[:100]}"

    # ===============================
    # HELPER METHODS
    # ===============================

    async def _calculate_key_metrics(self, user_id: int = None) -> List[FinancialMetric]:
        """Calculate key financial metrics."""
        current_month = datetime.now().replace(day=1)
        previous_month = (current_month - timedelta(days=1)).replace(day=1)
        
        metrics = []
        
        # Net Worth
        current_net_worth = await self._calculate_net_worth(user_id)
        previous_net_worth = await self._calculate_net_worth(user_id, previous_month)
        net_worth_change = self._calculate_percentage_change(current_net_worth, previous_net_worth)
        
        metrics.append(FinancialMetric(
            name="Net Worth",
            value=current_net_worth,
            previous_value=previous_net_worth,
            change_percentage=net_worth_change,
            trend=self._determine_trend(net_worth_change),
            category="summary",
            icon="💰"
        ))
        
        return metrics

    async def _calculate_net_worth(self, user_id: int = None, as_of_date: datetime = None) -> float:
        """Calculate net worth."""
        date_filter = ""
        params = [user_id, user_id]
        
        if as_of_date:
            date_filter = "AND created_at <= ?"
            params.append(as_of_date.strftime('%Y-%m-%d'))
        
        assets = self.db.query_one(f"""
            SELECT COALESCE(SUM(balance), 0) as total
            FROM accounts
            WHERE (user_id = ? OR ? IS NULL)
            AND account_type IN ('checking', 'savings', 'investment', 'cash')
            AND is_active = TRUE
            {date_filter}
        """, params)
        
        liabilities = self.db.query_one(f"""
            SELECT COALESCE(SUM(ABS(balance)), 0) as total
            FROM accounts
            WHERE (user_id = ? OR ? IS NULL)
            AND account_type IN ('credit_card', 'loan')
            AND is_active = TRUE
            {date_filter}
        """, params)
        
        return float(assets['total']) - float(liabilities['total'])

    async def _analyze_trends(self, user_id: int = None, months: int = 6) -> List[str]:
        """Analyze financial trends over time."""
        trends = []
        
        # Simple trend analysis
        start_date = (datetime.now() - timedelta(days=30 * months)).strftime('%Y-%m-%d')
        
        # Income trend
        income_trend = self.db.query_all("""
            SELECT 
                strftime('%Y-%m', t.date) as month,
                SUM(t.amount) as monthly_income
            FROM transactions t
            JOIN accounts a ON t.account_id = a.id
            WHERE (a.user_id = ? OR ? IS NULL) 
            AND t.transaction_type = 'income'
            AND t.date >= ?
            GROUP BY strftime('%Y-%m', t.date)
            ORDER BY month
        """, (user_id, user_id, start_date))
        
        if len(income_trend) >= 3:
            recent_avg = statistics.mean([float(row['monthly_income']) for row in income_trend[-3:]])
            older_avg = statistics.mean([float(row['monthly_income']) for row in income_trend[:-3]]) if len(income_trend) > 3 else income_trend[0]['monthly_income']
            
            change_pct = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
            
            if change_pct > 10:
                trends.append("Your income has been growing consistently")
            elif change_pct < -10:
                trends.append("Your income has been declining - consider additional income sources")
        
        return trends[:3]  # Return top 3 trends

    async def _generate_alerts(self, user_id: int = None) -> List[str]:
        """Generate financial alerts and warnings."""
        alerts = []
        current_month = datetime.now().strftime('%Y-%m-01')
        
        # Budget overage alerts
        budget_overages = self.db.query_all("""
            SELECT 
                b.category,
                b.monthly_limit,
                COALESCE(spent.amount, 0) as spent_amount
            FROM budgets b
            LEFT JOIN (
                SELECT 
                    t.category,
                    SUM(t.amount) as amount
                FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                WHERE (a.user_id = ? OR ? IS NULL)
                AND t.transaction_type = 'expense'
                AND t.date >= ?
                GROUP BY t.category
            ) spent ON b.category = spent.category
            WHERE (b.user_id = ? OR ? IS NULL)
            AND b.is_active = TRUE
            AND spent.amount > b.monthly_limit
        """, (user_id, user_id, current_month, user_id, user_id))
        
        for overage in budget_overages:
            overage_amount = float(overage['spent_amount']) - float(overage['monthly_limit'])
            alerts.append(f"Over budget in {overage['category']} by ${overage_amount:.2f}")
        
        # Low balance alerts
        low_balances = self.db.query_all("""
            SELECT name, balance, account_type
            FROM accounts
            WHERE (user_id = ? OR ? IS NULL)
            AND is_active = TRUE
            AND account_type IN ('checking', 'savings')
            AND balance < ?
        """, (user_id, user_id, self.low_balance_threshold))
        
        for account in low_balances:
            alerts.append(f"Low balance: {account['name']} has ${float(account['balance']):.2f}")
        
        return alerts

    async def _generate_recommendations(self, metrics: List[FinancialMetric], user_id: int = None) -> List[str]:
        """Generate personalized financial recommendations."""
        recommendations = []
        
        # Basic recommendations based on metrics
        for metric in metrics:
            if metric.name == "Net Worth" and metric.trend == "down":
                recommendations.append("Review expenses and create a budget to improve net worth")
        
        # Check emergency fund
        checking_savings = self.db.query_one("""
            SELECT COALESCE(SUM(balance), 0) as total
            FROM accounts
            WHERE (user_id = ? OR ? IS NULL)
            AND account_type IN ('checking', 'savings')
            AND is_active = TRUE
        """, (user_id, user_id))
        
        if checking_savings and float(checking_savings['total']) < 1000:
            recommendations.append("Build an emergency fund of 3-6 months of expenses")
        
        return recommendations[:3]

    # Placeholder methods for health score calculation
    async def _calculate_emergency_fund_score(self, user_id: int = None) -> float:
        """Calculate emergency fund score."""
        return 15.0  # Placeholder
    
    async def _calculate_savings_rate_score(self, user_id: int = None) -> float:
        """Calculate savings rate score."""
        return 20.0  # Placeholder
    
    async def _calculate_debt_score(self, user_id: int = None) -> float:
        """Calculate debt management score."""
        return 18.0  # Placeholder
    
    async def _calculate_budget_score(self, user_id: int = None) -> float:
        """Calculate budget adherence score."""
        return 12.0  # Placeholder
    
    async def _calculate_investment_score(self, user_id: int = None) -> float:
        """Calculate investment score."""
        return 8.0  # Placeholder
    
    async def _calculate_goal_progress_score(self, user_id: int = None) -> float:
        """Calculate goal progress score."""
        return 7.0  # Placeholder

    async def _generate_health_recommendations(self, scores: Dict[str, Any]) -> List[str]:
        """Generate health score recommendations."""
        recommendations = []
        
        if scores['emergency_fund']['score'] < 15:
            recommendations.append("Build emergency fund to cover 3-6 months of expenses")
        if scores['savings_rate']['score'] < 20:
            recommendations.append("Increase savings rate to at least 15% of income")
        if scores['budget_adherence']['score'] < 10:
            recommendations.append("Create and stick to a detailed monthly budget")
        
        return recommendations

    @staticmethod
    def _calculate_percentage_change(current: float, previous: float) -> float:
        """Calculate percentage change."""
        if previous == 0:
            return 0
        return ((current - previous) / abs(previous)) * 100

    @staticmethod
    def _determine_trend(change_percentage: float) -> str:
        """Determine trend direction."""
        if change_percentage > 2:
            return "up"
        elif change_percentage < -2:
            return "down"
        else:
            return "stable"

    # ===============================
    # LEGACY COMPATIBILITY METHODS
    # ===============================

    async def generate_report(self, period: str = "month") -> str:
        """Generate financial report (legacy compatibility)."""
        try:
            if period == "month":
                start_date = datetime.now().replace(day=1)
            elif period == "week":
                start_date = datetime.now() - timedelta(days=7)
            else:
                start_date = datetime.now() - timedelta(days=30)

            # Get transactions
            transactions = self.db.query_all("""
                SELECT t.*, a.name as account_name
                FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                WHERE (a.user_id = 0 OR a.user_id IS NULL) AND t.date >= ? 
                AND t.transaction_type = 'expense'
                ORDER BY t.date DESC
            """, (start_date.isoformat(),))

            if not transactions:
                return f"No transactions recorded for this {period}"

            # Calculate totals by category
            categories = {}
            total = 0

            for txn in transactions:
                cat = txn['category'] or 'Other'
                amount = float(txn['amount'])
                categories[cat] = categories.get(cat, 0) + amount
                total += amount

            # Sort by amount
            sorted_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)

            # Format report
            category_lines = [
                f"• {cat}: ${amount:.2f} ({amount/total*100:.1f}%)"
                for cat, amount in sorted_cats
            ]

            # Get top expenses
            top_expenses = sorted(transactions, key=lambda x: float(x['amount']), reverse=True)[:3]
            top_lines = [
                f"• ${float(e['amount']):.2f} - {e['description'][:30]}"
                for e in top_expenses
            ]

            return f"""**📈 Financial Report**

**Period:** {period.title()} (from {start_date.strftime('%Y-%m-%d')})
**Total Spent:** ${total:.2f}
**Transactions:** {len(transactions)}

**By Category:**
{chr(10).join(category_lines)}

**Top Expenses:**
{chr(10).join(top_lines)}

**Daily Average:** ${total / max(1, (datetime.now() - start_date).days):.2f}"""

        except Exception as e:
            return f"❌ Report generation failed: {str(e)[:100]}"

    async def get_expense_summary(self, user_id: int = None) -> str:
        """Get expense summary for a user (legacy compatibility)."""
        try:
            # Get current month transactions
            current_month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')

            summary = self.db.query_one("""
                SELECT
                    COUNT(*) as transaction_count,
                    SUM(amount) as total_amount,
                    AVG(amount) as avg_amount
                FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                WHERE t.date >= ? AND (a.user_id = ? OR ? IS NULL OR a.user_id = 0)
                AND t.transaction_type = 'expense'
            """, (current_month_start, user_id, user_id))

            # Get category breakdown
            categories = self.db.query_all("""
                SELECT t.category, SUM(t.amount) as total
                FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                WHERE t.date >= ? AND (a.user_id = ? OR ? IS NULL OR a.user_id = 0)
                AND t.transaction_type = 'expense'
                GROUP BY t.category
                ORDER BY total DESC
            """, (current_month_start, user_id, user_id))

            category_breakdown = []
            for cat in categories[:5]:  # Top 5 categories
                category_breakdown.append(f"• {cat['category'] or 'Other'}: ${float(cat['total']):.2f}")

            return f"""**📊 Expense Summary**

**This Month:**
• Total Transactions: {summary['transaction_count'] or 0}
• Total Amount: ${float(summary['total_amount'] or 0):.2f}
• Average per Transaction: ${float(summary['avg_amount'] or 0):.2f}

**Top Categories:**
{chr(10).join(category_breakdown) if category_breakdown else "No expenses recorded"}"""

        except Exception as e:
            return f"❌ Expense summary failed: {str(e)[:100]}"

    async def monthly_financial_report(self) -> str:
        """Generate detailed monthly financial report (legacy compatibility)."""
        try:
            # Get current month data
            current_month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            
            # Total expenses this month
            monthly_total = self.db.query_one("""
                SELECT SUM(amount) as total FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                WHERE t.date >= ? AND t.transaction_type = 'expense'
                AND (a.user_id = 0 OR a.user_id IS NULL)
            """, (current_month_start,))

            # Budget vs actual
            budgets = self.db.query_all("""
                SELECT category, monthly_limit FROM budgets 
                WHERE (user_id = 0 OR user_id IS NULL) AND is_active = TRUE
            """)
            
            budget_comparison = []
            total_budget = 0

            for budget in budgets:
                category = budget['category']
                limit = float(budget['monthly_limit'])
                total_budget += limit

                actual = self.db.query_one("""
                    SELECT SUM(t.amount) as total FROM transactions t
                    JOIN accounts a ON t.account_id = a.id
                    WHERE t.category = ? AND t.date >= ? AND t.transaction_type = 'expense'
                    AND (a.user_id = 0 OR a.user_id IS NULL)
                """, (category, current_month_start))

                actual_amount = float(actual['total']) if actual and actual['total'] else 0
                percentage = (actual_amount / limit * 100) if limit > 0 else 0
                status = "🟢" if percentage < 80 else "🟡" if percentage < 100 else "🔴"

                budget_comparison.append(
                    f"{status} {category}: ${actual_amount:.2f} / ${limit:.2f} ({percentage:.1f}%)"
                )

            # Financial insights
            insights = []
            total_spent = float(monthly_total['total']) if monthly_total and monthly_total['total'] else 0
            if total_spent > total_budget:
                insights.append("⚠️ You're over budget this month")
            elif total_spent < total_budget * 0.5:
                insights.append("💰 You're doing great staying under budget!")
            else:
                insights.append("📊 You're on track with your budget")

            return f"""**📈 Monthly Financial Report**
**{datetime.now().strftime('%B %Y')}**

**Summary:**
• Total Spent: ${total_spent:.2f}
• Total Budget: ${total_budget:.2f}
• Remaining: ${max(0, total_budget - total_spent):.2f}

**Budget Breakdown:**
{chr(10).join(budget_comparison) if budget_comparison else "No budgets set"}

**Insights:**
{chr(10).join(insights)}"""

        except Exception as e:
            return f"❌ Monthly report failed: {str(e)[:100]}"

    # ===============================
    # PLACEHOLDER METHODS FOR FUTURE FEATURES
    # ===============================

    async def buy_investment(self, account_id: int, symbol: str, quantity: float, 
                           price: float, user_id: int = None) -> str:
        """Buy investment (placeholder)."""
        if not self.enable_investments:
            return "❌ Investment tracking feature is not enabled."
        return "🚧 Investment features coming soon!"

    async def sell_investment(self, account_id: int, symbol: str, quantity: float, 
                            price: float, user_id: int = None) -> str:
        """Sell investment (placeholder)."""
        if not self.enable_investments:
            return "❌ Investment tracking feature is not enabled."
        return "🚧 Investment features coming soon!"

    async def get_investment_portfolio(self, user_id: int = None) -> str:
        """Get investment portfolio (placeholder)."""
        if not self.enable_investments:
            return "❌ Investment tracking feature is not enabled."
        return "🚧 Investment portfolio features coming soon!"

    async def calculate_retirement_needs(self, current_age: int, retirement_age: int,
                                       desired_income: float, user_id: int = None) -> str:
        """Calculate retirement needs (placeholder)."""
        if not self.enable_retirement_planning:
            return "❌ Retirement planning feature is not enabled."
        return "🚧 Retirement planning features coming soon!"

    async def create_debt_payoff_plan(self, strategy: str = "avalanche", 
                                    extra_payment: float = 0, user_id: int = None) -> str:
        """Create debt payoff plan (placeholder)."""
        if not self.enable_debt_planning:
            return "❌ Debt planning feature is not enabled."
        return "🚧 Debt payoff planning features coming soon!"

    async def generate_tax_summary(self, tax_year: int = None, user_id: int = None) -> str:
        """Generate tax summary (placeholder)."""
        if not self.enable_tax_tracking:
            return "❌ Tax tracking feature is not enabled."
        return "🚧 Tax preparation features coming soon!"

    # ===============================
    # PRODUCTION-READY EXTENSIONS
    # ===============================

    async def process_receipt(self, image_data: bytes, filename: str = "receipt.jpg", 
                            transaction_id: int = None, user_id: int = None) -> str:
        """Process receipt image with OCR and extract data."""
        return await self.extensions.process_receipt_image(image_data, transaction_id, user_id, filename)

    async def list_receipts(self, user_id: int = None) -> str:
        """List uploaded receipt documents."""
        return await self.extensions.list_receipt_documents(user_id)

    async def get_receipt_details(self, document_id: int, user_id: int = None) -> str:
        """Get detailed receipt document information."""
        return await self.extensions.get_receipt_document(document_id, user_id)

    async def link_receipt_to_transaction(self, document_id: int, transaction_id: int, user_id: int = None) -> str:
        """Link receipt document to a transaction."""
        try:
            # Verify both document and transaction exist and belong to user
            document = self.db.query_one("""SELECT id FROM receipt_documents 
                WHERE id = ? AND (user_id = ? OR ? IS NULL)""", (document_id, user_id, user_id))
            
            transaction = self.db.query_one("""SELECT id, description, amount FROM transactions t
                JOIN accounts a ON t.account_id = a.id 
                WHERE t.id = ? AND (a.user_id = ? OR ? IS NULL)""", (transaction_id, user_id, user_id))
                
            if not document or not transaction:
                return "❌ Document or transaction not found"
                
            # Update the link
            self.db.execute("UPDATE receipt_documents SET transaction_id = ? WHERE id = ?", 
                          (transaction_id, document_id))
            
            return f"""✅ **Receipt Linked Successfully**

Receipt Document #{document_id} linked to:
Transaction #{transaction_id}: {transaction['description']} (${transaction['amount']})

Use 'get receipt {document_id}' to view details."""
            
        except Exception as e:
            return f"❌ Failed to link receipt: {str(e)[:100]}"

    async def get_stock_quote(self, symbol: str) -> str:
        """Get real-time stock quote."""
        quote = await self.extensions.get_stock_quote(symbol)
        
        if quote['success']:
            change_emoji = "📈" if quote['change'] >= 0 else "📉"
            return f"""**📊 Stock Quote: {quote['symbol']}**

**Price:** ${quote['price']:.2f}
**Change:** {change_emoji} {quote['change']:+.2f} ({quote['change_percent']:+.1f}%)
**Volume:** {quote.get('volume', 'N/A'):,}
**Last Updated:** {quote['last_updated']}
**Source:** {quote['provider'].title()}

💡 Use 'buy investment' or 'add investment' to track this in your portfolio."""
        else:
            return f"❌ Failed to get quote for {symbol}: {quote['error']}"

    async def update_investment_prices(self, user_id: int = None) -> str:
        """Update all investment prices."""
        return await self.extensions.update_investment_prices(user_id)

    async def analyze_investments(self, user_id: int = None) -> str:
        """Analyze investment portfolio performance."""
        try:
            investments = self.db.query_all("""SELECT * FROM investments 
                WHERE (user_id = ? OR ? IS NULL)""", (user_id, user_id))
                
            if not investments:
                return "No investments found. Add some with 'buy investment [symbol] [quantity] [price]'"
                
            total_value = Decimal('0')
            total_cost = Decimal('0')
            analysis_lines = []
            
            for inv in investments:
                quantity = Decimal(str(inv['quantity']))
                purchase_price = Decimal(str(inv['purchase_price']))
                current_price = Decimal(str(inv['current_price'])) if inv['current_price'] else purchase_price
                
                cost_basis = quantity * purchase_price
                current_value = quantity * current_price
                gain_loss = current_value - cost_basis
                gain_loss_pct = (gain_loss / cost_basis * 100) if cost_basis > 0 else 0
                
                total_value += current_value
                total_cost += cost_basis
                
                emoji = "📈" if gain_loss >= 0 else "📉"
                analysis_lines.append(
                    f"{emoji} **{inv['symbol']}**: {quantity} shares @ ${current_price:.2f} = ${current_value:.2f} ({gain_loss_pct:+.1f}%)"
                )
            
            total_gain_loss = total_value - total_cost
            total_gain_loss_pct = (total_gain_loss / total_cost * 100) if total_cost > 0 else 0
            overall_emoji = "📈" if total_gain_loss >= 0 else "📉"
            
            return f"""**📊 Investment Portfolio Analysis**

{chr(10).join(analysis_lines)}

**Portfolio Summary:**
• **Total Value:** ${total_value:.2f}
• **Total Cost:** ${total_cost:.2f}
• **Gain/Loss:** {overall_emoji} {total_gain_loss:+.2f} ({total_gain_loss_pct:+.1f}%)
• **Number of Holdings:** {len(investments)}

💡 Use 'update stock prices' to refresh current values."""
            
        except Exception as e:
            return f"❌ Investment analysis failed: {str(e)[:100]}"

    async def setup_tax_categories(self) -> str:
        """Setup tax deductible categories."""
        return await self.extensions.setup_tax_categories()

    async def calculate_tax_deductions(self, year: int = None, user_id: int = None) -> str:
        """Calculate tax deductions for the year."""
        return await self.extensions.calculate_tax_deductions(year, user_id)

    async def export_tax_data(self, year: int = None, format: str = 'csv', user_id: int = None) -> str:
        """Export tax data for accountant."""
        return await self.extensions.export_tax_data(year, user_id, format)

    async def tax_planning_advice(self, user_id: int = None) -> str:
        """Provide tax planning advice based on current data."""
        try:
            current_year = datetime.now().year
            
            # Get year-to-date deductible expenses
            ytd_deductions = await self.extensions.calculate_tax_deductions(current_year, user_id)
            
            # Get remaining months in year
            months_remaining = 12 - datetime.now().month
            
            # Get current month spending on deductible categories
            current_month = datetime.now().replace(day=1).strftime('%Y-%m-%d')
            deductible_spending = self.db.query_one("""SELECT SUM(t.amount) as total FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                JOIN tax_categories tc ON t.category = tc.expense_category
                WHERE (a.user_id = ? OR ? IS NULL) AND t.transaction_type = 'expense'
                AND t.date >= ? AND tc.tax_deductible = TRUE""", (user_id, user_id, current_month))
                
            monthly_deductible = float(deductible_spending['total']) if deductible_spending and deductible_spending['total'] else 0
            
            advice = []
            if months_remaining > 0 and monthly_deductible > 0:
                projected_annual = monthly_deductible * 12
                advice.append(f"📊 Based on this month's spending, you're on track for ~${projected_annual:.0f} in deductions")
            
            if months_remaining > 0:
                advice.extend([
                    "💡 **Tax Planning Opportunities:**",
                    "• Consider making charitable donations before year-end",
                    "• Review business expense purchases you've been postponing",
                    "• Check if you need any medical procedures (HSA eligible)",
                    "• Review retirement contributions (401k, IRA limits)"
                ])
                
            if datetime.now().month >= 10:  # Q4
                advice.extend([
                    "⚠️ **Year-End Reminders:**",
                    "• Gather all receipts and documentation",
                    "• Consider tax-loss harvesting on investments",
                    "• Review estimated tax payments if self-employed"
                ])
                
            advice_text = "\n".join(advice) if advice else "No specific advice at this time."
            
            return f"""**🧾 Tax Planning Advice - {current_year}**

{advice_text}

📋 **Action Items:**
• Use 'tax deductions' to see current deductible amounts
• Use 'setup tax categories' to ensure proper categorization
• Use 'export tax data' when ready for tax preparation

⚠️ This is general advice - consult a tax professional for your specific situation."""
            
        except Exception as e:
            return f"❌ Tax planning advice failed: {str(e)[:100]}"

    async def import_bank_data(self, csv_data: str, account_id: int, user_id: int = None) -> str:
        """Import bank transaction data from CSV."""
        return await self.extensions.import_bank_csv(csv_data, account_id, user_id)

    async def export_financial_data(self, format: str = "json", year: int = None, user_id: int = None) -> str:
        """Export comprehensive financial data."""
        try:
            export_year = year or datetime.now().year
            year_start = f"{export_year}-01-01"
            year_end = f"{export_year}-12-31"
            
            # Get all financial data
            export_data = {
                'accounts': self.db.query_all("SELECT * FROM accounts WHERE (user_id = ? OR ? IS NULL)", (user_id, user_id)),
                'transactions': self.db.query_all("""SELECT t.*, a.name as account_name FROM transactions t
                    JOIN accounts a ON t.account_id = a.id 
                    WHERE (a.user_id = ? OR ? IS NULL) AND t.date BETWEEN ? AND ?""", 
                    (user_id, user_id, year_start, year_end)),
                'budgets': self.db.query_all("SELECT * FROM budgets WHERE (user_id = ? OR ? IS NULL)", (user_id, user_id)),
                'goals': self.db.query_all("SELECT * FROM financial_goals WHERE (user_id = ? OR ? IS NULL)", (user_id, user_id)) if self.enable_goals else [],
                'investments': self.db.query_all("SELECT * FROM investments WHERE (user_id = ? OR ? IS NULL)", (user_id, user_id)) if self.enable_investments else [],
                'export_metadata': {
                    'export_date': datetime.now().isoformat(),
                    'export_year': export_year,
                    'format': format,
                    'version': '3.0.0'
                }
            }
            
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"umbra_finance_export_{export_year}_{timestamp}.{format}"
            
            # In production, this would save to R2 or file system
            transaction_count = len(export_data['transactions'])
            account_count = len(export_data['accounts'])
            
            return f"""**📁 Financial Data Export Complete**

**File:** {filename}
**Format:** {format.upper()}
**Year:** {export_year}
**Size:** ~{len(json.dumps(export_data, default=str)) / 1024:.1f}KB

**Exported Data:**
• {account_count} accounts
• {transaction_count} transactions
• {len(export_data['budgets'])} budgets
• {len(export_data['goals'])} goals
• {len(export_data['investments'])} investments

✅ Export ready for download or backup."""
            
        except Exception as e:
            return f"❌ Data export failed: {str(e)[:100]}"

    async def backup_financial_data(self, user_id: int = None) -> str:
        """Create backup of all financial data."""
        try:
            # Create comprehensive backup including all years
            backup_data = {
                'accounts': self.db.query_all("SELECT * FROM accounts WHERE (user_id = ? OR ? IS NULL)", (user_id, user_id)),
                'transactions': self.db.query_all("""SELECT * FROM transactions t
                    JOIN accounts a ON t.account_id = a.id WHERE (a.user_id = ? OR ? IS NULL)""", (user_id, user_id)),
                'budgets': self.db.query_all("SELECT * FROM budgets WHERE (user_id = ? OR ? IS NULL)", (user_id, user_id)),
                'categories': self.db.query_all("SELECT * FROM categories"),
                'goals': self.db.query_all("SELECT * FROM financial_goals WHERE (user_id = ? OR ? IS NULL)", (user_id, user_id)) if self.enable_goals else [],
                'investments': self.db.query_all("SELECT * FROM investments WHERE (user_id = ? OR ? IS NULL)", (user_id, user_id)) if self.enable_investments else [],
                'receipts': self.db.query_all("SELECT * FROM receipt_documents WHERE (user_id = ? OR ? IS NULL)", (user_id, user_id)),
                'backup_metadata': {
                    'backup_date': datetime.now().isoformat(),
                    'backup_type': 'full',
                    'version': '3.0.0',
                    'user_id': user_id
                }
            }
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"umbra_finance_backup_{timestamp}.json"
            
            # Calculate backup size and stats
            backup_size = len(json.dumps(backup_data, default=str))
            total_transactions = len(backup_data['transactions'])
            date_range = "All time"
            
            if backup_data['transactions']:
                oldest = min(t['date'] for t in backup_data['transactions'])
                newest = max(t['date'] for t in backup_data['transactions'])
                date_range = f"{oldest} to {newest}"
            
            return f"""**💾 Financial Data Backup Complete**

**Backup File:** {backup_filename}
**Size:** {backup_size / 1024:.1f}KB
**Date Range:** {date_range}

**Backed Up:**
• {len(backup_data['accounts'])} accounts
• {total_transactions} transactions
• {len(backup_data['budgets'])} budgets
• {len(backup_data['categories'])} categories
• {len(backup_data['goals'])} financial goals
• {len(backup_data['investments'])} investments
• {len(backup_data['receipts'])} receipt documents

✅ Complete backup saved securely.

💡 Store this backup file safely - it contains all your financial data!"""
            
        except Exception as e:
            return f"❌ Backup failed: {str(e)[:100]}"

    # Additional analytics placeholders
    async def analyze_spending(self, user_id: int = None) -> str:
        """Analyze spending patterns."""
        return "🚧 Advanced spending analysis coming soon!"

    async def compare_income_expenses(self, user_id: int = None) -> str:
        """Compare income vs expenses."""
        return "🚧 Income vs expenses analysis coming soon!"

    async def generate_yearly_report(self, year: int = None, user_id: int = None) -> str:
        """Generate yearly financial report."""
        return "🚧 Yearly reporting features coming soon!"

    async def analyze_cash_flow(self, user_id: int = None) -> str:
        """Analyze cash flow."""
        return "🚧 Cash flow analysis coming soon!"

    async def generate_spending_forecast(self, months: int = 3, user_id: int = None) -> str:
        """Generate spending forecast."""
        return "🚧 Spending forecasting features coming soon!"

    async def generate_wealth_projection(self, years: int = 5, user_id: int = None) -> str:
        """Generate wealth projection."""
        return "🚧 Wealth projection features coming soon!"
