"""Core envelope types for Umbra bot system communication."""

from typing import Any, Dict, Generic, Literal, Optional, TypeVar, Union
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

# Type aliases
SupportedLanguage = Literal["EN", "FR", "PT"]
Priority = Literal["normal", "urgent"]
ErrorType = Literal["functional", "technical", "conflict", "auth"]
ModuleStatus = Literal["success", "error", "needs_validation", "processing"]

TPayload = TypeVar("TPayload", bound="BasePayload")


class BasePayload(BaseModel):
    """Base payload interface for all module communications."""
    action: str
    
    class Config:
        extra = "allow"


class ValidationToken(BaseModel):
    """Validation token for critical operations."""
    token: str
    user_id: str
    action: str
    expires_at: datetime
    validated: bool = False


class Envelope(BaseModel, Generic[TPayload]):
    """Core envelope for module communication."""
    req_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    lang: SupportedLanguage
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: TPayload
    meta: Optional[Dict[str, Any]] = None
    
    class Config:
        # Allow for pydantic v2 serialization
        arbitrary_types_allowed = True


class ErrorInfo(BaseModel):
    """Error information for module results."""
    type: ErrorType
    code: str
    message: str
    retryable: bool


class AuditInfo(BaseModel):
    """Audit information for module results."""
    module: str
    duration_ms: int
    provider: Optional[str] = None
    token_usage: Optional[int] = None
    cost_usd: Optional[float] = None


class ModuleResult(BaseModel, Generic[TPayload]):
    """Result wrapper for module responses."""
    req_id: str
    status: ModuleStatus
    data: Optional[TPayload] = None
    error: Optional[ErrorInfo] = None
    audit: Optional[AuditInfo] = None


class ModuleRequest(Envelope[TPayload]):
    """Request envelope for module communication."""
    pass


# Specific payload types for each module
class UmbraPayload(BasePayload):
    """Umbra Main Agent payloads."""
    action: Literal["classify", "route", "execute", "clarify"]
    message: Optional[str] = None
    intent: Optional[str] = None
    confidence: Optional[float] = None
    target_module: Optional[str] = None


class FinancePayload(BasePayload):
    """Finance Module payloads."""
    action: Literal["ocr", "extract", "categorize", "report", "deduplicate"]
    document_url: Optional[str] = None
    document_type: Optional[Literal["invoice", "receipt", "statement", "payroll"]] = None
    report_type: Optional[Literal["budget", "vat", "tax"]] = None
    date_range: Optional[Dict[str, str]] = None


class ConciergePayload(BasePayload):
    """VPS Concierge payloads."""
    action: Literal["monitor", "execute", "validate", "client_management"]
    command: Optional[str] = None
    script: Optional[str] = None
    validation_token: Optional[str] = None
    client_action: Optional[Literal["create", "delete", "list"]] = None
    client_name: Optional[str] = None
    client_port: Optional[int] = None


class BusinessPayload(BasePayload):
    """Business Module payloads."""
    action: Literal["client_lifecycle", "create_client", "delete_client", "delegate_task"]
    client_name: Optional[str] = None
    target_module: Optional[str] = None
    task_data: Optional[Dict[str, Any]] = None


class ProductionPayload(BasePayload):
    """Production Module payloads."""
    action: Literal["create_workflow", "deploy_workflow", "rollback_workflow"]
    workflow_type: Optional[str] = None
    description: Optional[str] = None
    workflow_spec: Optional[Dict[str, Any]] = None
    environment: Optional[str] = None
    workflow_id: Optional[str] = None
    version: Optional[str] = None


class CreatorPayload(BasePayload):
    """Creator Module payloads."""
    action: Literal["generate_text", "generate_image", "generate_video", "generate_audio", "edit_video"]
    provider: Optional[Literal["openrouter", "runway", "shotstack", "elevenlabs"]] = None
    prompt: Optional[str] = None
    media_type: Optional[Literal["text", "image", "video", "audio"]] = None
    parameters: Optional[Dict[str, Any]] = None


# Union type for all module payloads
ModulePayload = Union[
    UmbraPayload,
    FinancePayload,
    ConciergePayload,
    BusinessPayload,
    ProductionPayload,
    CreatorPayload,
]


# Result data types for each module
class FinanceResult(BaseModel):
    """Finance module result data."""
    extracted_data: Optional[Dict[str, Any]] = None
    report_data: Optional[Dict[str, Any]] = None
    anomalies: Optional[list[str]] = None
    raw_text: Optional[str] = None
    storage_key: Optional[str] = None
    document_url: Optional[str] = None
    confidence: Optional[float] = None
    needs_review: Optional[bool] = None


class BusinessResult(BaseModel):
    """Business module result data."""
    client_info: Optional[Dict[str, Any]] = None
    task_result: Optional[Dict[str, Any]] = None
    delegation_status: Optional[str] = None


class ConciergeResult(BaseModel):
    """Concierge module result data."""
    system_status: Optional[Dict[str, Any]] = None
    command_output: Optional[str] = None
    validation_status: Optional[str] = None
    client_status: Optional[Dict[str, Any]] = None


class ProductionResult(BaseModel):
    """Production module result data."""
    workflow_id: Optional[str] = None
    workflow_json: Optional[Dict[str, Any]] = None
    deployment_status: Optional[str] = None
    deployment_url: Optional[str] = None


class CreatorResult(BaseModel):
    """Creator module result data."""
    generated_content: Optional[str] = None
    media_url: Optional[str] = None
    provider_used: Optional[str] = None
    generation_time: Optional[float] = None
    cost_estimate: Optional[float] = None