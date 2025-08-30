"""Financial data extraction and categorization."""

import json
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal

from umbra_shared import (
    OpenRouterClient,
    UmbraLogger,
    Envelope,
    FinancePayload,
    ModuleResult,
    FinanceResult,
)


class FinanceExtractor:
    """Extract and categorize financial data from documents."""
    
    def __init__(self, openrouter_client: OpenRouterClient):
        self.logger = UmbraLogger("FinanceExtractor")
        self.openrouter_client = openrouter_client
        
        # Expense categories for classification
        self.expense_categories = {
            "office_supplies": ["paper", "pen", "stationery", "office", "supplies"],
            "software": ["software", "license", "subscription", "saas", "cloud"],
            "travel": ["hotel", "flight", "taxi", "uber", "travel", "transport"],
            "meals": ["restaurant", "food", "meal", "lunch", "dinner", "catering"],
            "utilities": ["electric", "gas", "water", "internet", "phone", "utility"],
            "rent": ["rent", "lease", "office space", "building"],
            "equipment": ["computer", "laptop", "monitor", "equipment", "hardware"],
            "marketing": ["advertising", "marketing", "promotion", "ad", "campaign"],
            "professional": ["consultant", "legal", "accounting", "professional"],
            "other": []
        }
        
        # VAT rates by country (can be extended)
        self.vat_rates = {
            "default": 0.20,  # 20%
            "FR": 0.20,       # France
            "DE": 0.19,       # Germany
            "UK": 0.20,       # United Kingdom
            "ES": 0.21,       # Spain
            "IT": 0.22,       # Italy
            "PT": 0.23,       # Portugal
        }
    
    async def extract_and_categorize(
        self,
        envelope: Envelope[FinancePayload],
        raw_text: str,
        extracted_data: Optional[Dict[str, Any]] = None
    ) -> ModuleResult[FinanceResult]:
        """Extract financial data and categorize expenses."""
        start_time = datetime.utcnow()
        req_id = envelope.req_id
        
        try:
            self.logger.debug("Starting financial data extraction",
                            req_id=req_id,
                            action=envelope.payload.action)
            
            # Use provided extracted data or extract from text
            if not extracted_data:
                extracted_data = await self._extract_financial_data(raw_text, envelope.payload.document_type)
            
            # Categorize the expense
            category = self._categorize_expense(raw_text, extracted_data)
            extracted_data["category"] = category
            
            # Calculate VAT if not present
            if "tax_amount" not in extracted_data and "amount" in extracted_data:
                vat_info = self._calculate_vat(extracted_data.get("amount"), extracted_data.get("currency"))
                extracted_data.update(vat_info)
            
            # Validate and clean data
            validated_data = self._validate_data(extracted_data)
            
            # Check for potential anomalies
            anomalies = self._detect_anomalies(validated_data)
            
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            result_data = FinanceResult(
                extracted_data=validated_data,
                anomalies=anomalies,
                raw_text=raw_text,
                confidence=validated_data.get("confidence", 0.8),
                needs_review=len(anomalies) > 0 or validated_data.get("confidence", 0.8) < 0.7
            )
            
            self.logger.info("Financial data extraction completed",
                           req_id=req_id,
                           category=category,
                           anomalies_count=len(anomalies))
            
            return ModuleResult(
                req_id=req_id,
                status="success",
                data=result_data,
                audit={
                    "module": "finance-extractor",
                    "duration_ms": duration_ms,
                    "category": category,
                    "anomalies": len(anomalies)
                }
            )
            
        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            self.logger.error("Financial data extraction failed",
                            req_id=req_id,
                            error=str(e))
            
            return ModuleResult(
                req_id=req_id,
                status="error",
                error={
                    "type": "technical",
                    "code": "EXTRACTION_ERROR",
                    "message": f"Financial data extraction failed: {str(e)}",
                    "retryable": True
                },
                audit={
                    "module": "finance-extractor",
                    "duration_ms": duration_ms
                }
            )
    
    async def _extract_financial_data(
        self,
        text: str,
        document_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract financial data using AI."""
        try:
            doc_type = document_type or "financial_document"
            
            system_prompt = f"""You are a financial data extraction specialist. 
Extract structured data from this {doc_type} and return a JSON object with:

Required fields:
- vendor: company/vendor name
- amount: total amount (number only, no currency symbol)
- currency: currency code (EUR, USD, GBP, etc.)
- date: date in YYYY-MM-DD format
- confidence: extraction confidence (0-1)

Optional fields:
- document_number: invoice/receipt number
- tax_amount: VAT/tax amount
- net_amount: amount before tax
- description: brief description of goods/services
- payment_method: how it was paid
- location: where the transaction occurred

Return only valid JSON, no additional text."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract data from: {text[:2000]}"}
            ]
            
            response = await self.openrouter_client.chat_completion(
                model="openai/gpt-3.5-turbo",
                messages=messages,
                temperature=0.1,
                max_tokens=800
            )
            
            # Parse JSON response
            extracted_data = json.loads(response.choices[0].message.content)
            
            self.logger.debug("AI extraction completed",
                            vendor=extracted_data.get("vendor"),
                            amount=extracted_data.get("amount"))
            
            return extracted_data
            
        except Exception as e:
            self.logger.warning("AI extraction failed, using pattern matching", error=str(e))
            return self._pattern_based_extraction(text)
    
    def _pattern_based_extraction(self, text: str) -> Dict[str, Any]:
        """Fallback pattern-based extraction."""
        extracted = {"confidence": 0.6}
        
        # Extract vendor/company (first line or after specific keywords)
        vendor_patterns = [
            r'^([A-Z][A-Za-z\s&.,]+?)(?:\n|$)',
            r'(?:company|vendor|from)[:\s]*([A-Za-z\s&.,]+)',
        ]
        
        for pattern in vendor_patterns:
            matches = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
            if matches:
                extracted["vendor"] = matches[0].strip()
                break
        
        # Extract amounts with currency
        amount_patterns = [
            r'(?:total|amount|sum)[:\s]*([€$£¥₹]?)(\d+[.,]\d{2})\s*([A-Z]{3})?',
            r'([€$£¥₹])(\d+[.,]\d{2})',
            r'(\d+[.,]\d{2})\s*([€$£¥₹€USD|EUR|GBP|JPY])',
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                match = matches[0]
                if len(match) == 3:  # (symbol, amount, currency)
                    symbol, amount, currency = match
                    extracted["amount"] = float(amount.replace(',', '.'))
                    extracted["currency"] = currency or self._symbol_to_currency(symbol)
                elif len(match) == 2:  # (symbol/currency, amount) or (amount, symbol/currency)
                    if match[0].replace(',', '.').replace('.', '').isdigit():
                        # (amount, currency)
                        extracted["amount"] = float(match[0].replace(',', '.'))
                        extracted["currency"] = self._symbol_to_currency(match[1])
                    else:
                        # (currency, amount)
                        extracted["amount"] = float(match[1].replace(',', '.'))
                        extracted["currency"] = self._symbol_to_currency(match[0])
                break
        
        # Extract dates
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
            r'(\d{2}[./]\d{2}[./]\d{4})',  # DD/MM/YYYY or MM/DD/YYYY
            r'(\d{1,2}[./]\d{1,2}[./]\d{2})',  # D/M/YY
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            if matches:
                extracted["date"] = self._normalize_date(matches[0])
                break
        
        # Extract document number
        doc_patterns = [
            r'(?:invoice|bill|receipt|document|ref)[\s#:]*([A-Z0-9-]+)',
            r'(?:nr|no|number)[\s#:]*([A-Z0-9-]+)',
        ]
        
        for pattern in doc_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                extracted["document_number"] = matches[0]
                break
        
        return extracted
    
    def _symbol_to_currency(self, symbol: str) -> str:
        """Convert currency symbol to currency code."""
        symbol_map = {
            "€": "EUR",
            "$": "USD", 
            "£": "GBP",
            "¥": "JPY",
            "₹": "INR"
        }
        return symbol_map.get(symbol, symbol.upper())
    
    def _normalize_date(self, date_str: str) -> str:
        """Normalize date string to YYYY-MM-DD format."""
        try:
            # Try different date formats
            formats = [
                "%Y-%m-%d",
                "%d/%m/%Y", "%m/%d/%Y",
                "%d.%m.%Y", "%m.%d.%Y",
                "%d/%m/%y", "%m/%d/%y"
            ]
            
            for fmt in formats:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    return date_obj.strftime("%Y-%m-%d")
                except ValueError:
                    continue
            
            return date_str
            
        except Exception:
            return date_str
    
    def _categorize_expense(self, text: str, extracted_data: Dict[str, Any]) -> str:
        """Categorize expense based on text content and extracted data."""
        text_lower = text.lower()
        vendor = extracted_data.get("vendor", "").lower()
        description = extracted_data.get("description", "").lower()
        
        search_text = f"{text_lower} {vendor} {description}"
        
        # Check each category
        for category, keywords in self.expense_categories.items():
            if category == "other":
                continue
                
            for keyword in keywords:
                if keyword in search_text:
                    return category
        
        return "other"
    
    def _calculate_vat(self, amount: Any, currency: Optional[str] = None) -> Dict[str, Any]:
        """Calculate VAT information."""
        try:
            amount_float = float(amount)
            vat_rate = self.vat_rates.get("default", 0.20)
            
            # Assume amount includes VAT, calculate net and VAT
            net_amount = amount_float / (1 + vat_rate)
            vat_amount = amount_float - net_amount
            
            return {
                "net_amount": round(net_amount, 2),
                "tax_amount": round(vat_amount, 2),
                "tax_rate": vat_rate
            }
            
        except (ValueError, TypeError):
            return {}
    
    def _validate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean extracted data."""
        validated = data.copy()
        
        # Validate amount
        if "amount" in validated:
            try:
                validated["amount"] = float(validated["amount"])
                if validated["amount"] <= 0:
                    del validated["amount"]
            except (ValueError, TypeError):
                if "amount" in validated:
                    del validated["amount"]
        
        # Validate date
        if "date" in validated:
            try:
                datetime.strptime(validated["date"], "%Y-%m-%d")
            except ValueError:
                # Try to normalize it
                validated["date"] = self._normalize_date(validated["date"])
        
        # Validate currency
        if "currency" in validated:
            currency = validated["currency"].upper()
            if len(currency) == 3 and currency.isalpha():
                validated["currency"] = currency
            else:
                del validated["currency"]
        
        # Ensure confidence is between 0 and 1
        if "confidence" in validated:
            try:
                confidence = float(validated["confidence"])
                validated["confidence"] = max(0.0, min(1.0, confidence))
            except (ValueError, TypeError):
                validated["confidence"] = 0.5
        
        return validated
    
    def _detect_anomalies(self, data: Dict[str, Any]) -> List[str]:
        """Detect potential anomalies in the data."""
        anomalies = []
        
        # Check for unusually high amounts
        if "amount" in data:
            amount = data["amount"]
            if amount > 10000:
                anomalies.append(f"High amount detected: {amount}")
            if amount < 0:
                anomalies.append("Negative amount detected")
        
        # Check for future dates
        if "date" in data:
            try:
                doc_date = datetime.strptime(data["date"], "%Y-%m-%d")
                if doc_date > datetime.now() + timedelta(days=1):
                    anomalies.append("Future date detected")
                if doc_date < datetime.now() - timedelta(days=365 * 2):
                    anomalies.append("Very old date detected (>2 years)")
            except ValueError:
                anomalies.append("Invalid date format")
        
        # Check for missing critical fields
        critical_fields = ["vendor", "amount", "date"]
        for field in critical_fields:
            if field not in data:
                anomalies.append(f"Missing critical field: {field}")
        
        # Check confidence
        if data.get("confidence", 1.0) < 0.5:
            anomalies.append("Low extraction confidence")
        
        return anomalies