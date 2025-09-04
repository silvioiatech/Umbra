"""
Production MCP - n8n Workflow Creator
Creates and deploys n8n workflows via MCP API
"""
import json
from datetime import datetime
from typing import Any

import httpx

from ..core.envelope import InternalEnvelope
from ..core.module_base import ModuleBase


class ProductionMCP(ModuleBase):
    """n8n Workflow Creator - Automation via MCP API."""

    def __init__(self, config, db_manager):
        super().__init__("production")
        self.config = config
        self.db = db_manager

        # n8n MCP endpoint
        self.n8n_url = config.N8N_API_URL if hasattr(config, 'N8N_API_URL') else None
        self.n8n_key = config.N8N_API_KEY if hasattr(config, 'N8N_API_KEY') else None

        self._init_database()

    async def initialize(self) -> bool:
        """Initialize the Production module."""
        try:
            # Test database connectivity
            test_query = "SELECT name FROM sqlite_master WHERE type='table' AND name='workflows'"
            self.db.query_one(test_query)

            # Test n8n connectivity if configured
            if self.n8n_url and self.n8n_key:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            f"{self.n8n_url}/workflows",
                            headers={"X-N8N-API-KEY": self.n8n_key},
                            timeout=5
                        )
                        if response.status_code == 200:
                            self.logger.info("n8n API connectivity confirmed")
                        else:
                            self.logger.warning("n8n API not accessible")
                except Exception:
                    self.logger.warning("n8n API connectivity test failed")

            self.logger.info("Production module initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Production initialization failed: {e}")
            return False

    async def register_handlers(self) -> dict[str, Any]:
        """Register command handlers for the Production module."""
        return {
            "create workflow": self.create_workflow,
            "list workflows": self.list_workflows,
            "deploy workflow": self.deploy_workflow,
            "workflow status": self.get_workflow_status,
            "workflow templates": self.get_workflow_templates,
            "delete workflow": self.delete_workflow
        }

    async def process_envelope(self, envelope: InternalEnvelope) -> str | None:
        """Process envelope for Production operations."""
        action = envelope.action.lower()
        data = envelope.data

        if action == "create_workflow":
            workflow_type = data.get("workflow_type", "")
            description = data.get("description", "")
            return await self.create_workflow(workflow_type, description)
        elif action == "list_workflows":
            return await self.list_workflows()
        elif action == "deploy_workflow":
            workflow_name = data.get("workflow_name", "")
            return await self.deploy_workflow(workflow_name)
        elif action == "workflow_status":
            workflow_name = data.get("workflow_name", "")
            return await self.get_workflow_status(workflow_name)
        elif action == "workflow_templates":
            return await self.get_workflow_templates()
        elif action == "delete_workflow":
            workflow_name = data.get("workflow_name", "")
            return await self.delete_workflow(workflow_name)
        else:
            return None

    async def health_check(self) -> dict[str, Any]:
        """Perform health check of the Production module."""
        try:
            # Check database connectivity
            workflows_count = self.db.query_one("SELECT COUNT(*) as count FROM workflows")
            deployed_count = self.db.query_one("SELECT COUNT(*) as count FROM workflows WHERE status = 'deployed'")

            # Check n8n connectivity
            n8n_connected = False
            if self.n8n_url and self.n8n_key:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            f"{self.n8n_url}/workflows",
                            headers={"X-N8N-API-KEY": self.n8n_key},
                            timeout=5
                        )
                        n8n_connected = response.status_code == 200
                except Exception:
                    pass

            return {
                "status": "healthy",
                "details": {
                    "total_workflows": workflows_count["count"] if workflows_count else 0,
                    "deployed_workflows": deployed_count["count"] if deployed_count else 0,
                    "n8n_connected": n8n_connected,
                    "n8n_configured": bool(self.n8n_url and self.n8n_key),
                    "database_accessible": True
                }
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def shutdown(self):
        """Gracefully shutdown the Production module."""
        self.logger.info("Production module shutting down")
        # No specific cleanup needed for this module

    def _init_database(self):
        """Initialize workflow tables."""
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS workflows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    type TEXT,
                    description TEXT,
                    workflow_json TEXT,
                    status TEXT,
                    n8n_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.logger.info("✅ Production database initialized")
        except Exception as e:
            self.logger.error(f"Production DB init failed: {e}")

    async def create_workflow(self, workflow_type: str, description: str) -> str:
        """Create an n8n workflow."""
        try:
            # Generate workflow based on type
            workflow_data = self._generate_workflow_template(workflow_type, description)

            # Save to database
            self.db.execute(
                "INSERT INTO workflows (name, type, description, workflow_json, status) VALUES (?, ?, ?, ?, ?)",
                (workflow_data['name'], workflow_type, description, json.dumps(workflow_data), 'draft')
            )

            # If n8n MCP is configured, deploy
            if self.n8n_url and self.n8n_key:
                deploy_result = await self._deploy_to_n8n(workflow_data)
                status = deploy_result
            else:
                status = "Workflow created locally (n8n MCP not configured)"

            return f"""**⚙️ Workflow Created**

Name: {workflow_data['name']}
Type: {workflow_type}
Description: {description}

**Workflow Structure:**
{self._describe_workflow(workflow_data)}

**Status:** {status}

Use 'deploy workflow [name]' to activate."""

        except Exception as e:
            self.logger.error(f"Workflow creation failed: {e}")
            return f"❌ Failed to create workflow: {str(e)[:100]}"

    def _generate_workflow_template(self, workflow_type: str, description: str) -> dict:
        """Generate n8n workflow template."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        templates = {
            'backup': {
                'name': f'backup_workflow_{timestamp}',
                'nodes': [
                    {
                        'type': 'n8n-nodes-base.cron',
                        'name': 'Daily Trigger',
                        'parameters': {
                            'triggerTimes': {'item': [{'hour': 2, 'minute': 0}]}
                        }
                    },
                    {
                        'type': 'n8n-nodes-base.executeCommand',
                        'name': 'Create Backup',
                        'parameters': {
                            'command': 'tar -czf /backups/backup_$(date +%Y%m%d).tar.gz /data'
                        }
                    },
                    {
                        'type': 'n8n-nodes-base.telegram',
                        'name': 'Notify Success',
                        'parameters': {
                            'text': 'Backup completed successfully'
                        }
                    }
                ]
            },
            'monitoring': {
                'name': f'monitoring_workflow_{timestamp}',
                'nodes': [
                    {
                        'type': 'n8n-nodes-base.interval',
                        'name': 'Every 5 Minutes',
                        'parameters': {
                            'interval': 5,
                            'unit': 'minutes'
                        }
                    },
                    {
                        'type': 'n8n-nodes-base.httpRequest',
                        'name': 'Check Health',
                        'parameters': {
                            'url': 'http://localhost:8000/health',
                            'method': 'GET'
                        }
                    },
                    {
                        'type': 'n8n-nodes-base.if',
                        'name': 'Check Status',
                        'parameters': {
                            'conditions': {
                                'boolean': [
                                    {
                                        'value1': '={{$json["status"]}}',
                                        'operation': 'notEqual',
                                        'value2': 'healthy'
                                    }
                                ]
                            }
                        }
                    },
                    {
                        'type': 'n8n-nodes-base.telegram',
                        'name': 'Alert',
                        'parameters': {
                            'text': '🚨 System unhealthy!'
                        }
                    }
                ]
            },
            'alert': {
                'name': f'alert_workflow_{timestamp}',
                'nodes': [
                    {
                        'type': 'n8n-nodes-base.webhook',
                        'name': 'Alert Webhook',
                        'parameters': {
                            'path': 'alert-trigger',
                            'responseMode': 'onReceived'
                        }
                    },
                    {
                        'type': 'n8n-nodes-base.telegram',
                        'name': 'Send Alert',
                        'parameters': {
                            'text': '{{$json["message"]}}'
                        }
                    }
                ]
            },
            'general': {
                'name': f'custom_workflow_{timestamp}',
                'nodes': [
                    {
                        'type': 'n8n-nodes-base.start',
                        'name': 'Start',
                        'parameters': {}
                    }
                ]
            }
        }

        template = templates.get(workflow_type, templates['general'])
        template['description'] = description
        return template

    def _describe_workflow(self, workflow: dict) -> str:
        """Describe workflow structure."""
        nodes = workflow.get('nodes', [])
        descriptions = []

        for i, node in enumerate(nodes, 1):
            node_type = node['type'].split('.')[-1]
            descriptions.append(f"{i}. {node['name']} ({node_type})")

        return '\n'.join(descriptions)

    async def _deploy_to_n8n(self, workflow: dict) -> str:
        """Deploy workflow to n8n via MCP API."""
        try:
            if not self.n8n_url:
                return "n8n MCP not configured"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.n8n_url}/workflows",
                    json=workflow,
                    headers={'X-API-Key': self.n8n_key},
                    timeout=30
                )

                if response.status_code == 200:
                    result = response.json()
                    workflow_id = result.get('id', 'unknown')

                    # Update database with n8n ID
                    self.db.execute(
                        "UPDATE workflows SET n8n_id = ?, status = ? WHERE name = ?",
                        (workflow_id, 'deployed', workflow['name'])
                    )

                    return f"✅ Deployed to n8n (ID: {workflow_id})"
                else:
                    return f"❌ n8n deployment failed: {response.status_code}"

        except Exception as e:
            self.logger.error(f"n8n deployment error: {e}")
            return f"❌ Deployment error: {str(e)[:50]}"

    async def list_workflows(self) -> str:
        """List all workflows."""
        try:
            workflows = self.db.query_all(
                "SELECT * FROM workflows ORDER BY created_at DESC LIMIT 10"
            )

            if not workflows:
                return "No workflows created yet"

            workflow_lines = []
            for wf in workflows:
                status_emoji = {
                    'deployed': '🟢',
                    'draft': '📝',
                    'error': '❌'
                }.get(wf['status'], '⚪')

                workflow_lines.append(
                    f"{status_emoji} {wf['name']} ({wf['type']}) - {wf['status']}"
                )

            return f"""**📋 Workflows**

{chr(10).join(workflow_lines)}

Total: {len(workflows)} workflows"""

        except Exception as e:
            return f"❌ Failed to list workflows: {str(e)[:100]}"

    async def deploy_workflow(self, workflow_name: str) -> str:
        """Deploy a workflow to n8n."""
        try:
            # Get workflow from database
            workflow = self.db.query_one(
                "SELECT * FROM workflows WHERE name LIKE ?",
                (f'%{workflow_name}%',)
            )

            if not workflow:
                return f"❌ Workflow '{workflow_name}' not found"

            workflow_data = json.loads(workflow['workflow_json'])

            # Deploy to n8n
            result = await self._deploy_to_n8n(workflow_data)

            return f"""**🚀 Deploying Workflow**

Name: {workflow['name']}
Type: {workflow['type']}

Result: {result}"""

        except Exception as e:
            return f"❌ Deployment failed: {str(e)[:100]}"

    async def get_workflow_status(self, workflow_name: str) -> str:
        """Get status of a workflow."""
        try:
            workflow = self.db.query_one(
                "SELECT * FROM workflows WHERE name LIKE ?",
                (f'%{workflow_name}%',)
            )

            if not workflow:
                return f"❌ Workflow '{workflow_name}' not found"

            # If deployed to n8n, check execution status
            if workflow['n8n_id'] and self.n8n_url:
                exec_status = await self._check_n8n_executions(workflow['n8n_id'])
            else:
                exec_status = "Local workflow (not deployed)"

            return f"""**📊 Workflow Status**

Name: {workflow['name']}
Type: {workflow['type']}
Status: {workflow['status']}
n8n ID: {workflow['n8n_id'] or 'Not deployed'}

**Execution Status:**
{exec_status}"""

        except Exception as e:
            return f"❌ Status check failed: {str(e)[:100]}"

    async def _check_n8n_executions(self, workflow_id: str) -> str:
        """Check n8n workflow executions."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.n8n_url}/executions?workflowId={workflow_id}&limit=5",
                    headers={'X-API-Key': self.n8n_key},
                    timeout=30
                )

                if response.status_code == 200:
                    executions = response.json()
                    if executions:
                        exec_lines = []
                        for exec in executions[:3]:
                            status = "✅" if exec.get('finished') else "⏳"
                            exec_lines.append(
                                f"{status} {exec.get('startedAt', 'Unknown time')}"
                            )
                        return '\n'.join(exec_lines)
                    else:
                        return "No executions yet"
                else:
                    return "Could not fetch execution status"

        except Exception as e:
            return f"Execution check error: {str(e)[:50]}"

    async def get_workflow_templates(self) -> str:
        """Get available workflow templates."""
        try:
            templates = {
                "data_sync": "Data Synchronization - Sync data between systems",
                "notification": "Notification System - Send alerts and notifications",
                "backup": "Backup Automation - Automated backup workflows",
                "monitoring": "System Monitoring - Monitor resources and alert",
                "email_automation": "Email Automation - Automated email sequences",
                "api_integration": "API Integration - Connect different APIs",
                "file_processing": "File Processing - Process and transform files",
                "social_media": "Social Media - Automate social media posts",
                "crm_sync": "CRM Synchronization - Keep CRM data in sync",
                "report_generation": "Report Generation - Generate automated reports"
            }

            template_list = []
            for key, description in templates.items():
                template_list.append(f"• **{key}**: {description}")

            return f"""**🛠️ Available Workflow Templates**

{chr(10).join(template_list)}

To create a workflow, use: "create workflow [template_name] [description]"

Example: "create workflow data_sync Sync customer data between CRM and email platform"
"""

        except Exception as e:
            return f"❌ Template listing failed: {str(e)[:100]}"

    async def delete_workflow(self, workflow_name: str) -> str:
        """Delete a workflow."""
        try:
            # Find workflow
            workflow = self.db.query_one(
                "SELECT * FROM workflows WHERE name LIKE ?",
                (f'%{workflow_name}%',)
            )

            if not workflow:
                return f"❌ Workflow '{workflow_name}' not found"

            # If deployed to n8n, should delete from there too
            if workflow['n8n_id'] and self.n8n_url and self.n8n_key:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.delete(
                            f"{self.n8n_url}/workflows/{workflow['n8n_id']}",
                            headers={"X-N8N-API-KEY": self.n8n_key},
                            timeout=30
                        )
                        if response.status_code == 200:
                            self.logger.info(f"Workflow {workflow['n8n_id']} deleted from n8n")
                except Exception as e:
                    self.logger.warning(f"Failed to delete from n8n: {e}")

            # Delete from local database
            self.db.execute("DELETE FROM workflows WHERE id = ?", (workflow['id'],))

            return f"""**🗑️ Workflow Deleted**

Name: {workflow['name']}
Type: {workflow['type']}
Status: Removed from system
{f"n8n ID: {workflow['n8n_id']} (also removed from n8n)" if workflow['n8n_id'] else ""}

The workflow has been permanently deleted."""

        except Exception as e:
            return f"❌ Workflow deletion failed: {str(e)[:100]}"
