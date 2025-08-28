import axios, { AxiosInstance } from 'axios';
import { RetryUtils } from '../utils/retry';
import Logger from '../utils/logger';

interface TelegramConfig {
  botToken: string;
  webhookUrl?: string;
}

interface SendMessageOptions {
  chat_id: string | number;
  text: string;
  parse_mode?: 'HTML' | 'Markdown' | 'MarkdownV2';
  reply_markup?: any;
  disable_web_page_preview?: boolean;
}

interface SendDocumentOptions {
  chat_id: string | number;
  document: string; // URL or file_id
  caption?: string;
  parse_mode?: 'HTML' | 'Markdown' | 'MarkdownV2';
}

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
    document?: {
      file_name?: string;
      mime_type?: string;
      file_id: string;
      file_unique_id: string;
      file_size?: number;
    };
    photo?: Array<{
      file_id: string;
      file_unique_id: string;
      width: number;
      height: number;
      file_size?: number;
    }>;
  };
}

export class TelegramClient {
  private client: AxiosInstance;
  private logger: Logger;
  private retryConfig: any;
  private botToken: string;

  constructor(config: TelegramConfig) {
    this.botToken = config.botToken;
    this.logger = new Logger('TelegramClient');
    this.retryConfig = RetryUtils.createRetryConfig('api');

    this.client = axios.create({
      baseURL: `https://api.telegram.org/bot${config.botToken}`,
      timeout: 30000
    });

    // Add request/response interceptors
    this.client.interceptors.request.use(
      (config) => {
        this.logger.debug('Telegram API request', {
          url: config.url,
          method: config.method
        });
        return config;
      }
    );

    this.client.interceptors.response.use(
      (response) => {
        this.logger.debug('Telegram API response', {
          status: response.status,
          url: response.config.url
        });
        return response;
      },
      (error) => {
        this.logger.error('Telegram API error', {
          status: error.response?.status,
          message: error.message,
          url: error.config?.url
        });
        return Promise.reject(error);
      }
    );
  }

  /**
   * Send text message to user
   */
  async sendMessage(options: SendMessageOptions): Promise<any> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post('/sendMessage', options);
      return response.data;
    }, this.retryConfig);
  }

  /**
   * Send document to user
   */
  async sendDocument(options: SendDocumentOptions): Promise<any> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post('/sendDocument', options);
      return response.data;
    }, this.retryConfig);
  }

  /**
   * Send photo to user
   */
  async sendPhoto(chatId: string | number, photoUrl: string, caption?: string): Promise<any> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post('/sendPhoto', {
        chat_id: chatId,
        photo: photoUrl,
        caption
      });
      return response.data;
    }, this.retryConfig);
  }

  /**
   * Send video to user
   */
  async sendVideo(chatId: string | number, videoUrl: string, caption?: string): Promise<any> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post('/sendVideo', {
        chat_id: chatId,
        video: videoUrl,
        caption
      });
      return response.data;
    }, this.retryConfig);
  }

  /**
   * Send audio to user
   */
  async sendAudio(chatId: string | number, audioUrl: string, caption?: string): Promise<any> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post('/sendAudio', {
        chat_id: chatId,
        audio: audioUrl,
        caption
      });
      return response.data;
    }, this.retryConfig);
  }

  /**
   * Get file information
   */
  async getFile(fileId: string): Promise<any> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post('/getFile', { file_id: fileId });
      return response.data;
    }, this.retryConfig);
  }

  /**
   * Download file from Telegram
   */
  async downloadFile(filePath: string): Promise<Buffer> {
    return RetryUtils.retry(async () => {
      const response = await axios.get(`https://api.telegram.org/file/bot${this.botToken}/${filePath}`, {
        responseType: 'arraybuffer'
      });
      return Buffer.from(response.data);
    }, this.retryConfig);
  }

  /**
   * Set webhook for receiving updates
   */
  async setWebhook(webhookUrl: string): Promise<any> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post('/setWebhook', {
        url: webhookUrl,
        allowed_updates: ['message', 'callback_query']
      });
      return response.data;
    }, this.retryConfig);
  }

  /**
   * Delete webhook
   */
  async deleteWebhook(): Promise<any> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post('/deleteWebhook');
      return response.data;
    }, this.retryConfig);
  }

  /**
   * Get bot information
   */
  async getMe(): Promise<any> {
    return RetryUtils.retry(async () => {
      const response = await this.client.get('/getMe');
      return response.data;
    }, this.retryConfig);
  }

  /**
   * Send typing action
   */
  async sendChatAction(chatId: string | number, action: 'typing' | 'upload_photo' | 'upload_video' | 'upload_audio' | 'upload_document'): Promise<any> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post('/sendChatAction', {
        chat_id: chatId,
        action
      });
      return response.data;
    }, this.retryConfig);
  }

  /**
   * Format message for different languages
   */
  formatMessage(template: string, params: Record<string, any>, lang: 'EN' | 'FR' | 'PT'): string {
    const translations = {
      EN: {
        processing: 'Processing your request...',
        error: 'An error occurred: {error}',
        success: 'Operation completed successfully',
        validation_required: 'This operation requires validation. Please confirm with: {token}',
        invalid_format: 'Invalid file format. Supported formats: {formats}',
        file_too_large: 'File too large. Maximum size: {maxSize}MB',
        ocr_complete: 'Document processed. Found: {data}',
        workflow_created: 'Workflow created successfully: {workflowId}',
        media_generated: 'Media generated: {mediaUrl}',
        system_status: 'System Status:\nCPU: {cpu}%\nMemory: {memory}%\nDisk: {disk}%'
      },
      FR: {
        processing: 'Traitement de votre demande...',
        error: 'Une erreur est survenue : {error}',
        success: 'Opération terminée avec succès',
        validation_required: 'Cette opération nécessite une validation. Veuillez confirmer avec : {token}',
        invalid_format: 'Format de fichier invalide. Formats supportés : {formats}',
        file_too_large: 'Fichier trop volumineux. Taille maximale : {maxSize}MB',
        ocr_complete: 'Document traité. Trouvé : {data}',
        workflow_created: 'Workflow créé avec succès : {workflowId}',
        media_generated: 'Média généré : {mediaUrl}',
        system_status: 'État du système :\nCPU : {cpu}%\nMémoire : {memory}%\nDisque : {disk}%'
      },
      PT: {
        processing: 'Processando sua solicitação...',
        error: 'Ocorreu um erro: {error}',
        success: 'Operação concluída com sucesso',
        validation_required: 'Esta operação requer validação. Confirme com: {token}',
        invalid_format: 'Formato de arquivo inválido. Formatos suportados: {formats}',
        file_too_large: 'Arquivo muito grande. Tamanho máximo: {maxSize}MB',
        ocr_complete: 'Documento processado. Encontrado: {data}',
        workflow_created: 'Workflow criado com sucesso: {workflowId}',
        media_generated: 'Mídia gerada: {mediaUrl}',
        system_status: 'Status do Sistema:\nCPU: {cpu}%\nMemória: {memory}%\nDisco: {disk}%'
      }
    };

    let message = translations[lang][template as keyof typeof translations[typeof lang]] || template;
    
    // Replace parameters
    for (const [key, value] of Object.entries(params)) {
      message = message.replace(new RegExp(`{${key}}`, 'g'), String(value));
    }

    return message;
  }

  /**
   * Send localized message
   */
  async sendLocalizedMessage(
    chatId: string | number,
    template: string,
    params: Record<string, any> = {},
    lang: 'EN' | 'FR' | 'PT' = 'EN'
  ): Promise<any> {
    const message = this.formatMessage(template, params, lang);
    return this.sendMessage({
      chat_id: chatId,
      text: message,
      parse_mode: 'HTML'
    });
  }

  /**
   * Send validation request for critical operations
   */
  async sendValidationRequest(
    chatId: string | number,
    action: string,
    token: string,
    lang: 'EN' | 'FR' | 'PT' = 'EN'
  ): Promise<any> {
    const keyboard = {
      inline_keyboard: [
        [
          { text: '✅ Confirm', callback_data: `validate:${token}:confirm` },
          { text: '❌ Cancel', callback_data: `validate:${token}:cancel` }
        ]
      ]
    };

    return this.sendLocalizedMessage(
      chatId,
      'validation_required',
      { action, token },
      lang
    ).then(() => {
      return this.sendMessage({
        chat_id: chatId,
        text: '⚠️ Critical Operation Validation Required',
        reply_markup: keyboard
      });
    });
  }

  /**
   * Parse incoming update
   */
  parseUpdate(update: TelegramUpdate): {
    messageId?: number;
    userId?: number;
    chatId?: number;
    text?: string;
    document?: any;
    photo?: any;
    username?: string;
    language?: string;
  } {
    if (!update.message) return {};

    return {
      messageId: update.message.message_id,
      userId: update.message.from.id,
      chatId: update.message.chat.id,
      text: update.message.text,
      document: update.message.document,
      photo: update.message.photo,
      username: update.message.from.username,
      language: update.message.from.language_code
    };
  }
}