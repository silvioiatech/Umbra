import express from 'express';

const router = express.Router();

// Health check endpoint
router.get('/', (req, res) => {
  const health = {
    status: 'healthy',
    service: 'umbra-main-agent',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    memory: process.memoryUsage(),
    environment: process.env.NODE_ENV || 'development'
  };

  res.json(health);
});

// Detailed health check
router.get('/detailed', (req, res) => {
  const detailed = {
    status: 'healthy',
    service: 'umbra-main-agent',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    memory: process.memoryUsage(),
    cpu: process.cpuUsage(),
    environment: process.env.NODE_ENV || 'development',
    dependencies: {
      telegram: {
        configured: !!process.env.BOT_TOKEN,
        webhookSet: !!process.env.WEBHOOK_URL
      },
      openrouter: {
        configured: !!process.env.OPENROUTER_API_KEY
      },
      storage: {
        configured: !!(process.env.STORAGE_ENDPOINT && process.env.STORAGE_ACCESS_KEY)
      }
    },
    features: {
      multiLanguage: true,
      intentClassification: true,
      moduleRouting: true,
      validationGates: true
    }
  };

  res.json(detailed);
});

export { router as healthRoutes };