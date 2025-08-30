"""Telegram bot handler for Umbra."""

import os
from typing import Dict, Any, Optional
from datetime import datetime

from umbra_shared import (
    TelegramClient,
    OpenRouterClient,
    UmbraLogger,
    TelegramUpdate,
    TelegramMessage,
    Envelope,
    UmbraPayload,
    SupportedLanguage,
)

from ..routing.intent_classifier import IntentClassifier
from ..routing.module_router import ModuleRouter
from ..handlers.task_executor import TaskExecutor


class TelegramHandler:
    """Handle Telegram bot interactions."""
    
    def __init__(
        self,
        telegram_client: TelegramClient,
        openrouter_client: OpenRouterClient,
        intent_classifier: IntentClassifier,
        module_router: ModuleRouter,
        task_executor: TaskExecutor
    ):
        self.telegram_client = telegram_client
        self.openrouter_client = openrouter_client
        self.intent_classifier = intent_classifier
        self.module_router = module_router
        self.task_executor = task_executor
        self.logger = UmbraLogger("TelegramHandler")
        
        # Language detection
        self.language_map = {
            "en": "EN",
            "fr": "FR", 
            "pt": "PT",
            "pt-br": "PT",
            "pt-pt": "PT"
        }
    
    async def handle_update(self, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming Telegram update."""
        try:
            update = self.telegram_client.parse_update(update_data)
            
            if not update.message:
                return {"status": "ignored", "reason": "no_message"}
            
            message = update.message
            
            self.logger.info("Processing Telegram message",
                           message_id=message.message_id,
                           user_id=message.from_user.id if message.from_user else None,
                           chat_id=message.chat.id)
            
            # Process the message
            result = await self._process_message(message)
            
            return {"status": "processed", "result": result}
            
        except Exception as e:
            self.logger.error("Error handling Telegram update", error=str(e))
            return {"status": "error", "error": str(e)}
    
    async def _process_message(self, message: TelegramMessage) -> Dict[str, Any]:
        """Process a Telegram message."""
        try:
            # Extract message info
            user_id = str(message.from_user.id) if message.from_user else "unknown"
            chat_id = message.chat.id
            text_content = message.text or message.caption or ""
            
            # Detect language
            language = self._detect_language(message)
            
            # Handle documents/photos
            if message.document or message.photo:
                return await self._handle_media_message(message, user_id, language)
            
            # Handle text message
            if text_content:
                return await self._handle_text_message(text_content, user_id, chat_id, language)
            
            # Unknown message type
            await self._send_help_message(chat_id, language)
            return {"type": "help_sent"}
            
        except Exception as e:
            self.logger.error("Error processing message", error=str(e))
            
            # Send error message to user
            error_messages = {
                "EN": "Sorry, I encountered an error processing your message. Please try again.",
                "FR": "Désolé, j'ai rencontré une erreur en traitant votre message. Veuillez réessayer.",
                "PT": "Desculpe, encontrei um erro ao processar sua mensagem. Tente novamente."
            }
            
            language = self._detect_language(message)
            await self.telegram_client.send_message(
                chat_id=message.chat.id,
                text=error_messages.get(language, error_messages["EN"])
            )
            
            return {"type": "error", "error": str(e)}
    
    def _detect_language(self, message: TelegramMessage) -> SupportedLanguage:
        """Detect language from message."""
        if message.from_user and message.from_user.language_code:
            lang_code = message.from_user.language_code.lower()
            return self.language_map.get(lang_code, "EN")
        
        return "EN"  # Default to English
    
    async def _handle_text_message(
        self,
        text: str,
        user_id: str,
        chat_id: int,
        language: SupportedLanguage
    ) -> Dict[str, Any]:
        """Handle text message."""
        try:
            # Create envelope for processing
            envelope = Envelope[UmbraPayload](
                user_id=user_id,
                lang=language,
                payload=UmbraPayload(
                    action="classify",
                    message=text
                )
            )
            
            # Classify intent
            classification_result = await self.intent_classifier.classify_intent(envelope)
            
            if classification_result.status != "success":
                await self._send_error_message(chat_id, language, "classification")
                return {"type": "classification_error"}
            
            classification = classification_result.data
            
            self.logger.info("Intent classified",
                           req_id=envelope.req_id,
                           intent=classification.intent,
                           target_module=classification.target_module,
                           confidence=classification.confidence)
            
            # Handle based on target module
            if classification.target_module == "umbra":
                # Handle locally
                return await self._handle_local_task(envelope, chat_id, language)
            else:
                # Route to appropriate module
                return await self._handle_module_routing(envelope, chat_id, language, classification)
            
        except Exception as e:
            self.logger.error("Error handling text message", error=str(e))
            await self._send_error_message(chat_id, language, "processing")
            return {"type": "error", "error": str(e)}
    
    async def _handle_media_message(
        self,
        message: TelegramMessage,
        user_id: str,
        language: SupportedLanguage
    ) -> Dict[str, Any]:
        """Handle document or photo message."""
        try:
            chat_id = message.chat.id
            
            # Get file info
            file_id = None
            if message.document:
                file_id = message.document.file_id
            elif message.photo:
                # Get the largest photo
                file_id = message.photo[-1].file_id
            
            if not file_id:
                await self._send_error_message(chat_id, language, "file_processing")
                return {"type": "no_file"}
            
            # Get file from Telegram
            file_info = await self.telegram_client.get_file(file_id)
            file_path = file_info.get("file_path")
            
            if not file_path:
                await self._send_error_message(chat_id, language, "file_processing")
                return {"type": "file_error"}
            
            # Create envelope for finance module (OCR processing)
            envelope = Envelope[UmbraPayload](
                user_id=user_id,
                lang=language,
                payload=UmbraPayload(
                    action="route",
                    message=f"Process document: {file_path}",
                    target_module="finance"
                )
            )
            
            # Send to finance module for processing
            processing_message = {
                "EN": "📄 Processing your document... This may take a moment.",
                "FR": "📄 Traitement de votre document... Cela peut prendre un moment.",
                "PT": "📄 Processando seu documento... Isso pode levar um momento."
            }
            
            await self.telegram_client.send_message(
                chat_id=chat_id,
                text=processing_message.get(language, processing_message["EN"])
            )
            
            # Route to finance module
            result = await self.module_router.route_to_module(envelope)
            
            if result.status == "success":
                success_message = {
                    "EN": "✅ Document processed successfully! Check the extracted data.",
                    "FR": "✅ Document traité avec succès ! Vérifiez les données extraites.",
                    "PT": "✅ Documento processado com sucesso! Verifique os dados extraídos."
                }
                
                await self.telegram_client.send_message(
                    chat_id=chat_id,
                    text=success_message.get(language, success_message["EN"])
                )
            else:
                await self._send_error_message(chat_id, language, "document_processing")
            
            return {"type": "document_processed", "result": result.model_dump()}
            
        except Exception as e:
            self.logger.error("Error handling media message", error=str(e))
            await self._send_error_message(chat_id, language, "file_processing")
            return {"type": "error", "error": str(e)}
    
    async def _handle_local_task(
        self,
        envelope: Envelope[UmbraPayload],
        chat_id: int,
        language: SupportedLanguage
    ) -> Dict[str, Any]:
        """Handle task locally (simple tasks)."""
        try:
            # Update envelope for execution
            envelope.payload.action = "execute"
            
            # Execute task
            result = await self.task_executor.execute_task(envelope)
            
            if result.status == "success" and result.data:
                response_text = result.data.get("response", "Task completed")
                
                await self.telegram_client.send_message(
                    chat_id=chat_id,
                    text=response_text,
                    parse_mode="Markdown"
                )
                
                return {"type": "task_executed", "result": result.model_dump()}
            else:
                await self._send_error_message(chat_id, language, "execution")
                return {"type": "execution_error", "result": result.model_dump()}
            
        except Exception as e:
            self.logger.error("Error handling local task", error=str(e))
            await self._send_error_message(chat_id, language, "execution")
            return {"type": "error", "error": str(e)}
    
    async def _handle_module_routing(
        self,
        envelope: Envelope[UmbraPayload],
        chat_id: int,
        language: SupportedLanguage,
        classification
    ) -> Dict[str, Any]:
        """Handle routing to external module."""
        try:
            # Update envelope for routing
            envelope.payload.action = "route"
            envelope.payload.target_module = classification.target_module
            
            # Send processing message
            processing_messages = {
                "EN": f"🔄 Processing your request with {classification.target_module} module...",
                "FR": f"🔄 Traitement de votre demande avec le module {classification.target_module}...",
                "PT": f"🔄 Processando sua solicitação com o módulo {classification.target_module}..."
            }
            
            await self.telegram_client.send_message(
                chat_id=chat_id,
                text=processing_messages.get(language, processing_messages["EN"])
            )
            
            # Route to module
            result = await self.module_router.route_to_module(envelope)
            
            if result.status == "success":
                success_messages = {
                    "EN": "✅ Request processed successfully!",
                    "FR": "✅ Demande traitée avec succès !",
                    "PT": "✅ Solicitação processada com sucesso!"
                }
                
                await self.telegram_client.send_message(
                    chat_id=chat_id,
                    text=success_messages.get(language, success_messages["EN"])
                )
            else:
                await self._send_error_message(chat_id, language, "module_processing")
            
            return {"type": "module_routed", "result": result.model_dump()}
            
        except Exception as e:
            self.logger.error("Error handling module routing", error=str(e))
            await self._send_error_message(chat_id, language, "routing")
            return {"type": "error", "error": str(e)}
    
    async def _send_error_message(
        self,
        chat_id: int,
        language: SupportedLanguage,
        error_type: str
    ):
        """Send appropriate error message to user."""
        error_messages = {
            "EN": {
                "classification": "❌ I couldn't understand your request. Please try rephrasing it.",
                "processing": "❌ There was an error processing your request. Please try again.",
                "execution": "❌ I couldn't complete that task. Please try again or contact support.",
                "file_processing": "❌ I couldn't process that file. Please make sure it's a valid document or image.",
                "document_processing": "❌ Document processing failed. Please try again with a different file.",
                "module_processing": "❌ The specialized module couldn't process your request. Please try again.",
                "routing": "❌ I couldn't route your request to the appropriate module. Please try again."
            },
            "FR": {
                "classification": "❌ Je n'ai pas pu comprendre votre demande. Veuillez la reformuler.",
                "processing": "❌ Il y a eu une erreur lors du traitement de votre demande. Veuillez réessayer.",
                "execution": "❌ Je n'ai pas pu accomplir cette tâche. Veuillez réessayer ou contacter le support.",
                "file_processing": "❌ Je n'ai pas pu traiter ce fichier. Assurez-vous que c'est un document ou une image valide.",
                "document_processing": "❌ Le traitement du document a échoué. Veuillez réessayer avec un autre fichier.",
                "module_processing": "❌ Le module spécialisé n'a pas pu traiter votre demande. Veuillez réessayer.",
                "routing": "❌ Je n'ai pas pu acheminer votre demande vers le module approprié. Veuillez réessayer."
            },
            "PT": {
                "classification": "❌ Não consegui entender sua solicitação. Tente reformular.",
                "processing": "❌ Houve um erro ao processar sua solicitação. Tente novamente.",
                "execution": "❌ Não consegui completar essa tarefa. Tente novamente ou entre em contato com o suporte.",
                "file_processing": "❌ Não consegui processar esse arquivo. Certifique-se de que é um documento ou imagem válida.",
                "document_processing": "❌ O processamento do documento falhou. Tente novamente com um arquivo diferente.",
                "module_processing": "❌ O módulo especializado não conseguiu processar sua solicitação. Tente novamente.",
                "routing": "❌ Não consegui rotear sua solicitação para o módulo apropriado. Tente novamente."
            }
        }
        
        message = error_messages.get(language, error_messages["EN"]).get(
            error_type, 
            error_messages["EN"]["processing"]
        )
        
        await self.telegram_client.send_message(
            chat_id=chat_id,
            text=message
        )
    
    async def _send_help_message(self, chat_id: int, language: SupportedLanguage):
        """Send help message to user."""
        help_messages = {
            "EN": """🤖 **Umbra AI Assistant**

I can help you with:

🏦 **Finance**: Send invoices/receipts for OCR processing
🖥️ **VPS Management**: Monitor servers, execute commands
👥 **Business**: Manage clients and operations  
⚙️ **Workflows**: Create automation workflows
🎨 **Media**: Generate images, videos, audio
🔢 **Simple Tasks**: Math, translations, questions

Just send me a message or document!""",
            
            "FR": """🤖 **Assistant IA Umbra**

Je peux vous aider avec :

🏦 **Finance** : Envoyez factures/reçus pour traitement OCR
🖥️ **Gestion VPS** : Surveillez serveurs, exécutez commandes
👥 **Business** : Gérez clients et opérations
⚙️ **Workflows** : Créez workflows d'automatisation
🎨 **Médias** : Générez images, vidéos, audio
🔢 **Tâches simples** : Math, traductions, questions

Envoyez-moi simplement un message ou document !""",
            
            "PT": """🤖 **Assistente de IA Umbra**

Posso ajudar você com:

🏦 **Finanças**: Envie faturas/recibos para processamento OCR
🖥️ **Gerenciamento VPS**: Monitore servidores, execute comandos
👥 **Negócios**: Gerencie clientes e operações
⚙️ **Workflows**: Crie workflows de automação
🎨 **Mídia**: Gere imagens, vídeos, áudio
🔢 **Tarefas simples**: Matemática, traduções, perguntas

Apenas me envie uma mensagem ou documento!"""
        }
        
        await self.telegram_client.send_message(
            chat_id=chat_id,
            text=help_messages.get(language, help_messages["EN"]),
            parse_mode="Markdown"
        )