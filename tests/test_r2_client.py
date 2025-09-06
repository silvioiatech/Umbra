"""
Tests for F4R2 R2Client.
Tests Cloudflare R2 client operations and error handling.
"""
import pytest
import boto3
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError, BotoCoreError

from umbra.storage.r2_client import (
    R2Client, 
    R2ClientError, 
    R2ConnectionError, 
    R2AuthenticationError, 
    R2NotFoundError
)


class TestR2ClientConfiguration:
    """Test R2Client configuration and initialization."""
    
    @pytest.fixture
    def valid_config(self):
        """Mock valid R2 configuration."""
        config = Mock()
        config.R2_ACCOUNT_ID = "test_account_id"
        config.R2_ACCESS_KEY_ID = "test_access_key"
        config.R2_SECRET_ACCESS_KEY = "test_secret_key"
        config.R2_BUCKET = "test-bucket"
        config.R2_ENDPOINT = "https://test_account_id.r2.cloudflarestorage.com"
        return config
    
    @pytest.fixture
    def incomplete_config(self):
        """Mock incomplete R2 configuration."""
        config = Mock()
        config.R2_ACCOUNT_ID = "test_account_id"
        config.R2_ACCESS_KEY_ID = None
        config.R2_SECRET_ACCESS_KEY = "test_secret_key"
        config.R2_BUCKET = "test-bucket"
        config.R2_ENDPOINT = None
        return config
    
    def test_valid_configuration(self, valid_config):
        """Test client initialization with valid configuration."""
        
        with patch('boto3.client') as mock_boto_client, \
             patch.object(R2Client, '_initialize_client') as mock_init:
            
            client = R2Client(valid_config)
            
            assert client.account_id == "test_account_id"
            assert client.access_key_id == "test_access_key"
            assert client.secret_access_key == "test_secret_key"
            assert client.bucket_name == "test-bucket"
            assert client.endpoint_url == "https://test_account_id.r2.cloudflarestorage.com"
            assert client.is_configured() == True
    
    def test_auto_endpoint_generation(self):
        """Test automatic endpoint URL generation from account ID."""
        
        config = Mock()
        config.R2_ACCOUNT_ID = "abc123"
        config.R2_ACCESS_KEY_ID = "test_key"
        config.R2_SECRET_ACCESS_KEY = "test_secret"
        config.R2_BUCKET = "test-bucket"
        config.R2_ENDPOINT = None  # No explicit endpoint
        
        with patch.object(R2Client, '_initialize_client'):
            client = R2Client(config)
            
            assert client.endpoint_url == "https://abc123.r2.cloudflarestorage.com"
    
    def test_incomplete_configuration(self, incomplete_config):
        """Test client with incomplete configuration."""
        
        with patch.object(R2Client, '_initialize_client'):
            client = R2Client(incomplete_config)
            
            assert client.is_configured() == False
            assert client.is_available() == False
    
    def test_boto_config_optimization(self, valid_config):
        """Test boto3 configuration is optimized for R2."""
        
        with patch.object(R2Client, '_initialize_client'):
            client = R2Client(valid_config)
            
            # Check boto config settings
            assert client.boto_config.region_name == 'auto'
            assert client.boto_config.retries['max_attempts'] == 3
            assert client.boto_config.retries['mode'] == 'adaptive'
            assert client.boto_config.max_pool_connections == 50


class TestR2ClientInitialization:
    """Test R2Client initialization and connection testing."""
    
    @pytest.fixture
    def valid_config(self):
        config = Mock()
        config.R2_ACCOUNT_ID = "test_account"
        config.R2_ACCESS_KEY_ID = "test_key"
        config.R2_SECRET_ACCESS_KEY = "test_secret"
        config.R2_BUCKET = "test-bucket"
        config.R2_ENDPOINT = "https://test.r2.cloudflarestorage.com"
        return config
    
    def test_successful_initialization(self, valid_config):
        """Test successful S3 client initialization."""
        
        with patch('boto3.client') as mock_boto_client:
            mock_s3_client = Mock()
            mock_boto_client.return_value = mock_s3_client
            
            # Mock successful head_bucket call
            mock_s3_client.head_bucket.return_value = {}
            
            client = R2Client(valid_config)
            
            # Verify boto3 client was created with correct parameters
            mock_boto_client.assert_called_once_with(
                's3',
                endpoint_url="https://test.r2.cloudflarestorage.com",
                aws_access_key_id="test_key",
                aws_secret_access_key="test_secret",
                config=client.boto_config
            )
            
            # Verify head_bucket was called to test connection
            mock_s3_client.head_bucket.assert_called_once_with(Bucket="test-bucket")
            
            assert client.is_available() == True
    
    def test_bucket_not_found_error(self, valid_config):
        """Test handling of bucket not found error."""
        
        with patch('boto3.client') as mock_boto_client:
            mock_s3_client = Mock()
            mock_boto_client.return_value = mock_s3_client
            
            # Mock NoSuchBucket error
            error = ClientError(
                error_response={'Error': {'Code': 'NoSuchBucket'}},
                operation_name='HeadBucket'
            )
            mock_s3_client.head_bucket.side_effect = error
            
            with pytest.raises(R2ClientError, match="does not exist"):
                R2Client(valid_config)
    
    def test_authentication_error(self, valid_config):
        """Test handling of authentication errors."""
        
        with patch('boto3.client') as mock_boto_client:
            mock_s3_client = Mock()
            mock_boto_client.return_value = mock_s3_client
            
            # Mock authentication error
            error = ClientError(
                error_response={'Error': {'Code': 'InvalidAccessKeyId'}},
                operation_name='HeadBucket'
            )
            mock_s3_client.head_bucket.side_effect = error
            
            with pytest.raises(R2AuthenticationError, match="authentication failed"):
                R2Client(valid_config)
    
    def test_connection_error(self, valid_config):
        """Test handling of connection errors."""
        
        with patch('boto3.client') as mock_boto_client:
            mock_s3_client = Mock()
            mock_boto_client.return_value = mock_s3_client
            
            # Mock BotoCoreError
            mock_s3_client.head_bucket.side_effect = BotoCoreError()
            
            with pytest.raises(R2ConnectionError, match="connection error"):
                R2Client(valid_config)


class TestR2ClientOperations:
    """Test R2Client CRUD operations."""
    
    @pytest.fixture
    def client_with_mock_s3(self):
        """Create R2Client with mocked S3 client."""
        config = Mock()
        config.R2_ACCOUNT_ID = "test"
        config.R2_ACCESS_KEY_ID = "key"
        config.R2_SECRET_ACCESS_KEY = "secret"
        config.R2_BUCKET = "bucket"
        config.R2_ENDPOINT = "https://test.r2.cloudflarestorage.com"
        
        with patch.object(R2Client, '_initialize_client'):
            client = R2Client(config)
            client.s3_client = Mock()
            return client
    
    def test_put_object_success(self, client_with_mock_s3):
        """Test successful object upload."""
        client = client_with_mock_s3
        
        # Mock successful put_object response
        client.s3_client.put_object.return_value = {
            'ETag': '"abc123"',
            'VersionId': 'v1'
        }
        
        data = b"test data"
        result = client.put_object(
            key="test/file.txt",
            data=data,
            content_type="text/plain",
            metadata={"key": "value"}
        )
        
        # Verify put_object was called correctly
        client.s3_client.put_object.assert_called_once_with(
            Bucket="bucket",
            Key="test/file.txt",
            Body=data,
            ContentType="text/plain",
            Metadata={"key": "value"}
        )
        
        # Verify result
        assert result["etag"] == "abc123"
        assert result["version_id"] == "v1"
        assert result["size"] == len(data)
        assert "duration_ms" in result
    
    def test_get_object_success(self, client_with_mock_s3):
        """Test successful object download."""
        client = client_with_mock_s3
        
        # Mock successful get_object response
        mock_body = Mock()
        mock_body.read.return_value = b"test data"
        
        client.s3_client.get_object.return_value = {
            'Body': mock_body,
            'ETag': '"abc123"',
            'ContentType': 'text/plain',
            'Metadata': {'key': 'value'},
            'LastModified': '2025-01-01T00:00:00Z'
        }
        
        result = client.get_object("test/file.txt")
        
        # Verify get_object was called correctly
        client.s3_client.get_object.assert_called_once_with(
            Bucket="bucket",
            Key="test/file.txt"
        )
        
        # Verify result
        assert result["data"] == b"test data"
        assert result["etag"] == "abc123"
        assert result["content_type"] == "text/plain"
        assert result["metadata"] == {'key': 'value'}
        assert "duration_ms" in result
    
    def test_get_object_not_found(self, client_with_mock_s3):
        """Test object not found error."""
        client = client_with_mock_s3
        
        # Mock NoSuchKey error
        error = ClientError(
            error_response={'Error': {'Code': 'NoSuchKey'}},
            operation_name='GetObject'
        )
        client.s3_client.get_object.side_effect = error
        
        with pytest.raises(R2NotFoundError, match="not found"):
            client.get_object("nonexistent/file.txt")
    
    def test_head_object_success(self, client_with_mock_s3):
        """Test successful head object operation."""
        client = client_with_mock_s3
        
        # Mock successful head_object response
        client.s3_client.head_object.return_value = {
            'ETag': '"abc123"',
            'ContentType': 'text/plain',
            'ContentLength': 100,
            'Metadata': {'key': 'value'},
            'LastModified': '2025-01-01T00:00:00Z'
        }
        
        result = client.head_object("test/file.txt")
        
        # Verify head_object was called correctly
        client.s3_client.head_object.assert_called_once_with(
            Bucket="bucket",
            Key="test/file.txt"
        )
        
        # Verify result
        assert result["etag"] == "abc123"
        assert result["content_type"] == "text/plain"
        assert result["size"] == 100
        assert result["metadata"] == {'key': 'value'}
    
    def test_delete_object_success(self, client_with_mock_s3):
        """Test successful object deletion."""
        client = client_with_mock_s3
        
        # Mock successful delete_object
        client.s3_client.delete_object.return_value = {}
        
        result = client.delete_object("test/file.txt")
        
        # Verify delete_object was called correctly
        client.s3_client.delete_object.assert_called_once_with(
            Bucket="bucket",
            Key="test/file.txt"
        )
        
        assert result == True
    
    def test_list_objects_success(self, client_with_mock_s3):
        """Test successful object listing."""
        client = client_with_mock_s3
        
        # Mock successful list_objects_v2 response
        client.s3_client.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'test/file1.txt',
                    'ETag': '"abc123"',
                    'Size': 100,
                    'LastModified': '2025-01-01T00:00:00Z'
                },
                {
                    'Key': 'test/file2.txt',
                    'ETag': '"def456"',
                    'Size': 200,
                    'LastModified': '2025-01-01T01:00:00Z'
                }
            ],
            'IsTruncated': False,
            'KeyCount': 2
        }
        
        result = client.list_objects(prefix="test/", max_keys=10)
        
        # Verify list_objects_v2 was called correctly
        client.s3_client.list_objects_v2.assert_called_once_with(
            Bucket="bucket",
            MaxKeys=10,
            Prefix="test/"
        )
        
        # Verify result
        assert len(result["objects"]) == 2
        assert result["objects"][0]["key"] == "test/file1.txt"
        assert result["objects"][0]["etag"] == "abc123"
        assert result["objects"][0]["size"] == 100
        assert result["is_truncated"] == False
        assert result["key_count"] == 2
    
    def test_generate_presigned_url_success(self, client_with_mock_s3):
        """Test successful presigned URL generation."""
        client = client_with_mock_s3
        
        # Mock successful presigned URL generation
        expected_url = "https://test.r2.cloudflarestorage.com/bucket/test/file.txt?X-Amz-Signature=..."
        client.s3_client.generate_presigned_url.return_value = expected_url
        
        result = client.generate_presigned_url(
            key="test/file.txt",
            expiration=3600,
            method="get_object"
        )
        
        # Verify generate_presigned_url was called correctly
        client.s3_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={'Bucket': "bucket", 'Key': "test/file.txt"},
            ExpiresIn=3600
        )
        
        assert result == expected_url
    
    def test_unavailable_client_operations(self):
        """Test operations fail when client is not available."""
        config = Mock()
        config.R2_ACCESS_KEY_ID = None  # Missing key makes client unavailable
        
        with patch.object(R2Client, '_initialize_client'):
            client = R2Client(config)
            client.s3_client = None
            
            # All operations should raise R2ClientError
            with pytest.raises(R2ClientError, match="not available"):
                client.put_object("key", b"data")
            
            with pytest.raises(R2ClientError, match="not available"):
                client.get_object("key")
            
            with pytest.raises(R2ClientError, match="not available"):
                client.head_object("key")
            
            with pytest.raises(R2ClientError, match="not available"):
                client.delete_object("key")
            
            with pytest.raises(R2ClientError, match="not available"):
                client.list_objects()
            
            with pytest.raises(R2ClientError, match="not available"):
                client.generate_presigned_url("key")


class TestR2ClientUtilities:
    """Test R2Client utility methods."""
    
    def test_get_client_info(self):
        """Test client info retrieval."""
        config = Mock()
        config.R2_ACCOUNT_ID = "test123"
        config.R2_ACCESS_KEY_ID = "key"
        config.R2_SECRET_ACCESS_KEY = "secret"
        config.R2_BUCKET = "test-bucket"
        config.R2_ENDPOINT = "https://test.r2.cloudflarestorage.com"
        
        with patch.object(R2Client, '_initialize_client'):
            client = R2Client(config)
            
            info = client.get_client_info()
            
            assert info["configured"] == True
            assert info["bucket"] == "test-bucket"
            assert info["endpoint"] == "https://test.r2.cloudflarestorage.com"
            assert info["account_id"] == "test123..."
    
    def test_availability_check_with_exception(self):
        """Test availability check handles exceptions gracefully."""
        config = Mock()
        config.R2_ACCOUNT_ID = "test"
        config.R2_ACCESS_KEY_ID = "key"
        config.R2_SECRET_ACCESS_KEY = "secret"
        config.R2_BUCKET = "bucket"
        config.R2_ENDPOINT = "https://test.r2.cloudflarestorage.com"
        
        with patch.object(R2Client, '_initialize_client'):
            client = R2Client(config)
            client.s3_client = Mock()
            
            # Mock head_bucket to raise exception
            client.s3_client.head_bucket.side_effect = Exception("Connection failed")
            
            # Should return False instead of raising exception
            assert client.is_available() == False


if __name__ == "__main__":
    pytest.main([__file__])
