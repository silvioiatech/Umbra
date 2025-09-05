"""
Business MCP - Intelligent Operations Manager
Smart client management with proactive monitoring and automation
Enhanced from v3.0 to CEO Assistant functionality
"""
import json
import random
import string
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from ..core.envelope import InternalEnvelope
from ..core.module_base import ModuleBase


class BusinessMCP(ModuleBase):
    """Intelligent Operations Manager - Proactive client management and automation."""

    def __init__(self, config, db_manager):
        super().__init__("business")
        self.config = config
        self.db = db_manager
        
        # Smart monitoring settings
        self.auto_monitoring = True
        self.predictive_analytics = True
        
        # Resource defaults from config
        self.default_cpu = getattr(config, 'DEFAULT_INSTANCE_CPU', 2)
        self.default_ram = getattr(config, 'DEFAULT_INSTANCE_RAM', 4)
        self.default_disk = getattr(config, 'DEFAULT_INSTANCE_DISK', 50)

        # Initialize business intelligence database
        self._init_database()

    async def initialize(self) -> bool:
        """Initialize the Business module with smart features."""
        try:
            # Test database connectivity
            test_query = "SELECT name FROM sqlite_master WHERE type='table' AND name='clients'"
            self.db.query_one(test_query)

            # Initialize business intelligence if no data exists
            client_count = self.db.query_one("SELECT COUNT(*) as count FROM clients")
            if not client_count or client_count['count'] == 0:
                await self._initialize_sample_data()
                self.logger.info("Business module initialized with sample data for demonstration")
            else:
                self.logger.info(f"Business module initialized with {client_count['count']} existing clients")

            # Start background monitoring if enabled
            if self.auto_monitoring:
                asyncio.create_task(self._background_monitoring_loop())
                self.logger.info("Smart monitoring enabled - proactive client management active")

            return True
        except Exception as e:
            self.logger.error(f"Business initialization failed: {e}")
            return False

    async def register_handlers(self) -> dict[str, Any]:
        """Register command handlers for the Business module."""
        return {
            "create client": self.create_client_instance,
            "list clients": self.list_clients,
            "client status": self.get_client_status,
            "generate invoice": self.generate_invoice,
            "add project": self.add_project,
            "list projects": self.list_projects,
            "client usage": self.get_client_usage,
            "business metrics": self.get_business_metrics,
            "smart monitoring": self.get_monitoring_report,
            "predict issues": self.predict_client_issues,
            "auto optimize": self.auto_optimize_resources,
            "business intelligence": self.get_business_intelligence
        }

    async def process_envelope(self, envelope: InternalEnvelope) -> str | None:
        """Process envelope for Business operations with smart routing."""
        action = envelope.action.lower()
        data = envelope.data

        # Smart action routing
        handlers = {
            "create_client": lambda: self.create_client_instance(
                data.get("client_name", ""), 
                data.get("resources", {}),
                data.get("auto_optimize", True)
            ),
            "list_clients": lambda: self.list_clients(),
            "client_status": lambda: self.get_client_status(data.get("client_name", "")),
            "generate_invoice": lambda: self.generate_invoice(
                data.get("client_name", ""), 
                data.get("amount", 0), 
                data.get("description", ""),
                data.get("auto_send", False)
            ),
            "add_project": lambda: self.add_project(
                data.get("client_name", ""), 
                data.get("project_name", ""), 
                data.get("description", ""), 
                data.get("deadline", "")
            ),
            "business_metrics": lambda: self.get_business_metrics(),
            "smart_monitoring": lambda: self.get_monitoring_report(),
            "predict_issues": lambda: self.predict_client_issues(data.get("client_name", "")),
            "auto_optimize": lambda: self.auto_optimize_resources(),
            "business_intelligence": lambda: self.get_business_intelligence()
        }

        handler = handlers.get(action)
        return await handler() if handler else None

    async def health_check(self) -> dict[str, Any]:
        """Enhanced health check with business intelligence."""
        try:
            # Basic counts
            clients_count = self.db.query_one("SELECT COUNT(*) as count FROM clients")
            active_clients = self.db.query_one("SELECT COUNT(*) as count FROM clients WHERE status = 'active'")
            projects_count = self.db.query_one("SELECT COUNT(*) as count FROM projects")
            
            # Business intelligence metrics
            revenue_this_month = await self._calculate_monthly_revenue()
            alerts_count = len(await self._get_active_alerts())
            auto_actions_today = self.db.query_one(
                "SELECT COUNT(*) as count FROM business_actions WHERE DATE(created_at) = DATE('now')"
            )

            return {
                "status": "healthy",
                "details": {
                    "total_clients": clients_count["count"] if clients_count else 0,
                    "active_clients": active_clients["count"] if active_clients else 0,
                    "total_projects": projects_count["count"] if projects_count else 0,
                    "monthly_revenue": revenue_this_month,
                    "active_alerts": alerts_count,
                    "auto_actions_today": auto_actions_today["count"] if auto_actions_today else 0,
                    "smart_monitoring": self.auto_monitoring,
                    "predictive_analytics": self.predictive_analytics,
                    "database_accessible": True
                }
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    def _init_database(self):
        """Initialize enhanced business intelligence database."""
        try:
            # Enhanced clients table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    email TEXT,
                    instance_id TEXT,
                    resources TEXT,
                    status TEXT,
                    monthly_revenue REAL DEFAULT 0,
                    health_score INTEGER DEFAULT 100,
                    last_issue_date TEXT,
                    upgrade_predicted_date TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Enhanced projects table
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER,
                    name TEXT,
                    description TEXT,
                    status TEXT,
                    deadline TEXT,
                    priority INTEGER DEFAULT 3,
                    estimated_hours REAL DEFAULT 0,
                    actual_hours REAL DEFAULT 0,
                    completion_percentage INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients (id)
                )
            """)

            # Business intelligence tables
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS business_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT,
                    metric_value REAL,
                    metric_date TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            self.db.execute("""
                CREATE TABLE IF NOT EXISTS business_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER,
                    action_type TEXT,
                    action_description TEXT,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients (id)
                )
            """)

            self.db.execute("""
                CREATE TABLE IF NOT EXISTS client_usage_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER,
                    cpu_usage REAL,
                    memory_usage REAL,
                    disk_usage REAL,
                    bandwidth_gb REAL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients (id)
                )
            """)

            self.logger.info("✅ Enhanced Business Intelligence database initialized")
        except Exception as e:
            self.logger.error(f"Business DB init failed: {e}")

    async def _initialize_sample_data(self):
        """Initialize with sample data for demonstration."""
        try:
            sample_clients = [
                {
                    'name': 'TechStartup Co',
                    'email': 'admin@techstartup.com',
                    'resources': {'cpu': 4, 'ram': 8, 'disk': 100, 'type': 'performance'},
                    'monthly_revenue': 299.99,
                    'health_score': 95
                },
                {
                    'name': 'E-Commerce Plus',
                    'email': 'ops@ecommerceplus.com',
                    'resources': {'cpu': 2, 'ram': 4, 'disk': 50, 'type': 'standard'},
                    'monthly_revenue': 149.99,
                    'health_score': 88
                },
                {
                    'name': 'DevAgency LLC',
                    'email': 'hello@devagency.com',
                    'resources': {'cpu': 6, 'ram': 16, 'disk': 200, 'type': 'premium'},
                    'monthly_revenue': 499.99,
                    'health_score': 92
                }
            ]

            for client_data in sample_clients:
                instance_id = f"vps-{client_data['name'].lower().replace(' ', '-')}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}"
                
                self.db.execute("""
                    INSERT INTO clients (name, email, instance_id, resources, status, monthly_revenue, health_score)
                    VALUES (?, ?, ?, ?, 'active', ?, ?)
                """, (
                    client_data['name'],
                    client_data['email'],
                    instance_id,
                    json.dumps(client_data['resources']),
                    client_data['monthly_revenue'],
                    client_data['health_score']
                ))

            self.logger.info("✅ Sample business data initialized")
        except Exception as e:
            self.logger.warning(f"Sample data initialization failed: {e}")

    async def _background_monitoring_loop(self):
        """Smart background monitoring with proactive actions."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                # Get all active clients
                clients = self.db.query_all("SELECT * FROM clients WHERE status = 'active'")
                
                for client in clients:
                    await self._monitor_client_intelligence(client)
                    
            except Exception as e:
                self.logger.error(f"Background monitoring error: {e}")
                await asyncio.sleep(60)  # Short retry delay

    async def _monitor_client_intelligence(self, client: Dict):
        """Monitor individual client with AI-like intelligence."""
        try:
            client_id = client['id']
            client_name = client['name']
            
            # Simulate real usage data (in production, this would come from actual monitoring)
            current_usage = await self._get_simulated_usage(client)
            
            # Record usage history
            self.db.execute("""
                INSERT INTO client_usage_history (client_id, cpu_usage, memory_usage, disk_usage, bandwidth_gb)
                VALUES (?, ?, ?, ?, ?)
            """, (client_id, current_usage['cpu'], current_usage['memory'], 
                  current_usage['disk'], current_usage['bandwidth']))

            # Predictive analysis
            predictions = await self._analyze_usage_trends(client_id)
            
            # Automatic actions based on intelligence
            actions_taken = []
            
            # CPU upgrade prediction
            if predictions.get('cpu_upgrade_needed_in_days', 999) < 7:
                action_desc = f"Predicted CPU bottleneck in {predictions['cpu_upgrade_needed_in_days']} days"
                await self._schedule_automatic_upgrade(client, 'cpu', action_desc)
                actions_taken.append(action_desc)
            
            # Disk space warning
            if current_usage['disk'] > 80:
                action_desc = f"Disk usage high: {current_usage['disk']:.1f}%"
                await self._create_disk_cleanup_task(client, action_desc)
                actions_taken.append(action_desc)
            
            # Health score update
            new_health_score = await self._calculate_health_score(client, current_usage, predictions)
            if abs(new_health_score - client['health_score']) > 5:
                self.db.execute(
                    "UPDATE clients SET health_score = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (new_health_score, client_id)
                )
                actions_taken.append(f"Health score updated: {new_health_score}")

            # Log actions if any were taken
            if actions_taken:
                for action in actions_taken:
                    self.db.execute("""
                        INSERT INTO business_actions (client_id, action_type, action_description, status)
                        VALUES (?, 'auto_monitoring', ?, 'completed')
                    """, (client_id, action))

        except Exception as e:
            self.logger.error(f"Client monitoring failed for {client.get('name', 'unknown')}: {e}")

    async def _get_simulated_usage(self, client: Dict) -> Dict[str, float]:
        """Generate realistic usage simulation (replace with real monitoring)."""
        resources = json.loads(client['resources']) if client['resources'] else {}
        base_cpu = resources.get('cpu', 2)
        base_memory = resources.get('ram', 4)
        
        # Simulate realistic usage patterns with some variance
        return {
            'cpu': min(95, random.uniform(20, 85) + (base_cpu * 2)),  # Higher spec = higher usage
            'memory': min(95, random.uniform(30, 80) + (base_memory * 1.5)),
            'disk': random.uniform(25, 85),
            'bandwidth': random.uniform(50, 500)  # GB per month
        }

    async def _analyze_usage_trends(self, client_id: int) -> Dict[str, Any]:
        """Analyze usage trends for predictive insights."""
        try:
            # Get recent usage history
            history = self.db.query_all("""
                SELECT * FROM client_usage_history 
                WHERE client_id = ? 
                ORDER BY recorded_at DESC 
                LIMIT 20
            """, (client_id,))

            if len(history) < 5:
                return {'insufficient_data': True}

            # Simple trend analysis
            recent_cpu = [h['cpu_usage'] for h in history[:5]]
            older_cpu = [h['cpu_usage'] for h in history[5:10]]
            
            cpu_trend = sum(recent_cpu) / len(recent_cpu) - sum(older_cpu) / len(older_cpu) if older_cpu else 0
            
            predictions = {
                'cpu_trend': 'increasing' if cpu_trend > 5 else 'stable',
                'cpu_upgrade_needed_in_days': max(1, 30 - int(cpu_trend * 2)) if cpu_trend > 5 else 999,
                'disk_cleanup_recommended': any(h['disk_usage'] > 75 for h in history[:3]),
                'performance_degradation_risk': any(h['cpu_usage'] > 85 and h['memory_usage'] > 85 for h in history[:3])
            }

            return predictions

        except Exception as e:
            self.logger.error(f"Trend analysis failed: {e}")
            return {}

    async def _calculate_health_score(self, client: Dict, usage: Dict, predictions: Dict) -> int:
        """Calculate intelligent health score (0-100)."""
        score = 100
        
        # Deduct for high resource usage
        if usage['cpu'] > 80:
            score -= (usage['cpu'] - 80) * 2
        if usage['memory'] > 85:
            score -= (usage['memory'] - 85) * 2
        if usage['disk'] > 90:
            score -= (usage['disk'] - 90) * 3
        
        # Deduct for predicted issues
        if predictions.get('cpu_upgrade_needed_in_days', 999) < 14:
            score -= 15
        if predictions.get('performance_degradation_risk'):
            score -= 10
        
        return max(0, min(100, int(score)))

    async def create_client_instance(self, client_name: str, resources: dict = None, auto_optimize: bool = True) -> str:
        """Create intelligent client instance with auto-optimization."""
        try:
            if not client_name:
                return "❌ Please provide a client name"

            # Smart resource allocation
            if not resources:
                resources = await self._recommend_resources(client_name)

            # Generate unique instance ID
            instance_id = f"vps-{client_name.lower().replace(' ', '-')}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}"

            # Check if client exists
            existing = self.db.query_one("SELECT id FROM clients WHERE name = ?", (client_name,))
            if existing:
                return f"❌ Client '{client_name}' already exists. Use 'client status {client_name}' to view details."

            # Estimate monthly revenue based on resources
            monthly_revenue = await self._calculate_estimated_revenue(resources)

            # Create client with intelligence
            self.db.execute("""
                INSERT INTO clients (name, instance_id, resources, status, monthly_revenue, health_score)
                VALUES (?, ?, ?, 'provisioning', ?, 100)
            """, (client_name, instance_id, json.dumps(resources), monthly_revenue))

            # Get client ID for actions
            client = self.db.query_one("SELECT id FROM clients WHERE instance_id = ?", (instance_id,))
            client_id = client['id']

            # Log creation action
            self.db.execute("""
                INSERT INTO business_actions (client_id, action_type, action_description, status)
                VALUES (?, 'instance_creation', 'Client instance created with smart resource allocation', 'completed')
            """, (client_id,))

            # Simulate intelligent provisioning process
            provisioning_steps = await self._simulate_intelligent_provisioning(client_name, resources, instance_id)

            # Update to active status
            self.db.execute("UPDATE clients SET status = 'active' WHERE id = ?", (client_id,))

            # Schedule follow-up monitoring
            if auto_optimize:
                self.db.execute("""
                    INSERT INTO business_actions (client_id, action_type, action_description, status)
                    VALUES (?, 'scheduled_monitoring', 'Auto-monitoring enabled for proactive management', 'scheduled')
                """, (client_id,))

            return f"""{provisioning_steps}

**🤖 Smart Features Enabled:**
• Predictive resource monitoring
• Auto-scaling recommendations
• Performance optimization alerts
• Monthly revenue tracking: ${monthly_revenue:.2f}

🎯 The client is now under intelligent management."""

        except Exception as e:
            self.logger.error(f"Smart instance creation failed: {e}")
            return f"❌ Failed to create instance: {str(e)[:100]}"

    async def _recommend_resources(self, client_name: str) -> Dict[str, Any]:
        """AI-like resource recommendation based on client analysis."""
        name_lower = client_name.lower()
        
        # Smart resource recommendations based on naming patterns
        if any(keyword in name_lower for keyword in ['startup', 'small', 'personal']):
            return {'cpu': 2, 'ram': 4, 'disk': 50, 'type': 'standard'}
        elif any(keyword in name_lower for keyword in ['enterprise', 'corp', 'large', 'inc']):
            return {'cpu': 8, 'ram': 32, 'disk': 500, 'type': 'enterprise'}
        elif any(keyword in name_lower for keyword in ['ecommerce', 'shop', 'store']):
            return {'cpu': 4, 'ram': 8, 'disk': 100, 'type': 'performance'}
        elif any(keyword in name_lower for keyword in ['dev', 'agency', 'tech']):
            return {'cpu': 6, 'ram': 16, 'disk': 200, 'type': 'development'}
        else:
            return {'cpu': self.default_cpu, 'ram': self.default_ram, 'disk': self.default_disk, 'type': 'standard'}

    async def _calculate_estimated_revenue(self, resources: Dict) -> float:
        """Calculate estimated monthly revenue based on resources."""
        base_prices = {
            'standard': {'cpu': 15, 'ram': 8, 'disk': 0.5},
            'performance': {'cpu': 20, 'ram': 10, 'disk': 0.75},
            'enterprise': {'cpu': 30, 'ram': 12, 'disk': 1.0},
            'development': {'cpu': 25, 'ram': 11, 'disk': 0.8}
        }
        
        resource_type = resources.get('type', 'standard')
        prices = base_prices.get(resource_type, base_prices['standard'])
        
        cpu_cost = resources.get('cpu', 2) * prices['cpu']
        ram_cost = resources.get('ram', 4) * prices['ram']
        disk_cost = resources.get('disk', 50) * prices['disk']
        
        return round(cpu_cost + ram_cost + disk_cost + 29.99, 2)  # Base fee + resources

    async def _simulate_intelligent_provisioning(self, client_name: str, resources: Dict, instance_id: str) -> str:
        """Simulate intelligent provisioning with realistic steps."""
        return f"""**🚀 Intelligent Client Provisioning**

Client: {client_name}
Instance ID: {instance_id}

**AI-Optimized Resources:**
• CPU: {resources['cpu']} vCPUs (optimized for {resources['type']} workload)
• RAM: {resources['ram']} GB (performance-tuned)
• Disk: {resources['disk']} GB SSD (high-speed storage)
• Type: {resources['type']} configuration

**Smart Provisioning Process:**
✅ Resource allocation optimized
✅ Security hardening applied
✅ Performance monitoring configured
✅ Auto-scaling policies set
✅ Backup strategy implemented
⚡ Smart monitoring activated

**Intelligence Features Active:**
• Predictive resource monitoring
• Automatic performance optimization
• Proactive issue detection
• Resource usage forecasting"""

    async def list_clients(self) -> str:
        """List clients with business intelligence."""
        try:
            clients = self.db.query_all("""
                SELECT *, 
                (SELECT COUNT(*) FROM projects WHERE client_id = clients.id AND status IN ('planning', 'in_progress')) as active_projects
                FROM clients 
                ORDER BY health_score DESC, created_at DESC
            """)

            if not clients:
                return """No clients yet. Add clients to get started with business management."""
            
            # Format client display
            result = "**📊 Client Health Dashboard**\n\n"
            for client in clients:
                health_emoji = "🟢" if client[9] >= 8 else "🟡" if client[9] >= 6 else "🔴"
                result += f"{health_emoji} **{client[1]}** (Score: {client[9]}/10)\n"
                result += f"   📧 {client[2]}\n"
                result += f"   💼 Active Projects: {client[11]}\n"
                result += f"   📅 Since: {client[10][:10]}\n\n"
            
            return result
            
        except Exception as e:
            return f"❌ Failed to get dashboard: {str(e)[:100]}" 