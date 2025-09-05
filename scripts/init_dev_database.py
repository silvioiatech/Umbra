#!/usr/bin/env python3
"""
UMBRA Development Database Initializer
Initializes development database structure for feature branches.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

async def init_development_database():
    """Initialize development database with proper structure."""
    print("🗄️ Initializing UMBRA development database...")
    
    # Set development environment
    os.environ.setdefault('DATABASE_PATH', 'data/umbra_dev.db')
    os.environ.setdefault('ENVIRONMENT', 'development')
    
    try:
        from umbra.storage.database import DatabaseManager
        from umbra.core.config import UmbraConfig
        
        # Create development config
        config = UmbraConfig()
        db_path = config.get_storage_path() / "umbra_dev.db"
        
        print(f"📍 Database location: {db_path}")
        
        # Ensure data directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database manager
        db_manager = DatabaseManager(str(db_path))
        await db_manager.connect()
        
        print("✅ Database connection established")
        
        # Initialize core tables
        await init_core_tables(db_manager)
        
        # Initialize module-specific tables
        await init_module_tables(db_manager)
        
        await db_manager.close()
        
        print(f"✅ Development database initialized: {db_path}")
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

async def init_core_tables(db_manager):
    """Initialize core application tables."""
    print("📋 Creating core tables...")
    
    # Users table
    await db_manager.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            is_admin BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Conversations table for AI context
    await db_manager.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message_id INTEGER,
            user_message TEXT,
            bot_response TEXT,
            module_used TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (telegram_id)
        )
    """)
    
    # System metrics
    await db_manager.execute("""
        CREATE TABLE IF NOT EXISTS system_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            metric_value TEXT NOT NULL,
            metric_type TEXT DEFAULT 'counter',
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    print("✅ Core tables created")

async def init_module_tables(db_manager):
    """Initialize tables for all MCP modules."""
    print("🔧 Creating module tables...")
    
    # Finance module tables
    await db_manager.execute("""
        CREATE TABLE IF NOT EXISTS finance_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            category TEXT,
            date DATE DEFAULT CURRENT_DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (telegram_id)
        )
    """)
    
    await db_manager.execute("""
        CREATE TABLE IF NOT EXISTS finance_budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT NOT NULL,
            monthly_limit REAL NOT NULL,
            current_spent REAL DEFAULT 0,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (telegram_id)
        )
    """)
    
    # Business module tables
    await db_manager.execute("""
        CREATE TABLE IF NOT EXISTS business_clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            client_name TEXT NOT NULL,
            contact_info TEXT,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (telegram_id)
        )
    """)
    
    await db_manager.execute("""
        CREATE TABLE IF NOT EXISTS business_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            client_id INTEGER,
            project_name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'planning',
            budget REAL,
            start_date DATE,
            end_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (telegram_id),
            FOREIGN KEY (client_id) REFERENCES business_clients (id)
        )
    """)
    
    # Production module tables (workflows)
    await db_manager.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            workflow_json TEXT,
            status TEXT DEFAULT 'draft',
            n8n_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (telegram_id)
        )
    """)
    
    # Creator module tables
    await db_manager.execute("""
        CREATE TABLE IF NOT EXISTS creator_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content_type TEXT NOT NULL,
            title TEXT,
            content TEXT,
            metadata TEXT,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (telegram_id)
        )
    """)
    
    # Concierge module tables (system monitoring)
    await db_manager.execute("""
        CREATE TABLE IF NOT EXISTS system_monitoring (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            server_name TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            value TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (telegram_id)
        )
    """)
    
    print("✅ Module tables created")

async def seed_development_data(db_manager):
    """Seed with some development data."""
    print("🌱 Seeding development data...")
    
    # Add a development user entry (placeholder)
    await db_manager.execute("""
        INSERT OR IGNORE INTO users (telegram_id, username, first_name, is_admin)
        VALUES (999999999, 'dev_user', 'Development User', TRUE)
    """)
    
    # Add some sample categories for finance
    sample_categories = ['food', 'transport', 'entertainment', 'utilities', 'income']
    for category in sample_categories:
        await db_manager.execute("""
            INSERT OR IGNORE INTO finance_budgets (user_id, category, monthly_limit, month, year)
            VALUES (999999999, ?, 1000.0, ?, ?)
        """, (category, 1, 2024))
    
    print("✅ Development data seeded")

def main():
    """Main initialization function."""
    print("🔧 UMBRA Development Database Initializer")
    print("=" * 50)
    
    try:
        # Run initialization
        result = asyncio.run(init_development_database())
        
        if result:
            print("\n✅ Development database ready for feature branch development!")
            print("\n💡 The database includes:")
            print("   - User management tables")
            print("   - All MCP module tables")
            print("   - System metrics tracking") 
            print("   - Sample development data")
            print(f"\n📍 Database location: data/umbra_dev.db")
            return 0
        else:
            print("\n❌ Database initialization failed")
            return 1
            
    except Exception as e:
        print(f"\n❌ Initialization error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())