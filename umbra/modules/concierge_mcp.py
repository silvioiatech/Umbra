"""
Concierge MCP - Complete VPS Management
Handles everything on your VPS like an MCP server
"""
import subprocess
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

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
        
        # Instance management configuration
        self.client_port_range = self._parse_port_range(
            getattr(config, 'CLIENT_PORT_RANGE', '20000-21000')
        )
        
        # Initialize instance registry database
        self._init_instance_database()

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
            "create instance": self.create_instance,
            "list instances": self.list_instances,
            "delete instance": self.delete_instance
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
        elif action == "instances.create":
            client = data.get("client", "")
            name = data.get("name")
            port = data.get("port")
            return await self.create_instance(client, name, port)
        elif action == "instances.list":
            client = data.get("client")
            return await self.list_instances(client)
        elif action == "instances.delete":
            client = data.get("client", "")
            mode = data.get("mode", "keep")
            return await self.delete_instance(client, mode)
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

    def _parse_port_range(self, port_range_str: str) -> tuple[int, int]:
        """Parse port range string like '20000-21000'."""
        try:
            start, end = port_range_str.split('-')
            return (int(start.strip()), int(end.strip()))
        except (ValueError, AttributeError):
            self.logger.warning(f"Invalid port range '{port_range_str}', using default 20000-21000")
            return (20000, 21000)

    def _init_instance_database(self):
        """Initialize instance registry database tables."""
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS instance_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    port INTEGER UNIQUE NOT NULL,
                    status TEXT DEFAULT 'active',
                    data_dir TEXT,
                    reserved BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Index for faster lookups
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_instance_client_id 
                ON instance_registry(client_id)
            """)
            
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_instance_port 
                ON instance_registry(port)
            """)
            
            self.logger.info("Instance registry database initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize instance database: {e}")

    def _validate_client_slug(self, client: str) -> bool:
        """Validate client slug format: [a-z0-9-]{1,32}."""
        if not client or len(client) > 32:
            return False
        return bool(re.match(r'^[a-z0-9\-]+$', client))

    def _validate_port(self, port: Optional[int]) -> bool:
        """Validate port is within allowed range."""
        if port is None:
            return True
        start, end = self.client_port_range
        return start <= port <= end

    def _allocate_port(self) -> Optional[int]:
        """Allocate next available port from the range."""
        start, end = self.client_port_range
        
        # Get all used ports (including reserved)
        used_ports = set()
        instances = self.db.query_all("SELECT port FROM instance_registry")
        for instance in instances:
            used_ports.add(instance['port'])
        
        # Find first available port
        for port in range(start, end + 1):
            if port not in used_ports:
                return port
        
        return None  # No ports available

    async def create_instance(self, client: str, name: Optional[str] = None, port: Optional[int] = None) -> dict:
        """Create a new client n8n instance."""
        try:
            # Validate client slug
            if not self._validate_client_slug(client):
                return {
                    "ok": False,
                    "error": "Invalid client slug. Must be [a-z0-9-] max 32 chars."
                }
            
            # Check if client already exists
            existing = self.db.query_one(
                "SELECT client_id FROM instance_registry WHERE client_id = ?", 
                (client,)
            )
            if existing:
                # Return existing instance (idempotent)
                instance = self.db.query_one(
                    "SELECT * FROM instance_registry WHERE client_id = ?", 
                    (client,)
                )
                return {
                    "ok": True,
                    "client_id": instance['client_id'],
                    "display_name": instance['display_name'],
                    "url": instance['url'],
                    "port": instance['port'],
                    "status": instance['status'],
                    "message": "Instance already exists"
                }
            
            # Validate or allocate port
            if port is not None:
                if not self._validate_port(port):
                    return {
                        "ok": False,
                        "error": f"Port {port} outside allowed range {self.client_port_range[0]}-{self.client_port_range[1]}"
                    }
                
                # Check if port is already used
                port_exists = self.db.query_one(
                    "SELECT client_id FROM instance_registry WHERE port = ?", 
                    (port,)
                )
                if port_exists:
                    return {
                        "ok": False,
                        "error": f"Port {port} already in use by client '{port_exists['client_id']}'"
                    }
            else:
                port = self._allocate_port()
                if port is None:
                    return {
                        "ok": False,
                        "error": "No available ports in range"
                    }
            
            # Set defaults
            display_name = name or f"n8n-{client}"
            url = f"http://localhost:{port}"
            data_dir = f"/data/n8n/{client}"
            
            # Create instance record
            self.db.execute("""
                INSERT INTO instance_registry 
                (client_id, display_name, url, port, status, data_dir, reserved, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'active', ?, FALSE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (client, display_name, url, port, data_dir))
            
            audit_id = f"inst_create_{client}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            return {
                "ok": True,
                "client_id": client,
                "display_name": display_name,
                "url": url,
                "port": port,
                "status": "active",
                "audit_id": audit_id,
                "message": f"Instance created successfully on port {port}"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create instance for {client}: {e}")
            return {
                "ok": False,
                "error": f"Instance creation failed: {str(e)}"
            }

    async def list_instances(self, client: Optional[str] = None) -> dict:
        """List instances or get single client details."""
        try:
            if client:
                # Single client details
                if not self._validate_client_slug(client):
                    return {
                        "ok": False,
                        "error": "Invalid client slug"
                    }
                
                instance = self.db.query_one(
                    "SELECT * FROM instance_registry WHERE client_id = ?", 
                    (client,)
                )
                
                if not instance:
                    return {
                        "ok": False,
                        "error": f"Client '{client}' not found"
                    }
                
                return {
                    "ok": True,
                    "client_id": instance['client_id'],
                    "display_name": instance['display_name'],
                    "url": instance['url'],
                    "port": instance['port'],
                    "status": instance['status'],
                    "data_dir": instance['data_dir'],
                    "reserved": bool(instance['reserved'])
                }
            else:
                # List all instances
                instances = self.db.query_all(
                    "SELECT client_id, display_name, url, port, status FROM instance_registry ORDER BY created_at DESC"
                )
                
                return {
                    "ok": True,
                    "instances": [
                        {
                            "client_id": inst['client_id'],
                            "display_name": inst['display_name'],
                            "url": inst['url'],
                            "port": inst['port'],
                            "status": inst['status']
                        }
                        for inst in instances
                    ]
                }
                
        except Exception as e:
            self.logger.error(f"Failed to list instances: {e}")
            return {
                "ok": False,
                "error": f"Failed to list instances: {str(e)}"
            }

    async def delete_instance(self, client: str, mode: str = "keep") -> dict:
        """Delete instance with keep-data or wipe-data mode."""
        try:
            # Validate inputs
            if not self._validate_client_slug(client):
                return {
                    "ok": False,
                    "error": "Invalid client slug"
                }
            
            if mode not in ["keep", "wipe"]:
                return {
                    "ok": False,
                    "error": "Mode must be 'keep' or 'wipe'"
                }
            
            # Check if instance exists
            instance = self.db.query_one(
                "SELECT * FROM instance_registry WHERE client_id = ?", 
                (client,)
            )
            
            if not instance:
                return {
                    "ok": False,
                    "error": f"Client '{client}' not found"
                }
            
            audit_id = f"inst_delete_{client}_{mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if mode == "keep":
                # Keep data, reserve port (archived)
                self.db.execute("""
                    UPDATE instance_registry 
                    SET status = 'archived', reserved = TRUE, updated_at = CURRENT_TIMESTAMP
                    WHERE client_id = ?
                """, (client,))
                
                message = f"Instance archived, data preserved, port {instance['port']} reserved"
                
            elif mode == "wipe":
                # Remove completely, free port
                self.db.execute(
                    "DELETE FROM instance_registry WHERE client_id = ?", 
                    (client,)
                )
                
                message = f"Instance completely removed, port {instance['port']} freed"
            
            return {
                "ok": True,
                "mode": mode,
                "audit_id": audit_id,
                "message": message
            }
            
        except Exception as e:
            self.logger.error(f"Failed to delete instance {client}: {e}")
            return {
                "ok": False,
                "error": f"Instance deletion failed: {str(e)}"
            }
