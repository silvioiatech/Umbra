"""
Base module abstraction for Umbra Bot modules.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime

from .envelope import InternalEnvelope
from .logger import get_logger
from .config import get_config


class ModuleBase(ABC):
    """
    Abstract base class for all Umbra Bot modules.
    
    Defines the standard lifecycle and interface that all modules must implement.
    Provides common functionality for handler registration, health checks, and logging.
    """
    
    def __init__(self, name: str):
        """
        Initialize the module.
        
        Args:
            name: Module name (should be unique across the bot)
        """
        self.name = name
        self.config = get_config()
        self.logger = get_logger(f"umbra.modules.{name}")
        self.handlers: Dict[str, Callable] = {}
        self.is_initialized = False
        self.is_healthy = False
        self.initialization_time: Optional[datetime] = None
        self.last_health_check: Optional[datetime] = None
        
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the module.
        
        This method should:
        - Set up any required resources
        - Validate configuration
        - Prepare the module for operation
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def register_handlers(self) -> Dict[str, Callable]:
        """
        Register command handlers for this module.
        
        Returns:
            Dictionary mapping command patterns to handler functions
        """
        pass
    
    @abstractmethod
    async def process_envelope(self, envelope: InternalEnvelope) -> Optional[str]:
        """
        Process an internal envelope.
        
        Args:
            envelope: The envelope to process
            
        Returns:
            Response message, or None if no response needed
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of this module.
        
        Returns:
            Dictionary with health status information
        """
        pass
    
    @abstractmethod
    async def shutdown(self):
        """
        Gracefully shutdown the module.
        
        This method should:
        - Clean up resources
        - Close connections
        - Persist any necessary state
        """
        pass
    
    async def _initialize_wrapper(self) -> bool:
        """
        Wrapper for initialization with error handling and logging.
        
        Returns:
            True if initialization successful
        """
        try:
            self.logger.info("Module initialization starting")
            
            result = await self.initialize()
            
            if result:
                self.is_initialized = True
                self.initialization_time = datetime.utcnow()
                self.logger.info("Module initialization successful")
            else:
                self.logger.error("Module initialization failed")
                
            return result
            
        except Exception as e:
            self.logger.error("Module initialization error", error=str(e))
            return False
    
    async def _register_handlers_wrapper(self) -> Dict[str, Callable]:
        """
        Wrapper for handler registration with error handling and logging.
        
        Returns:
            Dictionary of registered handlers
        """
        try:
            self.logger.info("Registering module handlers")
            
            handlers = await self.register_handlers()
            self.handlers = handlers or {}
            
            self.logger.info("Module handlers registered", 
                           handler_count=len(self.handlers),
                           handlers=list(self.handlers.keys()))
            
            return self.handlers
            
        except Exception as e:
            self.logger.error("Handler registration error", error=str(e))
            return {}
    
    async def _process_envelope_wrapper(self, envelope: InternalEnvelope) -> Optional[str]:
        """
        Wrapper for envelope processing with error handling and logging.
        
        Args:
            envelope: The envelope to process
            
        Returns:
            Response message or None
        """
        try:
            envelope.mark_received(self.name)
            
            self.logger.debug("Processing envelope",
                            req_id=envelope.req_id,
                            action=envelope.action,
                            user_id=envelope.user_id)
            
            result = await self.process_envelope(envelope)
            
            envelope.mark_processed(self.name)
            duration = envelope.get_processing_duration(self.name)
            
            self.logger.debug("Envelope processed",
                            req_id=envelope.req_id,
                            action=envelope.action,
                            duration_ms=duration,
                            has_response=result is not None)
            
            return result
            
        except Exception as e:
            self.logger.error("Envelope processing error",
                            req_id=envelope.req_id,
                            action=envelope.action,
                            error=str(e))
            return None
    
    async def _health_check_wrapper(self) -> Dict[str, Any]:
        """
        Wrapper for health check with error handling and logging.
        
        Returns:
            Health status dictionary
        """
        try:
            health_info = await self.health_check()
            
            # Add standard fields
            health_info.update({
                "module": self.name,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "is_initialized": self.is_initialized,
                "initialization_time": self.initialization_time.isoformat() + "Z" if self.initialization_time else None,
                "uptime_seconds": (datetime.utcnow() - self.initialization_time).total_seconds() if self.initialization_time else None
            })
            
            self.is_healthy = health_info.get("status") == "healthy"
            self.last_health_check = datetime.utcnow()
            
            return health_info
            
        except Exception as e:
            self.logger.error("Health check error", error=str(e))
            self.is_healthy = False
            self.last_health_check = datetime.utcnow()
            
            return {
                "module": self.name,
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
    
    async def _shutdown_wrapper(self):
        """
        Wrapper for shutdown with error handling and logging.
        """
        try:
            self.logger.info("Module shutdown starting")
            
            await self.shutdown()
            
            self.is_initialized = False
            self.is_healthy = False
            
            self.logger.info("Module shutdown completed")
            
        except Exception as e:
            self.logger.error("Module shutdown error", error=str(e))
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current module status.
        
        Returns:
            Dictionary with current module status
        """
        return {
            "name": self.name,
            "is_initialized": self.is_initialized,
            "is_healthy": self.is_healthy,
            "initialization_time": self.initialization_time.isoformat() + "Z" if self.initialization_time else None,
            "last_health_check": self.last_health_check.isoformat() + "Z" if self.last_health_check else None,
            "handler_count": len(self.handlers),
            "handlers": list(self.handlers.keys())
        }
    
    def matches_command(self, command: str) -> Optional[str]:
        """
        Check if this module can handle a command.
        
        Args:
            command: Command to check
            
        Returns:
            Handler key if command matches, None otherwise
        """
        command_lower = command.lower().strip()
        
        for pattern, handler in self.handlers.items():
            # Simple pattern matching - can be enhanced later
            if pattern.lower() in command_lower:
                return pattern
                
        return None
    
    async def handle_command(self, command: str, envelope: InternalEnvelope) -> Optional[str]:
        """
        Handle a command if this module supports it.
        
        Args:
            command: Command to handle
            envelope: Request envelope
            
        Returns:
            Response message or None
        """
        pattern = self.matches_command(command)
        if not pattern:
            return None
            
        handler = self.handlers.get(pattern)
        if not handler:
            return None
            
        try:
            # Call the handler
            if hasattr(handler, '__call__'):
                result = await handler(envelope)
                return result
            else:
                self.logger.warning(f"Handler {pattern} is not callable")
                return None
                
        except Exception as e:
            self.logger.error(f"Command handler error", 
                            command=command,
                            pattern=pattern,
                            error=str(e))
            return f"Error processing command: {str(e)}"