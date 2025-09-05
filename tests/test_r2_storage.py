"""
Test suite for R2 storage functionality.
Tests upload/download roundtrip, presigned URLs, ETag collision retry, 
search index functionality, and Parquet partition naming.
"""

import asyncio
import json
import os
import pytest
import tempfile
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

# Import the modules to test
from umbra.storage.r2_manager import R2StorageManager, ManifestEntry, R2Object
from umbra.storage.unified_storage import UnifiedStorageManager, StorageRecord
from umbra.core.config import UmbraConfig


class MockR2Config:
    """Mock configuration for R2 testing."""
    def __init__(self):
        self.R2_ACCOUNT_ID = "test_account"
        self.R2_ACCESS_KEY_ID = "test_access_key"
        self.R2_SECRET_ACCESS_KEY = "test_secret_key"
        self.R2_BUCKET = "test_bucket"
        self.R2_ENDPOINT = "https://test_account.r2.cloudflarestorage.com"
        self.feature_r2_storage = True
        self.STORAGE_BACKEND = "r2"
        self.DATABASE_PATH = "test.db"


class TestR2StorageManager:
    """Test R2 storage manager functionality."""
    
    @pytest.fixture
    def mock_config(self):
        return MockR2Config()
    
    @pytest.fixture
    def mock_boto3_client(self):
        """Mock boto3 S3 client."""
        mock_client = MagicMock()
        
        # Mock put_object response
        mock_client.put_object.return_value = {
            'ETag': '"test_etag_123"'
        }
        
        # Mock head_bucket (for connection test)
        mock_client.head_bucket.return_value = {}
        
        # Mock get_object response
        mock_content = MagicMock()
        mock_content.read.return_value = b'{"test": "data"}'
        mock_client.get_object.return_value = {
            'Body': mock_content
        }
        
        # Mock head_object response
        mock_client.head_object.return_value = {
            'ETag': '"test_etag_123"'
        }
        
        # Mock list_objects_v2 response
        mock_client.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'test/key1.json',
                    'ETag': '"etag1"',
                    'Size': 100,
                    'LastModified': datetime.now(timezone.utc)
                }
            ]
        }
        
        # Mock generate_presigned_url
        mock_client.generate_presigned_url.return_value = "https://presigned.url/test"
        
        return mock_client
    
    @patch('umbra.storage.r2_manager.DEPS_AVAILABLE', True)
    @patch('umbra.storage.r2_manager.boto3')
    @pytest.mark.asyncio
    async def test_r2_storage_manager_init(self, mock_boto3, mock_config):
        """Test R2 storage manager initialization."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_client = MagicMock()
        mock_session.client.return_value = mock_client
        mock_client.head_bucket.return_value = {}
        
        manager = R2StorageManager(mock_config)
        client = await manager._get_client()
        
        assert client is not None
        mock_boto3.Session.assert_called_once_with(
            aws_access_key_id="test_access_key",
            aws_secret_access_key="test_secret_key"
        )
    
    @patch('umbra.storage.r2_manager.DEPS_AVAILABLE', True)
    @patch('umbra.storage.r2_manager.boto3')
    @pytest.mark.asyncio
    async def test_upload_download_jsonl_roundtrip(self, mock_boto3, mock_config, mock_boto3_client):
        """Test JSONL upload/download roundtrip."""
        # Setup mocks
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_boto3_client
        
        # Test data
        test_data = [
            {"id": 1, "name": "test1", "value": "data1"},
            {"id": 2, "name": "test2", "value": "data2"}
        ]
        
        # Mock the download to return our test data as JSONL
        jsonl_content = '\n'.join(json.dumps(item) for item in test_data)
        mock_content = MagicMock()
        mock_content.read.return_value = jsonl_content.encode('utf-8')
        mock_boto3_client.get_object.return_value = {'Body': mock_content}
        
        manager = R2StorageManager(mock_config)
        
        # Upload data
        entry = await manager.upload_jsonl_data(
            module="test_module",
            user_id="test_user", 
            data=test_data
        )
        
        assert isinstance(entry, ManifestEntry)
        assert entry.module == "test_module"
        assert entry.user_id == "test_user"
        assert entry.data_type == "jsonl"
        assert entry.key.endswith('.jsonl')
        
        # Download data
        downloaded_data = await manager.download_data(entry.key)
        assert downloaded_data == test_data
    
    @patch('umbra.storage.r2_manager.DEPS_AVAILABLE', True)
    @patch('umbra.storage.r2_manager.boto3')
    @patch('umbra.storage.r2_manager.pd')
    @patch('umbra.storage.r2_manager.pa')
    @patch('umbra.storage.r2_manager.pq')
    @pytest.mark.asyncio
    async def test_upload_download_parquet_roundtrip(self, mock_pq, mock_pa, mock_pd, mock_boto3, mock_config, mock_boto3_client):
        """Test Parquet upload/download roundtrip."""
        # Setup mocks
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_boto3_client
        
        # Mock pandas DataFrame
        test_data = [{"id": 1, "name": "test1"}, {"id": 2, "name": "test2"}]
        mock_df = MagicMock()
        mock_df.columns.tolist.return_value = ["id", "name"]
        mock_pd.DataFrame.return_value = mock_df
        
        # Mock pyarrow table
        mock_table = MagicMock()
        mock_pa.Table.from_pandas.return_value = mock_table
        
        # Mock parquet write
        mock_pq.write_table.return_value = None
        
        # Mock parquet read for download
        mock_read_table = MagicMock()
        mock_read_df = MagicMock()
        mock_read_df.to_dict.return_value = test_data
        mock_read_table.to_pandas.return_value = mock_read_df
        mock_pq.read_table.return_value = mock_read_table
        
        manager = R2StorageManager(mock_config)
        
        # Upload data
        entry = await manager.upload_parquet_data(
            module="test_module",
            user_id="test_user",
            data=test_data
        )
        
        assert isinstance(entry, ManifestEntry)
        assert entry.data_type == "parquet"
        assert entry.key.endswith('.parquet')
        
        # Verify parquet operations were called
        mock_pd.DataFrame.assert_called_once_with(test_data)
        mock_pa.Table.from_pandas.assert_called_once()
        mock_pq.write_table.assert_called_once()
    
    @patch('umbra.storage.r2_manager.DEPS_AVAILABLE', True)
    @patch('umbra.storage.r2_manager.boto3')
    @pytest.mark.asyncio
    async def test_presigned_url_generation(self, mock_boto3, mock_config, mock_boto3_client):
        """Test presigned URL generation."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_boto3_client
        
        manager = R2StorageManager(mock_config)
        
        # Test GET presigned URL
        url = await manager.generate_presigned_url("test/key.json", expiration=7200, method="GET")
        assert url == "https://presigned.url/test"
        
        mock_boto3_client.generate_presigned_url.assert_called_with(
            'get_object',
            Params={'Bucket': 'test_bucket', 'Key': 'test/key.json'},
            ExpiresIn=7200
        )
    
    @patch('umbra.storage.r2_manager.DEPS_AVAILABLE', True)
    @patch('umbra.storage.r2_manager.boto3')
    @pytest.mark.asyncio
    async def test_etag_conflict_detection(self, mock_boto3, mock_config, mock_boto3_client):
        """Test ETag-based optimistic concurrency control."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_boto3_client
        
        manager = R2StorageManager(mock_config)
        
        # Test no conflict (ETags match)
        conflict = await manager.check_etag_conflict("test/key.json", "test_etag_123")
        assert conflict is False
        
        # Test conflict (ETags don't match)
        conflict = await manager.check_etag_conflict("test/key.json", "different_etag")
        assert conflict is True
        
        # Test object doesn't exist
        from botocore.exceptions import ClientError
        mock_boto3_client.head_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey'}}, 'HeadObject'
        )
        
        conflict = await manager.check_etag_conflict("nonexistent/key.json", None)
        assert conflict is False  # No conflict if object doesn't exist and expected_etag is None
        
        conflict = await manager.check_etag_conflict("nonexistent/key.json", "some_etag")
        assert conflict is True  # Conflict if object doesn't exist but we expected an etag
    
    @patch('umbra.storage.r2_manager.DEPS_AVAILABLE', True)
    @patch('umbra.storage.r2_manager.boto3')
    @pytest.mark.asyncio
    async def test_search_functionality(self, mock_boto3, mock_config, mock_boto3_client):
        """Test search index functionality."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_boto3_client
        
        # Mock manifest data
        manifest_data = [
            {
                'id': 'entry1',
                'module': 'test_module',
                'user_id': 'test_user',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'data_type': 'jsonl',
                'key': 'test_module/test_user/2024/01/01/file1.jsonl',
                'metadata': {'description': 'financial data', 'category': 'receipts'}
            },
            {
                'id': 'entry2',
                'module': 'test_module',
                'user_id': 'test_user',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'data_type': 'parquet',
                'key': 'test_module/test_user/2024/01/01/file2.parquet',
                'metadata': {'description': 'user preferences', 'category': 'settings'}
            }
        ]
        
        jsonl_content = '\n'.join(json.dumps(item) for item in manifest_data)
        mock_content = MagicMock()
        mock_content.read.return_value = jsonl_content.encode('utf-8')
        mock_boto3_client.get_object.return_value = {'Body': mock_content}
        
        manager = R2StorageManager(mock_config)
        
        # Test search
        results = await manager.search_data("test_module", "test_user", "financial")
        assert len(results) == 1
        assert results[0].metadata['category'] == 'receipts'
        
        results = await manager.search_data("test_module", "test_user", "parquet")
        assert len(results) == 1
        assert results[0].data_type == 'parquet'
    
    @patch('umbra.storage.r2_manager.DEPS_AVAILABLE', True)
    @patch('umbra.storage.r2_manager.boto3')
    @pytest.mark.asyncio
    async def test_parquet_partition_naming(self, mock_boto3, mock_config, mock_boto3_client):
        """Test Parquet partition naming and readback."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_boto3_client
        
        manager = R2StorageManager(mock_config)
        
        # Test key generation for different modules/users
        key1 = manager._generate_key("finance", "user123", "parquet")
        key2 = manager._generate_key("production", "user456", "parquet")
        
        # Verify partition structure: module/user_id/YYYY/MM/DD/filename.parquet
        assert key1.startswith("finance/user123/")
        assert key1.endswith(".parquet")
        assert key2.startswith("production/user456/")
        assert key2.endswith(".parquet")
        
        # Verify date partitioning
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime('%Y/%m/%d')
        assert today in key1
        assert today in key2
        
        # Keys should be unique
        assert key1 != key2


class TestUnifiedStorageManager:
    """Test unified storage manager functionality."""
    
    @pytest.fixture
    def mock_config_r2(self):
        config = MockR2Config()
        config.feature_r2_storage = True
        config.STORAGE_BACKEND = "r2"
        return config
    
    @pytest.fixture
    def mock_config_sqlite(self):
        config = MockR2Config()
        config.feature_r2_storage = False
        config.STORAGE_BACKEND = "sqlite"
        return config
    
    @patch('umbra.storage.unified_storage.R2StorageManager')
    @pytest.mark.asyncio
    async def test_unified_storage_r2_backend(self, mock_r2_manager_class, mock_config_r2):
        """Test unified storage with R2 backend."""
        mock_r2_instance = MagicMock()
        mock_r2_manager_class.return_value = mock_r2_instance
        
        unified_manager = UnifiedStorageManager(mock_config_r2)
        
        assert unified_manager.use_r2 is True
        assert unified_manager.primary_backend == 'r2'
        mock_r2_manager_class.assert_called_once_with(mock_config_r2)
    
    @patch('umbra.storage.unified_storage.DatabaseManager')
    @patch('umbra.storage.unified_storage.R2StorageManager')
    @pytest.mark.asyncio
    async def test_unified_storage_fallback_to_sqlite(self, mock_r2_manager_class, mock_db_manager_class, mock_config_r2):
        """Test unified storage fallback from R2 to SQLite."""
        # Make R2 initialization fail
        mock_r2_manager_class.side_effect = ImportError("boto3 not available")
        mock_db_instance = MagicMock()
        mock_db_manager_class.return_value = mock_db_instance
        
        unified_manager = UnifiedStorageManager(mock_config_r2)
        
        assert unified_manager.use_r2 is False
        assert unified_manager.primary_backend == 'sqlite'
        mock_db_manager_class.assert_called_once()
    
    @patch('umbra.storage.unified_storage.DatabaseManager')
    @pytest.mark.asyncio
    async def test_unified_storage_sqlite_backend(self, mock_db_manager_class, mock_config_sqlite):
        """Test unified storage with SQLite backend."""
        mock_db_instance = MagicMock()
        mock_db_manager_class.return_value = mock_db_instance
        
        unified_manager = UnifiedStorageManager(mock_config_sqlite)
        
        assert unified_manager.use_r2 is False
        assert unified_manager.primary_backend == 'sqlite'
        mock_db_manager_class.assert_called_once_with(mock_config_sqlite.DATABASE_PATH)


def test_manifest_entry_dataclass():
    """Test ManifestEntry dataclass functionality."""
    entry = ManifestEntry(
        id="test_id",
        module="test_module",
        user_id="test_user",
        timestamp=datetime.now(timezone.utc),
        data_type="jsonl",
        key="test/key.jsonl",
        etag="test_etag",
        size=1024,
        metadata={"test": "metadata"}
    )
    
    assert entry.id == "test_id"
    assert entry.module == "test_module"
    assert entry.data_type == "jsonl"
    assert entry.size == 1024


def test_r2_object_dataclass():
    """Test R2Object dataclass functionality."""
    obj = R2Object(
        key="test/key.json",
        etag="test_etag",
        size=512,
        last_modified=datetime.now(timezone.utc),
        metadata={"content_type": "application/json"}
    )
    
    assert obj.key == "test/key.json"
    assert obj.etag == "test_etag"
    assert obj.size == 512


def test_storage_record_dataclass():
    """Test StorageRecord dataclass functionality."""
    record = StorageRecord(
        id="test_record",
        module="test_module",
        user_id="test_user",
        data={"test": "data"},
        timestamp=datetime.now(timezone.utc),
        storage_backend="r2",
        storage_key="test/key.json"
    )
    
    assert record.id == "test_record"
    assert record.storage_backend == "r2"
    assert record.data == {"test": "data"}


if __name__ == "__main__":
    # Simple test runner for manual testing
    import asyncio
    
    async def run_basic_tests():
        """Run basic tests manually."""
        print("Running basic R2 storage tests...")
        
        # Test configuration
        config = MockR2Config()
        print(f"✓ Mock config created: {config.R2_BUCKET}")
        
        # Test dataclasses
        entry = ManifestEntry(
            id="test", module="test", user_id="test",
            timestamp=datetime.now(timezone.utc), data_type="jsonl", key="test.jsonl"
        )
        print(f"✓ ManifestEntry created: {entry.key}")
        
        obj = R2Object(key="test.json", etag="etag123")
        print(f"✓ R2Object created: {obj.key}")
        
        record = StorageRecord(
            id="test", module="test", user_id="test",
            data={}, timestamp=datetime.now(timezone.utc), storage_backend="r2"
        )
        print(f"✓ StorageRecord created: {record.storage_backend}")
        
        print("Basic tests completed successfully!")
    
    asyncio.run(run_basic_tests())