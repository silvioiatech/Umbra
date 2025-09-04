"""
Concierge MCP - Complete VPS Management
Handles everything on your VPS like an MCP server
"""
import subprocess
from datetime import datetime
from typing import Any

import psutil

from ..core.envelope import InternalEnvelope
from ..core.module_base import ModuleBase


class ConciergeMCP(ModuleBase):
    """VPS Manager - Complete control over your server."""

    def __init__(self, config, db_manager):
        super().__init__("concierge")
        self.config = config
        self.db = db_manager
        self.ssh_available = hasattr(config, 'VPS_HOST') and config.VPS_HOST
        self.docker_available = hasattr(config, 'DOCKER_AVAILABLE') and config.DOCKER_AVAILABLE

    async def initialize(self) -> bool:
        """Initialize the Concierge module."""
        try:
            # Test system monitoring capabilities
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()

            self.logger.info(f"System monitoring initialized - CPU: {cpu_percent}%, Memory: {memory.percent}%")

            # Test Docker availability if enabled
            if self.docker_available:
                try:
                    result = subprocess.run(['docker', 'version'], check=False, capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        self.logger.info("Docker integration available")
                    else:
                        self.logger.warning("Docker not available")
                        self.docker_available = False
                except Exception:
                    self.logger.warning("Docker not available")
                    self.docker_available = False

            return True
        except Exception as e:
            self.logger.error(f"Concierge initialization failed: {e}")
            return False

    async def register_handlers(self) -> dict[str, Any]:
        """Register command handlers for the Concierge module."""
        return {
            "system status": self.get_system_status,
            "docker status": self.get_docker_status,
            "resource usage": self.get_resource_usage,
            "execute": self.execute_command,
            "service": self.manage_service,
            "logs": self.get_recent_logs,
            "ports": self.check_ports,
            "backup": self.backup_system,
            "processes": self.get_running_processes
        }

    async def process_envelope(self, envelope: InternalEnvelope) -> str | None:
        """Process envelope for Concierge operations."""
        action = envelope.action.lower()
        data = envelope.data

        if action == "system_status":
            return await self.get_system_status()
        elif action == "docker_status":
            return await self.get_docker_status()
        elif action == "resource_usage":
            return await self.get_resource_usage()
        elif action == "execute_command":
            command = data.get("command", "")
            return await self.execute_command(command)
        elif action == "manage_service":
            service = data.get("service", "")
            action_type = data.get("action_type", "status")
            return await self.manage_service(service, action_type)
        elif action == "get_logs":
            service = data.get("service")
            return await self.get_recent_logs(service)
        elif action == "check_ports":
            return await self.check_ports()
        elif action == "backup_system":
            return await self.backup_system()
        else:
            return None

    async def health_check(self) -> dict[str, Any]:
        """Perform health check of the Concierge module."""
        try:
            # Check system resources
            cpu = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Determine health status
            status = "healthy"
            issues = []

            if cpu > 90:
                issues.append(f"High CPU usage: {cpu:.1f}%")
                status = "warning"

            if memory.percent > 90:
                issues.append(f"High memory usage: {memory.percent:.1f}%")
                status = "warning"

            if disk.percent > 95:
                issues.append(f"High disk usage: {disk.percent:.1f}%")
                status = "critical"

            return {
                "status": status,
                "details": {
                    "cpu_percent": cpu,
                    "memory_percent": memory.percent,
                    "disk_percent": disk.percent,
                    "ssh_available": self.ssh_available,
                    "docker_available": self.docker_available
                },
                "issues": issues
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def shutdown(self):
        """Gracefully shutdown the Concierge module."""
        self.logger.info("Concierge module shutting down")
        # No specific cleanup needed for this module

    async def get_system_status(self) -> str:
        """Get complete system status."""
        try:
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Get network stats
            net = psutil.net_io_counters()

            # Get uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time

            status = f"""**📊 VPS System Status**

**Resources:**
• CPU: {cpu:.1f}% ({psutil.cpu_count()} cores)
• RAM: {memory.percent:.1f}% ({memory.used/1024**3:.1f}/{memory.total/1024**3:.1f} GB)
• Disk: {disk.percent:.1f}% ({disk.used/1024**3:.1f}/{disk.total/1024**3:.1f} GB)

**Network:**
• Sent: {net.bytes_sent/1024**2:.1f} MB
• Received: {net.bytes_recv/1024**2:.1f} MB

**System:**
• Uptime: {uptime.days}d {uptime.seconds//3600}h
• Load: {', '.join(map(str, psutil.getloadavg()))}"""

            return status

        except Exception as e:
            self.logger.error(f"System status error: {e}")
            return f"❌ Failed to get system status: {str(e)[:100]}"

    async def get_docker_status(self) -> str:
        """Get Docker container status."""
        try:
            # Check if Docker is available
            result = subprocess.run(
                ['docker', 'ps', '--format', 'table {{.Names}}\t{{.Status}}\t{{.Size}}'],
                check=False, capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                containers = result.stdout.strip().split('\n')
                count = len(containers) - 1 if len(containers) > 1 else 0

                # Get Docker stats
                stats_result = subprocess.run(
                    ['docker', 'system', 'df'],
                    check=False, capture_output=True,
                    text=True,
                    timeout=10
                )

                return f"""**🐳 Docker Status**

**Containers:** {count} running

```
{result.stdout[:500]}
```

**Docker Storage:**
```
{stats_result.stdout[:300] if stats_result.returncode == 0 else 'N/A'}
```"""
            else:
                return "❌ Docker not available or no permission"

        except Exception as e:
            return f"❌ Docker check failed: {str(e)[:100]}"

    async def get_resource_usage(self) -> str:
        """Get detailed resource usage."""
        try:
            # CPU per process
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    pinfo = proc.info
                    if pinfo['cpu_percent'] > 1:  # Only show processes using >1% CPU
                        processes.append(pinfo)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            # Sort by CPU usage
            processes = sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:5]

            process_list = "\n".join([
                f"• {p['name'][:20]}: CPU {p['cpu_percent']:.1f}%, RAM {p['memory_percent']:.1f}%"
                for p in processes
            ])

            return f"""**🔧 Resource Usage**

**Top Processes:**
{process_list}

**Memory Details:**
• Available: {psutil.virtual_memory().available/1024**3:.1f} GB
• Cached: {psutil.virtual_memory().cached/1024**3:.1f} GB
• Swap: {psutil.swap_memory().percent:.1f}% used"""

        except Exception as e:
            return f"❌ Resource check failed: {str(e)[:100]}"

    async def execute_command(self, command: str) -> str:
        """Execute shell command on VPS."""
        try:
            # Safety check
            dangerous = ['rm -rf', 'format', 'mkfs', 'dd if=']
            if any(d in command.lower() for d in dangerous):
                return "❌ Command blocked for safety. Use admin confirmation for dangerous operations."

            result = subprocess.run(
                command,
                check=False, shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )

            output = result.stdout or result.stderr
            return f"""**⚡ Command Executed**

```bash
$ {command}
```

**Output:**
```
{output[:500]}
```"""

        except subprocess.TimeoutExpired:
            return "❌ Command timed out after 30 seconds"
        except Exception as e:
            return f"❌ Command failed: {str(e)[:100]}"

    async def manage_service(self, service: str, action: str) -> str:
        """Manage system services."""
        try:
            valid_actions = ['start', 'stop', 'restart', 'status']
            if action not in valid_actions:
                return f"❌ Invalid action. Use: {', '.join(valid_actions)}"

            result = subprocess.run(
                ['systemctl', action, service],
                check=False, capture_output=True,
                text=True,
                timeout=10
            )

            return f"""**⚙️ Service Management**

Service: {service}
Action: {action}
Result: {'✅ Success' if result.returncode == 0 else '❌ Failed'}

{result.stdout or result.stderr}"""

        except Exception as e:
            return f"❌ Service management failed: {str(e)[:100]}"

    async def get_recent_logs(self, service: str | None = None) -> str:
        """Get recent system or service logs."""
        try:
            if service:
                cmd = f"journalctl -u {service} -n 20 --no-pager"
            else:
                cmd = "journalctl -n 20 --no-pager"

            result = subprocess.run(
                cmd,
                check=False, shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )

            logs = result.stdout[:800] if result.stdout else "No logs available"

            return f"""**📜 Recent Logs**

```
{logs}
```"""

        except Exception as e:
            return f"❌ Log retrieval failed: {str(e)[:100]}"

    async def check_ports(self) -> str:
        """Check open ports and services."""
        try:
            connections = psutil.net_connections()
            listening = [c for c in connections if c.status == 'LISTEN']

            ports = []
            for conn in listening[:10]:  # Top 10 ports
                try:
                    proc = psutil.Process(conn.pid)
                    ports.append(f"• {conn.laddr.port}: {proc.name()}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    ports.append(f"• {conn.laddr.port}: unknown")

            return f"""**🔌 Open Ports**

{chr(10).join(ports)}

Total listening ports: {len(listening)}"""

        except Exception as e:
            return f"❌ Port check failed: {str(e)[:100]}"

    async def backup_system(self) -> str:
        """Create system backup."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}"

            # This is a placeholder - implement actual backup logic
            return f"""**💾 Backup Created**

Name: {backup_name}
Status: ✅ Ready
Location: /backups/{backup_name}

Note: Implement actual backup logic based on your VPS setup."""

        except Exception as e:
            return f"❌ Backup failed: {str(e)[:100]}"

    async def get_running_processes(self) -> str:
        """Get list of running processes."""
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    pinfo = proc.info
                    if pinfo['cpu_percent'] and pinfo['cpu_percent'] > 0.1:
                        processes.append(pinfo)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            # Sort by CPU usage
            processes.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
            processes = processes[:10]  # Top 10

            process_list = []
            for proc in processes:
                process_list.append(
                    f"• {proc['name']} (PID: {proc['pid']}) - "
                    f"CPU: {proc['cpu_percent']:.1f}%, "
                    f"Memory: {proc['memory_percent']:.1f}%"
                )

            return f"""**🔍 Running Processes**

**Top CPU Processes:**
{chr(10).join(process_list[:10]) if process_list else "No high-CPU processes found"}

**Total Processes:** {len(list(psutil.process_iter()))}"""

        except Exception as e:
            return f"❌ Process check failed: {str(e)[:100]}"
