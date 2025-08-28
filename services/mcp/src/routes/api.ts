import { Router, Request, Response } from 'express';
import { ModuleRequest, ModuleResult } from '@umbra/shared/src/types/envelopes';
import { MCPResult } from '@umbra/shared/src/types/modules';
import Logger from '@umbra/shared/src/utils/logger';
import axios from 'axios';

const logger = new Logger('MCPAPI');

export function apiRoutes() {
  const router = Router();

  /**
   * Workflow validation and dry-run endpoint
   */
  router.post('/validate', async (req: Request, res: Response) => {
    const envelope = req.body as ModuleRequest<any>;
    const startTime = Date.now();

    try {
      logger.info('Workflow validation request received', { 
        reqId: envelope.reqId,
        action: envelope.payload.action
      });

      const result = await validateWorkflow(envelope.payload.workflowJson, envelope.reqId);

      const response: ModuleResult<MCPResult> = {
        reqId: envelope.reqId,
        status: 'success',
        data: result,
        audit: {
          module: 'mcp-validate',
          durationMs: Date.now() - startTime
        }
      };

      res.status(200).json(response);
    } catch (error) {
      logger.error('Workflow validation failed', { 
        reqId: envelope.reqId, 
        error: (error as Error).message 
      });

      const errorResult: ModuleResult<MCPResult> = {
        reqId: envelope.reqId,
        status: 'error',
        error: {
          type: 'functional',
          code: 'VALIDATION_FAILED',
          message: 'Workflow validation failed',
          retryable: false
        },
        audit: {
          module: 'mcp-validate',
          durationMs: Date.now() - startTime
        }
      };

      res.status(400).json(errorResult);
    }
  });

  /**
   * Workflow import endpoint
   */
  router.post('/import', async (req: Request, res: Response) => {
    const envelope = req.body as ModuleRequest<any>;
    const startTime = Date.now();

    try {
      logger.info('Workflow import request received', { reqId: envelope.reqId });

      const result = await importWorkflow(envelope.payload.workflowJson, envelope.payload.environment, envelope.reqId);

      const response: ModuleResult<MCPResult> = {
        reqId: envelope.reqId,
        status: 'success',
        data: result,
        audit: {
          module: 'mcp-import',
          durationMs: Date.now() - startTime
        }
      };

      res.status(200).json(response);
    } catch (error) {
      logger.error('Workflow import failed', { 
        reqId: envelope.reqId, 
        error: (error as Error).message 
      });

      const errorResult: ModuleResult<MCPResult> = {
        reqId: envelope.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'IMPORT_FAILED',
          message: 'Workflow import failed',
          retryable: true
        },
        audit: {
          module: 'mcp-import',
          durationMs: Date.now() - startTime
        }
      };

      res.status(500).json(errorResult);
    }
  });

  /**
   * Workflow lifecycle management endpoint
   */
  router.post('/lifecycle', async (req: Request, res: Response) => {
    const envelope = req.body as ModuleRequest<any>;
    const startTime = Date.now();

    try {
      const { action, workflowId, environment } = envelope.payload;
      let result;

      switch (action) {
        case 'enable':
          result = await enableWorkflow(workflowId, envelope.reqId);
          break;
        case 'test_run':
          result = await testWorkflow(workflowId, envelope.reqId);
          break;
        case 'promote':
          result = await promoteWorkflow(workflowId, environment, envelope.reqId);
          break;
        case 'rollback':
          result = await rollbackWorkflow(workflowId, envelope.payload.version, envelope.reqId);
          break;
        default:
          throw new Error(`Unsupported lifecycle action: ${action}`);
      }

      const response: ModuleResult<MCPResult> = {
        reqId: envelope.reqId,
        status: 'success',
        data: result,
        audit: {
          module: 'mcp-lifecycle',
          durationMs: Date.now() - startTime
        }
      };

      res.status(200).json(response);
    } catch (error) {
      logger.error('Workflow lifecycle operation failed', { 
        reqId: envelope.reqId, 
        error: (error as Error).message 
      });

      const errorResult: ModuleResult<MCPResult> = {
        reqId: envelope.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'LIFECYCLE_FAILED',
          message: 'Workflow lifecycle operation failed',
          retryable: true
        },
        audit: {
          module: 'mcp-lifecycle',
          durationMs: Date.now() - startTime
        }
      };

      res.status(500).json(errorResult);
    }
  });

  return router;
}

/**
 * Validate workflow JSON structure and logic
 */
async function validateWorkflow(workflowJson: any, reqId: string): Promise<MCPResult> {
  logger.info('Validating workflow', { reqId });
  
  const errors: string[] = [];
  
  // Basic structure validation
  if (!workflowJson.nodes || !Array.isArray(workflowJson.nodes)) {
    errors.push('Missing or invalid nodes array');
  }
  
  if (!workflowJson.connections || typeof workflowJson.connections !== 'object') {
    errors.push('Missing or invalid connections object');
  }
  
  // Node validation
  if (workflowJson.nodes) {
    workflowJson.nodes.forEach((node: any, index: number) => {
      if (!node.id) errors.push(`Node ${index}: Missing ID`);
      if (!node.type) errors.push(`Node ${index}: Missing type`);
      if (!node.position) errors.push(`Node ${index}: Missing position`);
    });
  }
  
  return {
    status: errors.length === 0 ? 'validated' : 'failed',
    errors: errors.length > 0 ? errors : undefined
  };
}

/**
 * Import workflow to n8n
 */
async function importWorkflow(workflowJson: any, environment: string, reqId: string): Promise<MCPResult> {
  logger.info('Importing workflow to n8n', { reqId, environment });
  
  try {
    const n8nUrl = environment === 'production' 
      ? process.env.N8N_PROD_API_URL 
      : process.env.N8N_API_URL || 'http://localhost:5678';
    
    // Mock implementation - would call actual n8n API
    const workflowId = `wf_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    logger.info('Workflow imported successfully', { reqId, workflowId });
    
    return {
      workflowId,
      status: 'imported',
      version: '1.0.0'
    };
    
  } catch (error) {
    logger.error('n8n import failed', { reqId, error: (error as Error).message });
    throw error;
  }
}

/**
 * Enable workflow in n8n
 */
async function enableWorkflow(workflowId: string, reqId: string): Promise<MCPResult> {
  logger.info('Enabling workflow', { reqId, workflowId });
  
  // Mock implementation
  return {
    workflowId,
    status: 'enabled'
  };
}

/**
 * Test workflow execution
 */
async function testWorkflow(workflowId: string, reqId: string): Promise<MCPResult> {
  logger.info('Testing workflow', { reqId, workflowId });
  
  // Mock implementation
  return {
    workflowId,
    status: 'validated'
  };
}

/**
 * Promote workflow to production
 */
async function promoteWorkflow(workflowId: string, environment: string, reqId: string): Promise<MCPResult> {
  logger.info('Promoting workflow', { reqId, workflowId, environment });
  
  // Mock implementation
  return {
    workflowId,
    status: 'promoted',
    version: '1.0.0'
  };
}

/**
 * Rollback workflow to previous version
 */
async function rollbackWorkflow(workflowId: string, version: string, reqId: string): Promise<MCPResult> {
  logger.info('Rolling back workflow', { reqId, workflowId, version });
  
  // Mock implementation
  return {
    workflowId,
    status: 'promoted',
    version
  };
}