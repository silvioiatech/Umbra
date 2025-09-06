"""
Shared classes for update management.

This module contains common classes used by both update_watcher and update_clients
to avoid circular imports.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime


class UpdateStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class UpdateRiskLevel(Enum):
    """Risk levels for update operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class UpdatePlan:
    """Plan for system updates."""
    update_id: str
    target_version: str
    current_version: str
    risk_level: UpdateRiskLevel
    requires_restart: bool
    estimated_duration: int  # minutes
    rollback_supported: bool
    description: str
    affected_components: List[str]
    prerequisites: List[str]
    rollback_plan: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'update_id': self.update_id,
            'target_version': self.target_version,
            'current_version': self.current_version,
            'risk_level': self.risk_level.value,
            'requires_restart': self.requires_restart,
            'estimated_duration': self.estimated_duration,
            'rollback_supported': self.rollback_supported,
            'description': self.description,
            'affected_components': self.affected_components,
            'prerequisites': self.prerequisites,
            'rollback_plan': self.rollback_plan,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


@dataclass
class ScanResult:
    """Result of update scanning."""
    available_updates: List[UpdatePlan]
    scan_timestamp: datetime
    scan_duration: float  # seconds
    errors: List[str]
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'available_updates': [update.to_dict() for update in self.available_updates],
            'scan_timestamp': self.scan_timestamp.isoformat(),
            'scan_duration': self.scan_duration,
            'errors': self.errors,
            'warnings': self.warnings
        }