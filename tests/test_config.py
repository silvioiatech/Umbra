"""
Tests for Umbra configuration validation and parsing.

Focused tests for config improvements including duration parsing
for HEALTH_CHECK_TIMEOUT and improved validation.
"""

import os
import pytest
from pydantic import ValidationError

from umbra.core.config import UmbraConfig


class TestConfigValidation:
    """Test configuration validation and parsing."""
    
    def setup_method(self):
        """Setup clean environment for each test."""
        # Store original environment
        self.original_env = os.environ.copy()
        
        # Clear test-related environment variables
        test_vars = [
            "TELEGRAM_BOT_TOKEN",
            "ALLOWED_USER_IDS", 
            "HEALTH_CHECK_TIMEOUT",
            "LOG_LEVEL"
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]
    
    def teardown_method(self):
        """Restore environment after each test."""
        # Clear any test variables
        test_vars = [
            "TELEGRAM_BOT_TOKEN",
            "ALLOWED_USER_IDS", 
            "HEALTH_CHECK_TIMEOUT",
            "LOG_LEVEL"
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]
        
        # Restore original environment
        for key, value in self.original_env.items():
            if key not in os.environ:
                os.environ[key] = value

    def test_missing_required_fields(self):
        """Test that missing required fields raise validation errors."""
        # Missing TELEGRAM_BOT_TOKEN should raise ValidationError
        os.environ["ALLOWED_USER_IDS"] = "123456789"
        
        with pytest.raises(ValidationError) as exc_info:
            UmbraConfig()
        
        error = exc_info.value
        assert "telegram_bot_token" in str(error)

    def test_telegram_bot_token_validation(self):
        """Test telegram bot token validation with explicit colon requirement."""
        os.environ["ALLOWED_USER_IDS"] = "123456789"
        
        # Valid tokens should work
        valid_tokens = [
            "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefg",
            "bot123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefg"
        ]
        
        for token in valid_tokens:
            os.environ["TELEGRAM_BOT_TOKEN"] = token
            config = UmbraConfig()
            assert config.telegram_bot_token == token

        # Invalid tokens without colon should raise error with explicit message
        invalid_tokens = [
            "123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefg",  # No colon
            "invalid_token",  # No colon
            ""  # Empty
        ]
        
        for token in invalid_tokens:
            os.environ["TELEGRAM_BOT_TOKEN"] = token
            with pytest.raises(ValidationError) as exc_info:
                UmbraConfig()
            
            error_str = str(exc_info.value)
            assert "telegram_bot_token" in error_str


class TestAllowedUserIdsValidation:
    """Test allowed_user_ids validation improvements."""
    
    def setup_method(self):
        """Setup clean environment for each test."""
        self.original_env = os.environ.copy()
        
        # Clear test-related environment variables
        test_vars = [
            "TELEGRAM_BOT_TOKEN",
            "ALLOWED_USER_IDS"
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]
        
        # Set required token
        os.environ["TELEGRAM_BOT_TOKEN"] = "123456789:test_token_for_testing"
    
    def teardown_method(self):
        """Restore environment after each test."""
        # Clear any test variables
        test_vars = [
            "TELEGRAM_BOT_TOKEN",
            "ALLOWED_USER_IDS"
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]
        
        # Restore original environment
        for key, value in self.original_env.items():
            if key not in os.environ:
                os.environ[key] = value

    def test_valid_user_ids(self):
        """Test that valid user IDs are parsed correctly."""
        test_cases = [
            ("123456789", ["123456789"]),
            ("123456789,987654321", ["123456789", "987654321"]),
            ("123, 456, 789", ["123", "456", "789"]),  # With spaces
            (" 123 , 456 , 789 ", ["123", "456", "789"]),  # Extra spaces
        ]
        
        for input_ids, expected_ids in test_cases:
            os.environ["ALLOWED_USER_IDS"] = input_ids
            config = UmbraConfig()
            assert config.allowed_user_ids == expected_ids

    def test_empty_user_ids_error(self):
        """Test that empty or whitespace-only user IDs raise explicit validation error."""
        invalid_values = [
            "",  # Empty string
            "   ",  # Whitespace only
            ",",  # Just comma
            ",,",  # Multiple commas
            " , , ",  # Whitespace and commas
        ]
        
        for invalid_value in invalid_values:
            os.environ["ALLOWED_USER_IDS"] = invalid_value
            with pytest.raises(ValidationError) as exc_info:
                UmbraConfig()
            
            error_str = str(exc_info.value)
            assert "allowed_user_ids" in error_str


class TestHealthCheckTimeoutDurationParsing:
    """Test HEALTH_CHECK_TIMEOUT duration parsing functionality."""
    
    def setup_method(self):
        """Setup clean environment for each test."""
        self.original_env = os.environ.copy()
        
        # Clear test-related environment variables
        test_vars = [
            "TELEGRAM_BOT_TOKEN",
            "ALLOWED_USER_IDS",
            "HEALTH_CHECK_TIMEOUT"
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]
        
        # Set required fields
        os.environ["TELEGRAM_BOT_TOKEN"] = "123456789:test_token_for_testing"
        os.environ["ALLOWED_USER_IDS"] = "123456789"
    
    def teardown_method(self):
        """Restore environment after each test."""
        # Clear any test variables
        test_vars = [
            "TELEGRAM_BOT_TOKEN",
            "ALLOWED_USER_IDS",
            "HEALTH_CHECK_TIMEOUT"
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]
        
        # Restore original environment
        for key, value in self.original_env.items():
            if key not in os.environ:
                os.environ[key] = value

    def test_default_health_check_timeout(self):
        """Test default health check timeout value."""
        config = UmbraConfig()
        assert config.health_check_timeout == 5  # Default value

    def test_integer_duration_parsing(self):
        """Test parsing of integer duration values."""
        test_cases = [
            ("5", 5),
            ("10", 10),
            ("0", 1),  # Should be clamped to minimum 1
            ("1", 1),
            ("3600", 3600),  # 1 hour
        ]
        
        for input_timeout, expected_timeout in test_cases:
            os.environ["HEALTH_CHECK_TIMEOUT"] = input_timeout
            config = UmbraConfig()
            assert config.health_check_timeout == expected_timeout

    def test_seconds_duration_parsing(self):
        """Test parsing of duration strings with seconds."""
        test_cases = [
            ("3s", 3),
            ("10s", 10),
            ("0s", 1),  # Should be clamped to minimum 1
            ("1s", 1),
            ("30s", 30),
        ]
        
        for input_timeout, expected_timeout in test_cases:
            os.environ["HEALTH_CHECK_TIMEOUT"] = input_timeout
            config = UmbraConfig()
            assert config.health_check_timeout == expected_timeout

    def test_milliseconds_duration_parsing(self):
        """Test parsing of duration strings with milliseconds."""
        test_cases = [
            ("1500ms", 1),  # 1.5 seconds -> floor to 1
            ("3000ms", 3),  # 3 seconds
            ("500ms", 1),   # 0.5 seconds -> clamped to minimum 1
            ("10000ms", 10), # 10 seconds
            ("999ms", 1),   # 0.999 seconds -> clamped to minimum 1
        ]
        
        for input_timeout, expected_timeout in test_cases:
            os.environ["HEALTH_CHECK_TIMEOUT"] = input_timeout
            config = UmbraConfig()
            assert config.health_check_timeout == expected_timeout

    def test_minutes_duration_parsing(self):
        """Test parsing of duration strings with minutes."""
        test_cases = [
            ("1m", 60),
            ("2m", 120),
            ("1min", 60),
            ("2min", 120),
            ("5min", 300),
            ("0m", 1),  # Should be clamped to minimum 1
        ]
        
        for input_timeout, expected_timeout in test_cases:
            os.environ["HEALTH_CHECK_TIMEOUT"] = input_timeout
            config = UmbraConfig()
            assert config.health_check_timeout == expected_timeout

    def test_invalid_duration_formats(self):
        """Test that invalid duration formats raise validation errors."""
        invalid_formats = [
            "abc",
            "10hours",  # Unsupported unit
            "5x",       # Invalid unit
            "m5",       # Unit before number
            "1.5.3s",   # Invalid number format
            "-5s",      # Negative value
            "s",        # Missing number
            "10ss",     # Double unit
        ]
        
        for invalid_format in invalid_formats:
            os.environ["HEALTH_CHECK_TIMEOUT"] = invalid_format
            with pytest.raises(ValidationError) as exc_info:
                UmbraConfig()
            
            error_str = str(exc_info.value)
            assert "health_check_timeout" in error_str

    def test_backward_compatibility(self):
        """Test that integer values are still accepted unchanged."""
        # Integer values should work as before
        os.environ["HEALTH_CHECK_TIMEOUT"] = "5"
        config = UmbraConfig()
        assert config.health_check_timeout == 5
        
        # But also support the old way of setting it
        del os.environ["HEALTH_CHECK_TIMEOUT"]
        config = UmbraConfig()
        assert config.health_check_timeout == 5  # Default


class TestAcceptanceCriteria:
    """Test specific acceptance criteria from the problem statement."""
    
    def setup_method(self):
        """Setup clean environment for each test."""
        self.original_env = os.environ.copy()
        
        # Clear test-related environment variables
        test_vars = [
            "TELEGRAM_BOT_TOKEN",
            "ALLOWED_USER_IDS",
            "HEALTH_CHECK_TIMEOUT"
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]
        
        # Set required fields
        os.environ["TELEGRAM_BOT_TOKEN"] = "123456789:test_token_for_testing"
        os.environ["ALLOWED_USER_IDS"] = "123456789"
    
    def teardown_method(self):
        """Restore environment after each test."""
        # Clear any test variables
        test_vars = [
            "TELEGRAM_BOT_TOKEN",
            "ALLOWED_USER_IDS",
            "HEALTH_CHECK_TIMEOUT"
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]
        
        # Restore original environment
        for key, value in self.original_env.items():
            if key not in os.environ:
                os.environ[key] = value

    def test_acceptance_criteria(self):
        """Test specific acceptance criteria from problem statement."""
        # HEALTH_CHECK_TIMEOUT=3s -> 3
        os.environ["HEALTH_CHECK_TIMEOUT"] = "3s"
        config = UmbraConfig()
        assert config.health_check_timeout == 3
        
        # HEALTH_CHECK_TIMEOUT=1500ms -> 1 (minimum 1 second enforced after floor conversion)
        os.environ["HEALTH_CHECK_TIMEOUT"] = "1500ms"
        config = UmbraConfig()
        assert config.health_check_timeout == 1
        
        # HEALTH_CHECK_TIMEOUT=2min -> 120
        os.environ["HEALTH_CHECK_TIMEOUT"] = "2min"
        config = UmbraConfig()
        assert config.health_check_timeout == 120

    def test_empty_allowed_user_ids_raises_validation_error(self):
        """Test that empty ALLOWED_USER_IDS raises validation error."""
        os.environ["ALLOWED_USER_IDS"] = ""
        
        with pytest.raises(ValidationError) as exc_info:
            UmbraConfig()
        
        error_str = str(exc_info.value)
        assert "allowed_user_ids" in error_str

    def test_missing_telegram_bot_token_raises_expected_error(self):
        """Test that missing TELEGRAM_BOT_TOKEN still raises expected error."""
        # Remove TELEGRAM_BOT_TOKEN from environment
        if "TELEGRAM_BOT_TOKEN" in os.environ:
            del os.environ["TELEGRAM_BOT_TOKEN"]
        # Only set ALLOWED_USER_IDS, not TELEGRAM_BOT_TOKEN
        os.environ["ALLOWED_USER_IDS"] = "123456789"
        
        with pytest.raises(ValidationError) as exc_info:
            UmbraConfig()
        
        error_str = str(exc_info.value)
        assert "telegram_bot_token" in error_str