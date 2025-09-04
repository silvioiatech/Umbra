"""
Fixed OpenRouter API client for LLM interactions.
Provides text generation, image generation, and other AI capabilities.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional
import httpx
import logging

class OpenRouterProvider:
    """OpenRouter API provider with proper error handling."""

    def __init__(self, config):
        """Initialize OpenRouter provider."""
        self.config = config
        self.api_key = config.OPENROUTER_API_KEY
        self.base_url = config.OPENROUTER_BASE_URL.rstrip("/")
        self.default_model = config.OPENROUTER_MODEL
        self.timeout = 30.0
        self.max_retries = 2
        self.logger = logging.getLogger(__name__)
        
        # Log initialization status
        if self.api_key:
            self.logger.info(f"✅ OpenRouter provider initialized")
            self.logger.info(f"   API Key: {self.api_key[:10]}...{self.api_key[-4:]}")
            self.logger.info(f"   Base URL: {self.base_url}")
            self.logger.info(f"   Default Model: {self.default_model}")
        else:
            self.logger.error("❌ OpenRouter API key not found!")
            raise ValueError("OpenRouter API key is required but not configured")

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
            "X-Title": "Umbra Bot"
        }

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    
                    if response.status_code == 200:
                        result = response.json()
                        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        self.logger.debug(f"Chat completion successful: {model}")
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
            "X-Title": "Umbra Bot"
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

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 500,
        temperature: float = 0.7,
        **kwargs
    ) -> Optional[str]:
        """Simplified interface for generating responses."""
        return await self.chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
    
    async def is_available(self) -> bool:
        """Check if OpenRouter API is available."""
        if not self.api_key:
            return False
            
        try:
            # Simple test call
            response = await self.chat_completion([
                {"role": "user", "content": "Hello"}
            ], max_tokens=10)
            return response is not None
        except Exception:
            return False

    def get_text_models(self) -> List[str]:
        """Get list of recommended text models."""
        return [
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
