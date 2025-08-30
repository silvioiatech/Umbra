import express from 'express';
import { OpenRouterClient } from '@umbra/shared';
import { Envelope, UmbraPayload, ModuleResult } from '@umbra/shared';
import { IntentClassifier } from '../routing/intent-classifier';
import { ModuleRouter } from '../routing/module-router';
import { TaskExecutor } from '../handlers/task-executor';
import { Logger } from '@umbra/shared';

export function apiRoutes(openRouterClient: OpenRouterClient): express.Router {
  const router = express.Router();
  const logger = new Logger('UmbraAPIRoutes');
  const intentClassifier = new IntentClassifier(openRouterClient);
  const moduleRouter = new ModuleRouter();
  const taskExecutor = new TaskExecutor(openRouterClient);

  // Route envelope to appropriate handler
  router.post('/route', async (req, res) => {
    try {
      const envelope: Envelope<UmbraPayload> = req.body;
      const { reqId, userId, lang, payload } = envelope;

      logger.audit('Route request received', userId, {
        reqId,
        action: payload.action,
        lang
      });

      let result: ModuleResult<any>;

      switch (payload.action) {
        case 'classify':
          result = await intentClassifier.classifyIntent(envelope);
          break;
        case 'route':
          result = await moduleRouter.routeToModule(envelope);
          break;
        case 'execute':
          result = await taskExecutor.executeTask(envelope);
          break;
        case 'clarify':
          result = await taskExecutor.requestClarification(envelope);
          break;
        default:
          result = {
            reqId,
            status: 'error',
            error: {
              type: 'functional',
              code: 'INVALID_ACTION',
              message: `Unknown action: ${payload.action}`,
              retryable: false
            }
          };
      }

      logger.audit('Route request completed', userId, {
        reqId,
        status: result.status,
        durationMs: result.audit?.durationMs
      });

      res.json(result);

    } catch (error) {
      logger.error('Route request failed', {
        error: error.message,
        reqId: req.body?.reqId
      });

      res.status(500).json({
        reqId: req.body?.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'INTERNAL_ERROR',
          message: 'Internal server error',
          retryable: true
        }
      });
    }
  });

  // Execute simple tasks directly
  router.post('/execute', async (req, res) => {
    try {
      const envelope: Envelope<UmbraPayload> = req.body;
      const result = await taskExecutor.executeTask(envelope);
      res.json(result);
    } catch (error) {
      logger.error('Execute request failed', {
        error: error.message,
        reqId: req.body?.reqId
      });

      res.status(500).json({
        reqId: req.body?.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'EXECUTION_ERROR',
          message: 'Task execution failed',
          retryable: true
        }
      });
    }
  });

  // Classify user intent
  router.post('/classify', async (req, res) => {
    try {
      const envelope: Envelope<UmbraPayload> = req.body;
      const result = await intentClassifier.classifyIntent(envelope);
      res.json(result);
    } catch (error) {
      logger.error('Classification request failed', {
        error: error.message,
        reqId: req.body?.reqId
      });

      res.status(500).json({
        reqId: req.body?.reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'CLASSIFICATION_ERROR',
          message: 'Intent classification failed',
          retryable: true
        }
      });
    }
  });

  return router;
}