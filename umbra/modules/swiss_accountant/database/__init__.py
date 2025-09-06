"""
Database module for Swiss Accountant
Handles SQLite database operations and schema management.
"""

from .manager import DatabaseManager, create_database_manager
from .schema import create_tables

__all__ = ['DatabaseManager', 'create_database_manager', 'create_tables']
