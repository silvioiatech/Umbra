"""Tests for umbra.core.config module."""
import os
import pytest
from unittest.mock import patch

from umbra.core.config import UmbraConfig


class TestUmbraConfig:
    """Test cases for UmbraConfig class."""
    
    def test_config_defaults(self):
        """Test configuration defaults without validation."""
        with patch.dict(os.environ, {'UMBRA_SKIP_VALIDATION': 'true'}, clear=False):
            config = UmbraConfig()
            
            # Test default values
            assert config.PORT == 8000
            assert config.LOCALE_TZ == 'UTC'
            assert config.PRIVACY_MODE is True
            assert config.ENVIRONMENT == 'production'
            assert config.LOG_LEVEL == 'INFO'
            assert config.R2_BUCKET == 'umbra-storage'
            assert config.RATE_LIMIT_PER_MIN == 30
            assert config.OPENROUTER_DEFAULT_MODEL == 'anthropic/claude-3-haiku'
            assert config.OPENROUTER_BASE_URL == 'https://openrouter.ai/api/v1'
    
    def test_config_environment_variables(self):
        """Test configuration with environment variables."""
        test_env = {
            'UMBRA_SKIP_VALIDATION': 'true',
            'PORT': '9000',
            'LOCALE_TZ': 'America/New_York',
            'PRIVACY_MODE': 'false',
            'R2_BUCKET': 'custom-bucket',
            'RATE_LIMIT_PER_MIN': '60',
            'OPENROUTER_DEFAULT_MODEL': 'anthropic/claude-3-opus'
        }
        
        with patch.dict(os.environ, test_env, clear=False):
            config = UmbraConfig()
            
            assert config.PORT == 9000
            assert config.LOCALE_TZ == 'America/New_York'
            assert config.PRIVACY_MODE is False
            assert config.R2_BUCKET == 'custom-bucket'
            assert config.RATE_LIMIT_PER_MIN == 60
            assert config.OPENROUTER_DEFAULT_MODEL == 'anthropic/claude-3-opus'
    
    def test_parse_user_ids(self):
        """Test user ID parsing functionality."""
        with patch.dict(os.environ, {'UMBRA_SKIP_VALIDATION': 'true'}, clear=False):
            config = UmbraConfig()
            
            # Test empty string
            assert config._parse_user_ids('') == []
            
            # Test single ID
            assert config._parse_user_ids('123') == [123]
            
            # Test multiple IDs
            assert config._parse_user_ids('123,456,789') == [123, 456, 789]
            
            # Test with spaces
            assert config._parse_user_ids('123, 456 , 789') == [123, 456, 789]
            
            # Test invalid IDs
            assert config._parse_user_ids('123,invalid,789') == []
    
    def test_parse_bool(self):
        """Test boolean parsing functionality."""
        with patch.dict(os.environ, {'UMBRA_SKIP_VALIDATION': 'true'}, clear=False):
            config = UmbraConfig()
            
            # Test true values
            assert config._parse_bool('TEST_TRUE', default=False) is False  # not set
            
        # Test with environment variables
        true_values = ['true', 'True', '1', 'yes', 'on']
        false_values = ['false', 'False', '0', 'no', 'off']
        
        for val in true_values:
            with patch.dict(os.environ, {'TEST_BOOL': val, 'UMBRA_SKIP_VALIDATION': 'true'}, clear=False):
                config = UmbraConfig()
                assert config._parse_bool('TEST_BOOL') is True
        
        for val in false_values:
            with patch.dict(os.environ, {'TEST_BOOL': val, 'UMBRA_SKIP_VALIDATION': 'true'}, clear=False):
                config = UmbraConfig()
                assert config._parse_bool('TEST_BOOL') is False
    
    def test_validation_required_fields(self):
        """Test that validation fails when required fields are missing."""
        # Clear required environment variables
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                UmbraConfig()
            
            error_message = str(exc_info.value)
            assert 'TELEGRAM_BOT_TOKEN is required' in error_message
            assert 'ALLOWED_USER_IDS is required' in error_message
            assert 'ALLOWED_ADMIN_IDS is required' in error_message
    
    def test_validation_with_required_fields(self):
        """Test that validation passes when required fields are provided."""
        required_env = {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'ALLOWED_USER_IDS': '123,456',
            'ALLOWED_ADMIN_IDS': '789'
        }
        
        with patch.dict(os.environ, required_env, clear=True):
            config = UmbraConfig()
            
            assert config.TELEGRAM_BOT_TOKEN == 'test_token'
            assert config.ALLOWED_USER_IDS == [123, 456]
            assert config.ALLOWED_ADMIN_IDS == [789]
    
    def test_user_permission_methods(self):
        """Test user permission checking methods."""
        required_env = {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'ALLOWED_USER_IDS': '123,456',
            'ALLOWED_ADMIN_IDS': '789'
        }
        
        with patch.dict(os.environ, required_env, clear=True):
            config = UmbraConfig()
            
            # Test allowed users
            assert config.is_user_allowed(123) is True
            assert config.is_user_allowed(456) is True
            assert config.is_user_allowed(999) is False
            
            # Test admin users
            assert config.is_user_admin(789) is True
            assert config.is_user_admin(123) is False
            assert config.is_user_admin(999) is False