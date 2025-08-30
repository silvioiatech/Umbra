import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import { config } from 'dotenv';
import { TelegramClient, OpenRouterClient } from '@umbra/shared';
import { AuthMiddleware, ValidationMiddleware, AuditMiddleware } from '@umbra/shared';
import { Logger } from '@umbra/shared';
import { telegramRoutes } from './routes/telegram';
import { apiRoutes } from './routes/api';
import { healthRoutes } from './routes/health';

// Load environment variables
config();

class UmbraServer {
  private app: express.Application;
  private logger: Logger;
  private telegramClient: TelegramClient;
  private openRouterClient: OpenRouterClient;
  private port: number;

  constructor() {
    this.app = express();
    this.logger = new Logger('UmbraServer');
    this.port = parseInt(process.env.PORT || '8080');

    // Initialize API clients
    this.initializeClients();
    
    // Setup middleware
    this.setupMiddleware();
    
    // Setup routes
    this.setupRoutes();
    
    // Setup error handling
    this.setupErrorHandling();
  }

  private initializeClients(): void {
    try {
      this.telegramClient = new TelegramClient({
        botToken: process.env.BOT_TOKEN!,
        webhookUrl: process.env.WEBHOOK_URL
      });

      this.openRouterClient = new OpenRouterClient({
        apiKey: process.env.OPENROUTER_API_KEY!,
        baseUrl: process.env.OPENROUTER_BASE_URL || 'https://openrouter.ai/api/v1'
      });

      this.logger.info('API clients initialized successfully');
    } catch (error) {
      this.logger.error('Failed to initialize API clients', { error: error.message });
      throw error;
    }
  }

  private setupMiddleware(): void {
    // Security middleware
    this.app.use(helmet());
    this.app.use(cors({
      origin: process.env.ALLOWED_ORIGINS?.split(',') || ['*'],
      credentials: true
    }));

    // Performance middleware
    this.app.use(compression());

    // Body parsing
    this.app.use(express.json({ limit: '10mb' }));
    this.app.use(express.urlencoded({ extended: true, limit: '10mb' }));

    // Audit middleware
    this.app.use(AuditMiddleware.generateAuditId());
    this.app.use(AuditMiddleware.logRequest());
    this.app.use(AuditMiddleware.logResponse());
    this.app.use(AuditMiddleware.monitorPerformance());

    // Rate limiting
    this.app.use(AuthMiddleware.rateLimit(200, 60000)); // 200 requests per minute

    // Input sanitization
    this.app.use(ValidationMiddleware.sanitizeInput());

    this.logger.info('Middleware setup completed');
  }

  private setupRoutes(): void {
    // Health check routes (no authentication required)
    this.app.use('/health', healthRoutes);
    this.app.use('/healthz', healthRoutes);

    // Telegram webhook routes
    this.app.use('/webhook/telegram', 
      AuthMiddleware.validateTelegramWebhook(process.env.TELEGRAM_WEBHOOK_SECRET),
      telegramRoutes(this.telegramClient, this.openRouterClient)
    );

    // Internal API routes (require service authentication)
    this.app.use('/api/v1',
      AuthMiddleware.validateInternalAuth(),
      ValidationMiddleware.validateEnvelope(),
      ValidationMiddleware.validatePayload('umbra'),
      AuditMiddleware.logEnvelopeCommunication(),
      apiRoutes(this.openRouterClient)
    );

    // Root route
    this.app.get('/', (req, res) => {
      res.json({
        service: 'Umbra Main Agent',
        version: '1.0.0',
        status: 'running',
        timestamp: new Date().toISOString()
      });
    });

    this.logger.info('Routes setup completed');
  }

  private setupErrorHandling(): void {
    // 404 handler
    this.app.use('*', (req, res) => {
      this.logger.warn('Route not found', { 
        method: req.method, 
        url: req.url,
        ip: req.ip 
      });
      
      res.status(404).json({
        error: 'Route not found',
        message: `${req.method} ${req.url} is not a valid endpoint`
      });
    });

    // Global error handler
    this.app.use(AuditMiddleware.logError());
    this.app.use((error: Error, req: express.Request, res: express.Response, next: express.NextFunction) => {
      this.logger.error('Unhandled error', {
        error: error.message,
        stack: error.stack,
        url: req.url,
        method: req.method
      });

      res.status(500).json({
        error: 'Internal server error',
        message: 'An unexpected error occurred'
      });
    });

    this.logger.info('Error handling setup completed');
  }

  public async start(): Promise<void> {
    try {
      // Initialize internal service authentication
      const serviceKeys = {
        finance: process.env.FINANCE_API_KEY!,
        concierge: process.env.CONCIERGE_API_KEY!,
        business: process.env.BUSINESS_API_KEY!,
        production: process.env.PRODUCTION_API_KEY!,
        creator: process.env.CREATOR_API_KEY!
      };

      AuthMiddleware.initializeServices(serviceKeys);

      // Set up Telegram webhook if in production
      if (process.env.NODE_ENV === 'production' && process.env.WEBHOOK_URL) {
        await this.telegramClient.setWebhook(process.env.WEBHOOK_URL + '/webhook/telegram');
        this.logger.info('Telegram webhook configured', { 
          webhookUrl: process.env.WEBHOOK_URL + '/webhook/telegram' 
        });
      }

      // Start server
      this.app.listen(this.port, () => {
        this.logger.info('Umbra Main Agent started', {
          port: this.port,
          environment: process.env.NODE_ENV || 'development',
          timestamp: new Date().toISOString()
        });
      });

    } catch (error) {
      this.logger.error('Failed to start server', { error: error.message });
      process.exit(1);
    }
  }

  public getApp(): express.Application {
    return this.app;
  }
}

// Start server if this file is run directly
if (require.main === module) {
  const server = new UmbraServer();
  server.start().catch(error => {
    console.error('Failed to start Umbra server:', error);
    process.exit(1);
  });
}

export default UmbraServer;