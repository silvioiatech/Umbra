import { OpenRouterClient } from '@umbra/shared';
import { Envelope, UmbraPayload, ModuleResult, SupportedLanguage } from '@umbra/shared';
import { Logger } from '@umbra/shared';

interface IntentClassificationResult {
  intent: string;
  confidence: number;
  targetModule: string;
  parameters?: Record<string, any>;
  requiresClarification: boolean;
}

export class IntentClassifier {
  private logger: Logger;
  private openRouterClient: OpenRouterClient;

  // Intent patterns for quick classification
  private intentPatterns = {
    finance_ocr: [
      /(?:extract|ocr|scan|read|process).*(?:document|invoice|receipt|bill|statement)/i,
      /(?:upload|send).*(?:invoice|receipt|bill|document)/i,
      /(?:analyze|parse).*(?:financial|invoice|receipt)/i
    ],
    finance_report: [
      /(?:generate|create|make).*(?:report|summary|analysis)/i,
      /(?:vat|tax|budget).*(?:report|summary)/i,
      /(?:financial|expense).*(?:report|analysis)/i
    ],
    vps_monitor: [
      /(?:check|show|display).*(?:status|health|system|server)/i,
      /(?:monitor|monitoring).*(?:system|server|vps)/i,
      /(?:cpu|memory|disk|uptime)/i
    ],
    vps_execute: [
      /(?:run|execute|start|stop|restart).*(?:command|script|service|container)/i,
      /(?:docker|container).*(?:start|stop|restart|remove)/i,
      /(?:deploy|update|manage).*(?:service|application)/i
    ],
    client_manage: [
      /(?:create|add|new).*(?:client|customer|account)/i,
      /(?:remove|delete).*(?:client|customer|account)/i,
      /(?:list|show).*(?:clients|customers|accounts)/i
    ],
    workflow_create: [
      /(?:create|build|make).*(?:workflow|automation|process)/i,
      /(?:n8n|workflow).*(?:create|build)/i,
      /(?:automate|automation)/i
    ],
    media_generate: [
      /(?:generate|create|make).*(?:image|video|audio|media)/i,
      /(?:create|generate).*(?:picture|photo|sound|music)/i,
      /(?:text.*speech|tts|voice)/i
    ],
    translation: [
      /(?:translate|translation).*(?:to|into)/i,
      /(?:convert|change).*(?:language)/i,
      /(?:french|english|portuguese|fr|en|pt)/i
    ],
    calculation: [
      /(?:calculate|compute|math|arithmetic)/i,
      /(?:\d+\s*[\+\-\*\/]\s*\d+)/,
      /(?:add|subtract|multiply|divide|sum)/i
    ]
  };

  constructor(openRouterClient: OpenRouterClient) {
    this.logger = new Logger('IntentClassifier');
    this.openRouterClient = openRouterClient;
  }

  async classifyIntent(envelope: Envelope<UmbraPayload>): Promise<ModuleResult<IntentClassificationResult>> {
    const startTime = Date.now();
    const { reqId, userId, lang, payload } = envelope;

    try {
      const message = payload.message;
      
      if (!message) {
        return {
          reqId,
          status: 'error',
          error: {
            type: 'functional',
            code: 'MISSING_MESSAGE',
            message: 'Message is required for intent classification',
            retryable: false
          }
        };
      }

      this.logger.debug('Classifying intent', {
        reqId,
        userId,
        messageLength: message.length,
        lang
      });

      // Try pattern-based classification first (faster)
      let patternResult = this.classifyByPatterns(message);
      
      // If pattern classification is uncertain, use AI
      if (!patternResult || patternResult.confidence < 0.7) {
        const aiResult = await this.classifyWithAI(message, lang);
        
        // Use AI result if it's more confident, otherwise combine
        if (aiResult.confidence > (patternResult?.confidence || 0)) {
          patternResult = aiResult;
        }
      }

      const durationMs = Date.now() - startTime;

      if (!patternResult || patternResult.confidence < 0.5) {
        return {
          reqId,
          status: 'needs_validation',
          data: {
            intent: 'clarification_needed',
            confidence: 0,
            targetModule: 'umbra',
            requiresClarification: true
          },
          audit: {
            module: 'umbra-classifier',
            durationMs
          }
        };
      }

      this.logger.audit('Intent classified', userId, {
        reqId,
        intent: patternResult.intent,
        confidence: patternResult.confidence,
        targetModule: patternResult.targetModule,
        method: patternResult.confidence >= 0.7 ? 'pattern' : 'ai'
      });

      return {
        reqId,
        status: 'success',
        data: patternResult,
        audit: {
          module: 'umbra-classifier',
          durationMs
        }
      };

    } catch (error) {
      const durationMs = Date.now() - startTime;
      
      this.logger.error('Intent classification failed', {
        reqId,
        userId,
        error: error.message
      });

      return {
        reqId,
        status: 'error',
        error: {
          type: 'technical',
          code: 'CLASSIFICATION_ERROR',
          message: 'Failed to classify user intent',
          retryable: true
        },
        audit: {
          module: 'umbra-classifier',
          durationMs
        }
      };
    }
  }

  private classifyByPatterns(message: string): IntentClassificationResult | null {
    const normalizedMessage = message.toLowerCase().trim();

    for (const [intent, patterns] of Object.entries(this.intentPatterns)) {
      for (const pattern of patterns) {
        if (pattern.test(normalizedMessage)) {
          const targetModule = this.getTargetModule(intent);
          
          return {
            intent,
            confidence: 0.8, // High confidence for pattern matches
            targetModule,
            requiresClarification: false
          };
        }
      }
    }

    return null;
  }

  private async classifyWithAI(message: string, lang: SupportedLanguage): Promise<IntentClassificationResult> {
    try {
      const result = await this.openRouterClient.classifyIntent(message, lang);
      
      return {
        intent: result.intent,
        confidence: result.confidence,
        targetModule: result.targetModule,
        requiresClarification: result.confidence < 0.7
      };
    } catch (error) {
      this.logger.warn('AI classification failed, using fallback', {
        error: error.message
      });

      return {
        intent: 'unknown',
        confidence: 0.1,
        targetModule: 'umbra',
        requiresClarification: true
      };
    }
  }

  private getTargetModule(intent: string): string {
    const moduleMapping: Record<string, string> = {
      finance_ocr: 'finance',
      finance_report: 'finance',
      vps_monitor: 'concierge',
      vps_execute: 'concierge',
      client_manage: 'business',
      workflow_create: 'production',
      media_generate: 'creator',
      translation: 'umbra',
      calculation: 'umbra'
    };

    return moduleMapping[intent] || 'umbra';
  }

  /**
   * Get clarification questions for ambiguous intents
   */
  getClarificationQuestions(message: string, lang: SupportedLanguage): string[] {
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
}