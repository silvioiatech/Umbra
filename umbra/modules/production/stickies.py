"""
Sticky Notes Manager for Production Module

Generates and manages workflow documentation through AI-powered sticky notes
that provide context and explanations without modifying workflow structure.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import time

from ...ai.agent import UmbraAIAgent
from ...core.config import UmbraConfig

logger = logging.getLogger(__name__)

@dataclass
class StickyNote:
    """Represents a sticky note annotation"""
    id: str
    type: str  # "workflow", "node", "connection", "parameter"
    target: str  # Target element ID or path
    title: str
    content: str
    category: str  # "explanation", "warning", "tip", "example"
    created_at: float
    ai_generated: bool = True

@dataclass
class StickyNotesResult:
    """Result of sticky notes generation"""
    workflow_id: Optional[str]
    notes_count: int
    notes: List[StickyNote]
    workflow_summary: str
    tokens_used: int
    generation_time: float

class StickyNotesManager:
    """Manages AI-generated documentation for workflows"""
    
    def __init__(self, ai_agent: UmbraAIAgent, config: UmbraConfig):
        self.ai_agent = ai_agent
        self.config = config
        
        # Configuration
        self.max_notes_per_workflow = config.get("PROD_MAX_STICKY_NOTES", 50)
        self.note_categories = ["explanation", "warning", "tip", "example", "best_practice"]
        
        logger.info("Sticky notes manager initialized")
    
    async def generate_sticky_notes(self, workflow_id: Optional[str] = None, workflow_json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate sticky notes for workflow"""
        try:
            start_time = time.time()
            
            # Get workflow data
            if workflow_json:
                workflow = workflow_json
                workflow_id = workflow.get("id", "unknown")
            elif workflow_id:
                # This would require getting workflow from n8n, but we'll work with provided JSON
                raise Exception("workflow_json must be provided when workflow_id is not available")
            else:
                raise Exception("Either workflow_id or workflow_json must be provided")
            
            # Generate comprehensive notes
            notes = await self._generate_comprehensive_notes(workflow)
            
            # Generate workflow summary
            summary = await self._generate_workflow_summary(workflow, notes)
            
            # Apply notes to workflow
            annotated_workflow = self._apply_notes_to_workflow(workflow, notes)
            
            generation_time = time.time() - start_time
            
            result = StickyNotesResult(
                workflow_id=workflow_id,
                notes_count=len(notes),
                notes=notes,
                workflow_summary=summary,
                tokens_used=sum(note.content.count(' ') * 1.3 for note in notes),  # Rough estimate
                generation_time=generation_time
            )
            
            return {
                "workflow": annotated_workflow,
                "notes_count": result.notes_count,
                "summary": result.workflow_summary,
                "notes": [note.__dict__ for note in result.notes],
                "generation_time": result.generation_time,
                "tokens_used": int(result.tokens_used),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Sticky notes generation failed: {e}")
            return {
                "error": str(e),
                "workflow_id": workflow_id,
                "status": "failed"
            }
    
    async def _generate_comprehensive_notes(self, workflow: Dict[str, Any]) -> List[StickyNote]:
        """Generate comprehensive sticky notes for workflow"""
        notes = []
        
        # Generate workflow-level notes
        workflow_notes = await self._generate_workflow_level_notes(workflow)
        notes.extend(workflow_notes)
        
        # Generate node-level notes
        nodes = workflow.get("nodes", [])
        for node in nodes:
            node_notes = await self._generate_node_level_notes(node, workflow)
            notes.extend(node_notes)
        
        # Generate connection-level notes
        connections = workflow.get("connections", {})
        connection_notes = await self._generate_connection_level_notes(connections, nodes)
        notes.extend(connection_notes)
        
        # Limit total notes
        if len(notes) > self.max_notes_per_workflow:
            # Prioritize by importance
            notes = self._prioritize_notes(notes)[:self.max_notes_per_workflow]
        
        return notes
    
    async def _generate_workflow_level_notes(self, workflow: Dict[str, Any]) -> List[StickyNote]:
        """Generate workflow-level documentation notes"""
        notes = []
        
        # Workflow overview note
        overview_prompt = f"""
        Analyze this n8n workflow and provide a clear overview explanation.
        
        Workflow: {workflow.get('name', 'Unnamed')}
        Nodes: {len(workflow.get('nodes', []))}
        Active: {workflow.get('active', False)}
        
        Node Types: {[node.get('type', 'unknown') for node in workflow.get('nodes', [])]}
        
        Provide a concise but informative overview (2-3 sentences) that explains:
        1. What this workflow does
        2. How it works at a high level
        3. Key benefits or use cases
        
        Keep it accessible for both technical and non-technical users.
        """
        
        try:
            overview_response = await self.ai_agent.generate_response(
                overview_prompt,
                role="planner",
                response_format="text",
                max_tokens=200
            )
            
            notes.append(StickyNote(
                id=f"workflow_overview_{int(time.time())}",
                type="workflow",
                target="workflow",
                title="Workflow Overview",
                content=overview_response.strip(),
                category="explanation",
                created_at=time.time()
            ))
            
        except Exception as e:
            logger.warning(f"Failed to generate workflow overview: {e}")
        
        # Trigger analysis note
        trigger_nodes = [node for node in workflow.get("nodes", []) 
                        if "trigger" in node.get("type", "").lower() or 
                           "webhook" in node.get("type", "").lower()]
        
        if trigger_nodes:
            trigger_note = self._generate_trigger_analysis_note(trigger_nodes)
            if trigger_note:
                notes.append(trigger_note)
        
        # Security considerations note
        security_note = self._generate_security_considerations_note(workflow)
        if security_note:
            notes.append(security_note)
        
        return notes
    
    async def _generate_node_level_notes(self, node: Dict[str, Any], workflow: Dict[str, Any]) -> List[StickyNote]:
        """Generate notes for individual nodes"""
        notes = []
        node_id = node.get("id", "unknown")
        node_type = node.get("type", "unknown")
        node_name = node.get("name", node_id)
        
        # Generate explanation note for complex nodes
        if self._is_complex_node(node):
            explanation_note = await self._generate_node_explanation(node)
            if explanation_note:
                notes.append(explanation_note)
        
        # Generate parameter guidance notes
        parameters = node.get("parameters", {})
        if parameters:
            param_notes = self._generate_parameter_notes(node_id, node_name, parameters)
            notes.extend(param_notes)
        
        # Generate best practice notes
        best_practice_note = self._generate_best_practice_note(node)
        if best_practice_note:
            notes.append(best_practice_note)
        
        # Generate warning notes for potentially problematic configurations
        warning_notes = self._generate_warning_notes(node)
        notes.extend(warning_notes)
        
        return notes
    
    async def _generate_connection_level_notes(self, connections: Dict[str, Any], nodes: List[Dict[str, Any]]) -> List[StickyNote]:
        """Generate notes about workflow connections and data flow"""
        notes = []
        
        # Create node lookup
        node_lookup = {node.get("id"): node for node in nodes}
        
        # Analyze complex connection patterns
        for source_id, connection_data in connections.items():
            source_node = node_lookup.get(source_id)
            if not source_node:
                continue
            
            # Check for complex routing patterns
            total_connections = sum(
                len(output_list)
                for outputs in connection_data.values()
                for output_list in outputs
            )
            
            if total_connections > 3:  # Multiple outputs
                note = StickyNote(
                    id=f"connection_complex_{source_id}_{int(time.time())}",
                    type="connection",
                    target=source_id,
                    title="Complex Routing",
                    content=f"This node routes data to {total_connections} different paths. "
                           f"Ensure all branches handle the data appropriately and consider "
                           f"adding error handling for each path.",
                    category="tip",
                    created_at=time.time()
                )
                notes.append(note)
        
        return notes
    
    def _is_complex_node(self, node: Dict[str, Any]) -> bool:
        """Determine if node is complex enough to need explanation"""
        node_type = node.get("type", "").lower()
        
        # Node types that typically need explanation
        complex_types = [
            "code", "function", "javascript", "python",
            "if", "switch", "merge", "aggregate",
            "split", "itemlists", "json", "xml"
        ]
        
        return any(ctype in node_type for ctype in complex_types)
    
    async def _generate_node_explanation(self, node: Dict[str, Any]) -> Optional[StickyNote]:
        """Generate explanation note for complex node"""
        node_id = node.get("id", "unknown")
        node_type = node.get("type", "unknown")
        node_name = node.get("name", node_id)
        parameters = node.get("parameters", {})
        
        explanation_prompt = f"""
        Explain what this n8n node does in simple terms.
        
        Node Type: {node_type}
        Node Name: {node_name}
        Key Parameters: {list(parameters.keys())[:5]}  # Show first 5 parameter keys
        
        Provide a clear, concise explanation (1-2 sentences) that:
        1. Explains the node's primary function
        2. Mentions key configuration aspects if relevant
        3. Is understandable to users with basic workflow knowledge
        
        Focus on practical understanding, not technical implementation details.
        """
        
        try:
            explanation = await self.ai_agent.generate_response(
                explanation_prompt,
                role="planner",
                response_format="text",
                max_tokens=150
            )
            
            return StickyNote(
                id=f"node_explanation_{node_id}_{int(time.time())}",
                type="node",
                target=node_id,
                title=f"How {node_name} Works",
                content=explanation.strip(),
                category="explanation",
                created_at=time.time()
            )
            
        except Exception as e:
            logger.warning(f"Failed to generate node explanation for {node_id}: {e}")
            return None
    
    def _generate_parameter_notes(self, node_id: str, node_name: str, parameters: Dict[str, Any]) -> List[StickyNote]:
        """Generate notes about important parameters"""
        notes = []
        
        # Look for parameters that commonly need explanation
        important_params = {
            "code": "Custom code that processes input data",
            "expression": "JavaScript expression that transforms data",
            "condition": "Logic that determines execution path",
            "url": "Target endpoint for HTTP requests",
            "method": "HTTP method (GET, POST, etc.)",
            "timeout": "Maximum time to wait for response",
            "retries": "Number of retry attempts on failure"
        }
        
        for param_key, param_value in parameters.items():
            if param_key.lower() in important_params:
                note = StickyNote(
                    id=f"param_{node_id}_{param_key}_{int(time.time())}",
                    type="parameter",
                    target=f"{node_id}.parameters.{param_key}",
                    title=f"Parameter: {param_key}",
                    content=important_params[param_key.lower()],
                    category="explanation",
                    created_at=time.time()
                )
                notes.append(note)
        
        return notes
    
    def _generate_best_practice_note(self, node: Dict[str, Any]) -> Optional[StickyNote]:
        """Generate best practice note for node"""
        node_id = node.get("id", "unknown")
        node_type = node.get("type", "").lower()
        node_name = node.get("name", node_id)
        
        # Best practices by node type
        best_practices = {
            "http": "Set appropriate timeouts and handle HTTP errors gracefully. Consider rate limiting for external APIs.",
            "code": "Keep code simple and well-commented. Avoid complex logic that's hard to debug in the workflow context.",
            "webhook": "Validate incoming data and implement proper authentication. Consider request size limits.",
            "email": "Use templates for consistent formatting. Be mindful of rate limits and delivery reliability.",
            "if": "Make conditions explicit and handle edge cases. Consider what happens when conditions are not met.",
            "switch": "Ensure all possible cases are handled. Add a default case for unexpected values."
        }
        
        for pattern, practice in best_practices.items():
            if pattern in node_type:
                return StickyNote(
                    id=f"best_practice_{node_id}_{int(time.time())}",
                    type="node",
                    target=node_id,
                    title=f"Best Practice for {node_name}",
                    content=practice,
                    category="best_practice",
                    created_at=time.time()
                )
        
        return None
    
    def _generate_warning_notes(self, node: Dict[str, Any]) -> List[StickyNote]:
        """Generate warning notes for potential issues"""
        notes = []
        node_id = node.get("id", "unknown")
        node_type = node.get("type", "").lower()
        node_name = node.get("name", node_id)
        parameters = node.get("parameters", {})
        
        # Check for common issues
        
        # Missing error handling
        if "http" in node_type and not parameters.get("continueOnFail"):
            notes.append(StickyNote(
                id=f"warning_error_handling_{node_id}_{int(time.time())}",
                type="node",
                target=node_id,
                title="Error Handling",
                content="Consider enabling 'Continue on Fail' to handle HTTP errors gracefully and prevent workflow crashes.",
                category="warning",
                created_at=time.time()
            ))
        
        # Missing timeout
        if "http" in node_type and not parameters.get("timeout"):
            notes.append(StickyNote(
                id=f"warning_timeout_{node_id}_{int(time.time())}",
                type="node",
                target=node_id,
                title="Missing Timeout",
                content="Set a timeout value to prevent the workflow from hanging on slow or unresponsive endpoints.",
                category="warning",
                created_at=time.time()
            ))
        
        # Hardcoded values that should be dynamic
        for param_key, param_value in parameters.items():
            if isinstance(param_value, str) and param_value.startswith("http") and "example.com" in param_value:
                notes.append(StickyNote(
                    id=f"warning_example_url_{node_id}_{int(time.time())}",
                    type="parameter",
                    target=f"{node_id}.parameters.{param_key}",
                    title="Example URL Detected",
                    content="This appears to be an example URL. Update with the actual endpoint before using in production.",
                    category="warning",
                    created_at=time.time()
                ))
        
        return notes
    
    def _generate_trigger_analysis_note(self, trigger_nodes: List[Dict[str, Any]]) -> Optional[StickyNote]:
        """Generate note analyzing workflow triggers"""
        if not trigger_nodes:
            return None
        
        trigger_types = [node.get("type", "unknown") for node in trigger_nodes]
        
        if len(trigger_nodes) == 1:
            trigger_type = trigger_types[0]
            if "webhook" in trigger_type.lower():
                content = "This workflow is triggered by incoming HTTP requests. Ensure the webhook URL is properly secured and consider authentication."
            elif "cron" in trigger_type.lower():
                content = "This workflow runs on a schedule. Monitor execution frequency and ensure it doesn't overlap with previous runs."
            elif "manual" in trigger_type.lower():
                content = "This workflow is manually triggered. Consider adding proper input validation and user permissions."
            else:
                content = f"This workflow is triggered by {trigger_type}. Review trigger configuration for your use case."
        else:
            content = f"This workflow has {len(trigger_nodes)} triggers: {', '.join(set(trigger_types))}. Multiple triggers can provide flexibility but may complicate testing and monitoring."
        
        return StickyNote(
            id=f"trigger_analysis_{int(time.time())}",
            type="workflow",
            target="triggers",
            title="Trigger Analysis",
            content=content,
            category="explanation",
            created_at=time.time()
        )
    
    def _generate_security_considerations_note(self, workflow: Dict[str, Any]) -> Optional[StickyNote]:
        """Generate security considerations note"""
        nodes = workflow.get("nodes", [])
        
        # Check for security-relevant patterns
        has_http_nodes = any("http" in node.get("type", "").lower() for node in nodes)
        has_code_nodes = any("code" in node.get("type", "").lower() for node in nodes)
        has_webhook_nodes = any("webhook" in node.get("type", "").lower() for node in nodes)
        has_credentials = any("credentials" in node for node in nodes)
        
        security_notes = []
        
        if has_webhook_nodes:
            security_notes.append("webhook endpoints should be secured")
        if has_code_nodes:
            security_notes.append("custom code should be reviewed for security")
        if has_http_nodes:
            security_notes.append("external API calls should use HTTPS")
        if has_credentials:
            security_notes.append("credentials should be properly configured")
        
        if security_notes:
            content = f"Security considerations: {', '.join(security_notes)}. Review these aspects before production deployment."
            
            return StickyNote(
                id=f"security_considerations_{int(time.time())}",
                type="workflow",
                target="security",
                title="Security Considerations",
                content=content,
                category="warning",
                created_at=time.time()
            )
        
        return None
    
    def _prioritize_notes(self, notes: List[StickyNote]) -> List[StickyNote]:
        """Prioritize notes by importance"""
        priority_order = {
            "warning": 1,
            "explanation": 2,
            "best_practice": 3,
            "tip": 4,
            "example": 5
        }
        
        return sorted(notes, key=lambda note: priority_order.get(note.category, 6))
    
    def _apply_notes_to_workflow(self, workflow: Dict[str, Any], notes: List[StickyNote]) -> Dict[str, Any]:
        """Apply sticky notes to workflow metadata without modifying structure"""
        annotated_workflow = workflow.copy()
        
        # Add notes to workflow metadata
        annotated_workflow.setdefault("meta", {})
        annotated_workflow["meta"]["x_sticky_notes"] = [note.__dict__ for note in notes]
        annotated_workflow["meta"]["x_notes_generated"] = time.time()
        annotated_workflow["meta"]["x_notes_count"] = len(notes)
        
        # Add summary note to each node (safe metadata only)
        nodes = annotated_workflow.get("nodes", [])
        for node in nodes:
            node_id = node.get("id")
            node_notes = [note for note in notes if note.target == node_id]
            
            if node_notes:
                # Add notes to node parameters as safe metadata
                node.setdefault("parameters", {})
                node["parameters"]["x_sticky_notes"] = [
                    {
                        "title": note.title,
                        "content": note.content,
                        "category": note.category
                    }
                    for note in node_notes
                ]
        
        return annotated_workflow
    
    async def _generate_workflow_summary(self, workflow: Dict[str, Any], notes: List[StickyNote]) -> str:
        """Generate comprehensive workflow summary"""
        workflow_name = workflow.get("name", "Unnamed Workflow")
        nodes = workflow.get("nodes", [])
        
        summary_prompt = f"""
        Create a comprehensive but concise summary of this n8n workflow.
        
        Workflow: {workflow_name}
        Node Count: {len(nodes)}
        Node Types: {list(set(node.get('type', 'unknown') for node in nodes))}
        
        Generated Notes: {len(notes)} documentation notes were created
        Note Categories: {list(set(note.category for note in notes))}
        
        Provide a summary (3-4 sentences) that covers:
        1. What the workflow accomplishes
        2. Key components and flow
        3. Important considerations or requirements
        4. Overall complexity and maintenance needs
        
        Make it suitable for technical documentation.
        """
        
        try:
            summary = await self.ai_agent.generate_response(
                summary_prompt,
                role="planner",
                response_format="text",
                max_tokens=300
            )
            
            return summary.strip()
            
        except Exception as e:
            logger.warning(f"Failed to generate workflow summary: {e}")
            return f"Workflow '{workflow_name}' with {len(nodes)} nodes. {len(notes)} documentation notes generated."
