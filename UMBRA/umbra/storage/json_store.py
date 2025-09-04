"""
Lightweight persistent JSON storage for the Umbra bot.

Provides async-safe JSON file operations with atomic writes,
file locking, and thread-safe operations for small data storage.
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Union

from ..core.logger import get_logger

logger = get_logger("umbra.storage")


class JSONStore:
    """Async-safe JSON file storage with atomic writes and locking."""

    def __init__(self, file_path: Union[str, Path], create_dirs: bool = True):
        """
        Initialize JSON store.
        
        Args:
            file_path: Path to the JSON file
            create_dirs: Whether to create parent directories if they don't exist
        """
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()
        self._initialized = False

        if create_dirs:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # using extra for structured logging (migrated file_path from unsupported kwargs)
        logger.info("JSON store initialized", extra={"file_path": str(self.file_path)})

    async def initialize(self) -> bool:
        """
        Initialize the store, creating the file if it doesn't exist.
        
        Returns:
            True if initialization successful
        """
        async with self._lock:
            if self._initialized:
                return True

            try:
                if not self.file_path.exists():
                    await self._atomic_write({})
                    # using extra for structured logging (migrated file_path from unsupported kwargs)
                    logger.info("Created new JSON store file", extra={"file_path": str(self.file_path)})
                else:
                    # Validate existing file
                    await self.read()
                    # using extra for structured logging (migrated file_path from unsupported kwargs)
                    logger.info("Validated existing JSON store file", extra={"file_path": str(self.file_path)})

                self._initialized = True
                return True

            except Exception as e:
                logger.exception("Failed to initialize JSON store",
                           extra={"file_path": str(self.file_path)})
                return False

    async def read(self) -> dict[str, Any]:
        """
        Read data from the JSON file.
        
        Returns:
            Dictionary containing the JSON data
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            try:
                if not self.file_path.exists():
                    return {}

                # Read the file using thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                content = await loop.run_in_executor(
                    None,
                    lambda: self.file_path.read_text(encoding='utf-8')
                )

                if not content.strip():
                    return {}

                data = json.loads(content)
                logger.debug("Read data from JSON store",
                           file_path=str(self.file_path),
                           size_bytes=len(content))

                return data

            except json.JSONDecodeError as e:
                logger.exception("Invalid JSON in store file",
                           extra={"file_path": str(self.file_path)})
                # Return empty dict for corrupted file
                return {}
            except Exception as e:
                logger.exception("Failed to read from JSON store",
                           extra={"file_path": str(self.file_path)})
                raise

    async def write(self, data: dict[str, Any]) -> bool:
        """
        Write data to the JSON file using atomic operation.
        
        Args:
            data: Dictionary to write as JSON
            
        Returns:
            True if write successful
        """
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            return await self._atomic_write(data)

    async def _atomic_write(self, data: dict[str, Any]) -> bool:
        """
        Perform atomic write using temporary file and rename.
        
        Args:
            data: Data to write
            
        Returns:
            True if successful
        """
        try:
            # Serialize JSON
            json_content = json.dumps(data, indent=2, ensure_ascii=False)

            # Create temporary file in the same directory for atomic rename
            temp_dir = self.file_path.parent
            temp_fd, temp_path = tempfile.mkstemp(
                dir=temp_dir,
                prefix=f".{self.file_path.name}.tmp",
                suffix=".json"
            )
            temp_path = Path(temp_path)

            try:
                # Write to temporary file using thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self._write_temp_file(temp_fd, json_content)
                )

                # Atomic rename
                await loop.run_in_executor(
                    None,
                    lambda: temp_path.replace(self.file_path)
                )

                logger.debug("Atomic write completed",
                           file_path=str(self.file_path),
                           size_bytes=len(json_content))

                return True

            except Exception as e:
                # Clean up temporary file on error
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except:
                    pass
                raise e

        except Exception as e:
            logger.exception("Atomic write failed",
                       file_path=str(self.file_path),
                       )
            return False

    def _write_temp_file(self, fd: int, content: str):
        """Write content to temporary file descriptor."""
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())  # Ensure data is written to disk
        except Exception:
            # Close the file descriptor if something goes wrong
            try:
                os.close(fd)
            except:
                pass
            raise

    async def append_event(self, event: dict[str, Any]) -> bool:
        """
        Append an event to a list in the JSON file.
        
        Args:
            event: Event dictionary to append
            
        Returns:
            True if successful
        """
        try:
            data = await self.read()

            # Initialize events list if it doesn't exist
            if 'events' not in data:
                data['events'] = []

            # Add timestamp if not present
            if 'timestamp' not in event:
                event['timestamp'] = datetime.utcnow().isoformat()

            # Append event
            data['events'].append(event)

            # Limit event history (keep last 1000 events)
            if len(data['events']) > 1000:
                data['events'] = data['events'][-1000:]

            return await self.write(data)

        except Exception as e:
            logger.exception("Failed to append event",
                       file_path=str(self.file_path),
                       )
            return False

    async def update_field(self, field_path: str, value: Any) -> bool:
        """
        Update a specific field in the JSON data.
        
        Args:
            field_path: Dot-separated path to the field (e.g., "config.enabled")
            value: Value to set
            
        Returns:
            True if successful
        """
        try:
            data = await self.read()

            # Navigate to the field location
            keys = field_path.split('.')
            current = data

            # Navigate to parent of target field
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            # Set the final value
            current[keys[-1]] = value

            return await self.write(data)

        except Exception as e:
            logger.exception("Failed to update field",
                       file_path=str(self.file_path),
                       field_path=field_path,
                       )
            return False

    async def get_field(self, field_path: str, default: Any = None) -> Any:
        """
        Get a specific field from the JSON data.
        
        Args:
            field_path: Dot-separated path to the field
            default: Default value if field doesn't exist
            
        Returns:
            Field value or default
        """
        try:
            data = await self.read()

            keys = field_path.split('.')
            current = data

            for key in keys:
                if not isinstance(current, dict) or key not in current:
                    return default
                current = current[key]

            return current

        except Exception as e:
            logger.exception("Failed to get field",
                       file_path=str(self.file_path),
                       field_path=field_path,
                       )
            return default

    async def clear(self) -> bool:
        """
        Clear the JSON file (reset to empty dict).
        
        Returns:
            True if successful
        """
        return await self.write({})

    def get_file_path(self) -> Path:
        """Get the file path."""
        return self.file_path

    async def exists(self) -> bool:
        """Check if the file exists."""
        return self.file_path.exists()

    async def get_file_size(self) -> int:
        """Get file size in bytes."""
        try:
            if await self.exists():
                return self.file_path.stat().st_size
            return 0
        except Exception:
            return 0


# Convenience functions for default storage paths

def get_default_storage_path() -> Path:
    """Get default storage directory path."""
    return Path(__file__).parent.parent.parent / "storage"


def get_finance_store_path() -> Path:
    """Get finance module storage path."""
    return get_default_storage_path() / "finance.json"


def get_metrics_store_path() -> Path:
    """Get metrics storage path."""
    return get_default_storage_path() / "metrics.json"


def get_user_data_store_path() -> Path:
    """Get user data storage path."""
    return get_default_storage_path() / "user_data.json"


async def create_finance_store() -> JSONStore:
    """Create and initialize finance JSON store."""
    store = JSONStore(get_finance_store_path())
    await store.initialize()
    return store


async def create_metrics_store() -> JSONStore:
    """Create and initialize metrics JSON store."""
    store = JSONStore(get_metrics_store_path())
    await store.initialize()
    return store


async def create_user_data_store() -> JSONStore:
    """Create and initialize user data JSON store."""
    store = JSONStore(get_user_data_store_path())
    await store.initialize()
    return store
