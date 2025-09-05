"""
Internal message envelope for UMBRA modules.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional
from datetime import datetime


@dataclass
class InternalEnvelope:
    """Internal message envelope for module communication."""
    
    command: str
    data: Dict[str, Any]
    user_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}