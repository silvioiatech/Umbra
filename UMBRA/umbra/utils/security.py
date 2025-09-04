"""
Security utilities for Umbra bot.
"""

import logging
import re
from typing import List, Set
from functools import wraps


class SecurityManager:
    """
    Manages security and permissions for the bot.
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Convert to sets for faster lookup
        self.allowed_users: Set[int] = set(config.allowed_user_ids)
        self.admin_users: Set[int] = set(config.allowed_admin_ids)
        
        # Add admins to allowed users
        self.allowed_users.update(self.admin_users)
        
        self.logger.info(f"🔐 Security initialized: {len(self.allowed_users)} allowed users, {len(self.admin_users)} admins")
    
    def is_user_allowed(self, user_id: int) -> bool:
        """
        Check if user is allowed to use the bot.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user is allowed, False otherwise
        """
        return user_id in self.allowed_users
    
    def is_admin(self, user_id: int) -> bool:
        """
        Check if user has admin privileges.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user is admin, False otherwise
        """
        return user_id in self.admin_users
    
    def add_user(self, user_id: int) -> bool:
        """
        Add user to allowed users list.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user was added, False if already existed
        """
        if user_id not in self.allowed_users:
            self.allowed_users.add(user_id)
            self.logger.info(f"👤 User {user_id} added to allowed users")
            return True
        return False
    
    def remove_user(self, user_id: int) -> bool:
        """
        Remove user from allowed users list.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user was removed, False if didn't exist
        """
        if user_id in self.allowed_users and user_id not in self.admin_users:
            self.allowed_users.remove(user_id)
            self.logger.info(f"👤 User {user_id} removed from allowed users")
            return True
        return False
    
    def promote_to_admin(self, user_id: int) -> bool:
        """
        Promote user to admin.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user was promoted, False if already admin
        """
        if user_id not in self.admin_users:
            self.admin_users.add(user_id)
            self.allowed_users.add(user_id)  # Ensure they're also in allowed
            self.logger.info(f"👑 User {user_id} promoted to admin")
            return True
        return False
    
    def demote_from_admin(self, user_id: int) -> bool:
        """
        Demote user from admin.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if user was demoted, False if wasn't admin
        """
        if user_id in self.admin_users:
            self.admin_users.remove(user_id)
            # Keep them in allowed users unless specifically removed
            self.logger.info(f"👑 User {user_id} demoted from admin")
            return True
        return False
    
    def get_allowed_users(self) -> List[int]:
        """
        Get list of allowed users.
        
        Returns:
            List of allowed user IDs
        """
        return list(self.allowed_users)
    
    def get_admin_users(self) -> List[int]:
        """
        Get list of admin users.
        
        Returns:
            List of admin user IDs
        """
        return list(self.admin_users)
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """
        Sanitize user input to prevent injection attacks.
        
        Args:
            text: Input text to sanitize
            
        Returns:
            Sanitized text
        """
        if not text:
            return ""
        
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\'\/\\]', '', text)
        
        # Limit length
        sanitized = sanitized[:1000]
        
        # Remove excessive whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return sanitized
    
    @staticmethod
    def is_safe_url(url: str) -> bool:
        """
        Check if URL is safe (basic validation).
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL appears safe, False otherwise
        """
        if not url:
            return False
        
        # Basic URL pattern
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'  # domain...
            r'(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # host...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        return bool(url_pattern.match(url))


def require_permission(permission_type: str = "user"):
    """
    Decorator to require specific permissions for handler functions.
    
    Args:
        permission_type: "user" or "admin"
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, update, context, *args, **kwargs):
            user_id = update.effective_user.id
            
            if permission_type == "admin":
                if not self.security.is_admin(user_id):
                    await update.message.reply_text("❌ Admin permissions required.")
                    return
            else:  # user permission
                if not self.security.is_user_allowed(user_id):
                    await update.message.reply_text("❌ You don't have permission to use this bot.")
                    return
            
            return await func(self, update, context, *args, **kwargs)
        return wrapper
    return decorator


def sanitize_input(func):
    """
    Decorator to sanitize user input.
    """
    @wraps(func)
    async def wrapper(self, update, context, *args, **kwargs):
        if update.message and update.message.text:
            # Sanitize the message text
            original_text = update.message.text
            sanitized_text = SecurityManager.sanitize_input(original_text)
            
            # Replace the text in the update object
            update.message.text = sanitized_text
        
        return await func(self, update, context, *args, **kwargs)
    return wrapper
