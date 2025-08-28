import { OpenRouterClient } from '@umbra/shared';
import { Envelope, UmbraPayload, ModuleResult, SupportedLanguage } from '@umbra/shared';
import Logger from '@umbra/shared/src/utils/logger';

export class TaskExecutor {
  private logger: Logger;
  private openRouterClient: OpenRouterClient;

  constructor(openRouterClient: OpenRouterClient) {
    this.logger = new Logger('TaskExecutor');
    this.openRouterClient = openRouterClient;
  }

  async executeTask(envelope: Envelope<UmbraPayload>): Promise<ModuleResult<any>> {
    const { reqId, userId, lang, payload } = envelope;
    const startTime = Date.now();

    try {
      this.logger.debug('Executing task', {
        reqId,
        userId,
        action: payload.action,
        intent: payload.intent
      });

      let result: any;

      // Handle tasks that Umbra can execute directly
      switch (payload.intent) {
        case 'calculation':
          result = await this.performCalculation(payload.message || '', lang);
          break;
        case 'translation':
          result = await this.performTranslation(payload.message || '', lang);
          break;
        case 'clarification_needed':
          result = await this.requestClarification(envelope);
          break;
        default:
          return {
            reqId,
            status: 'error',
            error: {
              type: 'functional',
              code: 'UNSUPPORTED_TASK',
              message: `Cannot execute task with intent: ${payload.intent}`,
              retryable: false
            }
          };
      }

      const durationMs = Date.now() - startTime;

      this.logger.audit('Task executed successfully', userId, {
        reqId,
        intent: payload.intent,
        durationMs
      });

      return {
        reqId,
        status: 'success',
        data: result,
        audit: {
          module: 'umbra-executor',
          durationMs
        }
      };

    } catch (error) {
      const durationMs = Date.now() - startTime;
      
      this.logger.error('Task execution failed', {
        reqId,
        userId,
        intent: payload.intent,
        error: error.message
      });

      return {
        reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'EXECUTION_ERROR',
          message: 'Task execution failed',
          retryable: true
        },
        audit: {
          module: 'umbra-executor',
          durationMs
        }
      };
    }
  }

  async requestClarification(envelope: Envelope<UmbraPayload>): Promise<ModuleResult<any>> {
    const { reqId, lang, payload } = envelope;
    
    const questions = this.getClarificationQuestions(payload.message || '', lang);
    
    return {
      reqId,
      status: 'needs_validation',
      data: {
        type: 'clarification_request',
        message: questions.join('\n'),
        options: [
          'Finance - Document processing',
          'VPS - System management', 
          'Business - Client management',
          'Production - Workflow creation',
          'Creator - Media generation',
          'Translation - Language conversion',
          'Calculation - Math operations'
        ]
      }
    };
  }

  private async performCalculation(expression: string, lang: SupportedLanguage): Promise<any> {
    try {
      // Safe mathematical expression evaluation
      const mathExpression = this.extractMathExpression(expression);
      
      if (!mathExpression) {
        // Use AI for complex math problems
        const prompt = `Solve this math problem and show the result: ${expression}`;
        const result = await this.openRouterClient.generateText(prompt, 'anthropic/claude-3-haiku');
        
        return {
          type: 'calculation',
          expression,
          result,
          method: 'ai'
        };
      }

      // Simple expression evaluation
      const result = this.evaluateExpression(mathExpression);
      
      return {
        type: 'calculation',
        expression: mathExpression,
        result,
        method: 'direct'
      };

    } catch (error) {
      throw new Error(`Calculation failed: ${error.message}`);
    }
  }

  private async performTranslation(text: string, targetLang: SupportedLanguage): Promise<any> {
    try {
      const translatedText = await this.openRouterClient.translateText(text, targetLang);
      
      return {
        type: 'translation',
        originalText: text,
        translatedText,
        targetLanguage: targetLang
      };

    } catch (error) {
      throw new Error(`Translation failed: ${error.message}`);
    }
  }

  private extractMathExpression(text: string): string | null {
    // Extract simple mathematical expressions
    const patterns = [
      /(\d+(?:\.\d+)?)\s*([\+\-\*\/])\s*(\d+(?:\.\d+)?)/g,
      /(\d+)\s*\+\s*(\d+)/g,
      /(\d+)\s*\-\s*(\d+)/g,
      /(\d+)\s*\*\s*(\d+)/g,
      /(\d+)\s*\/\s*(\d+)/g
    ];

    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match) {
        return match[0];
      }
    }

    return null;
  }

  private evaluateExpression(expression: string): number {
    // Safe evaluation of simple mathematical expressions
    const sanitized = expression.replace(/[^0-9+\-*/.() ]/g, '');
    
    try {
      // Use Function constructor for safer evaluation than eval
      const result = new Function('return ' + sanitized)();
      
      if (typeof result !== 'number' || !isFinite(result)) {
        throw new Error('Invalid result');
      }
      
      return Math.round(result * 100) / 100; // Round to 2 decimal places
    } catch (error) {
      throw new Error('Invalid mathematical expression');
    }
  }

  private getClarificationQuestions(message: string, lang: SupportedLanguage): string[] {
    const questions = {
      EN: [
        "I understand you want help, but could you be more specific?",
        "Are you looking to:",
        "• Process a financial document (invoice, receipt)?",
        "• Check system status or run commands?",
        "• Manage client accounts?",
        "• Create a workflow or automation?",
        "• Generate media (images, videos, audio)?",
        "• Translate text?",
        "• Perform calculations?",
        "",
        "Please let me know which of these options matches what you need."
      ],
      FR: [
        "Je comprends que vous voulez de l'aide, mais pourriez-vous être plus précis ?",
        "Cherchez-vous à :",
        "• Traiter un document financier (facture, reçu) ?",
        "• Vérifier l'état du système ou exécuter des commandes ?",
        "• Gérer des comptes clients ?",
        "• Créer un workflow ou une automatisation ?",
        "• Générer des médias (images, vidéos, audio) ?",
        "• Traduire du texte ?",
        "• Effectuer des calculs ?",
        "",
        "Merci de me faire savoir laquelle de ces options correspond à vos besoins."
      ],
      PT: [
        "Entendo que você quer ajuda, mas poderia ser mais específico?",
        "Você está procurando:",
        "• Processar um documento financeiro (fatura, recibo)?",
        "• Verificar status do sistema ou executar comandos?",
        "• Gerenciar contas de clientes?",
        "• Criar um fluxo de trabalho ou automação?",
        "• Gerar mídia (imagens, vídeos, áudio)?",
        "• Traduzir texto?",
        "• Realizar cálculos?",
        "",
        "Por favor, me informe qual dessas opções corresponde ao que você precisa."
      ]
    };

    return questions[lang] || questions.EN;
  }

  /**
   * Handle simple text summarization
   */
  async summarizeText(text: string, lang: SupportedLanguage, maxLength: number = 500): Promise<string> {
    if (text.length <= maxLength) {
      return text; // No need to summarize
    }

    const prompt = `Summarize the following text in ${maxLength} characters or less. Keep it clear and concise:\n\n${text}`;
    
    return this.openRouterClient.generateText(prompt, 'anthropic/claude-3-haiku');
  }

  /**
   * Extract key information from user messages
   */
  extractParameters(message: string): Record<string, any> {
    const parameters: Record<string, any> = {};

    // Extract common parameters
    const patterns = {
      amount: /\$?(\d+(?:\.\d{2})?)/g,
      date: /(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})/g,
      email: /([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g,
      phone: /(\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})/g,
      url: /(https?:\/\/[^\s]+)/g
    };

    for (const [key, pattern] of Object.entries(patterns)) {
      const matches = message.match(pattern);
      if (matches) {
        parameters[key] = matches.length === 1 ? matches[0] : matches;
      }
    }

    return parameters;
  }

  /**
   * Check if task requires validation
   */
  requiresValidation(intent: string, parameters: Record<string, any>): boolean {
    const criticalIntents = [
      'vps_execute',
      'client_manage',
      'workflow_deploy'
    ];

    return criticalIntents.includes(intent) || 
           parameters.delete || 
           parameters.remove ||
           parameters.restart;
  }
}