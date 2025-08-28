import { Router, Request, Response } from 'express';
import Logger from '@umbra/shared/src/utils/logger';

const router = Router();
const logger = new Logger('CreatorHealth');

router.get('/', (req: Request, res: Response) => {
  try {
    const healthStatus = {
      status: 'healthy',
      service: 'creator',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
      memory: process.memoryUsage(),
      version: '1.0.0',
      capabilities: [
        'Multi-provider media generation',
        'Text generation',
        'Image generation', 
        'Video generation',
        'Audio generation'
      ]
    };

    res.status(200).json(healthStatus);
  } catch (error) {
    logger.error('Health check failed', { error: (error as Error).message });
    res.status(500).json({
      status: 'unhealthy',
      service: 'creator',
      timestamp: new Date().toISOString(),
      error: 'Health check failed'
    });
  }
});

router.get('/ready', (req: Request, res: Response) => {
  try {
    const readyStatus = {
      status: 'ready',
      service: 'creator',
      timestamp: new Date().toISOString(),
      providers: {
        openrouter: !!process.env.OPENROUTER_API_KEY,
        runway: !!process.env.RUNWAY_API_KEY,
        shotstack: !!process.env.SHOTSTACK_API_KEY,
        elevenlabs: !!process.env.ELEVENLABS_API_KEY
      }
    };

    res.status(200).json(readyStatus);
  } catch (error) {
    logger.error('Ready check failed', { error: (error as Error).message });
    res.status(503).json({
      status: 'not ready',
      service: 'creator',
      timestamp: new Date().toISOString(),
      error: 'Service not ready'
    });
  }
});

export { router as healthRoutes };