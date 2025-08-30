import { Router, Request, Response } from 'express';
import { VPSManager } from '../vps/vps-manager';
import { SystemMonitor } from '../monitoring/system-monitor';
import { ModuleRequest, ModuleResult } from '@umbra/shared';
import { ConciergeResult } from '@umbra/shared';
import { Logger } from '@umbra/shared';
import { RetryUtils } from '@umbra/shared';

const logger = new Logger('ConciergeAPI');

export function apiRoutes(vpsManager: VPSManager, systemMonitor: SystemMonitor) {
  const router = Router();

  /**
   * System monitoring endpoint
   */
  router.post('/monitor', async (req: Request, res: Response) => {
    const envelope = req.body as ModuleRequest<any>;
    const startTime = Date.now();

    try {
      logger.info('System monitoring request received', { 
        reqId: envelope.reqId,
        action: envelope.payload.action 
      });

      const systemStatus = await systemMonitor.getSystemStatus();
      
      const result: ModuleResult<ConciergeResult> = {
        reqId: envelope.reqId,
        status: 'success',
        data: {
          systemStatus,
          timestamp: new Date().toISOString()
        },
        audit: {
          module: 'concierge-monitor',
          durationMs: Date.now() - startTime
        }
      };

      res.status(200).json(result);
    } catch (error) {
      logger.error('System monitoring failed', { 
        reqId: envelope.reqId, 
        error: (error as Error).message 
      });

      const errorResult: ModuleResult<ConciergeResult> = {
        reqId: envelope.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'MONITOR_FAILED',
          message: 'System monitoring failed',
          retryable: true
        },
        audit: {
          module: 'concierge-monitor',
          durationMs: Date.now() - startTime
        }
      };

      res.status(500).json(errorResult);
    }
  });

  /**
   * Command execution endpoint - requires validation gate
   */
  router.post('/execute', async (req: Request, res: Response) => {
    const envelope = req.body as ModuleRequest<any>;
    const startTime = Date.now();

    try {
      logger.info('Command execution request received', { 
        reqId: envelope.reqId,
        command: envelope.payload.command?.substring(0, 50) + '...'
      });

      // Validation gate check - critical operation
      if (!req.headers['x-validation-token']) {
        const errorResult: ModuleResult<ConciergeResult> = {
          reqId: envelope.reqId,
          status: 'error',
          error: {
            type: 'auth',
            code: 'VALIDATION_REQUIRED',
            message: 'Command execution requires validation token',
            retryable: false
          },
          audit: {
            module: 'concierge-execute',
            durationMs: Date.now() - startTime
          }
        };

        return res.status(403).json(errorResult);
      }

      // Execute command with retry logic
      const retryConfig = RetryUtils.createRetryConfig('technical');
      const executionResult = await RetryUtils.retry(
        () => vpsManager.executeCommand(envelope.payload.command, envelope.payload.options),
        retryConfig
      );

      const result: ModuleResult<ConciergeResult> = {
        reqId: envelope.reqId,
        status: 'success',
        data: {
          executionResult,
          timestamp: new Date().toISOString()
        },
        audit: {
          module: 'concierge-execute',
          durationMs: Date.now() - startTime
        }
      };

      res.status(200).json(result);
    } catch (error) {
      logger.error('Command execution failed', { 
        reqId: envelope.reqId, 
        error: (error as Error).message 
      });

      const errorResult: ModuleResult<ConciergeResult> = {
        reqId: envelope.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'EXECUTION_FAILED',
          message: 'Command execution failed',
          retryable: true
        },
        audit: {
          module: 'concierge-execute',
          durationMs: Date.now() - startTime
        }
      };

      res.status(500).json(errorResult);
    }
  });

  /**
   * Container management endpoint
   */
  router.post('/container', async (req: Request, res: Response) => {
    const envelope = req.body as ModuleRequest<any>;
    const startTime = Date.now();

    try {
      logger.info('Container management request received', { 
        reqId: envelope.reqId,
        action: envelope.payload.action,
        container: envelope.payload.containerName 
      });

      let containerResult;
      const { action, containerName, options } = envelope.payload;

      switch (action) {
        case 'status':
          containerResult = await vpsManager.getContainerStatus(containerName);
          break;
        case 'start':
          containerResult = await vpsManager.startContainer(containerName, options);
          break;
        case 'stop':
          containerResult = await vpsManager.stopContainer(containerName);
          break;
        case 'restart':
          containerResult = await vpsManager.restartContainer(containerName);
          break;
        case 'logs':
          containerResult = await vpsManager.getContainerLogs(containerName, options);
          break;
        default:
          throw new Error(`Unsupported container action: ${action}`);
      }

      const result: ModuleResult<ConciergeResult> = {
        reqId: envelope.reqId,
        status: 'success',
        data: {
          containerResult,
          timestamp: new Date().toISOString()
        },
        audit: {
          module: 'concierge-container',
          durationMs: Date.now() - startTime
        }
      };

      res.status(200).json(result);
    } catch (error) {
      logger.error('Container management failed', { 
        reqId: envelope.reqId, 
        error: (error as Error).message 
      });

      const errorResult: ModuleResult<ConciergeResult> = {
        reqId: envelope.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'CONTAINER_FAILED',
          message: 'Container management failed',
          retryable: true
        },
        audit: {
          module: 'concierge-container',
          durationMs: Date.now() - startTime
        }
      };

      res.status(500).json(errorResult);
    }
  });

  /**
   * Script validation endpoint
   */
  router.post('/validate', async (req: Request, res: Response) => {
    const envelope = req.body as ModuleRequest<any>;
    const startTime = Date.now();

    try {
      logger.info('Script validation request received', { 
        reqId: envelope.reqId,
        scriptType: envelope.payload.scriptType 
      });

      const validationResult = await vpsManager.validateScript(
        envelope.payload.script,
        envelope.payload.scriptType,
        envelope.payload.options
      );

      const result: ModuleResult<ConciergeResult> = {
        reqId: envelope.reqId,
        status: 'success',
        data: {
          validationResult,
          timestamp: new Date().toISOString()
        },
        audit: {
          module: 'concierge-validate',
          durationMs: Date.now() - startTime
        }
      };

      res.status(200).json(result);
    } catch (error) {
      logger.error('Script validation failed', { 
        reqId: envelope.reqId, 
        error: (error as Error).message 
      });

      const errorResult: ModuleResult<ConciergeResult> = {
        reqId: envelope.reqId,
        status: 'error',
        error: {
          type: 'functional',
          code: 'VALIDATION_FAILED',
          message: 'Script validation failed',
          retryable: false
        },
        audit: {
          module: 'concierge-validate',
          durationMs: Date.now() - startTime
        }
      };

      res.status(400).json(errorResult);
    }
  });

  return router;
}