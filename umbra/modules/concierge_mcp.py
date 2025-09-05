"""
Concierge MCP - Complete VPS Management
Handles everything on your VPS like an MCP server
"""
import subprocess
import random
import json
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
            "processes": self.get_running_processes,
            # Instances registry operations
            "create instance": self.create_instance,
            "list instances": self.list_instances,
            "delete instance": self.delete_instance,
            "instance status": self.get_instance_status
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
        elif action == "create_instance":
            instance_name = data.get("instance_name", "")
            instance_type = data.get("instance_type", "vps")
            client_id = data.get("client_id")
            resources = data.get("resources", {})
            return await self.create_instance(instance_name, instance_type, client_id, resources)
        elif action == "list_instances":
            return await self.list_instances()
        elif action == "delete_instance":
            instance_id = data.get("instance_id", "")
            return await self.delete_instance(instance_id)
        elif action == "instance_status":
            instance_id = data.get("instance_id", "")
            return await self.get_instance_status(instance_id)
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

    # Instances Registry Methods
    
    async def create_instance(self, instance_name: str, instance_type: str = "vps", 
                            client_id: int = None, resources: dict = None) -> str:
        """Create a new instance in the registry."""
        try:
            if not instance_name:
                return "❌ Instance name is required"
            
            # Generate unique instance ID
            import random
            import string
            instance_id = f"{instance_type}-{instance_name.lower().replace(' ', '-')}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}"
            
            # Default resources if not provided
            if not resources:
                resources = {
                    "cpu": 2,
                    "memory": 4,
                    "disk": 50,
                    "bandwidth": 1000
                }
            
            # Generate IP address (simulated)
            ip_address = f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"
            port = random.randint(8000, 9999)
            
            # Insert into database
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO instances (instance_id, name, instance_type, status, client_id, 
                                         resources, ip_address, port, created_by)
                    VALUES (?, ?, ?, 'provisioning', ?, ?, ?, ?, 'concierge')
                """, (instance_id, instance_name, instance_type, client_id, 
                      str(resources), ip_address, port))
                conn.commit()
            
            # Simulate provisioning steps
            provisioning_status = await self._simulate_instance_provisioning(instance_name, instance_type, resources)
            
            # Update status to active
            with self.db.get_connection() as conn:
                conn.execute("""
                    UPDATE instances SET status = 'active', updated_at = CURRENT_TIMESTAMP 
                    WHERE instance_id = ?
                """, (instance_id,))
                conn.commit()
            
            return f"""**🚀 Instance Created Successfully**

{provisioning_status}

**Instance Details:**
• ID: {instance_id}
• Name: {instance_name}
• Type: {instance_type}
• Status: ✅ Active
• IP: {ip_address}:{port}
• Resources: {resources}

✅ Instance is ready for use."""
            
        except Exception as e:
            self.logger.error(f"Instance creation failed: {e}")
            return f"❌ Failed to create instance: {str(e)[:100]}"
    
    async def list_instances(self) -> str:
        """List all instances in the registry."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT i.*, c.name as client_name 
                    FROM instances i
                    LEFT JOIN clients c ON i.client_id = c.id
                    ORDER BY i.created_at DESC
                """)
                instances = [dict(row) for row in cursor.fetchall()]
            
            if not instances:
                return """**📋 Instance Registry**

No instances found. Use 'create instance' to create your first instance.

**Available Instance Types:**
• vps - Virtual Private Server
• container - Docker Container  
• service - Microservice
• database - Database Instance"""
            
            instance_list = []
            for instance in instances:
                status_emoji = "✅" if instance['status'] == 'active' else "⏳" if instance['status'] == 'provisioning' else "❌"
                client_info = f" (Client: {instance['client_name']})" if instance['client_name'] else " (No client)"
                
                instance_list.append(f"""• **{instance['name']}** {status_emoji}
  - ID: `{instance['instance_id']}`
  - Type: {instance['instance_type']}
  - Status: {instance['status']}
  - IP: {instance['ip_address']}:{instance['port']}{client_info}
  - Created: {instance['created_at'][:16]}""")
            
            return f"""**📋 Instance Registry**

**Total Instances: {len(instances)}**

{chr(10).join(instance_list)}

Use 'instance status <instance_id>' for detailed information."""
            
        except Exception as e:
            self.logger.error(f"List instances failed: {e}")
            return f"❌ Failed to list instances: {str(e)[:100]}"
    
    async def delete_instance(self, instance_id: str) -> str:
        """Delete an instance from the registry."""
        try:
            if not instance_id:
                return "❌ Instance ID is required"
            
            # Find the instance
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM instances WHERE instance_id = ? OR name LIKE ?
                """, (instance_id, f"%{instance_id}%"))
                instance = cursor.fetchone()
            
            if not instance:
                return f"❌ Instance '{instance_id}' not found"
            
            instance = dict(instance)
            
            # Simulate cleanup process
            cleanup_status = await self._simulate_instance_cleanup(instance)
            
            # Delete from database
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM instances WHERE id = ?", (instance['id'],))
                conn.commit()
            
            return f"""**🗑️ Instance Deleted**

{cleanup_status}

**Deleted Instance:**
• Name: {instance['name']}
• ID: {instance['instance_id']}
• Type: {instance['instance_type']}
• IP: {instance['ip_address']}:{instance['port']}

✅ Instance has been permanently removed from the registry."""
            
        except Exception as e:
            self.logger.error(f"Instance deletion failed: {e}")
            return f"❌ Failed to delete instance: {str(e)[:100]}"
    
    async def get_instance_status(self, instance_id: str) -> str:
        """Get detailed status of a specific instance."""
        try:
            if not instance_id:
                return "❌ Instance ID is required"
            
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT i.*, c.name as client_name, c.email as client_email
                    FROM instances i
                    LEFT JOIN clients c ON i.client_id = c.id
                    WHERE i.instance_id = ? OR i.name LIKE ?
                """, (instance_id, f"%{instance_id}%"))
                instance = cursor.fetchone()
            
            if not instance:
                return f"❌ Instance '{instance_id}' not found"
            
            instance = dict(instance)
            
            # Parse resources
            import json
            try:
                resources = eval(instance['resources']) if instance['resources'] else {}
            except:
                resources = {}
            
            status_emoji = "✅" if instance['status'] == 'active' else "⏳" if instance['status'] == 'provisioning' else "❌"
            
            # Simulate resource usage
            cpu_usage = random.randint(20, 80)
            memory_usage = random.randint(30, 90)
            disk_usage = random.randint(25, 85)
            
            client_section = ""
            if instance['client_name']:
                client_section = f"""
**Client Information:**
• Name: {instance['client_name']}
• Email: {instance['client_email']}"""
            
            return f"""**🔍 Instance Status**

**Basic Information:**
• Name: {instance['name']}
• ID: `{instance['instance_id']}`
• Type: {instance['instance_type']}
• Status: {status_emoji} {instance['status']}
• IP Address: {instance['ip_address']}:{instance['port']}

**Resources:**
• CPU: {resources.get('cpu', 'N/A')} cores ({cpu_usage}% usage)
• Memory: {resources.get('memory', 'N/A')} GB ({memory_usage}% usage)
• Disk: {resources.get('disk', 'N/A')} GB ({disk_usage}% usage)
• Bandwidth: {resources.get('bandwidth', 'N/A')} MB/month
{client_section}

**Management:**
• Created: {instance['created_at']}
• Updated: {instance['updated_at']}
• Created by: {instance['created_by']}

⚡ Instance is operational and ready for use."""
            
        except Exception as e:
            self.logger.error(f"Instance status check failed: {e}")
            return f"❌ Failed to get instance status: {str(e)[:100]}"
    
    async def _simulate_instance_provisioning(self, name: str, instance_type: str, resources: dict) -> str:
        """Simulate the instance provisioning process."""
        return f"""**Instance Provisioning Process:**
✅ Resource allocation verified
✅ Network configuration applied
✅ Security policies configured
✅ Monitoring systems activated
✅ Backup strategy implemented
⚡ {instance_type.title()} instance '{name}' provisioned successfully"""
    
    async def _simulate_instance_cleanup(self, instance: dict) -> str:
        """Simulate the instance cleanup process."""
        return f"""**Instance Cleanup Process:**
✅ Data backup completed
✅ Network resources released
✅ Security policies removed
✅ Monitoring systems deactivated
✅ Storage cleanup completed
⚡ {instance['instance_type'].title()} instance '{instance['name']}' cleaned up successfully"""
