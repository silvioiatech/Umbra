import axios from 'axios';
import { Envelope, UmbraPayload, ModuleResult, SERVICES, API_ENDPOINTS } from '@umbra/shared';
import { RetryUtils } from '@umbra/shared';
import Logger from '@umbra/shared/src/utils/logger';

export class ModuleRouter {
  private logger: Logger;
  private retryConfig: any;

  constructor() {
    this.logger = new Logger('ModuleRouter');
    this.retryConfig = RetryUtils.createRetryConfig('api');
  }

  async routeToModule(envelope: Envelope<UmbraPayload>): Promise<ModuleResult<any>> {
    const { reqId, payload } = envelope;
    const targetModule = payload.targetModule;

    if (!targetModule || targetModule === 'umbra') {
      return {
        reqId,
        status: 'error',
        error: {
          type: 'functional',
          code: 'NO_TARGET_MODULE',
          message: 'No target module specified or routing to self',
          retryable: false
        }
      };
    }

    const startTime = Date.now();

    try {
      this.logger.debug('Routing envelope to module', {
        reqId,
        targetModule,
        action: payload.action
      });

      const result = await this.sendToModule(targetModule, envelope);
      const durationMs = Date.now() - startTime;

      this.logger.audit('Module routing completed', envelope.userId, {
        reqId,
        targetModule,
        status: result.status,
        durationMs
      });

      return result;

    } catch (error) {
      const durationMs = Date.now() - startTime;
      
      this.logger.error('Module routing failed', {
        reqId,
        targetModule,
        error: error.message
      });

      return {
        reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'ROUTING_ERROR',
          message: `Failed to route to module: ${targetModule}`,
          retryable: true
        },
        audit: {
          module: 'umbra-router',
          durationMs
        }
      };
    }
  }

  private async sendToModule(moduleName: string, envelope: Envelope<any>): Promise<ModuleResult<any>> {
    const service = SERVICES[moduleName];
    
    if (!service) {
      throw new Error(`Unknown module: ${moduleName}`);
    }

    // Build the target URL
    const baseUrl = this.getModuleBaseUrl(moduleName);
    const endpoint = this.getModuleEndpoint(moduleName, envelope.payload.action);
    const url = `${baseUrl}${endpoint}`;

    return RetryUtils.retry(async () => {
      const response = await axios.post(url, envelope, {
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': this.getModuleApiKey(moduleName),
          'X-Service-Name': 'umbra'
        },
        timeout: 30000
      });

      return response.data;
    }, this.retryConfig);
  }

  private getModuleBaseUrl(moduleName: string): string {
    // In development, use localhost
    if (process.env.NODE_ENV === 'development') {
      const port = SERVICES[moduleName].port;
      return `http://localhost:${port}`;
    }

    // In production, use Railway internal URLs or configured URLs
    const envKey = `${moduleName.toUpperCase()}_URL`;
    const configuredUrl = process.env[envKey];
    
    if (configuredUrl) {
      return configuredUrl;
    }

    // Fallback to Railway internal service naming
    return `http://${moduleName}:${SERVICES[moduleName].port}`;
  }

  private getModuleEndpoint(moduleName: string, action: string): string {
    const endpoints = API_ENDPOINTS[moduleName as keyof typeof API_ENDPOINTS];
    
    if (!endpoints) {
      return '/api/v1/process'; // Default endpoint
    }

    // Map actions to specific endpoints
    switch (moduleName) {
      case 'finance':
        if (action === 'ocr' || action === 'extract') return endpoints.ocr;
        if (action === 'report') return endpoints.report;
        return endpoints.extract;
        
      case 'concierge':
        if (action === 'monitor') return endpoints.monitor;
        if (action === 'validate') return endpoints.validate;
        return endpoints.execute;
        
      case 'business':
        if (action === 'manage_client') return endpoints.clients;
        return endpoints.delegate;
        
      case 'production':
        if (action === 'deploy') return endpoints.deploy;
        return endpoints.workflow;
        
      case 'creator':
        if (action.startsWith('generate')) return endpoints.generate;
        return endpoints.media;
        
      case 'mcp':
        if (action === 'validate') return endpoints.validate;
        return endpoints.lifecycle;
        
      default:
        return '/api/v1/process';
    }
  }

  private getModuleApiKey(moduleName: string): string {
    const envKey = `${moduleName.toUpperCase()}_API_KEY`;
    const apiKey = process.env[envKey];
    
    if (!apiKey) {
      this.logger.warn('Missing API key for module', { moduleName, envKey });
      throw new Error(`Missing API key for module: ${moduleName}`);
    }
    
    return apiKey;
  }

  /**
   * Check if a module is available
   */
  async checkModuleHealth(moduleName: string): Promise<boolean> {
    try {
      const baseUrl = this.getModuleBaseUrl(moduleName);
      const healthEndpoint = SERVICES[moduleName].health;
      
      const response = await axios.get(`${baseUrl}${healthEndpoint}`, {
        timeout: 5000,
        headers: {
          'X-Service-Name': 'umbra'
        }
      });

      return response.status === 200;
    } catch (error) {
      this.logger.warn('Module health check failed', {
        moduleName,
        error: error.message
      });
      return false;
    }
  }

  /**
   * Get available modules and their status
   */
  async getModuleStatus(): Promise<Record<string, { available: boolean; latency?: number }>> {
    const status: Record<string, { available: boolean; latency?: number }> = {};

    const checks = Object.keys(SERVICES).map(async (moduleName) => {
      if (moduleName === 'umbra') return; // Skip self

      const startTime = Date.now();
      const available = await this.checkModuleHealth(moduleName);
      const latency = available ? Date.now() - startTime : undefined;

      status[moduleName] = { available, latency };
    });

    await Promise.all(checks);
    return status;
  }

  /**
   * Route with fallback logic
   */
  async routeWithFallback(envelope: Envelope<UmbraPayload>): Promise<ModuleResult<any>> {
    const { reqId, payload } = envelope;
    const primaryModule = payload.targetModule;

    if (!primaryModule || primaryModule === 'umbra') {
      return this.routeToModule(envelope);
    }

    // Check if primary module is available
    const isAvailable = await this.checkModuleHealth(primaryModule);
    
    if (!isAvailable) {
      this.logger.warn('Primary module unavailable, checking fallbacks', {
        reqId,
        primaryModule
      });

      // Get fallback module based on intent
      const fallbackModule = this.getFallbackModule(payload.intent || '');
      
      if (fallbackModule && fallbackModule !== primaryModule) {
        const fallbackAvailable = await this.checkModuleHealth(fallbackModule);
        
        if (fallbackAvailable) {
          this.logger.info('Using fallback module', {
            reqId,
            primaryModule,
            fallbackModule
          });

          // Update envelope to use fallback
          const fallbackEnvelope = {
            ...envelope,
            payload: {
              ...payload,
              targetModule: fallbackModule
            }
          };

          return this.routeToModule(fallbackEnvelope);
        }
      }

      // No fallback available
      return {
        reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'MODULE_UNAVAILABLE',
          message: `Module ${primaryModule} is currently unavailable`,
          retryable: true
        }
      };
    }

    // Primary module is available, route normally
    return this.routeToModule(envelope);
  }

  private getFallbackModule(intent: string): string | null {
    // Simple fallback logic - could be made more sophisticated
    const fallbacks: Record<string, string> = {
      'finance_ocr': 'umbra', // Fall back to Umbra for basic text extraction
      'translation': 'umbra', // Umbra can handle simple translation
      'calculation': 'umbra', // Umbra can handle basic math
    };

    return fallbacks[intent] || null;
  }
}