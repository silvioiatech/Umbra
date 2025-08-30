import { Router, Request, Response } from 'express';
import { ModuleRequest, ModuleResult } from '@umbra/shared';
import { BusinessResult } from '@umbra/shared';
import { Logger } from '@umbra/shared';
import { RetryUtils } from '@umbra/shared';
import axios from 'axios';

const logger = new Logger('BusinessAPI');

export function apiRoutes() {
  const router = Router();

  /**
   * Client management endpoint - delegates to Concierge for VPS operations
   */
  router.post('/clients', async (req: Request, res: Response) => {
    const envelope = req.body as ModuleRequest<any>;
    const startTime = Date.now();

    try {
      logger.info('Client management request received', { 
        reqId: envelope.reqId,
        action: envelope.payload.clientAction,
        clientName: envelope.payload.clientName
      });

      const { clientAction, clientName, clientPort } = envelope.payload;
      
      let operationResult;

      switch (clientAction) {
        case 'create':
          operationResult = await delegateToConciergeCo(
            'container',
            {
              action: 'start',
              containerName: `n8n_${clientName}`,
              options: { port: clientPort }
            },
            envelope.reqId
          );
          break;
          
        case 'delete':
          operationResult = await delegateToConciergeCo(
            'container',
            {
              action: 'stop',
              containerName: `n8n_${clientName}`
            },
            envelope.reqId
          );
          break;
          
        case 'list':
          operationResult = await delegateToConciergeCo(
            'monitor',
            { action: 'list_containers' },
            envelope.reqId
          );
          break;
          
        default:
          throw new Error(`Unsupported client action: ${clientAction}`);
      }

      const result: ModuleResult<BusinessResult> = {
        reqId: envelope.reqId,
        status: 'success',
        data: {
          operationResult,
          timestamp: new Date().toISOString()
        },
        audit: {
          module: 'business-clients',
          durationMs: Date.now() - startTime
        }
      };

      res.status(200).json(result);
    } catch (error) {
      logger.error('Client management failed', { 
        reqId: envelope.reqId, 
        error: (error as Error).message 
      });

      const errorResult: ModuleResult<BusinessResult> = {
        reqId: envelope.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'CLIENT_MANAGEMENT_FAILED',
          message: 'Client management operation failed',
          retryable: true
        },
        audit: {
          module: 'business-clients',
          durationMs: Date.now() - startTime
        }
      };

      res.status(500).json(errorResult);
    }
  });

  /**
   * Workflow delegation endpoint - delegates to Production module
   */
  router.post('/delegate', async (req: Request, res: Response) => {
    const envelope = req.body as ModuleRequest<any>;
    const startTime = Date.now();

    try {
      logger.info('Workflow delegation request received', { 
        reqId: envelope.reqId,
        workflowSpec: envelope.payload.workflowSpec?.name
      });

      // Delegate workflow creation to Production module
      const delegationResult = await delegateToProduction(
        'create_workflow',
        envelope.payload.workflowSpec,
        envelope.reqId
      );

      const result: ModuleResult<BusinessResult> = {
        reqId: envelope.reqId,
        status: 'success',
        data: {
          workflowStatus: {
            delegated: true,
            targetModule: 'production',
            taskId: delegationResult.taskId
          },
          timestamp: new Date().toISOString()
        },
        audit: {
          module: 'business-delegate',
          durationMs: Date.now() - startTime
        }
      };

      res.status(200).json(result);
    } catch (error) {
      logger.error('Workflow delegation failed', { 
        reqId: envelope.reqId, 
        error: (error as Error).message 
      });

      const errorResult: ModuleResult<BusinessResult> = {
        reqId: envelope.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'DELEGATION_FAILED',
          message: 'Workflow delegation failed',
          retryable: true
        },
        audit: {
          module: 'business-delegate',
          durationMs: Date.now() - startTime
        }
      };

      res.status(500).json(errorResult);
    }
  });

  /**
   * Inventory tracking endpoint
   */
  router.post('/inventory', async (req: Request, res: Response) => {
    const envelope = req.body as ModuleRequest<any>;
    const startTime = Date.now();

    try {
      logger.info('Inventory tracking request received', { 
        reqId: envelope.reqId,
        operationType: envelope.payload.operationType
      });

      // Simulated inventory management
      const inventoryData = await manageInventory(
        envelope.payload.operationType,
        envelope.payload.itemData
      );

      const result: ModuleResult<BusinessResult> = {
        reqId: envelope.reqId,
        status: 'success',
        data: {
          inventoryData,
          timestamp: new Date().toISOString()
        },
        audit: {
          module: 'business-inventory',
          durationMs: Date.now() - startTime
        }
      };

      res.status(200).json(result);
    } catch (error) {
      logger.error('Inventory tracking failed', { 
        reqId: envelope.reqId, 
        error: (error as Error).message 
      });

      const errorResult: ModuleResult<BusinessResult> = {
        reqId: envelope.reqId,
        status: 'error',
        error: {
          type: 'functional',
          code: 'INVENTORY_FAILED',
          message: 'Inventory tracking failed',
          retryable: false
        },
        audit: {
          module: 'business-inventory',
          durationMs: Date.now() - startTime
        }
      };

      res.status(400).json(errorResult);
    }
  });

  return router;
}

/**
 * Delegate operations to Concierge service
 */
async function delegateToConciergeCo(action: string, payload: any, reqId: string): Promise<any> {
  const conciergeUrl = process.env.CONCIERGE_URL || 'http://localhost:9090';
  
  try {
    const response = await axios.post(`${conciergeUrl}/api/v1/${action}`, {
      reqId,
      userId: 'business-module',
      lang: 'EN',
      timestamp: new Date().toISOString(),
      payload
    }, {
      headers: {
        'X-API-Key': process.env.CONCIERGE_API_KEY,
        'X-Service-Name': 'business',
        'Content-Type': 'application/json'
      },
      timeout: 30000
    });

    return response.data;
  } catch (error) {
    logger.error('Concierge delegation failed', { 
      action, 
      reqId, 
      error: (error as Error).message 
    });
    throw error;
  }
}

/**
 * Delegate workflow operations to Production service
 */
async function delegateToProduction(action: string, workflowSpec: any, reqId: string): Promise<any> {
  const productionUrl = process.env.PRODUCTION_URL || 'http://localhost:8083';
  
  try {
    const response = await axios.post(`${productionUrl}/api/v1/workflow`, {
      reqId,
      userId: 'business-module',
      lang: 'EN',
      timestamp: new Date().toISOString(),
      payload: {
        action,
        workflowSpec,
        environment: 'staging'
      }
    }, {
      headers: {
        'X-API-Key': process.env.PRODUCTION_API_KEY,
        'X-Service-Name': 'business',
        'Content-Type': 'application/json'
      },
      timeout: 60000
    });

    return response.data;
  } catch (error) {
    logger.error('Production delegation failed', { 
      action, 
      reqId, 
      error: (error as Error).message 
    });
    throw error;
  }
}

/**
 * Simple inventory management implementation
 */
async function manageInventory(operationType: string, itemData: any): Promise<any> {
  // Mock inventory data - in real implementation would use database
  const mockInventory = {
    containers: [
      { id: 'n8n_client1', status: 'running', port: 5678 },
      { id: 'n8n_client2', status: 'stopped', port: 5679 }
    ],
    workflows: [
      { id: 'wf_001', name: 'customer_onboarding', status: 'active' },
      { id: 'wf_002', name: 'invoice_processing', status: 'draft' }
    ],
    clients: [
      { name: 'client1', port: 5678, status: 'active' },
      { name: 'client2', port: 5679, status: 'inactive' }
    ]
  };

  switch (operationType) {
    case 'list':
      return mockInventory;
      
    case 'create':
      mockInventory.clients.push({
        name: itemData.name,
        port: itemData.port,
        status: 'pending'
      });
      return { created: itemData, inventory: mockInventory };
      
    case 'update':
      const index = mockInventory.clients.findIndex(c => c.name === itemData.name);
      if (index >= 0) {
        mockInventory.clients[index] = { ...mockInventory.clients[index], ...itemData };
      }
      return { updated: itemData, inventory: mockInventory };
      
    case 'delete':
      const deleteIndex = mockInventory.clients.findIndex(c => c.name === itemData.name);
      if (deleteIndex >= 0) {
        mockInventory.clients.splice(deleteIndex, 1);
      }
      return { deleted: itemData, inventory: mockInventory };
      
    default:
      throw new Error(`Unsupported inventory operation: ${operationType}`);
  }
}