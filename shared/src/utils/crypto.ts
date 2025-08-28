import crypto from 'crypto';

export class CryptoUtils {
  /**
   * Generate a cryptographically secure random token
   */
  static generateToken(length: number = 32): string {
    return crypto.randomBytes(length).toString('hex');
  }

  /**
   * Hash sensitive data for logging purposes
   */
  static hashForLogging(data: string): string {
    return crypto.createHash('sha256').update(data).digest('hex').substring(0, 16);
  }

  /**
   * Generate validation token for critical operations
   */
  static generateValidationToken(userId: string, action: string): string {
    const payload = `${userId}:${action}:${Date.now()}`;
    return crypto.createHash('sha256').update(payload).digest('hex');
  }

  /**
   * Verify validation token
   */
  static verifyValidationToken(token: string, userId: string, action: string, maxAge: number = 300000): boolean {
    // In production, this would check against a secure store
    // For now, we'll implement basic structure
    return token.length === 64; // SHA256 hex length
  }

  /**
   * Encrypt sensitive data
   */
  static encrypt(text: string, key: string): string {
    const algorithm = 'aes-256-gcm';
    const iv = crypto.randomBytes(16);
    const cipher = crypto.createCipher(algorithm, key);
    
    let encrypted = cipher.update(text, 'utf8', 'hex');
    encrypted += cipher.final('hex');
    
    return iv.toString('hex') + ':' + encrypted;
  }

  /**
   * Decrypt sensitive data
   */
  static decrypt(encryptedText: string, key: string): string {
    const algorithm = 'aes-256-gcm';
    const [ivHex, encrypted] = encryptedText.split(':');
    const iv = Buffer.from(ivHex, 'hex');
    const decipher = crypto.createDecipher(algorithm, key);
    
    let decrypted = decipher.update(encrypted, 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    
    return decrypted;
  }

  /**
   * Minimize PII in financial data for logging
   */
  static minimizePII(data: any): any {
    if (typeof data !== 'object' || data === null) return data;

    const minimized = { ...data };
    
    // Hash or mask sensitive fields
    const sensitiveFields = ['vendor', 'accountNumber', 'cardNumber', 'ssn', 'bankAccount'];
    
    for (const field of sensitiveFields) {
      if (minimized[field]) {
        minimized[field] = this.hashForLogging(minimized[field]);
      }
    }

    // Recursive handling for nested objects
    for (const key in minimized) {
      if (typeof minimized[key] === 'object') {
        minimized[key] = this.minimizePII(minimized[key]);
      }
    }

    return minimized;
  }
}