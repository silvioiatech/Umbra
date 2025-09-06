"""
Concierge Instances Operations - C3: Instance Registry and Management

Manages client n8n instances with:
- Automatic port allocation from CLIENT_PORT_RANGE
- Data directory management under CLIENTS_BASE_DIR
- Docker container lifecycle (create, stop, remove)
- URL generation and status tracking
- SQLite registry with comprehensive audit trail
"""
import os
import time
import json
import hashlib
import subprocess
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    import docker
    from docker.errors import DockerException, APIError, NotFound
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

from ...core.logger import get_context_logger

@dataclass
class InstanceInfo:
    """Information about a client n8n instance."""
    client_id: str
    display_name: str
    url: str
    port: int
    data_dir: str
    status: str  # running, stopped, archived, deleted
    reserved: bool
    created_at: str
    updated_at: str
    container_id: Optional[str] = None
    container_name: Optional[str] = None

@dataclass
class InstanceCreateRequest:
    """Request to create a new instance."""
    client: str
    name: Optional[str] = None
    port: Optional[int] = None
    env_overrides: Optional[Dict[str, str]] = None

@dataclass
class InstanceCreateResult:
    """Result of instance creation."""
    success: bool
    instance: Optional[InstanceInfo] = None
    error: Optional[str] = None
    audit_id: Optional[str] = None

class InstancesRegistry:
    """
    Registry for managing client n8n instances.
    
    Provides complete lifecycle management for client instances including
    port allocation, Docker container management, data persistence,
    and comprehensive audit logging.
    """
    
    def __init__(self, config, db_manager):
        self.config = config
        self.db = db_manager
        self.logger = get_context_logger(__name__)
        
        # Configuration from config
        self.client_port_range = self._parse_port_range(
            getattr(config, 'CLIENT_PORT_RANGE', '20000-21000')
        )
        self.clients_base_dir = Path(getattr(config, 'CLIENTS_BASE_DIR', '/srv/n8n-clients'))
        self.n8n_image = getattr(config, 'N8N_IMAGE', 'n8nio/n8n:latest')
        self.n8n_base_env = self._parse_env_string(
            getattr(config, 'N8N_BASE_ENV', '')
        )
        self.nginx_container = getattr(config, 'NGINX_CONTAINER_NAME', None)
        self.host = getattr(config, 'INSTANCES_HOST', 'localhost')
        self.use_https = getattr(config, 'INSTANCES_USE_HTTPS', False)
        
        # Docker client
        self.docker_client = None
        self.docker_available = False
        
        if DOCKER_AVAILABLE:
            try:
                self.docker_client = docker.from_env()
                # Test connection
                self.docker_client.ping()
                self.docker_available = True
                self.logger.info("Docker client initialized successfully")
            except Exception as e:
                self.logger.warning(f"Docker not available: {e}")
                self.docker_available = False
        else:
            self.logger.warning("Docker SDK not installed - instances functionality limited")
        
        # Initialize database schema
        self._init_schema()
        
        self.logger.info(
            "Instances registry initialized",
            extra={
                "port_range": f"{self.client_port_range[0]}-{self.client_port_range[1]}",
                "base_dir": str(self.clients_base_dir),
                "n8n_image": self.n8n_image,
                "docker_available": self.docker_available,
                "env_vars_count": len(self.n8n_base_env)
            }
        )
    
    def _parse_port_range(self, port_range_str: str) -> Tuple[int, int]:
        """Parse port range string like '20000-21000'."""
        try:
            start_str, end_str = port_range_str.split('-')
            start_port = int(start_str.strip())
            end_port = int(end_str.strip())
            
            if start_port >= end_port or start_port < 1024 or end_port > 65535:
                raise ValueError(f"Invalid port range: {port_range_str}")
            
            return (start_port, end_port)
        except Exception as e:
            self.logger.error(f"Failed to parse port range '{port_range_str}': {e}")
            # Fallback to default
            return (20000, 21000)
    
    def _parse_env_string(self, env_str: str) -> Dict[str, str]:
        """Parse environment string like 'KEY1=val1,KEY2=val2'."""
        env_dict = {}
        
        if not env_str.strip():
            return env_dict
        
        try:
            for pair in env_str.split(','):
                pair = pair.strip()
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    env_dict[key.strip()] = value.strip()
        except Exception as e:
            self.logger.error(f"Failed to parse environment string: {e}")
        
        return env_dict
    
    def _init_schema(self):
        """Initialize instances registry database schema."""
        try:
            # Main instances registry table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS instances_registry (
                    client_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    port INTEGER UNIQUE NOT NULL,
                    data_dir TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('running','stopped','archived','deleted')),
                    reserved INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    container_id TEXT,
                    container_name TEXT,
                    env_overrides TEXT  -- JSON string of environment overrides
                )
            """)
            
            # Indexes for performance
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_instances_status 
                ON instances_registry (status)
            """)
            
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_instances_reserved 
                ON instances_registry (reserved)
            """)
            
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_instances_port 
                ON instances_registry (port)
            """)
            
            # Instances audit table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS instances_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    audit_id TEXT NOT NULL UNIQUE,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    client_id TEXT,
                    params_redacted TEXT,
                    status TEXT NOT NULL,
                    duration_ms REAL,
                    result_hash TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_instances_audit_user_time 
                ON instances_audit (user_id, created_at)
            """)
            
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_instances_audit_client 
                ON instances_audit (client_id, created_at)
            """)
            
            self.logger.info("Instances registry schema initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize instances schema: {e}")
            raise
    
    def list_instances(self, client_filter: Optional[str] = None) -> List[InstanceInfo]:
        """
        List instances with optional client filter.
        
        Args:
            client_filter: Optional client ID to filter by
        
        Returns:
            List of InstanceInfo objects
        """
        try:
            if client_filter:
                query = """
                    SELECT client_id, display_name, url, port, data_dir, status, 
                           reserved, created_at, updated_at, container_id, container_name 
                    FROM instances_registry 
                    WHERE client_id = ?
                    ORDER BY created_at DESC
                """
                rows = self.db.query(query, (client_filter,))
            else:
                query = """
                    SELECT client_id, display_name, url, port, data_dir, status, 
                           reserved, created_at, updated_at, container_id, container_name 
                    FROM instances_registry 
                    ORDER BY created_at DESC
                """
                rows = self.db.query(query)
            
            instances = []
            for row in rows:
                instance = InstanceInfo(
                    client_id=row[0],
                    display_name=row[1],
                    url=row[2],
                    port=row[3],
                    data_dir=row[4],
                    status=row[5],
                    reserved=bool(row[6]),
                    created_at=row[7],
                    updated_at=row[8],
                    container_id=row[9],
                    container_name=row[10]
                )
                instances.append(instance)
            
            self.logger.info(
                f"Listed {len(instances)} instances",
                extra={"client_filter": client_filter, "count": len(instances)}
            )
            
            return instances
            
        except Exception as e:
            self.logger.error(f"Failed to list instances: {e}")
            return []
    
    def get_instance(self, client_id: str) -> Optional[InstanceInfo]:
        """Get single instance by client ID."""
        instances = self.list_instances(client_filter=client_id)
        return instances[0] if instances else None
    
    def _allocate_port(self, preferred_port: Optional[int] = None) -> Optional[int]:
        """
        Allocate an available port from the range.
        
        Args:
            preferred_port: Specific port to try first
        
        Returns:
            Allocated port number or None if none available
        """
        start_port, end_port = self.client_port_range
        
        # Get used and reserved ports
        used_ports = set()
        try:
            query = "SELECT port FROM instances_registry WHERE status != 'deleted'"
            rows = self.db.query(query)
            used_ports.update(row[0] for row in rows)
        except Exception as e:
            self.logger.error(f"Failed to get used ports: {e}")
            return None
        
        # Try preferred port first if specified
        if preferred_port:
            if start_port <= preferred_port <= end_port and preferred_port not in used_ports:
                self.logger.info(f"Allocated preferred port: {preferred_port}")
                return preferred_port
            else:
                self.logger.warning(f"Preferred port {preferred_port} not available")
        
        # Find next available port
        for port in range(start_port, end_port + 1):
            if port not in used_ports:
                self.logger.info(f"Allocated port: {port}")
                return port
        
        self.logger.error("No ports available in range")
        return None
    
    def _create_data_directory(self, client_id: str) -> str:
        """Create data directory for client."""
        client_dir = self.clients_base_dir / client_id
        
        try:
            client_dir.mkdir(parents=True, exist_ok=True)
            
            # Set appropriate permissions
            os.chmod(client_dir, 0o755)
            
            self.logger.info(f"Created data directory: {client_dir}")
            return str(client_dir)
            
        except Exception as e:
            self.logger.error(f"Failed to create data directory: {e}")
            raise
    
    def _generate_url(self, port: int) -> str:
        """Generate URL for instance."""
        protocol = "https" if self.use_https else "http"
        return f"{protocol}://{self.host}:{port}"
    
    def _create_container(self, instance_info: InstanceInfo, env_overrides: Optional[Dict[str, str]] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Create Docker container for instance.
        
        Returns:
            Tuple of (success, container_id, error_message)
        """
        if not self.docker_available:
            return False, None, "Docker not available"
        
        try:
            # Prepare environment variables
            environment = self.n8n_base_env.copy()
            
            # Add default n8n environment
            environment.update({
                'N8N_PORT': '5678',
                'N8N_PROTOCOL': 'http',
                'N8N_HOST': '0.0.0.0',
                'WEBHOOK_URL': instance_info.url,
                'N8N_BASIC_AUTH_ACTIVE': 'true',
                'N8N_BASIC_AUTH_USER': 'admin',
                'N8N_BASIC_AUTH_PASSWORD': 'admin123',  # Should be configurable
                'N8N_USER_FOLDER': '/home/node/.n8n',
                'EXECUTIONS_DATA_SAVE_ON_ERROR': 'all',
                'EXECUTIONS_DATA_SAVE_ON_SUCCESS': 'all'
            })
            
            # Apply environment overrides
            if env_overrides:
                environment.update(env_overrides)
            
            container_name = f"n8n-{instance_info.client_id}"
            
            # Create container
            container = self.docker_client.containers.run(
                image=self.n8n_image,
                name=container_name,
                ports={'5678/tcp': instance_info.port},
                volumes={
                    instance_info.data_dir: {'bind': '/home/node/.n8n', 'mode': 'rw'}
                },
                environment=environment,
                detach=True,
                restart_policy={'Name': 'unless-stopped'},
                labels={
                    'umbra.instance.client_id': instance_info.client_id,
                    'umbra.instance.managed': 'true'
                }
            )
            
            self.logger.info(
                f"Created container for {instance_info.client_id}",
                extra={
                    "container_id": container.id,
                    "container_name": container_name,
                    "port": instance_info.port
                }
            )
            
            return True, container.id, None
            
        except Exception as e:
            error_msg = f"Failed to create container: {str(e)}"
            self.logger.error(error_msg)
            return False, None, error_msg
    
    async def create_instance(self, request: InstanceCreateRequest, user_id: int) -> InstanceCreateResult:
        """
        Create new client instance.
        
        Args:
            request: Instance creation request
            user_id: User requesting the creation
        
        Returns:
            InstanceCreateResult with success/error information
        """
        start_time = time.time()
        audit_id = self._generate_audit_id()
        
        try:
            # Validate client ID
            if not request.client or not request.client.strip():
                return InstanceCreateResult(
                    success=False,
                    error="Client ID required",
                    audit_id=audit_id
                )
            
            client_id = request.client.strip().lower()
            
            # Check if instance already exists
            existing = self.get_instance(client_id)
            if existing:
                return InstanceCreateResult(
                    success=False,
                    error=f"Instance already exists for client: {client_id}",
                    audit_id=audit_id
                )
            
            # Allocate port
            port = self._allocate_port(request.port)
            if not port:
                return InstanceCreateResult(
                    success=False,
                    error="No available ports",
                    audit_id=audit_id
                )
            
            # Create data directory
            data_dir = self._create_data_directory(client_id)
            
            # Generate display name and URL
            display_name = request.name or f"n8n-{client_id}"
            url = self._generate_url(port)
            
            # Create instance info
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            instance_info = InstanceInfo(
                client_id=client_id,
                display_name=display_name,
                url=url,
                port=port,
                data_dir=data_dir,
                status='stopped',  # Will be updated after container creation
                reserved=False,
                created_at=timestamp,
                updated_at=timestamp
            )
            
            # Create Docker container
            container_success, container_id, container_error = self._create_container(
                instance_info, request.env_overrides
            )
            
            if container_success:
                instance_info.status = 'running'
                instance_info.container_id = container_id
                instance_info.container_name = f"n8n-{client_id}"
            else:
                instance_info.status = 'stopped'
                self.logger.warning(f"Container creation failed: {container_error}")
            
            # Store in database
            env_overrides_json = json.dumps(request.env_overrides or {})
            
            self.db.execute("""
                INSERT INTO instances_registry (
                    client_id, display_name, url, port, data_dir, status, reserved,
                    created_at, updated_at, container_id, container_name, env_overrides
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                instance_info.client_id,
                instance_info.display_name,
                instance_info.url,
                instance_info.port,
                instance_info.data_dir,
                instance_info.status,
                0,  # reserved = False
                instance_info.created_at,
                instance_info.updated_at,
                instance_info.container_id,
                instance_info.container_name,
                env_overrides_json
            ))
            
            # Audit successful creation
            duration_ms = (time.time() - start_time) * 1000
            await self._audit_action(
                audit_id, user_id, "instances.create", 
                {"client": client_id, "port": port},
                "success", duration_ms
            )
            
            self.logger.info(
                f"Instance created successfully: {client_id}",
                extra={
                    "client_id": client_id,
                    "port": port,
                    "status": instance_info.status,
                    "container_created": container_success
                }
            )
            
            return InstanceCreateResult(
                success=True,
                instance=instance_info,
                audit_id=audit_id
            )
            
        except Exception as e:
            # Audit failed creation
            duration_ms = (time.time() - start_time) * 1000
            await self._audit_action(
                audit_id, user_id, "instances.create",
                {"client": request.client},
                "error", duration_ms, str(e)
            )
            
            error_msg = f"Instance creation failed: {str(e)}"
            self.logger.error(error_msg)
            
            return InstanceCreateResult(
                success=False,
                error=error_msg,
                audit_id=audit_id
            )
    
    async def delete_instance(self, client_id: str, mode: str, user_id: int) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Delete instance with specified mode.
        
        Args:
            client_id: Client ID to delete
            mode: 'keep' (preserve data) or 'wipe' (remove everything)
            user_id: User requesting deletion
        
        Returns:
            Tuple of (success, audit_id, error_message)
        """
        start_time = time.time()
        audit_id = self._generate_audit_id()
        
        if mode not in ['keep', 'wipe']:
            await self._audit_action(
                audit_id, user_id, "instances.delete",
                {"client": client_id, "mode": mode},
                "error", 0, "Invalid mode"
            )
            return False, audit_id, "Mode must be 'keep' or 'wipe'"
        
        try:
            # Get instance
            instance = self.get_instance(client_id)
            if not instance:
                return False, audit_id, f"Instance not found: {client_id}"
            
            # Stop and remove container if exists
            if instance.container_name and self.docker_available:
                try:
                    container = self.docker_client.containers.get(instance.container_name)
                    
                    # Stop container
                    if container.status == 'running':
                        container.stop(timeout=10)
                        self.logger.info(f"Stopped container: {instance.container_name}")
                    
                    # Remove container
                    container.remove(force=True)
                    self.logger.info(f"Removed container: {instance.container_name}")
                    
                except NotFound:
                    self.logger.info(f"Container not found (already removed): {instance.container_name}")
                except Exception as e:
                    self.logger.warning(f"Failed to remove container: {e}")
            
            if mode == 'wipe':
                # Remove data directory
                try:
                    import shutil
                    if os.path.exists(instance.data_dir):
                        shutil.rmtree(instance.data_dir)
                        self.logger.info(f"Removed data directory: {instance.data_dir}")
                except Exception as e:
                    self.logger.warning(f"Failed to remove data directory: {e}")
                
                # Remove from database
                self.db.execute("DELETE FROM instances_registry WHERE client_id = ?", (client_id,))
                
                status_update = "deleted"
                
            else:  # mode == 'keep'
                # Update status to archived and set reserved
                self.db.execute("""
                    UPDATE instances_registry 
                    SET status = 'archived', reserved = 1, updated_at = ?,
                        container_id = NULL, container_name = NULL
                    WHERE client_id = ?
                """, (time.strftime('%Y-%m-%d %H:%M:%S'), client_id))
                
                status_update = "archived"
            
            # Audit successful deletion
            duration_ms = (time.time() - start_time) * 1000
            await self._audit_action(
                audit_id, user_id, "instances.delete",
                {"client": client_id, "mode": mode},
                "success", duration_ms
            )
            
            self.logger.info(
                f"Instance deleted: {client_id}",
                extra={
                    "client_id": client_id,
                    "mode": mode,
                    "status": status_update
                }
            )
            
            return True, audit_id, None
            
        except Exception as e:
            # Audit failed deletion
            duration_ms = (time.time() - start_time) * 1000
            await self._audit_action(
                audit_id, user_id, "instances.delete",
                {"client": client_id, "mode": mode},
                "error", duration_ms, str(e)
            )
            
            error_msg = f"Instance deletion failed: {str(e)}"
            self.logger.error(error_msg)
            
            return False, audit_id, error_msg
    
    def _generate_audit_id(self) -> str:
        """Generate unique audit ID."""
        timestamp = str(int(time.time() * 1000))
        random_data = os.urandom(8).hex()
        return f"inst_{timestamp}_{random_data[:8]}"
    
    async def _audit_action(
        self,
        audit_id: str,
        user_id: int,
        action: str,
        params: Dict[str, Any],
        status: str,
        duration_ms: float,
        error_message: Optional[str] = None
    ):
        """Audit instance action."""
        try:
            # Generate result hash for integrity
            result_data = f"{status}:{duration_ms}:{len(str(error_message or ''))}"
            result_hash = hashlib.sha256(result_data.encode()).hexdigest()[:16]
            
            self.db.execute("""
                INSERT INTO instances_audit (
                    audit_id, user_id, action, client_id, params_redacted,
                    status, duration_ms, result_hash, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                audit_id,
                user_id,
                action,
                params.get('client'),
                str(params)[:500],  # Truncate long params
                status,
                duration_ms,
                result_hash,
                error_message[:500] if error_message else None
            ))
            
        except Exception as e:
            self.logger.error(f"Audit logging failed: {e}")
    
    def get_port_usage_stats(self) -> Dict[str, Any]:
        """Get port usage statistics."""
        try:
            start_port, end_port = self.client_port_range
            total_ports = end_port - start_port + 1
            
            # Get used ports
            query = "SELECT port FROM instances_registry WHERE status != 'deleted'"
            rows = self.db.query(query)
            used_ports = len(rows)
            
            # Get reserved ports
            query = "SELECT COUNT(*) FROM instances_registry WHERE reserved = 1 AND status != 'deleted'"
            reserved_count = self.db.query_one(query)[0]
            
            return {
                "total_ports": total_ports,
                "used_ports": used_ports,
                "available_ports": total_ports - used_ports,
                "reserved_ports": reserved_count,
                "utilization_percent": round((used_ports / total_ports) * 100, 1),
                "port_range": f"{start_port}-{end_port}"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get port stats: {e}")
            return {"error": str(e)}
    
    def format_instances_summary(self, instances: List[InstanceInfo]) -> str:
        """Format instances list for display."""
        if not instances:
            return "📋 **No instances found**"
        
        lines = [f"📋 **Instances Registry** ({len(instances)} total)\n"]
        
        for instance in instances:
            status_emoji = {
                'running': '🟢',
                'stopped': '🔴',
                'archived': '📦',
                'deleted': '❌'
            }.get(instance.status, '❓')
            
            reserved_flag = " 🔒" if instance.reserved else ""
            
            lines.append(
                f"{status_emoji} **{instance.display_name}**{reserved_flag}\n"
                f"   • Client: `{instance.client_id}`\n"
                f"   • URL: {instance.url}\n"
                f"   • Port: {instance.port}\n"
                f"   • Status: {instance.status}\n"
                f"   • Created: {instance.created_at}\n"
            )
        
        # Add port usage summary
        port_stats = self.get_port_usage_stats()
        if 'error' not in port_stats:
            lines.append(
                f"\n📊 **Port Usage**: {port_stats['used_ports']}/{port_stats['total_ports']} "
                f"({port_stats['utilization_percent']}% utilized)"
            )
        
        return "\n".join(lines)
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on instances system."""
        try:
            checks = {}
            
            # Database connectivity
            try:
                instance_count = len(self.list_instances())
                checks["database"] = {
                    "status": "ok",
                    "details": f"Registry accessible, {instance_count} instances"
                }
            except Exception as e:
                checks["database"] = {"status": "error", "details": str(e)}
            
            # Docker connectivity
            checks["docker"] = {
                "status": "ok" if self.docker_available else "warning",
                "details": "Docker available" if self.docker_available else "Docker not available"
            }
            
            # Data directory access
            try:
                self.clients_base_dir.mkdir(parents=True, exist_ok=True)
                checks["data_directory"] = {
                    "status": "ok",
                    "details": f"Base directory accessible: {self.clients_base_dir}"
                }
            except Exception as e:
                checks["data_directory"] = {"status": "error", "details": str(e)}
            
            # Port allocation
            try:
                port_stats = self.get_port_usage_stats()
                if 'error' not in port_stats:
                    checks["port_allocation"] = {
                        "status": "ok" if port_stats['available_ports'] > 10 else "warning",
                        "details": f"{port_stats['available_ports']} ports available"
                    }
                else:
                    checks["port_allocation"] = {"status": "error", "details": port_stats['error']}
            except Exception as e:
                checks["port_allocation"] = {"status": "error", "details": str(e)}
            
            # Overall status
            error_count = len([c for c in checks.values() if c["status"] == "error"])
            
            if error_count == 0:
                overall_status = "healthy"
            elif error_count <= 1:
                overall_status = "degraded"
            else:
                overall_status = "unhealthy"
            
            return {
                "status": overall_status,
                "checks": checks,
                "config": {
                    "port_range": f"{self.client_port_range[0]}-{self.client_port_range[1]}",
                    "base_dir": str(self.clients_base_dir),
                    "docker_available": self.docker_available
                }
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

# Export
__all__ = ["InstancesRegistry", "InstanceInfo", "InstanceCreateRequest", "InstanceCreateResult"]
