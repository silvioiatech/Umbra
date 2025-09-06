"""
Expense Transaction Matcher for Swiss Accountant
Reconciles expenses with bank/card transactions using exact and probable matching strategies.
"""
import re
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime, date, timedelta
from enum import Enum
import json
import logging


class MatchType(Enum):
    """Types of expense-transaction matches."""
    EXACT = "exact"
    PROBABLE = "probable"
    NEEDS_REVIEW = "needs_review"
    NO_MATCH = "no_match"


class MatchStrategy(Enum):
    """Matching strategies."""
    AMOUNT_DATE_REFERENCE = "amount_date_reference"
    AMOUNT_DATE_MERCHANT = "amount_date_merchant"
    AMOUNT_DATE_ONLY = "amount_date_only"
    REFERENCE_ONLY = "reference_only"
    FUZZY_MATCHING = "fuzzy_matching"


class ExpenseTransactionMatcher:
    """Matches expenses with bank/card transactions for reconciliation."""
    
    def __init__(self, db_manager):
        """Initialize expense transaction matcher.
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Matching configuration
        self.config = {
            'exact_match_tolerance_days': 2,  # Days tolerance for date matching
            'probable_match_tolerance_days': 7,
            'amount_tolerance_percentage': 0.01,  # 1% tolerance
            'minimum_match_score': 0.7,
            'auto_accept_exact_threshold': 0.95,
            'auto_accept_probable_threshold': 0.85
        }
        
        # Initialize reconciliation tables
        self._init_reconciliation_tables()
    
    def _init_reconciliation_tables(self):
        """Initialize reconciliation tracking tables."""
        try:
            # Reconciliation matches table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sa_reconciliation_matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expense_id INTEGER NOT NULL,
                    transaction_id INTEGER NOT NULL,
                    match_type TEXT NOT NULL,
                    match_strategy TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    auto_matched BOOLEAN DEFAULT FALSE,
                    user_confirmed BOOLEAN DEFAULT FALSE,
                    user_rejected BOOLEAN DEFAULT FALSE,
                    match_details_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (expense_id) REFERENCES sa_expenses (id),
                    FOREIGN KEY (transaction_id) REFERENCES sa_transactions (id),
                    UNIQUE(expense_id, transaction_id)
                )
            """)
            
            # Reconciliation sessions table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sa_reconciliation_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_name TEXT,
                    period_start DATE,
                    period_end DATE,
                    strategy TEXT,
                    total_expenses INTEGER DEFAULT 0,
                    total_transactions INTEGER DEFAULT 0,
                    exact_matches INTEGER DEFAULT 0,
                    probable_matches INTEGER DEFAULT 0,
                    needs_review INTEGER DEFAULT 0,
                    unmatched_expenses INTEGER DEFAULT 0,
                    unmatched_transactions INTEGER DEFAULT 0,
                    session_data_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_reconciliation_expense ON sa_reconciliation_matches (expense_id)")
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_reconciliation_transaction ON sa_reconciliation_matches (transaction_id)")
            self.db.execute("CREATE INDEX IF NOT EXISTS idx_reconciliation_confidence ON sa_reconciliation_matches (confidence_score)")
            
        except Exception as e:
            self.logger.error(f"Reconciliation tables initialization failed: {e}")
    
    def reconcile_period(self, 
                        period_start: date,
                        period_end: date,
                        user_id: str,
                        strategy: MatchStrategy = MatchStrategy.AMOUNT_DATE_MERCHANT,
                        auto_accept: bool = True) -> Dict[str, Any]:
        """Reconcile expenses with transactions for a given period.
        
        Args:
            period_start: Start date for reconciliation
            period_end: End date for reconciliation
            user_id: User identifier
            strategy: Matching strategy to use
            auto_accept: Whether to auto-accept high-confidence matches
            
        Returns:
            Dict with reconciliation results
        """
        try:
            # Create reconciliation session
            session_id = self.db.execute("""
                INSERT INTO sa_reconciliation_sessions 
                (user_id, period_start, period_end, strategy, session_name)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, period_start, period_end, strategy.value, 
                  f"Reconciliation {period_start} to {period_end}"))
            
            # Get unmatched expenses for period
            expenses = self._get_unmatched_expenses(period_start, period_end, user_id)
            
            # Get unmatched transactions for period (with some buffer)
            buffer_start = period_start - timedelta(days=self.config['probable_match_tolerance_days'])
            buffer_end = period_end + timedelta(days=self.config['probable_match_tolerance_days'])
            transactions = self._get_unmatched_transactions(buffer_start, buffer_end, user_id)
            
            # Perform matching
            matches = self._perform_matching(expenses, transactions, strategy)
            
            # Process matches
            results = self._process_matches(matches, session_id, auto_accept)
            
            # Update session with results
            self._update_session_results(session_id, len(expenses), len(transactions), results)
            
            return {
                'success': True,
                'session_id': session_id,
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'strategy': strategy.value,
                'total_expenses': len(expenses),
                'total_transactions': len(transactions),
                'exact_matches': results['exact_matches'],
                'probable_matches': results['probable_matches'],
                'needs_review': results['needs_review'],
                'unmatched_expenses': results['unmatched_expenses'],
                'unmatched_transactions': results['unmatched_transactions'],
                'auto_accepted': results['auto_accepted'],
                'matches': results['match_details'][:50]  # Limit for response size
            }
            
        except Exception as e:
            self.logger.error(f"Reconciliation failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'session_id': None
            }
    
    def _get_unmatched_expenses(self, start_date: date, end_date: date, user_id: str) -> List[Dict[str, Any]]:
        """Get unmatched expenses for period."""
        try:
            expenses = self.db.query_all("""
                SELECT e.*, m.canonical as merchant_canonical
                FROM sa_expenses e
                LEFT JOIN sa_merchants m ON e.merchant_id = m.id
                LEFT JOIN sa_reconciliation_matches rm ON e.id = rm.expense_id
                WHERE e.user_id = ?
                AND e.date_local BETWEEN ? AND ?
                AND rm.id IS NULL
                ORDER BY e.date_local, e.amount_cents DESC
            """, (user_id, start_date, end_date))
            
            return expenses
            
        except Exception as e:
            self.logger.error(f"Failed to get unmatched expenses: {e}")
            return []
    
    def _get_unmatched_transactions(self, start_date: date, end_date: date, user_id: str) -> List[Dict[str, Any]]:
        """Get unmatched transactions for period."""
        try:
            transactions = self.db.query_all("""
                SELECT t.*
                FROM sa_transactions t
                LEFT JOIN sa_statements s ON t.statement_id = s.id
                LEFT JOIN sa_reconciliation_matches rm ON t.id = rm.transaction_id
                WHERE (s.user_id = ? OR ? IS NULL)
                AND (t.value_date BETWEEN ? AND ? OR t.booking_date BETWEEN ? AND ?)
                AND rm.id IS NULL
                AND t.amount_cents != 0
                ORDER BY COALESCE(t.value_date, t.booking_date), ABS(t.amount_cents) DESC
            """, (user_id, user_id, start_date, end_date, start_date, end_date))
            
            return transactions
            
        except Exception as e:
            self.logger.error(f"Failed to get unmatched transactions: {e}")
            return []
    
    def _perform_matching(self, 
                         expenses: List[Dict[str, Any]], 
                         transactions: List[Dict[str, Any]], 
                         strategy: MatchStrategy) -> List[Dict[str, Any]]:
        """Perform matching between expenses and transactions."""
        try:
            matches = []
            
            for expense in expenses:
                expense_amount = Decimal(expense['amount_cents']) / 100
                expense_date = datetime.fromisoformat(expense['date_local']).date()
                
                best_matches = []
                
                for transaction in transactions:
                    transaction_amount = abs(Decimal(transaction['amount_cents']) / 100)
                    transaction_date = self._get_transaction_date(transaction)
                    
                    # Calculate match score based on strategy
                    match_score = self._calculate_match_score(
                        expense, transaction, expense_amount, expense_date,
                        transaction_amount, transaction_date, strategy
                    )
                    
                    if match_score['total_score'] >= self.config['minimum_match_score']:
                        best_matches.append({
                            'expense': expense,
                            'transaction': transaction,
                            'score': match_score['total_score'],
                            'details': match_score,
                            'strategy': strategy
                        })
                
                # Sort matches by score and take the best one
                if best_matches:
                    best_matches.sort(key=lambda x: x['score'], reverse=True)
                    best_match = best_matches[0]
                    
                    # Determine match type based on score
                    if best_match['score'] >= self.config['auto_accept_exact_threshold']:
                        match_type = MatchType.EXACT
                    elif best_match['score'] >= self.config['auto_accept_probable_threshold']:
                        match_type = MatchType.PROBABLE
                    else:
                        match_type = MatchType.NEEDS_REVIEW
                    
                    best_match['match_type'] = match_type
                    matches.append(best_match)
            
            return matches
            
        except Exception as e:
            self.logger.error(f"Matching process failed: {e}")
            return []
    
    def _get_transaction_date(self, transaction: Dict[str, Any]) -> Optional[date]:
        """Get best available date from transaction."""
        try:
            # Prefer value date, fall back to booking date
            if transaction.get('value_date'):
                return datetime.fromisoformat(transaction['value_date']).date()
            elif transaction.get('booking_date'):
                return datetime.fromisoformat(transaction['booking_date']).date()
            return None
            
        except (ValueError, TypeError):
            return None
    
    def _calculate_match_score(self, 
                              expense: Dict[str, Any], 
                              transaction: Dict[str, Any],
                              expense_amount: Decimal,
                              expense_date: date,
                              transaction_amount: Decimal,
                              transaction_date: Optional[date],
                              strategy: MatchStrategy) -> Dict[str, Any]:
        """Calculate match score between expense and transaction."""
        try:
            scores = {
                'amount_score': 0.0,
                'date_score': 0.0,
                'reference_score': 0.0,
                'merchant_score': 0.0,
                'description_score': 0.0
            }
            
            # Amount score (most important)
            amount_diff = abs(expense_amount - transaction_amount)
            amount_tolerance = expense_amount * Decimal(str(self.config['amount_tolerance_percentage']))
            
            if amount_diff == 0:
                scores['amount_score'] = 1.0
            elif amount_diff <= amount_tolerance:
                scores['amount_score'] = 0.95
            elif amount_diff <= expense_amount * Decimal('0.05'):  # 5% tolerance
                scores['amount_score'] = 0.8
            elif amount_diff <= expense_amount * Decimal('0.10'):  # 10% tolerance
                scores['amount_score'] = 0.6
            else:
                scores['amount_score'] = 0.0
            
            # Date score
            if transaction_date and expense_date:
                date_diff = abs((expense_date - transaction_date).days)
                
                if date_diff == 0:
                    scores['date_score'] = 1.0
                elif date_diff <= self.config['exact_match_tolerance_days']:
                    scores['date_score'] = 0.9
                elif date_diff <= self.config['probable_match_tolerance_days']:
                    scores['date_score'] = 0.7
                else:
                    scores['date_score'] = 0.3
            
            # Reference score
            expense_ref = self._extract_reference(expense.get('notes', ''))
            transaction_ref = transaction.get('reference', '')
            
            if expense_ref and transaction_ref:
                if expense_ref.lower() == transaction_ref.lower():
                    scores['reference_score'] = 1.0
                elif expense_ref.lower() in transaction_ref.lower() or transaction_ref.lower() in expense_ref.lower():
                    scores['reference_score'] = 0.8
                else:
                    scores['reference_score'] = 0.0
            
            # Merchant/counterparty score
            merchant_name = expense.get('merchant_text', '') or expense.get('merchant_canonical', '')
            counterparty = transaction.get('counterparty', '')
            
            if merchant_name and counterparty:
                merchant_score = self._calculate_text_similarity(merchant_name, counterparty)
                scores['merchant_score'] = merchant_score
            
            # Description score
            expense_desc = expense.get('notes', '')
            transaction_desc = transaction.get('description', '') or transaction.get('raw_desc', '')
            
            if expense_desc and transaction_desc:
                desc_score = self._calculate_text_similarity(expense_desc, transaction_desc)
                scores['description_score'] = desc_score
            
            # Calculate weighted total score based on strategy
            weights = self._get_strategy_weights(strategy)
            total_score = sum(scores[key] * weights.get(key, 0) for key in scores.keys())
            
            return {
                'total_score': total_score,
                'component_scores': scores,
                'weights': weights,
                'amount_diff': float(amount_diff),
                'date_diff': abs((expense_date - transaction_date).days) if transaction_date else None
            }
            
        except Exception as e:
            self.logger.error(f"Match score calculation failed: {e}")
            return {
                'total_score': 0.0,
                'component_scores': {},
                'weights': {},
                'error': str(e)
            }
    
    def _get_strategy_weights(self, strategy: MatchStrategy) -> Dict[str, float]:
        """Get scoring weights for different strategies."""
        if strategy == MatchStrategy.AMOUNT_DATE_REFERENCE:
            return {
                'amount_score': 0.4,
                'date_score': 0.3,
                'reference_score': 0.3,
                'merchant_score': 0.0,
                'description_score': 0.0
            }
        elif strategy == MatchStrategy.AMOUNT_DATE_MERCHANT:
            return {
                'amount_score': 0.5,
                'date_score': 0.25,
                'reference_score': 0.1,
                'merchant_score': 0.15,
                'description_score': 0.0
            }
        elif strategy == MatchStrategy.AMOUNT_DATE_ONLY:
            return {
                'amount_score': 0.7,
                'date_score': 0.3,
                'reference_score': 0.0,
                'merchant_score': 0.0,
                'description_score': 0.0
            }
        elif strategy == MatchStrategy.REFERENCE_ONLY:
            return {
                'amount_score': 0.3,
                'date_score': 0.2,
                'reference_score': 0.5,
                'merchant_score': 0.0,
                'description_score': 0.0
            }
        elif strategy == MatchStrategy.FUZZY_MATCHING:
            return {
                'amount_score': 0.3,
                'date_score': 0.2,
                'reference_score': 0.15,
                'merchant_score': 0.2,
                'description_score': 0.15
            }
        else:
            # Default weights
            return {
                'amount_score': 0.4,
                'date_score': 0.3,
                'reference_score': 0.15,
                'merchant_score': 0.1,
                'description_score': 0.05
            }
    
    def _extract_reference(self, text: str) -> Optional[str]:
        """Extract reference number from text."""
        try:
            if not text:
                return None
            
            # Look for reference patterns
            patterns = [
                r'ref[:\s]*([A-Z0-9\-]{5,20})',
                r'référence[:\s]*([A-Z0-9\-]{5,20})',
                r'nr[:\s]*([A-Z0-9\-]{5,20})',
                r'([A-Z0-9]{10,})',  # Long alphanumeric sequences
                r'([0-9]{8,})'  # Long numeric sequences
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1)
            
            return None
            
        except Exception:
            return None
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings."""
        try:
            if not text1 or not text2:
                return 0.0
            
            # Simple similarity based on common words
            words1 = set(re.findall(r'\w+', text1.lower()))
            words2 = set(re.findall(r'\w+', text2.lower()))
            
            if not words1 or not words2:
                return 0.0
            
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            
            return len(intersection) / len(union) if union else 0.0
            
        except Exception:
            return 0.0
    
    def _process_matches(self, 
                        matches: List[Dict[str, Any]], 
                        session_id: int,
                        auto_accept: bool) -> Dict[str, Any]:
        """Process and store matches."""
        try:
            results = {
                'exact_matches': 0,
                'probable_matches': 0,
                'needs_review': 0,
                'unmatched_expenses': 0,
                'unmatched_transactions': 0,
                'auto_accepted': 0,
                'match_details': []
            }
            
            for match in matches:
                expense = match['expense']
                transaction = match['transaction']
                match_type = match['match_type']
                
                # Determine if auto-accept
                should_auto_accept = (
                    auto_accept and 
                    match_type in [MatchType.EXACT, MatchType.PROBABLE] and
                    match['score'] >= self.config['auto_accept_probable_threshold']
                )
                
                # Store match
                match_id = self.db.execute("""
                    INSERT INTO sa_reconciliation_matches 
                    (expense_id, transaction_id, match_type, match_strategy, confidence_score, 
                     auto_matched, user_confirmed, match_details_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    expense['id'], transaction['id'], match_type.value, 
                    match['strategy'].value, match['score'],
                    should_auto_accept, should_auto_accept,
                    json.dumps(match['details'])
                ))
                
                # Update expense with transaction reference
                if should_auto_accept:
                    self.db.execute("""
                        UPDATE sa_expenses 
                        SET notes = CASE 
                            WHEN notes IS NULL OR notes = '' THEN 'Matched with transaction #' || ?
                            ELSE notes || '; Matched with transaction #' || ?
                        END
                        WHERE id = ?
                    """, (transaction['id'], transaction['id'], expense['id']))
                    
                    # Update transaction with expense reference
                    self.db.execute("""
                        UPDATE sa_transactions 
                        SET matched_expense_id = ?
                        WHERE id = ?
                    """, (expense['id'], transaction['id']))
                
                # Count results
                if match_type == MatchType.EXACT:
                    results['exact_matches'] += 1
                elif match_type == MatchType.PROBABLE:
                    results['probable_matches'] += 1
                else:
                    results['needs_review'] += 1
                
                if should_auto_accept:
                    results['auto_accepted'] += 1
                
                # Add to details (limited info for response)
                results['match_details'].append({
                    'match_id': match_id,
                    'expense_id': expense['id'],
                    'transaction_id': transaction['id'],
                    'match_type': match_type.value,
                    'confidence': round(match['score'], 3),
                    'auto_accepted': should_auto_accept,
                    'expense_amount': float(Decimal(expense['amount_cents']) / 100),
                    'transaction_amount': float(Decimal(transaction['amount_cents']) / 100),
                    'expense_date': expense['date_local'],
                    'transaction_date': transaction.get('value_date') or transaction.get('booking_date'),
                    'merchant': expense.get('merchant_text', ''),
                    'counterparty': transaction.get('counterparty', '')
                })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Match processing failed: {e}")
            return {
                'exact_matches': 0,
                'probable_matches': 0,
                'needs_review': 0,
                'unmatched_expenses': 0,
                'unmatched_transactions': 0,
                'auto_accepted': 0,
                'match_details': [],
                'error': str(e)
            }
    
    def _update_session_results(self, 
                               session_id: int, 
                               total_expenses: int, 
                               total_transactions: int, 
                               results: Dict[str, Any]):
        """Update reconciliation session with results."""
        try:
            unmatched_expenses = total_expenses - results['exact_matches'] - results['probable_matches'] - results['needs_review']
            unmatched_transactions = total_transactions - results['exact_matches'] - results['probable_matches'] - results['needs_review']
            
            self.db.execute("""
                UPDATE sa_reconciliation_sessions 
                SET total_expenses = ?, total_transactions = ?,
                    exact_matches = ?, probable_matches = ?, needs_review = ?,
                    unmatched_expenses = ?, unmatched_transactions = ?,
                    completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                total_expenses, total_transactions,
                results['exact_matches'], results['probable_matches'], results['needs_review'],
                unmatched_expenses, unmatched_transactions,
                session_id
            ))
            
        except Exception as e:
            self.logger.error(f"Session update failed: {e}")
    
    def get_pending_matches(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get matches that need user review.
        
        Args:
            user_id: User identifier
            limit: Maximum results
            
        Returns:
            List of pending matches
        """
        try:
            pending_matches = self.db.query_all("""
                SELECT rm.*, 
                       e.amount_cents as expense_amount, e.date_local as expense_date,
                       e.merchant_text, e.notes as expense_notes,
                       t.amount_cents as transaction_amount, 
                       COALESCE(t.value_date, t.booking_date) as transaction_date,
                       t.counterparty, t.description as transaction_desc,
                       t.reference as transaction_ref
                FROM sa_reconciliation_matches rm
                JOIN sa_expenses e ON rm.expense_id = e.id
                JOIN sa_transactions t ON rm.transaction_id = t.id
                WHERE e.user_id = ?
                AND rm.user_confirmed = FALSE
                AND rm.user_rejected = FALSE
                AND rm.match_type = 'needs_review'
                ORDER BY rm.confidence_score DESC, rm.created_at
                LIMIT ?
            """, (user_id, limit))
            
            return [
                {
                    'match_id': match['id'],
                    'expense_id': match['expense_id'],
                    'transaction_id': match['transaction_id'],
                    'confidence': match['confidence_score'],
                    'match_details': json.loads(match['match_details_json']) if match['match_details_json'] else {},
                    'expense': {
                        'amount': float(Decimal(match['expense_amount']) / 100),
                        'date': match['expense_date'],
                        'merchant': match['merchant_text'],
                        'notes': match['expense_notes']
                    },
                    'transaction': {
                        'amount': float(Decimal(match['transaction_amount']) / 100),
                        'date': match['transaction_date'],
                        'counterparty': match['counterparty'],
                        'description': match['transaction_desc'],
                        'reference': match['transaction_ref']
                    }
                }
                for match in pending_matches
            ]
            
        except Exception as e:
            self.logger.error(f"Get pending matches failed: {e}")
            return []
    
    def confirm_match(self, match_id: int, user_id: str) -> Dict[str, Any]:
        """Confirm a pending match.
        
        Args:
            match_id: Match ID to confirm
            user_id: User identifier for security
            
        Returns:
            Dict with result
        """
        try:
            # Get match details
            match = self.db.query_one("""
                SELECT rm.*, e.user_id
                FROM sa_reconciliation_matches rm
                JOIN sa_expenses e ON rm.expense_id = e.id
                WHERE rm.id = ? AND e.user_id = ?
            """, (match_id, user_id))
            
            if not match:
                return {
                    'success': False,
                    'error': 'Match not found or access denied'
                }
            
            # Update match as confirmed
            self.db.execute("""
                UPDATE sa_reconciliation_matches 
                SET user_confirmed = TRUE, user_rejected = FALSE, 
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (match_id,))
            
            # Update expense and transaction links
            self.db.execute("""
                UPDATE sa_expenses 
                SET notes = CASE 
                    WHEN notes IS NULL OR notes = '' THEN 'Matched with transaction #' || ?
                    ELSE notes || '; Matched with transaction #' || ?
                END
                WHERE id = ?
            """, (match['transaction_id'], match['transaction_id'], match['expense_id']))
            
            self.db.execute("""
                UPDATE sa_transactions 
                SET matched_expense_id = ?
                WHERE id = ?
            """, (match['expense_id'], match['transaction_id']))
            
            return {
                'success': True,
                'match_id': match_id,
                'expense_id': match['expense_id'],
                'transaction_id': match['transaction_id'],
                'status': 'confirmed'
            }
            
        except Exception as e:
            self.logger.error(f"Confirm match failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def reject_match(self, match_id: int, user_id: str) -> Dict[str, Any]:
        """Reject a pending match.
        
        Args:
            match_id: Match ID to reject
            user_id: User identifier for security
            
        Returns:
            Dict with result
        """
        try:
            # Get match details
            match = self.db.query_one("""
                SELECT rm.*, e.user_id
                FROM sa_reconciliation_matches rm
                JOIN sa_expenses e ON rm.expense_id = e.id
                WHERE rm.id = ? AND e.user_id = ?
            """, (match_id, user_id))
            
            if not match:
                return {
                    'success': False,
                    'error': 'Match not found or access denied'
                }
            
            # Update match as rejected
            self.db.execute("""
                UPDATE sa_reconciliation_matches 
                SET user_rejected = TRUE, user_confirmed = FALSE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (match_id,))
            
            return {
                'success': True,
                'match_id': match_id,
                'status': 'rejected'
            }
            
        except Exception as e:
            self.logger.error(f"Reject match failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_reconciliation_summary(self, user_id: str) -> Dict[str, Any]:
        """Get overall reconciliation summary for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict with reconciliation statistics
        """
        try:
            # Get overall statistics
            stats = self.db.query_one("""
                SELECT 
                    COUNT(*) as total_matches,
                    SUM(CASE WHEN match_type = 'exact' THEN 1 ELSE 0 END) as exact_matches,
                    SUM(CASE WHEN match_type = 'probable' THEN 1 ELSE 0 END) as probable_matches,
                    SUM(CASE WHEN match_type = 'needs_review' THEN 1 ELSE 0 END) as needs_review,
                    SUM(CASE WHEN user_confirmed = TRUE THEN 1 ELSE 0 END) as confirmed_matches,
                    SUM(CASE WHEN user_rejected = TRUE THEN 1 ELSE 0 END) as rejected_matches,
                    AVG(confidence_score) as avg_confidence
                FROM sa_reconciliation_matches rm
                JOIN sa_expenses e ON rm.expense_id = e.id
                WHERE e.user_id = ?
            """, (user_id,))
            
            # Get unmatched counts
            unmatched_expenses = self.db.query_one("""
                SELECT COUNT(*) as count
                FROM sa_expenses e
                LEFT JOIN sa_reconciliation_matches rm ON e.id = rm.expense_id
                WHERE e.user_id = ? AND rm.id IS NULL
            """, (user_id,))
            
            unmatched_transactions = self.db.query_one("""
                SELECT COUNT(*) as count
                FROM sa_transactions t
                LEFT JOIN sa_statements s ON t.statement_id = s.id
                LEFT JOIN sa_reconciliation_matches rm ON t.id = rm.transaction_id
                WHERE (s.user_id = ? OR ? IS NULL) AND rm.id IS NULL
            """, (user_id, user_id))
            
            # Get recent sessions
            recent_sessions = self.db.query_all("""
                SELECT * FROM sa_reconciliation_sessions
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 5
            """, (user_id,))
            
            return {
                'total_matches': stats['total_matches'] or 0,
                'exact_matches': stats['exact_matches'] or 0,
                'probable_matches': stats['probable_matches'] or 0,
                'needs_review': stats['needs_review'] or 0,
                'confirmed_matches': stats['confirmed_matches'] or 0,
                'rejected_matches': stats['rejected_matches'] or 0,
                'avg_confidence': round(stats['avg_confidence'] or 0, 2),
                'unmatched_expenses': unmatched_expenses['count'] or 0,
                'unmatched_transactions': unmatched_transactions['count'] or 0,
                'recent_sessions': [
                    {
                        'id': session['id'],
                        'session_name': session['session_name'],
                        'period_start': session['period_start'],
                        'period_end': session['period_end'],
                        'strategy': session['strategy'],
                        'exact_matches': session['exact_matches'],
                        'probable_matches': session['probable_matches'],
                        'needs_review': session['needs_review'],
                        'created_at': session['created_at'],
                        'completed_at': session['completed_at']
                    }
                    for session in recent_sessions
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Reconciliation summary failed: {e}")
            return {
                'total_matches': 0,
                'exact_matches': 0,
                'probable_matches': 0,
                'needs_review': 0,
                'confirmed_matches': 0,
                'rejected_matches': 0,
                'avg_confidence': 0.0,
                'unmatched_expenses': 0,
                'unmatched_transactions': 0,
                'recent_sessions': [],
                'error': str(e)
            }


# Factory function for easy import
def create_expense_transaction_matcher(db_manager) -> ExpenseTransactionMatcher:
    """Create expense transaction matcher instance."""
    return ExpenseTransactionMatcher(db_manager)
