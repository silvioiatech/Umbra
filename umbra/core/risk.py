"""
Risk Classification System for Umbra Operations

Defines risk levels for all system operations across modules.
"""
from enum import Enum

class RiskLevel(Enum):
    """Risk levels for operations."""
    SAFE = "SAFE"
    SENSITIVE = "SENSITIVE" 
    DESTRUCTIVE = "DESTRUCTIVE"
    CATASTROPHIC = "CATASTROPHIC"
    
    def __str__(self):
        return self.value
    
    @property
    def requires_approval(self) -> bool:
        """Whether this risk level requires approval."""
        return self in [RiskLevel.DESTRUCTIVE, RiskLevel.CATASTROPHIC]
    
    @property
    def requires_admin(self) -> bool:
        """Whether this risk level requires admin privileges."""
        return self in [RiskLevel.CATASTROPHIC]