"""
Cloudflare R2 Client - F4R2: S3-compatible object storage client.
Thin wrapper around boto3 for Cloudflare R2 with optimized settings.
"""
import boto3
import time
from typing import Optional, Dict, Any
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError

from ..core.logger import get_context_logger
from ..core.config import config

logger = get_context_logger(__name__)

class R2ClientError(Exception):
    """Base exception for R2 client errors."""
    pass

class R2ConnectionError(R2ClientError):
    """R2 connection/network related errors."""
    pass

class R2AuthenticationError(R2ClientError):
    """R2 authentication errors."""
    pass

class R2NotFoundError(R2ClientError):
    """R2 object not found errors."""
    pass

class R2Client:
    """
    Cloudflare R2 client using S3 API compatibility.
    
    F4R2 Implementation: Optimized for R2 with proper error handling,
    connection pooling, and monitoring.
    """
    
    def __init__(self, config_obj=None):
        self.config = config_obj or config
        self.logger = get_context_logger(__name__)
        
        # R2 configuration
        self.account_id = getattr(self.config, 'R2_ACCOUNT_ID', None)
        self.access_key_id = getattr(self.config, 'R2_ACCESS_KEY_ID', None)
        self.secret_access_key = getattr(self.config, 'R2_SECRET_ACCESS_KEY', None)
        self.bucket_name = getattr(self.config, 'R2_BUCKET', None)
        self.endpoint_url = getattr(self.config, 'R2_ENDPOINT', None)
        
        # Auto-generate endpoint if account_id provided but no explicit endpoint
        if self.account_id and not self.endpoint_url:
            self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"
        
        # Boto3 configuration optimized for R2
        self.boto_config = Config(
            region_name='auto',  # R2 uses 'auto' region
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            max_pool_connections=50,
            connect_timeout=10,
            read_timeout=30
        )
        
        # Initialize S3 client
        self.s3_client = None
        self._initialize_client()
        
        self.logger.info(
            "R2 client initialized",
            extra={
                "bucket": self.bucket_name,
                "endpoint": self.endpoint_url,
                "account_id": self.account_id[:8] + "..." if self.account_id else None,
                "available": self.is_available()
            }
        )
    
    def _initialize_client(self) -> None:
        """Initialize the S3 client for R2."""
        
        if not self.is_configured():
            self.logger.warning("R2 not configured, client will be unavailable")
            return
        
        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                config=self.boto_config
            )
            
            # Test connection with a simple head_bucket call
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            
            self.logger.info(
                "R2 client connection verified",
                extra={
                    "bucket": self.bucket_name,
                    "endpoint": self.endpoint_url
                }
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            if error_code == 'NoSuchBucket':
                self.logger.error(
                    "R2 bucket does not exist",
                    extra={
                        "bucket": self.bucket_name,
                        "error_code": error_code
                    }
                )
                raise R2ClientError(f"Bucket '{self.bucket_name}' does not exist")
            elif error_code in ['InvalidAccessKeyId', 'SignatureDoesNotMatch']:
                self.logger.error(
                    "R2 authentication failed",
                    extra={
                        "error_code": error_code,
                        "bucket": self.bucket_name
                    }
                )
                raise R2AuthenticationError(f"R2 authentication failed: {error_code}")
            else:
                self.logger.error(
                    "R2 client initialization failed",
                    extra={
                        "error_code": error_code,
                        "error": str(e)
                    }
                )
                raise R2ConnectionError(f"Failed to initialize R2 client: {error_code}")
                
        except BotoCoreError as e:
            self.logger.error(
                "R2 connection error",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise R2ConnectionError(f"R2 connection error: {str(e)}")
    
    def is_configured(self) -> bool:
        """Check if R2 is properly configured."""
        required_fields = [
            self.access_key_id,
            self.secret_access_key,
            self.bucket_name,
            self.endpoint_url
        ]
        return all(field is not None for field in required_fields)
    
    def is_available(self) -> bool:
        """Check if R2 client is available and working."""
        if not self.is_configured():
            return False
        
        if self.s3_client is None:
            return False
        
        try:
            # Quick connectivity test
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except Exception:
            return False
    
    def put_object(
        self, 
        key: str, 
        data: bytes, 
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Upload object to R2.
        
        Args:
            key: Object key/path
            data: Object data as bytes
            content_type: MIME type (auto-detected if None)
            metadata: Additional metadata headers
            
        Returns:
            Dict with ETag, upload info
        """
        
        if not self.is_available():
            raise R2ClientError("R2 client not available")
        
        start_time = time.time()
        
        try:
            # Build put request parameters
            put_params = {
                'Bucket': self.bucket_name,
                'Key': key,
                'Body': data
            }
            
            if content_type:
                put_params['ContentType'] = content_type
            
            if metadata:
                put_params['Metadata'] = metadata
            
            # Upload object
            response = self.s3_client.put_object(**put_params)
            
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                "R2 object uploaded",
                extra={
                    "key": key,
                    "size_bytes": len(data),
                    "content_type": content_type,
                    "etag": response.get('ETag', '').strip('"'),
                    "duration_ms": round(duration_ms, 2)
                }
            )
            
            return {
                "etag": response.get('ETag', '').strip('"'),
                "version_id": response.get('VersionId'),
                "size": len(data),
                "duration_ms": round(duration_ms, 2)
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            self.logger.error(
                "R2 put_object failed",
                extra={
                    "key": key,
                    "error_code": error_code,
                    "size_bytes": len(data)
                }
            )
            
            if error_code == 'NoSuchBucket':
                raise R2NotFoundError(f"Bucket '{self.bucket_name}' not found")
            else:
                raise R2ClientError(f"Failed to upload object: {error_code}")
                
        except Exception as e:
            self.logger.error(
                "R2 put_object unexpected error",
                extra={
                    "key": key,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise R2ClientError(f"Unexpected error uploading object: {str(e)}")
    
    def get_object(self, key: str) -> Dict[str, Any]:
        """
        Download object from R2.
        
        Args:
            key: Object key/path
            
        Returns:
            Dict with object data, metadata, etag
        """
        
        if not self.is_available():
            raise R2ClientError("R2 client not available")
        
        start_time = time.time()
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            
            # Read the object data
            object_data = response['Body'].read()
            
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                "R2 object downloaded",
                extra={
                    "key": key,
                    "size_bytes": len(object_data),
                    "content_type": response.get('ContentType'),
                    "etag": response.get('ETag', '').strip('"'),
                    "duration_ms": round(duration_ms, 2)
                }
            )
            
            return {
                "data": object_data,
                "etag": response.get('ETag', '').strip('"'),
                "content_type": response.get('ContentType'),
                "metadata": response.get('Metadata', {}),
                "last_modified": response.get('LastModified'),
                "size": len(object_data),
                "duration_ms": round(duration_ms, 2)
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            if error_code == 'NoSuchKey':
                self.logger.debug(
                    "R2 object not found",
                    extra={"key": key}
                )
                raise R2NotFoundError(f"Object '{key}' not found")
            else:
                self.logger.error(
                    "R2 get_object failed",
                    extra={
                        "key": key,
                        "error_code": error_code
                    }
                )
                raise R2ClientError(f"Failed to download object: {error_code}")
                
        except Exception as e:
            self.logger.error(
                "R2 get_object unexpected error",
                extra={
                    "key": key,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise R2ClientError(f"Unexpected error downloading object: {str(e)}")
    
    def head_object(self, key: str) -> Dict[str, Any]:
        """
        Get object metadata without downloading content.
        
        Args:
            key: Object key/path
            
        Returns:
            Dict with metadata, etag, size
        """
        
        if not self.is_available():
            raise R2ClientError("R2 client not available")
        
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            
            self.logger.debug(
                "R2 head_object success",
                extra={
                    "key": key,
                    "etag": response.get('ETag', '').strip('"'),
                    "size": response.get('ContentLength', 0)
                }
            )
            
            return {
                "etag": response.get('ETag', '').strip('"'),
                "content_type": response.get('ContentType'),
                "metadata": response.get('Metadata', {}),
                "last_modified": response.get('LastModified'),
                "size": response.get('ContentLength', 0)
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            if error_code == 'NoSuchKey':
                raise R2NotFoundError(f"Object '{key}' not found")
            else:
                self.logger.error(
                    "R2 head_object failed",
                    extra={
                        "key": key,
                        "error_code": error_code
                    }
                )
                raise R2ClientError(f"Failed to get object metadata: {error_code}")
    
    def delete_object(self, key: str) -> bool:
        """
        Delete object from R2.
        
        Args:
            key: Object key/path
            
        Returns:
            True if deleted or already didn't exist
        """
        
        if not self.is_available():
            raise R2ClientError("R2 client not available")
        
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            
            self.logger.info(
                "R2 object deleted",
                extra={"key": key}
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "R2 delete_object failed",
                extra={
                    "key": key,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise R2ClientError(f"Failed to delete object: {str(e)}")
    
    def list_objects(
        self, 
        prefix: str = "", 
        max_keys: int = 1000,
        continuation_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List objects in R2 bucket with optional prefix.
        
        Args:
            prefix: Key prefix to filter by
            max_keys: Maximum number of keys to return
            continuation_token: Token for pagination
            
        Returns:
            Dict with objects list and pagination info
        """
        
        if not self.is_available():
            raise R2ClientError("R2 client not available")
        
        try:
            list_params = {
                'Bucket': self.bucket_name,
                'MaxKeys': max_keys
            }
            
            if prefix:
                list_params['Prefix'] = prefix
            
            if continuation_token:
                list_params['ContinuationToken'] = continuation_token
            
            response = self.s3_client.list_objects_v2(**list_params)
            
            objects = []
            for obj in response.get('Contents', []):
                objects.append({
                    'key': obj['Key'],
                    'etag': obj.get('ETag', '').strip('"'),
                    'size': obj.get('Size', 0),
                    'last_modified': obj.get('LastModified')
                })
            
            self.logger.debug(
                "R2 list_objects success",
                extra={
                    "prefix": prefix,
                    "count": len(objects),
                    "is_truncated": response.get('IsTruncated', False)
                }
            )
            
            return {
                "objects": objects,
                "is_truncated": response.get('IsTruncated', False),
                "next_continuation_token": response.get('NextContinuationToken'),
                "key_count": response.get('KeyCount', 0)
            }
            
        except Exception as e:
            self.logger.error(
                "R2 list_objects failed",
                extra={
                    "prefix": prefix,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise R2ClientError(f"Failed to list objects: {str(e)}")
    
    def generate_presigned_url(
        self, 
        key: str, 
        expiration: int = 3600,
        method: str = 'get_object'
    ) -> str:
        """
        Generate presigned URL for object access.
        
        Args:
            key: Object key/path
            expiration: URL expiration in seconds (default 1 hour)
            method: S3 method ('get_object', 'put_object')
            
        Returns:
            Presigned URL string
        """
        
        if not self.is_available():
            raise R2ClientError("R2 client not available")
        
        try:
            url = self.s3_client.generate_presigned_url(
                method,
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            
            self.logger.debug(
                "R2 presigned URL generated",
                extra={
                    "key": key,
                    "method": method,
                    "expiration": expiration
                }
            )
            
            return url
            
        except Exception as e:
            self.logger.error(
                "R2 presigned URL generation failed",
                extra={
                    "key": key,
                    "method": method,
                    "error": str(e)
                }
            )
            raise R2ClientError(f"Failed to generate presigned URL: {str(e)}")
    
    def get_client_info(self) -> Dict[str, Any]:
        """Get R2 client configuration info (for debugging/status)."""
        
        return {
            "configured": self.is_configured(),
            "available": self.is_available(),
            "bucket": self.bucket_name,
            "endpoint": self.endpoint_url,
            "account_id": self.account_id[:8] + "..." if self.account_id else None
        }

# Export
__all__ = [
    "R2Client", 
    "R2ClientError", 
    "R2ConnectionError", 
    "R2AuthenticationError", 
    "R2NotFoundError"
]
