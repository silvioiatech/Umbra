"""
R2 Object Operations - F4R2: High-level object storage operations.
Provides put/get/head/delete operations with utilities and presigned URLs.
"""
import hashlib
import mimetypes
import json
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timezone
import time

from .r2_client import R2Client, R2ClientError, R2NotFoundError
from ..core.logger import get_context_logger

logger = get_context_logger(__name__)

class ObjectStorageError(Exception):
    """Base exception for object storage operations."""
    pass

class ObjectNotFoundError(ObjectStorageError):
    """Object not found in storage."""
    pass

class ObjectStorage:
    """
    High-level object storage operations using R2.
    
    F4R2 Implementation: Provides convenient methods for common storage patterns
    with automatic content type detection, SHA256 verification, and utilities.
    """
    
    def __init__(self, config=None):
        self.config = config
        self.logger = get_context_logger(__name__)
        self.r2_client = R2Client(config)
        
        self.logger.info(
            "Object storage initialized",
            extra={
                "r2_available": self.r2_client.is_available(),
                "bucket": self.r2_client.bucket_name
            }
        )
    
    def is_available(self) -> bool:
        """Check if object storage is available."""
        return self.r2_client.is_available()
    
    def put_object(
        self,
        key: str,
        data: Union[bytes, str],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        verify_sha256: bool = True
    ) -> Dict[str, Any]:
        """
        Store object in R2 with automatic content type detection.
        
        Args:
            key: Object key/path
            data: Object data (bytes or string)
            content_type: MIME type (auto-detected if None)
            metadata: Additional metadata
            verify_sha256: Whether to compute and store SHA256 hash
            
        Returns:
            Dict with upload info including etag, sha256, size
        """
        
        if not self.is_available():
            raise ObjectStorageError("Object storage not available")
        
        # Convert string to bytes
        if isinstance(data, str):
            data = data.encode('utf-8')
            if content_type is None:
                content_type = 'text/plain; charset=utf-8'
        
        # Auto-detect content type if not provided
        if content_type is None:
            content_type, _ = mimetypes.guess_type(key)
            if content_type is None:
                content_type = 'application/octet-stream'
        
        # Compute SHA256 if requested
        sha256_hash = None
        if verify_sha256:
            sha256_hash = hashlib.sha256(data).hexdigest()
            
            # Add SHA256 to metadata
            if metadata is None:
                metadata = {}
            metadata['sha256'] = sha256_hash
        
        # Add upload timestamp
        if metadata is None:
            metadata = {}
        metadata['uploaded_at'] = datetime.now(timezone.utc).isoformat()
        
        start_time = time.time()
        
        try:
            result = self.r2_client.put_object(
                key=key,
                data=data,
                content_type=content_type,
                metadata=metadata
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                "Object stored successfully",
                extra={
                    "key": key,
                    "size_bytes": len(data),
                    "content_type": content_type,
                    "sha256": sha256_hash,
                    "etag": result["etag"],
                    "duration_ms": round(duration_ms, 2)
                }
            )
            
            return {
                **result,
                "key": key,
                "content_type": content_type,
                "sha256": sha256_hash,
                "uploaded_at": metadata.get('uploaded_at')
            }
            
        except R2ClientError as e:
            self.logger.error(
                "Failed to store object",
                extra={
                    "key": key,
                    "size_bytes": len(data),
                    "error": str(e)
                }
            )
            raise ObjectStorageError(f"Failed to store object '{key}': {str(e)}")
    
    def get_object(self, key: str, verify_sha256: bool = True) -> Dict[str, Any]:
        """
        Retrieve object from R2 with optional SHA256 verification.
        
        Args:
            key: Object key/path
            verify_sha256: Whether to verify SHA256 hash if available
            
        Returns:
            Dict with object data, metadata, and verification info
        """
        
        if not self.is_available():
            raise ObjectStorageError("Object storage not available")
        
        start_time = time.time()
        
        try:
            result = self.r2_client.get_object(key)
            
            # Verify SHA256 if requested and available
            sha256_verified = None
            if verify_sha256 and 'sha256' in result.get('metadata', {}):
                expected_sha256 = result['metadata']['sha256']
                actual_sha256 = hashlib.sha256(result['data']).hexdigest()
                sha256_verified = (expected_sha256 == actual_sha256)
                
                if not sha256_verified:
                    self.logger.warning(
                        "SHA256 verification failed",
                        extra={
                            "key": key,
                            "expected": expected_sha256,
                            "actual": actual_sha256
                        }
                    )
            
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                "Object retrieved successfully",
                extra={
                    "key": key,
                    "size_bytes": len(result['data']),
                    "content_type": result.get('content_type'),
                    "sha256_verified": sha256_verified,
                    "duration_ms": round(duration_ms, 2)
                }
            )
            
            return {
                **result,
                "key": key,
                "sha256_verified": sha256_verified
            }
            
        except R2NotFoundError:
            raise ObjectNotFoundError(f"Object '{key}' not found")
        except R2ClientError as e:
            self.logger.error(
                "Failed to retrieve object",
                extra={"key": key, "error": str(e)}
            )
            raise ObjectStorageError(f"Failed to retrieve object '{key}': {str(e)}")
    
    def head_object(self, key: str) -> Dict[str, Any]:
        """
        Get object metadata without downloading content.
        
        Args:
            key: Object key/path
            
        Returns:
            Dict with object metadata
        """
        
        if not self.is_available():
            raise ObjectStorageError("Object storage not available")
        
        try:
            result = self.r2_client.head_object(key)
            
            self.logger.debug(
                "Object metadata retrieved",
                extra={
                    "key": key,
                    "size_bytes": result.get('size', 0),
                    "content_type": result.get('content_type')
                }
            )
            
            return {
                **result,
                "key": key
            }
            
        except R2NotFoundError:
            raise ObjectNotFoundError(f"Object '{key}' not found")
        except R2ClientError as e:
            raise ObjectStorageError(f"Failed to get object metadata '{key}': {str(e)}")
    
    def delete_object(self, key: str) -> bool:
        """
        Delete object from R2.
        
        Args:
            key: Object key/path
            
        Returns:
            True if deleted successfully
        """
        
        if not self.is_available():
            raise ObjectStorageError("Object storage not available")
        
        try:
            result = self.r2_client.delete_object(key)
            
            self.logger.info(
                "Object deleted successfully",
                extra={"key": key}
            )
            
            return result
            
        except R2ClientError as e:
            self.logger.error(
                "Failed to delete object",
                extra={"key": key, "error": str(e)}
            )
            raise ObjectStorageError(f"Failed to delete object '{key}': {str(e)}")
    
    def object_exists(self, key: str) -> bool:
        """
        Check if object exists in R2.
        
        Args:
            key: Object key/path
            
        Returns:
            True if object exists
        """
        
        try:
            self.head_object(key)
            return True
        except ObjectNotFoundError:
            return False
        except ObjectStorageError:
            return False
    
    def list_objects(
        self,
        prefix: str = "",
        max_keys: int = 1000,
        continuation_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List objects with optional prefix filtering.
        
        Args:
            prefix: Key prefix to filter by
            max_keys: Maximum number of keys to return
            continuation_token: Token for pagination
            
        Returns:
            Dict with objects list and pagination info
        """
        
        if not self.is_available():
            raise ObjectStorageError("Object storage not available")
        
        try:
            result = self.r2_client.list_objects(
                prefix=prefix,
                max_keys=max_keys,
                continuation_token=continuation_token
            )
            
            self.logger.debug(
                "Objects listed successfully",
                extra={
                    "prefix": prefix,
                    "count": len(result['objects']),
                    "is_truncated": result['is_truncated']
                }
            )
            
            return result
            
        except R2ClientError as e:
            raise ObjectStorageError(f"Failed to list objects: {str(e)}")
    
    def generate_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        method: str = 'download'
    ) -> str:
        """
        Generate presigned URL for object access.
        
        Args:
            key: Object key/path
            expiration: URL expiration in seconds (default 1 hour)
            method: Access method ('download', 'upload')
            
        Returns:
            Presigned URL string
        """
        
        if not self.is_available():
            raise ObjectStorageError("Object storage not available")
        
        # Map method names to S3 operations
        method_mapping = {
            'download': 'get_object',
            'upload': 'put_object',
            'get_object': 'get_object',
            'put_object': 'put_object'
        }
        
        s3_method = method_mapping.get(method, 'get_object')
        
        try:
            url = self.r2_client.generate_presigned_url(
                key=key,
                expiration=expiration,
                method=s3_method
            )
            
            self.logger.info(
                "Presigned URL generated",
                extra={
                    "key": key,
                    "method": method,
                    "expiration": expiration
                }
            )
            
            return url
            
        except R2ClientError as e:
            raise ObjectStorageError(f"Failed to generate presigned URL: {str(e)}")
    
    def put_json(self, key: str, data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Store JSON object in R2.
        
        Args:
            key: Object key/path
            data: Dictionary to store as JSON
            **kwargs: Additional arguments for put_object
            
        Returns:
            Upload result info
        """
        
        json_data = json.dumps(data, indent=2, ensure_ascii=False)
        
        return self.put_object(
            key=key,
            data=json_data,
            content_type='application/json; charset=utf-8',
            **kwargs
        )
    
    def get_json(self, key: str, **kwargs) -> Dict[str, Any]:
        """
        Retrieve and parse JSON object from R2.
        
        Args:
            key: Object key/path
            **kwargs: Additional arguments for get_object
            
        Returns:
            Parsed JSON data
        """
        
        result = self.get_object(key, **kwargs)
        
        try:
            json_data = json.loads(result['data'].decode('utf-8'))
            
            return {
                **result,
                "json_data": json_data
            }
            
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ObjectStorageError(f"Failed to parse JSON from '{key}': {str(e)}")
    
    def store_document(
        self,
        data: bytes,
        filename: str,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Store document with SHA256-based key in documents/ folder.
        
        Args:
            data: Document data
            filename: Original filename (for extension)
            content_type: MIME type
            
        Returns:
            Storage info with document key and URL
        """
        
        # Compute SHA256 hash
        sha256_hash = hashlib.sha256(data).hexdigest()
        
        # Extract file extension
        _, ext = mimetypes.guess_extension(content_type) or ("", "")
        if not ext and "." in filename:
            ext = "." + filename.split(".")[-1].lower()
        
        # Create document key
        document_key = f"documents/{sha256_hash}{ext}"
        
        # Check if document already exists
        if self.object_exists(document_key):
            self.logger.info(
                "Document already exists",
                extra={
                    "sha256": sha256_hash,
                    "key": document_key,
                    "filename": filename
                }
            )
            
            # Return existing document info
            metadata = self.head_object(document_key)
            return {
                "key": document_key,
                "sha256": sha256_hash,
                "filename": filename,
                "already_exists": True,
                "size": metadata.get('size', 0),
                "content_type": metadata.get('content_type')
            }
        
        # Store new document
        result = self.put_object(
            key=document_key,
            data=data,
            content_type=content_type,
            metadata={
                "original_filename": filename,
                "document_type": "user_upload"
            }
        )
        
        return {
            **result,
            "filename": filename,
            "already_exists": False
        }
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage usage statistics.
        
        Returns:
            Dict with storage statistics
        """
        
        if not self.is_available():
            return {
                "available": False,
                "error": "Storage not available"
            }
        
        try:
            # Get some basic stats by listing a subset of objects
            manifests = self.list_objects(prefix="manifests/", max_keys=100)
            documents = self.list_objects(prefix="documents/", max_keys=100)
            exports = self.list_objects(prefix="exports/", max_keys=100)
            
            total_objects = manifests['key_count'] + documents['key_count'] + exports['key_count']
            
            # Calculate approximate sizes
            manifest_size = sum(obj.get('size', 0) for obj in manifests['objects'])
            document_size = sum(obj.get('size', 0) for obj in documents['objects'])
            export_size = sum(obj.get('size', 0) for obj in exports['objects'])
            
            return {
                "available": True,
                "bucket": self.r2_client.bucket_name,
                "objects": {
                    "manifests": manifests['key_count'],
                    "documents": documents['key_count'],
                    "exports": exports['key_count'],
                    "total": total_objects
                },
                "sizes": {
                    "manifests_bytes": manifest_size,
                    "documents_bytes": document_size,
                    "exports_bytes": export_size,
                    "total_bytes": manifest_size + document_size + export_size
                },
                "note": "Statistics based on sample of objects"
            }
            
        except Exception as e:
            self.logger.error(
                "Failed to get storage stats",
                extra={"error": str(e)}
            )
            return {
                "available": True,
                "error": f"Failed to get stats: {str(e)}"
            }

# Export
__all__ = [
    "ObjectStorage", 
    "ObjectStorageError", 
    "ObjectNotFoundError"
]
