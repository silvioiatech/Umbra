"""OCR processing for financial documents."""

import pytesseract
import cv2
import numpy as np
import mimetypes
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import io
from PIL import Image
import PyPDF2
from pdf2image import convert_from_bytes

from umbra_shared import (
    OpenRouterClient,
    UmbraLogger,
    Envelope,
    FinancePayload,
    ModuleResult,
    FinanceResult,
)


class OCRProcessor:
    """Process documents using OCR for text extraction."""
    
    def __init__(self, openrouter_client: OpenRouterClient):
        self.logger = UmbraLogger("OCRProcessor")
        self.openrouter_client = openrouter_client
        
        # OCR configuration
        self.tesseract_config = '--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,@€$£¥₹+-=():;!?"\' '
        
        # Supported mime types
        self.supported_types = {
            'application/pdf',
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
            'image/bmp', 'image/tiff', 'image/webp'
        }
    
    async def process_document(
        self,
        envelope: Envelope[FinancePayload],
        document_buffer: bytes,
        filename: str
    ) -> ModuleResult[FinanceResult]:
        """Process document and extract text using OCR."""
        start_time = datetime.utcnow()
        req_id = envelope.req_id
        user_id = envelope.user_id
        
        try:
            self.logger.debug("Starting OCR processing",
                            req_id=req_id,
                            user_id=user_id,
                            filename=filename,
                            file_size=len(document_buffer))
            
            # Determine file type
            mime_type = self._get_mime_type(filename)
            
            if mime_type not in self.supported_types:
                return ModuleResult(
                    req_id=req_id,
                    status="error",
                    error={
                        "type": "functional",
                        "code": "UNSUPPORTED_FILE_TYPE",
                        "message": f"Unsupported file type: {mime_type}",
                        "retryable": False
                    }
                )
            
            # Extract text based on file type
            if mime_type == 'application/pdf':
                extracted_text = await self._extract_from_pdf(document_buffer)
            else:
                extracted_text = await self._extract_from_image(document_buffer)
            
            if not extracted_text or not extracted_text.strip():
                return ModuleResult(
                    req_id=req_id,
                    status="error",
                    error={
                        "type": "functional",
                        "code": "NO_TEXT_EXTRACTED",
                        "message": "No text could be extracted from the document",
                        "retryable": True
                    }
                )
            
            self.logger.info("OCR processing completed",
                           req_id=req_id,
                           text_length=len(extracted_text))
            
            # Enhance extraction with AI if available
            enhanced_data = await self._enhance_with_ai(extracted_text, envelope.payload.document_type)
            
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            result_data = FinanceResult(
                raw_text=extracted_text,
                extracted_data=enhanced_data,
                confidence=enhanced_data.get("confidence", 0.8),
                needs_review=enhanced_data.get("confidence", 0.8) < 0.7
            )
            
            return ModuleResult(
                req_id=req_id,
                status="success",
                data=result_data,
                audit={
                    "module": "finance-ocr",
                    "duration_ms": duration_ms,
                    "provider": "tesseract+openrouter",
                    "text_length": len(extracted_text)
                }
            )
            
        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            self.logger.error("OCR processing failed",
                            req_id=req_id,
                            filename=filename,
                            error=str(e))
            
            return ModuleResult(
                req_id=req_id,
                status="error",
                error={
                    "type": "technical",
                    "code": "OCR_PROCESSING_ERROR",
                    "message": f"OCR processing failed: {str(e)}",
                    "retryable": True
                },
                audit={
                    "module": "finance-ocr",
                    "duration_ms": duration_ms
                }
            )
    
    def _get_mime_type(self, filename: str) -> str:
        """Get MIME type from filename."""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"
    
    async def _extract_from_pdf(self, pdf_buffer: bytes) -> str:
        """Extract text from PDF document."""
        try:
            # First try PyPDF2 for text-based PDFs
            pdf_text = ""
            pdf_file = io.BytesIO(pdf_buffer)
            
            try:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text.strip():
                        pdf_text += page_text + "\n"
                
                if pdf_text.strip():
                    self.logger.debug("Extracted text from PDF using PyPDF2")
                    return pdf_text.strip()
                    
            except Exception as e:
                self.logger.warning("PyPDF2 extraction failed, trying OCR", error=str(e))
            
            # Fall back to OCR for image-based PDFs
            self.logger.debug("Converting PDF to images for OCR")
            images = convert_from_bytes(pdf_buffer, dpi=300)
            
            ocr_text = ""
            for i, image in enumerate(images):
                self.logger.debug(f"Processing page {i+1} with OCR")
                
                # Preprocess image
                processed_image = self._preprocess_image(np.array(image))
                
                # Extract text
                page_text = pytesseract.image_to_string(
                    processed_image,
                    config=self.tesseract_config
                )
                
                if page_text.strip():
                    ocr_text += page_text + "\n"
            
            return ocr_text.strip()
            
        except Exception as e:
            self.logger.error("PDF text extraction failed", error=str(e))
            raise
    
    async def _extract_from_image(self, image_buffer: bytes) -> str:
        """Extract text from image using OCR."""
        try:
            # Load image
            image = Image.open(io.BytesIO(image_buffer))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert to numpy array
            image_np = np.array(image)
            
            # Preprocess image
            processed_image = self._preprocess_image(image_np)
            
            # Extract text
            text = pytesseract.image_to_string(
                processed_image,
                config=self.tesseract_config
            )
            
            self.logger.debug("Extracted text from image using Tesseract")
            return text.strip()
            
        except Exception as e:
            self.logger.error("Image text extraction failed", error=str(e))
            raise
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for better OCR results."""
        try:
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image
            
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)
            
            # Apply threshold to get binary image
            _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Morphological operations to clean up
            kernel = np.ones((1, 1), np.uint8)
            processed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            processed = cv2.morphologyEx(processed, cv2.MORPH_OPEN, kernel)
            
            return processed
            
        except Exception as e:
            self.logger.warning("Image preprocessing failed, using original", error=str(e))
            return image
    
    async def _enhance_with_ai(
        self,
        raw_text: str,
        document_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enhance OCR results with AI-based extraction."""
        try:
            if not document_type:
                document_type = "financial_document"
            
            system_prompt = f"""You are a financial document data extraction AI. 
Extract structured data from this {document_type} text.
Return a JSON object with relevant fields like:
- vendor/company name
- amount/total 
- date
- document_number/invoice_number
- tax_amount (if applicable)
- currency
- confidence (0-1 score)

Text to analyze:
{raw_text}"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract data from: {raw_text[:1000]}"}  # Limit text
            ]
            
            response = await self.openrouter_client.chat_completion(
                model="openai/gpt-3.5-turbo",
                messages=messages,
                temperature=0.1,
                max_tokens=500
            )
            
            # Parse JSON response
            import json
            extracted_data = json.loads(response.choices[0].message.content)
            
            self.logger.debug("AI enhancement completed", 
                            confidence=extracted_data.get("confidence"))
            
            return extracted_data
            
        except Exception as e:
            self.logger.warning("AI enhancement failed, using basic extraction", error=str(e))
            
            # Fallback to basic pattern matching
            return self._basic_pattern_extraction(raw_text)
    
    def _basic_pattern_extraction(self, text: str) -> Dict[str, Any]:
        """Basic pattern-based extraction as fallback."""
        import re
        
        extracted = {
            "confidence": 0.5,
            "extraction_method": "pattern_matching"
        }
        
        # Extract amounts (€, $, £ symbols or decimal numbers)
        amount_patterns = [
            r'(?:€|EUR|$|USD|£|GBP)\s*(\d+[.,]\d{2})',
            r'(\d+[.,]\d{2})\s*(?:€|EUR|$|USD|£|GBP)',
            r'(?:total|amount|sum)[:\s]*(\d+[.,]\d{2})',
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                extracted["amount"] = matches[0].replace(',', '.')
                break
        
        # Extract dates
        date_patterns = [
            r'(\d{1,2}[./]\d{1,2}[./]\d{2,4})',
            r'(\d{2,4}-\d{1,2}-\d{1,2})',
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            if matches:
                extracted["date"] = matches[0]
                break
        
        # Extract invoice/document numbers
        doc_patterns = [
            r'(?:invoice|bill|receipt|doc)[\s#:]*([A-Z0-9-]+)',
            r'(?:nr|no|number)[\s#:]*([A-Z0-9-]+)',
        ]
        
        for pattern in doc_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                extracted["document_number"] = matches[0]
                break
        
        return extracted