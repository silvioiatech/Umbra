import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';
import { RetryUtils } from '../utils/retry';
import Logger from '../utils/logger';

interface OpenRouterConfig {
  apiKey: string;
  baseUrl: string;
}

interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

interface ChatCompletionRequest {
  model: string;
  messages: ChatMessage[];
  max_tokens?: number;
  temperature?: number;
  stream?: boolean;
}

interface ChatCompletionResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: {
    index: number;
    message: ChatMessage;
    finish_reason: string;
  }[];
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

export class OpenRouterClient {
  private client: AxiosInstance;
  private logger: Logger;
  private retryConfig: any;

  constructor(config: OpenRouterConfig) {
    this.logger = new Logger('OpenRouterClient');
    this.retryConfig = RetryUtils.createRetryConfig('api');

    this.client = axios.create({
      baseURL: config.baseUrl || 'https://openrouter.ai/api/v1',
      headers: {
        'Authorization': `Bearer ${config.apiKey}`,
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://umbra-bot.com',
        'X-Title': 'Umbra Bot System'
      },
      timeout: 30000
    });

    // Add request interceptor for logging
    this.client.interceptors.request.use(
      (config) => {
        this.logger.debug('OpenRouter API request', {
          url: config.url,
          method: config.method
        });
        return config;
      },
      (error) => {
        this.logger.error('OpenRouter request error', { error: error.message });
        return Promise.reject(error);
      }
    );

    // Add response interceptor for logging
    this.client.interceptors.response.use(
      (response) => {
        this.logger.debug('OpenRouter API response', {
          status: response.status,
          url: response.config.url
        });
        return response;
      },
      (error) => {
        this.logger.error('OpenRouter response error', {
          status: error.response?.status,
          message: error.message,
          url: error.config?.url
        });
        return Promise.reject(error);
      }
    );
  }

  /**
   * Create chat completion with Claude for planning and validation
   */
  async createChatCompletion(request: ChatCompletionRequest): Promise<ChatCompletionResponse> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post('/chat/completions', request);
      return response.data;
    }, this.retryConfig);
  }

  /**
   * Generate text using Claude for planning tasks
   */
  async generateText(prompt: string, model: string = 'anthropic/claude-3-sonnet'): Promise<string> {
    const request: ChatCompletionRequest = {
      model,
      messages: [{ role: 'user', content: prompt }],
      max_tokens: 4000,
      temperature: 0.7
    };

    const response = await this.createChatCompletion(request);
    return response.choices[0]?.message?.content || '';
  }

  /**
   * Generate structured JSON using GPT for n8n workflows
   */
  async generateJSON(prompt: string, model: string = 'openai/gpt-4'): Promise<any> {
    const request: ChatCompletionRequest = {
      model,
      messages: [
        {
          role: 'system',
          content: 'You are a precise JSON generator. Return only valid JSON without any explanations or markdown formatting.'
        },
        { role: 'user', content: prompt }
      ],
      max_tokens: 4000,
      temperature: 0.1 // Low temperature for consistency
    };

    const response = await this.createChatCompletion(request);
    const content = response.choices[0]?.message?.content || '{}';
    
    try {
      return JSON.parse(content);
    } catch (error) {
      this.logger.error('Failed to parse JSON response', { content, error: (error as Error).message });
      throw new Error('Invalid JSON response from OpenRouter');
    }
  }

  /**
   * Analyze image using vision-capable models
   */
  async analyzeImage(imageUrl: string, prompt: string, model: string = 'openai/gpt-4-vision-preview'): Promise<string> {
    const request = {
      model,
      messages: [
        {
          role: 'user',
          content: [
            { type: 'text', text: prompt },
            { type: 'image_url', image_url: { url: imageUrl } }
          ]
        }
      ],
      max_tokens: 2000
    };

    const response = await this.createChatCompletion(request as any);
    return response.choices[0]?.message?.content || '';
  }

  /**
   * Translate text to supported languages
   */
  async translateText(text: string, targetLang: 'EN' | 'FR' | 'PT', model: string = 'anthropic/claude-3-haiku'): Promise<string> {
    const langMap = {
      'EN': 'English',
      'FR': 'French', 
      'PT': 'Portuguese'
    };

    const prompt = `Translate the following text to ${langMap[targetLang]}. Return only the translation:\n\n${text}`;
    
    return this.generateText(prompt, model);
  }

  /**
   * Classify user intent for routing decisions
   */
  async classifyIntent(message: string, language: 'EN' | 'FR' | 'PT'): Promise<{
    intent: string;
    confidence: number;
    targetModule: string;
  }> {
    const prompt = `
Analyze this user message and classify the intent. Respond with JSON only:

Message: "${message}"
Language: ${language}

Return JSON with:
{
  "intent": "specific_intent_name",
  "confidence": 0.0-1.0,
  "targetModule": "finance|concierge|business|production|creator|umbra"
}

Intents:
- finance_ocr: OCR processing, document extraction
- finance_report: Financial reporting, VAT, taxes
- vps_monitor: System monitoring, status checks
- vps_execute: Running commands, managing containers  
- client_manage: Creating/managing client containers
- workflow_create: Building n8n workflows
- media_generate: Creating images, videos, audio
- translation: Text translation
- calculation: Simple math operations
- clarification_needed: Unclear or ambiguous requests
`;

    const response = await this.generateJSON(prompt);
    
    // Validate response structure
    if (!response.intent || typeof response.confidence !== 'number' || !response.targetModule) {
      throw new Error('Invalid intent classification response');
    }

    return response;
  }

  /**
   * Get available models
   */
  async getModels(): Promise<any[]> {
    return RetryUtils.retry(async () => {
      const response = await this.client.get('/models');
      return response.data.data || [];
    }, this.retryConfig);
  }

  /**
   * Get usage statistics
   */
  async getUsage(): Promise<any> {
    return RetryUtils.retry(async () => {
      const response = await this.client.get('/usage');
      return response.data;
    }, this.retryConfig);
  }
}