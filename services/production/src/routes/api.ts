import { Router, Request, Response } from 'express';
import { ModuleRequest, ModuleResult } from '@umbra/shared/src/types/envelopes';
import { ProductionResult } from '@umbra/shared/src/types/modules';
import Logger from '@umbra/shared/src/utils/logger';
import { RetryUtils } from '@umbra/shared/src/utils/retry';
import axios from 'axios';

const logger = new Logger('ProductionAPI');

export function apiRoutes() {
  const router = Router();

  /**
   * Workflow creation endpoint - implements Claude → GPT → MCP pipeline
   */
  router.post('/workflow', async (req: Request, res: Response) => {
    const envelope = req.body as ModuleRequest<any>;
    const startTime = Date.now();

    try {
      logger.info('Workflow creation request received', { 
        reqId: envelope.reqId,
        action: envelope.payload.action,
        workflowName: envelope.payload.workflowName
      });

      const { action, workflowSpec, nlDescription, environment } = envelope.payload;
      let result;

      switch (action) {
        case 'create_workflow':
          result = await createWorkflowPipeline(workflowSpec, nlDescription, envelope.reqId);
          break;
        case 'validate':
          result = await validateWorkflow(workflowSpec, envelope.reqId);
          break;
        case 'deploy':
          result = await deployWorkflow(workflowSpec, environment, envelope.reqId);
          break;
        case 'rollback':
          result = await rollbackWorkflow(envelope.payload.workflowId, envelope.payload.version, envelope.reqId);
          break;
        default:
          throw new Error(`Unsupported workflow action: ${action}`);
      }

      const response: ModuleResult<ProductionResult> = {
        reqId: envelope.reqId,
        status: 'success',
        data: result,
        audit: {
          module: 'production-workflow',
          durationMs: Date.now() - startTime
        }
      };

      res.status(200).json(response);
    } catch (error) {
      logger.error('Workflow operation failed', { 
        reqId: envelope.reqId, 
        error: (error as Error).message 
      });

      const errorResult: ModuleResult<ProductionResult> = {
        reqId: envelope.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'WORKFLOW_FAILED',
          message: 'Workflow operation failed',
          retryable: true
        },
        audit: {
          module: 'production-workflow',
          durationMs: Date.now() - startTime
        }
      };

      res.status(500).json(errorResult);
    }
  });

  return router;
}

/**
 * Claude → GPT → MCP Pipeline Implementation
 */
async function createWorkflowPipeline(workflowSpec: any, nlDescription: string, reqId: string): Promise<ProductionResult> {
  logger.info('Starting Claude → GPT → MCP pipeline', { reqId });
  
  try {
    // Step 1: Claude - Architecture Planning
    const claudeResult = await claudeArchitecturePlanning(nlDescription || workflowSpec, reqId);
    
    // Step 2: GPT - JSON Generation with retry logic
    const retryConfig = RetryUtils.createRetryConfig('api');
    const gptResult = await RetryUtils.retry(
      () => gptJsonGeneration(claudeResult.architecture, reqId),
      retryConfig
    );
    
    // Step 3: MCP - Lifecycle Management with circuit breaker
    const circuitBreaker = RetryUtils.createCircuitBreaker(3, 30000);
    const mcpResult = await circuitBreaker(
      () => mcpWorkflowManagement(gptResult.workflowJson, reqId)
    );

    return {
      workflowId: mcpResult.workflowId,
      status: 'created',
      testResults: {
        claude: claudeResult,
        gpt: gptResult,
        mcp: mcpResult
      }
    };
    
  } catch (error) {
    logger.error('Pipeline failed', { reqId, error: (error as Error).message });
    throw error;
  }
}

/**
 * Step 1: Claude Architecture Planning
 */
async function claudeArchitecturePlanning(description: any, reqId: string): Promise<any> {
  logger.info('Claude architecture planning started', { reqId });
  
  const prompt = `
You are an expert n8n workflow architect. Based on the following requirements, create a detailed architecture plan for an n8n workflow:

Requirements: ${JSON.stringify(description, null, 2)}

Please provide:
1. Workflow overview and purpose
2. Node sequence and connections
3. Data transformations needed
4. Error handling strategy
5. Best practices recommendations

Format your response as a structured JSON object with clear sections.
`;

  try {
    const response = await callOpenRouter({
      model: 'anthropic/claude-3-sonnet-20240229',
      messages: [
        {
          role: 'system',
          content: 'You are an expert n8n workflow architect. Always respond with valid JSON that can be parsed.'
        },
        {
          role: 'user',
          content: prompt
        }
      ],
      temperature: 0.3,
      max_tokens: 4000
    });

    const architecture = JSON.parse(response.content);
    
    logger.info('Claude architecture planning completed', { reqId });
    return { architecture, provider: 'claude' };
    
  } catch (error) {
    logger.error('Claude planning failed', { reqId, error: (error as Error).message });
    throw new Error(`Claude architecture planning failed: ${(error as Error).message}`);
  }
}

/**
 * Step 2: GPT JSON Generation
 */
async function gptJsonGeneration(architecture: any, reqId: string): Promise<any> {
  logger.info('GPT JSON generation started', { reqId });
  
  const prompt = `
Convert this n8n workflow architecture into a complete, executable n8n workflow JSON:

Architecture: ${JSON.stringify(architecture, null, 2)}

Requirements:
1. Generate a complete n8n workflow JSON that can be imported directly
2. Include all necessary nodes with proper configurations
3. Set up correct connections between nodes
4. Add appropriate error handling nodes
5. Include webhook configurations if needed
6. Ensure the JSON follows n8n's exact format specification

Return only the workflow JSON, no additional text.
`;

  try {
    const response = await callOpenRouter({
      model: 'openai/gpt-4-turbo-preview',
      messages: [
        {
          role: 'system',
          content: 'You are an expert n8n workflow developer. Always respond with valid n8n workflow JSON that can be directly imported.'
        },
        {
          role: 'user',
          content: prompt
        }
      ],
      temperature: 0.1,
      max_tokens: 8000
    });

    const workflowJson = JSON.parse(response.content);
    
    // Validate JSON structure
    if (!workflowJson.nodes || !Array.isArray(workflowJson.nodes)) {
      throw new Error('Generated JSON missing required nodes array');
    }
    
    logger.info('GPT JSON generation completed', { reqId, nodeCount: workflowJson.nodes.length });
    return { workflowJson, provider: 'gpt' };
    
  } catch (error) {
    logger.error('GPT generation failed', { reqId, error: (error as Error).message });
    throw new Error(`GPT JSON generation failed: ${(error as Error).message}`);
  }
}

/**
 * Step 3: MCP Workflow Management
 */
async function mcpWorkflowManagement(workflowJson: any, reqId: string): Promise<any> {
  logger.info('MCP workflow management started', { reqId });
  
  try {
    const mcpUrl = process.env.MCP_URL || 'http://localhost:8085';
    
    // Send to MCP for validation and import
    const response = await axios.post(`${mcpUrl}/api/v1/import`, {
      reqId,
      userId: 'production-module',
      lang: 'EN',
      timestamp: new Date().toISOString(),
      payload: {
        action: 'import',
        workflowJson,
        environment: 'staging'
      }
    }, {
      headers: {
        'X-API-Key': process.env.MCP_API_KEY,
        'X-Service-Name': 'production',
        'Content-Type': 'application/json'
      },
      timeout: 60000
    });

    const mcpResult = response.data;
    
    logger.info('MCP workflow management completed', { reqId, workflowId: mcpResult.data?.workflowId });
    return mcpResult.data;
    
  } catch (error) {
    logger.error('MCP management failed', { reqId, error: (error as Error).message });
    throw new Error(`MCP workflow management failed: ${(error as Error).message}`);
  }
}

/**
 * Validate workflow
 */
async function validateWorkflow(workflowSpec: any, reqId: string): Promise<ProductionResult> {
  logger.info('Workflow validation started', { reqId });
  
  try {
    const validationErrors: string[] = [];
    
    // Basic validation
    if (!workflowSpec.nodes || !Array.isArray(workflowSpec.nodes)) {
      validationErrors.push('Missing or invalid nodes array');
    }
    
    if (!workflowSpec.connections || typeof workflowSpec.connections !== 'object') {
      validationErrors.push('Missing or invalid connections object');
    }
    
    // Node validation
    if (workflowSpec.nodes) {
      workflowSpec.nodes.forEach((node: any, index: number) => {
        if (!node.id) validationErrors.push(`Node ${index} missing ID`);
        if (!node.type) validationErrors.push(`Node ${index} missing type`);
        if (!node.position) validationErrors.push(`Node ${index} missing position`);
      });
    }
    
    const isValid = validationErrors.length === 0;
    
    return {
      status: isValid ? 'validated' : 'failed',
      validationErrors: validationErrors.length > 0 ? validationErrors : undefined
    };
    
  } catch (error) {
    logger.error('Workflow validation failed', { reqId, error: (error as Error).message });
    throw error;
  }
}

/**
 * Deploy workflow
 */
async function deployWorkflow(workflowSpec: any, environment: string, reqId: string): Promise<ProductionResult> {
  logger.info('Workflow deployment started', { reqId, environment });
  
  try {
    // Delegate to MCP for deployment
    const mcpUrl = process.env.MCP_URL || 'http://localhost:8085';
    
    const response = await axios.post(`${mcpUrl}/api/v1/deploy`, {
      reqId,
      userId: 'production-module',
      lang: 'EN',
      timestamp: new Date().toISOString(),
      payload: {
        action: 'promote',
        workflowJson: workflowSpec,
        environment
      }
    }, {
      headers: {
        'X-API-Key': process.env.MCP_API_KEY,
        'X-Service-Name': 'production',
        'Content-Type': 'application/json'
      },
      timeout: 60000
    });

    return {
      workflowId: response.data.data?.workflowId,
      status: 'deployed'
    };
    
  } catch (error) {
    logger.error('Workflow deployment failed', { reqId, error: (error as Error).message });
    throw error;
  }
}

/**
 * Rollback workflow
 */
async function rollbackWorkflow(workflowId: string, version: string, reqId: string): Promise<ProductionResult> {
  logger.info('Workflow rollback started', { reqId, workflowId, version });
  
  try {
    const mcpUrl = process.env.MCP_URL || 'http://localhost:8085';
    
    const response = await axios.post(`${mcpUrl}/api/v1/rollback`, {
      reqId,
      userId: 'production-module',
      lang: 'EN',
      timestamp: new Date().toISOString(),
      payload: {
        action: 'rollback',
        workflowId,
        version
      }
    }, {
      headers: {
        'X-API-Key': process.env.MCP_API_KEY,
        'X-Service-Name': 'production',
        'Content-Type': 'application/json'
      },
      timeout: 30000
    });

    return {
      workflowId,
      status: 'deployed' // Rolled back to previous version
    };
    
  } catch (error) {
    logger.error('Workflow rollback failed', { reqId, error: (error as Error).message });
    throw error;
  }
}

/**
 * Call OpenRouter API with retry logic
 */
async function callOpenRouter(payload: any): Promise<any> {
  const openrouterUrl = process.env.OPENROUTER_BASE_URL || 'https://openrouter.ai/api/v1';
  
  try {
    const response = await axios.post(`${openrouterUrl}/chat/completions`, payload, {
      headers: {
        'Authorization': `Bearer ${process.env.OPENROUTER_API_KEY}`,
        'Content-Type': 'application/json',
        'HTTP-Referer': process.env.OPENROUTER_SITE_URL || 'https://umbra.ai',
        'X-Title': 'Umbra Production Module'
      },
      timeout: 60000
    });

    if (!response.data.choices || response.data.choices.length === 0) {
      throw new Error('No response from OpenRouter');
    }

    return {
      content: response.data.choices[0].message.content,
      usage: response.data.usage
    };
    
  } catch (error) {
    logger.error('OpenRouter API call failed', { error: (error as Error).message });
    throw error;
  }
}