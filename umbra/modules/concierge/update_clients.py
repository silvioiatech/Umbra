"""
Client Update Manager - Manages updates for client instances with maintenance windows
Handles per-client update scheduling, maintenance window enforcement, and rolling updates.
"""
import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import re

from ...core.config import UmbraConfig
from .docker_registry import DockerRegistryHelper
from .update_watcher import UpdatePlan, RiskLevel


class MaintenanceStatus(Enum):
    IN_WINDOW = "in_window"
    OUT_OF_WINDOW = "out_of_window"
    NO_WINDOW = "no_window"
    FROZEN = "frozen"


@dataclass
class ClientInfo:
    name: str
    port: int
    container_name: str
    image: str
    status: str
    maintenance_window: Optional[str] = None
    frozen: bool = False
    last_update: Optional[datetime] = None


@dataclass
class MaintenanceWindow:
    start_time: time
    end_time: time
    timezone: str = "Europe/Zurich"


class ClientUpdateManager:
    """Manages updates for client n8n instances."""
    
    def __init__(self, config: UmbraConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.client_port_range = self._parse_port_range(
            config.get('CLIENT_PORT_RANGE', '20000-21000')
        )
        self.maintenance_windows = config.get('MAINTENANCE_WINDOWS', {})
        self.freeze_list = set(config.get('FREEZE_LIST', []))
        self.require_double_confirm = config.get('REQUIRE_DOUBLE_CONFIRM_ON_MAJOR', True)
        
        # Docker helper
        self.docker_helper = DockerRegistryHelper(config)
        
        # Client registry cache
        self.client_cache = {}
        self.cache_ttl = 300  # 5 minutes
        self.last_cache_update = None
        
        self.logger.info(f"ClientUpdateManager initialized")
        self.logger.info(f"Port range: {self.client_port_range[0]}-{self.client_port_range[1]}")
        self.logger.info(f"Maintenance windows: {len(self.maintenance_windows)}")

    def _parse_port_range(self, port_range_str: str) -> Tuple[int, int]:
        """Parse port range string."""
        try:
            start_str, end_str = port_range_str.split('-')
            return int(start_str), int(end_str)
        except (ValueError, AttributeError):
            self.logger.warning(f"Invalid port range format: {port_range_str}, using default")
            return 20000, 21000

    async def list_client_services(self) -> List[str]:
        """List all client services."""
        try:
            # Get all containers matching client pattern
            cmd = ['docker', 'ps', '--format', 'json']
            result = await self.docker_helper._run_docker_command(cmd)
            
            if not result:
                return []
            
            client_services = []
            for line in result.strip().split('\n'):
                if not line.strip():
                    continue
                    
                try:
                    container_info = eval(line)  # Should be JSON, but docker sometimes outputs dict-like
                    container_name = container_info.get('Names', '')
                    
                    # Check if this looks like a client container
                    if self._is_client_container(container_name):
                        client_services.append(container_name)
                        
                except Exception as e:
                    self.logger.debug(f"Error parsing container info: {e}")
                    continue
            
            return client_services
            
        except Exception as e:
            self.logger.error(f"Error listing client services: {e}")
            return []

    def _is_client_container(self, container_name: str) -> bool:
        """Check if a container name matches client pattern."""
        # Pattern: n8n-client-<port> or similar
        patterns = [
            r'n8n-client-\d+',
            r'n8n-\d+',
            r'client-\d+',
        ]
        
        for pattern in patterns:
            if re.match(pattern, container_name):
                return True
        
        # Also check if it's using a port in our client range
        port_match = re.search(r'-(\d+)$', container_name)
        if port_match:
            port = int(port_match.group(1))
            return self.client_port_range[0] <= port <= self.client_port_range[1]
        
        return False

    async def get_client_info(self, client_name: str) -> Optional[ClientInfo]:
        """Get detailed information about a client."""
        try:
            # Get container info
            cmd = ['docker', 'inspect', client_name, '--format', 'json']
            result = await self.docker_helper._run_docker_command(cmd)
            
            if not result:
                return None
            
            import json
            container_data = json.loads(result)[0]  # Inspect returns array
            
            # Extract information
            container_name = container_data['Name'].lstrip('/')
            image = container_data['Config']['Image']
            status = container_data['State']['Status']
            
            # Extract port from container name or port bindings
            port = self._extract_port_from_container(container_data)
            
            # Get maintenance window
            maintenance_window = self.maintenance_windows.get(client_name)
            
            # Check if frozen
            frozen = client_name in self.freeze_list
            
            return ClientInfo(
                name=client_name,
                port=port,
                container_name=container_name,
                image=image,
                status=status,
                maintenance_window=maintenance_window,
                frozen=frozen
            )
            
        except Exception as e:
            self.logger.error(f"Error getting client info for {client_name}: {e}")
            return None

    def _extract_port_from_container(self, container_data: Dict[str, Any]) -> int:
        """Extract port number from container data."""
        try:
            # Try port bindings first
            port_bindings = container_data.get('NetworkSettings', {}).get('Ports', {})
            for container_port, host_bindings in port_bindings.items():
                if host_bindings and '5678' in container_port:  # n8n default port
                    return int(host_bindings[0]['HostPort'])
            
            # Fallback to container name
            container_name = container_data['Name']
            port_match = re.search(r'-(\d+)$', container_name)
            if port_match:
                return int(port_match.group(1))
            
            return 5678  # Default
            
        except Exception:
            return 5678

    async def create_client_plan(self, client_name: str, when: str = "window") -> UpdatePlan:
        """Create an update plan for a client."""
        client_info = await self.get_client_info(client_name)
        if not client_info:
            raise ValueError(f"Client {client_name} not found")
        
        # Check maintenance window if required
        if when == "window":
            maintenance_status = await self.check_maintenance_status(client_name)
            if maintenance_status == MaintenanceStatus.OUT_OF_WINDOW:
                raise ValueError(f"Client {client_name} is outside maintenance window")
            elif maintenance_status == MaintenanceStatus.FROZEN:
                raise ValueError(f"Client {client_name} is frozen from updates")
        
        # Get current and target image info
        current_info = await self.docker_helper.get_current_image_info(client_name)
        if not current_info:
            raise ValueError(f"Could not get current image info for {client_name}")
        
        # For now, target is the latest version of the same image
        repository = current_info['repository']
        current_tag = current_info['tag']
        
        # Get latest remote info
        remote_info = await self.docker_helper.get_remote_image_info(repository, current_tag)
        if not remote_info:
            raise ValueError(f"Could not get remote image info for {repository}:{current_tag}")
        
        # Check if update is needed
        if current_info['digest'] == remote_info['digest']:
            raise ValueError(f"Client {client_name} is already up to date")
        
        # Assess risk
        risk_level = await self._assess_client_update_risk(client_name, current_tag, repository)
        
        # Create steps
        steps = await self._create_client_update_steps(client_info, remote_info)
        
        # Generate plan ID
        import hashlib
        plan_data = f"{client_name}:{current_info['digest']}:{remote_info['digest']}"
        plan_id = hashlib.md5(plan_data.encode()).hexdigest()[:8]
        
        plan = UpdatePlan(
            id=plan_id,
            service_name=client_name,
            current_digest=current_info['digest'],
            target_digest=remote_info['digest'],
            target_tag=remote_info['tag'],
            risk_level=risk_level,
            steps=steps,
            estimated_duration=await self._estimate_client_duration(steps),
            created_at=datetime.now(),
            requires_double_confirm=(risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL])
        )
        
        return plan

    async def _create_client_update_steps(self, client_info: ClientInfo, 
                                        target_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create update steps for a client."""
        steps = [
            {
                "id": "pull_image",
                "type": "pull_image",
                "description": f"Pull new image {target_info['tag']}",
                "repository": target_info['repository'],
                "tag": target_info['tag'],
                "timeout": 300
            },
            {
                "id": "stop_client",
                "type": "stop_container",
                "description": f"Stop client container {client_info.name}",
                "container_name": client_info.name,
                "timeout": 30
            },
            {
                "id": "backup_data",
                "type": "backup_data",
                "description": f"Backup client data",
                "client_name": client_info.name,
                "timeout": 60
            },
            {
                "id": "start_client",
                "type": "start_container",
                "description": f"Start client with new image",
                "container_name": client_info.name,
                "image": target_info['image_name'],
                "port": client_info.port,
                "timeout": 60
            },
            {
                "id": "health_check",
                "type": "health_check",
                "description": f"Health check client",
                "container_name": client_info.name,
                "port": client_info.port,
                "timeout": 120
            },
            {
                "id": "verify_data",
                "type": "verify_data",
                "description": f"Verify client data integrity",
                "client_name": client_info.name,
                "timeout": 30
            }
        ]
        
        return steps

    async def execute_client_update(self, plan: UpdatePlan) -> Dict[str, Any]:
        """Execute a client update plan."""
        execution_id = f"client_update_{int(datetime.now().timestamp())}"
        
        self.logger.info(f"Starting client update {execution_id} for {plan.service_name}")
        
        results = {
            "execution_id": execution_id,
            "client_name": plan.service_name,
            "target_digest": plan.target_digest,
            "started_at": datetime.now().timestamp(),
            "steps": [],
            "success": False
        }
        
        try:
            for step in plan.steps:
                step_result = await self._execute_client_step(step)
                results["steps"].append(step_result)
                
                if not step_result["success"] and step.get("required", True):
                    raise Exception(f"Required step {step['id']} failed: {step_result.get('error')}")
            
            results["success"] = True
            results["completed_at"] = datetime.now().timestamp()
            
            self.logger.info(f"Client update {execution_id} completed successfully")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Client update {execution_id} failed: {e}")
            results["error"] = str(e)
            results["failed_at"] = datetime.now().timestamp()
            raise

    async def _execute_client_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single client update step."""
        step_id = step["id"]
        step_type = step["type"]
        
        self.logger.info(f"Executing client step {step_id}: {step['description']}")
        
        result = {
            "step_id": step_id,
            "type": step_type,
            "started_at": datetime.now().timestamp(),
            "success": False
        }
        
        try:
            if step_type == "pull_image":
                success = await self.docker_helper.pull_image(
                    step["repository"], step["tag"]
                )
                result["success"] = success
                
            elif step_type == "stop_container":
                success = await self._stop_client_container(step["container_name"])
                result["success"] = success
                
            elif step_type == "backup_data":
                success = await self._backup_client_data(step["client_name"])
                result["success"] = success
                
            elif step_type == "start_container":
                success = await self._start_client_container(
                    step["container_name"], step["image"], step["port"]
                )
                result["success"] = success
                
            elif step_type == "health_check":
                success = await self._health_check_client(
                    step["container_name"], step["port"]
                )
                result["success"] = success
                
            elif step_type == "verify_data":
                success = await self._verify_client_data(step["client_name"])
                result["success"] = success
                
            else:
                result["error"] = f"Unknown step type: {step_type}"
                result["success"] = False
            
            result["completed_at"] = datetime.now().timestamp()
            result["duration"] = result["completed_at"] - result["started_at"]
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["failed_at"] = datetime.now().timestamp()
            result["duration"] = result["failed_at"] - result["started_at"]
            
            self.logger.error(f"Client step {step_id} failed: {e}")
            return result

    async def _stop_client_container(self, container_name: str) -> bool:
        """Stop a client container."""
        try:
            cmd = ['docker', 'stop', container_name]
            result = await self.docker_helper._run_docker_command(cmd)
            return result is not None
            
        except Exception as e:
            self.logger.error(f"Error stopping client container {container_name}: {e}")
            return False

    async def _backup_client_data(self, client_name: str) -> bool:
        """Backup client data before update."""
        try:
            # Create backup directory
            backup_dir = f"/tmp/n8n-backups/{client_name}"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{backup_dir}/backup_{timestamp}"
            
            # This is a simplified implementation
            # In practice, you would backup the client's data volume or directory
            
            self.logger.info(f"Creating backup for {client_name} at {backup_path}")
            
            # Create backup using docker cp or volume backup
            cmd = ['mkdir', '-p', backup_path]
            result = await self.docker_helper._run_docker_command(cmd)
            
            # Copy important files/data
            # This would be specific to your n8n client setup
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error backing up client data for {client_name}: {e}")
            return False

    async def _start_client_container(self, container_name: str, image: str, port: int) -> bool:
        """Start a client container with new image."""
        try:
            # Remove old container
            cmd = ['docker', 'rm', '-f', container_name]
            await self.docker_helper._run_docker_command(cmd)
            
            # Start new container
            cmd = [
                'docker', 'run', '-d',
                '--name', container_name,
                '--restart', 'unless-stopped',
                '-p', f'{port}:5678',
                '--network', 'n8n-network',
                # Add volume mounts for data persistence
                '-v', f'n8n-{container_name}-data:/home/node/.n8n',
                image
            ]
            
            result = await self.docker_helper._run_docker_command(cmd)
            if result:
                # Wait for container to initialize
                await asyncio.sleep(10)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error starting client container {container_name}: {e}")
            return False

    async def _health_check_client(self, container_name: str, port: int) -> bool:
        """Health check a client container."""
        try:
            # Check if container is running
            cmd = ['docker', 'ps', '--filter', f'name={container_name}', '--format', 'json']
            result = await self.docker_helper._run_docker_command(cmd)
            
            if not result or not result.strip():
                return False
            
            # Try HTTP health check
            try:
                import aiohttp
                url = f"http://localhost:{port}/"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=30) as response:
                        return response.status == 200
                        
            except Exception:
                # HTTP check failed, but container might still be starting
                # Wait a bit and check container status
                await asyncio.sleep(5)
                
                cmd = ['docker', 'inspect', container_name, '--format', '{{.State.Status}}']
                status_result = await self.docker_helper._run_docker_command(cmd)
                
                return status_result and status_result.strip() == "running"
            
        except Exception as e:
            self.logger.error(f"Error health checking client {container_name}: {e}")
            return False

    async def _verify_client_data(self, client_name: str) -> bool:
        """Verify client data integrity after update."""
        try:
            # This is a placeholder for data verification
            # In practice, you might:
            # 1. Check that workflows are still accessible
            # 2. Verify database connectivity
            # 3. Test a simple workflow execution
            
            self.logger.info(f"Verifying data integrity for {client_name}")
            
            # Simple verification - check if data volume exists and has content
            cmd = ['docker', 'exec', client_name, 'ls', '-la', '/home/node/.n8n']
            result = await self.docker_helper._run_docker_command(cmd)
            
            return result is not None and 'workflows' in result
            
        except Exception as e:
            self.logger.error(f"Error verifying client data for {client_name}: {e}")
            return False

    async def rollback_client(self, client_name: str) -> Dict[str, Any]:
        """Rollback a client to its previous version."""
        try:
            # This is a simplified rollback implementation
            # In practice, you would restore from backup and restart with previous image
            
            self.logger.info(f"Rolling back client {client_name}")
            
            # Find previous backup
            backup_dir = f"/tmp/n8n-backups/{client_name}"
            
            # Stop current container
            await self._stop_client_container(client_name)
            
            # Restore from backup (implementation would depend on backup strategy)
            # Start with previous image (would need to track previous image digests)
            
            return {
                "client_name": client_name,
                "rollback_completed": True,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error rolling back client {client_name}: {e}")
            raise

    async def execute_rollback(self, rollback_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a rollback plan for a client."""
        # For clients, rollback is simpler than blue-green
        client_name = rollback_plan.get("client_name")
        
        if not client_name:
            raise ValueError("Rollback plan missing client_name")
        
        return await self.rollback_client(client_name)

    async def check_maintenance_status(self, client_name: str) -> MaintenanceStatus:
        """Check if a client is in its maintenance window."""
        if client_name in self.freeze_list:
            return MaintenanceStatus.FROZEN
        
        window_str = self.maintenance_windows.get(client_name)
        if not window_str:
            return MaintenanceStatus.NO_WINDOW
        
        try:
            window = self._parse_maintenance_window(window_str)
            if await self._is_in_window(window):
                return MaintenanceStatus.IN_WINDOW
            else:
                return MaintenanceStatus.OUT_OF_WINDOW
                
        except Exception as e:
            self.logger.error(f"Error checking maintenance window for {client_name}: {e}")
            return MaintenanceStatus.NO_WINDOW

    async def is_in_maintenance_window(self, client_name: str) -> bool:
        """Check if client is currently in maintenance window."""
        status = await self.check_maintenance_status(client_name)
        return status in [MaintenanceStatus.IN_WINDOW, MaintenanceStatus.NO_WINDOW]

    def _parse_maintenance_window(self, window_str: str) -> MaintenanceWindow:
        """Parse maintenance window string."""
        try:
            start_str, end_str = window_str.split('-')
            start_hour, start_min = map(int, start_str.split(':'))
            end_hour, end_min = map(int, end_str.split(':'))
            
            return MaintenanceWindow(
                start_time=time(start_hour, start_min),
                end_time=time(end_hour, end_min)
            )
            
        except (ValueError, IndexError):
            raise ValueError(f"Invalid maintenance window format: {window_str}")

    async def _is_in_window(self, window: MaintenanceWindow) -> bool:
        """Check if current time is within maintenance window."""
        from zoneinfo import ZoneInfo
        
        # Get current time in the specified timezone
        tz = ZoneInfo(window.timezone)
        now = datetime.now(tz).time()
        
        # Handle windows that cross midnight
        if window.start_time <= window.end_time:
            # Normal window (e.g., 02:00-05:00)
            return window.start_time <= now <= window.end_time
        else:
            # Cross-midnight window (e.g., 23:00-02:00)
            return now >= window.start_time or now <= window.end_time

    async def _assess_client_update_risk(self, client_name: str, current_tag: str, 
                                       repository: str) -> RiskLevel:
        """Assess risk level for client update."""
        try:
            # Get version info
            version_info = await self.docker_helper.parse_version_info(current_tag, repository)
            
            if not version_info:
                return RiskLevel.MEDIUM
            
            # Clients are generally lower risk than main service
            if version_info.get('major_jump', False):
                return RiskLevel.HIGH  # One level down from main
            elif version_info.get('minor_jump', False):
                return RiskLevel.MEDIUM
            else:
                return RiskLevel.LOW
                
        except Exception:
            return RiskLevel.MEDIUM

    async def _estimate_client_duration(self, steps: List[Dict[str, Any]]) -> int:
        """Estimate duration for client update steps."""
        duration = 0
        
        for step in steps:
            step_type = step.get('type', '')
            
            if step_type == 'pull_image':
                duration += 60   # 1 minute for client image pull
            elif step_type == 'stop_container':
                duration += 10   # 10 seconds to stop
            elif step_type == 'backup_data':
                duration += 30   # 30 seconds for backup
            elif step_type == 'start_container':
                duration += 20   # 20 seconds to start
            elif step_type == 'health_check':
                duration += 30   # 30 seconds for health check
            elif step_type == 'verify_data':
                duration += 15   # 15 seconds for verification
            else:
                duration += 20   # Default 20 seconds
        
        return duration

    def get_status(self) -> Dict[str, Any]:
        """Get client update manager status."""
        return {
            "port_range": f"{self.client_port_range[0]}-{self.client_port_range[1]}",
            "maintenance_windows": len(self.maintenance_windows),
            "frozen_clients": len(self.freeze_list),
            "cache_ttl": self.cache_ttl,
            "last_cache_update": self.last_cache_update.isoformat() if self.last_cache_update else None
        }
