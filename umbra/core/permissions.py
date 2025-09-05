"""Permission management for Umbra bot."""
import logging
from typing import List, Set
from .config import config
from .rbac import rbac_manager, Role, Module, Action

class PermissionManager:
    """Manages user permissions and access control."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.allowed_users: Set[int] = set(config.ALLOWED_USER_IDS)
        self.admin_users: Set[int] = set(config.ALLOWED_ADMIN_IDS)
        
        # Initialize RBAC roles based on existing user lists
        self._init_rbac_roles()
        
        self.logger.info(f"Permission manager initialized: {len(self.allowed_users)} allowed users, {len(self.admin_users)} admins")
    
    def _init_rbac_roles(self):
        """Initialize RBAC roles based on existing user configurations."""
        # Assign roles to existing users
        for user_id in self.admin_users:
            rbac_manager.set_user_role(user_id, Role.ADMIN)
        
        for user_id in self.allowed_users:
            if user_id not in self.admin_users:
                rbac_manager.set_user_role(user_id, Role.USER)
    
    def is_user_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to use the bot."""
        return user_id in self.allowed_users
    
    def is_user_admin(self, user_id: int) -> bool:
        """Check if user has admin privileges."""
        return user_id in self.admin_users
    
    def check_module_permission(self, user_id: int, module: str, action: str) -> bool:
        """Check if user has permission for specific module/action using RBAC."""
        # First check basic access
        if not self.is_user_allowed(user_id):
            return False
        
        try:
            # Convert string module/action to enums
            module_enum = Module(module.lower())
            action_enum = Action(action.lower())
            
            return rbac_manager.check_permission(user_id, module_enum, action_enum)
        except ValueError:
            # If module/action not in enum, fall back to admin check for admin-only actions
            self.logger.warning(f"Unknown module/action: {module}/{action}, falling back to admin check")
            return self.is_user_admin(user_id)
    
    def get_user_role(self, user_id: int) -> str:
        """Get user's RBAC role."""
        role = rbac_manager.get_user_role(user_id)
        return role.value
    
    def set_user_role(self, user_id: int, role: str) -> bool:
        """Set user's RBAC role (admin only)."""
        try:
            role_enum = Role(role.lower())
            rbac_manager.set_user_role(user_id, role_enum)
            return True
        except ValueError:
            self.logger.error(f"Invalid role: {role}")
            return False
    
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
