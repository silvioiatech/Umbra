"""Umbra shared utilities and types."""

from .types import (
    # Base types
    BasePayload,
    Envelope,
    ModuleRequest,
    ModuleResult,
    ErrorInfo,
    AuditInfo,
    ValidationToken,
    
    # Type aliases
    SupportedLanguage,
    Priority,
    ErrorType,
    ModuleStatus,
    
    # Module-specific payloads
    UmbraPayload,
    FinancePayload,
    ConciergePayload,
    BusinessPayload,
    ProductionPayload,
    CreatorPayload,
    ModulePayload,
    
    # Result types
    FinanceResult,
    BusinessResult,
    ConciergeResult,
    ProductionResult,
    CreatorResult,
)

from .logger import UmbraLogger, get_logger, setup_logger

from .retry import RetryUtils, RetryConfig, retry_async, retry_sync

from .openrouter_client import (
    OpenRouterClient,
    ChatMessage,
    ChatCompletionRequest,
    ChatCompletionResponse,
)

from .telegram_client import (
    TelegramClient,
    TelegramUpdate,
    TelegramMessage,
    TelegramUser,
    TelegramChat,
    TelegramDocument,
    TelegramPhoto,
    SendMessageOptions,
    SendDocumentOptions,
)

from .storage_client import StorageClient

from .middleware import (
    AuthMiddleware,
    ValidationMiddleware,
    AuditMiddleware,
    get_request_user_id,
    get_request_envelope,
)

__version__ = "1.0.0"

__all__ = [
    # Types
    "BasePayload",
    "Envelope", 
    "ModuleRequest",
    "ModuleResult",
    "ErrorInfo",
    "AuditInfo",
    "ValidationToken",
    "SupportedLanguage",
    "Priority", 
    "ErrorType",
    "ModuleStatus",
    "UmbraPayload",
    "FinancePayload",
    "ConciergePayload", 
    "BusinessPayload",
    "ProductionPayload",
    "CreatorPayload",
    "ModulePayload",
    "FinanceResult",
    "BusinessResult",
    "ConciergeResult",
    "ProductionResult", 
    "CreatorResult",
    
    # Logger
    "UmbraLogger",
    "get_logger",
    "setup_logger",
    
    # Retry
    "RetryUtils",
    "RetryConfig", 
    "retry_async",
    "retry_sync",
    
    # Clients
    "OpenRouterClient",
    "ChatMessage",
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "TelegramClient",
    "TelegramUpdate",
    "TelegramMessage", 
    "TelegramUser",
    "TelegramChat",
    "TelegramDocument",
    "TelegramPhoto",
    "SendMessageOptions",
    "SendDocumentOptions",
    "StorageClient",
    
    # Middleware
    "AuthMiddleware",
    "ValidationMiddleware", 
    "AuditMiddleware",
    "get_request_user_id",
    "get_request_envelope",
]