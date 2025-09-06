"""
Swiss VAT Engine
Handles Swiss VAT calculations with support for multiple rates (8.1%, 2.6%, 3.8%, 0%) and prorata calculations.
"""
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from enum import Enum
import json
import logging


class SwissVATRate(Enum):
    """Swiss VAT rate types."""
    STANDARD = 8.1      # Standard rate for most goods and services
    REDUCED = 2.6       # Reduced rate for food, books, medicine, etc.
    SPECIAL = 3.8       # Special rate for accommodation/hotels
    ZERO = 0.0          # Zero rate for exports, exempt services


class VATCalculationType(Enum):
    """Types of VAT calculations."""
    INCLUSIVE = "inclusive"     # VAT included in amount
    EXCLUSIVE = "exclusive"     # VAT to be added to amount
    PRORATA = "prorata"        # Mixed private/business use


class VATEngine:
    """Swiss VAT calculation engine."""
    
    def __init__(self):
        """Initialize VAT engine."""
        self.logger = logging.getLogger(__name__)
        
        # Current Swiss VAT rates (effective 2024)
        self.current_rates = {
            'standard': Decimal('8.1'),
            'reduced': Decimal('2.6'),
            'special': Decimal('3.8'),
            'zero': Decimal('0.0')
        }
        
        # Category mappings to VAT rates
        self.category_vat_mapping = {
            # Standard rate (8.1%)
            'office_supplies': 'standard',
            'electronics': 'standard',
            'clothing': 'standard',
            'services_professional': 'standard',
            'transport_services': 'standard',
            'entertainment': 'standard',
            'fuel': 'standard',
            'alcohol': 'standard',
            'tobacco': 'standard',
            
            # Reduced rate (2.6%)
            'food_groceries': 'reduced',
            'beverages_non_alcoholic': 'reduced',
            'books': 'reduced',
            'newspapers': 'reduced',
            'medicine': 'reduced',
            'medical_devices': 'reduced',
            'agricultural_products': 'reduced',
            'flowers_plants': 'reduced',
            'animal_feed': 'reduced',
            
            # Special rate (3.8%)
            'accommodation': 'special',
            'hotel_services': 'special',
            'camping': 'special',
            'holiday_rental': 'special',
            
            # Zero rate (0%)
            'exports': 'zero',
            'financial_services': 'zero',
            'insurance': 'zero',
            'real_estate': 'zero',
            'education': 'zero',
            'healthcare': 'zero',
            'postal_services': 'zero'
        }
    
    def calculate_vat(self, 
                     net_amount: Decimal, 
                     vat_rate: Decimal, 
                     calculation_type: VATCalculationType = VATCalculationType.EXCLUSIVE) -> Dict[str, Decimal]:
        """Calculate VAT for given amount and rate.
        
        Args:
            net_amount: Net amount (excluding VAT)
            vat_rate: VAT rate as percentage (e.g., 8.1 for 8.1%)
            calculation_type: Type of calculation
            
        Returns:
            Dict with net, vat, and gross amounts
        """
        try:
            vat_rate_decimal = vat_rate / Decimal('100')
            
            if calculation_type == VATCalculationType.EXCLUSIVE:
                # VAT to be added
                net = net_amount
                vat = (net * vat_rate_decimal).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                gross = net + vat
                
            elif calculation_type == VATCalculationType.INCLUSIVE:
                # VAT included in amount
                gross = net_amount
                net = (gross / (Decimal('1') + vat_rate_decimal)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                vat = gross - net
                
            else:  # PRORATA handled separately
                return self._calculate_prorata_vat(net_amount, vat_rate)
            
            return {
                'net_amount': net,
                'vat_amount': vat,
                'gross_amount': gross,
                'vat_rate': vat_rate,
                'calculation_type': calculation_type.value
            }
            
        except Exception as e:
            self.logger.error(f"VAT calculation failed: {e}")
            return {
                'net_amount': Decimal('0'),
                'vat_amount': Decimal('0'),
                'gross_amount': Decimal('0'),
                'vat_rate': vat_rate,
                'calculation_type': calculation_type.value,
                'error': str(e)
            }
    
    def parse_multi_rate_receipt(self, receipt_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse receipt with multiple VAT rates.
        
        Args:
            receipt_data: Receipt data with line items
            
        Returns:
            Dict with VAT breakdown by rate
        """
        try:
            vat_breakdown = {
                'lines': [],
                'totals_by_rate': {},
                'total_net': Decimal('0'),
                'total_vat': Decimal('0'),
                'total_gross': Decimal('0'),
                'rates_found': []
            }
            
            lines = receipt_data.get('line_items', [])
            
            for line in lines:
                line_amount = Decimal(str(line.get('amount', 0)))
                line_category = line.get('category', 'standard')
                
                # Determine VAT rate for this line
                vat_rate_type = self.category_vat_mapping.get(line_category, 'standard')
                vat_rate = self.current_rates[vat_rate_type]
                
                # Calculate VAT for this line
                vat_calc = self.calculate_vat(
                    line_amount, 
                    vat_rate, 
                    VATCalculationType.INCLUSIVE  # Assume prices include VAT
                )
                
                # Add to breakdown
                line_breakdown = {
                    'description': line.get('description', ''),
                    'category': line_category,
                    'net_amount': vat_calc['net_amount'],
                    'vat_rate': vat_rate,
                    'vat_amount': vat_calc['vat_amount'],
                    'gross_amount': vat_calc['gross_amount']
                }
                
                vat_breakdown['lines'].append(line_breakdown)
                
                # Accumulate totals by rate
                rate_key = f"{vat_rate}%"
                if rate_key not in vat_breakdown['totals_by_rate']:
                    vat_breakdown['totals_by_rate'][rate_key] = {
                        'rate': vat_rate,
                        'net_total': Decimal('0'),
                        'vat_total': Decimal('0'),
                        'gross_total': Decimal('0')
                    }
                
                vat_breakdown['totals_by_rate'][rate_key]['net_total'] += vat_calc['net_amount']
                vat_breakdown['totals_by_rate'][rate_key]['vat_total'] += vat_calc['vat_amount']
                vat_breakdown['totals_by_rate'][rate_key]['gross_total'] += vat_calc['gross_amount']
                
                # Accumulate grand totals
                vat_breakdown['total_net'] += vat_calc['net_amount']
                vat_breakdown['total_vat'] += vat_calc['vat_amount']
                vat_breakdown['total_gross'] += vat_calc['gross_amount']
                
                # Track rates found
                if vat_rate not in vat_breakdown['rates_found']:
                    vat_breakdown['rates_found'].append(vat_rate)
            
            return vat_breakdown
            
        except Exception as e:
            self.logger.error(f"Multi-rate receipt parsing failed: {e}")
            return {
                'error': str(e),
                'lines': [],
                'totals_by_rate': {},
                'total_net': Decimal('0'),
                'total_vat': Decimal('0'),
                'total_gross': Decimal('0'),
                'rates_found': []
            }
    
    def calculate_prorata_vat(self, 
                             total_amount: Decimal, 
                             business_percentage: Decimal,
                             vat_rate: Decimal) -> Dict[str, Any]:
        """Calculate prorata VAT for mixed business/private use.
        
        Args:
            total_amount: Total amount of expense
            business_percentage: Percentage used for business (0-100)
            vat_rate: VAT rate as percentage
            
        Returns:
            Dict with business and private portions
        """
        try:
            if business_percentage < 0 or business_percentage > 100:
                raise ValueError(f"Business percentage must be 0-100, got {business_percentage}")
            
            business_pct = business_percentage / Decimal('100')
            private_pct = Decimal('1') - business_pct
            
            # Calculate total VAT
            total_vat_calc = self.calculate_vat(total_amount, vat_rate, VATCalculationType.INCLUSIVE)
            
            # Split business/private
            business_gross = (total_amount * business_pct).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            private_gross = (total_amount * private_pct).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            business_vat = (total_vat_calc['vat_amount'] * business_pct).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            private_vat = (total_vat_calc['vat_amount'] * private_pct).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            business_net = business_gross - business_vat
            private_net = private_gross - private_vat
            
            return {
                'total': {
                    'net_amount': total_vat_calc['net_amount'],
                    'vat_amount': total_vat_calc['vat_amount'],
                    'gross_amount': total_vat_calc['gross_amount']
                },
                'business': {
                    'percentage': business_percentage,
                    'net_amount': business_net,
                    'vat_amount': business_vat,
                    'gross_amount': business_gross,
                    'deductible_vat': business_vat  # VAT that can be reclaimed
                },
                'private': {
                    'percentage': Decimal('100') - business_percentage,
                    'net_amount': private_net,
                    'vat_amount': private_vat,
                    'gross_amount': private_gross
                },
                'vat_rate': vat_rate,
                'calculation_type': 'prorata'
            }
            
        except Exception as e:
            self.logger.error(f"Prorata VAT calculation failed: {e}")
            return {
                'error': str(e),
                'total': {'net_amount': Decimal('0'), 'vat_amount': Decimal('0'), 'gross_amount': Decimal('0')},
                'business': {'percentage': Decimal('0'), 'net_amount': Decimal('0'), 'vat_amount': Decimal('0'), 'gross_amount': Decimal('0'), 'deductible_vat': Decimal('0')},
                'private': {'percentage': Decimal('0'), 'net_amount': Decimal('0'), 'vat_amount': Decimal('0'), 'gross_amount': Decimal('0')},
                'vat_rate': vat_rate,
                'calculation_type': 'prorata'
            }
    
    def get_vat_rate_for_category(self, category: str) -> Decimal:
        """Get VAT rate for given category.
        
        Args:
            category: Category code
            
        Returns:
            VAT rate as Decimal
        """
        rate_type = self.category_vat_mapping.get(category, 'standard')
        return self.current_rates[rate_type]
    
    def detect_vat_rates_in_text(self, text: str) -> List[Dict[str, Any]]:
        """Detect VAT rates mentioned in OCR text.
        
        Args:
            text: OCR text to analyze
            
        Returns:
            List of detected VAT rates with context
        """
        import re
        
        detected_rates = []
        
        # Swiss VAT rate patterns
        vat_patterns = [
            r'(?:MWST|TVA|IVA|VAT)\s*([0-9.,]+)\s*%',
            r'([0-9.,]+)\s*%\s*(?:MWST|TVA|IVA|VAT)',
            r'(?:Mehrwertsteuer|Taxe|Imposta)\s*([0-9.,]+)\s*%',
            r'([0-9.,]+)\s*%\s*(?:Mehrwertsteuer|Taxe|Imposta)'
        ]
        
        for pattern in vat_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    rate_str = match.group(1).replace(',', '.')
                    rate = Decimal(rate_str)
                    
                    # Check if it's a valid Swiss VAT rate
                    valid_rates = [Decimal('8.1'), Decimal('2.6'), Decimal('3.8'), Decimal('0.0')]
                    if rate in valid_rates:
                        detected_rates.append({
                            'rate': rate,
                            'text_match': match.group(0),
                            'position': match.span(),
                            'rate_type': self._get_rate_type(rate),
                            'confidence': 0.9
                        })
                    elif abs(rate - Decimal('7.7')) < Decimal('0.1'):
                        # Old rate (before 2024)
                        detected_rates.append({
                            'rate': rate,
                            'text_match': match.group(0),
                            'position': match.span(),
                            'rate_type': 'old_standard',
                            'confidence': 0.8,
                            'note': 'Old VAT rate (pre-2024)'
                        })
                        
                except (ValueError, TypeError):
                    continue
        
        return detected_rates
    
    def _get_rate_type(self, rate: Decimal) -> str:
        """Get rate type for given rate."""
        if rate == Decimal('8.1'):
            return 'standard'
        elif rate == Decimal('2.6'):
            return 'reduced'
        elif rate == Decimal('3.8'):
            return 'special'
        elif rate == Decimal('0.0'):
            return 'zero'
        else:
            return 'unknown'
    
    def generate_vat_report(self, 
                           expenses: List[Dict[str, Any]], 
                           period_start: date, 
                           period_end: date) -> Dict[str, Any]:
        """Generate VAT report for given period.
        
        Args:
            expenses: List of expense records
            period_start: Start of reporting period
            period_end: End of reporting period
            
        Returns:
            Dict with VAT report data
        """
        try:
            report = {
                'period': {
                    'start': period_start.isoformat(),
                    'end': period_end.isoformat()
                },
                'totals_by_rate': {},
                'total_input_vat': Decimal('0'),
                'total_net_amount': Decimal('0'),
                'total_gross_amount': Decimal('0'),
                'expense_count': 0,
                'deductible_vat': Decimal('0')
            }
            
            for expense in expenses:
                expense_date = datetime.fromisoformat(expense.get('date_local', '')).date()
                
                # Check if expense is in period
                if not (period_start <= expense_date <= period_end):
                    continue
                
                report['expense_count'] += 1
                
                # Parse VAT breakdown
                vat_breakdown = expense.get('vat_breakdown_json', '{}')
                if isinstance(vat_breakdown, str):
                    vat_breakdown = json.loads(vat_breakdown) if vat_breakdown else {}
                
                amount_cents = expense.get('amount_cents', 0)
                amount = Decimal(amount_cents) / Decimal('100')
                pro_pct = Decimal(str(expense.get('pro_pct', 0)))
                
                # Determine VAT rate
                if 'rate' in vat_breakdown:
                    vat_rate = Decimal(str(vat_breakdown['rate']))
                else:
                    category = expense.get('category_code', 'standard')
                    vat_rate = self.get_vat_rate_for_category(category)
                
                # Calculate VAT
                if pro_pct > 0:
                    # Prorata calculation
                    vat_calc = self.calculate_prorata_vat(amount, pro_pct, vat_rate)
                    deductible_vat = vat_calc['business']['deductible_vat']
                    net_amount = vat_calc['business']['net_amount']
                    gross_amount = vat_calc['business']['gross_amount']
                else:
                    # Standard calculation
                    vat_calc = self.calculate_vat(amount, vat_rate, VATCalculationType.INCLUSIVE)
                    deductible_vat = vat_calc['vat_amount']
                    net_amount = vat_calc['net_amount']
                    gross_amount = vat_calc['gross_amount']
                
                # Accumulate by rate
                rate_key = f"{vat_rate}%"
                if rate_key not in report['totals_by_rate']:
                    report['totals_by_rate'][rate_key] = {
                        'rate': vat_rate,
                        'net_total': Decimal('0'),
                        'vat_total': Decimal('0'),
                        'gross_total': Decimal('0'),
                        'deductible_vat_total': Decimal('0'),
                        'expense_count': 0
                    }
                
                report['totals_by_rate'][rate_key]['net_total'] += net_amount
                report['totals_by_rate'][rate_key]['vat_total'] += vat_calc.get('vat_amount', Decimal('0'))
                report['totals_by_rate'][rate_key]['gross_total'] += gross_amount
                report['totals_by_rate'][rate_key]['deductible_vat_total'] += deductible_vat
                report['totals_by_rate'][rate_key]['expense_count'] += 1
                
                # Accumulate totals
                report['total_net_amount'] += net_amount
                report['total_gross_amount'] += gross_amount
                report['deductible_vat'] += deductible_vat
            
            report['total_input_vat'] = sum(
                rate_data['vat_total'] for rate_data in report['totals_by_rate'].values()
            )
            
            return report
            
        except Exception as e:
            self.logger.error(f"VAT report generation failed: {e}")
            return {
                'error': str(e),
                'period': {'start': period_start.isoformat(), 'end': period_end.isoformat()},
                'totals_by_rate': {},
                'total_input_vat': Decimal('0'),
                'total_net_amount': Decimal('0'),
                'total_gross_amount': Decimal('0'),
                'expense_count': 0,
                'deductible_vat': Decimal('0')
            }
    
    def _calculate_prorata_vat(self, amount: Decimal, rate: Decimal) -> Dict[str, Decimal]:
        """Helper for prorata VAT calculation."""
        # This is called when calculation_type is PRORATA
        # For now, assume 50% business use as default
        return self.calculate_prorata_vat(amount, Decimal('50'), rate)


# Factory function for easy import
def create_vat_engine() -> VATEngine:
    """Create VAT engine instance."""
    return VATEngine()
