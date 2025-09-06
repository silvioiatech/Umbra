"""
Concierge MCP v0 - Docker-first ops butler with risk classification

Complete VPS management with:
- Risk-classified command execution with approvals
- Docker container management with locking
- File operations with chunking and integrity
- AI-assisted patching with validation
- Comprehensive audit trail to R2
- RBAC enforcement and output redaction
"""
import os
import time
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import asdict

from ..core.logger import get_context_logger
from ..core.approvals import ApprovalManager, ApprovalStatus
from ..core.redact import DataRedactor

from .concierge.risk import RiskClassifier, RiskLevel
from .concierge.system_ops import SystemOps, SystemMetrics
from .concierge.docker_ops import DockerOps
from .concierge.exec_ops import ExecOps, ExecutionRequest
from .concierge.files_ops import FileOps, FileManifest
from .concierge.patch_ops import PatchOps, PatchStatus
from .concierge.ai_helpers import AIHelpers
from .concierge.validators import Validators
from .concierge.instances_ops import InstancesRegistry, InstanceCreateRequest
from .concierge.update_watcher import UpdateWatcher

class ConciergeMCP:
    """
    Concierge MCP v0: Docker-first operations butler
    
    Provides comprehensive VPS management with risk classification,
    approval flows, and AI assistance while maintaining security
    and audit compliance.
    """
    
    def __init__(self, config, db_manager, ai_agent=None):
        self.config = config
        self.db = db_manager
        self.ai_agent = ai_agent
        self.logger = get_context_logger(__name__)
        
        # Initialize subsystems
        self.risk_classifier = RiskClassifier()
        self.approval_manager = ApprovalManager(db_manager)
        self.redactor = DataRedactor(getattr(config, 'PRIVACY_MODE', 'strict'))
        
        self.system_ops = SystemOps()
        self.docker_ops = DockerOps()
        self.exec_ops = ExecOps(db_manager, config)
        self.file_ops = FileOps(config)
        self.patch_ops = PatchOps(config, db_manager)
        self.ai_helpers = AIHelpers(config, ai_agent)
        self.validators = Validators(config)
        self.instances_registry = InstancesRegistry(config, db_manager)
        self.update_watcher = UpdateWatcher(config)
        
        # Configuration
        self.rbac_enabled = getattr(config, 'CONCIERGE_RBAC_ENABLED', True)
        self.audit_enabled = getattr(config, 'CONCIERGE_AUDIT_ENABLED', True)
        self.output_max_bytes = getattr(config, 'OUTPUT_MAX_BYTES', 100000)
        
        # Initialize audit schema
        self._init_audit_schema()
        
        self.logger.info(
            "Concierge MCP v0 initialized",
            extra={
                "subsystems": ["system_ops", "docker_ops", "exec_ops", "file_ops", "patch_ops", "ai_helpers", "instances_registry", "update_watcher"],
                "rbac_enabled": self.rbac_enabled,
                "audit_enabled": self.audit_enabled,
                "docker_available": self.docker_ops.docker_available,
                "ai_enabled": self.ai_helpers.ai_enabled,
                "instances_enabled": self.instances_registry.docker_available,
                "update_watcher_enabled": True,
                "scheduler_running": False  # Will be started separately
            }
        )
    
    def _init_audit_schema(self):
        """Initialize audit logging schema."""
        if not self.audit_enabled:
            return
        
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS concierge_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    params_redacted TEXT,
                    risk_level TEXT,
                    approval_token TEXT,
                    status TEXT NOT NULL,
                    duration_ms REAL,
                    result_hash TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_concierge_audit_user_time 
                ON concierge_audit (user_id, created_at)
            """)
            
        except Exception as e:
            self.logger.error(f"Failed to initialize audit schema: {e}")
    
    async def get_capabilities(self) -> Dict[str, Any]:
        """Get capabilities exposed by Concierge module."""
        return {
            # System monitoring (read-only)
            "check_system": {
                "description": "Get comprehensive system status and metrics",
                "parameters": {
                    "detailed": {"type": "boolean", "description": "Include detailed metrics", "default": False}
                },
                "admin_only": False
            },
            
            # Docker operations
            "docker_list": {
                "description": "List Docker containers with status",
                "parameters": {
                    "all": {"type": "boolean", "description": "Include stopped containers", "default": True}
                },
                "admin_only": False
            },
            "docker_logs": {
                "description": "Get container logs with filtering",
                "parameters": {
                    "container": {"type": "string", "description": "Container name or ID"},
                    "lines": {"type": "integer", "description": "Number of lines", "default": 100},
                    "since": {"type": "string", "description": "Time filter (e.g., '2h')", "default": None}
                },
                "admin_only": False
            },
            "docker_restart": {
                "description": "Restart Docker container with safety checks",
                "parameters": {
                    "container": {"type": "string", "description": "Container name or ID"}
                },
                "admin_only": True,
                "requires_approval": True
            },
            "docker_stats": {
                "description": "Get container resource statistics",
                "parameters": {
                    "container": {"type": "string", "description": "Specific container (optional)"}
                },
                "admin_only": False
            },
            
            # Command execution with risk classification
            "exec": {
                "description": "Execute shell command with risk assessment",
                "parameters": {
                    "command": {"type": "string", "description": "Command to execute"},
                    "cwd": {"type": "string", "description": "Working directory", "default": None},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
                    "approval_token": {"type": "string", "description": "Approval token for risky commands", "default": None}
                },
                "admin_only": False,  # Risk classification handles access control
                "requires_approval": "conditional"  # Based on risk level
            },
            "exec_macro": {
                "description": "Execute predefined safe command macro",
                "parameters": {
                    "macro": {"type": "string", "description": "Macro name (e.g., 'df_h', 'docker_stats')"}
                },
                "admin_only": False
            },
            
            # Approval management
            "approve": {
                "description": "Approve a pending operation",
                "parameters": {
                    "token": {"type": "string", "description": "Approval token"},
                    "confirm_token": {"type": "string", "description": "Double-confirmation token", "default": None}
                },
                "admin_only": True
            },
            "deny": {
                "description": "Deny a pending operation",
                "parameters": {
                    "token": {"type": "string", "description": "Approval token"}
                },
                "admin_only": True
            },
            "list_approvals": {
                "description": "List pending approval requests",
                "parameters": {
                    "user_id": {"type": "integer", "description": "Filter by user ID", "default": None}
                },
                "admin_only": True
            },
            
            # File operations
            "file_export": {
                "description": "Export file or directory with chunking",
                "parameters": {
                    "path": {"type": "string", "description": "File or directory path"},
                    "compress": {"type": "boolean", "description": "Compress archive", "default": True}
                },
                "admin_only": True,
                "requires_approval": True
            },
            "file_import": {
                "description": "Import file with integrity verification",
                "parameters": {
                    "operation_id": {"type": "string", "description": "Export operation ID"},
                    "destination": {"type": "string", "description": "Destination path"},
                    "overwrite": {"type": "boolean", "description": "Overwrite existing", "default": False}
                },
                "admin_only": True,
                "requires_approval": True
            },
            "file_info": {
                "description": "Get detailed file information",
                "parameters": {
                    "path": {"type": "string", "description": "File path"}
                },
                "admin_only": False
            },
            
            # AI-assisted patching
            "patch_propose": {
                "description": "Propose AI-assisted patch for file",
                "parameters": {
                    "target": {"type": "string", "description": "Target file path"},
                    "context": {"type": "string", "description": "Description of changes needed"}
                },
                "admin_only": True
            },
            "patch_preview": {
                "description": "Preview proposed patch",
                "parameters": {
                    "patch_id": {"type": "string", "description": "Patch operation ID"}
                },
                "admin_only": True
            },
            "patch_apply": {
                "description": "Apply patch with backup and validation",
                "parameters": {
                    "patch_id": {"type": "string", "description": "Patch operation ID"},
                    "backup": {"type": "boolean", "description": "Create backup", "default": True},
                    "validate": {"type": "boolean", "description": "Run validators", "default": True}
                },
                "admin_only": True,
                "requires_approval": True
            },
            "patch_rollback": {
                "description": "Rollback applied patch",
                "parameters": {
                    "patch_id": {"type": "string", "description": "Patch operation ID"}
                },
                "admin_only": True,
                "requires_approval": True
            },
            
            # AI helpers
            "analyze_logs": {
                "description": "AI-powered log analysis and triage",
                "parameters": {
                    "logs": {"type": "string", "description": "Log content to analyze"},
                    "context": {"type": "string", "description": "Additional context", "default": None}
                },
                "admin_only": False
            },
            "explain_stacktrace": {
                "description": "AI explanation of stacktrace/error",
                "parameters": {
                    "stacktrace": {"type": "string", "description": "Stacktrace content"},
                    "context": {"type": "string", "description": "Additional context", "default": None}
                },
                "admin_only": False
            },
            
            # Validation
            "validate_config": {
                "description": "Validate configuration file",
                "parameters": {
                    "file_path": {"type": "string", "description": "Configuration file path"},
                    "validators": {"type": "array", "description": "Specific validators to use", "default": None}
                },
                "admin_only": False
            },
            
            # C3: Instance Registry Management
            "instances.create": {
                "description": "Create new client n8n instance with automatic port allocation",
                "parameters": {
                    "client": {"type": "string", "description": "Client ID (unique identifier)"},
                    "name": {"type": "string", "description": "Display name for instance", "default": None},
                    "port": {"type": "integer", "description": "Specific port (auto-allocated if not specified)", "default": None},
                    "env_overrides": {"type": "object", "description": "Environment variable overrides", "default": None}
                },
                "admin_only": True,
                "requires_approval": True
            },
            "instances.list": {
                "description": "List client n8n instances with status and details",
                "parameters": {
                    "client": {"type": "string", "description": "Filter by specific client ID", "default": None}
                },
                "admin_only": False
            },
            "instances.delete": {
                "description": "Delete client instance with data preservation options",
                "parameters": {
                    "client": {"type": "string", "description": "Client ID to delete"},
                    "mode": {"type": "string", "description": "Deletion mode: 'keep' (preserve data) or 'wipe' (remove all)", "enum": ["keep", "wipe"]}
                },
                "admin_only": True,
                "requires_approval": True
            },
            "instances.stats": {
                "description": "Get instance registry statistics and port usage",
                "parameters": {},
                "admin_only": False
            },
            
            # C2: Auto-Update Watcher
            "updates.scan": {
                "description": "Scan for available Docker image updates",
                "parameters": {
                    "force": {"type": "boolean", "description": "Force scan even if recently completed", "default": False}
                },
                "admin_only": True
            },
            "updates.plan_main": {
                "description": "Create blue-green update plan for main n8n service",
                "parameters": {
                    "target_tag": {"type": "string", "description": "Specific tag to update to (optional)", "default": None},
                    "target_digest": {"type": "string", "description": "Specific digest to update to (optional)", "default": None}
                },
                "admin_only": True
            },
            "updates.plan_client": {
                "description": "Create update plan for client instance",
                "parameters": {
                    "client_name": {"type": "string", "description": "Client instance name"},
                    "when": {"type": "string", "description": "When to apply: 'window' or 'now'", "enum": ["window", "now"], "default": "window"}
                },
                "admin_only": True
            },
            "updates.apply": {
                "description": "Apply an update plan",
                "parameters": {
                    "plan_id": {"type": "string", "description": "Update plan ID"},
                    "confirmed": {"type": "boolean", "description": "Confirmation for plan execution", "default": False},
                    "double_confirmed": {"type": "boolean", "description": "Double confirmation for high-risk updates", "default": False}
                },
                "admin_only": True,
                "requires_approval": "conditional"
            },
            "updates.rollback": {
                "description": "Rollback service to previous version",
                "parameters": {
                    "service_name": {"type": "string", "description": "Service to rollback"}
                },
                "admin_only": True,
                "requires_approval": True
            },
            "updates.freeze": {
                "description": "Freeze or unfreeze service from automatic updates",
                "parameters": {
                    "service_name": {"type": "string", "description": "Service name"},
                    "frozen": {"type": "boolean", "description": "Freeze (true) or unfreeze (false)", "default": True}
                },
                "admin_only": True
            },
            "updates.window": {
                "description": "Set maintenance window for service",
                "parameters": {
                    "service_name": {"type": "string", "description": "Service name"},
                    "window": {"type": "string", "description": "Maintenance window (HH:MM-HH:MM)"}
                },
                "admin_only": True
            },
            "updates.status": {
                "description": "Get update watcher status and scan results",
                "parameters": {},
                "admin_only": False
            },
            "updates.start_scheduler": {
                "description": "Start automatic update scheduler",
                "parameters": {},
                "admin_only": True
            },
            "updates.stop_scheduler": {
                "description": "Stop automatic update scheduler",
                "parameters": {},
                "admin_only": True
            }
        }
    
    async def execute(self, action: str, params: Dict[str, Any], user_id: int, is_admin: bool = False) -> Dict[str, Any]:
        """
        Execute Concierge action with full RBAC and audit trail.
        
        Args:
            action: Action to execute
            params: Action parameters
            user_id: User requesting the action
            is_admin: Whether user has admin privileges
        
        Returns:
            Execution result with success/error information
        """
        start_time = time.time()
        
        # Get capabilities to check permissions
        capabilities = await self.get_capabilities()
        
        if action not in capabilities:
            return {
                "success": False,
                "error": f"Unknown action: {action}",
                "available_actions": list(capabilities.keys())
            }
        
        capability = capabilities[action]
        
        # Check admin requirements
        if capability.get("admin_only", False) and not is_admin:
            await self._audit_action(user_id, action, params, "permission_denied", 0, "Admin access required")
            return {
                "success": False,
                "error": "Admin access required for this action"
            }
        
        # Redact parameters for audit
        redacted_params = self.redactor.redact_dict(params)
        
        try:
            # Route to appropriate handler
            if action.startswith("docker_"):
                result = await self._handle_docker_action(action, params, user_id, is_admin)
            elif action in ["exec", "exec_macro"]:
                result = await self._handle_exec_action(action, params, user_id, is_admin)
            elif action in ["approve", "deny", "list_approvals"]:
                result = await self._handle_approval_action(action, params, user_id, is_admin)
            elif action.startswith("file_"):
                result = await self._handle_file_action(action, params, user_id, is_admin)
            elif action.startswith("patch_"):
                result = await self._handle_patch_action(action, params, user_id, is_admin)
            elif action in ["analyze_logs", "explain_stacktrace"]:
                result = await self._handle_ai_action(action, params, user_id, is_admin)
            elif action == "check_system":
                result = await self._handle_system_action(action, params, user_id, is_admin)
            elif action == "validate_config":
                result = await self._handle_validation_action(action, params, user_id, is_admin)
            elif action.startswith("instances."):
                result = await self._handle_instances_action(action, params, user_id, is_admin)
            elif action.startswith("updates."):
                result = await self._handle_updates_action(action, params, user_id, is_admin)
            else:
                result = {
                    "success": False,
                    "error": f"Action handler not implemented: {action}"
                }
            
            # Audit successful execution
            duration_ms = (time.time() - start_time) * 1000
            
            await self._audit_action(
                user_id, action, redacted_params, 
                "success" if result.get("success") else "error",
                duration_ms, 
                result.get("error")
            )
            
            return result
            
        except Exception as e:
            # Audit failed execution
            duration_ms = (time.time() - start_time) * 1000
            await self._audit_action(user_id, action, redacted_params, "exception", duration_ms, str(e))
            
            self.logger.error(
                f"Concierge action failed: {action}",
                extra={"error": str(e), "user_id": user_id, "params": redacted_params}
            )
            
            return {
                "success": False,
                "error": f"Action execution failed: {str(e)[:200]}"
            }
    
    async def _handle_system_action(self, action: str, params: Dict[str, Any], user_id: int, is_admin: bool) -> Dict[str, Any]:
        """Handle system monitoring actions."""
        
        if action == "check_system":
            detailed = params.get("detailed", False)
            
            try:
                # Get system metrics
                metrics = self.system_ops.check_system()
                
                if detailed:
                    # Include additional detailed information
                    cpu_info = self.system_ops.get_detailed_cpu_info()
                    memory_info = self.system_ops.get_memory_details()
                    disk_info = self.system_ops.get_disk_info()
                    network_info = self.system_ops.get_network_info()
                    top_processes = self.system_ops.get_top_processes(limit=10)
                    
                    result = {
                        "success": True,
                        "metrics": asdict(metrics),
                        "detailed": {
                            "cpu": cpu_info,
                            "memory": memory_info,
                            "disk": disk_info,
                            "network": network_info,
                            "top_processes": [asdict(p) for p in top_processes]
                        },
                        "health": self.system_ops.get_health_status(metrics),
                        "formatted": self.system_ops.format_system_summary(metrics)
                    }
                else:
                    result = {
                        "success": True,
                        "metrics": asdict(metrics),
                        "health": self.system_ops.get_health_status(metrics),
                        "formatted": self.system_ops.format_system_summary(metrics)
                    }
                
                return result
                
            except Exception as e:
                return {
                    "success": False,
                    "error": f"System check failed: {str(e)}"
                }
        
        return {"success": False, "error": f"Unknown system action: {action}"}
    
    async def _handle_docker_action(self, action: str, params: Dict[str, Any], user_id: int, is_admin: bool) -> Dict[str, Any]:
        """Handle Docker-related actions."""
        
        if not self.docker_ops.docker_available:
            return {
                "success": False,
                "error": "Docker not available on this system"
            }
        
        if action == "docker_list":
            all_containers = params.get("all", True)
            containers = self.docker_ops.list_containers(all_containers)
            
            return {
                "success": True,
                "containers": [asdict(c) for c in containers],
                "count": len(containers),
                "formatted": self.docker_ops.format_container_list(containers)
            }
        
        elif action == "docker_logs":
            container = params.get("container")
            lines = params.get("lines", 100)
            since = params.get("since")
            
            if not container:
                return {"success": False, "error": "Container name/ID required"}
            
            success, logs = self.docker_ops.tail_logs(container, lines, since)
            
            return {
                "success": success,
                "logs": logs if success else None,
                "error": logs if not success else None
            }
        
        elif action == "docker_restart":
            container = params.get("container")
            
            if not container:
                return {"success": False, "error": "Container name/ID required"}
            
            success, message = self.docker_ops.restart_container(container)
            
            return {
                "success": success,
                "message": message,
                "error": message if not success else None
            }
        
        elif action == "docker_stats":
            container = params.get("container")
            stats = self.docker_ops.get_container_stats(container)
            
            return {
                "success": True,
                "stats": [asdict(s) for s in stats],
                "formatted": self.docker_ops.format_container_stats(stats)
            }
        
        return {"success": False, "error": f"Unknown Docker action: {action}"}
    
    async def _handle_exec_action(self, action: str, params: Dict[str, Any], user_id: int, is_admin: bool) -> Dict[str, Any]:
        """Handle command execution actions."""
        
        if action == "exec":
            command = params.get("command", "").strip()
            
            if not command:
                return {"success": False, "error": "Command required"}
            
            # Create execution request
            request = ExecutionRequest(
                command=command,
                user_id=user_id,
                cwd=params.get("cwd"),
                timeout=params.get("timeout", 30),
                approval_token=params.get("approval_token")
            )
            
            # Execute with risk assessment and approval flow
            result = self.exec_ops.execute_command(request)
            
            # Format result for response
            response = {
                "success": result.success,
                "command": result.command,
                "risk_level": result.risk_level.value,
                "return_code": result.return_code,
                "execution_time": result.execution_time,
                "formatted": self.exec_ops.format_execution_result(result)
            }
            
            if result.success:
                response["output"] = {
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
            else:
                response["error"] = result.stderr
                if result.approval_token:
                    response["approval_token"] = result.approval_token
                    response["approval_required"] = True
            
            return response
        
        elif action == "exec_macro":
            macro = params.get("macro", "").strip()
            
            if not macro:
                return {"success": False, "error": "Macro name required"}
            
            # Get available macros
            macros = self.exec_ops.get_safe_macros()
            
            if macro not in macros:
                return {
                    "success": False,
                    "error": f"Unknown macro: {macro}",
                    "available_macros": list(macros.keys())
                }
            
            # Execute macro
            result = self.exec_ops.execute_macro(macro, user_id)
            
            return {
                "success": result.success,
                "macro": macro,
                "command": macros[macro],
                "output": {
                    "stdout": result.stdout,
                    "stderr": result.stderr
                } if result.success else None,
                "error": result.stderr if not result.success else None,
                "formatted": self.exec_ops.format_execution_result(result)
            }
        
        return {"success": False, "error": f"Unknown exec action: {action}"}
    
    async def _handle_approval_action(self, action: str, params: Dict[str, Any], user_id: int, is_admin: bool) -> Dict[str, Any]:
        """Handle approval management actions."""
        
        if action == "approve":
            token = params.get("token", "").strip()
            confirm_token = params.get("confirm_token", "").strip()
            
            if not token:
                return {"success": False, "error": "Approval token required"}
            
            # Get approval request
            approval_request = self.approval_manager.get_approval_request(token)
            if not approval_request:
                return {"success": False, "error": "Invalid approval token"}
            
            # Handle double confirmation if required
            if approval_request.requires_double_confirm:
                if not confirm_token:
                    # First approval step
                    success = self.approval_manager.approve_request(token, user_id)
                    if success:
                        # Reload to get confirm token
                        approval_request = self.approval_manager.get_approval_request(token)
                        return {
                            "success": True,
                            "message": "First approval granted",
                            "double_confirm_required": True,
                            "confirm_token": approval_request.double_confirm_token
                        }
                    else:
                        return {"success": False, "error": "Failed to approve request"}
                else:
                    # Second approval step (double confirmation)
                    success = self.approval_manager.double_confirm_request(token, confirm_token, user_id)
                    if success:
                        return {
                            "success": True,
                            "message": "Double confirmation completed - request approved"
                        }
                    else:
                        return {"success": False, "error": "Invalid confirmation token"}
            else:
                # Simple approval
                success = self.approval_manager.approve_request(token, user_id)
                return {
                    "success": success,
                    "message": "Request approved" if success else "Failed to approve request"
                }
        
        elif action == "deny":
            token = params.get("token", "").strip()
            
            if not token:
                return {"success": False, "error": "Approval token required"}
            
            success = self.approval_manager.deny_request(token, user_id)
            return {
                "success": success,
                "message": "Request denied" if success else "Failed to deny request"
            }
        
        elif action == "list_approvals":
            filter_user_id = params.get("user_id")
            pending_approvals = self.approval_manager.get_pending_approvals(filter_user_id)
            
            return {
                "success": True,
                "approvals": [
                    {
                        "token": approval.token[:8] + "...",
                        "command": approval.command,
                        "risk_level": approval.risk_level.value,
                        "requires_double_confirm": approval.requires_double_confirm,
                        "created_at": approval.created_at,
                        "expires_at": approval.expires_at,
                        "user_id": approval.user_id,
                        "formatted": self.approval_manager.format_approval_request(approval)
                    }
                    for approval in pending_approvals
                ],
                "count": len(pending_approvals)
            }
        
        return {"success": False, "error": f"Unknown approval action: {action}"}
    
    async def _handle_file_action(self, action: str, params: Dict[str, Any], user_id: int, is_admin: bool) -> Dict[str, Any]:
        """Handle file operation actions."""
        
        if action == "file_export":
            path = params.get("path", "").strip()
            compress = params.get("compress", True)
            
            if not path:
                return {"success": False, "error": "File path required"}
            
            success, manifest, error = self.file_ops.file_send(path, compress=compress)
            
            if success:
                return {
                    "success": True,
                    "operation_id": manifest.operation_id,
                    "manifest": asdict(manifest),
                    "chunks": len(manifest.chunks),
                    "total_size": manifest.total_size
                }
            else:
                return {"success": False, "error": error}
        
        elif action == "file_import":
            operation_id = params.get("operation_id", "").strip()
            destination = params.get("destination", "").strip()
            overwrite = params.get("overwrite", False)
            
            if not operation_id or not destination:
                return {"success": False, "error": "Operation ID and destination required"}
            
            # Get manifest for operation
            manifests = self.file_ops.list_pending_operations()
            manifest = None
            for m in manifests:
                if m.operation_id == operation_id:
                    manifest = m
                    break
            
            if not manifest:
                return {"success": False, "error": f"Operation not found: {operation_id}"}
            
            success, result, error = self.file_ops.file_receive(manifest, destination, overwrite)
            
            if success:
                return {
                    "success": True,
                    "result": asdict(result),
                    "formatted": self.file_ops.format_transfer_result(result)
                }
            else:
                return {"success": False, "error": error}
        
        elif action == "file_info":
            path = params.get("path", "").strip()
            
            if not path:
                return {"success": False, "error": "File path required"}
            
            info = self.file_ops.get_file_info(path)
            
            if info:
                return {"success": True, "info": info}
            else:
                return {"success": False, "error": "File not found or access denied"}
        
        return {"success": False, "error": f"Unknown file action: {action}"}
    
    async def _handle_patch_action(self, action: str, params: Dict[str, Any], user_id: int, is_admin: bool) -> Dict[str, Any]:
        """Handle patch operation actions."""
        
        if action == "patch_propose":
            target = params.get("target", "").strip()
            context = params.get("context", "").strip()
            
            if not target or not context:
                return {"success": False, "error": "Target file and context required"}
            
            success, patch_op, error = await self.patch_ops.propose_patch(
                target, context, user_id, self.ai_agent
            )
            
            if success:
                return {
                    "success": True,
                    "patch_id": patch_op.patch_id,
                    "patch": asdict(patch_op),
                    "risk_assessment": patch_op.risk_assessment,
                    "ai_confidence": patch_op.ai_confidence
                }
            else:
                return {"success": False, "error": error}
        
        elif action == "patch_preview":
            patch_id = params.get("patch_id", "").strip()
            
            if not patch_id:
                return {"success": False, "error": "Patch ID required"}
            
            success, preview, error = self.patch_ops.patch_preview(patch_id)
            
            if success:
                return {"success": True, "preview": preview}
            else:
                return {"success": False, "error": error}
        
        elif action == "patch_apply":
            patch_id = params.get("patch_id", "").strip()
            backup = params.get("backup", True)
            validate = params.get("validate", True)
            
            if not patch_id:
                return {"success": False, "error": "Patch ID required"}
            
            success, patch_op, error = self.patch_ops.patch_apply(
                patch_id, atomic=True, backup=backup, validate=validate
            )
            
            if success:
                return {
                    "success": True,
                    "patch": asdict(patch_op),
                    "validation_results": patch_op.validation_results
                }
            else:
                return {"success": False, "error": error}
        
        elif action == "patch_rollback":
            patch_id = params.get("patch_id", "").strip()
            
            if not patch_id:
                return {"success": False, "error": "Patch ID required"}
            
            success, error = self.patch_ops.patch_rollback(patch_id)
            
            return {
                "success": success,
                "message": "Patch rolled back successfully" if success else error
            }
        
        return {"success": False, "error": f"Unknown patch action: {action}"}
    
    async def _handle_ai_action(self, action: str, params: Dict[str, Any], user_id: int, is_admin: bool) -> Dict[str, Any]:
        """Handle AI assistant actions."""
        
        if not self.ai_helpers.ai_enabled:
            return {
                "success": False,
                "error": "AI assistance not available"
            }
        
        if action == "analyze_logs":
            logs = params.get("logs", "").strip()
            context = params.get("context")
            
            if not logs:
                return {"success": False, "error": "Log content required"}
            
            try:
                analysis = await self.ai_helpers.analyze_logs(logs, context)
                
                return {
                    "success": True,
                    "analysis": asdict(analysis),
                    "summary": analysis.summary,
                    "recommendations": analysis.recommendations,
                    "confidence": analysis.confidence_score
                }
            except Exception as e:
                return {"success": False, "error": f"Log analysis failed: {str(e)}"}
        
        elif action == "explain_stacktrace":
            stacktrace = params.get("stacktrace", "").strip()
            context = params.get("context")
            
            if not stacktrace:
                return {"success": False, "error": "Stacktrace content required"}
            
            try:
                analysis = await self.ai_helpers.explain_stacktrace(stacktrace, context)
                
                return {
                    "success": True,
                    "analysis": asdict(analysis),
                    "explanation": analysis.explanation,
                    "suggested_fixes": analysis.suggested_fixes,
                    "confidence": analysis.confidence_score
                }
            except Exception as e:
                return {"success": False, "error": f"Stacktrace analysis failed: {str(e)}"}
        
        return {"success": False, "error": f"Unknown AI action: {action}"}
    
    async def _handle_validation_action(self, action: str, params: Dict[str, Any], user_id: int, is_admin: bool) -> Dict[str, Any]:
        """Handle validation actions."""
        
        if action == "validate_config":
            file_path = params.get("file_path", "").strip()
            validators = params.get("validators")
            
            if not file_path:
                return {"success": False, "error": "File path required"}
            
            try:
                results = self.validators.validate_file(file_path, validators)
                
                success = all(result.success for result in results if result.validator_name != "file_existence")
                
                return {
                    "success": success,
                    "validation_results": [asdict(result) for result in results],
                    "summary": f"{len([r for r in results if r.success])}/{len(results)} validators passed"
                }
            except Exception as e:
                return {"success": False, "error": f"Validation failed: {str(e)}"}
        
        return {"success": False, "error": f"Unknown validation action: {action}"}
    
    async def _handle_instances_action(self, action: str, params: Dict[str, Any], user_id: int, is_admin: bool) -> Dict[str, Any]:
        """Handle instance registry actions."""
        
        if action == "instances.create":
            client = params.get("client", "").strip()
            name = params.get("name")
            port = params.get("port")
            env_overrides = params.get("env_overrides")
            
            if not client:
                return {"success": False, "error": "Client ID required"}
            
            # Create instance request
            request = InstanceCreateRequest(
                client=client,
                name=name,
                port=port,
                env_overrides=env_overrides
            )
            
            # Create instance
            result = await self.instances_registry.create_instance(request, user_id)
            
            if result.success:
                return {
                    "success": True,
                    "instance": {
                        "client_id": result.instance.client_id,
                        "display_name": result.instance.display_name,
                        "url": result.instance.url,
                        "port": result.instance.port,
                        "data_dir": result.instance.data_dir,
                        "status": result.instance.status
                    },
                    "audit_id": result.audit_id,
                    "message": f"Instance created successfully: {result.instance.client_id}"
                }
            else:
                return {
                    "success": False,
                    "error": result.error,
                    "audit_id": result.audit_id
                }
        
        elif action == "instances.list":
            client_filter = params.get("client")
            
            try:
                instances = self.instances_registry.list_instances(client_filter)
                
                # Format instances for response
                instances_data = []
                for instance in instances:
                    instances_data.append({
                        "client_id": instance.client_id,
                        "display_name": instance.display_name,
                        "url": instance.url,
                        "port": instance.port,
                        "data_dir": instance.data_dir,
                        "status": instance.status,
                        "reserved": instance.reserved,
                        "created_at": instance.created_at,
                        "updated_at": instance.updated_at
                    })
                
                return {
                    "success": True,
                    "instances": instances_data,
                    "count": len(instances_data),
                    "formatted": self.instances_registry.format_instances_summary(instances)
                }
                
            except Exception as e:
                return {"success": False, "error": f"Failed to list instances: {str(e)}"}
        
        elif action == "instances.delete":
            client = params.get("client", "").strip()
            mode = params.get("mode", "keep").strip().lower()
            
            if not client:
                return {"success": False, "error": "Client ID required"}
            
            if mode not in ["keep", "wipe"]:
                return {"success": False, "error": "Mode must be 'keep' or 'wipe'"}
            
            try:
                success, audit_id, error = await self.instances_registry.delete_instance(
                    client, mode, user_id
                )
                
                if success:
                    return {
                        "success": True,
                        "message": f"Instance {client} deleted successfully (mode: {mode})",
                        "audit_id": audit_id
                    }
                else:
                    return {
                        "success": False,
                        "error": error,
                        "audit_id": audit_id
                    }
                    
            except Exception as e:
                return {"success": False, "error": f"Failed to delete instance: {str(e)}"}
        
        elif action == "instances.stats":
            try:
                port_stats = self.instances_registry.get_port_usage_stats()
                instances = self.instances_registry.list_instances()
                
                # Count by status
                status_counts = {}
                for instance in instances:
                    status_counts[instance.status] = status_counts.get(instance.status, 0) + 1
                
                return {
                    "success": True,
                    "port_usage": port_stats,
                    "instance_counts": {
                        "total": len(instances),
                        "by_status": status_counts
                    },
                    "health": self.instances_registry.health_check()
                }
                
            except Exception as e:
                return {"success": False, "error": f"Failed to get instance stats: {str(e)}"}
        
        return {"success": False, "error": f"Unknown instances action: {action}"}
    
    async def _handle_updates_action(self, action: str, params: Dict[str, Any], user_id: int, is_admin: bool) -> Dict[str, Any]:
        """Handle auto-update watcher actions."""
        
        if action == "updates.scan":
            force = params.get("force", False)
            
            try:
                # Skip scan if recent one exists and not forced
                if not force and self.update_watcher.last_scan:
                    from datetime import datetime, timedelta
                    if datetime.now() - self.update_watcher.last_scan < timedelta(minutes=30):
                        return {
                            "success": True,
                            "message": "Recent scan available, use force=true to rescan",
                            "scan_results": self.update_watcher.get_scan_results(),
                            "last_scan": self.update_watcher.last_scan.isoformat()
                        }
                
                # Perform scan
                scan_results = await self.update_watcher.scan()
                
                # Format results
                formatted_results = {}
                for service_name, result in scan_results.items():
                    formatted_results[service_name] = {
                        "current_digest": result.current_digest[:12] + "...",
                        "available_digest": result.available_digest[:12] + "...",
                        "needs_update": result.needs_update,
                        "risk_level": result.risk_level.value,
                        "release_notes": result.release_notes
                    }
                
                updates_available = sum(1 for r in scan_results.values() if r.needs_update)
                
                return {
                    "success": True,
                    "scan_results": formatted_results,
                    "summary": {
                        "services_scanned": len(scan_results),
                        "updates_available": updates_available,
                        "last_scan": self.update_watcher.last_scan.isoformat()
                    }
                }
                
            except Exception as e:
                return {"success": False, "error": f"Scan failed: {str(e)}"}
        
        elif action == "updates.plan_main":
            target_tag = params.get("target_tag")
            target_digest = params.get("target_digest")
            
            try:
                plan = await self.update_watcher.plan_main_blue_green(target_tag, target_digest)
                
                return {
                    "success": True,
                    "plan": {
                        "id": plan.id,
                        "service_name": plan.service_name,
                        "target_tag": plan.target_tag,
                        "risk_level": plan.risk_level.value,
                        "steps_count": len(plan.steps),
                        "estimated_duration": plan.estimated_duration,
                        "requires_double_confirm": plan.requires_double_confirm,
                        "created_at": plan.created_at.isoformat()
                    },
                    "steps_preview": [{
                        "id": step["id"],
                        "description": step["description"],
                        "timeout": step["timeout"]
                    } for step in plan.steps[:5]]  # Show first 5 steps
                }
                
            except Exception as e:
                return {"success": False, "error": f"Plan creation failed: {str(e)}"}
        
        elif action == "updates.plan_client":
            client_name = params.get("client_name", "").strip()
            when = params.get("when", "window")
            
            if not client_name:
                return {"success": False, "error": "Client name required"}
            
            try:
                plan = await self.update_watcher.plan_client(client_name, when)
                
                return {
                    "success": True,
                    "plan": {
                        "id": plan.id,
                        "client_name": plan.service_name,
                        "target_tag": plan.target_tag,
                        "risk_level": plan.risk_level.value,
                        "steps_count": len(plan.steps),
                        "estimated_duration": plan.estimated_duration,
                        "requires_double_confirm": plan.requires_double_confirm,
                        "scheduled_for": when
                    }
                }
                
            except Exception as e:
                return {"success": False, "error": f"Client plan creation failed: {str(e)}"}
        
        elif action == "updates.apply":
            plan_id = params.get("plan_id", "").strip()
            confirmed = params.get("confirmed", False)
            double_confirmed = params.get("double_confirmed", False)
            
            if not plan_id:
                return {"success": False, "error": "Plan ID required"}
            
            if not confirmed:
                return {
                    "success": False,
                    "error": "Plan execution requires confirmation",
                    "confirmation_required": True
                }
            
            try:
                result = await self.update_watcher.apply(plan_id, confirmed, double_confirmed)
                
                return {
                    "success": True,
                    "execution_result": {
                        "deployment_id": result.get("deployment_id"),
                        "success": result.get("success"),
                        "steps_completed": len(result.get("steps", [])),
                        "duration": result.get("completed_at", 0) - result.get("started_at", 0)
                    },
                    "message": "Update applied successfully" if result.get("success") else "Update failed"
                }
                
            except Exception as e:
                return {"success": False, "error": f"Update application failed: {str(e)}"}
        
        elif action == "updates.rollback":
            service_name = params.get("service_name", "").strip()
            
            if not service_name:
                return {"success": False, "error": "Service name required"}
            
            try:
                result = await self.update_watcher.rollback(service_name)
                
                return {
                    "success": True,
                    "rollback_result": result,
                    "message": f"Service {service_name} rolled back successfully"
                }
                
            except Exception as e:
                return {"success": False, "error": f"Rollback failed: {str(e)}"}
        
        elif action == "updates.freeze":
            service_name = params.get("service_name", "").strip()
            frozen = params.get("frozen", True)
            
            if not service_name:
                return {"success": False, "error": "Service name required"}
            
            try:
                result = await self.update_watcher.freeze(service_name, frozen)
                
                return {
                    "success": True,
                    "result": result,
                    "message": f"Service {service_name} {'frozen' if frozen else 'unfrozen'}"
                }
                
            except Exception as e:
                return {"success": False, "error": f"Freeze operation failed: {str(e)}"}
        
        elif action == "updates.window":
            service_name = params.get("service_name", "").strip()
            window = params.get("window", "").strip()
            
            if not service_name or not window:
                return {"success": False, "error": "Service name and window required"}
            
            try:
                result = await self.update_watcher.set_maintenance_window(service_name, window)
                
                return {
                    "success": True,
                    "result": result,
                    "message": f"Maintenance window set for {service_name}: {window}"
                }
                
            except Exception as e:
                return {"success": False, "error": f"Window setting failed: {str(e)}"}
        
        elif action == "updates.status":
            try:
                status = self.update_watcher.get_status()
                scan_results = self.update_watcher.get_scan_results()
                active_plans = self.update_watcher.get_active_plans()
                
                # Format scan results summary
                scan_summary = {}
                for service_name, result in scan_results.items():
                    scan_summary[service_name] = {
                        "needs_update": result.needs_update,
                        "risk_level": result.risk_level.value
                    }
                
                return {
                    "success": True,
                    "status": status,
                    "scan_summary": scan_summary,
                    "active_plans": {
                        "count": len(active_plans),
                        "plans": [{
                            "id": plan.id,
                            "service": plan.service_name,
                            "risk": plan.risk_level.value
                        } for plan in active_plans.values()]
                    }
                }
                
            except Exception as e:
                return {"success": False, "error": f"Status retrieval failed: {str(e)}"}
        
        elif action == "updates.start_scheduler":
            try:
                await self.update_watcher.start_scheduler()
                
                return {
                    "success": True,
                    "message": "Update scheduler started",
                    "next_scan": self.update_watcher._get_next_scan_time().isoformat()
                }
                
            except Exception as e:
                return {"success": False, "error": f"Scheduler start failed: {str(e)}"}
        
        elif action == "updates.stop_scheduler":
            try:
                await self.update_watcher.stop_scheduler()
                
                return {
                    "success": True,
                    "message": "Update scheduler stopped"
                }
                
            except Exception as e:
                return {"success": False, "error": f"Scheduler stop failed: {str(e)}"}
        
        return {"success": False, "error": f"Unknown updates action: {action}"}
    
    async def _audit_action(
        self, 
        user_id: int, 
        action: str, 
        params: Dict[str, Any], 
        status: str,
        duration_ms: float, 
        error_message: Optional[str] = None
    ):
        """Audit action execution."""
        if not self.audit_enabled:
            return
        
        try:
            # Generate result hash for integrity
            import hashlib
            result_data = f"{status}:{duration_ms}:{len(str(error_message or ''))}"
            result_hash = hashlib.sha256(result_data.encode()).hexdigest()[:16]
            
            # Get risk level if it was classified
            risk_level = None
            if action == "exec" and "command" in params:
                risk_level, _, _ = self.risk_classifier.classify_command(params["command"])
                risk_level = risk_level.value
            
            self.db.execute("""
                INSERT INTO concierge_audit (
                    user_id, action, params_redacted, risk_level, status,
                    duration_ms, result_hash, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                action,
                str(params)[:1000],  # Truncate long params
                risk_level,
                status,
                duration_ms,
                result_hash,
                error_message[:500] if error_message else None  # Truncate long errors
            ))
            
        except Exception as e:
            self.logger.error(f"Audit logging failed: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of Concierge subsystems."""
        try:
            checks = {}
            
            # System operations
            try:
                metrics = self.system_ops.check_system()
                checks["system_ops"] = {
                    "status": "ok",
                    "details": f"System monitoring functional, {metrics.cpu_percent:.1f}% CPU"
                }
            except Exception as e:
                checks["system_ops"] = {"status": "error", "details": str(e)}
            
            # Docker operations
            checks["docker_ops"] = {
                "status": "ok" if self.docker_ops.docker_available else "warning",
                "details": "Docker available" if self.docker_ops.docker_available else "Docker not available"
            }
            
            # Database connectivity
            try:
                self.db.query_one("SELECT 1")
                checks["database"] = {"status": "ok", "details": "Database accessible"}
            except Exception as e:
                checks["database"] = {"status": "error", "details": str(e)}
            
            # AI assistance
            checks["ai_helpers"] = {
                "status": "ok" if self.ai_helpers.ai_enabled else "warning",
                "details": "AI assistance available" if self.ai_helpers.ai_enabled else "AI not configured"
            }
            
            # Update watcher
            try:
                update_status = self.update_watcher.get_status()
                checks["update_watcher"] = {
                    "status": "ok" if update_status["scheduler_running"] else "warning",
                    "details": f"Scheduler {'running' if update_status['scheduler_running'] else 'stopped'}, {update_status['services_with_updates']} updates available"
                }
            except Exception as e:
                checks["update_watcher"] = {"status": "error", "details": str(e)}
            
            # Approval manager
            try:
                stats = self.approval_manager.get_approval_stats()
                checks["approval_manager"] = {
                    "status": "ok",
                    "details": f"Approval system functional, {stats.get('pending_count', 0)} pending"
                }
            except Exception as e:
                checks["approval_manager"] = {"status": "error", "details": str(e)}
            
            # Overall status
            error_count = len([c for c in checks.values() if c["status"] == "error"])
            
            if error_count == 0:
                overall_status = "healthy"
            elif error_count <= 2:
                overall_status = "degraded"
            else:
                overall_status = "unhealthy"
            
            return {
                "status": overall_status,
                "subsystems": checks,
                "config": {
                    "rbac_enabled": self.rbac_enabled,
                    "audit_enabled": self.audit_enabled,
                    "docker_available": self.docker_ops.docker_available,
                    "ai_enabled": self.ai_helpers.ai_enabled,
                    "update_watcher_enabled": True,
                    "scheduler_running": self.update_watcher.scheduler_task is not None and not self.update_watcher.scheduler_task.done() if hasattr(self.update_watcher, 'scheduler_task') else False
                }
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def cleanup(self):
        """Cleanup temporary files and expired approvals."""
        try:
            # Stop update scheduler if running
            if hasattr(self.update_watcher, 'scheduler_task') and self.update_watcher.scheduler_task:
                await self.update_watcher.stop_scheduler()
            
            # Cleanup expired approvals
            cleaned_approvals = self.approval_manager.cleanup_expired()
            
            # Cleanup temporary files
            self.file_ops.cleanup_old_operations()
            self.patch_ops.cleanup_old_backups()
            self.validators.cleanup_temp_files()
            
            self.logger.info(
                "Concierge cleanup completed",
                extra={"cleaned_approvals": cleaned_approvals, "scheduler_stopped": True}
            )
            
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")

# Export
__all__ = ["ConciergeMCP"]
