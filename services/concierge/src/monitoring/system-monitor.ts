import { VPSManager } from '../vps/vps-manager';
import { Logger } from '@umbra/shared';

export interface SystemMetrics {
  cpu: {
    usage: number;
    cores: number;
    loadAverage: number[];
  };
  memory: {
    total: number;
    used: number;
    free: number;
    percentage: number;
  };
  disk: {
    total: number;
    used: number;
    free: number;
    percentage: number;
  };
  network: {
    interfaces: NetworkInterface[];
  };
  containers: ContainerMetrics[];
  uptime: number;
  timestamp: string;
}

export interface NetworkInterface {
  name: string;
  rx: number;
  tx: number;
  status: string;
}

export interface ContainerMetrics {
  name: string;
  status: string;
  cpu: number;
  memory: number;
  network: {
    rx: number;
    tx: number;
  };
}

export class SystemMonitor {
  private logger: Logger;
  private vpsManager: VPSManager;
  private monitoringInterval: NodeJS.Timeout | null = null;
  private metrics: SystemMetrics | null = null;

  constructor(vpsManager: VPSManager) {
    this.vpsManager = vpsManager;
    this.logger = new Logger('SystemMonitor');
  }

  /**
   * Start continuous system monitoring
   */
  startMonitoring(intervalMs: number = 30000): void {
    if (this.monitoringInterval) {
      this.stopMonitoring();
    }

    this.logger.info('Starting system monitoring', { intervalMs });

    this.monitoringInterval = setInterval(async () => {
      try {
        this.metrics = await this.collectMetrics();
        this.logger.debug('System metrics collected', { 
          cpu: this.metrics.cpu.usage,
          memory: this.metrics.memory.percentage,
          disk: this.metrics.disk.percentage
        });
      } catch (error) {
        this.logger.error('Failed to collect system metrics', { 
          error: (error as Error).message 
        });
      }
    }, intervalMs);
  }

  /**
   * Stop system monitoring
   */
  stopMonitoring(): void {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
      this.monitoringInterval = null;
      this.logger.info('System monitoring stopped');
    }
  }

  /**
   * Get current system status
   */
  async getSystemStatus(): Promise<SystemMetrics> {
    if (!this.metrics) {
      this.metrics = await this.collectMetrics();
    }
    return this.metrics;
  }

  /**
   * Collect comprehensive system metrics
   */
  private async collectMetrics(): Promise<SystemMetrics> {
    try {
      const [cpuMetrics, memoryMetrics, diskMetrics, networkMetrics, containerMetrics, uptimeMetrics] = 
        await Promise.all([
          this.getCPUMetrics(),
          this.getMemoryMetrics(),
          this.getDiskMetrics(),
          this.getNetworkMetrics(),
          this.getContainerMetrics(),
          this.getUptimeMetrics()
        ]);

      return {
        cpu: cpuMetrics,
        memory: memoryMetrics,
        disk: diskMetrics,
        network: networkMetrics,
        containers: containerMetrics,
        uptime: uptimeMetrics,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      this.logger.error('Failed to collect system metrics', { 
        error: (error as Error).message 
      });
      throw error;
    }
  }

  /**
   * Get CPU metrics
   */
  private async getCPUMetrics(): Promise<SystemMetrics['cpu']> {
    try {
      // Get CPU usage
      const cpuResult = await this.vpsManager.executeCommand(
        "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | sed 's/%us,//'"
      );
      
      // Get CPU cores
      const coresResult = await this.vpsManager.executeCommand('nproc');
      
      // Get load average
      const loadResult = await this.vpsManager.executeCommand("uptime | awk '{print $(NF-2),$(NF-1),$NF}' | tr -d ','");

      const usage = parseFloat(cpuResult.stdout.trim()) || 0;
      const cores = parseInt(coresResult.stdout.trim()) || 1;
      const loadAverage = loadResult.stdout.trim().split(' ').map(n => parseFloat(n) || 0);

      return {
        usage,
        cores,
        loadAverage
      };
    } catch (error) {
      this.logger.warn('Failed to get CPU metrics', { error: (error as Error).message });
      return { usage: 0, cores: 1, loadAverage: [0, 0, 0] };
    }
  }

  /**
   * Get memory metrics
   */
  private async getMemoryMetrics(): Promise<SystemMetrics['memory']> {
    try {
      const result = await this.vpsManager.executeCommand("free -b | grep '^Mem:' | awk '{print $2,$3,$7}'");
      const [total, used, available] = result.stdout.trim().split(' ').map(n => parseInt(n) || 0);
      
      const free = available;
      const percentage = total > 0 ? Math.round((used / total) * 100) : 0;

      return {
        total,
        used,
        free,
        percentage
      };
    } catch (error) {
      this.logger.warn('Failed to get memory metrics', { error: (error as Error).message });
      return { total: 0, used: 0, free: 0, percentage: 0 };
    }
  }

  /**
   * Get disk metrics
   */
  private async getDiskMetrics(): Promise<SystemMetrics['disk']> {
    try {
      const result = await this.vpsManager.executeCommand("df -B1 / | tail -1 | awk '{print $2,$3,$4}'");
      const [total, used, free] = result.stdout.trim().split(' ').map(n => parseInt(n) || 0);
      
      const percentage = total > 0 ? Math.round((used / total) * 100) : 0;

      return {
        total,
        used,
        free,
        percentage
      };
    } catch (error) {
      this.logger.warn('Failed to get disk metrics', { error: (error as Error).message });
      return { total: 0, used: 0, free: 0, percentage: 0 };
    }
  }

  /**
   * Get network metrics
   */
  private async getNetworkMetrics(): Promise<SystemMetrics['network']> {
    try {
      const result = await this.vpsManager.executeCommand(
        "cat /proc/net/dev | grep -E '^\\s*(eth|ens|enp)' | awk '{print $1,$2,$10}' | tr -d ':'"
      );
      
      const interfaces: NetworkInterface[] = [];
      const lines = result.stdout.trim().split('\n').filter(line => line.trim());
      
      for (const line of lines) {
        const [name, rx, tx] = line.trim().split(/\s+/);
        if (name && rx && tx) {
          interfaces.push({
            name,
            rx: parseInt(rx) || 0,
            tx: parseInt(tx) || 0,
            status: 'up' // Would need additional command to get actual status
          });
        }
      }

      return { interfaces };
    } catch (error) {
      this.logger.warn('Failed to get network metrics', { error: (error as Error).message });
      return { interfaces: [] };
    }
  }

  /**
   * Get container metrics
   */
  private async getContainerMetrics(): Promise<ContainerMetrics[]> {
    try {
      const result = await this.vpsManager.executeCommand(
        "docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}' | tail -n +2"
      );
      
      const containers: ContainerMetrics[] = [];
      const lines = result.stdout.trim().split('\n').filter(line => line.trim());
      
      for (const line of lines) {
        const parts = line.trim().split('\t');
        if (parts.length >= 4) {
          const [name, cpuPerc, memUsage, netIO] = parts;
          
          // Parse CPU percentage
          const cpu = parseFloat(cpuPerc.replace('%', '')) || 0;
          
          // Parse memory usage (extract used memory in bytes)
          const memMatch = memUsage.match(/(\d+(?:\.\d+)?)(GiB|MiB|KiB|B)/);
          let memory = 0;
          if (memMatch) {
            const value = parseFloat(memMatch[1]);
            const unit = memMatch[2];
            switch (unit) {
              case 'GiB': memory = value * 1024 * 1024 * 1024; break;
              case 'MiB': memory = value * 1024 * 1024; break;
              case 'KiB': memory = value * 1024; break;
              default: memory = value;
            }
          }
          
          // Parse network I/O
          const netParts = netIO.split(' / ');
          let rx = 0, tx = 0;
          if (netParts.length === 2) {
            rx = this.parseNetworkBytes(netParts[0]);
            tx = this.parseNetworkBytes(netParts[1]);
          }
          
          containers.push({
            name,
            status: 'running', // Would need additional call to get status
            cpu,
            memory,
            network: { rx, tx }
          });
        }
      }

      return containers;
    } catch (error) {
      this.logger.warn('Failed to get container metrics', { error: (error as Error).message });
      return [];
    }
  }

  /**
   * Get system uptime
   */
  private async getUptimeMetrics(): Promise<number> {
    try {
      const result = await this.vpsManager.executeCommand("cat /proc/uptime | awk '{print $1}'");
      return parseFloat(result.stdout.trim()) || 0;
    } catch (error) {
      this.logger.warn('Failed to get uptime metrics', { error: (error as Error).message });
      return 0;
    }
  }

  /**
   * Parse network bytes from docker stats format
   */
  private parseNetworkBytes(value: string): number {
    const match = value.match(/(\d+(?:\.\d+)?)(GB|MB|KB|B)/);
    if (!match) return 0;
    
    const num = parseFloat(match[1]);
    const unit = match[2];
    
    switch (unit) {
      case 'GB': return num * 1000 * 1000 * 1000;
      case 'MB': return num * 1000 * 1000;
      case 'KB': return num * 1000;
      default: return num;
    }
  }

  /**
   * Check if system is healthy based on metrics
   */
  isSystemHealthy(): boolean {
    if (!this.metrics) return true; // Assume healthy if no metrics yet
    
    return (
      this.metrics.cpu.usage < 90 &&
      this.metrics.memory.percentage < 90 &&
      this.metrics.disk.percentage < 90
    );
  }

  /**
   * Get system alerts based on thresholds
   */
  getSystemAlerts(): string[] {
    if (!this.metrics) return [];
    
    const alerts: string[] = [];
    
    if (this.metrics.cpu.usage > 90) {
      alerts.push(`High CPU usage: ${this.metrics.cpu.usage}%`);
    }
    
    if (this.metrics.memory.percentage > 90) {
      alerts.push(`High memory usage: ${this.metrics.memory.percentage}%`);
    }
    
    if (this.metrics.disk.percentage > 90) {
      alerts.push(`High disk usage: ${this.metrics.disk.percentage}%`);
    }
    
    return alerts;
  }
}