"""
Statement Parser for Swiss Accountant
Normalizes bank/card statements from camt.053/052 XML, CSV, and PDF formats to standard transaction format.
"""
import re
import csv
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime, date
from enum import Enum
from io import StringIO
import logging


class StatementFormat(Enum):
    """Supported statement formats."""
    CAMT_052 = "camt.052"  # Account Report
    CAMT_053 = "camt.053"  # Bank-to-Customer Statement
    CSV_GENERIC = "csv_generic"
    CSV_UBS = "csv_ubs"
    CSV_CREDIT_SUISSE = "csv_credit_suisse"
    CSV_POSTFINANCE = "csv_postfinance"
    CSV_REVOLUT = "csv_revolut"
    CSV_SWISSCARD = "csv_swisscard"
    PDF_STATEMENT = "pdf_statement"


class StatementParser:
    """Parser for various bank and card statement formats."""
    
    def __init__(self):
        """Initialize statement parser."""
        self.logger = logging.getLogger(__name__)
        
        # CAMT namespace mappings
        self.camt_namespaces = {
            'camt052': 'urn:iso:std:iso:20022:tech:xsd:camt.052.001.02',
            'camt053': 'urn:iso:std:iso:20022:tech:xsd:camt.053.001.02',
            'pain': 'urn:iso:std:iso:20022:tech:xsd:pain.001.001.03'
        }
        
        # CSV format detection patterns
        self.csv_patterns = {
            StatementFormat.CSV_UBS: [
                r'Trade Date.*Valuta Date.*Description.*Debit.*Credit',
                r'Buchungsdatum.*Valuta.*Beschreibung.*Belastung.*Gutschrift'
            ],
            StatementFormat.CSV_CREDIT_SUISSE: [
                r'Date.*Description.*Amount.*Currency.*Balance',
                r'Datum.*Beschreibung.*Betrag.*Währung.*Saldo'
            ],
            StatementFormat.CSV_POSTFINANCE: [
                r'Datum.*Beschreibung.*Gutschrift.*Belastung.*Saldo',
                r'Date.*Description.*Credit.*Debit.*Balance'
            ],
            StatementFormat.CSV_REVOLUT: [
                r'Type.*Product.*Started Date.*Completed Date.*Description.*Amount.*Fee.*Currency.*State.*Balance'
            ],
            StatementFormat.CSV_SWISSCARD: [
                r'Card.*Transaction Date.*Posting Date.*Description.*Amount.*Currency'
            ]
        }
    
    def detect_statement_format(self, content: str, filename: str = "") -> Dict[str, Any]:
        """Detect statement format from content and filename.
        
        Args:
            content: File content as string
            filename: Optional filename for format hints
            
        Returns:
            Dict with detected format and confidence
        """
        try:
            content_sample = content[:2000]  # First 2KB for detection
            filename_lower = filename.lower()
            
            # Check for CAMT XML formats
            if content.strip().startswith('<?xml') or '<Document' in content_sample:
                if 'camt.052' in content_sample:
                    return {
                        'format': StatementFormat.CAMT_052,
                        'confidence': 0.95,
                        'detected_from': 'xml_content'
                    }
                elif 'camt.053' in content_sample:
                    return {
                        'format': StatementFormat.CAMT_053,
                        'confidence': 0.95,
                        'detected_from': 'xml_content'
                    }
                else:
                    return {
                        'format': StatementFormat.CAMT_053,  # Default CAMT
                        'confidence': 0.7,
                        'detected_from': 'xml_content_generic'
                    }
            
            # Check for CSV formats
            if ',' in content_sample or ';' in content_sample:
                # Try to detect specific bank CSV formats
                for format_type, patterns in self.csv_patterns.items():
                    for pattern in patterns:
                        if re.search(pattern, content_sample, re.IGNORECASE):
                            return {
                                'format': format_type,
                                'confidence': 0.9,
                                'detected_from': 'csv_pattern'
                            }
                
                # Generic CSV fallback
                return {
                    'format': StatementFormat.CSV_GENERIC,
                    'confidence': 0.6,
                    'detected_from': 'csv_generic'
                }
            
            # Filename-based detection
            if 'camt' in filename_lower:
                if '052' in filename_lower:
                    return {'format': StatementFormat.CAMT_052, 'confidence': 0.8, 'detected_from': 'filename'}
                elif '053' in filename_lower:
                    return {'format': StatementFormat.CAMT_053, 'confidence': 0.8, 'detected_from': 'filename'}
            
            if filename_lower.endswith('.csv'):
                if 'ubs' in filename_lower:
                    return {'format': StatementFormat.CSV_UBS, 'confidence': 0.8, 'detected_from': 'filename'}
                elif 'credit' in filename_lower or 'cs' in filename_lower:
                    return {'format': StatementFormat.CSV_CREDIT_SUISSE, 'confidence': 0.8, 'detected_from': 'filename'}
                elif 'postfinance' in filename_lower or 'pf' in filename_lower:
                    return {'format': StatementFormat.CSV_POSTFINANCE, 'confidence': 0.8, 'detected_from': 'filename'}
                elif 'revolut' in filename_lower:
                    return {'format': StatementFormat.CSV_REVOLUT, 'confidence': 0.8, 'detected_from': 'filename'}
                elif 'swisscard' in filename_lower:
                    return {'format': StatementFormat.CSV_SWISSCARD, 'confidence': 0.8, 'detected_from': 'filename'}
            
            return {
                'format': StatementFormat.CSV_GENERIC,
                'confidence': 0.3,
                'detected_from': 'unknown'
            }
            
        except Exception as e:
            self.logger.error(f"Statement format detection failed: {e}")
            return {
                'format': StatementFormat.CSV_GENERIC,
                'confidence': 0.1,
                'error': str(e)
            }
    
    def parse_statement(self, content: str, format_hint: StatementFormat = None) -> Dict[str, Any]:
        """Parse statement content to normalized transaction format.
        
        Args:
            content: Statement file content
            format_hint: Optional format hint
            
        Returns:
            Dict with parsed statement data
        """
        try:
            # Detect format if not provided
            if not format_hint:
                detection = self.detect_statement_format(content)
                format_hint = detection['format']
            
            # Route to appropriate parser
            if format_hint in [StatementFormat.CAMT_052, StatementFormat.CAMT_053]:
                return self._parse_camt_xml(content, format_hint)
            elif format_hint.name.startswith('CSV_'):
                return self._parse_csv_statement(content, format_hint)
            else:
                return self._parse_generic_statement(content)
                
        except Exception as e:
            self.logger.error(f"Statement parsing failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'transactions': [],
                'account_info': {},
                'statement_info': {}
            }
    
    def _parse_camt_xml(self, xml_content: str, format_type: StatementFormat) -> Dict[str, Any]:
        """Parse CAMT.052/053 XML statement.
        
        Args:
            xml_content: XML content string
            format_type: CAMT format type
            
        Returns:
            Dict with parsed statement data
        """
        try:
            # Parse XML
            root = ET.fromstring(xml_content)
            
            # Determine namespace
            ns_key = 'camt052' if format_type == StatementFormat.CAMT_052 else 'camt053'
            namespace = {'ns': self.camt_namespaces.get(ns_key, '')}
            
            # If no namespace in our map, try to detect from XML
            if not namespace['ns']:
                # Extract namespace from root element
                if root.tag.startswith('{'):
                    namespace['ns'] = root.tag.split('}')[0][1:]
            
            # Parse statement header
            stmt_element = root.find('.//ns:Stmt', namespace) or root.find('.//ns:Rpt', namespace)
            if stmt_element is None:
                # Try without namespace
                stmt_element = root.find('.//Stmt') or root.find('.//Rpt')
                namespace = {'ns': ''}
            
            if stmt_element is None:
                raise ValueError("No statement/report element found in XML")
            
            # Extract account information
            account_info = self._extract_camt_account_info(stmt_element, namespace)
            
            # Extract statement info
            statement_info = self._extract_camt_statement_info(stmt_element, namespace)
            
            # Extract transactions
            transactions = self._extract_camt_transactions(stmt_element, namespace)
            
            return {
                'success': True,
                'format': format_type.value,
                'account_info': account_info,
                'statement_info': statement_info,
                'transactions': transactions,
                'transaction_count': len(transactions)
            }
            
        except ET.ParseError as e:
            return {
                'success': False,
                'error': f'XML parsing error: {e}',
                'transactions': [],
                'account_info': {},
                'statement_info': {}
            }
        except Exception as e:
            self.logger.error(f"CAMT parsing failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'transactions': [],
                'account_info': {},
                'statement_info': {}
            }
    
    def _extract_camt_account_info(self, stmt_element, namespace: Dict[str, str]) -> Dict[str, Any]:
        """Extract account information from CAMT statement."""
        try:
            account_info = {}
            
            # Account identification
            acct_elem = stmt_element.find('.//ns:Acct', namespace)
            if acct_elem is not None:
                # IBAN
                iban_elem = acct_elem.find('.//ns:IBAN', namespace)
                if iban_elem is not None:
                    account_info['iban'] = iban_elem.text
                
                # Account owner
                owner_elem = acct_elem.find('.//ns:Ownr//ns:Nm', namespace)
                if owner_elem is not None:
                    account_info['owner_name'] = owner_elem.text
                
                # Currency
                ccy_elem = acct_elem.find('.//ns:Ccy', namespace)
                if ccy_elem is not None:
                    account_info['currency'] = ccy_elem.text
            
            # Account servicer (bank)
            svcr_elem = stmt_element.find('.//ns:AcctSvcr//ns:FinInstnId//ns:Nm', namespace)
            if svcr_elem is not None:
                account_info['bank_name'] = svcr_elem.text
            
            return account_info
            
        except Exception as e:
            self.logger.error(f"CAMT account info extraction failed: {e}")
            return {}
    
    def _extract_camt_statement_info(self, stmt_element, namespace: Dict[str, str]) -> Dict[str, Any]:
        """Extract statement information from CAMT statement."""
        try:
            statement_info = {}
            
            # Statement ID
            id_elem = stmt_element.find('.//ns:Id', namespace)
            if id_elem is not None:
                statement_info['statement_id'] = id_elem.text
            
            # Creation date/time
            cre_dt_elem = stmt_element.find('.//ns:CreDtTm', namespace)
            if cre_dt_elem is not None:
                statement_info['creation_datetime'] = cre_dt_elem.text
            
            # From/To dates
            fr_dt_elem = stmt_element.find('.//ns:FrDt', namespace)
            if fr_dt_elem is not None:
                statement_info['from_date'] = fr_dt_elem.text
            
            to_dt_elem = stmt_element.find('.//ns:ToDt', namespace)
            if to_dt_elem is not None:
                statement_info['to_date'] = to_dt_elem.text
            
            # Opening balance
            opening_bal_elem = stmt_element.find('.//ns:Bal[ns:Tp/ns:CdOrPrtry/ns:Cd="OPBD"]//ns:Amt', namespace)
            if opening_bal_elem is not None:
                statement_info['opening_balance'] = {
                    'amount': float(opening_bal_elem.text),
                    'currency': opening_bal_elem.get('Ccy', 'CHF')
                }
            
            # Closing balance
            closing_bal_elem = stmt_element.find('.//ns:Bal[ns:Tp/ns:CdOrPrtry/ns:Cd="CLBD"]//ns:Amt', namespace)
            if closing_bal_elem is not None:
                statement_info['closing_balance'] = {
                    'amount': float(closing_bal_elem.text),
                    'currency': closing_bal_elem.get('Ccy', 'CHF')
                }
            
            return statement_info
            
        except Exception as e:
            self.logger.error(f"CAMT statement info extraction failed: {e}")
            return {}
    
    def _extract_camt_transactions(self, stmt_element, namespace: Dict[str, str]) -> List[Dict[str, Any]]:
        """Extract transactions from CAMT statement."""
        try:
            transactions = []
            
            # Find all entry elements (transactions)
            entries = stmt_element.findall('.//ns:Ntry', namespace)
            
            for entry in entries:
                try:
                    transaction = {}
                    
                    # Amount
                    amt_elem = entry.find('.//ns:Amt', namespace)
                    if amt_elem is not None:
                        transaction['amount'] = float(amt_elem.text)
                        transaction['currency'] = amt_elem.get('Ccy', 'CHF')
                    
                    # Credit/Debit indicator
                    cdt_dbt_elem = entry.find('.//ns:CdtDbtInd', namespace)
                    if cdt_dbt_elem is not None:
                        transaction['credit_debit'] = cdt_dbt_elem.text
                        # Make debit amounts negative
                        if cdt_dbt_elem.text == 'DBIT' and 'amount' in transaction:
                            transaction['amount'] = -abs(transaction['amount'])
                    
                    # Booking date
                    book_dt_elem = entry.find('.//ns:BookgDt//ns:Dt', namespace)
                    if book_dt_elem is not None:
                        transaction['booking_date'] = book_dt_elem.text
                    
                    # Value date
                    val_dt_elem = entry.find('.//ns:ValDt//ns:Dt', namespace)
                    if val_dt_elem is not None:
                        transaction['value_date'] = val_dt_elem.text
                    
                    # Reference
                    ref_elem = entry.find('.//ns:AcctSvcrRef', namespace)
                    if ref_elem is not None:
                        transaction['reference'] = ref_elem.text
                    
                    # Transaction details
                    tx_dtl_elem = entry.find('.//ns:NtryDtls//ns:TxDtls', namespace)
                    if tx_dtl_elem is not None:
                        # Counterparty
                        rltd_pties_elem = tx_dtl_elem.find('.//ns:RltdPties', namespace)
                        if rltd_pties_elem is not None:
                            # Debtor
                            dbtr_elem = rltd_pties_elem.find('.//ns:Dbtr//ns:Nm', namespace)
                            if dbtr_elem is not None:
                                transaction['counterparty'] = dbtr_elem.text
                            
                            # Creditor (if no debtor)
                            if 'counterparty' not in transaction:
                                cdtr_elem = rltd_pties_elem.find('.//ns:Cdtr//ns:Nm', namespace)
                                if cdtr_elem is not None:
                                    transaction['counterparty'] = cdtr_elem.text
                        
                        # Remittance information (description)
                        rmtinf_elem = tx_dtl_elem.find('.//ns:RmtInf//ns:Ustrd', namespace)
                        if rmtinf_elem is not None:
                            transaction['description'] = rmtinf_elem.text
                        
                        # Bank transaction code
                        btc_elem = tx_dtl_elem.find('.//ns:BkTxCd//ns:Prtry//ns:Cd', namespace)
                        if btc_elem is not None:
                            transaction['bank_transaction_code'] = btc_elem.text
                    
                    # Add transaction if it has minimum required fields
                    if 'amount' in transaction and ('booking_date' in transaction or 'value_date' in transaction):
                        transactions.append(transaction)
                        
                except Exception as e:
                    self.logger.warning(f"Failed to parse individual transaction: {e}")
                    continue
            
            return transactions
            
        except Exception as e:
            self.logger.error(f"CAMT transactions extraction failed: {e}")
            return []
    
    def _parse_csv_statement(self, csv_content: str, format_type: StatementFormat) -> Dict[str, Any]:
        """Parse CSV statement based on format type.
        
        Args:
            csv_content: CSV content string
            format_type: Specific CSV format
            
        Returns:
            Dict with parsed statement data
        """
        try:
            # Route to specific CSV parser
            if format_type == StatementFormat.CSV_UBS:
                return self._parse_ubs_csv(csv_content)
            elif format_type == StatementFormat.CSV_CREDIT_SUISSE:
                return self._parse_credit_suisse_csv(csv_content)
            elif format_type == StatementFormat.CSV_POSTFINANCE:
                return self._parse_postfinance_csv(csv_content)
            elif format_type == StatementFormat.CSV_REVOLUT:
                return self._parse_revolut_csv(csv_content)
            elif format_type == StatementFormat.CSV_SWISSCARD:
                return self._parse_swisscard_csv(csv_content)
            else:
                return self._parse_generic_csv(csv_content)
                
        except Exception as e:
            self.logger.error(f"CSV parsing failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'transactions': [],
                'account_info': {},
                'statement_info': {}
            }
    
    def _parse_ubs_csv(self, csv_content: str) -> Dict[str, Any]:
        """Parse UBS-specific CSV format."""
        try:
            transactions = []
            
            # Detect delimiter and encoding
            delimiter = ';' if ';' in csv_content[:1000] else ','
            
            reader = csv.DictReader(StringIO(csv_content), delimiter=delimiter)
            
            for row in reader:
                try:
                    # UBS CSV columns (may vary)
                    transaction = {
                        'booking_date': row.get('Trade Date', row.get('Buchungsdatum', '')),
                        'value_date': row.get('Valuta Date', row.get('Valuta', '')),
                        'description': row.get('Description', row.get('Beschreibung', '')),
                        'counterparty': row.get('Counterparty', ''),
                        'reference': row.get('Reference', row.get('Referenz', '')),
                        'currency': row.get('Currency', row.get('Währung', 'CHF'))
                    }
                    
                    # Handle amount (could be in separate debit/credit columns)
                    debit = row.get('Debit', row.get('Belastung', ''))
                    credit = row.get('Credit', row.get('Gutschrift', ''))
                    
                    if credit and credit.strip():
                        amount_str = credit.replace("'", "").replace(",", ".")
                        transaction['amount'] = float(amount_str) if amount_str else 0
                    elif debit and debit.strip():
                        amount_str = debit.replace("'", "").replace(",", ".")
                        transaction['amount'] = -abs(float(amount_str)) if amount_str else 0
                    else:
                        # Single amount column
                        amount_str = row.get('Amount', row.get('Betrag', '0'))
                        amount_str = amount_str.replace("'", "").replace(",", ".")
                        transaction['amount'] = float(amount_str) if amount_str else 0
                    
                    if transaction['amount'] != 0:
                        transactions.append(transaction)
                        
                except Exception as e:
                    self.logger.warning(f"Failed to parse UBS CSV row: {e}")
                    continue
            
            return {
                'success': True,
                'format': 'csv_ubs',
                'transactions': transactions,
                'transaction_count': len(transactions),
                'account_info': {'bank': 'UBS'},
                'statement_info': {}
            }
            
        except Exception as e:
            self.logger.error(f"UBS CSV parsing failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'transactions': [],
                'account_info': {},
                'statement_info': {}
            }
    
    def _parse_postfinance_csv(self, csv_content: str) -> Dict[str, Any]:
        """Parse PostFinance-specific CSV format."""
        try:
            transactions = []
            
            # PostFinance typically uses semicolon separator
            delimiter = ';'
            
            reader = csv.DictReader(StringIO(csv_content), delimiter=delimiter)
            
            for row in reader:
                try:
                    transaction = {
                        'booking_date': row.get('Datum', row.get('Date', '')),
                        'value_date': row.get('Valuta', row.get('Value Date', '')),
                        'description': row.get('Beschreibung', row.get('Description', '')),
                        'counterparty': row.get('Auftraggeber/Zahlungsempfänger', ''),
                        'reference': row.get('Referenz', row.get('Reference', '')),
                        'currency': 'CHF'  # PostFinance is primarily CHF
                    }
                    
                    # Handle PostFinance amount columns
                    credit = row.get('Gutschrift', row.get('Credit', ''))
                    debit = row.get('Belastung', row.get('Debit', ''))
                    
                    if credit and credit.strip():
                        amount_str = credit.replace("'", "").replace(",", ".")
                        transaction['amount'] = float(amount_str) if amount_str else 0
                    elif debit and debit.strip():
                        amount_str = debit.replace("'", "").replace(",", ".")
                        transaction['amount'] = -abs(float(amount_str)) if amount_str else 0
                    
                    if transaction.get('amount', 0) != 0:
                        transactions.append(transaction)
                        
                except Exception as e:
                    self.logger.warning(f"Failed to parse PostFinance CSV row: {e}")
                    continue
            
            return {
                'success': True,
                'format': 'csv_postfinance',
                'transactions': transactions,
                'transaction_count': len(transactions),
                'account_info': {'bank': 'PostFinance'},
                'statement_info': {}
            }
            
        except Exception as e:
            self.logger.error(f"PostFinance CSV parsing failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'transactions': [],
                'account_info': {},
                'statement_info': {}
            }
    
    def _parse_revolut_csv(self, csv_content: str) -> Dict[str, Any]:
        """Parse Revolut-specific CSV format."""
        try:
            transactions = []
            
            reader = csv.DictReader(StringIO(csv_content))
            
            for row in reader:
                try:
                    # Skip pending transactions
                    if row.get('State', '').upper() != 'COMPLETED':
                        continue
                    
                    transaction = {
                        'booking_date': row.get('Completed Date', row.get('Started Date', '')),
                        'value_date': row.get('Completed Date', ''),
                        'description': row.get('Description', ''),
                        'counterparty': '',  # Revolut doesn't always provide this
                        'reference': row.get('Reference', ''),
                        'currency': row.get('Currency', 'CHF'),
                        'transaction_type': row.get('Type', '')
                    }
                    
                    # Amount
                    amount_str = row.get('Amount', '0')
                    try:
                        transaction['amount'] = float(amount_str) if amount_str else 0
                    except ValueError:
                        continue
                    
                    # Fee
                    fee_str = row.get('Fee', '0')
                    try:
                        fee = float(fee_str) if fee_str else 0
                        if fee != 0:
                            transaction['fee'] = fee
                    except ValueError:
                        pass
                    
                    if transaction['amount'] != 0:
                        transactions.append(transaction)
                        
                except Exception as e:
                    self.logger.warning(f"Failed to parse Revolut CSV row: {e}")
                    continue
            
            return {
                'success': True,
                'format': 'csv_revolut',
                'transactions': transactions,
                'transaction_count': len(transactions),
                'account_info': {'bank': 'Revolut'},
                'statement_info': {}
            }
            
        except Exception as e:
            self.logger.error(f"Revolut CSV parsing failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'transactions': [],
                'account_info': {},
                'statement_info': {}
            }
    
    def _parse_swisscard_csv(self, csv_content: str) -> Dict[str, Any]:
        """Parse Swisscard credit card CSV format."""
        try:
            transactions = []
            
            delimiter = ';' if ';' in csv_content[:1000] else ','
            reader = csv.DictReader(StringIO(csv_content), delimiter=delimiter)
            
            for row in reader:
                try:
                    transaction = {
                        'booking_date': row.get('Posting Date', row.get('Buchungsdatum', '')),
                        'value_date': row.get('Transaction Date', row.get('Transaktionsdatum', '')),
                        'description': row.get('Description', row.get('Beschreibung', '')),
                        'counterparty': row.get('Merchant', row.get('Händler', '')),
                        'reference': row.get('Reference', ''),
                        'currency': row.get('Currency', 'CHF'),
                        'card_number': row.get('Card', '')
                    }
                    
                    # Amount (usually negative for expenses on credit card statements)
                    amount_str = row.get('Amount', row.get('Betrag', '0'))
                    amount_str = amount_str.replace("'", "").replace(",", ".")
                    
                    try:
                        transaction['amount'] = float(amount_str) if amount_str else 0
                    except ValueError:
                        continue
                    
                    if transaction['amount'] != 0:
                        transactions.append(transaction)
                        
                except Exception as e:
                    self.logger.warning(f"Failed to parse Swisscard CSV row: {e}")
                    continue
            
            return {
                'success': True,
                'format': 'csv_swisscard',
                'transactions': transactions,
                'transaction_count': len(transactions),
                'account_info': {'bank': 'Swisscard'},
                'statement_info': {}
            }
            
        except Exception as e:
            self.logger.error(f"Swisscard CSV parsing failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'transactions': [],
                'account_info': {},
                'statement_info': {}
            }
    
    def _parse_generic_csv(self, csv_content: str) -> Dict[str, Any]:
        """Parse generic CSV format with smart column detection."""
        try:
            transactions = []
            
            # Try different delimiters
            delimiters = [';', ',', '\t']
            best_delimiter = ';'
            max_columns = 0
            
            for delimiter in delimiters:
                try:
                    sample_reader = csv.reader(StringIO(csv_content[:1000]), delimiter=delimiter)
                    first_row = next(sample_reader)
                    if len(first_row) > max_columns:
                        max_columns = len(first_row)
                        best_delimiter = delimiter
                except:
                    continue
            
            reader = csv.DictReader(StringIO(csv_content), delimiter=best_delimiter)
            fieldnames = reader.fieldnames or []
            
            # Map common column names to standard fields
            column_mapping = self._detect_csv_columns(fieldnames)
            
            for row in reader:
                try:
                    transaction = {}
                    
                    # Map columns to standard fields
                    for standard_field, csv_column in column_mapping.items():
                        if csv_column and csv_column in row:
                            transaction[standard_field] = row[csv_column]
                    
                    # Clean up amount
                    if 'amount' in transaction:
                        amount_str = transaction['amount']
                        amount_str = amount_str.replace("'", "").replace(",", ".")
                        try:
                            transaction['amount'] = float(amount_str) if amount_str else 0
                        except ValueError:
                            continue
                    
                    # Ensure minimum required fields
                    if transaction.get('amount', 0) != 0 and (transaction.get('booking_date') or transaction.get('value_date')):
                        transactions.append(transaction)
                        
                except Exception as e:
                    self.logger.warning(f"Failed to parse generic CSV row: {e}")
                    continue
            
            return {
                'success': True,
                'format': 'csv_generic',
                'transactions': transactions,
                'transaction_count': len(transactions),
                'account_info': {},
                'statement_info': {'column_mapping': column_mapping}
            }
            
        except Exception as e:
            self.logger.error(f"Generic CSV parsing failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'transactions': [],
                'account_info': {},
                'statement_info': {}
            }
    
    def _detect_csv_columns(self, fieldnames: List[str]) -> Dict[str, Optional[str]]:
        """Detect column mapping for generic CSV."""
        mapping = {
            'booking_date': None,
            'value_date': None,
            'description': None,
            'amount': None,
            'counterparty': None,
            'reference': None,
            'currency': None
        }
        
        fieldnames_lower = [f.lower() for f in fieldnames]
        
        # Date patterns
        date_patterns = ['date', 'datum', 'booking', 'transaction', 'posted']
        for pattern in date_patterns:
            for i, field in enumerate(fieldnames_lower):
                if pattern in field and not mapping['booking_date']:
                    mapping['booking_date'] = fieldnames[i]
                    break
        
        # Amount patterns
        amount_patterns = ['amount', 'betrag', 'montant', 'importo']
        for pattern in amount_patterns:
            for i, field in enumerate(fieldnames_lower):
                if pattern in field and not mapping['amount']:
                    mapping['amount'] = fieldnames[i]
                    break
        
        # Description patterns
        desc_patterns = ['description', 'beschreibung', 'text', 'details', 'transaction']
        for pattern in desc_patterns:
            for i, field in enumerate(fieldnames_lower):
                if pattern in field and not mapping['description']:
                    mapping['description'] = fieldnames[i]
                    break
        
        return mapping
    
    def _parse_generic_statement(self, content: str) -> Dict[str, Any]:
        """Parse unknown statement format with basic heuristics."""
        return {
            'success': False,
            'error': 'Unknown statement format',
            'transactions': [],
            'account_info': {},
            'statement_info': {}
        }


# Factory function for easy import
def create_statement_parser() -> StatementParser:
    """Create statement parser instance."""
    return StatementParser()
