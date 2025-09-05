"""
Provider-agnostic AI interface for UMBRA.
Supports multiple AI providers with fallback capabilities.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import logging


class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    @abstractmethod
    async def generate_response(
        self, 
        messages: List[Dict[str, str]], 
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7
    ) -> str:
        """Generate a response from the AI provider."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available and configured."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the name of the provider."""
        pass


class ProviderAgnosticAI:
    """Provider-agnostic AI agent that can work with multiple providers."""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.providers: List[AIProvider] = []
        self.fallback_enabled = True
        
        # Initialize available providers
        self._init_providers()
    
    def _init_providers(self):
        """Initialize available AI providers in order of preference."""
        # Try OpenRouter first (current implementation)
        if hasattr(self.config, 'OPENROUTER_API_KEY') and self.config.OPENROUTER_API_KEY:
            try:
                from ..providers.openrouter_provider import OpenRouterProvider
                provider = OpenRouterProvider(self.config)
                if provider.is_available():
                    self.providers.append(provider)
                    self.logger.info(f"✅ {provider.provider_name} initialized")
            except Exception as e:
                self.logger.warning(f"OpenRouter provider failed: {e}")
        
        # Add other providers here in the future
        # e.g., Anthropic Claude, OpenAI, local models, etc.
        
        if self.providers:
            self.logger.info(f"🤖 {len(self.providers)} AI provider(s) available")
        else:
            self.logger.info("💭 No AI providers available - using fallback mode")
    
    async def generate_response(
        self, 
        messages: List[Dict[str, str]], 
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7
    ) -> Optional[str]:
        """Generate response using available providers with fallback."""
        
        for provider in self.providers:
            try:
                if provider.is_available():
                    response = await provider.generate_response(
                        messages, system_prompt, max_tokens, temperature
                    )
                    if response:
                        return response
                    else:
                        self.logger.warning(f"{provider.provider_name} returned empty response")
            except Exception as e:
                self.logger.error(f"{provider.provider_name} failed: {e}")
                continue
        
        # If all providers fail and fallback is enabled
        if self.fallback_enabled:
            self.logger.info("All AI providers failed, using fallback response")
            return self._generate_fallback_response(messages, system_prompt)
        
        return None
    
    def _generate_fallback_response(
        self, 
        messages: List[Dict[str, str]], 
        system_prompt: Optional[str] = None
    ) -> str:
        """Generate a fallback response when AI providers are unavailable."""
        if not messages:
            return "I'm ready to help! What would you like me to do?"
        
        last_message = messages[-1].get('content', '').lower()
        
        # Simple pattern-based responses
        if any(word in last_message for word in ['hello', 'hi', 'hey']):
            return "Hello! I'm Umbra, your AI assistant. How can I help you today?"
        
        if any(word in last_message for word in ['help', 'what can you do']):
            return ("I can help you with:\n"
                   "• VPS and system management\n"
                   "• Financial tracking and budgeting\n"
                   "• Business and client management\n"
                   "• Workflow automation\n"
                   "• Content creation\n\n"
                   "Just tell me what you'd like to do!")
        
        if any(word in last_message for word in ['thanks', 'thank you']):
            return "You're welcome! Is there anything else I can help you with?"
        
        # Default response
        return ("I understand you want help with something. "
               "I have various modules available to assist you. "
               "Could you be more specific about what you'd like to do?")
    
    def is_ai_available(self) -> bool:
        """Check if any AI provider is available."""
        return any(provider.is_available() for provider in self.providers)
    
    def get_available_providers(self) -> List[str]:
        """Get list of available provider names."""
        return [provider.provider_name for provider in self.providers if provider.is_available()]
    
    def add_provider(self, provider: AIProvider):
        """Add a new AI provider."""
        if provider.is_available():
            self.providers.append(provider)
            self.logger.info(f"✅ Added provider: {provider.provider_name}")
        else:
            self.logger.warning(f"Provider {provider.provider_name} not available")