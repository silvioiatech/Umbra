"""Test RBAC functionality."""
import pytest
from umbra.core.rbac import RBACManager, Role, Module, Action

class TestRBAC:
    """Test Role-Based Access Control system."""
    
    def test_rbac_manager_initialization(self):
        """Test RBAC manager initializes correctly."""
        rbac = RBACManager()
        assert rbac is not None
        assert len(rbac._rbac_matrix) > 0
    
    def test_user_role_assignment(self):
        """Test user role assignment and retrieval."""
        rbac = RBACManager()
        user_id = 12345
        
        # Default role should be GUEST
        assert rbac.get_user_role(user_id) == Role.GUEST
        
        # Assign USER role
        rbac.set_user_role(user_id, Role.USER)
        assert rbac.get_user_role(user_id) == Role.USER
        
        # Assign ADMIN role
        rbac.set_user_role(user_id, Role.ADMIN)
        assert rbac.get_user_role(user_id) == Role.ADMIN
    
    def test_permission_checks(self):
        """Test permission checking logic."""
        rbac = RBACManager()
        user_id = 12345
        
        # GUEST should not have access to most things
        rbac.set_user_role(user_id, Role.GUEST)
        assert not rbac.check_permission(user_id, Module.FINANCE, Action.READ)
        assert not rbac.check_permission(user_id, Module.SYSTEM, Action.READ)
        
        # USER should have basic access
        rbac.set_user_role(user_id, Role.USER)
        assert rbac.check_permission(user_id, Module.FINANCE, Action.READ)
        assert rbac.check_permission(user_id, Module.CREATOR, Action.EXECUTE)
        assert not rbac.check_permission(user_id, Module.SYSTEM, Action.USER_MANAGEMENT)
        
        # ADMIN should have broader access
        rbac.set_user_role(user_id, Role.ADMIN)
        assert rbac.check_permission(user_id, Module.FINANCE, Action.AUDIT_VIEW)
        assert rbac.check_permission(user_id, Module.SYSTEM, Action.USER_MANAGEMENT)
        assert not rbac.check_permission(user_id, Module.SYSTEM, Action.DELETE)
        
        # SUPER_ADMIN should have all access
        rbac.set_user_role(user_id, Role.SUPER_ADMIN)
        assert rbac.check_permission(user_id, Module.SYSTEM, Action.DELETE)
    
    def test_role_hierarchy(self):
        """Test role hierarchy works correctly."""
        rbac = RBACManager()
        
        # Test that higher roles inherit lower role permissions
        assert rbac._role_has_permission(Role.ADMIN, Role.USER)
        assert rbac._role_has_permission(Role.MODERATOR, Role.USER)
        assert rbac._role_has_permission(Role.SUPER_ADMIN, Role.ADMIN)
        
        # Test that lower roles don't have higher role permissions
        assert not rbac._role_has_permission(Role.USER, Role.ADMIN)
        assert not rbac._role_has_permission(Role.GUEST, Role.USER)
    
    def test_get_user_permissions(self):
        """Test getting all permissions for a user."""
        rbac = RBACManager()
        user_id = 12345
        
        rbac.set_user_role(user_id, Role.USER)
        permissions = rbac.get_user_permissions(user_id)
        
        assert isinstance(permissions, dict)
        assert "finance" in permissions
        assert "read" in permissions["finance"]
        assert permissions["finance"]["read"] is True
        
        # Admin-only actions should be False for USER
        assert "user_management" in permissions.get("system", {})
        assert permissions["system"]["user_management"] is False

if __name__ == "__main__":
    pytest.main([__file__])