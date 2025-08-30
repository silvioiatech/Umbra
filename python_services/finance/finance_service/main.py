"""Finance service main module."""

import os
import tempfile
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware

from umbra_shared import (
    UmbraLogger,
    OpenRouterClient,
    StorageClient,
    AuthMiddleware,
    ValidationMiddleware,
    AuditMiddleware,
    Envelope,
    FinancePayload,
    ModuleResult,
    get_request_envelope,
)

from .ocr.ocr_processor import OCRProcessor
from .extraction.finance_extractor import FinanceExtractor
from .reports.report_generator import ReportGenerator


class FinanceService:
    """Finance service for OCR processing and financial document extraction."""
    
    def __init__(self):
        self.logger = UmbraLogger("FinanceService")
        
        # Initialize clients
        self._init_clients()
        
        # Initialize processors
        self.ocr_processor = OCRProcessor(self.openrouter_client)
        self.finance_extractor = FinanceExtractor(self.openrouter_client)
        self.report_generator = ReportGenerator(self.openrouter_client, self.storage_client)
        
        self.logger.info("Finance service initialized successfully")
    
    def _init_clients(self):
        """Initialize API clients."""
        try:
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
                    bucket_name=os.getenv("STORAGE_BUCKET", "umbra-finance-storage")
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
            if hasattr(self, 'openrouter_client'):
                await self.openrouter_client.close()
            self.logger.info("Service cleanup completed")
        except Exception as e:
            self.logger.error("Error during service cleanup", error=str(e))


# Global service instance
service_instance: Optional[FinanceService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global service_instance
    
    # Startup
    service_instance = FinanceService()
    yield
    
    # Shutdown
    if service_instance:
        await service_instance.cleanup()


# Create FastAPI app
app = FastAPI(
    title="Finance Module",
    description="OCR processing and financial document extraction",
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


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Finance Module",
        "version": "1.0.0",
        "status": "running",
        "features": ["OCR", "data_extraction", "financial_reports"]
    }


@app.get("/health")
@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "finance",
        "timestamp": "2024-01-01T00:00:00Z"
    }


@app.post("/api/v1/ocr")
async def process_ocr(
    envelope: Dict[str, Any],
    auth_validated: bool = Depends(
        auth_middleware.validate_internal_auth(os.getenv("UMBRA_API_KEY"))
    ),
    envelope_validated: Dict = Depends(validation_middleware.validate_envelope()),
    payload_validated: Dict = Depends(validation_middleware.validate_payload("finance")),
    audit_logged: bool = Depends(audit_middleware.log_envelope_communication())
):
    """Process OCR on uploaded document."""
    try:
        if not service_instance:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not initialized"
            )
        
        # Parse envelope
        envelope_obj = Envelope[FinancePayload](**envelope)
        
        # Get document URL from payload
        document_url = envelope_obj.payload.document_url
        if not document_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document URL is required for OCR processing"
            )
        
        # For now, we'll simulate document processing
        # In a real implementation, you would download the document from the URL
        mock_document_data = b"Mock document content for OCR processing"
        
        # Process document
        result = await service_instance.ocr_processor.process_document(
            envelope_obj,
            mock_document_data,
            "document.pdf"
        )
        
        return result.model_dump()
        
    except Exception as e:
        service_instance.logger.error("Error processing OCR", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OCR processing error"
        )


@app.post("/api/v1/extract")
async def extract_financial_data(
    envelope: Dict[str, Any],
    auth_validated: bool = Depends(
        auth_middleware.validate_internal_auth(os.getenv("UMBRA_API_KEY"))
    ),
    envelope_validated: Dict = Depends(validation_middleware.validate_envelope()),
    payload_validated: Dict = Depends(validation_middleware.validate_payload("finance")),
    audit_logged: bool = Depends(audit_middleware.log_envelope_communication())
):
    """Extract and categorize financial data."""
    try:
        if not service_instance:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not initialized"
            )
        
        # Parse envelope
        envelope_obj = Envelope[FinancePayload](**envelope)
        
        # Mock raw text for extraction
        mock_text = """
        Invoice #INV-2024-001
        ACME Corp
        Date: 2024-01-15
        Office Supplies: €245.50
        VAT (20%): €49.10
        Total: €294.60
        """
        
        # Extract financial data
        result = await service_instance.finance_extractor.extract_and_categorize(
            envelope_obj,
            mock_text
        )
        
        return result.model_dump()
        
    except Exception as e:
        service_instance.logger.error("Error extracting financial data", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Financial data extraction error"
        )


@app.post("/api/v1/report")
async def generate_report(
    envelope: Dict[str, Any],
    auth_validated: bool = Depends(
        auth_middleware.validate_internal_auth(os.getenv("UMBRA_API_KEY"))
    ),
    envelope_validated: Dict = Depends(validation_middleware.validate_envelope()),
    payload_validated: Dict = Depends(validation_middleware.validate_payload("finance")),
    audit_logged: bool = Depends(audit_middleware.log_envelope_communication())
):
    """Generate financial report."""
    try:
        if not service_instance:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not initialized"
            )
        
        # Parse envelope
        envelope_obj = Envelope[FinancePayload](**envelope)
        
        # Generate report
        result = await service_instance.report_generator.generate_report(envelope_obj)
        
        return result.model_dump()
        
    except Exception as e:
        service_instance.logger.error("Error generating report", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report generation error"
        )


@app.post("/api/v1/categorize")
async def categorize_expense(
    envelope: Dict[str, Any],
    auth_validated: bool = Depends(
        auth_middleware.validate_internal_auth(os.getenv("UMBRA_API_KEY"))
    ),
    envelope_validated: Dict = Depends(validation_middleware.validate_envelope()),
    payload_validated: Dict = Depends(validation_middleware.validate_payload("finance")),
    audit_logged: bool = Depends(audit_middleware.log_envelope_communication())
):
    """Categorize expense."""
    try:
        if not service_instance:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not initialized"
            )
        
        # Parse envelope
        envelope_obj = Envelope[FinancePayload](**envelope)
        
        # Mock text for categorization
        mock_text = "Microsoft Office 365 subscription monthly payment"
        
        # Extract and categorize
        result = await service_instance.finance_extractor.extract_and_categorize(
            envelope_obj,
            mock_text
        )
        
        return result.model_dump()
        
    except Exception as e:
        service_instance.logger.error("Error categorizing expense", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Expense categorization error"
        )


@app.post("/api/v1/deduplicate")
async def deduplicate_transactions(
    envelope: Dict[str, Any],
    auth_validated: bool = Depends(
        auth_middleware.validate_internal_auth(os.getenv("UMBRA_API_KEY"))
    ),
    envelope_validated: Dict = Depends(validation_middleware.validate_envelope()),
    payload_validated: Dict = Depends(validation_middleware.validate_payload("finance")),
    audit_logged: bool = Depends(audit_middleware.log_envelope_communication())
):
    """Deduplicate financial transactions."""
    try:
        if not service_instance:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not initialized"
            )
        
        # Parse envelope
        envelope_obj = Envelope[FinancePayload](**envelope)
        
        # Mock deduplication result
        from umbra_shared import FinanceResult
        
        result_data = FinanceResult(
            extracted_data={
                "duplicates_found": 2,
                "unique_transactions": 15,
                "total_processed": 17,
                "confidence": 0.95
            },
            confidence=0.95,
            needs_review=False
        )
        
        from umbra_shared import ModuleResult
        result = ModuleResult(
            req_id=envelope_obj.req_id,
            status="success",
            data=result_data,
            audit={
                "module": "finance-deduplication",
                "duration_ms": 150,
                "transactions_processed": 17
            }
        )
        
        return result.model_dump()
        
    except Exception as e:
        service_instance.logger.error("Error deduplicating transactions", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transaction deduplication error"
        )


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    language: str = Form(default="EN")
):
    """Upload document for OCR processing."""
    try:
        if not service_instance:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service not initialized"
            )
        
        # Read file content
        content = await file.read()
        
        # Create envelope for processing
        envelope = Envelope[FinancePayload](
            user_id=user_id,
            lang=language,
            payload=FinancePayload(
                action="ocr",
                document_type="invoice"
            )
        )
        
        # Process document
        result = await service_instance.ocr_processor.process_document(
            envelope,
            content,
            file.filename or "document"
        )
        
        return result.model_dump()
        
    except Exception as e:
        service_instance.logger.error("Error uploading document", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document upload error"
        )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8081"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)