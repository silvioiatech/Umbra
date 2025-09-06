"""
Merchant Normalizer for Swiss Accountant
Handles canonical merchant names, aliases, and VAT number management.
"""
import re
import difflib
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
import json
import logging


class MerchantNormalizer:
    """Normalizes merchant names and manages merchant data."""
    
    def __init__(self, db_manager):
        """Initialize merchant normalizer.
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Common merchant patterns and normalizations
        self.merchant_patterns = {
            # Swiss retail chains
            'migros': r'(?i)(migros|mig\s)',
            'coop': r'(?i)(coop|co-op)',
            'denner': r'(?i)denner',
            'aldi': r'(?i)aldi',
            'lidl': r'(?i)lidl',
            'manor': r'(?i)manor',
            'globus': r'(?i)globus',
            'jelmoli': r'(?i)jelmoli',
            
            # Swiss restaurants/food
            'mcdonalds': r'(?i)(mcdonald|mcdo|mcd\s)',
            'burger_king': r'(?i)(burger\s*king|bk\s)',
            'kfc': r'(?i)(kfc|kentucky)',
            'subway': r'(?i)subway',
            'starbucks': r'(?i)(starbucks|sbux)',
            'pizza_hut': r'(?i)(pizza\s*hut|ph\s)',
            
            # Swiss banks/financial
            'ubs': r'(?i)(ubs|union\s*bank)',
            'credit_suisse': r'(?i)(credit\s*suisse|cs\s)',
            'postfinance': r'(?i)(postfinance|pf\s)',
            'raiffeisen': r'(?i)raiffeisen',
            'bcv': r'(?i)(bcv|banque\s*cantonale\s*vaudoise)',
            'zkb': r'(?i)(zkb|zürcher\s*kantonalbank)',
            
            # Transport
            'sbb': r'(?i)(sbb|cff|ffs|swiss\s*federal)',
            'tpg': r'(?i)(tpg|transports\s*publics\s*genevois)',
            'vbz': r'(?i)(vbz|verkehrsbetriebe\s*zürich)',
            'postbus': r'(?i)(postauto|car\s*postal)',
            
            # Swiss telecom
            'swisscom': r'(?i)swisscom',
            'sunrise': r'(?i)sunrise',
            'salt': r'(?i)salt\s*mobile',
            'upc': r'(?i)(upc|liberty\s*global)',
            
            # International chains in Switzerland
            'apple': r'(?i)(apple\s*store|apple\s*inc)',
            'google': r'(?i)(google|alphabet)',
            'microsoft': r'(?i)microsoft',
            'amazon': r'(?i)amazon',
            'netflix': r'(?i)netflix',
            'spotify': r'(?i)spotify',
            'uber': r'(?i)uber',
            'booking': r'(?i)(booking\.com|booking)',
            'airbnb': r'(?i)airbnb'
        }
        
        # Cleanup patterns
        self.cleanup_patterns = [
            (r'\s+', ' '),  # Multiple spaces to single
            (r'[^\w\s&\-\.]', ''),  # Remove special chars except &, -, .
            (r'\b(?:gmbh|ag|sa|ltd|inc|corp|co|llc|sarl)\b', ''),  # Remove company suffixes
            (r'\b(?:the|le|la|les|der|die|das)\b', ''),  # Remove articles
            (r'^\s+|\s+$', ''),  # Trim whitespace
        ]
        
        # Initialize default merchants
        self._init_default_merchants()
    
    def _init_default_merchants(self):
        """Initialize database with default Swiss merchants."""
        try:
            # Check if merchants table has data
            existing_count = self.db.query_one("SELECT COUNT(*) as count FROM sa_merchants")
            if existing_count and existing_count['count'] > 0:
                return  # Already initialized
            
            # Default Swiss merchants with VAT numbers where known
            default_merchants = [
                # Major retail
                ('Migros-Genossenschafts-Bund', 'CHE-116.281.277', 'migros,mig,migros genossenschaft'),
                ('Coop Genossenschaft', 'CHE-116.200.681', 'coop,co-op,coop schweiz'),
                ('Denner AG', 'CHE-116.295.681', 'denner,denner discount'),
                ('Aldi Suisse AG', 'CHE-116.068.092', 'aldi,aldi suisse'),
                ('Lidl Schweiz AG', 'CHE-116.309.304', 'lidl,lidl schweiz'),
                ('Manor AG', 'CHE-116.220.306', 'manor,manor ag'),
                
                # Banks
                ('UBS AG', 'CHE-116.281.053', 'ubs,union bank,ubs switzerland'),
                ('Credit Suisse AG', 'CHE-116.281.070', 'credit suisse,cs,crédit suisse'),
                ('PostFinance AG', 'CHE-116.287.984', 'postfinance,pf,post finance'),
                ('Raiffeisen Schweiz', 'CHE-116.285.595', 'raiffeisen,raiffeisen bank'),
                
                # Transport
                ('SBB AG', 'CHE-116.169.445', 'sbb,cff,ffs,swiss federal railways'),
                ('PostAuto Schweiz AG', 'CHE-116.287.228', 'postauto,car postal,postbus'),
                
                # Telecom
                ('Swisscom AG', 'CHE-116.281.070', 'swisscom,swisscom schweiz'),
                ('Sunrise Communications AG', 'CHE-116.068.542', 'sunrise,sunrise communications'),
                ('Salt Mobile SA', 'CHE-116.281.811', 'salt,salt mobile'),
                
                # Fast food
                ("McDonald's Schweiz", '', 'mcdonalds,mcdonald,mcdo,mcd'),
                ('Burger King Switzerland', '', 'burger king,bk'),
                ('KFC Switzerland', '', 'kfc,kentucky fried chicken'),
                ('Subway Switzerland', '', 'subway'),
                ('Starbucks Switzerland', '', 'starbucks,sbux'),
                
                # International services
                ('Apple Distribution International', 'CHE-116.281.053', 'apple,apple store,apple inc'),
                ('Google Switzerland GmbH', 'CHE-116.281.070', 'google,alphabet,google pay'),
                ('Microsoft Switzerland GmbH', 'CHE-116.281.811', 'microsoft,ms'),
                ('Amazon Europe Core S.à r.l.', '', 'amazon,amazon.ch'),
                ('Netflix International B.V.', '', 'netflix'),
                ('Spotify AB', '', 'spotify'),
                ('Uber Switzerland GmbH', '', 'uber,uber eats'),
                ('Booking.com B.V.', '', 'booking.com,booking,priceline'),
                ('Airbnb Ireland UC', '', 'airbnb')
            ]
            
            for canonical, vat_no, aliases in default_merchants:
                try:
                    self.db.execute(
                        "INSERT OR IGNORE INTO sa_merchants (canonical, vat_no, aliases) VALUES (?, ?, ?)",
                        (canonical, vat_no, aliases)
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to insert default merchant {canonical}: {e}")
            
            self.logger.info(f"Initialized {len(default_merchants)} default merchants")
            
        except Exception as e:
            self.logger.error(f"Default merchants initialization failed: {e}")
    
    def normalize_merchant_name(self, raw_name: str) -> Dict[str, Any]:
        """Normalize merchant name to canonical form.
        
        Args:
            raw_name: Raw merchant name from OCR/transaction
            
        Returns:
            Dict with normalized merchant info
        """
        try:
            if not raw_name or not raw_name.strip():
                return {
                    'success': False,
                    'error': 'Empty merchant name',
                    'raw_name': raw_name,
                    'canonical': None,
                    'confidence': 0.0
                }
            
            # Clean up the raw name
            cleaned_name = self._clean_merchant_name(raw_name)
            
            # Try exact match first
            exact_match = self._find_exact_match(cleaned_name)
            if exact_match:
                return {
                    'success': True,
                    'raw_name': raw_name,
                    'cleaned_name': cleaned_name,
                    'canonical': exact_match['canonical'],
                    'merchant_id': exact_match['id'],
                    'vat_no': exact_match['vat_no'],
                    'confidence': 1.0,
                    'match_type': 'exact'
                }
            
            # Try pattern matching
            pattern_match = self._find_pattern_match(cleaned_name)
            if pattern_match:
                return {
                    'success': True,
                    'raw_name': raw_name,
                    'cleaned_name': cleaned_name,
                    'canonical': pattern_match['canonical'],
                    'merchant_id': pattern_match['id'],
                    'vat_no': pattern_match['vat_no'],
                    'confidence': pattern_match['confidence'],
                    'match_type': 'pattern'
                }
            
            # Try fuzzy matching
            fuzzy_match = self._find_fuzzy_match(cleaned_name)
            if fuzzy_match and fuzzy_match['confidence'] > 0.8:
                return {
                    'success': True,
                    'raw_name': raw_name,
                    'cleaned_name': cleaned_name,
                    'canonical': fuzzy_match['canonical'],
                    'merchant_id': fuzzy_match['id'],
                    'vat_no': fuzzy_match['vat_no'],
                    'confidence': fuzzy_match['confidence'],
                    'match_type': 'fuzzy'
                }
            
            # No match found - return cleaned name
            return {
                'success': True,
                'raw_name': raw_name,
                'cleaned_name': cleaned_name,
                'canonical': cleaned_name,
                'merchant_id': None,
                'vat_no': None,
                'confidence': 0.0,
                'match_type': 'none',
                'suggestion': fuzzy_match['canonical'] if fuzzy_match else None
            }
            
        except Exception as e:
            self.logger.error(f"Merchant normalization failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'raw_name': raw_name,
                'canonical': None,
                'confidence': 0.0
            }
    
    def _clean_merchant_name(self, name: str) -> str:
        """Clean and normalize merchant name."""
        try:
            cleaned = name.strip()
            
            # Apply cleanup patterns
            for pattern, replacement in self.cleanup_patterns:
                cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
            
            # Convert to title case for consistency
            cleaned = cleaned.title()
            
            return cleaned.strip()
            
        except Exception as e:
            self.logger.error(f"Merchant name cleaning failed: {e}")
            return name
    
    def _find_exact_match(self, cleaned_name: str) -> Optional[Dict[str, Any]]:
        """Find exact match in merchants database."""
        try:
            # Check canonical names
            exact_canonical = self.db.query_one(
                "SELECT * FROM sa_merchants WHERE LOWER(canonical) = LOWER(?)",
                (cleaned_name,)
            )
            if exact_canonical:
                return exact_canonical
            
            # Check aliases
            merchants_with_aliases = self.db.query_all(
                "SELECT * FROM sa_merchants WHERE aliases IS NOT NULL AND aliases != ''"
            )
            
            for merchant in merchants_with_aliases:
                aliases = merchant['aliases'].split(',')
                for alias in aliases:
                    if alias.strip().lower() == cleaned_name.lower():
                        return merchant
            
            return None
            
        except Exception as e:
            self.logger.error(f"Exact match search failed: {e}")
            return None
    
    def _find_pattern_match(self, cleaned_name: str) -> Optional[Dict[str, Any]]:
        """Find pattern-based match using predefined patterns."""
        try:
            for canonical_key, pattern in self.merchant_patterns.items():
                if re.search(pattern, cleaned_name, re.IGNORECASE):
                    # Look up merchant by pattern key
                    merchants = self.db.query_all(
                        "SELECT * FROM sa_merchants WHERE LOWER(canonical) LIKE ? OR LOWER(aliases) LIKE ?",
                        (f'%{canonical_key}%', f'%{canonical_key}%')
                    )
                    
                    if merchants:
                        match = merchants[0]  # Take first match
                        return {
                            'id': match['id'],
                            'canonical': match['canonical'],
                            'vat_no': match['vat_no'],
                            'confidence': 0.9  # High confidence for pattern match
                        }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Pattern match search failed: {e}")
            return None
    
    def _find_fuzzy_match(self, cleaned_name: str) -> Optional[Dict[str, Any]]:
        """Find fuzzy match using string similarity."""
        try:
            # Get all merchants for fuzzy matching
            all_merchants = self.db.query_all("SELECT * FROM sa_merchants")
            
            best_match = None
            best_score = 0.0
            
            for merchant in all_merchants:
                # Check canonical name
                canonical_score = difflib.SequenceMatcher(None, cleaned_name.lower(), merchant['canonical'].lower()).ratio()
                
                if canonical_score > best_score:
                    best_score = canonical_score
                    best_match = {
                        'id': merchant['id'],
                        'canonical': merchant['canonical'],
                        'vat_no': merchant['vat_no'],
                        'confidence': canonical_score
                    }
                
                # Check aliases if available
                if merchant['aliases']:
                    aliases = merchant['aliases'].split(',')
                    for alias in aliases:
                        alias_score = difflib.SequenceMatcher(None, cleaned_name.lower(), alias.strip().lower()).ratio()
                        if alias_score > best_score:
                            best_score = alias_score
                            best_match = {
                                'id': merchant['id'],
                                'canonical': merchant['canonical'],
                                'vat_no': merchant['vat_no'],
                                'confidence': alias_score
                            }
            
            return best_match if best_score > 0.6 else None  # Minimum threshold
            
        except Exception as e:
            self.logger.error(f"Fuzzy match search failed: {e}")
            return None
    
    def add_merchant(self, canonical: str, vat_no: str = None, aliases: str = None) -> Dict[str, Any]:
        """Add new merchant to database.
        
        Args:
            canonical: Canonical merchant name
            vat_no: Swiss VAT number (CHE-XXX.XXX.XXX)
            aliases: Comma-separated aliases
            
        Returns:
            Dict with result
        """
        try:
            # Validate VAT number format if provided
            if vat_no and not self._validate_swiss_vat_number(vat_no):
                return {
                    'success': False,
                    'error': f'Invalid Swiss VAT number format: {vat_no}'
                }
            
            # Check if canonical name already exists
            existing = self.db.query_one(
                "SELECT id FROM sa_merchants WHERE LOWER(canonical) = LOWER(?)",
                (canonical,)
            )
            
            if existing:
                return {
                    'success': False,
                    'error': f'Merchant with canonical name "{canonical}" already exists'
                }
            
            # Insert new merchant
            merchant_id = self.db.execute(
                "INSERT INTO sa_merchants (canonical, vat_no, aliases) VALUES (?, ?, ?)",
                (canonical, vat_no, aliases)
            )
            
            return {
                'success': True,
                'merchant_id': merchant_id,
                'canonical': canonical,
                'vat_no': vat_no,
                'aliases': aliases
            }
            
        except Exception as e:
            self.logger.error(f"Add merchant failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def add_alias(self, merchant_id: int, alias: str) -> Dict[str, Any]:
        """Add alias to existing merchant.
        
        Args:
            merchant_id: Merchant ID
            alias: Alias to add
            
        Returns:
            Dict with result
        """
        try:
            # Get current merchant
            merchant = self.db.query_one("SELECT * FROM sa_merchants WHERE id = ?", (merchant_id,))
            if not merchant:
                return {
                    'success': False,
                    'error': f'Merchant with ID {merchant_id} not found'
                }
            
            # Get current aliases
            current_aliases = merchant['aliases'] or ''
            aliases_list = [a.strip() for a in current_aliases.split(',') if a.strip()]
            
            # Add new alias if not already present
            alias = alias.strip()
            if alias.lower() not in [a.lower() for a in aliases_list]:
                aliases_list.append(alias)
                new_aliases = ','.join(aliases_list)
                
                # Update database
                self.db.execute(
                    "UPDATE sa_merchants SET aliases = ? WHERE id = ?",
                    (new_aliases, merchant_id)
                )
                
                return {
                    'success': True,
                    'merchant_id': merchant_id,
                    'canonical': merchant['canonical'],
                    'new_alias': alias,
                    'all_aliases': new_aliases
                }
            else:
                return {
                    'success': False,
                    'error': f'Alias "{alias}" already exists for this merchant'
                }
            
        except Exception as e:
            self.logger.error(f"Add alias failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_merchant_info(self, merchant_id: int) -> Optional[Dict[str, Any]]:
        """Get merchant information by ID.
        
        Args:
            merchant_id: Merchant ID
            
        Returns:
            Merchant info dict or None
        """
        try:
            merchant = self.db.query_one("SELECT * FROM sa_merchants WHERE id = ?", (merchant_id,))
            if not merchant:
                return None
            
            return {
                'id': merchant['id'],
                'canonical': merchant['canonical'],
                'vat_no': merchant['vat_no'],
                'aliases': merchant['aliases'].split(',') if merchant['aliases'] else [],
                'is_swiss_vat_registered': bool(merchant['vat_no'] and merchant['vat_no'].startswith('CHE-'))
            }
            
        except Exception as e:
            self.logger.error(f"Get merchant info failed: {e}")
            return None
    
    def search_merchants(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search merchants by name or alias.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of matching merchants
        """
        try:
            query_pattern = f'%{query}%'
            
            merchants = self.db.query_all("""
                SELECT * FROM sa_merchants 
                WHERE LOWER(canonical) LIKE LOWER(?) 
                   OR LOWER(aliases) LIKE LOWER(?)
                ORDER BY 
                    CASE WHEN LOWER(canonical) LIKE LOWER(?) THEN 1 ELSE 2 END,
                    canonical
                LIMIT ?
            """, (query_pattern, query_pattern, f'{query}%', limit))
            
            results = []
            for merchant in merchants:
                results.append({
                    'id': merchant['id'],
                    'canonical': merchant['canonical'],
                    'vat_no': merchant['vat_no'],
                    'aliases': merchant['aliases'].split(',') if merchant['aliases'] else [],
                    'relevance_score': self._calculate_relevance_score(query, merchant)
                })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Merchant search failed: {e}")
            return []
    
    def _validate_swiss_vat_number(self, vat_no: str) -> bool:
        """Validate Swiss VAT number format.
        
        Args:
            vat_no: VAT number to validate
            
        Returns:
            True if valid format
        """
        try:
            # Swiss VAT format: CHE-XXX.XXX.XXX
            pattern = r'^CHE-\d{3}\.\d{3}\.\d{3}$'
            return bool(re.match(pattern, vat_no))
            
        except Exception:
            return False
    
    def _calculate_relevance_score(self, query: str, merchant: Dict[str, Any]) -> float:
        """Calculate relevance score for search results."""
        try:
            query_lower = query.lower()
            canonical_lower = merchant['canonical'].lower()
            
            # Exact match gets highest score
            if query_lower == canonical_lower:
                return 1.0
            
            # Starts with query gets high score
            if canonical_lower.startswith(query_lower):
                return 0.9
            
            # Contains query gets medium score
            if query_lower in canonical_lower:
                return 0.7
            
            # Check aliases
            if merchant['aliases']:
                aliases = [a.strip().lower() for a in merchant['aliases'].split(',')]
                for alias in aliases:
                    if query_lower == alias:
                        return 0.95
                    elif alias.startswith(query_lower):
                        return 0.85
                    elif query_lower in alias:
                        return 0.65
            
            # Fuzzy matching as fallback
            return difflib.SequenceMatcher(None, query_lower, canonical_lower).ratio()
            
        except Exception:
            return 0.0
    
    def get_merchant_statistics(self) -> Dict[str, Any]:
        """Get merchant database statistics."""
        try:
            stats = {
                'total_merchants': 0,
                'merchants_with_vat': 0,
                'merchants_with_aliases': 0,
                'top_merchants_by_usage': []
            }
            
            # Total count
            total_result = self.db.query_one("SELECT COUNT(*) as count FROM sa_merchants")
            stats['total_merchants'] = total_result['count'] if total_result else 0
            
            # With VAT numbers
            vat_result = self.db.query_one("SELECT COUNT(*) as count FROM sa_merchants WHERE vat_no IS NOT NULL AND vat_no != ''")
            stats['merchants_with_vat'] = vat_result['count'] if vat_result else 0
            
            # With aliases
            alias_result = self.db.query_one("SELECT COUNT(*) as count FROM sa_merchants WHERE aliases IS NOT NULL AND aliases != ''")
            stats['merchants_with_aliases'] = alias_result['count'] if alias_result else 0
            
            # Top merchants by expense count (if expenses table exists)
            try:
                top_merchants = self.db.query_all("""
                    SELECT m.canonical, COUNT(e.id) as expense_count
                    FROM sa_merchants m
                    LEFT JOIN sa_expenses e ON m.id = e.merchant_id
                    GROUP BY m.id, m.canonical
                    HAVING expense_count > 0
                    ORDER BY expense_count DESC
                    LIMIT 10
                """)
                stats['top_merchants_by_usage'] = [
                    {'canonical': m['canonical'], 'expense_count': m['expense_count']}
                    for m in top_merchants
                ]
            except Exception:
                # Expenses table might not exist yet
                pass
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Merchant statistics failed: {e}")
            return {
                'total_merchants': 0,
                'merchants_with_vat': 0,
                'merchants_with_aliases': 0,
                'top_merchants_by_usage': [],
                'error': str(e)
            }


# Factory function for easy import
def create_merchant_normalizer(db_manager) -> MerchantNormalizer:
    """Create merchant normalizer instance."""
    return MerchantNormalizer(db_manager)
