"""
Configuration management for Umbra Bot using Pydantic BaseSettings.
"""

import os
import re
from typing import List, Optional, Union, Annotated
from pydantic import Field, field_validator, ConfigDict, BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict, EnvSettingsSource
from pydantic_settings.sources import PydanticBaseSettingsSource


class CustomEnvSettingsSource(EnvSettingsSource):
    """Custom environment settings source that doesn't parse List fields as JSON."""
    
    def prepare_field_value(
        self, field_name: str, field, field_value, value_is_complex: bool
    ):
        # Don't try to parse allowed_user_ids as JSON - let the validator handle it
        if field_name == 'allowed_user_ids':
            return field_value
        # Use the default behavior for other fields
        return super().prepare_field_value(field_name, field, field_value, value_is_complex)


def parse_user_ids(v):
    """Parse comma-separated user IDs string into list."""
    if isinstance(v, str):
        # Remove whitespace and split by comma
        user_ids = [uid.strip() for uid in v.split(",") if uid.strip()]
        
        # Reject empty or whitespace-only values with explicit error
        if not user_ids:
            raise ValueError("ALLOWED_USER_IDS cannot be empty or contain only whitespace")
        
        return user_ids
    elif isinstance(v, int):
        return [str(v)]
    elif isinstance(v, list):
        return v
    return v


class UmbraConfig(BaseSettings):
    """
    Configuration for the Umbra Bot.
    
    Uses Pydantic BaseSettings to load configuration from environment variables
    with validation and type conversion.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Disable automatic complex type parsing for all fields
        env_ignore_empty=True,
    )
    
    # Required configuration
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    allowed_user_ids: List[str] = Field(..., env="ALLOWED_USER_IDS")
    
    # Optional configuration with defaults
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_format: str = Field("json", env="LOG_FORMAT")
    
    # Module-specific optional configuration
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY") 
    openrouter_api_key: Optional[str] = Field(None, env="OPENROUTER_API_KEY")
    
    # Finance module configuration
    finance_storage_path: str = Field("./finance_data", env="FINANCE_STORAGE_PATH")
    ocr_language: str = Field("eng", env="OCR_LANGUAGE")
    
    # Monitoring configuration
    monitoring_interval: int = Field(30, env="MONITORING_INTERVAL")
    health_check_timeout: int = Field(
        5, 
        env="HEALTH_CHECK_TIMEOUT",
        description="Health check timeout duration. Accepts integers (seconds) or duration strings like '3s', '1500ms', '2min'."
    )
    
    # VPS/SSH configuration (for future concierge module)
    vps_host: Optional[str] = Field(None, env="VPS_HOST")
    vps_username: Optional[str] = Field(None, env="VPS_USERNAME")
    ssh_private_key: Optional[str] = Field(None, env="SSH_PRIVATE_KEY")
    
    # Workflow automation (for future production module)
    n8n_api_url: Optional[str] = Field(None, env="N8N_API_URL")
    n8n_api_key: Optional[str] = Field(None, env="N8N_API_KEY")
    
    # Feature flags (defaults in feature_flags.py)
    feature_finance_ocr: bool = Field(True, env="FEATURE_FINANCE_OCR")
    feature_ai_integration: bool = Field(False, env="FEATURE_AI_INTEGRATION")
    feature_ssh_operations: bool = Field(False, env="FEATURE_SSH_OPERATIONS")
    feature_workflow_automation: bool = Field(False, env="FEATURE_WORKFLOW_AUTOMATION")
    feature_media_generation: bool = Field(False, env="FEATURE_MEDIA_GENERATION")
    feature_detailed_logging: bool = Field(False, env="FEATURE_DETAILED_LOGGING")
    feature_metrics_collection: bool = Field(True, env="FEATURE_METRICS_COLLECTION")
    
    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def parse_user_ids(cls, v):
        """Parse comma-separated user IDs string into list."""
        if isinstance(v, str):
            # Remove whitespace and split by comma
            user_ids = [uid.strip() for uid in v.split(",") if uid.strip()]
            
            # Reject empty or whitespace-only values with explicit error
            if not user_ids:
                raise ValueError("ALLOWED_USER_IDS cannot be empty or contain only whitespace")
            
            return user_ids
        elif isinstance(v, int):
            return [str(v)]
        elif isinstance(v, list):
            return v
        return v

    @field_validator("health_check_timeout", mode="before")
    @classmethod
    def parse_health_check_timeout(cls, v):
        """
        Parse health check timeout duration.
        
        Accepts:
        - Integer values (seconds): 5, 10, 30
        - String integer values: "5", "10", "30"
        - Duration strings: "3s", "1500ms", "2min", "1m"
        
        Returns integer seconds with minimum value of 1.
        """
        if isinstance(v, int):
            return max(1, v)  # Ensure minimum 1 second
        
        if isinstance(v, str):
            v = v.strip()
            
            # Try parsing as plain integer first
            try:
                timeout_seconds = int(v)
                return max(1, timeout_seconds)  # Ensure minimum 1 second
            except ValueError:
                pass
            
            # Parse duration strings using regex
            duration_pattern = r'^(\d+(?:\.\d+)?)\s*(s|ms|m|min)$'
            match = re.match(duration_pattern, v, re.IGNORECASE)
            
            if not match:
                raise ValueError(f"Invalid duration format '{v}'. Use formats like: 5, '3s', '1500ms', '2min'")
            
            number_str, unit = match.groups()
            
            try:
                number = float(number_str)
            except ValueError:
                raise ValueError(f"Invalid number in duration '{v}'")
            
            # Convert to seconds based on unit
            unit = unit.lower()
            if unit == 's':
                seconds = number
            elif unit == 'ms':
                seconds = number / 1000.0
            elif unit in ('m', 'min'):
                seconds = number * 60
            else:
                raise ValueError(f"Unsupported time unit '{unit}'. Supported units: s, ms, m, min")
            
            # Floor the result and ensure minimum 1 second
            return max(1, int(seconds))
        
        raise ValueError(f"Invalid health_check_timeout value: {v}")

    @field_validator("telegram_bot_token")
    @classmethod
    def validate_bot_token(cls, v):
        """Validate Telegram bot token format."""
        if not v:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
            
        # Telegram bot tokens must contain a colon
        if ":" not in v:
            raise ValueError("Invalid Telegram bot token format: must contain a colon (:)")
        
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of: {valid_levels}")
        return v.upper()
    
    def get_missing_optional_keys(self) -> List[str]:
        """
        Get list of missing optional API keys for logging warnings.
        
        Returns:
            List of missing optional configuration keys
        """
        missing = []
        
        # Check optional API keys
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")
        if not self.openrouter_api_key:
            missing.append("OPENROUTER_API_KEY")
        if not self.vps_host:
            missing.append("VPS_HOST")
        if not self.n8n_api_url:
            missing.append("N8N_API_URL")
            
        return missing
    
    def is_module_enabled(self, module_name: str) -> bool:
        """
        Check if a module should be enabled based on configuration.
        
        Args:
            module_name: Name of the module to check
            
        Returns:
            True if module should be enabled
        """
        module_requirements = {
            "finance": True,  # Always enabled as a phase 1 module
            "monitoring": True,  # Always enabled as a phase 1 module
            "business": self.vps_host is not None,
            "production": self.n8n_api_url is not None,
            "creator": any([self.openai_api_key, self.anthropic_api_key, self.openrouter_api_key]),
            "concierge": self.vps_host is not None and self.ssh_private_key is not None
        }
        
        return module_requirements.get(module_name, False)
    
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Replace the default env_settings with our custom one
        return init_settings, CustomEnvSettingsSource(settings_cls), dotenv_settings, file_secret_settings


# Global config instance
_config: Optional[UmbraConfig] = None


def get_config() -> UmbraConfig:
    """
    Get the global configuration instance.
    
    Returns:
        The global UmbraConfig instance
    """
    global _config
    if _config is None:
        _config = UmbraConfig()
    return _config


def reload_config() -> UmbraConfig:
    """
    Reload configuration from environment.
    
    Returns:
        The reloaded UmbraConfig instance
    """
    global _config
    _config = UmbraConfig()
    return _config