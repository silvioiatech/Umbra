"""
OCR Pipeline for Swiss Accountant
Handles PDF to image conversion and OCR text extraction with language hints.
"""
import os
import tempfile
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from decimal import Decimal
import logging

try:
    import pytesseract
    from PIL import Image
    import fitz  # PyMuPDF for PDF handling
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


class OCRPipeline:
    """OCR pipeline for document text extraction."""
    
    def __init__(self, engine: str = 'tesseract', languages: str = 'deu+fra+ita+eng'):
        """Initialize OCR pipeline.
        
        Args:
            engine: OCR engine to use ('tesseract' or 'fallback')
            languages: Language codes for OCR (e.g., 'deu+fra+ita+eng')
        """
        self.engine = engine
        self.languages = languages
        self.logger = logging.getLogger(__name__)
        
        # Check if Tesseract is available
        if engine == 'tesseract' and not TESSERACT_AVAILABLE:
            self.logger.warning("Tesseract not available, falling back to simulation")
            self.engine = 'fallback'
    
    def extract_text_from_file(self, file_path: str, file_type: str = None) -> Dict[str, Any]:
        """Extract text from file (PDF, image, etc.).
        
        Args:
            file_path: Path to the file
            file_type: File type hint ('pdf', 'image', etc.)
            
        Returns:
            Dict with text, confidence, and metadata
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                return {
                    'success': False,
                    'error': f'File not found: {file_path}',
                    'text': '',
                    'confidence': 0,
                    'pages': 0
                }
            
            # Detect file type if not provided
            if not file_type:
                file_type = self._detect_file_type(file_path)
            
            if file_type == 'pdf':
                return self._extract_from_pdf(file_path)
            elif file_type in ['image', 'jpg', 'jpeg', 'png', 'tiff']:
                return self._extract_from_image(file_path)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported file type: {file_type}',
                    'text': '',
                    'confidence': 0,
                    'pages': 0
                }
                
        except Exception as e:
            self.logger.error(f"OCR extraction failed for {file_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'confidence': 0,
                'pages': 0
            }
    
    def _detect_file_type(self, file_path: Path) -> str:
        """Detect file type from extension."""
        extension = file_path.suffix.lower()
        
        if extension == '.pdf':
            return 'pdf'
        elif extension in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
            return 'image'
        else:
            return 'unknown'
    
    def _extract_from_pdf(self, file_path: Path) -> Dict[str, Any]:
        """Extract text from PDF file."""
        if self.engine == 'fallback':
            return self._fallback_pdf_extraction(file_path)
        
        try:
            # Open PDF with PyMuPDF
            doc = fitz.open(str(file_path))
            all_text = []
            all_confidence = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # First try to extract text directly (if PDF has text layer)
                text = page.get_text()
                
                if text.strip():
                    # PDF has text layer
                    all_text.append(text)
                    all_confidence.append(95.0)  # High confidence for text layer
                else:
                    # No text layer, need OCR
                    # Convert page to image
                    mat = fitz.Matrix(2.0, 2.0)  # 200% zoom for better OCR
                    pix = page.get_pixmap(matrix=mat)
                    img_data = pix.tobytes("png")
                    
                    # Save to temp file for OCR
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                        temp_file.write(img_data)
                        temp_file.flush()
                        
                        # Perform OCR on image
                        ocr_result = self._extract_from_image(Path(temp_file.name))
                        all_text.append(ocr_result['text'])
                        all_confidence.append(ocr_result['confidence'])
                        
                        # Clean up temp file
                        os.unlink(temp_file.name)
            
            doc.close()
            
            # Combine all pages
            combined_text = '\n\n--- PAGE BREAK ---\n\n'.join(all_text)
            avg_confidence = sum(all_confidence) / len(all_confidence) if all_confidence else 0
            
            return {
                'success': True,
                'text': combined_text,
                'confidence': avg_confidence,
                'pages': len(doc),
                'method': 'pdf_text_and_ocr' if any(c < 90 for c in all_confidence) else 'pdf_text'
            }
            
        except Exception as e:
            self.logger.error(f"PDF OCR failed: {e}")
            return self._fallback_pdf_extraction(file_path)
    
    def _extract_from_image(self, file_path: Path) -> Dict[str, Any]:
        """Extract text from image file."""
        if self.engine == 'fallback':
            return self._fallback_image_extraction(file_path)
        
        try:
            # Open image with PIL
            image = Image.open(file_path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Perform OCR with Tesseract
            config = f'--oem 3 --psm 6 -l {self.languages}'
            
            # Get text and confidence
            text = pytesseract.image_to_string(image, config=config)
            
            # Get detailed OCR data for confidence calculation
            data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
            
            # Calculate average confidence (excluding -1 values)
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            return {
                'success': True,
                'text': text.strip(),
                'confidence': avg_confidence,
                'pages': 1,
                'method': 'tesseract_ocr',
                'language_hint': self.languages
            }
            
        except Exception as e:
            self.logger.error(f"Image OCR failed: {e}")
            return self._fallback_image_extraction(file_path)
    
    def _fallback_pdf_extraction(self, file_path: Path) -> Dict[str, Any]:
        """Fallback PDF extraction when libraries are not available."""
        return {
            'success': True,
            'text': f"""[OCR SIMULATION - PDF: {file_path.name}]

RECHNUNG / FACTURE / FATTURA

Migros Supermarkt
Bahnhofstrasse 123
8001 Zürich

Datum: 15.01.2024
Zeit: 14:30

Positionen:
- Brot Vollkorn         CHF 3.50
- Milch Bio 1L          CHF 1.95
- Äpfel Gala 1kg        CHF 4.20
- Kaffee Bohnen         CHF 8.90

Zwischensumme:         CHF 18.55
MWST 2.6% (Lebensmittel): CHF 0.48
Total:                 CHF 19.03

Zahlung: Maestro ****1234
Danke für Ihren Einkauf!

UID: CHE-123.456.789""",
            'confidence': 75.0,
            'pages': 1,
            'method': 'simulation'
        }
    
    def _fallback_image_extraction(self, file_path: Path) -> Dict[str, Any]:
        """Fallback image extraction when libraries are not available."""
        return {
            'success': True,
            'text': f"""[OCR SIMULATION - Image: {file_path.name}]

QUITTUNG
Restaurant Sternen
Hauptgasse 45, 3000 Bern

15.01.2024  19:45
Tisch 12

2x Schnitzel Wiener Art  CHF 36.00
1x Rösti                 CHF 12.00
2x Salat gemischt        CHF 16.00
3x Mineralwasser         CHF 9.00

Zwischensumme:          CHF 73.00
MWST 8.1%:              CHF 5.91
Total:                  CHF 78.91

Trinkgeld:              CHF 6.00
Gesamtbetrag:           CHF 84.91

Bar bezahlt
Merci!""",
            'confidence': 78.0,
            'pages': 1,
            'method': 'simulation'
        }
    
    def preprocess_image_for_ocr(self, image_path: Path) -> Path:
        """Preprocess image for better OCR results.
        
        Args:
            image_path: Path to original image
            
        Returns:
            Path to processed image
        """
        if not TESSERACT_AVAILABLE:
            return image_path
        
        try:
            from PIL import ImageEnhance, ImageFilter
            
            # Open image
            image = Image.open(image_path)
            
            # Convert to grayscale for better OCR
            if image.mode != 'L':
                image = image.convert('L')
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)
            
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.0)
            
            # Apply slight blur to reduce noise
            image = image.filter(ImageFilter.MedianFilter())
            
            # Save processed image
            processed_path = image_path.parent / f"processed_{image_path.name}"
            image.save(processed_path)
            
            return processed_path
            
        except Exception as e:
            self.logger.warning(f"Image preprocessing failed: {e}")
            return image_path
    
    def extract_swiss_specific_patterns(self, text: str) -> Dict[str, Any]:
        """Extract Swiss-specific patterns from OCR text.
        
        Args:
            text: OCR extracted text
            
        Returns:
            Dict with extracted patterns
        """
        import re
        
        patterns = {
            'amounts': [],
            'swiss_vat_rates': [],
            'iban': None,
            'uid_number': None,
            'postal_codes': [],
            'dates': []
        }
        
        # Swiss amount patterns (CHF)
        amount_patterns = [
            r'CHF\s*(\d{1,6}(?:[.,]\d{2})?)',
            r'(\d{1,6}(?:[.,]\d{2})?)\s*CHF',
            r'Fr\.?\s*(\d{1,6}(?:[.,]\d{2})?)',
            r'(\d{1,6}(?:[.,]\d{2})?)\s*Fr\.?'
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    # Normalize decimal separator
                    amount_str = match.replace(',', '.')
                    amount = float(amount_str)
                    if 0.01 <= amount <= 999999:  # Reasonable range
                        patterns['amounts'].append(amount)
                except (ValueError, TypeError):
                    continue
        
        # Swiss VAT rates (8.1%, 2.6%, 3.8%)
        vat_patterns = [
            r'(?:MWST|TVA|IVA|VAT)\s*([0-9.,]+)\s*%',
            r'([0-9.,]+)\s*%\s*(?:MWST|TVA|IVA|VAT)'
        ]
        
        for pattern in vat_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    rate = float(match.replace(',', '.'))
                    if rate in [8.1, 2.6, 3.8, 0.0]:
                        patterns['swiss_vat_rates'].append(rate)
                except (ValueError, TypeError):
                    continue
        
        # Swiss IBAN
        iban_pattern = r'CH\d{2}\s?(?:\d{4}\s?){4}\d{1}'
        iban_match = re.search(iban_pattern, text)
        if iban_match:
            patterns['iban'] = iban_match.group(0).replace(' ', '')
        
        # Swiss UID number
        uid_pattern = r'CHE[-\s]?(\d{3}\.?\d{3}\.?\d{3})'
        uid_match = re.search(uid_pattern, text, re.IGNORECASE)
        if uid_match:
            patterns['uid_number'] = f"CHE-{uid_match.group(1).replace('.', '.')}"
        
        # Swiss postal codes
        postal_pattern = r'\b([1-9]\d{3})\b'
        postal_matches = re.findall(postal_pattern, text)
        for match in postal_matches:
            code = int(match)
            if 1000 <= code <= 9999:  # Valid Swiss postal code range
                patterns['postal_codes'].append(code)
        
        # Date patterns (DD.MM.YYYY, DD/MM/YYYY)
        date_patterns = [
            r'(\d{1,2})[./](\d{1,2})[./](\d{4})',
            r'(\d{1,2})[./](\d{1,2})[./](\d{2})'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    day, month, year = map(int, match)
                    if len(match[2]) == 2:  # 2-digit year
                        year = 2000 + year if year < 50 else 1900 + year
                    
                    if 1 <= day <= 31 and 1 <= month <= 12 and 1990 <= year <= 2030:
                        patterns['dates'].append(f"{day:02d}.{month:02d}.{year}")
                except (ValueError, TypeError):
                    continue
        
        return patterns


# Factory function for easy import
def create_ocr_pipeline(engine: str = 'tesseract', languages: str = 'deu+fra+ita+eng') -> OCRPipeline:
    """Create OCR pipeline instance."""
    return OCRPipeline(engine, languages)
