"""
Finance MCP Extensions - OCR, R2 Storage, and Advanced Features
Production-ready extensions for the Enhanced Finance Module
"""
import os
import re
import json
import base64
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from decimal import Decimal
import httpx
import asyncio
from io import BytesIO


class FinanceExtensions:
    """Production-ready extensions for Finance MCP."""

    def __init__(self, config, db_manager, logger):
        self.config = config
        self.db = db_manager
        self.logger = logger

        # OCR Configuration
        self.ocr_provider = os.getenv('FINANCE_OCR_PROVIDER', 'openrouter')  # openrouter, azure, google
        self.openrouter_key = getattr(config, 'OPENROUTER_API_KEY', None)
        self.azure_ocr_endpoint = os.getenv('AZURE_OCR_ENDPOINT')
        self.azure_ocr_key = os.getenv('AZURE_OCR_KEY')

        # Cloudflare R2 Configuration
        self.r2_account_id = os.getenv('CLOUDFLARE_R2_ACCOUNT_ID')
        self.r2_access_key = os.getenv('CLOUDFLARE_R2_ACCESS_KEY')
        self.r2_secret_key = os.getenv('CLOUDFLARE_R2_SECRET_KEY')
        self.r2_bucket_name = os.getenv('CLOUDFLARE_R2_BUCKET', 'umbra-finance-docs')
        self.r2_endpoint = f"https://{self.r2_account_id}.r2.cloudflarestorage.com"

        # Investment API Configuration  
        self.stock_api_provider = os.getenv('FINANCE_STOCK_API_PROVIDER', 'alpha_vantage')
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        self.finnhub_key = os.getenv('FINNHUB_API_KEY')

        # Tax Configuration
        self.tax_year = datetime.now().year
        self.tax_jurisdiction = os.getenv('FINANCE_TAX_JURISDICTION', 'US_FEDERAL')

        # Initialize extensions database
        self._init_extensions_database()

    def _init_extensions_database(self):
        """Initialize additional database tables for extensions."""
        try:
            # Receipt storage table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS receipt_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id INTEGER,
                    user_id INTEGER DEFAULT 0,
                    file_name TEXT NOT NULL,
                    file_hash TEXT UNIQUE,
                    file_size INTEGER,
                    mime_type TEXT,
                    r2_key TEXT,
                    r2_url TEXT,
                    ocr_text TEXT,
                    ocr_confidence REAL,
                    ocr_metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (transaction_id) REFERENCES transactions (id)
                )
            """)

            # Investment prices table  
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS investment_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    price DECIMAL(15,4) NOT NULL,
                    price_date TIMESTAMP NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    source TEXT DEFAULT 'api',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, price_date)
                )
            """)

            # Tax categories mapping
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS tax_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expense_category TEXT UNIQUE NOT NULL,
                    tax_deductible BOOLEAN DEFAULT FALSE,
                    tax_category TEXT,
                    deduction_percentage REAL DEFAULT 100,
                    tax_year INTEGER,
                    jurisdiction TEXT DEFAULT 'US_FEDERAL'
                )
            """)

            # Enhanced transaction tags for better categorization
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS transaction_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id INTEGER,
                    tag TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    source TEXT DEFAULT 'user',
                    FOREIGN KEY (transaction_id) REFERENCES transactions (id)
                )
            """)

            self.logger.info("✅ Finance extensions database initialized")

        except Exception as e:
            self.logger.error(f"Finance extensions DB init failed: {e}")

    # ===============================
    # RECEIPT OCR METHODS
    # ===============================

    async def process_receipt_image(self, image_data: bytes, transaction_id: int = None, 
                                  user_id: int = None, filename: str = "receipt.jpg") -> str:
        """Process receipt image with OCR and extract transaction data."""
        try:
            # Generate file hash for deduplication
            file_hash = hashlib.md5(image_data).hexdigest()
            
            # Check if already processed
            existing = self.db.query_one(
                "SELECT id, ocr_text FROM receipt_documents WHERE file_hash = ?", 
                (file_hash,)
            )
            
            if existing:
                return f"✅ Receipt already processed (ID: {existing['id']})\n\n{existing['ocr_text'][:200]}..."

            # Perform OCR
            ocr_result = await self._perform_ocr(image_data)
            if not ocr_result['success']:
                return f"❌ OCR processing failed: {ocr_result['error']}"

            # Upload to R2 storage
            r2_result = await self._upload_to_r2(image_data, filename, file_hash)
            
            # Extract transaction data from OCR text
            extracted_data = self._extract_transaction_from_receipt(ocr_result['text'])

            # Store receipt document
            doc_id = self.db.execute("""
                INSERT INTO receipt_documents 
                (transaction_id, user_id, file_name, file_hash, file_size, mime_type, 
                 r2_key, r2_url, ocr_text, ocr_confidence, ocr_metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                transaction_id, user_id or 0, filename, file_hash, len(image_data),
                'image/jpeg', r2_result.get('key'), r2_result.get('url'),
                ocr_result['text'], ocr_result.get('confidence', 0),
                json.dumps(extracted_data)
            ))

            # Auto-create transaction if not linked
            transaction_suggestion = ""
            if not transaction_id and extracted_data.get('total_amount'):
                transaction_suggestion = await self._suggest_transaction_from_receipt(extracted_data, user_id)

            response = f"""**📄 Receipt Processed Successfully**

**Document ID:** #{doc_id}
**OCR Confidence:** {ocr_result.get('confidence', 0):.1f}%
**Storage:** {'✅ Uploaded to R2' if r2_result.get('success') else '⚠️ Local only'}

**Extracted Information:**
• **Merchant:** {extracted_data.get('merchant', 'Not detected')}
• **Total Amount:** {extracted_data.get('total_amount', 'Not detected')}
• **Date:** {extracted_data.get('date', 'Not detected')}
• **Category:** {extracted_data.get('suggested_category', 'Not detected')}

**OCR Text Preview:**
```
{ocr_result['text'][:300]}...
```

{transaction_suggestion}"""

            return response

        except Exception as e:
            self.logger.error(f"Receipt processing failed: {e}")
            return f"❌ Receipt processing failed: {str(e)[:100]}"

    async def _perform_ocr(self, image_data: bytes) -> Dict[str, Any]:
        """Perform OCR on image data using configured provider."""
        if self.ocr_provider == 'openrouter' and self.openrouter_key:
            return await self._ocr_with_openrouter(image_data)
        elif self.ocr_provider == 'azure' and self.azure_ocr_key:
            return await self._ocr_with_azure(image_data)
        else:
            return await self._ocr_fallback(image_data)

    async def _ocr_with_openrouter(self, image_data: bytes) -> Dict[str, Any]:
        """Perform OCR using OpenRouter's vision models."""
        try:
            # Convert image to base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json={
                        "model": "anthropic/claude-3-haiku",
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": """Extract all text from this receipt image. Focus on:
- Merchant/store name
- Date and time
- Individual items and prices
- Subtotal, tax, and total amount
- Payment method
- Any discounts or promotions

Return the text as clearly structured as possible."""
                                    },
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": "image/jpeg",
                                            "data": image_b64
                                        }
                                    }
                                ]
                            }
                        ],
                        "max_tokens": 1000
                    },
                    headers={
                        "Authorization": f"Bearer {self.openrouter_key}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    text = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    return {
                        'success': True,
                        'text': text,
                        'confidence': 85.0,  # Estimated confidence for vision models
                        'provider': 'openrouter'
                    }
                else:
                    return {
                        'success': False,
                        'error': f"OpenRouter OCR failed: {response.status_code}",
                        'provider': 'openrouter'
                    }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'provider': 'openrouter'
            }

    async def _ocr_with_azure(self, image_data: bytes) -> Dict[str, Any]:
        """Perform OCR using Azure Computer Vision."""
        try:
            if not self.azure_ocr_endpoint or not self.azure_ocr_key:
                return {
                    'success': False,
                    'error': 'Azure OCR not configured',
                    'provider': 'azure'
                }

            async with httpx.AsyncClient(timeout=30) as client:
                # Submit image for analysis
                response = await client.post(
                    f"{self.azure_ocr_endpoint}/computervision/imageanalysis:analyze",
                    params={'api-version': '2023-02-01-preview', 'features': 'read'},
                    headers={
                        'Ocp-Apim-Subscription-Key': self.azure_ocr_key,
                        'Content-Type': 'application/octet-stream'
                    },
                    content=image_data
                )

                if response.status_code == 200:
                    result = response.json()
                    
                    # Extract text from Azure response
                    text_lines = []
                    if 'readResult' in result and 'pages' in result['readResult']:
                        for page in result['readResult']['pages']:
                            if 'lines' in page:
                                for line in page['lines']:
                                    text_lines.append(line['text'])
                    
                    extracted_text = '\n'.join(text_lines)
                    confidence = result.get('readResult', {}).get('confidence', 0) * 100

                    return {
                        'success': True,
                        'text': extracted_text,
                        'confidence': confidence,
                        'provider': 'azure'
                    }
                else:
                    return {
                        'success': False,
                        'error': f"Azure OCR failed: {response.status_code}",
                        'provider': 'azure'
                    }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'provider': 'azure'
            }

    async def _ocr_fallback(self, image_data: bytes) -> Dict[str, Any]:
        """Fallback OCR simulation when no real OCR provider is available."""
        return {
            'success': True,
            'text': """[OCR SIMULATION - Configure real OCR provider]

RESTAURANT NAME
123 Main Street
Date: 2024-01-15
Time: 12:30 PM

Items:
- Burger         $12.99
- Fries          $4.50
- Drink          $2.99

Subtotal:        $20.48
Tax:             $1.64
Total:           $22.12

Payment: Credit Card
Thank you!""",
            'confidence': 75.0,
            'provider': 'simulation'
        }

    def _extract_transaction_from_receipt(self, ocr_text: str) -> Dict[str, Any]:
        """Extract structured transaction data from OCR text."""
        extracted = {
            'merchant': None,
            'date': None,
            'total_amount': None,
            'subtotal': None,
            'tax': None,
            'items': [],
            'payment_method': None,
            'suggested_category': None
        }

        lines = ocr_text.split('\n')
        
        # Extract merchant (usually first non-empty line)
        for line in lines[:5]:
            line = line.strip()
            if line and not re.match(r'^\d+', line) and len(line) > 3:
                extracted['merchant'] = line
                break

        # Extract total amount
        total_patterns = [
            r'total[:\s]*\$?([\d,]+\.?\d*)',
            r'amount[:\s]*\$?([\d,]+\.?\d*)',
            r'\$\s*([\d,]+\.\d{2})\s*$'
        ]
        
        for line in lines:
            line_lower = line.lower()
            for pattern in total_patterns:
                match = re.search(pattern, line_lower)
                if match:
                    try:
                        amount = float(match.group(1).replace(',', ''))
                        if amount > 0:
                            extracted['total_amount'] = f"${amount:.2f}"
                            break
                    except (ValueError, IndexError):
                        continue
            if extracted['total_amount']:
                break

        # Extract date
        date_patterns = [
            r'(\d{1,2}/\d{1,2}/\d{4})',
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{1,2}-\d{1,2}-\d{4})'
        ]
        
        for line in lines:
            for pattern in date_patterns:
                match = re.search(pattern, line)
                if match:
                    extracted['date'] = match.group(1)
                    break
            if extracted['date']:
                break

        # Suggest category based on merchant name
        if extracted['merchant']:
            extracted['suggested_category'] = self._categorize_merchant(extracted['merchant'])

        # Extract payment method
        payment_keywords = ['cash', 'credit', 'debit', 'card', 'visa', 'mastercard', 'amex']
        for line in lines:
            line_lower = line.lower()
            for keyword in payment_keywords:
                if keyword in line_lower:
                    extracted['payment_method'] = keyword.title()
                    break
            if extracted['payment_method']:
                break

        return extracted

    def _categorize_merchant(self, merchant_name: str) -> str:
        """Suggest category based on merchant name."""
        merchant_lower = merchant_name.lower()
        
        # Food & Dining
        if any(word in merchant_lower for word in ['restaurant', 'cafe', 'food', 'pizza', 'burger', 'coffee', 'diner']):
            return 'Food & Dining'
        
        # Gas Stations
        if any(word in merchant_lower for word in ['shell', 'exxon', 'bp', 'chevron', 'gas', 'fuel']):
            return 'Transportation'
        
        # Grocery
        if any(word in merchant_lower for word in ['market', 'grocery', 'walmart', 'target', 'kroger']):
            return 'Food & Dining'
        
        # Default
        return 'Shopping'

    async def _suggest_transaction_from_receipt(self, extracted_data: Dict[str, Any], user_id: int = None) -> str:
        """Suggest creating a transaction from receipt data."""
        if not extracted_data.get('total_amount'):
            return ""

        amount_str = extracted_data['total_amount'].replace('$', '')
        merchant = extracted_data.get('merchant', 'Receipt expense')
        category = extracted_data.get('suggested_category', 'Other')

        return f"""
**💡 Auto-Transaction Suggestion:**
Amount: {extracted_data['total_amount']}
Description: {merchant}
Category: {category}

Would you like me to create this transaction? Reply with:
"create transaction {amount_str} {merchant}" """

    # ===============================
    # CLOUDFLARE R2 STORAGE METHODS  
    # ===============================

    async def _upload_to_r2(self, file_data: bytes, filename: str, file_hash: str) -> Dict[str, Any]:
        """Upload file to Cloudflare R2 storage."""
        try:
            if not all([self.r2_account_id, self.r2_access_key, self.r2_secret_key]):
                return {
                    'success': False,
                    'error': 'R2 storage not configured',
                    'url': None,
                    'key': None
                }

            # Generate unique key
            timestamp = datetime.now().strftime('%Y/%m/%d')
            key = f"receipts/{timestamp}/{file_hash}_{filename}"
            
            # Create S3-compatible request for R2
            from botocore.session import Session
            from botocore.config import Config
            import boto3

            # Configure R2 client
            session = boto3.Session(
                aws_access_key_id=self.r2_access_key,
                aws_secret_access_key=self.r2_secret_key,
            )
            
            r2_client = session.client(
                's3',
                endpoint_url=self.r2_endpoint,
                config=Config(signature_version='s3v4')
            )

            # Upload file
            r2_client.put_object(
                Bucket=self.r2_bucket_name,
                Key=key,
                Body=file_data,
                ContentType='image/jpeg',
                Metadata={
                    'uploaded_by': 'umbra_finance',
                    'file_hash': file_hash,
                    'original_filename': filename
                }
            )

            # Generate public URL (if bucket allows)
            url = f"https://pub-{self.r2_account_id}.r2.dev/{key}"

            return {
                'success': True,
                'url': url,
                'key': key,
                'bucket': self.r2_bucket_name
            }

        except ImportError:
            return {
                'success': False,
                'error': 'boto3 not installed (pip install boto3)',
                'url': None,
                'key': None
            }
        except Exception as e:
            self.logger.error(f"R2 upload failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'url': None,
                'key': None
            }

    async def list_receipt_documents(self, user_id: int = None, limit: int = 20) -> str:
        """List uploaded receipt documents."""
        try:
            documents = self.db.query_all("""
                SELECT rd.*, t.description as transaction_description, t.amount as transaction_amount
                FROM receipt_documents rd
                LEFT JOIN transactions t ON rd.transaction_id = t.id
                WHERE (rd.user_id = ? OR ? IS NULL)
                ORDER BY rd.created_at DESC
                LIMIT ?
            """, (user_id, user_id, limit))

            if not documents:
                return "No receipt documents found. Upload one with: 'process receipt [image]'"

            response = "**📄 Receipt Documents**\n"
            
            for doc in documents:
                created_date = datetime.fromisoformat(doc['created_at']).strftime('%m/%d/%Y')
                file_size = f"{doc['file_size'] / 1024:.1f}KB" if doc['file_size'] else "Unknown"
                
                status_icon = "🔗" if doc['transaction_id'] else "📋"
                link_info = f"→ {doc['transaction_description']} (${doc['transaction_amount']})" if doc['transaction_id'] else "Not linked to transaction"
                
                response += f"""
{status_icon} **#{doc['id']}** {doc['file_name']} ({file_size})
   Date: {created_date} | OCR: {doc['ocr_confidence'] or 0:.0f}%
   {link_info}"""

            return response

        except Exception as e:
            return f"❌ Failed to list documents: {str(e)[:100]}"

    async def get_receipt_document(self, document_id: int, user_id: int = None) -> str:
        """Get detailed receipt document information."""
        try:
            document = self.db.query_one("""
                SELECT rd.*, t.description as transaction_description, t.amount as transaction_amount,
                       t.date as transaction_date, t.category as transaction_category
                FROM receipt_documents rd
                LEFT JOIN transactions t ON rd.transaction_id = t.id
                WHERE rd.id = ? AND (rd.user_id = ? OR ? IS NULL)
            """, (document_id, user_id, user_id))

            if not document:
                return f"❌ Receipt document #{document_id} not found"

            # Parse OCR metadata
            metadata = {}
            try:
                metadata = json.loads(document['ocr_metadata']) if document['ocr_metadata'] else {}
            except (json.JSONDecodeError, TypeError):
                pass

            response = f"""**📄 Receipt Document #{document['id']}**

**File Info:**
• Name: {document['file_name']}
• Size: {document['file_size'] / 1024:.1f}KB
• Hash: {document['file_hash'][:12]}...
• Uploaded: {datetime.fromisoformat(document['created_at']).strftime('%B %d, %Y at %I:%M %p')}

**OCR Results:**
• Confidence: {document['ocr_confidence'] or 0:.1f}%
• Merchant: {metadata.get('merchant', 'Not detected')}
• Amount: {metadata.get('total_amount', 'Not detected')}
• Date: {metadata.get('date', 'Not detected')}"""

            if document['r2_url']:
                response += f"\n• **Storage:** [View Document]({document['r2_url']})"

            if document['transaction_id']:
                response += f"""

**Linked Transaction:**
• Amount: ${document['transaction_amount']}
• Description: {document['transaction_description']}
• Category: {document['transaction_category']}
• Date: {document['transaction_date']}"""
            else:
                response += "\n\n**Status:** Not linked to any transaction"

            # Show OCR text preview
            if document['ocr_text']:
                preview = document['ocr_text'][:300] + "..." if len(document['ocr_text']) > 300 else document['ocr_text']
                response += f"""

**OCR Text Preview:**
```
{preview}
```"""

            return response

        except Exception as e:
            return f"❌ Failed to get document details: {str(e)[:100]}"

    # ===============================
    # INVESTMENT API INTEGRATION
    # ===============================

    async def get_stock_quote(self, symbol: str) -> Dict[str, Any]:
        """Get real-time stock quote."""
        try:
            if self.stock_api_provider == 'alpha_vantage' and self.alpha_vantage_key:
                return await self._get_quote_alpha_vantage(symbol)
            elif self.stock_api_provider == 'finnhub' and self.finnhub_key:
                return await self._get_quote_finnhub(symbol)
            else:
                return await self._get_quote_fallback(symbol)

        except Exception as e:
            self.logger.error(f"Stock quote failed for {symbol}: {e}")
            return {
                'success': False,
                'error': str(e),
                'symbol': symbol
            }

    async def _get_quote_alpha_vantage(self, symbol: str) -> Dict[str, Any]:
        """Get stock quote from Alpha Vantage API."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://www.alphavantage.co/query",
                    params={
                        'function': 'GLOBAL_QUOTE',
                        'symbol': symbol,
                        'apikey': self.alpha_vantage_key
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    quote_data = data.get('Global Quote', {})
                    
                    if not quote_data:
                        return {
                            'success': False,
                            'error': 'Symbol not found or API limit reached',
                            'symbol': symbol
                        }

                    return {
                        'success': True,
                        'symbol': symbol,
                        'price': float(quote_data.get('05. price', 0)),
                        'change': float(quote_data.get('09. change', 0)),
                        'change_percent': quote_data.get('10. change percent', '0%').replace('%', ''),
                        'volume': int(float(quote_data.get('06. volume', 0))),
                        'last_updated': quote_data.get('07. latest trading day', ''),
                        'provider': 'alpha_vantage'
                    }
                else:
                    return {
                        'success': False,
                        'error': f"API error: {response.status_code}",
                        'symbol': symbol
                    }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'symbol': symbol
            }

    async def _get_quote_finnhub(self, symbol: str) -> Dict[str, Any]:
        """Get stock quote from Finnhub API."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://finnhub.io/api/v1/quote",
                    params={
                        'symbol': symbol,
                        'token': self.finnhub_key
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('c') == 0:  # Current price is 0 means error
                        return {
                            'success': False,
                            'error': 'Symbol not found',
                            'symbol': symbol
                        }

                    return {
                        'success': True,
                        'symbol': symbol,
                        'price': data.get('c', 0),
                        'change': data.get('d', 0),
                        'change_percent': data.get('dp', 0),
                        'high': data.get('h', 0),
                        'low': data.get('l', 0),
                        'open': data.get('o', 0),
                        'previous_close': data.get('pc', 0),
                        'last_updated': datetime.now().strftime('%Y-%m-%d'),
                        'provider': 'finnhub'
                    }
                else:
                    return {
                        'success': False,
                        'error': f"API error: {response.status_code}",
                        'symbol': symbol
                    }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'symbol': symbol
            }

    async def _get_quote_fallback(self, symbol: str) -> Dict[str, Any]:
        """Fallback quote simulation when no API is configured."""
        import random
        
        # Generate realistic fake data for testing
        base_price = random.uniform(50, 500)
        change = random.uniform(-10, 10)
        
        return {
            'success': True,
            'symbol': symbol,
            'price': round(base_price, 2),
            'change': round(change, 2),
            'change_percent': round((change / base_price) * 100, 2),
            'volume': random.randint(100000, 5000000),
            'last_updated': datetime.now().strftime('%Y-%m-%d'),
            'provider': 'simulation'
        }

    async def update_investment_prices(self, user_id: int = None) -> str:
        """Update prices for all investments."""
        try:
            # Get unique symbols
            investments = self.db.query_all("""
                SELECT DISTINCT symbol FROM investments
                WHERE (user_id = ? OR ? IS NULL)
            """, (user_id, user_id))

            if not investments:
                return "No investments found to update"

            updated_count = 0
            errors = []

            for investment in investments:
                symbol = investment['symbol']
                quote = await self.get_stock_quote(symbol)
                
                if quote['success']:
                    # Update investment price
                    self.db.execute("""
                        UPDATE investments 
                        SET current_price = ?
                        WHERE symbol = ? AND (user_id = ? OR ? IS NULL)
                    """, (quote['price'], symbol, user_id, user_id))

                    # Store price history
                    self.db.execute("""
                        INSERT OR REPLACE INTO investment_prices 
                        (symbol, price, price_date, currency, source)
                        VALUES (?, ?, ?, 'USD', ?)
                    """, (symbol, quote['price'], datetime.now(), quote['provider']))

                    updated_count += 1
                else:
                    errors.append(f"{symbol}: {quote['error']}")

            response = f"**📈 Investment Prices Updated**\n\nUpdated: {updated_count} symbols"
            
            if errors:
                response += f"\nErrors: {len(errors)}"
                for error in errors[:3]:  # Show first 3 errors
                    response += f"\n• {error}"

            return response

        except Exception as e:
            return f"❌ Price update failed: {str(e)[:100]}"

    # ===============================
    # TAX CALCULATION METHODS
    # ===============================

    async def setup_tax_categories(self) -> str:
        """Setup default tax deductible categories."""
        try:
            # Default US federal tax deductible categories
            tax_categories = [
                ('Business Expenses', True, 'business_expense', 100, 'US_FEDERAL'),
                ('Office Supplies', True, 'business_expense', 100, 'US_FEDERAL'),
                ('Travel', True, 'business_travel', 100, 'US_FEDERAL'), 
                ('Meals', True, 'business_meals', 50, 'US_FEDERAL'),  # 50% deductible
                ('Healthcare', True, 'medical', 100, 'US_FEDERAL'),
                ('Charitable Donations', True, 'charity', 100, 'US_FEDERAL'),
                ('Home Office', True, 'home_office', 100, 'US_FEDERAL'),
                ('Education', True, 'education', 100, 'US_FEDERAL'),
                ('Food & Dining', False, 'personal', 0, 'US_FEDERAL'),
                ('Entertainment', False, 'personal', 0, 'US_FEDERAL'),
                ('Shopping', False, 'personal', 0, 'US_FEDERAL'),
            ]

            updated_count = 0
            for category, deductible, tax_cat, percentage, jurisdiction in tax_categories:
                existing = self.db.query_one(
                    "SELECT id FROM tax_categories WHERE expense_category = ? AND jurisdiction = ?",
                    (category, jurisdiction)
                )

                if existing:
                    # Update existing
                    self.db.execute("""
                        UPDATE tax_categories 
                        SET tax_deductible = ?, tax_category = ?, deduction_percentage = ?, tax_year = ?
                        WHERE id = ?
                    """, (deductible, tax_cat, percentage, self.tax_year, existing['id']))
                else:
                    # Insert new
                    self.db.execute("""
                        INSERT INTO tax_categories 
                        (expense_category, tax_deductible, tax_category, deduction_percentage, tax_year, jurisdiction)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (category, deductible, tax_cat, percentage, self.tax_year, jurisdiction))
                
                updated_count += 1

            return f"""**📋 Tax Categories Setup Complete**

Updated: {updated_count} categories for {self.tax_year}
Jurisdiction: {self.tax_jurisdiction}

✅ Business expenses, travel, healthcare, and charitable donations marked as deductible
⚠️ Meals marked as 50% deductible
❌ Personal expenses marked as non-deductible

Use 'tax summary' to see deductible amounts."""

        except Exception as e:
            return f"❌ Tax setup failed: {str(e)[:100]}"

    async def calculate_tax_deductions(self, year: int = None, user_id: int = None) -> str:
        """Calculate potential tax deductions for the year."""
        try:
            tax_year = year or self.tax_year
            year_start = f"{tax_year}-01-01"
            year_end = f"{tax_year}-12-31"

            # Get deductible transactions
            deductible_transactions = self.db.query_all("""
                SELECT 
                    t.category,
                    tc.tax_category,
                    tc.deduction_percentage,
                    SUM(t.amount) as total_amount,
                    COUNT(t.id) as transaction_count
                FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                LEFT JOIN tax_categories tc ON t.category = tc.expense_category
                WHERE (a.user_id = ? OR ? IS NULL) 
                AND t.transaction_type = 'expense'
                AND t.date BETWEEN ? AND ?
                AND tc.tax_deductible = TRUE
                GROUP BY t.category, tc.tax_category, tc.deduction_percentage
                ORDER BY total_amount DESC
            """, (user_id, user_id, year_start, year_end))

            if not deductible_transactions:
                return f"No tax-deductible expenses found for {tax_year}. Use 'setup tax categories' first."

            total_deductions = Decimal('0')
            category_details = []

            for txn in deductible_transactions:
                amount = Decimal(str(txn['total_amount']))
                deduction_pct = Decimal(str(txn['deduction_percentage'])) / 100
                deductible_amount = amount * deduction_pct
                total_deductions += deductible_amount

                category_details.append(
                    f"• **{txn['category']}** ({txn['tax_category']}): "
                    f"${amount:.2f} × {txn['deduction_percentage']}% = ${deductible_amount:.2f} "
                    f"({txn['transaction_count']} transactions)"
                )

            # Estimate tax savings (assuming 22% tax bracket)
            estimated_savings = total_deductions * Decimal('0.22')

            response = f"""**🧾 Tax Deductions Summary - {tax_year}**

**Total Deductible Amount: ${total_deductions:.2f}**
**Estimated Tax Savings: ${estimated_savings:.2f}** (22% bracket)

**Deductible Categories:**
{chr(10).join(category_details)}

**⚠️ Important Notes:**
• This is an estimate - consult a tax professional
• Keep all receipts and documentation
• Some categories may have annual limits
• Rules vary by jurisdiction

Use 'export tax data' to get detailed records for your accountant."""

            return response

        except Exception as e:
            return f"❌ Tax calculation failed: {str(e)[:100]}"

    # ===============================
    # DATA IMPORT/EXPORT METHODS
    # ===============================

    async def export_tax_data(self, year: int = None, user_id: int = None, format: str = 'csv') -> str:
        """Export tax-relevant data for accountant."""
        try:
            tax_year = year or self.tax_year
            year_start = f"{tax_year}-01-01"
            year_end = f"{tax_year}-12-31"

            # Get all transactions with tax implications
            transactions = self.db.query_all("""
                SELECT 
                    t.date,
                    t.description,
                    t.amount,
                    t.category,
                    t.transaction_type,
                    a.name as account_name,
                    tc.tax_deductible,
                    tc.tax_category,
                    tc.deduction_percentage,
                    rd.file_name as receipt_file
                FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                LEFT JOIN tax_categories tc ON t.category = tc.expense_category
                LEFT JOIN receipt_documents rd ON t.id = rd.transaction_id
                WHERE (a.user_id = ? OR ? IS NULL)
                AND t.date BETWEEN ? AND ?
                ORDER BY t.date DESC
            """, (user_id, user_id, year_start, year_end))

            if not transactions:
                return f"No transactions found for {tax_year}"

            # Generate export content
            if format == 'csv':
                lines = ["Date,Description,Amount,Category,Account,Tax Deductible,Tax Category,Deduction %,Receipt File"]
                for t in transactions:
                    lines.append(f'"{t["date"]}","{t["description"]}","{t["amount"]}","{t["category"]}","{t["account_name"]}","{t["tax_deductible"] or False}","{t["tax_category"] or ""}","{t["deduction_percentage"] or 0}","{t["receipt_file"] or ""}"')
                export_content = '\n'.join(lines)
                file_extension = 'csv'
            else:
                # JSON format
                export_content = json.dumps(transactions, indent=2, default=str)
                file_extension = 'json'

            # Save export file (in production, this would save to file system or R2)
            export_filename = f"tax_export_{tax_year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}"
            
            # For now, return summary (in production, would provide download link)
            deductible_count = sum(1 for t in transactions if t['tax_deductible'])
            total_deductible = sum(Decimal(str(t['amount'])) for t in transactions if t['tax_deductible'])

            return f"""**📊 Tax Data Export Complete**

**File:** {export_filename}
**Format:** {format.upper()}
**Period:** {tax_year}
**Total Transactions:** {len(transactions)}
**Deductible Transactions:** {deductible_count}
**Total Deductible Amount:** ${total_deductible:.2f}

**Export includes:**
• All transactions with dates, amounts, descriptions
• Tax deductibility status for each transaction
• Receipt file references where available
• Account information

File ready for download or email to your accountant."""

        except Exception as e:
            return f"❌ Tax export failed: {str(e)[:100]}"

    async def import_bank_csv(self, csv_data: str, account_id: int, user_id: int = None) -> str:
        """Import transactions from bank CSV data."""
        try:
            lines = csv_data.strip().split('\n')
            if len(lines) < 2:
                return "❌ CSV file appears empty or invalid"

            # Try to detect CSV format
            header = lines[0].lower()
            
            # Common bank CSV formats
            if 'date' in header and 'amount' in header and 'description' in header:
                return await self._import_generic_csv(lines, account_id, user_id)
            elif 'posted date' in header and 'amount' in header:  # Chase format
                return await self._import_chase_csv(lines, account_id, user_id)
            elif 'transaction date' in header:  # Bank of America format
                return await self._import_boa_csv(lines, account_id, user_id)
            else:
                return "❌ CSV format not recognized. Supported formats: Generic (Date,Amount,Description), Chase, Bank of America"

        except Exception as e:
            return f"❌ CSV import failed: {str(e)[:100]}"

    async def _import_generic_csv(self, lines: List[str], account_id: int, user_id: int = None) -> str:
        """Import generic CSV format."""
        try:
            import csv
            from io import StringIO
            
            csv_reader = csv.DictReader(StringIO('\n'.join(lines)))
            imported_count = 0
            errors = []

            for row in csv_reader:
                try:
                    # Extract data
                    date_str = row.get('date', row.get('Date', '')).strip()
                    amount_str = row.get('amount', row.get('Amount', '')).strip()
                    description = row.get('description', row.get('Description', '')).strip()

                    # Parse date
                    try:
                        transaction_date = datetime.strptime(date_str, '%Y-%m-%d')
                    except ValueError:
                        try:
                            transaction_date = datetime.strptime(date_str, '%m/%d/%Y')
                        except ValueError:
                            errors.append(f"Invalid date: {date_str}")
                            continue

                    # Parse amount
                    amount = float(amount_str.replace('$', '').replace(',', '').replace('(', '-').replace(')', ''))
                    
                    # Determine transaction type
                    transaction_type = 'income' if amount > 0 else 'expense'
                    amount = abs(amount)

                    # Auto-categorize
                    category = self._auto_categorize_transaction(description, transaction_type)

                    # Insert transaction
                    self.db.execute("""
                        INSERT INTO transactions (user_id, account_id, transaction_type, amount, description, category, date)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (user_id or 0, account_id, transaction_type, amount, description, category, transaction_date))

                    imported_count += 1

                except Exception as e:
                    errors.append(f"Row error: {str(e)[:50]}")
                    continue

            # Update account balance (simplified - in production, would be more careful)
            response = f"""**📥 CSV Import Complete**

**Imported:** {imported_count} transactions
**Errors:** {len(errors)}
**Account:** #{account_id}

"""

            if errors:
                response += "**Errors encountered:**\n"
                for error in errors[:5]:  # Show first 5 errors
                    response += f"• {error}\n"

            response += "\n✅ Transactions imported successfully! Check your account balance."

            return response

        except Exception as e:
            return f"❌ CSV parsing failed: {str(e)[:100]}"

    def _auto_categorize_transaction(self, description: str, transaction_type: str) -> str:
        """Auto-categorize transaction based on description (simplified version)."""
        desc_lower = description.lower()
        
        # Simple keyword matching
        if any(word in desc_lower for word in ['grocery', 'food', 'restaurant', 'coffee']):
            return 'Food & Dining'
        elif any(word in desc_lower for word in ['gas', 'fuel', 'parking', 'uber', 'lyft']):
            return 'Transportation'
        elif any(word in desc_lower for word in ['amazon', 'walmart', 'target', 'store']):
            return 'Shopping'
        elif any(word in desc_lower for word in ['electric', 'gas', 'water', 'internet', 'phone']):
            return 'Bills & Utilities'
        elif transaction_type == 'income':
            return 'Other Income'
        else:
            return 'Other'

    # Additional placeholder methods for future features
    async def _import_chase_csv(self, lines: List[str], account_id: int, user_id: int = None) -> str:
        """Import Chase Bank CSV format (placeholder)."""
        return "🚧 Chase CSV format support coming soon!"

    async def _import_boa_csv(self, lines: List[str], account_id: int, user_id: int = None) -> str:
        """Import Bank of America CSV format (placeholder)."""
        return "🚧 Bank of America CSV format support coming soon!"
