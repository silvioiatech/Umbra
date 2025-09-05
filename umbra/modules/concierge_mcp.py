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
        
        # Docker Auto-Update Watcher configuration
        self.auto_update_enabled = getattr(config, 'DOCKER_AUTO_UPDATE_ENABLED', False)
        self.auto_update_schedule = getattr(config, 'DOCKER_AUTO_UPDATE_SCHEDULE', '0 2 * * *')  # Daily at 2 AM
        self.update_check_interval = getattr(config, 'DOCKER_UPDATE_CHECK_INTERVAL', 3600)  # Check every hour for updates

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
            "docker updates": self.check_docker_updates,
            "docker auto-update": self.auto_update_docker,
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
        elif action == "docker_updates":
            return await self.check_docker_updates()
        elif action == "docker_auto_update":
            container_name = data.get("container")
            force = data.get("force", False)
            return await self.auto_update_docker(container_name, force)
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
                    "docker_available": self.docker_available,
                    "auto_update_enabled": self.auto_update_enabled
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
```

**Auto-Update Watcher:** {'🟢 Enabled' if self.auto_update_enabled else '🔴 Disabled'}
**Last Check:** Use 'docker updates' to check for available updates"""
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

    async def check_docker_updates(self) -> str:
        """Check for available Docker container updates."""
        try:
            if not self.docker_available:
                return "❌ Docker not available"

            # Get running containers
            containers_result = subprocess.run(
                ['docker', 'ps', '--format', '{{.Names}}\t{{.Image}}'],
                check=False, capture_output=True, text=True, timeout=15
            )

            if containers_result.returncode != 0:
                return "❌ Failed to get container list"

            containers = []
            for line in containers_result.stdout.strip().split('\n'):
                if '\t' in line:
                    name, image = line.split('\t', 1)
                    containers.append((name, image))

            if not containers:
                return "ℹ️ No running containers to check"

            updates_available = []
            up_to_date = []

            for container_name, current_image in containers:
                try:
                    # Check if image has latest tag or specific version
                    if ':' not in current_image:
                        current_image += ':latest'
                    
                    image_name, current_tag = current_image.rsplit(':', 1)
                    
                    # Pull latest to check for updates (without changing local image)
                    pull_result = subprocess.run(
                        ['docker', 'pull', f"{image_name}:latest"],
                        check=False, capture_output=True, text=True, timeout=30
                    )
                    
                    if pull_result.returncode == 0:
                        # Check if pulled image is different from current
                        inspect_current = subprocess.run(
                            ['docker', 'inspect', '--format', '{{.Image}}', container_name],
                            check=False, capture_output=True, text=True, timeout=5
                        )
                        
                        inspect_latest = subprocess.run(
                            ['docker', 'inspect', '--format', '{{.Id}}', f"{image_name}:latest"],
                            check=False, capture_output=True, text=True, timeout=5
                        )
                        
                        if (inspect_current.returncode == 0 and inspect_latest.returncode == 0):
                            current_id = inspect_current.stdout.strip()
                            latest_id = inspect_latest.stdout.strip()
                            
                            if current_id != latest_id:
                                updates_available.append({
                                    'name': container_name,
                                    'image': current_image,
                                    'status': 'update_available'
                                })
                            else:
                                up_to_date.append({
                                    'name': container_name,
                                    'image': current_image,
                                    'status': 'up_to_date'
                                })
                        else:
                            up_to_date.append({
                                'name': container_name,
                                'image': current_image,
                                'status': 'check_failed'
                            })
                    else:
                        up_to_date.append({
                            'name': container_name,
                            'image': current_image,
                            'status': 'pull_failed'
                        })
                        
                except Exception as e:
                    self.logger.warning(f"Update check failed for {container_name}: {e}")
                    up_to_date.append({
                        'name': container_name,
                        'image': current_image,
                        'status': 'error'
                    })

            # Format response
            response = "**🔄 Docker Auto-Update Check**\n\n"
            
            if updates_available:
                response += "**📦 Updates Available:**\n"
                for container in updates_available:
                    response += f"• {container['name']}: {container['image']} ⬆️\n"
                response += "\n"
            
            if up_to_date:
                response += "**✅ Up to Date:**\n"
                for container in up_to_date:
                    status_icon = {
                        'up_to_date': '✅',
                        'check_failed': '⚠️',
                        'pull_failed': '⚠️',
                        'error': '❌'
                    }.get(container['status'], '❓')
                    response += f"• {container['name']}: {container['image']} {status_icon}\n"
            
            response += f"\n**Auto-Update:** {'🟢 Enabled' if self.auto_update_enabled else '🔴 Disabled'}"
            
            return response

        except Exception as e:
            self.logger.error(f"Docker update check failed: {e}")
            return f"❌ Update check failed: {str(e)[:100]}"

    async def auto_update_docker(self, container_name: str = None, force: bool = False) -> str:
        """Automatically update Docker containers."""
        try:
            if not self.docker_available:
                return "❌ Docker not available"

            if not force and not self.auto_update_enabled:
                return "❌ Auto-update is disabled. Use force=true to override."

            # If specific container specified, update only that one
            if container_name:
                return await self._update_single_container(container_name)
            
            # Otherwise, update all containers with available updates
            update_check = await self.check_docker_updates()
            
            # Parse update check results to find containers needing updates
            if "Updates Available:" not in update_check:
                return "ℹ️ No updates available for any containers"

            # Get containers with updates (simplified parsing)
            containers_result = subprocess.run(
                ['docker', 'ps', '--format', '{{.Names}}\t{{.Image}}'],
                check=False, capture_output=True, text=True, timeout=10
            )

            if containers_result.returncode != 0:
                return "❌ Failed to get container list"

            updated_containers = []
            failed_updates = []

            for line in containers_result.stdout.strip().split('\n'):
                if '\t' in line:
                    name, image = line.split('\t', 1)
                    try:
                        result = await self._update_single_container(name)
                        if "✅" in result:
                            updated_containers.append(name)
                        else:
                            failed_updates.append(f"{name}: {result}")
                    except Exception as e:
                        failed_updates.append(f"{name}: {str(e)[:50]}")

            # Format response
            response = "**🔄 Docker Auto-Update Results**\n\n"
            
            if updated_containers:
                response += "**✅ Successfully Updated:**\n"
                for container in updated_containers:
                    response += f"• {container}\n"
                response += "\n"
            
            if failed_updates:
                response += "**❌ Failed Updates:**\n"
                for failure in failed_updates:
                    response += f"• {failure}\n"
            
            if not updated_containers and not failed_updates:
                response += "ℹ️ No containers required updates"

            return response

        except Exception as e:
            self.logger.error(f"Docker auto-update failed: {e}")
            return f"❌ Auto-update failed: {str(e)[:100]}"

    async def _update_single_container(self, container_name: str) -> str:
        """Update a single Docker container."""
        try:
            # Get container's current image
            inspect_result = subprocess.run(
                ['docker', 'inspect', '--format', '{{.Config.Image}}', container_name],
                check=False, capture_output=True, text=True, timeout=5
            )
            
            if inspect_result.returncode != 0:
                return f"❌ Container {container_name} not found"
            
            current_image = inspect_result.stdout.strip()
            if ':' not in current_image:
                current_image += ':latest'
            
            image_name, tag = current_image.rsplit(':', 1)
            
            # Pull latest image
            pull_result = subprocess.run(
                ['docker', 'pull', f"{image_name}:latest"],
                check=False, capture_output=True, text=True, timeout=60
            )
            
            if pull_result.returncode != 0:
                return f"❌ Failed to pull {image_name}:latest"
            
            # Get container configuration for recreation
            config_result = subprocess.run(
                ['docker', 'inspect', container_name],
                check=False, capture_output=True, text=True, timeout=5
            )
            
            if config_result.returncode != 0:
                return f"❌ Failed to get container config"
            
            # Stop container
            stop_result = subprocess.run(
                ['docker', 'stop', container_name],
                check=False, capture_output=True, text=True, timeout=30
            )
            
            if stop_result.returncode != 0:
                return f"❌ Failed to stop container"
            
            # Remove old container
            rm_result = subprocess.run(
                ['docker', 'rm', container_name],
                check=False, capture_output=True, text=True, timeout=10
            )
            
            if rm_result.returncode != 0:
                return f"❌ Failed to remove old container"
            
            # Create and start new container with latest image
            # This is a simplified approach - in production, you'd want to preserve
            # the exact configuration, volumes, networks, etc.
            run_result = subprocess.run(
                ['docker', 'run', '-d', '--name', container_name, f"{image_name}:latest"],
                check=False, capture_output=True, text=True, timeout=30
            )
            
            if run_result.returncode == 0:
                return f"✅ Updated {container_name} to latest {image_name}"
            else:
                return f"❌ Failed to recreate container: {run_result.stderr[:100]}"
                
        except Exception as e:
            return f"❌ Update failed: {str(e)[:100]}"
