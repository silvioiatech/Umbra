// Service contract definitions for inter-module communication
export interface ServiceContract {
  name: string;
  port: number;
  health: string;
  version: string;
}

// Railway service configuration
export const SERVICES: Record<string, ServiceContract> = {
  umbra: {
    name: 'umbra',
    port: 8080,
    health: '/health',
    version: '1.0.0'
  },
  finance: {
    name: 'finance', 
    port: 8081,
    health: '/health',
    version: '1.0.0'
  },
  business: {
    name: 'business',
    port: 8082, 
    health: '/health',
    version: '1.0.0'
  },
  production: {
    name: 'production',
    port: 8083,
    health: '/health', 
    version: '1.0.0'
  },
  creator: {
    name: 'creator',
    port: 8084,
    health: '/health',
    version: '1.0.0'
  },
  concierge: {
    name: 'concierge',
    port: 9090,
    health: '/health',
    version: '1.0.0'
  }
};

// API endpoints for each service
export const API_ENDPOINTS = {
  umbra: {
    route: '/api/v1/route',
    execute: '/api/v1/execute',
    classify: '/api/v1/classify'
  },
  finance: {
    ocr: '/api/v1/ocr',
    extract: '/api/v1/extract', 
    report: '/api/v1/report'
  },
  concierge: {
    monitor: '/api/v1/monitor',
    execute: '/api/v1/execute',
    validate: '/api/v1/validate'
  },
  business: {
    clients: '/api/v1/clients',
    delegate: '/api/v1/delegate'
  },
  production: {
    workflow: '/api/v1/workflow',
    deploy: '/api/v1/deploy'
  },
  creator: {
    generate: '/api/v1/generate',
    media: '/api/v1/media'
  }
};

// Environment configuration interface
export interface EnvironmentConfig {
  nodeEnv: 'development' | 'production' | 'test';
  logLevel: 'error' | 'warn' | 'info' | 'debug';
  port: number;
  serviceName: string;
}

// External API provider configurations
export interface ProviderConfig {
  openrouter: {
    apiKey: string;
    baseUrl: string;
  };
  runway: {
    apiKey: string;
    baseUrl: string;
  };
  shotstack: {
    apiKey: string;
    baseUrl: string;
  };
  elevenlabs: {
    apiKey: string;
    baseUrl: string;
  };
  telegram: {
    botToken: string;
    webhookUrl?: string;
  };
  storage: {
    endpoint: string;
    accessKey: string;
    secretKey: string;
    bucket: string;
    region: string;
  };
  n8n: {
    apiKey: string;
    baseUrl: string;
  };
}