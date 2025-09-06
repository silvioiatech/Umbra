"""
Document Parsers for Swiss Accountant
Detectors and parsers for various document types (receipt, invoice, qr_bill, payslip, etc.)
"""
import re
import json
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime, date
from enum import Enum
from pathlib import Path
import logging


class DocumentType(Enum):
    """Supported document types."""
    RECEIPT = "receipt"
    INVOICE = "invoice"
    QR_BILL = "qr_bill"
    PAYSLIP = "payslip"
    BANK_STATEMENT = "bank_stmt"
    CARD_STATEMENT = "card_stmt"
    CREDIT_NOTE = "credit_note"
    REFUND = "refund"
    OTHER = "other"


class DocumentParser:
    """Main document parser with type detection and field extraction."""
    
    def __init__(self):
        """Initialize document parser."""
        self.logger = logging.getLogger(__name__)
        
        # Document type detection patterns
        self.type_patterns = {
            DocumentType.RECEIPT: [
                r'(?i)(quittung|reçu|ricevuta|receipt)',
                r'(?i)(kassenzettel|ticket de caisse)',
                r'(?i)(bon d\'achat|scontrino)',
                r'(?i)(merci|danke|grazie|thank you)',
                r'(?i)(kasse|caisse|cassa|cash register)'
            ],
            DocumentType.INVOICE: [
                r'(?i)(rechnung|facture|fattura|invoice)',
                r'(?i)(rechnungs[_-]?nr|facture[_-]?n[ro]|invoice[_-]?n[ro])',
                r'(?i)(zahlbar|payable|à payer|da pagare)',
                r'(?i)(zahlungsbedingungen|conditions de paiement)'
            ],
            DocumentType.QR_BILL: [
                r'(?i)(qr[_-]?rechnung|qr[_-]?facture)',
                r'(?i)(swiss qr)',
                r'(?i)(zahlteil|section paiement|sezione pagamento)',
                r'CH\d{19}',  # Swiss IBAN pattern
                r'(?i)(empfangsschein|récépissé|ricevuta)'
            ],
            DocumentType.PAYSLIP: [
                r'(?i)(lohnausweis|salaire|stipendio|payslip)',
                r'(?i)(gehaltsabrechnung|fiche de salaire)',
                r'(?i)(ahv|avs|ivs)',  # Swiss social insurance
                r'(?i)(bvg|lpp)',  # Swiss pension
                r'(?i)(alv|ac|ad)',  # Swiss unemployment insurance
                r'(?i)(bruttolohn|salaire brut|stipendio lordo)'
            ],
            DocumentType.BANK_STATEMENT: [
                r'(?i)(kontoauszug|relevé de compte|estratto conto)',
                r'(?i)(bank[_-]?auszug|bank statement)',
                r'(?i)(saldo|solde|balance)',
                r'(?i)(buchung|écriture|movimento)',
                r'camt\.05[23]'  # CAMT format
            ],
            DocumentType.CARD_STATEMENT: [
                r'(?i)(kreditkarten[_-]?abrechnung|décompte carte)',
                r'(?i)(visa|mastercard|american express)',
                r'(?i)(kartennummer|numéro de carte)',
                r'(?i)(card statement|credit card)'
            ]
        }
        
        # Common field extraction patterns
        self.field_patterns = {
            'amounts': [
                r'(?i)(?:chf|fr\.?|eur|€)\s*([0-9]{1,6}[.,]\d{2})',
                r'([0-9]{1,6}[.,]\d{2})\s*(?i)(?:chf|fr\.?|eur|€)',
                r'(?i)(?:total|gesamt|montant|importo|amount)\s*:?\s*(?:chf|fr\.?|eur|€)?\s*([0-9]{1,6}[.,]\d{2})',
                r'([0-9]{1,6}[.,]\d{2})'  # Fallback for any decimal amount
            ],
            'dates': [
                r'(\d{1,2})[./](\d{1,2})[./](\d{4})',
                r'(\d{1,2})[./](\d{1,2})[./](\d{2})',
                r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',
                r'(?i)(jan|feb|mär|apr|mai|jun|jul|aug|sep|okt|nov|dez)\w*\s+(\d{1,2}),?\s+(\d{4})',
                r'(\d{1,2})\.\s*(?i)(januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember)\s+(\d{4})'
            ],
            'merchants': [
                r'^([A-ZÄÖÜ][a-zäöüß\s&\-\.]{2,40})',  # First line often merchant
                r'(?i)(?:firma|company|société|ditta):\s*([A-Za-zäöüÄÖÜ\s&\-\.]{3,50})',
                r'^(.{3,50})$'  # Fallback for any reasonable first line
            ],
            'addresses': [
                r'([1-9]\d{3})\s+([A-ZÄÖÜ][a-zäöüß\s\-]{2,30})',  # Swiss postal code + city
                r'([A-ZÄÖÜ][a-zäöüß\s\-]{3,40})\s+([1-9]\d{3})',  # City + postal code
                r'([A-Za-zäöüÄÖÜ\s\-\.]{5,50})\s*,?\s*([1-9]\d{3})\s+([A-ZÄÖÜ][a-zäöüß\s\-]{2,30})'
            ],
            'payment_methods': [
                r'(?i)(bar|cash|espèces|contanti)',
                r'(?i)(karte|carte|carta|card)',
                r'(?i)(maestro|visa|mastercard|american express|amex)',
                r'(?i)(twint|apple pay|google pay|samsung pay)',
                r'(?i)(überweisung|virement|bonifico|transfer)',
                r'(?i)(lastschrift|prélèvement|addebito diretto)'
            ],
            'vat_info': [
                r'(?i)(?:mwst|tva|iva|vat)\s*([0-9.,]+)\s*%',
                r'([0-9.,]+)\s*%\s*(?i)(?:mwst|tva|iva|vat)',
                r'(?i)(?:mehrwertsteuer|taxe sur la valeur ajoutée)\s*([0-9.,]+)\s*%'
            ],
            'references': [
                r'(?i)(?:ref|référence|referenza|reference)[:\s]*([A-Z0-9\-]{5,30})',
                r'(?i)(?:nr|no|n°)[:\s]*([A-Z0-9\-]{3,20})',
                r'(?i)(?:beleg|ticket)[:\s]*([A-Z0-9\-]{3,20})'
            ]
        }
    
    def detect_document_type(self, ocr_text: str, filename: str = "") -> Dict[str, Any]:
        """Detect document type from OCR text and filename.
        
        Args:
            ocr_text: Extracted text from document
            filename: Optional filename for additional hints
            
        Returns:
            Dict with detected type and confidence
        """
        try:
            scores = {}
            text_lower = ocr_text.lower()
            filename_lower = filename.lower()
            
            # Score each document type based on pattern matches
            for doc_type, patterns in self.type_patterns.items():
                score = 0
                matches = []
                
                for pattern in patterns:
                    # Check OCR text
                    text_matches = re.findall(pattern, ocr_text, re.IGNORECASE | re.MULTILINE)
                    if text_matches:
                        score += len(text_matches) * 10
                        matches.extend(text_matches)
                    
                    # Check filename if provided
                    if filename and re.search(pattern, filename, re.IGNORECASE):
                        score += 5
                        matches.append(f"filename:{pattern}")
                
                scores[doc_type] = {
                    'score': score,
                    'matches': matches
                }
            
            # Find best match
            if not scores or all(s['score'] == 0 for s in scores.values()):
                return {
                    'document_type': DocumentType.OTHER,
                    'confidence': 0.1,
                    'scores': scores,
                    'reason': 'No clear pattern matches found'
                }
            
            best_type = max(scores.keys(), key=lambda k: scores[k]['score'])
            best_score = scores[best_type]['score']
            max_possible_score = len(self.type_patterns[best_type]) * 10
            confidence = min(best_score / max_possible_score, 1.0)
            
            return {
                'document_type': best_type,
                'confidence': confidence,
                'scores': scores,
                'matches': scores[best_type]['matches']
            }
            
        except Exception as e:
            self.logger.error(f"Document type detection failed: {e}")
            return {
                'document_type': DocumentType.OTHER,
                'confidence': 0.0,
                'error': str(e)
            }
    
    def extract_common_fields(self, ocr_text: str) -> Dict[str, Any]:
        """Extract common fields from OCR text.
        
        Args:
            ocr_text: Text extracted from document
            
        Returns:
            Dict with extracted fields
        """
        try:
            fields = {
                'amounts': [],
                'dates': [],
                'merchants': [],
                'addresses': [],
                'payment_methods': [],
                'vat_rates': [],
                'references': []
            }
            
            lines = ocr_text.split('\n')
            
            # Extract amounts
            for pattern in self.field_patterns['amounts']:
                matches = re.findall(pattern, ocr_text, re.IGNORECASE)
                for match in matches:
                    try:
                        if isinstance(match, tuple):
                            amount_str = match[0] if match[0] else match[1]
                        else:
                            amount_str = match
                        
                        # Clean and convert amount
                        amount_str = amount_str.replace(',', '.')
                        amount = float(amount_str)
                        
                        if 0.01 <= amount <= 999999:  # Reasonable range
                            fields['amounts'].append({
                                'value': amount,
                                'text': match,
                                'currency': 'CHF'  # Default assumption
                            })
                    except (ValueError, TypeError):
                        continue
            
            # Extract dates
            for pattern in self.field_patterns['dates']:
                matches = re.findall(pattern, ocr_text, re.IGNORECASE)
                for match in matches:
                    try:
                        if len(match) == 3:
                            if pattern.startswith(r'(\d{4})'):  # YYYY-MM-DD format
                                year, month, day = map(int, match)
                            else:  # DD/MM/YYYY or DD.MM.YYYY format
                                day, month, year = map(int, match)
                                if year < 100:  # 2-digit year
                                    year = 2000 + year if year < 50 else 1900 + year
                            
                            if 1 <= day <= 31 and 1 <= month <= 12 and 1990 <= year <= 2030:
                                date_obj = date(year, month, day)
                                fields['dates'].append({
                                    'date': date_obj.isoformat(),
                                    'text': '/'.join(match),
                                    'confidence': 0.8
                                })
                    except (ValueError, TypeError):
                        continue
            
            # Extract merchant names (first few meaningful lines)
            meaningful_lines = [line.strip() for line in lines[:5] if line.strip() and len(line.strip()) > 2]
            for i, line in enumerate(meaningful_lines):
                if not re.search(r'\d{4}|\d{1,2}[./]\d{1,2}', line):  # Skip lines with dates/years
                    confidence = 0.9 - (i * 0.2)  # Higher confidence for earlier lines
                    if confidence > 0:
                        fields['merchants'].append({
                            'name': line,
                            'confidence': confidence,
                            'line_number': i
                        })
            
            # Extract payment methods
            for pattern in self.field_patterns['payment_methods']:
                matches = re.findall(pattern, ocr_text, re.IGNORECASE)
                for match in matches:
                    fields['payment_methods'].append({
                        'method': match.lower(),
                        'text': match,
                        'confidence': 0.8
                    })
            
            # Extract VAT rates
            for pattern in self.field_patterns['vat_info']:
                matches = re.findall(pattern, ocr_text, re.IGNORECASE)
                for match in matches:
                    try:
                        rate_str = match.replace(',', '.')
                        rate = float(rate_str)
                        
                        # Check if it's a valid Swiss VAT rate
                        if rate in [8.1, 2.6, 3.8, 0.0, 7.7]:  # Including old rate
                            fields['vat_rates'].append({
                                'rate': rate,
                                'text': match,
                                'confidence': 0.9 if rate in [8.1, 2.6, 3.8, 0.0] else 0.7
                            })
                    except (ValueError, TypeError):
                        continue
            
            # Extract references
            for pattern in self.field_patterns['references']:
                matches = re.findall(pattern, ocr_text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        ref = match[1] if len(match) > 1 else match[0]
                    else:
                        ref = match
                    
                    fields['references'].append({
                        'reference': ref,
                        'text': match,
                        'confidence': 0.7
                    })
            
            # Remove duplicates and sort by confidence
            for field_type in fields:
                if field_type in ['amounts', 'dates', 'merchants', 'payment_methods', 'vat_rates', 'references']:
                    # Remove duplicates while preserving order
                    seen = set()
                    unique_items = []
                    for item in fields[field_type]:
                        key = str(item.get('value', item.get('name', item.get('method', item.get('rate', item.get('reference'))))))
                        if key not in seen:
                            seen.add(key)
                            unique_items.append(item)
                    
                    # Sort by confidence (descending)
                    fields[field_type] = sorted(unique_items, 
                                              key=lambda x: x.get('confidence', 0), 
                                              reverse=True)
            
            return fields
            
        except Exception as e:
            self.logger.error(f"Field extraction failed: {e}")
            return {
                'amounts': [],
                'dates': [],
                'merchants': [],
                'addresses': [],
                'payment_methods': [],
                'vat_rates': [],
                'references': [],
                'error': str(e)
            }
    
    def parse_receipt(self, ocr_text: str) -> Dict[str, Any]:
        """Parse receipt-specific fields.
        
        Args:
            ocr_text: OCR text from receipt
            
        Returns:
            Dict with receipt-specific data
        """
        try:
            common_fields = self.extract_common_fields(ocr_text)
            
            # Receipt-specific parsing
            receipt_data = {
                'document_type': 'receipt',
                'merchant': common_fields['merchants'][0]['name'] if common_fields['merchants'] else None,
                'date': common_fields['dates'][0]['date'] if common_fields['dates'] else None,
                'total_amount': common_fields['amounts'][-1]['value'] if common_fields['amounts'] else None,
                'payment_method': common_fields['payment_methods'][0]['method'] if common_fields['payment_methods'] else None,
                'vat_rate': common_fields['vat_rates'][0]['rate'] if common_fields['vat_rates'] else None,
                'reference': common_fields['references'][0]['reference'] if common_fields['references'] else None,
                'line_items': self._extract_line_items(ocr_text),
                'confidence': self._calculate_confidence(common_fields)
            }
            
            return receipt_data
            
        except Exception as e:
            self.logger.error(f"Receipt parsing failed: {e}")
            return {'error': str(e), 'document_type': 'receipt'}
    
    def parse_invoice(self, ocr_text: str) -> Dict[str, Any]:
        """Parse invoice-specific fields.
        
        Args:
            ocr_text: OCR text from invoice
            
        Returns:
            Dict with invoice-specific data
        """
        try:
            common_fields = self.extract_common_fields(ocr_text)
            
            # Invoice-specific patterns
            invoice_patterns = {
                'invoice_number': [
                    r'(?i)(?:rechnung|facture|invoice)[s]?[_\-\s]*(?:nr|no|n°|number)[:\s]*([A-Z0-9\-]{3,20})',
                    r'(?i)(?:rg|rn|fn|in)[:\-\s]*([A-Z0-9\-]{3,20})'
                ],
                'due_date': [
                    r'(?i)(?:fällig|due|échéance|scadenza)[:\s]*(\d{1,2}[./]\d{1,2}[./]\d{2,4})',
                    r'(?i)(?:zahlbar bis|payable until|à payer avant)[:\s]*(\d{1,2}[./]\d{1,2}[./]\d{2,4})'
                ],
                'customer_number': [
                    r'(?i)(?:kunden|customer|client)[_\-\s]*(?:nr|no|n°|number)[:\s]*([A-Z0-9\-]{3,20})'
                ]
            }
            
            # Extract invoice-specific fields
            invoice_number = None
            due_date = None
            customer_number = None
            
            for pattern in invoice_patterns['invoice_number']:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    invoice_number = match.group(1)
                    break
            
            for pattern in invoice_patterns['due_date']:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    due_date = match.group(1)
                    break
            
            for pattern in invoice_patterns['customer_number']:
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    customer_number = match.group(1)
                    break
            
            invoice_data = {
                'document_type': 'invoice',
                'invoice_number': invoice_number,
                'merchant': common_fields['merchants'][0]['name'] if common_fields['merchants'] else None,
                'date': common_fields['dates'][0]['date'] if common_fields['dates'] else None,
                'due_date': due_date,
                'total_amount': common_fields['amounts'][-1]['value'] if common_fields['amounts'] else None,
                'customer_number': customer_number,
                'vat_breakdown': self._extract_vat_breakdown(ocr_text),
                'line_items': self._extract_line_items(ocr_text),
                'confidence': self._calculate_confidence(common_fields)
            }
            
            return invoice_data
            
        except Exception as e:
            self.logger.error(f"Invoice parsing failed: {e}")
            return {'error': str(e), 'document_type': 'invoice'}
    
    def parse_payslip(self, ocr_text: str) -> Dict[str, Any]:
        """Parse payslip-specific fields.
        
        Args:
            ocr_text: OCR text from payslip
            
        Returns:
            Dict with payslip-specific data
        """
        try:
            common_fields = self.extract_common_fields(ocr_text)
            
            # Payslip-specific patterns
            payslip_patterns = {
                'gross_salary': [
                    r'(?i)(?:brutto|brut|gross|lordo)[:\s]*(?:chf|fr\.?)?\s*([0-9]{1,6}[.,]\d{2})',
                    r'(?i)(?:grundlohn|salaire de base)[:\s]*(?:chf|fr\.?)?\s*([0-9]{1,6}[.,]\d{2})'
                ],
                'net_salary': [
                    r'(?i)(?:netto|net|netto lohn)[:\s]*(?:chf|fr\.?)?\s*([0-9]{1,6}[.,]\d{2})',
                    r'(?i)(?:auszahlung|versement|payout)[:\s]*(?:chf|fr\.?)?\s*([0-9]{1,6}[.,]\d{2})'
                ],
                'ahv_contribution': [
                    r'(?i)(?:ahv|avs)[:\s]*(?:chf|fr\.?)?\s*([0-9]{1,6}[.,]\d{2})',
                ],
                'bvg_contribution': [
                    r'(?i)(?:bvg|lpp)[:\s]*(?:chf|fr\.?)?\s*([0-9]{1,6}[.,]\d{2})',
                ],
                'period': [
                    r'(?i)(?:periode|period|période)[:\s]*(\d{1,2}[./]\d{4})',
                    r'(?i)(?:monat|mois|month)[:\s]*(\d{1,2}[./]\d{4})'
                ]
            }
            
            # Extract payslip fields
            extracted = {}
            for field, patterns in payslip_patterns.items():
                for pattern in patterns:
                    match = re.search(pattern, ocr_text, re.IGNORECASE)
                    if match:
                        if field in ['gross_salary', 'net_salary', 'ahv_contribution', 'bvg_contribution']:
                            try:
                                amount_str = match.group(1).replace(',', '.')
                                extracted[field] = float(amount_str)
                            except (ValueError, TypeError):
                                continue
                        else:
                            extracted[field] = match.group(1)
                        break
            
            payslip_data = {
                'document_type': 'payslip',
                'employer': common_fields['merchants'][0]['name'] if common_fields['merchants'] else None,
                'period': extracted.get('period'),
                'gross_salary': extracted.get('gross_salary'),
                'net_salary': extracted.get('net_salary'),
                'ahv_contribution': extracted.get('ahv_contribution'),
                'bvg_contribution': extracted.get('bvg_contribution'),
                'social_contributions': self._extract_social_contributions(ocr_text),
                'confidence': self._calculate_confidence(common_fields)
            }
            
            return payslip_data
            
        except Exception as e:
            self.logger.error(f"Payslip parsing failed: {e}")
            return {'error': str(e), 'document_type': 'payslip'}
    
    def _extract_line_items(self, ocr_text: str) -> List[Dict[str, Any]]:
        """Extract line items from receipt/invoice."""
        try:
            lines = ocr_text.split('\n')
            line_items = []
            
            # Look for lines with amount patterns
            for line in lines:
                line = line.strip()
                if len(line) < 3:
                    continue
                
                # Try to find amount at end of line
                amount_match = re.search(r'([0-9]{1,6}[.,]\d{2})\s*(?:chf|fr\.?|eur|€)?\s*$', line, re.IGNORECASE)
                if amount_match:
                    try:
                        amount_str = amount_match.group(1).replace(',', '.')
                        amount = float(amount_str)
                        
                        # Extract description (everything before the amount)
                        description = line[:amount_match.start()].strip()
                        
                        if description and 0.01 <= amount <= 9999:
                            line_items.append({
                                'description': description,
                                'amount': amount,
                                'line_text': line
                            })
                    except (ValueError, TypeError):
                        continue
            
            return line_items[:20]  # Limit to reasonable number
            
        except Exception as e:
            self.logger.error(f"Line item extraction failed: {e}")
            return []
    
    def _extract_vat_breakdown(self, ocr_text: str) -> Dict[str, Any]:
        """Extract VAT breakdown from text."""
        try:
            vat_breakdown = {
                'rates': [],
                'total_vat': None,
                'net_amount': None
            }
            
            # Look for VAT breakdown patterns
            vat_patterns = [
                r'(?i)(?:mwst|tva|iva)\s*([0-9.,]+)\s*%[:\s]*(?:chf|fr\.?)?\s*([0-9]{1,6}[.,]\d{2})',
                r'([0-9.,]+)\s*%\s*(?:mwst|tva|iva)[:\s]*(?:chf|fr\.?)?\s*([0-9]{1,6}[.,]\d{2})'
            ]
            
            for pattern in vat_patterns:
                matches = re.findall(pattern, ocr_text, re.IGNORECASE)
                for match in matches:
                    try:
                        rate_str = match[0].replace(',', '.')
                        amount_str = match[1].replace(',', '.')
                        
                        rate = float(rate_str)
                        amount = float(amount_str)
                        
                        vat_breakdown['rates'].append({
                            'rate': rate,
                            'amount': amount
                        })
                    except (ValueError, TypeError):
                        continue
            
            # Look for total VAT
            total_vat_pattern = r'(?i)(?:total.*mwst|mwst.*total|total.*tva)[:\s]*(?:chf|fr\.?)?\s*([0-9]{1,6}[.,]\d{2})'
            total_match = re.search(total_vat_pattern, ocr_text, re.IGNORECASE)
            if total_match:
                try:
                    vat_breakdown['total_vat'] = float(total_match.group(1).replace(',', '.'))
                except (ValueError, TypeError):
                    pass
            
            return vat_breakdown
            
        except Exception as e:
            self.logger.error(f"VAT breakdown extraction failed: {e}")
            return {'rates': [], 'total_vat': None, 'net_amount': None}
    
    def _extract_social_contributions(self, ocr_text: str) -> Dict[str, Any]:
        """Extract social insurance contributions from payslip."""
        try:
            contributions = {}
            
            # Swiss social insurance patterns
            patterns = {
                'ahv_iv_eo': r'(?i)(?:ahv|avs)[:\s]*(?:chf|fr\.?)?\s*([0-9]{1,6}[.,]\d{2})',
                'alv': r'(?i)(?:alv|ac)[:\s]*(?:chf|fr\.?)?\s*([0-9]{1,6}[.,]\d{2})',
                'bvg': r'(?i)(?:bvg|lpp)[:\s]*(?:chf|fr\.?)?\s*([0-9]{1,6}[.,]\d{2})',
                'uvg': r'(?i)(?:uvg|nbu)[:\s]*(?:chf|fr\.?)?\s*([0-9]{1,6}[.,]\d{2})',
                'ktg': r'(?i)(?:ktg|ijm)[:\s]*(?:chf|fr\.?)?\s*([0-9]{1,6}[.,]\d{2})'
            }
            
            for contrib_type, pattern in patterns.items():
                match = re.search(pattern, ocr_text, re.IGNORECASE)
                if match:
                    try:
                        amount_str = match.group(1).replace(',', '.')
                        contributions[contrib_type] = float(amount_str)
                    except (ValueError, TypeError):
                        continue
            
            return contributions
            
        except Exception as e:
            self.logger.error(f"Social contributions extraction failed: {e}")
            return {}
    
    def _calculate_confidence(self, common_fields: Dict[str, Any]) -> float:
        """Calculate overall confidence score for parsed document."""
        try:
            score = 0.0
            max_score = 0.0
            
            # Weight different fields
            field_weights = {
                'amounts': 0.3,
                'dates': 0.2,
                'merchants': 0.2,
                'payment_methods': 0.1,
                'vat_rates': 0.1,
                'references': 0.1
            }
            
            for field, weight in field_weights.items():
                max_score += weight
                if common_fields.get(field):
                    field_confidence = sum(item.get('confidence', 0) for item in common_fields[field]) / len(common_fields[field])
                    score += field_confidence * weight
            
            return min(score / max_score if max_score > 0 else 0, 1.0)
            
        except Exception as e:
            self.logger.error(f"Confidence calculation failed: {e}")
            return 0.0


# Factory function for easy import
def create_document_parser() -> DocumentParser:
    """Create document parser instance."""
    return DocumentParser()
