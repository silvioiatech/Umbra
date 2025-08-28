import Logger from './logger';

interface RetryOptions {
  maxRetries: number;
  baseDelay: number;
  maxDelay: number;
  retryableErrors?: string[];
  onRetry?: (error: Error, attempt: number) => void;
}

export class RetryUtils {
  private static logger = new Logger('RetryUtils');

  /**
   * Retry a function with exponential backoff
   */
  static async retry<T>(
    fn: () => Promise<T>,
    options: RetryOptions
  ): Promise<T> {
    const {
      maxRetries,
      baseDelay,
      maxDelay,
      retryableErrors,
      onRetry
    } = options;

    let lastError: Error;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const result = await fn();
        if (attempt > 0) {
          this.logger.info(`Operation succeeded after ${attempt} retries`);
        }
        return result;
      } catch (error) {
        lastError = error as Error;

        // Check if error is retryable
        if (retryableErrors && !this.isRetryableError(lastError, retryableErrors)) {
          this.logger.warn('Non-retryable error encountered', { error: lastError.message });
          throw lastError;
        }

        // Don't retry on final attempt
        if (attempt === maxRetries) {
          this.logger.error(`Operation failed after ${maxRetries} retries`, { error: lastError.message });
          break;
        }

        // Calculate delay with exponential backoff
        const delay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
        
        this.logger.warn(`Attempt ${attempt + 1} failed, retrying in ${delay}ms`, {
          error: lastError.message,
          attempt: attempt + 1
        });

        if (onRetry) {
          onRetry(lastError, attempt + 1);
        }

        await this.sleep(delay);
      }
    }

    throw lastError;
  }

  /**
   * Create retry configuration for different error types
   */
  static createRetryConfig(errorType: 'technical' | 'api' | 'network'): RetryOptions {
    const configs = {
      technical: {
        maxRetries: 3,
        baseDelay: 5000,  // 5s
        maxDelay: 30000,  // 30s
        retryableErrors: ['500', '502', '503', '504', 'ECONNRESET', 'ETIMEDOUT']
      },
      api: {
        maxRetries: 2,
        baseDelay: 1000,  // 1s
        maxDelay: 15000,  // 15s
        retryableErrors: ['429', '500', '502', '503', '504']
      },
      network: {
        maxRetries: 3,
        baseDelay: 2000,  // 2s
        maxDelay: 10000,  // 10s
        retryableErrors: ['ENOTFOUND', 'ECONNRESET', 'ETIMEDOUT', 'ECONNREFUSED']
      }
    };

    return configs[errorType];
  }

  /**
   * Circuit breaker for preventing cascading failures
   */
  static createCircuitBreaker(failureThreshold: number = 5, resetTimeout: number = 60000) {
    let failures = 0;
    let lastFailureTime = 0;
    let state: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';

    return async <T>(fn: () => Promise<T>): Promise<T> => {
      const now = Date.now();

      // Reset circuit breaker if enough time has passed
      if (state === 'OPEN' && now - lastFailureTime >= resetTimeout) {
        state = 'HALF_OPEN';
        failures = 0;
        this.logger.info('Circuit breaker moving to HALF_OPEN state');
      }

      // Reject immediately if circuit is open
      if (state === 'OPEN') {
        throw new Error('Circuit breaker is OPEN - rejecting request');
      }

      try {
        const result = await fn();
        
        // Reset on success
        if (state === 'HALF_OPEN') {
          state = 'CLOSED';
          failures = 0;
          this.logger.info('Circuit breaker reset to CLOSED state');
        }
        
        return result;
      } catch (error) {
        failures++;
        lastFailureTime = now;

        if (failures >= failureThreshold) {
          state = 'OPEN';
          this.logger.warn(`Circuit breaker opened due to ${failures} failures`);
        }

        throw error;
      }
    };
  }

  private static isRetryableError(error: Error, retryableErrors: string[]): boolean {
    const errorMessage = error.message.toLowerCase();
    const errorCode = (error as any).code || '';
    const statusCode = (error as any).status || (error as any).statusCode || '';

    return retryableErrors.some(retryableError => 
      errorMessage.includes(retryableError.toLowerCase()) ||
      errorCode === retryableError ||
      statusCode.toString() === retryableError
    );
  }

  private static sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Validate input parameters before retrying operations
   */
  static validateRetryParams(options: Partial<RetryOptions>): RetryOptions {
    return {
      maxRetries: Math.min(options.maxRetries || 3, 10), // Cap at 10 retries
      baseDelay: Math.max(options.baseDelay || 1000, 100), // Min 100ms
      maxDelay: Math.min(options.maxDelay || 30000, 300000), // Max 5 minutes
      retryableErrors: options.retryableErrors || ['500', '502', '503', '504'],
      onRetry: options.onRetry
    };
  }
}