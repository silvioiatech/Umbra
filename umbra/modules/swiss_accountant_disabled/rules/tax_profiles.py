"""
Swiss Tax Profiles Manager
Manages canton/year specific tax profiles with deduction caps and allowances.
"""
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime, date
from enum import Enum
import json
import logging


class MaritalStatus(Enum):
    """Marital status options."""
    SINGLE = "single"
    MARRIED = "married"
    DIVORCED = "divorced"
    WIDOWED = "widowed"
    REGISTERED_PARTNERSHIP = "registered_partnership"


class TransportMode(Enum):
    """Transportation modes for commuting."""
    PUBLIC_TRANSPORT = "public_transport"
    CAR = "car"
    BICYCLE = "bicycle"
    WALKING = "walking"
    MIXED = "mixed"


class TaxProfileManager:
    """Manages Swiss tax profiles by canton and year."""
    
    def __init__(self, db_manager):
        """Initialize tax profile manager.
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Swiss cantons
        self.cantons = {
            'AG': 'Aargau', 'AI': 'Appenzell Innerrhoden', 'AR': 'Appenzell Ausserrhoden',
            'BE': 'Bern', 'BL': 'Basel-Landschaft', 'BS': 'Basel-Stadt',
            'FR': 'Fribourg', 'GE': 'Geneva', 'GL': 'Glarus', 'GR': 'Graubünden',
            'JU': 'Jura', 'LU': 'Luzern', 'NE': 'Neuchâtel', 'NW': 'Nidwalden',
            'OW': 'Obwalden', 'SG': 'St. Gallen', 'SH': 'Schaffhausen', 'SO': 'Solothurn',
            'SZ': 'Schwyz', 'TG': 'Thurgau', 'TI': 'Ticino', 'UR': 'Uri',
            'VD': 'Vaud', 'VS': 'Valais', 'ZG': 'Zug', 'ZH': 'Zürich'
        }
        
        # Initialize default tax profiles
        self._init_tax_profiles()
    
    def _init_tax_profiles(self):
        """Initialize default tax profiles for Swiss cantons."""
        try:
            # Create tax profiles table if not exists
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS sa_tax_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    canton TEXT NOT NULL,
                    commune TEXT,
                    marital_status TEXT,
                    children_count INTEGER DEFAULT 0,
                    religion TEXT,
                    commute_km INTEGER DEFAULT 0,
                    commute_days_per_week INTEGER DEFAULT 5,
                    transport_mode TEXT DEFAULT 'public_transport',
                    source_tax_percentage REAL DEFAULT 0,
                    profile_data_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, year)
                )
            """)
            
            # Insert default federal tax data for 2024
            self._insert_federal_tax_data_2024()
            
            # Insert canton-specific data
            self._insert_canton_tax_data_2024()
            
        except Exception as e:
            self.logger.error(f"Tax profiles initialization failed: {e}")
    
    def _insert_federal_tax_data_2024(self):
        """Insert federal tax data for 2024."""
        federal_data = {
            'year': 2024,
            'country': 'CH',
            'federal_deductions': {
                'professional_expenses': {
                    'minimum': 2000,  # CHF
                    'maximum': None,  # No maximum for proven expenses
                    'flat_rate_max': 4000  # CHF
                },
                'commute_public_transport': {
                    'maximum': 3000  # CHF per year
                },
                'commute_car': {
                    'rate_per_km': 0.70,  # CHF per km
                    'minimum_distance': 2,  # km one way
                    'maximum_deduction': None
                },
                'meals_work': {
                    'rate_per_meal': 15,  # CHF
                    'maximum_per_day': 30,  # CHF
                    'minimum_hours_away': 5  # hours
                },
                'pillar_3a': {
                    'employed_max': 7056,  # CHF for 2024
                    'self_employed_max': 35280  # CHF for 2024 (20% of income, max)
                },
                'education': {
                    'professional_max': 12000,  # CHF per year
                    'retraining_max': 20000  # CHF per year
                },
                'childcare': {
                    'maximum': 25000,  # CHF per child per year
                    'minimum_age': 0,
                    'maximum_age': 14
                },
                'donations': {
                    'minimum': 100,  # CHF
                    'maximum_percentage': 20  # % of net income
                },
                'medical_expenses': {
                    'threshold_percentage': 5  # % of net income
                }
            },
            'social_insurance_2024': {
                'ahv_iv_eo': {
                    'rate': 5.3,  # %
                    'max_income': 148200  # CHF
                },
                'alv': {
                    'rate_standard': 1.1,  # %
                    'rate_high_income': 0.5,  # % additional above threshold
                    'high_income_threshold': 148200  # CHF
                },
                'bvg': {
                    'coordination_deduction': 25725,  # CHF
                    'minimum_insured_salary': 22050,  # CHF
                    'maximum_insured_salary': 88200  # CHF
                },
                'uvg_nbu': {
                    'rate': 1.4  # % (varies by employer)
                }
            }
        }
        
        # Store in database as JSON
        existing = self.db.query_one(
            "SELECT id FROM sa_user_rules WHERE rule_json LIKE '%federal_tax_data_2024%'"
        )
        
        if not existing:
            self.db.execute(
                "INSERT INTO sa_user_rules (user_id, rule_json) VALUES (?, ?)",
                ('system', json.dumps({'type': 'federal_tax_data_2024', 'data': federal_data}))
            )
    
    def _insert_canton_tax_data_2024(self):
        """Insert canton-specific tax data for 2024."""
        # Sample canton data - in production, this would be comprehensive
        canton_data = {
            'ZH': {  # Zürich
                'multiplier': 1.0,  # Canton tax multiplier
                'commune_avg_multiplier': 1.19,
                'specific_deductions': {
                    'commute_public_transport_bonus': 500,  # Additional CHF
                    'home_office_max': 1500,  # CHF per year
                    'insurance_bonus': 600  # CHF
                },
                'childcare_additional': 2000  # CHF additional per child
            },
            'GE': {  # Geneva
                'multiplier': 1.0,
                'commune_avg_multiplier': 0.455,
                'specific_deductions': {
                    'commute_public_transport_bonus': 1000,
                    'home_office_max': 2000,
                    'insurance_bonus': 800
                },
                'childcare_additional': 3000
            },
            'BS': {  # Basel-Stadt
                'multiplier': 1.0,
                'commune_avg_multiplier': 0.75,
                'specific_deductions': {
                    'commute_public_transport_bonus': 800,
                    'home_office_max': 1800,
                    'insurance_bonus': 700
                },
                'childcare_additional': 2500
            },
            'VD': {  # Vaud
                'multiplier': 1.0,
                'commune_avg_multiplier': 0.64,
                'specific_deductions': {
                    'commute_public_transport_bonus': 600,
                    'home_office_max': 1200,
                    'insurance_bonus': 500
                },
                'childcare_additional': 1800
            },
            'BE': {  # Bern
                'multiplier': 1.0,
                'commune_avg_multiplier': 1.54,
                'specific_deductions': {
                    'commute_public_transport_bonus': 400,
                    'home_office_max': 1000,
                    'insurance_bonus': 400
                },
                'childcare_additional': 1500
            }
        }
        
        for canton_code, data in canton_data.items():
            existing = self.db.query_one(
                "SELECT id FROM sa_user_rules WHERE rule_json LIKE ? AND rule_json LIKE ?",
                (f'%canton_tax_data_2024%', f'%{canton_code}%')
            )
            
            if not existing:
                self.db.execute(
                    "INSERT INTO sa_user_rules (user_id, rule_json) VALUES (?, ?)",
                    ('system', json.dumps({
                        'type': 'canton_tax_data_2024',
                        'canton': canton_code,
                        'data': data
                    }))
                )
    
    def set_tax_profile(self, 
                       user_id: str,
                       year: int,
                       canton: str,
                       commune: str = None,
                       marital_status: MaritalStatus = MaritalStatus.SINGLE,
                       children_count: int = 0,
                       religion: str = None,
                       commute_km: int = 0,
                       commute_days_per_week: int = 5,
                       transport_mode: TransportMode = TransportMode.PUBLIC_TRANSPORT,
                       source_tax_percentage: float = 0) -> Dict[str, Any]:
        """Set tax profile for user.
        
        Args:
            user_id: User identifier
            year: Tax year
            canton: Swiss canton code (e.g., 'ZH', 'GE')
            commune: Commune/municipality
            marital_status: Marital status
            children_count: Number of children
            religion: Religion (for church tax)
            commute_km: Commute distance in km (one way)
            commute_days_per_week: Days per week commuting
            transport_mode: Mode of transportation
            source_tax_percentage: Source tax percentage if applicable
            
        Returns:
            Dict with profile setting result
        """
        try:
            # Validate canton
            if canton not in self.cantons:
                return {
                    'success': False,
                    'error': f'Invalid canton: {canton}',
                    'valid_cantons': list(self.cantons.keys())
                }
            
            # Calculate estimated annual commute costs
            commute_costs = self._calculate_commute_allowance(
                commute_km, 
                commute_days_per_week, 
                transport_mode,
                canton,
                year
            )
            
            # Get canton-specific data
            canton_data = self._get_canton_data(canton, year)
            
            # Build profile data
            profile_data = {
                'canton_name': self.cantons[canton],
                'commute_allowance': commute_costs,
                'canton_specific': canton_data,
                'estimated_deductions': self._estimate_deductions(
                    year, canton, marital_status, children_count, commute_costs
                )
            }
            
            # Upsert tax profile
            existing = self.db.query_one(
                "SELECT id FROM sa_tax_profiles WHERE user_id = ? AND year = ?",
                (user_id, year)
            )
            
            if existing:
                # Update existing
                self.db.execute("""
                    UPDATE sa_tax_profiles SET
                        canton = ?, commune = ?, marital_status = ?, children_count = ?,
                        religion = ?, commute_km = ?, commute_days_per_week = ?,
                        transport_mode = ?, source_tax_percentage = ?, profile_data_json = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    canton, commune, marital_status.value, children_count,
                    religion, commute_km, commute_days_per_week,
                    transport_mode.value, source_tax_percentage,
                    json.dumps(profile_data), existing['id']
                ))
                profile_id = existing['id']
            else:
                # Insert new
                profile_id = self.db.execute("""
                    INSERT INTO sa_tax_profiles (
                        user_id, year, canton, commune, marital_status, children_count,
                        religion, commute_km, commute_days_per_week, transport_mode,
                        source_tax_percentage, profile_data_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, year, canton, commune, marital_status.value, children_count,
                    religion, commute_km, commute_days_per_week, transport_mode.value,
                    source_tax_percentage, json.dumps(profile_data)
                ))
            
            return {
                'success': True,
                'profile_id': profile_id,
                'canton': f"{canton} ({self.cantons[canton]})",
                'year': year,
                'estimated_annual_commute_deduction': commute_costs['annual_deduction'],
                'estimated_total_deductions': profile_data['estimated_deductions']['total'],
                'profile_data': profile_data
            }
            
        except Exception as e:
            self.logger.error(f"Tax profile setting failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_tax_profile(self, user_id: str, year: int) -> Optional[Dict[str, Any]]:
        """Get tax profile for user and year.
        
        Args:
            user_id: User identifier
            year: Tax year
            
        Returns:
            Tax profile data or None if not found
        """
        try:
            profile = self.db.query_one(
                "SELECT * FROM sa_tax_profiles WHERE user_id = ? AND year = ?",
                (user_id, year)
            )
            
            if not profile:
                return None
            
            # Parse profile data
            profile_data = json.loads(profile['profile_data_json']) if profile['profile_data_json'] else {}
            
            return {
                'id': profile['id'],
                'user_id': profile['user_id'],
                'year': profile['year'],
                'canton': profile['canton'],
                'canton_name': self.cantons.get(profile['canton'], profile['canton']),
                'commune': profile['commune'],
                'marital_status': profile['marital_status'],
                'children_count': profile['children_count'],
                'religion': profile['religion'],
                'commute_km': profile['commute_km'],
                'commute_days_per_week': profile['commute_days_per_week'],
                'transport_mode': profile['transport_mode'],
                'source_tax_percentage': profile['source_tax_percentage'],
                'profile_data': profile_data,
                'created_at': profile['created_at'],
                'updated_at': profile['updated_at']
            }
            
        except Exception as e:
            self.logger.error(f"Tax profile retrieval failed: {e}")
            return None
    
    def _calculate_commute_allowance(self, 
                                   km: int, 
                                   days_per_week: int, 
                                   transport_mode: TransportMode,
                                   canton: str,
                                   year: int) -> Dict[str, Any]:
        """Calculate commute allowance for given parameters.
        
        Args:
            km: Distance in km (one way)
            days_per_week: Working days per week
            transport_mode: Mode of transportation
            canton: Canton code
            year: Tax year
            
        Returns:
            Dict with commute calculations
        """
        try:
            # Federal base rates for 2024
            federal_data = self._get_federal_data(year)
            
            if transport_mode == TransportMode.PUBLIC_TRANSPORT:
                # Public transport: actual costs up to maximum
                estimated_annual_cost = km * 2 * days_per_week * 48 * 0.30  # Rough estimate
                max_deduction = federal_data.get('commute_public_transport', {}).get('maximum', 3000)
                annual_deduction = min(estimated_annual_cost, max_deduction)
                
                # Canton bonus
                canton_data = self._get_canton_data(canton, year)
                bonus = canton_data.get('specific_deductions', {}).get('commute_public_transport_bonus', 0)
                annual_deduction += bonus
                
            elif transport_mode == TransportMode.CAR:
                # Car: per km rate
                rate_per_km = federal_data.get('commute_car', {}).get('rate_per_km', 0.70)
                min_distance = federal_data.get('commute_car', {}).get('minimum_distance', 2)
                
                if km >= min_distance:
                    annual_deduction = km * 2 * days_per_week * 48 * rate_per_km
                else:
                    annual_deduction = 0
                    
            else:
                # Other modes (bicycle, walking, mixed)
                annual_deduction = 0
            
            return {
                'transport_mode': transport_mode.value,
                'distance_km': km,
                'days_per_week': days_per_week,
                'annual_deduction': round(annual_deduction, 2),
                'calculation_method': 'federal_rates_2024'
            }
            
        except Exception as e:
            self.logger.error(f"Commute allowance calculation failed: {e}")
            return {
                'transport_mode': transport_mode.value,
                'distance_km': km,
                'days_per_week': days_per_week,
                'annual_deduction': 0,
                'error': str(e)
            }
    
    def _get_federal_data(self, year: int) -> Dict[str, Any]:
        """Get federal tax data for year."""
        try:
            rule = self.db.query_one(
                "SELECT rule_json FROM sa_user_rules WHERE rule_json LIKE ? AND rule_json LIKE ?",
                (f'%federal_tax_data_{year}%', '%federal_deductions%')
            )
            
            if rule:
                data = json.loads(rule['rule_json'])
                return data.get('data', {}).get('federal_deductions', {})
            
            # Fallback to default values
            return {
                'commute_public_transport': {'maximum': 3000},
                'commute_car': {'rate_per_km': 0.70, 'minimum_distance': 2}
            }
            
        except Exception as e:
            self.logger.error(f"Federal data retrieval failed: {e}")
            return {}
    
    def _get_canton_data(self, canton: str, year: int) -> Dict[str, Any]:
        """Get canton-specific tax data."""
        try:
            rule = self.db.query_one(
                "SELECT rule_json FROM sa_user_rules WHERE rule_json LIKE ? AND rule_json LIKE ?",
                (f'%canton_tax_data_{year}%', f'%{canton}%')
            )
            
            if rule:
                data = json.loads(rule['rule_json'])
                return data.get('data', {})
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Canton data retrieval failed: {e}")
            return {}
    
    def _estimate_deductions(self, 
                           year: int,
                           canton: str,
                           marital_status: MaritalStatus,
                           children_count: int,
                           commute_costs: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate total deductions for profile."""
        try:
            federal_data = self._get_federal_data(year)
            canton_data = self._get_canton_data(canton, year)
            
            # Professional expenses minimum
            professional_min = federal_data.get('professional_expenses', {}).get('minimum', 2000)
            
            # Commute
            commute_deduction = commute_costs.get('annual_deduction', 0)
            
            # Pillar 3a typical
            pillar_3a_typical = federal_data.get('pillar_3a', {}).get('employed_max', 7056)
            
            # Childcare estimate
            childcare_max_per_child = federal_data.get('childcare', {}).get('maximum', 25000)
            canton_childcare_bonus = canton_data.get('childcare_additional', 0)
            childcare_estimate = children_count * (childcare_max_per_child + canton_childcare_bonus)
            
            # Insurance estimate
            insurance_estimate = canton_data.get('specific_deductions', {}).get('insurance_bonus', 500)
            
            total_estimate = (
                professional_min + 
                commute_deduction + 
                pillar_3a_typical + 
                childcare_estimate + 
                insurance_estimate
            )
            
            return {
                'professional_expenses': professional_min,
                'commute': commute_deduction,
                'pillar_3a': pillar_3a_typical,
                'childcare': childcare_estimate,
                'insurance': insurance_estimate,
                'total': total_estimate,
                'breakdown': {
                    'federal_base': professional_min + pillar_3a_typical,
                    'canton_specific': commute_deduction + childcare_estimate + insurance_estimate
                }
            }
            
        except Exception as e:
            self.logger.error(f"Deduction estimation failed: {e}")
            return {'total': 0, 'error': str(e)}
    
    def calculate_tax_savings(self, 
                            user_id: str, 
                            year: int, 
                            gross_income: Decimal,
                            additional_deductions: Decimal = Decimal('0')) -> Dict[str, Any]:
        """Calculate estimated tax savings for given income and deductions.
        
        Args:
            user_id: User identifier
            year: Tax year
            gross_income: Annual gross income
            additional_deductions: Additional deductions beyond profile
            
        Returns:
            Dict with tax calculation
        """
        try:
            profile = self.get_tax_profile(user_id, year)
            if not profile:
                return {
                    'success': False,
                    'error': 'No tax profile found for user and year'
                }
            
            # Get estimated deductions from profile
            estimated_deductions = profile['profile_data'].get('estimated_deductions', {})
            total_deductions = Decimal(str(estimated_deductions.get('total', 0))) + additional_deductions
            
            # Simplified tax calculation (this would be much more complex in reality)
            # This is just an estimate for demonstration
            
            # Social insurance deductions (approximate)
            social_insurance = gross_income * Decimal('0.064')  # AHV/IV + ALV + BVG approx
            
            # Taxable income
            taxable_income = gross_income - total_deductions - social_insurance
            
            # Simplified progressive tax (very rough estimate)
            canton = profile['canton']
            canton_data = self._get_canton_data(canton, year)
            canton_multiplier = Decimal(str(canton_data.get('multiplier', 1.0)))
            commune_multiplier = Decimal(str(canton_data.get('commune_avg_multiplier', 1.0)))
            
            # Federal tax (simplified)
            if taxable_income <= 14500:
                federal_tax = Decimal('0')
            elif taxable_income <= 31600:
                federal_tax = (taxable_income - 14500) * Decimal('0.0077')
            else:
                federal_tax = 131 + (taxable_income - 31600) * Decimal('0.088')
            
            # Canton/commune tax (very simplified)
            canton_commune_tax = federal_tax * canton_multiplier * commune_multiplier
            
            total_tax = federal_tax + canton_commune_tax
            net_income = gross_income - social_insurance - total_tax
            
            return {
                'success': True,
                'gross_income': gross_income,
                'social_insurance_deductions': social_insurance,
                'total_deductions': total_deductions,
                'taxable_income': taxable_income,
                'federal_tax': federal_tax,
                'canton_commune_tax': canton_commune_tax,
                'total_tax': total_tax,
                'net_income': net_income,
                'effective_tax_rate': (total_tax / gross_income * 100) if gross_income > 0 else 0,
                'deduction_breakdown': estimated_deductions,
                'note': 'This is a simplified calculation for estimation purposes only'
            }
            
        except Exception as e:
            self.logger.error(f"Tax calculation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Factory function for easy import
def create_tax_profile_manager(db_manager) -> TaxProfileManager:
    """Create tax profile manager instance."""
    return TaxProfileManager(db_manager)
