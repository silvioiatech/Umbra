"""
Command Execution Operations with Risk Classification

Provides secure command execution with:
- Risk classification and approval flow
- Command validation and sanitization
- Output redaction and truncation
- Execution timeouts and monitoring
- Audit logging for all operations
"""
import subprocess
import time
import os
import shlex
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from .risk import RiskClassifier, RiskLevel
from ...core.approvals import ApprovalManager, ApprovalStatus
from ...core.redact import DataRedactor

@dataclass
class ExecutionResult:
    """Command execution result."""
    command: str
    success: bool
    return_code: int
    stdout: str
    stderr: str
    execution_time: float
    risk_level: RiskLevel
    approval_token: Optional[str] = None
    redacted: bool = False

@dataclass
class ExecutionRequest:
    """Command execution request."""
    command: str
    user_id: int
    cwd: Optional[str] = None
    timeout: int = 30
    env: Optional[Dict[str, str]] = None
    use_sudo: bool = False
    approval_token: Optional[str] = None

class ExecOps:
    """Secure command execution with risk classification and approvals."""
    
    def __init__(self, db_manager, config):
        self.db = db_manager
        self.config = config
        self.risk_classifier = RiskClassifier()
        self.approval_manager = ApprovalManager(db_manager)
        self.redactor = DataRedactor(getattr(config, 'PRIVACY_MODE', 'strict'))
        
        # Configuration
        self.max_output_bytes = getattr(config, 'OUTPUT_MAX_BYTES', 100000)  # 100KB
        self.default_timeout = getattr(config, 'DEFAULT_COMMAND_TIMEOUT', 30)
        self.max_timeout = getattr(config, 'MAX_COMMAND_TIMEOUT', 300)  # 5 minutes
        
        # Initialize audit schema
        self._init_audit_schema()
    
    def _init_audit_schema(self):
        """Initialize command execution audit schema."""
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS command_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    command TEXT NOT NULL,
                    command_hash TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    approval_token TEXT,
                    success BOOLEAN NOT NULL,
                    return_code INTEGER,
                    execution_time REAL,
                    output_size INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    result_hash TEXT
                )
            """)
            
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_command_audit_user_time 
                ON command_audit (user_id, created_at)
            """)
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize audit schema: {e}")
    
    def validate_and_classify_command(self, command: str) -> Tuple[RiskLevel, str, bool]:
        """
        Validate and classify command risk level.
        
        Returns:
            Tuple of (risk_level, reason, is_blocked)
        """
        # Basic validation
        if not command or not command.strip():
            return RiskLevel.SAFE, "Empty command", True
        
        command = command.strip()
        
        # Check for obviously malicious patterns
        dangerous_patterns = [
            '$(', '`', '&&', '||', ';', '|',  # Command injection patterns
            '../', '~/', '/etc/passwd', '/etc/shadow',  # Path traversal
            'curl', 'wget', 'nc', 'netcat',  # Network commands (context dependent)
        ]
        
        # Classify using risk classifier
        risk_level, pattern, is_blocked = self.risk_classifier.classify_command(command)
        
        return risk_level, pattern.description, is_blocked
    
    def execute_command(self, request: ExecutionRequest) -> ExecutionResult:
        """
        Execute command with full risk assessment and approval flow.
        
        Args:
            request: ExecutionRequest object
        
        Returns:
            ExecutionResult object
        """
        start_time = time.time()
        
        # Validate and classify command
        risk_level, risk_reason, is_blocked = self.validate_and_classify_command(request.command)
        
        # Check if command is blocked
        if is_blocked:
            return ExecutionResult(
                command=request.command,
                success=False,
                return_code=-1,
                stdout="",
                stderr=f"Command blocked: {risk_reason}",
                execution_time=time.time() - start_time,
                risk_level=risk_level
            )
        
        # Check approval requirements
        approval_requirements = self.risk_classifier.get_approval_requirements(risk_level, None)
        
        if approval_requirements['requires_approval']:
            # Check if approval token is provided and valid
            if not request.approval_token:
                # Create approval request
                approval_request = self.approval_manager.create_approval_request(
                    user_id=request.user_id,
                    command=request.command,
                    risk_level=risk_level,
                    requires_double_confirm=approval_requirements['requires_double_confirm']
                )
                
                return ExecutionResult(
                    command=request.command,
                    success=False,
                    return_code=-2,
                    stdout="",
                    stderr=f"Approval required. Token: {approval_request.token}",
                    execution_time=time.time() - start_time,
                    risk_level=risk_level,
                    approval_token=approval_request.token
                )
            
            # Validate approval token
            approval_request = self.approval_manager.get_approval_request(request.approval_token)
            if not approval_request:
                return ExecutionResult(
                    command=request.command,
                    success=False,
                    return_code=-3,
                    stdout="",
                    stderr="Invalid approval token",
                    execution_time=time.time() - start_time,
                    risk_level=risk_level
                )
            
            # Check if approval is valid and not expired
            if approval_request.status != ApprovalStatus.APPROVED:
                return ExecutionResult(
                    command=request.command,
                    success=False,
                    return_code=-4,
                    stdout="",
                    stderr=f"Approval not granted (status: {approval_request.status.value})",
                    execution_time=time.time() - start_time,
                    risk_level=risk_level
                )
            
            # Check if command matches approved command
            if approval_request.command != request.command:
                return ExecutionResult(
                    command=request.command,
                    success=False,
                    return_code=-5,
                    stdout="",
                    stderr="Command does not match approved command",
                    execution_time=time.time() - start_time,
                    risk_level=risk_level
                )
            
            # Consume approval (single-use)
            if not self.approval_manager.consume_approval(request.approval_token):
                return ExecutionResult(
                    command=request.command,
                    success=False,
                    return_code=-6,
                    stdout="",
                    stderr="Failed to consume approval token",
                    execution_time=time.time() - start_time,
                    risk_level=risk_level
                )
        
        # Execute the command
        try:
            result = self._execute_command_safely(request)
            
            # Audit logging
            self._audit_command_execution(request, result)
            
            return result
            
        except Exception as e:
            # Audit failed execution
            error_result = ExecutionResult(
                command=request.command,
                success=False,
                return_code=-999,
                stdout="",
                stderr=f"Execution error: {str(e)}",
                execution_time=time.time() - start_time,
                risk_level=risk_level,
                approval_token=request.approval_token
            )
            
            self._audit_command_execution(request, error_result)
            return error_result
    
    def _execute_command_safely(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute command with safety measures."""
        start_time = time.time()
        
        # Prepare command
        command = request.command
        if request.use_sudo:
            command = f"sudo {command}"
        
        # Prepare environment
        env = os.environ.copy()
        if request.env:
            env.update(request.env)
        
        # Set timeout
        timeout = min(request.timeout, self.max_timeout)
        
        try:
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                cwd=request.cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            execution_time = time.time() - start_time
            
            # Get outputs
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            
            # Truncate if too long
            if len(stdout) > self.max_output_bytes:
                stdout = stdout[:self.max_output_bytes] + "\n[OUTPUT TRUNCATED]"
            
            if len(stderr) > self.max_output_bytes:
                stderr = stderr[:self.max_output_bytes] + "\n[ERROR OUTPUT TRUNCATED]"
            
            # Redact sensitive information
            redacted_stdout = self.redactor.redact(stdout)
            redacted_stderr = self.redactor.redact(stderr)
            
            return ExecutionResult(
                command=request.command,
                success=result.returncode == 0,
                return_code=result.returncode,
                stdout=redacted_stdout,
                stderr=redacted_stderr,
                execution_time=execution_time,
                risk_level=self.validate_and_classify_command(request.command)[0],
                approval_token=request.approval_token,
                redacted=redacted_stdout != stdout or redacted_stderr != stderr
            )
            
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                command=request.command,
                success=False,
                return_code=-7,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                execution_time=timeout,
                risk_level=self.validate_and_classify_command(request.command)[0],
                approval_token=request.approval_token
            )
        
        except Exception as e:
            return ExecutionResult(
                command=request.command,
                success=False,
                return_code=-8,
                stdout="",
                stderr=f"Execution failed: {str(e)}",
                execution_time=time.time() - start_time,
                risk_level=self.validate_and_classify_command(request.command)[0],
                approval_token=request.approval_token
            )
    
    def _audit_command_execution(self, request: ExecutionRequest, result: ExecutionResult):
        """Audit command execution for security tracking."""
        try:
            import hashlib
            
            # Create command hash for audit trail
            command_hash = hashlib.sha256(request.command.encode()).hexdigest()[:16]
            
            # Create result hash for integrity
            result_data = f"{result.return_code}:{len(result.stdout)}:{len(result.stderr)}"
            result_hash = hashlib.sha256(result_data.encode()).hexdigest()[:16]
            
            # Store audit record
            self.db.execute("""
                INSERT INTO command_audit (
                    user_id, command, command_hash, risk_level, approval_token,
                    success, return_code, execution_time, output_size, result_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.user_id,
                self.redactor.redact(request.command),  # Redact command in audit
                command_hash,
                result.risk_level.value,
                request.approval_token,
                result.success,
                result.return_code,
                result.execution_time,
                len(result.stdout) + len(result.stderr),
                result_hash
            ))
            
        except Exception as e:
            # Don't fail execution due to audit errors, but log it
            print(f"Audit logging failed: {e}")
    
    def get_safe_macros(self) -> Dict[str, str]:
        """Get predefined safe command macros."""
        return self.risk_classifier.get_safe_macros()
    
    def execute_macro(self, macro_name: str, user_id: int) -> ExecutionResult:
        """Execute a predefined safe macro."""
        macros = self.get_safe_macros()
        
        if macro_name not in macros:
            return ExecutionResult(
                command=macro_name,
                success=False,
                return_code=-10,
                stdout="",
                stderr=f"Unknown macro: {macro_name}",
                execution_time=0,
                risk_level=RiskLevel.SAFE
            )
        
        # Execute macro command
        command = macros[macro_name]
        request = ExecutionRequest(
            command=command,
            user_id=user_id,
            timeout=30
        )
        
        return self.execute_command(request)
    
    def get_execution_history(self, user_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get command execution history."""
        if user_id:
            rows = self.db.query_all("""
                SELECT * FROM command_audit 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))
        else:
            rows = self.db.query_all("""
                SELECT * FROM command_audit 
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        
        return [dict(row) for row in rows]
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get command execution statistics."""
        stats = {}
        
        # Total executions
        total = self.db.query_one("SELECT COUNT(*) as count FROM command_audit")
        stats['total_executions'] = total['count'] if total else 0
        
        # Success rate
        successful = self.db.query_one("SELECT COUNT(*) as count FROM command_audit WHERE success = 1")
        stats['successful_executions'] = successful['count'] if successful else 0
        stats['success_rate'] = (stats['successful_executions'] / stats['total_executions'] * 100) if stats['total_executions'] > 0 else 0
        
        # Risk level distribution
        for risk_level in RiskLevel:
            count = self.db.query_one(
                "SELECT COUNT(*) as count FROM command_audit WHERE risk_level = ?",
                (risk_level.value,)
            )
            stats[f"{risk_level.value.lower()}_count"] = count['count'] if count else 0
        
        # Recent activity (last 24 hours)
        recent = self.db.query_one("""
            SELECT COUNT(*) as count FROM command_audit 
            WHERE created_at > datetime('now', '-24 hours')
        """)
        stats['recent_24h'] = recent['count'] if recent else 0
        
        return stats
    
    def format_execution_result(self, result: ExecutionResult) -> str:
        """Format execution result for display."""
        status_emoji = "✅" if result.success else "❌"
        risk_emoji = {
            RiskLevel.SAFE: "🟢",
            RiskLevel.SENSITIVE: "🟡", 
            RiskLevel.DESTRUCTIVE: "🟠",
            RiskLevel.CATASTROPHIC: "🔴"
        }
        
        emoji = risk_emoji.get(result.risk_level, "❓")
        
        message = f"""{status_emoji} **Command Execution Result**

**Risk Level:** {emoji} {result.risk_level.value}
**Command:** `{result.command}`
**Status:** {'Success' if result.success else 'Failed'}
**Return Code:** {result.return_code}
**Execution Time:** {result.execution_time:.2f}s"""

        if result.redacted:
            message += "\n**⚠️ Output was redacted for security**"
        
        if result.stdout:
            message += f"\n\n**Output:**\n```\n{result.stdout[:1000]}\n```"
        
        if result.stderr:
            message += f"\n\n**Errors:**\n```\n{result.stderr[:500]}\n```"
        
        return message

# Export
__all__ = ["ExecutionResult", "ExecutionRequest", "ExecOps"]
