"""FastAPI middleware for Umbra services."""

import secrets
import hashlib
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .logger import UmbraLogger
from .types import Envelope, BasePayload


class AuthMiddleware:
    """Authentication middleware for Umbra services."""
    
    def __init__(self):
        self.logger = UmbraLogger("AuthMiddleware")
    
    def validate_internal_auth(self, required_api_key: Optional[str] = None):
        """Validate internal service authentication."""
        def dependency(request: Request):
            if not required_api_key:
                # No authentication required for development
                return True
            
            auth_header = request.headers.get("authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                self.logger.warning("Missing or invalid authorization header", 
                                  ip=request.client.host)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication"
                )
            
            token = auth_header[7:]  # Remove "Bearer " prefix
            if token != required_api_key:
                self.logger.warning("Invalid API key provided",
                                  ip=request.client.host)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication"
                )
            
            self.logger.debug("Internal authentication successful")
            return True
        
        return dependency
    
    def validate_telegram_webhook(self, webhook_secret: Optional[str] = None):
        """Validate Telegram webhook signature."""
        def dependency(request: Request):
            if not webhook_secret:
                # No secret configured, allow all (for development)
                return True
            
            telegram_signature = request.headers.get("x-telegram-bot-api-secret-token")
            
            if not telegram_signature or telegram_signature != webhook_secret:
                self.logger.warning("Invalid Telegram webhook signature",
                                  ip=request.client.host,
                                  has_signature=bool(telegram_signature))
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid webhook signature"
                )
            
            self.logger.debug("Telegram webhook validated")
            return True
        
        return dependency
    
    def validate_telegram_user(self, allowed_users: Optional[List[str]] = None):
        """Validate Telegram user access."""
        async def dependency(request: Request):
            # Extract user ID from request body or headers
            user_id = None
            
            # Try to get from headers first
            user_id = request.headers.get("x-user-id")
            
            # If not in headers, try to extract from body (for webhook)
            if not user_id:
                try:
                    body = await request.body()
                    if body:
                        import json
                        data = json.loads(body)
                        if "message" in data and "from" in data["message"]:
                            user_id = str(data["message"]["from"]["id"])
                except Exception:
                    pass
            
            if not user_id:
                self.logger.warning("Missing user ID in request", url=str(request.url))
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User ID required"
                )
            
            # Check if user is in allowed list
            if allowed_users and user_id not in allowed_users:
                self.logger.warning("Unauthorized user access attempt",
                                  user_id=user_id,
                                  url=str(request.url),
                                  ip=request.client.host)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            
            self.logger.debug("User authenticated", user_id=user_id, url=str(request.url))
            
            # Store user_id in request state for later use
            request.state.user_id = user_id
            return user_id
        
        return dependency
    
    @staticmethod
    def generate_validation_token(user_id: str, action: str) -> Dict[str, str]:
        """Generate validation token for critical operations."""
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
        
        logger = UmbraLogger("AuthMiddleware")
        logger.audit("Validation token generated", user_id, 
                    action=action,
                    token_hash=hashlib.sha256(token.encode()).hexdigest()[:16],
                    expires_at=expires_at)
        
        return {
            "token": token,
            "expires_at": expires_at
        }


class ValidationMiddleware:
    """Validation middleware for envelope communications."""
    
    def __init__(self):
        self.logger = UmbraLogger("ValidationMiddleware")
    
    def validate_envelope(self):
        """Validate envelope structure."""
        async def dependency(request: Request):
            try:
                body = await request.body()
                if not body:
                    raise ValueError("Empty request body")
                
                import json
                data = json.loads(body)
                
                # Basic envelope validation
                required_fields = ["req_id", "user_id", "lang", "timestamp", "payload"]
                for field in required_fields:
                    if field not in data:
                        raise ValueError(f"Missing required field: {field}")
                
                # Validate language
                if data["lang"] not in ["EN", "FR", "PT"]:
                    raise ValueError("Invalid language code")
                
                # Validate payload has action
                if "action" not in data.get("payload", {}):
                    raise ValueError("Missing action in payload")
                
                self.logger.debug("Envelope validation successful", req_id=data["req_id"])
                
                # Store parsed envelope in request state
                request.state.envelope = data
                return data
                
            except json.JSONDecodeError:
                self.logger.warning("Invalid JSON in request body")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON"
                )
            except ValueError as e:
                self.logger.warning("Envelope validation failed", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid envelope: {str(e)}"
                )
            except Exception as e:
                self.logger.error("Unexpected error during envelope validation", error=str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Validation error"
                )
        
        return dependency
    
    def validate_payload(self, service_name: str):
        """Validate payload for specific service."""
        def dependency(request: Request):
            envelope = getattr(request.state, 'envelope', None)
            if not envelope:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Envelope not validated"
                )
            
            payload = envelope.get("payload", {})
            action = payload.get("action")
            
            # Service-specific validation
            valid_actions = {
                "umbra": ["classify", "route", "execute", "clarify"],
                "finance": ["ocr", "extract", "categorize", "report", "deduplicate"],
                "concierge": ["monitor", "execute", "validate", "client_management"],
                "business": ["client_lifecycle", "create_client", "delete_client", "delegate_task"],
                "production": ["create_workflow", "deploy_workflow", "rollback_workflow"],
                "creator": ["generate_text", "generate_image", "generate_video", "generate_audio", "edit_video"]
            }
            
            if service_name in valid_actions:
                if action not in valid_actions[service_name]:
                    self.logger.warning("Invalid action for service",
                                      service=service_name,
                                      action=action)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid action '{action}' for service '{service_name}'"
                    )
            
            self.logger.debug("Payload validation successful",
                            service=service_name,
                            action=action)
            return payload
        
        return dependency


class AuditMiddleware:
    """Audit middleware for logging envelope communications."""
    
    def __init__(self):
        self.logger = UmbraLogger("AuditMiddleware")
    
    def log_envelope_communication(self):
        """Log envelope communications for audit trails."""
        async def dependency(request: Request):
            envelope = getattr(request.state, 'envelope', None)
            if envelope:
                self.logger.audit(
                    "Envelope received",
                    envelope.get("user_id", "unknown"),
                    req_id=envelope.get("req_id"),
                    action=envelope.get("payload", {}).get("action"),
                    lang=envelope.get("lang"),
                    ip=request.client.host
                )
            
            return True
        
        return dependency


# Utility functions for middleware
def get_request_user_id(request: Request) -> Optional[str]:
    """Get user ID from request state."""
    return getattr(request.state, 'user_id', None)


def get_request_envelope(request: Request) -> Optional[Dict]:
    """Get envelope from request state."""
    return getattr(request.state, 'envelope', None)