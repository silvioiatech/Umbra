"""OpenRouter AI client for Umbra services."""

import httpx
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from .logger import UmbraLogger
from .retry import RetryUtils


class ChatMessage(BaseModel):
    """Chat message for OpenRouter API."""
    role: str  # 'user', 'assistant', 'system'
    content: str


class ChatCompletionRequest(BaseModel):
    """Chat completion request structure."""
    model: str
    messages: List[ChatMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: Optional[bool] = False


class UsageInfo(BaseModel):
    """Token usage information."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Choice(BaseModel):
    """Response choice from OpenRouter."""
    index: int
    message: ChatMessage
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    """Chat completion response structure."""
    id: str
    object: str
    created: int
    model: str
    choices: List[Choice]
    usage: UsageInfo


class OpenRouterClient:
    """Client for OpenRouter AI API."""
    
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.logger = UmbraLogger("OpenRouterClient")
        self.retry_utils = RetryUtils()
        
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://umbra.ai",
                "X-Title": "Umbra Bot System"
            },
            timeout=60.0
        )
    
    async def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> ChatCompletionResponse:
        """Create a chat completion."""
        try:
            # Convert messages to ChatMessage objects
            chat_messages = [ChatMessage(**msg) for msg in messages]
            
            request_data = ChatCompletionRequest(
                model=model,
                messages=chat_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            
            self.logger.debug("Sending chat completion request", 
                            model=model, 
                            message_count=len(messages))
            
            response = await self.client.post(
                "/chat/completions",
                json=request_data.model_dump(exclude_none=True)
            )
            response.raise_for_status()
            
            result = ChatCompletionResponse(**response.json())
            
            self.logger.info("Chat completion successful",
                           model=model,
                           tokens_used=result.usage.total_tokens,
                           finish_reason=result.choices[0].finish_reason if result.choices else None)
            
            return result
            
        except httpx.HTTPStatusError as e:
            self.logger.error("OpenRouter API error", 
                            status_code=e.response.status_code,
                            error=str(e))
            raise
        except Exception as e:
            self.logger.error("Unexpected error in chat completion", error=str(e))
            raise
    
    async def classify_intent(
        self,
        message: str,
        language: str = "EN",
        available_modules: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Classify user intent using AI."""
        try:
            modules_list = available_modules or [
                "finance", "concierge", "business", "production", "creator"
            ]
            
            system_prompt = f"""You are an intent classifier for the Umbra bot system.
Available modules: {', '.join(modules_list)}

Classify the user's intent and determine which module should handle it.
Return a JSON object with:
- intent: brief description of what the user wants
- target_module: which module should handle this (one of the available modules, or 'umbra' for simple tasks)
- confidence: float between 0 and 1
- reasoning: brief explanation

Language: {language}"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ]
            
            response = await self.chat_completion(
                model="openai/gpt-3.5-turbo",
                messages=messages,
                temperature=0.1,
                max_tokens=150
            )
            
            # Parse the JSON response
            import json
            result = json.loads(response.choices[0].message.content)
            
            return result
            
        except Exception as e:
            self.logger.error("Intent classification failed", error=str(e))
            # Return fallback classification
            return {
                "intent": "unclear_request",
                "target_module": "umbra",
                "confidence": 0.1,
                "reasoning": "Classification failed, defaulting to main agent"
            }
    
    async def extract_document_data(
        self,
        image_url: str,
        document_type: str = "invoice"
    ) -> Dict[str, Any]:
        """Extract data from document image using vision models."""
        try:
            system_prompt = f"""You are a document data extraction AI. 
Extract structured data from this {document_type} image.
Return a JSON object with relevant fields like vendor, amount, date, etc."""
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": system_prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ]
            
            response = await self.chat_completion(
                model="openai/gpt-4-vision-preview",
                messages=messages,
                max_tokens=500
            )
            
            # Parse the JSON response
            import json
            result = json.loads(response.choices[0].message.content)
            
            return result
            
        except Exception as e:
            self.logger.error("Document extraction failed", error=str(e))
            return {"error": "Extraction failed", "raw_response": ""}
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()