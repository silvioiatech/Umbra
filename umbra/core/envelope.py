"""
Internal envelope for module communication.
"""
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class InternalEnvelope:
    """Envelope for internal module communication."""
    
    action: str
    data: Dict[str, Any]
    user_id: Optional[int] = None
    module: Optional[str] = None
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        """Set defaults after initialization."""
        if self.timestamp is None:
            from datetime import datetime
            self.timestamp = datetime.now().isoformat()