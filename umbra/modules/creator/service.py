"""
Creator MCP - Multi-API Content Creator Service
Refactored to use standardized provider routing and CREATOR_* environment variables.
"""
import json
import os
from datetime import datetime
from typing import Any, Dict

from ...core.envelope import InternalEnvelope
from ...core.module_base import ModuleBase
from .model_provider import (
    create_text_provider,
    create_image_provider,
    create_video_provider,
    create_tts_provider,
    create_music_provider,
    create_asr_provider
)
from .export import CreatorExporter


class CreatorMCP(ModuleBase):
    """Content Creator - Multi-API content generation with provider routing."""

    def __init__(self, config, db_manager):
        super().__init__("creator")
        self.config = config
        self.db = db_manager
        
        # Convert config object to dict for providers
        self.config_dict = self._config_to_dict(config)

        # Initialize providers
        self.text_provider = create_text_provider(self.config_dict)
        self.image_provider = create_image_provider(self.config_dict)
        self.video_provider = create_video_provider(self.config_dict)
        self.tts_provider = create_tts_provider(self.config_dict)
        self.music_provider = create_music_provider(self.config_dict)
        self.asr_provider = create_asr_provider(self.config_dict)
        
        # Initialize exporter
        self.exporter = CreatorExporter(self.config_dict)

        self._init_database()

    def _config_to_dict(self, config) -> Dict[str, Any]:
        """Convert config object to dictionary for providers."""
        config_dict = {}
        
        # Legacy compatibility - map old variables to new CREATOR_* format
        legacy_mappings = {
            "OPENROUTER_API_KEY": "OPENROUTER_API_KEY",  # Keep global for fallback
            "STABILITY_API_KEY": "CREATOR_STABILITY_API_KEY",
            "ELEVENLABS_API_KEY": "CREATOR_ELEVENLABS_API_KEY"
        }
        
        # Get all environment variables
        for key, value in os.environ.items():
            config_dict[key] = value
            
        # Get config attributes
        for attr in dir(config):
            if not attr.startswith('_'):
                value = getattr(config, attr, None)
                if value is not None:
                    config_dict[attr] = value
                    
                    # Apply legacy mappings
                    if attr in legacy_mappings:
                        new_key = legacy_mappings[attr]
                        if new_key not in config_dict:
                            config_dict[new_key] = value
                            
        return config_dict

    async def initialize(self) -> bool:
        """Initialize the Creator module."""
        try:
            # Test database connectivity
            test_query = "SELECT name FROM sqlite_master WHERE type='table' AND name='creations'"
            self.db.query_one(test_query)

            # Check provider availability
            available_providers = []
            
            if self.text_provider and await self.text_provider.is_available():
                available_providers.append("Text (OpenRouter)")
            
            if self.image_provider and await self.image_provider.is_available():
                provider_name = self.config_dict.get("CREATOR_IMAGE_PROVIDER", "auto")
                available_providers.append(f"Images ({provider_name})")
                
            if self.video_provider and await self.video_provider.is_available():
                provider_name = self.config_dict.get("CREATOR_VIDEO_PROVIDER", "unknown")
                available_providers.append(f"Video ({provider_name})")
                
            if self.tts_provider and await self.tts_provider.is_available():
                provider_name = self.config_dict.get("CREATOR_TTS_PROVIDER", "unknown")
                available_providers.append(f"TTS ({provider_name})")
                
            if self.music_provider and await self.music_provider.is_available():
                provider_name = self.config_dict.get("CREATOR_MUSIC_PROVIDER", "unknown")
                available_providers.append(f"Music ({provider_name})")
                
            if self.asr_provider and await self.asr_provider.is_available():
                provider_name = self.config_dict.get("CREATOR_ASR_PROVIDER", "unknown")
                available_providers.append(f"ASR ({provider_name})")

            storage_status = "enabled" if self.exporter.is_storage_enabled() else "disabled"

            if available_providers:
                self.logger.info(f"Creator module initialized with providers: {', '.join(available_providers)}")
                self.logger.info(f"R2 storage: {storage_status}")
            else:
                self.logger.info("Creator module initialized (no external providers configured)")
                self.logger.info(f"R2 storage: {storage_status}")

            return True
        except Exception as e:
            self.logger.error(f"Creator initialization failed: {e}")
            return False

    async def register_handlers(self) -> dict[str, Any]:
        """Register command handlers for the Creator module."""
        return {
            "create image": self.create_image,
            "create document": self.create_document,
            "create video": self.create_video,
            "create audio": self.create_audio,
            "create music": self.create_music,
            "transcribe audio": self.transcribe_audio,
            "list creations": self.list_creations,
            "content templates": self.get_content_templates,
            "api status": self.get_api_status
        }

    async def process_envelope(self, envelope: InternalEnvelope) -> str | None:
        """Process envelope for Creator operations."""
        action = envelope.action.lower()
        data = envelope.data

        if action == "create_image":
            prompt = data.get("prompt", "")
            return await self.create_image(prompt)
        elif action == "create_document":
            request = data.get("request", "")
            return await self.create_document(request)
        elif action == "create_video":
            request = data.get("request", "")
            return await self.create_video(request)
        elif action == "create_audio":
            text = data.get("text", "")
            return await self.create_audio(text)
        elif action == "create_music":
            prompt = data.get("prompt", "")
            return await self.create_music(prompt)
        elif action == "transcribe_audio":
            audio_data = data.get("audio_data", b"")
            return await self.transcribe_audio(audio_data)
        elif action == "list_creations":
            return await self.list_creations()
        elif action == "content_templates":
            return await self.get_content_templates()
        elif action == "api_status":
            return await self.get_api_status()
        else:
            return None

    async def health_check(self) -> dict[str, Any]:
        """Perform health check of the Creator module."""
        try:
            # Check database connectivity
            creations_count = self.db.query_one("SELECT COUNT(*) as count FROM creations")

            # Check recent activity
            recent_creations = self.db.query_one("""
                SELECT COUNT(*) as count FROM creations
                WHERE created_at >= date('now', '-7 days')
            """)

            # Check provider availability
            provider_status = {
                "text": bool(self.text_provider and await self.text_provider.is_available()),
                "image": bool(self.image_provider and await self.image_provider.is_available()),
                "video": bool(self.video_provider and await self.video_provider.is_available()),
                "tts": bool(self.tts_provider and await self.tts_provider.is_available()),
                "music": bool(self.music_provider and await self.music_provider.is_available()),
                "asr": bool(self.asr_provider and await self.asr_provider.is_available()),
                "storage": self.exporter.is_storage_enabled()
            }

            return {
                "status": "healthy",
                "details": {
                    "total_creations": creations_count["count"] if creations_count else 0,
                    "recent_creations": recent_creations["count"] if recent_creations else 0,
                    "providers_available": provider_status,
                    "providers_count": sum(1 for v in provider_status.values() if v),
                    "database_accessible": True
                }
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def shutdown(self):
        """Gracefully shutdown the Creator module."""
        self.logger.info("Creator module shutting down")
        # No specific cleanup needed for this module

    def _init_database(self):
        """Initialize creator tables."""
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS creations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT,
                    prompt TEXT,
                    result TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.logger.info("✅ Creator database initialized")
        except Exception as e:
            self.logger.error(f"Creator DB init failed: {e}")

    async def create_image(self, prompt: str) -> str:
        """Generate image using configured provider."""
        try:
            if not prompt:
                return "❌ Please provide an image prompt"

            if not self.image_provider:
                return self._get_provider_not_configured_message("image")

            if not await self.image_provider.is_available():
                return "❌ Image provider is not available"

            # Generate image
            result = await self.image_provider.generate_image(prompt)
            
            if not result.success:
                return f"❌ Image generation failed: {result.error}"

            # Save to database
            self.db.execute(
                "INSERT INTO creations (type, prompt, result, metadata) VALUES (?, ?, ?, ?)",
                ('image', prompt, result.url or result.content[:100], json.dumps(result.metadata))
            )

            # Try to export to storage
            export_result = None
            if result.url:
                export_result = await self.exporter.export_image(
                    image_url=result.url,
                    prompt=prompt,
                    provider=result.metadata.get("provider") if result.metadata else None
                )
            elif result.content:
                # Assume base64 content for now
                import base64
                try:
                    image_data = base64.b64decode(result.content)
                    export_result = await self.exporter.export_image(
                        image_data=image_data,
                        prompt=prompt,
                        provider=result.metadata.get("provider") if result.metadata else None
                    )
                except Exception:
                    pass  # Continue without export

            # Format response
            response = f"""**🎨 Image Generated**

Prompt: {prompt}
Provider: {result.metadata.get('provider', 'unknown') if result.metadata else 'unknown'}

"""

            if export_result and export_result.success:
                response += f"🖼️ [View Image]({export_result.url})\n\n✅ Image saved to storage"
            elif result.url:
                response += f"🖼️ [View Image]({result.url})\n\n⚠️ Image not saved (storage not configured)"
            else:
                response += "✅ Image generated (base64 format)\n\n⚠️ Image not saved (storage not configured)"

            return response

        except Exception as e:
            self.logger.error(f"Image generation failed: {e}")
            return f"❌ Image generation failed: {str(e)[:100]}"

    async def create_document(self, request: str) -> str:
        """Generate document content using text provider."""
        try:
            if not request:
                return "❌ Please provide a document request"

            if not self.text_provider:
                return self._get_provider_not_configured_message("text")

            if not await self.text_provider.is_available():
                return "❌ Text provider is not available"

            # Parse document type from request
            doc_type = self._determine_doc_type(request)

            # Generate content
            result = await self.text_provider.generate_text(
                prompt=f"Generate a professional {doc_type} document based on: {request}",
                max_tokens=1000
            )

            if not result.success:
                return f"❌ Document generation failed: {result.error}"

            # Save to database
            self.db.execute(
                "INSERT INTO creations (type, prompt, result, metadata) VALUES (?, ?, ?, ?)",
                ('document', request, result.content[:500], json.dumps(result.metadata))
            )

            # Try to export to storage
            export_result = await self.exporter.export_text(
                text=result.content,
                document_type=doc_type,
                prompt=request,
                provider=result.metadata.get("provider") if result.metadata else None
            )

            response = f"""**📄 Document Generated**

Type: {doc_type}
Request: {request}
Provider: {result.metadata.get('provider', 'unknown') if result.metadata else 'unknown'}

**Content Preview:**
```
{result.content[:500]}{'...' if len(result.content) > 500 else ''}
```

"""

            if export_result.success:
                response += f"📄 [Download Document]({export_result.url})\n\n✅ Document saved to storage"
            else:
                response += "⚠️ Document not saved (storage not configured)"

            return response

        except Exception as e:
            return f"❌ Document generation failed: {str(e)[:100]}"

    async def create_video(self, request: str) -> str:
        """Create video content using configured provider."""
        try:
            if not request:
                return "❌ Please provide a video request"

            if not self.video_provider:
                return self._get_provider_not_configured_message("video")

            if not await self.video_provider.is_available():
                return "❌ Video provider is not available"

            # For now, generate a script/storyboard since most video APIs are placeholders
            result = await self.video_provider.generate_video(request)

            # Save to database
            self.db.execute(
                "INSERT INTO creations (type, prompt, result, metadata) VALUES (?, ?, ?, ?)",
                ('video', request, "Video generation requested", json.dumps({"provider": "placeholder"}))
            )

            return f"""**🎬 Video Creation Plan**

Request: {request}
Status: {result.error if not result.success else "In development"}

**Note:** Video generation is being developed. Current providers support:
- Script and storyboard generation
- Technical specifications
- Placeholder implementation

Configure CREATOR_VIDEO_PROVIDER (pika/runway/replicate) for future video generation."""

        except Exception as e:
            return f"❌ Video creation failed: {str(e)[:100]}"

    async def create_audio(self, text: str) -> str:
        """Create audio from text using TTS provider."""
        try:
            if not text:
                return "❌ Please provide text to convert to audio"

            if not self.tts_provider:
                return self._get_provider_not_configured_message("TTS")

            if not await self.tts_provider.is_available():
                return "❌ TTS provider is not available"

            result = await self.tts_provider.generate_speech(text)

            # Save to database
            creation_id = f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.db.execute("""
                INSERT INTO creations (type, prompt, result, metadata)
                VALUES (?, ?, ?, ?)
            """, ("audio", text, f"Audio creation: {creation_id}", json.dumps({
                "length": len(text),
                "provider": "placeholder"
            })))

            return f"""**🎵 Audio Creation**

ID: {creation_id}
Text: {text[:100]}{'...' if len(text) > 100 else ''}
Status: {result.error if not result.success else "In development"}

**Note:** TTS generation is being developed. Configure CREATOR_TTS_PROVIDER (elevenlabs/openai) for audio generation."""

        except Exception as e:
            return f"❌ Audio creation failed: {str(e)[:100]}"

    async def create_music(self, prompt: str) -> str:
        """Create music using configured provider."""
        try:
            if not prompt:
                return "❌ Please provide a music prompt"

            if not self.music_provider:
                return self._get_provider_not_configured_message("music")

            result = await self.music_provider.generate_music(prompt)

            # Save to database
            creation_id = f"music_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.db.execute("""
                INSERT INTO creations (type, prompt, result, metadata)
                VALUES (?, ?, ?, ?)
            """, ("music", prompt, f"Music creation: {creation_id}", json.dumps({
                "provider": "placeholder"
            })))

            return f"""**🎵 Music Creation**

ID: {creation_id}
Prompt: {prompt}
Status: {result.error if not result.success else "In development"}

**Note:** Music generation is being developed. Configure CREATOR_MUSIC_PROVIDER (suno/replicate) for music generation."""

        except Exception as e:
            return f"❌ Music creation failed: {str(e)[:100]}"

    async def transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio using ASR provider."""
        try:
            if not audio_data:
                return "❌ Please provide audio data to transcribe"

            if not self.asr_provider:
                return self._get_provider_not_configured_message("ASR")

            result = await self.asr_provider.transcribe_audio(audio_data)

            return f"""**🎤 Audio Transcription**

Status: {result.error if not result.success else "In development"}

**Note:** ASR is being developed. Configure CREATOR_ASR_PROVIDER (openai/deepgram) for transcription."""

        except Exception as e:
            return f"❌ Audio transcription failed: {str(e)[:100]}"

    def _get_provider_not_configured_message(self, provider_type: str) -> str:
        """Get message for when a provider is not configured."""
        config_hints = {
            "image": "Set CREATOR_IMAGE_PROVIDER (stability/openai/replicate) and corresponding API key",
            "video": "Set CREATOR_VIDEO_PROVIDER (pika/runway/replicate) and corresponding API key",
            "TTS": "Set CREATOR_TTS_PROVIDER (elevenlabs/openai) and corresponding API key",
            "music": "Set CREATOR_MUSIC_PROVIDER (suno/replicate) and corresponding API key",
            "ASR": "Set CREATOR_ASR_PROVIDER (openai/deepgram) and corresponding API key",
            "text": "Set OPENROUTER_API_KEY or CREATOR_OPENROUTER_API_KEY for text generation"
        }
        
        hint = config_hints.get(provider_type, f"Configure {provider_type} provider")
        return f"❌ {provider_type.title()} provider not configured. {hint}"

    def _determine_doc_type(self, request: str) -> str:
        """Determine document type from request."""
        request_lower = request.lower()

        if any(word in request_lower for word in ['report', 'analysis']):
            return 'report'
        elif any(word in request_lower for word in ['proposal', 'pitch']):
            return 'proposal'
        elif any(word in request_lower for word in ['email', 'message']):
            return 'email'
        elif any(word in request_lower for word in ['contract', 'agreement']):
            return 'contract'
        else:
            return 'general'

    async def list_creations(self) -> str:
        """List recent creations."""
        try:
            creations = self.db.query_all(
                "SELECT * FROM creations ORDER BY created_at DESC LIMIT 10"
            )

            if not creations:
                return "No content created yet"

            creation_lines = []
            for creation in creations:
                type_emoji = {
                    'image': '🎨',
                    'document': '📄',
                    'video': '🎬',
                    'audio': '🎵',
                    'music': '🎵'
                }.get(creation['type'], '📦')

                prompt_short = creation['prompt'][:50] + '...' if len(creation['prompt']) > 50 else creation['prompt']
                creation_lines.append(
                    f"{type_emoji} {creation['type'].title()}: {prompt_short}"
                )

            return f"""**📚 Recent Creations**

{chr(10).join(creation_lines)}

Total: {len(creations)} items created"""

        except Exception as e:
            return f"❌ Failed to list creations: {str(e)[:100]}"

    async def get_content_templates(self) -> str:
        """Get available content creation templates."""
        try:
            templates = {
                "images": {
                    "logo": "Professional logo design",
                    "banner": "Social media banner",
                    "illustration": "Custom illustration",
                    "icon": "App or web icon",
                    "avatar": "Profile avatar/character",
                    "product": "Product showcase image"
                },
                "documents": {
                    "proposal": "Business proposal template",
                    "report": "Professional report format",
                    "resume": "Modern resume layout",
                    "invoice": "Invoice template",
                    "letter": "Formal letter format",
                    "contract": "Basic contract template"
                },
                "videos": {
                    "explainer": "Product explainer video",
                    "tutorial": "Step-by-step tutorial",
                    "promo": "Promotional video",
                    "demo": "Software demo video",
                    "slideshow": "Image slideshow with music"
                },
                "audio": {
                    "narration": "Professional narration",
                    "podcast": "Podcast episode intro",
                    "announcement": "Public announcement",
                    "commercial": "Radio commercial"
                }
            }

            template_list = []
            for category, items in templates.items():
                template_list.append(f"**{category.upper()}:**")
                for key, description in items.items():
                    template_list.append(f"  • {key}: {description}")
                template_list.append("")

            return f"""**🎨 Content Creation Templates**

{chr(10).join(template_list)}

Use templates by specifying the type in your request:
"create image logo for tech startup"
"create document proposal for web development project"
"""

        except Exception as e:
            return f"❌ Template listing failed: {str(e)[:100]}"

    async def get_api_status(self) -> str:
        """Get status of configured providers."""
        try:
            status_lines = []

            # Text Provider
            if self.text_provider and await self.text_provider.is_available():
                model = getattr(self.text_provider, 'model', 'unknown')
                status_lines.append(f"✅ Text Generation - OpenRouter ({model})")
            else:
                status_lines.append("❌ Text Generation - Not configured (set OPENROUTER_API_KEY)")

            # Image Provider
            if self.image_provider and await self.image_provider.is_available():
                provider_name = self.config_dict.get("CREATOR_IMAGE_PROVIDER", "auto-detected")
                status_lines.append(f"✅ Image Generation - {provider_name}")
            else:
                status_lines.append("❌ Image Generation - Not configured (set CREATOR_IMAGE_PROVIDER + API key)")

            # Video Provider
            if self.video_provider:
                provider_name = self.config_dict.get("CREATOR_VIDEO_PROVIDER", "unknown")
                status_lines.append(f"🚧 Video Generation - {provider_name} (in development)")
            else:
                status_lines.append("❌ Video Generation - Not configured (set CREATOR_VIDEO_PROVIDER + API key)")

            # TTS Provider
            if self.tts_provider:
                provider_name = self.config_dict.get("CREATOR_TTS_PROVIDER", "unknown")
                status_lines.append(f"🚧 TTS Generation - {provider_name} (in development)")
            else:
                status_lines.append("❌ TTS Generation - Not configured (set CREATOR_TTS_PROVIDER + API key)")

            # Music Provider
            if self.music_provider:
                provider_name = self.config_dict.get("CREATOR_MUSIC_PROVIDER", "unknown")
                status_lines.append(f"🚧 Music Generation - {provider_name} (in development)")
            else:
                status_lines.append("❌ Music Generation - Not configured (set CREATOR_MUSIC_PROVIDER + API key)")

            # ASR Provider
            if self.asr_provider:
                provider_name = self.config_dict.get("CREATOR_ASR_PROVIDER", "unknown")
                status_lines.append(f"🚧 ASR - {provider_name} (in development)")
            else:
                status_lines.append("❌ ASR - Not configured (set CREATOR_ASR_PROVIDER + API key)")

            # Storage
            if self.exporter.is_storage_enabled():
                status_lines.append("✅ R2 Storage - Configured")
            else:
                status_lines.append("❌ R2 Storage - Not configured (set R2_* variables)")

            configured_count = sum(1 for line in status_lines if line.startswith("✅"))

            return f"""**🔌 Creator Provider Status**

{chr(10).join(status_lines)}

**Summary:** {configured_count} providers fully configured

**Configuration:**
Text models use OpenRouter with Creator override support
Media tasks use provider-specific adapters based on CREATOR_*_PROVIDER settings
All secrets are namespaced with CREATOR_* prefix
"""

        except Exception as e:
            return f"❌ API status check failed: {str(e)[:100]}"