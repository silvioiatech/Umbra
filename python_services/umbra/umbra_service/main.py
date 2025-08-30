"""Main Umbra service - NLU routing and task delegation."""

import os
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from pydantic import BaseModel

from umbra_shared import (
    UmbraLogger, 
    OpenRouterClient, 
    TelegramClient,
    StorageClient,
    AuthMiddleware,
    ValidationMiddleware,
    AuditMiddleware,
    Envelope,
    UmbraPayload,
    ModuleResult,
    get_request_envelope,
    get_request_user_id,
)

from .routing.intent_classifier import IntentClassifier
from .routing.module_router import ModuleRouter
from .handlers.task_executor import TaskExecutor
from .telegram.telegram_handler import TelegramHandler


class UmbraService:
    """Main Umbra service class."""
    
    def __init__(self):
        self.logger = UmbraLogger("UmbraService")
        
        # Initialize clients
        self._init_clients()
        
        # Initialize handlers
        self.intent_classifier = IntentClassifier(self.openrouter_client)
        self.module_router = ModuleRouter()
        self.task_executor = TaskExecutor(self.openrouter_client)
        self.telegram_handler = TelegramHandler(
            self.telegram_client,
            self.openrouter_client,
            self.intent_classifier,
            self.module_router,
            self.task_executor
        )
        
        self.logger.info("Umbra service initialized successfully")
    
    def _init_clients(self):
        """Initialize API clients."""
        try:
            # Telegram client
            bot_token = os.getenv("BOT_TOKEN")
            if not bot_token:
                raise ValueError("BOT_TOKEN environment variable is required")
            
            webhook_url = os.getenv("WEBHOOK_URL")
            self.telegram_client = TelegramClient(bot_token, webhook_url)
            
            # OpenRouter client
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            if not openrouter_key:
                raise ValueError("OPENROUTER_API_KEY environment variable is required")
            
            openrouter_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
            self.openrouter_client = OpenRouterClient(openrouter_key, openrouter_url)
            
            # Storage client (optional)
            storage_endpoint = os.getenv("STORAGE_ENDPOINT")
            if storage_endpoint:
                self.storage_client = StorageClient(
                    endpoint_url=storage_endpoint,
                    access_key=os.getenv("STORAGE_ACCESS_KEY", ""),
                    secret_key=os.getenv("STORAGE_SECRET_KEY", ""),
                    bucket_name=os.getenv("STORAGE_BUCKET", "umbra-storage")
                )
            else:
                self.storage_client = None
            
            self.logger.info("API clients initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize API clients", error=str(e))
            raise
    
    async def cleanup(self):
        """Cleanup resources."""
        try:
            if hasattr(self, 'telegram_client'):
                await self.telegram_client.close()
            if hasattr(self, 'openrouter_client'):
                await self.openrouter_client.close()
            self.logger.info("Service cleanup completed")
        except Exception as e:
            self.logger.error("Error during service cleanup", error=str(e))


# Global service instance
service_instance: Optional[UmbraService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global service_instance
    
    # Startup
    service_instance = UmbraService()
    yield
    
    # Shutdown
    if service_instance:
        await service_instance.cleanup()


# Create FastAPI app
app = FastAPI(
    title="Umbra Main Agent",
    description="Entry point, NLU routing and simple task execution",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize middleware
auth_middleware = AuthMiddleware()
validation_middleware = ValidationMiddleware()
audit_middleware = AuditMiddleware()

# Security
security = HTTPBearer(auto_error=False)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Umbra Main Agent",
        "version": "1.0.0",
        "status": "running",
        "timestamp": "2024-01-01T00:00:00Z"
    }


@app.get("/health")
@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "umbra",
        "timestamp": "2024-01-01T00:00:00Z"
    }


@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    telegram_validated: bool = Depends(
        auth_middleware.validate_telegram_webhook(os.getenv("TELEGRAM_WEBHOOK_SECRET"))
    )
):
    """Handle Telegram webhook updates."""
    try:
        body = await request.json()
        
        if not service_instance:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not initialized"
            )
        
        # Process update
        result = await service_instance.telegram_handler.handle_update(body)
        
        return {"status": "ok", "result": result}
        
    except Exception as e:
        service_instance.logger.error("Error processing Telegram webhook", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.post("/api/v1/classify")
async def classify_intent(
    envelope: Dict[str, Any],
    auth_validated: bool = Depends(
        auth_middleware.validate_internal_auth(os.getenv("UMBRA_API_KEY"))
    ),
    envelope_validated: Dict = Depends(validation_middleware.validate_envelope()),
    payload_validated: Dict = Depends(validation_middleware.validate_payload("umbra")),
    audit_logged: bool = Depends(audit_middleware.log_envelope_communication())
):
    """Classify user intent."""
    try:
        if not service_instance:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not initialized"
            )
        
        # Parse envelope
        envelope_obj = Envelope[UmbraPayload](**envelope)
        
        # Classify intent
        result = await service_instance.intent_classifier.classify_intent(envelope_obj)
        
        return result.model_dump()
        
    except Exception as e:
        service_instance.logger.error("Error classifying intent", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Classification error"
        )


@app.post("/api/v1/route")
async def route_to_module(
    envelope: Dict[str, Any],
    auth_validated: bool = Depends(
        auth_middleware.validate_internal_auth(os.getenv("UMBRA_API_KEY"))
    ),
    envelope_validated: Dict = Depends(validation_middleware.validate_envelope()),
    payload_validated: Dict = Depends(validation_middleware.validate_payload("umbra")),
    audit_logged: bool = Depends(audit_middleware.log_envelope_communication())
):
    """Route request to appropriate module."""
    try:
        if not service_instance:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not initialized"
            )
        
        # Parse envelope
        envelope_obj = Envelope[UmbraPayload](**envelope)
        
        # Route to module
        result = await service_instance.module_router.route_to_module(envelope_obj)
        
        return result.model_dump()
        
    except Exception as e:
        service_instance.logger.error("Error routing to module", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Routing error"
        )


@app.post("/api/v1/execute")
async def execute_task(
    envelope: Dict[str, Any],
    auth_validated: bool = Depends(
        auth_middleware.validate_internal_auth(os.getenv("UMBRA_API_KEY"))
    ),
    envelope_validated: Dict = Depends(validation_middleware.validate_envelope()),
    payload_validated: Dict = Depends(validation_middleware.validate_payload("umbra")),
    audit_logged: bool = Depends(audit_middleware.log_envelope_communication())
):
    """Execute simple task directly."""
    try:
        if not service_instance:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not initialized"
            )
        
        # Parse envelope
        envelope_obj = Envelope[UmbraPayload](**envelope)
        
        # Execute task
        result = await service_instance.task_executor.execute_task(envelope_obj)
        
        return result.model_dump()
        
    except Exception as e:
        service_instance.logger.error("Error executing task", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Execution error"
        )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)