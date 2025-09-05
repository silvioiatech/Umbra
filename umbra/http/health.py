"""
Health check HTTP server for Railway deployment.
Provides /health endpoint and request ID middleware.
"""
import json
import uuid
import time
from typing import Optional, Dict, Any
from aiohttp import web
from aiohttp.web import Request, Response, StreamResponse, middleware
import logging

from ..core.config import config
from ..core.logger import get_context_logger, set_request_context, clear_request_context

logger = get_context_logger(__name__)

@middleware
async def request_id_middleware(request: Request, handler) -> StreamResponse:
    """Middleware to generate request IDs and track request latency."""
    
    # Generate unique request ID
    request_id = str(uuid.uuid4())
    
    # Set request context for logging
    set_request_context(
        request_id=request_id,
        module="http",
        action=f"{request.method}_{request.path_qs}"
    )
    
    # Add request ID to request for handlers
    request['request_id'] = request_id
    
    # Track request start time
    start_time = time.time()
    
    # Log incoming request (hide sensitive headers)
    safe_headers = {k: v for k, v in request.headers.items() 
                   if k.lower() not in ['authorization', 'cookie', 'x-api-key']}
    
    logger.info(
        "HTTP request started",
        extra={
            "method": request.method,
            "path": request.path_qs,
            "remote": request.remote,
            "user_agent": request.headers.get('User-Agent', 'Unknown'),
            "headers_count": len(request.headers)
        }
    )
    
    try:
        # Process request
        response = await handler(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Add request ID to response headers
        response.headers['X-Request-ID'] = request_id
        
        # Log completed request
        logger.info(
            "HTTP request completed",
            extra={
                "status_code": response.status,
                "duration_ms": round(duration_ms, 2),
                "response_size": response.content_length or 0
            }
        )
        
        return response
        
    except Exception as e:
        # Calculate duration for failed requests
        duration_ms = (time.time() - start_time) * 1000
        
        logger.error(
            "HTTP request failed",
            extra={
                "error": str(e),
                "duration_ms": round(duration_ms, 2),
                "exception_type": type(e).__name__
            }
        )
        
        # Return error response with request ID
        error_response = web.json_response(
            {
                "error": "Internal server error",
                "request_id": request_id,
                "status": "error"
            },
            status=500
        )
        error_response.headers['X-Request-ID'] = request_id
        
        return error_response
    
    finally:
        # Clear request context
        clear_request_context()

async def health_handler(request: Request) -> Response:
    """Health check endpoint for Railway deployment."""
    
    request_id = request.get('request_id', 'unknown')
    
    # Basic health data
    health_data = {
        "status": "ok",
        "service": "umbra-mcp",
        "version": "3.0.0",
        "environment": config.ENVIRONMENT,
        "request_id": request_id,
        "timestamp": time.time()
    }
    
    # Add service status checks
    try:
        health_data["checks"] = await _perform_health_checks()
        health_data["overall_status"] = "healthy"
        status_code = 200
        
    except Exception as e:
        logger.error(
            "Health check failed",
            extra={
                "error": str(e),
                "exception_type": type(e).__name__
            }
        )
        
        health_data["overall_status"] = "unhealthy"
        health_data["error"] = str(e)
        status_code = 503
    
    return web.json_response(health_data, status=status_code)

async def _perform_health_checks() -> Dict[str, Any]:
    """Perform basic health checks."""
    
    checks = {}
    
    # Configuration check
    checks["config"] = {
        "status": "ok" if config.TELEGRAM_BOT_TOKEN else "error",
        "details": "Configuration loaded successfully" if config.TELEGRAM_BOT_TOKEN else "Missing required configuration"
    }
    
    # OpenRouter check
    if config.OPENROUTER_API_KEY:
        checks["openrouter"] = {
            "status": "configured",
            "details": f"Using model: {config.OPENROUTER_DEFAULT_MODEL}"
        }
    else:
        checks["openrouter"] = {
            "status": "not_configured",
            "details": "OpenRouter API key not provided"
        }
    
    # R2 Storage check
    if config.feature_r2_storage:
        checks["r2_storage"] = {
            "status": "configured",
            "details": f"Using bucket: {config.R2_BUCKET}"
        }
    else:
        checks["r2_storage"] = {
            "status": "not_configured", 
            "details": "R2 storage not configured, using local storage"
        }
    
    # Permissions check
    checks["permissions"] = {
        "status": "ok",
        "details": f"{len(config.ALLOWED_USER_IDS)} allowed users, {len(config.ALLOWED_ADMIN_IDS)} admins"
    }
    
    return checks

async def root_handler(request: Request) -> Response:
    """Root endpoint with service information."""
    
    request_id = request.get('request_id', 'unknown')
    
    service_info = {
        "name": "Umbra MCP",
        "description": "Claude Desktop-style AI with MCP modules",
        "version": "3.0.0",
        "architecture": "Railway + Telegram + OpenRouter + R2",
        "endpoints": {
            "/": "Service information",
            "/health": "Health check and status",
        },
        "modules": [
            "concierge",
            "finance", 
            "business",
            "production",
            "creator"
        ],
        "features": {
            "ai_integration": config.feature_ai_integration,
            "r2_storage": config.feature_r2_storage,
            "metrics_collection": config.feature_metrics_collection
        },
        "environment": config.ENVIRONMENT,
        "request_id": request_id
    }
    
    return web.json_response(service_info)

def create_health_app() -> web.Application:
    """Create aiohttp application with health endpoints and middleware."""
    
    # Create application with middleware
    app = web.Application(
        middlewares=[request_id_middleware]
    )
    
    # Add routes
    app.router.add_get('/', root_handler)
    app.router.add_get('/health', health_handler)
    
    # Add CORS headers for development
    if config.ENVIRONMENT == 'development':
        
        @middleware
        async def cors_middleware(request: Request, handler):
            response = await handler(request)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            return response
        
        app.middlewares.append(cors_middleware)
    
    logger.info(
        "Health app created",
        extra={
            "environment": config.ENVIRONMENT,
            "middleware_count": len(app.middlewares),
            "route_count": len(list(app.router.routes()))
        }
    )
    
    return app

# Utility function for manual health checks
async def check_service_health() -> Dict[str, Any]:
    """Manually check service health (for use in other modules)."""
    
    try:
        checks = await _perform_health_checks()
        
        # Determine overall health
        unhealthy_services = [
            name for name, check in checks.items() 
            if check.get("status") == "error"
        ]
        
        return {
            "healthy": len(unhealthy_services) == 0,
            "checks": checks,
            "unhealthy_services": unhealthy_services
        }
        
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "checks": {}
        }

# Export public functions
__all__ = [
    "create_health_app",
    "health_handler", 
    "root_handler",
    "check_service_health"
]
