import axios, { AxiosInstance } from 'axios';
import { RetryUtils } from '../utils/retry';
import Logger from '../utils/logger';

// External API clients for Creator module

interface RunwayConfig {
  apiKey: string;
  baseUrl: string;
}

interface ShotstackConfig {
  apiKey: string;
  baseUrl: string;
}

interface ElevenLabsConfig {
  apiKey: string;
  baseUrl: string;
}

interface N8nConfig {
  apiKey: string;
  baseUrl: string;
}

/**
 * Runway AI client for video generation
 */
export class RunwayClient {
  private client: AxiosInstance;
  private logger: Logger;
  private retryConfig: any;

  constructor(config: RunwayConfig) {
    this.logger = new Logger('RunwayClient');
    this.retryConfig = RetryUtils.createRetryConfig('api');

    this.client = axios.create({
      baseURL: config.baseUrl || 'https://api.runwayml.com/v1',
      headers: {
        'Authorization': `Bearer ${config.apiKey}`,
        'Content-Type': 'application/json'
      },
      timeout: 60000
    });
  }

  async generateVideo(prompt: string, duration: number = 4): Promise<{
    id: string;
    status: string;
    videoUrl?: string;
  }> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post('/generate', {
        prompt,
        duration,
        mode: 'text_to_video'
      });
      
      this.logger.info('Runway video generation initiated', {
        id: response.data.id,
        prompt: prompt.substring(0, 100)
      });

      return response.data;
    }, this.retryConfig);
  }

  async getVideoStatus(id: string): Promise<{
    status: string;
    videoUrl?: string;
    progress?: number;
  }> {
    return RetryUtils.retry(async () => {
      const response = await this.client.get(`/generate/${id}`);
      return response.data;
    }, this.retryConfig);
  }
}

/**
 * Shotstack client for video editing
 */
export class ShotstackClient {
  private client: AxiosInstance;
  private logger: Logger;
  private retryConfig: any;

  constructor(config: ShotstackConfig) {
    this.logger = new Logger('ShotstackClient');
    this.retryConfig = RetryUtils.createRetryConfig('api');

    this.client = axios.create({
      baseURL: config.baseUrl || 'https://api.shotstack.io/v1',
      headers: {
        'x-api-key': config.apiKey,
        'Content-Type': 'application/json'
      },
      timeout: 60000
    });
  }

  async renderVideo(timeline: any): Promise<{
    id: string;
    status: string;
  }> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post('/render', {
        timeline,
        output: {
          format: 'mp4',
          resolution: 'hd'
        }
      });

      this.logger.info('Shotstack render initiated', {
        id: response.data.response.id
      });

      return response.data.response;
    }, this.retryConfig);
  }

  async getRenderStatus(id: string): Promise<{
    status: string;
    url?: string;
    progress?: number;
  }> {
    return RetryUtils.retry(async () => {
      const response = await this.client.get(`/render/${id}`);
      return response.data.response;
    }, this.retryConfig);
  }

  /**
   * Create timeline for video with narration and subtitles
   */
  createTimelineWithNarration(videoClips: string[], audioUrl: string, subtitles?: any[]): any {
    const tracks = [
      {
        clips: videoClips.map((url, index) => ({
          asset: {
            type: 'video',
            src: url
          },
          start: index * 4, // 4 seconds per clip
          length: 4
        }))
      },
      {
        clips: [{
          asset: {
            type: 'audio',
            src: audioUrl
          },
          start: 0,
          length: videoClips.length * 4
        }]
      }
    ];

    if (subtitles && subtitles.length > 0) {
      tracks.push({
        clips: subtitles.map((subtitle: any) => ({
          asset: {
            type: 'title',
            text: subtitle.text,
            style: 'subtitle'
          } as any,
          start: subtitle.start,
          length: subtitle.duration
        })) as any
      });
    }

    return { tracks };
  }
}

/**
 * ElevenLabs client for text-to-speech
 */
export class ElevenLabsClient {
  private client: AxiosInstance;
  private logger: Logger;
  private retryConfig: any;

  constructor(config: ElevenLabsConfig) {
    this.logger = new Logger('ElevenLabsClient');
    this.retryConfig = RetryUtils.createRetryConfig('api');

    this.client = axios.create({
      baseURL: config.baseUrl || 'https://api.elevenlabs.io/v1',
      headers: {
        'xi-api-key': config.apiKey,
        'Content-Type': 'application/json'
      },
      timeout: 30000
    });
  }

  async synthesizeSpeech(
    text: string,
    voiceId: string = 'EXAVITQu4vr4xnSDxMaL',
    language: 'EN' | 'FR' | 'PT' = 'EN'
  ): Promise<Buffer> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post(`/text-to-speech/${voiceId}`, {
        text,
        model_id: 'eleven_multilingual_v2',
        voice_settings: {
          stability: 0.5,
          similarity_boost: 0.5
        }
      }, {
        responseType: 'arraybuffer'
      });

      this.logger.info('ElevenLabs speech synthesis completed', {
        textLength: text.length,
        voiceId,
        language
      });

      return Buffer.from(response.data);
    }, this.retryConfig);
  }

  async getVoices(): Promise<any[]> {
    return RetryUtils.retry(async () => {
      const response = await this.client.get('/voices');
      return response.data.voices;
    }, this.retryConfig);
  }
}

/**
 * n8n client for workflow management
 */
export class N8nClient {
  private client: AxiosInstance;
  private logger: Logger;
  private retryConfig: any;

  constructor(config: N8nConfig) {
    this.logger = new Logger('N8nClient');
    this.retryConfig = RetryUtils.createRetryConfig('api');

    this.client = axios.create({
      baseURL: config.baseUrl,
      headers: {
        'X-N8N-API-KEY': config.apiKey,
        'Content-Type': 'application/json'
      },
      timeout: 30000
    });
  }

  async createWorkflow(workflow: any): Promise<{
    id: string;
    name: string;
    active: boolean;
  }> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post('/workflows', workflow);
      
      this.logger.info('n8n workflow created', {
        id: response.data.id,
        name: response.data.name
      });

      return response.data;
    }, this.retryConfig);
  }

  async updateWorkflow(id: string, workflow: any): Promise<any> {
    return RetryUtils.retry(async () => {
      const response = await this.client.put(`/workflows/${id}`, workflow);
      return response.data;
    }, this.retryConfig);
  }

  async activateWorkflow(id: string): Promise<any> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post(`/workflows/${id}/activate`);
      return response.data;
    }, this.retryConfig);
  }

  async deactivateWorkflow(id: string): Promise<any> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post(`/workflows/${id}/deactivate`);
      return response.data;
    }, this.retryConfig);
  }

  async testWorkflow(id: string): Promise<any> {
    return RetryUtils.retry(async () => {
      const response = await this.client.post(`/workflows/${id}/test`);
      return response.data;
    }, this.retryConfig);
  }

  async getWorkflow(id: string): Promise<any> {
    return RetryUtils.retry(async () => {
      const response = await this.client.get(`/workflows/${id}`);
      return response.data;
    }, this.retryConfig);
  }

  async listWorkflows(): Promise<any[]> {
    return RetryUtils.retry(async () => {
      const response = await this.client.get('/workflows');
      return response.data;
    }, this.retryConfig);
  }

  async deleteWorkflow(id: string): Promise<void> {
    return RetryUtils.retry(async () => {
      await this.client.delete(`/workflows/${id}`);
    }, this.retryConfig);
  }

  async validateWorkflow(workflow: any): Promise<{
    valid: boolean;
    errors: string[];
  }> {
    try {
      // Basic validation - check for required fields
      const errors: string[] = [];

      if (!workflow.name) {
        errors.push('Workflow name is required');
      }

      if (!workflow.nodes || !Array.isArray(workflow.nodes)) {
        errors.push('Workflow must have nodes array');
      }

      if (!workflow.connections || typeof workflow.connections !== 'object') {
        errors.push('Workflow must have connections object');
      }

      // Check for required node types
      const hasStartNode = workflow.nodes?.some((node: any) => 
        node.type === 'n8n-nodes-base.start' || node.type === 'n8n-nodes-base.trigger'
      );

      if (!hasStartNode) {
        errors.push('Workflow must have a start or trigger node');
      }

      return {
        valid: errors.length === 0,
        errors
      };
    } catch (error) {
      this.logger.error('Workflow validation error', { error: (error as Error).message });
      return {
        valid: false,
        errors: ['Validation failed: ' + (error as Error).message]
      };
    }
  }
}