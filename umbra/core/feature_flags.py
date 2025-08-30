"""
Feature flag system for the Umbra Bot.

Provides runtime feature toggling based on environment variables and configuration.
"""

from typing import Dict, Optional


# Default feature flag values
DEFAULT_FLAGS = {
    "finance_ocr_enabled": True,
    "ai_integration_enabled": False,
    "ssh_operations_enabled": False,
    "workflow_automation_enabled": False,
    "media_generation_enabled": False,
    "detailed_logging_enabled": False,
    "metrics_collection_enabled": True,
}

# Lazy logger initialization to avoid circular imports
_logger = None


def _get_logger():
    """Get logger lazily to avoid circular imports."""
    global _logger
    if _logger is None:
        from .logger import get_logger
        _logger = get_logger("umbra.feature_flags")
    return _logger


def is_enabled(flag_name: str, default: Optional[bool] = None) -> bool:
    """
    Check if a feature flag is enabled.
    
    Args:
        flag_name: Name of the feature flag
        default: Default value if flag is not configured
        
    Returns:
        True if feature is enabled, False otherwise
    """
    try:
        from .config import get_config
        config = get_config()
        
        # Map flag names to config attributes
        flag_mapping = {
            "finance_ocr_enabled": config.feature_finance_ocr,
            "ai_integration_enabled": config.feature_ai_integration,
            "ssh_operations_enabled": config.feature_ssh_operations,
            "workflow_automation_enabled": config.feature_workflow_automation,
            "media_generation_enabled": config.feature_media_generation,
            "detailed_logging_enabled": config.feature_detailed_logging,
            "metrics_collection_enabled": config.feature_metrics_collection,
        }
        
        if flag_name in flag_mapping:
            enabled = flag_mapping[flag_name]
            
            if config.feature_detailed_logging:
                logger = _get_logger()
                logger.debug(f"Feature flag check", 
                           flag_name=flag_name, 
                           enabled=enabled)
            
            return enabled
        
        # Fall back to default if provided, otherwise use system default
        if default is not None:
            return default
        
        return DEFAULT_FLAGS.get(flag_name, False)
        
    except Exception as e:
        logger = _get_logger()
        if logger:
            logger.warning(f"Feature flag check failed", 
                         flag_name=flag_name, 
                         error=str(e))
        
        # Safe fallback
        if default is not None:
            return default
        return DEFAULT_FLAGS.get(flag_name, False)


def get_enabled_features() -> Dict[str, bool]:
    """
    Get dictionary of all feature flags and their current state.
    
    Returns:
        Dictionary mapping feature names to enabled status
    """
    features = {}
    
    for flag_name in DEFAULT_FLAGS.keys():
        features[flag_name] = is_enabled(flag_name)
    
    return features


def require_feature(flag_name: str, operation: str = "operation"):
    """
    Decorator to require a feature flag for a function to execute.
    
    Args:
        flag_name: Name of the required feature flag
        operation: Description of the operation for error messages
        
    Raises:
        RuntimeError: If feature is not enabled
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not is_enabled(flag_name):
                raise RuntimeError(f"Feature '{flag_name}' is not enabled for {operation}")
            return func(*args, **kwargs)
        return wrapper
    return decorator


class FeatureGate:
    """
    Context manager for feature-gated code blocks.
    
    Example:
        with FeatureGate("ai_integration_enabled") as gate:
            if gate.is_enabled:
                # AI integration code
                pass
            else:
                # Fallback code
                pass
    """
    
    def __init__(self, flag_name: str, default: bool = False):
        """
        Initialize feature gate.
        
        Args:
            flag_name: Name of the feature flag
            default: Default value if flag check fails
        """
        self.flag_name = flag_name
        self.default = default
        self.is_enabled = False
    
    def __enter__(self):
        """Enter context manager."""
        self.is_enabled = is_enabled(self.flag_name, self.default)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        pass


def log_feature_status():
    """
    Log the status of all feature flags for debugging.
    """
    features = get_enabled_features()
    enabled_features = [name for name, enabled in features.items() if enabled]
    disabled_features = [name for name, enabled in features.items() if not enabled]
    
    logger = _get_logger()
    logger.info("Feature flags initialized",
               enabled_count=len(enabled_features),
               disabled_count=len(disabled_features),
               enabled_features=enabled_features,
               disabled_features=disabled_features)