"""
Monitoring module for the Umbra Bot - Phase 1 implementation.

Provides system health monitoring and status reporting capabilities.
"""

import psutil
import platform
import sys
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta

from ..core.module_base import ModuleBase
from ..core.envelope import InternalEnvelope
from ..core.feature_flags import is_enabled


class MonitoringModule(ModuleBase):
    """
    Monitoring module for system health checks and metrics collection.
    
    Phase 1: Basic health checks and system status
    Future phases: Advanced metrics, alerting, performance monitoring
    """
    
    def __init__(self):
        """Initialize monitoring module."""
        super().__init__("monitoring")
        self.startup_time = datetime.utcnow()
        self.metrics_enabled = False
        self.metrics_data = {}
        
    async def initialize(self) -> bool:
        """
        Initialize the monitoring module.
        
        Returns:
            True if initialization successful
        """
        try:
            # Check if metrics collection is enabled
            self.metrics_enabled = is_enabled("metrics_collection_enabled")
            
            # Initialize metrics storage
            if self.metrics_enabled:
                self.metrics_data = {
                    "requests_total": 0,
                    "errors_total": 0,
                    "commands_processed": {},
                    "response_times": [],
                    "health_checks": 0
                }
                self.logger.info("Metrics collection enabled")
            else:
                self.logger.info("Metrics collection disabled")
            
            # Test system access
            try:
                cpu_percent = psutil.cpu_percent()
                memory_info = psutil.virtual_memory()
                self.logger.info("System monitoring initialized",
                               cpu_percent=cpu_percent,
                               memory_percent=memory_info.percent)
            except Exception as e:
                self.logger.warning("Limited system monitoring available", error=str(e))
            
            self.logger.info("Monitoring module initialized successfully",
                           metrics_enabled=self.metrics_enabled,
                           startup_time=self.startup_time.isoformat())
            
            return True
            
        except Exception as e:
            self.logger.error("Monitoring module initialization failed", error=str(e))
            return False
    
    async def register_handlers(self) -> Dict[str, Callable]:
        """
        Register monitoring command handlers.
        
        Returns:
            Dictionary of command handlers
        """
        handlers = {
            "health": self._handle_health,
            "status": self._handle_status,
            "metrics": self._handle_metrics,
            "system": self._handle_system_info,
            "uptime": self._handle_uptime
        }
        
        return handlers
    
    async def process_envelope(self, envelope: InternalEnvelope) -> Optional[str]:
        """
        Process monitoring-related envelope.
        
        Args:
            envelope: The envelope to process
            
        Returns:
            Response message or None
        """
        action = envelope.action.lower()
        
        # Update metrics if enabled
        if self.metrics_enabled:
            self._update_metrics(envelope)
        
        if "health" in action:
            return await self._handle_health(envelope)
        elif "status" in action or "system" in action:
            return await self._handle_status(envelope)
        elif "metrics" in action:
            return await self._handle_metrics(envelope)
        elif "uptime" in action:
            return await self._handle_uptime(envelope)
        
        return None
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform monitoring module health check.
        
        Returns:
            Health status information
        """
        health_info = {
            "status": "healthy",
            "uptime_seconds": (datetime.utcnow() - self.startup_time).total_seconds(),
            "metrics_enabled": self.metrics_enabled,
            "system_accessible": True
        }
        
        # Test system monitoring capabilities
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            health_info.update({
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2)
            })
            
        except Exception as e:
            health_info["system_accessible"] = False
            health_info["system_error"] = str(e)
            health_info["status"] = "degraded"
        
        # Update health check counter
        if self.metrics_enabled:
            self.metrics_data["health_checks"] += 1
        
        return health_info
    
    async def shutdown(self):
        """Shutdown monitoring module."""
        self.logger.info("Monitoring module shutting down",
                        uptime_seconds=(datetime.utcnow() - self.startup_time).total_seconds())
        
        # TODO: Phase 2+ - Persist metrics, send final alerts
    
    # Command handlers
    
    async def _handle_health(self, envelope: InternalEnvelope) -> str:
        """
        Handle health check command.
        
        Args:
            envelope: Request envelope
            
        Returns:
            Health status message
        """
        health_info = await self._health_check_wrapper()
        
        uptime = datetime.utcnow() - self.startup_time
        uptime_str = self._format_uptime(uptime)
        
        status_emoji = "✅" if health_info["status"] == "healthy" else "⚠️"
        
        return (f"{status_emoji} **System Health Check**\n\n"
               f"**Status:** {health_info['status'].title()}\n"
               f"**Uptime:** {uptime_str}\n"
               f"**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
               f"**System Resources:**\n"
               f"• CPU Usage: {health_info.get('cpu_percent', 'N/A')}%\n"
               f"• Memory Usage: {health_info.get('memory_percent', 'N/A')}%\n"
               f"• Memory Available: {health_info.get('memory_available_gb', 'N/A')} GB\n\n"
               f"**Monitoring:**\n"
               f"• Metrics Collection: {'✅ Enabled' if self.metrics_enabled else '❌ Disabled'}\n"
               f"• Health Checks Performed: {self.metrics_data.get('health_checks', 0) if self.metrics_enabled else 'N/A'}")
    
    async def _handle_status(self, envelope: InternalEnvelope) -> str:
        """
        Handle system status command.
        
        Args:
            envelope: Request envelope
            
        Returns:
            System status message
        """
        self.logger.info("System status requested", req_id=envelope.req_id)
        
        # Get comprehensive system information
        system_info = self._get_system_info()
        
        return (f"🖥️ **System Status Report**\n\n"
               f"**Platform Information:**\n"
               f"• OS: {system_info['platform']}\n"
               f"• Python: {system_info['python_version']}\n"
               f"• Architecture: {system_info['architecture']}\n\n"
               f"**Resource Usage:**\n"
               f"• CPU Cores: {system_info['cpu_cores']}\n"
               f"• CPU Usage: {system_info['cpu_percent']}%\n"
               f"• Memory Total: {system_info['memory_total_gb']} GB\n"
               f"• Memory Used: {system_info['memory_used_gb']} GB ({system_info['memory_percent']}%)\n"
               f"• Disk Usage: {system_info['disk_percent']}%\n\n"
               f"**Bot Information:**\n"
               f"• Uptime: {system_info['uptime']}\n"
               f"• Requests Processed: {self.metrics_data.get('requests_total', 0) if self.metrics_enabled else 'N/A'}\n"
               f"• Errors: {self.metrics_data.get('errors_total', 0) if self.metrics_enabled else 'N/A'}")
    
    async def _handle_metrics(self, envelope: InternalEnvelope) -> str:
        """
        Handle metrics request command.
        
        Args:
            envelope: Request envelope
            
        Returns:
            Metrics information
        """
        if not self.metrics_enabled:
            return ("📊 Metrics collection is currently disabled.\n\n"
                   "To enable metrics, set `FEATURE_METRICS_COLLECTION=true` in your environment.")
        
        # Calculate some basic statistics
        avg_response_time = 0
        if self.metrics_data["response_times"]:
            avg_response_time = sum(self.metrics_data["response_times"]) / len(self.metrics_data["response_times"])
        
        top_commands = sorted(self.metrics_data["commands_processed"].items(), 
                            key=lambda x: x[1], reverse=True)[:5]
        
        return (f"📊 **Bot Metrics**\n\n"
               f"**Request Statistics:**\n"
               f"• Total Requests: {self.metrics_data['requests_total']}\n"
               f"• Total Errors: {self.metrics_data['errors_total']}\n"
               f"• Success Rate: {self._calculate_success_rate()}%\n"
               f"• Average Response Time: {avg_response_time:.2f}ms\n\n"
               f"**Top Commands:**\n" +
               "\n".join([f"• {cmd}: {count}" for cmd, count in top_commands[:3]]) +
               f"\n\n**Health Checks:** {self.metrics_data['health_checks']}\n"
               f"**Collection Period:** {self._format_uptime(datetime.utcnow() - self.startup_time)}")
    
    async def _handle_system_info(self, envelope: InternalEnvelope) -> str:
        """
        Handle system information command.
        
        Args:
            envelope: Request envelope
            
        Returns:
            Detailed system information
        """
        info = self._get_system_info()
        
        return (f"💻 **Detailed System Information**\n\n"
               f"**Platform:**\n"
               f"• Operating System: {info['platform']}\n"
               f"• Architecture: {info['architecture']}\n"
               f"• Python Version: {info['python_version']}\n"
               f"• Hostname: {info['hostname']}\n\n"
               f"**Hardware:**\n"
               f"• CPU Cores: {info['cpu_cores']}\n"
               f"• CPU Frequency: {info['cpu_freq']} MHz\n"
               f"• Total Memory: {info['memory_total_gb']} GB\n"
               f"• Total Disk: {info['disk_total_gb']} GB\n\n"
               f"**Current Usage:**\n"
               f"• CPU: {info['cpu_percent']}%\n"
               f"• Memory: {info['memory_percent']}%\n"
               f"• Disk: {info['disk_percent']}%\n\n"
               f"**Network:**\n"
               f"• Boot Time: {info['boot_time']}\n"
               f"• Bot Uptime: {info['uptime']}")
    
    async def _handle_uptime(self, envelope: InternalEnvelope) -> str:
        """
        Handle uptime command.
        
        Args:
            envelope: Request envelope
            
        Returns:
            Uptime information
        """
        uptime = datetime.utcnow() - self.startup_time
        uptime_str = self._format_uptime(uptime)
        
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        system_uptime = datetime.utcnow() - boot_time
        system_uptime_str = self._format_uptime(system_uptime)
        
        return (f"⏰ **Uptime Information**\n\n"
               f"**Bot Uptime:** {uptime_str}\n"
               f"**System Uptime:** {system_uptime_str}\n\n"
               f"**Started:** {self.startup_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
               f"**Current Time:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Helper methods
    
    def _update_metrics(self, envelope: InternalEnvelope):
        """Update metrics data based on envelope processing."""
        if not self.metrics_enabled:
            return
        
        self.metrics_data["requests_total"] += 1
        
        # Track command usage
        action = envelope.action
        if action in self.metrics_data["commands_processed"]:
            self.metrics_data["commands_processed"][action] += 1
        else:
            self.metrics_data["commands_processed"][action] = 1
        
        # Track response time if available
        duration = envelope.get_total_duration()
        if duration is not None:
            self.metrics_data["response_times"].append(duration)
            # Keep only last 100 response times to avoid memory issues
            if len(self.metrics_data["response_times"]) > 100:
                self.metrics_data["response_times"] = self.metrics_data["response_times"][-100:]
    
    def _calculate_success_rate(self) -> float:
        """Calculate success rate based on errors vs total requests."""
        if self.metrics_data["requests_total"] == 0:
            return 100.0
        
        success_rate = ((self.metrics_data["requests_total"] - self.metrics_data["errors_total"]) / 
                       self.metrics_data["requests_total"]) * 100
        return round(success_rate, 2)
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information."""
        try:
            cpu_freq = psutil.cpu_freq()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            
            return {
                "platform": platform.system() + " " + platform.release(),
                "architecture": platform.machine(),
                "python_version": sys.version.split()[0],
                "hostname": platform.node(),
                "cpu_cores": psutil.cpu_count(),
                "cpu_freq": round(cpu_freq.current) if cpu_freq else "Unknown",
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_used_gb": round(memory.used / (1024**3), 2),
                "memory_percent": memory.percent,
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "disk_percent": round((disk.used / disk.total) * 100, 1),
                "boot_time": boot_time.strftime('%Y-%m-%d %H:%M:%S UTC'),
                "uptime": self._format_uptime(datetime.utcnow() - self.startup_time)
            }
        except Exception as e:
            self.logger.error("Failed to get system info", error=str(e))
            return {
                "platform": "Unknown",
                "error": str(e)
            }
    
    def _format_uptime(self, uptime: timedelta) -> str:
        """Format uptime timedelta as human-readable string."""
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if not parts or (days == 0 and hours == 0):
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
        
        return ", ".join(parts)