#!/usr/bin/env python3
"""
Swiss Accountant Backup & Migration Utilities
Database backup, restore, and migration tools.
"""

import os
import sys
import sqlite3
import shutil
import json
import gzip
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Optional, Any
import tempfile
import logging

# Add the module path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from umbra.modules.swiss_accountant import create_swiss_accountant, get_default_config

class BackupManager:
    """Manages database backup and restore operations."""
    
    def __init__(self, db_path: str):
        """Initialize backup manager.
        
        Args:
            db_path: Path to Swiss Accountant database
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    def create_backup(self, backup_path: str = None, compress: bool = True) -> Dict[str, Any]:
        """Create full database backup.
        
        Args:
            backup_path: Optional backup file path
            compress: Whether to compress the backup
            
        Returns:
            Dict with backup result
        """
        try:
            if not os.path.exists(self.db_path):
                return {
                    'success': False,
                    'error': f'Database file not found: {self.db_path}'
                }
            
            # Generate backup filename if not provided
            if not backup_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f'swiss_accountant_backup_{timestamp}'
                backup_name += '.sql.gz' if compress else '.sql'
                backup_path = backup_name
            
            self.logger.info(f"Creating backup: {backup_path}")
            
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            
            # Create SQL dump
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as tmp_file:
                tmp_sql_path = tmp_file.name
                
                # Write header
                tmp_file.write(f"-- Swiss Accountant Database Backup\n")
                tmp_file.write(f"-- Created: {datetime.now().isoformat()}\n")
                tmp_file.write(f"-- Source: {self.db_path}\n\n")
                
                # Dump database
                for line in conn.iterdump():
                    tmp_file.write(f"{line}\n")
            
            conn.close()
            
            # Compress if requested
            if compress:
                with open(tmp_sql_path, 'rb') as f_in:
                    with gzip.open(backup_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.unlink(tmp_sql_path)
            else:
                shutil.move(tmp_sql_path, backup_path)
            
            # Get backup info
            backup_size = os.path.getsize(backup_path)
            
            # Get database statistics
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {}
            tables = ['sa_expenses', 'sa_transactions', 'sa_statements', 'sa_merchants', 'sa_documents']
            
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    stats[table] = count
                except sqlite3.OperationalError:
                    stats[table] = 0
            
            conn.close()
            
            return {
                'success': True,
                'backup_path': backup_path,
                'backup_size': backup_size,
                'compressed': compress,
                'timestamp': datetime.now().isoformat(),
                'database_stats': stats
            }
            
        except Exception as e:
            self.logger.error(f"Backup failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def restore_backup(self, backup_path: str, target_db_path: str = None) -> Dict[str, Any]:
        """Restore database from backup.
        
        Args:
            backup_path: Path to backup file
            target_db_path: Optional target database path (defaults to original)
            
        Returns:
            Dict with restore result
        """
        try:
            if not os.path.exists(backup_path):
                return {
                    'success': False,
                    'error': f'Backup file not found: {backup_path}'
                }
            
            if not target_db_path:
                target_db_path = self.db_path
            
            self.logger.info(f"Restoring backup: {backup_path} -> {target_db_path}")
            
            # Check if backup is compressed
            is_compressed = backup_path.endswith('.gz')
            
            # Read backup content
            if is_compressed:
                with gzip.open(backup_path, 'rt') as f:
                    sql_content = f.read()
            else:
                with open(backup_path, 'r') as f:
                    sql_content = f.read()
            
            # Remove existing database if it exists
            if os.path.exists(target_db_path):
                backup_existing = f"{target_db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.move(target_db_path, backup_existing)
                self.logger.info(f"Existing database backed up to: {backup_existing}")
            
            # Create new database
            conn = sqlite3.connect(target_db_path)
            
            # Execute SQL dump
            conn.executescript(sql_content)
            conn.close()
            
            # Verify restoration
            verification = self._verify_database(target_db_path)
            
            return {
                'success': True,
                'target_path': target_db_path,
                'backup_path': backup_path,
                'compressed': is_compressed,
                'verification': verification,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Restore failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _verify_database(self, db_path: str) -> Dict[str, Any]:
        """Verify database integrity after restore."""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check integrity
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            
            # Get table counts
            tables = {}
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            table_names = [row[0] for row in cursor.fetchall()]
            
            for table in table_names:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                tables[table] = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'integrity': integrity_result,
                'tables': tables,
                'valid': integrity_result == 'ok'
            }
            
        except Exception as e:
            return {
                'integrity': f'Error: {e}',
                'tables': {},
                'valid': False
            }
    
    def export_data(self, export_path: str, format: str = 'json', 
                   user_id: str = None, include_documents: bool = False) -> Dict[str, Any]:
        """Export data in various formats.
        
        Args:
            export_path: Output file path
            format: Export format ('json', 'csv')
            user_id: Optional user filter
            include_documents: Whether to include document content
            
        Returns:
            Dict with export result
        """
        try:
            self.logger.info(f"Exporting data to {export_path} (format: {format})")
            
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            # Export data based on format
            if format.lower() == 'json':
                result = self._export_json(cursor, export_path, user_id, include_documents)
            elif format.lower() == 'csv':
                result = self._export_csv(cursor, export_path, user_id)
            else:
                result = {
                    'success': False,
                    'error': f'Unsupported format: {format}'
                }
            
            conn.close()
            return result
            
        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _export_json(self, cursor, export_path: str, user_id: str = None, 
                    include_documents: bool = False) -> Dict[str, Any]:
        """Export data as JSON."""
        try:
            export_data = {
                'metadata': {
                    'export_timestamp': datetime.now().isoformat(),
                    'source_database': self.db_path,
                    'user_id': user_id,
                    'include_documents': include_documents,
                    'version': '1.0'
                },
                'data': {}
            }
            
            # Define tables to export
            tables = [
                'sa_expenses',
                'sa_transactions', 
                'sa_statements',
                'sa_merchants',
                'sa_category_mappings',
                'sa_reconciliation_matches'
            ]
            
            if include_documents:
                tables.extend(['sa_documents', 'sa_receipts'])
            
            total_records = 0
            
            for table in tables:
                try:
                    # Build query with optional user filter
                    query = f"SELECT * FROM {table}"
                    params = []
                    
                    if user_id and table in ['sa_expenses', 'sa_statements']:
                        query += " WHERE user_id = ?"
                        params.append(user_id)
                    
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    
                    # Convert rows to dictionaries
                    table_data = []
                    for row in rows:
                        row_dict = dict(row)
                        # Convert date objects to strings
                        for key, value in row_dict.items():
                            if isinstance(value, (date, datetime)):
                                row_dict[key] = value.isoformat()
                        table_data.append(row_dict)
                    
                    export_data['data'][table] = table_data
                    total_records += len(table_data)
                    
                except sqlite3.OperationalError:
                    # Table doesn't exist
                    export_data['data'][table] = []
            
            # Write JSON file
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            export_size = os.path.getsize(export_path)
            
            return {
                'success': True,
                'export_path': export_path,
                'format': 'json',
                'total_records': total_records,
                'export_size': export_size,
                'tables_exported': list(export_data['data'].keys())
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _export_csv(self, cursor, export_path: str, user_id: str = None) -> Dict[str, Any]:
        """Export expenses as CSV."""
        try:
            import csv
            
            # Query expenses with related data
            query = """
                SELECT 
                    e.id,
                    e.date_local,
                    e.merchant_text,
                    m.canonical as merchant_canonical,
                    e.amount_cents / 100.0 as amount_chf,
                    e.currency,
                    e.category_code,
                    e.pro_pct,
                    e.notes,
                    e.payment_method,
                    e.vat_breakdown_json,
                    e.created_at
                FROM sa_expenses e
                LEFT JOIN sa_merchants m ON e.merchant_id = m.id
            """
            
            params = []
            if user_id:
                query += " WHERE e.user_id = ?"
                params.append(user_id)
            
            query += " ORDER BY e.date_local DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            if not rows:
                return {
                    'success': False,
                    'error': 'No data to export'
                }
            
            # Write CSV file
            with open(export_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')
                
                # Header
                header = [
                    'ID', 'Date', 'Merchant', 'Canonical Merchant', 'Amount (CHF)',
                    'Currency', 'Category', 'Business %', 'Notes', 'Payment Method',
                    'VAT Info', 'Created At'
                ]
                writer.writerow(header)
                
                # Data rows
                for row in rows:
                    writer.writerow([
                        row['id'],
                        row['date_local'],
                        row['merchant_text'],
                        row['merchant_canonical'] or '',
                        f"{row['amount_chf']:.2f}",
                        row['currency'],
                        row['category_code'],
                        row['pro_pct'],
                        row['notes'] or '',
                        row['payment_method'] or '',
                        row['vat_breakdown_json'] or '',
                        row['created_at']
                    ])
            
            export_size = os.path.getsize(export_path)
            
            return {
                'success': True,
                'export_path': export_path,
                'format': 'csv',
                'total_records': len(rows),
                'export_size': export_size,
                'delimiter': ';'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def import_data(self, import_path: str, user_id: str, 
                   merge: bool = False) -> Dict[str, Any]:
        """Import data from exported file.
        
        Args:
            import_path: Path to import file
            user_id: User ID for imported data
            merge: Whether to merge with existing data
            
        Returns:
            Dict with import result
        """
        try:
            if not os.path.exists(import_path):
                return {
                    'success': False,
                    'error': f'Import file not found: {import_path}'
                }
            
            self.logger.info(f"Importing data from {import_path}")
            
            # Determine format from file extension
            if import_path.endswith('.json'):
                return self._import_json(import_path, user_id, merge)
            elif import_path.endswith('.csv'):
                return self._import_csv(import_path, user_id, merge)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported import format'
                }
                
        except Exception as e:
            self.logger.error(f"Import failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _import_json(self, import_path: str, user_id: str, merge: bool) -> Dict[str, Any]:
        """Import JSON data."""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            if 'data' not in import_data:
                return {
                    'success': False,
                    'error': 'Invalid JSON format - missing data section'
                }
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            imported_counts = {}
            
            # Import each table
            for table, records in import_data['data'].items():
                if not records:
                    imported_counts[table] = 0
                    continue
                
                try:
                    # Get table columns
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns_info = cursor.fetchall()
                    columns = [col[1] for col in columns_info]
                    
                    imported_count = 0
                    
                    for record in records:
                        # Update user_id if applicable
                        if 'user_id' in record and 'user_id' in columns:
                            record['user_id'] = user_id
                        
                        # Prepare insert statement
                        placeholders = ', '.join(['?'] * len(record))
                        column_names = ', '.join(record.keys())
                        
                        if merge:
                            # Use INSERT OR REPLACE for merging
                            query = f"INSERT OR REPLACE INTO {table} ({column_names}) VALUES ({placeholders})"
                        else:
                            # Use INSERT OR IGNORE to skip duplicates
                            query = f"INSERT OR IGNORE INTO {table} ({column_names}) VALUES ({placeholders})"
                        
                        cursor.execute(query, list(record.values()))
                        
                        if cursor.rowcount > 0:
                            imported_count += 1
                    
                    imported_counts[table] = imported_count
                    
                except sqlite3.OperationalError as e:
                    self.logger.warning(f"Failed to import table {table}: {e}")
                    imported_counts[table] = 0
            
            conn.commit()
            conn.close()
            
            total_imported = sum(imported_counts.values())
            
            return {
                'success': True,
                'import_path': import_path,
                'user_id': user_id,
                'merge_mode': merge,
                'total_imported': total_imported,
                'imported_by_table': imported_counts
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

def main():
    """Main backup utility function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Swiss Accountant Backup & Migration Utility')
    parser.add_argument('--database', '-d', required=True, help='Database file path')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Create database backup')
    backup_parser.add_argument('--output', '-o', help='Backup file path')
    backup_parser.add_argument('--no-compress', action='store_true', help='Disable compression')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore from backup')
    restore_parser.add_argument('backup_file', help='Backup file to restore')
    restore_parser.add_argument('--target', '-t', help='Target database path')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export data')
    export_parser.add_argument('output_file', help='Output file path')
    export_parser.add_argument('--format', '-f', choices=['json', 'csv'], default='json', help='Export format')
    export_parser.add_argument('--user-id', '-u', help='User ID filter')
    export_parser.add_argument('--include-documents', action='store_true', help='Include document content')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import data')
    import_parser.add_argument('import_file', help='File to import')
    import_parser.add_argument('--user-id', '-u', required=True, help='User ID for imported data')
    import_parser.add_argument('--merge', action='store_true', help='Merge with existing data')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize backup manager
    backup_manager = BackupManager(args.database)
    
    # Execute command
    if args.command == 'backup':
        result = backup_manager.create_backup(
            backup_path=args.output,
            compress=not args.no_compress
        )
        
        if result['success']:
            print(f"✅ Backup created successfully!")
            print(f"   File: {result['backup_path']}")
            print(f"   Size: {result['backup_size']:,} bytes")
            print(f"   Compressed: {result['compressed']}")
            print(f"   Records by table:")
            for table, count in result['database_stats'].items():
                print(f"      {table}: {count:,}")
        else:
            print(f"❌ Backup failed: {result['error']}")
    
    elif args.command == 'restore':
        result = backup_manager.restore_backup(
            backup_path=args.backup_file,
            target_db_path=args.target
        )
        
        if result['success']:
            print(f"✅ Restore completed successfully!")
            print(f"   Source: {result['backup_path']}")
            print(f"   Target: {result['target_path']}")
            print(f"   Verification: {'✅ Passed' if result['verification']['valid'] else '❌ Failed'}")
            if result['verification']['tables']:
                print(f"   Restored tables:")
                for table, count in result['verification']['tables'].items():
                    print(f"      {table}: {count:,} records")
        else:
            print(f"❌ Restore failed: {result['error']}")
    
    elif args.command == 'export':
        result = backup_manager.export_data(
            export_path=args.output_file,
            format=args.format,
            user_id=args.user_id,
            include_documents=args.include_documents
        )
        
        if result['success']:
            print(f"✅ Export completed successfully!")
            print(f"   File: {result['export_path']}")
            print(f"   Format: {result['format']}")
            print(f"   Records: {result['total_records']:,}")
            print(f"   Size: {result['export_size']:,} bytes")
            if 'tables_exported' in result:
                print(f"   Tables: {', '.join(result['tables_exported'])}")
        else:
            print(f"❌ Export failed: {result['error']}")
    
    elif args.command == 'import':
        result = backup_manager.import_data(
            import_path=args.import_file,
            user_id=args.user_id,
            merge=args.merge
        )
        
        if result['success']:
            print(f"✅ Import completed successfully!")
            print(f"   File: {result['import_path']}")
            print(f"   User ID: {result['user_id']}")
            print(f"   Mode: {'Merge' if result['merge_mode'] else 'Insert new only'}")
            print(f"   Total imported: {result['total_imported']:,}")
            print(f"   By table:")
            for table, count in result['imported_by_table'].items():
                print(f"      {table}: {count:,}")
        else:
            print(f"❌ Import failed: {result['error']}")

if __name__ == "__main__":
    main()
