import { Request, Response, NextFunction } from 'express';
import { v4 as uuidv4 } from 'uuid';
import Logger from '../utils/logger';
import { CryptoUtils } from '../utils/crypto';

interface AuditRequest extends Request {
  userId?: string;
  serviceName?: string;
  auditId?: string;
  startTime?: number;
}

export class AuditMiddleware {
  private static logger = new Logger('AuditMiddleware');

  /**
   * Generate unique audit ID for request tracking
   */
  static generateAuditId() {
    return (req: AuditRequest, res: Response, next: NextFunction): void => {
      req.auditId = uuidv4();
      req.startTime = Date.now();
      
      this.logger.debug('Audit ID generated', {
        auditId: req.auditId,
        method: req.method,
        url: req.url,
        ip: req.ip
      });

      next();
    };
  }

  /**
   * Log request details
   */
  static logRequest() {
    return (req: AuditRequest, res: Response, next: NextFunction): void => {
      const sanitizedBody = this.sanitizeAuditData(req.body);
      
      this.logger.audit('Request received', req.userId || 'anonymous', {
        auditId: req.auditId,
        method: req.method,
        url: req.url,
        userAgent: req.headers['user-agent'],
        ip: req.ip,
        serviceName: req.serviceName,
        body: sanitizedBody,
        query: req.query,
        headers: this.sanitizeHeaders(req.headers)
      });

      next();
    };
  }

  /**
   * Log response details
   */
  static logResponse() {
    return (req: AuditRequest, res: Response, next: NextFunction): void => {
      const originalSend = res.send;
      const originalJson = res.json;

      res.send = function(body: any) {
        const durationMs = Date.now() - (req.startTime || Date.now());
        
        AuditMiddleware.logger.audit('Response sent', req.userId || 'anonymous', {
          auditId: req.auditId,
          statusCode: res.statusCode,
          durationMs,
          method: req.method,
          url: req.url,
          responseSize: Buffer.byteLength(body || ''),
          serviceName: req.serviceName
        });

        return originalSend.call(this, body);
      };

      res.json = function(obj: any) {
        const durationMs = Date.now() - (req.startTime || Date.now());
        const sanitizedResponse = AuditMiddleware.sanitizeAuditData(obj);
        
        AuditMiddleware.logger.audit('JSON response sent', req.userId || 'anonymous', {
          auditId: req.auditId,
          statusCode: res.statusCode,
          durationMs,
          method: req.method,
          url: req.url,
          response: sanitizedResponse,
          serviceName: req.serviceName
        });

        return originalJson.call(this, obj);
      };

      next();
    };
  }

  /**
   * Log envelope communication between services
   */
  static logEnvelopeCommunication() {
    return (req: AuditRequest, res: Response, next: NextFunction): void => {
      if (req.body && req.body.reqId) {
        const envelope = req.body;
        
        this.logger.audit('Envelope received', envelope.userId, {
          reqId: envelope.reqId,
          auditId: req.auditId,
          sourceService: req.serviceName || 'external',
          targetService: process.env.SERVICE_NAME || 'unknown',
          action: envelope.payload?.action,
          lang: envelope.lang,
          priority: envelope.meta?.priority,
          retryCount: envelope.meta?.retryCount
        });
      }

      next();
    };
  }

  /**
   * Log critical operations with enhanced detail
   */
  static logCriticalOperation() {
    return (req: AuditRequest, res: Response, next: NextFunction): void => {
      const action = req.body?.payload?.action || req.body?.action;
      const criticalActions = [
        'delete',
        'restart',
        'promote_to_prod',
        'remove_container',
        'execute_script',
        'client_delete'
      ];

      if (criticalActions.includes(action)) {
        const validationToken = req.headers['x-validation-token'] as string;
        
        this.logger.audit('Critical operation attempted', req.userId || 'anonymous', {
          auditId: req.auditId,
          action,
          hasValidationToken: !!validationToken,
          validationTokenHash: validationToken ? CryptoUtils.hashForLogging(validationToken) : undefined,
          ip: req.ip,
          userAgent: req.headers['user-agent'],
          serviceName: req.serviceName,
          payload: this.sanitizeAuditData(req.body?.payload),
          severity: 'CRITICAL'
        });
      }

      next();
    };
  }

  /**
   * Log errors with context
   */
  static logError() {
    return (error: Error, req: AuditRequest, res: Response, next: NextFunction): void => {
      const durationMs = Date.now() - (req.startTime || Date.now());
      
      this.logger.audit('Request error', req.userId || 'anonymous', {
        auditId: req.auditId,
        error: {
          name: error.name,
          message: error.message,
          stack: error.stack
        },
        method: req.method,
        url: req.url,
        statusCode: res.statusCode || 500,
        durationMs,
        serviceName: req.serviceName,
        severity: 'ERROR'
      });

      next(error);
    };
  }

  /**
   * Log API usage and costs
   */
  static logApiUsage(provider: string, operation: string, cost?: number, tokens?: number) {
    return (req: AuditRequest, res: Response, next: NextFunction): void => {
      this.logger.audit('API usage', req.userId || 'anonymous', {
        auditId: req.auditId,
        provider,
        operation,
        cost,
        tokens,
        timestamp: new Date().toISOString(),
        serviceName: req.serviceName
      });

      next();
    };
  }

  /**
   * Log data processing activities
   */
  static logDataProcessing(dataType: string, operation: string, recordCount?: number) {
    return (req: AuditRequest, res: Response, next: NextFunction): void => {
      this.logger.audit('Data processing', req.userId || 'anonymous', {
        auditId: req.auditId,
        dataType,
        operation,
        recordCount,
        timestamp: new Date().toISOString(),
        serviceName: req.serviceName,
        compliance: {
          piiMinimized: true,
          dataRetention: this.getDataRetentionPolicy(dataType),
          purpose: operation
        }
      });

      next();
    };
  }

  /**
   * Log file operations
   */
  static logFileOperation(operation: 'upload' | 'download' | 'delete', filename?: string, size?: number) {
    return (req: AuditRequest, res: Response, next: NextFunction): void => {
      this.logger.audit('File operation', req.userId || 'anonymous', {
        auditId: req.auditId,
        operation,
        filename: filename ? CryptoUtils.hashForLogging(filename) : undefined,
        size,
        timestamp: new Date().toISOString(),
        serviceName: req.serviceName,
        ip: req.ip
      });

      next();
    };
  }

  /**
   * Generate compliance report data
   */
  static generateComplianceReport(startDate: Date, endDate: Date): Promise<any> {
    // This would typically query a database or log aggregation system
    // For now, return a basic structure
    return Promise.resolve({
      period: {
        start: startDate.toISOString(),
        end: endDate.toISOString()
      },
      summary: {
        totalRequests: 0,
        criticalOperations: 0,
        errors: 0,
        dataProcessingActivities: 0
      },
      compliance: {
        piiMinimization: true,
        auditTrailComplete: true,
        retentionPolicyCompliance: true
      }
    });
  }

  /**
   * Sanitize data for audit logging (remove PII)
   */
  private static sanitizeAuditData(data: any): any {
    if (!data) return data;

    // Use existing PII minimization from CryptoUtils
    return CryptoUtils.minimizePII(data);
  }

  /**
   * Sanitize headers for audit logging
   */
  private static sanitizeHeaders(headers: any): any {
    const sanitized = { ...headers };
    
    // Remove sensitive headers
    delete sanitized.authorization;
    delete sanitized['x-api-key'];
    delete sanitized['x-validation-token'];
    delete sanitized.cookie;
    
    return sanitized;
  }

  /**
   * Get data retention policy for different data types
   */
  private static getDataRetentionPolicy(dataType: string): string {
    const policies: Record<string, string> = {
      'financial': '90 days',
      'media': '30 days',
      'temp': '7 days',
      'logs': '365 days',
      'audit': '7 years',
      'default': '30 days'
    };

    return policies[dataType] || policies.default;
  }

  /**
   * Health check audit logging
   */
  static logHealthCheck() {
    return (req: Request, res: Response, next: NextFunction): void => {
      if (req.url === '/health' || req.url === '/healthz') {
        // Don't log health checks as they're frequent and not user-initiated
        next();
        return;
      }

      next();
    };
  }

  /**
   * Performance monitoring
   */
  static monitorPerformance() {
    return (req: AuditRequest, res: Response, next: NextFunction): void => {
      const startMemory = process.memoryUsage();
      const startCpu = process.cpuUsage();

      res.on('finish', () => {
        const durationMs = Date.now() - (req.startTime || Date.now());
        const endMemory = process.memoryUsage();
        const endCpu = process.cpuUsage(startCpu);

        if (durationMs > 5000) { // Log slow requests (>5s)
          this.logger.audit('Slow request detected', req.userId || 'anonymous', {
            auditId: req.auditId,
            durationMs,
            method: req.method,
            url: req.url,
            memoryDelta: {
              heapUsed: endMemory.heapUsed - startMemory.heapUsed,
              external: endMemory.external - startMemory.external
            },
            cpuUsage: {
              user: endCpu.user,
              system: endCpu.system
            },
            serviceName: req.serviceName,
            severity: 'PERFORMANCE'
          });
        }
      });

      next();
    };
  }
}