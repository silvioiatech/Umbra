"""Health check HTTP server for Umbra Railway deployment."""
import time
from typing import Dict, Any

from aiohttp import web
from aiohttp.web import Request, Response, Application, middleware

from ..core.logger import get_logger, set_request_context, clear_request_context, get_request_id


logger = get_logger(__name__)


@middleware
async def request_id_middleware(request: Request, handler) -> Response:
    """Generate and track request ID for each request."""
    set_request_context()
    request_id = get_request_id()
    request['request_id'] = request_id
    
    try:
        response = await handler(request)
        response.headers['X-Request-ID'] = request_id
        return response
    finally:
        clear_request_context()


@middleware
async def logging_middleware(request: Request, handler) -> Response:
    """Log request details with latency measurement."""
    start_time = time.time()
    request_id = request.get('request_id', 'unknown')
    
    # Log request start
    logger.info(
        "Request started",
        action="request_start",
        method=request.method,
        path=request.path,
        remote=request.remote,
        user_agent=request.headers.get('User-Agent', '').split()[0] if request.headers.get('User-Agent') else None
    )
    
    try:
        response = await handler(request)
        latency = time.time() - start_time
        
        # Log successful request
        logger.info(
            "Request completed",
            action="request_complete",
            method=request.method,
            path=request.path,
            status=response.status,
            latency_ms=round(latency * 1000, 2)
        )
        
        return response
    except Exception as e:
        latency = time.time() - start_time
        
        # Log failed request
        logger.error(
            "Request failed",
            action="request_error",
            method=request.method,
            path=request.path,
            error=str(e),
            latency_ms=round(latency * 1000, 2)
        )
        raise


@middleware 
async def security_middleware(request: Request, handler) -> Response:
    """Hide sensitive headers and add security headers."""
    response = await handler(request)
    
    # Remove sensitive headers from response
    response.headers.pop('Server', None)
    response.headers.pop('X-Powered-By', None)
    
    # Add security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    
    return response


async def health_handler(request: Request) -> Response:
    """Health check endpoint returning JSON status."""
    logger.info("Health check requested", action="health_check")
    
    health_data = {
        "status": "ok",
        "timestamp": time.time(),
        "service": "umbra",
        "version": "3.0.0",
        "request_id": request.get('request_id')
    }
    
    return web.json_response(health_data)


async def root_handler(request: Request) -> Response:
    """Root endpoint with service information."""
    logger.info("Root endpoint requested", action="root_info")
    
    info_data = {
        "name": "Umbra",
        "description": "Claude Desktop-style AI with MCP modules",
        "version": "3.0.0",
        "endpoints": {
            "/": "Service information",
            "/health": "Health check"
        },
        "request_id": request.get('request_id')
    }
    
    return web.json_response(info_data)


def create_health_app() -> Application:
    """Create and configure the health check aiohttp application."""
    # Create application with middlewares
    app = web.Application(middlewares=[
        request_id_middleware,
        logging_middleware,
        security_middleware
    ])
    
    # Add routes
    app.router.add_get('/', root_handler)
    app.router.add_get('/health', health_handler)
    
    logger.info("Health application created", action="app_created")
    
    return app