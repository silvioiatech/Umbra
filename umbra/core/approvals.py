"""
Approval Flow System for Concierge Operations

Manages approval requests with TTL, double-confirmation for destructive operations,
and secure token-based approval tracking.
"""
import time
import secrets
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from .risk import RiskLevel

class ApprovalStatus(Enum):
    """Status of approval requests."""
    PENDING = "pending"
    APPROVED = "approved" 
    DENIED = "denied"
    EXPIRED = "expired"
    CONSUMED = "consumed"

@dataclass
class ApprovalRequest:
    """Approval request data structure."""
    token: str
    user_id: int
    command: str
    risk_level: RiskLevel
    requires_double_confirm: bool
    created_at: float
    expires_at: float
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_at: Optional[float] = None
    approved_by: Optional[int] = None
    execution_hash: Optional[str] = None
    double_confirm_token: Optional[str] = None
    double_confirm_at: Optional[float] = None

class ApprovalManager:
    """Manages approval flow with SQLite storage and TTL enforcement."""
    
    def __init__(self, db_manager, ttl_minutes: int = 5):
        self.db = db_manager
        self.ttl_seconds = ttl_minutes * 60
        self._init_schema()
    
    def _init_schema(self):
        """Initialize approval storage schema."""
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS approvals (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    command TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    requires_double_confirm BOOLEAN NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    status TEXT NOT NULL,
                    approved_at REAL,
                    approved_by INTEGER,
                    execution_hash TEXT,
                    double_confirm_token TEXT,
                    double_confirm_at REAL,
                    request_data TEXT
                )
            """)
            
            # Create index for efficient lookups
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_approvals_status_expires 
                ON approvals (status, expires_at)
            """)
            
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_approvals_user_status 
                ON approvals (user_id, status)
            """)
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize approval schema: {e}")
    
    def create_approval_request(
        self, 
        user_id: int, 
        command: str, 
        risk_level: RiskLevel,
        requires_double_confirm: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ApprovalRequest:
        """Create new approval request with TTL."""
        
        # Generate secure token
        token = secrets.token_urlsafe(32)
        
        # Set expiry
        now = time.time()
        expires_at = now + self.ttl_seconds
        
        # Create request object
        request = ApprovalRequest(
            token=token,
            user_id=user_id,
            command=command,
            risk_level=risk_level,
            requires_double_confirm=requires_double_confirm,
            created_at=now,
            expires_at=expires_at
        )
        
        # Store in database
        self.db.execute("""
            INSERT INTO approvals (
                token, user_id, command, risk_level, requires_double_confirm,
                created_at, expires_at, status, request_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.token,
            request.user_id,
            request.command,
            request.risk_level.value,
            request.requires_double_confirm,
            request.created_at,
            request.expires_at,
            request.status.value,
            json.dumps(metadata) if metadata else None
        ))
        
        return request
    
    def get_approval_request(self, token: str) -> Optional[ApprovalRequest]:
        """Get approval request by token."""
        row = self.db.query_one(
            "SELECT * FROM approvals WHERE token = ?",
            (token,)
        )
        
        if not row:
            return None
        
        return self._row_to_approval(row)
    
    def approve_request(self, token: str, approver_id: int) -> bool:
        """Approve a request (first step for double-confirm operations)."""
        request = self.get_approval_request(token)
        
        if not request:
            return False
        
        # Check if expired
        if time.time() > request.expires_at:
            self._mark_expired(token)
            return False
        
        # Check if already processed
        if request.status != ApprovalStatus.PENDING:
            return False
        
        now = time.time()
        
        if request.requires_double_confirm:
            # Generate double-confirm token
            double_confirm_token = secrets.token_urlsafe(16)
            
            self.db.execute("""
                UPDATE approvals 
                SET approved_at = ?, approved_by = ?, double_confirm_token = ?
                WHERE token = ?
            """, (now, approver_id, double_confirm_token, token))
            
            return True
        else:
            # Direct approval for non-destructive operations
            self.db.execute("""
                UPDATE approvals 
                SET status = ?, approved_at = ?, approved_by = ?
                WHERE token = ?
            """, (ApprovalStatus.APPROVED.value, now, approver_id, token))
            
            return True
    
    def double_confirm_request(self, token: str, confirm_token: str, confirmer_id: int) -> bool:
        """Complete double-confirmation for destructive operations."""
        request = self.get_approval_request(token)
        
        if not request:
            return False
        
        # Check expiry
        if time.time() > request.expires_at:
            self._mark_expired(token)
            return False
        
        # Check if double-confirm is required and token matches
        if not request.requires_double_confirm or request.double_confirm_token != confirm_token:
            return False
        
        # Check if already double-confirmed
        if request.status == ApprovalStatus.APPROVED:
            return False
        
        now = time.time()
        
        self.db.execute("""
            UPDATE approvals 
            SET status = ?, double_confirm_at = ?
            WHERE token = ?
        """, (ApprovalStatus.APPROVED.value, now, token))
        
        return True
    
    def deny_request(self, token: str, denier_id: int) -> bool:
        """Deny an approval request."""
        request = self.get_approval_request(token)
        
        if not request or request.status != ApprovalStatus.PENDING:
            return False
        
        self.db.execute("""
            UPDATE approvals 
            SET status = ?, approved_by = ?
            WHERE token = ?
        """, (ApprovalStatus.DENIED.value, denier_id, token))
        
        return True
    
    def consume_approval(self, token: str) -> bool:
        """Mark approval as consumed (single-use)."""
        request = self.get_approval_request(token)
        
        if not request or request.status != ApprovalStatus.APPROVED:
            return False
        
        # Check expiry
        if time.time() > request.expires_at:
            self._mark_expired(token)
            return False
        
        # Generate execution hash for audit trail
        execution_hash = hashlib.sha256(
            f"{request.command}:{request.user_id}:{time.time()}".encode()
        ).hexdigest()[:16]
        
        self.db.execute("""
            UPDATE approvals 
            SET status = ?, execution_hash = ?
            WHERE token = ?
        """, (ApprovalStatus.CONSUMED.value, execution_hash, token))
        
        return True
    
    def cleanup_expired(self) -> int:
        """Clean up expired approval requests."""
        now = time.time()
        
        # Mark expired requests
        result = self.db.execute("""
            UPDATE approvals 
            SET status = ?
            WHERE expires_at < ? AND status = ?
        """, (ApprovalStatus.EXPIRED.value, now, ApprovalStatus.PENDING.value))
        
        return result.rowcount if hasattr(result, 'rowcount') else 0
    
    def get_pending_approvals(self, user_id: Optional[int] = None) -> List[ApprovalRequest]:
        """Get pending approval requests for a user or all users."""
        # Clean up expired first
        self.cleanup_expired()
        
        if user_id:
            rows = self.db.query_all("""
                SELECT * FROM approvals 
                WHERE user_id = ? AND status = ?
                ORDER BY created_at DESC
            """, (user_id, ApprovalStatus.PENDING.value))
        else:
            rows = self.db.query_all("""
                SELECT * FROM approvals 
                WHERE status = ?
                ORDER BY created_at DESC
            """, (ApprovalStatus.PENDING.value,))
        
        return [self._row_to_approval(row) for row in rows]
    
    def get_approval_history(self, user_id: Optional[int] = None, limit: int = 50) -> List[ApprovalRequest]:
        """Get approval history."""
        if user_id:
            rows = self.db.query_all("""
                SELECT * FROM approvals 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))
        else:
            rows = self.db.query_all("""
                SELECT * FROM approvals 
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        
        return [self._row_to_approval(row) for row in rows]
    
    def _mark_expired(self, token: str):
        """Mark a specific request as expired."""
        self.db.execute("""
            UPDATE approvals 
            SET status = ?
            WHERE token = ?
        """, (ApprovalStatus.EXPIRED.value, token))
    
    def _row_to_approval(self, row: Dict[str, Any]) -> ApprovalRequest:
        """Convert database row to ApprovalRequest."""
        return ApprovalRequest(
            token=row['token'],
            user_id=row['user_id'],
            command=row['command'],
            risk_level=RiskLevel(row['risk_level']),
            requires_double_confirm=bool(row['requires_double_confirm']),
            created_at=row['created_at'],
            expires_at=row['expires_at'],
            status=ApprovalStatus(row['status']),
            approved_at=row.get('approved_at'),
            approved_by=row.get('approved_by'),
            execution_hash=row.get('execution_hash'),
            double_confirm_token=row.get('double_confirm_token'),
            double_confirm_at=row.get('double_confirm_at')
        )
    
    def get_approval_stats(self) -> Dict[str, Any]:
        """Get approval statistics."""
        stats = {}
        
        # Count by status
        for status in ApprovalStatus:
            count = self.db.query_one("""
                SELECT COUNT(*) as count FROM approvals WHERE status = ?
            """, (status.value,))
            stats[f"{status.value}_count"] = count['count'] if count else 0
        
        # Recent activity
        recent_count = self.db.query_one("""
            SELECT COUNT(*) as count FROM approvals 
            WHERE created_at > ?
        """, (time.time() - 86400,))  # Last 24 hours
        stats['recent_24h'] = recent_count['count'] if recent_count else 0
        
        return stats
    
    def format_approval_request(self, request: ApprovalRequest) -> str:
        """Format approval request for user display."""
        time_left = max(0, request.expires_at - time.time())
        time_left_str = f"{int(time_left // 60)}m {int(time_left % 60)}s"
        
        status_emoji = {
            ApprovalStatus.PENDING: "⏳",
            ApprovalStatus.APPROVED: "✅", 
            ApprovalStatus.DENIED: "❌",
            ApprovalStatus.EXPIRED: "⏰",
            ApprovalStatus.CONSUMED: "✅"
        }
        
        emoji = status_emoji.get(request.status, "❓")
        
        result = f"""{emoji} **Approval Request**

**Command:** `{request.command}`
**Risk Level:** {request.risk_level.value}
**Status:** {request.status.value.title()}
**Token:** `{request.token[:8]}...`
**Time Left:** {time_left_str}"""

        if request.requires_double_confirm:
            result += "\n**⚠️ Requires Double Confirmation**"
            if request.double_confirm_token:
                result += f"\n**Confirm Token:** `{request.double_confirm_token}`"
        
        return result

# Export
__all__ = ["ApprovalStatus", "ApprovalRequest", "ApprovalManager"]
