import { S3Client, PutObjectCommand, GetObjectCommand, DeleteObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';
import Logger from '../utils/logger';
import { RetryUtils } from '../utils/retry';

interface StorageConfig {
  endpoint: string;
  accessKey: string;
  secretKey: string;
  bucket: string;
  region: string;
}

interface UploadOptions {
  key: string;
  body: Buffer | Uint8Array | string;
  contentType?: string;
  metadata?: Record<string, string>;
  prefix?: 'temp' | 'reports' | 'media' | 'documents';
}

interface SignedUrlOptions {
  key: string;
  expiresIn?: number; // seconds, default 3600 (1 hour)
  operation?: 'getObject' | 'putObject';
}

export class StorageClient {
  private s3: S3Client;
  private bucket: string;
  private logger: Logger;
  private retryConfig: any;

  constructor(config: StorageConfig) {
    this.logger = new Logger('StorageClient');
    this.bucket = config.bucket;
    this.retryConfig = RetryUtils.createRetryConfig('network');

    this.s3 = new S3Client({
      endpoint: config.endpoint,
      region: config.region,
      credentials: {
        accessKeyId: config.accessKey,
        secretAccessKey: config.secretKey
      },
      forcePathStyle: true // Required for some S3-compatible services
    });
  }

  /**
   * Upload file to storage with automatic prefix handling
   */
  async uploadFile(options: UploadOptions): Promise<{
    key: string;
    url: string;
    size: number;
  }> {
    const { key, body, contentType, metadata, prefix } = options;
    const fullKey = prefix ? `${prefix}/${key}` : key;

    const bodyBuffer = Buffer.isBuffer(body) ? body : Buffer.from(body);

    return RetryUtils.retry(async () => {
      const command = new PutObjectCommand({
        Bucket: this.bucket,
        Key: fullKey,
        Body: bodyBuffer,
        ContentType: contentType || 'application/octet-stream',
        Metadata: metadata || {}
      });

      await this.s3.send(command);

      this.logger.info('File uploaded successfully', {
        key: fullKey,
        size: bodyBuffer.length,
        contentType
      });

      return {
        key: fullKey,
        url: await this.getSignedUrl({ key: fullKey }),
        size: bodyBuffer.length
      };
    }, this.retryConfig);
  }

  /**
   * Get signed URL for secure access
   */
  async getSignedUrl(options: SignedUrlOptions): Promise<string> {
    const { key, expiresIn = 3600, operation = 'getObject' } = options;

    return RetryUtils.retry(async () => {
      const command = operation === 'getObject' 
        ? new GetObjectCommand({ Bucket: this.bucket, Key: key })
        : new PutObjectCommand({ Bucket: this.bucket, Key: key });

      const url = await getSignedUrl(this.s3, command, { expiresIn });

      this.logger.debug('Generated signed URL', {
        key,
        operation,
        expiresIn
      });

      return url;
    }, this.retryConfig);
  }

  /**
   * Download file from storage
   */
  async downloadFile(key: string): Promise<Buffer> {
    return RetryUtils.retry(async () => {
      const command = new GetObjectCommand({
        Bucket: this.bucket,
        Key: key
      });

      const response = await this.s3.send(command);
      
      if (!response.Body) {
        throw new Error(`No body in response for key: ${key}`);
      }

      // Convert stream to buffer
      const chunks: Uint8Array[] = [];
      for await (const chunk of response.Body as any) {
        chunks.push(chunk);
      }

      const buffer = Buffer.concat(chunks);

      this.logger.info('File downloaded successfully', {
        key,
        size: buffer.length
      });

      return buffer;
    }, this.retryConfig);
  }

  /**
   * Delete file from storage
   */
  async deleteFile(key: string): Promise<void> {
    return RetryUtils.retry(async () => {
      const command = new DeleteObjectCommand({
        Bucket: this.bucket,
        Key: key
      });

      await this.s3.send(command);

      this.logger.info('File deleted successfully', { key });
    }, this.retryConfig);
  }

  /**
   * Upload financial document with proper lifecycle
   */
  async uploadFinancialDocument(
    fileName: string,
    document: Buffer,
    metadata: {
      userId: string;
      documentType: string;
      uploadedAt: string;
    }
  ): Promise<{ key: string; url: string }> {
    const key = `${metadata.userId}/${Date.now()}-${fileName}`;
    
    const result = await this.uploadFile({
      key,
      body: document,
      contentType: this.getContentType(fileName),
      metadata: {
        userId: metadata.userId,
        documentType: metadata.documentType,
        uploadedAt: metadata.uploadedAt,
        retention: 'financial-docs' // 90 days
      },
      prefix: 'documents'
    });

    return {
      key: result.key,
      url: result.url
    };
  }

  /**
   * Upload media with proper lifecycle
   */
  async uploadMedia(
    fileName: string,
    media: Buffer,
    metadata: {
      userId: string;
      mediaType: string;
      provider?: string;
    }
  ): Promise<{ key: string; url: string }> {
    const key = `${metadata.userId}/${Date.now()}-${fileName}`;
    
    const result = await this.uploadFile({
      key,
      body: media,
      contentType: this.getContentType(fileName),
      metadata: {
        userId: metadata.userId,
        mediaType: metadata.mediaType,
        provider: metadata.provider || 'unknown',
        retention: 'media-files' // 30 days
      },
      prefix: 'media'
    });

    return {
      key: result.key,
      url: result.url
    };
  }

  /**
   * Upload temporary file with short lifecycle
   */
  async uploadTempFile(
    fileName: string,
    data: Buffer,
    userId: string
  ): Promise<{ key: string; url: string }> {
    const key = `${userId}/${Date.now()}-${fileName}`;
    
    const result = await this.uploadFile({
      key,
      body: data,
      contentType: this.getContentType(fileName),
      metadata: {
        userId,
        retention: 'temp-files' // 7 days
      },
      prefix: 'temp'
    });

    return {
      key: result.key,
      url: result.url
    };
  }

  /**
   * Generate report upload with extended lifecycle
   */
  async uploadReport(
    reportName: string,
    reportData: Buffer | string,
    metadata: {
      userId: string;
      reportType: string;
      generatedAt: string;
    }
  ): Promise<{ key: string; url: string }> {
    const key = `${metadata.userId}/${metadata.reportType}/${Date.now()}-${reportName}`;
    
    const result = await this.uploadFile({
      key,
      body: typeof reportData === 'string' ? Buffer.from(reportData) : reportData,
      contentType: 'application/pdf',
      metadata: {
        userId: metadata.userId,
        reportType: metadata.reportType,
        generatedAt: metadata.generatedAt,
        retention: 'reports' // 90 days
      },
      prefix: 'reports'
    });

    return {
      key: result.key,
      url: result.url
    };
  }

  private getContentType(fileName: string): string {
    const ext = fileName.split('.').pop()?.toLowerCase();
    const contentTypes: Record<string, string> = {
      'pdf': 'application/pdf',
      'jpg': 'image/jpeg',
      'jpeg': 'image/jpeg',
      'png': 'image/png',
      'gif': 'image/gif',
      'mp4': 'video/mp4',
      'avi': 'video/avi',
      'mov': 'video/quicktime',
      'mp3': 'audio/mpeg',
      'wav': 'audio/wav',
      'json': 'application/json',
      'txt': 'text/plain',
      'csv': 'text/csv',
      'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    };

    return contentTypes[ext || ''] || 'application/octet-stream';
  }
}