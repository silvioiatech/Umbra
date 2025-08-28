import { TelegramClient, OpenRouterClient } from '@umbra/shared';
import { SupportedLanguage, Envelope, UmbraPayload } from '@umbra/shared';
import { IntentClassifier } from '../routing/intent-classifier';
import { ModuleRouter } from '../routing/module-router';
import { TaskExecutor } from '../handlers/task-executor';
import Logger from '@umbra/shared/src/utils/logger';
import { v4 as uuidv4 } from 'uuid';

interface TelegramUpdate {
  update_id: number;
  message?: {
    message_id: number;
    from: {
      id: number;
      is_bot: boolean;
      first_name: string;
      last_name?: string;
      username?: string;
      language_code?: string;
    };
    chat: {
      id: number;
      first_name?: string;
      last_name?: string;
      username?: string;
      type: 'private' | 'group' | 'supergroup' | 'channel';
    };
    date: number;
    text?: string;
    document?: any;
    photo?: any[];
  };
  callback_query?: {
    id: string;
    from: any;
    message?: any;
    data?: string;
  };
}

export class TelegramHandler {
  private logger: Logger;
  private telegramClient: TelegramClient;
  private intentClassifier: IntentClassifier;
  private moduleRouter: ModuleRouter;
  private taskExecutor: TaskExecutor;

  constructor(telegramClient: TelegramClient, openRouterClient: OpenRouterClient) {
    this.logger = new Logger('TelegramHandler');
    this.telegramClient = telegramClient;
    this.intentClassifier = new IntentClassifier(openRouterClient);
    this.moduleRouter = new ModuleRouter();
    this.taskExecutor = new TaskExecutor(openRouterClient);
  }

  async handleUpdate(update: TelegramUpdate): Promise<void> {
    try {
      if (update.message) {
        await this.handleMessage(update.message);
      } else if (update.callback_query) {
        await this.handleCallbackQuery(update.callback_query);
      }
    } catch (error) {
      this.logger.error('Failed to handle Telegram update', {
        updateId: update.update_id,
        error: error.message
      });
    }
  }

  private async handleMessage(message: any): Promise<void> {
    const userId = message.from.id.toString();
    const chatId = message.chat.id;
    const text = message.text;
    const document = message.document;
    const photo = message.photo;
    
    // Detect user language
    const lang = this.detectLanguage(message.from.language_code);

    this.logger.debug('Processing Telegram message', {
      userId,
      chatId,
      hasText: !!text,
      hasDocument: !!document,
      hasPhoto: !!photo,
      lang
    });

    try {
      // Send typing indicator
      await this.telegramClient.sendChatAction(chatId, 'typing');

      // Handle different message types
      if (text) {
        await this.handleTextMessage(userId, chatId, text, lang);
      } else if (document) {
        await this.handleDocumentMessage(userId, chatId, document, lang);
      } else if (photo) {
        await this.handlePhotoMessage(userId, chatId, photo, lang);
      } else {
        await this.telegramClient.sendLocalizedMessage(
          chatId,
          'error',
          { error: 'Unsupported message type' },
          lang
        );
      }
    } catch (error) {
      this.logger.error('Message handling failed', {
        userId,
        chatId,
        error: error.message
      });

      await this.telegramClient.sendLocalizedMessage(
        chatId,
        'error',
        { error: 'An error occurred while processing your message' },
        lang
      );
    }
  }

  private async handleTextMessage(
    userId: string,
    chatId: number,
    text: string,
    lang: SupportedLanguage
  ): Promise<void> {
    // Handle special commands
    if (text.startsWith('/')) {
      await this.handleCommand(userId, chatId, text, lang);
      return;
    }

    // Create envelope for processing
    const envelope: Envelope<UmbraPayload> = {
      reqId: uuidv4(),
      userId,
      lang,
      timestamp: new Date().toISOString(),
      payload: {
        action: 'classify',
        message: text
      }
    };

    // Classify intent
    const classificationResult = await this.intentClassifier.classifyIntent(envelope);

    if (classificationResult.status === 'error') {
      await this.telegramClient.sendLocalizedMessage(
        chatId,
        'error',
        { error: 'Failed to understand your request' },
        lang
      );
      return;
    }

    const classification = classificationResult.data!;

    // Handle clarification requests
    if (classification.requiresClarification) {
      const questions = this.intentClassifier.getClarificationQuestions(text, lang);
      await this.telegramClient.sendMessage({
        chat_id: chatId,
        text: questions.join('\n'),
        parse_mode: 'HTML'
      });
      return;
    }

    // Execute task if Umbra can handle it directly
    if (classification.targetModule === 'umbra' && 
        ['calculation', 'translation'].includes(classification.intent)) {
      
      const taskEnvelope: Envelope<UmbraPayload> = {
        ...envelope,
        payload: {
          action: 'execute',
          intent: classification.intent,
          message: text
        }
      };

      const result = await this.taskExecutor.executeTask(taskEnvelope);
      await this.sendTaskResult(chatId, result, lang);
      return;
    }

    // Route to appropriate module
    const routingEnvelope: Envelope<UmbraPayload> = {
      ...envelope,
      payload: {
        action: 'route',
        intent: classification.intent,
        targetModule: classification.targetModule,
        message: text,
        confidence: classification.confidence
      }
    };

    await this.telegramClient.sendLocalizedMessage(
      chatId,
      'processing',
      {},
      lang
    );

    const routingResult = await this.moduleRouter.routeWithFallback(routingEnvelope);
    await this.sendTaskResult(chatId, routingResult, lang);
  }

  private async handleDocumentMessage(
    userId: string,
    chatId: number,
    document: any,
    lang: SupportedLanguage
  ): Promise<void> {
    try {
      // Check file size and type
      if (document.file_size > 50 * 1024 * 1024) { // 50MB limit
        await this.telegramClient.sendLocalizedMessage(
          chatId,
          'file_too_large',
          { maxSize: '50' },
          lang
        );
        return;
      }

      // Supported document types for financial processing
      const supportedTypes = [
        'application/pdf',
        'image/jpeg',
        'image/png',
        'image/gif'
      ];

      if (!supportedTypes.includes(document.mime_type)) {
        await this.telegramClient.sendLocalizedMessage(
          chatId,
          'invalid_format',
          { formats: 'PDF, JPEG, PNG, GIF' },
          lang
        );
        return;
      }

      // Get file and upload to storage
      const fileInfo = await this.telegramClient.getFile(document.file_id);
      const fileBuffer = await this.telegramClient.downloadFile(fileInfo.result.file_path);

      // Create envelope for finance module
      const envelope: Envelope<UmbraPayload> = {
        reqId: uuidv4(),
        userId,
        lang,
        timestamp: new Date().toISOString(),
        payload: {
          action: 'route',
          intent: 'finance_ocr',
          targetModule: 'finance',
          message: `Process document: ${document.file_name}`,
          documentData: fileBuffer.toString('base64'),
          documentType: this.detectDocumentType(document.file_name)
        }
      };

      await this.telegramClient.sendLocalizedMessage(
        chatId,
        'processing',
        {},
        lang
      );

      const result = await this.moduleRouter.routeWithFallback(envelope);
      await this.sendTaskResult(chatId, result, lang);

    } catch (error) {
      this.logger.error('Document processing failed', {
        userId,
        fileName: document.file_name,
        error: error.message
      });

      await this.telegramClient.sendLocalizedMessage(
        chatId,
        'error',
        { error: 'Failed to process document' },
        lang
      );
    }
  }

  private async handlePhotoMessage(
    userId: string,
    chatId: number,
    photos: any[],
    lang: SupportedLanguage
  ): Promise<void> {
    // Use the highest resolution photo
    const photo = photos[photos.length - 1];
    
    try {
      // Get file and process as document
      const fileInfo = await this.telegramClient.getFile(photo.file_id);
      const fileBuffer = await this.telegramClient.downloadFile(fileInfo.result.file_path);

      // Create envelope for finance module (treat photo as document)
      const envelope: Envelope<UmbraPayload> = {
        reqId: uuidv4(),
        userId,
        lang,
        timestamp: new Date().toISOString(),
        payload: {
          action: 'route',
          intent: 'finance_ocr',
          targetModule: 'finance',
          message: 'Process photo document',
          documentData: fileBuffer.toString('base64'),
          documentType: 'receipt'
        }
      };

      await this.telegramClient.sendLocalizedMessage(
        chatId,
        'processing',
        {},
        lang
      );

      const result = await this.moduleRouter.routeWithFallback(envelope);
      await this.sendTaskResult(chatId, result, lang);

    } catch (error) {
      this.logger.error('Photo processing failed', {
        userId,
        error: error.message
      });

      await this.telegramClient.sendLocalizedMessage(
        chatId,
        'error',
        { error: 'Failed to process photo' },
        lang
      );
    }
  }

  private async handleCommand(
    userId: string,
    chatId: number,
    command: string,
    lang: SupportedLanguage
  ): Promise<void> {
    const cmd = command.toLowerCase();

    switch (cmd) {
      case '/start':
        await this.sendWelcomeMessage(chatId, lang);
        break;
      case '/help':
        await this.sendHelpMessage(chatId, lang);
        break;
      case '/status':
        await this.sendStatusMessage(chatId, lang);
        break;
      case '/lang':
        await this.sendLanguageSelection(chatId);
        break;
      default:
        await this.telegramClient.sendLocalizedMessage(
          chatId,
          'error',
          { error: 'Unknown command' },
          lang
        );
    }
  }

  private async handleCallbackQuery(callbackQuery: any): Promise<void> {
    const userId = callbackQuery.from.id.toString();
    const data = callbackQuery.data;
    const chatId = callbackQuery.message.chat.id;

    this.logger.debug('Processing callback query', {
      userId,
      data
    });

    // Handle validation callbacks
    if (data.startsWith('validate:')) {
      await this.handleValidationCallback(userId, chatId, data);
    }

    // Acknowledge the callback
    await this.telegramClient.sendMessage({
      chat_id: chatId,
      text: 'Processing your selection...'
    });
  }

  private async handleValidationCallback(userId: string, chatId: number, data: string): Promise<void> {
    const [, token, action] = data.split(':');
    
    // This would integrate with the validation system
    // For now, just acknowledge
    await this.telegramClient.sendMessage({
      chat_id: chatId,
      text: `Validation ${action} for token ${token.substring(0, 8)}...`
    });
  }

  private async sendTaskResult(chatId: number, result: any, lang: SupportedLanguage): Promise<void> {
    if (result.status === 'success') {
      let message = '';
      
      if (result.data?.type === 'calculation') {
        message = `**Result:** ${result.data.result}`;
      } else if (result.data?.type === 'translation') {
        message = `**Translation:** ${result.data.translatedText}`;
      } else if (result.data?.extractedData) {
        const data = result.data.extractedData;
        message = this.telegramClient.formatMessage('ocr_complete', { data: JSON.stringify(data) }, lang);
      } else {
        message = this.telegramClient.formatMessage('success', {}, lang);
      }

      await this.telegramClient.sendMessage({
        chat_id: chatId,
        text: message,
        parse_mode: 'Markdown'
      });
    } else {
      const errorMessage = result.error?.message || 'Unknown error occurred';
      await this.telegramClient.sendLocalizedMessage(
        chatId,
        'error',
        { error: errorMessage },
        lang
      );
    }
  }

  private async sendWelcomeMessage(chatId: number, lang: SupportedLanguage): Promise<void> {
    const welcomeMessages = {
      EN: "Welcome to Umbra Bot! 🤖\n\nI can help you with:\n• Financial document processing\n• System monitoring\n• Client management\n• Workflow automation\n• Media generation\n• Translation\n• Calculations\n\nJust send me a message or document to get started!",
      FR: "Bienvenue sur Umbra Bot ! 🤖\n\nJe peux vous aider avec :\n• Traitement de documents financiers\n• Surveillance du système\n• Gestion des clients\n• Automatisation des workflows\n• Génération de médias\n• Traduction\n• Calculs\n\nEnvoyez-moi simplement un message ou un document pour commencer !",
      PT: "Bem-vindo ao Umbra Bot! 🤖\n\nPosso ajudá-lo com:\n• Processamento de documentos financeiros\n• Monitoramento do sistema\n• Gerenciamento de clientes\n• Automação de workflows\n• Geração de mídia\n• Tradução\n• Cálculos\n\nApenas me envie uma mensagem ou documento para começar!"
    };

    await this.telegramClient.sendMessage({
      chat_id: chatId,
      text: welcomeMessages[lang] || welcomeMessages.EN,
      parse_mode: 'Markdown'
    });
  }

  private async sendHelpMessage(chatId: number, lang: SupportedLanguage): Promise<void> {
    const helpMessages = {
      EN: "**Umbra Bot Help** 🆘\n\n**Commands:**\n/start - Welcome message\n/help - This help message\n/status - System status\n/lang - Change language\n\n**Usage:**\n• Send text for intent classification\n• Upload documents for OCR processing\n• Send photos of receipts/invoices\n• Ask for translations or calculations",
      FR: "**Aide Umbra Bot** 🆘\n\n**Commandes :**\n/start - Message de bienvenue\n/help - Ce message d'aide\n/status - État du système\n/lang - Changer de langue\n\n**Utilisation :**\n• Envoyez du texte pour la classification d'intention\n• Téléchargez des documents pour le traitement OCR\n• Envoyez des photos de reçus/factures\n• Demandez des traductions ou des calculs",
      PT: "**Ajuda do Umbra Bot** 🆘\n\n**Comandos:**\n/start - Mensagem de boas-vindas\n/help - Esta mensagem de ajuda\n/status - Status do sistema\n/lang - Alterar idioma\n\n**Uso:**\n• Envie texto para classificação de intenção\n• Faça upload de documentos para processamento OCR\n• Envie fotos de recibos/faturas\n• Peça traduções ou cálculos"
    };

    await this.telegramClient.sendMessage({
      chat_id: chatId,
      text: helpMessages[lang] || helpMessages.EN,
      parse_mode: 'Markdown'
    });
  }

  private async sendStatusMessage(chatId: number, lang: SupportedLanguage): Promise<void> {
    try {
      const moduleStatus = await this.moduleRouter.getModuleStatus();
      
      let statusText = "**System Status** 📊\n\n";
      
      for (const [module, status] of Object.entries(moduleStatus)) {
        const icon = status.available ? "✅" : "❌";
        const latency = status.latency ? ` (${status.latency}ms)` : "";
        statusText += `${icon} ${module}${latency}\n`;
      }

      await this.telegramClient.sendMessage({
        chat_id: chatId,
        text: statusText,
        parse_mode: 'Markdown'
      });
    } catch (error) {
      await this.telegramClient.sendLocalizedMessage(
        chatId,
        'error',
        { error: 'Failed to get system status' },
        lang
      );
    }
  }

  private async sendLanguageSelection(chatId: number): Promise<void> {
    const keyboard = {
      inline_keyboard: [
        [
          { text: '🇺🇸 English', callback_data: 'lang:EN' },
          { text: '🇫🇷 Français', callback_data: 'lang:FR' },
          { text: '🇵🇹 Português', callback_data: 'lang:PT' }
        ]
      ]
    };

    await this.telegramClient.sendMessage({
      chat_id: chatId,
      text: 'Select your preferred language:',
      reply_markup: keyboard
    });
  }

  private detectLanguage(languageCode?: string): SupportedLanguage {
    if (!languageCode) return 'EN';
    
    const code = languageCode.toLowerCase();
    
    if (code.startsWith('fr')) return 'FR';
    if (code.startsWith('pt')) return 'PT';
    
    return 'EN'; // Default to English
  }

  private detectDocumentType(fileName: string): string {
    const name = fileName.toLowerCase();
    
    if (name.includes('invoice') || name.includes('facture') || name.includes('fatura')) {
      return 'invoice';
    }
    if (name.includes('receipt') || name.includes('reçu') || name.includes('recibo')) {
      return 'receipt';
    }
    if (name.includes('statement') || name.includes('relevé') || name.includes('extrato')) {
      return 'statement';
    }
    if (name.includes('payroll') || name.includes('salaire') || name.includes('folha')) {
      return 'payroll';
    }
    
    return 'document'; // Default type
  }
}