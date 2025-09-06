"""
Patching Operations for Concierge

Provides AI-assisted semi-automatic patching with:
- Diff proposal and preview
- Atomic apply with backup
- Validation and rollback capabilities
- AI-powered patch analysis and suggestions
"""
import os
import shutil
import tempfile
import time
import json
import difflib
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

class PatchStatus(Enum):
    """Patch operation status."""
    PROPOSED = "proposed"
    APPROVED = "approved"
    APPLIED = "applied"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

@dataclass
class PatchOperation:
    """Patch operation data structure."""
    patch_id: str
    target_path: str
    description: str
    diff: str
    status: PatchStatus
    created_at: float
    applied_at: Optional[float] = None
    backup_path: Optional[str] = None
    validation_results: Optional[List[Dict[str, Any]]] = None
    rollback_available: bool = False
    ai_confidence: Optional[float] = None
    risk_assessment: Optional[str] = None

@dataclass
class ValidationRule:
    """Validation rule for patches."""
    name: str
    command: str
    description: str
    required: bool = True
    timeout: int = 30

class PatchOps:
    """AI-assisted patching operations with backup and validation."""
    
    def __init__(self, config, db_manager):
        self.config = config
        self.db = db_manager
        
        # Configuration
        self.backup_dir = Path(getattr(config, 'PATCH_BACKUP_DIR', '/tmp/umbra_patches'))
        self.backup_dir.mkdir(exist_ok=True)
        
        self.max_patch_size = getattr(config, 'MAX_PATCH_SIZE', 1024 * 1024)  # 1MB
        self.backup_retention_days = getattr(config, 'BACKUP_RETENTION_DAYS', 30)
        
        # Initialize validators
        self.validators = self._initialize_validators()
        
        # Initialize schema
        self._init_schema()
    
    def _init_schema(self):
        """Initialize patch tracking schema."""
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS patch_operations (
                    patch_id TEXT PRIMARY KEY,
                    target_path TEXT NOT NULL,
                    description TEXT,
                    diff_content TEXT,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    applied_at REAL,
                    backup_path TEXT,
                    validation_results TEXT,
                    rollback_available BOOLEAN,
                    ai_confidence REAL,
                    risk_assessment TEXT,
                    user_id INTEGER
                )
            """)
            
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_patch_status_time 
                ON patch_operations (status, created_at)
            """)
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize patch schema: {e}")
    
    def _initialize_validators(self) -> List[ValidationRule]:
        """Initialize built-in validation rules."""
        return [
            ValidationRule(
                name="nginx_config",
                command="nginx -t",
                description="Validate Nginx configuration",
                required=True
            ),
            ValidationRule(
                name="docker_compose",
                command="docker compose config -q",
                description="Validate Docker Compose configuration",
                required=True
            ),
            ValidationRule(
                name="apache_config",
                command="apache2ctl configtest",
                description="Validate Apache configuration",
                required=False
            ),
            ValidationRule(
                name="systemd_config",
                command="systemd-analyze verify",
                description="Validate systemd unit files",
                required=False
            ),
            ValidationRule(
                name="json_syntax",
                command="python3 -m json.tool",
                description="Validate JSON syntax",
                required=True
            ),
            ValidationRule(
                name="yaml_syntax",
                command="python3 -c 'import yaml; yaml.safe_load(open(\"$FILE\"))'",
                description="Validate YAML syntax",
                required=True
            )
        ]
    
    def _generate_patch_id(self) -> str:
        """Generate unique patch ID."""
        import hashlib
        return hashlib.sha256(f"{time.time()}:{os.urandom(16).hex()}".encode()).hexdigest()[:16]
    
    async def propose_patch(
        self, 
        target_path: str, 
        context: str,
        user_id: int,
        ai_agent = None
    ) -> Tuple[bool, PatchOperation, str]:
        """
        Propose a patch using AI assistance.
        
        Args:
            target_path: Path to file to patch
            context: Context/description of what needs to be changed
            user_id: User requesting the patch
            ai_agent: AI agent for generating patches
        
        Returns:
            Tuple of (success, patch_operation, error_message)
        """
        try:
            # Validate target file
            if not os.path.exists(target_path):
                return False, None, f"Target file does not exist: {target_path}"
            
            if not os.access(target_path, os.R_OK):
                return False, None, f"Cannot read target file: {target_path}"
            
            # Read current file content
            with open(target_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
            
            if len(current_content) > self.max_patch_size:
                return False, None, f"File too large for patching: {len(current_content)} bytes"
            
            # Generate patch using AI if available
            if ai_agent:
                try:
                    ai_response = await self._generate_ai_patch(
                        current_content, context, target_path, ai_agent
                    )
                    
                    if ai_response['success']:
                        proposed_content = ai_response['content']
                        ai_confidence = ai_response.get('confidence', 0.5)
                        risk_assessment = ai_response.get('risk_assessment', 'unknown')
                    else:
                        return False, None, f"AI patch generation failed: {ai_response.get('error', 'Unknown error')}"
                        
                except Exception as e:
                    return False, None, f"AI patch generation error: {str(e)}"
            else:
                # Manual patch proposal (user provides the changes)
                proposed_content = current_content + f"\n# Manual patch context: {context}\n"
                ai_confidence = None
                risk_assessment = "manual"
            
            # Generate diff
            diff = self._generate_unified_diff(
                current_content, 
                proposed_content, 
                target_path
            )
            
            if not diff.strip():
                return False, None, "No changes detected in proposed patch"
            
            # Create patch operation
            patch_id = self._generate_patch_id()
            
            patch_op = PatchOperation(
                patch_id=patch_id,
                target_path=target_path,
                description=context,
                diff=diff,
                status=PatchStatus.PROPOSED,
                created_at=time.time(),
                ai_confidence=ai_confidence,
                risk_assessment=risk_assessment
            )
            
            # Store in database
            self._store_patch_operation(patch_op, user_id)
            
            return True, patch_op, ""
            
        except Exception as e:
            return False, None, f"Patch proposal failed: {str(e)}"
    
    async def _generate_ai_patch(
        self, 
        current_content: str, 
        context: str, 
        file_path: str,
        ai_agent
    ) -> Dict[str, Any]:
        """Generate patch using AI assistance."""
        
        # Prepare prompt for AI
        prompt = f"""You are a system administrator assistant. Generate a precise patch for the following file.

**File Path:** {file_path}
**Task:** {context}

**Current File Content:**
```
{current_content[:2000]}{'...' if len(current_content) > 2000 else ''}
```

**Instructions:**
1. Analyze the current file content
2. Apply the requested changes precisely
3. Ensure the changes are minimal and safe
4. Maintain proper formatting and syntax
5. Return ONLY the complete modified file content
6. Do NOT include explanations or markdown formatting

**Requirements:**
- Preserve all existing functionality
- Make minimal necessary changes
- Follow best practices for the file type
- Ensure syntax is valid

**Modified File Content:**"""

        try:
            # Generate response using AI agent
            response = await ai_agent.generate_response(
                message=prompt,
                user_id=0,  # System user
                temperature=0.3,  # Low temperature for precision
                max_tokens=4000
            )
            
            if response.success:
                # Basic validation of AI response
                proposed_content = response.content.strip()
                
                # Remove any markdown code blocks if present
                if proposed_content.startswith('```'):
                    lines = proposed_content.split('\n')
                    if lines[0].startswith('```'):
                        lines = lines[1:]
                    if lines[-1].startswith('```'):
                        lines = lines[:-1]
                    proposed_content = '\n'.join(lines)
                
                # Assess risk based on changes
                risk_level = self._assess_patch_risk(current_content, proposed_content)
                
                return {
                    'success': True,
                    'content': proposed_content,
                    'confidence': 0.8,  # AI confidence score
                    'risk_assessment': risk_level
                }
            else:
                return {
                    'success': False,
                    'error': response.error or 'AI generation failed'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"AI patch generation error: {str(e)}"
            }
    
    def _assess_patch_risk(self, original: str, modified: str) -> str:
        """Assess risk level of proposed patch."""
        # Calculate change percentage
        original_lines = original.split('\n')
        modified_lines = modified.split('\n')
        
        diff_lines = list(difflib.unified_diff(original_lines, modified_lines, n=0))
        changed_lines = len([line for line in diff_lines if line.startswith(('+', '-'))])
        
        change_percentage = (changed_lines / max(len(original_lines), 1)) * 100
        
        # Risk assessment
        if change_percentage > 50:
            return "high"
        elif change_percentage > 20:
            return "medium"
        elif change_percentage > 5:
            return "low"
        else:
            return "minimal"
    
    def _generate_unified_diff(self, original: str, modified: str, filename: str) -> str:
        """Generate unified diff between original and modified content."""
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"{filename}.original",
            tofile=f"{filename}.modified",
            n=3
        )
        
        return ''.join(diff)
    
    def patch_preview(self, patch_id: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        Preview a proposed patch.
        
        Args:
            patch_id: Patch operation ID
        
        Returns:
            Tuple of (success, preview_info, error_message)
        """
        try:
            patch_op = self._get_patch_operation(patch_id)
            if not patch_op:
                return False, {}, f"Patch not found: {patch_id}"
            
            # Analyze diff
            diff_lines = patch_op.diff.split('\n')
            additions = len([line for line in diff_lines if line.startswith('+')])
            deletions = len([line for line in diff_lines if line.startswith('-')])
            
            # Get file info
            file_info = {}
            if os.path.exists(patch_op.target_path):
                stat = os.stat(patch_op.target_path)
                file_info = {
                    'size': stat.st_size,
                    'modified': stat.st_mtime,
                    'permissions': oct(stat.st_mode)[-3:]
                }
            
            preview = {
                'patch_id': patch_id,
                'target_path': patch_op.target_path,
                'description': patch_op.description,
                'status': patch_op.status.value,
                'diff': patch_op.diff,
                'stats': {
                    'additions': additions,
                    'deletions': deletions,
                    'total_changes': additions + deletions
                },
                'file_info': file_info,
                'ai_confidence': patch_op.ai_confidence,
                'risk_assessment': patch_op.risk_assessment,
                'created_at': patch_op.created_at
            }
            
            return True, preview, ""
            
        except Exception as e:
            return False, {}, f"Preview failed: {str(e)}"
    
    def patch_apply(
        self, 
        patch_id: str, 
        atomic: bool = True, 
        backup: bool = True,
        validate: bool = True
    ) -> Tuple[bool, PatchOperation, str]:
        """
        Apply a patch with backup and validation.
        
        Args:
            patch_id: Patch operation ID
            atomic: Use atomic operations (temp→move)
            backup: Create backup before applying
            validate: Run validators after applying
        
        Returns:
            Tuple of (success, updated_patch_operation, error_message)
        """
        try:
            patch_op = self._get_patch_operation(patch_id)
            if not patch_op:
                return False, None, f"Patch not found: {patch_id}"
            
            if patch_op.status != PatchStatus.PROPOSED:
                return False, patch_op, f"Patch not in proposed state: {patch_op.status.value}"
            
            target_path = patch_op.target_path
            
            # Verify target file still exists and is readable
            if not os.path.exists(target_path):
                return False, patch_op, f"Target file no longer exists: {target_path}"
            
            # Create backup if requested
            backup_path = None
            if backup:
                backup_path = self._create_backup(target_path, patch_id)
                if not backup_path:
                    return False, patch_op, "Failed to create backup"
            
            # Read current content
            with open(target_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
            
            # Apply diff to generate new content
            try:
                new_content = self._apply_diff_to_content(current_content, patch_op.diff)
            except Exception as e:
                return False, patch_op, f"Failed to apply diff: {str(e)}"
            
            # Write new content (atomic or direct)
            if atomic:
                success = self._atomic_write(target_path, new_content)
                if not success:
                    return False, patch_op, "Atomic write failed"
            else:
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
            
            # Update patch operation
            patch_op.status = PatchStatus.APPLIED
            patch_op.applied_at = time.time()
            patch_op.backup_path = backup_path
            patch_op.rollback_available = backup_path is not None
            
            # Run validation if requested
            if validate:
                validation_results = self._run_validators(target_path)
                patch_op.validation_results = validation_results
                
                # Check if any required validators failed
                failed_required = any(
                    not result['success'] and result['required']
                    for result in validation_results
                )
                
                if failed_required:
                    # Rollback if validation failed
                    if backup_path:
                        rollback_success, rollback_error = self.patch_rollback(patch_id)
                        if rollback_success:
                            return False, patch_op, f"Validation failed, rolled back: {rollback_error}"
                        else:
                            return False, patch_op, f"Validation failed and rollback failed: {rollback_error}"
                    else:
                        patch_op.status = PatchStatus.FAILED
                        return False, patch_op, "Validation failed and no backup available"
            
            # Update database
            self._update_patch_operation(patch_op)
            
            return True, patch_op, ""
            
        except Exception as e:
            return False, patch_op if 'patch_op' in locals() else None, f"Patch apply failed: {str(e)}"
    
    def patch_rollback(self, patch_id: str) -> Tuple[bool, str]:
        """
        Rollback a patch to previous state.
        
        Args:
            patch_id: Patch operation ID
        
        Returns:
            Tuple of (success, error_message)
        """
        try:
            patch_op = self._get_patch_operation(patch_id)
            if not patch_op:
                return False, f"Patch not found: {patch_id}"
            
            if not patch_op.rollback_available or not patch_op.backup_path:
                return False, "No backup available for rollback"
            
            if not os.path.exists(patch_op.backup_path):
                return False, f"Backup file not found: {patch_op.backup_path}"
            
            # Restore from backup
            shutil.copy2(patch_op.backup_path, patch_op.target_path)
            
            # Update status
            patch_op.status = PatchStatus.ROLLED_BACK
            self._update_patch_operation(patch_op)
            
            return True, ""
            
        except Exception as e:
            return False, f"Rollback failed: {str(e)}"
    
    def _create_backup(self, file_path: str, patch_id: str) -> Optional[str]:
        """Create backup of file before patching."""
        try:
            backup_name = f"{os.path.basename(file_path)}.{patch_id}.backup"
            backup_path = self.backup_dir / backup_name
            
            shutil.copy2(file_path, backup_path)
            return str(backup_path)
            
        except Exception:
            return None
    
    def _atomic_write(self, target_path: str, content: str) -> bool:
        """Write file atomically using temp→fsync→move."""
        try:
            temp_path = f"{target_path}.tmp.{int(time.time())}"
            
            # Write to temporary file
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic move
            shutil.move(temp_path, target_path)
            return True
            
        except Exception:
            # Cleanup temp file if it exists
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)
            return False
    
    def _apply_diff_to_content(self, original_content: str, diff: str) -> str:
        """Apply unified diff to content."""
        # This is a simplified diff application
        # In production, you might want to use a more robust library
        
        original_lines = original_content.splitlines()
        diff_lines = diff.split('\n')
        
        result_lines = original_lines.copy()
        line_offset = 0
        
        i = 0
        while i < len(diff_lines):
            line = diff_lines[i]
            
            if line.startswith('@@'):
                # Parse hunk header: @@ -start,count +start,count @@
                parts = line.split()
                if len(parts) >= 3:
                    old_info = parts[1][1:]  # Remove '-'
                    new_info = parts[2][1:]  # Remove '+'
                    
                    old_start = int(old_info.split(',')[0]) - 1  # Convert to 0-based
                    
                    # Process hunk
                    i += 1
                    hunk_old_lines = []
                    hunk_new_lines = []
                    
                    while i < len(diff_lines) and not diff_lines[i].startswith('@@'):
                        hunk_line = diff_lines[i]
                        if hunk_line.startswith('-'):
                            hunk_old_lines.append(hunk_line[1:])
                        elif hunk_line.startswith('+'):
                            hunk_new_lines.append(hunk_line[1:])
                        elif hunk_line.startswith(' '):
                            # Context line (unchanged)
                            hunk_old_lines.append(hunk_line[1:])
                            hunk_new_lines.append(hunk_line[1:])
                        i += 1
                    
                    # Apply hunk
                    start_idx = old_start + line_offset
                    end_idx = start_idx + len(hunk_old_lines)
                    
                    # Replace old lines with new lines
                    result_lines[start_idx:end_idx] = hunk_new_lines
                    line_offset += len(hunk_new_lines) - len(hunk_old_lines)
                    
                    continue
            
            i += 1
        
        return '\n'.join(result_lines)
    
    def _run_validators(self, file_path: str) -> List[Dict[str, Any]]:
        """Run validation rules on file."""
        results = []
        
        for validator in self.validators:
            # Skip validators that don't apply to this file type
            if not self._validator_applies_to_file(validator, file_path):
                continue
            
            result = {
                'name': validator.name,
                'description': validator.description,
                'required': validator.required,
                'success': False,
                'output': '',
                'error': ''
            }
            
            try:
                # Prepare command with file substitution
                command = validator.command.replace('$FILE', file_path)
                
                # Run validator
                proc_result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=validator.timeout,
                    cwd=os.path.dirname(file_path)
                )
                
                result['success'] = proc_result.returncode == 0
                result['output'] = proc_result.stdout
                result['error'] = proc_result.stderr
                
            except subprocess.TimeoutExpired:
                result['error'] = f"Validator timed out after {validator.timeout}s"
            except Exception as e:
                result['error'] = str(e)
            
            results.append(result)
        
        return results
    
    def _validator_applies_to_file(self, validator: ValidationRule, file_path: str) -> bool:
        """Check if validator applies to file type."""
        file_ext = os.path.splitext(file_path)[1].lower()
        file_name = os.path.basename(file_path).lower()
        
        # Define mappings
        mappings = {
            'nginx_config': ['.conf', 'nginx.conf', 'default'],
            'docker_compose': ['docker-compose.yml', 'docker-compose.yaml', 'compose.yml'],
            'apache_config': ['.conf', 'httpd.conf', 'apache2.conf'],
            'json_syntax': ['.json'],
            'yaml_syntax': ['.yml', '.yaml']
        }
        
        applicable_patterns = mappings.get(validator.name, [])
        
        return any(
            pattern in file_name or file_ext == pattern
            for pattern in applicable_patterns
        )
    
    def _store_patch_operation(self, patch_op: PatchOperation, user_id: int):
        """Store patch operation in database."""
        self.db.execute("""
            INSERT INTO patch_operations (
                patch_id, target_path, description, diff_content, status,
                created_at, applied_at, backup_path, validation_results,
                rollback_available, ai_confidence, risk_assessment, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            patch_op.patch_id,
            patch_op.target_path,
            patch_op.description,
            patch_op.diff,
            patch_op.status.value,
            patch_op.created_at,
            patch_op.applied_at,
            patch_op.backup_path,
            json.dumps(patch_op.validation_results) if patch_op.validation_results else None,
            patch_op.rollback_available,
            patch_op.ai_confidence,
            patch_op.risk_assessment,
            user_id
        ))
    
    def _get_patch_operation(self, patch_id: str) -> Optional[PatchOperation]:
        """Get patch operation from database."""
        row = self.db.query_one(
            "SELECT * FROM patch_operations WHERE patch_id = ?",
            (patch_id,)
        )
        
        if not row:
            return None
        
        return PatchOperation(
            patch_id=row['patch_id'],
            target_path=row['target_path'],
            description=row['description'],
            diff=row['diff_content'],
            status=PatchStatus(row['status']),
            created_at=row['created_at'],
            applied_at=row['applied_at'],
            backup_path=row['backup_path'],
            validation_results=json.loads(row['validation_results']) if row['validation_results'] else None,
            rollback_available=bool(row['rollback_available']),
            ai_confidence=row['ai_confidence'],
            risk_assessment=row['risk_assessment']
        )
    
    def _update_patch_operation(self, patch_op: PatchOperation):
        """Update patch operation in database."""
        self.db.execute("""
            UPDATE patch_operations SET
                status = ?, applied_at = ?, backup_path = ?,
                validation_results = ?, rollback_available = ?
            WHERE patch_id = ?
        """, (
            patch_op.status.value,
            patch_op.applied_at,
            patch_op.backup_path,
            json.dumps(patch_op.validation_results) if patch_op.validation_results else None,
            patch_op.rollback_available,
            patch_op.patch_id
        ))
    
    def list_patches(self, status: Optional[PatchStatus] = None) -> List[PatchOperation]:
        """List patch operations."""
        if status:
            rows = self.db.query_all(
                "SELECT * FROM patch_operations WHERE status = ? ORDER BY created_at DESC",
                (status.value,)
            )
        else:
            rows = self.db.query_all(
                "SELECT * FROM patch_operations ORDER BY created_at DESC"
            )
        
        patches = []
        for row in rows:
            patch_op = PatchOperation(
                patch_id=row['patch_id'],
                target_path=row['target_path'],
                description=row['description'],
                diff=row['diff_content'],
                status=PatchStatus(row['status']),
                created_at=row['created_at'],
                applied_at=row['applied_at'],
                backup_path=row['backup_path'],
                validation_results=json.loads(row['validation_results']) if row['validation_results'] else None,
                rollback_available=bool(row['rollback_available']),
                ai_confidence=row['ai_confidence'],
                risk_assessment=row['risk_assessment']
            )
            patches.append(patch_op)
        
        return patches
    
    def cleanup_old_backups(self):
        """Clean up old backup files."""
        cutoff_time = time.time() - (self.backup_retention_days * 24 * 3600)
        
        for backup_file in self.backup_dir.glob("*.backup"):
            try:
                if backup_file.stat().st_mtime < cutoff_time:
                    backup_file.unlink()
            except Exception:
                continue

# Export
__all__ = ["PatchStatus", "PatchOperation", "ValidationRule", "PatchOps"]
