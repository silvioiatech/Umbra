"""Database management for Umbra bot."""
import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, NamedTuple
from datetime import datetime
from contextlib import contextmanager

# Global database manager instance
_db_manager: Optional["DatabaseManager"] = None

class ConversationMessage(NamedTuple):
    """Represents a conversation message from the database."""
    message: str
    response: str
    timestamp: str
    module: Optional[str]


class Client(NamedTuple):
    """Represents a client from the database."""
    id: Optional[int] = None
    name: str = ""
    company: str = ""
    email: str = ""
    phone: str = ""
    status: str = "active"
    metadata: Dict[str, Any] = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Workflow(NamedTuple):
    """Represents a workflow from the database."""
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    client_id: Optional[int] = None
    status: str = "pending"
    plan: str = ""
    created_by: str = ""
    deployed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class DatabaseManager:
    """Manages SQLite database operations for Umbra bot."""
    
    def __init__(self, db_path: str = "storage/umbra.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self._init_database()
    
    def _init_database(self):
        """Initialize the database with required tables."""
        with self.get_connection() as conn:
            # Users table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Conversations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    chat_id TEXT,
                    message TEXT,
                    response TEXT,
                    intent TEXT,
                    confidence REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    module TEXT,
                    metadata TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # User preferences table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id INTEGER PRIMARY KEY,
                    language TEXT DEFAULT 'en',
                    timezone TEXT DEFAULT 'UTC',
                    notifications_enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Module data table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS module_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    module TEXT,
                    key TEXT,
                    value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            """)
            
            # Clients table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    company TEXT,
                    email TEXT,
                    phone TEXT,
                    status TEXT DEFAULT 'active',
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Workflows table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    client_id INTEGER,
                    status TEXT DEFAULT 'pending',
                    plan TEXT,
                    created_by TEXT,
                    deployed_at TIMESTAMP,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients (id)
                )
            """)
            
            conn.commit()
            self.logger.info("Database initialized successfully")
    
    def execute(self, query: str, params: tuple = None) -> bool:
        """Execute a query (for INSERT, UPDATE, DELETE)."""
        try:
            with self.get_connection() as conn:
                if params:
                    conn.execute(query, params)
                else:
                    conn.execute(query)
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Database execute error: {e}")
            return False
    
    def query_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Execute a query and return one result as a dictionary."""
        try:
            with self.get_connection() as conn:
                if params:
                    cursor = conn.execute(query, params)
                else:
                    cursor = conn.execute(query)
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            self.logger.error(f"Database query_one error: {e}")
            return None
    
    def query_all(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute a query and return all results as dictionaries."""
        try:
            with self.get_connection() as conn:
                if params:
                    cursor = conn.execute(query, params)
                else:
                    cursor = conn.execute(query)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Database query_all error: {e}")
            return []
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def add_user(self, user_id: int, username: Optional[str] = None, 
                first_name: Optional[str] = None, last_name: Optional[str] = None):
        """Add or update a user in the database."""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_activity)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, username, first_name, last_name))
            conn.commit()
    
    def add_conversation(self, user_id: int, message: str, response: str, 
                        module: Optional[str] = None) -> int:
        """Add a conversation entry."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO conversations (user_id, message, response, module)
                VALUES (?, ?, ?, ?)
            """, (user_id, message, response, module))
            conn.commit()
            return cursor.lastrowid
    
    def get_conversation_history(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get conversation history for a user."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT message, response, timestamp, module
                FROM conversations
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def set_user_preference(self, user_id: int, key: str, value: Any):
        """Set a user preference."""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_preferences (user_id, language, timezone, notifications_enabled, updated_at)
                VALUES (
                    ?,
                    COALESCE((SELECT language FROM user_preferences WHERE user_id = ?), 'en'),
                    COALESCE((SELECT timezone FROM user_preferences WHERE user_id = ?), 'UTC'),
                    COALESCE((SELECT notifications_enabled FROM user_preferences WHERE user_id = ?), TRUE),
                    CURRENT_TIMESTAMP
                )
            """, (user_id, user_id, user_id, user_id))
            
            # Update specific preference
            if key == "language":
                conn.execute("UPDATE user_preferences SET language = ? WHERE user_id = ?", (value, user_id))
            elif key == "timezone":
                conn.execute("UPDATE user_preferences SET timezone = ? WHERE user_id = ?", (value, user_id))
            elif key == "notifications_enabled":
                conn.execute("UPDATE user_preferences SET notifications_enabled = ? WHERE user_id = ?", (value, user_id))
            conn.commit()
    
    def get_user_preference(self, user_id: int, key: str, default: Any = None) -> Any:
        """Get a user preference."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT language, timezone, notifications_enabled
                FROM user_preferences
                WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row).get(key, default)
            return default
    
    def set_module_data(self, user_id: int, module: str, key: str, value: Any):
        """Set module-specific data for a user."""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO module_data (user_id, module, key, value, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, module, key, json.dumps(value) if not isinstance(value, str) else value))
            conn.commit()
    
    def get_module_data(self, user_id: int, module: str, key: Optional[str] = None) -> Any:
        """Get module-specific data for a user."""
        with self.get_connection() as conn:
            if key:
                cursor = conn.execute("""
                    SELECT value FROM module_data
                    WHERE user_id = ? AND module = ? AND key = ?
                """, (user_id, module, key))
                row = cursor.fetchone()
                if row:
                    try:
                        return json.loads(row["value"])
                    except json.JSONDecodeError:
                        return row["value"]
            else:
                cursor = conn.execute("""
                    SELECT key, value FROM module_data
                    WHERE user_id = ? AND module = ?
                """, (user_id, module))
                result = {}
                for row in cursor.fetchall():
                    try:
                        result[row["key"]] = json.loads(row["value"])
                    except json.JSONDecodeError:
                        result[row["key"]] = row["value"]
                return result
            return None

    # Client management methods
    async def add_client(self, client: Client) -> int:
        """Add a client to the database."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO clients (name, company, email, phone, status, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (client.name, client.company, client.email, client.phone, client.status, 
                  json.dumps(client.metadata)))
            conn.commit()
            return cursor.lastrowid

    async def get_clients(self, status: str = None) -> List[Client]:
        """Get clients from the database."""
        with self.get_connection() as conn:
            if status:
                cursor = conn.execute("SELECT * FROM clients WHERE status = ? ORDER BY created_at DESC", (status,))
            else:
                cursor = conn.execute("SELECT * FROM clients ORDER BY created_at DESC")
            
            clients = []
            for row in cursor.fetchall():
                clients.append(Client(
                    id=row["id"],
                    name=row["name"],
                    company=row["company"],
                    email=row["email"],
                    phone=row["phone"],
                    status=row["status"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                    updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None
                ))
            return clients

    async def get_client_by_id(self, client_id: int) -> Optional[Client]:
        """Get a specific client by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
            row = cursor.fetchone()
            if row:
                return Client(
                    id=row["id"],
                    name=row["name"],
                    company=row["company"],
                    email=row["email"],
                    phone=row["phone"],
                    status=row["status"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                    updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None
                )
            return None

    # Workflow management methods
    async def add_workflow(self, workflow: Workflow) -> int:
        """Add a workflow to the database."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO workflows (name, description, client_id, status, plan, created_by, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (workflow.name, workflow.description, workflow.client_id, workflow.status, 
                  workflow.plan, workflow.created_by, json.dumps(workflow.metadata)))
            conn.commit()
            return cursor.lastrowid

    async def get_workflows(self, created_by: str = None, client_id: int = None) -> List[Workflow]:
        """Get workflows from the database."""
        with self.get_connection() as conn:
            query = "SELECT * FROM workflows"
            params = []
            
            if created_by and client_id:
                query += " WHERE created_by = ? AND client_id = ?"
                params = [created_by, client_id]
            elif created_by:
                query += " WHERE created_by = ?"
                params = [created_by]
            elif client_id:
                query += " WHERE client_id = ?"
                params = [client_id]
            
            query += " ORDER BY created_at DESC"
            cursor = conn.execute(query, params)
            
            workflows = []
            for row in cursor.fetchall():
                workflows.append(Workflow(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    client_id=row["client_id"],
                    status=row["status"],
                    plan=row["plan"],
                    created_by=row["created_by"],
                    deployed_at=datetime.fromisoformat(row["deployed_at"]) if row["deployed_at"] else None,
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                    updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None
                ))
            return workflows

# Global database functions that agent.py expects

async def get_database() -> DatabaseManager:
    """Get or create the global database manager instance."""
    global _db_manager
    
    if _db_manager is None:
        from ..core.config import get_config
        config = get_config()
        _db_manager = DatabaseManager(config.database_path)
    
    return _db_manager

async def add_conversation_message(
    user_id: str,
    chat_id: str, 
    message: str,
    intent: str,
    confidence: float,
    response: str,
    metadata: Dict[str, Any]
) -> None:
    """Add a conversation message to the database."""
    db = await get_database()
    
    with db.get_connection() as conn:
        conn.execute("""
            INSERT INTO conversations 
            (user_id, chat_id, message, intent, confidence, response, metadata, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            int(user_id), chat_id, message, intent, confidence, response,
            json.dumps(metadata) if metadata else None
        ))
        conn.commit()

async def get_conversation_history(chat_id: str, limit: int = 50) -> List[ConversationMessage]:
    """Get conversation history for a chat."""
    db = await get_database()
    
    with db.get_connection() as conn:
        cursor = conn.execute("""
            SELECT message, response, timestamp, module
            FROM conversations
            WHERE chat_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (chat_id, limit))
        
        messages = []
        for row in cursor.fetchall():
            messages.append(ConversationMessage(
                message=row["message"],
                response=row["response"],
                timestamp=row["timestamp"],
                module=row["module"]
            ))
        
        return messages