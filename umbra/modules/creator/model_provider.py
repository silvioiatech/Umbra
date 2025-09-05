"""
Creator provider interfaces and implementations.
Standardized provider routing for text, images, video, audio, music, and ASR.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import httpx


@dataclass
class GenerationResult:
    """Standard result object for all provider operations."""
    success: bool
    content: Optional[str] = None
    url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BaseProvider(ABC):
    """Base provider interface."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is properly configured and available."""
        pass


class TextProvider(BaseProvider):
    """Interface for text generation providers."""
    
    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.7,
        **kwargs
    ) -> GenerationResult:
        """Generate text content."""
        pass


class ImageProvider(BaseProvider):
    """Interface for image generation providers."""
    
    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        **kwargs
    ) -> GenerationResult:
        """Generate image content."""
        pass


class VideoProvider(BaseProvider):
    """Interface for video generation providers."""
    
    @abstractmethod
    async def generate_video(
        self,
        prompt: str,
        duration: int = 5,
        **kwargs
    ) -> GenerationResult:
        """Generate video content."""
        pass


class TTSProvider(BaseProvider):
    """Interface for text-to-speech providers."""
    
    @abstractmethod
    async def generate_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        **kwargs
    ) -> GenerationResult:
        """Generate speech from text."""
        pass


class MusicProvider(BaseProvider):
    """Interface for music generation providers."""
    
    @abstractmethod
    async def generate_music(
        self,
        prompt: str,
        duration: int = 30,
        **kwargs
    ) -> GenerationResult:
        """Generate music content."""
        pass


class ASRProvider(BaseProvider):
    """Interface for automatic speech recognition providers."""
    
    @abstractmethod
    async def transcribe_audio(
        self,
        audio_data: bytes,
        format: str = "wav",
        **kwargs
    ) -> GenerationResult:
        """Transcribe audio to text."""
        pass


# OpenRouter Text Provider Implementation
class OpenRouterTextProvider(TextProvider):
    """OpenRouter text provider with Creator override support."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Check for Creator-specific override first, then fall back to global
        self.api_key = (
            config.get("CREATOR_OPENROUTER_API_KEY") or 
            config.get("OPENROUTER_API_KEY")
        )
        
        # Model selection with Creator override
        self.model = (
            config.get("CREATOR_OPENROUTER_MODEL_TEXT") or
            config.get("OPENROUTER_MODEL_CHAT") or
            config.get("OPENROUTER_DEFAULT_MODEL") or
            "anthropic/claude-3-haiku"
        )
        
        self.base_url = "https://openrouter.ai/api/v1"
        
    async def is_available(self) -> bool:
        """Check if OpenRouter is available."""
        return bool(self.api_key)
        
    async def generate_text(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.7,
        **kwargs
    ) -> GenerationResult:
        """Generate text using OpenRouter."""
        if not self.api_key:
            return GenerationResult(
                success=False,
                error="OpenRouter API key not configured (set OPENROUTER_API_KEY or CREATOR_OPENROUTER_API_KEY)"
            )
            
        try:
            messages = [{"role": "user", "content": prompt}]
            if "messages" in kwargs:
                messages = kwargs["messages"]
                
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        **{k: v for k, v in kwargs.items() if k != "messages"}
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/silvioiatech/Umbra",
                        "X-Title": "Umbra Creator"
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return GenerationResult(
                        success=True,
                        content=content,
                        metadata={"model": self.model, "provider": "openrouter"}
                    )
                else:
                    error_text = response.text[:200] if response.text else "Unknown error"
                    return GenerationResult(
                        success=False,
                        error=f"OpenRouter API error {response.status_code}: {error_text}"
                    )
                    
        except Exception as e:
            return GenerationResult(
                success=False,
                error=f"OpenRouter text generation failed: {str(e)}"
            )


# Image Provider Implementations
class StabilityImageProvider(ImageProvider):
    """Stability AI image provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("CREATOR_STABILITY_API_KEY")
        
    async def is_available(self) -> bool:
        return bool(self.api_key)
        
    async def generate_image(self, prompt: str, size: str = "1024x1024", **kwargs) -> GenerationResult:
        if not self.api_key:
            return GenerationResult(
                success=False,
                error="Stability AI API key not configured (set CREATOR_STABILITY_API_KEY)"
            )
            
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
                    json={
                        "text_prompts": [{"text": prompt}],
                        "cfg_scale": kwargs.get("cfg_scale", 7),
                        "steps": kwargs.get("steps", 30),
                        "samples": 1
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    artifacts = result.get("artifacts", [])
                    if artifacts:
                        return GenerationResult(
                            success=True,
                            content=artifacts[0].get("base64"),
                            metadata={"provider": "stability", "format": "base64"}
                        )
                        
                return GenerationResult(
                    success=False,
                    error=f"Stability AI error {response.status_code}: {response.text[:200]}"
                )
                
        except Exception as e:
            return GenerationResult(
                success=False,
                error=f"Stability AI generation failed: {str(e)}"
            )


class OpenAIImageProvider(ImageProvider):
    """OpenAI DALL-E image provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("CREATOR_OPENAI_API_KEY")
        
    async def is_available(self) -> bool:
        return bool(self.api_key)
        
    async def generate_image(self, prompt: str, size: str = "1024x1024", **kwargs) -> GenerationResult:
        if not self.api_key:
            return GenerationResult(
                success=False,
                error="OpenAI API key not configured (set CREATOR_OPENAI_API_KEY)"
            )
            
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/images/generations",
                    json={
                        "prompt": prompt,
                        "size": size,
                        "n": 1,
                        "model": kwargs.get("model", "dall-e-3")
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    image_url = result.get("data", [{}])[0].get("url")
                    if image_url:
                        return GenerationResult(
                            success=True,
                            url=image_url,
                            metadata={"provider": "openai", "model": kwargs.get("model", "dall-e-3")}
                        )
                        
                return GenerationResult(
                    success=False,
                    error=f"OpenAI API error {response.status_code}: {response.text[:200]}"
                )
                
        except Exception as e:
            return GenerationResult(
                success=False,
                error=f"OpenAI image generation failed: {str(e)}"
            )


class ReplicateImageProvider(ImageProvider):
    """Replicate image provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_token = config.get("CREATOR_REPLICATE_API_TOKEN")
        
    async def is_available(self) -> bool:
        return bool(self.api_token)
        
    async def generate_image(self, prompt: str, size: str = "1024x1024", **kwargs) -> GenerationResult:
        if not self.api_token:
            return GenerationResult(
                success=False,
                error="Replicate API token not configured (set CREATOR_REPLICATE_API_TOKEN)"
            )
            
        # Placeholder implementation - would integrate with Replicate API
        return GenerationResult(
            success=False,
            error="Replicate image generation not yet implemented"
        )


# TTS Provider Implementations
class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs TTS provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("CREATOR_ELEVENLABS_API_KEY")
        
    async def is_available(self) -> bool:
        return bool(self.api_key)
        
    async def generate_speech(self, text: str, voice: Optional[str] = None, **kwargs) -> GenerationResult:
        if not self.api_key:
            return GenerationResult(
                success=False,
                error="ElevenLabs API key not configured (set CREATOR_ELEVENLABS_API_KEY)"
            )
            
        # Placeholder implementation - would integrate with ElevenLabs API
        return GenerationResult(
            success=False,
            error="ElevenLabs TTS generation not yet implemented"
        )


class OpenAITTSProvider(TTSProvider):
    """OpenAI TTS provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("CREATOR_OPENAI_API_KEY")
        
    async def is_available(self) -> bool:
        return bool(self.api_key)
        
    async def generate_speech(self, text: str, voice: Optional[str] = None, **kwargs) -> GenerationResult:
        if not self.api_key:
            return GenerationResult(
                success=False,
                error="OpenAI API key not configured (set CREATOR_OPENAI_API_KEY)"
            )
            
        # Placeholder implementation - would integrate with OpenAI TTS API
        return GenerationResult(
            success=False,
            error="OpenAI TTS generation not yet implemented"
        )


# Video Provider Implementations (placeholders)
class PikaVideoProvider(VideoProvider):
    """Pika video provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("CREATOR_PIKA_API_KEY")
        
    async def is_available(self) -> bool:
        return bool(self.api_key)
        
    async def generate_video(self, prompt: str, duration: int = 5, **kwargs) -> GenerationResult:
        return GenerationResult(success=False, error="Pika video generation not yet implemented")


class RunwayVideoProvider(VideoProvider):
    """Runway video provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("CREATOR_RUNWAY_API_KEY")
        
    async def is_available(self) -> bool:
        return bool(self.api_key)
        
    async def generate_video(self, prompt: str, duration: int = 5, **kwargs) -> GenerationResult:
        return GenerationResult(success=False, error="Runway video generation not yet implemented")


class ReplicateVideoProvider(VideoProvider):
    """Replicate video provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_token = config.get("CREATOR_REPLICATE_API_TOKEN")
        
    async def is_available(self) -> bool:
        return bool(self.api_token)
        
    async def generate_video(self, prompt: str, duration: int = 5, **kwargs) -> GenerationResult:
        return GenerationResult(success=False, error="Replicate video generation not yet implemented")


# Music Provider Implementations (placeholders)
class SunoMusicProvider(MusicProvider):
    """Suno music provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("CREATOR_SUNO_API_KEY")
        
    async def is_available(self) -> bool:
        return bool(self.api_key)
        
    async def generate_music(self, prompt: str, duration: int = 30, **kwargs) -> GenerationResult:
        return GenerationResult(success=False, error="Suno music generation not yet implemented")


class ReplicateMusicProvider(MusicProvider):
    """Replicate music provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_token = config.get("CREATOR_REPLICATE_API_TOKEN")
        
    async def is_available(self) -> bool:
        return bool(self.api_token)
        
    async def generate_music(self, prompt: str, duration: int = 30, **kwargs) -> GenerationResult:
        return GenerationResult(success=False, error="Replicate music generation not yet implemented")


# ASR Provider Implementations (placeholders)
class OpenAIASRProvider(ASRProvider):
    """OpenAI Whisper ASR provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("CREATOR_OPENAI_API_KEY")
        
    async def is_available(self) -> bool:
        return bool(self.api_key)
        
    async def transcribe_audio(self, audio_data: bytes, format: str = "wav", **kwargs) -> GenerationResult:
        return GenerationResult(success=False, error="OpenAI ASR not yet implemented")


class DeepgramASRProvider(ASRProvider):
    """Deepgram ASR provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("CREATOR_DEEPGRAM_API_KEY")
        
    async def is_available(self) -> bool:
        return bool(self.api_key)
        
    async def transcribe_audio(self, audio_data: bytes, format: str = "wav", **kwargs) -> GenerationResult:
        return GenerationResult(success=False, error="Deepgram ASR not yet implemented")


def create_text_provider(config: Dict[str, Any]) -> TextProvider:
    """Create text provider based on configuration."""
    # Creator always prefers OpenRouter for text
    return OpenRouterTextProvider(config)


def create_image_provider(config: Dict[str, Any]) -> Optional[ImageProvider]:
    """Create image provider based on CREATOR_IMAGE_PROVIDER setting."""
    provider_name = config.get("CREATOR_IMAGE_PROVIDER", "").lower()
    
    if provider_name == "stability":
        return StabilityImageProvider(config)
    elif provider_name == "openai":
        return OpenAIImageProvider(config)
    elif provider_name == "replicate":
        return ReplicateImageProvider(config)
    else:
        # Try to auto-detect based on available keys
        if config.get("CREATOR_STABILITY_API_KEY"):
            return StabilityImageProvider(config)
        elif config.get("CREATOR_OPENAI_API_KEY"):
            return OpenAIImageProvider(config)
        elif config.get("CREATOR_REPLICATE_API_TOKEN"):
            return ReplicateImageProvider(config)
        
    return None


def create_video_provider(config: Dict[str, Any]) -> Optional[VideoProvider]:
    """Create video provider based on CREATOR_VIDEO_PROVIDER setting."""
    provider_name = config.get("CREATOR_VIDEO_PROVIDER", "").lower()
    
    if provider_name == "pika":
        return PikaVideoProvider(config)
    elif provider_name == "runway":
        return RunwayVideoProvider(config)
    elif provider_name == "replicate":
        return ReplicateVideoProvider(config)
        
    return None


def create_tts_provider(config: Dict[str, Any]) -> Optional[TTSProvider]:
    """Create TTS provider based on CREATOR_TTS_PROVIDER setting."""
    provider_name = config.get("CREATOR_TTS_PROVIDER", "").lower()
    
    if provider_name == "elevenlabs":
        return ElevenLabsTTSProvider(config)
    elif provider_name == "openai":
        return OpenAITTSProvider(config)
        
    return None


def create_music_provider(config: Dict[str, Any]) -> Optional[MusicProvider]:
    """Create music provider based on CREATOR_MUSIC_PROVIDER setting."""
    provider_name = config.get("CREATOR_MUSIC_PROVIDER", "").lower()
    
    if provider_name == "suno":
        return SunoMusicProvider(config)
    elif provider_name == "replicate":
        return ReplicateMusicProvider(config)
        
    return None


def create_asr_provider(config: Dict[str, Any]) -> Optional[ASRProvider]:
    """Create ASR provider based on CREATOR_ASR_PROVIDER setting."""
    provider_name = config.get("CREATOR_ASR_PROVIDER", "").lower()
    
    if provider_name == "openai":
        return OpenAIASRProvider(config)
    elif provider_name == "deepgram":
        return DeepgramASRProvider(config)
        
    return None