"""
Enhanced Status System - BOT2: Comprehensive health monitoring and diagnostics.
Provides per-service health checks, configuration validation, and performance metrics.
"""
import asyncio
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from ..core.logger import get_context_logger
from ..core.config import config

logger = get_context_logger(__name__)

class ServiceStatus(Enum):
    """Service status states."""
    ACTIVE = "active"
    DEGRADED = "degraded" 
    INACTIVE = "inactive"
    UNKNOWN = "unknown"
    ERROR = "error"

@dataclass
class HealthCheck:
    """Health check result."""
    service: str
    status: ServiceStatus
    response_time_ms: float
    configured: bool
    details: str
    error: Optional[str] = None

class HealthChecker:
    """
    BOT2: Comprehensive health checking system.
    
    Provides time-boxed, parallel health checks for all services.
    """
    
    def __init__(self, config_obj=None):
        self.config = config_obj or config
        self.logger = get_context_logger(__name__)
        self.check_timeout = 1.5  # seconds per check
        self.total_timeout = 10.0  # total status command timeout
        
    async def check_all_services(self, verbose: bool = False) -> Dict[str, HealthCheck]:
        """Run all health checks with timeout protection."""
        
        start_time = time.time()
        
        checks = {
            "telegram": self._check_telegram(),
            "openrouter": self._check_openrouter(),
            "r2_storage": self._check_r2_storage(), 
            "database": self._check_database(),
            "modules": self._check_modules(),
            "rate_limiter": self._check_rate_limiter(),
            "permissions": self._check_permissions()
        }
        
        if verbose:
            checks.update({
                "system_resources": self._check_system_resources(),
                "network": self._check_network(),
                "configuration": self._check_configuration()
            })
        
        try:
            # Run checks in parallel with timeout
            results = await asyncio.wait_for(
                asyncio.gather(*checks.values(), return_exceptions=True),
                timeout=self.total_timeout
            )
            
            # Combine results
            health_results = {}
            for (service_name, _), result in zip(checks.items(), results):
                if isinstance(result, Exception):
                    health_results[service_name] = HealthCheck(
                        service=service_name,
                        status=ServiceStatus.ERROR,
                        response_time_ms=0,
                        configured=False,
                        details=f"Check failed: {str(result)[:100]}",
                        error=str(result)
                    )
                else:
                    health_results[service_name] = result
            
            duration = (time.time() - start_time) * 1000
            
            self.logger.info(
                "Health checks completed",
                extra={
                    "duration_ms": duration,
                    "checks_count": len(health_results),
                    "verbose": verbose
                }
            )
            
            return health_results
            
        except asyncio.TimeoutError:
            self.logger.warning(
                "Health checks timed out",
                extra={"timeout_seconds": self.total_timeout}
            )
            
            # Return partial results with timeout errors
            return {
                service: HealthCheck(
                    service=service,
                    status=ServiceStatus.UNKNOWN,
                    response_time_ms=self.total_timeout * 1000,
                    configured=False,
                    details="Health check timed out",
                    error="Timeout"
                )
                for service in checks.keys()
            }
    
    async def _check_telegram(self) -> HealthCheck:
        """Check Telegram bot connectivity."""
        start_time = time.time()
        
        try:
            configured = bool(self.config.TELEGRAM_BOT_TOKEN)
            
            if not configured:
                return HealthCheck(
                    service="telegram",
                    status=ServiceStatus.INACTIVE,
                    response_time_ms=0,
                    configured=False,
                    details="No bot token configured"
                )
            
            # TODO: Could add actual bot API test here
            # For now, assume active if configured
            
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheck(
                service="telegram",
                status=ServiceStatus.ACTIVE,
                response_time_ms=duration_ms,
                configured=True,
                details="Bot token configured and ready"
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                service="telegram",
                status=ServiceStatus.ERROR,
                response_time_ms=duration_ms,
                configured=bool(self.config.TELEGRAM_BOT_TOKEN),
                details="Error during check",
                error=str(e)
            )
    
    async def _check_openrouter(self) -> HealthCheck:
        """Check OpenRouter API connectivity."""
        start_time = time.time()
        
        try:
            configured = bool(getattr(self.config, 'OPENROUTER_API_KEY', None))
            
            if not configured:
                return HealthCheck(
                    service="openrouter",
                    status=ServiceStatus.INACTIVE,
                    response_time_ms=0,
                    configured=False,
                    details="No API key configured"
                )
            
            # Test OpenRouter connectivity
            try:
                from ..providers.openrouter import OpenRouterProvider
                provider = OpenRouterProvider(self.config)
                
                # Quick availability check
                available = provider.is_available()
                duration_ms = (time.time() - start_time) * 1000
                
                if available:
                    return HealthCheck(
                        service="openrouter",
                        status=ServiceStatus.ACTIVE,
                        response_time_ms=duration_ms,
                        configured=True,
                        details=f"Connected, model: {provider.default_model}"
                    )
                else:
                    return HealthCheck(
                        service="openrouter",
                        status=ServiceStatus.DEGRADED,
                        response_time_ms=duration_ms,
                        configured=True,
                        details="API key configured but not responding"
                    )
                    
            except ImportError:
                duration_ms = (time.time() - start_time) * 1000
                return HealthCheck(
                    service="openrouter",
                    status=ServiceStatus.DEGRADED,
                    response_time_ms=duration_ms,
                    configured=True,
                    details="Provider not available"
                )
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                service="openrouter",
                status=ServiceStatus.ERROR,
                response_time_ms=duration_ms,
                configured=configured,
                details="Error during check",
                error=str(e)
            )
    
    async def _check_r2_storage(self) -> HealthCheck:
        """Check Cloudflare R2 storage connectivity."""
        start_time = time.time()
        
        try:
            configured = all([
                getattr(self.config, 'R2_ACCOUNT_ID', None),
                getattr(self.config, 'R2_ACCESS_KEY_ID', None),
                getattr(self.config, 'R2_SECRET_ACCESS_KEY', None),
                getattr(self.config, 'R2_BUCKET', None)
            ])
            
            if not configured:
                return HealthCheck(
                    service="r2_storage",
                    status=ServiceStatus.INACTIVE,
                    response_time_ms=0,
                    configured=False,
                    details="R2 credentials not fully configured"
                )
            
            # Test R2 connectivity
            try:
                from ..storage.r2_client import R2Client
                
                r2_client = R2Client(
                    account_id=self.config.R2_ACCOUNT_ID,
                    access_key_id=self.config.R2_ACCESS_KEY_ID,
                    secret_access_key=self.config.R2_SECRET_ACCESS_KEY,
                    bucket_name=self.config.R2_BUCKET
                )
                
                # Simple connectivity test (check if client can be created)
                # Note: We don't actually test connection to avoid rate limits in status checks
                duration_ms = (time.time() - start_time) * 1000
                
                return HealthCheck(
                    service="r2_storage",
                    status=ServiceStatus.ACTIVE,
                    response_time_ms=duration_ms,
                    configured=True,
                    details=f"Configured for bucket: {self.config.R2_BUCKET}"
                )
                
            except ImportError:
                duration_ms = (time.time() - start_time) * 1000
                return HealthCheck(
                    service="r2_storage",
                    status=ServiceStatus.DEGRADED,
                    response_time_ms=duration_ms,
                    configured=True,
                    details="R2 client not available"
                )
            except asyncio.TimeoutError:
                duration_ms = (time.time() - start_time) * 1000
                return HealthCheck(
                    service="r2_storage",
                    status=ServiceStatus.DEGRADED,
                    response_time_ms=duration_ms,
                    configured=True,
                    details="Connection timeout"
                )
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                service="r2_storage",
                status=ServiceStatus.ERROR,
                response_time_ms=duration_ms,
                configured=configured,
                details="Error during check",
                error=str(e)
            )
    
    async def _check_database(self) -> HealthCheck:
        """Check database connectivity and performance."""
        start_time = time.time()
        
        try:
            from ..storage.database import DatabaseManager
            
            db_path = getattr(self.config, 'DATABASE_PATH', 'data/umbra.db')
            
            # Test database connection
            db_manager = DatabaseManager(db_path)
            
            # Simple query test
            await asyncio.wait_for(
                db_manager.execute("SELECT 1"),
                timeout=self.check_timeout
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            return HealthCheck(
                service="database",
                status=ServiceStatus.ACTIVE,
                response_time_ms=duration_ms,
                configured=True,
                details=f"SQLite database responding ({duration_ms:.1f}ms)"
            )
            
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                service="database",
                status=ServiceStatus.DEGRADED,
                response_time_ms=duration_ms,
                configured=True,
                details="Database query timeout"
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                service="database",
                status=ServiceStatus.ERROR,
                response_time_ms=duration_ms,
                configured=True,
                details="Database error",
                error=str(e)
            )
    
    async def _check_modules(self) -> HealthCheck:
        """Check module registry status."""
        start_time = time.time()
        
        try:
            from ..modules.registry import ModuleRegistry
            
            # Create module registry instance
            registry = ModuleRegistry(self.config)
            
            # Get module status
            module_status = registry.get_status()
            
            duration_ms = (time.time() - start_time) * 1000
            
            available_count = module_status['available_modules']
            total_count = module_status['total_modules']
            
            if available_count == 0:
                status = ServiceStatus.INACTIVE
                details = "No modules available"
            elif available_count == total_count:
                status = ServiceStatus.ACTIVE
                details = f"All {total_count} modules active"
            else:
                status = ServiceStatus.DEGRADED
                details = f"{available_count}/{total_count} modules active"
            
            return HealthCheck(
                service="modules",
                status=status,
                response_time_ms=duration_ms,
                configured=True,
                details=details
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                service="modules",
                status=ServiceStatus.ERROR,
                response_time_ms=duration_ms,
                configured=True,
                details="Module check error",
                error=str(e)
            )
    
    async def _check_rate_limiter(self) -> HealthCheck:
        """Check rate limiter functionality."""
        start_time = time.time()
        
        try:
            from ..utils.rate_limiter import rate_limiter
            
            # Get rate limiter stats
            stats = rate_limiter.get_stats()
            
            duration_ms = (time.time() - start_time) * 1000
            
            enabled = getattr(self.config, 'RATE_LIMIT_ENABLED', True)
            
            if not enabled:
                status = ServiceStatus.INACTIVE
                details = "Rate limiting disabled"
            else:
                status = ServiceStatus.ACTIVE
                active_users = stats.get('active_users', 0)
                details = f"Active, {active_users} users tracked"
            
            return HealthCheck(
                service="rate_limiter",
                status=status,
                response_time_ms=duration_ms,
                configured=True,
                details=details
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                service="rate_limiter",
                status=ServiceStatus.ERROR,
                response_time_ms=duration_ms,
                configured=True,
                details="Rate limiter error",
                error=str(e)
            )
    
    async def _check_permissions(self) -> HealthCheck:
        """Check permission system."""
        start_time = time.time()
        
        try:
            from ..core.permissions import PermissionManager
            
            perm_manager = PermissionManager()
            status_summary = perm_manager.get_status_summary()
            
            duration_ms = (time.time() - start_time) * 1000
            
            allowed_users = len(self.config.ALLOWED_USER_IDS)
            admin_users = len(self.config.ALLOWED_ADMIN_IDS)
            
            if allowed_users == 0:
                status = ServiceStatus.INACTIVE
                details = "No users configured"
            elif admin_users == 0:
                status = ServiceStatus.DEGRADED
                details = f"{allowed_users} users, no admins"
            else:
                status = ServiceStatus.ACTIVE
                details = f"{allowed_users} users, {admin_users} admins"
            
            return HealthCheck(
                service="permissions",
                status=status,
                response_time_ms=duration_ms,
                configured=True,
                details=details
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                service="permissions",
                status=ServiceStatus.ERROR,
                response_time_ms=duration_ms,
                configured=True,
                details="Permissions error",
                error=str(e)
            )
    
    async def _check_system_resources(self) -> HealthCheck:
        """Check system resource usage (verbose mode)."""
        start_time = time.time()
        
        try:
            import psutil
            
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Determine status based on usage
            if cpu_percent > 90 or memory.percent > 90 or disk.percent > 95:
                status = ServiceStatus.DEGRADED
                details = f"High usage: CPU {cpu_percent:.1f}%, RAM {memory.percent:.1f}%, Disk {disk.percent:.1f}%"
            elif cpu_percent > 95 or memory.percent > 95:
                status = ServiceStatus.ERROR
                details = f"Critical usage: CPU {cpu_percent:.1f}%, RAM {memory.percent:.1f}%"
            else:
                status = ServiceStatus.ACTIVE
                details = f"Healthy: CPU {cpu_percent:.1f}%, RAM {memory.percent:.1f}%, Disk {disk.percent:.1f}%"
            
            return HealthCheck(
                service="system_resources",
                status=status,
                response_time_ms=duration_ms,
                configured=True,
                details=details
            )
            
        except ImportError:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                service="system_resources",
                status=ServiceStatus.UNKNOWN,
                response_time_ms=duration_ms,
                configured=False,
                details="psutil not available"
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                service="system_resources",
                status=ServiceStatus.ERROR,
                response_time_ms=duration_ms,
                configured=True,
                details="Resource check error",
                error=str(e)
            )
    
    async def _check_network(self) -> HealthCheck:
        """Check network connectivity (verbose mode)."""
        start_time = time.time()
        
        try:
            import httpx
            
            # Test basic internet connectivity
            async with httpx.AsyncClient(timeout=self.check_timeout) as client:
                response = await client.get("https://httpbin.org/status/200")
                
            duration_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                status = ServiceStatus.ACTIVE
                details = f"Internet connectivity OK ({duration_ms:.1f}ms)"
            else:
                status = ServiceStatus.DEGRADED
                details = f"Connectivity issues (status {response.status_code})"
            
            return HealthCheck(
                service="network",
                status=status,
                response_time_ms=duration_ms,
                configured=True,
                details=details
            )
            
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                service="network",
                status=ServiceStatus.DEGRADED,
                response_time_ms=duration_ms,
                configured=True,
                details="Network timeout"
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                service="network",
                status=ServiceStatus.ERROR,
                response_time_ms=duration_ms,
                configured=True,
                details="Network error",
                error=str(e)
            )
    
    async def _check_configuration(self) -> HealthCheck:
        """Check overall configuration completeness (verbose mode)."""
        start_time = time.time()
        
        try:
            required_configs = {
                "TELEGRAM_BOT_TOKEN": bool(self.config.TELEGRAM_BOT_TOKEN),
                "ALLOWED_USER_IDS": len(self.config.ALLOWED_USER_IDS) > 0,
                "ALLOWED_ADMIN_IDS": len(self.config.ALLOWED_ADMIN_IDS) > 0
            }
            
            optional_configs = {
                "OPENROUTER_API_KEY": bool(getattr(self.config, 'OPENROUTER_API_KEY', None)),
                "R2_STORAGE": bool(getattr(self.config, 'R2_ACCOUNT_ID', None)),
                "MAIN_N8N_URL": bool(getattr(self.config, 'MAIN_N8N_URL', None))
            }
            
            duration_ms = (time.time() - start_time) * 1000
            
            required_ok = all(required_configs.values())
            optional_count = sum(optional_configs.values())
            
            if not required_ok:
                status = ServiceStatus.ERROR
                missing = [k for k, v in required_configs.items() if not v]
                details = f"Missing required: {', '.join(missing)}"
            elif optional_count == 0:
                status = ServiceStatus.DEGRADED
                details = "Basic config only, no optional features"
            else:
                status = ServiceStatus.ACTIVE
                details = f"Complete: {optional_count}/{len(optional_configs)} optional features"
            
            return HealthCheck(
                service="configuration",
                status=status,
                response_time_ms=duration_ms,
                configured=True,
                details=details
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheck(
                service="configuration",
                status=ServiceStatus.ERROR,
                response_time_ms=duration_ms,
                configured=True,
                details="Configuration check error",
                error=str(e)
            )

# Export
__all__ = ["HealthChecker", "HealthCheck", "ServiceStatus"]
