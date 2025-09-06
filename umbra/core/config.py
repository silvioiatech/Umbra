"""
Production-optimized configuration for Umbra Bot.
Railway-ready with comprehensive environment variable support.
"""
import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load .env file if it exists (for local development)
if Path('.env').exists():
    load_dotenv()

class UmbraConfig:
    """Production-ready configuration for Railway deployment with graceful degradation."""
    
    def __init__(self):
        """Initialize configuration with comprehensive environment variable support."""
        
        # ========================================
        # REQUIRED CORE CONFIGURATION
        # ========================================
        
        # Core Bot Configuration (Required)
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.ALLOWED_USER_IDS = self._parse_user_ids(os.getenv('ALLOWED_USER_IDS', ''))
        self.ALLOWED_ADMIN_IDS = self._parse_user_ids(os.getenv('ALLOWED_ADMIN_IDS', ''))
        
        # System Configuration
        self.PORT = int(os.getenv('PORT', '8000'))
        self.LOCALE_TZ = os.getenv('LOCALE_TZ', 'Europe/Zurich')
        self.PRIVACY_MODE = os.getenv('PRIVACY_MODE', 'strict')
        self.RATE_LIMIT_PER_MIN = int(os.getenv('RATE_LIMIT_PER_MIN', '20'))
        
        # Environment & Logging
        self.ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        
        # ========================================
        # CLOUDFLARE R2 STORAGE CONFIGURATION
        # ========================================
        
        self.R2_ACCOUNT_ID = os.getenv('R2_ACCOUNT_ID')
        self.R2_ACCESS_KEY_ID = os.getenv('R2_ACCESS_KEY_ID')
        self.R2_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY')
        self.R2_BUCKET = os.getenv('R2_BUCKET')
        self.R2_ENDPOINT = os.getenv('R2_ENDPOINT')
        
        # ========================================
        # OPENROUTER AI CONFIGURATION
        # ========================================
        
        self.OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
        self.OPENROUTER_BASE_URL = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
        self.OPENROUTER_DEFAULT_MODEL = os.getenv('OPENROUTER_DEFAULT_MODEL', 'anthropic/claude-3-haiku')
        
        # ========================================
        # OPTIONAL CONFIGURATION
        # ========================================
        
        # Redis (Optional)
        self.REDIS_URL = os.getenv('REDIS_URL')
        
        # Main n8n URL for Production module
        self.MAIN_N8N_URL = os.getenv('MAIN_N8N_URL')
        
        # Database
        self.DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/umbra.db')
        
        # Legacy OpenRouter Model Support
        self.OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', self.OPENROUTER_DEFAULT_MODEL)
        
        # ========================================
        # CREATOR MODULE PROVIDERS
        # ========================================
        
        # Image Generation
        self.CREATOR_IMAGE_PROVIDER = os.getenv('CREATOR_IMAGE_PROVIDER', 'openai')
        self.CREATOR_STABILITY_API_KEY = os.getenv('CREATOR_STABILITY_API_KEY')
        self.CREATOR_OPENAI_API_KEY = os.getenv('CREATOR_OPENAI_API_KEY')
        self.CREATOR_REPLICATE_API_TOKEN = os.getenv('CREATOR_REPLICATE_API_TOKEN')
        
        # Video Generation
        self.CREATOR_VIDEO_PROVIDER = os.getenv('CREATOR_VIDEO_PROVIDER', 'pika')
        self.CREATOR_PIKA_API_KEY = os.getenv('CREATOR_PIKA_API_KEY')
        self.CREATOR_RUNWAY_API_KEY = os.getenv('CREATOR_RUNWAY_API_KEY')
        
        # Text-to-Speech
        self.CREATOR_TTS_PROVIDER = os.getenv('CREATOR_TTS_PROVIDER', 'elevenlabs')
        self.CREATOR_ELEVENLABS_API_KEY = os.getenv('CREATOR_ELEVENLABS_API_KEY')
        
        # Music Generation
        self.CREATOR_MUSIC_PROVIDER = os.getenv('CREATOR_MUSIC_PROVIDER', 'suno')
        self.CREATOR_SUNO_API_KEY = os.getenv('CREATOR_SUNO_API_KEY')
        
        # Speech Recognition
        self.CREATOR_ASR_PROVIDER = os.getenv('CREATOR_ASR_PROVIDER', 'deepgram')
        self.CREATOR_DEEPGRAM_API_KEY = os.getenv('CREATOR_DEEPGRAM_API_KEY')
        
        # ========================================
        # C3: CONCIERGE INSTANCES CONFIGURATION
        # ========================================
        
        # Instance Registry Configuration
        self.CLIENT_PORT_RANGE = os.getenv('CLIENT_PORT_RANGE', '20000-21000')
        self.CLIENTS_BASE_DIR = os.getenv('CLIENTS_BASE_DIR', '/srv/n8n-clients')
        self.N8N_IMAGE = os.getenv('N8N_IMAGE', 'n8nio/n8n:latest')
        self.N8N_BASE_ENV = os.getenv('N8N_BASE_ENV', '')
        self.NGINX_CONTAINER_NAME = os.getenv('NGINX_CONTAINER_NAME')
        self.INSTANCES_HOST = os.getenv('INSTANCES_HOST', 'localhost')
        self.INSTANCES_USE_HTTPS = self._parse_bool('INSTANCES_USE_HTTPS', default=False)
        
        # Concierge Configuration
        self.CONCIERGE_RBAC_ENABLED = self._parse_bool('CONCIERGE_RBAC_ENABLED', default=True)
        self.CONCIERGE_AUDIT_ENABLED = self._parse_bool('CONCIERGE_AUDIT_ENABLED', default=True)
        self.OUTPUT_MAX_BYTES = int(os.getenv('OUTPUT_MAX_BYTES', '100000'))
        self.FILE_LIMIT_MB = int(os.getenv('FILE_LIMIT_MB', '100'))
        self.SPLIT_ABOVE_MB = int(os.getenv('SPLIT_ABOVE_MB', '100'))
        self.CHUNK_MB = int(os.getenv('CHUNK_MB', '8'))
        self.INTEGRITY = os.getenv('INTEGRITY', 'sha256')
        self.DOCKER_HOST = os.getenv('DOCKER_HOST', 'unix:///var/run/docker.sock')
        
        # ========================================
        # COMPUTED PROPERTIES & FEATURE FLAGS
        # ========================================
        
        # Storage Strategy - R2 first, fallback to local/SQLite
        self.STORAGE_BACKEND = os.getenv('STORAGE_BACKEND', 'r2' if self.R2_ACCOUNT_ID else 'sqlite')
        
        # Feature Flags with Safe Defaults
        self.feature_ai_integration = self._parse_bool('FEATURE_AI_INTEGRATION', default=bool(self.OPENROUTER_API_KEY))
        self.feature_r2_storage = self._parse_bool('FEATURE_R2_STORAGE', default=bool(self.R2_ACCOUNT_ID))
        self.feature_metrics_collection = self._parse_bool('FEATURE_METRICS_COLLECTION', default=True)
        self.feature_detailed_logging = self._parse_bool('FEATURE_DETAILED_LOGGING', default=False)
        
        # ========================================
        # LEGACY SUPPORT & ADDITIONAL FEATURES
        # ========================================
        
        # System Configuration
        self.DOCKER_AVAILABLE = self._parse_bool('DOCKER_AVAILABLE', default=False)
        self.VPS_HOST = os.getenv('VPS_HOST')
        self.SSH_PRIVATE_KEY = os.getenv('SSH_PRIVATE_KEY')
        self.N8N_API_URL = os.getenv('N8N_API_URL')
        self.N8N_API_KEY = os.getenv('N8N_API_KEY')
        
        # Alert Thresholds
        self.CPU_ALERT_THRESHOLD = int(os.getenv('CPU_ALERT_THRESHOLD', '85'))
        self.MEMORY_ALERT_THRESHOLD = int(os.getenv('MEMORY_ALERT_THRESHOLD', '85'))
        self.DISK_ALERT_THRESHOLD = int(os.getenv('DISK_ALERT_THRESHOLD', '90'))
        
        # Security Settings
        self.REQUIRE_ADMIN_CONFIRMATION = self._parse_bool('REQUIRE_ADMIN_CONFIRMATION', default=True)
        self.RATE_LIMIT_ENABLED = self._parse_bool('RATE_LIMIT_ENABLED', default=True)
        self.RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv('RATE_LIMIT_REQUESTS_PER_MINUTE', '30'))
        
        # Validate only if not explicitly skipped
        if not os.getenv('UMBRA_SKIP_VALIDATION'):
            self._validate_required()
    
    # ========================================
    # UTILITY METHODS
    # ========================================
    
    def _parse_user_ids(self, user_ids_str: str) -> List[int]:
        """Parse comma-separated user IDs."""
        if not user_ids_str:
            return []
        try:
            return [int(uid.strip()) for uid in user_ids_str.split(',') if uid.strip()]
        except ValueError:
            return []
    
    def _parse_bool(self, env_var: str, default: bool = False) -> bool:
        """Parse boolean environment variable with default."""
        value = os.getenv(env_var, '').lower()
        if value in ('true', '1', 'yes', 'on'):
            return True
        elif value in ('false', '0', 'no', 'off'):
            return False
        return default
    
    def _validate_required(self):
        """Validate only absolutely required configuration for Railway deployment."""
        errors = []
        
        if not self.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is required (get from @BotFather)")
        
        if not self.ALLOWED_USER_IDS:
            errors.append("ALLOWED_USER_IDS is required (get from @userinfobot)")
        
        if not self.ALLOWED_ADMIN_IDS:
            errors.append("ALLOWED_ADMIN_IDS is required")
        
        if errors:
            raise ValueError(f"Configuration errors: {'; '.join(errors)}")
    
    # ========================================
    # PERMISSION METHODS
    # ========================================
    
    def is_user_allowed(self, user_id: int) -> bool:
        """Check if user is allowed."""
        return user_id in self.ALLOWED_USER_IDS
    
    def is_user_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return user_id in self.ALLOWED_ADMIN_IDS
    
    # ========================================
    # PATH UTILITIES
    # ========================================
    
    def get_project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent
    
    def ensure_directory(self, path: Path) -> Path:
        """Ensure directory exists."""
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_storage_path(self) -> Path:
        """Get storage directory."""
        storage_dir = self.get_project_root() / "data"
        return self.ensure_directory(storage_dir)
    
    # ========================================
    # STATUS & DIAGNOSTIC METHODS
    # ========================================
    
    def get_missing_optional_features(self) -> List[str]:
        """Get list of missing optional features."""
        missing = []
        
        if not self.OPENROUTER_API_KEY:
            missing.append("AI Conversation (set OPENROUTER_API_KEY)")
        
        if not self.feature_r2_storage:
            missing.append("R2 Storage (set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET)")
        
        if not self.MAIN_N8N_URL:
            missing.append("Production n8n Integration (set MAIN_N8N_URL)")
        
        if not self.VPS_HOST:
            missing.append("SSH Operations (set VPS_HOST)")
        
        return missing
    
    def get_status_summary(self) -> dict:
        """Get configuration status for debugging."""
        return {
            "bot_token": "✅ Set" if self.TELEGRAM_BOT_TOKEN else "❌ Missing",
            "allowed_users": f"✅ {len(self.ALLOWED_USER_IDS)} users" if self.ALLOWED_USER_IDS else "❌ None",
            "admin_users": f"✅ {len(self.ALLOWED_ADMIN_IDS)} admins" if self.ALLOWED_ADMIN_IDS else "❌ None",
            "ai_integration": "✅ Enabled" if self.feature_ai_integration else "⚠️ Disabled",
            "r2_storage": "✅ Enabled" if self.feature_r2_storage else "⚠️ Disabled (using SQLite)",
            "openrouter": "✅ Configured" if self.OPENROUTER_API_KEY else "⚠️ Not configured",
            "storage_backend": self.STORAGE_BACKEND,
            "optional_features": len(self.get_missing_optional_features()),
            "environment": self.ENVIRONMENT,
            "port": self.PORT,
            "locale_tz": self.LOCALE_TZ,
            "privacy_mode": self.PRIVACY_MODE,
            "rate_limit": f"{self.RATE_LIMIT_PER_MIN}/min" if self.RATE_LIMIT_ENABLED else "Disabled"
        }
    
    def get_creator_providers_status(self) -> dict:
        """Get status of Creator module providers."""
        return {
            "image": {
                "provider": self.CREATOR_IMAGE_PROVIDER,
                "configured": bool(
                    (self.CREATOR_IMAGE_PROVIDER == 'openai' and self.CREATOR_OPENAI_API_KEY) or
                    (self.CREATOR_IMAGE_PROVIDER == 'stability' and self.CREATOR_STABILITY_API_KEY) or
                    (self.CREATOR_IMAGE_PROVIDER == 'replicate' and self.CREATOR_REPLICATE_API_TOKEN)
                )
            },
            "video": {
                "provider": self.CREATOR_VIDEO_PROVIDER,
                "configured": bool(
                    (self.CREATOR_VIDEO_PROVIDER == 'pika' and self.CREATOR_PIKA_API_KEY) or
                    (self.CREATOR_VIDEO_PROVIDER == 'runway' and self.CREATOR_RUNWAY_API_KEY) or
                    (self.CREATOR_VIDEO_PROVIDER == 'replicate' and self.CREATOR_REPLICATE_API_TOKEN)
                )
            },
            "tts": {
                "provider": self.CREATOR_TTS_PROVIDER,
                "configured": bool(
                    (self.CREATOR_TTS_PROVIDER == 'elevenlabs' and self.CREATOR_ELEVENLABS_API_KEY) or
                    (self.CREATOR_TTS_PROVIDER == 'openai' and self.CREATOR_OPENAI_API_KEY)
                )
            },
            "music": {
                "provider": self.CREATOR_MUSIC_PROVIDER,
                "configured": bool(
                    (self.CREATOR_MUSIC_PROVIDER == 'suno' and self.CREATOR_SUNO_API_KEY) or
                    (self.CREATOR_MUSIC_PROVIDER == 'replicate' and self.CREATOR_REPLICATE_API_TOKEN)
                )
            },
            "asr": {
                "provider": self.CREATOR_ASR_PROVIDER,
                "configured": bool(
                    (self.CREATOR_ASR_PROVIDER == 'deepgram' and self.CREATOR_DEEPGRAM_API_KEY) or
                    (self.CREATOR_ASR_PROVIDER == 'openai' and self.CREATOR_OPENAI_API_KEY)
                )
            }
        }

# Create global config instance
config = UmbraConfig()

# Export for compatibility
__all__ = ["UmbraConfig", "config"]
