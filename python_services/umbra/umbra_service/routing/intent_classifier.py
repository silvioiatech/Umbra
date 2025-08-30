"""Intent classification for Umbra requests."""

import re
from typing import Dict, List, Any, Optional
from datetime import datetime

from umbra_shared import (
    OpenRouterClient,
    UmbraLogger,
    Envelope,
    UmbraPayload,
    ModuleResult,
    SupportedLanguage,
)


class IntentClassificationResult:
    """Result of intent classification."""
    
    def __init__(
        self,
        intent: str,
        confidence: float,
        target_module: str,
        parameters: Optional[Dict[str, Any]] = None,
        requires_clarification: bool = False
    ):
        self.intent = intent
        self.confidence = confidence
        self.target_module = target_module
        self.parameters = parameters or {}
        self.requires_clarification = requires_clarification


class IntentClassifier:
    """Classify user intents for routing to appropriate modules."""
    
    def __init__(self, openrouter_client: OpenRouterClient):
        self.logger = UmbraLogger("IntentClassifier")
        self.openrouter_client = openrouter_client
        
        # Intent patterns for quick classification
        self.intent_patterns = {
            "finance_ocr": [
                r"(?:extract|ocr|scan|read|process).*(?:document|invoice|receipt|bill|statement)",
                r"(?:upload|send).*(?:invoice|receipt|bill|document)",
                r"(?:analyze|parse).*(?:financial|invoice|receipt)"
            ],
            "finance_report": [
                r"(?:generate|create|make).*(?:report|summary|analysis)",
                r"(?:vat|tax|budget).*(?:report|summary)",
                r"(?:financial|expense).*(?:report|analysis)"
            ],
            "vps_monitor": [
                r"(?:check|show|display).*(?:status|health|system|server)",
                r"(?:monitor|monitoring).*(?:system|server|vps)",
                r"(?:cpu|memory|disk|uptime)"
            ],
            "vps_execute": [
                r"(?:run|execute|start|stop|restart).*(?:command|script|service|container)",
                r"(?:docker|container).*(?:start|stop|restart|remove)",
                r"(?:deploy|update|manage).*(?:service|application)"
            ],
            "client_manage": [
                r"(?:create|add|new).*(?:client|customer|account)",
                r"(?:remove|delete).*(?:client|customer|account)",
                r"(?:list|show).*(?:clients|customers|accounts)"
            ],
            "workflow_create": [
                r"(?:create|build|make).*(?:workflow|automation|process)",
                r"(?:n8n|workflow).*(?:create|build)",
                r"(?:automate|automation)"
            ],
            "media_generate": [
                r"(?:generate|create|make).*(?:image|video|audio|media)",
                r"(?:ai|artificial intelligence).*(?:generate|create)",
                r"(?:text to|convert to).*(?:image|video|audio)"
            ],
            "simple_calculate": [
                r"(?:calculate|compute|math|arithmetic)",
                r"(?:\d+\s*[+\-*/]\s*\d+)",
                r"(?:what is|what's|whats).*(?:\d+.*\d+)"
            ],
            "simple_translate": [
                r"(?:translate|translation).*(?:to|into)",
                r"(?:french|english|portuguese).*(?:translation|translate)",
                r"(?:what does.*mean in|how do you say.*in)"
            ],
            "simple_help": [
                r"(?:help|assistance|support)",
                r"(?:what can you|what do you)",
                r"(?:how to|how do i|how can i)"
            ]
        }
        
        # Module mapping
        self.intent_to_module = {
            "finance_ocr": "finance",
            "finance_report": "finance",
            "vps_monitor": "concierge",
            "vps_execute": "concierge",
            "client_manage": "business",
            "workflow_create": "production",
            "media_generate": "creator",
            "simple_calculate": "umbra",
            "simple_translate": "umbra",
            "simple_help": "umbra"
        }
    
    async def classify_intent(
        self,
        envelope: Envelope[UmbraPayload]
    ) -> ModuleResult[IntentClassificationResult]:
        """Classify user intent from message."""
        start_time = datetime.utcnow()
        req_id = envelope.req_id
        
        try:
            message = envelope.payload.message or ""
            language = envelope.lang
            
            self.logger.debug("Classifying intent",
                            req_id=req_id,
                            message_length=len(message),
                            language=language)
            
            # First try pattern matching for fast classification
            pattern_result = self._classify_with_patterns(message)
            
            if pattern_result and pattern_result.confidence > 0.7:
                self.logger.info("Intent classified with patterns",
                               req_id=req_id,
                               intent=pattern_result.intent,
                               confidence=pattern_result.confidence)
                
                duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                return ModuleResult(
                    req_id=req_id,
                    status="success",
                    data=pattern_result,
                    audit={
                        "module": "umbra-intent-classifier",
                        "duration_ms": duration_ms,
                        "provider": "pattern_matching"
                    }
                )
            
            # Fall back to AI classification
            ai_result = await self._classify_with_ai(message, language)
            
            self.logger.info("Intent classified with AI",
                           req_id=req_id,
                           intent=ai_result.intent,
                           confidence=ai_result.confidence)
            
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return ModuleResult(
                req_id=req_id,
                status="success",
                data=ai_result,
                audit={
                    "module": "umbra-intent-classifier",
                    "duration_ms": duration_ms,
                    "provider": "openrouter_ai"
                }
            )
            
        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            self.logger.error("Intent classification failed",
                            req_id=req_id,
                            error=str(e))
            
            return ModuleResult(
                req_id=req_id,
                status="error",
                error={
                    "type": "technical",
                    "code": "CLASSIFICATION_ERROR",
                    "message": f"Failed to classify intent: {str(e)}",
                    "retryable": True
                },
                audit={
                    "module": "umbra-intent-classifier",
                    "duration_ms": duration_ms
                }
            )
    
    def _classify_with_patterns(self, message: str) -> Optional[IntentClassificationResult]:
        """Classify intent using regex patterns."""
        message_lower = message.lower()
        best_match = None
        best_confidence = 0.0
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    # Calculate confidence based on pattern strength
                    confidence = 0.8  # Base confidence for pattern match
                    
                    # Boost confidence for exact keyword matches
                    if any(keyword in message_lower for keyword in ["invoice", "receipt", "document", "workflow"]):
                        confidence += 0.1
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = intent
        
        if best_match:
            target_module = self.intent_to_module.get(best_match, "umbra")
            return IntentClassificationResult(
                intent=best_match,
                confidence=best_confidence,
                target_module=target_module,
                requires_clarification=best_confidence < 0.8
            )
        
        return None
    
    async def _classify_with_ai(
        self,
        message: str,
        language: SupportedLanguage
    ) -> IntentClassificationResult:
        """Classify intent using AI."""
        try:
            available_modules = ["finance", "concierge", "business", "production", "creator"]
            
            classification_result = await self.openrouter_client.classify_intent(
                message=message,
                language=language,
                available_modules=available_modules
            )
            
            intent = classification_result.get("intent", "unclear_request")
            target_module = classification_result.get("target_module", "umbra")
            confidence = float(classification_result.get("confidence", 0.5))
            
            return IntentClassificationResult(
                intent=intent,
                confidence=confidence,
                target_module=target_module,
                requires_clarification=confidence < 0.7
            )
            
        except Exception as e:
            self.logger.warning("AI classification failed, using fallback", error=str(e))
            
            return IntentClassificationResult(
                intent="unclear_request",
                confidence=0.1,
                target_module="umbra",
                requires_clarification=True
            )
    
    def get_clarification_prompts(
        self,
        intent: str,
        language: SupportedLanguage
    ) -> Dict[str, str]:
        """Get clarification prompts for unclear intents."""
        prompts = {
            "EN": {
                "finance_unclear": "I can help with financial documents. Are you trying to upload an invoice/receipt, or generate a financial report?",
                "vps_unclear": "I can help with VPS management. Do you want to check system status or execute a command?",
                "workflow_unclear": "I can help create workflows. What kind of automation are you looking to build?",
                "general_unclear": "I can help with finance, VPS management, business operations, workflows, or media generation. What would you like to do?"
            },
            "FR": {
                "finance_unclear": "Je peux vous aider avec les documents financiers. Essayez-vous de télécharger une facture/reçu, ou générer un rapport financier ?",
                "vps_unclear": "Je peux vous aider avec la gestion VPS. Voulez-vous vérifier l'état du système ou exécuter une commande ?",
                "workflow_unclear": "Je peux vous aider à créer des workflows. Quel type d'automatisation voulez-vous construire ?",
                "general_unclear": "Je peux vous aider avec les finances, la gestion VPS, les opérations commerciales, les workflows, ou la génération de médias. Que voulez-vous faire ?"
            },
            "PT": {
                "finance_unclear": "Posso ajudar com documentos financeiros. Você está tentando enviar uma fatura/recibo, ou gerar um relatório financeiro?",
                "vps_unclear": "Posso ajudar com gerenciamento VPS. Você quer verificar o status do sistema ou executar um comando?",
                "workflow_unclear": "Posso ajudar a criar workflows. Que tipo de automação você quer construir?",
                "general_unclear": "Posso ajudar com finanças, gerenciamento VPS, operações comerciais, workflows, ou geração de mídia. O que você gostaria de fazer?"
            }
        }
        
        return prompts.get(language, prompts["EN"])