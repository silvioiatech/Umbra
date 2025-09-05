"""
ModuleRegistry for dynamic discovery of MCP-style modules.
Discovers modules that expose get_capabilities() and execute(action, params).
"""
import os
import importlib
import inspect
import logging
from typing import Dict, List, Any, Optional, Type
from pathlib import Path

from ..core.module_base import ModuleBase


class ModuleRegistry:
    """Registry for discovering and managing MCP-style modules."""
    
    def __init__(self, config, db_manager):
        self.config = config
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Registry of discovered modules
        self.modules: Dict[str, ModuleBase] = {}
        self.module_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Module discovery paths
        self.discovery_paths = [
            Path(__file__).parent.parent / "modules",  # Default modules directory
        ]
        
        self.logger.info("🔍 ModuleRegistry initialized")
    
    async def discover_modules(self) -> Dict[str, ModuleBase]:
        """Discover and load all available modules."""
        self.logger.info("🔍 Starting module discovery...")
        
        discovered_count = 0
        
        for search_path in self.discovery_paths:
            if search_path.exists():
                discovered_count += await self._discover_in_path(search_path)
        
        # Initialize all discovered modules
        await self._initialize_modules()
        
        self.logger.info(f"✅ Module discovery completed: {discovered_count} modules found, {len(self.modules)} loaded")
        return self.modules
    
    async def _discover_in_path(self, search_path: Path) -> int:
        """Discover modules in a specific path."""
        discovered = 0
        
        # Look for Python files that might contain modules
        for py_file in search_path.glob("*_mcp.py"):
            try:
                module_name = py_file.stem
                if module_name.startswith('__'):
                    continue
                
                # Import the module
                module_path = f"umbra.modules.{module_name}"
                imported_module = importlib.import_module(module_path)
                
                # Find classes that inherit from ModuleBase
                for name, obj in inspect.getmembers(imported_module):
                    if (inspect.isclass(obj) and 
                        issubclass(obj, ModuleBase) and 
                        obj != ModuleBase):
                        
                        # Extract module ID from class name or filename
                        module_id = self._extract_module_id(name, module_name)
                        
                        try:
                            # Instantiate the module
                            module_instance = obj(self.config, self.db_manager)
                            
                            # Verify it has the required interface
                            if self._verify_module_interface(module_instance):
                                self.modules[module_id] = module_instance
                                self.module_metadata[module_id] = {
                                    'class_name': name,
                                    'file_path': str(py_file),
                                    'module_path': module_path,
                                    'discovered_at': self._get_timestamp()
                                }
                                discovered += 1
                                self.logger.info(f"📦 Discovered module: {module_id} ({name})")
                            else:
                                self.logger.warning(f"⚠️  Module {name} missing required interface")
                                
                        except Exception as e:
                            self.logger.error(f"❌ Failed to instantiate {name}: {e}")
                
            except Exception as e:
                self.logger.error(f"❌ Failed to import {py_file}: {e}")
        
        return discovered
    
    def _extract_module_id(self, class_name: str, filename: str) -> str:
        """Extract module ID from class name or filename."""
        # Try to extract from class name (e.g., "FinanceMCP" -> "finance")
        if class_name.endswith('MCP'):
            return class_name[:-3].lower()
        
        # Try to extract from filename (e.g., "finance_mcp" -> "finance")
        if filename.endswith('_mcp'):
            return filename[:-4]
        
        # Fallback to class name
        return class_name.lower()
    
    def _verify_module_interface(self, module: Any) -> bool:
        """Verify module has the required MCP interface."""
        required_methods = ['get_capabilities', 'execute']
        
        for method_name in required_methods:
            if not hasattr(module, method_name):
                return False
            
            method = getattr(module, method_name)
            if not callable(method):
                return False
        
        return True
    
    async def _initialize_modules(self):
        """Initialize all discovered modules."""
        for module_id, module in list(self.modules.items()):
            try:
                success = await module.initialize()
                if success:
                    self.logger.info(f"✅ Initialized module: {module_id}")
                else:
                    self.logger.warning(f"⚠️  Module {module_id} initialization returned False")
                    # Don't remove the module, let it handle the state
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize {module_id}: {e}")
                # Remove failed module from registry
                del self.modules[module_id]
                if module_id in self.module_metadata:
                    del self.module_metadata[module_id]
    
    def get_module(self, module_id: str) -> Optional[ModuleBase]:
        """Get a specific module by ID."""
        return self.modules.get(module_id)
    
    def get_all_modules(self) -> Dict[str, ModuleBase]:
        """Get all registered modules."""
        return self.modules.copy()
    
    def get_module_capabilities(self) -> Dict[str, List[str]]:
        """Get capabilities for all modules."""
        capabilities = {}
        for module_id, module in self.modules.items():
            try:
                capabilities[module_id] = module.get_capabilities()
            except Exception as e:
                self.logger.error(f"Failed to get capabilities for {module_id}: {e}")
                capabilities[module_id] = []
        
        return capabilities
    
    async def execute_action(self, module_id: str, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action on a specific module."""
        module = self.get_module(module_id)
        if not module:
            return {
                "success": False,
                "error": f"Module '{module_id}' not found",
                "available_modules": list(self.modules.keys())
            }
        
        try:
            return await module.execute(action, params)
        except Exception as e:
            self.logger.error(f"Error executing {action} on {module_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "module": module_id,
                "action": action
            }
    
    def get_module_info(self, module_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a module."""
        if module_id not in self.modules:
            return None
        
        module = self.modules[module_id]
        metadata = self.module_metadata.get(module_id, {})
        
        return {
            "module_id": module_id,
            "capabilities": module.get_capabilities(),
            "metadata": metadata,
            "status": "active"
        }
    
    def list_modules(self) -> List[Dict[str, Any]]:
        """List all registered modules with their info."""
        return [
            {
                "module_id": module_id,
                "capabilities": module.get_capabilities(),
                "class_name": self.module_metadata.get(module_id, {}).get('class_name', 'Unknown'),
                "status": "active"
            }
            for module_id, module in self.modules.items()
        ]
    
    async def health_check_all(self) -> Dict[str, Any]:
        """Perform health check on all modules."""
        results = {}
        
        for module_id, module in self.modules.items():
            try:
                if hasattr(module, 'health_check'):
                    results[module_id] = await module.health_check()
                else:
                    results[module_id] = {
                        "module": module_id,
                        "status": "healthy",
                        "note": "No health_check method"
                    }
            except Exception as e:
                results[module_id] = {
                    "module": module_id,
                    "status": "error",
                    "error": str(e)
                }
        
        return results
    
    def add_discovery_path(self, path: Path):
        """Add a new path for module discovery."""
        if path not in self.discovery_paths:
            self.discovery_paths.append(path)
            self.logger.info(f"Added discovery path: {path}")
    
    def _get_timestamp(self) -> str:
        """Get current timestamp as string."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get statistics about the module registry."""
        total_capabilities = sum(len(module.get_capabilities()) for module in self.modules.values())
        
        return {
            "total_modules": len(self.modules),
            "total_capabilities": total_capabilities,
            "discovery_paths": [str(path) for path in self.discovery_paths],
            "modules": list(self.modules.keys())
        }