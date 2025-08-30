"""Module router for forwarding requests to appropriate services."""

import httpx
import os
from typing import Dict, Any, Optional
from datetime import datetime

from umbra_shared import (
    UmbraLogger,
    RetryUtils,
    RetryConfig,
    Envelope,
    UmbraPayload,
    ModuleResult,
    retry_async,
)


class ModuleRouter:
    """Route requests to appropriate Umbra modules."""
    
    def __init__(self):
        self.logger = UmbraLogger("ModuleRouter")
        self.retry_utils = RetryUtils()
        self.retry_config = RetryUtils.create_retry_config("api")
        
        # Module configuration
        self.modules = {
            "finance": {
                "base_url": os.getenv("FINANCE_BASE_URL", "http://localhost:8081"),
                "api_key": os.getenv("FINANCE_API_KEY"),
                "health_endpoint": "/health",
                "api_endpoint": "/api/v1"
            },
            "concierge": {
                "base_url": os.getenv("CONCIERGE_BASE_URL", "http://localhost:9090"),
                "api_key": os.getenv("CONCIERGE_API_KEY"),
                "health_endpoint": "/health",
                "api_endpoint": "/api/v1"
            },
            "business": {
                "base_url": os.getenv("BUSINESS_BASE_URL", "http://localhost:8082"),
                "api_key": os.getenv("BUSINESS_API_KEY"),
                "health_endpoint": "/health",
                "api_endpoint": "/api/v1"
            },
            "production": {
                "base_url": os.getenv("PRODUCTION_BASE_URL", "http://localhost:8083"),
                "api_key": os.getenv("PRODUCTION_API_KEY"),
                "health_endpoint": "/health",
                "api_endpoint": "/api/v1"
            },
            "creator": {
                "base_url": os.getenv("CREATOR_BASE_URL", "http://localhost:8084"),
                "api_key": os.getenv("CREATOR_API_KEY"),
                "health_endpoint": "/health",
                "api_endpoint": "/api/v1"
            }
        }
    
    async def route_to_module(
        self,
        envelope: Envelope[UmbraPayload]
    ) -> ModuleResult[Any]:
        """Route envelope to the appropriate module."""
        start_time = datetime.utcnow()
        req_id = envelope.req_id
        target_module = envelope.payload.target_module
        
        if not target_module:
            return ModuleResult(
                req_id=req_id,
                status="error",
                error={
                    "type": "functional",
                    "code": "NO_TARGET_MODULE",
                    "message": "No target module specified in payload",
                    "retryable": False
                }
            )
        
        if target_module not in self.modules:
            return ModuleResult(
                req_id=req_id,
                status="error",
                error={
                    "type": "functional",
                    "code": "INVALID_MODULE",
                    "message": f"Invalid target module: {target_module}",
                    "retryable": False
                }
            )
        
        try:
            self.logger.info("Routing to module",
                           req_id=req_id,
                           target_module=target_module)
            
            # Check module health first
            is_healthy = await self.check_module_health(target_module)
            if not is_healthy:
                self.logger.warning("Target module unhealthy, trying anyway",
                                  req_id=req_id,
                                  target_module=target_module)
            
            # Send to module
            result = await self._send_to_module(target_module, envelope)
            
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            self.logger.info("Module routing successful",
                           req_id=req_id,
                           target_module=target_module,
                           status=result.get("status"))
            
            return ModuleResult(
                req_id=req_id,
                status=result.get("status", "success"),
                data=result.get("data"),
                error=result.get("error"),
                audit={
                    "module": "umbra-router",
                    "duration_ms": duration_ms,
                    "target_module": target_module
                }
            )
            
        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            self.logger.error("Module routing failed",
                            req_id=req_id,
                            target_module=target_module,
                            error=str(e))
            
            return ModuleResult(
                req_id=req_id,
                status="error",
                error={
                    "type": "technical",
                    "code": "ROUTING_ERROR",
                    "message": f"Failed to route to module: {target_module}",
                    "retryable": True
                },
                audit={
                    "module": "umbra-router",
                    "duration_ms": duration_ms
                }
            )
    
    @retry_async()
    async def _send_to_module(
        self,
        module_name: str,
        envelope: Envelope[UmbraPayload]
    ) -> Dict[str, Any]:
        """Send envelope to specific module."""
        module_config = self.modules[module_name]
        base_url = module_config["base_url"]
        api_key = module_config["api_key"]
        endpoint = f"{base_url}{module_config['api_endpoint']}"
        
        headers = {
            "Content-Type": "application/json",
            "X-Service-Name": "umbra"
        }
        
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                endpoint,
                json=envelope.model_dump(),
                headers=headers
            )
            response.raise_for_status()
            return response.json()
    
    async def check_module_health(self, module_name: str) -> bool:
        """Check if a module is available and healthy."""
        if module_name not in self.modules:
            return False
        
        try:
            module_config = self.modules[module_name]
            health_url = f"{module_config['base_url']}{module_config['health_endpoint']}"
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    health_url,
                    headers={"X-Service-Name": "umbra"}
                )
                return response.status_code == 200
                
        except Exception as e:
            self.logger.warning("Module health check failed",
                              module_name=module_name,
                              error=str(e))
            return False
    
    async def get_module_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all available modules."""
        status = {}
        
        for module_name in self.modules.keys():
            start_time = datetime.utcnow()
            
            try:
                is_available = await self.check_module_health(module_name)
                latency = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                status[module_name] = {
                    "available": is_available,
                    "latency": latency if is_available else None
                }
                
            except Exception as e:
                status[module_name] = {
                    "available": False,
                    "error": str(e)
                }
        
        return status
    
    async def route_with_fallback(
        self,
        envelope: Envelope[UmbraPayload],
        fallback_modules: Optional[list[str]] = None
    ) -> ModuleResult[Any]:
        """Route with fallback logic if primary module fails."""
        primary_module = envelope.payload.target_module
        
        if not primary_module:
            return await self.route_to_module(envelope)
        
        # Try primary module first
        result = await self.route_to_module(envelope)
        
        if result.status == "success":
            return result
        
        # Try fallback modules if provided
        if fallback_modules:
            self.logger.info("Trying fallback modules",
                           req_id=envelope.req_id,
                           primary_module=primary_module,
                           fallbacks=fallback_modules)
            
            for fallback_module in fallback_modules:
                if fallback_module == primary_module:
                    continue
                
                # Update envelope to target fallback module
                envelope.payload.target_module = fallback_module
                
                fallback_result = await self.route_to_module(envelope)
                if fallback_result.status == "success":
                    self.logger.info("Fallback routing successful",
                                   req_id=envelope.req_id,
                                   fallback_module=fallback_module)
                    return fallback_result
        
        # Return original error if all fallbacks failed
        return result