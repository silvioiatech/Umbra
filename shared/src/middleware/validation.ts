import { Request, Response, NextFunction } from 'express';
import { Envelope } from '../types/envelopes';
import { ModulePayload } from '../types/modules';
import Logger from '../utils/logger';

interface ValidationRequest extends Request {
  body: Envelope<ModulePayload>;
}

export class ValidationMiddleware {
  private static logger = new Logger('ValidationMiddleware');

  /**
   * Validate envelope structure
   */
  static validateEnvelope() {
    return (req: ValidationRequest, res: Response, next: NextFunction): void => {
      const envelope = req.body;

      if (!envelope) {
        res.status(400).json({
          error: 'Request body is required'
        });
        return;
      }

      const errors: string[] = [];

      // Validate required fields
      if (!envelope.reqId || typeof envelope.reqId !== 'string') {
        errors.push('reqId is required and must be a string');
      }

      if (!envelope.userId || typeof envelope.userId !== 'string') {
        errors.push('userId is required and must be a string');
      }

      if (!envelope.lang || !['EN', 'FR', 'PT'].includes(envelope.lang)) {
        errors.push('lang is required and must be one of: EN, FR, PT');
      }

      if (!envelope.timestamp || typeof envelope.timestamp !== 'string') {
        errors.push('timestamp is required and must be a string');
      }

      if (!envelope.payload || typeof envelope.payload !== 'object') {
        errors.push('payload is required and must be an object');
      }

      // Validate timestamp format
      if (envelope.timestamp) {
        try {
          const date = new Date(envelope.timestamp);
          if (isNaN(date.getTime())) {
            errors.push('timestamp must be a valid ISO date string');
          }
        } catch (error) {
          errors.push('timestamp must be a valid ISO date string');
        }
      }

      // Validate UUID format for reqId
      if (envelope.reqId) {
        const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
        if (!uuidRegex.test(envelope.reqId)) {
          errors.push('reqId must be a valid UUID');
        }
      }

      // Validate meta object if present
      if (envelope.meta) {
        if (envelope.meta.costCapUsd && typeof envelope.meta.costCapUsd !== 'number') {
          errors.push('meta.costCapUsd must be a number');
        }

        if (envelope.meta.priority && !['normal', 'urgent'].includes(envelope.meta.priority)) {
          errors.push('meta.priority must be either "normal" or "urgent"');
        }

        if (envelope.meta.retryCount && typeof envelope.meta.retryCount !== 'number') {
          errors.push('meta.retryCount must be a number');
        }
      }

      if (errors.length > 0) {
        this.logger.warn('Envelope validation failed', {
          errors,
          reqId: envelope.reqId,
          userId: envelope.userId
        });

        res.status(400).json({
          error: 'Validation failed',
          details: errors
        });
        return;
      }

      this.logger.debug('Envelope validation passed', {
        reqId: envelope.reqId,
        userId: envelope.userId,
        action: envelope.payload?.action
      });

      next();
    };
  }

  /**
   * Validate payload based on service type
   */
  static validatePayload(serviceName: string) {
    return (req: ValidationRequest, res: Response, next: NextFunction): void => {
      const payload = req.body.payload;
      const errors: string[] = [];

      if (!payload.action || typeof payload.action !== 'string') {
        errors.push('payload.action is required and must be a string');
      }

      // Service-specific validation
      switch (serviceName) {
        case 'finance':
          this.validateFinancePayload(payload, errors);
          break;
        case 'concierge':
          this.validateConciergePayload(payload, errors);
          break;
        case 'business':
          this.validateBusinessPayload(payload, errors);
          break;
        case 'production':
          this.validateProductionPayload(payload, errors);
          break;
        case 'creator':
          this.validateCreatorPayload(payload, errors);
          break;
        case 'umbra':
          this.validateUmbraPayload(payload, errors);
          break;
      }

      if (errors.length > 0) {
        this.logger.warn('Payload validation failed', {
          service: serviceName,
          action: payload.action,
          errors,
          reqId: req.body.reqId
        });

        res.status(400).json({
          error: 'Payload validation failed',
          service: serviceName,
          details: errors
        });
        return;
      }

      this.logger.debug('Payload validation passed', {
        service: serviceName,
        action: payload.action,
        reqId: req.body.reqId
      });

      next();
    };
  }

  private static validateFinancePayload(payload: any, errors: string[]): void {
    const validActions = ['ocr', 'extract', 'categorize', 'report', 'deduplicate'];
    
    if (!validActions.includes(payload.action)) {
      errors.push(`Invalid action for finance service: ${payload.action}`);
    }

    if (payload.action === 'ocr' || payload.action === 'extract') {
      if (!payload.documentUrl || typeof payload.documentUrl !== 'string') {
        errors.push('documentUrl is required for OCR/extract actions');
      }

      if (payload.documentType && !['invoice', 'receipt', 'statement', 'payroll'].includes(payload.documentType)) {
        errors.push('documentType must be one of: invoice, receipt, statement, payroll');
      }
    }

    if (payload.action === 'report') {
      if (payload.reportType && !['budget', 'vat', 'tax'].includes(payload.reportType)) {
        errors.push('reportType must be one of: budget, vat, tax');
      }

      if (payload.dateRange) {
        if (!payload.dateRange.start || !payload.dateRange.end) {
          errors.push('dateRange must have start and end dates');
        }
      }
    }
  }

  private static validateConciergePayload(payload: any, errors: string[]): void {
    const validActions = ['monitor', 'execute', 'validate', 'client_management'];

    if (!validActions.includes(payload.action)) {
      errors.push(`Invalid action for concierge service: ${payload.action}`);
    }

    if (payload.action === 'execute') {
      if (!payload.command && !payload.script) {
        errors.push('Either command or script is required for execute action');
      }
    }

    if (payload.action === 'client_management') {
      if (!payload.clientAction || !['create', 'delete', 'list'].includes(payload.clientAction)) {
        errors.push('clientAction must be one of: create, delete, list');
      }

      if (payload.clientAction === 'create') {
        if (!payload.clientName || typeof payload.clientName !== 'string') {
          errors.push('clientName is required for create action');
        }
        if (!payload.clientPort || typeof payload.clientPort !== 'number') {
          errors.push('clientPort is required for create action');
        }
      }

      if (payload.clientAction === 'delete') {
        if (!payload.clientName || typeof payload.clientName !== 'string') {
          errors.push('clientName is required for delete action');
        }
      }
    }
  }

  private static validateBusinessPayload(payload: any, errors: string[]): void {
    const validActions = ['manage_client', 'delegate_workflow', 'track_inventory'];

    if (!validActions.includes(payload.action)) {
      errors.push(`Invalid action for business service: ${payload.action}`);
    }

    if (payload.action === 'manage_client') {
      if (!payload.operationType || !['create', 'update', 'delete', 'list'].includes(payload.operationType)) {
        errors.push('operationType must be one of: create, update, delete, list');
      }
    }
  }

  private static validateProductionPayload(payload: any, errors: string[]): void {
    const validActions = ['create_workflow', 'validate', 'deploy', 'rollback'];

    if (!validActions.includes(payload.action)) {
      errors.push(`Invalid action for production service: ${payload.action}`);
    }

    if (payload.action === 'create_workflow') {
      if (!payload.nlDescription || typeof payload.nlDescription !== 'string') {
        errors.push('nlDescription is required for create_workflow action');
      }
    }

    if (payload.action === 'deploy' || payload.action === 'rollback') {
      if (!payload.workflowId || typeof payload.workflowId !== 'string') {
        errors.push('workflowId is required for deploy/rollback actions');
      }
    }
  }

  private static validateCreatorPayload(payload: any, errors: string[]): void {
    const validActions = ['generate_text', 'generate_image', 'generate_video', 'generate_audio', 'edit_video'];

    if (!validActions.includes(payload.action)) {
      errors.push(`Invalid action for creator service: ${payload.action}`);
    }

    if (!payload.prompt || typeof payload.prompt !== 'string') {
      errors.push('prompt is required for creator actions');
    }

    if (payload.provider && !['openrouter', 'runway', 'shotstack', 'elevenlabs'].includes(payload.provider)) {
      errors.push('provider must be one of: openrouter, runway, shotstack, elevenlabs');
    }
  }


  private static validateUmbraPayload(payload: any, errors: string[]): void {
    const validActions = ['classify', 'route', 'execute', 'clarify'];

    if (!validActions.includes(payload.action)) {
      errors.push(`Invalid action for umbra service: ${payload.action}`);
    }

    if (payload.action === 'classify' || payload.action === 'route') {
      if (!payload.message || typeof payload.message !== 'string') {
        errors.push('message is required for classify/route actions');
      }
    }
  }

  /**
   * Validate file upload constraints
   */
  static validateFileUpload(maxSizeMB: number = 50, allowedMimeTypes: string[] = []) {
    return (req: Request, res: Response, next: NextFunction): void => {
      const file = req.file;
      
      if (!file) {
        next();
        return;
      }

      const errors: string[] = [];

      // Check file size
      const maxSizeBytes = maxSizeMB * 1024 * 1024;
      if (file.size > maxSizeBytes) {
        errors.push(`File size exceeds maximum allowed size of ${maxSizeMB}MB`);
      }

      // Check MIME type if specified
      if (allowedMimeTypes.length > 0 && !allowedMimeTypes.includes(file.mimetype)) {
        errors.push(`File type not allowed. Allowed types: ${allowedMimeTypes.join(', ')}`);
      }

      if (errors.length > 0) {
        this.logger.warn('File upload validation failed', {
          filename: file.originalname,
          size: file.size,
          mimetype: file.mimetype,
          errors
        });

        res.status(400).json({
          error: 'File validation failed',
          details: errors
        });
        return;
      }

      this.logger.debug('File upload validation passed', {
        filename: file.originalname,
        size: file.size,
        mimetype: file.mimetype
      });

      next();
    };
  }

  /**
   * Sanitize input to prevent injection attacks
   */
  static sanitizeInput() {
    return (req: Request, res: Response, next: NextFunction): void => {
      // Basic sanitization - remove potentially dangerous patterns
      const sanitizeString = (str: string): string => {
        return str
          .replace(/[<>]/g, '') // Remove angle brackets
          .replace(/javascript:/gi, '') // Remove javascript: protocol
          .replace(/data:/gi, '') // Remove data: protocol
          .trim();
      };

      const sanitizeObject = (obj: any): any => {
        if (typeof obj === 'string') {
          return sanitizeString(obj);
        }
        
        if (Array.isArray(obj)) {
          return obj.map(sanitizeObject);
        }
        
        if (obj && typeof obj === 'object') {
          const sanitized: any = {};
          for (const [key, value] of Object.entries(obj)) {
            sanitized[key] = sanitizeObject(value);
          }
          return sanitized;
        }
        
        return obj;
      };

      if (req.body) {
        req.body = sanitizeObject(req.body);
      }

      if (req.query) {
        req.query = sanitizeObject(req.query);
      }

      next();
    };
  }
}