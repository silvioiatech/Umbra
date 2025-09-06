"""
OpenRouter Provider - F3R1: OpenRouter integration for Umbra AI Agent.
Adapted from working implementation with F3R1 AI Agent interface.
"""
import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from enum import Enum
import httpx

from ..ai.agent import AIProvider, AgentRequest, AgentResponse, AgentCapability
from ..core.logger import get_context_logger

logger = get_context_logger(__name__)


class ModelRole(Enum):
    """AI model roles for different tasks."""
    PLANNER = "planner"
    BUILDER = "builder"
    CONTROLLER = "controller"
    CHAT = "chat"

class OpenRouterProvider(AIProvider):
    """OpenRouter API provider with F3R1 AI Agent interface."""

    def __init__(self, config):
        """Initialize OpenRouter provider."""
        self.config = config
        self.api_key = config.OPENROUTER_API_KEY
        self.base_url = config.OPENROUTER_BASE_URL.rstrip("/")
        self.default_model = config.OPENROUTER_DEFAULT_MODEL
        self.timeout = 30.0
        self.max_retries = 2
        self.logger = get_context_logger(__name__)
        
        # Role-based model mapping
        self.role_models = {
            "planner": getattr(config, 'OPENROUTER_MODEL_PLANNER', self.default_model),
            "builder": getattr(config, 'OPENROUTER_MODEL_BUILDER', self.default_model),
            "controller": getattr(config, 'OPENROUTER_MODEL_CONTROLLER', self.default_model),
            "chat": getattr(config, 'OPENROUTER_MODEL_CHAT', self.default_model)
        }
        
        # Log initialization status
        if self.api_key:
            self.logger.info(
                "OpenRouter provider initialized (F3R1)",
                extra={
                    "api_key_preview": f"{self.api_key[:10]}...{self.api_key[-4:]}",
                    "base_url": self.base_url,
                    "default_model": self.default_model,
                    "role_models": self.role_models
                }
            )
        else:
            self.logger.error("OpenRouter API key not found!")
            raise ValueError("OpenRouter API key is required but not configured")

    def get_capabilities(self) -> List[AgentCapability]:
        """Get capabilities supported by OpenRouter."""
        return [
            AgentCapability.CONVERSATION,
            AgentCapability.FUNCTION_CALLING,
            AgentCapability.CODE_GENERATION,
            AgentCapability.DOCUMENT_ANALYSIS
        ]

    def is_available(self) -> bool:
        """Check if provider is available."""
        return bool(self.api_key)

    def get_model_for_role(self, role: str = "chat") -> str:
        """Get model for specific role."""
        return self.role_models.get(role, self.default_model)

    async def generate_response(self, request: AgentRequest) -> AgentResponse:
        """Generate response using OpenRouter API (F3R1 interface)."""
        
        start_time = time.time()
        
        try:
            # Determine model to use (check context for role)
            role = request.context.get("role", "chat") if request.context else "chat"
            model = self.get_model_for_role(role)
            
            # Prepare messages
            messages = [
                {"role": "user", "content": request.message}
            ]
            
            # Add context if provided
            if request.context and request.context.get("system_prompt"):
                messages.insert(0, {
                    "role": "system", 
                    "content": request.context["system_prompt"]
                })
            
            # Generate completion
            content = await self.chat_completion(
                messages=messages,
                model=model,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            if content:
                return AgentResponse(
                    content=content,
                    success=True,
                    provider="openrouter",
                    model=model,
                    duration_ms=duration_ms,
                    usage={"model": model, "role": role}
                )
            else:
                return AgentResponse(
                    content="",
                    success=False,
                    error="OpenRouter returned empty response",
                    provider="openrouter",
                    model=model,
                    duration_ms=duration_ms
                )
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.logger.error(
                "OpenRouter response generation failed",
                extra={
                    "error": str(e),
                    "user_id": request.user_id,
                    "duration_ms": duration_ms
                }
            )
            
            return AgentResponse(
                content="",
                success=False,
                error=str(e),
                provider="openrouter",
                duration_ms=duration_ms
            )

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
        **kwargs
    ) -> Optional[str]:
        """
        Generate chat completion using OpenRouter.
        
        Returns:
            Generated text response or None if failed
        """
        if not self.api_key:
            self.logger.warning("OpenRouter API key not configured")
            return None
            
        model = model or self.default_model
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/silvioiatech/Umbra",
            "X-Title": "Umbra Bot F3R1"
        }

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    
                    if response.status_code == 200:
                        result = response.json()
                        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        self.logger.debug(
                            "Chat completion successful",
                            extra={"model": model, "response_length": len(content)}
                        )
                        return content
                        
                    elif response.status_code == 401:
                        self.logger.error("OpenRouter API key invalid or expired")
                        return None
                        
                    elif response.status_code == 429:
                        # Rate limit - wait and retry
                        wait_time = 2 ** attempt
                        self.logger.warning(f"Rate limited, waiting {wait_time}s (attempt {attempt + 1})")
                        if attempt < self.max_retries:
                            await asyncio.sleep(wait_time)
                            continue
                        
                    elif response.status_code >= 500:
                        # Server error - retry
                        wait_time = 2 ** attempt
                        self.logger.warning(f"Server error {response.status_code}, retrying in {wait_time}s")
                        if attempt < self.max_retries:
                            await asyncio.sleep(wait_time)
                            continue
                    else:
                        # Client error - don't retry
                        error_text = response.text[:200] if response.text else "No error details"
                        self.logger.error(f"Chat completion failed: Status {response.status_code} - {error_text}")
                        return None
                        
            except httpx.TimeoutException:
                self.logger.warning(f"Request timeout (attempt {attempt + 1})")
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except Exception as e:
                self.logger.warning(f"Chat completion error: {str(e)} (attempt {attempt + 1})")
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
        
        self.logger.error("Chat completion failed after all retries")
        return None

    async def image_generation(
        self,
        prompt: str,
        model: str = "black-forest-labs/flux-schnell",
        size: str = "1024x1024",
        **kwargs
    ) -> Optional[str]:
        """
        Generate image using OpenRouter.
        
        Returns:
            Image URL or None if failed
        """
        if not self.api_key:
            self.logger.warning("OpenRouter API key not configured")
            return None
            
        url = f"{self.base_url}/images/generations"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size,
            **kwargs
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/silvioiatech/Umbra",
            "X-Title": "Umbra Bot F3R1"
        }

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    
                    if response.status_code == 200:
                        result = response.json()
                        image_url = result.get("data", [{}])[0].get("url", "")
                        self.logger.debug(f"Image generation successful: {model}")
                        return image_url
                        
                    elif response.status_code == 401:
                        self.logger.error("OpenRouter API key invalid for image generation")
                        return None
                        
                    elif response.status_code == 429:
                        wait_time = 2 ** attempt
                        self.logger.warning(f"Image generation rate limited, waiting {wait_time}s")
                        if attempt < self.max_retries:
                            await asyncio.sleep(wait_time)
                            continue
                        
                    elif response.status_code >= 500:
                        wait_time = 2 ** attempt
                        self.logger.warning(f"Image generation server error {response.status_code}")
                        if attempt < self.max_retries:
                            await asyncio.sleep(wait_time)
                            continue
                    else:
                        error_text = response.text[:200] if response.text else "No error details"
                        self.logger.error(f"Image generation failed: Status {response.status_code} - {error_text}")
                        return None
                        
            except httpx.TimeoutException:
                self.logger.warning(f"Image generation timeout (attempt {attempt + 1})")
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except Exception as e:
                self.logger.warning(f"Image generation error: {str(e)} (attempt {attempt + 1})")
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                    continue
        
        self.logger.error("Image generation failed after all retries")
        return None

    def get_text_models(self) -> List[str]:
        """Get list of recommended text models."""
        return [
            "anthropic/claude-3.5-sonnet:beta",
            "anthropic/claude-3-haiku",
            "openai/gpt-4o-mini", 
            "google/gemini-pro-1.5",
            "meta-llama/llama-3.1-8b-instruct"
        ]

    def get_image_models(self) -> List[str]:
        """Get list of recommended image models."""
        return [
            "black-forest-labs/flux-schnell",
            "black-forest-labs/flux-dev",
            "stability-ai/stable-diffusion-xl"
        ]

# Export
# For backwards compatibility
OpenRouterClient = OpenRouterProvider

__all__ = ["OpenRouterProvider", "OpenRouterClient", "ModelRole"]
