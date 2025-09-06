"""
Module Registry - F3: Discovery and management of MCP-style modules.
Provides uniform interface for module discovery and interaction.
"""
import os
import importlib
import inspect
from typing import Dict, Any, List, Optional, Callable, Type
from pathlib import Path
from dataclasses import dataclass

from ..core.logger import get_context_logger, set_request_context

logger = get_context_logger(__name__)

@dataclass
class ModuleCapability:
    """Represents a capability exposed by a module."""
    name: str
    description: str
    parameters: Dict[str, Any]
    admin_only: bool = False

@dataclass
class ModuleInfo:
    """Information about a discovered module."""
    name: str
    class_name: str
    module_path: str
    capabilities: List[ModuleCapability]
    instance: Optional[Any] = None
    available: bool = True
    error: Optional[str] = None

class ModuleRegistry:
    """
    Discovers and manages MCP-style modules.
    
    F3 Implementation: Discovers modules exposing get_capabilities() and execute(action, params).
    Provides uniform call surface for all modules.
    """
    
    def __init__(self, config=None, db_manager=None):
        self.config = config
        self.db_manager = db_manager
        self.logger = get_context_logger(__name__)
        
        # Registry of discovered modules
        self.modules: Dict[str, ModuleInfo] = {}
        self.module_instances: Dict[str, Any] = {}
        
        # Module directory path
        self.modules_path = Path(__file__).parent
        
        self.logger.info(
            "ModuleRegistry initialized", 
            extra={
                "modules_path": str(self.modules_path),
                "config_available": config is not None,
                "db_available": db_manager is not None
            }
        )
    
    async def discover_modules(self) -> int:
        """
        Discover all *_mcp.py modules in the modules directory.
        Returns the number of modules discovered.
        """
        
        self.logger.info("Starting module discovery")
        discovered_count = 0
        
        try:
            # Get all *_mcp.py files
            mcp_files = list(self.modules_path.glob("*_mcp.py"))
            
            self.logger.info(
                "Found MCP files",
                extra={
                    "file_count": len(mcp_files),
                    "files": [f.name for f in mcp_files]
                }
            )
            
            for mcp_file in mcp_files:
                try:
                    module_name = mcp_file.stem  # Remove .py extension
                    await self._discover_module(module_name, mcp_file)
                    discovered_count += 1
                    
                except Exception as e:
                    self.logger.error(
                        "Failed to discover module",
                        extra={
                            "module_file": mcp_file.name,
                            "error": str(e),
                            "error_type": type(e).__name__
                        }
                    )
                    
                    # Add failed module to registry with error
                    self.modules[module_name] = ModuleInfo(
                        name=module_name,
                        class_name="unknown",
                        module_path=str(mcp_file),
                        capabilities=[],
                        available=False,
                        error=str(e)
                    )
            
            self.logger.info(
                "Module discovery completed",
                extra={
                    "discovered_count": discovered_count,
                    "total_modules": len(self.modules),
                    "available_modules": len([m for m in self.modules.values() if m.available])
                }
            )
            
            return discovered_count
            
        except Exception as e:
            self.logger.error(
                "Module discovery failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            return 0
    
    async def _discover_module(self, module_name: str, module_path: Path) -> None:
        """Discover and register a single module."""
        
        self.logger.debug(
            "Discovering module",
            extra={
                "module_name": module_name,
                "module_path": str(module_path)
            }
        )
        
        try:
            # Import the module
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if not spec or not spec.loader:
                raise ImportError(f"Could not load spec for {module_name}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find the main class (should be NameMCP format)
            expected_class_name = self._get_expected_class_name(module_name)
            module_class = None
            
            # Look for the expected class name first
            if hasattr(module, expected_class_name):
                module_class = getattr(module, expected_class_name)
            else:
                # Fallback: find any class with MCP in the name
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (inspect.isclass(attr) and 
                        'MCP' in attr_name and 
                        attr_name != 'ModuleBase'):
                        module_class = attr
                        break
            
            if not module_class:
                raise ValueError(f"No MCP class found in {module_name}")
            
            # Create instance of the module
            if self.config and self.db_manager:
                instance = module_class(self.config, self.db_manager)
            elif self.config:
                instance = module_class(self.config)
            else:
                instance = module_class()
            
            # Get capabilities if the method exists
            capabilities = []
            if hasattr(instance, 'get_capabilities'):
                try:
                    caps_data = await instance.get_capabilities()
                    capabilities = self._parse_capabilities(caps_data)
                except Exception as e:
                    self.logger.warning(
                        "Failed to get module capabilities",
                        extra={
                            "module_name": module_name,
                            "error": str(e)
                        }
                    )
            
            # Initialize module if method exists
            if hasattr(instance, 'initialize'):
                try:
                    init_success = await instance.initialize()
                    if not init_success:
                        raise RuntimeError("Module initialization returned False")
                except Exception as e:
                    self.logger.warning(
                        "Module initialization failed",
                        extra={
                            "module_name": module_name,
                            "error": str(e)
                        }
                    )
                    # Continue with module registration even if init fails
            
            # Register the module
            module_info = ModuleInfo(
                name=module_name,
                class_name=module_class.__name__,
                module_path=str(module_path),
                capabilities=capabilities,
                instance=instance,
                available=True
            )
            
            self.modules[module_name] = module_info
            self.module_instances[module_name] = instance
            
            self.logger.info(
                "Module discovered and registered",
                extra={
                    "module_name": module_name,
                    "class_name": module_class.__name__,
                    "capabilities_count": len(capabilities),
                    "capabilities": [cap.name for cap in capabilities]
                }
            )
            
        except Exception as e:
            self.logger.error(
                "Module discovery failed",
                extra={
                    "module_name": module_name,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise
    
    def _get_expected_class_name(self, module_name: str) -> str:
        """Get expected class name for a module."""
        # Convert finance_mcp -> FinanceMCP
        parts = module_name.split('_')
        if parts[-1].lower() == 'mcp':
            parts = parts[:-1] + ['MCP']
        return ''.join(word.capitalize() for word in parts)
    
    def _parse_capabilities(self, caps_data: Any) -> List[ModuleCapability]:
        """Parse capabilities data into ModuleCapability objects."""
        capabilities = []
        
        if isinstance(caps_data, dict):
            for name, details in caps_data.items():
                if isinstance(details, dict):
                    capabilities.append(ModuleCapability(
                        name=name,
                        description=details.get('description', name),
                        parameters=details.get('parameters', {}),
                        admin_only=details.get('admin_only', False)
                    ))
                else:
                    capabilities.append(ModuleCapability(
                        name=name,
                        description=str(details),
                        parameters={}
                    ))
        
        elif isinstance(caps_data, list):
            for item in caps_data:
                if isinstance(item, dict):
                    capabilities.append(ModuleCapability(
                        name=item.get('name', 'unknown'),
                        description=item.get('description', ''),
                        parameters=item.get('parameters', {}),
                        admin_only=item.get('admin_only', False)
                    ))
                else:
                    capabilities.append(ModuleCapability(
                        name=str(item),
                        description=str(item),
                        parameters={}
                    ))
        
        return capabilities
    
    def get_available_modules(self) -> List[str]:
        """Get list of available module names."""
        return [
            name for name, info in self.modules.items() 
            if info.available
        ]
    
    def get_module_info(self, module_name: str) -> Optional[ModuleInfo]:
        """Get information about a specific module."""
        return self.modules.get(module_name)
    
    def get_all_capabilities(self) -> Dict[str, List[ModuleCapability]]:
        """Get all capabilities from all modules."""
        all_caps = {}
        for name, info in self.modules.items():
            if info.available:
                all_caps[name] = info.capabilities
        return all_caps
    
    async def execute_module_action(
        self, 
        module_name: str, 
        action: str, 
        params: Dict[str, Any],
        user_id: int
    ) -> Dict[str, Any]:
        """
        Execute an action on a module using the uniform interface.
        
        Expects modules to have execute(action, params) method.
        """
        
        # Set request context
        set_request_context(
            user_id=user_id,
            module=module_name,
            action=action
        )
        
        self.logger.info(
            "Executing module action",
            extra={
                "module_name": module_name,
                "action": action,
                "user_id": user_id,
                "params_keys": list(params.keys()) if params else []
            }
        )
        
        try:
            # Check if module exists and is available
            if module_name not in self.modules:
                return {
                    "success": False,
                    "error": f"Module '{module_name}' not found",
                    "error_type": "module_not_found"
                }
            
            module_info = self.modules[module_name]
            if not module_info.available:
                return {
                    "success": False,
                    "error": f"Module '{module_name}' is not available: {module_info.error}",
                    "error_type": "module_unavailable"
                }
            
            instance = module_info.instance
            if not instance:
                return {
                    "success": False,
                    "error": f"Module '{module_name}' has no instance",
                    "error_type": "module_no_instance"
                }
            
            # Check if module has execute method
            if hasattr(instance, 'execute'):
                # New F3 interface: execute(action, params)
                result = await instance.execute(action, params)
            elif hasattr(instance, 'process_envelope'):
                # Legacy interface: convert to envelope format
                from ..core.envelope import InternalEnvelope
                envelope = InternalEnvelope(
                    action=action,
                    data=params,
                    user_id=user_id
                )
                result = await instance.process_envelope(envelope)
            else:
                return {
                    "success": False,
                    "error": f"Module '{module_name}' has no execute or process_envelope method",
                    "error_type": "method_not_found"
                }
            
            self.logger.info(
                "Module action completed",
                extra={
                    "module_name": module_name,
                    "action": action,
                    "user_id": user_id,
                    "success": True
                }
            )
            
            # Standardize response format
            if isinstance(result, dict):
                return {
                    "success": True,
                    "result": result,
                    "module": module_name,
                    "action": action
                }
            else:
                return {
                    "success": True,
                    "result": {"content": str(result)},
                    "module": module_name,
                    "action": action
                }
            
        except Exception as e:
            self.logger.error(
                "Module action failed",
                extra={
                    "module_name": module_name,
                    "action": action,
                    "user_id": user_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "module": module_name,
                "action": action
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get registry status."""
        available_modules = self.get_available_modules()
        total_capabilities = sum(len(info.capabilities) for info in self.modules.values())
        
        return {
            "total_modules": len(self.modules),
            "available_modules": len(available_modules),
            "available_module_names": available_modules,
            "total_capabilities": total_capabilities,
            "modules_detail": {
                name: {
                    "available": info.available,
                    "capabilities_count": len(info.capabilities),
                    "class_name": info.class_name,
                    "error": info.error
                }
                for name, info in self.modules.items()
            }
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all modules."""
        health_results = {}
        
        for name, info in self.modules.items():
            if not info.available:
                health_results[name] = {
                    "status": "unavailable",
                    "error": info.error
                }
                continue
            
            try:
                instance = info.instance
                if hasattr(instance, 'health_check'):
                    health_result = await instance.health_check()
                    health_results[name] = health_result
                else:
                    health_results[name] = {
                        "status": "healthy",
                        "note": "No health_check method available"
                    }
            except Exception as e:
                health_results[name] = {
                    "status": "error",
                    "error": str(e)
                }
        
        # Overall health
        healthy_count = len([
            result for result in health_results.values() 
            if result.get("status") in ["healthy", "ok"]
        ])
        
        return {
            "overall_status": "healthy" if healthy_count > 0 else "degraded",
            "healthy_modules": healthy_count,
            "total_modules": len(health_results),
            "modules": health_results
        }

# Export
__all__ = ["ModuleRegistry", "ModuleInfo", "ModuleCapability"]
