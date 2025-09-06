"""
Umbra AI Agent - F3R1: Provider-agnostic AI agent with OpenRouter integration.
Enhanced with automatic provider registration and OpenRouter support.
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from ..core.logger import get_context_logger, set_request_context

logger = get_context_logger(__name__)

class AgentCapability(Enum):
    """AI Agent capabilities."""
    CONVERSATION = "conversation"
    FUNCTION_CALLING = "function_calling" 
    CODE_GENERATION = "code_generation"
    IMAGE_ANALYSIS = "image_analysis"
    DOCUMENT_ANALYSIS = "document_analysis"

@dataclass
class AgentRequest:
    """Request to the AI agent."""
    message: str
    user_id: int
    context: Optional[Dict[str, Any]] = None
    capabilities_required: Optional[List[AgentCapability]] = None
    timeout: int = 30
    temperature: float = 0.7
    max_tokens: int = 1000

@dataclass
class AgentResponse:
    """Response from the AI agent."""
    content: str
    success: bool
    error: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    duration_ms: Optional[float] = None

class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    @abstractmethod
    async def generate_response(self, request: AgentRequest) -> AgentResponse:
        """Generate response from the AI provider."""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[AgentCapability]:
        """Get capabilities supported by this provider."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available and configured."""
        pass

class UmbraAIAgent:
    """
    Provider-agnostic AI agent for Umbra.
    
    F3R1 Implementation: Enhanced with OpenRouter auto-registration and full AI capabilities.
    """
    
    def __init__(self, config=None):
        self.config = config
        self.logger = get_context_logger(__name__)
        self.providers: Dict[str, AIProvider] = {}
        self.default_provider: Optional[str] = None
        
        # Error mapping for common issues
        self.error_mappings = {
            "timeout": "Request timed out. Please try again.",
            "rate_limit": "Too many requests. Please wait a moment.",
            "invalid_request": "Invalid request format.",
            "provider_error": "AI service temporarily unavailable.",
            "no_provider": "No AI provider available. Operating in basic mode."
        }
        
        # F3R1: Auto-register OpenRouter if available
        self._auto_register_providers()
        
        self.logger.info(
            "UmbraAIAgent F3R1 initialized",
            extra={
                "provider_count": len(self.providers),
                "default_provider": self.default_provider,
                "openrouter_available": "openrouter" in self.providers
            }
        )
    
    def _auto_register_providers(self) -> None:
        """F3R1: Automatically register available providers."""
        
        # Try to register OpenRouter if configured
        if (hasattr(self.config, 'OPENROUTER_API_KEY') and 
            self.config.OPENROUTER_API_KEY):
            
            try:
                from ..providers.openrouter import OpenRouterProvider
                
                openrouter_provider = OpenRouterProvider(self.config)
                if openrouter_provider.is_available():
                    self.register_provider("openrouter", openrouter_provider)
                    
                    self.logger.info(
                        "OpenRouter provider auto-registered",
                        extra={
                            "provider": "openrouter",
                            "is_default": self.default_provider == "openrouter"
                        }
                    )
                
            except ImportError as e:
                self.logger.warning(
                    "Failed to import OpenRouter provider",
                    extra={"error": str(e)}
                )
            except Exception as e:
                self.logger.error(
                    "Failed to register OpenRouter provider",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
    
    def register_provider(self, name: str, provider: AIProvider) -> None:
        """Register an AI provider."""
        self.providers[name] = provider
        
        if self.default_provider is None and provider.is_available():
            self.default_provider = name
        
        self.logger.info(
            "AI provider registered",
            extra={
                "provider": name,
                "available": provider.is_available(),
                "capabilities": [cap.value for cap in provider.get_capabilities()],
                "is_default": self.default_provider == name
            }
        )
    
    def get_available_providers(self) -> List[str]:
        """Get list of available providers."""
        return [
            name for name, provider in self.providers.items() 
            if provider.is_available()
        ]
    
    def get_capabilities(self, provider_name: Optional[str] = None) -> List[AgentCapability]:
        """Get capabilities for a specific provider or default."""
        if provider_name and provider_name in self.providers:
            return self.providers[provider_name].get_capabilities()
        elif self.default_provider:
            return self.providers[self.default_provider].get_capabilities()
        else:
            return []
    
    async def generate_response(
        self, 
        message: str, 
        user_id: int,
        context: Optional[Dict[str, Any]] = None,
        provider_name: Optional[str] = None,
        **kwargs
    ) -> AgentResponse:
        """
        Generate AI response using specified or default provider.
        
        F3R1 Implementation: Full OpenRouter integration with fallback handling.
        """
        
        # Set request context for logging
        request_id = set_request_context(
            user_id=user_id,
            module="ai_agent",
            action="generate_response"
        )
        
        # Create request object
        request = AgentRequest(
            message=message,
            user_id=user_id,
            context=context or {},
            timeout=kwargs.get('timeout', 30),
            temperature=kwargs.get('temperature', 0.7),
            max_tokens=kwargs.get('max_tokens', 1000)
        )
        
        self.logger.info(
            "AI request started",
            extra={
                "user_id": user_id,
                "message_length": len(message),
                "provider_requested": provider_name,
                "timeout": request.timeout
            }
        )
        
        try:
            # Determine which provider to use
            provider_to_use = provider_name or self.default_provider
            
            if not provider_to_use or provider_to_use not in self.providers:
                return self._create_fallback_response(request, "no_provider")
            
            provider = self.providers[provider_to_use]
            
            if not provider.is_available():
                return self._create_fallback_response(request, "provider_error")
            
            # Generate response with timeout
            response = await asyncio.wait_for(
                provider.generate_response(request),
                timeout=request.timeout
            )
            
            self.logger.info(
                "AI response generated",
                extra={
                    "user_id": user_id,
                    "provider": provider_to_use,
                    "success": response.success,
                    "duration_ms": response.duration_ms,
                    "response_length": len(response.content) if response.content else 0
                }
            )
            
            return response
            
        except asyncio.TimeoutError:
            self.logger.warning(
                "AI request timeout",
                extra={
                    "user_id": user_id,
                    "timeout": request.timeout,
                    "provider": provider_to_use
                }
            )
            return self._create_fallback_response(request, "timeout")
            
        except Exception as e:
            self.logger.error(
                "AI request failed",
                extra={
                    "user_id": user_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "provider": provider_to_use
                }
            )
            return self._create_fallback_response(request, "provider_error")
    
    def _create_fallback_response(self, request: AgentRequest, error_type: str) -> AgentResponse:
        """Create fallback response for errors."""
        error_message = self.error_mappings.get(error_type, "Unknown error occurred.")
        
        # F3R1: Enhanced fallback with better responses
        fallback_content = self._generate_basic_response(request.message)
        
        return AgentResponse(
            content=fallback_content,
            success=False,
            error=error_message,
            provider="fallback",
            model="basic_patterns"
        )
    
    def _generate_basic_response(self, message: str) -> str:
        """
        Generate basic pattern-based responses for F3R1.
        F3R1: This should rarely be used since we have OpenRouter + general_chat.
        """
        message_lower = message.lower()
        
        # Basic pattern matching
        if any(word in message_lower for word in ['hello', 'hi', 'hey']):
            return "Hello! I'm Umbra AI Agent. OpenRouter integration is available for enhanced conversation."
        
        if any(word in message_lower for word in ['help', 'what can you do']):
            return (
                "I'm Umbra AI Agent with F3R1 capabilities:\n\n"
                "• Full AI conversation via OpenRouter\n"
                "• Smart routing to specialized modules\n"
                "• Built-in tools (calculator, time, units)\n"
                "• System operations and monitoring\n\n"
                "Try asking natural questions or use specific commands!"
            )
        
        if any(word in message_lower for word in ['status', 'health']):
            return "🤖 AI Agent Status: F3R1 Mode with OpenRouter integration ready."
        
        # Default response
        return (
            f"I understand you're asking about: '{message}'\n\n"
            "🤖 F3R1 Mode: Enhanced AI with OpenRouter integration.\n"
            "I can help with conversations, calculations, system operations, and more!\n\n"
            "Try asking:\n"
            "• 'What's 2+2?' (calculator)\n"
            "• 'What time is it?' (time helper)\n"
            "• 'System status' (concierge module)\n"
            "• Or just chat naturally!"
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get AI agent status (F3R1 enhanced)."""
        available_providers = self.get_available_providers()
        
        return {
            "mode": "F3R1_enhanced",
            "providers_registered": len(self.providers),
            "providers_available": len(available_providers),
            "available_providers": available_providers,
            "default_provider": self.default_provider,
            "capabilities": [cap.value for cap in self.get_capabilities()],
            "openrouter_configured": "openrouter" in available_providers,
            "fallback_mode": len(available_providers) == 0
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of AI agent and providers."""
        health_status = {
            "agent_healthy": True,
            "providers": {}
        }
        
        for name, provider in self.providers.items():
            try:
                is_available = provider.is_available()
                capabilities = provider.get_capabilities()
                
                health_status["providers"][name] = {
                    "available": is_available,
                    "capabilities": [cap.value for cap in capabilities],
                    "status": "healthy" if is_available else "unavailable"
                }
            except Exception as e:
                health_status["providers"][name] = {
                    "available": False,
                    "status": "error",
                    "error": str(e)
                }
        
        # Overall health
        any_available = any(
            provider_health["available"] 
            for provider_health in health_status["providers"].values()
        )
        
        health_status["overall_status"] = "healthy" if any_available else "degraded"
        
        return health_status

# Export classes
__all__ = [
    "UmbraAIAgent", 
    "AIProvider", 
    "AgentRequest", 
    "AgentResponse", 
    "AgentCapability"
]
