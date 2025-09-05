# R2 Storage Integration for UMBRA

This document describes the Cloudflare R2 storage integration that replaces SQLite for JSONL/Parquet manifests, presigned URLs, and optimistic concurrency control.

## Overview

The R2 storage system provides:
- **JSONL/Parquet manifests** for structured data storage
- **Presigned URLs** for secure downloads
- **ETag-based optimistic concurrency** control
- **Module/user data partitioning** with date-based organization
- **Simple text search** via manifest indexing
- **Graceful fallback** to SQLite when R2 is unavailable

## Configuration

Add these environment variables to enable R2 storage:

```bash
# Required R2 configuration
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY_ID=your_r2_access_key_id
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
R2_BUCKET=your_r2_bucket_name

# Optional configuration
R2_ENDPOINT=https://your_account.r2.cloudflarestorage.com
STORAGE_BACKEND=r2  # 'r2', 'sqlite', or 'hybrid'
FEATURE_R2_STORAGE=true
```

## Storage Structure

Data is organized in R2 with the following structure:

```
bucket/
├── finance/
│   └── user123/
│       └── 2024/01/15/
│           ├── abc123.jsonl          # Transaction records
│           ├── def456.parquet        # Analytics data
│           └── ghi789.json           # Configuration
├── json_blobs/
│   ├── user_config_user123.json     # Key-value data
│   └── settings_global.json
└── manifests/
    └── finance/
        └── user123/
            └── manifest.jsonl       # Index of all files
```

## Usage Examples

### Basic Storage Operations

```python
from umbra.storage import get_storage_manager

# Get storage manager (automatically selects R2 or SQLite)
storage = await get_storage_manager()

# Store single transaction as JSON
record = await storage.store_data(
    module="finance",
    user_id="user123", 
    data={"amount": 50.00, "description": "Coffee"},
    data_format="json"
)

# Store multiple transactions as JSONL
record = await storage.store_data(
    module="finance", 
    user_id="user123",
    data={"records": [transaction1, transaction2, ...]},
    data_format="jsonl"
)

# Store analytics as Parquet
record = await storage.store_data(
    module="analytics",
    user_id="user123", 
    data={"records": [analytics_row1, analytics_row2, ...]},
    data_format="parquet"
)
```

### Retrieval and Search

```python
# Retrieve specific record
record = await storage.retrieve_data("finance", "user123", "record_id")

# Retrieve all records for module/user
records = await storage.retrieve_data("finance", "user123")

# Search records
results = await storage.search_data("finance", "user123", "coffee")

# Generate presigned download URL
url = await storage.generate_presigned_url(record.storage_key, expiration=3600)
```

### Direct R2 Manager Usage

```python
from umbra.storage.r2_manager import R2StorageManager
from umbra.core.config import config

manager = R2StorageManager(config)

# Upload JSONL data
entry = await manager.upload_jsonl_data(
    module="finance",
    user_id="user123",
    data=[{"id": 1, "amount": 25.50}, {"id": 2, "amount": 100.00}]
)

# Upload Parquet data 
entry = await manager.upload_parquet_data(
    module="analytics", 
    user_id="user123",
    data=[{"month": "2024-01", "income": 3000, "expenses": 2500}]
)

# Upload JSON blob
obj = await manager.upload_json_blob(
    key="user_settings",
    data={"theme": "dark", "currency": "USD"}
)
```

## ETag Concurrency Control

```python
# Check for conflicts before updating
conflict = await manager.check_etag_conflict(
    key="finance/user123/data.json",
    expected_etag="abc123"
)

if conflict:
    # Handle conflict - reload and retry
    print("Data was modified by another process")
else:
    # Safe to proceed with update
    await manager.upload_json_blob(key, updated_data)
```

## Testing

Run the test suite:

```bash
# Run all R2 storage tests
pytest tests/test_r2_storage.py -v

# Run specific test categories
pytest tests/test_r2_storage.py -k "dataclass" -v
pytest tests/test_r2_storage.py -k "presigned" -v
pytest tests/test_r2_storage.py -k "etag" -v
```

Run the demonstration:

```bash
# Simple feature demo (no dependencies required)
python demo_r2_simple.py

# Integration example (requires mocking)
python umbra/storage/r2_integration_example.py
```

## Migration from SQLite

The system provides a seamless migration path:

1. **Phase 1**: Deploy with `STORAGE_BACKEND=hybrid` to use both systems
2. **Phase 2**: Migrate existing data from SQLite to R2
3. **Phase 3**: Switch to `STORAGE_BACKEND=r2` for R2-only mode

The unified storage interface handles backend selection automatically based on configuration.

## Dependencies

Required packages (automatically installed):

```
boto3>=1.34.51         # AWS S3 SDK for R2 access
pyarrow>=15.0.0        # Parquet file support
pandas>=2.2.1          # Data manipulation for Parquet
pytest>=8.0.0          # Testing framework
pytest-asyncio>=0.23.5 # Async test support
```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Modules       │    │ Unified Storage  │    │ R2 Storage      │
│ (finance, etc.) │───▶│    Manager       │───▶│   Manager       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                 │                        │
                                 ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │ SQLite Database  │    │ Cloudflare R2   │
                       │   (fallback)     │    │   (primary)     │
                       └──────────────────┘    └─────────────────┘
```

## Error Handling

The system includes comprehensive error handling:

- **R2 connection failures**: Automatic fallback to SQLite
- **Missing dependencies**: Graceful degradation with warnings
- **ETag conflicts**: Detection and retry mechanisms
- **Network issues**: Exponential backoff and retry logic

## Security Considerations

- R2 credentials are loaded from environment variables only
- Presigned URLs have configurable expiration times
- ETag validation prevents concurrent modification issues
- Module/user data isolation via key prefixes

For more details, see the source code in `umbra/storage/r2_manager.py` and `umbra/storage/unified_storage.py`.