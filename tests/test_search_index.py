"""
Tests for F4R2 SearchIndex.
Tests simple inverted index for text search in R2 manifests.
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from umbra.storage.search_index import (
    SearchIndex,
    SearchIndexError
)
from umbra.storage.objects import ObjectNotFoundError, ObjectStorageError


class TestSearchIndexInitialization:
    """Test SearchIndex initialization and configuration."""
    
    @pytest.fixture
    def mock_storage(self):
        """Create mock ObjectStorage."""
        storage = Mock()
        storage.is_available.return_value = True
        return storage
    
    def test_initialization(self, mock_storage):
        """Test SearchIndex initialization."""
        index = SearchIndex(mock_storage)
        
        assert index.storage == mock_storage
        assert index.is_available() == True
        assert index.min_word_length == 2
        assert index.max_word_length == 50
        assert len(index.stop_words) > 0
        assert 'the' in index.stop_words
        assert 'der' in index.stop_words  # German
        assert 'le' in index.stop_words   # French
    
    def test_unavailable_storage(self):
        """Test SearchIndex with unavailable storage."""
        storage = Mock()
        storage.is_available.return_value = False
        
        index = SearchIndex(storage)
        assert index.is_available() == False


class TestTextNormalization:
    """Test text normalization and word extraction."""
    
    @pytest.fixture
    def search_index(self):
        """Create SearchIndex with mock storage."""
        storage = Mock()
        storage.is_available.return_value = True
        return SearchIndex(storage)
    
    def test_normalize_text(self, search_index):
        """Test text normalization."""
        
        test_cases = [
            ("Hello World", "hello world"),
            ("Café München", "cafe munchen"),
            ("École française", "ecole francaise"),
            ("UPPERCASE", "uppercase"),
            ("Mixed_Case-123", "mixed_case-123")
        ]
        
        for input_text, expected in test_cases:
            result = search_index._normalize_text(input_text)
            assert result == expected
    
    def test_extract_words_basic(self, search_index):
        """Test basic word extraction."""
        
        text = "This is a test document with some words."
        words = search_index._extract_words(text)
        
        # Should exclude stop words and include meaningful words
        assert "test" in words
        assert "document" in words
        assert "words" in words
        
        # Should exclude stop words
        assert "this" not in words
        assert "is" not in words
        assert "a" not in words
        assert "with" not in words
        assert "some" not in words
    
    def test_extract_words_filtering(self, search_index):
        """Test word filtering rules."""
        
        text = "Test 123 word a veryverylongwordthatexceedsthelimit short"
        words = search_index._extract_words(text)
        
        # Should include valid words
        assert "test" in words
        assert "word" in words
        assert "short" in words
        
        # Should exclude pure numbers
        assert "123" not in words
        
        # Should exclude stop words
        assert "a" not in words
        
        # Should exclude too long words (> 50 chars)
        assert "veryverylongwordthatexceedsthelimit" not in words
    
    def test_extract_words_multilingual(self, search_index):
        """Test word extraction with multilingual text."""
        
        text = "Restaurant München Café français English words"
        words = search_index._extract_words(text)
        
        # Should normalize and include all languages
        assert "restaurant" in words
        assert "munchen" in words  # Normalized
        assert "cafe" in words     # Normalized
        assert "francais" in words # Normalized
        assert "english" in words
        assert "words" in words
    
    def test_extract_words_empty_input(self, search_index):
        """Test word extraction with empty/None input."""
        
        assert search_index._extract_words("") == set()
        assert search_index._extract_words(None) == set()
        assert search_index._extract_words("   ") == set()


class TestIndexOperations:
    """Test search index operations."""
    
    @pytest.fixture
    def search_index(self):
        """Create SearchIndex with mock storage."""
        storage = Mock()
        storage.is_available.return_value = True
        return SearchIndex(storage)
    
    def test_index_key_generation(self, search_index):
        """Test search index key generation."""
        
        # Test without user ID
        key = search_index._get_index_key("test_module")
        assert key == "manifests/test_module/search_index.json"
        
        # Test with user ID
        key_with_user = search_index._get_index_key("test_module", 123)
        assert key_with_user == "manifests/test_module/search_index-123.json"
    
    def test_load_index_new(self, search_index):
        """Test loading non-existent index (creates new)."""
        
        # Mock storage to return not found
        search_index.storage.get_json.side_effect = ObjectNotFoundError("Not found")
        
        index_data = search_index._load_index("test_module", 123)
        
        # Should return new empty index
        assert index_data["version"] == "1.0"
        assert index_data["module"] == "test_module"
        assert index_data["user_id"] == 123
        assert index_data["inverted_index"] == {}
        assert index_data["documents"] == {}
        assert index_data["merchants"] == {}
        assert "created_at" in index_data
    
    def test_load_index_existing(self, search_index):
        """Test loading existing index."""
        
        existing_index = {
            "version": "1.0",
            "module": "test_module",
            "user_id": 123,
            "inverted_index": {"test": ["doc1", "doc2"]},
            "documents": {"doc1": {"words": ["test"]}},
            "merchants": {},
            "stats": {"total_documents": 1}
        }
        
        search_index.storage.get_json.return_value = {
            "json_data": existing_index
        }
        
        result = search_index._load_index("test_module", 123)
        
        assert result == existing_index
        
        # Verify correct key was used
        expected_key = "manifests/test_module/search_index-123.json"
        search_index.storage.get_json.assert_called_once_with(expected_key)
    
    def test_save_index(self, search_index):
        """Test saving index to storage."""
        
        index_data = {
            "version": "1.0",
            "module": "test_module",
            "inverted_index": {"test": ["doc1"]},
            "documents": {"doc1": {"words": ["test"]}},
            "merchants": {}
        }
        
        search_index._save_index(index_data, "test_module", 123)
        
        # Verify put_json was called
        search_index.storage.put_json.assert_called_once()
        
        call_args = search_index.storage.put_json.call_args
        saved_key = call_args[0][0]
        saved_data = call_args[0][1]
        
        assert saved_key == "manifests/test_module/search_index-123.json"
        assert "updated_at" in saved_data
        assert saved_data["stats"]["total_documents"] == 1
        assert saved_data["stats"]["total_terms"] == 1


class TestDocumentIndexing:
    """Test document indexing operations."""
    
    @pytest.fixture
    def search_index(self):
        """Create SearchIndex with mock storage."""
        storage = Mock()
        storage.is_available.return_value = True
        return SearchIndex(storage)
    
    def test_add_document_new(self, search_index):
        """Test adding new document to index."""
        
        # Mock empty index
        search_index._load_index = Mock(return_value={
            "version": "1.0",
            "module": "test_module",
            "user_id": 123,
            "inverted_index": {},
            "documents": {},
            "merchants": {}
        })
        
        search_index._save_index = Mock()
        
        result = search_index.add_document(
            module="test_module",
            document_id="doc1",
            text_content="This is a test document about machine learning",
            metadata={"type": "article"},
            merchant="TechCorp",
            user_id=123
        )
        
        # Verify save_index was called
        assert search_index._save_index.call_count == 1
        
        saved_data = search_index._save_index.call_args[0][0]
        
        # Verify document was added
        assert "doc1" in saved_data["documents"]
        doc_info = saved_data["documents"]["doc1"]
        assert doc_info["merchant"] == "TechCorp"
        assert doc_info["metadata"] == {"type": "article"}
        assert "machine" in doc_info["words"]
        assert "learning" in doc_info["words"]
        
        # Verify inverted index
        assert "machine" in saved_data["inverted_index"]
        assert "doc1" in saved_data["inverted_index"]["machine"]
        assert "learning" in saved_data["inverted_index"]
        assert "doc1" in saved_data["inverted_index"]["learning"]
        
        # Verify merchant index
        assert "techcorp" in saved_data["merchants"]
        assert "doc1" in saved_data["merchants"]["techcorp"]
        
        # Verify result
        assert result["success"] == True
        assert result["document_id"] == "doc1"
        assert result["words_indexed"] > 0
    
    def test_add_document_update_existing(self, search_index):
        """Test updating existing document in index."""
        
        # Mock existing index with document
        existing_index = {
            "version": "1.0",
            "module": "test_module",
            "user_id": 123,
            "inverted_index": {"old": {"doc1"}, "word": {"doc1"}},
            "documents": {
                "doc1": {
                    "words": ["old", "word"],
                    "merchant": "OldCorp",
                    "metadata": {"type": "old"}
                }
            },
            "merchants": {"oldcorp": {"doc1"}}
        }
        
        search_index._load_index = Mock(return_value=existing_index)
        search_index._save_index = Mock()
        
        result = search_index.add_document(
            module="test_module",
            document_id="doc1",
            text_content="This is updated content with new words",
            metadata={"type": "updated"},
            merchant="NewCorp",
            user_id=123
        )
        
        saved_data = search_index._save_index.call_args[0][0]
        
        # Verify old words were removed from inverted index
        assert "old" not in saved_data["inverted_index"]
        
        # Verify new words were added
        assert "updated" in saved_data["inverted_index"]
        assert "content" in saved_data["inverted_index"]
        
        # Verify old merchant was removed
        assert "oldcorp" not in saved_data["merchants"]
        
        # Verify new merchant was added
        assert "newcorp" in saved_data["merchants"]
        assert "doc1" in saved_data["merchants"]["newcorp"]
        
        # Verify document was updated
        doc_info = saved_data["documents"]["doc1"]
        assert doc_info["merchant"] == "NewCorp"
        assert doc_info["metadata"]["type"] == "updated"
    
    def test_add_document_unavailable(self, search_index):
        """Test adding document when index is unavailable."""
        search_index.storage.is_available.return_value = False
        
        with pytest.raises(SearchIndexError, match="not available"):
            search_index.add_document(
                module="test_module",
                document_id="doc1",
                text_content="test"
            )


class TestSearchOperations:
    """Test search operations."""
    
    @pytest.fixture
    def search_index_with_data(self):
        """Create SearchIndex with sample data."""
        storage = Mock()
        storage.is_available.return_value = True
        index = SearchIndex(storage)
        
        # Mock index with sample data
        sample_index = {
            "version": "1.0",
            "module": "test_module",
            "user_id": 123,
            "inverted_index": {
                "machine": ["doc1", "doc3"],
                "learning": ["doc1", "doc2"],
                "artificial": ["doc1"],
                "intelligence": ["doc1", "doc3"],
                "python": ["doc2"],
                "programming": ["doc2"],
                "restaurant": ["doc4"],
                "food": ["doc4"]
            },
            "documents": {
                "doc1": {
                    "words": ["machine", "learning", "artificial", "intelligence"],
                    "merchant": "TechCorp",
                    "metadata": {"type": "article"},
                    "indexed_at": "2025-01-01T10:00:00Z"
                },
                "doc2": {
                    "words": ["learning", "python", "programming"],
                    "merchant": "CodeAcademy",
                    "metadata": {"type": "tutorial"},
                    "indexed_at": "2025-01-01T11:00:00Z"
                },
                "doc3": {
                    "words": ["machine", "intelligence"],
                    "merchant": "AILab",
                    "metadata": {"type": "research"},
                    "indexed_at": "2025-01-01T12:00:00Z"
                },
                "doc4": {
                    "words": ["restaurant", "food"],
                    "merchant": "RestaurantGuide",
                    "metadata": {"type": "review"},
                    "indexed_at": "2025-01-01T13:00:00Z"
                }
            },
            "merchants": {
                "techcorp": ["doc1"],
                "codeacademy": ["doc2"],
                "ailab": ["doc3"],
                "restaurantguide": ["doc4"]
            }
        }
        
        index._load_index = Mock(return_value=sample_index)
        return index
    
    def test_search_keywords_and_operator(self, search_index_with_data):
        """Test keyword search with AND operator."""
        
        results = search_index_with_data.search_keywords(
            module="test_module",
            keywords=["machine", "learning"],
            user_id=123,
            operator="AND"
        )
        
        # Should find doc1 (has both "machine" and "learning")
        assert len(results) == 1
        assert results[0]["document_id"] == "doc1"
        assert results[0]["merchant"] == "TechCorp"
        assert results[0]["metadata"]["type"] == "article"
    
    def test_search_keywords_or_operator(self, search_index_with_data):
        """Test keyword search with OR operator."""
        
        results = search_index_with_data.search_keywords(
            module="test_module",
            keywords=["python", "artificial"],
            user_id=123,
            operator="OR"
        )
        
        # Should find doc1 (has "artificial") and doc2 (has "python")
        assert len(results) == 2
        
        doc_ids = [r["document_id"] for r in results]
        assert "doc1" in doc_ids
        assert "doc2" in doc_ids
    
    def test_search_keywords_partial_match(self, search_index_with_data):
        """Test partial keyword matching."""
        
        results = search_index_with_data.search_keywords(
            module="test_module",
            keywords=["intel"],  # Should match "intelligence"
            user_id=123
        )
        
        # Should find doc1 and doc3 (both have "intelligence")
        assert len(results) == 2
        
        doc_ids = [r["document_id"] for r in results]
        assert "doc1" in doc_ids
        assert "doc3" in doc_ids
    
    def test_search_keywords_empty_results(self, search_index_with_data):
        """Test keyword search with no matches."""
        
        results = search_index_with_data.search_keywords(
            module="test_module",
            keywords=["nonexistent", "keywords"],
            user_id=123,
            operator="AND"
        )
        
        assert len(results) == 0
    
    def test_search_keywords_with_limit(self, search_index_with_data):
        """Test keyword search with result limit."""
        
        results = search_index_with_data.search_keywords(
            module="test_module",
            keywords=["machine"],  # Should match doc1 and doc3
            user_id=123,
            limit=1
        )
        
        # Should return only 1 result (most recent)
        assert len(results) == 1
        assert results[0]["document_id"] == "doc3"  # More recent timestamp
    
    def test_search_merchants_exact_match(self, search_index_with_data):
        """Test merchant search with exact match."""
        
        results = search_index_with_data.search_merchants(
            module="test_module",
            merchant_query="TechCorp",
            user_id=123
        )
        
        assert len(results) == 1
        assert results[0]["document_id"] == "doc1"
        assert results[0]["merchant"] == "TechCorp"
    
    def test_search_merchants_partial_match(self, search_index_with_data):
        """Test merchant search with partial match."""
        
        results = search_index_with_data.search_merchants(
            module="test_module",
            merchant_query="corp",  # Should match "techcorp"
            user_id=123
        )
        
        assert len(results) == 1
        assert results[0]["merchant"] == "TechCorp"
    
    def test_search_merchants_case_insensitive(self, search_index_with_data):
        """Test merchant search is case insensitive."""
        
        results = search_index_with_data.search_merchants(
            module="test_module",
            merchant_query="TECHCORP",
            user_id=123
        )
        
        assert len(results) == 1
        assert results[0]["merchant"] == "TechCorp"
    
    def test_search_merchants_empty_query(self, search_index_with_data):
        """Test merchant search with empty query."""
        
        results = search_index_with_data.search_merchants(
            module="test_module",
            merchant_query="",
            user_id=123
        )
        
        assert len(results) == 0
    
    def test_search_unavailable(self, search_index_with_data):
        """Test search when index is unavailable."""
        search_index_with_data.storage.is_available.return_value = False
        
        with pytest.raises(SearchIndexError, match="not available"):
            search_index_with_data.search_keywords("module", ["test"])
        
        with pytest.raises(SearchIndexError, match="not available"):
            search_index_with_data.search_merchants("module", "test")


class TestIndexManagement:
    """Test index management operations."""
    
    @pytest.fixture
    def search_index(self):
        """Create SearchIndex with mock storage."""
        storage = Mock()
        storage.is_available.return_value = True
        return SearchIndex(storage)
    
    def test_remove_document(self, search_index):
        """Test removing document from index."""
        
        # Mock existing index with document
        existing_index = {
            "version": "1.0",
            "inverted_index": {
                "test": {"doc1", "doc2"}, 
                "word": {"doc1"}
            },
            "documents": {
                "doc1": {
                    "words": ["test", "word"],
                    "merchant": "TestCorp"
                },
                "doc2": {
                    "words": ["test"],
                    "merchant": "OtherCorp"
                }
            },
            "merchants": {
                "testcorp": {"doc1"},
                "othercorp": {"doc2"}
            }
        }
        
        search_index._load_index = Mock(return_value=existing_index)
        search_index._save_index = Mock()
        
        result = search_index.remove_document(
            module="test_module",
            document_id="doc1",
            user_id=123
        )
        
        assert result == True
        
        saved_data = search_index._save_index.call_args[0][0]
        
        # Verify document was removed
        assert "doc1" not in saved_data["documents"]
        assert "doc2" in saved_data["documents"]
        
        # Verify words were cleaned up
        assert "word" not in saved_data["inverted_index"]  # Only doc1 had this
        assert saved_data["inverted_index"]["test"] == ["doc2"]  # doc2 still has it
        
        # Verify merchant was cleaned up
        assert "testcorp" not in saved_data["merchants"]
        assert "othercorp" in saved_data["merchants"]
    
    def test_remove_document_not_found(self, search_index):
        """Test removing non-existent document."""
        
        search_index._load_index = Mock(return_value={
            "documents": {},
            "inverted_index": {},
            "merchants": {}
        })
        
        result = search_index.remove_document(
            module="test_module",
            document_id="nonexistent",
            user_id=123
        )
        
        assert result == False
    
    def test_rebuild_index(self, search_index):
        """Test rebuilding index from scratch."""
        
        search_index._save_index = Mock()
        
        documents = [
            {
                "document_id": "doc1",
                "text_content": "This is test content",
                "metadata": {"type": "test"},
                "merchant": "TestCorp"
            },
            {
                "document_id": "doc2",
                "text_content": "Another document with different words",
                "metadata": {"type": "other"},
                "merchant": "OtherCorp"
            },
            {
                "document_id": "invalid_doc",  # Missing text_content
                "metadata": {"type": "invalid"}
            }
        ]
        
        result = search_index.rebuild_index(
            module="test_module",
            documents=documents,
            user_id=123
        )
        
        # Verify result
        assert result["success"] == True
        assert result["indexed_documents"] == 2  # One invalid skipped
        assert result["errors"] == 1
        assert result["total_terms"] > 0
        assert result["total_merchants"] == 2
        
        # Verify save was called
        search_index._save_index.assert_called_once()
        
        saved_data = search_index._save_index.call_args[0][0]
        
        # Verify documents were indexed
        assert "doc1" in saved_data["documents"]
        assert "doc2" in saved_data["documents"]
        assert "invalid_doc" not in saved_data["documents"]
        
        # Verify inverted index was built
        assert "test" in saved_data["inverted_index"]
        assert "content" in saved_data["inverted_index"]
        assert "document" in saved_data["inverted_index"]
        
        # Verify merchant index was built
        assert "testcorp" in saved_data["merchants"]
        assert "othercorp" in saved_data["merchants"]


class TestIndexStatistics:
    """Test index statistics operations."""
    
    @pytest.fixture
    def search_index(self):
        """Create SearchIndex with mock storage."""
        storage = Mock()
        storage.is_available.return_value = True
        return SearchIndex(storage)
    
    def test_get_index_stats(self, search_index):
        """Test getting index statistics."""
        
        sample_index = {
            "version": "1.0",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T12:00:00Z",
            "inverted_index": {
                "machine": ["doc1", "doc2"],
                "learning": ["doc1"],
                "python": ["doc2"]
            },
            "merchants": {
                "techcorp": ["doc1"],
                "codeacademy": ["doc2"]
            },
            "stats": {
                "total_documents": 2,
                "total_terms": 3,
                "total_merchants": 2
            }
        }
        
        search_index._load_index = Mock(return_value=sample_index)
        
        result = search_index.get_index_stats("test_module", 123)
        
        assert result["available"] == True
        assert result["module"] == "test_module"
        assert result["user_id"] == 123
        assert result["version"] == "1.0"
        assert result["stats"]["total_documents"] == 2
        assert result["stats"]["total_terms"] == 3
        assert result["stats"]["total_merchants"] == 2
        assert len(result["sample_terms"]) <= 10
        assert len(result["sample_merchants"]) <= 10
    
    def test_get_index_stats_unavailable(self):
        """Test getting statistics when index is unavailable."""
        storage = Mock()
        storage.is_available.return_value = False
        
        index = SearchIndex(storage)
        result = index.get_index_stats("test_module")
        
        assert result["available"] == False
        assert "error" in result
    
    def test_get_index_stats_error(self, search_index):
        """Test statistics error handling."""
        
        search_index._load_index = Mock(side_effect=Exception("Load failed"))
        
        result = search_index.get_index_stats("test_module")
        
        assert result["available"] == True
        assert "error" in result
        assert "Failed to get stats" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__])
