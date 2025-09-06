"""
Tests for F4R2 ManifestManager.
Tests JSONL/Parquet manifest files with ETag concurrency control.
"""
import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from umbra.storage.manifest import (
    ManifestManager,
    ManifestEntry,
    ManifestError,
    ManifestConcurrencyError,
    PARQUET_AVAILABLE
)
from umbra.storage.objects import ObjectNotFoundError, ObjectStorageError


class TestManifestManagerInitialization:
    """Test ManifestManager initialization."""
    
    @pytest.fixture
    def mock_storage(self):
        """Create mock ObjectStorage."""
        storage = Mock()
        storage.is_available.return_value = True
        return storage
    
    def test_initialization(self, mock_storage):
        """Test ManifestManager initialization."""
        manager = ManifestManager(mock_storage)
        
        assert manager.storage == mock_storage
        assert manager.is_available() == True
    
    def test_unavailable_storage(self):
        """Test ManifestManager with unavailable storage."""
        storage = Mock()
        storage.is_available.return_value = False
        
        manager = ManifestManager(storage)
        assert manager.is_available() == False
    
    def test_key_generation(self, mock_storage):
        """Test manifest key generation."""
        manager = ManifestManager(mock_storage)
        
        # Test JSONL key generation
        jsonl_key = manager._get_jsonl_key("test_module", "expenses", 123)
        assert jsonl_key == "manifests/test_module/expenses-123.jsonl"
        
        jsonl_key_no_user = manager._get_jsonl_key("test_module", "expenses")
        assert jsonl_key_no_user == "manifests/test_module/expenses.jsonl"
        
        # Test Parquet key generation
        parquet_key = manager._get_parquet_key("test_module", "transactions", "2025-01", 123)
        assert parquet_key == "manifests/test_module/transactions-123-2025-01.parquet"
        
        parquet_key_no_user = manager._get_parquet_key("test_module", "transactions", "2025-01")
        assert parquet_key_no_user == "manifests/test_module/transactions-2025-01.parquet"


class TestJSONLManifests:
    """Test JSONL manifest operations."""
    
    @pytest.fixture
    def mock_storage(self):
        """Create mock ObjectStorage."""
        storage = Mock()
        storage.is_available.return_value = True
        return storage
    
    @pytest.fixture
    def manifest_manager(self, mock_storage):
        """Create ManifestManager with mock storage."""
        return ManifestManager(mock_storage)
    
    def test_append_jsonl_new_manifest(self, manifest_manager):
        """Test appending to new JSONL manifest."""
        
        # Mock storage to simulate new manifest (not found)
        manifest_manager.storage.get_object.side_effect = ObjectNotFoundError("Not found")
        manifest_manager.storage.put_object.return_value = {
            "etag": "new123",
            "duration_ms": 50.0
        }
        
        entry_data = {"amount": 100.50, "description": "Test expense"}
        
        result = manifest_manager.append_jsonl(
            module="test_module",
            name="expenses",
            entry=entry_data,
            user_id=123
        )
        
        # Verify get_object was called to check existing manifest
        expected_key = "manifests/test_module/expenses-123.jsonl"
        manifest_manager.storage.get_object.assert_called_once_with(expected_key)
        
        # Verify put_object was called with correct data
        put_call = manifest_manager.storage.put_object.call_args
        assert put_call[1]["key"] == expected_key
        assert put_call[1]["content_type"] == "application/x-ndjson; charset=utf-8"
        
        # Verify JSON line was formatted correctly
        stored_data = put_call[1]["data"].decode('utf-8')
        lines = stored_data.strip().split('\n')
        assert len(lines) == 1
        
        line_data = json.loads(lines[0])
        assert line_data["data"] == entry_data
        assert "timestamp" in line_data
        assert "entry_id" in line_data
        
        # Verify result
        assert result["success"] == True
        assert result["key"] == expected_key
        assert result["etag"] == "new123"
        assert result["attempt"] == 1
        assert result["total_entries"] == 1
    
    def test_append_jsonl_existing_manifest(self, manifest_manager):
        """Test appending to existing JSONL manifest."""
        
        # Mock existing manifest content
        existing_line = json.dumps({
            "timestamp": "2025-01-01T00:00:00Z",
            "entry_id": "1000000",
            "data": {"amount": 50.0, "description": "Existing expense"}
        })
        existing_content = existing_line + "\n"
        
        manifest_manager.storage.get_object.return_value = {
            "data": existing_content.encode('utf-8'),
            "etag": "existing123"
        }
        
        manifest_manager.storage.put_object.return_value = {
            "etag": "updated456",
            "duration_ms": 60.0
        }
        
        entry_data = {"amount": 75.25, "description": "New expense"}
        
        result = manifest_manager.append_jsonl(
            module="test_module",
            name="expenses",
            entry=entry_data,
            user_id=123
        )
        
        # Verify stored data contains both entries
        put_call = manifest_manager.storage.put_object.call_args
        stored_data = put_call[1]["data"].decode('utf-8')
        lines = stored_data.strip().split('\n')
        assert len(lines) == 2
        
        # Verify first line is unchanged
        first_line = json.loads(lines[0])
        assert first_line["data"]["amount"] == 50.0
        
        # Verify second line is new entry
        second_line = json.loads(lines[1])
        assert second_line["data"] == entry_data
        
        assert result["total_entries"] == 2
    
    def test_append_jsonl_concurrency_retry(self, manifest_manager):
        """Test ETag concurrency conflict and retry."""
        
        # First call succeeds (get existing)
        manifest_manager.storage.get_object.return_value = {
            "data": b"",
            "etag": "original123"
        }
        
        # First put_object fails with concurrency error, second succeeds
        manifest_manager.storage.put_object.side_effect = [
            ObjectStorageError("Concurrency conflict"),
            {"etag": "retry456", "duration_ms": 80.0}
        ]
        
        entry_data = {"test": "retry"}
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = manifest_manager.append_jsonl(
                module="test_module",
                name="test",
                entry=entry_data,
                max_retries=2
            )
        
        # Verify it retried and succeeded
        assert result["success"] == True
        assert result["attempt"] == 2
        assert manifest_manager.storage.put_object.call_count == 2
    
    def test_append_jsonl_max_retries_exceeded(self, manifest_manager):
        """Test max retries exceeded for concurrency conflicts."""
        
        manifest_manager.storage.get_object.return_value = {
            "data": b"",
            "etag": "original123"
        }
        
        # Always fail with concurrency error
        manifest_manager.storage.put_object.side_effect = ObjectStorageError("Concurrency conflict")
        
        entry_data = {"test": "fail"}
        
        with patch('time.sleep'):
            with pytest.raises(ManifestConcurrencyError, match="Failed to append after"):
                manifest_manager.append_jsonl(
                    module="test_module",
                    name="test",
                    entry=entry_data,
                    max_retries=1
                )
    
    def test_read_jsonl_success(self, manifest_manager):
        """Test reading JSONL manifest."""
        
        # Create test JSONL content
        entries = [
            {
                "timestamp": "2025-01-01T10:00:00Z",
                "entry_id": "1000001",
                "data": {"amount": 100.0, "description": "First"}
            },
            {
                "timestamp": "2025-01-01T11:00:00Z",
                "entry_id": "1000002",
                "data": {"amount": 200.0, "description": "Second"}
            },
            {
                "timestamp": "2025-01-01T12:00:00Z",
                "entry_id": "1000003",
                "data": {"amount": 300.0, "description": "Third"}
            }
        ]
        
        jsonl_content = "\n".join(json.dumps(entry) for entry in entries) + "\n"
        
        manifest_manager.storage.get_object.return_value = {
            "data": jsonl_content.encode('utf-8')
        }
        
        # Read all entries
        results = list(manifest_manager.read_jsonl("test_module", "expenses", user_id=123))
        
        assert len(results) == 3
        assert all(isinstance(entry, ManifestEntry) for entry in results)
        
        # Verify first entry
        assert results[0].timestamp == "2025-01-01T10:00:00Z"
        assert results[0].entry_id == "1000001"
        assert results[0].data["amount"] == 100.0
    
    def test_read_jsonl_with_limit(self, manifest_manager):
        """Test reading JSONL manifest with limit."""
        
        # Create test content with 5 entries
        entries = []
        for i in range(5):
            entries.append({
                "timestamp": f"2025-01-01T{10+i:02d}:00:00Z",
                "entry_id": f"100000{i}",
                "data": {"amount": float(i * 100), "index": i}
            })
        
        jsonl_content = "\n".join(json.dumps(entry) for entry in entries) + "\n"
        
        manifest_manager.storage.get_object.return_value = {
            "data": jsonl_content.encode('utf-8')
        }
        
        # Read with limit
        results = list(manifest_manager.read_jsonl(
            "test_module", "expenses", user_id=123, limit=3
        ))
        
        assert len(results) == 3
        assert results[0].data["index"] == 0
        assert results[2].data["index"] == 2
    
    def test_read_jsonl_with_timestamp_filter(self, manifest_manager):
        """Test reading JSONL manifest with timestamp filter."""
        
        entries = [
            {
                "timestamp": "2025-01-01T10:00:00Z",
                "entry_id": "1000001",
                "data": {"amount": 100.0}
            },
            {
                "timestamp": "2025-01-01T11:00:00Z",
                "entry_id": "1000002",
                "data": {"amount": 200.0}
            },
            {
                "timestamp": "2025-01-01T12:00:00Z",
                "entry_id": "1000003",
                "data": {"amount": 300.0}
            }
        ]
        
        jsonl_content = "\n".join(json.dumps(entry) for entry in entries) + "\n"
        
        manifest_manager.storage.get_object.return_value = {
            "data": jsonl_content.encode('utf-8')
        }
        
        # Read entries after 11:00
        results = list(manifest_manager.read_jsonl(
            "test_module", "expenses", user_id=123,
            since_timestamp="2025-01-01T10:30:00Z"
        ))
        
        assert len(results) == 2
        assert results[0].data["amount"] == 200.0
        assert results[1].data["amount"] == 300.0
    
    def test_read_jsonl_not_found(self, manifest_manager):
        """Test reading non-existent JSONL manifest."""
        
        manifest_manager.storage.get_object.side_effect = ObjectNotFoundError("Not found")
        
        # Should return empty iterator
        results = list(manifest_manager.read_jsonl("test_module", "nonexistent"))
        assert len(results) == 0
    
    def test_read_jsonl_invalid_json_lines(self, manifest_manager):
        """Test reading JSONL with some invalid JSON lines."""
        
        # Mix valid and invalid JSON lines
        content = """{"timestamp": "2025-01-01T10:00:00Z", "entry_id": "1", "data": {"valid": true}}
{ invalid json line }
{"timestamp": "2025-01-01T11:00:00Z", "entry_id": "2", "data": {"also_valid": true}}
"""
        
        manifest_manager.storage.get_object.return_value = {
            "data": content.encode('utf-8')
        }
        
        # Should skip invalid lines and process valid ones
        results = list(manifest_manager.read_jsonl("test_module", "mixed"))
        
        assert len(results) == 2
        assert results[0].data["valid"] == True
        assert results[1].data["also_valid"] == True


class TestParquetManifests:
    """Test Parquet manifest operations."""
    
    @pytest.fixture
    def mock_storage(self):
        """Create mock ObjectStorage."""
        storage = Mock()
        storage.is_available.return_value = True
        return storage
    
    @pytest.fixture
    def manifest_manager(self, mock_storage):
        """Create ManifestManager with mock storage."""
        return ManifestManager(mock_storage)
    
    def test_write_parquet_success(self, manifest_manager):
        """Test writing Parquet manifest (if pyarrow available)."""
        
        if not PARQUET_AVAILABLE:
            pytest.skip("PyArrow not available, testing CSV fallback instead")
        
        manifest_manager.storage.put_object.return_value = {
            "etag": "parquet123",
            "duration_ms": 100.0
        }
        
        test_data = [
            {"name": "Alice", "age": 30, "amount": 100.50},
            {"name": "Bob", "age": 25, "amount": 75.25},
            {"name": "Charlie", "age": 35, "amount": 200.00}
        ]
        
        with patch('umbra.storage.manifest.PARQUET_AVAILABLE', True), \
             patch('umbra.storage.manifest.pa') as mock_pa, \
             patch('umbra.storage.manifest.pq') as mock_pq:
            
            # Mock PyArrow operations
            mock_table = Mock()
            mock_pa.table.return_value = mock_table
            
            # Mock parquet writing
            mock_buffer = Mock()
            mock_buffer.getvalue.return_value = b"parquet_data"
            
            with patch('io.BytesIO', return_value=mock_buffer):
                result = manifest_manager.write_parquet(
                    module="test_module",
                    name="users",
                    data=test_data,
                    partition="2025-01",
                    user_id=123
                )
        
        # Verify put_object was called
        put_call = manifest_manager.storage.put_object.call_args
        assert put_call[1]["key"] == "manifests/test_module/users-123-2025-01.parquet"
        assert put_call[1]["content_type"] == "application/parquet"
        assert put_call[1]["data"] == b"parquet_data"
        
        # Verify metadata
        metadata = put_call[1]["metadata"]
        assert metadata["manifest_type"] == "parquet"
        assert metadata["module"] == "test_module"
        assert metadata["name"] == "users"
        assert metadata["partition"] == "2025-01"
        assert metadata["record_count"] == "3"
        
        # Verify result
        assert result["success"] == True
        assert result["records"] == 3
        assert result["format"] == "parquet"
        assert result["partition"] == "2025-01"
    
    def test_write_parquet_csv_fallback(self, manifest_manager):
        """Test CSV fallback when PyArrow not available."""
        
        manifest_manager.storage.put_object.return_value = {
            "etag": "csv123",
            "duration_ms": 75.0
        }
        
        test_data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25}
        ]
        
        with patch('umbra.storage.manifest.PARQUET_AVAILABLE', False):
            result = manifest_manager.write_parquet(
                module="test_module",
                name="users",
                data=test_data,
                partition="2025-01"
            )
        
        # Should call CSV fallback
        put_call = manifest_manager.storage.put_object.call_args
        assert put_call[1]["key"] == "manifests/test_module/users-2025-01.csv"
        assert put_call[1]["content_type"] == "text/csv; charset=utf-8"
        
        # Verify CSV format
        csv_content = put_call[1]["data"].decode('utf-8')
        lines = csv_content.strip().split('\n')
        assert len(lines) == 3  # Header + 2 data rows
        assert "name,age" in lines[0]
        assert "Alice,30" in lines[1]
        assert "Bob,25" in lines[2]
        
        assert result["format"] == "csv"
    
    def test_write_parquet_empty_data(self, manifest_manager):
        """Test writing Parquet with empty data."""
        
        with pytest.raises(ManifestError, match="No data provided"):
            manifest_manager.write_parquet(
                module="test_module",
                name="empty",
                data=[]
            )
    
    def test_write_parquet_auto_partition(self, manifest_manager):
        """Test automatic partition generation."""
        
        manifest_manager.storage.put_object.return_value = {
            "etag": "auto123",
            "duration_ms": 50.0
        }
        
        test_data = [{"test": "data"}]
        
        with patch('umbra.storage.manifest.PARQUET_AVAILABLE', False):
            with patch('umbra.storage.manifest.datetime') as mock_datetime:
                # Mock current time for partition generation
                mock_now = Mock()
                mock_now.strftime.return_value = "2025-01"
                mock_datetime.now.return_value = mock_now
                mock_datetime.timezone = timezone
                
                result = manifest_manager.write_parquet(
                    module="test_module",
                    name="auto",
                    data=test_data
                    # No partition specified
                )
        
        # Should use auto-generated partition
        assert result["partition"] == "2025-01"
    
    def test_read_parquet_success(self, manifest_manager):
        """Test reading Parquet manifest."""
        
        if not PARQUET_AVAILABLE:
            pytest.skip("PyArrow not available")
        
        # Mock parquet file data
        manifest_manager.storage.get_object.return_value = {
            "data": b"mock_parquet_data"
        }
        
        expected_records = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25}
        ]
        
        with patch('umbra.storage.manifest.PARQUET_AVAILABLE', True), \
             patch('umbra.storage.manifest.pq') as mock_pq, \
             patch('io.BytesIO') as mock_bytesio:
            
            # Mock PyArrow table
            mock_table = Mock()
            mock_table.to_pylist.return_value = expected_records
            mock_pq.read_table.return_value = mock_table
            
            result = manifest_manager.read_parquet(
                module="test_module",
                name="users",
                partition="2025-01",
                user_id=123
            )
        
        assert result == expected_records
        
        # Verify get_object was called with correct key
        expected_key = "manifests/test_module/users-123-2025-01.parquet"
        manifest_manager.storage.get_object.assert_called_once_with(expected_key)
    
    def test_read_parquet_not_found(self, manifest_manager):
        """Test reading non-existent Parquet manifest."""
        
        manifest_manager.storage.get_object.side_effect = ObjectNotFoundError("Not found")
        
        result = manifest_manager.read_parquet(
            module="test_module",
            name="nonexistent",
            partition="2025-01"
        )
        
        assert result == []
    
    def test_list_partitions(self, manifest_manager):
        """Test listing available partitions."""
        
        # Mock list_objects response
        manifest_manager.storage.list_objects.return_value = {
            "objects": [
                {
                    "key": "manifests/test_module/data-123-2025-01.parquet",
                    "size": 1000,
                    "last_modified": "2025-01-01T00:00:00Z"
                },
                {
                    "key": "manifests/test_module/data-123-2025-02.parquet",
                    "size": 1500,
                    "last_modified": "2025-02-01T00:00:00Z"
                },
                {
                    "key": "manifests/test_module/data-123-2025-03.csv",
                    "size": 800,
                    "last_modified": "2025-03-01T00:00:00Z"
                },
                {
                    "key": "manifests/test_module/other_file.txt",  # Should be ignored
                    "size": 100,
                    "last_modified": "2025-01-01T00:00:00Z"
                }
            ]
        }
        
        result = manifest_manager.list_partitions(
            module="test_module",
            name="data",
            user_id=123
        )
        
        # Should return sorted partitions
        assert len(result) == 3
        
        assert result[0]["partition"] == "2025-01"
        assert result[0]["format"] == "parquet"
        assert result[0]["size"] == 1000
        
        assert result[1]["partition"] == "2025-02"
        assert result[1]["format"] == "parquet"
        
        assert result[2]["partition"] == "2025-03"
        assert result[2]["format"] == "csv"


class TestManifestManagerUtilities:
    """Test ManifestManager utility methods."""
    
    @pytest.fixture
    def manifest_manager(self):
        """Create ManifestManager with mock storage."""
        storage = Mock()
        storage.is_available.return_value = True
        return ManifestManager(storage)
    
    def test_get_manifest_stats(self, manifest_manager):
        """Test manifest statistics retrieval."""
        
        # Mock list_objects response
        manifest_manager.storage.list_objects.return_value = {
            "objects": [
                {"key": "manifests/module1/data.jsonl", "size": 1000},
                {"key": "manifests/module1/archive-2025-01.parquet", "size": 5000},
                {"key": "manifests/module2/logs.jsonl", "size": 2000},
                {"key": "manifests/module2/backup-2025-01.csv", "size": 3000}
            ]
        }
        
        result = manifest_manager.get_manifest_stats()
        
        assert result["available"] == True
        assert result["total_manifests"] == 4
        assert result["by_format"]["jsonl"] == 2
        assert result["by_format"]["parquet"] == 1
        assert result["by_format"]["csv"] == 1
        assert result["by_module"]["module1"] == 2
        assert result["by_module"]["module2"] == 2
        assert result["total_size"] == 11000
        assert result["parquet_available"] == PARQUET_AVAILABLE
    
    def test_get_manifest_stats_unavailable(self):
        """Test manifest statistics when unavailable."""
        storage = Mock()
        storage.is_available.return_value = False
        
        manager = ManifestManager(storage)
        result = manager.get_manifest_stats()
        
        assert result["available"] == False
        assert "error" in result
    
    def test_get_manifest_stats_error(self, manifest_manager):
        """Test manifest statistics error handling."""
        
        manifest_manager.storage.list_objects.side_effect = Exception("API Error")
        
        result = manifest_manager.get_manifest_stats()
        
        assert result["available"] == True
        assert "error" in result
        assert "Failed to get stats" in result["error"]


class TestManifestManagerErrorHandling:
    """Test ManifestManager error handling."""
    
    @pytest.fixture
    def manifest_manager(self):
        """Create ManifestManager with mock storage."""
        storage = Mock()
        storage.is_available.return_value = True
        return ManifestManager(storage)
    
    def test_operations_unavailable_manager(self):
        """Test operations fail when manager is unavailable."""
        storage = Mock()
        storage.is_available.return_value = False
        
        manager = ManifestManager(storage)
        
        # All operations should raise ManifestError
        with pytest.raises(ManifestError, match="not available"):
            manager.append_jsonl("module", "name", {})
        
        with pytest.raises(ManifestError, match="not available"):
            list(manager.read_jsonl("module", "name"))
        
        with pytest.raises(ManifestError, match="not available"):
            manager.write_parquet("module", "name", [])
        
        with pytest.raises(ManifestError, match="not available"):
            manager.read_parquet("module", "name", "partition")
        
        with pytest.raises(ManifestError, match="not available"):
            manager.list_partitions("module", "name")
    
    def test_storage_error_propagation(self, manifest_manager):
        """Test storage errors are properly wrapped."""
        
        # Mock storage error
        manifest_manager.storage.get_object.side_effect = ObjectStorageError("Storage failed")
        
        with pytest.raises(ManifestError, match="Storage failed"):
            list(manifest_manager.read_jsonl("module", "name"))


if __name__ == "__main__":
    pytest.main([__file__])
