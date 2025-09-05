"""Internal message envelope for module communication."""
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class InternalEnvelope:
    """Internal envelope for passing messages between modules."""
    action: str
    data: Dict[str, Any]
    source_module: Optional[str] = None
    target_module: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}