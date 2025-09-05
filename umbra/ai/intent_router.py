"""
Intent router for UMBRA - Deterministic routing with LLM fallback.
Routes user requests to appropriate modules based on intent analysis.
"""
import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from .provider_agnostic import ProviderAgnosticAI


@dataclass
class Intent:
    """Represents user intent with confidence score."""
    module_id: str
    action: str
    confidence: float
    params: Dict[str, Any]
    reasoning: str = ""


@dataclass
class RouteRule:
    """Deterministic routing rule."""
    patterns: List[str]  # Regex patterns or keywords
    module_id: str
    action: str
    confidence: float = 1.0
    param_extractors: Optional[Dict[str, str]] = None  # Parameter extraction patterns


class IntentRouter:
    """Routes user intents to appropriate modules with deterministic rules first."""
    
    def __init__(self, config, ai_provider: Optional[ProviderAgnosticAI] = None):
        self.config = config
        self.ai_provider = ai_provider
        self.logger = logging.getLogger(__name__)
        
        # Deterministic routing rules (processed first)
        self.deterministic_rules = self._init_deterministic_rules()
        
        # Available modules and their capabilities (set by ModuleRegistry)
        self.module_capabilities: Dict[str, List[str]] = {}
        
        self.logger.info(f"🧭 Intent router initialized with {len(self.deterministic_rules)} deterministic rules")
    
    def _init_deterministic_rules(self) -> List[RouteRule]:
        """Initialize deterministic routing rules."""
        return [
            # Finance module rules
            RouteRule(
                patterns=[r'\$\d+', r'expense', r'spent', r'budget', r'money', r'cost', r'price'],
                module_id='finance',
                action='track_expense',
                confidence=0.9,
                param_extractors={'amount': r'\$?(\d+(?:\.\d{2})?)'}
            ),
            RouteRule(
                patterns=[r'financial report', r'spending report', r'monthly report'],
                module_id='finance',
                action='monthly_report',
                confidence=0.95
            ),
            RouteRule(
                patterns=[r'account balance', r'balance', r'how much.*have'],
                module_id='finance',
                action='account_balance',
                confidence=0.9
            ),
            
            # System/Concierge module rules
            RouteRule(
                patterns=[r'system status', r'server status', r'cpu', r'memory', r'disk'],
                module_id='concierge',
                action='system_status',
                confidence=0.9
            ),
            RouteRule(
                patterns=[r'docker', r'container', r'restart.*service'],
                module_id='concierge',
                action='docker_status',
                confidence=0.85
            ),
            RouteRule(
                patterns=[r'backup', r'backup system'],
                module_id='concierge',
                action='backup_system',
                confidence=0.9
            ),
            
            # Business module rules
            RouteRule(
                patterns=[r'client', r'create.*instance', r'new.*vps', r'business'],
                module_id='business',
                action='create_client_instance',
                confidence=0.8
            ),
            RouteRule(
                patterns=[r'invoice', r'billing', r'project.*status'],
                module_id='business',
                action='generate_invoice',
                confidence=0.85
            ),
            
            # Production/Automation rules
            RouteRule(
                patterns=[r'workflow', r'automation', r'n8n', r'create.*workflow'],
                module_id='production',
                action='create_workflow',
                confidence=0.85
            ),
            
            # Creator module rules
            RouteRule(
                patterns=[r'generate.*image', r'create.*document', r'dall.?e', r'generate.*content'],
                module_id='creator',
                action='generate_content',
                confidence=0.8
            ),
            
            # Help and general rules
            RouteRule(
                patterns=[r'help', r'what.*can.*do', r'capabilities', r'modules'],
                module_id='help',
                action='show_capabilities',
                confidence=0.95
            )
        ]
    
    def set_module_capabilities(self, capabilities: Dict[str, List[str]]):
        """Set available modules and their capabilities."""
        self.module_capabilities = capabilities
        self.logger.info(f"📋 Updated capabilities for {len(capabilities)} modules")
    
    async def route_intent(self, message: str, user_context: Optional[Dict] = None) -> Intent:
        """Route user message to appropriate module and action."""
        message = message.strip()
        
        # First, try deterministic routing
        deterministic_intent = self._route_deterministic(message, user_context)
        if deterministic_intent and deterministic_intent.confidence >= 0.7:
            self.logger.info(f"🎯 Deterministic route: {deterministic_intent.module_id}.{deterministic_intent.action} (confidence: {deterministic_intent.confidence})")
            return deterministic_intent
        
        # Fallback to LLM-based routing if available
        if self.ai_provider and self.ai_provider.is_ai_available():
            llm_intent = await self._route_with_llm(message, user_context)
            if llm_intent:
                self.logger.info(f"🤖 LLM route: {llm_intent.module_id}.{llm_intent.action} (confidence: {llm_intent.confidence})")
                return llm_intent
        
        # Final fallback - return help intent
        self.logger.info("❓ No clear intent detected, routing to help")
        return Intent(
            module_id='help',
            action='show_capabilities',
            confidence=0.5,
            params={},
            reasoning="No clear intent detected"
        )
    
    def _route_deterministic(self, message: str, user_context: Optional[Dict] = None) -> Optional[Intent]:
        """Route using deterministic pattern matching."""
        message_lower = message.lower()
        best_match = None
        best_confidence = 0.0
        
        for rule in self.deterministic_rules:
            confidence = 0.0
            matched_patterns = 0
            extracted_params = {}
            
            # Check if any patterns match
            for pattern in rule.patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    matched_patterns += 1
            
            # Calculate confidence based on pattern matches
            if matched_patterns > 0:
                confidence = rule.confidence * (matched_patterns / len(rule.patterns))
                
                # Extract parameters if specified
                if rule.param_extractors:
                    for param_name, pattern in rule.param_extractors.items():
                        match = re.search(pattern, message, re.IGNORECASE)
                        if match:
                            extracted_params[param_name] = match.group(1)
                            confidence += 0.1  # Boost confidence for parameter extraction
                
                # Check if this is the best match so far
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = Intent(
                        module_id=rule.module_id,
                        action=rule.action,
                        confidence=min(confidence, 1.0),
                        params=extracted_params,
                        reasoning=f"Matched patterns: {rule.patterns[:matched_patterns]}"
                    )
        
        return best_match
    
    async def _route_with_llm(self, message: str, user_context: Optional[Dict] = None) -> Optional[Intent]:
        """Route using LLM analysis when deterministic routing fails."""
        try:
            # Build system prompt with available modules
            modules_info = []
            for module_id, capabilities in self.module_capabilities.items():
                caps_str = ", ".join(capabilities[:3])  # Show first 3 capabilities
                modules_info.append(f"- {module_id}: {caps_str}")
            
            system_prompt = f"""You are an intent router for UMBRA. Analyze the user message and determine which module and action to use.

Available modules:
{chr(10).join(modules_info)}

Respond ONLY with a JSON object in this format:
{{
    "module_id": "module_name",
    "action": "action_name", 
    "confidence": 0.8,
    "params": {{}},
    "reasoning": "why this module/action was chosen"
}}

If unsure, use "help" module with "show_capabilities" action."""
            
            messages = [{"role": "user", "content": message}]
            
            response = await self.ai_provider.generate_response(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=200,
                temperature=0.3
            )
            
            if response:
                # Try to parse JSON response
                try:
                    intent_data = self._extract_json_from_response(response)
                    if intent_data:
                        return Intent(
                            module_id=intent_data.get('module_id', 'help'),
                            action=intent_data.get('action', 'show_capabilities'),
                            confidence=intent_data.get('confidence', 0.5),
                            params=intent_data.get('params', {}),
                            reasoning=intent_data.get('reasoning', 'LLM analysis')
                        )
                except Exception as e:
                    self.logger.warning(f"Failed to parse LLM response: {e}")
        
        except Exception as e:
            self.logger.error(f"LLM routing failed: {e}")
        
        return None
    
    def _extract_json_from_response(self, response: str) -> Optional[Dict]:
        """Extract JSON from LLM response."""
        import json
        
        # Try to find JSON in the response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        return None
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get statistics about routing performance."""
        return {
            "deterministic_rules": len(self.deterministic_rules),
            "available_modules": len(self.module_capabilities),
            "llm_available": self.ai_provider.is_ai_available() if self.ai_provider else False
        }