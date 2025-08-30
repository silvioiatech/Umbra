import Tesseract from 'tesseract.js';
import sharp from 'sharp';
import pdfParse from 'pdf-parse';
import { OpenRouterClient } from '@umbra/shared';
import { Envelope, FinancePayload, ModuleResult, FinanceResult } from '@umbra/shared';
import { CryptoUtils } from '@umbra/shared';
import { Logger } from '@umbra/shared';

export class OCRProcessor {
  private logger: Logger;
  private openRouterClient: OpenRouterClient;

  constructor(openRouterClient: OpenRouterClient) {
    this.logger = new Logger('OCRProcessor');
    this.openRouterClient = openRouterClient;
  }

  async processDocument(
    envelope: Envelope<FinancePayload>,
    documentBuffer: Buffer,
    fileName: string
  ): Promise<ModuleResult<FinanceResult>> {
    const { reqId, userId, lang } = envelope;
    const startTime = Date.now();

    try {
      this.logger.debug('Starting OCR processing', {
        reqId,
        userId,
        fileName,
        fileSize: documentBuffer.length
      });

      // Determine file type and extract text
      const mimeType = this.getMimeType(fileName);
      let extractedText: string;

      if (mimeType === 'application/pdf') {
        extractedText = await this.extractFromPDF(documentBuffer);
      } else if (mimeType.startsWith('image/')) {
        extractedText = await this.extractFromImage(documentBuffer);
      } else {
        throw new Error(`Unsupported file type: ${mimeType}`);
      }

      if (!extractedText || extractedText.trim().length === 0) {
        return {
          reqId,
          status: 'error',
          error: {
            type: 'functional',
            code: 'NO_TEXT_EXTRACTED',
            message: 'No text could be extracted from the document',
            retryable: false
          }
        };
      }

      // Use AI to structure the extracted data
      const structuredData = await this.structureExtractedData(extractedText, lang);

      // Validate confidence threshold
      if (structuredData.confidence < 0.8) {
        return {
          reqId,
          status: 'needs_validation',
          data: {
            extractedData: CryptoUtils.minimizePII(structuredData),
            rawText: extractedText.substring(0, 1000), // Truncate for security
            confidence: structuredData.confidence,
            needsReview: true
          }
        };
      }

      const durationMs = Date.now() - startTime;

      this.logger.audit('OCR processing completed successfully', userId, {
        reqId,
        fileName: CryptoUtils.hashForLogging(fileName),
        confidence: structuredData.confidence,
        durationMs
      });

      return {
        reqId,
        status: 'success',
        data: {
          extractedData: CryptoUtils.minimizePII(structuredData)
        },
        audit: {
          module: 'finance-ocr',
          durationMs
        }
      };

    } catch (error) {
      const durationMs = Date.now() - startTime;
      
      this.logger.error('OCR processing failed', {
        reqId,
        userId,
        fileName: CryptoUtils.hashForLogging(fileName),
        error: error.message
      });

      return {
        reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'OCR_FAILED',
          message: 'Failed to process document with OCR',
          retryable: true
        },
        audit: {
          module: 'finance-ocr',
          durationMs
        }
      };
    }
  }

  private async extractFromPDF(pdfBuffer: Buffer): Promise<string> {
    try {
      const data = await pdfParse(pdfBuffer);
      return data.text;
    } catch (error) {
      this.logger.warn('PDF text extraction failed, trying OCR on pages');
      // If PDF text extraction fails, we could convert to images and OCR
      // For now, throw the error
      throw new Error(`PDF processing failed: ${error.message}`);
    }
  }

  private async extractFromImage(imageBuffer: Buffer): Promise<string> {
    try {
      // Preprocess image for better OCR results
      const processedImage = await this.preprocessImage(imageBuffer);
      
      // Perform OCR
      const { data: { text } } = await Tesseract.recognize(processedImage, 'eng', {
        logger: m => {
          if (m.status === 'recognizing text') {
            this.logger.debug('OCR progress', { progress: m.progress });
          }
        }
      });

      return text;
    } catch (error) {
      throw new Error(`Image OCR failed: ${error.message}`);
    }
  }

  private async preprocessImage(imageBuffer: Buffer): Promise<Buffer> {
    try {
      // Enhance image for better OCR results
      return await sharp(imageBuffer)
        .greyscale() // Convert to grayscale
        .normalize() // Normalize contrast
        .sharpen() // Sharpen text
        .png() // Convert to PNG for consistent processing
        .toBuffer();
    } catch (error) {
      this.logger.warn('Image preprocessing failed, using original', { error: error.message });
      return imageBuffer;
    }
  }

  private async structureExtractedData(text: string, lang: string): Promise<any> {
    const prompt = `
Extract structured financial data from this text. Return JSON only with these fields:
{
  "vendor": "company/vendor name",
  "amount": "numeric amount",
  "currency": "currency code (USD, EUR, etc)",
  "date": "date in YYYY-MM-DD format",
  "category": "expense category",
  "description": "item description",
  "invoiceNumber": "invoice/receipt number",
  "confidence": 0.0-1.0,
  "documentType": "invoice|receipt|statement|other"
}

Text to process:
${text}

Important: 
- Only return valid JSON
- Set confidence based on data quality (0.8+ for clear data)
- Use null for missing fields
- Detect language and extract accordingly
`;

    try {
      const result = await this.openRouterClient.generateJSON(prompt);
      
      // Validate and clean the result
      return this.validateAndCleanData(result);
    } catch (error) {
      this.logger.warn('AI structuring failed, using basic extraction', { error: error.message });
      return this.basicDataExtraction(text);
    }
  }

  private validateAndCleanData(data: any): any {
    const cleaned = {
      vendor: this.cleanString(data.vendor),
      amount: this.parseAmount(data.amount),
      currency: this.cleanString(data.currency) || 'USD',
      date: this.parseDate(data.date),
      category: this.cleanString(data.category),
      description: this.cleanString(data.description),
      invoiceNumber: this.cleanString(data.invoiceNumber),
      confidence: typeof data.confidence === 'number' ? data.confidence : 0.5,
      documentType: this.cleanString(data.documentType) || 'other'
    };

    // Adjust confidence based on completeness
    const requiredFields = ['vendor', 'amount', 'date'];
    const presentFields = requiredFields.filter(field => cleaned[field] !== null);
    const completeness = presentFields.length / requiredFields.length;
    
    cleaned.confidence = Math.min(cleaned.confidence, completeness);

    return cleaned;
  }

  private basicDataExtraction(text: string): any {
    // Basic regex-based extraction as fallback
    const patterns = {
      amount: /\$?(\d+[.,]\d{2})/g,
      date: /(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})/g,
      invoice: /(?:invoice|receipt|ref)[:\s#]*([A-Z0-9\-]+)/i
    };

    const amounts = text.match(patterns.amount);
    const dates = text.match(patterns.date);
    const invoices = text.match(patterns.invoice);

    return {
      vendor: null,
      amount: amounts ? this.parseAmount(amounts[0]) : null,
      currency: 'USD',
      date: dates ? this.parseDate(dates[0]) : null,
      category: null,
      description: null,
      invoiceNumber: invoices ? invoices[1] : null,
      confidence: 0.3, // Low confidence for basic extraction
      documentType: 'other'
    };
  }

  private cleanString(value: any): string | null {
    if (typeof value !== 'string') return null;
    const cleaned = value.trim();
    return cleaned.length > 0 ? cleaned : null;
  }

  private parseAmount(value: any): number | null {
    if (typeof value === 'number') return value;
    if (typeof value !== 'string') return null;
    
    const cleaned = value.replace(/[^\d.,]/g, '');
    const parsed = parseFloat(cleaned.replace(',', '.'));
    
    return isNaN(parsed) ? null : parsed;
  }

  private parseDate(value: any): string | null {
    if (!value) return null;
    
    try {
      const date = new Date(value);
      if (isNaN(date.getTime())) return null;
      return date.toISOString().split('T')[0];
    } catch (error) {
      return null;
    }
  }

  private getMimeType(fileName: string): string {
    const ext = fileName.split('.').pop()?.toLowerCase();
    const mimeTypes: Record<string, string> = {
      'pdf': 'application/pdf',
      'jpg': 'image/jpeg',
      'jpeg': 'image/jpeg',
      'png': 'image/png',
      'gif': 'image/gif',
      'webp': 'image/webp'
    };

    return mimeTypes[ext || ''] || 'application/octet-stream';
  }

  /**
   * Detect anomalies in extracted data
   */
  detectAnomalies(data: any): string[] {
    const anomalies: string[] = [];

    // Check for unusually high amounts
    if (data.amount && data.amount > 10000) {
      anomalies.push('High amount detected');
    }

    // Check for future dates
    if (data.date) {
      const docDate = new Date(data.date);
      const today = new Date();
      if (docDate > today) {
        anomalies.push('Future date detected');
      }
    }

    // Check for very old dates
    if (data.date) {
      const docDate = new Date(data.date);
      const oneYearAgo = new Date();
      oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
      if (docDate < oneYearAgo) {
        anomalies.push('Old document detected');
      }
    }

    // Check for suspicious vendors
    if (data.vendor) {
      const suspiciousPatterns = ['test', 'sample', 'example', 'dummy'];
      if (suspiciousPatterns.some(pattern => 
        data.vendor.toLowerCase().includes(pattern))) {
        anomalies.push('Suspicious vendor name');
      }
    }

    return anomalies;
  }
}