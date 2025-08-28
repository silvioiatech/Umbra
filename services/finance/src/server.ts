import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import multer from 'multer';
import { config } from 'dotenv';
import { OpenRouterClient, StorageClient } from '@umbra/shared';
import { AuthMiddleware, ValidationMiddleware, AuditMiddleware } from '@umbra/shared';
import Logger from '@umbra/shared/src/utils/logger';
import { apiRoutes } from './routes/api';
import { healthRoutes } from './routes/health';

// Load environment variables
config();

class FinanceServer {
  private app: express.Application;
  private logger: Logger;
  private openRouterClient: OpenRouterClient;
  private storageClient: StorageClient;
  private upload: multer.Multer;
  private port: number;

  constructor() {
    this.app = express();
    this.logger = new Logger('FinanceServer');
    this.port = parseInt(process.env.PORT || '8081');

    // Initialize clients
    this.initializeClients();
    
    // Setup file upload
    this.setupFileUpload();
    
    // Setup middleware
    this.setupMiddleware();
    
    // Setup routes
    this.setupRoutes();
    
    // Setup error handling
    this.setupErrorHandling();
  }

  private initializeClients(): void {
    try {
      this.openRouterClient = new OpenRouterClient({
        apiKey: process.env.OPENROUTER_API_KEY!,
        baseUrl: process.env.OPENROUTER_BASE_URL || 'https://openrouter.ai/api/v1'
      });

      this.storageClient = new StorageClient({
        endpoint: process.env.STORAGE_ENDPOINT!,
        accessKey: process.env.STORAGE_ACCESS_KEY!,
        secretKey: process.env.STORAGE_SECRET_KEY!,
        bucket: process.env.STORAGE_BUCKET!,
        region: process.env.STORAGE_REGION || 'us-east-1'
      });

      this.logger.info('Finance service clients initialized successfully');
    } catch (error) {
      this.logger.error('Failed to initialize clients', { error: error.message });
      throw error;
    }
  }

  private setupFileUpload(): void {
    // Configure multer for file uploads
    this.upload = multer({
      limits: {
        fileSize: 50 * 1024 * 1024, // 50MB limit
        files: 1
      },
      fileFilter: (req, file, cb) => {
        // Allowed file types for financial documents
        const allowedTypes = [
          'application/pdf',
          'image/jpeg',
          'image/jpg', 
          'image/png',
          'image/gif',
          'image/webp',
          'application/vnd.ms-excel',
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ];

        if (allowedTypes.includes(file.mimetype)) {
          cb(null, true);
        } else {
          cb(new Error(`Unsupported file type: ${file.mimetype}`));
        }
      },
      storage: multer.memoryStorage()
    });
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

    this.logger.info('Finance service middleware setup completed');
  }

  private setupRoutes(): void {
    // Health check routes
    this.app.use('/health', healthRoutes);
    this.app.use('/healthz', healthRoutes);

    // API routes (require service authentication)
    this.app.use('/api/v1',
      AuthMiddleware.validateInternalAuth(),
      ValidationMiddleware.validateEnvelope(),
      ValidationMiddleware.validatePayload('finance'),
      AuditMiddleware.logEnvelopeCommunication(),
      AuditMiddleware.logDataProcessing('financial', 'processing'),
      apiRoutes(this.openRouterClient, this.storageClient, this.upload)
    );

    // Root route
    this.app.get('/', (req, res) => {
      res.json({
        service: 'Umbra Finance Service',
        version: '1.0.0',
        status: 'running',
        capabilities: [
          'OCR processing',
          'Document extraction',
          'Financial categorization',
          'Report generation',
          'Data deduplication',
          'PII minimization'
        ],
        timestamp: new Date().toISOString()
      });
    });

    this.logger.info('Finance service routes setup completed');
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

    this.logger.info('Finance service error handling setup completed');
  }

  public async start(): Promise<void> {
    try {
      // Initialize service authentication
      const serviceKeys = {
        umbra: process.env.UMBRA_API_KEY!,
        business: process.env.BUSINESS_API_KEY!,
        production: process.env.PRODUCTION_API_KEY!
      };

      AuthMiddleware.initializeServices(serviceKeys);

      // Start server
      this.app.listen(this.port, () => {
        this.logger.info('Finance Service started', {
          port: this.port,
          environment: process.env.NODE_ENV || 'development',
          timestamp: new Date().toISOString()
        });
      });

    } catch (error) {
      this.logger.error('Failed to start Finance service', { error: error.message });
      process.exit(1);
    }
  }

  public getApp(): express.Application {
    return this.app;
  }
}

// Start server if this file is run directly
if (require.main === module) {
  const server = new FinanceServer();
  server.start().catch(error => {
    console.error('Failed to start Finance server:', error);
    process.exit(1);
  });
}

export default FinanceServer;