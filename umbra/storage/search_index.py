"""
R2 Search Index - F4R2: Simple inverted index for text search in manifests.
Provides keyword and merchant search across stored documents.
"""
import json
import re
from typing import Dict, Set, List, Any, Optional, Tuple
from datetime import datetime, timezone
from collections import defaultdict
import unicodedata

from .objects import ObjectStorage, ObjectNotFoundError, ObjectStorageError
from ..core.logger import get_context_logger

logger = get_context_logger(__name__)

class SearchIndexError(Exception):
    """Base exception for search index operations."""
    pass

class SearchIndex:
    """
    Simple inverted index for text search in R2 manifests.
    
    F4R2 Implementation: Provides basic keyword search functionality
    for documents stored in R2 manifests. Optimized for small to medium datasets.
    """
    
    def __init__(self, storage: ObjectStorage):
        self.storage = storage
        self.logger = get_context_logger(__name__)
        
        # Index configuration
        self.min_word_length = 2
        self.max_word_length = 50
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'among', 'around',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'do', 'does', 'did', 'will', 'would', 'should', 'could', 'can', 'may',
            'might', 'must', 'shall',
            # German stop words
            'der', 'die', 'das', 'den', 'dem', 'des', 'ein', 'eine', 'einer', 'eines',
            'und', 'oder', 'aber', 'mit', 'von', 'zu', 'in', 'auf', 'für', 'bei',
            'ist', 'sind', 'war', 'waren', 'hat', 'haben', 'wird', 'werden',
            # French stop words  
            'le', 'la', 'les', 'un', 'une', 'du', 'de', 'des', 'et', 'ou', 'mais',
            'avec', 'dans', 'sur', 'pour', 'par', 'est', 'sont', 'était', 'étaient'
        }
        
        self.logger.info(
            "Search index initialized",
            extra={
                "storage_available": storage.is_available(),
                "stop_words_count": len(self.stop_words)
            }
        )
    
    def is_available(self) -> bool:
        """Check if search index is available."""
        return self.storage.is_available()
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for indexing."""
        if not text:
            return ""
        
        # Convert to lowercase and normalize unicode
        text = unicodedata.normalize('NFKD', text.lower())
        
        # Remove accents/diacritics
        text = ''.join(c for c in text if not unicodedata.combining(c))
        
        return text
    
    def _extract_words(self, text: str) -> Set[str]:
        """Extract words from text for indexing."""
        if not text:
            return set()
        
        # Normalize text
        normalized = self._normalize_text(text)
        
        # Extract words (letters, numbers, some punctuation)
        words = re.findall(r'\b\w+\b', normalized)
        
        # Filter words
        filtered_words = set()
        for word in words:
            if (self.min_word_length <= len(word) <= self.max_word_length and
                word not in self.stop_words and
                not word.isdigit()):  # Skip pure numbers
                filtered_words.add(word)
        
        return filtered_words
    
    def _get_index_key(self, module: str, user_id: Optional[int] = None) -> str:
        """Generate index file key."""
        if user_id:
            return f"manifests/{module}/search_index-{user_id}.json"
        else:
            return f"manifests/{module}/search_index.json"
    
    def _load_index(self, module: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Load existing search index."""
        
        index_key = self._get_index_key(module, user_id)
        
        try:
            result = self.storage.get_json(index_key)
            index_data = result['json_data']
            
            self.logger.debug(
                "Search index loaded",
                extra={
                    "key": index_key,
                    "terms": len(index_data.get('inverted_index', {})),
                    "documents": len(index_data.get('documents', {}))
                }
            )
            
            return index_data
            
        except ObjectNotFoundError:
            # Return empty index
            return {
                "version": "1.0",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "module": module,
                "user_id": user_id,
                "inverted_index": {},  # term -> set of document_ids
                "documents": {},       # document_id -> metadata
                "merchants": {},       # normalized_merchant -> set of document_ids
                "stats": {
                    "total_documents": 0,
                    "total_terms": 0,
                    "total_merchants": 0
                }
            }
        except Exception as e:
            self.logger.error(
                "Failed to load search index",
                extra={"key": index_key, "error": str(e)}
            )
            raise SearchIndexError(f"Failed to load search index: {str(e)}")
    
    def _save_index(self, index_data: Dict[str, Any], module: str, user_id: Optional[int] = None) -> None:
        """Save search index to storage."""
        
        index_key = self._get_index_key(module, user_id)
        
        # Update metadata
        index_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        index_data["stats"] = {
            "total_documents": len(index_data.get("documents", {})),
            "total_terms": len(index_data.get("inverted_index", {})),
            "total_merchants": len(index_data.get("merchants", {}))
        }
        
        try:
            self.storage.put_json(index_key, index_data)
            
            self.logger.debug(
                "Search index saved",
                extra={
                    "key": index_key,
                    "terms": index_data["stats"]["total_terms"],
                    "documents": index_data["stats"]["total_documents"]
                }
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to save search index",
                extra={"key": index_key, "error": str(e)}
            )
            raise SearchIndexError(f"Failed to save search index: {str(e)}")
    
    def add_document(
        self,
        module: str,
        document_id: str,
        text_content: str,
        metadata: Optional[Dict[str, Any]] = None,
        merchant: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Add or update document in search index.
        
        Args:
            module: Module name (e.g., 'swiss_accountant')
            document_id: Unique document identifier
            text_content: Text content to index
            metadata: Additional document metadata
            merchant: Merchant name for special merchant index
            user_id: Optional user ID for per-user indexes
            
        Returns:
            Dict with indexing results
        """
        
        if not self.is_available():
            raise SearchIndexError("Search index not available")
        
        # Load current index
        index_data = self._load_index(module, user_id)
        
        # Extract words from text content
        words = self._extract_words(text_content)
        
        # Remove document from old index entries if it exists
        old_doc = index_data["documents"].get(document_id)
        if old_doc:
            old_words = set(old_doc.get("words", []))
            for word in old_words:
                if word in index_data["inverted_index"]:
                    index_data["inverted_index"][word].discard(document_id)
                    if not index_data["inverted_index"][word]:
                        del index_data["inverted_index"][word]
            
            # Remove from merchant index
            old_merchant = old_doc.get("merchant")
            if old_merchant:
                normalized_merchant = self._normalize_text(old_merchant)
                if normalized_merchant in index_data["merchants"]:
                    index_data["merchants"][normalized_merchant].discard(document_id)
                    if not index_data["merchants"][normalized_merchant]:
                        del index_data["merchants"][normalized_merchant]
        
        # Add document to inverted index
        for word in words:
            if word not in index_data["inverted_index"]:
                index_data["inverted_index"][word] = set()
            index_data["inverted_index"][word].add(document_id)
        
        # Add to merchant index if provided
        if merchant:
            normalized_merchant = self._normalize_text(merchant)
            if normalized_merchant not in index_data["merchants"]:
                index_data["merchants"][normalized_merchant] = set()
            index_data["merchants"][normalized_merchant].add(document_id)
        
        # Store document metadata
        index_data["documents"][document_id] = {
            "words": list(words),
            "merchant": merchant,
            "metadata": metadata or {},
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "text_length": len(text_content),
            "word_count": len(words)
        }
        
        # Convert sets to lists for JSON serialization
        serializable_index = {
            **index_data,
            "inverted_index": {
                term: list(doc_set) for term, doc_set in index_data["inverted_index"].items()
            },
            "merchants": {
                merchant: list(doc_set) for merchant, doc_set in index_data["merchants"].items()
            }
        }
        
        # Save updated index
        self._save_index(serializable_index, module, user_id)
        
        self.logger.info(
            "Document added to search index",
            extra={
                "module": module,
                "document_id": document_id,
                "user_id": user_id,
                "words_indexed": len(words),
                "merchant": merchant,
                "text_length": len(text_content)
            }
        )
        
        return {
            "success": True,
            "document_id": document_id,
            "words_indexed": len(words),
            "total_terms": len(index_data["inverted_index"]),
            "total_documents": len(index_data["documents"])
        }
    
    def search_keywords(
        self,
        module: str,
        keywords: List[str],
        user_id: Optional[int] = None,
        operator: str = 'AND',
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search documents by keywords.
        
        Args:
            module: Module name
            keywords: List of keywords to search for
            user_id: Optional user ID for per-user search
            operator: 'AND' or 'OR' for combining keywords
            limit: Maximum results to return
            
        Returns:
            List of matching documents with metadata
        """
        
        if not self.is_available():
            raise SearchIndexError("Search index not available")
        
        if not keywords:
            return []
        
        # Load index
        index_data = self._load_index(module, user_id)
        inverted_index = {
            term: set(docs) for term, docs in index_data.get("inverted_index", {}).items()
        }
        
        # Normalize keywords
        normalized_keywords = [self._normalize_text(kw) for kw in keywords if kw.strip()]
        
        if not normalized_keywords:
            return []
        
        # Find matching documents
        matching_docs = None
        
        for keyword in normalized_keywords:
            keyword_docs = set()
            
            # Find exact matches and partial matches
            for term, doc_set in inverted_index.items():
                if keyword in term or term in keyword:
                    keyword_docs.update(doc_set)
            
            if matching_docs is None:
                matching_docs = keyword_docs
            elif operator.upper() == 'AND':
                matching_docs = matching_docs.intersection(keyword_docs)
            elif operator.upper() == 'OR':
                matching_docs = matching_docs.union(keyword_docs)
        
        if not matching_docs:
            return []
        
        # Build results with metadata
        results = []
        documents = index_data.get("documents", {})
        
        for doc_id in list(matching_docs)[:limit]:
            doc_info = documents.get(doc_id, {})
            
            results.append({
                "document_id": doc_id,
                "merchant": doc_info.get("merchant"),
                "metadata": doc_info.get("metadata", {}),
                "indexed_at": doc_info.get("indexed_at"),
                "text_length": doc_info.get("text_length", 0),
                "word_count": doc_info.get("word_count", 0)
            })
        
        # Sort by indexed_at (most recent first)
        results.sort(key=lambda x: x.get("indexed_at", ""), reverse=True)
        
        self.logger.debug(
            "Keyword search completed",
            extra={
                "module": module,
                "keywords": keywords,
                "operator": operator,
                "results": len(results),
                "user_id": user_id
            }
        )
        
        return results
    
    def search_merchants(
        self,
        module: str,
        merchant_query: str,
        user_id: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search documents by merchant name.
        
        Args:
            module: Module name
            merchant_query: Merchant name or partial name to search for
            user_id: Optional user ID for per-user search
            limit: Maximum results to return
            
        Returns:
            List of matching documents
        """
        
        if not self.is_available():
            raise SearchIndexError("Search index not available")
        
        if not merchant_query.strip():
            return []
        
        # Load index
        index_data = self._load_index(module, user_id)
        merchants_index = {
            merchant: set(docs) for merchant, docs in index_data.get("merchants", {}).items()
        }
        
        # Normalize merchant query
        normalized_query = self._normalize_text(merchant_query)
        
        # Find matching merchants
        matching_docs = set()
        matched_merchants = []
        
        for merchant, doc_set in merchants_index.items():
            if normalized_query in merchant or merchant in normalized_query:
                matching_docs.update(doc_set)
                matched_merchants.append(merchant)
        
        if not matching_docs:
            return []
        
        # Build results
        results = []
        documents = index_data.get("documents", {})
        
        for doc_id in list(matching_docs)[:limit]:
            doc_info = documents.get(doc_id, {})
            
            results.append({
                "document_id": doc_id,
                "merchant": doc_info.get("merchant"),
                "metadata": doc_info.get("metadata", {}),
                "indexed_at": doc_info.get("indexed_at"),
                "text_length": doc_info.get("text_length", 0),
                "word_count": doc_info.get("word_count", 0)
            })
        
        # Sort by indexed_at (most recent first)
        results.sort(key=lambda x: x.get("indexed_at", ""), reverse=True)
        
        self.logger.debug(
            "Merchant search completed",
            extra={
                "module": module,
                "merchant_query": merchant_query,
                "matched_merchants": matched_merchants,
                "results": len(results),
                "user_id": user_id
            }
        )
        
        return results
    
    def get_index_stats(self, module: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get search index statistics.
        
        Args:
            module: Module name
            user_id: Optional user ID
            
        Returns:
            Dict with index statistics
        """
        
        if not self.is_available():
            return {"available": False, "error": "Search index not available"}
        
        try:
            index_data = self._load_index(module, user_id)
            
            return {
                "available": True,
                "module": module,
                "user_id": user_id,
                "version": index_data.get("version", "unknown"),
                "created_at": index_data.get("created_at"),
                "updated_at": index_data.get("updated_at"),
                "stats": index_data.get("stats", {}),
                "sample_terms": list(index_data.get("inverted_index", {}).keys())[:10],
                "sample_merchants": list(index_data.get("merchants", {}).keys())[:10]
            }
            
        except Exception as e:
            return {
                "available": True,
                "error": f"Failed to get stats: {str(e)}"
            }
    
    def remove_document(
        self,
        module: str,
        document_id: str,
        user_id: Optional[int] = None
    ) -> bool:
        """
        Remove document from search index.
        
        Args:
            module: Module name
            document_id: Document identifier to remove
            user_id: Optional user ID
            
        Returns:
            True if document was removed
        """
        
        if not self.is_available():
            raise SearchIndexError("Search index not available")
        
        # Load index
        index_data = self._load_index(module, user_id)
        
        # Check if document exists
        if document_id not in index_data["documents"]:
            return False
        
        doc_info = index_data["documents"][document_id]
        
        # Remove from inverted index
        for word in doc_info.get("words", []):
            if word in index_data["inverted_index"]:
                index_data["inverted_index"][word].discard(document_id)
                if not index_data["inverted_index"][word]:
                    del index_data["inverted_index"][word]
        
        # Remove from merchant index
        merchant = doc_info.get("merchant")
        if merchant:
            normalized_merchant = self._normalize_text(merchant)
            if normalized_merchant in index_data["merchants"]:
                index_data["merchants"][normalized_merchant].discard(document_id)
                if not index_data["merchants"][normalized_merchant]:
                    del index_data["merchants"][normalized_merchant]
        
        # Remove document
        del index_data["documents"][document_id]
        
        # Convert sets to lists for JSON serialization
        serializable_index = {
            **index_data,
            "inverted_index": {
                term: list(doc_set) for term, doc_set in index_data["inverted_index"].items()
            },
            "merchants": {
                merchant: list(doc_set) for merchant, doc_set in index_data["merchants"].items()
            }
        }
        
        # Save updated index
        self._save_index(serializable_index, module, user_id)
        
        self.logger.info(
            "Document removed from search index",
            extra={
                "module": module,
                "document_id": document_id,
                "user_id": user_id
            }
        )
        
        return True
    
    def rebuild_index(
        self,
        module: str,
        documents: List[Dict[str, Any]],
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Rebuild search index from scratch.
        
        Args:
            module: Module name
            documents: List of documents to index
            user_id: Optional user ID
            
        Returns:
            Dict with rebuild results
        """
        
        if not self.is_available():
            raise SearchIndexError("Search index not available")
        
        # Create new empty index
        index_data = {
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "module": module,
            "user_id": user_id,
            "inverted_index": {},
            "documents": {},
            "merchants": {},
            "stats": {}
        }
        
        # Index all documents
        indexed_count = 0
        error_count = 0
        
        for doc in documents:
            try:
                document_id = doc.get("document_id")
                text_content = doc.get("text_content", "")
                metadata = doc.get("metadata", {})
                merchant = doc.get("merchant")
                
                if not document_id:
                    error_count += 1
                    continue
                
                # Extract words
                words = self._extract_words(text_content)
                
                # Add to inverted index
                for word in words:
                    if word not in index_data["inverted_index"]:
                        index_data["inverted_index"][word] = set()
                    index_data["inverted_index"][word].add(document_id)
                
                # Add to merchant index
                if merchant:
                    normalized_merchant = self._normalize_text(merchant)
                    if normalized_merchant not in index_data["merchants"]:
                        index_data["merchants"][normalized_merchant] = set()
                    index_data["merchants"][normalized_merchant].add(document_id)
                
                # Store document metadata
                index_data["documents"][document_id] = {
                    "words": list(words),
                    "merchant": merchant,
                    "metadata": metadata,
                    "indexed_at": datetime.now(timezone.utc).isoformat(),
                    "text_length": len(text_content),
                    "word_count": len(words)
                }
                
                indexed_count += 1
                
            except Exception as e:
                self.logger.warning(
                    "Failed to index document during rebuild",
                    extra={
                        "document_id": doc.get("document_id"),
                        "error": str(e)
                    }
                )
                error_count += 1
        
        # Convert sets to lists for JSON serialization
        serializable_index = {
            **index_data,
            "inverted_index": {
                term: list(doc_set) for term, doc_set in index_data["inverted_index"].items()
            },
            "merchants": {
                merchant: list(doc_set) for merchant, doc_set in index_data["merchants"].items()
            }
        }
        
        # Save rebuilt index
        self._save_index(serializable_index, module, user_id)
        
        self.logger.info(
            "Search index rebuilt",
            extra={
                "module": module,
                "user_id": user_id,
                "indexed_documents": indexed_count,
                "errors": error_count,
                "total_terms": len(index_data["inverted_index"]),
                "total_merchants": len(index_data["merchants"])
            }
        )
        
        return {
            "success": True,
            "indexed_documents": indexed_count,
            "errors": error_count,
            "total_terms": len(index_data["inverted_index"]),
            "total_merchants": len(index_data["merchants"])
        }

# Export
__all__ = [
    "SearchIndex",
    "SearchIndexError"
]
