#!/usr/bin/env python3
"""
F4R2 Demo Script - Showcase R2 Object Storage Capabilities
Demonstrates the complete F4R2 storage stack with real examples.
"""

import os
import sys
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from umbra.storage import (
        ObjectStorage, ManifestManager, SearchIndex,
        ObjectStorageError, ManifestError, SearchIndexError,
        PARQUET_AVAILABLE
    )
    from umbra.core.config import config
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Make sure you're running from the project root and dependencies are installed.")
    sys.exit(1)


class F4R2Demo:
    """F4R2 demonstration class."""
    
    def __init__(self):
        """Initialize F4R2 components."""
        print("🚀 Initializing F4R2 Demo...")
        
        self.storage = ObjectStorage()
        self.manifests = ManifestManager(self.storage)
        self.search = SearchIndex(self.storage)
        
        # Demo data
        self.demo_user_id = 12345
        self.demo_module = "f4r2_demo"
        
    def check_availability(self):
        """Check if F4R2 is properly configured."""
        print("\n🔍 F4R2 Health Check")
        print("=" * 50)
        
        # R2 Client
        r2_available = self.storage.r2_client.is_available()
        print(f"R2 Client:       {'✅ Available' if r2_available else '❌ Unavailable'}")
        
        if not r2_available:
            print("❌ R2 not configured properly!")
            print("Please set these environment variables:")
            print("  - R2_ACCOUNT_ID")
            print("  - R2_ACCESS_KEY_ID") 
            print("  - R2_SECRET_ACCESS_KEY")
            print("  - R2_BUCKET")
            print("  - R2_ENDPOINT (optional, auto-generated)")
            return False
        
        # Components
        print(f"Object Storage:  {'✅ Available' if self.storage.is_available() else '❌ Unavailable'}")
        print(f"Manifest Mgr:    {'✅ Available' if self.manifests.is_available() else '❌ Unavailable'}")
        print(f"Search Index:    {'✅ Available' if self.search.is_available() else '❌ Unavailable'}")
        print(f"Parquet Support: {'✅ Available' if PARQUET_AVAILABLE else '⚠️  CSV Fallback'}")
        
        # Client info
        client_info = self.storage.r2_client.get_client_info()
        print(f"\nR2 Configuration:")
        print(f"  Bucket: {client_info['bucket']}")
        print(f"  Endpoint: {client_info['endpoint']}")
        print(f"  Account: {client_info['account_id']}")
        
        return True
    
    def demo_object_storage(self):
        """Demonstrate basic object storage operations."""
        print("\n📄 Object Storage Demo")
        print("=" * 50)
        
        try:
            # 1. Store text file
            print("1. Storing text document...")
            text_content = f"""
F4R2 Demo Document
==================

This is a demonstration of F4R2 object storage capabilities.

Created: {datetime.now(timezone.utc).isoformat()}
Features:
- Content-addressed storage with SHA256
- Automatic content type detection
- Metadata support
- Presigned URL generation

F4R2 provides enterprise-grade object storage using Cloudflare R2.
            """.strip()
            
            result = self.storage.put_object(
                key="demo/readme.txt",
                data=text_content,
                metadata={
                    "demo": "true",
                    "created_by": "f4r2_demo",
                    "version": "1.0"
                }
            )
            
            print(f"   ✅ Stored with ETag: {result['etag'][:8]}...")
            print(f"   📊 Size: {result['size']} bytes")
            print(f"   🔐 SHA256: {result['sha256'][:16]}...")
            
            # 2. Store JSON configuration
            print("\n2. Storing JSON configuration...")
            config_data = {
                "demo_settings": {
                    "theme": "dark",
                    "language": "en",
                    "features": ["storage", "manifests", "search"],
                    "limits": {
                        "max_file_size": "100MB",
                        "retention_days": 365
                    }
                },
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            json_result = self.storage.put_json("demo/config.json", config_data)
            print(f"   ✅ JSON stored with ETag: {json_result['etag'][:8]}...")
            
            # 3. Generate presigned URL
            print("\n3. Generating presigned download URL...")
            download_url = self.storage.generate_presigned_url(
                key="demo/readme.txt",
                expiration=1800,  # 30 minutes
                method="download"
            )
            print(f"   🔗 URL: {download_url[:80]}...")
            print("   ⏰ Expires in 30 minutes")
            
            # 4. Store document with SHA256 naming
            print("\n4. Storing document with content-addressed naming...")
            sample_doc = b"This is a sample document for SHA256-based storage."
            
            doc_result = self.storage.store_document(
                data=sample_doc,
                filename="sample.txt",
                content_type="text/plain"
            )
            
            print(f"   📄 Document key: {doc_result['key']}")
            print(f"   🔐 SHA256: {doc_result['sha256']}")
            print(f"   ♻️  Already existed: {doc_result['already_exists']}")
            
            # 5. List objects
            print("\n5. Listing demo objects...")
            objects = self.storage.list_objects(prefix="demo/", max_keys=10)
            
            print(f"   📁 Found {len(objects['objects'])} objects:")
            for obj in objects["objects"]:
                print(f"      - {obj['key']} ({obj['size']} bytes)")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    def demo_jsonl_manifests(self):
        """Demonstrate JSONL manifest operations."""
        print("\n📝 JSONL Manifests Demo")
        print("=" * 50)
        
        try:
            # 1. Add expense entries
            print("1. Adding expense entries to JSONL manifest...")
            
            expenses = [
                {
                    "date": "2025-01-15",
                    "amount": 25.50,
                    "merchant": "Downtown Coffee",
                    "category": "Food & Drink",
                    "description": "Morning coffee and croissant",
                    "payment_method": "Credit Card"
                },
                {
                    "date": "2025-01-15", 
                    "amount": 1200.00,
                    "merchant": "Tech Conference Ltd",
                    "category": "Education",
                    "description": "AI/ML Conference registration",
                    "payment_method": "Company Card"
                },
                {
                    "date": "2025-01-16",
                    "amount": 45.75,
                    "merchant": "City Taxi",
                    "category": "Travel",
                    "description": "Airport transfer",
                    "payment_method": "Cash"
                }
            ]
            
            for i, expense in enumerate(expenses, 1):
                result = self.manifests.append_jsonl(
                    module=self.demo_module,
                    name="expenses",
                    entry=expense,
                    user_id=self.demo_user_id
                )
                print(f"   ✅ Entry {i}: {expense['merchant']} - ${expense['amount']}")
                print(f"      ID: {result['entry_id']}, Attempt: {result['attempt']}")
            
            # 2. Read back entries
            print("\n2. Reading expense entries...")
            entries = list(self.manifests.read_jsonl(
                module=self.demo_module,
                name="expenses",
                user_id=self.demo_user_id,
                limit=10
            ))
            
            print(f"   📊 Found {len(entries)} expense entries:")
            total_amount = 0
            for entry in entries:
                amount = entry.data['amount']
                merchant = entry.data['merchant']
                total_amount += amount
                print(f"      - {merchant}: ${amount:.2f}")
            
            print(f"   💰 Total expenses: ${total_amount:.2f}")
            
            # 3. Read recent entries (last 24 hours)
            print("\n3. Reading recent entries (last 24 hours)...")
            yesterday = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            
            recent_entries = list(self.manifests.read_jsonl(
                module=self.demo_module,
                name="expenses",
                user_id=self.demo_user_id,
                since_timestamp=yesterday
            ))
            
            print(f"   📅 Found {len(recent_entries)} recent entries")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    def demo_parquet_manifests(self):
        """Demonstrate Parquet manifest operations."""
        print("\n📊 Parquet Manifests Demo")
        print("=" * 50)
        
        try:
            # Generate sample transaction data
            print("1. Creating monthly transaction data...")
            
            transactions = []
            categories = ["Food", "Travel", "Equipment", "Education", "Entertainment"]
            merchants = ["Coffee Shop", "Gas Station", "Tech Store", "Online Course", "Cinema"]
            
            # Generate 50 sample transactions
            for i in range(50):
                day = (i % 28) + 1
                transaction = {
                    "transaction_id": f"TXN_{i:04d}",
                    "date": f"2025-01-{day:02d}",
                    "amount": round(20.0 + (i * 15.5) % 500, 2),
                    "merchant": merchants[i % len(merchants)],
                    "category": categories[i % len(categories)],
                    "payment_method": "Credit Card" if i % 3 == 0 else "Debit Card",
                    "currency": "USD",
                    "description": f"Sample transaction #{i+1}"
                }
                transactions.append(transaction)
            
            print(f"   📊 Generated {len(transactions)} transactions")
            
            # 2. Store as Parquet
            print("2. Storing transactions as Parquet...")
            
            schema = {
                "transaction_id": "string",
                "date": "string", 
                "amount": "float64",
                "merchant": "string",
                "category": "string",
                "payment_method": "string",
                "currency": "string",
                "description": "string"
            }
            
            result = self.manifests.write_parquet(
                module=self.demo_module,
                name="transactions",
                data=transactions,
                partition="2025-01",
                user_id=self.demo_user_id,
                schema=schema
            )
            
            print(f"   ✅ Stored {result['records']} records in {result['format']} format")
            print(f"   📅 Partition: {result['partition']}")
            print(f"   📄 Key: {result['key']}")
            
            # 3. Read Parquet data back
            print("\n3. Reading Parquet data...")
            
            read_data = self.manifests.read_parquet(
                module=self.demo_module,
                name="transactions",
                partition="2025-01",
                user_id=self.demo_user_id,
                columns=["date", "amount", "merchant", "category"]  # Select specific columns
            )
            
            if read_data:
                print(f"   📊 Read {len(read_data)} transactions")
                
                # Calculate some analytics
                total_amount = sum(t['amount'] for t in read_data)
                avg_amount = total_amount / len(read_data)
                
                category_totals = {}
                for t in read_data:
                    cat = t['category']
                    category_totals[cat] = category_totals.get(cat, 0) + t['amount']
                
                print(f"   💰 Total: ${total_amount:.2f}")
                print(f"   📊 Average: ${avg_amount:.2f}")
                print("   📈 By category:")
                for cat, amount in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
                    print(f"      - {cat}: ${amount:.2f}")
            
            # 4. List partitions
            print("\n4. Listing available partitions...")
            partitions = self.manifests.list_partitions(
                module=self.demo_module,
                name="transactions",
                user_id=self.demo_user_id
            )
            
            print(f"   📁 Found {len(partitions)} partitions:")
            for partition in partitions:
                print(f"      - {partition['partition']}: {partition['size']} bytes ({partition['format']})")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    def demo_search_index(self):
        """Demonstrate search index operations."""
        print("\n🔍 Search Index Demo")
        print("=" * 50)
        
        try:
            # 1. Index documents
            print("1. Indexing sample documents...")
            
            documents = [
                {
                    "id": "doc_001",
                    "content": "Machine learning conference receipt for AI summit in San Francisco",
                    "merchant": "Tech Conference Ltd",
                    "metadata": {"amount": 1200.0, "category": "Education"}
                },
                {
                    "id": "doc_002", 
                    "content": "Restaurant receipt for business dinner with potential clients",
                    "merchant": "Fine Dining Restaurant",
                    "metadata": {"amount": 185.50, "category": "Business Meals"}
                },
                {
                    "id": "doc_003",
                    "content": "Coffee shop receipt for morning meeting with development team",
                    "merchant": "Downtown Coffee",
                    "metadata": {"amount": 28.75, "category": "Food & Drink"}
                },
                {
                    "id": "doc_004",
                    "content": "Equipment purchase receipt for new laptop and accessories",
                    "merchant": "Tech Store",
                    "metadata": {"amount": 2450.00, "category": "Equipment"}
                },
                {
                    "id": "doc_005",
                    "content": "Travel expense receipt for flight booking and hotel accommodation",
                    "merchant": "Travel Agency",
                    "metadata": {"amount": 875.25, "category": "Travel"}
                }
            ]
            
            for doc in documents:
                result = self.search.add_document(
                    module=self.demo_module,
                    document_id=doc["id"],
                    text_content=doc["content"],
                    metadata=doc["metadata"],
                    merchant=doc["merchant"],
                    user_id=self.demo_user_id
                )
                print(f"   ✅ {doc['id']}: {result['words_indexed']} words indexed")
            
            # 2. Keyword searches
            print("\n2. Testing keyword searches...")
            
            search_tests = [
                (["machine", "learning"], "AND"),
                (["coffee", "restaurant"], "OR"),
                (["business"], "AND"),
                (["receipt"], "AND"),
                (["travel", "flight"], "AND")
            ]
            
            for keywords, operator in search_tests:
                results = self.search.search_keywords(
                    module=self.demo_module,
                    keywords=keywords,
                    user_id=self.demo_user_id,
                    operator=operator
                )
                
                print(f"   🔍 '{' '.join(keywords)}' ({operator}): {len(results)} results")
                for result in results[:2]:  # Show top 2 results
                    print(f"      - {result['document_id']}: {result['merchant']}")
            
            # 3. Merchant searches
            print("\n3. Testing merchant searches...")
            
            merchant_queries = ["coffee", "tech", "restaurant", "travel"]
            
            for query in merchant_queries:
                results = self.search.search_merchants(
                    module=self.demo_module,
                    merchant_query=query,
                    user_id=self.demo_user_id
                )
                
                print(f"   🏪 '{query}': {len(results)} results")
                for result in results:
                    amount = result['metadata'].get('amount', 0)
                    print(f"      - {result['merchant']}: ${amount:.2f}")
            
            # 4. Index statistics
            print("\n4. Search index statistics...")
            stats = self.search.get_index_stats(self.demo_module, self.demo_user_id)
            
            if stats["available"]:
                index_stats = stats["stats"]
                print(f"   📊 Documents: {index_stats['total_documents']}")
                print(f"   📝 Unique terms: {index_stats['total_terms']}")
                print(f"   🏪 Merchants: {index_stats['total_merchants']}")
                print(f"   🔤 Sample terms: {', '.join(stats['sample_terms'][:5])}...")
                print(f"   🏢 Sample merchants: {', '.join(stats['sample_merchants'][:3])}...")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    def demo_statistics(self):
        """Show comprehensive F4R2 statistics."""
        print("\n📊 F4R2 Statistics")
        print("=" * 50)
        
        try:
            # 1. Storage statistics
            print("1. Storage Statistics:")
            storage_stats = self.storage.get_storage_stats()
            
            if storage_stats["available"]:
                print(f"   🪣 Bucket: {storage_stats['bucket']}")
                print(f"   📄 Total objects: {storage_stats['objects']['total']}")
                print(f"   📊 Manifests: {storage_stats['objects']['manifests']}")
                print(f"   📋 Documents: {storage_stats['objects']['documents']}")
                print(f"   📦 Exports: {storage_stats['objects']['exports']}")
                print(f"   💾 Total size: {storage_stats['sizes']['total_bytes']:,} bytes")
            else:
                print(f"   ❌ Unavailable: {storage_stats.get('error', 'Unknown')}")
            
            # 2. Manifest statistics  
            print("\n2. Manifest Statistics:")
            manifest_stats = self.manifests.get_manifest_stats()
            
            if manifest_stats["available"]:
                print(f"   📝 Total manifests: {manifest_stats['total_manifests']}")
                print(f"   📊 By format: {manifest_stats['by_format']}")
                print(f"   📁 By module: {manifest_stats['by_module']}")
                print(f"   📄 Total size: {manifest_stats['total_size']:,} bytes")
                print(f"   🐼 Parquet available: {manifest_stats['parquet_available']}")
            else:
                print(f"   ❌ Unavailable: {manifest_stats.get('error', 'Unknown')}")
            
            # 3. Search statistics
            print("\n3. Search Index Statistics:")
            search_stats = self.search.get_index_stats(self.demo_module, self.demo_user_id)
            
            if search_stats["available"]:
                stats = search_stats["stats"]
                print(f"   🔍 Module: {search_stats['module']}")
                print(f"   👤 User ID: {search_stats['user_id']}")
                print(f"   📄 Indexed documents: {stats['total_documents']}")
                print(f"   🔤 Unique terms: {stats['total_terms']}")
                print(f"   🏪 Merchants: {stats['total_merchants']}")
                print(f"   📅 Created: {search_stats['created_at']}")
                print(f"   🔄 Updated: {search_stats['updated_at']}")
            else:
                print(f"   ❌ Unavailable: {search_stats.get('error', 'Unknown')}")
        
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    def run_demo(self):
        """Run the complete F4R2 demonstration."""
        print("🎉 F4R2 - Cloudflare R2 Object Storage Demo")
        print("=" * 60)
        print("This demo showcases F4R2's enterprise storage capabilities:")
        print("• Object Storage with SHA256 verification")
        print("• JSONL Manifests for real-time data streams") 
        print("• Parquet Analytics with partitioning")
        print("• Built-in Search Index for text retrieval")
        print("• Comprehensive monitoring and statistics")
        
        # Check if F4R2 is available
        if not self.check_availability():
            print("\n❌ F4R2 not available. Please configure R2 credentials.")
            return False
        
        # Run demonstrations
        try:
            self.demo_object_storage()
            self.demo_jsonl_manifests()
            self.demo_parquet_manifests()
            self.demo_search_index()
            self.demo_statistics()
            
            print("\n🎉 F4R2 Demo Completed Successfully!")
            print("=" * 60)
            print("F4R2 provides enterprise-grade object storage for Umbra.")
            print("Ready for production workloads with:")
            print("• ✅ Scalable R2 object storage")
            print("• ✅ Real-time JSONL manifests") 
            print("• ✅ Analytics-ready Parquet files")
            print("• ✅ Full-text search capabilities")
            print("• ✅ Comprehensive monitoring")
            
            return True
            
        except KeyboardInterrupt:
            print("\n\n⏹️  Demo interrupted by user")
            return False
        except Exception as e:
            print(f"\n❌ Demo failed: {e}")
            return False


def main():
    """Main demo function."""
    demo = F4R2Demo()
    success = demo.run_demo()
    
    if success:
        print("\n💡 Next Steps:")
        print("1. Explore the F4R2_README.md for detailed documentation")
        print("2. Run the test suite: pytest tests/test_*r2* tests/test_*storage* -v")
        print("3. Integrate F4R2 into your Umbra modules")
        print("4. Monitor R2 usage in the Cloudflare dashboard")
    else:
        print("\n🔧 Troubleshooting:")
        print("1. Ensure R2 credentials are set in environment variables")
        print("2. Verify R2 bucket exists and is accessible")
        print("3. Check network connectivity to Cloudflare R2")
        print("4. Review F4R2_README.md for setup instructions")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
