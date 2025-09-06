"""
Validators for Concierge Configuration Management

Provides pluggable validation system for:
- Nginx configuration validation
- Docker Compose syntax checking
- Apache configuration testing
- JSON/YAML syntax validation
- Custom validation rules
"""
import os
import subprocess
import json
import tempfile
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

class ValidatorType(Enum):
    """Types of validators."""
    COMMAND = "command"
    FUNCTION = "function"
    SYNTAX = "syntax"

@dataclass
class ValidationResult:
    """Result of validation operation."""
    validator_name: str
    success: bool
    message: str
    details: Optional[str] = None
    return_code: Optional[int] = None
    execution_time: float = 0.0

@dataclass
class ValidatorRule:
    """Validation rule definition."""
    name: str
    description: str
    validator_type: ValidatorType
    command: Optional[str] = None
    function: Optional[Callable] = None
    file_patterns: Optional[List[str]] = None
    required: bool = True
    timeout: int = 30
    enabled: bool = True

class Validators:
    """Configuration validators with built-in and custom rules."""
    
    def __init__(self, config):
        self.config = config
        self.validators = {}
        self.temp_dir = Path(tempfile.gettempdir()) / 'umbra_validators'
        self.temp_dir.mkdir(exist_ok=True)
        
        # Initialize built-in validators
        self._initialize_builtin_validators()
    
    def _initialize_builtin_validators(self):
        """Initialize built-in validation rules."""
        
        # Nginx validator
        self.register_validator(ValidatorRule(
            name="nginx_config",
            description="Validate Nginx configuration syntax",
            validator_type=ValidatorType.COMMAND,
            command="nginx -t",
            file_patterns=["*.conf", "nginx.conf", "default", "sites-available/*"],
            required=True,
            timeout=10
        ))
        
        # Docker Compose validator
        self.register_validator(ValidatorRule(
            name="docker_compose",
            description="Validate Docker Compose configuration",
            validator_type=ValidatorType.COMMAND,
            command="docker compose config -q",
            file_patterns=["docker-compose.yml", "docker-compose.yaml", "compose.yml"],
            required=True,
            timeout=15
        ))
        
        # Apache validator
        self.register_validator(ValidatorRule(
            name="apache_config",
            description="Validate Apache configuration",
            validator_type=ValidatorType.COMMAND,
            command="apache2ctl configtest",
            file_patterns=["*.conf", "apache2.conf", "httpd.conf"],
            required=False,
            timeout=10
        ))
        
        # Systemd service validator
        self.register_validator(ValidatorRule(
            name="systemd_service",
            description="Validate systemd service files",
            validator_type=ValidatorType.FUNCTION,
            function=self._validate_systemd_service,
            file_patterns=["*.service", "*.timer", "*.socket"],
            required=False,
            timeout=5
        ))
        
        # JSON syntax validator
        self.register_validator(ValidatorRule(
            name="json_syntax",
            description="Validate JSON syntax",
            validator_type=ValidatorType.FUNCTION,
            function=self._validate_json_syntax,
            file_patterns=["*.json"],
            required=True,
            timeout=5
        ))
        
        # YAML syntax validator
        self.register_validator(ValidatorRule(
            name="yaml_syntax",
            description="Validate YAML syntax",
            validator_type=ValidatorType.FUNCTION,
            function=self._validate_yaml_syntax,
            file_patterns=["*.yml", "*.yaml"],
            required=True,
            timeout=5
        ))
        
        # SSH config validator
        self.register_validator(ValidatorRule(
            name="ssh_config",
            description="Validate SSH configuration",
            validator_type=ValidatorType.COMMAND,
            command="sshd -t",
            file_patterns=["sshd_config", "ssh_config"],
            required=False,
            timeout=5
        ))
        
        # Crontab validator
        self.register_validator(ValidatorRule(
            name="crontab",
            description="Validate crontab syntax",
            validator_type=ValidatorType.FUNCTION,
            function=self._validate_crontab,
            file_patterns=["crontab", "*.cron"],
            required=False,
            timeout=5
        ))
    
    def register_validator(self, rule: ValidatorRule):
        """Register a new validator rule."""
        self.validators[rule.name] = rule
    
    def get_applicable_validators(self, file_path: str) -> List[ValidatorRule]:
        """Get validators applicable to a specific file."""
        applicable = []
        filename = os.path.basename(file_path)
        
        for validator in self.validators.values():
            if not validator.enabled:
                continue
            
            if validator.file_patterns:
                for pattern in validator.file_patterns:
                    if self._matches_pattern(filename, pattern) or self._matches_pattern(file_path, pattern):
                        applicable.append(validator)
                        break
        
        return applicable
    
    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Check if filename matches pattern (with simple glob support)."""
        import fnmatch
        
        # Handle directory patterns
        if '/' in pattern:
            return fnmatch.fnmatch(filename, pattern) or filename.endswith(pattern.split('/')[-1])
        
        return fnmatch.fnmatch(filename, pattern)
    
    def validate_file(self, file_path: str, validators: Optional[List[str]] = None) -> List[ValidationResult]:
        """
        Validate a file using applicable validators.
        
        Args:
            file_path: Path to file to validate
            validators: Specific validators to use (None for auto-detect)
        
        Returns:
            List of ValidationResult objects
        """
        if not os.path.exists(file_path):
            return [ValidationResult(
                validator_name="file_existence",
                success=False,
                message=f"File does not exist: {file_path}"
            )]
        
        # Determine validators to use
        if validators:
            validator_rules = [self.validators[name] for name in validators if name in self.validators]
        else:
            validator_rules = self.get_applicable_validators(file_path)
        
        results = []
        
        for rule in validator_rules:
            if not rule.enabled:
                continue
            
            try:
                if rule.validator_type == ValidatorType.COMMAND:
                    result = self._run_command_validator(rule, file_path)
                elif rule.validator_type == ValidatorType.FUNCTION:
                    result = self._run_function_validator(rule, file_path)
                else:
                    result = ValidationResult(
                        validator_name=rule.name,
                        success=False,
                        message=f"Unknown validator type: {rule.validator_type}"
                    )
                
                results.append(result)
                
            except Exception as e:
                results.append(ValidationResult(
                    validator_name=rule.name,
                    success=False,
                    message=f"Validator execution failed: {str(e)}"
                ))
        
        return results
    
    def _run_command_validator(self, rule: ValidatorRule, file_path: str) -> ValidationResult:
        """Run command-based validator."""
        import time
        
        start_time = time.time()
        
        # Prepare command with file path substitution
        command = rule.command
        if "$FILE" in command:
            command = command.replace("$FILE", file_path)
        elif rule.name == "docker_compose":
            # Special handling for docker compose - needs to be run in file directory
            work_dir = os.path.dirname(file_path)
        else:
            # For commands like nginx -t, we may need to temporarily use the file
            work_dir = os.path.dirname(file_path) if os.path.dirname(file_path) else "."
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=rule.timeout,
                cwd=work_dir if 'work_dir' in locals() else None
            )
            
            execution_time = time.time() - start_time
            success = result.returncode == 0
            
            # Combine stdout and stderr for details
            details = ""
            if result.stdout:
                details += f"STDOUT:\n{result.stdout}\n"
            if result.stderr:
                details += f"STDERR:\n{result.stderr}"
            
            message = "Validation passed" if success else "Validation failed"
            if result.stderr and not success:
                # Use first line of stderr as message
                first_error_line = result.stderr.split('\n')[0].strip()
                if first_error_line:
                    message = first_error_line
            
            return ValidationResult(
                validator_name=rule.name,
                success=success,
                message=message,
                details=details.strip() if details.strip() else None,
                return_code=result.returncode,
                execution_time=execution_time
            )
            
        except subprocess.TimeoutExpired:
            return ValidationResult(
                validator_name=rule.name,
                success=False,
                message=f"Validation timed out after {rule.timeout} seconds",
                execution_time=rule.timeout
            )
        except FileNotFoundError:
            return ValidationResult(
                validator_name=rule.name,
                success=False,
                message=f"Validator command not found: {command.split()[0]}"
            )
    
    def _run_function_validator(self, rule: ValidatorRule, file_path: str) -> ValidationResult:
        """Run function-based validator."""
        import time
        
        start_time = time.time()
        
        try:
            result = rule.function(file_path)
            execution_time = time.time() - start_time
            
            # Ensure result is a ValidationResult
            if isinstance(result, ValidationResult):
                result.execution_time = execution_time
                return result
            else:
                # Legacy support for boolean returns
                success = bool(result)
                return ValidationResult(
                    validator_name=rule.name,
                    success=success,
                    message="Validation passed" if success else "Validation failed",
                    execution_time=execution_time
                )
                
        except Exception as e:
            return ValidationResult(
                validator_name=rule.name,
                success=False,
                message=f"Function validator error: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def _validate_json_syntax(self, file_path: str) -> ValidationResult:
        """Validate JSON file syntax."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json.load(f)
            
            return ValidationResult(
                validator_name="json_syntax",
                success=True,
                message="Valid JSON syntax"
            )
            
        except json.JSONDecodeError as e:
            return ValidationResult(
                validator_name="json_syntax",
                success=False,
                message=f"JSON syntax error: {str(e)}",
                details=f"Line {e.lineno}, Column {e.colno}: {e.msg}"
            )
        except Exception as e:
            return ValidationResult(
                validator_name="json_syntax",
                success=False,
                message=f"JSON validation error: {str(e)}"
            )
    
    def _validate_yaml_syntax(self, file_path: str) -> ValidationResult:
        """Validate YAML file syntax."""
        try:
            import yaml
            
            with open(file_path, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)
            
            return ValidationResult(
                validator_name="yaml_syntax",
                success=True,
                message="Valid YAML syntax"
            )
            
        except yaml.YAMLError as e:
            return ValidationResult(
                validator_name="yaml_syntax",
                success=False,
                message=f"YAML syntax error: {str(e)}",
                details=str(e)
            )
        except ImportError:
            return ValidationResult(
                validator_name="yaml_syntax",
                success=False,
                message="YAML library not available (install PyYAML)"
            )
        except Exception as e:
            return ValidationResult(
                validator_name="yaml_syntax",
                success=False,
                message=f"YAML validation error: {str(e)}"
            )
    
    def _validate_systemd_service(self, file_path: str) -> ValidationResult:
        """Validate systemd service file."""
        try:
            import configparser
            
            # Read service file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Basic syntax check using configparser
            config = configparser.ConfigParser()
            config.read_string(content)
            
            # Check for required sections
            required_sections = ["Unit"]
            missing_sections = []
            
            for section in required_sections:
                if section not in config.sections():
                    missing_sections.append(section)
            
            if missing_sections:
                return ValidationResult(
                    validator_name="systemd_service",
                    success=False,
                    message=f"Missing required sections: {', '.join(missing_sections)}"
                )
            
            # Check for common issues
            issues = []
            
            # Check if it's a service file and has Service section
            if file_path.endswith('.service') and 'Service' not in config.sections():
                issues.append("Service files should have a [Service] section")
            
            # Check for ExecStart in Service section
            if 'Service' in config.sections():
                service_section = config['Service']
                if 'ExecStart' not in service_section:
                    issues.append("Service section should have ExecStart")
            
            if issues:
                return ValidationResult(
                    validator_name="systemd_service",
                    success=False,
                    message="Configuration issues found",
                    details="; ".join(issues)
                )
            
            return ValidationResult(
                validator_name="systemd_service",
                success=True,
                message="Valid systemd service file"
            )
            
        except configparser.Error as e:
            return ValidationResult(
                validator_name="systemd_service",
                success=False,
                message=f"Systemd file syntax error: {str(e)}"
            )
        except Exception as e:
            return ValidationResult(
                validator_name="systemd_service",
                success=False,
                message=f"Systemd validation error: {str(e)}"
            )
    
    def _validate_crontab(self, file_path: str) -> ValidationResult:
        """Validate crontab syntax."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            issues = []
            line_number = 0
            
            for line in lines:
                line_number += 1
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Check crontab line format
                parts = line.split()
                if len(parts) < 6:
                    issues.append(f"Line {line_number}: Invalid crontab format (needs at least 6 fields)")
                    continue
                
                # Validate time fields (first 5 parts)
                time_fields = parts[:5]
                field_names = ["minute", "hour", "day", "month", "weekday"]
                field_ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]
                
                for i, (field, field_name, (min_val, max_val)) in enumerate(zip(time_fields, field_names, field_ranges)):
                    if field == '*':
                        continue
                    
                    # Handle ranges and lists
                    if ',' in field:
                        values = field.split(',')
                    elif '-' in field:
                        try:
                            start, end = field.split('-')
                            values = [start, end]
                        except ValueError:
                            issues.append(f"Line {line_number}: Invalid range in {field_name} field")
                            continue
                    elif '/' in field:
                        # Handle step values
                        values = [field.split('/')[0]]
                    else:
                        values = [field]
                    
                    # Validate numeric values
                    for value in values:
                        if value.replace('*', '').replace('/', '').isdigit():
                            num_val = int(value.replace('*', '0').split('/')[0])
                            if not (min_val <= num_val <= max_val):
                                issues.append(f"Line {line_number}: {field_name} value {num_val} out of range ({min_val}-{max_val})")
            
            if issues:
                return ValidationResult(
                    validator_name="crontab",
                    success=False,
                    message="Crontab syntax issues found",
                    details="\n".join(issues)
                )
            
            return ValidationResult(
                validator_name="crontab",
                success=True,
                message="Valid crontab syntax"
            )
            
        except Exception as e:
            return ValidationResult(
                validator_name="crontab",
                success=False,
                message=f"Crontab validation error: {str(e)}"
            )
    
    def validate_content(self, content: str, content_type: str) -> ValidationResult:
        """Validate content string based on type."""
        # Create temporary file for validation
        temp_file = self.temp_dir / f"validate_{int(time.time())}.{content_type}"
        
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Get appropriate validators
            validators = self.get_applicable_validators(str(temp_file))
            
            if not validators:
                return ValidationResult(
                    validator_name="content_validation",
                    success=False,
                    message=f"No validators available for content type: {content_type}"
                )
            
            # Run first applicable validator
            result = self.validate_file(str(temp_file), [validators[0].name])[0]
            
            return result
            
        finally:
            # Cleanup temp file
            if temp_file.exists():
                temp_file.unlink()
    
    def list_validators(self) -> List[Dict[str, Any]]:
        """List all available validators."""
        return [
            {
                "name": rule.name,
                "description": rule.description,
                "type": rule.validator_type.value,
                "file_patterns": rule.file_patterns,
                "required": rule.required,
                "enabled": rule.enabled,
                "timeout": rule.timeout
            }
            for rule in self.validators.values()
        ]
    
    def enable_validator(self, name: str) -> bool:
        """Enable a validator."""
        if name in self.validators:
            self.validators[name].enabled = True
            return True
        return False
    
    def disable_validator(self, name: str) -> bool:
        """Disable a validator."""
        if name in self.validators:
            self.validators[name].enabled = False
            return True
        return False
    
    def cleanup_temp_files(self):
        """Clean up temporary validation files."""
        try:
            import time
            cutoff_time = time.time() - 3600  # 1 hour ago
            
            for temp_file in self.temp_dir.glob("validate_*"):
                if temp_file.stat().st_mtime < cutoff_time:
                    temp_file.unlink()
        except Exception:
            pass  # Ignore cleanup errors

# Export
__all__ = ["ValidatorType", "ValidationResult", "ValidatorRule", "Validators"]
