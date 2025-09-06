"""
Redaction System for Sensitive Data

Redacts tokens, passwords, emails, private IPs, and other sensitive information
from command outputs, logs, and audit trails.
"""
import re
from typing import Dict, List, Optional, Tuple, Pattern
from dataclasses import dataclass

@dataclass
class RedactionRule:
    """Rule for redacting sensitive data."""
    name: str
    pattern: Pattern[str]
    replacement: str
    description: str
    enabled: bool = True

class DataRedactor:
    """Redacts sensitive information from text with configurable rules."""
    
    def __init__(self, privacy_mode: str = "strict"):
        self.privacy_mode = privacy_mode
        self.rules = self._initialize_rules()
    
    def _initialize_rules(self) -> List[RedactionRule]:
        """Initialize redaction rules based on privacy mode."""
        
        # Core security rules (always enabled)
        core_rules = [
            # API Keys and Tokens
            RedactionRule(
                name="api_keys",
                pattern=re.compile(r'\b[A-Za-z0-9]{32,}\b'),
                replacement="[REDACTED_API_KEY]",
                description="API keys and long tokens"
            ),
            
            # JWT Tokens
            RedactionRule(
                name="jwt_tokens",
                pattern=re.compile(r'\bey[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\b'),
                replacement="[REDACTED_JWT]",
                description="JWT tokens"
            ),
            
            # Generic passwords in commands
            RedactionRule(
                name="password_flags",
                pattern=re.compile(r'(-p|--password|passwd|password)[\s=]+[^\s]+', re.IGNORECASE),
                replacement=r'\1 [REDACTED_PASSWORD]',
                description="Password flags in commands"
            ),
            
            # SSH private keys
            RedactionRule(
                name="ssh_keys",
                pattern=re.compile(r'-----BEGIN [A-Z\s]+ PRIVATE KEY-----.*?-----END [A-Z\s]+ PRIVATE KEY-----', re.DOTALL),
                replacement="[REDACTED_PRIVATE_KEY]",
                description="SSH private keys"
            ),
            
            # Database connection strings
            RedactionRule(
                name="db_connections",
                pattern=re.compile(r'(mysql|postgresql|mongodb|redis)://[^@]+:[^@]+@[^\s]+', re.IGNORECASE),
                replacement=r'\1://[REDACTED_CREDENTIALS]@[REDACTED_HOST]',
                description="Database connection strings"
            ),
            
            # Environment variables with sensitive data
            RedactionRule(
                name="env_secrets",
                pattern=re.compile(r'(TOKEN|KEY|SECRET|PASSWORD|PASS)=[^\s]+', re.IGNORECASE),
                replacement=r'\1=[REDACTED]',
                description="Environment variables with secrets"
            ),
        ]
        
        # Additional rules for strict mode
        strict_rules = [
            # Email addresses
            RedactionRule(
                name="emails",
                pattern=re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
                replacement="[REDACTED_EMAIL]",
                description="Email addresses"
            ),
            
            # Private IP addresses
            RedactionRule(
                name="private_ips",
                pattern=re.compile(r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b'),
                replacement="[REDACTED_PRIVATE_IP]",
                description="Private IP addresses"
            ),
            
            # Phone numbers (basic patterns)
            RedactionRule(
                name="phone_numbers",
                pattern=re.compile(r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b'),
                replacement="[REDACTED_PHONE]",
                description="Phone numbers"
            ),
            
            # Credit card numbers (basic Luhn check patterns)
            RedactionRule(
                name="credit_cards",
                pattern=re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3[0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b'),
                replacement="[REDACTED_CARD]",
                description="Credit card numbers"
            ),
            
            # URLs with credentials
            RedactionRule(
                name="url_credentials",
                pattern=re.compile(r'(https?://)([^:]+):([^@]+)@([^\s]+)'),
                replacement=r'\1[REDACTED_CREDENTIALS]@\4',
                description="URLs with embedded credentials"
            ),
        ]
        
        # Docker-specific rules
        docker_rules = [
            # Docker registry tokens
            RedactionRule(
                name="docker_tokens",
                pattern=re.compile(r'(docker login.*?-p\s+)[^\s]+', re.IGNORECASE),
                replacement=r'\1[REDACTED_TOKEN]',
                description="Docker registry passwords"
            ),
            
            # Docker environment secrets
            RedactionRule(
                name="docker_env_secrets",
                pattern=re.compile(r'(-e\s+[A-Z_]*(?:TOKEN|KEY|SECRET|PASSWORD|PASS)[A-Z_]*=)[^\s]+', re.IGNORECASE),
                replacement=r'\1[REDACTED]',
                description="Docker environment secrets"
            ),
        ]
        
        # Combine rules based on privacy mode
        rules = core_rules + docker_rules
        
        if self.privacy_mode in ["strict", "paranoid"]:
            rules.extend(strict_rules)
        
        return rules
    
    def redact(self, text: str, additional_patterns: Optional[Dict[str, str]] = None) -> str:
        """
        Redact sensitive information from text.
        
        Args:
            text: Text to redact
            additional_patterns: Additional regex patterns to redact {pattern: replacement}
        
        Returns:
            Redacted text
        """
        if not text:
            return text
        
        redacted = text
        
        # Apply built-in rules
        for rule in self.rules:
            if rule.enabled:
                redacted = rule.pattern.sub(rule.replacement, redacted)
        
        # Apply additional patterns if provided
        if additional_patterns:
            for pattern, replacement in additional_patterns.items():
                try:
                    compiled_pattern = re.compile(pattern)
                    redacted = compiled_pattern.sub(replacement, redacted)
                except re.error:
                    # Skip invalid patterns
                    continue
        
        return redacted
    
    def redact_command_output(self, command: str, output: str) -> Tuple[str, str]:
        """
        Redact both command and its output.
        
        Returns:
            Tuple of (redacted_command, redacted_output)
        """
        return self.redact(command), self.redact(output)
    
    def redact_logs(self, log_entries: List[str]) -> List[str]:
        """Redact a list of log entries."""
        return [self.redact(entry) for entry in log_entries]
    
    def redact_dict(self, data: Dict, keys_to_redact: Optional[List[str]] = None) -> Dict:
        """
        Redact values in a dictionary.
        
        Args:
            data: Dictionary to redact
            keys_to_redact: List of keys whose values should be redacted
        
        Returns:
            Dictionary with redacted values
        """
        if keys_to_redact is None:
            keys_to_redact = [
                'password', 'token', 'key', 'secret', 'auth', 'credential',
                'api_key', 'access_token', 'refresh_token', 'private_key'
            ]
        
        redacted = {}
        
        for key, value in data.items():
            key_lower = key.lower()
            
            if any(sensitive in key_lower for sensitive in keys_to_redact):
                redacted[key] = "[REDACTED]"
            elif isinstance(value, str):
                redacted[key] = self.redact(value)
            elif isinstance(value, dict):
                redacted[key] = self.redact_dict(value, keys_to_redact)
            elif isinstance(value, list):
                redacted[key] = [
                    self.redact(item) if isinstance(item, str) 
                    else self.redact_dict(item, keys_to_redact) if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                redacted[key] = value
        
        return redacted
    
    def get_redaction_summary(self, original: str, redacted: str) -> Dict[str, int]:
        """Get summary of redactions performed."""
        summary = {}
        
        for rule in self.rules:
            if rule.enabled:
                original_matches = len(rule.pattern.findall(original))
                redacted_matches = len(rule.pattern.findall(redacted))
                redacted_count = original_matches - redacted_matches
                
                if redacted_count > 0:
                    summary[rule.name] = redacted_count
        
        return summary
    
    def enable_rule(self, rule_name: str) -> bool:
        """Enable a redaction rule."""
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = True
                return True
        return False
    
    def disable_rule(self, rule_name: str) -> bool:
        """Disable a redaction rule."""
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = False
                return True
        return False
    
    def list_rules(self) -> List[Dict[str, str]]:
        """List all redaction rules."""
        return [
            {
                "name": rule.name,
                "description": rule.description,
                "enabled": rule.enabled,
                "replacement": rule.replacement
            }
            for rule in self.rules
        ]
    
    def add_custom_rule(
        self, 
        name: str, 
        pattern: str, 
        replacement: str, 
        description: str = ""
    ) -> bool:
        """Add a custom redaction rule."""
        try:
            compiled_pattern = re.compile(pattern)
            rule = RedactionRule(
                name=name,
                pattern=compiled_pattern,
                replacement=replacement,
                description=description or f"Custom rule: {name}"
            )
            self.rules.append(rule)
            return True
        except re.error:
            return False

# Convenience function for quick redaction
def quick_redact(text: str, privacy_mode: str = "strict") -> str:
    """Quick redaction function for one-off use."""
    redactor = DataRedactor(privacy_mode)
    return redactor.redact(text)

# Export
__all__ = ["RedactionRule", "DataRedactor", "quick_redact"]
