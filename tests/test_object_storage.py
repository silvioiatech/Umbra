"""
Tests for F4R2 ObjectStorage.
Tests high-level object storage operations and utilities.
"""
import pytest
import json
import hashlib
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from umbra.storage.objects import (
    ObjectStorage, 
    ObjectStorageError, 
    ObjectNotFoundError
)
from umbra.storage.r2_client import R2NotFoundError, R2ClientError


class TestObjectStorageBasicOperations:
    """Test basic ObjectStorage operations."""
    
    @pytest.fixture
    def mock_r2_client(self):
        """Create mock R2Client."""
        mock_client = Mock()
        mock_client.is_available.return_value = True
        mock_client.bucket_name = "test-bucket"
        return mock_client
    
    @pytest.fixture
    def object_storage(self, mock_r2_client):
        """Create ObjectStorage with mocked R2Client."""
        with patch('umbra.storage.objects.R2Client', return_value=mock_r2_client):
            storage = ObjectStorage()
            return storage
    
    def test_initialization(self, mock_r2_client):
        """Test ObjectStorage initialization."""
        with patch('umbra.storage.objects.R2Client', return_value=mock_r2_client):
            storage = ObjectStorage()
            
            assert storage.is_available() == True
            assert storage.r2_client == mock_r2_client
    
    def test_put_object_bytes_data(self, object_storage):
        """Test storing bytes data."""
        
        # Mock successful R2 put_object
        object_storage.r2_client.put_object.return_value = {
            "etag": "abc123",
            "size": 9,
            "duration_ms": 100.5
        }
        
        data = b"test data"
        result = object_storage.put_object(
            key="test/file.txt",
            data=data,
            content_type="text/plain"
        )
        
        # Verify R2 client was called correctly
        object_storage.r2_client.put_object.assert_called_once()
        call_args = object_storage.r2_client.put_object.call_args
        
        assert call_args[1]["key"] == "test/file.txt"
        assert call_args[1]["data"] == data
        assert call_args[1]["content_type"] == "text/plain"
        
        # Verify SHA256 was computed and added to metadata
        assert "metadata" in call_args[1]
        assert "sha256" in call_args[1]["metadata"]
        assert "uploaded_at" in call_args[1]["metadata"]
        
        # Verify result
        assert result["etag"] == "abc123"
        assert result["key"] == "test/file.txt"
        assert result["content_type"] == "text/plain"
        assert "sha256" in result
    
    def test_put_object_string_data(self, object_storage):
        """Test storing string data (auto-converted to bytes)."""
        
        object_storage.r2_client.put_object.return_value = {
            "etag": "def456",
            "size": 12,
            "duration_ms": 75.2
        }
        
        data = "test string"
        result = object_storage.put_object(
            key="test/string.txt",
            data=data
        )
        
        # Verify string was converted to bytes and UTF-8 content type was set
        call_args = object_storage.r2_client.put_object.call_args[1]
        assert call_args["data"] == data.encode('utf-8')
        assert call_args["content_type"] == "text/plain; charset=utf-8"
    
    def test_put_object_content_type_detection(self, object_storage):
        """Test automatic content type detection."""
        
        object_storage.r2_client.put_object.return_value = {
            "etag": "ghi789",
            "size": 100,
            "duration_ms": 50.0
        }
        
        # Test various file extensions
        test_cases = [
            ("test.json", "application/json"),
            ("test.html", "text/html"),
            ("test.pdf", "application/pdf"),
            ("test.png", "image/png"),
            ("unknown_extension", "application/octet-stream")
        ]
        
        for filename, expected_type in test_cases:
            object_storage.put_object(key=filename, data=b"test")
            
            call_args = object_storage.r2_client.put_object.call_args[1]
            assert call_args["content_type"] == expected_type
    
    def test_put_object_sha256_verification(self, object_storage):
        """Test SHA256 hash computation and storage."""
        
        object_storage.r2_client.put_object.return_value = {
            "etag": "test123",
            "size": 9,
            "duration_ms": 25.0
        }
        
        data = b"test data"
        expected_sha256 = hashlib.sha256(data).hexdigest()
        
        result = object_storage.put_object(
            key="test/hash.txt",
            data=data,
            verify_sha256=True
        )
        
        # Verify SHA256 was computed correctly
        assert result["sha256"] == expected_sha256
        
        # Verify SHA256 was added to metadata
        call_args = object_storage.r2_client.put_object.call_args[1]
        assert call_args["metadata"]["sha256"] == expected_sha256
    
    def test_put_object_without_sha256(self, object_storage):
        """Test storing object without SHA256 verification."""
        
        object_storage.r2_client.put_object.return_value = {
            "etag": "test456",
            "size": 9,
            "duration_ms": 30.0
        }
        
        result = object_storage.put_object(
            key="test/no_hash.txt",
            data=b"test data",
            verify_sha256=False
        )
        
        # Verify no SHA256 in result or metadata
        assert result["sha256"] is None
        
        call_args = object_storage.r2_client.put_object.call_args[1]
        assert "sha256" not in call_args["metadata"]
    
    def test_get_object_success(self, object_storage):
        """Test successful object retrieval."""
        
        data = b"retrieved data"
        sha256_hash = hashlib.sha256(data).hexdigest()
        
        object_storage.r2_client.get_object.return_value = {
            "data": data,
            "etag": "retrieve123",
            "content_type": "text/plain",
            "metadata": {"sha256": sha256_hash},
            "last_modified": "2025-01-01T00:00:00Z",
            "size": len(data),
            "duration_ms": 45.5
        }
        
        result = object_storage.get_object("test/file.txt", verify_sha256=True)
        
        # Verify R2 client was called
        object_storage.r2_client.get_object.assert_called_once_with("test/file.txt")
        
        # Verify result
        assert result["data"] == data
        assert result["etag"] == "retrieve123"
        assert result["key"] == "test/file.txt"
        assert result["sha256_verified"] == True
    
    def test_get_object_sha256_verification_failed(self, object_storage):
        """Test SHA256 verification failure."""
        
        data = b"retrieved data"
        wrong_sha256 = "wrong_hash"
        
        object_storage.r2_client.get_object.return_value = {
            "data": data,
            "etag": "retrieve456",
            "content_type": "text/plain",
            "metadata": {"sha256": wrong_sha256},
            "last_modified": "2025-01-01T00:00:00Z",
            "size": len(data),
            "duration_ms": 50.0
        }
        
        result = object_storage.get_object("test/file.txt", verify_sha256=True)
        
        # SHA256 verification should fail
        assert result["sha256_verified"] == False
    
    def test_get_object_not_found(self, object_storage):
        """Test object not found error handling."""
        
        object_storage.r2_client.get_object.side_effect = R2NotFoundError("Object not found")
        
        with pytest.raises(ObjectNotFoundError, match="not found"):
            object_storage.get_object("nonexistent/file.txt")
    
    def test_head_object_success(self, object_storage):
        """Test successful head object operation."""
        
        object_storage.r2_client.head_object.return_value = {
            "etag": "head123",
            "content_type": "text/plain",
            "metadata": {"key": "value"},
            "last_modified": "2025-01-01T00:00:00Z",
            "size": 100
        }
        
        result = object_storage.head_object("test/file.txt")
        
        object_storage.r2_client.head_object.assert_called_once_with("test/file.txt")
        
        assert result["etag"] == "head123"
        assert result["key"] == "test/file.txt"
        assert result["size"] == 100
    
    def test_delete_object_success(self, object_storage):
        """Test successful object deletion."""
        
        object_storage.r2_client.delete_object.return_value = True
        
        result = object_storage.delete_object("test/file.txt")
        
        object_storage.r2_client.delete_object.assert_called_once_with("test/file.txt")
        assert result == True
    
    def test_object_exists_true(self, object_storage):
        """Test object exists check (positive case)."""
        
        object_storage.r2_client.head_object.return_value = {
            "etag": "exists123",
            "size": 100
        }
        
        exists = object_storage.object_exists("test/file.txt")
        
        assert exists == True
    
    def test_object_exists_false(self, object_storage):
        """Test object exists check (negative case)."""
        
        object_storage.r2_client.head_object.side_effect = R2NotFoundError("Not found")
        
        exists = object_storage.object_exists("nonexistent/file.txt")
        
        assert exists == False
    
    def test_unavailable_storage_operations(self):
        """Test operations fail when storage is not available."""
        mock_client = Mock()
        mock_client.is_available.return_value = False
        
        with patch('umbra.storage.objects.R2Client', return_value=mock_client):
            storage = ObjectStorage()
            
            # All operations should raise ObjectStorageError
            with pytest.raises(ObjectStorageError, match="not available"):
                storage.put_object("key", b"data")
            
            with pytest.raises(ObjectStorageError, match="not available"):
                storage.get_object("key")
            
            with pytest.raises(ObjectStorageError, match="not available"):
                storage.head_object("key")
            
            with pytest.raises(ObjectStorageError, match="not available"):
                storage.delete_object("key")


class TestObjectStorageUtilities:
    """Test ObjectStorage utility methods."""
    
    @pytest.fixture
    def object_storage(self):
        """Create ObjectStorage with mocked R2Client."""
        mock_client = Mock()
        mock_client.is_available.return_value = True
        mock_client.bucket_name = "test-bucket"
        
        with patch('umbra.storage.objects.R2Client', return_value=mock_client):
            storage = ObjectStorage()
            return storage
    
    def test_list_objects(self, object_storage):
        """Test object listing."""
        
        object_storage.r2_client.list_objects.return_value = {
            "objects": [
                {"key": "test/file1.txt", "size": 100},
                {"key": "test/file2.txt", "size": 200}
            ],
            "is_truncated": False,
            "key_count": 2
        }
        
        result = object_storage.list_objects(prefix="test/", max_keys=10)
        
        object_storage.r2_client.list_objects.assert_called_once_with(
            prefix="test/",
            max_keys=10,
            continuation_token=None
        )
        
        assert len(result["objects"]) == 2
        assert result["key_count"] == 2
    
    def test_generate_presigned_url_download(self, object_storage):
        """Test presigned URL generation for download."""
        
        expected_url = "https://test.r2.com/bucket/test/file.txt?signature=..."
        object_storage.r2_client.generate_presigned_url.return_value = expected_url
        
        result = object_storage.generate_presigned_url(
            key="test/file.txt",
            expiration=3600,
            method="download"
        )
        
        object_storage.r2_client.generate_presigned_url.assert_called_once_with(
            key="test/file.txt",
            expiration=3600,
            method="get_object"
        )
        
        assert result == expected_url
    
    def test_generate_presigned_url_upload(self, object_storage):
        """Test presigned URL generation for upload."""
        
        expected_url = "https://test.r2.com/bucket/test/file.txt?signature=..."
        object_storage.r2_client.generate_presigned_url.return_value = expected_url
        
        result = object_storage.generate_presigned_url(
            key="test/file.txt",
            expiration=1800,
            method="upload"
        )
        
        object_storage.r2_client.generate_presigned_url.assert_called_once_with(
            key="test/file.txt",
            expiration=1800,
            method="put_object"
        )
        
        assert result == expected_url


class TestObjectStorageJSON:
    """Test JSON-specific operations."""
    
    @pytest.fixture
    def object_storage(self):
        """Create ObjectStorage with mocked R2Client."""
        mock_client = Mock()
        mock_client.is_available.return_value = True
        
        with patch('umbra.storage.objects.R2Client', return_value=mock_client):
            storage = ObjectStorage()
            return storage
    
    def test_put_json(self, object_storage):
        """Test JSON object storage."""
        
        object_storage.r2_client.put_object.return_value = {
            "etag": "json123",
            "size": 50,
            "duration_ms": 25.0
        }
        
        test_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        
        result = object_storage.put_json("config/settings.json", test_data)
        
        # Verify put_object was called with JSON data
        call_args = object_storage.r2_client.put_object.call_args[1]
        
        assert call_args["key"] == "config/settings.json"
        assert call_args["content_type"] == "application/json; charset=utf-8"
        
        # Verify data was serialized to JSON
        stored_data = call_args["data"]
        assert isinstance(stored_data, str)
        parsed_data = json.loads(stored_data)
        assert parsed_data == test_data
    
    def test_get_json(self, object_storage):
        """Test JSON object retrieval."""
        
        test_data = {"key": "value", "number": 42}
        json_string = json.dumps(test_data, indent=2)
        
        object_storage.r2_client.get_object.return_value = {
            "data": json_string.encode('utf-8'),
            "etag": "json456",
            "content_type": "application/json",
            "metadata": {},
            "size": len(json_string),
            "duration_ms": 30.0
        }
        
        result = object_storage.get_json("config/settings.json")
        
        object_storage.r2_client.get_object.assert_called_once_with("config/settings.json")
        
        assert result["json_data"] == test_data
        assert result["etag"] == "json456"
    
    def test_get_json_parse_error(self, object_storage):
        """Test JSON parsing error handling."""
        
        # Invalid JSON data
        invalid_json = b"{ invalid json }"
        
        object_storage.r2_client.get_object.return_value = {
            "data": invalid_json,
            "etag": "invalid123",
            "content_type": "application/json",
            "metadata": {},
            "size": len(invalid_json),
            "duration_ms": 20.0
        }
        
        with pytest.raises(ObjectStorageError, match="Failed to parse JSON"):
            object_storage.get_json("config/invalid.json")


class TestObjectStorageDocuments:
    """Test document storage with SHA256-based naming."""
    
    @pytest.fixture
    def object_storage(self):
        """Create ObjectStorage with mocked R2Client."""
        mock_client = Mock()
        mock_client.is_available.return_value = True
        
        with patch('umbra.storage.objects.R2Client', return_value=mock_client):
            storage = ObjectStorage()
            return storage
    
    def test_store_document_new(self, object_storage):
        """Test storing new document."""
        
        # Mock object_exists to return False (new document)
        object_storage.object_exists = Mock(return_value=False)
        
        object_storage.r2_client.put_object.return_value = {
            "etag": "doc123",
            "size": 100,
            "duration_ms": 40.0
        }
        
        data = b"document content"
        filename = "report.pdf"
        content_type = "application/pdf"
        
        expected_sha256 = hashlib.sha256(data).hexdigest()
        expected_key = f"documents/{expected_sha256}.pdf"
        
        result = object_storage.store_document(data, filename, content_type)
        
        # Verify object_exists was called
        object_storage.object_exists.assert_called_once_with(expected_key)
        
        # Verify put_object was called with correct parameters
        call_args = object_storage.r2_client.put_object.call_args[1]
        assert call_args["key"] == expected_key
        assert call_args["data"] == data
        assert call_args["content_type"] == content_type
        assert call_args["metadata"]["original_filename"] == filename
        assert call_args["metadata"]["document_type"] == "user_upload"
        
        # Verify result
        assert result["key"] == expected_key
        assert result["sha256"] == expected_sha256
        assert result["filename"] == filename
        assert result["already_exists"] == False
    
    def test_store_document_existing(self, object_storage):
        """Test storing document that already exists."""
        
        # Mock object_exists to return True (existing document)
        object_storage.object_exists = Mock(return_value=True)
        
        # Mock head_object for existing document info
        object_storage.head_object = Mock(return_value={
            "size": 100,
            "content_type": "application/pdf"
        })
        
        data = b"document content"
        filename = "report.pdf"
        content_type = "application/pdf"
        
        expected_sha256 = hashlib.sha256(data).hexdigest()
        expected_key = f"documents/{expected_sha256}.pdf"
        
        result = object_storage.store_document(data, filename, content_type)
        
        # Verify no put_object call was made
        object_storage.r2_client.put_object.assert_not_called()
        
        # Verify result indicates existing document
        assert result["key"] == expected_key
        assert result["sha256"] == expected_sha256
        assert result["already_exists"] == True
        assert result["size"] == 100
    
    def test_store_document_extension_detection(self, object_storage):
        """Test file extension detection for documents."""
        
        object_storage.object_exists = Mock(return_value=False)
        object_storage.r2_client.put_object.return_value = {
            "etag": "ext123",
            "size": 50,
            "duration_ms": 20.0
        }
        
        data = b"text content"
        
        # Test various scenarios
        test_cases = [
            ("document.txt", "text/plain", ".txt"),
            ("image.png", "image/png", ".png"),
            ("data.json", "application/json", ".json"),
            ("archive.zip", "application/zip", ".zip"),
            ("no_extension", "application/pdf", ""),  # No extension from filename
            ("unknown.xyz", None, ".xyz")  # Unknown content type
        ]
        
        for filename, content_type, expected_ext in test_cases:
            result = object_storage.store_document(data, filename, content_type)
            
            # Verify key includes correct extension
            expected_sha256 = hashlib.sha256(data).hexdigest()
            expected_key = f"documents/{expected_sha256}{expected_ext}"
            assert result["key"] == expected_key


class TestObjectStorageStats:
    """Test storage statistics."""
    
    @pytest.fixture
    def object_storage(self):
        """Create ObjectStorage with mocked R2Client."""
        mock_client = Mock()
        mock_client.is_available.return_value = True
        mock_client.bucket_name = "test-bucket"
        
        with patch('umbra.storage.objects.R2Client', return_value=mock_client):
            storage = ObjectStorage()
            return storage
    
    def test_get_storage_stats_success(self, object_storage):
        """Test successful storage statistics retrieval."""
        
        # Mock list_objects responses
        manifests_response = {
            "objects": [{"key": "manifests/test/data.jsonl", "size": 1000}],
            "key_count": 1
        }
        
        documents_response = {
            "objects": [
                {"key": "documents/abc123.pdf", "size": 5000},
                {"key": "documents/def456.txt", "size": 500}
            ],
            "key_count": 2
        }
        
        exports_response = {
            "objects": [{"key": "exports/test/export.zip", "size": 2000}],
            "key_count": 1
        }
        
        # Configure mock to return different responses based on prefix
        def list_objects_side_effect(prefix, max_keys):
            if prefix == "manifests/":
                return manifests_response
            elif prefix == "documents/":
                return documents_response
            elif prefix == "exports/":
                return exports_response
            else:
                return {"objects": [], "key_count": 0}
        
        object_storage.r2_client.list_objects.side_effect = list_objects_side_effect
        
        result = object_storage.get_storage_stats()
        
        # Verify statistics
        assert result["available"] == True
        assert result["bucket"] == "test-bucket"
        assert result["objects"]["manifests"] == 1
        assert result["objects"]["documents"] == 2
        assert result["objects"]["exports"] == 1
        assert result["objects"]["total"] == 4
        assert result["sizes"]["manifests_bytes"] == 1000
        assert result["sizes"]["documents_bytes"] == 5500
        assert result["sizes"]["exports_bytes"] == 2000
        assert result["sizes"]["total_bytes"] == 8500
    
    def test_get_storage_stats_unavailable(self):
        """Test storage statistics when storage is unavailable."""
        mock_client = Mock()
        mock_client.is_available.return_value = False
        
        with patch('umbra.storage.objects.R2Client', return_value=mock_client):
            storage = ObjectStorage()
            
            result = storage.get_storage_stats()
            
            assert result["available"] == False
            assert "error" in result
    
    def test_get_storage_stats_error(self, object_storage):
        """Test storage statistics error handling."""
        
        object_storage.r2_client.list_objects.side_effect = Exception("API Error")
        
        result = object_storage.get_storage_stats()
        
        assert result["available"] == True
        assert "error" in result
        assert "Failed to get stats" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__])
