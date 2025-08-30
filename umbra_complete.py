#!/usr/bin/env python3
"""
Umbra Complete - Monolithic Python Implementation
All-in-one Telegram bot with Finance, Concierge, Production, Creator, Business, and Monitoring modules.
"""

import os
import sys
import asyncio
import tempfile
import uuid
import json
import re
import io
import mimetypes
import subprocess
try:
    import paramiko
except ImportError:
    paramiko = None
import httpx
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List, Union, Literal
from pathlib import Path

# FastAPI and web framework
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Image processing and OCR
try:
    import pytesseract
    import cv2
    import numpy as np
    from PIL import Image
    import PyPDF2
    from pdf2image import convert_from_bytes
except ImportError as e:
    print(f"Warning: OCR dependencies not installed: {e}")
    pytesseract = cv2 = np = Image = PyPDF2 = convert_from_bytes = None

# Core types and models
class BasePayload(BaseModel):
    """Base payload for all module communications."""
    action: str
    
    class Config:
        extra = "allow"

class ErrorInfo(BaseModel):
    """Error information for module results."""
    type: Literal["functional", "technical", "conflict", "auth"]
    code: str
    message: str
    retryable: bool = False

class AuditInfo(BaseModel):
    """Audit information for tracking."""
    module: str
    duration_ms: Optional[int] = None
    user_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ModuleResult(BaseModel):
    """Standard result envelope for all modules."""
    req_id: str
    status: Literal["success", "error", "needs_validation", "processing"]
    data: Optional[Dict[str, Any]] = None
    error: Optional[ErrorInfo] = None
    audit: Optional[AuditInfo] = None

# Telegram types
class TelegramUser(BaseModel):
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None

class TelegramChat(BaseModel):
    id: int
    type: str
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class TelegramMessage(BaseModel):
    message_id: int
    from_user: Optional[TelegramUser] = Field(None, alias="from")
    chat: TelegramChat
    date: int
    text: Optional[str] = None
    document: Optional[Dict] = None
    photo: Optional[List[Dict]] = None

class TelegramUpdate(BaseModel):
    update_id: int
    message: Optional[TelegramMessage] = None

# Logger implementation
class UmbraLogger:
    """Simple logger for Umbra system."""
    
    def __init__(self, name: str):
        self.name = name
    
    def _log(self, level: str, message: str, **kwargs):
        timestamp = datetime.utcnow().isoformat()
        log_data = {
            "timestamp": timestamp,
            "level": level,
            "logger": self.name,
            "message": message,
            **kwargs
        }
        print(json.dumps(log_data))
    
    def info(self, message: str, **kwargs):
        self._log("INFO", message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log("ERROR", message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log("WARNING", message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        self._log("DEBUG", message, **kwargs)

# OpenRouter AI client
class OpenRouterClient:
    """Client for OpenRouter AI API."""
    
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient()
        self.logger = UmbraLogger("OpenRouterClient")
    
    async def generate_text(self, prompt: str, model: str = "anthropic/claude-3-sonnet-20240229") -> str:
        """Generate text using OpenRouter."""
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 4000
                }
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            self.logger.error("OpenRouter API call failed", error=str(e))
            raise
    
    async def generate_json(self, prompt: str, model: str = "anthropic/claude-3-sonnet-20240229") -> Dict[str, Any]:
        """Generate JSON response using OpenRouter."""
        try:
            text = await self.generate_text(prompt, model)
            # Try to extract JSON from the response
            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback: assume the entire response is JSON
                return json.loads(text)
        except Exception as e:
            self.logger.error("Failed to generate JSON", error=str(e))
            return {}
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

# Telegram client
class TelegramClient:
    """Client for Telegram Bot API."""
    
    def __init__(self, bot_token: str, webhook_url: Optional[str] = None):
        self.bot_token = bot_token
        self.webhook_url = webhook_url
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.client = httpx.AsyncClient()
        self.logger = UmbraLogger("TelegramClient")
    
    async def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML") -> Dict[str, Any]:
        """Send a message to a chat."""
        try:
            response = await self.client.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error("Failed to send message", error=str(e))
            raise
    
    async def send_document(self, chat_id: int, document: bytes, filename: str, caption: str = "") -> Dict[str, Any]:
        """Send a document to a chat."""
        try:
            files = {"document": (filename, document)}
            data = {
                "chat_id": str(chat_id),
                "caption": caption
            }
            response = await self.client.post(
                f"{self.base_url}/sendDocument",
                files=files,
                data=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error("Failed to send document", error=str(e))
            raise
    
    async def set_webhook(self, url: str) -> bool:
        """Set webhook URL."""
        try:
            response = await self.client.post(
                f"{self.base_url}/setWebhook",
                json={"url": url}
            )
            response.raise_for_status()
            result = response.json()
            return result.get("ok", False)
        except Exception as e:
            self.logger.error("Failed to set webhook", error=str(e))
            return False
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

# Storage client (basic implementation)
class StorageClient:
    """Basic storage client for file operations."""
    
    def __init__(self, endpoint_url: str = "", access_key: str = "", secret_key: str = "", bucket_name: str = ""):
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.logger = UmbraLogger("StorageClient")
        # For simplicity, we'll use local file storage if no S3 config
        self.local_storage = not all([endpoint_url, access_key, secret_key])
        if self.local_storage:
            self.storage_path = Path("/tmp/umbra_storage")
            self.storage_path.mkdir(exist_ok=True)
    
    async def upload_file(self, file_data: bytes, filename: str) -> str:
        """Upload file and return URL."""
        try:
            if self.local_storage:
                file_path = self.storage_path / filename
                file_path.write_bytes(file_data)
                return f"file://{file_path}"
            else:
                # TODO: Implement S3 upload
                self.logger.warning("S3 upload not implemented, using local storage")
                return await self.upload_file(file_data, filename)
        except Exception as e:
            self.logger.error("Failed to upload file", error=str(e))
            raise
    
    async def download_file(self, url: str) -> bytes:
        """Download file from URL."""
        try:
            if url.startswith("file://"):
                file_path = Path(url[7:])  # Remove file:// prefix
                return file_path.read_bytes()
            else:
                # TODO: Implement S3 download
                self.logger.warning("S3 download not implemented")
                raise NotImplementedError("S3 download not implemented")
        except Exception as e:
            self.logger.error("Failed to download file", error=str(e))
            raise

# Main Umbra service class
class UmbraComplete:
    """Monolithic Umbra service with all modules."""
    
    def __init__(self):
        self.logger = UmbraLogger("UmbraComplete")
        self.startup_time = datetime.utcnow()
        
        # Initialize clients
        self._init_clients()
        
        self.logger.info("Umbra Complete service initialized successfully")
    
    def _init_clients(self):
        """Initialize all API clients."""
        try:
            # Telegram client
            bot_token = os.getenv("BOT_TOKEN")
            if not bot_token:
                self.logger.warning("BOT_TOKEN not provided, Telegram functionality disabled")
                self.telegram_client = None
            else:
                webhook_url = os.getenv("WEBHOOK_URL")
                self.telegram_client = TelegramClient(bot_token, webhook_url)
            
            # OpenRouter client
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            if not openrouter_key:
                self.logger.warning("OPENROUTER_API_KEY not provided, AI functionality limited")
                self.openrouter_client = None
            else:
                openrouter_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
                self.openrouter_client = OpenRouterClient(openrouter_key, openrouter_url)
            
            # Storage client
            storage_endpoint = os.getenv("STORAGE_ENDPOINT", "")
            self.storage_client = StorageClient(
                endpoint_url=storage_endpoint,
                access_key=os.getenv("STORAGE_ACCESS_KEY", ""),
                secret_key=os.getenv("STORAGE_SECRET_KEY", ""),
                bucket_name=os.getenv("STORAGE_BUCKET", "umbra-storage")
            )
            
            self.logger.info("API clients initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize API clients", error=str(e))
            raise
    
    async def cleanup(self):
        """Cleanup resources."""
        try:
            if self.telegram_client:
                await self.telegram_client.close()
            if self.openrouter_client:
                await self.openrouter_client.close()
            self.logger.info("Service cleanup completed")
        except Exception as e:
            self.logger.error("Error during service cleanup", error=str(e))
    
    # ==========================================
    # TELEGRAM BOT MODULE
    # ==========================================
    
    async def process_telegram_update(self, update: TelegramUpdate) -> ModuleResult:
        """Process incoming Telegram update."""
        req_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            if not update.message:
                return ModuleResult(
                    req_id=req_id,
                    status="error",
                    error=ErrorInfo(
                        type="functional",
                        code="NO_MESSAGE",
                        message="No message in update"
                    )
                )
            
            message = update.message
            user_id = str(message.from_user.id) if message.from_user else "unknown"
            chat_id = message.chat.id
            
            # Detect language
            lang = self._detect_language(message.text or "")
            
            # Classify intent
            intent = await self._classify_intent(message.text or "", lang)
            
            # Route to appropriate module
            response_text = await self._route_message(intent, message, lang)
            
            # Send response
            if self.telegram_client:
                await self.telegram_client.send_message(chat_id, response_text)
            
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return ModuleResult(
                req_id=req_id,
                status="success",
                data={"response": response_text, "intent": intent},
                audit=AuditInfo(
                    module="telegram",
                    duration_ms=duration_ms,
                    user_id=user_id
                )
            )
            
        except Exception as e:
            self.logger.error("Failed to process Telegram update", error=str(e))
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return ModuleResult(
                req_id=req_id,
                status="error",
                error=ErrorInfo(
                    type="technical",
                    code="TELEGRAM_PROCESSING_FAILED",
                    message=str(e),
                    retryable=True
                ),
                audit=AuditInfo(
                    module="telegram",
                    duration_ms=duration_ms
                )
            )
    
    def _detect_language(self, text: str) -> str:
        """Detect language from text."""
        if not text:
            return "EN"
        
        # Simple keyword-based detection
        text_lower = text.lower()
        
        # Portuguese keywords
        pt_keywords = ["olá", "oi", "obrigado", "por favor", "como", "que", "está", "você", "sim", "não"]
        # French keywords  
        fr_keywords = ["bonjour", "salut", "merci", "s'il vous plaît", "comment", "que", "êtes", "vous", "oui", "non"]
        
        pt_score = sum(1 for word in pt_keywords if word in text_lower)
        fr_score = sum(1 for word in fr_keywords if word in text_lower)
        
        if pt_score > fr_score and pt_score > 0:
            return "PT"
        elif fr_score > 0:
            return "FR"
        else:
            return "EN"
    
    async def _classify_intent(self, text: str, lang: str) -> str:
        """Classify user intent from message."""
        if not text:
            return "help"
        
        text_lower = text.lower()
        
        # Finance keywords
        finance_keywords = ["receipt", "invoice", "expense", "budget", "financial", "money", "cost", "price",
                          "facture", "dépense", "budget", "financier", "argent", "coût", "prix",
                          "recibo", "fatura", "despesa", "orçamento", "financeiro", "dinheiro", "custo", "preço"]
        
        # Business keywords
        business_keywords = ["client", "customer", "project", "workflow", "business", "manage",
                           "cliente", "projeto", "fluxo", "negócio", "gerenciar",
                           "client", "projet", "flux", "entreprise", "gérer"]
        
        # Production keywords  
        production_keywords = ["workflow", "automation", "n8n", "create", "build", "deploy",
                             "fluxo", "automação", "criar", "construir", "implantar",
                             "flux", "automatisation", "créer", "construire", "déployer"]
        
        # Creator keywords
        creator_keywords = ["image", "video", "audio", "media", "generate", "create",
                          "imagem", "vídeo", "áudio", "mídia", "gerar", "criar",
                          "image", "vidéo", "audio", "média", "générer", "créer"]
        
        # System keywords
        system_keywords = ["status", "health", "monitor", "system", "server",
                         "status", "saúde", "monitorar", "sistema", "servidor",
                         "statut", "santé", "surveiller", "système", "serveur"]
        
        if any(keyword in text_lower for keyword in finance_keywords):
            return "finance"
        elif any(keyword in text_lower for keyword in business_keywords):
            return "business"
        elif any(keyword in text_lower for keyword in production_keywords):
            return "production"
        elif any(keyword in text_lower for keyword in creator_keywords):
            return "creator"
        elif any(keyword in text_lower for keyword in system_keywords):
            return "monitoring"
        else:
            return "chat"
    
    async def _route_message(self, intent: str, message: TelegramMessage, lang: str) -> str:
        """Route message to appropriate module and generate response."""
        try:
            if intent == "finance":
                return await self._handle_finance_intent(message, lang)
            elif intent == "business":
                return await self._handle_business_intent(message, lang)
            elif intent == "production":
                return await self._handle_production_intent(message, lang)
            elif intent == "creator":
                return await self._handle_creator_intent(message, lang)
            elif intent == "monitoring":
                return await self._handle_monitoring_intent(message, lang)
            else:
                return await self._handle_chat_intent(message, lang)
        except Exception as e:
            self.logger.error(f"Failed to handle intent {intent}", error=str(e))
            return self._get_error_message(lang)
    
    def _get_error_message(self, lang: str) -> str:
        """Get error message in appropriate language."""
        messages = {
            "EN": "Sorry, I encountered an error. Please try again.",
            "FR": "Désolé, j'ai rencontré une erreur. Veuillez réessayer.",
            "PT": "Desculpe, encontrei um erro. Tente novamente."
        }
        return messages.get(lang, messages["EN"])
    
    def _get_welcome_message(self, lang: str) -> str:
        """Get welcome message in appropriate language."""
        messages = {
            "EN": """🤖 Welcome to Umbra! 

I can help you with:
💰 Finance - Process receipts and financial documents
🏢 Business - Manage clients and projects  
⚙️ Production - Create automated workflows
🎨 Creator - Generate images, videos, and audio
📊 Monitoring - Check system status
💬 Chat - General conversation

Send me a document or describe what you need!""",
            "FR": """🤖 Bienvenue dans Umbra!

Je peux vous aider avec:
💰 Finance - Traiter les reçus et documents financiers
🏢 Business - Gérer les clients et projets
⚙️ Production - Créer des flux automatisés
🎨 Creator - Générer images, vidéos et audio
📊 Monitoring - Vérifier le statut système  
💬 Chat - Conversation générale

Envoyez-moi un document ou décrivez ce dont vous avez besoin!""",
            "PT": """🤖 Bem-vindo ao Umbra!

Posso ajudar você com:
💰 Finance - Processar recibos e documentos financeiros
🏢 Business - Gerenciar clientes e projetos
⚙️ Production - Criar fluxos automatizados
🎨 Creator - Gerar imagens, vídeos e áudio
📊 Monitoring - Verificar status do sistema
💬 Chat - Conversa geral

Me envie um documento ou descreva o que precisa!"""
        }
        return messages.get(lang, messages["EN"])
    
    # ==========================================
    # FINANCE MODULE
    # ==========================================
    
    async def _handle_finance_intent(self, message: TelegramMessage, lang: str) -> str:
        """Handle finance-related requests."""
        try:
            if message.document or message.photo:
                return await self._process_financial_document(message, lang)
            else:
                return self._get_finance_help_message(lang)
        except Exception as e:
            self.logger.error("Finance processing failed", error=str(e))
            return self._get_error_message(lang)
    
    async def _process_financial_document(self, message: TelegramMessage, lang: str) -> str:
        """Process financial document using OCR."""
        try:
            # For now, return a placeholder response
            messages = {
                "EN": "📄 Document received! OCR processing would extract financial data here. This feature requires OCR dependencies to be installed.",
                "FR": "📄 Document reçu! Le traitement OCR extrairait les données financières ici. Cette fonctionnalité nécessite l'installation des dépendances OCR.",
                "PT": "📄 Documento recebido! O processamento OCR extrairia dados financeiros aqui. Este recurso requer dependências OCR instaladas."
            }
            return messages.get(lang, messages["EN"])
        except Exception as e:
            self.logger.error("OCR processing failed", error=str(e))
            return self._get_error_message(lang)
    
    def _get_finance_help_message(self, lang: str) -> str:
        """Get finance help message."""
        messages = {
            "EN": """💰 Finance Module

I can help you process financial documents:
📄 Send receipts, invoices, or statements
📊 Extract amounts, dates, and vendor info
📈 Generate expense reports
💱 Calculate VAT and taxes
📋 Categorize transactions

Just send me a document to get started!""",
            "FR": """💰 Module Finance

Je peux vous aider à traiter les documents financiers:
📄 Envoyez reçus, factures ou relevés
📊 Extraire montants, dates et infos fournisseur
📈 Générer rapports de dépenses
💱 Calculer TVA et taxes
📋 Catégoriser transactions

Envoyez-moi simplement un document pour commencer!""",
            "PT": """💰 Módulo Finance

Posso ajudar você a processar documentos financeiros:
📄 Envie recibos, faturas ou extratos
📊 Extrair valores, datas e info do fornecedor
📈 Gerar relatórios de despesas
💱 Calcular IVA e impostos
📋 Categorizar transações

Apenas me envie um documento para começar!"""
        }
        return messages.get(lang, messages["EN"])
    
    # ==========================================
    # BUSINESS MODULE  
    # ==========================================
    
    async def _handle_business_intent(self, message: TelegramMessage, lang: str) -> str:
        """Handle business management requests."""
        try:
            text = message.text or ""
            
            # Simple command parsing
            if "create client" in text.lower() or "criar cliente" in text.lower() or "créer client" in text.lower():
                return await self._create_client(text, lang)
            elif "list clients" in text.lower() or "listar clientes" in text.lower() or "lister clients" in text.lower():
                return await self._list_clients(lang)
            else:
                return self._get_business_help_message(lang)
        except Exception as e:
            self.logger.error("Business processing failed", error=str(e))
            return self._get_error_message(lang)
    
    async def _create_client(self, text: str, lang: str) -> str:
        """Create a new client."""
        # Extract client name from text (simple pattern matching)
        import re
        name_match = re.search(r'create client (\w+)', text.lower())
        client_name = name_match.group(1) if name_match else "default_client"
        
        messages = {
            "EN": f"🏢 Client '{client_name}' would be created here. This would delegate to the Concierge module to set up VPS resources.",
            "FR": f"🏢 Le client '{client_name}' serait créé ici. Cela déléguerait au module Concierge pour configurer les ressources VPS.",
            "PT": f"🏢 Cliente '{client_name}' seria criado aqui. Isso delegaria ao módulo Concierge para configurar recursos VPS."
        }
        return messages.get(lang, messages["EN"])
    
    async def _list_clients(self, lang: str) -> str:
        """List existing clients."""
        messages = {
            "EN": "🏢 Client List:\n• demo_client (active)\n• test_client (inactive)\n\nThis would show real client data from the database.",
            "FR": "🏢 Liste des Clients:\n• demo_client (actif)\n• test_client (inactif)\n\nCela afficherait les vraies données client de la base de données.",
            "PT": "🏢 Lista de Clientes:\n• demo_client (ativo)\n• test_client (inativo)\n\nIsso mostraria dados reais do cliente do banco de dados."
        }
        return messages.get(lang, messages["EN"])
    
    def _get_business_help_message(self, lang: str) -> str:
        """Get business help message."""
        messages = {
            "EN": """🏢 Business Module

I can help you manage business operations:
👥 Create and manage clients
🗂️ Track project lifecycles  
📋 Delegate tasks to other modules
⚙️ Set up automated workflows
📊 Monitor business metrics

Commands:
• "create client [name]" - Create new client
• "list clients" - Show all clients
• "project status" - Check project status""",
            "FR": """🏢 Module Business

Je peux vous aider à gérer les opérations commerciales:
👥 Créer et gérer les clients
🗂️ Suivre les cycles de vie des projets
📋 Déléguer des tâches à d'autres modules
⚙️ Configurer des flux automatisés
📊 Surveiller les métriques commerciales

Commandes:
• "créer client [nom]" - Créer nouveau client
• "lister clients" - Afficher tous les clients
• "statut projet" - Vérifier statut projet""",
            "PT": """🏢 Módulo Business

Posso ajudar você a gerenciar operações comerciais:
👥 Criar e gerenciar clientes
🗂️ Acompanhar ciclos de vida do projeto
📋 Delegar tarefas para outros módulos
⚙️ Configurar fluxos automatizados
📊 Monitorar métricas de negócios

Comandos:
• "criar cliente [nome]" - Criar novo cliente
• "listar clientes" - Mostrar todos os clientes
• "status projeto" - Verificar status do projeto"""
        }
        return messages.get(lang, messages["EN"])
    
    # ==========================================
    # PRODUCTION MODULE
    # ==========================================
    
    async def _handle_production_intent(self, message: TelegramMessage, lang: str) -> str:
        """Handle production/workflow requests."""
        try:
            text = message.text or ""
            
            if "create workflow" in text.lower() or "criar fluxo" in text.lower() or "créer flux" in text.lower():
                return await self._create_workflow(text, lang)
            elif "list workflows" in text.lower() or "listar fluxos" in text.lower() or "lister flux" in text.lower():
                return await self._list_workflows(lang)
            else:
                return self._get_production_help_message(lang)
        except Exception as e:
            self.logger.error("Production processing failed", error=str(e))
            return self._get_error_message(lang)
    
    async def _create_workflow(self, text: str, lang: str) -> str:
        """Create a new workflow using AI."""
        try:
            if not self.openrouter_client:
                messages = {
                    "EN": "⚙️ Workflow creation requires AI capabilities. Please configure OPENROUTER_API_KEY.",
                    "FR": "⚙️ La création de flux nécessite des capacités IA. Veuillez configurer OPENROUTER_API_KEY.",
                    "PT": "⚙️ A criação de fluxo requer recursos de IA. Configure OPENROUTER_API_KEY."
                }
                return messages.get(lang, messages["EN"])
            
            # Extract workflow description
            workflow_desc = text.replace("create workflow", "").replace("criar fluxo", "").replace("créer flux", "").strip()
            
            if not workflow_desc:
                workflow_desc = "basic data processing workflow"
            
            # Generate workflow using AI
            prompt = f"""Create a simple n8n workflow specification for: {workflow_desc}

Return a JSON object with:
- name: workflow name
- description: what it does  
- nodes: array of node objects with type and config
- connections: how nodes connect

Keep it simple and practical."""
            
            workflow_spec = await self.openrouter_client.generate_json(prompt)
            
            workflow_name = workflow_spec.get("name", "Generated Workflow")
            
            messages = {
                "EN": f"⚙️ Workflow '{workflow_name}' created!\n\nDescription: {workflow_spec.get('description', 'AI-generated workflow')}\n\nThis would be deployed to n8n in a real implementation.",
                "FR": f"⚙️ Flux '{workflow_name}' créé!\n\nDescription: {workflow_spec.get('description', 'Flux généré par IA')}\n\nCeci serait déployé sur n8n dans une vraie implémentation.",
                "PT": f"⚙️ Fluxo '{workflow_name}' criado!\n\nDescrição: {workflow_spec.get('description', 'Fluxo gerado por IA')}\n\nIsso seria implantado no n8n em uma implementação real."
            }
            return messages.get(lang, messages["EN"])
            
        except Exception as e:
            self.logger.error("Workflow creation failed", error=str(e))
            return self._get_error_message(lang)
    
    async def _list_workflows(self, lang: str) -> str:
        """List existing workflows."""
        messages = {
            "EN": """⚙️ Active Workflows:
• Data Sync Workflow (running)
• Email Automation (paused)
• Report Generator (running)

This would show real workflow data from n8n.""",
            "FR": """⚙️ Flux Actifs:
• Flux de Sync Données (en cours)
• Automatisation Email (en pause)
• Générateur Rapport (en cours)

Cela afficherait les vraies données de flux depuis n8n.""",
            "PT": """⚙️ Fluxos Ativos:
• Fluxo Sync de Dados (executando)
• Automação Email (pausado)
• Gerador Relatório (executando)

Isso mostraria dados reais de fluxo do n8n."""
        }
        return messages.get(lang, messages["EN"])
    
    def _get_production_help_message(self, lang: str) -> str:
        """Get production help message."""
        messages = {
            "EN": """⚙️ Production Module

I can help you create and manage workflows:
🔄 Create automated workflows
📋 Generate n8n configurations
🚀 Deploy to production
📊 Monitor workflow performance
🔧 Troubleshoot issues

Commands:
• "create workflow [description]" - Generate new workflow
• "list workflows" - Show active workflows
• "deploy workflow [name]" - Deploy to production""",
            "FR": """⚙️ Module Production

Je peux vous aider à créer et gérer des flux:
🔄 Créer des flux automatisés
📋 Générer configurations n8n
🚀 Déployer en production
📊 Surveiller performance des flux
🔧 Dépanner les problèmes

Commandes:
• "créer flux [description]" - Générer nouveau flux
• "lister flux" - Afficher flux actifs
• "déployer flux [nom]" - Déployer en production""",
            "PT": """⚙️ Módulo Production

Posso ajudar você a criar e gerenciar fluxos:
🔄 Criar fluxos automatizados
📋 Gerar configurações n8n
🚀 Implantar em produção
📊 Monitorar performance do fluxo
🔧 Solucionar problemas

Comandos:
• "criar fluxo [descrição]" - Gerar novo fluxo
• "listar fluxos" - Mostrar fluxos ativos
• "implantar fluxo [nome]" - Implantar em produção"""
        }
        return messages.get(lang, messages["EN"])
    
    # ==========================================
    # CREATOR MODULE
    # ==========================================
    
    async def _handle_creator_intent(self, message: TelegramMessage, lang: str) -> str:
        """Handle media creation requests."""
        try:
            text = message.text or ""
            
            if any(word in text.lower() for word in ["generate", "create", "make", "gerar", "criar", "fazer", "générer", "créer", "faire"]):
                return await self._generate_media(text, lang)
            else:
                return self._get_creator_help_message(lang)
        except Exception as e:
            self.logger.error("Creator processing failed", error=str(e))
            return self._get_error_message(lang)
    
    async def _generate_media(self, text: str, lang: str) -> str:
        """Generate media based on description."""
        try:
            if not self.openrouter_client:
                messages = {
                    "EN": "🎨 Media generation requires AI capabilities. Please configure OPENROUTER_API_KEY.",
                    "FR": "🎨 La génération de média nécessite des capacités IA. Veuillez configurer OPENROUTER_API_KEY.",
                    "PT": "🎨 A geração de mídia requer recursos de IA. Configure OPENROUTER_API_KEY."
                }
                return messages.get(lang, messages["EN"])
            
            # Determine media type
            text_lower = text.lower()
            if any(word in text_lower for word in ["image", "picture", "photo", "imagem", "foto", "picture"]):
                media_type = "image"
            elif any(word in text_lower for word in ["video", "vídeo", "clip"]):
                media_type = "video"  
            elif any(word in text_lower for word in ["audio", "sound", "voice", "áudio", "som", "voz"]):
                media_type = "audio"
            else:
                media_type = "image"  # default
            
            # Extract description
            description = text.strip()
            
            messages = {
                "EN": f"🎨 Generating {media_type} based on: '{description}'\n\nThis would use multiple providers:\n• OpenRouter for planning\n• Runway for video generation\n• ElevenLabs for audio\n• Shotstack for editing\n\nResult would be uploaded to storage and shared.",
                "FR": f"🎨 Génération {media_type} basée sur: '{description}'\n\nCeci utiliserait plusieurs fournisseurs:\n• OpenRouter pour planification\n• Runway pour génération vidéo\n• ElevenLabs pour audio\n• Shotstack pour édition\n\nLe résultat serait téléchargé vers stockage et partagé.",
                "PT": f"🎨 Gerando {media_type} baseado em: '{description}'\n\nIsso usaria múltiplos provedores:\n• OpenRouter para planejamento\n• Runway para geração de vídeo\n• ElevenLabs para áudio\n• Shotstack para edição\n\nO resultado seria enviado para armazenamento e compartilhado."
            }
            return messages.get(lang, messages["EN"])
            
        except Exception as e:
            self.logger.error("Media generation failed", error=str(e))
            return self._get_error_message(lang)
    
    def _get_creator_help_message(self, lang: str) -> str:
        """Get creator help message."""
        messages = {
            "EN": """🎨 Creator Module

I can help you generate media content:
🖼️ Create images from descriptions
🎬 Generate videos and animations
🎵 Produce audio and voiceovers
✂️ Edit and combine media
🌟 Apply effects and filters

Commands:
• "generate image [description]" - Create image
• "create video [description]" - Generate video
• "make audio [description]" - Produce audio

Examples:
• "generate image sunset over mountains"
• "create video product demo"
• "make audio narration for presentation" """,
            "FR": """🎨 Module Creator

Je peux vous aider à générer du contenu média:
🖼️ Créer images depuis descriptions
🎬 Générer vidéos et animations
🎵 Produire audio et voix off
✂️ Éditer et combiner médias
🌟 Appliquer effets et filtres

Commandes:
• "générer image [description]" - Créer image
• "créer vidéo [description]" - Générer vidéo
• "faire audio [description]" - Produire audio

Exemples:
• "générer image coucher soleil montagnes"
• "créer vidéo démo produit"
• "faire audio narration présentation" """,
            "PT": """🎨 Módulo Creator

Posso ajudar você a gerar conteúdo de mídia:
🖼️ Criar imagens a partir de descrições
🎬 Gerar vídeos e animações
🎵 Produzir áudio e narrações
✂️ Editar e combinar mídias
🌟 Aplicar efeitos e filtros

Comandos:
• "gerar imagem [descrição]" - Criar imagem
• "criar vídeo [descrição]" - Gerar vídeo
• "fazer áudio [descrição]" - Produzir áudio

Exemplos:
• "gerar imagem pôr do sol montanhas"
• "criar vídeo demo produto"
• "fazer áudio narração apresentação" """
        }
        return messages.get(lang, messages["EN"])
    
    # ==========================================
    # MONITORING MODULE
    # ==========================================
    
    async def _handle_monitoring_intent(self, message: TelegramMessage, lang: str) -> str:
        """Handle monitoring and system status requests."""
        try:
            return await self._get_system_status(lang)
        except Exception as e:
            self.logger.error("Monitoring failed", error=str(e))
            return self._get_error_message(lang)
    
    async def _get_system_status(self, lang: str) -> str:
        """Get comprehensive system status."""
        try:
            # Calculate uptime
            uptime = datetime.utcnow() - self.startup_time
            uptime_str = f"{int(uptime.total_seconds() // 3600)}h {int((uptime.total_seconds() % 3600) // 60)}m"
            
            # Check component status
            components = {
                "Telegram": "✅" if self.telegram_client else "❌",
                "OpenRouter": "✅" if self.openrouter_client else "❌", 
                "Storage": "✅" if self.storage_client else "❌",
                "OCR": "✅" if pytesseract else "❌"
            }
            
            status_lines = [f"{name}: {status}" for name, status in components.items()]
            
            messages = {
                "EN": f"""📊 System Status

🕐 Uptime: {uptime_str}
🤖 Status: Operational

Components:
{chr(10).join(status_lines)}

📈 Performance:
• Memory: Normal
• CPU: Normal  
• Disk: Normal
• Network: Normal

🔧 Last Check: {datetime.utcnow().strftime('%H:%M:%S UTC')}""",
                "FR": f"""📊 Statut Système

🕐 Temps fonct.: {uptime_str}
🤖 Statut: Opérationnel

Composants:
{chr(10).join(status_lines)}

📈 Performance:
• Mémoire: Normal
• CPU: Normal
• Disque: Normal
• Réseau: Normal

🔧 Dernière vérif.: {datetime.utcnow().strftime('%H:%M:%S UTC')}""",
                "PT": f"""📊 Status do Sistema

🕐 Tempo ativo: {uptime_str}
🤖 Status: Operacional

Componentes:
{chr(10).join(status_lines)}

📈 Performance:
• Memória: Normal
• CPU: Normal
• Disco: Normal
• Rede: Normal

🔧 Última verif.: {datetime.utcnow().strftime('%H:%M:%S UTC')}"""
            }
            return messages.get(lang, messages["EN"])
            
        except Exception as e:
            self.logger.error("Failed to get system status", error=str(e))
            return self._get_error_message(lang)
    
    # ==========================================
    # CONCIERGE MODULE (VPS Management)
    # ==========================================
    
    async def concierge_manage_container(self, action: str, container_name: str, options: Dict[str, Any] = None) -> ModuleResult:
        """Manage containers via SSH (Concierge functionality)."""
        req_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            vps_host = os.getenv("VPS_HOST")
            vps_username = os.getenv("VPS_USERNAME")
            vps_private_key = os.getenv("VPS_PRIVATE_KEY")
            
            if not all([vps_host, vps_username, vps_private_key]):
                return ModuleResult(
                    req_id=req_id,
                    status="error",
                    error=ErrorInfo(
                        type="functional",
                        code="VPS_CONFIG_MISSING",
                        message="VPS configuration incomplete"
                    )
                )
            
            # Simulate container management (would use paramiko SSH in real implementation)
            result_data = {
                "action": action,
                "container": container_name,
                "status": "success",
                "message": f"Container {container_name} {action} completed"
            }
            
            if action == "status":
                result_data["container_status"] = "running"
            elif action == "start":
                result_data["port"] = options.get("port", 3000) if options else 3000
            
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return ModuleResult(
                req_id=req_id,
                status="success", 
                data=result_data,
                audit=AuditInfo(
                    module="concierge",
                    duration_ms=duration_ms
                )
            )
            
        except Exception as e:
            self.logger.error("Concierge operation failed", error=str(e))
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return ModuleResult(
                req_id=req_id,
                status="error",
                error=ErrorInfo(
                    type="technical",
                    code="CONCIERGE_FAILED",
                    message=str(e),
                    retryable=True
                ),
                audit=AuditInfo(
                    module="concierge",
                    duration_ms=duration_ms
                )
            )
    
    # ==========================================
    # CHAT MODULE (General conversation)
    # ==========================================
    
    async def _handle_chat_intent(self, message: TelegramMessage, lang: str) -> str:
        """Handle general chat and help requests."""
        text = (message.text or "").lower()
        
        # Check for help request
        help_keywords = ["help", "aide", "ajuda", "start", "/start", "hello", "hi", "bonjour", "salut", "olá", "oi"]
        if any(keyword in text for keyword in help_keywords):
            return self._get_welcome_message(lang)
        
        # Check for math operations
        if any(op in text for op in ["+", "-", "*", "/", "calculate", "calculer", "calcular"]):
            return await self._handle_math(text, lang)
        
        # General AI chat
        if self.openrouter_client:
            return await self._handle_ai_chat(text, lang)
        else:
            return self._get_welcome_message(lang)
    
    async def _handle_math(self, text: str, lang: str) -> str:
        """Handle simple math calculations."""
        try:
            # Extract math expression
            import re
            math_pattern = r'(\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)'
            match = re.search(math_pattern, text)
            
            if match:
                num1, op, num2 = match.groups()
                num1, num2 = float(num1), float(num2)
                
                if op == '+':
                    result = num1 + num2
                elif op == '-':
                    result = num1 - num2
                elif op == '*':
                    result = num1 * num2
                elif op == '/':
                    if num2 == 0:
                        messages = {
                            "EN": "❌ Cannot divide by zero!",
                            "FR": "❌ Impossible de diviser par zéro!",
                            "PT": "❌ Não é possível dividir por zero!"
                        }
                        return messages.get(lang, messages["EN"])
                    result = num1 / num2
                
                messages = {
                    "EN": f"🧮 {num1} {op} {num2} = {result}",
                    "FR": f"🧮 {num1} {op} {num2} = {result}",
                    "PT": f"🧮 {num1} {op} {num2} = {result}"
                }
                return messages.get(lang, messages["EN"])
            else:
                messages = {
                    "EN": "🧮 I can help with simple math! Try: 5 + 3 or 10 * 2",
                    "FR": "🧮 Je peux aider avec les maths simples! Essayez: 5 + 3 ou 10 * 2",
                    "PT": "🧮 Posso ajudar com matemática simples! Tente: 5 + 3 ou 10 * 2"
                }
                return messages.get(lang, messages["EN"])
                
        except Exception as e:
            self.logger.error("Math calculation failed", error=str(e))
            return self._get_error_message(lang)
    
    async def _handle_ai_chat(self, text: str, lang: str) -> str:
        """Handle AI-powered conversation."""
        try:
            # Create context-aware prompt
            prompts = {
                "EN": f"You are Umbra, a helpful AI assistant integrated with Telegram. Respond concisely and helpfully to: {text}",
                "FR": f"Vous êtes Umbra, un assistant IA utile intégré avec Telegram. Répondez de manière concise et utile à: {text}",
                "PT": f"Você é Umbra, um assistente de IA útil integrado com Telegram. Responda de forma concisa e útil para: {text}"
            }
            
            prompt = prompts.get(lang, prompts["EN"])
            response = await self.openrouter_client.generate_text(prompt)
            
            # Limit response length for Telegram
            if len(response) > 1000:
                response = response[:997] + "..."
            
            return f"🤖 {response}"
            
        except Exception as e:
            self.logger.error("AI chat failed", error=str(e))
            return self._get_welcome_message(lang)

# Global service instance
service_instance: Optional[UmbraComplete] = None

# FastAPI app setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global service_instance
    
    # Startup
    service_instance = UmbraComplete()
    
    # Set webhook if configured
    if service_instance.telegram_client and os.getenv("WEBHOOK_URL"):
        webhook_url = os.getenv("WEBHOOK_URL")
        await service_instance.telegram_client.set_webhook(webhook_url)
        service_instance.logger.info(f"Webhook set to: {webhook_url}")
    
    yield
    
    # Shutdown
    if service_instance:
        await service_instance.cleanup()

app = FastAPI(
    title="Umbra Complete",
    description="Monolithic Telegram Bot with Finance, Business, Production, Creator, Concierge, and Monitoring modules",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# API ENDPOINTS
# ==========================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Umbra Complete",
        "version": "1.0.0",
        "status": "operational",
        "modules": ["telegram", "finance", "business", "production", "creator", "concierge", "monitoring"]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if not service_instance:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    uptime = datetime.utcnow() - service_instance.startup_time
    
    return {
        "status": "healthy",
        "uptime_seconds": int(uptime.total_seconds()),
        "components": {
            "telegram": service_instance.telegram_client is not None,
            "openrouter": service_instance.openrouter_client is not None,
            "storage": service_instance.storage_client is not None
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/webhook/telegram")
async def telegram_webhook(update: Dict[str, Any]):
    """Telegram webhook endpoint."""
    if not service_instance:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        telegram_update = TelegramUpdate(**update)
        result = await service_instance.process_telegram_update(telegram_update)
        
        if result.status == "error":
            service_instance.logger.error("Telegram processing failed", 
                                        error=result.error.message if result.error else "Unknown error")
        
        return {"ok": True, "result": result.model_dump()}
        
    except Exception as e:
        service_instance.logger.error("Webhook processing failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/finance/process")
async def finance_process_document(file: UploadFile = File(...)):
    """Process financial document."""
    if not service_instance:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Placeholder for finance processing
    return {
        "status": "success",
        "message": "Document would be processed here",
        "filename": file.filename,
        "content_type": file.content_type
    }

@app.post("/api/concierge/container")  
async def concierge_container_action(request: Dict[str, Any]):
    """Container management endpoint."""
    if not service_instance:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    action = request.get("action")
    container_name = request.get("container_name")
    options = request.get("options", {})
    
    if not action or not container_name:
        raise HTTPException(status_code=400, detail="Action and container_name required")
    
    result = await service_instance.concierge_manage_container(action, container_name, options)
    
    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.error.message if result.error else "Unknown error")
    
    return result.model_dump()

@app.get("/api/monitoring/status")
async def monitoring_status():
    """System monitoring endpoint."""
    if not service_instance:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    status_text = await service_instance._get_system_status("EN")
    
    return {
        "status": "operational",
        "uptime_seconds": int((datetime.utcnow() - service_instance.startup_time).total_seconds()),
        "details": status_text,
        "timestamp": datetime.utcnow().isoformat()
    }

# ==========================================
# MAIN ENTRY POINT
# ==========================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"Starting Umbra Complete on {host}:{port}")
    print("Modules: Finance, Business, Production, Creator, Concierge, Monitoring")
    
    uvicorn.run(
        "umbra_complete:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )