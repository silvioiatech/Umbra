#!/usr/bin/env python3
"""
Swiss Accountant Maintenance Utilities
Database maintenance, cleanup, and optimization tools.
"""

import os
import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
import tempfile

# Add the module path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from umbra.modules.swiss_accountant import create_swiss_accountant, get_default_config

class MaintenanceManager:
    """Manages database maintenance and optimization tasks."""
    
    def __init__(self, db_path: str):
        """Initialize maintenance manager.
        
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
    
    def analyze_database(self) -> Dict[str, Any]:
        """Analyze database structure and content.
        
        Returns:
            Dict with analysis results
        """
        try:
            if not os.path.exists(self.db_path):
                return {
                    'success': False,
                    'error': f'Database file not found: {self.db_path}'
                }
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            analysis = {
                'database_info': self._get_database_info(cursor),
                'table_statistics': self._get_table_statistics(cursor),
                'data_quality': self._analyze_data_quality(cursor),
                'storage_analysis': self._analyze_storage(cursor),
                'performance_metrics': self._get_performance_metrics(cursor),
                'recommendations': []
            }
            
            # Generate recommendations
            analysis['recommendations'] = self._generate_recommendations(analysis)
            
            conn.close()
            
            return {
                'success': True,
                'analysis': analysis,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Database analysis failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_database_info(self, cursor) -> Dict[str, Any]:
        """Get basic database information."""
        try:
            info = {}
            
            # Database size
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            info['size_bytes'] = page_count * page_size
            info['size_mb'] = info['size_bytes'] / (1024 * 1024)
            
            # SQLite version
            cursor.execute("SELECT sqlite_version()")
            info['sqlite_version'] = cursor.fetchone()[0]
            
            # Schema version
            cursor.execute("PRAGMA schema_version")
            info['schema_version'] = cursor.fetchone()[0]
            
            # Journal mode
            cursor.execute("PRAGMA journal_mode")
            info['journal_mode'] = cursor.fetchone()[0]
            
            # Auto vacuum
            cursor.execute("PRAGMA auto_vacuum")
            info['auto_vacuum'] = cursor.fetchone()[0]
            
            return info
            
        except Exception as e:
            self.logger.error(f"Failed to get database info: {e}")
            return {}
    
    def _get_table_statistics(self, cursor) -> Dict[str, Any]:
        """Get statistics for each table."""
        try:
            stats = {}
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'sa_%'")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                table_stats = {}
                
                # Row count
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                table_stats['row_count'] = cursor.fetchone()[0]
                
                # Table size estimation
                cursor.execute(f"SELECT SUM(LENGTH(HEX(CAST(* AS BLOB)))) FROM {table}")
                result = cursor.fetchone()[0]
                table_stats['estimated_size_bytes'] = result or 0
                
                # Column info
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                table_stats['column_count'] = len(columns)
                table_stats['columns'] = [{'name': col[1], 'type': col[2], 'not_null': bool(col[3])} for col in columns]
                
                # Index info
                cursor.execute(f"PRAGMA index_list({table})")
                indexes = cursor.fetchall()
                table_stats['index_count'] = len(indexes)
                
                stats[table] = table_stats
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get table statistics: {e}")
            return {}
    
    def _analyze_data_quality(self, cursor) -> Dict[str, Any]:
        """Analyze data quality issues."""
        try:
            quality = {
                'issues': [],
                'metrics': {},
                'suggestions': []
            }
            
            # Check for expenses without merchants
            cursor.execute("SELECT COUNT(*) FROM sa_expenses WHERE merchant_text IS NULL OR merchant_text = ''")
            no_merchant = cursor.fetchone()[0]
            if no_merchant > 0:
                quality['issues'].append({
                    'type': 'missing_merchant',
                    'count': no_merchant,
                    'description': f'{no_merchant} expenses without merchant information'
                })
            
            # Check for expenses without categories
            cursor.execute("SELECT COUNT(*) FROM sa_expenses WHERE category_code IS NULL OR category_code = '' OR category_code = 'other'")
            no_category = cursor.fetchone()[0]
            if no_category > 0:
                quality['issues'].append({
                    'type': 'missing_category',
                    'count': no_category,
                    'description': f'{no_category} expenses without proper categorization'
                })
            
            # Check for duplicate expenses (same amount, date, merchant)
            cursor.execute("""
                SELECT COUNT(*) FROM (
                    SELECT amount_cents, date_local, merchant_text, COUNT(*) as cnt
                    FROM sa_expenses 
                    GROUP BY amount_cents, date_local, merchant_text 
                    HAVING cnt > 1
                )
            """)
            potential_duplicates = cursor.fetchone()[0]
            if potential_duplicates > 0:
                quality['issues'].append({
                    'type': 'potential_duplicates',
                    'count': potential_duplicates,
                    'description': f'{potential_duplicates} potential duplicate expense groups'
                })
            
            # Check for unmatched expenses
            cursor.execute("""
                SELECT COUNT(*) FROM sa_expenses e
                LEFT JOIN sa_reconciliation_matches rm ON e.id = rm.expense_id
                WHERE rm.id IS NULL
            """)
            unmatched_expenses = cursor.fetchone()[0]
            
            # Total expenses for percentage calculation
            cursor.execute("SELECT COUNT(*) FROM sa_expenses")
            total_expenses = cursor.fetchone()[0]
            
            quality['metrics'] = {
                'total_expenses': total_expenses,
                'unmatched_expenses': unmatched_expenses,
                'match_rate': ((total_expenses - unmatched_expenses) / total_expenses * 100) if total_expenses > 0 else 0,
                'data_completeness': self._calculate_data_completeness(cursor)
            }
            
            return quality
            
        except Exception as e:
            self.logger.error(f"Data quality analysis failed: {e}")
            return {}
    
    def _calculate_data_completeness(self, cursor) -> Dict[str, float]:
        """Calculate data completeness percentages."""
        try:
            completeness = {}
            
            # Get total expense count
            cursor.execute("SELECT COUNT(*) FROM sa_expenses")
            total = cursor.fetchone()[0]
            
            if total == 0:
                return completeness
            
            # Check various fields
            fields_to_check = [
                ('merchant_text', 'merchant_names'),
                ('category_code', 'categories'),
                ('payment_method', 'payment_methods'),
                ('notes', 'descriptions')
            ]
            
            for field, name in fields_to_check:
                cursor.execute(f"SELECT COUNT(*) FROM sa_expenses WHERE {field} IS NOT NULL AND {field} != ''")
                complete = cursor.fetchone()[0]
                completeness[name] = (complete / total * 100)
            
            return completeness
            
        except Exception as e:
            self.logger.error(f"Completeness calculation failed: {e}")
            return {}
    
    def _analyze_storage(self, cursor) -> Dict[str, Any]:
        """Analyze storage usage and optimization opportunities."""
        try:
            storage = {}
            
            # Check for unused space
            cursor.execute("PRAGMA freelist_count")
            freelist_count = cursor.fetchone()[0]
            
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            
            storage['unused_pages'] = freelist_count
            storage['unused_bytes'] = freelist_count * page_size
            storage['unused_mb'] = storage['unused_bytes'] / (1024 * 1024)
            
            # Check for large text fields
            cursor.execute("""
                SELECT 'sa_expenses' as table_name, 'notes' as column_name, 
                       AVG(LENGTH(notes)) as avg_length, MAX(LENGTH(notes)) as max_length
                FROM sa_expenses WHERE notes IS NOT NULL
                UNION ALL
                SELECT 'sa_transactions', 'description',
                       AVG(LENGTH(description)), MAX(LENGTH(description))
                FROM sa_transactions WHERE description IS NOT NULL
            """)
            text_analysis = cursor.fetchall()
            storage['text_field_analysis'] = [
                {
                    'table': row[0],
                    'column': row[1], 
                    'avg_length': row[2],
                    'max_length': row[3]
                }
                for row in text_analysis
            ]
            
            return storage
            
        except Exception as e:
            self.logger.error(f"Storage analysis failed: {e}")
            return {}
    
    def _get_performance_metrics(self, cursor) -> Dict[str, Any]:
        """Get performance-related metrics."""
        try:
            metrics = {}
            
            # Check for missing indexes on commonly queried columns
            common_queries = [
                ('sa_expenses', 'user_id'),
                ('sa_expenses', 'date_local'),
                ('sa_expenses', 'merchant_id'),
                ('sa_transactions', 'statement_id'),
                ('sa_reconciliation_matches', 'expense_id'),
                ('sa_reconciliation_matches', 'transaction_id')
            ]
            
            missing_indexes = []
            for table, column in common_queries:
                cursor.execute(f"PRAGMA index_list({table})")
                indexes = cursor.fetchall()
                
                # Check if column is indexed
                indexed = False
                for index in indexes:
                    cursor.execute(f"PRAGMA index_info({index[1]})")
                    index_columns = [col[2] for col in cursor.fetchall()]
                    if column in index_columns:
                        indexed = True
                        break
                
                if not indexed:
                    missing_indexes.append({'table': table, 'column': column})
            
            metrics['missing_indexes'] = missing_indexes
            
            # Query plan analysis for common queries
            query_plans = []
            common_sql_queries = [
                "SELECT * FROM sa_expenses WHERE user_id = 'test'",
                "SELECT * FROM sa_expenses WHERE date_local BETWEEN '2024-01-01' AND '2024-12-31'",
                "SELECT * FROM sa_expenses e JOIN sa_merchants m ON e.merchant_id = m.id"
            ]
            
            for query in common_sql_queries:
                try:
                    cursor.execute(f"EXPLAIN QUERY PLAN {query}")
                    plan = cursor.fetchall()
                    query_plans.append({
                        'query': query,
                        'plan': [{'detail': row[3]} for row in plan]
                    })
                except sqlite3.OperationalError:
                    pass  # Query might fail due to missing data
            
            metrics['query_plans'] = query_plans
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Performance metrics failed: {e}")
            return {}
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate maintenance recommendations based on analysis."""
        recommendations = []
        
        try:
            # Storage recommendations
            storage = analysis.get('storage_analysis', {})
            if storage.get('unused_mb', 0) > 10:  # More than 10MB unused
                recommendations.append({
                    'type': 'storage',
                    'priority': 'medium',
                    'action': 'vacuum_database',
                    'description': f"Database has {storage['unused_mb']:.1f}MB of unused space",
                    'benefit': 'Reduces file size and improves performance'
                })
            
            # Data quality recommendations
            quality = analysis.get('data_quality', {})
            for issue in quality.get('issues', []):
                if issue['type'] == 'missing_category' and issue['count'] > 10:
                    recommendations.append({
                        'type': 'data_quality',
                        'priority': 'high',
                        'action': 'categorize_expenses',
                        'description': f"Many expenses ({issue['count']}) lack proper categorization",
                        'benefit': 'Improves tax deduction accuracy'
                    })
                
                if issue['type'] == 'potential_duplicates' and issue['count'] > 5:
                    recommendations.append({
                        'type': 'data_quality',
                        'priority': 'medium',
                        'action': 'review_duplicates',
                        'description': f"Found {issue['count']} potential duplicate groups",
                        'benefit': 'Prevents double-counting expenses'
                    })
            
            # Performance recommendations
            performance = analysis.get('performance_metrics', {})
            if performance.get('missing_indexes'):
                recommendations.append({
                    'type': 'performance',
                    'priority': 'low',
                    'action': 'create_indexes',
                    'description': f"Missing indexes on {len(performance['missing_indexes'])} commonly queried columns",
                    'benefit': 'Improves query performance'
                })
            
            # Match rate recommendation
            metrics = quality.get('metrics', {})
            if metrics.get('match_rate', 100) < 80:
                recommendations.append({
                    'type': 'reconciliation',
                    'priority': 'high',
                    'action': 'improve_reconciliation',
                    'description': f"Low reconciliation rate ({metrics['match_rate']:.1f}%)",
                    'benefit': 'Better expense tracking accuracy'
                })
            
        except Exception as e:
            self.logger.error(f"Recommendation generation failed: {e}")
        
        return recommendations
    
    def optimize_database(self, actions: List[str] = None) -> Dict[str, Any]:
        """Perform database optimization tasks.
        
        Args:
            actions: List of specific actions to perform (default: all safe actions)
            
        Returns:
            Dict with optimization results
        """
        try:
            if not actions:
                actions = ['vacuum', 'analyze', 'reindex']
            
            results = {
                'actions_performed': [],
                'before_size': os.path.getsize(self.db_path),
                'errors': []
            }
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # VACUUM - reclaim unused space
            if 'vacuum' in actions:
                try:
                    self.logger.info("Performing VACUUM...")
                    cursor.execute("VACUUM")
                    results['actions_performed'].append('vacuum')
                    self.logger.info("VACUUM completed")
                except Exception as e:
                    results['errors'].append(f"VACUUM failed: {e}")
            
            # ANALYZE - update statistics
            if 'analyze' in actions:
                try:
                    self.logger.info("Performing ANALYZE...")
                    cursor.execute("ANALYZE")
                    results['actions_performed'].append('analyze')
                    self.logger.info("ANALYZE completed")
                except Exception as e:
                    results['errors'].append(f"ANALYZE failed: {e}")
            
            # REINDEX - rebuild indexes
            if 'reindex' in actions:
                try:
                    self.logger.info("Performing REINDEX...")
                    cursor.execute("REINDEX")
                    results['actions_performed'].append('reindex')
                    self.logger.info("REINDEX completed")
                except Exception as e:
                    results['errors'].append(f"REINDEX failed: {e}")
            
            # Create missing indexes
            if 'create_indexes' in actions:
                try:
                    self._create_recommended_indexes(cursor)
                    results['actions_performed'].append('create_indexes')
                except Exception as e:
                    results['errors'].append(f"Index creation failed: {e}")
            
            conn.close()
            
            # Calculate results
            results['after_size'] = os.path.getsize(self.db_path)
            results['size_reduction'] = results['before_size'] - results['after_size']
            results['size_reduction_mb'] = results['size_reduction'] / (1024 * 1024)
            results['success'] = len(results['errors']) == 0
            
            return results
            
        except Exception as e:
            self.logger.error(f"Database optimization failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'actions_performed': [],
                'errors': [str(e)]
            }
    
    def _create_recommended_indexes(self, cursor):
        """Create recommended indexes for performance."""
        indexes_to_create = [
            "CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON sa_expenses (user_id, date_local)",
            "CREATE INDEX IF NOT EXISTS idx_expenses_merchant ON sa_expenses (merchant_id)",
            "CREATE INDEX IF NOT EXISTS idx_expenses_category ON sa_expenses (category_code)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_statement ON sa_transactions (statement_id)",
            "CREATE INDEX IF NOT EXISTS idx_transactions_date ON sa_transactions (booking_date)",
            "CREATE INDEX IF NOT EXISTS idx_reconciliation_expense ON sa_reconciliation_matches (expense_id)",
            "CREATE INDEX IF NOT EXISTS idx_reconciliation_transaction ON sa_reconciliation_matches (transaction_id)",
            "CREATE INDEX IF NOT EXISTS idx_statements_user ON sa_statements (user_id)"
        ]
        
        for index_sql in indexes_to_create:
            try:
                cursor.execute(index_sql)
                self.logger.info(f"Created index: {index_sql.split('ON')[0].split()[-1]}")
            except sqlite3.OperationalError as e:
                if "already exists" not in str(e):
                    self.logger.warning(f"Failed to create index: {e}")
    
    def clean_old_data(self, days_old: int = 365, dry_run: bool = True) -> Dict[str, Any]:
        """Clean old data from the database.
        
        Args:
            days_old: Remove data older than this many days
            dry_run: If True, only report what would be deleted
            
        Returns:
            Dict with cleanup results
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_old)).date()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cleanup_results = {
                'cutoff_date': cutoff_date.isoformat(),
                'dry_run': dry_run,
                'items_to_clean': {}
            }
            
            # Find old expenses
            cursor.execute("SELECT COUNT(*) FROM sa_expenses WHERE date_local < ?", (cutoff_date,))
            old_expenses = cursor.fetchone()[0]
            cleanup_results['items_to_clean']['old_expenses'] = old_expenses
            
            # Find old statements
            cursor.execute("SELECT COUNT(*) FROM sa_statements WHERE processed_at < ?", 
                          (datetime.combine(cutoff_date, datetime.min.time()),))
            old_statements = cursor.fetchone()[0]
            cleanup_results['items_to_clean']['old_statements'] = old_statements
            
            # Find orphaned reconciliation matches
            cursor.execute("""
                SELECT COUNT(*) FROM sa_reconciliation_matches rm
                LEFT JOIN sa_expenses e ON rm.expense_id = e.id
                WHERE e.id IS NULL
            """)
            orphaned_matches = cursor.fetchone()[0]
            cleanup_results['items_to_clean']['orphaned_matches'] = orphaned_matches
            
            if not dry_run:
                # Actually perform cleanup
                deleted_counts = {}
                
                # Delete old expenses (and related data will cascade)
                if old_expenses > 0:
                    cursor.execute("DELETE FROM sa_expenses WHERE date_local < ?", (cutoff_date,))
                    deleted_counts['expenses'] = cursor.rowcount
                
                # Delete old statements
                if old_statements > 0:
                    cursor.execute("DELETE FROM sa_statements WHERE processed_at < ?", 
                                  (datetime.combine(cutoff_date, datetime.min.time()),))
                    deleted_counts['statements'] = cursor.rowcount
                
                # Clean orphaned matches
                if orphaned_matches > 0:
                    cursor.execute("""
                        DELETE FROM sa_reconciliation_matches 
                        WHERE expense_id NOT IN (SELECT id FROM sa_expenses)
                    """)
                    deleted_counts['orphaned_matches'] = cursor.rowcount
                
                conn.commit()
                cleanup_results['deleted_counts'] = deleted_counts
            
            conn.close()
            
            cleanup_results['success'] = True
            return cleanup_results
            
        except Exception as e:
            self.logger.error(f"Data cleanup failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def validate_data_integrity(self) -> Dict[str, Any]:
        """Validate data integrity and referential consistency.
        
        Returns:
            Dict with validation results
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            validation_results = {
                'checks_performed': [],
                'issues_found': [],
                'summary': {}
            }
            
            # Check foreign key constraints
            cursor.execute("PRAGMA foreign_key_check")
            fk_violations = cursor.fetchall()
            if fk_violations:
                validation_results['issues_found'].append({
                    'type': 'foreign_key_violation',
                    'count': len(fk_violations),
                    'details': fk_violations[:10]  # Limit to first 10
                })
            validation_results['checks_performed'].append('foreign_key_constraints')
            
            # Check for expenses with invalid merchant_id
            cursor.execute("""
                SELECT COUNT(*) FROM sa_expenses 
                WHERE merchant_id IS NOT NULL 
                AND merchant_id NOT IN (SELECT id FROM sa_merchants)
            """)
            invalid_merchants = cursor.fetchone()[0]
            if invalid_merchants > 0:
                validation_results['issues_found'].append({
                    'type': 'invalid_merchant_references',
                    'count': invalid_merchants
                })
            validation_results['checks_performed'].append('merchant_references')
            
            # Check for reconciliation matches with missing expenses or transactions
            cursor.execute("""
                SELECT COUNT(*) FROM sa_reconciliation_matches rm
                LEFT JOIN sa_expenses e ON rm.expense_id = e.id
                WHERE e.id IS NULL
            """)
            missing_expenses = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM sa_reconciliation_matches rm
                LEFT JOIN sa_transactions t ON rm.transaction_id = t.id
                WHERE t.id IS NULL
            """)
            missing_transactions = cursor.fetchone()[0]
            
            if missing_expenses > 0 or missing_transactions > 0:
                validation_results['issues_found'].append({
                    'type': 'broken_reconciliation_references',
                    'missing_expenses': missing_expenses,
                    'missing_transactions': missing_transactions
                })
            validation_results['checks_performed'].append('reconciliation_references')
            
            # Check for duplicate expenses
            cursor.execute("""
                SELECT amount_cents, date_local, merchant_text, COUNT(*) as cnt
                FROM sa_expenses 
                GROUP BY amount_cents, date_local, merchant_text 
                HAVING cnt > 1
                LIMIT 10
            """)
            duplicates = cursor.fetchall()
            if duplicates:
                validation_results['issues_found'].append({
                    'type': 'potential_duplicates',
                    'count': len(duplicates),
                    'examples': [
                        {
                            'amount': row[0] / 100,
                            'date': row[1],
                            'merchant': row[2],
                            'count': row[3]
                        }
                        for row in duplicates
                    ]
                })
            validation_results['checks_performed'].append('duplicate_detection')
            
            # Summary
            validation_results['summary'] = {
                'total_checks': len(validation_results['checks_performed']),
                'issues_found': len(validation_results['issues_found']),
                'integrity_score': max(0, 100 - len(validation_results['issues_found']) * 10)
            }
            
            conn.close()
            
            validation_results['success'] = True
            return validation_results
            
        except Exception as e:
            self.logger.error(f"Data validation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

def main():
    """Main maintenance utility function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Swiss Accountant Maintenance Utility')
    parser.add_argument('--database', '-d', required=True, help='Database file path')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze database')
    
    # Optimize command
    optimize_parser = subparsers.add_parser('optimize', help='Optimize database')
    optimize_parser.add_argument('--actions', nargs='*', 
                               choices=['vacuum', 'analyze', 'reindex', 'create_indexes'],
                               help='Specific optimization actions')
    
    # Clean command
    clean_parser = subparsers.add_parser('clean', help='Clean old data')
    clean_parser.add_argument('--days', '-n', type=int, default=365, 
                            help='Remove data older than N days')
    clean_parser.add_argument('--execute', action='store_true', 
                            help='Actually perform cleanup (default is dry run)')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate data integrity')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize maintenance manager
    maintenance = MaintenanceManager(args.database)
    
    # Execute command
    if args.command == 'analyze':
        result = maintenance.analyze_database()
        
        if result['success']:
            analysis = result['analysis']
            
            print("📊 Database Analysis Report")
            print("=" * 50)
            
            # Database info
            db_info = analysis['database_info']
            print(f"\n💾 Database Information:")
            print(f"   Size: {db_info.get('size_mb', 0):.1f} MB")
            print(f"   SQLite version: {db_info.get('sqlite_version', 'Unknown')}")
            print(f"   Journal mode: {db_info.get('journal_mode', 'Unknown')}")
            
            # Table statistics
            table_stats = analysis['table_statistics']
            print(f"\n📋 Table Statistics:")
            for table, stats in table_stats.items():
                print(f"   {table}: {stats['row_count']:,} rows")
            
            # Data quality
            quality = analysis['data_quality']
            print(f"\n🔍 Data Quality:")
            if quality.get('issues'):
                for issue in quality['issues']:
                    print(f"   ⚠️  {issue['description']}")
            else:
                print(f"   ✅ No data quality issues found")
            
            # Recommendations
            recommendations = analysis.get('recommendations', [])
            if recommendations:
                print(f"\n💡 Recommendations:")
                for rec in recommendations:
                    priority_emoji = "🔴" if rec['priority'] == 'high' else "🟡" if rec['priority'] == 'medium' else "🟢"
                    print(f"   {priority_emoji} {rec['description']}")
                    print(f"      Action: {rec['action']}")
                    print(f"      Benefit: {rec['benefit']}")
            else:
                print(f"\n✅ No maintenance recommendations")
        
        else:
            print(f"❌ Analysis failed: {result['error']}")
    
    elif args.command == 'optimize':
        result = maintenance.optimize_database(args.actions)
        
        if result['success']:
            print("🔧 Database Optimization Complete")
            print("=" * 40)
            print(f"Actions performed: {', '.join(result['actions_performed'])}")
            print(f"Size before: {result['before_size'] / (1024*1024):.1f} MB")
            print(f"Size after: {result['after_size'] / (1024*1024):.1f} MB")
            if result['size_reduction'] > 0:
                print(f"Space reclaimed: {result['size_reduction_mb']:.1f} MB")
            
            if result['errors']:
                print(f"\n⚠️  Errors:")
                for error in result['errors']:
                    print(f"   {error}")
        else:
            print(f"❌ Optimization failed: {result['error']}")
    
    elif args.command == 'clean':
        result = maintenance.clean_old_data(
            days_old=args.days, 
            dry_run=not args.execute
        )
        
        if result['success']:
            mode = "DRY RUN" if result['dry_run'] else "EXECUTED"
            print(f"🧹 Data Cleanup {mode}")
            print("=" * 30)
            print(f"Cutoff date: {result['cutoff_date']}")
            
            items = result['items_to_clean']
            print(f"\nItems to clean:")
            for item_type, count in items.items():
                print(f"   {item_type}: {count:,}")
            
            if not result['dry_run'] and 'deleted_counts' in result:
                print(f"\nActually deleted:")
                for item_type, count in result['deleted_counts'].items():
                    print(f"   {item_type}: {count:,}")
            
            if result['dry_run']:
                print(f"\n💡 Use --execute to actually perform cleanup")
        
        else:
            print(f"❌ Cleanup failed: {result['error']}")
    
    elif args.command == 'validate':
        result = maintenance.validate_data_integrity()
        
        if result['success']:
            print("✅ Data Integrity Validation")
            print("=" * 35)
            
            summary = result['summary']
            print(f"Checks performed: {summary['total_checks']}")
            print(f"Issues found: {summary['issues_found']}")
            print(f"Integrity score: {summary['integrity_score']}%")
            
            if result['issues_found']:
                print(f"\n⚠️  Issues Found:")
                for issue in result['issues_found']:
                    print(f"   {issue['type']}: {issue.get('count', 'Multiple')}")
                    if 'examples' in issue:
                        for example in issue['examples'][:3]:
                            print(f"      Example: {example}")
            else:
                print(f"\n✅ No integrity issues found")
        
        else:
            print(f"❌ Validation failed: {result['error']}")

if __name__ == "__main__":
    main()
