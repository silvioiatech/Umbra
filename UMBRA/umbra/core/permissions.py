"""Permission management for Umbra bot."""
import logging
from typing import List, Set
from .config import config

class PermissionManager:
    """Manages user permissions and access control."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.allowed_users: Set[int] = set(config.ALLOWED_USER_IDS)
        self.admin_users: Set[int] = set(config.ALLOWED_ADMIN_IDS)
        
        self.logger.info(f"Permission manager initialized: {len(self.allowed_users)} allowed users, {len(self.admin_users)} admins")
    
    def is_user_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to use the bot."""
        return user_id in self.allowed_users
    
    def is_user_admin(self, user_id: int) -> bool:
        """Check if user has admin privileges."""
        return user_id in self.admin_users
    
    def add_allowed_user(self, user_id: int) -> bool:
        """Add user to allowed list (admin only)."""
        if user_id not in self.allowed_users:
            self.allowed_users.add(user_id)
            self.logger.info(f"Added user {user_id} to allowed list")
            return True
        return False
    
    def remove_allowed_user(self, user_id: int) -> bool:
        """Remove user from allowed list (admin only)."""
        if user_id in self.allowed_users and user_id not in self.admin_users:
            self.allowed_users.remove(user_id)
            self.logger.info(f"Removed user {user_id} from allowed list")
            return True
        return False
    
    def get_allowed_users(self) -> List[int]:
        """Get list of allowed users."""
        return list(self.allowed_users)
    
    def get_admin_users(self) -> List[int]:
        """Get list of admin users."""
        return list(self.admin_users)
