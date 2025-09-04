"""
Production-optimized configuration for Umbra Bot.
Gracefully handles missing optional variables with smart defaults.
"""
import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load .env file if it exists (for local development)
if Path('.env').exists():
    load_dotenv()

class UmbraConfig:
    """Production-ready configuration with graceful degradation."""
    
    def __init__(self):
        """Initialize configuration with smart defaults."""
        # Core Bot Configuration (Required)
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
        self.ALLOWED_USER_IDS = self._parse_user_ids(os.getenv('ALLOWED_USER_IDS', ''))
        self.ALLOWED_ADMIN_IDS = self._parse_user_ids(os.getenv('ALLOWED_ADMIN_IDS', ''))
        
        # Database Configuration
        self.DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/umbra.db')
        
        # Logging Configuration
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        
        # Environment
        self.ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')
        self.PORT = os.getenv('PORT')
        
        # Optional AI Configuration
        self.OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
        self.OPENROUTER_BASE_URL = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
        self.OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'anthropic/claude-3-haiku')
        
        # Feature Flags with Safe Defaults
        self.feature_ai_integration = self._parse_bool('FEATURE_AI_INTEGRATION', default=bool(self.OPENROUTER_API_KEY))
        self.feature_metrics_collection = self._parse_bool('FEATURE_METRICS_COLLECTION', default=True)
        self.feature_finance_ocr = self._parse_bool('FEATURE_FINANCE_OCR', default=False)
        self.feature_ssh_operations = self._parse_bool('FEATURE_SSH_OPERATIONS', default=False)
        self.feature_workflow_automation = self._parse_bool('FEATURE_WORKFLOW_AUTOMATION', default=False)
        self.feature_media_generation = self._parse_bool('FEATURE_MEDIA_GENERATION', default=False)
        self.feature_detailed_logging = self._parse_bool('FEATURE_DETAILED_LOGGING', default=False)
        
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
        
        # Only validate required variables in production
        if not os.getenv('UMBRA_SKIP_VALIDATION'):
            self._validate_required()
    
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
        """Validate only absolutely required configuration."""
        errors = []
        
        if not self.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is required (get from @BotFather)")
        
        if not self.ALLOWED_USER_IDS:
            errors.append("ALLOWED_USER_IDS is required (get from @userinfobot)")
        
        if not self.ALLOWED_ADMIN_IDS:
            errors.append("ALLOWED_ADMIN_IDS is required")
        
        if errors:
            raise ValueError(f"Configuration errors: {'; '.join(errors)}")
    
    def is_user_allowed(self, user_id: int) -> bool:
        """Check if user is allowed."""
        return user_id in self.ALLOWED_USER_IDS
    
    def is_user_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return user_id in self.ALLOWED_ADMIN_IDS
    
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
    
    def get_missing_optional_features(self) -> List[str]:
        """Get list of missing optional features."""
        missing = []
        
        if not self.OPENROUTER_API_KEY:
            missing.append("AI Conversation (set OPENROUTER_API_KEY)")
        
        if not self.VPS_HOST:
            missing.append("SSH Operations (set VPS_HOST)")
        
        if not self.N8N_API_URL:
            missing.append("Workflow Automation (set N8N_API_URL)")
        
        return missing
    
    def get_status_summary(self) -> dict:
        """Get configuration status for debugging."""
        return {
            "bot_token": "✅ Set" if self.TELEGRAM_BOT_TOKEN else "❌ Missing",
            "allowed_users": f"✅ {len(self.ALLOWED_USER_IDS)} users" if self.ALLOWED_USER_IDS else "❌ None",
            "ai_integration": "✅ Enabled" if self.feature_ai_integration else "⚠️ Disabled",
            "optional_features": len(self.get_missing_optional_features()),
            "environment": self.ENVIRONMENT,
            "docker": "✅ Available" if self.DOCKER_AVAILABLE else "⚠️ Simulation"
        }

# Create global config instance
config = UmbraConfig()

# Export for compatibility
__all__ = ["UmbraConfig", "config"]
