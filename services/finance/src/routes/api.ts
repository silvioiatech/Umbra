import express from 'express';
import multer from 'multer';
import { OpenRouterClient, StorageClient } from '@umbra/shared';
import { Envelope, FinancePayload, ModuleResult } from '@umbra/shared';
import { OCRProcessor } from '../ocr/ocr-processor';
import { DocumentExtractor } from '../extraction/document-extractor';
import { FinancialCategorizer } from '../handlers/financial-categorizer';
import { ReportGenerator } from '../reports/report-generator';
import { DataDeduplicator } from '../handlers/data-deduplicator';
import { Logger } from '@umbra/shared';

export function apiRoutes(
  openRouterClient: OpenRouterClient, 
  storageClient: StorageClient, 
  upload: multer.Multer
): express.Router {
  const router = express.Router();
  const logger = new Logger('FinanceAPIRoutes');
  
  const ocrProcessor = new OCRProcessor(openRouterClient);
  const documentExtractor = new DocumentExtractor(openRouterClient);
  const categorizer = new FinancialCategorizer(openRouterClient);
  const reportGenerator = new ReportGenerator(openRouterClient, storageClient);
  const deduplicator = new DataDeduplicator();

  // OCR processing endpoint
  router.post('/ocr', upload.single('document'), async (req, res) => {
    try {
      const envelope: Envelope<FinancePayload> = req.body;
      const { reqId, userId, lang, payload } = envelope;
      const file = req.file;

      logger.audit('OCR processing started', userId, {
        reqId,
        action: payload.action,
        hasFile: !!file,
        documentType: payload.documentType
      });

      let documentBuffer: Buffer;
      let fileName: string;

      if (file) {
        documentBuffer = file.buffer;
        fileName = file.originalname;
      } else if (payload.documentUrl) {
        // Download from URL
        const response = await fetch(payload.documentUrl);
        documentBuffer = Buffer.from(await response.arrayBuffer());
        fileName = payload.documentUrl.split('/').pop() || 'document';
      } else if (payload.documentData) {
        // Base64 encoded data
        documentBuffer = Buffer.from(payload.documentData, 'base64');
        fileName = 'uploaded_document';
      } else {
        return res.status(400).json({
          reqId,
          status: 'error',
          error: {
            type: 'functional',
            code: 'NO_DOCUMENT',
            message: 'No document provided for OCR processing',
            retryable: false
          }
        });
      }

      // Upload to storage first
      const storageResult = await storageClient.uploadFinancialDocument(
        fileName,
        documentBuffer,
        {
          userId,
          documentType: payload.documentType || 'document',
          uploadedAt: new Date().toISOString()
        }
      );

      // Process OCR
      const result = await ocrProcessor.processDocument(envelope, documentBuffer, fileName);

      // Add storage information to result
      if (result.status === 'success' && result.data) {
        result.data.storageKey = storageResult.key;
        result.data.documentUrl = storageResult.url;
      }

      logger.audit('OCR processing completed', userId, {
        reqId,
        status: result.status,
        storageKey: storageResult.key,
        durationMs: result.audit?.durationMs
      });

      res.json(result);

    } catch (error) {
      logger.error('OCR processing failed', {
        error: error.message,
        reqId: req.body?.reqId
      });

      res.status(500).json({
        reqId: req.body?.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'OCR_ERROR',
          message: 'OCR processing failed',
          retryable: true
        }
      });
    }
  });

  // Document extraction endpoint
  router.post('/extract', async (req, res) => {
    try {
      const envelope: Envelope<FinancePayload> = req.body;
      const result = await documentExtractor.extractData(envelope);
      res.json(result);
    } catch (error) {
      logger.error('Document extraction failed', {
        error: error.message,
        reqId: req.body?.reqId
      });

      res.status(500).json({
        reqId: req.body?.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'EXTRACTION_ERROR',
          message: 'Document extraction failed',
          retryable: true
        }
      });
    }
  });

  // Categorization endpoint
  router.post('/categorize', async (req, res) => {
    try {
      const envelope: Envelope<FinancePayload> = req.body;
      const result = await categorizer.categorizeTransaction(envelope);
      res.json(result);
    } catch (error) {
      logger.error('Categorization failed', {
        error: error.message,
        reqId: req.body?.reqId
      });

      res.status(500).json({
        reqId: req.body?.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'CATEGORIZATION_ERROR',
          message: 'Categorization failed',
          retryable: true
        }
      });
    }
  });

  // Report generation endpoint
  router.post('/report', async (req, res) => {
    try {
      const envelope: Envelope<FinancePayload> = req.body;
      const result = await reportGenerator.generateReport(envelope);
      res.json(result);
    } catch (error) {
      logger.error('Report generation failed', {
        error: error.message,
        reqId: req.body?.reqId
      });

      res.status(500).json({
        reqId: req.body?.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'REPORT_ERROR',
          message: 'Report generation failed',
          retryable: true
        }
      });
    }
  });

  // Deduplication endpoint
  router.post('/deduplicate', async (req, res) => {
    try {
      const envelope: Envelope<FinancePayload> = req.body;
      const result = await deduplicator.deduplicateRecords(envelope);
      res.json(result);
    } catch (error) {
      logger.error('Deduplication failed', {
        error: error.message,
        reqId: req.body?.reqId
      });

      res.status(500).json({
        reqId: req.body?.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'DEDUPLICATION_ERROR',
          message: 'Deduplication failed',
          retryable: true
        }
      });
    }
  });

  // Main processing endpoint (handles all finance actions)
  router.post('/process', async (req, res) => {
    try {
      const envelope: Envelope<FinancePayload> = req.body;
      const { reqId, payload } = envelope;

      let result: ModuleResult<any>;

      switch (payload.action) {
        case 'ocr':
        case 'extract':
          // For OCR/extract without file upload, delegate to appropriate handler
          result = await documentExtractor.extractData(envelope);
          break;
        case 'categorize':
          result = await categorizer.categorizeTransaction(envelope);
          break;
        case 'report':
          result = await reportGenerator.generateReport(envelope);
          break;
        case 'deduplicate':
          result = await deduplicator.deduplicateRecords(envelope);
          break;
        default:
          result = {
            reqId,
            status: 'error',
            error: {
              type: 'functional',
              code: 'INVALID_ACTION',
              message: `Unknown action: ${payload.action}`,
              retryable: false
            }
          };
      }

      res.json(result);

    } catch (error) {
      logger.error('Finance processing failed', {
        error: error.message,
        reqId: req.body?.reqId
      });

      res.status(500).json({
        reqId: req.body?.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'PROCESSING_ERROR',
          message: 'Finance processing failed',
          retryable: true
        }
      });
    }
  });

  return router;
}