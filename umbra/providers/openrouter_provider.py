"""
OpenRouter provider implementation for provider-agnostic AI interface.
"""
import httpx
import json
import logging
from typing import Dict, List, Optional

from ..ai.provider_agnostic import AIProvider


class OpenRouterProvider(AIProvider):
    """OpenRouter AI provider implementation."""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.api_key = getattr(config, 'OPENROUTER_API_KEY', None)
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = getattr(config, 'OPENROUTER_MODEL', 'anthropic/claude-3-haiku')
        self.site_url = getattr(config, 'OPENROUTER_SITE_URL', 'https://umbra.ai')
        self.app_name = getattr(config, 'OPENROUTER_APP_NAME', 'Umbra')
    
    @property
    def provider_name(self) -> str:
        return "OpenRouter"
    
    def is_available(self) -> bool:
        """Check if OpenRouter is configured and available."""
        return bool(self.api_key)
    
    async def generate_response(
        self, 
        messages: List[Dict[str, str]], 
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7
    ) -> str:
        """Generate response using OpenRouter API."""
        if not self.is_available():
            raise ValueError("OpenRouter API key not configured")
        
        # Prepare messages
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        
        formatted_messages.extend(messages)
        
        # Prepare request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.site_url,
            "X-Title": self.app_name,
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                if 'choices' in data and len(data['choices']) > 0:
                    content = data['choices'][0]['message']['content']
                    return content.strip()
                else:
                    self.logger.error(f"Unexpected OpenRouter response: {data}")
                    return ""
                    
        except httpx.HTTPError as e:
            self.logger.error(f"OpenRouter HTTP error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"OpenRouter request failed: {e}")
            raise