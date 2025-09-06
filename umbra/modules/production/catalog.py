"""
Catalog Manager for Production Module

Manages n8n node catalog with caching, filtering, and efficient retrieval
for workflow building based on plan requirements.
"""

import json
import logging
import asyncio
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import hashlib

from ...core.config import UmbraConfig
from .n8n_client import N8nClient

logger = logging.getLogger(__name__)

@dataclass
class NodeInfo:
    """Compact node information for catalog"""
    id: str
    display_name: str
    description: str
    category: str
    parameters: List[Dict[str, Any]]
    inputs: List[str]
    outputs: List[str]
    credentials: Optional[str] = None
    webhooks: bool = False
    triggers: bool = False

@dataclass
class CatalogEntry:
    """Catalog entry with relevance scoring"""
    node: NodeInfo
    relevance_score: float
    tags: List[str]
    use_cases: List[str]

class CatalogManager:
    """Manages n8n node catalog with intelligent filtering"""
    
    def __init__(self, n8n_client: N8nClient, config: UmbraConfig):
        self.n8n_client = n8n_client
        self.config = config
        self.cache = {}
        self.cache_ttl = config.get("PROD_CATALOG_TTL_S", 21600)  # 6 hours
        
        # Node whitelist for security
        self.whitelisted_nodes = self._load_node_whitelist()
        
        logger.info("Catalog manager initialized")
    
    def _load_node_whitelist(self) -> List[str]:
        """Load whitelisted node types from config"""
        # Default whitelist of safe, commonly used nodes
        default_whitelist = [
            # Triggers
            "n8n-nodes-base.webhook",
            "n8n-nodes-base.cron",
            "n8n-nodes-base.manualTrigger",
            "n8n-nodes-base.intervalTrigger",
            
            # HTTP & APIs
            "n8n-nodes-base.httpRequest",
            "n8n-nodes-base.httpRequestV2",
            
            # Data manipulation
            "n8n-nodes-base.set",
            "n8n-nodes-base.code",
            "n8n-nodes-base.json",
            "n8n-nodes-base.dateTime",
            "n8n-nodes-base.filter",
            "n8n-nodes-base.merge",
            "n8n-nodes-base.sort",
            "n8n-nodes-base.aggregate",
            
            # Logic & Flow
            "n8n-nodes-base.if",
            "n8n-nodes-base.switch",
            "n8n-nodes-base.stopAndError",
            "n8n-nodes-base.wait",
            
            # Communication
            "n8n-nodes-base.gmail",
            "n8n-nodes-base.emailSend",
            "n8n-nodes-base.slack",
            "n8n-nodes-base.discord",
            "n8n-nodes-base.telegram",
            
            # File handling
            "n8n-nodes-base.readBinaryFile",
            "n8n-nodes-base.writeBinaryFile",
            "n8n-nodes-base.csvToJson",
            "n8n-nodes-base.jsonToCsv",
            
            # Databases
            "n8n-nodes-base.postgres",
            "n8n-nodes-base.mysql",
            "n8n-nodes-base.sqlite",
            "n8n-nodes-base.redis",
            
            # Cloud services
            "n8n-nodes-base.googleSheets",
            "n8n-nodes-base.googleDrive",
            "n8n-nodes-base.airtable",
            "n8n-nodes-base.notion",
            
            # Development
            "n8n-nodes-base.github",
            "n8n-nodes-base.gitlab",
            
            # Monitoring
            "n8n-nodes-base.pingdom",
            "n8n-nodes-base.healthchecks"
        ]
        
        # Allow custom whitelist from config
        custom_whitelist = self.config.get("PROD_NODE_WHITELIST", [])
        if custom_whitelist:
            return custom_whitelist
        
        return default_whitelist
    
    async def scrape_catalog(self, steps: List[Dict[str, Any]], k: int = 7, budget_tokens: Optional[int] = None) -> Dict[str, Any]:
        """Scrape and filter node catalog based on workflow steps"""
        try:
            # Get cached catalog or fetch fresh
            full_catalog = await self._get_full_catalog()
            
            # Filter and rank nodes for each step
            step_catalogs = {}
            for step in steps:
                step_id = step.get("id", f"step_{len(step_catalogs)}")
                relevant_nodes = await self._filter_nodes_for_step(step, full_catalog, k)
                step_catalogs[step_id] = relevant_nodes
            
            # Calculate token usage estimate
            estimated_tokens = self._estimate_catalog_tokens(step_catalogs)
            if budget_tokens and estimated_tokens > budget_tokens:
                # Reduce catalog size if over budget
                step_catalogs = self._reduce_catalog_size(step_catalogs, budget_tokens)
                estimated_tokens = budget_tokens
            
            return {
                "step_catalogs": step_catalogs,
                "estimated_tokens": estimated_tokens,
                "cache_age": self._get_cache_age(),
                "total_nodes_available": len(full_catalog)
            }
            
        except Exception as e:
            logger.error(f"Catalog scraping failed: {e}")
            raise Exception(f"Failed to scrape catalog: {e}")
    
    async def _get_full_catalog(self) -> List[NodeInfo]:
        """Get full node catalog with caching"""
        cache_key = "full_catalog"
        
        # Check cache first
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_ttl):
                logger.debug("Using cached catalog")
                return cached_data
        
        # Fetch fresh catalog
        logger.info("Fetching fresh node catalog from n8n")
        try:
            node_types = await self.n8n_client.get_node_types()
            catalog = await self._process_node_types(node_types)
            
            # Cache the result
            self.cache[cache_key] = (catalog, datetime.now())
            
            return catalog
            
        except Exception as e:
            logger.error(f"Failed to fetch node catalog: {e}")
            # Return cached data if available, even if expired
            if cache_key in self.cache:
                cached_data, _ = self.cache[cache_key]
                logger.warning("Using expired cache due to fetch failure")
                return cached_data
            raise
    
    async def _process_node_types(self, node_types: Dict[str, Any]) -> List[NodeInfo]:
        """Process raw node types into structured catalog"""
        catalog = []
        
        # Extract nodes from response
        nodes_data = node_types.get("data", {})
        if isinstance(nodes_data, list):
            # Some n8n versions return a list
            for node_data in nodes_data:
                node_info = self._extract_node_info(node_data)
                if node_info and self._is_whitelisted(node_info.id):
                    catalog.append(node_info)
        elif isinstance(nodes_data, dict):
            # Other versions return a dict
            for node_id, node_data in nodes_data.items():
                node_info = self._extract_node_info(node_data, node_id)
                if node_info and self._is_whitelisted(node_info.id):
                    catalog.append(node_info)
        
        logger.info(f"Processed {len(catalog)} whitelisted nodes")
        return catalog
    
    def _extract_node_info(self, node_data: Dict[str, Any], node_id: Optional[str] = None) -> Optional[NodeInfo]:
        """Extract NodeInfo from raw n8n node data"""
        try:
            # Extract basic info
            node_id = node_id or node_data.get("name") or node_data.get("type")
            display_name = node_data.get("displayName", node_id)
            description = node_data.get("description", "")
            
            # Extract category
            category = node_data.get("category", ["Other"])[0] if node_data.get("category") else "Other"
            
            # Extract parameters (simplified)
            properties = node_data.get("properties", [])
            parameters = []
            for prop in properties:
                if isinstance(prop, dict):
                    parameters.append({
                        "name": prop.get("name"),
                        "type": prop.get("type"),
                        "required": prop.get("required", False),
                        "description": prop.get("description", "")
                    })
            
            # Determine capabilities
            triggers = "trigger" in node_id.lower() or category.lower() == "trigger"
            webhooks = "webhook" in node_id.lower()
            
            # Extract input/output info (simplified)
            inputs = ["main"] if not triggers else []
            outputs = ["main"]
            
            # Extract credentials info
            credentials = None
            auth_info = node_data.get("credentials")
            if auth_info and isinstance(auth_info, list) and len(auth_info) > 0:
                credentials = auth_info[0].get("name")
            
            return NodeInfo(
                id=node_id,
                display_name=display_name,
                description=description,
                category=category,
                parameters=parameters,
                inputs=inputs,
                outputs=outputs,
                credentials=credentials,
                webhooks=webhooks,
                triggers=triggers
            )
            
        except Exception as e:
            logger.warning(f"Failed to extract node info: {e}")
            return None
    
    def _is_whitelisted(self, node_id: str) -> bool:
        """Check if node is whitelisted for use"""
        return node_id in self.whitelisted_nodes
    
    async def _filter_nodes_for_step(self, step: Dict[str, Any], catalog: List[NodeInfo], k: int) -> List[CatalogEntry]:
        """Filter and rank nodes relevant to a specific step"""
        step_type = step.get("type", "")
        step_description = step.get("description", "")
        requirements = step.get("requirements", {})
        
        # Score nodes based on relevance
        scored_nodes = []
        for node in catalog:
            score = self._calculate_relevance_score(node, step_type, step_description, requirements)
            if score > 0:
                entry = CatalogEntry(
                    node=node,
                    relevance_score=score,
                    tags=self._generate_tags(node, step),
                    use_cases=self._generate_use_cases(node, step)
                )
                scored_nodes.append(entry)
        
        # Sort by relevance and return top k
        scored_nodes.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored_nodes[:k]
    
    def _calculate_relevance_score(self, node: NodeInfo, step_type: str, description: str, requirements: Dict[str, Any]) -> float:
        """Calculate relevance score for node to step"""
        score = 0.0
        
        # Exact node type match (highest priority)
        required_node = requirements.get("node_type", "")
        if required_node and node.id == required_node:
            return 1.0
        
        # Step type matching
        type_scores = {
            "trigger": 0.9 if node.triggers else 0.1,
            "webhook": 0.9 if node.webhooks else 0.1,
            "action": 0.7 if not node.triggers else 0.2,
            "condition": 0.8 if "if" in node.id or "switch" in node.id else 0.2,
            "transform": 0.8 if "set" in node.id or "code" in node.id or "json" in node.id else 0.3
        }
        score += type_scores.get(step_type.lower(), 0.5)
        
        # Description keyword matching
        keywords = description.lower().split()
        node_text = f"{node.display_name} {node.description} {node.category}".lower()
        
        keyword_matches = sum(1 for keyword in keywords if keyword in node_text)
        if keywords:
            score += 0.3 * (keyword_matches / len(keywords))
        
        # Category bonus
        category_bonuses = {
            "communication": ["email", "slack", "discord", "telegram"],
            "data": ["json", "csv", "database", "transform"],
            "files": ["file", "read", "write", "binary"],
            "api": ["http", "request", "webhook", "api"]
        }
        
        for category, node_keywords in category_bonuses.items():
            if any(kw in node.id.lower() for kw in node_keywords):
                if any(kw in description.lower() for kw in node_keywords):
                    score += 0.2
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _generate_tags(self, node: NodeInfo, step: Dict[str, Any]) -> List[str]:
        """Generate relevant tags for catalog entry"""
        tags = [node.category.lower()]
        
        if node.triggers:
            tags.append("trigger")
        if node.webhooks:
            tags.append("webhook")
        if node.credentials:
            tags.append("authenticated")
        
        # Add step-specific tags
        step_type = step.get("type", "")
        if step_type:
            tags.append(step_type)
        
        return list(set(tags))
    
    def _generate_use_cases(self, node: NodeInfo, step: Dict[str, Any]) -> List[str]:
        """Generate use case examples for catalog entry"""
        use_cases = []
        
        # Common use cases by node type
        use_case_map = {
            "webhook": ["Receive HTTP requests", "API endpoint", "Form submissions"],
            "httpRequest": ["Call external API", "Fetch data", "Send data"],
            "gmail": ["Send emails", "Read inbox", "Email automation"],
            "slack": ["Send messages", "Bot interactions", "Notifications"],
            "set": ["Transform data", "Set variables", "Data mapping"],
            "if": ["Conditional logic", "Route data", "Decision making"],
            "code": ["Custom logic", "Data processing", "Calculations"]
        }
        
        for pattern, cases in use_case_map.items():
            if pattern in node.id.lower():
                use_cases.extend(cases[:2])  # Limit to 2 cases
                break
        
        if not use_cases:
            use_cases = ["Data processing", "Workflow automation"]
        
        return use_cases
    
    def _estimate_catalog_tokens(self, step_catalogs: Dict[str, List[CatalogEntry]]) -> int:
        """Estimate token usage for catalog"""
        total_tokens = 0
        
        for step_id, entries in step_catalogs.items():
            for entry in entries:
                # Rough estimate: node info ~50 tokens
                total_tokens += 50
        
        return total_tokens
    
    def _reduce_catalog_size(self, step_catalogs: Dict[str, List[CatalogEntry]], budget: int) -> Dict[str, List[CatalogEntry]]:
        """Reduce catalog size to fit token budget"""
        # Simple reduction: limit entries per step
        total_entries = sum(len(entries) for entries in step_catalogs.values())
        if total_entries == 0:
            return step_catalogs
        
        entries_per_step = max(1, budget // (total_entries * 50))
        
        reduced_catalogs = {}
        for step_id, entries in step_catalogs.items():
            reduced_catalogs[step_id] = entries[:entries_per_step]
        
        return reduced_catalogs
    
    def _get_cache_age(self) -> Optional[int]:
        """Get age of cached catalog in seconds"""
        cache_key = "full_catalog"
        if cache_key in self.cache:
            _, timestamp = self.cache[cache_key]
            return int((datetime.now() - timestamp).total_seconds())
        return None
    
    async def invalidate_cache(self):
        """Invalidate catalog cache"""
        self.cache.clear()
        logger.info("Catalog cache invalidated")
    
    async def get_node_details(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for specific node"""
        catalog = await self._get_full_catalog()
        
        for node in catalog:
            if node.id == node_id:
                return {
                    "node": asdict(node),
                    "is_whitelisted": self._is_whitelisted(node_id),
                    "security_notes": self._get_security_notes(node)
                }
        
        return None
    
    def _get_security_notes(self, node: NodeInfo) -> List[str]:
        """Get security considerations for node"""
        notes = []
        
        if node.credentials:
            notes.append("Requires authentication credentials")
        
        if "code" in node.id.lower():
            notes.append("Executes custom code - review carefully")
        
        if "http" in node.id.lower():
            notes.append("Makes external HTTP requests")
        
        if node.webhooks:
            notes.append("Exposes webhook endpoint - ensure proper validation")
        
        return notes
