"""
Cloudflare R2 storage manager for UMBRA.
Provides JSONL/Parquet manifest storage, presigned URLs, and optimistic concurrency.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
import uuid
import hashlib

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError, NoCredentialsError
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    DEPS_AVAILABLE = True
except ImportError:
    DEPS_AVAILABLE = False
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception

from ..core.logger import get_logger

logger = get_logger("umbra.storage.r2")


@dataclass
class R2Object:
    """Represents an object in R2 storage."""
    key: str
    etag: Optional[str] = None
    size: Optional[int] = None
    last_modified: Optional[datetime] = None
    metadata: Optional[Dict[str, str]] = None


@dataclass
class ManifestEntry:
    """Represents an entry in a manifest file."""
    id: str
    module: str
    user_id: str
    timestamp: datetime
    data_type: str  # 'jsonl', 'parquet', 'json'
    key: str
    etag: Optional[str] = None
    size: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class R2StorageManager:
    """Manages Cloudflare R2 storage with JSONL/Parquet manifests and presigned URLs."""
    
    def __init__(self, config):
        """Initialize R2 storage manager."""
        self.config = config
        self.logger = logger
        self._client = None
        self._session_lock = asyncio.Lock()
        
        # Validate configuration
        if not DEPS_AVAILABLE:
            raise ImportError("R2 dependencies not available. Install: pip install boto3 pandas pyarrow")
            
        if not all([
            config.R2_ACCOUNT_ID,
            config.R2_ACCESS_KEY_ID, 
            config.R2_SECRET_ACCESS_KEY,
            config.R2_BUCKET
        ]):
            raise ValueError("R2 configuration incomplete. Required: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET")
        
        # Set R2 endpoint if not provided
        if not config.R2_ENDPOINT:
            self.endpoint_url = f"https://{config.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        else:
            self.endpoint_url = config.R2_ENDPOINT
            
        self.bucket_name = config.R2_BUCKET

    async def _get_client(self):
        """Get or create R2 client."""
        if self._client is None:
            async with self._session_lock:
                if self._client is None:
                    try:
                        session = boto3.Session(
                            aws_access_key_id=self.config.R2_ACCESS_KEY_ID,
                            aws_secret_access_key=self.config.R2_SECRET_ACCESS_KEY,
                        )
                        
                        self._client = session.client(
                            's3',
                            endpoint_url=self.endpoint_url,
                            config=Config(signature_version='s3v4')
                        )
                        
                        # Test the connection
                        await asyncio.get_event_loop().run_in_executor(
                            None, self._client.head_bucket, Bucket=self.bucket_name
                        )
                        
                        self.logger.info(f"R2 client initialized for bucket: {self.bucket_name}")
                        
                    except (ClientError, NoCredentialsError) as e:
                        self.logger.error(f"Failed to initialize R2 client: {e}")
                        raise
                        
        return self._client

    def _generate_key(self, module: str, user_id: str, data_type: str, filename: str = None) -> str:
        """Generate a storage key for data organized by module/user."""
        timestamp = datetime.now(timezone.utc).strftime('%Y/%m/%d')
        
        if filename:
            # For specific files
            return f"{module}/{user_id}/{timestamp}/{filename}"
        else:
            # For auto-generated files
            unique_id = str(uuid.uuid4())[:8]
            extension = 'jsonl' if data_type == 'jsonl' else 'parquet' if data_type == 'parquet' else 'json'
            return f"{module}/{user_id}/{timestamp}/{unique_id}.{extension}"

    async def upload_jsonl_data(self, module: str, user_id: str, data: List[Dict[str, Any]], 
                                metadata: Dict[str, str] = None) -> ManifestEntry:
        """Upload data as JSONL format."""
        client = await self._get_client()
        
        # Convert data to JSONL
        jsonl_content = '\n'.join(json.dumps(item, default=str) for item in data)
        content_bytes = jsonl_content.encode('utf-8')
        
        # Generate key
        key = self._generate_key(module, user_id, 'jsonl')
        
        # Upload to R2
        try:
            upload_metadata = {
                'module': module,
                'user_id': user_id,
                'data_type': 'jsonl',
                'uploaded_at': datetime.now(timezone.utc).isoformat(),
                'record_count': str(len(data))
            }
            if metadata:
                upload_metadata.update(metadata)
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=content_bytes,
                    ContentType='application/x-ndjson',
                    Metadata=upload_metadata
                )
            )
            
            entry = ManifestEntry(
                id=str(uuid.uuid4()),
                module=module,
                user_id=user_id,
                timestamp=datetime.now(timezone.utc),
                data_type='jsonl',
                key=key,
                etag=response['ETag'].strip('"'),
                size=len(content_bytes),
                metadata=upload_metadata
            )
            
            # Update manifest
            await self._update_manifest(entry)
            
            self.logger.info(f"Uploaded JSONL data: {key} ({len(data)} records)")
            return entry
            
        except ClientError as e:
            self.logger.error(f"Failed to upload JSONL data: {e}")
            raise

    async def upload_parquet_data(self, module: str, user_id: str, data: List[Dict[str, Any]], 
                                  metadata: Dict[str, str] = None) -> ManifestEntry:
        """Upload data as Parquet format."""
        client = await self._get_client()
        
        # Convert data to Parquet
        df = pd.DataFrame(data)
        
        # Use BytesIO buffer for in-memory Parquet writing
        from io import BytesIO
        buffer = BytesIO()
        table = pa.Table.from_pandas(df)
        pq.write_table(table, buffer)
        content_bytes = buffer.getvalue()
        
        # Generate key
        key = self._generate_key(module, user_id, 'parquet')
        
        # Upload to R2
        try:
            upload_metadata = {
                'module': module,
                'user_id': user_id,
                'data_type': 'parquet',
                'uploaded_at': datetime.now(timezone.utc).isoformat(),
                'record_count': str(len(data)),
                'columns': ','.join(df.columns.tolist())
            }
            if metadata:
                upload_metadata.update(metadata)
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=content_bytes,
                    ContentType='application/x-parquet',
                    Metadata=upload_metadata
                )
            )
            
            entry = ManifestEntry(
                id=str(uuid.uuid4()),
                module=module,
                user_id=user_id,
                timestamp=datetime.now(timezone.utc),
                data_type='parquet',
                key=key,
                etag=response['ETag'].strip('"'),
                size=len(content_bytes),
                metadata=upload_metadata
            )
            
            # Update manifest
            await self._update_manifest(entry)
            
            self.logger.info(f"Uploaded Parquet data: {key} ({len(data)} records)")
            return entry
            
        except ClientError as e:
            self.logger.error(f"Failed to upload Parquet data: {e}")
            raise

    async def upload_json_blob(self, key: str, data: Dict[str, Any], 
                               metadata: Dict[str, str] = None) -> R2Object:
        """Upload small KV-like JSON blobs."""
        client = await self._get_client()
        
        # Ensure key is in JSON blobs area
        if not key.startswith('json_blobs/'):
            key = f"json_blobs/{key}"
        if not key.endswith('.json'):
            key = f"{key}.json"
        
        content = json.dumps(data, indent=2, default=str)
        content_bytes = content.encode('utf-8')
        
        try:
            upload_metadata = {
                'data_type': 'json_blob',
                'uploaded_at': datetime.now(timezone.utc).isoformat()
            }
            if metadata:
                upload_metadata.update(metadata)
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=content_bytes,
                    ContentType='application/json',
                    Metadata=upload_metadata
                )
            )
            
            obj = R2Object(
                key=key,
                etag=response['ETag'].strip('"'),
                size=len(content_bytes),
                last_modified=datetime.now(timezone.utc),
                metadata=upload_metadata
            )
            
            self.logger.debug(f"Uploaded JSON blob: {key}")
            return obj
            
        except ClientError as e:
            self.logger.error(f"Failed to upload JSON blob: {e}")
            raise

    async def download_data(self, key: str) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Download and parse data from R2."""
        client = await self._get_client()
        
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.get_object(Bucket=self.bucket_name, Key=key)
            )
            
            content = response['Body'].read()
            
            # Parse based on file type
            if key.endswith('.jsonl'):
                # Parse JSONL
                lines = content.decode('utf-8').strip().split('\n')
                return [json.loads(line) for line in lines if line.strip()]
            elif key.endswith('.parquet'):
                # Parse Parquet
                from io import BytesIO
                buffer = BytesIO(content)
                table = pq.read_table(buffer)
                df = table.to_pandas()
                return df.to_dict('records')
            elif key.endswith('.json'):
                # Parse JSON
                return json.loads(content.decode('utf-8'))
            else:
                # Return raw content for other file types
                return content.decode('utf-8')
                
        except ClientError as e:
            self.logger.error(f"Failed to download data from {key}: {e}")
            raise

    async def generate_presigned_url(self, key: str, expiration: int = 3600, 
                                     method: str = 'GET') -> str:
        """Generate presigned URL for download/upload."""
        client = await self._get_client()
        
        try:
            operation = 'get_object' if method == 'GET' else 'put_object'
            
            url = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.generate_presigned_url(
                    operation,
                    Params={'Bucket': self.bucket_name, 'Key': key},
                    ExpiresIn=expiration
                )
            )
            
            self.logger.debug(f"Generated presigned URL for {key} (expires in {expiration}s)")
            return url
            
        except ClientError as e:
            self.logger.error(f"Failed to generate presigned URL for {key}: {e}")
            raise

    async def check_etag_conflict(self, key: str, expected_etag: str) -> bool:
        """Check for ETag conflicts for optimistic concurrency control."""
        client = await self._get_client()
        
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.head_object(Bucket=self.bucket_name, Key=key)
            )
            
            current_etag = response['ETag'].strip('"')
            return current_etag != expected_etag
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                # Object doesn't exist, no conflict if expected_etag is None
                return expected_etag is not None
            else:
                self.logger.error(f"Failed to check ETag for {key}: {e}")
                raise

    async def _update_manifest(self, entry: ManifestEntry):
        """Update the manifest file with a new entry."""
        manifest_key = f"manifests/{entry.module}/{entry.user_id}/manifest.jsonl"
        
        # Try to get existing manifest
        try:
            existing_data = await self.download_data(manifest_key)
            if not isinstance(existing_data, list):
                existing_data = []
        except ClientError:
            existing_data = []
        
        # Add new entry
        existing_data.append(asdict(entry))
        
        # Upload updated manifest
        await self.upload_jsonl_data(
            module='_system', 
            user_id='manifests',
            data=existing_data,
            metadata={'manifest_for': f"{entry.module}/{entry.user_id}"}
        )

    async def search_data(self, module: str, user_id: str, query: str) -> List[ManifestEntry]:
        """Simple text search through manifest entries."""
        manifest_key = f"manifests/{module}/{user_id}/manifest.jsonl"
        
        try:
            manifest_data = await self.download_data(manifest_key)
            if not isinstance(manifest_data, list):
                return []
            
            # Simple text search in metadata and keys
            results = []
            query_lower = query.lower()
            
            for item in manifest_data:
                entry = ManifestEntry(**item)
                searchable_text = f"{entry.key} {entry.data_type}"
                if entry.metadata:
                    searchable_text += " " + " ".join(str(v) for v in entry.metadata.values())
                
                if query_lower in searchable_text.lower():
                    results.append(entry)
            
            return results
            
        except ClientError:
            return []

    async def list_objects(self, prefix: str = "", max_keys: int = 1000) -> List[R2Object]:
        """List objects in the bucket with optional prefix filter."""
        client = await self._get_client()
        
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=prefix,
                    MaxKeys=max_keys
                )
            )
            
            objects = []
            for obj in response.get('Contents', []):
                objects.append(R2Object(
                    key=obj['Key'],
                    etag=obj['ETag'].strip('"'),
                    size=obj['Size'],
                    last_modified=obj['LastModified']
                ))
            
            return objects
            
        except ClientError as e:
            self.logger.error(f"Failed to list objects: {e}")
            raise

    async def delete_object(self, key: str) -> bool:
        """Delete an object from R2."""
        client = await self._get_client()
        
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.delete_object(Bucket=self.bucket_name, Key=key)
            )
            
            self.logger.info(f"Deleted object: {key}")
            return True
            
        except ClientError as e:
            self.logger.error(f"Failed to delete object {key}: {e}")
            return False