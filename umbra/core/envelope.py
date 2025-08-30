"""
Internal envelope abstraction for standardized inter-module communication.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class InternalEnvelope(BaseModel):
    """
    Standardized message envelope for inter-module communication within Umbra Bot.
    
    This envelope provides a consistent format for all internal messages, enabling
    request tracing, correlation tracking, and structured data flow between modules.
    """
    
    # Core identification fields
    req_id: str = Field(default_factory=lambda: str(uuid.uuid4()), 
                       description="Unique request identifier")
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()),
                               description="Correlation ID for request tracing across modules")
    
    # User context
    user_id: str = Field(..., description="Telegram user ID who initiated the request")
    
    # Action and data
    action: str = Field(..., description="Action/command being performed")
    data: Dict[str, Any] = Field(default_factory=dict, 
                                description="Payload data for the action")
    
    # Context information
    context: Dict[str, Any] = Field(default_factory=dict,
                                   description="Additional context (language, feature flags, etc.)")
    
    # Timing information
    timestamps: Dict[str, datetime] = Field(default_factory=dict,
                                           description="Timestamps for request lifecycle")
    
    # Module-specific metadata
    metadata: Dict[str, Any] = Field(default_factory=dict,
                                    description="Module-specific metadata")
    
    def __init__(self, **data):
        """Initialize envelope with creation timestamp."""
        super().__init__(**data)
        if "created" not in self.timestamps:
            self.timestamps["created"] = datetime.utcnow()
    
    def mark_received(self, module_name: str):
        """
        Mark envelope as received by a module.
        
        Args:
            module_name: Name of the module that received the envelope
        """
        self.timestamps[f"received_by_{module_name}"] = datetime.utcnow()
    
    def mark_processed(self, module_name: str):
        """
        Mark envelope as processed by a module.
        
        Args:
            module_name: Name of the module that processed the envelope
        """
        self.timestamps[f"processed_by_{module_name}"] = datetime.utcnow()
    
    def add_context(self, key: str, value: Any):
        """
        Add context information to the envelope.
        
        Args:
            key: Context key
            value: Context value
        """
        self.context[key] = value
    
    def add_metadata(self, module_name: str, key: str, value: Any):
        """
        Add module-specific metadata to the envelope.
        
        Args:
            module_name: Name of the module adding metadata
            key: Metadata key
            value: Metadata value
        """
        if module_name not in self.metadata:
            self.metadata[module_name] = {}
        self.metadata[module_name][key] = value
    
    def get_processing_duration(self, module_name: str) -> Optional[float]:
        """
        Get processing duration for a specific module in milliseconds.
        
        Args:
            module_name: Name of the module
            
        Returns:
            Processing duration in milliseconds, or None if not available
        """
        received_key = f"received_by_{module_name}"
        processed_key = f"processed_by_{module_name}"
        
        if received_key in self.timestamps and processed_key in self.timestamps:
            received = self.timestamps[received_key]
            processed = self.timestamps[processed_key]
            duration = (processed - received).total_seconds() * 1000
            return round(duration, 2)
        
        return None
    
    def get_total_duration(self) -> Optional[float]:
        """
        Get total request duration from creation to last processing in milliseconds.
        
        Returns:
            Total duration in milliseconds, or None if not available
        """
        if "created" not in self.timestamps:
            return None
        
        created = self.timestamps["created"]
        
        # Find the latest timestamp
        latest_time = created
        for timestamp in self.timestamps.values():
            if timestamp > latest_time:
                latest_time = timestamp
        
        if latest_time == created:
            return 0.0
        
        duration = (latest_time - created).total_seconds() * 1000
        return round(duration, 2)
    
    def to_log_dict(self) -> Dict[str, Any]:
        """
        Convert envelope to dictionary suitable for logging.
        
        Returns:
            Dictionary with key envelope information for logging
        """
        return {
            "req_id": self.req_id,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "action": self.action,
            "context": self.context,
            "total_duration_ms": self.get_total_duration(),
            "timestamps_count": len(self.timestamps),
            "metadata_modules": list(self.metadata.keys())
        }
    
    def create_response_envelope(self, action: str, data: Dict[str, Any] = None) -> "InternalEnvelope":
        """
        Create a response envelope that maintains correlation with this request.
        
        Args:
            action: Action for the response
            data: Response data
            
        Returns:
            New envelope with shared correlation ID
        """
        return InternalEnvelope(
            correlation_id=self.correlation_id,
            user_id=self.user_id,
            action=action,
            data=data or {},
            context=self.context.copy()
        )
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z"
        }


def create_envelope(user_id: str, action: str, data: Dict[str, Any] = None, 
                   context: Dict[str, Any] = None) -> InternalEnvelope:
    """
    Convenience function to create a new internal envelope.
    
    Args:
        user_id: Telegram user ID
        action: Action being performed
        data: Action data
        context: Additional context
        
    Returns:
        New InternalEnvelope instance
    """
    return InternalEnvelope(
        user_id=user_id,
        action=action,
        data=data or {},
        context=context or {}
    )