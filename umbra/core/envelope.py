"""
Internal communication envelope for module interactions.
"""
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class InternalEnvelope:
    """Internal communication envelope for passing data between modules."""
    
    action: str
    data: Dict[str, Any]
    source_module: Optional[str] = None
    target_module: Optional[str] = None
    timestamp: Optional[float] = None
    
    def __post_init__(self):
        """Initialize envelope with timestamp if not provided."""
        if self.timestamp is None:
            import time
            self.timestamp = time.time()