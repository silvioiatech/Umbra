"""
Claude Desktop-style AI Agent
Natural conversation that intelligently uses MCP modules
"""
import logging
import json
import re
import os
from typing import Dict, Any, List, Optional
import asyncio

class ClaudeStyleAgent:
    """AI agent that works like Claude Desktop with MCP integration."""
    
    def __init__(self, config, conversation_manager):
        self.config = config
        self.conversation_manager = conversation_manager
        self.logger = logging.getLogger(__name__)
        
        # Initialize AI provider if available
        self.ai_provider = None
        self.ai_available = False
        
        if config.OPENROUTER_API_KEY:
            self._init_ai_provider()
    
    def _init_ai_provider(self):
        """Initialize OpenRouter for Claude-like conversation."""
        try:
            from ..providers.openrouter import OpenRouterProvider
            self.ai_provider = OpenRouterProvider(self.config)
            self.ai_available = True
            self.logger.info("✅ AI provider ready for Claude Desktop-style conversation")
        except Exception as e:
            self.logger.error(f"❌ AI provider failed: {e}")
            self.ai_available = False
    
    async def process(self, user_id: int, message: str, user_name: str, 
                     modules: Dict, context=None, update=None) -> str:
        """Process message like Claude Desktop - natural conversation with tool use."""
        
        self.logger.info(f"📝 Processing: '{message}' from {user_name}")
        
        # Use AI if available
        if self.ai_available and self.ai_provider:
            return await self._process_with_ai(
                user_id, message, user_name, modules, context, update
            )
        
        # Fallback to pattern matching
        return await self._process_with_patterns(
            message, user_name, modules, context, update
        )
    
    async def _process_with_ai(self, user_id: int, message: str, user_name: str,
                               modules: Dict, context=None, update=None) -> str:
        """Process with AI like Claude Desktop."""
        try:
            # Build module descriptions for AI
            module_descriptions = []
            for module_id, module in modules.items():
                desc = f"{module['name']}: {', '.join(module['capabilities'][:3])}"
                module_descriptions.append(desc)
            
            # System prompt - Claude Desktop style
            system_prompt = f"""You are Umbra, an AI assistant like Claude Desktop with access to specialized MCP modules.

Available modules:
{chr(10).join(module_descriptions)}

Instructions:
- Respond naturally and conversationally
- When users ask for specific tasks, mention you'll use the appropriate module
- Be helpful and proactive
- Keep responses concise but informative
- If asked to do something, explain what you're doing

User is {user_name}."""

            # Get conversation context
            recent = self.conversation_manager.get_recent_messages(user_id, 3)
            
            # Build messages
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add recent context
            for msg in recent[-2:]:  # Last 2 exchanges
                if msg.get('message'):
                    messages.append({"role": "user", "content": msg['message']})
                if msg.get('response'):
                    messages.append({"role": "assistant", "content": msg['response']})
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            # Get AI response
            response = await self.ai_provider.chat_completion(
                messages=messages,
                max_tokens=500,
                temperature=0.8
            )
            
            if response:
                # Check if AI mentions a specific task, try to execute it
                enhanced = await self._execute_mentioned_tasks(
                    response, message, modules, context, update
                )
                return enhanced or response
            
            return "I'm having trouble processing that. Could you rephrase?"
            
        except Exception as e:
            self.logger.error(f"AI processing error: {e}")
            return await self._process_with_patterns(message, user_name, modules, context, update)
    
    async def _execute_mentioned_tasks(self, ai_response: str, original_message: str,
                                      modules: Dict, context=None, update=None) -> Optional[str]:
        """Execute tasks mentioned in AI response."""
        try:
            response_lower = ai_response.lower()
            message_lower = original_message.lower()
            
            # VPS/System tasks
            if any(word in message_lower for word in ['server', 'system', 'cpu', 'memory', 'docker', 'vps']):
                if 'concierge' in modules:
                    result = await self._execute_vps_task(modules['concierge'], message_lower)
                    if result:
                        return f"{ai_response}\n\n{result}"
            
            # Finance tasks
            if any(word in message_lower for word in ['spent', 'expense', 'cost', '$', '€', 'budget']):
                if 'finance' in modules:
                    result = await self._execute_finance_task(modules['finance'], original_message)
                    if result:
                        return f"{ai_response}\n\n{result}"
            
            # Business tasks
            if any(word in message_lower for word in ['client', 'instance', 'project', 'invoice']):
                if 'business' in modules:
                    result = await self._execute_business_task(modules['business'], original_message)
                    if result:
                        return f"{ai_response}\n\n{result}"
            
            # n8n workflow tasks
            if any(word in message_lower for word in ['workflow', 'n8n', 'automation', 'automate']):
                if 'production' in modules:
                    result = await self._execute_workflow_task(modules['production'], original_message)
                    if result:
                        return f"{ai_response}\n\n{result}"
            
            # Content creation tasks
            if any(word in message_lower for word in ['create', 'generate', 'image', 'video', 'document']):
                if 'creator' in modules:
                    result = await self._execute_creator_task(modules['creator'], original_message)
                    if result:
                        return f"{ai_response}\n\n{result}"
            
            return None
            
        except Exception as e:
            self.logger.error(f"Task execution error: {e}")
            return None
    
    async def _execute_vps_task(self, module, message: str) -> Optional[str]:
        """Execute VPS management task."""
        try:
            concierge = module['module']
            
            # System status
            if any(word in message for word in ['status', 'check', 'monitor']):
                return await concierge.get_system_status()
            
            # Docker
            if 'docker' in message:
                return await concierge.get_docker_status()
            
            # CPU/Memory
            if any(word in message for word in ['cpu', 'memory', 'ram']):
                return await concierge.get_resource_usage()
            
            # Logs
            if 'log' in message:
                return await concierge.get_recent_logs()
            
            return None
            
        except Exception as e:
            self.logger.error(f"VPS task error: {e}")
            return f"❌ VPS task failed: {str(e)[:100]}"
    
    async def _execute_finance_task(self, module, message: str) -> Optional[str]:
        """Execute finance task."""
        try:
            finance = module['module']
            
            # Extract amount
            amount_match = re.search(r'(\d+(?:\.\d{2})?)\s*(?:dollars?|\$|euros?|€|chf)', message.lower())
            if amount_match:
                amount = float(amount_match.group(1))
                
                # Extract description
                description = message
                for word in ['spent', 'paid', 'cost', 'expense']:
                    description = description.replace(word, '')
                description = re.sub(r'[\$€]\d+(?:\.\d{2})?', '', description).strip()
                
                return await finance.track_expense(amount, description)
            
            # Budget check
            if 'budget' in message.lower():
                return await finance.get_budget_status()
            
            # Report
            if 'report' in message.lower():
                return await finance.generate_report()
            
            return None
            
        except Exception as e:
            self.logger.error(f"Finance task error: {e}")
            return f"❌ Finance task failed: {str(e)[:100]}"
    
    async def _execute_business_task(self, module, message: str) -> Optional[str]:
        """Execute business task."""
        try:
            business = module['module']
            
            # Create client instance
            if 'create' in message and 'client' in message:
                # Extract client name
                match = re.search(r'for\s+(\w+)', message)
                client_name = match.group(1) if match else "NewClient"
                return await business.create_client_instance(client_name)
            
            # List clients
            if 'list' in message and 'client' in message:
                return await business.list_clients()
            
            # Project status
            if 'project' in message:
                return await business.get_project_status()
            
            return None
            
        except Exception as e:
            self.logger.error(f"Business task error: {e}")
            return f"❌ Business task failed: {str(e)[:100]}"
    
    async def _execute_workflow_task(self, module, message: str) -> Optional[str]:
        """Execute n8n workflow task."""
        try:
            production = module['module']
            
            # Create workflow
            if 'create' in message:
                # Extract workflow type
                workflow_type = "general"
                if 'backup' in message:
                    workflow_type = "backup"
                elif 'monitor' in message:
                    workflow_type = "monitoring"
                elif 'alert' in message:
                    workflow_type = "alert"
                
                return await production.create_workflow(workflow_type, message)
            
            # List workflows
            if 'list' in message:
                return await production.list_workflows()
            
            # Deploy workflow
            if 'deploy' in message:
                return await production.deploy_workflow(message)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Workflow task error: {e}")
            return f"❌ Workflow task failed: {str(e)[:100]}"
    
    async def _execute_creator_task(self, module, message: str) -> Optional[str]:
        """Execute content creation task."""
        try:
            creator = module['module']
            
            # Image generation
            if 'image' in message:
                prompt = message.replace('create', '').replace('generate', '').replace('image', '').strip()
                return await creator.generate_image(prompt)
            
            # Document generation
            if 'document' in message:
                return await creator.generate_document(message)
            
            # Video creation
            if 'video' in message:
                return await creator.create_video(message)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Creator task error: {e}")
            return f"❌ Creation task failed: {str(e)[:100]}"
    
    async def _process_with_patterns(self, message: str, user_name: str, 
                                    modules: Dict, context=None, update=None) -> str:
        """Fallback pattern processing when AI unavailable."""
        message_lower = message.lower().strip()
        
        # Greetings
        if any(word in message_lower for word in ['hello', 'hi', 'hey', 'salut', 'olá']):
            return f"Hi {user_name}! I'm Umbra, your AI assistant. I can help with VPS management, finance tracking, business operations, workflow automation, and content creation. What do you need?"
        
        # Help
        if any(word in message_lower for word in ['help', 'what can you']):
            modules_list = "\n".join([f"• {m['name']}" for m in modules.values()])
            return f"I can help with:\n{modules_list}\n\nJust tell me what you need!"
        
        # System/VPS
        if any(word in message_lower for word in ['system', 'server', 'vps', 'docker', 'cpu', 'memory']):
            return "I can check your system status, monitor resources, manage Docker containers, and more. Let me check that for you..."
        
        # Finance
        if any(word in message_lower for word in ['expense', 'spent', 'budget', 'money']):
            return "I can track your expenses and manage budgets. Tell me the amount and what it was for."
        
        # Business
        if any(word in message_lower for word in ['client', 'project', 'business']):
            return "I can help create client instances, manage projects, and handle business operations. What do you need?"
        
        # Workflows
        if any(word in message_lower for word in ['workflow', 'n8n', 'automation']):
            return "I can create and deploy n8n workflows for automation. What workflow do you need?"
        
        # Creation
        if any(word in message_lower for word in ['create', 'generate', 'image', 'video']):
            return "I can create images, videos, and documents. What would you like me to create?"
        
        # Default
        return f"I understand you need help with something, {user_name}. Could you be more specific? I can help with VPS management, finances, business, workflows, or content creation."
