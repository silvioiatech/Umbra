"""Web server for metrics endpoint and health checks."""
import asyncio
import logging
from aiohttp import web, ClientError
from typing import Optional
import json
import time
import psutil
import os

from .metrics import metrics
from .audit import audit_logger

class MetricsServer:
    """HTTP server for Prometheus metrics and admin endpoints."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.logger = logging.getLogger(__name__)
        self.start_time = time.time()
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup HTTP routes."""
        self.app.router.add_get('/metrics', self._metrics_handler)
        self.app.router.add_get('/health', self._health_handler)
        self.app.router.add_get('/admin/metrics', self._admin_metrics_handler)
        self.app.router.add_get('/admin/audit', self._admin_audit_handler)
        
        # Add CORS headers for admin endpoints
        self.app.middlewares.append(self._cors_middleware)
    
    async def _cors_middleware(self, request, handler):
        """Add CORS headers for cross-origin requests."""
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    async def _metrics_handler(self, request):
        """Prometheus metrics endpoint."""
        try:
            # Update system metrics before serving
            self._update_system_metrics()
            
            # Get metrics in Prometheus format
            prometheus_data = metrics.get_prometheus_metrics()
            
            return web.Response(
                text=prometheus_data,
                content_type='text/plain; charset=utf-8'
            )
        except Exception as e:
            self.logger.error(f"Error serving metrics: {e}")
            return web.Response(text="Error generating metrics", status=500)
    
    async def _health_handler(self, request):
        """Health check endpoint."""
        try:
            uptime = time.time() - self.start_time
            
            health_data = {
                "status": "healthy",
                "uptime_seconds": uptime,
                "timestamp": time.time(),
                "version": "1.0.0",  # Could be loaded from config
                "components": {
                    "audit_logger": "healthy",
                    "metrics_collector": "healthy",
                    "rbac_system": "healthy"
                }
            }
            
            return web.json_response(health_data)
        except Exception as e:
            self.logger.error(f"Error in health check: {e}")
            return web.json_response(
                {"status": "unhealthy", "error": str(e)},
                status=500
            )
    
    async def _admin_metrics_handler(self, request):
        """Admin metrics dashboard endpoint."""
        try:
            # Get query parameters
            format_type = request.query.get('format', 'json')
            
            if format_type == 'prometheus':
                return await self._metrics_handler(request)
            
            # Get metrics summary
            summary = metrics.get_metrics_summary()
            
            # Add system info
            summary['system'] = self._get_system_info()
            
            return web.json_response(summary)
            
        except Exception as e:
            self.logger.error(f"Error serving admin metrics: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def _admin_audit_handler(self, request):
        """Admin audit log endpoint."""
        try:
            # Get query parameters
            user_id = request.query.get('user_id')
            module = request.query.get('module')
            action = request.query.get('action')
            status = request.query.get('status')
            limit = int(request.query.get('limit', '100'))
            days = int(request.query.get('days', '1'))
            
            # If user_id is provided, get user summary
            if user_id:
                try:
                    user_id_int = int(user_id)
                    summary = audit_logger.get_user_activity_summary(user_id_int, days)
                    return web.json_response(summary)
                except ValueError:
                    return web.json_response({"error": "Invalid user_id"}, status=400)
            
            # Otherwise get filtered events
            from datetime import datetime, timedelta
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            events = audit_logger.query_events(
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                module=module,
                action=action,
                status=status,
                limit=limit
            )
            
            return web.json_response({
                "events": events,
                "total": len(events),
                "filters": {
                    "module": module,
                    "action": action,
                    "status": status,
                    "days": days,
                    "limit": limit
                }
            })
            
        except Exception as e:
            self.logger.error(f"Error serving audit data: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    def _update_system_metrics(self):
        """Update system metrics."""
        try:
            uptime = time.time() - self.start_time
            
            # Get memory usage
            process = psutil.Process()
            memory_usage = process.memory_info().rss
            
            metrics.update_system_metrics(uptime, memory_usage)
            
        except Exception as e:
            self.logger.error(f"Error updating system metrics: {e}")
    
    def _get_system_info(self) -> dict:
        """Get system information."""
        try:
            process = psutil.Process()
            
            return {
                "pid": os.getpid(),
                "cpu_percent": process.cpu_percent(),
                "memory_mb": process.memory_info().rss / 1024 / 1024,
                "uptime_seconds": time.time() - self.start_time,
                "threads": process.num_threads(),
                "open_files": len(process.open_files()),
            }
        except Exception:
            return {"error": "Unable to get system info"}
    
    async def start(self):
        """Start the metrics server."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            
            self.logger.info(f"Metrics server started on http://{self.host}:{self.port}")
            self.logger.info(f"Endpoints available:")
            self.logger.info(f"  - /metrics (Prometheus format)")
            self.logger.info(f"  - /health (Health check)")
            self.logger.info(f"  - /admin/metrics (Admin dashboard)")
            self.logger.info(f"  - /admin/audit (Audit logs)")
            
        except Exception as e:
            self.logger.error(f"Failed to start metrics server: {e}")
            raise
    
    async def stop(self):
        """Stop the metrics server."""
        try:
            if self.site:
                await self.site.stop()
            if self.runner:
                await self.runner.cleanup()
            
            self.logger.info("Metrics server stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping metrics server: {e}")

# Global instance
metrics_server = MetricsServer()