"""
AI Helpers for Concierge Operations

Provides AI-powered assistance for:
- Log analysis and triage
- Stacktrace explanation and debugging
- Error pattern recognition
- System health insights
- Privacy-respecting analysis
"""
import re
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from ...core.redact import DataRedactor

class LogSeverity(Enum):
    """Log severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

@dataclass
class LogEntry:
    """Structured log entry."""
    timestamp: Optional[str]
    severity: LogSeverity
    component: Optional[str]
    message: str
    raw_line: str
    line_number: int

@dataclass
class LogAnalysis:
    """Log analysis result."""
    analysis_id: str
    total_lines: int
    entries_by_severity: Dict[str, int]
    key_issues: List[Dict[str, Any]]
    patterns_detected: List[Dict[str, Any]]
    recommendations: List[str]
    summary: str
    analysis_time: float
    confidence_score: float

@dataclass
class StacktraceAnalysis:
    """Stacktrace analysis result."""
    analysis_id: str
    error_type: Optional[str]
    root_cause: Optional[str]
    affected_components: List[str]
    suggested_fixes: List[str]
    related_logs: List[str]
    confidence_score: float
    explanation: str

class AIHelpers:
    """AI-powered helpers for system operations analysis."""
    
    def __init__(self, config, ai_agent=None):
        self.config = config
        self.ai_agent = ai_agent
        
        # Privacy settings
        self.privacy_mode = getattr(config, 'PRIVACY_MODE', 'strict')
        self.redactor = DataRedactor(self.privacy_mode)
        
        # AI settings
        self.ai_enabled = getattr(config, 'AI_ENABLED', True) and ai_agent is not None
        self.max_log_lines = getattr(config, 'MAX_LOG_ANALYSIS_LINES', 1000)
        self.max_context_chars = getattr(config, 'MAX_AI_CONTEXT_CHARS', 8000)
        
        # Log patterns for severity detection
        self.severity_patterns = self._initialize_severity_patterns()
        self.component_patterns = self._initialize_component_patterns()
    
    def _initialize_severity_patterns(self) -> Dict[LogSeverity, List[re.Pattern]]:
        """Initialize regex patterns for log severity detection."""
        return {
            LogSeverity.CRITICAL: [
                re.compile(r'\b(CRITICAL|FATAL|PANIC|EMERGENCY)\b', re.IGNORECASE),
                re.compile(r'\bcore dumped\b', re.IGNORECASE),
                re.compile(r'\bsegmentation fault\b', re.IGNORECASE),
                re.compile(r'\bkilled\b.*\bsignal\b', re.IGNORECASE),
            ],
            LogSeverity.ERROR: [
                re.compile(r'\b(ERROR|ERR|FAIL|FAILED|FAILURE)\b', re.IGNORECASE),
                re.compile(r'\bexception\b', re.IGNORECASE),
                re.compile(r'\bstack trace\b', re.IGNORECASE),
                re.compile(r'\bconnection refused\b', re.IGNORECASE),
                re.compile(r'\bpermission denied\b', re.IGNORECASE),
            ],
            LogSeverity.WARNING: [
                re.compile(r'\b(WARN|WARNING|CAUTION)\b', re.IGNORECASE),
                re.compile(r'\bdeprecated\b', re.IGNORECASE),
                re.compile(r'\bretrying\b', re.IGNORECASE),
                re.compile(r'\btimeout\b', re.IGNORECASE),
            ],
            LogSeverity.INFO: [
                re.compile(r'\b(INFO|INFORMATION)\b', re.IGNORECASE),
                re.compile(r'\bstarted\b', re.IGNORECASE),
                re.compile(r'\bstopped\b', re.IGNORECASE),
                re.compile(r'\binitialized\b', re.IGNORECASE),
            ],
            LogSeverity.DEBUG: [
                re.compile(r'\b(DEBUG|TRACE|VERBOSE)\b', re.IGNORECASE),
            ]
        }
    
    def _initialize_component_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Initialize patterns for component detection."""
        return {
            'nginx': [
                re.compile(r'\bnginx\b', re.IGNORECASE),
                re.compile(r'\[error\].*worker process', re.IGNORECASE),
            ],
            'docker': [
                re.compile(r'\bdocker\b', re.IGNORECASE),
                re.compile(r'\bcontainerd\b', re.IGNORECASE),
                re.compile(r'\bcontainer\b.*\b(started|stopped|died)\b', re.IGNORECASE),
            ],
            'systemd': [
                re.compile(r'\bsystemd\b', re.IGNORECASE),
                re.compile(r'\[.*\.service\]', re.IGNORECASE),
            ],
            'ssh': [
                re.compile(r'\bsshd\b', re.IGNORECASE),
                re.compile(r'\bSSH\b', re.IGNORECASE),
            ],
            'database': [
                re.compile(r'\b(mysql|postgresql|postgres|mongodb|redis)\b', re.IGNORECASE),
                re.compile(r'\bSQL\b', re.IGNORECASE),
            ],
            'web_server': [
                re.compile(r'\b(apache|httpd|lighttpd)\b', re.IGNORECASE),
                re.compile(r'\bHTTP\b', re.IGNORECASE),
            ]
        }
    
    def parse_log_entry(self, line: str, line_number: int) -> LogEntry:
        """Parse a single log line into structured entry."""
        # Extract timestamp (common formats)
        timestamp_patterns = [
            r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})',  # ISO format
            r'(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})',     # Syslog format
            r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})',   # US format
        ]
        
        timestamp = None
        for pattern in timestamp_patterns:
            match = re.search(pattern, line)
            if match:
                timestamp = match.group(1)
                break
        
        # Detect severity
        severity = LogSeverity.UNKNOWN
        for sev, patterns in self.severity_patterns.items():
            if any(pattern.search(line) for pattern in patterns):
                severity = sev
                break
        
        # Detect component
        component = None
        for comp, patterns in self.component_patterns.items():
            if any(pattern.search(line) for pattern in patterns):
                component = comp
                break
        
        # Clean message (remove timestamp and known prefixes)
        message = line
        if timestamp:
            message = re.sub(re.escape(timestamp), '', message).strip()
        
        # Remove common log prefixes
        message = re.sub(r'^\[[\w\s]+\]\s*', '', message)
        message = re.sub(r'^\w+:\s*', '', message)
        
        return LogEntry(
            timestamp=timestamp,
            severity=severity,
            component=component,
            message=message.strip(),
            raw_line=line,
            line_number=line_number
        )
    
    async def analyze_logs(
        self, 
        log_content: str, 
        context: Optional[str] = None,
        filter_severity: Optional[LogSeverity] = None
    ) -> LogAnalysis:
        """
        Analyze log content with AI assistance.
        
        Args:
            log_content: Raw log content to analyze
            context: Additional context about the logs
            filter_severity: Only analyze logs of specified severity or higher
        
        Returns:
            LogAnalysis object with insights and recommendations
        """
        start_time = time.time()
        
        # Redact sensitive information
        redacted_content = self.redactor.redact(log_content)
        
        # Parse log lines
        lines = redacted_content.split('\n')[:self.max_log_lines]
        entries = []
        
        for i, line in enumerate(lines):
            if line.strip():
                entry = self.parse_log_entry(line, i + 1)
                
                # Apply severity filter
                if filter_severity:
                    severity_order = [
                        LogSeverity.DEBUG, LogSeverity.INFO, LogSeverity.WARNING,
                        LogSeverity.ERROR, LogSeverity.CRITICAL
                    ]
                    if severity_order.index(entry.severity) < severity_order.index(filter_severity):
                        continue
                
                entries.append(entry)
        
        # Count entries by severity
        severity_counts = {}
        for severity in LogSeverity:
            severity_counts[severity.value] = len([e for e in entries if e.severity == severity])
        
        # Detect patterns and issues
        key_issues = self._detect_key_issues(entries)
        patterns = self._detect_patterns(entries)
        
        # Generate AI analysis if available
        ai_summary = ""
        ai_recommendations = []
        confidence_score = 0.5
        
        if self.ai_enabled and entries:
            try:
                ai_analysis = await self._generate_ai_log_analysis(entries, context)
                ai_summary = ai_analysis.get('summary', '')
                ai_recommendations = ai_analysis.get('recommendations', [])
                confidence_score = ai_analysis.get('confidence', 0.5)
            except Exception as e:
                ai_summary = f"AI analysis failed: {str(e)}"
        
        # Generate manual recommendations
        manual_recommendations = self._generate_manual_recommendations(entries, key_issues)
        
        # Combine recommendations
        all_recommendations = ai_recommendations + manual_recommendations
        
        analysis = LogAnalysis(
            analysis_id=self._generate_analysis_id(),
            total_lines=len(entries),
            entries_by_severity=severity_counts,
            key_issues=key_issues,
            patterns_detected=patterns,
            recommendations=all_recommendations,
            summary=ai_summary or self._generate_manual_summary(entries, key_issues),
            analysis_time=time.time() - start_time,
            confidence_score=confidence_score
        )
        
        return analysis
    
    async def explain_stacktrace(
        self, 
        stacktrace: str, 
        context: Optional[str] = None
    ) -> StacktraceAnalysis:
        """
        Explain stacktrace with AI assistance.
        
        Args:
            stacktrace: Stacktrace content to analyze
            context: Additional context about the error
        
        Returns:
            StacktraceAnalysis with explanation and suggestions
        """
        # Redact sensitive information
        redacted_trace = self.redactor.redact(stacktrace)
        
        # Extract basic information
        error_type = self._extract_error_type(redacted_trace)
        affected_components = self._extract_components(redacted_trace)
        
        # Generate AI explanation if available
        ai_explanation = ""
        ai_fixes = []
        confidence_score = 0.5
        
        if self.ai_enabled:
            try:
                ai_analysis = await self._generate_ai_stacktrace_analysis(redacted_trace, context)
                ai_explanation = ai_analysis.get('explanation', '')
                ai_fixes = ai_analysis.get('suggested_fixes', [])
                confidence_score = ai_analysis.get('confidence', 0.5)
            except Exception as e:
                ai_explanation = f"AI analysis failed: {str(e)}"
        
        # Generate manual analysis
        manual_fixes = self._generate_manual_fixes(error_type, redacted_trace)
        root_cause = self._analyze_root_cause(redacted_trace)
        
        analysis = StacktraceAnalysis(
            analysis_id=self._generate_analysis_id(),
            error_type=error_type,
            root_cause=root_cause,
            affected_components=affected_components,
            suggested_fixes=ai_fixes + manual_fixes,
            related_logs=[],  # Could be enhanced to find related log entries
            confidence_score=confidence_score,
            explanation=ai_explanation or self._generate_manual_explanation(error_type, redacted_trace)
        )
        
        return analysis
    
    async def _generate_ai_log_analysis(self, entries: List[LogEntry], context: Optional[str]) -> Dict[str, Any]:
        """Generate AI-powered log analysis."""
        
        # Prepare context for AI
        error_entries = [e for e in entries if e.severity in [LogSeverity.ERROR, LogSeverity.CRITICAL]]
        warning_entries = [e for e in entries if e.severity == LogSeverity.WARNING]
        
        # Create analysis prompt
        prompt = f"""Analyze the following system logs and provide insights:

**Context:** {context or 'System log analysis'}

**Log Summary:**
- Total entries: {len(entries)}
- Errors: {len(error_entries)}
- Warnings: {len(warning_entries)}

**Critical/Error Entries:**
{chr(10).join([f"- {e.message}" for e in error_entries[:10]])}

**Warning Entries:**
{chr(10).join([f"- {e.message}" for e in warning_entries[:5]])}

Please provide:
1. A concise summary of the main issues
2. 3-5 specific actionable recommendations
3. Assessment of system health

Keep analysis technical but clear. Focus on actionable insights."""
        
        # Limit prompt size
        if len(prompt) > self.max_context_chars:
            prompt = prompt[:self.max_context_chars] + "...\n[Content truncated]"
        
        try:
            response = await self.ai_agent.generate_response(
                message=prompt,
                user_id=0,  # System analysis
                temperature=0.3,
                max_tokens=1000
            )
            
            if response.success:
                # Parse AI response
                content = response.content
                
                # Extract recommendations (simple parsing)
                recommendations = []
                if "recommendations" in content.lower():
                    lines = content.split('\n')
                    in_recommendations = False
                    for line in lines:
                        if "recommendation" in line.lower():
                            in_recommendations = True
                            continue
                        if in_recommendations and (line.strip().startswith('-') or line.strip().startswith('*')):
                            recommendations.append(line.strip().lstrip('-*').strip())
                        elif in_recommendations and line.strip() and not line.startswith(' '):
                            break
                
                return {
                    'summary': content[:500],  # First 500 chars as summary
                    'recommendations': recommendations[:5],
                    'confidence': 0.8
                }
            else:
                return {
                    'summary': 'AI analysis unavailable',
                    'recommendations': [],
                    'confidence': 0.0
                }
                
        except Exception as e:
            return {
                'summary': f'AI analysis error: {str(e)}',
                'recommendations': [],
                'confidence': 0.0
            }
    
    async def _generate_ai_stacktrace_analysis(self, stacktrace: str, context: Optional[str]) -> Dict[str, Any]:
        """Generate AI-powered stacktrace analysis."""
        
        prompt = f"""Analyze this stacktrace and provide debugging guidance:

**Context:** {context or 'Error analysis'}

**Stacktrace:**
```
{stacktrace[:self.max_context_chars]}
```

Please provide:
1. Clear explanation of what went wrong
2. Most likely root cause
3. Specific steps to fix the issue
4. Prevention strategies

Be precise and actionable in your response."""
        
        try:
            response = await self.ai_agent.generate_response(
                message=prompt,
                user_id=0,
                temperature=0.3,
                max_tokens=800
            )
            
            if response.success:
                content = response.content
                
                # Simple parsing for suggested fixes
                suggested_fixes = []
                if "fix" in content.lower() or "solution" in content.lower():
                    lines = content.split('\n')
                    for line in lines:
                        if any(word in line.lower() for word in ['fix', 'solution', 'resolve', 'correct']):
                            if line.strip().startswith(('-', '*', '1.', '2.', '3.')):
                                suggested_fixes.append(line.strip().lstrip('-*123.').strip())
                
                return {
                    'explanation': content,
                    'suggested_fixes': suggested_fixes[:5],
                    'confidence': 0.8
                }
            else:
                return {
                    'explanation': 'AI analysis unavailable',
                    'suggested_fixes': [],
                    'confidence': 0.0
                }
                
        except Exception as e:
            return {
                'explanation': f'AI analysis error: {str(e)}',
                'suggested_fixes': [],
                'confidence': 0.0
            }
    
    def _detect_key_issues(self, entries: List[LogEntry]) -> List[Dict[str, Any]]:
        """Detect key issues from log entries."""
        issues = []
        
        # Group by error patterns
        error_patterns = {}
        for entry in entries:
            if entry.severity in [LogSeverity.ERROR, LogSeverity.CRITICAL]:
                # Normalize error message for grouping
                normalized = re.sub(r'\d+', 'NUM', entry.message)
                normalized = re.sub(r'[a-f0-9]{8,}', 'HEX', normalized)
                
                if normalized not in error_patterns:
                    error_patterns[normalized] = []
                error_patterns[normalized].append(entry)
        
        # Convert to issues
        for pattern, entries_list in error_patterns.items():
            if len(entries_list) >= 2:  # Repeated errors
                issues.append({
                    'type': 'repeated_error',
                    'pattern': pattern,
                    'occurrences': len(entries_list),
                    'severity': entries_list[0].severity.value,
                    'component': entries_list[0].component,
                    'sample_message': entries_list[0].message
                })
            else:
                issues.append({
                    'type': 'single_error',
                    'pattern': pattern,
                    'occurrences': 1,
                    'severity': entries_list[0].severity.value,
                    'component': entries_list[0].component,
                    'sample_message': entries_list[0].message
                })
        
        return sorted(issues, key=lambda x: x['occurrences'], reverse=True)
    
    def _detect_patterns(self, entries: List[LogEntry]) -> List[Dict[str, Any]]:
        """Detect patterns in log entries."""
        patterns = []
        
        # Detect component activity patterns
        component_activity = {}
        for entry in entries:
            if entry.component:
                if entry.component not in component_activity:
                    component_activity[entry.component] = []
                component_activity[entry.component].append(entry)
        
        for component, component_entries in component_activity.items():
            error_count = len([e for e in component_entries if e.severity in [LogSeverity.ERROR, LogSeverity.CRITICAL]])
            if error_count > 0:
                patterns.append({
                    'type': 'component_errors',
                    'component': component,
                    'error_count': error_count,
                    'total_entries': len(component_entries),
                    'error_rate': error_count / len(component_entries)
                })
        
        return patterns
    
    def _generate_manual_recommendations(self, entries: List[LogEntry], issues: List[Dict[str, Any]]) -> List[str]:
        """Generate manual recommendations based on detected patterns."""
        recommendations = []
        
        # Check for common issues
        error_count = len([e for e in entries if e.severity == LogSeverity.ERROR])
        critical_count = len([e for e in entries if e.severity == LogSeverity.CRITICAL])
        
        if critical_count > 0:
            recommendations.append("Critical errors detected - immediate investigation required")
        
        if error_count > 10:
            recommendations.append("High error rate detected - review system configuration")
        
        # Component-specific recommendations
        components_with_errors = set()
        for entry in entries:
            if entry.severity in [LogSeverity.ERROR, LogSeverity.CRITICAL] and entry.component:
                components_with_errors.add(entry.component)
        
        for component in components_with_errors:
            if component == 'docker':
                recommendations.append("Check Docker container health and resource limits")
            elif component == 'nginx':
                recommendations.append("Review Nginx configuration and check for upstream issues")
            elif component == 'database':
                recommendations.append("Check database connections and performance metrics")
        
        return recommendations[:5]
    
    def _generate_manual_summary(self, entries: List[LogEntry], issues: List[Dict[str, Any]]) -> str:
        """Generate manual summary of log analysis."""
        error_count = len([e for e in entries if e.severity == LogSeverity.ERROR])
        critical_count = len([e for e in entries if e.severity == LogSeverity.CRITICAL])
        warning_count = len([e for e in entries if e.severity == LogSeverity.WARNING])
        
        summary = f"Analyzed {len(entries)} log entries. "
        
        if critical_count > 0:
            summary += f"Found {critical_count} critical issues requiring immediate attention. "
        
        if error_count > 0:
            summary += f"Detected {error_count} errors. "
        
        if warning_count > 0:
            summary += f"Found {warning_count} warnings. "
        
        if len(issues) > 0:
            summary += f"Identified {len(issues)} distinct issue patterns."
        else:
            summary += "No significant issues detected."
        
        return summary
    
    def _extract_error_type(self, stacktrace: str) -> Optional[str]:
        """Extract error type from stacktrace."""
        # Common error patterns
        error_patterns = [
            r'(\w*Exception)',
            r'(\w*Error)',
            r'(\w*Fault)',
            r'(\w*Failure)',
        ]
        
        for pattern in error_patterns:
            match = re.search(pattern, stacktrace)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_components(self, stacktrace: str) -> List[str]:
        """Extract affected components from stacktrace."""
        components = []
        
        # Look for package/module names
        package_patterns = [
            r'at ([a-z]+\.[a-z]+)',  # Java-style
            r'in ([a-z_]+\.py)',     # Python files
            r'from ([a-z_]+)',       # Python modules
        ]
        
        for pattern in package_patterns:
            matches = re.findall(pattern, stacktrace, re.IGNORECASE)
            components.extend(matches)
        
        return list(set(components))[:5]  # Unique, limit to 5
    
    def _analyze_root_cause(self, stacktrace: str) -> Optional[str]:
        """Analyze root cause from stacktrace."""
        # Look for common root cause indicators
        if 'NullPointerException' in stacktrace:
            return "Null pointer dereference"
        elif 'ConnectionRefused' in stacktrace:
            return "Service connection failure"
        elif 'PermissionDenied' in stacktrace:
            return "Insufficient permissions"
        elif 'OutOfMemory' in stacktrace:
            return "Memory exhaustion"
        elif 'TimeoutException' in stacktrace:
            return "Operation timeout"
        
        return None
    
    def _generate_manual_fixes(self, error_type: Optional[str], stacktrace: str) -> List[str]:
        """Generate manual fix suggestions based on error type."""
        fixes = []
        
        if error_type:
            if 'NullPointer' in error_type:
                fixes.append("Add null checks before object access")
                fixes.append("Initialize variables properly")
            elif 'Connection' in error_type:
                fixes.append("Check network connectivity")
                fixes.append("Verify service is running and accessible")
            elif 'Permission' in error_type:
                fixes.append("Check file/directory permissions")
                fixes.append("Run with appropriate user privileges")
            elif 'Memory' in error_type:
                fixes.append("Increase available memory")
                fixes.append("Check for memory leaks")
            elif 'Timeout' in error_type:
                fixes.append("Increase timeout values")
                fixes.append("Optimize slow operations")
        
        # Generic fixes
        fixes.append("Check system logs for additional context")
        fixes.append("Restart the affected service")
        
        return fixes[:3]
    
    def _generate_manual_explanation(self, error_type: Optional[str], stacktrace: str) -> str:
        """Generate manual explanation of the error."""
        if error_type:
            return f"A {error_type} occurred in the system. This typically indicates an issue with the application logic or system configuration. Review the stacktrace to identify the specific line and method where the error originated."
        else:
            return "An error occurred in the system. Review the stacktrace to identify the root cause and affected components."
    
    def _generate_analysis_id(self) -> str:
        """Generate unique analysis ID."""
        import hashlib
        return hashlib.sha256(f"{time.time()}:{hash(id(self))}".encode()).hexdigest()[:12]

# Export
__all__ = ["LogSeverity", "LogEntry", "LogAnalysis", "StacktraceAnalysis", "AIHelpers"]
