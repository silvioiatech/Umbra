"""Storage client for S3/R2 compatible storage."""

import boto3
import hashlib
import mimetypes
from typing import Dict, Optional, Any, BinaryIO
from datetime import datetime, timedelta
from botocore.exceptions import ClientError, NoCredentialsError
from .logger import UmbraLogger
from .retry import RetryUtils, retry_async


class StorageClient:
    """Client for S3-compatible storage services."""
    
    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        region: str = "auto"
    ):
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.region = region
        self.logger = UmbraLogger("StorageClient")
        self.retry_utils = RetryUtils()
        
        # Initialize S3 client
        self.client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
    
    async def upload_file(
        self,
        file_data: bytes,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """Upload file to storage."""
        try:
            # Auto-detect content type if not provided
            if not content_type:
                content_type, _ = mimetypes.guess_type(key)
                if not content_type:
                    content_type = "application/octet-stream"
            
            # Prepare upload parameters
            upload_params = {
                'Bucket': self.bucket_name,
                'Key': key,
                'Body': file_data,
                'ContentType': content_type
            }
            
            if metadata:
                upload_params['Metadata'] = metadata
            
            # Calculate file hash for integrity
            file_hash = hashlib.sha256(file_data).hexdigest()
            upload_params['Metadata'] = upload_params.get('Metadata', {})
            upload_params['Metadata']['sha256'] = file_hash
            
            self.logger.debug("Uploading file", 
                            key=key, 
                            size=len(file_data),
                            content_type=content_type)
            
            # Upload file
            self.client.put_object(**upload_params)
            
            # Generate URL
            file_url = f"{self.endpoint_url}/{self.bucket_name}/{key}"
            
            self.logger.info("File uploaded successfully", 
                           key=key, 
                           url=file_url,
                           hash=file_hash)
            
            return file_url
            
        except (ClientError, NoCredentialsError) as e:
            self.logger.error("Failed to upload file", key=key, error=str(e))
            raise
        except Exception as e:
            self.logger.error("Unexpected error uploading file", key=key, error=str(e))
            raise
    
    async def download_file(self, key: str) -> bytes:
        """Download file from storage."""
        try:
            self.logger.debug("Downloading file", key=key)
            
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            file_data = response['Body'].read()
            
            self.logger.info("File downloaded successfully", 
                           key=key, 
                           size=len(file_data))
            
            return file_data
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                self.logger.warning("File not found", key=key)
                raise FileNotFoundError(f"File not found: {key}")
            else:
                self.logger.error("Failed to download file", key=key, error=str(e))
                raise
        except Exception as e:
            self.logger.error("Unexpected error downloading file", key=key, error=str(e))
            raise
    
    async def delete_file(self, key: str) -> bool:
        """Delete file from storage."""
        try:
            self.logger.debug("Deleting file", key=key)
            
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            
            self.logger.info("File deleted successfully", key=key)
            return True
            
        except ClientError as e:
            self.logger.error("Failed to delete file", key=key, error=str(e))
            raise
        except Exception as e:
            self.logger.error("Unexpected error deleting file", key=key, error=str(e))
            raise
    
    async def file_exists(self, key: str) -> bool:
        """Check if file exists in storage."""
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return False
            else:
                self.logger.error("Error checking file existence", key=key, error=str(e))
                raise
        except Exception as e:
            self.logger.error("Unexpected error checking file existence", key=key, error=str(e))
            raise
    
    async def get_file_metadata(self, key: str) -> Dict[str, Any]:
        """Get file metadata."""
        try:
            response = self.client.head_object(Bucket=self.bucket_name, Key=key)
            
            metadata = {
                'content_type': response.get('ContentType'),
                'content_length': response.get('ContentLength'),
                'last_modified': response.get('LastModified'),
                'etag': response.get('ETag', '').strip('"'),
                'metadata': response.get('Metadata', {})
            }
            
            return metadata
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                raise FileNotFoundError(f"File not found: {key}")
            else:
                self.logger.error("Failed to get file metadata", key=key, error=str(e))
                raise
        except Exception as e:
            self.logger.error("Unexpected error getting file metadata", key=key, error=str(e))
            raise
    
    async def generate_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        method: str = 'get_object'
    ) -> str:
        """Generate presigned URL for file access."""
        try:
            url = self.client.generate_presigned_url(
                method,
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            
            self.logger.debug("Generated presigned URL", 
                            key=key, 
                            expiration=expiration)
            
            return url
            
        except Exception as e:
            self.logger.error("Failed to generate presigned URL", key=key, error=str(e))
            raise
    
    async def list_files(
        self,
        prefix: str = "",
        max_keys: int = 1000
    ) -> list[Dict[str, Any]]:
        """List files in storage."""
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            files = []
            for obj in response.get('Contents', []):
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'etag': obj['ETag'].strip('"')
                })
            
            self.logger.debug("Listed files", prefix=prefix, count=len(files))
            return files
            
        except Exception as e:
            self.logger.error("Failed to list files", prefix=prefix, error=str(e))
            raise
    
    def generate_file_key(
        self,
        user_id: str,
        filename: str,
        prefix: str = "uploads"
    ) -> str:
        """Generate a unique file key."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        # Sanitize filename
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
        return f"{prefix}/{user_id}/{timestamp}_{safe_filename}"
    
    async def setup_lifecycle_policy(self, days_to_expiry: int = 30):
        """Set up lifecycle policy for automatic file cleanup."""
        try:
            lifecycle_config = {
                'Rules': [
                    {
                        'ID': 'UmbraFileCleanup',
                        'Status': 'Enabled',
                        'Filter': {'Prefix': 'uploads/'},
                        'Expiration': {'Days': days_to_expiry}
                    }
                ]
            }
            
            self.client.put_bucket_lifecycle_configuration(
                Bucket=self.bucket_name,
                LifecycleConfiguration=lifecycle_config
            )
            
            self.logger.info("Lifecycle policy configured", days_to_expiry=days_to_expiry)
            
        except Exception as e:
            self.logger.error("Failed to setup lifecycle policy", error=str(e))
            raise