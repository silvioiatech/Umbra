import { OpenRouterClient } from '@umbra/shared';
import { Envelope, FinancePayload, ModuleResult, FinanceResult } from '@umbra/shared';
import { CryptoUtils } from '@umbra/shared';
import Logger from '@umbra/shared/src/utils/logger';

export class DocumentExtractor {
  private logger: Logger;
  private openRouterClient: OpenRouterClient;

  constructor(openRouterClient: OpenRouterClient) {
    this.logger = new Logger('DocumentExtractor');
    this.openRouterClient = openRouterClient;
  }

  async extractData(envelope: Envelope<FinancePayload>): Promise<ModuleResult<FinanceResult>> {
    const { reqId, userId, lang, payload } = envelope;
    const startTime = Date.now();

    try {
      this.logger.debug('Starting document extraction', {
        reqId,
        userId,
        documentType: payload.documentType
      });

      if (!payload.documentUrl && !payload.documentData) {
        return {
          reqId,
          status: 'error',
          error: {
            type: 'functional',
            code: 'NO_DOCUMENT',
            message: 'No document provided for extraction',
            retryable: false
          }
        };
      }

      // Enhanced extraction using AI vision if document URL provided
      let extractedData;
      if (payload.documentUrl) {
        extractedData = await this.extractWithVision(payload.documentUrl, payload.documentType || 'document');
      } else {
        // Basic extraction from text data
        extractedData = await this.extractFromText(payload.documentData || '');
      }

      const durationMs = Date.now() - startTime;

      this.logger.audit('Document extraction completed', userId, {
        reqId,
        documentType: payload.documentType,
        confidence: extractedData.confidence,
        durationMs
      });

      return {
        reqId,
        status: 'success',
        data: {
          extractedData: CryptoUtils.minimizePII(extractedData)
        },
        audit: {
          module: 'finance-extractor',
          durationMs
        }
      };

    } catch (error) {
      const durationMs = Date.now() - startTime;
      
      this.logger.error('Document extraction failed', {
        reqId,
        userId,
        error: error.message
      });

      return {
        reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'EXTRACTION_FAILED',
          message: 'Failed to extract document data',
          retryable: true
        },
        audit: {
          module: 'finance-extractor',
          durationMs
        }
      };
    }
  }

  private async extractWithVision(documentUrl: string, documentType: string): Promise<any> {
    const prompt = `
Analyze this financial document and extract structured data. Return JSON with:
{
  "vendor": "company name",
  "amount": "total amount",
  "currency": "currency",
  "date": "date in YYYY-MM-DD",
  "category": "expense category",
  "items": [{"description": "", "amount": "", "quantity": ""}],
  "taxAmount": "tax amount",
  "subtotal": "subtotal before tax",
  "paymentMethod": "payment method",
  "invoiceNumber": "number",
  "confidence": 0.0-1.0
}

Document type: ${documentType}
Focus on accuracy and set confidence based on data clarity.
`;

    try {
      const extractedData = await this.openRouterClient.analyzeImage(documentUrl, prompt);
      return JSON.parse(extractedData);
    } catch (error) {
      this.logger.warn('Vision extraction failed', { error: error.message });
      throw error;
    }
  }

  private async extractFromText(textData: string): Promise<any> {
    // Basic text-based extraction
    return {
      vendor: null,
      amount: null,
      currency: 'USD',
      date: null,
      category: null,
      confidence: 0.1
    };
  }
}