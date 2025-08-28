import { Client } from 'ssh2';
import Logger from '@umbra/shared/src/utils/logger';

export interface VPSConfig {
  host: string;
  username: string;
  privateKey: string;
  port: number;
}

export interface CommandResult {
  stdout: string;
  stderr: string;
  exitCode: number;
  duration: number;
}

export interface ContainerStatus {
  name: string;
  status: string;
  image: string;
  ports: string[];
  created: string;
  size: string;
}

export class VPSManager {
  private logger: Logger;
  private config: VPSConfig;
  private connections: Map<string, Client> = new Map();

  constructor(config: VPSConfig) {
    this.config = config;
    this.logger = new Logger('VPSManager');
  }

  /**
   * Execute a command on the VPS
   */
  async executeCommand(command: string, options: any = {}): Promise<CommandResult> {
    const startTime = Date.now();
    
    return new Promise((resolve, reject) => {
      const conn = new Client();
      
      conn.on('ready', () => {
        this.logger.debug('SSH connection established for command execution');
        
        conn.exec(command, { pty: options.pty || false }, (err, stream) => {
          if (err) {
            this.logger.error('Command execution failed', { command, error: err.message });
            conn.end();
            return reject(err);
          }

          let stdout = '';
          let stderr = '';

          stream.on('close', (code: number) => {
            const duration = Date.now() - startTime;
            
            this.logger.info('Command executed', { 
              command: command.substring(0, 50) + '...',
              exitCode: code,
              duration 
            });

            conn.end();
            resolve({
              stdout,
              stderr,
              exitCode: code,
              duration
            });
          });

          stream.on('data', (data: Buffer) => {
            stdout += data.toString();
          });

          stream.stderr.on('data', (data: Buffer) => {
            stderr += data.toString();
          });
        });
      });

      conn.on('error', (err) => {
        this.logger.error('SSH connection failed', { error: err.message });
        reject(err);
      });

      conn.connect({
        host: this.config.host,
        username: this.config.username,
        privateKey: this.config.privateKey,
        port: this.config.port
      });
    });
  }

  /**
   * Get container status
   */
  async getContainerStatus(containerName: string): Promise<ContainerStatus | null> {
    try {
      const result = await this.executeCommand(`docker inspect ${containerName} --format "{{json .}}"`);
      
      if (result.exitCode !== 0) {
        return null;
      }

      const containerInfo = JSON.parse(result.stdout);
      
      return {
        name: containerInfo.Name.replace('/', ''),
        status: containerInfo.State.Status,
        image: containerInfo.Config.Image,
        ports: Object.keys(containerInfo.NetworkSettings.Ports || {}),
        created: containerInfo.Created,
        size: 'unknown' // Would need additional call to get size
      };
    } catch (error) {
      this.logger.error('Failed to get container status', { 
        containerName, 
        error: (error as Error).message 
      });
      throw error;
    }
  }

  /**
   * Start a container
   */
  async startContainer(containerName: string, options: any = {}): Promise<CommandResult> {
    let command = `docker start ${containerName}`;
    
    if (options.attach) {
      command += ' -a';
    }
    
    return this.executeCommand(command);
  }

  /**
   * Stop a container
   */
  async stopContainer(containerName: string): Promise<CommandResult> {
    return this.executeCommand(`docker stop ${containerName}`);
  }

  /**
   * Restart a container
   */
  async restartContainer(containerName: string): Promise<CommandResult> {
    return this.executeCommand(`docker restart ${containerName}`);
  }

  /**
   * Get container logs
   */
  async getContainerLogs(containerName: string, options: any = {}): Promise<CommandResult> {
    let command = `docker logs ${containerName}`;
    
    if (options.tail) {
      command += ` --tail ${options.tail}`;
    }
    
    if (options.follow) {
      command += ' -f';
    }
    
    return this.executeCommand(command);
  }

  /**
   * Validate a script before execution
   */
  async validateScript(script: string, scriptType: string, options: any = {}): Promise<any> {
    try {
      const validationResult = {
        valid: true,
        warnings: [] as string[],
        errors: [] as string[],
        suggestions: [] as string[]
      };

      // Basic validation based on script type
      switch (scriptType) {
        case 'bash':
          return this.validateBashScript(script, validationResult);
        case 'docker':
          return this.validateDockerScript(script, validationResult);
        case 'python':
          return this.validatePythonScript(script, validationResult);
        default:
          validationResult.warnings.push(`Unknown script type: ${scriptType}`);
      }

      return validationResult;
    } catch (error) {
      this.logger.error('Script validation failed', { 
        scriptType, 
        error: (error as Error).message 
      });
      throw error;
    }
  }

  private validateBashScript(script: string, result: any): any {
    // Basic bash script validation
    const dangerousCommands = ['rm -rf', 'dd if=', 'mkfs', 'fdisk'];
    
    for (const cmd of dangerousCommands) {
      if (script.includes(cmd)) {
        result.errors.push(`Dangerous command detected: ${cmd}`);
        result.valid = false;
      }
    }

    if (script.includes('sudo') && !script.includes('--non-interactive')) {
      result.warnings.push('sudo usage detected - ensure non-interactive mode');
    }

    return result;
  }

  private validateDockerScript(script: string, result: any): any {
    // Basic docker script validation
    if (script.includes('--privileged')) {
      result.warnings.push('Privileged container detected - security risk');
    }

    if (script.includes('docker run') && !script.includes('--rm')) {
      result.suggestions.push('Consider using --rm flag for temporary containers');
    }

    return result;
  }

  private validatePythonScript(script: string, result: any): any {
    // Basic python script validation
    const dangerousImports = ['os.system', 'subprocess.call', 'eval', 'exec'];
    
    for (const imp of dangerousImports) {
      if (script.includes(imp)) {
        result.warnings.push(`Potentially dangerous function: ${imp}`);
      }
    }

    return result;
  }

  /**
   * Clean up connections
   */
  async cleanup(): Promise<void> {
    for (const [id, conn] of this.connections) {
      conn.end();
      this.connections.delete(id);
    }
    
    this.logger.info('VPS connections cleaned up');
  }
}