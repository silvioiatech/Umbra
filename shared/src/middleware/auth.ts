import { Request, Response, NextFunction } from 'express';
import { CryptoUtils } from '../utils/crypto';
import Logger from '../utils/logger';

interface AuthenticatedRequest extends Request {
  userId?: string;
  serviceName?: string;
  isInternal?: boolean;
}

export class AuthMiddleware {
  private static logger = new Logger('AuthMiddleware');
  private static internalApiKeys: Map<string, string> = new Map();

  /**
   * Initialize internal service API keys
   */
  static initializeServices(serviceKeys: Record<string, string>): void {
    for (const [service, key] of Object.entries(serviceKeys)) {
      this.internalApiKeys.set(key, service);
    }
    this.logger.info('Internal service authentication initialized', {
      services: Object.keys(serviceKeys)
    });
  }

  /**
   * Middleware for validating internal service calls
   */
  static validateInternalAuth() {
    return (req: AuthenticatedRequest, res: Response, next: NextFunction): void => {
      const apiKey = req.headers['x-api-key'] as string;
      const serviceName = req.headers['x-service-name'] as string;

      if (!apiKey) {
        this.logger.warn('Missing API key in internal request', {
          url: req.url,
          ip: req.ip
        });
        res.status(401).json({ error: 'API key required' });
        return;
      }

      const validService = this.internalApiKeys.get(apiKey);
      if (!validService) {
        this.logger.warn('Invalid API key in internal request', {
          url: req.url,
          ip: req.ip,
          providedService: serviceName
        });
        res.status(401).json({ error: 'Invalid API key' });
        return;
      }

      if (serviceName && serviceName !== validService) {
        this.logger.warn('Service name mismatch', {
          expected: validService,
          provided: serviceName,
          ip: req.ip
        });
        res.status(401).json({ error: 'Service name mismatch' });
        return;
      }

      req.serviceName = validService;
      req.isInternal = true;

      this.logger.debug('Internal service authenticated', {
        service: validService,
        url: req.url
      });

      next();
    };
  }

  /**
   * Middleware for Telegram webhook validation
   */
  static validateTelegramWebhook(webhookSecret?: string) {
    return (req: Request, res: Response, next: NextFunction): void => {
      if (!webhookSecret) {
        // If no secret configured, allow all (for development)
        next();
        return;
      }

      const telegramSignature = req.headers['x-telegram-bot-api-secret-token'] as string;
      
      if (!telegramSignature || telegramSignature !== webhookSecret) {
        this.logger.warn('Invalid Telegram webhook signature', {
          ip: req.ip,
          hasSignature: !!telegramSignature
        });
        res.status(401).json({ error: 'Invalid webhook signature' });
        return;
      }

      this.logger.debug('Telegram webhook validated');
      next();
    };
  }

  /**
   * Middleware for user authentication via Telegram user ID
   */
  static validateTelegramUser(allowedUsers?: string[]) {
    return (req: AuthenticatedRequest, res: Response, next: NextFunction): void => {
      const userId = req.body?.message?.from?.id || req.headers['x-user-id'];

      if (!userId) {
        this.logger.warn('Missing user ID in request', { url: req.url });
        res.status(401).json({ error: 'User ID required' });
        return;
      }

      // If allowedUsers is specified, check if user is in the list
      if (allowedUsers && allowedUsers.length > 0) {
        if (!allowedUsers.includes(userId.toString())) {
          this.logger.warn('Unauthorized user access attempt', {
            userId,
            url: req.url,
            ip: req.ip
          });
          res.status(403).json({ error: 'Access denied' });
          return;
        }
      }

      req.userId = userId.toString();

      this.logger.debug('User authenticated', {
        userId: req.userId,
        url: req.url
      });

      next();
    };
  }

  /**
   * Middleware for validating critical operation tokens
   */
  static validateCriticalOperation() {
    return (req: AuthenticatedRequest, res: Response, next: NextFunction): void => {
      const validationToken = req.headers['x-validation-token'] as string;
      const userId = req.userId;
      const action = req.body?.action || req.params?.action;

      // Check if this is a critical operation
      const criticalActions = [
        'delete',
        'restart',
        'promote_to_prod',
        'remove_container',
        'execute_script',
        'client_delete'
      ];

      if (!criticalActions.includes(action)) {
        // Not a critical operation, proceed
        next();
        return;
      }

      if (!validationToken) {
        this.logger.warn('Critical operation attempted without validation token', {
          userId,
          action,
          ip: req.ip
        });
        res.status(403).json({
          error: 'Validation token required for critical operation',
          action,
          requiresValidation: true
        });
        return;
      }

      if (!userId) {
        this.logger.warn('Critical operation attempted without user ID', {
          action,
          ip: req.ip
        });
        res.status(401).json({ error: 'User ID required' });
        return;
      }

      // Verify the validation token
      const isValid = CryptoUtils.verifyValidationToken(validationToken, userId, action);

      if (!isValid) {
        this.logger.warn('Invalid validation token for critical operation', {
          userId,
          action,
          ip: req.ip
        });
        res.status(403).json({
          error: 'Invalid validation token',
          action
        });
        return;
      }

      this.logger.audit('Critical operation validated', userId, {
        action,
        validationToken: CryptoUtils.hashForLogging(validationToken),
        ip: req.ip
      });

      next();
    };
  }

  /**
   * Generate validation token for critical operations
   */
  static generateValidationToken(userId: string, action: string): {
    token: string;
    expiresAt: string;
  } {
    const token = CryptoUtils.generateValidationToken(userId, action);
    const expiresAt = new Date(Date.now() + 5 * 60 * 1000).toISOString(); // 5 minutes

    this.logger.audit('Validation token generated', userId, {
      action,
      tokenHash: CryptoUtils.hashForLogging(token),
      expiresAt
    });

    return { token, expiresAt };
  }

  /**
   * Rate limiting middleware (simple implementation)
   */
  static rateLimit(maxRequests: number = 100, windowMs: number = 60000) {
    const requests = new Map<string, { count: number; resetTime: number }>();

    return (req: Request, res: Response, next: NextFunction): void => {
      const identifier = req.ip || 'unknown';
      const now = Date.now();
      const windowStart = now - windowMs;

      // Clean up old entries
      for (const [key, value] of requests.entries()) {
        if (value.resetTime < windowStart) {
          requests.delete(key);
        }
      }

      const userRequests = requests.get(identifier);
      
      if (!userRequests) {
        requests.set(identifier, { count: 1, resetTime: now + windowMs });
        next();
        return;
      }

      if (userRequests.count >= maxRequests) {
        this.logger.warn('Rate limit exceeded', {
          identifier,
          count: userRequests.count,
          maxRequests
        });
        res.status(429).json({
          error: 'Rate limit exceeded',
          retryAfter: Math.ceil((userRequests.resetTime - now) / 1000)
        });
        return;
      }

      userRequests.count++;
      next();
    };
  }

  /**
   * CORS middleware for cross-origin requests
   */
  static cors(allowedOrigins: string[] = ['*']) {
    return (req: Request, res: Response, next: NextFunction): void => {
      const origin = req.headers.origin as string;

      if (allowedOrigins.includes('*') || allowedOrigins.includes(origin)) {
        res.header('Access-Control-Allow-Origin', origin || '*');
      }

      res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
      res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization, X-API-Key, X-Service-Name, X-User-ID, X-Validation-Token');
      res.header('Access-Control-Allow-Credentials', 'true');

      if (req.method === 'OPTIONS') {
        res.sendStatus(200);
        return;
      }

      next();
    };
  }
}