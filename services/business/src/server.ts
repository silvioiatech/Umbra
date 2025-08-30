import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import { config } from 'dotenv';
import { AuthMiddleware, ValidationMiddleware, AuditMiddleware } from '@umbra/shared';
import { Logger } from '@umbra/shared';
import { apiRoutes } from './routes/api';
import { healthRoutes } from './routes/health';

// Load environment variables
config();

class BusinessServer {
  private app: express.Application;
  private logger: Logger;
  private port: number;

  constructor() {
    this.app = express();
    this.logger = new Logger('BusinessServer');
    this.port = parseInt(process.env.PORT || '8082');

    // Setup middleware
    this.setupMiddleware();
    
    // Setup routes
    this.setupRoutes();
    
    // Setup error handling
    this.setupErrorHandling();
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
    this.app.use(AuthMiddleware.rateLimit(100, 60000)); // 100 requests per minute

    // Input sanitization
    this.app.use(ValidationMiddleware.sanitizeInput());

    this.logger.info('Business service middleware setup completed');
  }

  private setupRoutes(): void {
    // Health check routes
    this.app.use('/health', healthRoutes);
    this.app.use('/healthz', healthRoutes);

    // API routes (require service authentication)
    this.app.use('/api/v1',
      AuthMiddleware.validateInternalAuth(),
      ValidationMiddleware.validateEnvelope(),
      ValidationMiddleware.validatePayload('business'),
      AuditMiddleware.logEnvelopeCommunication(),
      apiRoutes()
    );

    // Root route
    this.app.get('/', (req, res) => {
      res.json({
        service: 'Umbra Business Module',
        version: '1.0.0',
        status: 'running',
        capabilities: [
          'Client lifecycle management',
          'n8n container tracking',
          'Workflow task delegation',
          'Inventory management'
        ],
        delegatesTo: ['concierge', 'production'],
        timestamp: new Date().toISOString()
      });
    });

    this.logger.info('Business service routes setup completed');
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

    this.logger.info('Business service error handling setup completed');
  }

  public async start(): Promise<void> {
    try {
      // Initialize service authentication
      const serviceKeys = {
        umbra: process.env.UMBRA_API_KEY!,
        concierge: process.env.CONCIERGE_API_KEY!,
        production: process.env.PRODUCTION_API_KEY!
      };

      AuthMiddleware.initializeServices(serviceKeys);

      // Start server
      this.app.listen(this.port, () => {
        this.logger.info('Business Module started', {
          port: this.port,
          environment: process.env.NODE_ENV || 'development',
          timestamp: new Date().toISOString()
        });
      });

    } catch (error) {
      this.logger.error('Failed to start Business service', { error: (error as Error).message });
      process.exit(1);
    }
  }

  public getApp(): express.Application {
    return this.app;
  }
}

// Start server if this file is run directly
if (require.main === module) {
  const server = new BusinessServer();
  server.start().catch(error => {
    console.error('Failed to start Business server:', error);
    process.exit(1);
  });
}

export default BusinessServer;