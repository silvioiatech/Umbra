"""Tests for umbra.core.permissions module."""
import os
import pytest
from unittest.mock import patch

from umbra.core.permissions import PermissionManager
from umbra.core.config import UmbraConfig


class TestPermissionManager:
    """Test cases for PermissionManager class."""
    
    def test_permission_manager_initialization(self):
        """Test PermissionManager initialization with config."""
        required_env = {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'ALLOWED_USER_IDS': '123,456,789',
            'ALLOWED_ADMIN_IDS': '999,888'
        }
        
        with patch.dict(os.environ, required_env, clear=True):
            config = UmbraConfig()
            pm = PermissionManager(config)
            
            assert len(pm.allowed_users) == 3
            assert 123 in pm.allowed_users
            assert 456 in pm.allowed_users
            assert 789 in pm.allowed_users
            
            assert len(pm.admin_users) == 2
            assert 999 in pm.admin_users
            assert 888 in pm.admin_users
    
    def test_is_user_allowed(self):
        """Test user allowlist checking."""
        required_env = {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'ALLOWED_USER_IDS': '123,456',
            'ALLOWED_ADMIN_IDS': '789'
        }
        
        with patch.dict(os.environ, required_env, clear=True):
            config = UmbraConfig()
            pm = PermissionManager(config)
            
            # Allowed users
            assert pm.is_user_allowed(123) is True
            assert pm.is_user_allowed(456) is True
            
            # Not allowed users
            assert pm.is_user_allowed(999) is False
            assert pm.is_user_allowed(0) is False
    
    def test_is_user_admin(self):
        """Test admin user checking."""
        required_env = {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'ALLOWED_USER_IDS': '123,456',
            'ALLOWED_ADMIN_IDS': '789,888'
        }
        
        with patch.dict(os.environ, required_env, clear=True):
            config = UmbraConfig()
            pm = PermissionManager(config)
            
            # Admin users
            assert pm.is_user_admin(789) is True
            assert pm.is_user_admin(888) is True
            
            # Non-admin users
            assert pm.is_user_admin(123) is False
            assert pm.is_user_admin(456) is False
            assert pm.is_user_admin(999) is False
    
    def test_add_allowed_user(self):
        """Test adding users to allowlist."""
        required_env = {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'ALLOWED_USER_IDS': '123',
            'ALLOWED_ADMIN_IDS': '789'
        }
        
        with patch.dict(os.environ, required_env, clear=True):
            config = UmbraConfig()
            pm = PermissionManager(config)
            
            # Initially not allowed
            assert pm.is_user_allowed(456) is False
            
            # Add user
            result = pm.add_allowed_user(456)
            assert result is True
            assert pm.is_user_allowed(456) is True
            
            # Try to add same user again
            result = pm.add_allowed_user(456)
            assert result is False  # Already exists
    
    def test_remove_allowed_user(self):
        """Test removing users from allowlist."""
        required_env = {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'ALLOWED_USER_IDS': '123,456',
            'ALLOWED_ADMIN_IDS': '789'
        }
        
        with patch.dict(os.environ, required_env, clear=True):
            config = UmbraConfig()
            pm = PermissionManager(config)
            
            # Initially allowed
            assert pm.is_user_allowed(456) is True
            
            # Remove user
            result = pm.remove_allowed_user(456)
            assert result is True
            assert pm.is_user_allowed(456) is False
            
            # Try to remove admin (should fail)
            result = pm.remove_allowed_user(789)
            assert result is False  # Cannot remove admin
            
            # Try to remove non-existent user
            result = pm.remove_allowed_user(999)
            assert result is False
    
    def test_get_allowed_users(self):
        """Test getting list of allowed users."""
        required_env = {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'ALLOWED_USER_IDS': '123,456,789',
            'ALLOWED_ADMIN_IDS': '999'
        }
        
        with patch.dict(os.environ, required_env, clear=True):
            config = UmbraConfig()
            pm = PermissionManager(config)
            
            allowed = pm.get_allowed_users()
            assert isinstance(allowed, list)
            assert len(allowed) == 3
            assert 123 in allowed
            assert 456 in allowed
            assert 789 in allowed
    
    def test_get_admin_users(self):
        """Test getting list of admin users."""
        required_env = {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'ALLOWED_USER_IDS': '123,456',
            'ALLOWED_ADMIN_IDS': '789,888'
        }
        
        with patch.dict(os.environ, required_env, clear=True):
            config = UmbraConfig()
            pm = PermissionManager(config)
            
            admins = pm.get_admin_users()
            assert isinstance(admins, list)
            assert len(admins) == 2
            assert 789 in admins
            assert 888 in admins