"""
Production Redactor for Production Module

Handles PII redaction and sensitive data masking for logs, payloads,
and workflow outputs to ensure privacy compliance.
"""

import re
import json
import logging
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
import hashlib

from ...core.config import UmbraConfig

logger = logging.getLogger(__name__)

@dataclass
class RedactionRule:
    """Represents a redaction rule"""
    name: str
    pattern: re.Pattern
    replacement: str
    confidence: float  # 0.0 to 1.0
    category: str  # "pii", "credential", "internal", "custom"

@dataclass
class RedactionResult:
    """Result of redaction operation"""
    original_size: int
    redacted_size: int
    redactions_count: int
    rules_triggered: List[str]
    confidence_score: float

class ProductionRedactor:
    """Redacts sensitive information from production data"""
    
    def __init__(self, config: UmbraConfig):
        self.config = config
        
        # Redaction settings
        self.redaction_enabled = config.get("PRIVACY_MODE", "standard") != "none"
        self.redaction_mode = config.get("PRIVACY_MODE", "standard")  # none, basic, standard, strict
        self.mask_char = config.get("PROD_MASK_CHAR", "*")
        self.preserve_length = config.get("PROD_PRESERVE_LENGTH", True)
        
        # Initialize redaction rules
        self.rules = self._initialize_redaction_rules()
        
        logger.info(f"Production redactor initialized with mode: {self.redaction_mode}")
    
    def _initialize_redaction_rules(self) -> List[RedactionRule]:
        """Initialize redaction rules based on mode"""
        rules = []
        
        if self.redaction_mode == "none":
            return rules
        
        # Basic rules (apply to all modes except 'none')
        basic_rules = [
            # Credit card numbers
            RedactionRule(
                name="credit_card",
                pattern=re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
                replacement="[CARD]",
                confidence=0.9,
                category="pii"
            ),
            
            # Social security numbers (US format)
            RedactionRule(
                name="ssn",
                pattern=re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b'),
                replacement="[SSN]",
                confidence=0.8,
                category="pii"
            ),
            
            # API keys and tokens (common patterns)
            RedactionRule(
                name="api_key",
                pattern=re.compile(r'\b[A-Za-z0-9]{32,}\b'),
                replacement="[API_KEY]",
                confidence=0.7,
                category="credential"
            ),
            
            # JWT tokens
            RedactionRule(
                name="jwt_token",
                pattern=re.compile(r'\beyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*\b'),
                replacement="[JWT]",
                confidence=0.9,
                category="credential"
            ),
        ]
        
        rules.extend(basic_rules)
        
        if self.redaction_mode in ["standard", "strict"]:
            # Standard rules
            standard_rules = [
                # Email addresses
                RedactionRule(
                    name="email",
                    pattern=re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
                    replacement="[EMAIL]",
                    confidence=0.95,
                    category="pii"
                ),
                
                # Phone numbers (international format)
                RedactionRule(
                    name="phone",
                    pattern=re.compile(r'\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'),
                    replacement="[PHONE]",
                    confidence=0.8,
                    category="pii"
                ),
                
                # IP addresses
                RedactionRule(
                    name="ip_address",
                    pattern=re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'),
                    replacement="[IP]",
                    confidence=0.7,
                    category="internal"
                ),
                
                # URLs with credentials
                RedactionRule(
                    name="url_with_creds",
                    pattern=re.compile(r'https?://[^:\s]+:[^@\s]+@[^\s]+'),
                    replacement="[URL_WITH_CREDS]",
                    confidence=0.9,
                    category="credential"
                ),
            ]
            
            rules.extend(standard_rules)
        
        if self.redaction_mode == "strict":
            # Strict rules
            strict_rules = [
                # Names (simple heuristic - capitalized words that might be names)
                RedactionRule(
                    name="potential_name",
                    pattern=re.compile(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'),
                    replacement="[NAME]",
                    confidence=0.6,
                    category="pii"
                ),
                
                # Addresses (simple pattern)
                RedactionRule(
                    name="address",
                    pattern=re.compile(r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln)\b', re.IGNORECASE),
                    replacement="[ADDRESS]",
                    confidence=0.7,
                    category="pii"
                ),
                
                # Database connection strings
                RedactionRule(
                    name="db_connection",
                    pattern=re.compile(r'(?:mongodb|mysql|postgresql|redis)://[^\s]+'),
                    replacement="[DB_CONNECTION]",
                    confidence=0.9,
                    category="credential"
                ),
            ]
            
            rules.extend(strict_rules)
        
        return rules
    
    def redact_text(self, text: str) -> Tuple[str, RedactionResult]:
        """Redact sensitive information from text"""
        if not self.redaction_enabled or not text:
            return text, RedactionResult(
                original_size=len(text) if text else 0,
                redacted_size=len(text) if text else 0,
                redactions_count=0,
                rules_triggered=[],
                confidence_score=0.0
            )
        
        redacted_text = text
        redactions_count = 0
        rules_triggered = []
        confidence_scores = []
        
        # Apply each redaction rule
        for rule in self.rules:
            matches = rule.pattern.findall(redacted_text)
            if matches:
                if self.preserve_length:
                    # Replace with masked version of same length
                    def mask_replacement(match):
                        original = match.group(0)
                        if len(original) <= 6:
                            return self.mask_char * len(original)
                        else:
                            # Keep first and last character, mask middle
                            return original[0] + self.mask_char * (len(original) - 2) + original[-1]
                    
                    redacted_text = rule.pattern.sub(mask_replacement, redacted_text)
                else:
                    redacted_text = rule.pattern.sub(rule.replacement, redacted_text)
                
                redactions_count += len(matches)
                rules_triggered.append(rule.name)
                confidence_scores.append(rule.confidence)
        
        # Calculate overall confidence
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        result = RedactionResult(
            original_size=len(text),
            redacted_size=len(redacted_text),
            redactions_count=redactions_count,
            rules_triggered=rules_triggered,
            confidence_score=avg_confidence
        )
        
        return redacted_text, result
    
    def redact_dict(self, data: Dict[str, Any], sensitive_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """Redact sensitive information from dictionary"""
        if not self.redaction_enabled:
            return data
        
        # Default sensitive keys
        if sensitive_keys is None:
            sensitive_keys = [
                "password", "token", "key", "secret", "credential",
                "auth", "authorization", "api_key", "private_key",
                "access_token", "refresh_token", "session_id"
            ]
        
        redacted = {}
        
        for key, value in data.items():
            key_lower = key.lower()
            
            # Check if key is sensitive
            is_sensitive_key = any(sens_key in key_lower for sens_key in sensitive_keys)
            
            if is_sensitive_key:
                # Mask the entire value
                if isinstance(value, str) and value:
                    redacted[key] = self._mask_value(value)
                else:
                    redacted[key] = "[REDACTED]"
            elif isinstance(value, str):
                # Apply text redaction to string values
                redacted_text, _ = self.redact_text(value)
                redacted[key] = redacted_text
            elif isinstance(value, dict):
                # Recursively redact nested dictionaries
                redacted[key] = self.redact_dict(value, sensitive_keys)
            elif isinstance(value, list):
                # Process lists
                redacted[key] = [
                    self.redact_dict(item, sensitive_keys) if isinstance(item, dict)
                    else self.redact_text(item)[0] if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                redacted[key] = value
        
        return redacted
    
    def _mask_value(self, value: str) -> str:
        """Mask a sensitive value"""
        if len(value) <= 4:
            return self.mask_char * len(value)
        elif len(value) <= 8:
            return value[:1] + self.mask_char * (len(value) - 2) + value[-1:]
        else:
            return value[:2] + self.mask_char * (len(value) - 4) + value[-2:]
    
    def redact_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive information from workflow definition"""
        if not self.redaction_enabled:
            return workflow
        
        redacted_workflow = workflow.copy()
        
        # Redact node parameters
        nodes = redacted_workflow.get("nodes", [])
        for node in nodes:
            if "parameters" in node:
                node["parameters"] = self.redact_dict(node["parameters"])
            
            # Redact credential information
            if "credentials" in node:
                credentials = node["credentials"]
                for cred_type, cred_info in credentials.items():
                    if isinstance(cred_info, dict):
                        # Keep name but remove sensitive details
                        redacted_cred = {"name": cred_info.get("name", "[REDACTED]")}
                        if "id" in cred_info:
                            redacted_cred["id"] = self._hash_value(cred_info["id"])
                        node["credentials"][cred_type] = redacted_cred
        
        # Redact static data
        if "staticData" in redacted_workflow:
            redacted_workflow["staticData"] = self.redact_dict(redacted_workflow["staticData"])
        
        return redacted_workflow
    
    def redact_workflow_list(self, workflows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Redact sensitive information from workflow list"""
        if not self.redaction_enabled:
            return workflows
        
        return [self.redact_workflow(workflow) for workflow in workflows]
    
    def redact_test_result(self, test_result: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive information from test execution result"""
        if not self.redaction_enabled:
            return test_result
        
        redacted = test_result.copy()
        
        # Redact output data
        if "output" in redacted and redacted["output"]:
            redacted["output"] = self.redact_dict(redacted["output"])
        
        # Redact test data
        if "test_data" in redacted and redacted["test_data"]:
            redacted["test_data"] = self.redact_dict(redacted["test_data"])
        
        # Redact error messages
        if "error" in redacted and isinstance(redacted["error"], str):
            redacted_error, _ = self.redact_text(redacted["error"])
            redacted["error"] = redacted_error
        
        return redacted
    
    def redact_execution_result(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive information from workflow execution result"""
        if not self.redaction_enabled:
            return execution_result
        
        redacted = execution_result.copy()
        
        # Redact execution data
        if "data" in redacted and redacted["data"]:
            redacted["data"] = self.redact_dict(redacted["data"])
        
        # Redact logs
        if "logs" in redacted and isinstance(redacted["logs"], list):
            redacted["logs"] = [
                self.redact_text(log)[0] if isinstance(log, str) else log
                for log in redacted["logs"]
            ]
        
        return redacted
    
    def redact_execution_status(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive information from execution status"""
        if not self.redaction_enabled:
            return status
        
        redacted = status.copy()
        
        # Redact execution data
        if "data" in redacted:
            redacted["data"] = self.redact_dict(redacted["data"])
        
        # Redact error information
        if "error" in redacted and redacted["error"]:
            if isinstance(redacted["error"], str):
                redacted["error"], _ = self.redact_text(redacted["error"])
            elif isinstance(redacted["error"], dict):
                redacted["error"] = self.redact_dict(redacted["error"])
        
        return redacted
    
    def _hash_value(self, value: str) -> str:
        """Create a consistent hash of a value for referencing"""
        return hashlib.sha256(value.encode()).hexdigest()[:8]
    
    def add_custom_rule(self, name: str, pattern: str, replacement: str, confidence: float = 0.8, category: str = "custom"):
        """Add a custom redaction rule"""
        try:
            regex_pattern = re.compile(pattern)
            rule = RedactionRule(
                name=name,
                pattern=regex_pattern,
                replacement=replacement,
                confidence=confidence,
                category=category
            )
            self.rules.append(rule)
            logger.info(f"Added custom redaction rule: {name}")
        except re.error as e:
            logger.error(f"Invalid regex pattern for rule {name}: {e}")
    
    def remove_rule(self, rule_name: str) -> bool:
        """Remove a redaction rule by name"""
        original_count = len(self.rules)
        self.rules = [rule for rule in self.rules if rule.name != rule_name]
        removed = len(self.rules) < original_count
        
        if removed:
            logger.info(f"Removed redaction rule: {rule_name}")
        
        return removed
    
    def get_redaction_stats(self) -> Dict[str, Any]:
        """Get statistics about redaction rules"""
        rule_categories = {}
        for rule in self.rules:
            category = rule.category
            rule_categories[category] = rule_categories.get(category, 0) + 1
        
        return {
            "enabled": self.redaction_enabled,
            "mode": self.redaction_mode,
            "total_rules": len(self.rules),
            "rule_categories": rule_categories,
            "preserve_length": self.preserve_length,
            "mask_character": self.mask_char
        }
    
    def test_redaction(self, test_text: str) -> Dict[str, Any]:
        """Test redaction on sample text and return detailed results"""
        redacted_text, result = self.redact_text(test_text)
        
        return {
            "original_text": test_text,
            "redacted_text": redacted_text,
            "redaction_result": {
                "original_size": result.original_size,
                "redacted_size": result.redacted_size,
                "redactions_count": result.redactions_count,
                "rules_triggered": result.rules_triggered,
                "confidence_score": result.confidence_score
            },
            "rules_applied": [
                {
                    "name": rule.name,
                    "category": rule.category,
                    "confidence": rule.confidence
                }
                for rule in self.rules if rule.name in result.rules_triggered
            ]
        }
    
    def redact_logs(self, logs: List[str]) -> List[str]:
        """Redact sensitive information from log entries"""
        if not self.redaction_enabled:
            return logs
        
        redacted_logs = []
        for log_entry in logs:
            if isinstance(log_entry, str):
                redacted_entry, _ = self.redact_text(log_entry)
                redacted_logs.append(redacted_entry)
            else:
                redacted_logs.append(log_entry)
        
        return redacted_logs
    
    def create_redaction_report(self, data: Any, data_type: str = "unknown") -> Dict[str, Any]:
        """Create a comprehensive redaction report"""
        report = {
            "data_type": data_type,
            "redaction_enabled": self.redaction_enabled,
            "redaction_mode": self.redaction_mode,
            "timestamp": time.time()
        }
        
        if not self.redaction_enabled:
            report["status"] = "disabled"
            return report
        
        # Perform redaction based on data type
        if isinstance(data, str):
            _, result = self.redact_text(data)
            report.update({
                "original_size": result.original_size,
                "redacted_size": result.redacted_size,
                "redactions_count": result.redactions_count,
                "rules_triggered": result.rules_triggered,
                "confidence_score": result.confidence_score
            })
        elif isinstance(data, dict):
            original_json = json.dumps(data)
            redacted_data = self.redact_dict(data)
            redacted_json = json.dumps(redacted_data)
            
            report.update({
                "original_size": len(original_json),
                "redacted_size": len(redacted_json),
                "size_reduction": len(original_json) - len(redacted_json),
                "keys_processed": len(data),
                "status": "completed"
            })
        else:
            report["status"] = "unsupported_type"
        
        return report
