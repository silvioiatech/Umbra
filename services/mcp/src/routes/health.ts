import { Router, Request, Response } from 'express';
import Logger from '@umbra/shared/src/utils/logger';

const router = Router();
const logger = new Logger('MCPHealth');

router.get('/', (req: Request, res: Response) => {
  try {
    const healthStatus = {
      status: 'healthy',
      service: 'mcp',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
      memory: process.memoryUsage(),
      version: '1.0.0',
      capabilities: [
        'n8n API abstraction',
        'Workflow validation',
        'Version management',
        'Environment control'
      ]
    };

    res.status(200).json(healthStatus);
  } catch (error) {
    logger.error('Health check failed', { error: (error as Error).message });
    res.status(500).json({
      status: 'unhealthy',
      service: 'mcp',
      timestamp: new Date().toISOString(),
      error: 'Health check failed'
    });
  }
});

router.get('/ready', (req: Request, res: Response) => {
  try {
    const readyStatus = {
      status: 'ready',
      service: 'mcp',
      timestamp: new Date().toISOString(),
      dependencies: {
        n8n: !!process.env.N8N_API_URL
      }
    };

    res.status(200).json(readyStatus);
  } catch (error) {
    logger.error('Ready check failed', { error: (error as Error).message });
    res.status(503).json({
      status: 'not ready',
      service: 'mcp',
      timestamp: new Date().toISOString(),
      error: 'Service not ready'
    });
  }
});

export { router as healthRoutes };