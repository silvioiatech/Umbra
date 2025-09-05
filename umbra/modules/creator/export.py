"""
Creator export functionality with R2 storage integration.
Saves outputs to Cloudflare R2 and returns presigned URLs.
"""

import os
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


@dataclass
class ExportResult:
    """Result of export operation."""
    success: bool
    url: Optional[str] = None
    key: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class R2Storage:
    """Cloudflare R2 storage client for Creator assets."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # R2 Configuration
        self.account_id = config.get("R2_ACCOUNT_ID")
        self.access_key_id = config.get("R2_ACCESS_KEY_ID")
        self.secret_access_key = config.get("R2_SECRET_ACCESS_KEY")
        self.bucket = config.get("R2_BUCKET", "umbra")
        self.endpoint = config.get("R2_ENDPOINT")
        
        # Auto-generate endpoint if not provided
        if not self.endpoint and self.account_id:
            self.endpoint = f"https://{self.account_id}.r2.cloudflarestorage.com"
            
        # File size limits (in bytes)
        self.max_file_size = int(config.get("R2_MAX_FILE_SIZE", 50 * 1024 * 1024))  # 50MB default
        
        self._client = None
        
    def is_configured(self) -> bool:
        """Check if R2 storage is properly configured."""
        return bool(
            BOTO3_AVAILABLE and
            self.account_id and
            self.access_key_id and
            self.secret_access_key and
            self.bucket
        )
        
    def _get_client(self):
        """Get or create S3-compatible client for R2."""
        if self._client is None:
            if not self.is_configured():
                raise ValueError("R2 storage not configured")
                
            self._client = boto3.client(
                's3',
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                endpoint_url=self.endpoint,
                config=Config(signature_version='s3v4')
            )
            
        return self._client
        
    def _generate_key(self, content_type: str, filename: str = None) -> str:
        """Generate unique storage key for content."""
        timestamp = datetime.now().strftime('%Y/%m/%d')
        
        if filename:
            # Use provided filename with timestamp prefix
            file_hash = hashlib.md5(filename.encode()).hexdigest()[:8]
            safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
            key = f"creator/{content_type}/{timestamp}/{file_hash}_{safe_filename}"
        else:
            # Generate random filename
            unique_id = hashlib.md5(f"{datetime.now().isoformat()}".encode()).hexdigest()[:12]
            extension = self._get_extension(content_type)
            key = f"creator/{content_type}/{timestamp}/{unique_id}{extension}"
            
        return key
        
    def _get_extension(self, content_type: str) -> str:
        """Get file extension based on content type."""
        extensions = {
            "image": ".png",
            "video": ".mp4",
            "audio": ".mp3",
            "music": ".mp3",
            "document": ".txt"
        }
        return extensions.get(content_type, ".bin")
        
    def _get_content_type(self, content_type: str) -> str:
        """Get MIME type based on content type."""
        mime_types = {
            "image": "image/png",
            "video": "video/mp4",
            "audio": "audio/mpeg",
            "music": "audio/mpeg",
            "document": "text/plain"
        }
        return mime_types.get(content_type, "application/octet-stream")
        
    async def upload_content(
        self,
        content: bytes,
        content_type: str,
        filename: str = None,
        metadata: Dict[str, Any] = None
    ) -> ExportResult:
        """Upload content to R2 storage."""
        if not self.is_configured():
            return ExportResult(
                success=False,
                error="R2 storage not configured. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_BUCKET"
            )
            
        if not BOTO3_AVAILABLE:
            return ExportResult(
                success=False,
                error="boto3 package not available. Install boto3 to enable R2 storage"
            )
            
        # Check file size
        if len(content) > self.max_file_size:
            return ExportResult(
                success=False,
                error=f"File size {len(content)} bytes exceeds maximum {self.max_file_size} bytes"
            )
            
        try:
            # Generate storage key
            key = self._generate_key(content_type, filename)
            
            # Prepare metadata
            upload_metadata = {
                'uploaded_by': 'umbra_creator',
                'content_type': content_type,
                'timestamp': datetime.now().isoformat()
            }
            if metadata:
                upload_metadata.update({k: str(v) for k, v in metadata.items()})
                
            # Upload to R2
            client = self._get_client()
            client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=self._get_content_type(content_type),
                Metadata=upload_metadata
            )
            
            # Generate presigned URL (valid for 24 hours)
            presigned_url = client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': key},
                ExpiresIn=24 * 3600  # 24 hours
            )
            
            self.logger.info(f"Uploaded {content_type} content to R2: {key}")
            
            return ExportResult(
                success=True,
                url=presigned_url,
                key=key,
                metadata={
                    "size": len(content),
                    "bucket": self.bucket,
                    "content_type": content_type
                }
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            return ExportResult(
                success=False,
                error=f"R2 upload failed ({error_code}): {error_msg}"
            )
            
        except Exception as e:
            return ExportResult(
                success=False,
                error=f"R2 upload failed: {str(e)}"
            )
            
    async def upload_text(self, text: str, filename: str = None, metadata: Dict[str, Any] = None) -> ExportResult:
        """Upload text content to R2."""
        return await self.upload_content(
            content=text.encode('utf-8'),
            content_type="document",
            filename=filename,
            metadata=metadata
        )
        
    async def upload_url_content(
        self,
        url: str,
        content_type: str,
        filename: str = None,
        metadata: Dict[str, Any] = None
    ) -> ExportResult:
        """Download content from URL and upload to R2."""
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                return await self.upload_content(
                    content=response.content,
                    content_type=content_type,
                    filename=filename,
                    metadata=metadata
                )
                
        except Exception as e:
            return ExportResult(
                success=False,
                error=f"Failed to download and upload content: {str(e)}"
            )


class CreatorExporter:
    """High-level exporter for Creator content."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.storage = R2Storage(config)
        self.logger = logging.getLogger(__name__)
        
    def is_storage_enabled(self) -> bool:
        """Check if storage is properly configured."""
        return self.storage.is_configured()
        
    async def export_image(
        self,
        image_data: bytes = None,
        image_url: str = None,
        prompt: str = None,
        provider: str = None
    ) -> ExportResult:
        """Export image to storage."""
        if not self.is_storage_enabled():
            return ExportResult(
                success=False,
                error="Storage not configured - images cannot be saved"
            )
            
        metadata = {}
        if prompt:
            metadata["prompt"] = prompt
        if provider:
            metadata["provider"] = provider
            
        if image_data:
            return await self.storage.upload_content(
                content=image_data,
                content_type="image",
                metadata=metadata
            )
        elif image_url:
            return await self.storage.upload_url_content(
                url=image_url,
                content_type="image",
                metadata=metadata
            )
        else:
            return ExportResult(
                success=False,
                error="No image data or URL provided"
            )
            
    async def export_text(
        self,
        text: str,
        document_type: str = "general",
        prompt: str = None,
        provider: str = None
    ) -> ExportResult:
        """Export text document to storage."""
        if not self.is_storage_enabled():
            return ExportResult(
                success=False,
                error="Storage not configured - documents cannot be saved"
            )
            
        metadata = {
            "document_type": document_type
        }
        if prompt:
            metadata["prompt"] = prompt
        if provider:
            metadata["provider"] = provider
            
        filename = f"{document_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        return await self.storage.upload_text(
            text=text,
            filename=filename,
            metadata=metadata
        )
        
    async def export_video(
        self,
        video_data: bytes = None,
        video_url: str = None,
        prompt: str = None,
        provider: str = None
    ) -> ExportResult:
        """Export video to storage."""
        if not self.is_storage_enabled():
            return ExportResult(
                success=False,
                error="Storage not configured - videos cannot be saved"
            )
            
        metadata = {}
        if prompt:
            metadata["prompt"] = prompt
        if provider:
            metadata["provider"] = provider
            
        if video_data:
            return await self.storage.upload_content(
                content=video_data,
                content_type="video",
                metadata=metadata
            )
        elif video_url:
            return await self.storage.upload_url_content(
                url=video_url,
                content_type="video",
                metadata=metadata
            )
        else:
            return ExportResult(
                success=False,
                error="No video data or URL provided"
            )
            
    async def export_audio(
        self,
        audio_data: bytes = None,
        audio_url: str = None,
        text: str = None,
        provider: str = None
    ) -> ExportResult:
        """Export audio to storage."""
        if not self.is_storage_enabled():
            return ExportResult(
                success=False,
                error="Storage not configured - audio cannot be saved"
            )
            
        metadata = {}
        if text:
            metadata["text"] = text
        if provider:
            metadata["provider"] = provider
            
        if audio_data:
            return await self.storage.upload_content(
                content=audio_data,
                content_type="audio",
                metadata=metadata
            )
        elif audio_url:
            return await self.storage.upload_url_content(
                url=audio_url,
                content_type="audio",
                metadata=metadata
            )
        else:
            return ExportResult(
                success=False,
                error="No audio data or URL provided"
            )
            
    async def export_music(
        self,
        music_data: bytes = None,
        music_url: str = None,
        prompt: str = None,
        provider: str = None
    ) -> ExportResult:
        """Export music to storage."""
        if not self.is_storage_enabled():
            return ExportResult(
                success=False,
                error="Storage not configured - music cannot be saved"
            )
            
        metadata = {}
        if prompt:
            metadata["prompt"] = prompt
        if provider:
            metadata["provider"] = provider
            
        if music_data:
            return await self.storage.upload_content(
                content=music_data,
                content_type="music",
                metadata=metadata
            )
        elif music_url:
            return await self.storage.upload_url_content(
                url=music_url,
                content_type="music",
                metadata=metadata
            )
        else:
            return ExportResult(
                success=False,
                error="No music data or URL provided"
            )