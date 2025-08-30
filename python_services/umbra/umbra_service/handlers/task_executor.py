"""Task executor for simple tasks that can be handled by the main agent."""

import re
import json
from typing import Dict, Any, Optional
from datetime import datetime

from umbra_shared import (
    OpenRouterClient,
    UmbraLogger,
    Envelope,
    UmbraPayload,
    ModuleResult,
    SupportedLanguage,
)


class TaskExecutor:
    """Execute simple tasks directly in the main agent."""
    
    def __init__(self, openrouter_client: OpenRouterClient):
        self.logger = UmbraLogger("TaskExecutor")
        self.openrouter_client = openrouter_client
    
    async def execute_task(
        self,
        envelope: Envelope[UmbraPayload]
    ) -> ModuleResult[Dict[str, Any]]:
        """Execute a simple task based on the payload action."""
        start_time = datetime.utcnow()
        req_id = envelope.req_id
        action = envelope.payload.action
        message = envelope.payload.message or ""
        
        try:
            self.logger.info("Executing task",
                           req_id=req_id,
                           action=action)
            
            result_data = None
            
            if action == "execute":
                # Determine task type from message
                task_type = self._determine_task_type(message)
                
                if task_type == "calculate":
                    result_data = await self._handle_calculation(message, envelope.lang)
                elif task_type == "translate":
                    result_data = await self._handle_translation(message, envelope.lang)
                elif task_type == "help":
                    result_data = await self._handle_help(message, envelope.lang)
                else:
                    result_data = await self._handle_general_query(message, envelope.lang)
            
            elif action == "clarify":
                result_data = await self._handle_clarification(message, envelope.lang)
            
            else:
                result_data = {
                    "response": f"Unknown action: {action}",
                    "task_type": "error"
                }
            
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            self.logger.info("Task execution completed",
                           req_id=req_id,
                           task_type=result_data.get("task_type"))
            
            return ModuleResult(
                req_id=req_id,
                status="success",
                data=result_data,
                audit={
                    "module": "umbra-task-executor",
                    "duration_ms": duration_ms,
                    "task_type": result_data.get("task_type")
                }
            )
            
        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            self.logger.error("Task execution failed",
                            req_id=req_id,
                            action=action,
                            error=str(e))
            
            return ModuleResult(
                req_id=req_id,
                status="error",
                error={
                    "type": "technical",
                    "code": "EXECUTION_ERROR",
                    "message": f"Failed to execute task: {str(e)}",
                    "retryable": True
                },
                audit={
                    "module": "umbra-task-executor",
                    "duration_ms": duration_ms
                }
            )
    
    def _determine_task_type(self, message: str) -> str:
        """Determine the type of simple task from the message."""
        message_lower = message.lower()
        
        # Math calculations
        if re.search(r"\d+\s*[+\-*/]\s*\d+", message) or \
           any(word in message_lower for word in ["calculate", "compute", "math", "arithmetic"]):
            return "calculate"
        
        # Translation
        if any(word in message_lower for word in ["translate", "translation", "mean in", "say in"]):
            return "translate"
        
        # Help requests
        if any(word in message_lower for word in ["help", "assistance", "what can you", "how to"]):
            return "help"
        
        return "general"
    
    async def _handle_calculation(
        self,
        message: str,
        language: SupportedLanguage
    ) -> Dict[str, Any]:
        """Handle mathematical calculations."""
        try:
            # Extract mathematical expression
            math_pattern = r"(\d+(?:\.\d+)?\s*[+\-*/]\s*\d+(?:\.\d+)?)"
            matches = re.findall(math_pattern, message)
            
            if matches:
                expression = matches[0].replace(" ", "")
                
                # Safe evaluation of simple math expressions
                allowed_chars = set("0123456789+-*/.() ")
                if all(c in allowed_chars for c in expression):
                    try:
                        result = eval(expression)  # Safe for simple math
                        
                        responses = {
                            "EN": f"The result of {expression} is {result}",
                            "FR": f"Le résultat de {expression} est {result}",
                            "PT": f"O resultado de {expression} é {result}"
                        }
                        
                        return {
                            "response": responses.get(language, responses["EN"]),
                            "result": result,
                            "expression": expression,
                            "task_type": "calculation"
                        }
                        
                    except Exception:
                        pass
            
            # Fall back to AI for complex math
            return await self._handle_with_ai(
                message,
                language,
                "You are a helpful math assistant. Solve this mathematical problem step by step."
            )
            
        except Exception as e:
            self.logger.warning("Calculation handling failed", error=str(e))
            
            error_responses = {
                "EN": "I couldn't process that calculation. Please try a simpler expression.",
                "FR": "Je n'ai pas pu traiter ce calcul. Veuillez essayer une expression plus simple.",
                "PT": "Não consegui processar esse cálculo. Tente uma expressão mais simples."
            }
            
            return {
                "response": error_responses.get(language, error_responses["EN"]),
                "task_type": "calculation_error"
            }
    
    async def _handle_translation(
        self,
        message: str,
        language: SupportedLanguage
    ) -> Dict[str, Any]:
        """Handle translation requests."""
        try:
            system_prompts = {
                "EN": "You are a helpful translation assistant. Provide accurate translations and explain the meaning when helpful.",
                "FR": "Vous êtes un assistant de traduction utile. Fournissez des traductions précises et expliquez le sens quand c'est utile.",
                "PT": "Você é um assistente de tradução útil. Forneça traduções precisas e explique o significado quando útil."
            }
            
            result = await self._handle_with_ai(
                message,
                language,
                system_prompts.get(language, system_prompts["EN"])
            )
            
            result["task_type"] = "translation"
            return result
            
        except Exception as e:
            self.logger.warning("Translation handling failed", error=str(e))
            
            error_responses = {
                "EN": "I couldn't process that translation request. Please be more specific about what you'd like to translate.",
                "FR": "Je n'ai pas pu traiter cette demande de traduction. Veuillez être plus précis sur ce que vous voulez traduire.",
                "PT": "Não consegui processar essa solicitação de tradução. Seja mais específico sobre o que você gostaria de traduzir."
            }
            
            return {
                "response": error_responses.get(language, error_responses["EN"]),
                "task_type": "translation_error"
            }
    
    async def _handle_help(
        self,
        message: str,
        language: SupportedLanguage
    ) -> Dict[str, Any]:
        """Handle help requests."""
        help_responses = {
            "EN": """I'm Umbra, your AI assistant! I can help you with:

🏦 **Finance**: Upload invoices/receipts for OCR processing, generate financial reports
🖥️ **VPS Management**: Monitor server status, execute commands, manage Docker containers
👥 **Business**: Manage clients, delegate tasks to other modules
⚙️ **Workflows**: Create n8n automation workflows
🎨 **Media**: Generate images, videos, audio content
🔢 **Simple Tasks**: Math calculations, translations, general questions

Just tell me what you'd like to do, and I'll route your request to the right module or handle it directly!""",
            
            "FR": """Je suis Umbra, votre assistant IA ! Je peux vous aider avec :

🏦 **Finance** : Téléchargez factures/reçus pour traitement OCR, générez des rapports financiers
🖥️ **Gestion VPS** : Surveillez l'état du serveur, exécutez des commandes, gérez les conteneurs Docker
👥 **Business** : Gérez les clients, déléguez des tâches aux autres modules
⚙️ **Workflows** : Créez des workflows d'automatisation n8n
🎨 **Médias** : Générez des images, vidéos, contenu audio
🔢 **Tâches simples** : Calculs mathématiques, traductions, questions générales

Dites-moi simplement ce que vous voulez faire, et je dirigerai votre demande vers le bon module ou la traiterai directement !""",
            
            "PT": """Eu sou Umbra, seu assistente de IA! Posso ajudar você com:

🏦 **Finanças**: Envie faturas/recibos para processamento OCR, gere relatórios financeiros
🖥️ **Gerenciamento VPS**: Monitore status do servidor, execute comandos, gerencie containers Docker
👥 **Negócios**: Gerencie clientes, delegue tarefas para outros módulos
⚙️ **Workflows**: Crie workflows de automação n8n
🎨 **Mídia**: Gere imagens, vídeos, conteúdo de áudio
🔢 **Tarefas simples**: Cálculos matemáticos, traduções, perguntas gerais

Apenas me diga o que você gostaria de fazer, e eu direcionarei sua solicitação para o módulo certo ou lidarei com ela diretamente!"""
        }
        
        return {
            "response": help_responses.get(language, help_responses["EN"]),
            "task_type": "help"
        }
    
    async def _handle_clarification(
        self,
        message: str,
        language: SupportedLanguage
    ) -> Dict[str, Any]:
        """Handle clarification requests."""
        clarification_responses = {
            "EN": "I need more information to help you properly. Could you please be more specific about what you'd like to do?",
            "FR": "J'ai besoin de plus d'informations pour vous aider correctement. Pourriez-vous être plus précis sur ce que vous voulez faire ?",
            "PT": "Preciso de mais informações para ajudá-lo adequadamente. Você poderia ser mais específico sobre o que gostaria de fazer?"
        }
        
        return {
            "response": clarification_responses.get(language, clarification_responses["EN"]),
            "task_type": "clarification"
        }
    
    async def _handle_general_query(
        self,
        message: str,
        language: SupportedLanguage
    ) -> Dict[str, Any]:
        """Handle general queries with AI."""
        try:
            system_prompts = {
                "EN": "You are Umbra, a helpful AI assistant. Provide concise, helpful responses. If the request seems complex or specialized, suggest using specific modules (finance, VPS management, business, workflows, or media generation).",
                "FR": "Vous êtes Umbra, un assistant IA utile. Fournissez des réponses concises et utiles. Si la demande semble complexe ou spécialisée, suggérez d'utiliser des modules spécifiques (finance, gestion VPS, business, workflows, ou génération de médias).",
                "PT": "Você é Umbra, um assistente de IA útil. Forneça respostas concisas e úteis. Se a solicitação parecer complexa ou especializada, sugira usar módulos específicos (finanças, gerenciamento VPS, negócios, workflows, ou geração de mídia)."
            }
            
            result = await self._handle_with_ai(
                message,
                language,
                system_prompts.get(language, system_prompts["EN"])
            )
            
            result["task_type"] = "general_query"
            return result
            
        except Exception as e:
            self.logger.warning("General query handling failed", error=str(e))
            
            error_responses = {
                "EN": "I'm having trouble processing your request right now. Please try again or be more specific.",
                "FR": "J'ai des difficultés à traiter votre demande en ce moment. Veuillez réessayer ou être plus précis.",
                "PT": "Estou tendo problemas para processar sua solicitação agora. Tente novamente ou seja mais específico."
            }
            
            return {
                "response": error_responses.get(language, error_responses["EN"]),
                "task_type": "general_error"
            }
    
    async def _handle_with_ai(
        self,
        message: str,
        language: SupportedLanguage,
        system_prompt: str
    ) -> Dict[str, Any]:
        """Handle request using AI."""
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ]
            
            response = await self.openrouter_client.chat_completion(
                model="openai/gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            ai_response = response.choices[0].message.content
            
            return {
                "response": ai_response,
                "task_type": "ai_response",
                "model_used": "gpt-3.5-turbo",
                "tokens_used": response.usage.total_tokens
            }
            
        except Exception as e:
            self.logger.error("AI handling failed", error=str(e))
            raise