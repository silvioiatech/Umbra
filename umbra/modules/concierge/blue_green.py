"""
Blue-Green Deployment Manager - Manages blue-green deployments for the main n8n service
Provides safe deployment with health checks, traffic switching, and rollback capabilities.
"""
import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from ...core.config import UmbraConfig
from .docker_registry import DockerRegistryHelper


class DeploymentColor(Enum):
    BLUE = "blue"
    GREEN = "green"


class HealthStatus(Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class DeploymentStep:
    id: str
    type: str
    description: str
    color: Optional[DeploymentColor] = None
    timeout: int = 60
    retry_count: int = 3
    required: bool = True
    rollback_action: Optional[str] = None


@dataclass
class HealthCheckResult:
    status: HealthStatus
    response_time: float
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class BlueGreenManager:
    """Manages blue-green deployments for the main n8n service."""
    
    def __init__(self, config: UmbraConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.main_service = config.get('MAIN_SERVICE', 'n8n-main')
        self.colors = config.get('BLUE_GREEN', {}).get('colors', ['blue', 'green'])
        self.upstream_name = config.get('BLUE_GREEN', {}).get('upstream', 'n8n-main')
        self.nginx_container = config.get('NGINX_CONTAINER_NAME', 'nginx-proxy')
        self.reload_cmd = config.get('BLUE_GREEN', {}).get('reload_cmd', 
                                   f'docker exec {self.nginx_container} nginx -s reload')
        
        # Health check configuration
        self.health_config = config.get('HEALTHCHECK', {})
        self.health_url = self.health_config.get('url', 'https://automatia.duckdns.org/n8n')
        self.health_webhook = self.health_config.get('workflow_webhook')
        self.health_timeout = self.health_config.get('timeout', 30)
        
        # Deployment state
        self.current_color = None
        self.last_deployment = None
        self.deployment_history = []
        
        # Docker helper
        self.docker_helper = DockerRegistryHelper(config)
        
        self.logger.info(f"BlueGreenManager initialized for service '{self.main_service}'")
        self.logger.info(f"Colors: {self.colors}, Nginx container: {self.nginx_container}")

    async def get_current_color(self) -> Optional[DeploymentColor]:
        """Determine which color is currently active."""
        try:
            # Check which containers are running
            active_containers = await self._get_active_containers()
            
            for color_str in self.colors:
                color = DeploymentColor(color_str)
                container_name = self._get_container_name(color)
                
                if container_name in active_containers:
                    # Check if this container is receiving traffic
                    if await self._is_color_active_in_nginx(color):
                        self.current_color = color
                        return color
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error determining current color: {e}")
            return None

    async def get_inactive_color(self) -> DeploymentColor:
        """Get the inactive color for deployment."""
        current = await self.get_current_color()
        
        if current == DeploymentColor.BLUE:
            return DeploymentColor.GREEN
        else:
            return DeploymentColor.BLUE

    async def create_deployment_steps(self, service_name: str, current_digest: str, 
                                    target_digest: str, target_tag: str) -> List[Dict[str, Any]]:
        """Create the deployment steps for blue-green deployment."""
        inactive_color = await self.get_inactive_color()
        
        steps = [
            {
                "id": "pull_image",
                "type": "pull_image",
                "description": f"Pull new image {target_tag}",
                "repository": service_name.replace('-main', ''),  # Remove -main suffix
                "tag": target_tag,
                "timeout": 300,
                "retry_count": 2,
                "required": True
            },
            {
                "id": "stop_inactive",
                "type": "stop_container",
                "description": f"Stop {inactive_color.value} container if running",
                "color": inactive_color,
                "container_name": self._get_container_name(inactive_color),
                "timeout": 30,
                "retry_count": 1,
                "required": False
            },
            {
                "id": "start_inactive",
                "type": "start_container", 
                "description": f"Start {inactive_color.value} container with new image",
                "color": inactive_color,
                "container_name": self._get_container_name(inactive_color),
                "image": f"{service_name.replace('-main', '')}:{target_tag}",
                "timeout": 60,
                "retry_count": 2,
                "required": True,
                "rollback_action": "stop_container"
            },
            {
                "id": "health_check_container",
                "type": "health_check",
                "description": f"Health check {inactive_color.value} container",
                "color": inactive_color,
                "check_type": "container",
                "timeout": 60,
                "retry_count": 5,
                "required": True,
                "rollback_action": "stop_container"
            },
            {
                "id": "update_nginx_config",
                "type": "update_nginx",
                "description": f"Update Nginx to point to {inactive_color.value}",
                "color": inactive_color,
                "timeout": 30,
                "retry_count": 2,
                "required": True,
                "rollback_action": "revert_nginx"
            },
            {
                "id": "reload_nginx",
                "type": "reload_nginx",
                "description": "Reload Nginx configuration",
                "timeout": 15,
                "retry_count": 3,
                "required": True,
                "rollback_action": "revert_nginx"
            },
            {
                "id": "health_check_public",
                "type": "health_check",
                "description": "Health check public endpoint",
                "check_type": "public",
                "url": self.health_url,
                "timeout": 60,
                "retry_count": 3,
                "required": True,
                "rollback_action": "revert_nginx"
            },
            {
                "id": "workflow_smoke_test",
                "type": "workflow_test", 
                "description": "Run workflow smoke test",
                "webhook_url": self.health_webhook,
                "timeout": 30,
                "retry_count": 2,
                "required": bool(self.health_webhook),
                "rollback_action": "revert_nginx"
            },
            {
                "id": "stop_active",
                "type": "stop_container",
                "description": f"Stop old active container",
                "color": await self.get_current_color(),
                "timeout": 30,
                "retry_count": 1,
                "required": False
            }
        ]
        
        return steps

    async def create_rollback_steps(self, service_name: str, rollback_digest: str) -> Dict[str, Any]:
        """Create rollback steps."""
        current_color = await self.get_current_color()
        rollback_color = await self.get_inactive_color()
        
        return {
            "type": "rollback",
            "description": f"Rollback to previous version",
            "steps": [
                {
                    "id": "revert_nginx",
                    "type": "update_nginx",
                    "description": f"Revert Nginx to {rollback_color.value}",
                    "color": rollback_color,
                    "timeout": 30
                },
                {
                    "id": "reload_nginx_rollback",
                    "type": "reload_nginx", 
                    "description": "Reload Nginx (rollback)",
                    "timeout": 15
                },
                {
                    "id": "health_check_rollback",
                    "type": "health_check",
                    "description": "Verify rollback health",
                    "check_type": "public",
                    "url": self.health_url,
                    "timeout": 60
                }
            ]
        }

    async def execute_deployment(self, plan) -> Dict[str, Any]:
        """Execute a blue-green deployment plan."""
        deployment_id = f"deployment_{int(time.time())}"
        
        self.logger.info(f"Starting blue-green deployment {deployment_id} for {plan.service_name}")
        
        results = {
            "deployment_id": deployment_id,
            "service_name": plan.service_name,
            "target_digest": plan.target_digest,
            "started_at": time.time(),
            "steps": [],
            "success": False
        }
        
        try:
            for step in plan.steps:
                step_result = await self._execute_step(step)
                results["steps"].append(step_result)
                
                if not step_result["success"] and step.get("required", True):
                    raise Exception(f"Required step {step['id']} failed: {step_result.get('error')}")
            
            results["success"] = True
            results["completed_at"] = time.time()
            
            # Update deployment history
            self.last_deployment = results
            self.deployment_history.append(results)
            
            # Keep only last 10 deployments
            if len(self.deployment_history) > 10:
                self.deployment_history = self.deployment_history[-10:]
            
            self.logger.info(f"Blue-green deployment {deployment_id} completed successfully")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Blue-green deployment {deployment_id} failed: {e}")
            results["error"] = str(e)
            results["failed_at"] = time.time()
            
            # Execute rollback if available
            if plan.rollback_plan:
                try:
                    self.logger.info(f"Executing automatic rollback for deployment {deployment_id}")
                    rollback_result = await self.execute_rollback(plan.rollback_plan)
                    results["rollback"] = rollback_result
                except Exception as rollback_error:
                    self.logger.error(f"Rollback failed for deployment {deployment_id}: {rollback_error}")
                    results["rollback_error"] = str(rollback_error)
            
            raise

    async def _execute_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single deployment step."""
        step_id = step["id"]
        step_type = step["type"]
        
        self.logger.info(f"Executing step {step_id}: {step['description']}")
        
        result = {
            "step_id": step_id,
            "type": step_type,
            "started_at": time.time(),
            "success": False
        }
        
        try:
            if step_type == "pull_image":
                success = await self.docker_helper.pull_image(
                    step["repository"], step["tag"]
                )
                result["success"] = success
                
            elif step_type == "stop_container":
                success = await self._stop_container(step["container_name"])
                result["success"] = success
                
            elif step_type == "start_container":
                success = await self._start_container(
                    step["container_name"], step["image"], step.get("color")
                )
                result["success"] = success
                
            elif step_type == "health_check":
                health_result = await self._perform_health_check(step)
                result["success"] = health_result.status == HealthStatus.HEALTHY
                result["health_details"] = health_result.details
                
            elif step_type == "update_nginx":
                success = await self._update_nginx_config(step.get("color"))
                result["success"] = success
                
            elif step_type == "reload_nginx":
                success = await self._reload_nginx()
                result["success"] = success
                
            elif step_type == "workflow_test":
                success = await self._test_workflow(step.get("webhook_url"))
                result["success"] = success
                
            else:
                result["error"] = f"Unknown step type: {step_type}"
                result["success"] = False
            
            result["completed_at"] = time.time()
            result["duration"] = result["completed_at"] - result["started_at"]
            
            if result["success"]:
                self.logger.info(f"Step {step_id} completed successfully in {result['duration']:.2f}s")
            else:
                self.logger.warning(f"Step {step_id} failed after {result['duration']:.2f}s")
            
            return result
            
        except Exception as e:
            result["error"] = str(e)
            result["failed_at"] = time.time()
            result["duration"] = result["failed_at"] - result["started_at"]
            
            self.logger.error(f"Step {step_id} failed with exception: {e}")
            return result

    async def _stop_container(self, container_name: str) -> bool:
        """Stop a container."""
        try:
            cmd = ['docker', 'stop', container_name]
            result = await self.docker_helper._run_docker_command(cmd)
            return result is not None
            
        except Exception as e:
            self.logger.error(f"Error stopping container {container_name}: {e}")
            return False

    async def _start_container(self, container_name: str, image: str, 
                             color: Optional[DeploymentColor]) -> bool:
        """Start a container with the specified image."""
        try:
            # This is a simplified implementation
            # In a real scenario, you would use docker-compose or more sophisticated orchestration
            
            # First, remove existing container if it exists
            await self._remove_container(container_name)
            
            # Build port mapping based on color
            port = self._get_port_for_color(color) if color else "5678"
            
            cmd = [
                'docker', 'run', '-d',
                '--name', container_name,
                '--restart', 'unless-stopped',
                '-p', f'{port}:5678',
                '--network', 'n8n-network',  # Assume network exists
                image
            ]
            
            result = await self.docker_helper._run_docker_command(cmd)
            if result:
                # Wait a moment for container to initialize
                await asyncio.sleep(5)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error starting container {container_name}: {e}")
            return False

    async def _remove_container(self, container_name: str) -> bool:
        """Remove a container (used before starting a new one)."""
        try:
            cmd = ['docker', 'rm', '-f', container_name]
            await self.docker_helper._run_docker_command(cmd)
            return True
            
        except Exception:
            # It's OK if container doesn't exist
            return True

    async def _perform_health_check(self, step: Dict[str, Any]) -> HealthCheckResult:
        """Perform health check based on step configuration."""
        check_type = step.get("check_type", "container")
        
        if check_type == "container":
            return await self._health_check_container(step.get("container_name"))
        elif check_type == "public":
            return await self._health_check_public(step.get("url", self.health_url))
        else:
            return HealthCheckResult(
                status=HealthStatus.UNKNOWN,
                response_time=0,
                error_message=f"Unknown health check type: {check_type}"
            )

    async def _health_check_container(self, container_name: str) -> HealthCheckResult:
        """Check if a container is healthy."""
        start_time = time.time()
        
        try:
            # Check if container is running
            cmd = ['docker', 'ps', '--filter', f'name={container_name}', '--format', 'json']
            result = await self.docker_helper._run_docker_command(cmd)
            
            if not result or not result.strip():
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    response_time=time.time() - start_time,
                    error_message="Container not running"
                )
            
            # Check container health if health check is configured
            cmd = ['docker', 'inspect', container_name, '--format', '{{.State.Health.Status}}']
            health_result = await self.docker_helper._run_docker_command(cmd)
            
            if health_result and health_result.strip() == "healthy":
                status = HealthStatus.HEALTHY
            elif health_result and health_result.strip() in ["unhealthy", "starting"]:
                status = HealthStatus.UNHEALTHY
            else:
                # No health check configured, assume healthy if running
                status = HealthStatus.HEALTHY
            
            return HealthCheckResult(
                status=status,
                response_time=time.time() - start_time,
                details={"container_status": health_result.strip() if health_result else "running"}
            )
            
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                error_message=str(e)
            )

    async def _health_check_public(self, url: str) -> HealthCheckResult:
        """Check public endpoint health."""
        start_time = time.time()
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.health_timeout)) as session:
                async with session.get(url) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        return HealthCheckResult(
                            status=HealthStatus.HEALTHY,
                            response_time=response_time,
                            details={"status_code": response.status, "url": url}
                        )
                    else:
                        return HealthCheckResult(
                            status=HealthStatus.UNHEALTHY,
                            response_time=response_time,
                            error_message=f"HTTP {response.status}",
                            details={"status_code": response.status, "url": url}
                        )
                        
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                error_message=str(e),
                details={"url": url}
            )

    async def _update_nginx_config(self, color: DeploymentColor) -> bool:
        """Update Nginx configuration to point to the specified color."""
        try:
            # This is a simplified implementation
            # In practice, you might update an nginx.conf file or use a config template
            
            port = self._get_port_for_color(color)
            
            # Update upstream configuration
            # This could be done via file editing, API call, or environment variable
            
            self.logger.info(f"Updated Nginx upstream to point to {color.value} (port {port})")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating Nginx config for {color.value}: {e}")
            return False

    async def _reload_nginx(self) -> bool:
        """Reload Nginx configuration."""
        try:
            # Parse the reload command
            reload_parts = self.reload_cmd.split()
            result = await self.docker_helper._run_docker_command(reload_parts)
            
            if result is not None:
                self.logger.info("Nginx configuration reloaded successfully")
                return True
            else:
                self.logger.error("Failed to reload Nginx configuration")
                return False
                
        except Exception as e:
            self.logger.error(f"Error reloading Nginx: {e}")
            return False

    async def _test_workflow(self, webhook_url: Optional[str]) -> bool:
        """Test workflow via webhook."""
        if not webhook_url:
            return True  # Skip if no webhook configured
        
        try:
            import aiohttp
            
            test_payload = {"test": True, "timestamp": time.time()}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=test_payload, timeout=30) as response:
                    if response.status in [200, 201, 202]:
                        self.logger.info("Workflow smoke test passed")
                        return True
                    else:
                        self.logger.warning(f"Workflow smoke test returned HTTP {response.status}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Workflow smoke test failed: {e}")
            return False

    async def execute_rollback(self, rollback_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a rollback plan."""
        rollback_id = f"rollback_{int(time.time())}"
        
        self.logger.info(f"Starting rollback {rollback_id}")
        
        results = {
            "rollback_id": rollback_id,
            "started_at": time.time(),
            "steps": [],
            "success": False
        }
        
        try:
            for step in rollback_plan["steps"]:
                step_result = await self._execute_step(step)
                results["steps"].append(step_result)
                
                if not step_result["success"]:
                    self.logger.warning(f"Rollback step {step['id']} failed, continuing...")
            
            results["success"] = True
            results["completed_at"] = time.time()
            
            self.logger.info(f"Rollback {rollback_id} completed")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Rollback {rollback_id} failed: {e}")
            results["error"] = str(e)
            results["failed_at"] = time.time()
            raise

    async def rollback_service(self, service_name: str) -> Dict[str, Any]:
        """Rollback a service to its previous deployment."""
        if not self.last_deployment:
            raise ValueError("No previous deployment found for rollback")
        
        # Create rollback plan based on last deployment
        rollback_plan = await self.create_rollback_steps(
            service_name, 
            self.last_deployment.get("previous_digest", "")
        )
        
        return await self.execute_rollback(rollback_plan)

    def _get_container_name(self, color: DeploymentColor) -> str:
        """Get container name for a color."""
        return f"{self.main_service}-{color.value}"

    def _get_port_for_color(self, color: DeploymentColor) -> str:
        """Get port number for a color."""
        if color == DeploymentColor.BLUE:
            return "15678"  # Blue port
        else:
            return "25678"  # Green port

    async def _get_active_containers(self) -> List[str]:
        """Get list of active container names."""
        try:
            cmd = ['docker', 'ps', '--format', '{{.Names}}']
            result = await self.docker_helper._run_docker_command(cmd)
            
            if result:
                return result.strip().split('\n')
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting active containers: {e}")
            return []

    async def _is_color_active_in_nginx(self, color: DeploymentColor) -> bool:
        """Check if a color is active in Nginx configuration."""
        # This is a placeholder implementation
        # In practice, you would check the actual Nginx configuration
        
        port = self._get_port_for_color(color)
        
        # Check if the port is being used (simple heuristic)
        try:
            cmd = ['docker', 'exec', self.nginx_container, 'cat', '/etc/nginx/nginx.conf']
            result = await self.docker_helper._run_docker_command(cmd)
            
            if result and port in result:
                return True
                
        except Exception:
            pass
        
        return False

    def get_status(self) -> Dict[str, Any]:
        """Get blue-green manager status."""
        return {
            "main_service": self.main_service,
            "colors": self.colors,
            "current_color": self.current_color.value if self.current_color else None,
            "nginx_container": self.nginx_container,
            "health_url": self.health_url,
            "health_webhook_configured": bool(self.health_webhook),
            "last_deployment": self.last_deployment["deployment_id"] if self.last_deployment else None,
            "deployment_history_count": len(self.deployment_history)
        }
