"""Role-Based Access Control (RBAC) for Umbra bot."""
import logging
from enum import Enum
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass

class Role(Enum):
    """User roles in the system."""
    GUEST = "guest"
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

class Module(Enum):
    """Available modules in the system."""
    CONCIERGE = "concierge"
    FINANCE = "finance"
    BUSINESS = "business"
    PRODUCTION = "production"
    CREATOR = "creator"
    SYSTEM = "system"

class Action(Enum):
    """Available actions in the system."""
    # Common actions
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    
    # Module-specific actions
    CREATE_WORKFLOW = "create_workflow"
    MANAGE_FINANCES = "manage_finances"
    SYSTEM_MONITOR = "system_monitor"
    USER_MANAGEMENT = "user_management"
    AUDIT_VIEW = "audit_view"

@dataclass
class RBACRule:
    """RBAC rule definition."""
    module: Module
    action: Action
    min_role: Role
    description: str = ""

class RBACManager:
    """Manages Role-Based Access Control."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # RBAC Matrix: {module: {action: min_role}}
        self._rbac_matrix = self._build_rbac_matrix()
        
        # User role assignments (to be populated from config/database)
        self._user_roles: Dict[int, Role] = {}
        
        self.logger.info("RBAC Manager initialized with access matrix")
    
    def _build_rbac_matrix(self) -> Dict[Module, Dict[Action, Role]]:
        """Build the RBAC access matrix."""
        matrix = {
            Module.CONCIERGE: {
                Action.READ: Role.USER,
                Action.EXECUTE: Role.USER,
                Action.SYSTEM_MONITOR: Role.MODERATOR,
                Action.WRITE: Role.MODERATOR,
                Action.DELETE: Role.ADMIN,
            },
            Module.FINANCE: {
                Action.READ: Role.USER,
                Action.WRITE: Role.USER,
                Action.MANAGE_FINANCES: Role.USER,
                Action.DELETE: Role.MODERATOR,
                Action.AUDIT_VIEW: Role.ADMIN,
            },
            Module.BUSINESS: {
                Action.READ: Role.USER,
                Action.WRITE: Role.MODERATOR,
                Action.EXECUTE: Role.MODERATOR,
                Action.DELETE: Role.ADMIN,
            },
            Module.PRODUCTION: {
                Action.READ: Role.USER,
                Action.CREATE_WORKFLOW: Role.MODERATOR,
                Action.EXECUTE: Role.MODERATOR,
                Action.DELETE: Role.ADMIN,
            },
            Module.CREATOR: {
                Action.READ: Role.USER,
                Action.WRITE: Role.USER,
                Action.EXECUTE: Role.USER,
                Action.DELETE: Role.MODERATOR,
            },
            Module.SYSTEM: {
                Action.READ: Role.MODERATOR,
                Action.WRITE: Role.ADMIN,
                Action.USER_MANAGEMENT: Role.ADMIN,
                Action.AUDIT_VIEW: Role.ADMIN,
                Action.DELETE: Role.SUPER_ADMIN,
            }
        }
        return matrix
    
    def set_user_role(self, user_id: int, role: Role) -> None:
        """Set role for a user."""
        self._user_roles[user_id] = role
        self.logger.info(f"User {user_id} assigned role: {role.value}")
    
    def get_user_role(self, user_id: int) -> Role:
        """Get role for a user (defaults to GUEST)."""
        return self._user_roles.get(user_id, Role.GUEST)
    
    def check_permission(self, user_id: int, module: Module, action: Action) -> bool:
        """Check if user has permission for module/action combination."""
        user_role = self.get_user_role(user_id)
        required_role = self._rbac_matrix.get(module, {}).get(action)
        
        if required_role is None:
            self.logger.warning(f"No RBAC rule defined for {module.value}/{action.value}")
            return False
        
        has_permission = self._role_has_permission(user_role, required_role)
        
        self.logger.debug(
            f"Permission check: user={user_id}, role={user_role.value}, "
            f"module={module.value}, action={action.value}, "
            f"required={required_role.value}, granted={has_permission}"
        )
        
        return has_permission
    
    def _role_has_permission(self, user_role: Role, required_role: Role) -> bool:
        """Check if user role meets the minimum required role."""
        role_hierarchy = {
            Role.GUEST: 0,
            Role.USER: 1,
            Role.MODERATOR: 2,
            Role.ADMIN: 3,
            Role.SUPER_ADMIN: 4
        }
        
        user_level = role_hierarchy.get(user_role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        return user_level >= required_level
    
    def get_user_permissions(self, user_id: int) -> Dict[str, Dict[str, bool]]:
        """Get all permissions for a user."""
        user_role = self.get_user_role(user_id)
        permissions = {}
        
        for module, actions in self._rbac_matrix.items():
            permissions[module.value] = {}
            for action, required_role in actions.items():
                permissions[module.value][action.value] = self._role_has_permission(user_role, required_role)
        
        return permissions
    
    def require_permission(self, user_id: int, module: Module, action: Action):
        """Decorator/guard to require specific permission."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                if not self.check_permission(user_id, module, action):
                    raise PermissionError(
                        f"User {user_id} lacks permission for {module.value}/{action.value}"
                    )
                return func(*args, **kwargs)
            return wrapper
        return decorator

# Global RBAC instance
rbac_manager = RBACManager()