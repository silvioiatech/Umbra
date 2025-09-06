"""
Umbra Storage Package - F4R2 R2 Object Storage

This package provides enterprise-grade object storage using Cloudflare R2
with JSONL/Parquet manifests and built-in search capabilities.

Components:
- R2Client: Low-level S3-compatible R2 API client
- ObjectStorage: High-level object operations with utilities  
- ManifestManager: JSONL/Parquet manifest files with optimistic locking
- SearchIndex: Simple text search across stored documents

Example Usage:
    from umbra.storage import ObjectStorage, ManifestManager, SearchIndex
    
    # Initialize storage stack
    storage = ObjectStorage()
    manifests = ManifestManager(storage)
    search = SearchIndex(storage)
    
    # Store and retrieve objects
    storage.put_object("documents/file.pdf", pdf_data)
    data = storage.get_object("documents/file.pdf")
    
    # Append to JSONL manifest
    manifests.append_jsonl("module", "data", {"key": "value"})
    
    # Index for search
    search.add_document("module", "doc1", "searchable text content")
"""

# F4R2 Core Components
from .r2_client import (
    R2Client,
    R2ClientError,
    R2ConnectionError, 
    R2AuthenticationError,
    R2NotFoundError
)

from .objects import (
    ObjectStorage,
    ObjectStorageError,
    ObjectNotFoundError
)

from .manifest import (
    ManifestManager,
    ManifestEntry,
    ManifestError,
    ManifestConcurrencyError,
    PARQUET_AVAILABLE
)

from .search_index import (
    SearchIndex,
    SearchIndexError
)

# Convenience imports
__all__ = [
    # Core Classes
    "R2Client",
    "ObjectStorage", 
    "ManifestManager",
    "SearchIndex",
    
    # Data Types
    "ManifestEntry",
    
    # Exceptions
    "R2ClientError",
    "R2ConnectionError",
    "R2AuthenticationError", 
    "R2NotFoundError",
    "ObjectStorageError",
    "ObjectNotFoundError",
    "ManifestError",
    "ManifestConcurrencyError",
    "SearchIndexError",
    
    # Feature Flags
    "PARQUET_AVAILABLE"
]

# Version info
__version__ = "4.2.0"
__author__ = "Umbra Development Team"
__description__ = "F4R2 - Cloudflare R2 Object Storage for Umbra"

# Feature detection
def get_storage_info():
    """Get information about available storage features."""
    from .r2_client import R2Client
    from umbra.core.config import config
    
    # Test R2 availability
    try:
        r2_client = R2Client(config)
        r2_available = r2_client.is_available()
        r2_configured = r2_client.is_configured()
    except Exception:
        r2_available = False
        r2_configured = False
    
    return {
        "version": __version__,
        "r2_configured": r2_configured,
        "r2_available": r2_available,
        "parquet_available": PARQUET_AVAILABLE,
        "components": {
            "r2_client": "✅ Available",
            "object_storage": "✅ Available", 
            "manifest_manager": "✅ Available",
            "search_index": "✅ Available"
        }
    }
