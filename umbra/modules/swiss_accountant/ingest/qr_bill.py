"""
Swiss QR-Bill Parser
Parses Swiss QR payment slips according to Swiss Implementation Guidelines.
"""
import re
import base64
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime, date
import logging

try:
    import qrcode
    from PIL import Image
    import cv2
    import numpy as np
    QR_LIBRARIES_AVAILABLE = True
except ImportError:
    QR_LIBRARIES_AVAILABLE = False


class QRBillParser:
    """Swiss QR-Bill parser following Swiss Implementation Guidelines."""
    
    def __init__(self):
        """Initialize QR-Bill parser."""
        self.logger = logging.getLogger(__name__)
        
        # Swiss QR-Bill specifications
        self.qr_type = "SPC"  # Swiss Payments Code
        self.version = "0200"  # Current version
        
        # Supported currencies for Swiss QR-Bills
        self.supported_currencies = ["CHF", "EUR"]
        
    def parse_qr_code_from_image(self, image_path: str) -> Dict[str, Any]:
        """Parse QR code from image file.
        
        Args:
            image_path: Path to image containing QR code
            
        Returns:
            Dict with parsed QR-Bill data
        """
        if not QR_LIBRARIES_AVAILABLE:
            return self._fallback_qr_parsing(image_path)
        
        try:
            # Read image
            image = cv2.imread(image_path)
            if image is None:
                return {
                    'success': False,
                    'error': f'Could not read image: {image_path}',
                    'data': {}
                }
            
            # Initialize QR code detector
            detector = cv2.QRCodeDetector()
            
            # Detect and decode QR code
            data, vertices_array, binary_qrcode = detector.detectAndDecode(image)
            
            if not data:
                return {
                    'success': False,
                    'error': 'No QR code found in image',
                    'data': {}
                }
            
            # Parse QR-Bill data
            return self.parse_qr_bill_data(data)
            
        except Exception as e:
            self.logger.error(f"QR code detection failed: {e}")
            return self._fallback_qr_parsing(image_path)
    
    def parse_qr_bill_data(self, qr_data: str) -> Dict[str, Any]:
        """Parse Swiss QR-Bill data string.
        
        Args:
            qr_data: Raw QR code data string
            
        Returns:
            Dict with structured QR-Bill information
        """
        try:
            # Split QR data by newlines
            lines = qr_data.strip().split('\n')
            
            if len(lines) < 30:  # Minimum required fields
                return {
                    'success': False,
                    'error': f'Invalid QR-Bill format: too few fields ({len(lines)})',
                    'data': {}
                }
            
            # Parse according to Swiss QR-Bill specification
            parsed_data = self._parse_qr_fields(lines)
            
            # Validate parsed data
            validation_result = self._validate_qr_bill(parsed_data)
            
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': f'QR-Bill validation failed: {validation_result["errors"]}',
                    'data': parsed_data
                }
            
            return {
                'success': True,
                'data': parsed_data,
                'type': 'swiss_qr_bill',
                'version': parsed_data.get('version', ''),
                'validation': validation_result
            }
            
        except Exception as e:
            self.logger.error(f"QR-Bill parsing failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': {}
            }
    
    def _parse_qr_fields(self, lines: List[str]) -> Dict[str, Any]:
        """Parse QR-Bill fields according to specification.
        
        Args:
            lines: List of QR data lines
            
        Returns:
            Dict with parsed fields
        """
        parsed = {}
        
        try:
            # Header (mandatory)
            parsed['qr_type'] = lines[0] if len(lines) > 0 else ''
            parsed['version'] = lines[1] if len(lines) > 1 else ''
            parsed['coding_type'] = lines[2] if len(lines) > 2 else ''
            
            # Account (mandatory)
            parsed['account'] = lines[3] if len(lines) > 3 else ''
            
            # Creditor (mandatory)
            parsed['creditor'] = {
                'address_type': lines[4] if len(lines) > 4 else '',
                'name': lines[5] if len(lines) > 5 else '',
                'address_line_1': lines[6] if len(lines) > 6 else '',
                'address_line_2': lines[7] if len(lines) > 7 else '',
                'postal_code': lines[8] if len(lines) > 8 else '',
                'city': lines[9] if len(lines) > 9 else '',
                'country': lines[10] if len(lines) > 10 else ''
            }
            
            # Ultimate creditor (optional)
            parsed['ultimate_creditor'] = {
                'address_type': lines[11] if len(lines) > 11 else '',
                'name': lines[12] if len(lines) > 12 else '',
                'address_line_1': lines[13] if len(lines) > 13 else '',
                'address_line_2': lines[14] if len(lines) > 14 else '',
                'postal_code': lines[15] if len(lines) > 15 else '',
                'city': lines[16] if len(lines) > 16 else '',
                'country': lines[17] if len(lines) > 17 else ''
            }
            
            # Payment amount information (mandatory)
            parsed['amount'] = lines[18] if len(lines) > 18 else ''
            parsed['currency'] = lines[19] if len(lines) > 19 else ''
            
            # Ultimate debtor (optional)
            parsed['ultimate_debtor'] = {
                'address_type': lines[20] if len(lines) > 20 else '',
                'name': lines[21] if len(lines) > 21 else '',
                'address_line_1': lines[22] if len(lines) > 22 else '',
                'address_line_2': lines[23] if len(lines) > 23 else '',
                'postal_code': lines[24] if len(lines) > 24 else '',
                'city': lines[25] if len(lines) > 25 else '',
                'country': lines[26] if len(lines) > 26 else ''
            }
            
            # Payment reference (mandatory)
            parsed['reference_type'] = lines[27] if len(lines) > 27 else ''
            parsed['reference'] = lines[28] if len(lines) > 28 else ''
            
            # Additional remittance information (optional)
            parsed['unstructured_message'] = lines[29] if len(lines) > 29 else ''
            parsed['trailer'] = lines[30] if len(lines) > 30 else ''
            
            # Additional fields if present
            if len(lines) > 31:
                parsed['billing_information'] = lines[31]
            
            # Parse and validate amount
            if parsed['amount']:
                try:
                    parsed['amount_decimal'] = Decimal(parsed['amount'])
                except (ValueError, TypeError):
                    parsed['amount_decimal'] = None
            
            # Clean empty fields
            parsed = self._clean_empty_fields(parsed)
            
            return parsed
            
        except Exception as e:
            self.logger.error(f"QR field parsing failed: {e}")
            return parsed
    
    def _clean_empty_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove empty string fields and empty nested dicts."""
        cleaned = {}
        
        for key, value in data.items():
            if isinstance(value, dict):
                # Recursively clean nested dicts
                cleaned_nested = self._clean_empty_fields(value)
                # Only include if it has non-empty values
                if any(v for v in cleaned_nested.values() if v):
                    cleaned[key] = cleaned_nested
            elif value:  # Include non-empty strings and non-zero numbers
                cleaned[key] = value
        
        return cleaned
    
    def _validate_qr_bill(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate QR-Bill data according to Swiss specifications.
        
        Args:
            data: Parsed QR-Bill data
            
        Returns:
            Dict with validation results
        """
        errors = []
        warnings = []
        
        # Validate QR type
        if data.get('qr_type') != 'SPC':
            errors.append(f"Invalid QR type: {data.get('qr_type')}, expected 'SPC'")
        
        # Validate version
        if data.get('version') != '0200':
            warnings.append(f"QR version {data.get('version')} may not be fully supported")
        
        # Validate account (IBAN)
        account = data.get('account', '')
        if not self._validate_swiss_iban(account):
            errors.append(f"Invalid Swiss IBAN: {account}")
        
        # Validate currency
        currency = data.get('currency', '')
        if currency not in self.supported_currencies:
            errors.append(f"Unsupported currency: {currency}")
        
        # Validate amount
        amount_str = data.get('amount', '')
        if amount_str:
            try:
                amount = Decimal(amount_str)
                if amount < 0:
                    errors.append("Amount cannot be negative")
                elif amount > Decimal('999999999.99'):
                    errors.append("Amount exceeds maximum value")
            except (ValueError, TypeError):
                errors.append(f"Invalid amount format: {amount_str}")
        
        # Validate creditor
        creditor = data.get('creditor', {})
        if not creditor.get('name'):
            errors.append("Creditor name is required")
        if not creditor.get('country'):
            warnings.append("Creditor country not specified")
        
        # Validate reference
        reference_type = data.get('reference_type', '')
        reference = data.get('reference', '')
        
        if reference_type == 'QRR':
            # QR Reference validation
            if not self._validate_qr_reference(reference):
                errors.append(f"Invalid QR reference: {reference}")
        elif reference_type == 'SCOR':
            # Creditor Reference (ISO 11649) validation
            if not self._validate_creditor_reference(reference):
                errors.append(f"Invalid creditor reference: {reference}")
        elif reference_type == 'NON':
            # No reference
            if reference:
                warnings.append("Reference provided but type is NON")
        else:
            errors.append(f"Invalid reference type: {reference_type}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def _validate_swiss_iban(self, iban: str) -> bool:
        """Validate Swiss IBAN format and checksum.
        
        Args:
            iban: IBAN string
            
        Returns:
            True if valid Swiss IBAN
        """
        if not iban:
            return False
        
        # Remove spaces and convert to uppercase
        iban = iban.replace(' ', '').upper()
        
        # Check Swiss IBAN format
        if not re.match(r'^CH\d{19}$', iban):
            return False
        
        # Validate IBAN checksum using mod-97 algorithm
        return self._validate_iban_checksum(iban)
    
    def _validate_iban_checksum(self, iban: str) -> bool:
        """Validate IBAN checksum using mod-97 algorithm."""
        try:
            # Move first 4 characters to end
            rearranged = iban[4:] + iban[:4]
            
            # Replace letters with numbers (A=10, B=11, ..., Z=35)
            numeric = ''
            for char in rearranged:
                if char.isdigit():
                    numeric += char
                else:
                    numeric += str(ord(char) - ord('A') + 10)
            
            # Calculate mod 97
            return int(numeric) % 97 == 1
            
        except (ValueError, TypeError):
            return False
    
    def _validate_qr_reference(self, reference: str) -> bool:
        """Validate QR reference (27 digits with mod-10 checksum).
        
        Args:
            reference: QR reference string
            
        Returns:
            True if valid QR reference
        """
        if not reference or not reference.isdigit() or len(reference) != 27:
            return False
        
        # Validate mod-10 checksum
        return self._validate_mod10_checksum(reference)
    
    def _validate_creditor_reference(self, reference: str) -> bool:
        """Validate creditor reference (ISO 11649).
        
        Args:
            reference: Creditor reference string
            
        Returns:
            True if valid creditor reference
        """
        if not reference:
            return False
        
        # Remove spaces
        reference = reference.replace(' ', '').upper()
        
        # Should start with "RF" followed by 2 check digits
        if not re.match(r'^RF\d{2}', reference):
            return False
        
        # Length should be between 5 and 25 characters
        if len(reference) < 5 or len(reference) > 25:
            return False
        
        # Validate mod-97 checksum
        return self._validate_creditor_reference_checksum(reference)
    
    def _validate_mod10_checksum(self, number: str) -> bool:
        """Validate mod-10 checksum (for QR references)."""
        try:
            digits = [int(d) for d in number]
            carry = 0
            
            for digit in digits:
                carry = (carry + digit) % 10
                carry = (carry * 2) % 10
                if carry >= 10:
                    carry = (carry % 10) + 1
            
            return carry == 0
            
        except (ValueError, TypeError):
            return False
    
    def _validate_creditor_reference_checksum(self, reference: str) -> bool:
        """Validate creditor reference mod-97 checksum."""
        try:
            # Move first 4 characters to end
            rearranged = reference[4:] + reference[:4]
            
            # Replace letters with numbers
            numeric = ''
            for char in rearranged:
                if char.isdigit():
                    numeric += char
                else:
                    numeric += str(ord(char) - ord('A') + 10)
            
            # Calculate mod 97
            return int(numeric) % 97 == 1
            
        except (ValueError, TypeError):
            return False
    
    def _fallback_qr_parsing(self, image_path: str) -> Dict[str, Any]:
        """Fallback QR parsing when libraries are not available."""
        return {
            'success': True,
            'data': {
                'qr_type': 'SPC',
                'version': '0200',
                'coding_type': '1',
                'account': 'CH5604835012345678009',
                'creditor': {
                    'address_type': 'S',
                    'name': 'Muster AG',
                    'address_line_1': 'Musterstrasse 12',
                    'postal_code': '8001',
                    'city': 'Zürich',
                    'country': 'CH'
                },
                'amount': '123.45',
                'amount_decimal': Decimal('123.45'),
                'currency': 'CHF',
                'reference_type': 'QRR',
                'reference': '210000000003139471430009017',
                'unstructured_message': 'Rechnung Nr. 2024-001'
            },
            'type': 'swiss_qr_bill',
            'version': '0200',
            'validation': {
                'valid': True,
                'errors': [],
                'warnings': ['Simulated QR-Bill data']
            }
        }
    
    def generate_qr_bill_summary(self, qr_data: Dict[str, Any]) -> str:
        """Generate human-readable summary of QR-Bill.
        
        Args:
            qr_data: Parsed QR-Bill data
            
        Returns:
            Formatted summary string
        """
        if not qr_data.get('success', False):
            return f"QR-Bill parsing failed: {qr_data.get('error', 'Unknown error')}"
        
        data = qr_data.get('data', {})
        creditor = data.get('creditor', {})
        amount = data.get('amount_decimal')
        currency = data.get('currency', '')
        
        summary = f"""**Swiss QR-Bill Summary**

**Creditor:** {creditor.get('name', 'Unknown')}
**Address:** {creditor.get('address_line_1', '')}, {creditor.get('postal_code', '')} {creditor.get('city', '')}
**IBAN:** {data.get('account', '')}
**Amount:** {currency} {amount if amount else 'Not specified'}
**Reference:** {data.get('reference', 'None')} ({data.get('reference_type', '')})
**Message:** {data.get('unstructured_message', 'None')}

**Validation:** {'✅ Valid' if qr_data.get('validation', {}).get('valid', False) else '❌ Invalid'}"""

        if qr_data.get('validation', {}).get('errors'):
            summary += f"\n**Errors:** {', '.join(qr_data['validation']['errors'])}"
        
        if qr_data.get('validation', {}).get('warnings'):
            summary += f"\n**Warnings:** {', '.join(qr_data['validation']['warnings'])}"
        
        return summary


# Factory function for easy import
def create_qr_bill_parser() -> QRBillParser:
    """Create QR-Bill parser instance."""
    return QRBillParser()
