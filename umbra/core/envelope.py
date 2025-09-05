"""
Internal envelope for module communication.
Provides structured messaging between AI agent and modules.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional
from datetime import datetime


@dataclass
class InternalEnvelope:
    """Internal envelope for structured communication between components."""
    
    action: str
    data: Dict[str, Any]
    user_id: Optional[int] = None
    message_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    context: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.context is None:
            self.context = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert envelope to dictionary."""
        return {
            'action': self.action,
            'data': self.data,
            'user_id': self.user_id,
            'message_id': self.message_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'context': self.context
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InternalEnvelope':
        """Create envelope from dictionary."""
        timestamp = None
        if data.get('timestamp'):
            timestamp = datetime.fromisoformat(data['timestamp'])
        
        return cls(
            action=data['action'],
            data=data['data'],
            user_id=data.get('user_id'),
            message_id=data.get('message_id'),
            timestamp=timestamp,
            context=data.get('context', {})
        )