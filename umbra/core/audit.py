"""Audit logging system for Umbra bot with redaction and durable storage."""
import json
import os
import time
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging
from threading import Lock
import uuid

from .logging_mw import LogRedactor

@dataclass
class AuditEvent:
    """Audit event structure."""
    timestamp: str
    event_id: str
    user_id: int
    module: str
    action: str
    resource: Optional[str] = None
    status: str = "success"  # success, error, denied
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    duration_ms: Optional[float] = None
    
    def __post_init__(self):
        """Post-init processing."""
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat() + 'Z'
        if not self.event_id:
            self.event_id = str(uuid.uuid4())

class AuditLogger:
    """Append-only audit logger with redaction and durable storage."""
    
    def __init__(self, audit_dir: str = "data/audit", enable_console: bool = False):
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        
        self.enable_console = enable_console
        self.logger = logging.getLogger(f"{__name__}.audit")
        self.redactor = LogRedactor()
        self._lock = Lock()
        
        # Current audit file
        self._current_file = None
        self._current_date = None
        
        # Buffer for batching writes (optional optimization)
        self._buffer: List[AuditEvent] = []
        self._buffer_size = 100  # Flush after this many events
        
        self.logger.info(f"Audit logger initialized: {self.audit_dir}")
    
    def log_event(self, 
                  user_id: int,
                  module: str, 
                  action: str,
                  status: str = "success",
                  resource: str = None,
                  details: Dict[str, Any] = None,
                  **context) -> str:
        """Log an audit event."""
        
        event = AuditEvent(
            timestamp=datetime.utcnow().isoformat() + 'Z',
            event_id=str(uuid.uuid4()),
            user_id=user_id,
            module=module,
            action=action,
            status=status,
            resource=resource,
            details=details or {},
            **context
        )
        
        self._write_event(event)
        
        if self.enable_console:
            self.logger.info(
                f"AUDIT: {event.module}/{event.action} by user {event.user_id} - {event.status}",
                extra={'audit_event': asdict(event)}
            )
        
        return event.event_id
    
    def log_access_attempt(self, user_id: int, module: str, action: str, 
                          granted: bool, reason: str = None, **context) -> str:
        """Log an access attempt (permission check)."""
        return self.log_event(
            user_id=user_id,
            module=module,
            action=action,
            status="granted" if granted else "denied",
            details={"reason": reason} if reason else None,
            **context
        )
    
    def log_data_access(self, user_id: int, resource_type: str, resource_id: str,
                       operation: str, status: str = "success", **context) -> str:
        """Log data access events."""
        return self.log_event(
            user_id=user_id,
            module="data",
            action=operation,
            status=status,
            resource=f"{resource_type}:{resource_id}",
            **context
        )
    
    def log_admin_action(self, admin_id: int, action: str, target_user: int = None,
                        details: Dict[str, Any] = None, **context) -> str:
        """Log administrative actions."""
        admin_details = details or {}
        if target_user:
            admin_details["target_user"] = target_user
        
        return self.log_event(
            user_id=admin_id,
            module="admin",
            action=action,
            details=admin_details,
            **context
        )
    
    def log_error(self, user_id: int, module: str, action: str, 
                 error_type: str, error_message: str, **context) -> str:
        """Log error events."""
        return self.log_event(
            user_id=user_id,
            module=module,
            action=action,
            status="error",
            details={
                "error_type": error_type,
                "error_message": error_message
            },
            **context
        )
    
    def _write_event(self, event: AuditEvent):
        """Write event to audit log file."""
        with self._lock:
            # Ensure we have the correct file for today
            self._ensure_current_file()
            
            # Redact sensitive information
            redacted_event = self._redact_event(event)
            
            # Write to file
            audit_line = json.dumps(asdict(redacted_event), default=str) + '\n'
            
            try:
                with open(self._current_file, 'a', encoding='utf-8') as f:
                    f.write(audit_line)
                    f.flush()  # Ensure immediate write
                    os.fsync(f.fileno())  # Ensure OS writes to disk
            except Exception as e:
                self.logger.error(f"Failed to write audit event: {e}")
                # In a production environment, you might want to:
                # 1. Buffer the event for retry
                # 2. Send to a backup location
                # 3. Alert monitoring systems
                raise
    
    def _ensure_current_file(self):
        """Ensure we have the correct audit file for the current date."""
        current_date = datetime.utcnow().strftime('%Y-%m-%d')
        
        if self._current_date != current_date:
            self._current_date = current_date
            self._current_file = self.audit_dir / f"audit-{current_date}.jsonl"
            
            # Create file if it doesn't exist
            if not self._current_file.exists():
                self._current_file.touch()
                self.logger.info(f"Created new audit file: {self._current_file}")
    
    def _redact_event(self, event: AuditEvent) -> AuditEvent:
        """Redact sensitive information from audit event."""
        # Convert to dict for redaction
        event_dict = asdict(event)
        
        # Apply redaction
        redacted_dict = self.redactor.redact_log_entry(event_dict)
        
        # Convert back to AuditEvent
        return AuditEvent(**redacted_dict)
    
    def query_events(self, 
                    start_date: str = None,
                    end_date: str = None,
                    user_id: int = None,
                    module: str = None,
                    action: str = None,
                    status: str = None,
                    limit: int = 100) -> List[Dict[str, Any]]:
        """Query audit events with filters."""
        events = []
        
        # Determine date range
        if not start_date:
            start_date = datetime.utcnow().strftime('%Y-%m-%d')
        if not end_date:
            end_date = start_date
        
        # Read audit files
        current_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current_date <= end_date_obj and len(events) < limit:
            date_str = current_date.strftime('%Y-%m-%d')
            audit_file = self.audit_dir / f"audit-{date_str}.jsonl"
            
            if audit_file.exists():
                try:
                    with open(audit_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            if len(events) >= limit:
                                break
                            
                            try:
                                event = json.loads(line.strip())
                                
                                # Apply filters
                                if user_id and event.get('user_id') != user_id:
                                    continue
                                if module and event.get('module') != module:
                                    continue
                                if action and event.get('action') != action:
                                    continue
                                if status and event.get('status') != status:
                                    continue
                                
                                events.append(event)
                            except json.JSONDecodeError:
                                continue
                                
                except Exception as e:
                    self.logger.error(f"Error reading audit file {audit_file}: {e}")
            
            # Move to next day
            from datetime import timedelta
            current_date += timedelta(days=1)
        
        return events[-limit:] if len(events) > limit else events
    
    def get_user_activity_summary(self, user_id: int, days: int = 7) -> Dict[str, Any]:
        """Get activity summary for a user."""
        from datetime import timedelta
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        events = self.query_events(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            user_id=user_id,
            limit=10000  # High limit for summary
        )
        
        summary = {
            "user_id": user_id,
            "period_days": days,
            "total_events": len(events),
            "modules_used": set(),
            "actions_performed": set(),
            "success_rate": 0.0,
            "most_used_module": None,
            "most_used_action": None,
            "error_count": 0,
            "denied_count": 0
        }
        
        if not events:
            return summary
        
        # Analyze events
        module_counts = {}
        action_counts = {}
        
        for event in events:
            module = event.get('module', 'unknown')
            action = event.get('action', 'unknown')
            status = event.get('status', 'unknown')
            
            summary["modules_used"].add(module)
            summary["actions_performed"].add(action)
            
            module_counts[module] = module_counts.get(module, 0) + 1
            action_counts[action] = action_counts.get(action, 0) + 1
            
            if status == "error":
                summary["error_count"] += 1
            elif status == "denied":
                summary["denied_count"] += 1
        
        # Calculate derived metrics
        success_count = len(events) - summary["error_count"] - summary["denied_count"]
        summary["success_rate"] = success_count / len(events) if events else 0.0
        
        if module_counts:
            summary["most_used_module"] = max(module_counts, key=module_counts.get)
        if action_counts:
            summary["most_used_action"] = max(action_counts, key=action_counts.get)
        
        # Convert sets to lists for JSON serialization
        summary["modules_used"] = list(summary["modules_used"])
        summary["actions_performed"] = list(summary["actions_performed"])
        
        return summary
    
    def cleanup_old_files(self, retention_days: int = 90):
        """Clean up audit files older than retention period."""
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
        
        removed_count = 0
        for audit_file in self.audit_dir.glob("audit-*.jsonl"):
            try:
                # Extract date from filename
                filename = audit_file.name
                date_part = filename.replace('audit-', '').replace('.jsonl', '')
                
                if date_part < cutoff_date_str:
                    audit_file.unlink()
                    removed_count += 1
                    self.logger.info(f"Removed old audit file: {audit_file}")
            except Exception as e:
                self.logger.error(f"Error processing audit file {audit_file}: {e}")
        
        if removed_count > 0:
            self.logger.info(f"Cleaned up {removed_count} old audit files")

# Global audit logger instance
audit_logger = AuditLogger()