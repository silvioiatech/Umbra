"""
Example integration showing how to use R2 storage in existing modules.
This demonstrates migration from SQLite to R2 storage for the finance module.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..storage import get_storage_manager, StorageRecord
from ..core.logger import get_logger

logger = get_logger("umbra.integration.r2_example")


class FinanceR2Integration:
    """Example showing how to integrate R2 storage into the finance module."""
    
    def __init__(self, config):
        """Initialize finance R2 integration."""
        self.config = config
        self.logger = logger
        self._storage_manager = None
    
    async def get_storage(self):
        """Get storage manager instance."""
        if self._storage_manager is None:
            self._storage_manager = await get_storage_manager()
        return self._storage_manager
    
    async def store_transaction(self, user_id: str, transaction_data: Dict[str, Any]) -> str:
        """Store a financial transaction using R2 storage."""
        storage = await self.get_storage()
        
        # Add timestamp and ID if not present
        if 'timestamp' not in transaction_data:
            transaction_data['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        if 'id' not in transaction_data:
            transaction_data['id'] = f"txn_{int(datetime.now(timezone.utc).timestamp())}"
        
        # Store transaction data
        try:
            record = await storage.store_data(
                module="finance",
                user_id=user_id,
                data=transaction_data,
                data_format="json"  # Single transaction as JSON
            )
            
            self.logger.info(f"Stored transaction {transaction_data['id']} for user {user_id}")
            return record.id
            
        except Exception as e:
            self.logger.error(f"Failed to store transaction: {e}")
            raise
    
    async def store_bulk_transactions(self, user_id: str, transactions: List[Dict[str, Any]]) -> str:
        """Store multiple transactions using JSONL format."""
        storage = await self.get_storage()
        
        # Prepare transactions with IDs and timestamps
        for i, txn in enumerate(transactions):
            if 'timestamp' not in txn:
                txn['timestamp'] = datetime.now(timezone.utc).isoformat()
            if 'id' not in txn:
                txn['id'] = f"txn_bulk_{int(datetime.now(timezone.utc).timestamp())}_{i}"
        
        try:
            record = await storage.store_data(
                module="finance",
                user_id=user_id,
                data={"records": transactions},
                data_format="jsonl"  # Multiple transactions as JSONL
            )
            
            self.logger.info(f"Stored {len(transactions)} transactions for user {user_id}")
            return record.id
            
        except Exception as e:
            self.logger.error(f"Failed to store bulk transactions: {e}")
            raise
    
    async def store_analytics_data(self, user_id: str, analytics: Dict[str, Any]) -> str:
        """Store financial analytics using Parquet format for structured data."""
        storage = await self.get_storage()
        
        # Convert analytics to list of records for Parquet storage
        analytics_records = []
        
        # Example: Convert monthly summaries to records
        if 'monthly_summaries' in analytics:
            for month, summary in analytics['monthly_summaries'].items():
                analytics_records.append({
                    'month': month,
                    'total_income': summary.get('income', 0),
                    'total_expenses': summary.get('expenses', 0),
                    'net_income': summary.get('net', 0),
                    'transaction_count': summary.get('count', 0),
                    'user_id': user_id,
                    'generated_at': datetime.now(timezone.utc).isoformat()
                })
        
        if analytics_records:
            try:
                record = await storage.store_data(
                    module="finance",
                    user_id=user_id,
                    data={"records": analytics_records},
                    data_format="parquet"  # Structured analytics as Parquet
                )
                
                self.logger.info(f"Stored analytics data for user {user_id}")
                return record.id
                
            except Exception as e:
                self.logger.error(f"Failed to store analytics data: {e}")
                raise
        else:
            # Store as JSON blob if no structured data
            record = await storage.store_data(
                module="finance",
                user_id=user_id,
                data=analytics,
                data_format="json"
            )
            return record.id
    
    async def retrieve_transactions(self, user_id: str, transaction_id: str = None) -> Optional[List[Dict[str, Any]]]:
        """Retrieve transactions from R2 storage."""
        storage = await self.get_storage()
        
        try:
            if transaction_id:
                # Retrieve specific transaction
                record = await storage.retrieve_data("finance", user_id, transaction_id)
                if record and isinstance(record, StorageRecord):
                    if isinstance(record.data, dict) and 'records' in record.data:
                        return record.data['records']
                    else:
                        return [record.data]
                return None
            else:
                # Retrieve all transactions for user
                records = await storage.retrieve_data("finance", user_id)
                if isinstance(records, list):
                    all_transactions = []
                    for record in records:
                        if isinstance(record.data, dict) and 'records' in record.data:
                            all_transactions.extend(record.data['records'])
                        else:
                            all_transactions.append(record.data)
                    return all_transactions
                return []
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve transactions: {e}")
            return []
    
    async def search_transactions(self, user_id: str, query: str) -> List[Dict[str, Any]]:
        """Search transactions using the R2 text search functionality."""
        storage = await self.get_storage()
        
        try:
            search_results = await storage.search_data("finance", user_id, query)
            
            transactions = []
            for record in search_results:
                if isinstance(record.data, dict) and 'records' in record.data:
                    # Filter records that match the query
                    for item in record.data['records']:
                        item_str = json.dumps(item, default=str).lower()
                        if query.lower() in item_str:
                            transactions.append(item)
                elif query.lower() in json.dumps(record.data, default=str).lower():
                    transactions.append(record.data)
            
            self.logger.info(f"Found {len(transactions)} transactions matching '{query}'")
            return transactions
            
        except Exception as e:
            self.logger.error(f"Failed to search transactions: {e}")
            return []
    
    async def generate_download_link(self, user_id: str, record_id: str) -> Optional[str]:
        """Generate presigned URL for downloading financial data."""
        storage = await self.get_storage()
        
        try:
            # Find the storage record
            record = await storage.retrieve_data("finance", user_id, record_id)
            if record and isinstance(record, StorageRecord) and record.storage_key:
                # Generate presigned URL
                url = await storage.generate_presigned_url(
                    record.storage_key, 
                    expiration=3600  # 1 hour
                )
                
                self.logger.info(f"Generated download link for record {record_id}")
                return url
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to generate download link: {e}")
            return None
    
    async def get_storage_info(self) -> Dict[str, Any]:
        """Get information about the storage backend being used."""
        storage = await self.get_storage()
        
        try:
            info = await storage.get_storage_info()
            return {
                'backend': info.get('backend', 'unknown'),
                'r2_enabled': info.get('r2_available', False),
                'hybrid_mode': info.get('hybrid_mode', False),
                'bucket': getattr(self.config, 'R2_BUCKET', None)
            }
        except Exception as e:
            self.logger.error(f"Failed to get storage info: {e}")
            return {'backend': 'error', 'error': str(e)}


# Example usage functions

async def demo_r2_integration():
    """Demonstrate R2 integration with sample data."""
    from ..core.config import config
    
    integration = FinanceR2Integration(config)
    user_id = "demo_user"
    
    print("=== R2 Storage Integration Demo ===")
    
    # 1. Store single transaction
    print("\n1. Storing single transaction...")
    transaction = {
        "amount": 50.00,
        "description": "Coffee shop",
        "category": "dining",
        "account": "checking"
    }
    
    try:
        txn_id = await integration.store_transaction(user_id, transaction)
        print(f"✓ Stored transaction: {txn_id}")
    except Exception as e:
        print(f"✗ Failed to store transaction: {e}")
    
    # 2. Store bulk transactions as JSONL
    print("\n2. Storing bulk transactions...")
    bulk_transactions = [
        {"amount": 25.50, "description": "Grocery store", "category": "food"},
        {"amount": 100.00, "description": "Gas station", "category": "transportation"},
        {"amount": 1500.00, "description": "Salary", "category": "income", "type": "income"}
    ]
    
    try:
        bulk_id = await integration.store_bulk_transactions(user_id, bulk_transactions)
        print(f"✓ Stored bulk transactions: {bulk_id}")
    except Exception as e:
        print(f"✗ Failed to store bulk transactions: {e}")
    
    # 3. Store analytics as Parquet
    print("\n3. Storing analytics data...")
    analytics = {
        "monthly_summaries": {
            "2024-01": {"income": 3000, "expenses": 2500, "net": 500, "count": 45},
            "2024-02": {"income": 3200, "expenses": 2800, "net": 400, "count": 52}
        }
    }
    
    try:
        analytics_id = await integration.store_analytics_data(user_id, analytics)
        print(f"✓ Stored analytics: {analytics_id}")
    except Exception as e:
        print(f"✗ Failed to store analytics: {e}")
    
    # 4. Retrieve transactions
    print("\n4. Retrieving transactions...")
    try:
        transactions = await integration.retrieve_transactions(user_id)
        print(f"✓ Retrieved {len(transactions) if transactions else 0} transactions")
    except Exception as e:
        print(f"✗ Failed to retrieve transactions: {e}")
    
    # 5. Search transactions
    print("\n5. Searching transactions...")
    try:
        results = await integration.search_transactions(user_id, "coffee")
        print(f"✓ Found {len(results)} matching transactions")
    except Exception as e:
        print(f"✗ Failed to search transactions: {e}")
    
    # 6. Get storage info
    print("\n6. Storage information...")
    try:
        info = await integration.get_storage_info()
        print(f"✓ Backend: {info['backend']}, R2 enabled: {info['r2_enabled']}")
    except Exception as e:
        print(f"✗ Failed to get storage info: {e}")
    
    print("\n=== Demo completed ===")


if __name__ == "__main__":
    # Run demo if executed directly
    asyncio.run(demo_r2_integration())