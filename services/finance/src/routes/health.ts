import express from 'express';

const router = express.Router();

// Health check endpoint
router.get('/', (req, res) => {
  const health = {
    status: 'healthy',
    service: 'finance-service',
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
    service: 'finance-service',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    memory: process.memoryUsage(),
    cpu: process.cpuUsage(),
    environment: process.env.NODE_ENV || 'development',
    dependencies: {
      openrouter: {
        configured: !!process.env.OPENROUTER_API_KEY
      },
      storage: {
        configured: !!(process.env.STORAGE_ENDPOINT && process.env.STORAGE_ACCESS_KEY)
      }
    },
    features: {
      ocrProcessing: true,
      documentExtraction: true,
      financialCategorization: true,
      reportGeneration: true,
      dataDeduplication: true,
      piiMinimization: true
    },
    supportedFormats: [
      'PDF',
      'JPEG',
      'PNG', 
      'GIF',
      'WebP',
      'Excel (XLS/XLSX)'
    ],
    limits: {
      maxFileSize: '50MB',
      maxFiles: 1,
      retentionPeriod: '90 days'
    }
  };

  res.json(detailed);
});

export { router as healthRoutes };