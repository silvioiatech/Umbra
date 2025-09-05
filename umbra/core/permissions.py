"""
Permission management for Umbra bot with structured logging.
Manages user permissions and access control with audit logging.
"""
import logging
from typing import List, Set
from .config import config
from .logger import get_context_logger, log_user_action

class PermissionManager:
    """Manages user permissions and access control with comprehensive logging."""
    
    def __init__(self):
        self.logger = get_context_logger(__name__)
        self.allowed_users: Set[int] = set(config.ALLOWED_USER_IDS)
        self.admin_users: Set[int] = set(config.ALLOWED_ADMIN_IDS)
        
        self.logger.info(
            "Permission manager initialized",
            extra={
                "allowed_users_count": len(self.allowed_users),
                "admin_users_count": len(self.admin_users),
                "umbra_module": "permissions",
                "action": "init"
            }
        )
    
    def is_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to use the bot (legacy method name)."""
        return self.is_user_allowed(user_id)
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user has admin privileges (legacy method name)."""
        return self.is_user_admin(user_id)
    
    def is_user_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to use the bot."""
        allowed = user_id in self.allowed_users
        
        if not allowed:
            self.logger.warning(
                "Unauthorized access attempt",
                extra={
                    "user_id": user_id,
                    "umbra_module": "permissions",
                    "action": "check_allowed",
                    "result": "denied"
                }
            )
        
        return allowed
    
    def is_user_admin(self, user_id: int) -> bool:
        """Check if user has admin privileges."""
        is_admin = user_id in self.admin_users
        
        self.logger.debug(
            "Admin privilege check",
            extra={
                "user_id": user_id,
                "umbra_module": "permissions",
                "action": "check_admin",
                "result": "granted" if is_admin else "denied"
            }
        )
        
        return is_admin
    
    def add_allowed_user(self, user_id: int, admin_user_id: int) -> bool:
        """Add user to allowed list (admin only)."""
        if not self.is_user_admin(admin_user_id):
            self.logger.warning(
                "Non-admin attempted to add user",
                extra={
                    "admin_user_id": admin_user_id,
                    "target_user_id": user_id,
                    "umbra_module": "permissions",
                    "action": "add_user",
                    "result": "denied"
                }
            )
            return False
        
        if user_id not in self.allowed_users:
            self.allowed_users.add(user_id)
            
            log_user_action(
                self.logger.logger,
                admin_user_id,
                "add_allowed_user",
                "permissions",
                True,
                {"target_user_id": user_id}
            )
            
            return True
        
        return False
    
    def remove_allowed_user(self, user_id: int, admin_user_id: int) -> bool:
        """Remove user from allowed list (admin only, cannot remove other admins)."""
        if not self.is_user_admin(admin_user_id):
            self.logger.warning(
                "Non-admin attempted to remove user",
                extra={
                    "admin_user_id": admin_user_id,
                    "target_user_id": user_id,
                    "umbra_module": "permissions",
                    "action": "remove_user",
                    "result": "denied"
                }
            )
            return False
        
        # Prevent removal of admin users
        if user_id in self.admin_users:
            self.logger.warning(
                "Attempt to remove admin user",
                extra={
                    "admin_user_id": admin_user_id,
                    "target_user_id": user_id,
                    "umbra_module": "permissions",
                    "action": "remove_user",
                    "result": "denied",
                    "reason": "target_is_admin"
                }
            )
            return False
        
        if user_id in self.allowed_users:
            self.allowed_users.remove(user_id)
            
            log_user_action(
                self.logger.logger,
                admin_user_id,
                "remove_allowed_user",
                "permissions",
                True,
                {"target_user_id": user_id}
            )
            
            return True
        
        return False
    
    def get_allowed_users(self) -> List[int]:
        """Get list of allowed users."""
        return list(self.allowed_users)
    
    def get_admin_users(self) -> List[int]:
        """Get list of admin users."""
        return list(self.admin_users)
    
    def get_user_role(self, user_id: int) -> str:
        """Get user role as string."""
        if user_id in self.admin_users:
            return "admin"
        elif user_id in self.allowed_users:
            return "user"
        else:
            return "unauthorized"
    
    def check_module_permission(self, user_id: int, module: str, action: str) -> bool:
        """Check if user has permission for specific module action."""
        
        # First check if user is allowed at all
        if not self.is_user_allowed(user_id):
            return False
        
        # Define admin-only modules and actions
        admin_only_modules = {'concierge', 'business', 'security'}
        admin_only_actions = {'exec', 'delete', 'modify_system', 'create_instance'}
        
        is_admin = self.is_user_admin(user_id)
        
        # Check module-level permissions
        if module in admin_only_modules and not is_admin:
            self.logger.warning(
                "Non-admin access to admin module denied",
                extra={
                    "user_id": user_id,
                    "umbra_module": module,
                    "action": action,
                    "result": "denied",
                    "reason": "admin_only_module"
                }
            )
            return False
        
        # Check action-level permissions
        if action in admin_only_actions and not is_admin:
            self.logger.warning(
                "Non-admin access to admin action denied",
                extra={
                    "user_id": user_id,
                    "umbra_module": module,
                    "action": action,
                    "result": "denied",
                    "reason": "admin_only_action"
                }
            )
            return False
        
        return True
    
    def get_status_summary(self) -> dict:
        """Get permission status summary."""
        return {
            "allowed_users": len(self.allowed_users),
            "admin_users": len(self.admin_users),
            "total_authorized": len(self.allowed_users),
            "privacy_mode": config.PRIVACY_MODE,
            "rate_limit_enabled": config.RATE_LIMIT_ENABLED,
            "rate_limit_per_min": config.RATE_LIMIT_PER_MIN
        }

# Export
__all__ = ["PermissionManager"]
