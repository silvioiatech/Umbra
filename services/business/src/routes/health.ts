import { Router, Request, Response } from 'express';
import Logger from '@umbra/shared/src/utils/logger';

const router = Router();
const logger = new Logger('BusinessHealth');

/**
 * Health check endpoint
 */
router.get('/', (req: Request, res: Response) => {
  try {
    const healthStatus = {
      status: 'healthy',
      service: 'business',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
      memory: process.memoryUsage(),
      version: '1.0.0',
      capabilities: [
        'Client lifecycle management',
        'n8n container tracking',
        'Workflow task delegation',
        'Inventory management'
      ]
    };

    res.status(200).json(healthStatus);
  } catch (error) {
    logger.error('Health check failed', { error: (error as Error).message });
    res.status(500).json({
      status: 'unhealthy',
      service: 'business',
      timestamp: new Date().toISOString(),
      error: 'Health check failed'
    });
  }
});

/**
 * Ready check endpoint
 */
router.get('/ready', (req: Request, res: Response) => {
  try {
    const readyStatus = {
      status: 'ready',
      service: 'business',
      timestamp: new Date().toISOString(),
      dependencies: {
        concierge: true, // Would check actual service
        production: true
      }
    };

    res.status(200).json(readyStatus);
  } catch (error) {
    logger.error('Ready check failed', { error: (error as Error).message });
    res.status(503).json({
      status: 'not ready',
      service: 'business',
      timestamp: new Date().toISOString(),
      error: 'Service not ready'
    });
  }
});

export { router as healthRoutes };