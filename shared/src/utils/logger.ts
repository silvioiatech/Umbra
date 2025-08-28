interface LogLevel {
  ERROR: 0;
  WARN: 1;
  INFO: 2;
  DEBUG: 3;
}

const LOG_LEVELS: LogLevel = {
  ERROR: 0,
  WARN: 1,
  INFO: 2,
  DEBUG: 3
};

class Logger {
  private level: number;
  private serviceName: string;

  constructor(serviceName: string, level: string = 'info') {
    this.serviceName = serviceName;
    this.level = LOG_LEVELS[level.toUpperCase() as keyof LogLevel] ?? LOG_LEVELS.INFO;
  }

  private log(level: string, message: string, meta?: any): void {
    const levelNum = LOG_LEVELS[level.toUpperCase() as keyof LogLevel];
    if (levelNum > this.level) return;

    const timestamp = new Date().toISOString();
    const logEntry = {
      timestamp,
      level: level.toUpperCase(),
      service: this.serviceName,
      message,
      ...(meta && { meta })
    };

    console.log(JSON.stringify(logEntry));
  }

  error(message: string, meta?: any): void {
    this.log('ERROR', message, meta);
  }

  warn(message: string, meta?: any): void {
    this.log('WARN', message, meta);
  }

  info(message: string, meta?: any): void {
    this.log('INFO', message, meta);
  }

  debug(message: string, meta?: any): void {
    this.log('DEBUG', message, meta);
  }

  // Audit logging for tracking operations across services
  audit(operation: string, userId: string, meta?: any): void {
    this.info(`AUDIT: ${operation}`, {
      userId,
      operation,
      audit: true,
      ...meta
    });
  }
}

export default Logger;