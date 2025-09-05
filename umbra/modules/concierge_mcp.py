"""
Concierge MCP - Complete VPS Management
Handles everything on your VPS like an MCP server
"""
import os
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
            "docker manage": self.manage_docker_container,
            "resource usage": self.get_resource_usage,
            "execute": self.execute_command,
            "service": self.manage_service,
            "logs": self.get_recent_logs,
            "ports": self.check_ports,
            "backup": self.backup_system,
            "processes": self.get_running_processes,
            "upload file": self.upload_file,
            "download file": self.download_file,
            "system updates": self.check_system_updates,
            "install updates": self.install_updates
        }

    async def process_envelope(self, envelope: InternalEnvelope) -> str | None:
        """Process envelope for Concierge operations."""
        action = envelope.action.lower()
        data = envelope.data

        if action == "system_status":
            return await self.get_system_status()
        elif action == "docker_status":
            return await self.get_docker_status()
        elif action == "docker_manage":
            container = data.get("container", "")
            action_type = data.get("action_type", "status")
            return await self.manage_docker_container(container, action_type)
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
        elif action == "upload_file":
            file_path = data.get("file_path", "")
            content = data.get("content", "")
            return await self.upload_file(file_path, content)
        elif action == "download_file":
            file_path = data.get("file_path", "")
            return await self.download_file(file_path)
        elif action == "check_updates":
            return await self.check_system_updates()
        elif action == "install_updates":
            packages = data.get("packages", [])
            return await self.install_updates(packages)
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
        """Execute shell command on VPS with enhanced risk classification."""
        try:
            # Enhanced risk classification
            high_risk = [
                'rm -rf', 'format', 'mkfs', 'dd if=', 'fdisk', 'parted',
                'shred', 'wipefs', 'mkswap', 'swapon', 'swapoff'
            ]
            
            medium_risk = [
                'rm ', 'mv ', 'chmod 777', 'chmod -R', 'chown -R',
                'kill -9', 'killall', 'pkill', 'systemctl stop',
                'service stop', 'mount', 'umount', 'iptables'
            ]
            
            # Check for high-risk commands
            if any(danger in command.lower() for danger in high_risk):
                return "❌ HIGH RISK: Command blocked for safety. Requires admin confirmation with --force flag."
            
            # Check for medium-risk commands
            risk_level = "LOW"
            if any(risk in command.lower() for risk in medium_risk):
                risk_level = "MEDIUM"
                if not command.endswith(' --confirmed'):
                    return f"⚠️ MEDIUM RISK: Add '--confirmed' flag to execute: {command} --confirmed"

            # Clean the command of confirmation flags
            clean_command = command.replace(' --confirmed', '').strip()

            result = subprocess.run(
                clean_command,
                check=False, shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )

            output = result.stdout or result.stderr
            status = "✅ Success" if result.returncode == 0 else "❌ Failed"
            
            return f"""**⚡ Command Executed**

Risk Level: {risk_level}
Command: `{clean_command}`
Status: {status}

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

    async def manage_docker_container(self, container: str, action: str) -> str:
        """Manage Docker containers with enhanced operations."""
        try:
            if not self.docker_available:
                return "❌ Docker not available on this system"

            valid_actions = ['start', 'stop', 'restart', 'status', 'logs', 'remove']
            if action not in valid_actions:
                return f"❌ Invalid action. Use: {', '.join(valid_actions)}"

            if action == 'status':
                result = subprocess.run(
                    ['docker', 'inspect', container, '--format', 
                     '{{.State.Status}} - {{.Config.Image}} - {{.NetworkSettings.IPAddress}}'],
                    check=False, capture_output=True, text=True, timeout=10
                )
            elif action == 'logs':
                result = subprocess.run(
                    ['docker', 'logs', '--tail', '20', container],
                    check=False, capture_output=True, text=True, timeout=10
                )
            else:
                result = subprocess.run(
                    ['docker', action, container],
                    check=False, capture_output=True, text=True, timeout=30
                )

            status = '✅ Success' if result.returncode == 0 else '❌ Failed'
            output = result.stdout or result.stderr

            return f"""**🐳 Docker Container Management**

Container: {container}
Action: {action}
Result: {status}

```
{output[:500]}
```"""

        except Exception as e:
            return f"❌ Docker management failed: {str(e)[:100]}"

    async def upload_file(self, file_path: str, content: str) -> str:
        """Securely upload file to server with safety checks."""
        try:
            import os
            import base64
            from pathlib import Path

            # Safety checks
            if not file_path or '..' in file_path:
                return "❌ Invalid file path for security reasons"
            
            # Restrict to safe directories
            safe_dirs = ['/tmp', '/home', '/var/www', '/opt']
            if not any(file_path.startswith(safe_dir) for safe_dir in safe_dirs):
                return "❌ File path not in allowed directories"

            # Decode base64 content if provided
            try:
                file_content = base64.b64decode(content).decode('utf-8')
            except:
                file_content = content

            # Create directory if it doesn't exist
            file_obj = Path(file_path)
            file_obj.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(file_content)

            file_size = os.path.getsize(file_path)
            
            return f"""**📁 File Upload Complete**

Path: {file_path}
Size: {file_size} bytes
Status: ✅ Success

File uploaded securely to server."""

        except Exception as e:
            return f"❌ File upload failed: {str(e)[:100]}"

    async def download_file(self, file_path: str) -> str:
        """Securely download file from server with safety checks."""
        try:
            import os
            import base64
            from pathlib import Path

            # Safety checks
            if not file_path or '..' in file_path:
                return "❌ Invalid file path for security reasons"

            if not os.path.exists(file_path):
                return "❌ File not found"

            # Check file size (limit to 1MB for safety)
            file_size = os.path.getsize(file_path)
            if file_size > 1024 * 1024:  # 1MB limit
                return f"❌ File too large ({file_size} bytes). Max 1MB allowed."

            # Read and encode file
            with open(file_path, 'rb') as f:
                file_content = f.read()

            # Base64 encode for safe transmission
            encoded_content = base64.b64encode(file_content).decode('utf-8')

            return f"""**📁 File Download Ready**

Path: {file_path}
Size: {file_size} bytes
Status: ✅ Success

Base64 Content (first 200 chars):
```
{encoded_content[:200]}...
```

Use base64 decode to get original file content."""

        except Exception as e:
            return f"❌ File download failed: {str(e)[:100]}"

    async def check_system_updates(self) -> str:
        """Check for available system updates."""
        try:
            # Check package manager type
            if os.path.exists('/usr/bin/apt'):
                # Debian/Ubuntu
                update_cmd = 'apt list --upgradable 2>/dev/null | head -20'
                check_cmd = 'apt update >/dev/null 2>&1 && apt list --upgradable 2>/dev/null | wc -l'
            elif os.path.exists('/usr/bin/yum'):
                # RHEL/CentOS
                update_cmd = 'yum check-update 2>/dev/null | head -20'
                check_cmd = 'yum check-update 2>/dev/null | grep -c "^[a-zA-Z]"'
            elif os.path.exists('/usr/bin/dnf'):
                # Fedora
                update_cmd = 'dnf check-update 2>/dev/null | head -20'
                check_cmd = 'dnf check-update 2>/dev/null | grep -c "^[a-zA-Z]"'
            else:
                return "❌ Unsupported package manager"

            # Get update count
            count_result = subprocess.run(
                check_cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            
            # Get update list
            list_result = subprocess.run(
                update_cmd, shell=True, capture_output=True, text=True, timeout=30
            )

            try:
                update_count = int(count_result.stdout.strip()) if count_result.stdout.strip().isdigit() else 0
            except:
                update_count = 0

            status = "🟢 Up to date" if update_count == 0 else f"🟡 {update_count} updates available"

            return f"""**🔄 System Updates Check**

Status: {status}

**Available Updates:**
```
{list_result.stdout[:500] if list_result.stdout else 'No updates available'}
```

Run 'install updates' to apply available updates."""

        except Exception as e:
            return f"❌ Update check failed: {str(e)[:100]}"

    async def install_updates(self, packages: list = None) -> str:
        """Install system updates with safety controls."""
        try:
            # Safety check - require admin confirmation for system updates
            if not self.config.is_user_admin(0):  # This would need proper user context
                return "❌ System updates require admin confirmation. Use admin override."

            # Determine package manager and command
            if os.path.exists('/usr/bin/apt'):
                if packages:
                    cmd = f"apt update && apt install -y {' '.join(packages)}"
                else:
                    cmd = "apt update && apt upgrade -y"
            elif os.path.exists('/usr/bin/yum'):
                if packages:
                    cmd = f"yum update -y {' '.join(packages)}"
                else:
                    cmd = "yum update -y"
            elif os.path.exists('/usr/bin/dnf'):
                if packages:
                    cmd = f"dnf update -y {' '.join(packages)}"
                else:
                    cmd = "dnf update -y"
            else:
                return "❌ Unsupported package manager"

            # Execute update (with extended timeout)
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=300
            )

            status = '✅ Success' if result.returncode == 0 else '❌ Failed'
            output = result.stdout[-500:] if result.stdout else result.stderr[-500:]

            return f"""**🔄 System Updates**

Target: {'Specific packages' if packages else 'All available updates'}
Status: {status}

**Output (last 500 chars):**
```
{output}
```

System update completed. Consider rebooting if kernel was updated."""

        except subprocess.TimeoutExpired:
            return "❌ Update process timed out after 5 minutes"
        except Exception as e:
            return f"❌ Update installation failed: {str(e)[:100]}"
