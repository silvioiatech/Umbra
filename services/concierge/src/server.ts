import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import { config } from 'dotenv';
import { AuthMiddleware, ValidationMiddleware, AuditMiddleware } from '@umbra/shared';
import { Logger } from '@umbra/shared';
import { apiRoutes } from './routes/api';
import { healthRoutes } from './routes/health';
import { VPSManager } from './vps/vps-manager';
import { SystemMonitor } from './monitoring/system-monitor';

// Load environment variables
config();

class ConciergeServer {
  private app: express.Application;
  private logger: Logger;
  private vpsManager!: VPSManager;
  private systemMonitor!: SystemMonitor;
  private port: number;

  constructor() {
    this.app = express();
    this.logger = new Logger('ConciergeServer');
    this.port = parseInt(process.env.PORT || '9090');

    // Initialize VPS components
    this.initializeVPSComponents();
    
    // Setup middleware
    this.setupMiddleware();
    
    // Setup routes
    this.setupRoutes();
    
    // Setup error handling
    this.setupErrorHandling();
  }

  private initializeVPSComponents(): void {
    try {
      this.vpsManager = new VPSManager({
        host: process.env.VPS_HOST!,
        username: process.env.VPS_USERNAME!,
        privateKey: process.env.VPS_PRIVATE_KEY!,
        port: parseInt(process.env.VPS_PORT || '22')
      });

      this.systemMonitor = new SystemMonitor(this.vpsManager);

      this.logger.info('VPS Concierge components initialized successfully');
    } catch (error) {
      this.logger.error('Failed to initialize VPS components', { error: (error as Error).message });
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
    this.app.use(express.json({ limit: '1mb' }));
    this.app.use(express.urlencoded({ extended: true, limit: '1mb' }));

    // Audit middleware
    this.app.use(AuditMiddleware.generateAuditId());
    this.app.use(AuditMiddleware.logRequest());
    this.app.use(AuditMiddleware.logResponse());
    this.app.use(AuditMiddleware.logCriticalOperation());
    this.app.use(AuditMiddleware.monitorPerformance());

    // Rate limiting (stricter for VPS access)
    this.app.use(AuthMiddleware.rateLimit(50, 60000)); // 50 requests per minute

    // Input sanitization
    this.app.use(ValidationMiddleware.sanitizeInput());

    this.logger.info('Concierge service middleware setup completed');
  }

  private setupRoutes(): void {
    // Health check routes
    this.app.use('/health', healthRoutes);
    this.app.use('/healthz', healthRoutes);

    // API routes (require service authentication + validation for critical ops)
    this.app.use('/api/v1',
      AuthMiddleware.validateInternalAuth(),
      ValidationMiddleware.validateEnvelope(),
      ValidationMiddleware.validatePayload('concierge'),
      AuditMiddleware.logEnvelopeCommunication(),
      AuthMiddleware.validateCriticalOperation(), // Validation gates for dangerous operations
      apiRoutes(this.vpsManager, this.systemMonitor)
    );

    // Root route
    this.app.get('/', (req, res) => {
      res.json({
        service: 'Umbra VPS Concierge',
        version: '1.0.0',
        status: 'running',
        capabilities: [
          'VPS monitoring',
          'Command execution',
          'Container management',
          'System status',
          'Client lifecycle management',
          'Script validation'
        ],
        security: {
          exclusiveVPSAccess: true,
          validationRequired: true,
          auditLogging: true
        },
        timestamp: new Date().toISOString()
      });
    });

    this.logger.info('Concierge service routes setup completed');
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

    this.logger.info('Concierge service error handling setup completed');
  }

  public async start(): Promise<void> {
    try {
      // Initialize service authentication
      const serviceKeys = {
        umbra: process.env.UMBRA_API_KEY!,
        business: process.env.BUSINESS_API_KEY!
      };

      AuthMiddleware.initializeServices(serviceKeys);

      // Start system monitoring
      this.systemMonitor.startMonitoring();

      // Start server
      this.app.listen(this.port, () => {
        this.logger.info('VPS Concierge Service started', {
          port: this.port,
          environment: process.env.NODE_ENV || 'development',
          vpsHost: process.env.VPS_HOST,
          timestamp: new Date().toISOString()
        });
      });

    } catch (error) {
      this.logger.error('Failed to start Concierge service', { error: (error as Error).message });
      process.exit(1);
    }
  }

  public getApp(): express.Application {
    return this.app;
  }
}

// Start server if this file is run directly
if (require.main === module) {
  const server = new ConciergeServer();
  server.start().catch(error => {
    console.error('Failed to start Concierge server:', error);
    process.exit(1);
  });
}

export default ConciergeServer;