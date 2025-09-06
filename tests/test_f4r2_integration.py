"""
Integration tests for F4R2 R2 Object Storage.
Tests complete workflows: R2Client -> ObjectStorage -> ManifestManager -> SearchIndex.
"""
import pytest
import json
import hashlib
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from umbra.storage import (
    R2Client, ObjectStorage, ManifestManager, SearchIndex,
    R2ClientError, ObjectStorageError, ManifestError, SearchIndexError,
    PARQUET_AVAILABLE
)


class TestF4R2BasicIntegration:
    """Test basic F4R2 integration workflow."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock F4R2 configuration."""
        config = Mock()
        config.R2_ACCOUNT_ID = "test_account"
        config.R2_ACCESS_KEY_ID = "test_key"
        config.R2_SECRET_ACCESS_KEY = "test_secret"
        config.R2_BUCKET = "test-bucket"
        config.R2_ENDPOINT = "https://test.r2.cloudflarestorage.com"
        return config
    
    @pytest.fixture
    def full_storage_stack(self, mock_config):
        """Create full F4R2 storage stack with mocked R2Client."""
        
        # Mock R2Client at the bottom
        with patch('umbra.storage.objects.R2Client') as mock_r2_client_class:
            mock_r2_client = Mock()
            mock_r2_client.is_available.return_value = True
            mock_r2_client.bucket_name = "test-bucket"
            mock_r2_client_class.return_value = mock_r2_client
            
            # Create storage stack
            object_storage = ObjectStorage(mock_config)
            manifest_manager = ManifestManager(object_storage)
            search_index = SearchIndex(object_storage)
            
            yield {
                "r2_client": mock_r2_client,
                "object_storage": object_storage,
                "manifest_manager": manifest_manager,
                "search_index": search_index
            }
    
    def test_document_storage_and_indexing_workflow(self, full_storage_stack):
        """Test complete document storage and indexing workflow."""
        
        stack = full_storage_stack
        r2_client = stack["r2_client"]
        object_storage = stack["object_storage"]
        manifest_manager = stack["manifest_manager"]
        search_index = stack["search_index"]
        
        # Step 1: Store document
        document_data = b"This is a test document about machine learning and AI."
        filename = "ml_article.txt"
        
        # Mock R2 operations for document storage
        r2_client.put_object.return_value = {
            "etag": "doc123",
            "size": len(document_data),
            "duration_ms": 50.0
        }
        
        # Mock object_exists for new document
        with patch.object(object_storage, 'object_exists', return_value=False):
            doc_result = object_storage.store_document(
                data=document_data,
                filename=filename,
                content_type="text/plain"
            )
        
        document_sha256 = hashlib.sha256(document_data).hexdigest()
        expected_doc_key = f"documents/{document_sha256}.txt"
        
        assert doc_result["key"] == expected_doc_key
        assert doc_result["sha256"] == document_sha256
        assert doc_result["already_exists"] == False
        
        # Step 2: Add to JSONL manifest
        manifest_entry = {
            "document_id": doc_result["sha256"],
            "filename": filename,
            "content_type": "text/plain",
            "size": len(document_data),
            "stored_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Mock manifest operations
        r2_client.get_object.side_effect = Exception("Not found")  # New manifest
        r2_client.put_object.return_value = {
            "etag": "manifest123",
            "duration_ms": 30.0
        }
        
        manifest_result = manifest_manager.append_jsonl(
            module="documents",
            name="uploads",
            entry=manifest_entry,
            user_id=123
        )
        
        assert manifest_result["success"] == True
        assert manifest_result["total_entries"] == 1
        
        # Step 3: Index document for search
        # Mock search index operations
        search_index._load_index = Mock(return_value={
            "version": "1.0",
            "module": "documents",
            "user_id": 123,
            "inverted_index": {},
            "documents": {},
            "merchants": {}
        })
        
        search_index._save_index = Mock()
        
        index_result = search_index.add_document(
            module="documents",
            document_id=doc_result["sha256"],
            text_content=document_data.decode('utf-8'),
            metadata={"filename": filename, "content_type": "text/plain"},
            user_id=123
        )
        
        assert index_result["success"] == True
        assert index_result["words_indexed"] > 0
        
        # Verify search index was saved
        search_index._save_index.assert_called_once()
        saved_index = search_index._save_index.call_args[0][0]
        
        # Verify document was indexed correctly
        assert doc_result["sha256"] in saved_index["documents"]
        assert "machine" in saved_index["inverted_index"]
        assert "learning" in saved_index["inverted_index"]
        assert doc_result["sha256"] in saved_index["inverted_index"]["machine"]
    
    def test_manifest_and_search_integration(self, full_storage_stack):
        """Test integration between manifests and search."""
        
        stack = full_storage_stack
        r2_client = stack["r2_client"]
        manifest_manager = stack["manifest_manager"]
        search_index = stack["search_index"]
        
        # Create test data for multiple documents
        test_documents = [
            {
                "id": "doc1",
                "content": "Machine learning algorithms for data analysis",
                "merchant": "TechCorp",
                "amount": 1500.00
            },
            {
                "id": "doc2", 
                "content": "Restaurant receipt for business dinner",
                "merchant": "Fine Dining",
                "amount": 85.50
            },
            {
                "id": "doc3",
                "content": "AI conference registration and travel expenses",
                "merchant": "Conference Ltd",
                "amount": 2200.00
            }
        ]
        
        # Step 1: Add all documents to JSONL manifest
        r2_client.get_object.side_effect = Exception("Not found")  # New manifest
        r2_client.put_object.return_value = {"etag": "manifest123"}
        
        for doc in test_documents:
            manifest_manager.append_jsonl(
                module="expenses",
                name="receipts",
                entry={
                    "document_id": doc["id"],
                    "merchant": doc["merchant"],
                    "amount": doc["amount"],
                    "description": doc["content"]
                },
                user_id=123
            )
        
        # Step 2: Index all documents for search
        search_index._load_index = Mock(return_value={
            "version": "1.0",
            "module": "expenses",
            "user_id": 123,
            "inverted_index": {},
            "documents": {},
            "merchants": {}
        })
        
        search_index._save_index = Mock()
        
        for doc in test_documents:
            search_index.add_document(
                module="expenses",
                document_id=doc["id"],
                text_content=doc["content"],
                metadata={"amount": doc["amount"]},
                merchant=doc["merchant"],
                user_id=123
            )
        
        # Step 3: Test search functionality
        final_index = search_index._save_index.call_args[0][0]
        
        # Mock search operations
        search_index._load_index = Mock(return_value=final_index)
        
        # Test keyword search
        ml_results = search_index.search_keywords(
            module="expenses",
            keywords=["machine", "learning"],
            user_id=123,
            operator="AND"
        )
        
        assert len(ml_results) == 1
        assert ml_results[0]["document_id"] == "doc1"
        
        # Test merchant search
        restaurant_results = search_index.search_merchants(
            module="expenses", 
            merchant_query="dining",
            user_id=123
        )
        
        assert len(restaurant_results) == 1
        assert restaurant_results[0]["document_id"] == "doc2"
        assert restaurant_results[0]["merchant"] == "Fine Dining"


class TestF4R2ParquetIntegration:
    """Test Parquet manifest integration."""
    
    @pytest.fixture
    def full_storage_stack(self):
        """Create storage stack for Parquet testing."""
        
        with patch('umbra.storage.objects.R2Client') as mock_r2_client_class:
            mock_r2_client = Mock()
            mock_r2_client.is_available.return_value = True
            mock_r2_client_class.return_value = mock_r2_client
            
            object_storage = ObjectStorage()
            manifest_manager = ManifestManager(object_storage)
            
            yield {
                "r2_client": mock_r2_client,
                "object_storage": object_storage,
                "manifest_manager": manifest_manager
            }
    
    def test_parquet_monthly_partitioning(self, full_storage_stack):
        """Test monthly Parquet partitioning workflow."""
        
        stack = full_storage_stack
        r2_client = stack["r2_client"]
        manifest_manager = stack["manifest_manager"]
        
        # Mock Parquet operations
        r2_client.put_object.return_value = {"etag": "parquet123"}
        
        # Test data for January 2025
        january_transactions = [
            {
                "date": "2025-01-05",
                "amount": 100.00,
                "merchant": "Coffee Shop",
                "category": "Food"
            },
            {
                "date": "2025-01-10", 
                "amount": 1500.00,
                "merchant": "Tech Store",
                "category": "Equipment"
            },
            {
                "date": "2025-01-15",
                "amount": 75.50,
                "merchant": "Gas Station", 
                "category": "Travel"
            }
        ]
        
        # Test data for February 2025
        february_transactions = [
            {
                "date": "2025-02-02",
                "amount": 200.00,
                "merchant": "Restaurant",
                "category": "Food"
            },
            {
                "date": "2025-02-20",
                "amount": 850.00,
                "merchant": "Conference",
                "category": "Education"
            }
        ]
        
        if PARQUET_AVAILABLE:
            # Test with actual Parquet
            with patch('umbra.storage.manifest.PARQUET_AVAILABLE', True), \
                 patch('umbra.storage.manifest.pa') as mock_pa, \
                 patch('umbra.storage.manifest.pq') as mock_pq:
                
                mock_pa.table.return_value = Mock()
                mock_buffer = Mock()
                mock_buffer.getvalue.return_value = b"parquet_data"
                
                with patch('io.BytesIO', return_value=mock_buffer):
                    # Store January data
                    jan_result = manifest_manager.write_parquet(
                        module="finance",
                        name="transactions",
                        data=january_transactions,
                        partition="2025-01",
                        user_id=123
                    )
                    
                    # Store February data  
                    feb_result = manifest_manager.write_parquet(
                        module="finance",
                        name="transactions",
                        data=february_transactions,
                        partition="2025-02",
                        user_id=123
                    )
        else:
            # Test with CSV fallback
            jan_result = manifest_manager.write_parquet(
                module="finance",
                name="transactions", 
                data=january_transactions,
                partition="2025-01",
                user_id=123
            )
            
            feb_result = manifest_manager.write_parquet(
                module="finance",
                name="transactions",
                data=february_transactions,
                partition="2025-02",
                user_id=123
            )
        
        # Verify both partitions were created
        assert jan_result["success"] == True
        assert jan_result["partition"] == "2025-01"
        assert jan_result["records"] == 3
        
        assert feb_result["success"] == True
        assert feb_result["partition"] == "2025-02"
        assert feb_result["records"] == 2
        
        # Verify correct keys were used
        jan_call = r2_client.put_object.call_args_list[0]
        feb_call = r2_client.put_object.call_args_list[1]
        
        expected_format = "parquet" if PARQUET_AVAILABLE else "csv"
        
        assert jan_call[1]["key"] == f"manifests/finance/transactions-123-2025-01.{expected_format}"
        assert feb_call[1]["key"] == f"manifests/finance/transactions-123-2025-02.{expected_format}"
        
        # Test listing partitions
        r2_client.list_objects.return_value = {
            "objects": [
                {
                    "key": f"manifests/finance/transactions-123-2025-01.{expected_format}",
                    "size": 1000,
                    "last_modified": "2025-01-31T23:59:59Z"
                },
                {
                    "key": f"manifests/finance/transactions-123-2025-02.{expected_format}",
                    "size": 800,
                    "last_modified": "2025-02-28T23:59:59Z"
                }
            ]
        }
        
        partitions = manifest_manager.list_partitions(
            module="finance",
            name="transactions",
            user_id=123
        )
        
        assert len(partitions) == 2
        assert partitions[0]["partition"] == "2025-01"
        assert partitions[1]["partition"] == "2025-02"
        assert all(p["format"] == expected_format for p in partitions)


class TestF4R2ErrorHandlingIntegration:
    """Test error handling across F4R2 components."""
    
    @pytest.fixture
    def partially_working_stack(self):
        """Create storage stack with some components failing."""
        
        with patch('umbra.storage.objects.R2Client') as mock_r2_client_class:
            mock_r2_client = Mock()
            mock_r2_client.is_available.return_value = True
            mock_r2_client_class.return_value = mock_r2_client
            
            object_storage = ObjectStorage()
            manifest_manager = ManifestManager(object_storage)
            search_index = SearchIndex(object_storage)
            
            yield {
                "r2_client": mock_r2_client,
                "object_storage": object_storage,
                "manifest_manager": manifest_manager,
                "search_index": search_index
            }
    
    def test_r2_client_failure_propagation(self, partially_working_stack):
        """Test how R2Client failures propagate through the stack."""
        
        stack = partially_working_stack
        r2_client = stack["r2_client"]
        object_storage = stack["object_storage"]
        manifest_manager = stack["manifest_manager"]
        
        # Simulate R2Client failure
        r2_client.put_object.side_effect = Exception("R2 API Error")
        
        # Should propagate through ObjectStorage
        with pytest.raises(ObjectStorageError, match="R2 API Error"):
            object_storage.put_object("test/key", b"data")
        
        # Should propagate through ManifestManager
        with pytest.raises(ManifestError, match="Failed to append"):
            manifest_manager.append_jsonl(
                module="test",
                name="test",
                entry={"test": "data"}
            )
    
    def test_graceful_degradation(self, partially_working_stack):
        """Test graceful degradation when some operations fail."""
        
        stack = partially_working_stack
        r2_client = stack["r2_client"]
        object_storage = stack["object_storage"]
        search_index = stack["search_index"]
        
        # Storage works for reads but fails for writes
        r2_client.get_object.return_value = {
            "data": b"test data",
            "etag": "test123"
        }
        r2_client.put_object.side_effect = Exception("Write failed")
        
        # Read operations should still work
        result = object_storage.get_object("test/key")
        assert result["data"] == b"test data"
        
        # Write operations should fail gracefully
        with pytest.raises(ObjectStorageError):
            object_storage.put_object("test/key", b"new data")
        
        # Search index can still load existing data
        search_index._load_index = Mock(return_value={
            "inverted_index": {"test": ["doc1"]},
            "documents": {"doc1": {"words": ["test"]}},
            "merchants": {}
        })
        
        # Search should work even if save fails
        search_index._save_index = Mock(side_effect=Exception("Save failed"))
        
        results = search_index.search_keywords(
            module="test",
            keywords=["test"]
        )
        
        assert len(results) == 1
        assert results[0]["document_id"] == "doc1"
    
    def test_availability_checks_cascade(self, partially_working_stack):
        """Test availability checks cascade through the stack."""
        
        stack = partially_working_stack
        r2_client = stack["r2_client"]
        object_storage = stack["object_storage"]
        manifest_manager = stack["manifest_manager"]
        search_index = stack["search_index"]
        
        # Make R2Client unavailable
        r2_client.is_available.return_value = False
        
        # All components should report as unavailable
        assert object_storage.is_available() == False
        assert manifest_manager.is_available() == False
        assert search_index.is_available() == False
        
        # Operations should fail with appropriate errors
        with pytest.raises(ObjectStorageError, match="not available"):
            object_storage.put_object("key", b"data")
        
        with pytest.raises(ManifestError, match="not available"):
            manifest_manager.append_jsonl("module", "name", {})
        
        with pytest.raises(SearchIndexError, match="not available"):
            search_index.add_document("module", "doc", "content")


class TestF4R2PerformanceIntegration:
    """Test performance characteristics of F4R2 integration."""
    
    @pytest.fixture
    def performance_stack(self):
        """Create storage stack for performance testing."""
        
        with patch('umbra.storage.objects.R2Client') as mock_r2_client_class:
            mock_r2_client = Mock()
            mock_r2_client.is_available.return_value = True
            
            # Mock fast operations
            mock_r2_client.put_object.return_value = {
                "etag": "fast123",
                "duration_ms": 10.0
            }
            mock_r2_client.get_object.return_value = {
                "data": b"test data",
                "etag": "fast123"
            }
            
            mock_r2_client_class.return_value = mock_r2_client
            
            object_storage = ObjectStorage()
            manifest_manager = ManifestManager(object_storage)
            search_index = SearchIndex(object_storage)
            
            yield {
                "r2_client": mock_r2_client,
                "object_storage": object_storage,
                "manifest_manager": manifest_manager,
                "search_index": search_index
            }
    
    def test_batch_operations_performance(self, performance_stack):
        """Test performance of batch operations."""
        
        stack = performance_stack
        manifest_manager = stack["manifest_manager"]
        search_index = stack["search_index"]
        
        # Mock JSONL operations for batch processing
        stack["r2_client"].get_object.side_effect = Exception("Not found")  # New manifest
        
        # Test batch JSONL append
        start_time = time.time()
        
        for i in range(100):
            manifest_manager.append_jsonl(
                module="performance_test",
                name="batch",
                entry={"id": i, "data": f"test data {i}"}
            )
        
        batch_time = time.time() - start_time
        
        # Should complete reasonably quickly (mocked operations)
        assert batch_time < 1.0  # Should be very fast with mocked operations
        
        # Verify all operations were attempted
        assert stack["r2_client"].put_object.call_count == 100
    
    def test_search_index_scaling(self, performance_stack):
        """Test search index performance with many documents."""
        
        search_index = performance_stack["search_index"]
        
        # Create large index
        large_index = {
            "version": "1.0",
            "inverted_index": {},
            "documents": {},
            "merchants": {}
        }
        
        # Add 1000 documents
        for i in range(1000):
            doc_id = f"doc{i}"
            words = [f"word{j}" for j in range(i % 10)]  # Varying word counts
            
            large_index["documents"][doc_id] = {
                "words": words,
                "merchant": f"Merchant{i % 50}",  # 50 different merchants
                "metadata": {"index": i}
            }
            
            # Add to inverted index
            for word in words:
                if word not in large_index["inverted_index"]:
                    large_index["inverted_index"][word] = []
                large_index["inverted_index"][word].append(doc_id)
            
            # Add to merchant index
            merchant = f"merchant{i % 50}"
            if merchant not in large_index["merchants"]:
                large_index["merchants"][merchant] = []
            large_index["merchants"][merchant].append(doc_id)
        
        search_index._load_index = Mock(return_value=large_index)
        
        # Test search performance
        start_time = time.time()
        
        results = search_index.search_keywords(
            module="performance_test",
            keywords=["word1", "word2"],
            operator="AND"
        )
        
        search_time = time.time() - start_time
        
        # Should complete quickly even with large index
        assert search_time < 0.1
        assert len(results) > 0
    
    def test_concurrent_operations_simulation(self, performance_stack):
        """Test simulation of concurrent operations."""
        
        stack = performance_stack
        manifest_manager = stack["manifest_manager"]
        
        # Simulate concurrent JSONL appends with ETag conflicts
        stack["r2_client"].get_object.return_value = {
            "data": b"existing content\n",
            "etag": "existing123"
        }
        
        # First append succeeds, second fails (simulated conflict), third succeeds
        stack["r2_client"].put_object.side_effect = [
            {"etag": "new123"},  # Success
            Exception("Concurrency conflict"),  # Conflict
            {"etag": "retry456"}  # Retry success
        ]
        
        # Test concurrent appends
        with patch('time.sleep'):  # Speed up retries
            results = []
            
            for i in range(2):
                try:
                    result = manifest_manager.append_jsonl(
                        module="concurrent_test",
                        name="test",
                        entry={"operation": i},
                        max_retries=2
                    )
                    results.append(result)
                except Exception as e:
                    results.append({"error": str(e)})
        
        # First should succeed immediately
        assert results[0]["success"] == True
        assert results[0]["attempt"] == 1
        
        # Second should succeed after retry
        assert results[1]["success"] == True
        assert results[1]["attempt"] == 2


class TestF4R2ConfigurationIntegration:
    """Test F4R2 configuration and setup integration."""
    
    def test_missing_configuration_handling(self):
        """Test handling of missing R2 configuration."""
        
        # Empty configuration
        empty_config = Mock()
        empty_config.R2_ACCOUNT_ID = None
        empty_config.R2_ACCESS_KEY_ID = None
        empty_config.R2_SECRET_ACCESS_KEY = None
        empty_config.R2_BUCKET = None
        empty_config.R2_ENDPOINT = None
        
        with patch('umbra.storage.objects.R2Client') as mock_r2_client_class:
            mock_r2_client = Mock()
            mock_r2_client.is_available.return_value = False
            mock_r2_client_class.return_value = mock_r2_client
            
            # All components should handle unavailable storage gracefully
            object_storage = ObjectStorage(empty_config)
            manifest_manager = ManifestManager(object_storage)
            search_index = SearchIndex(object_storage)
            
            assert object_storage.is_available() == False
            assert manifest_manager.is_available() == False
            assert search_index.is_available() == False
    
    def test_partial_configuration_handling(self):
        """Test handling of partial R2 configuration."""
        
        # Partial configuration (missing secret key)
        partial_config = Mock()
        partial_config.R2_ACCOUNT_ID = "test_account"
        partial_config.R2_ACCESS_KEY_ID = "test_key"
        partial_config.R2_SECRET_ACCESS_KEY = None  # Missing
        partial_config.R2_BUCKET = "test-bucket"
        partial_config.R2_ENDPOINT = "https://test.r2.cloudflarestorage.com"
        
        with patch('umbra.storage.objects.R2Client') as mock_r2_client_class:
            mock_r2_client = Mock()
            mock_r2_client.is_configured.return_value = False
            mock_r2_client.is_available.return_value = False
            mock_r2_client_class.return_value = mock_r2_client
            
            object_storage = ObjectStorage(partial_config)
            
            # Should detect incomplete configuration
            assert object_storage.is_available() == False
    
    def test_statistics_integration(self):
        """Test statistics collection across all F4R2 components."""
        
        with patch('umbra.storage.objects.R2Client') as mock_r2_client_class:
            mock_r2_client = Mock()
            mock_r2_client.is_available.return_value = True
            mock_r2_client.bucket_name = "test-bucket"
            
            # Mock statistics responses
            mock_r2_client.list_objects.return_value = {
                "objects": [
                    {"key": "manifests/module1/data.jsonl", "size": 1000},
                    {"key": "documents/abc123.pdf", "size": 5000}
                ],
                "key_count": 2
            }
            
            mock_r2_client_class.return_value = mock_r2_client
            
            object_storage = ObjectStorage()
            manifest_manager = ManifestManager(object_storage)
            search_index = SearchIndex(object_storage)
            
            # Get statistics from all components
            storage_stats = object_storage.get_storage_stats()
            manifest_stats = manifest_manager.get_manifest_stats()
            
            # Mock search index stats
            search_index._load_index = Mock(return_value={
                "stats": {"total_documents": 10, "total_terms": 100}
            })
            index_stats = search_index.get_index_stats("test_module")
            
            # Verify statistics are available
            assert storage_stats["available"] == True
            assert storage_stats["bucket"] == "test-bucket"
            
            assert manifest_stats["available"] == True
            assert manifest_stats["total_manifests"] >= 0
            
            assert index_stats["available"] == True
            assert index_stats["stats"]["total_documents"] == 10


if __name__ == "__main__":
    pytest.main([__file__])
