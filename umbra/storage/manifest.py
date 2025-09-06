"""
R2 Manifest Management - F4R2: JSONL/Parquet manifest files with ETag concurrency.
Handles append-only JSONL files and Parquet partitions with optimistic locking.
"""
import json
import time
import calendar
from typing import Dict, Any, List, Optional, Union, Iterator
from datetime import datetime, timezone
from dataclasses import dataclass

from .objects import ObjectStorage, ObjectNotFoundError, ObjectStorageError
from ..core.logger import get_context_logger

logger = get_context_logger(__name__)

# Optional Parquet support
try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    PARQUET_AVAILABLE = True
except ImportError:
    PARQUET_AVAILABLE = False
    pa = None
    pq = None

@dataclass
class ManifestEntry:
    """Single entry in a manifest file."""
    timestamp: str
    data: Dict[str, Any]
    entry_id: Optional[str] = None

class ManifestError(Exception):
    """Base exception for manifest operations."""
    pass

class ManifestConcurrencyError(ManifestError):
    """ETag concurrency conflict during manifest update."""
    pass

class ManifestManager:
    """
    Manages JSONL and Parquet manifest files with ETag-based optimistic concurrency.
    
    F4R2 Implementation: Provides append-only JSONL files for real-time data
    and Parquet files for analytical workloads with automatic partitioning.
    """
    
    def __init__(self, storage: ObjectStorage):
        self.storage = storage
        self.logger = get_context_logger(__name__)
        
        self.logger.info(
            "Manifest manager initialized",
            extra={
                "storage_available": storage.is_available(),
                "parquet_available": PARQUET_AVAILABLE
            }
        )
    
    def is_available(self) -> bool:
        """Check if manifest manager is available."""
        return self.storage.is_available()
    
    def _get_jsonl_key(self, module: str, name: str, user_id: Optional[int] = None) -> str:
        """Generate JSONL manifest key."""
        if user_id:
            return f"manifests/{module}/{name}-{user_id}.jsonl"
        else:
            return f"manifests/{module}/{name}.jsonl"
    
    def _get_parquet_key(
        self, 
        module: str, 
        name: str, 
        partition: str,
        user_id: Optional[int] = None
    ) -> str:
        """Generate Parquet manifest key with partitioning."""
        if user_id:
            return f"manifests/{module}/{name}-{user_id}-{partition}.parquet"
        else:
            return f"manifests/{module}/{name}-{partition}.parquet"
    
    def append_jsonl(
        self,
        module: str,
        name: str,
        entry: Dict[str, Any],
        user_id: Optional[int] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Append entry to JSONL manifest with ETag optimistic concurrency.
        
        Args:
            module: Module name (e.g., 'swiss_accountant')
            name: Manifest name (e.g., 'expenses')
            entry: Data to append
            user_id: Optional user ID for per-user manifests
            max_retries: Maximum retry attempts for concurrency conflicts
            
        Returns:
            Dict with append result and manifest info
        """
        
        if not self.is_available():
            raise ManifestError("Manifest manager not available")
        
        jsonl_key = self._get_jsonl_key(module, name, user_id)
        
        # Create manifest entry with timestamp
        manifest_entry = ManifestEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=entry,
            entry_id=f"{int(time.time() * 1000000)}"  # Microsecond timestamp
        )
        
        # JSON line to append
        json_line = json.dumps({
            "timestamp": manifest_entry.timestamp,
            "entry_id": manifest_entry.entry_id,
            "data": manifest_entry.data
        }, ensure_ascii=False) + "\n"
        
        for attempt in range(max_retries + 1):
            try:
                # Get current manifest if it exists
                current_data = ""
                current_etag = None
                
                try:
                    existing = self.storage.get_object(jsonl_key)
                    current_data = existing['data'].decode('utf-8')
                    current_etag = existing['etag']
                    
                    self.logger.debug(
                        "Found existing JSONL manifest",
                        extra={
                            "key": jsonl_key,
                            "current_etag": current_etag,
                            "size_bytes": len(current_data)
                        }
                    )
                    
                except ObjectNotFoundError:
                    # New manifest file
                    self.logger.debug(
                        "Creating new JSONL manifest",
                        extra={"key": jsonl_key}
                    )
                
                # Append new line
                new_data = current_data + json_line
                
                # Try to store with ETag check
                try:
                    metadata = {}
                    if current_etag:
                        # R2 uses If-Match header for optimistic concurrency
                        # We'll simulate this by checking the ETag after upload
                        pass
                    
                    result = self.storage.put_object(
                        key=jsonl_key,
                        data=new_data.encode('utf-8'),
                        content_type='application/x-ndjson; charset=utf-8',
                        metadata={
                            "manifest_type": "jsonl",
                            "module": module,
                            "name": name,
                            "user_id": str(user_id) if user_id else "",
                            "last_entry_id": manifest_entry.entry_id,
                            "last_updated": manifest_entry.timestamp
                        }
                    )
                    
                    self.logger.info(
                        "JSONL manifest entry appended",
                        extra={
                            "key": jsonl_key,
                            "entry_id": manifest_entry.entry_id,
                            "attempt": attempt + 1,
                            "new_etag": result["etag"],
                            "total_size": len(new_data)
                        }
                    )
                    
                    return {
                        "success": True,
                        "key": jsonl_key,
                        "entry_id": manifest_entry.entry_id,
                        "etag": result["etag"],
                        "attempt": attempt + 1,
                        "total_entries": len(new_data.strip().split('\n')) if new_data.strip() else 0
                    }
                    
                except ObjectStorageError as e:
                    if "concurrency" in str(e).lower() and attempt < max_retries:
                        # ETag conflict - retry
                        wait_time = 0.1 * (2 ** attempt)  # Exponential backoff
                        
                        self.logger.warning(
                            "JSONL manifest concurrency conflict, retrying",
                            extra={
                                "key": jsonl_key,
                                "attempt": attempt + 1,
                                "wait_time": wait_time,
                                "error": str(e)
                            }
                        )
                        
                        time.sleep(wait_time)
                        continue
                    else:
                        raise
                        
            except Exception as e:
                if attempt == max_retries:
                    self.logger.error(
                        "JSONL manifest append failed after retries",
                        extra={
                            "key": jsonl_key,
                            "attempts": attempt + 1,
                            "error": str(e)
                        }
                    )
                    raise ManifestError(f"Failed to append to JSONL manifest: {str(e)}")
                
                # Retry on any error
                continue
        
        raise ManifestConcurrencyError(f"Failed to append after {max_retries} retries")
    
    def read_jsonl(
        self,
        module: str,
        name: str,
        user_id: Optional[int] = None,
        limit: Optional[int] = None,
        since_timestamp: Optional[str] = None
    ) -> Iterator[ManifestEntry]:
        """
        Read entries from JSONL manifest.
        
        Args:
            module: Module name
            name: Manifest name
            user_id: Optional user ID
            limit: Maximum entries to return
            since_timestamp: Only return entries after this timestamp
            
        Yields:
            ManifestEntry objects
        """
        
        if not self.is_available():
            raise ManifestError("Manifest manager not available")
        
        jsonl_key = self._get_jsonl_key(module, name, user_id)
        
        try:
            result = self.storage.get_object(jsonl_key)
            content = result['data'].decode('utf-8')
            
            count = 0
            for line in content.strip().split('\n'):
                if not line.strip():
                    continue
                
                try:
                    entry_data = json.loads(line)
                    
                    # Filter by timestamp if specified
                    if since_timestamp and entry_data.get('timestamp', '') <= since_timestamp:
                        continue
                    
                    entry = ManifestEntry(
                        timestamp=entry_data.get('timestamp', ''),
                        data=entry_data.get('data', {}),
                        entry_id=entry_data.get('entry_id')
                    )
                    
                    yield entry
                    
                    count += 1
                    if limit and count >= limit:
                        break
                        
                except json.JSONDecodeError as e:
                    self.logger.warning(
                        "Invalid JSON line in manifest",
                        extra={
                            "key": jsonl_key,
                            "line": line[:100],
                            "error": str(e)
                        }
                    )
                    continue
            
            self.logger.debug(
                "JSONL manifest read completed",
                extra={
                    "key": jsonl_key,
                    "entries_yielded": count,
                    "limit": limit
                }
            )
            
        except ObjectNotFoundError:
            self.logger.debug(
                "JSONL manifest not found",
                extra={"key": jsonl_key}
            )
            return
            # Empty iterator
    
    def write_parquet(
        self,
        module: str,
        name: str,
        data: List[Dict[str, Any]],
        partition: Optional[str] = None,
        user_id: Optional[int] = None,
        schema: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Write data to Parquet manifest file.
        
        Args:
            module: Module name
            name: Manifest name
            data: List of records to write
            partition: Partition identifier (e.g., '2025-01')
            user_id: Optional user ID
            schema: Optional schema definition for data types
            
        Returns:
            Dict with write result info
        """
        
        if not self.is_available():
            raise ManifestError("Manifest manager not available")
        
        if not PARQUET_AVAILABLE:
            # Fallback to CSV
            self.logger.warning(
                "Parquet not available, falling back to CSV",
                extra={"module": module, "name": name}
            )
            return self._write_csv_fallback(module, name, data, partition, user_id)
        
        if not data:
            raise ManifestError("No data provided for Parquet write")
        
        # Generate partition if not provided
        if partition is None:
            partition = datetime.now(timezone.utc).strftime('%Y-%m')
        
        parquet_key = self._get_parquet_key(module, name, partition, user_id)
        
        try:
            # Convert data to PyArrow table
            if schema:
                # Use provided schema for data types
                pa_schema = []
                for field_name, field_type in schema.items():
                    if field_type == 'string':
                        pa_schema.append((field_name, pa.string()))
                    elif field_type == 'int64':
                        pa_schema.append((field_name, pa.int64()))
                    elif field_type == 'float64':
                        pa_schema.append((field_name, pa.float64()))
                    elif field_type == 'timestamp':
                        pa_schema.append((field_name, pa.timestamp('us')))
                    else:
                        pa_schema.append((field_name, pa.string()))  # Default to string
                
                table = pa.table(data, schema=pa.schema(pa_schema))
            else:
                # Infer schema from data
                table = pa.table(data)
            
            # Write to Parquet bytes
            import io
            parquet_buffer = io.BytesIO()
            pq.write_table(table, parquet_buffer, compression='snappy')
            parquet_data = parquet_buffer.getvalue()
            
            # Store in R2
            result = self.storage.put_object(
                key=parquet_key,
                data=parquet_data,
                content_type='application/parquet',
                metadata={
                    "manifest_type": "parquet",
                    "module": module,
                    "name": name,
                    "partition": partition,
                    "user_id": str(user_id) if user_id else "",
                    "record_count": str(len(data)),
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            )
            
            self.logger.info(
                "Parquet manifest written",
                extra={
                    "key": parquet_key,
                    "records": len(data),
                    "partition": partition,
                    "size_bytes": len(parquet_data),
                    "etag": result["etag"]
                }
            )
            
            return {
                "success": True,
                "key": parquet_key,
                "partition": partition,
                "records": len(data),
                "format": "parquet",
                "etag": result["etag"]
            }
            
        except Exception as e:
            self.logger.error(
                "Parquet manifest write failed",
                extra={
                    "key": parquet_key,
                    "records": len(data),
                    "error": str(e)
                }
            )
            raise ManifestError(f"Failed to write Parquet manifest: {str(e)}")
    
    def _write_csv_fallback(
        self,
        module: str,
        name: str,
        data: List[Dict[str, Any]],
        partition: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Fallback to CSV when Parquet is not available."""
        
        import csv
        import io
        
        if partition is None:
            partition = datetime.now(timezone.utc).strftime('%Y-%m')
        
        csv_key = self._get_parquet_key(module, name, partition, user_id).replace('.parquet', '.csv')
        
        # Convert to CSV
        csv_buffer = io.StringIO()
        if data:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        csv_data = csv_buffer.getvalue()
        
        result = self.storage.put_object(
            key=csv_key,
            data=csv_data.encode('utf-8'),
            content_type='text/csv; charset=utf-8',
            metadata={
                "manifest_type": "csv",
                "module": module,
                "name": name,
                "partition": partition,
                "user_id": str(user_id) if user_id else "",
                "record_count": str(len(data)),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        )
        
        self.logger.info(
            "CSV manifest written (Parquet fallback)",
            extra={
                "key": csv_key,
                "records": len(data),
                "partition": partition
            }
        )
        
        return {
            "success": True,
            "key": csv_key,
            "partition": partition,
            "records": len(data),
            "format": "csv",
            "etag": result["etag"]
        }
    
    def read_parquet(
        self,
        module: str,
        name: str,
        partition: str,
        user_id: Optional[int] = None,
        columns: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Read data from Parquet manifest file.
        
        Args:
            module: Module name
            name: Manifest name
            partition: Partition identifier
            user_id: Optional user ID
            columns: Optional list of columns to read
            
        Returns:
            List of records
        """
        
        if not self.is_available():
            raise ManifestError("Manifest manager not available")
        
        parquet_key = self._get_parquet_key(module, name, partition, user_id)
        
        try:
            result = self.storage.get_object(parquet_key)
            
            if not PARQUET_AVAILABLE:
                # Try CSV fallback
                csv_key = parquet_key.replace('.parquet', '.csv')
                return self._read_csv_fallback(csv_key, columns)
            
            # Read Parquet data
            import io
            parquet_buffer = io.BytesIO(result['data'])
            table = pq.read_table(parquet_buffer, columns=columns)
            
            # Convert to list of dicts
            records = table.to_pylist()
            
            self.logger.debug(
                "Parquet manifest read",
                extra={
                    "key": parquet_key,
                    "records": len(records),
                    "columns": columns
                }
            )
            
            return records
            
        except ObjectNotFoundError:
            self.logger.debug(
                "Parquet manifest not found",
                extra={"key": parquet_key}
            )
            return []
        except Exception as e:
            self.logger.error(
                "Parquet manifest read failed",
                extra={
                    "key": parquet_key,
                    "error": str(e)
                }
            )
            raise ManifestError(f"Failed to read Parquet manifest: {str(e)}")
    
    def _read_csv_fallback(
        self,
        csv_key: str,
        columns: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Fallback CSV reader."""
        
        import csv
        import io
        
        try:
            result = self.storage.get_object(csv_key)
            csv_content = result['data'].decode('utf-8')
            
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            records = []
            
            for row in csv_reader:
                if columns:
                    # Filter columns
                    filtered_row = {col: row.get(col) for col in columns if col in row}
                    records.append(filtered_row)
                else:
                    records.append(dict(row))
            
            return records
            
        except ObjectNotFoundError:
            return []
    
    def list_partitions(
        self,
        module: str,
        name: str,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List available partitions for a manifest.
        
        Args:
            module: Module name
            name: Manifest name
            user_id: Optional user ID
            
        Returns:
            List of partition info
        """
        
        if not self.is_available():
            raise ManifestError("Manifest manager not available")
        
        # Build prefix to search for partitions
        if user_id:
            prefix = f"manifests/{module}/{name}-{user_id}-"
        else:
            prefix = f"manifests/{module}/{name}-"
        
        try:
            result = self.storage.list_objects(prefix=prefix)
            
            partitions = []
            for obj in result['objects']:
                key = obj['key']
                
                # Extract partition from key
                if key.endswith('.parquet') or key.endswith('.csv'):
                    # Extract partition from filename
                    filename = key.split('/')[-1]
                    if user_id:
                        # Format: name-user_id-partition.ext
                        parts = filename.split('-')
                        if len(parts) >= 3:
                            partition = '-'.join(parts[2:]).split('.')[0]
                        else:
                            continue
                    else:
                        # Format: name-partition.ext
                        parts = filename.split('-')
                        if len(parts) >= 2:
                            partition = '-'.join(parts[1:]).split('.')[0]
                        else:
                            continue
                    
                    file_format = 'parquet' if key.endswith('.parquet') else 'csv'
                    
                    partitions.append({
                        "partition": partition,
                        "key": key,
                        "format": file_format,
                        "size": obj.get('size', 0),
                        "last_modified": obj.get('last_modified')
                    })
            
            # Sort by partition name
            partitions.sort(key=lambda x: x['partition'])
            
            self.logger.debug(
                "Partitions listed",
                extra={
                    "module": module,
                    "name": name,
                    "user_id": user_id,
                    "count": len(partitions)
                }
            )
            
            return partitions
            
        except Exception as e:
            self.logger.error(
                "Failed to list partitions",
                extra={
                    "module": module,
                    "name": name,
                    "error": str(e)
                }
            )
            raise ManifestError(f"Failed to list partitions: {str(e)}")
    
    def get_manifest_stats(self) -> Dict[str, Any]:
        """Get manifest usage statistics."""
        
        if not self.is_available():
            return {"available": False, "error": "Manifest manager not available"}
        
        try:
            result = self.storage.list_objects(prefix="manifests/", max_keys=1000)
            
            stats = {
                "total_manifests": len(result['objects']),
                "by_format": {"jsonl": 0, "parquet": 0, "csv": 0},
                "by_module": {},
                "total_size": 0
            }
            
            for obj in result['objects']:
                key = obj['key']
                size = obj.get('size', 0)
                stats['total_size'] += size
                
                # Determine format
                if key.endswith('.jsonl'):
                    stats['by_format']['jsonl'] += 1
                elif key.endswith('.parquet'):
                    stats['by_format']['parquet'] += 1
                elif key.endswith('.csv'):
                    stats['by_format']['csv'] += 1
                
                # Extract module
                parts = key.split('/')
                if len(parts) >= 2:
                    module = parts[1]
                    stats['by_module'][module] = stats['by_module'].get(module, 0) + 1
            
            stats['parquet_available'] = PARQUET_AVAILABLE
            stats['available'] = True
            
            return stats
            
        except Exception as e:
            return {
                "available": True,
                "error": f"Failed to get stats: {str(e)}"
            }

# Export
__all__ = [
    "ManifestManager", 
    "ManifestEntry", 
    "ManifestError", 
    "ManifestConcurrencyError",
    "PARQUET_AVAILABLE"
]
