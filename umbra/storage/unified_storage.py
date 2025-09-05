"""
Unified storage interface that works with both R2 and SQLite.
Provides a migration path from SQLite to R2 storage.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

from .database import DatabaseManager
from .r2_manager import R2StorageManager, ManifestEntry, R2Object
from ..core.logger import get_logger

logger = get_logger("umbra.storage.unified")


@dataclass
class StorageRecord:
    """Unified record format for both storage backends."""
    id: str
    module: str
    user_id: str
    data: Dict[str, Any]
    timestamp: datetime
    storage_backend: str  # 'sqlite' or 'r2'
    storage_key: Optional[str] = None  # R2 key or SQLite row identifier


class UnifiedStorageManager:
    """Unified storage manager that can use R2 or SQLite as backend."""
    
    def __init__(self, config):
        """Initialize unified storage manager."""
        self.config = config
        self.logger = logger
        
        # Determine storage backend
        self.use_r2 = config.feature_r2_storage and config.STORAGE_BACKEND == 'r2'
        
        # Initialize appropriate storage backend(s)
        if self.use_r2:
            try:
                self.r2_manager = R2StorageManager(config)
                self.primary_backend = 'r2'
                self.logger.info("Using R2 as primary storage backend")
            except (ImportError, ValueError) as e:
                self.logger.warning(f"R2 backend unavailable: {e}. Falling back to SQLite.")
                self.use_r2 = False
                
        if not self.use_r2:
            self.db_manager = DatabaseManager(config.DATABASE_PATH)
            self.primary_backend = 'sqlite'
            self.logger.info("Using SQLite as primary storage backend")
            
        # For hybrid mode (future migration support)
        self.hybrid_mode = config.STORAGE_BACKEND == 'hybrid'
        if self.hybrid_mode and self.use_r2:
            self.db_manager = DatabaseManager(config.DATABASE_PATH)
            self.logger.info("Hybrid mode enabled - using both R2 and SQLite")

    async def store_data(self, module: str, user_id: str, data: Dict[str, Any], 
                         data_format: str = 'json') -> StorageRecord:
        """Store data using the configured backend."""
        timestamp = datetime.now(timezone.utc)
        record_id = f"{module}_{user_id}_{int(timestamp.timestamp())}"
        
        if self.use_r2:
            return await self._store_to_r2(record_id, module, user_id, data, data_format, timestamp)
        else:
            return await self._store_to_sqlite(record_id, module, user_id, data, timestamp)

    async def _store_to_r2(self, record_id: str, module: str, user_id: str, 
                           data: Dict[str, Any], data_format: str, timestamp: datetime) -> StorageRecord:
        """Store data to R2."""
        try:
            if data_format == 'jsonl' and isinstance(data.get('records'), list):
                # Store as JSONL if we have multiple records
                entry = await self.r2_manager.upload_jsonl_data(
                    module=module,
                    user_id=user_id,
                    data=data['records'],
                    metadata={'record_id': record_id}
                )
                storage_key = entry.key
            elif data_format == 'parquet' and isinstance(data.get('records'), list):
                # Store as Parquet for structured data
                entry = await self.r2_manager.upload_parquet_data(
                    module=module,
                    user_id=user_id,
                    data=data['records'],
                    metadata={'record_id': record_id}
                )
                storage_key = entry.key
            else:
                # Store as JSON blob for simple key-value data
                blob_key = f"{module}_{user_id}_{record_id}"
                obj = await self.r2_manager.upload_json_blob(
                    key=blob_key,
                    data=data,
                    metadata={'record_id': record_id, 'module': module, 'user_id': user_id}
                )
                storage_key = obj.key
            
            return StorageRecord(
                id=record_id,
                module=module,
                user_id=user_id,
                data=data,
                timestamp=timestamp,
                storage_backend='r2',
                storage_key=storage_key
            )
            
        except Exception as e:
            self.logger.error(f"Failed to store data to R2: {e}")
            # Fallback to SQLite if R2 fails and hybrid mode is enabled
            if self.hybrid_mode and hasattr(self, 'db_manager'):
                self.logger.info("Falling back to SQLite storage")
                return await self._store_to_sqlite(record_id, module, user_id, data, timestamp)
            raise

    async def _store_to_sqlite(self, record_id: str, module: str, user_id: str, 
                               data: Dict[str, Any], timestamp: datetime) -> StorageRecord:
        """Store data to SQLite."""
        try:
            self.db_manager.set_module_data(
                user_id=int(user_id),
                module=module,
                key=record_id,
                value=data
            )
            
            return StorageRecord(
                id=record_id,
                module=module,
                user_id=user_id,
                data=data,
                timestamp=timestamp,
                storage_backend='sqlite',
                storage_key=record_id
            )
            
        except Exception as e:
            self.logger.error(f"Failed to store data to SQLite: {e}")
            raise

    async def retrieve_data(self, module: str, user_id: str, record_id: str = None) -> Union[StorageRecord, List[StorageRecord]]:
        """Retrieve data from the configured backend."""
        if self.use_r2:
            return await self._retrieve_from_r2(module, user_id, record_id)
        else:
            return await self._retrieve_from_sqlite(module, user_id, record_id)

    async def _retrieve_from_r2(self, module: str, user_id: str, record_id: str = None) -> Union[StorageRecord, List[StorageRecord]]:
        """Retrieve data from R2."""
        try:
            if record_id:
                # Search for specific record in manifest
                manifest_entries = await self.r2_manager.search_data(module, user_id, record_id)
                for entry in manifest_entries:
                    if record_id in (entry.metadata or {}).get('record_id', ''):
                        data = await self.r2_manager.download_data(entry.key)
                        return StorageRecord(
                            id=record_id,
                            module=module,
                            user_id=user_id,
                            data=data if isinstance(data, dict) else {'records': data},
                            timestamp=entry.timestamp,
                            storage_backend='r2',
                            storage_key=entry.key
                        )
                
                # Try JSON blob format
                blob_key = f"json_blobs/{module}_{user_id}_{record_id}.json"
                try:
                    data = await self.r2_manager.download_data(blob_key)
                    return StorageRecord(
                        id=record_id,
                        module=module,
                        user_id=user_id,
                        data=data,
                        timestamp=datetime.now(timezone.utc),  # We don't have exact timestamp for blobs
                        storage_backend='r2',
                        storage_key=blob_key
                    )
                except:
                    pass
                    
                return None
            else:
                # Return all records for module/user
                manifest_entries = await self.r2_manager.search_data(module, user_id, "")
                records = []
                for entry in manifest_entries:
                    try:
                        data = await self.r2_manager.download_data(entry.key)
                        records.append(StorageRecord(
                            id=entry.metadata.get('record_id', entry.id),
                            module=module,
                            user_id=user_id,
                            data=data if isinstance(data, dict) else {'records': data},
                            timestamp=entry.timestamp,
                            storage_backend='r2',
                            storage_key=entry.key
                        ))
                    except Exception as e:
                        self.logger.warning(f"Failed to load data from {entry.key}: {e}")
                        
                return records
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve data from R2: {e}")
            raise

    async def _retrieve_from_sqlite(self, module: str, user_id: str, record_id: str = None) -> Union[StorageRecord, List[StorageRecord]]:
        """Retrieve data from SQLite."""
        try:
            if record_id:
                data = self.db_manager.get_module_data(int(user_id), module, record_id)
                if data is not None:
                    return StorageRecord(
                        id=record_id,
                        module=module,
                        user_id=user_id,
                        data=data,
                        timestamp=datetime.now(timezone.utc),  # SQLite doesn't store timestamps for module data
                        storage_backend='sqlite',
                        storage_key=record_id
                    )
                return None
            else:
                # Get all data for module/user
                all_data = self.db_manager.get_module_data(int(user_id), module)
                records = []
                for key, data in all_data.items():
                    records.append(StorageRecord(
                        id=key,
                        module=module,
                        user_id=user_id,
                        data=data,
                        timestamp=datetime.now(timezone.utc),
                        storage_backend='sqlite',
                        storage_key=key
                    ))
                return records
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve data from SQLite: {e}")
            raise

    async def search_data(self, module: str, user_id: str, query: str) -> List[StorageRecord]:
        """Search data across the storage backend."""
        if self.use_r2:
            try:
                manifest_entries = await self.r2_manager.search_data(module, user_id, query)
                records = []
                for entry in manifest_entries:
                    try:
                        data = await self.r2_manager.download_data(entry.key)
                        records.append(StorageRecord(
                            id=entry.metadata.get('record_id', entry.id),
                            module=module,
                            user_id=user_id,
                            data=data if isinstance(data, dict) else {'records': data},
                            timestamp=entry.timestamp,
                            storage_backend='r2',
                            storage_key=entry.key
                        ))
                    except Exception as e:
                        self.logger.warning(f"Failed to load search result from {entry.key}: {e}")
                        
                return records
            except Exception as e:
                self.logger.error(f"Failed to search R2 data: {e}")
                return []
        else:
            # Simple text search in SQLite module data
            try:
                all_data = self.db_manager.get_module_data(int(user_id), module)
                results = []
                query_lower = query.lower()
                
                for key, data in all_data.items():
                    data_str = json.dumps(data, default=str).lower()
                    if query_lower in data_str or query_lower in key.lower():
                        results.append(StorageRecord(
                            id=key,
                            module=module,
                            user_id=user_id,
                            data=data,
                            timestamp=datetime.now(timezone.utc),
                            storage_backend='sqlite',
                            storage_key=key
                        ))
                        
                return results
            except Exception as e:
                self.logger.error(f"Failed to search SQLite data: {e}")
                return []

    async def generate_presigned_url(self, storage_key: str, expiration: int = 3600) -> Optional[str]:
        """Generate presigned URL for R2 objects."""
        if self.use_r2:
            try:
                return await self.r2_manager.generate_presigned_url(storage_key, expiration)
            except Exception as e:
                self.logger.error(f"Failed to generate presigned URL: {e}")
                return None
        else:
            # SQLite doesn't support presigned URLs
            return None

    async def delete_data(self, module: str, user_id: str, record_id: str) -> bool:
        """Delete data from the storage backend."""
        if self.use_r2:
            try:
                # Find and delete from manifest entries
                manifest_entries = await self.r2_manager.search_data(module, user_id, record_id)
                deleted = False
                for entry in manifest_entries:
                    if record_id in (entry.metadata or {}).get('record_id', ''):
                        deleted = await self.r2_manager.delete_object(entry.key)
                        break
                
                # Try JSON blob format if not found in manifest
                if not deleted:
                    blob_key = f"json_blobs/{module}_{user_id}_{record_id}.json"
                    deleted = await self.r2_manager.delete_object(blob_key)
                    
                return deleted
            except Exception as e:
                self.logger.error(f"Failed to delete data from R2: {e}")
                return False
        else:
            try:
                # SQLite doesn't have a direct delete method, set to None
                self.db_manager.set_module_data(int(user_id), module, record_id, None)
                return True
            except Exception as e:
                self.logger.error(f"Failed to delete data from SQLite: {e}")
                return False

    async def get_storage_info(self) -> Dict[str, Any]:
        """Get information about the storage backend."""
        info = {
            'backend': self.primary_backend,
            'hybrid_mode': self.hybrid_mode,
            'r2_available': self.use_r2
        }
        
        if self.use_r2:
            try:
                # Get some R2 statistics
                objects = await self.r2_manager.list_objects(max_keys=10)
                info['r2_object_count_sample'] = len(objects)
                info['r2_bucket'] = self.config.R2_BUCKET
            except Exception as e:
                info['r2_error'] = str(e)
                
        return info


# Global unified storage manager instance
_storage_manager: Optional[UnifiedStorageManager] = None


async def get_storage_manager() -> UnifiedStorageManager:
    """Get or create the global unified storage manager instance."""
    global _storage_manager
    
    if _storage_manager is None:
        from ..core.config import config
        _storage_manager = UnifiedStorageManager(config)
    
    return _storage_manager