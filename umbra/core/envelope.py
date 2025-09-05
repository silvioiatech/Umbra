"""
Internal envelope for module communication.
"""

from typing import Any, Dict
from dataclasses import dataclass


@dataclass
class InternalEnvelope:
    """Internal message envelope for module communication."""
    action: str
    data: Dict[str, Any]
    source: str = "unknown"
    target: str = "unknown"