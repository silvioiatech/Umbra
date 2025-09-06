"""
Internal envelope for module communication.

Provides a standardized way to pass data between modules and the main bot.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional
from datetime import datetime


@dataclass
class InternalEnvelope:
    """Internal envelope for module communication."""
    action: str
    data: Dict[str, Any]
    user_id: str
    timestamp: Optional[datetime] = None
    request_id: Optional[str] = None
    module_name: Optional[str] = None
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'action': self.action,
            'data': self.data,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'request_id': self.request_id,
            'module_name': self.module_name
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InternalEnvelope':
        """Create from dictionary."""
        timestamp = None
        if data.get('timestamp'):
            timestamp = datetime.fromisoformat(data['timestamp'])
        
        return cls(
            action=data['action'],
            data=data['data'],
            user_id=data['user_id'],
            timestamp=timestamp,
            request_id=data.get('request_id'),
            module_name=data.get('module_name')
        )