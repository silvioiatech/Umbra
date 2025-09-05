"""
Formatters for Business module Telegram responses.
Provides compact, user-friendly formatting for instance data.
"""
from typing import Dict, List, Any


def format_instance_summary(instance: Dict[str, Any]) -> str:
    """Format a single instance summary for Telegram."""
    return f"""**🖥️ {instance.get('display_name', 'Unknown')}**
• Client: `{instance.get('client_id', 'unknown')}`
• URL: {instance.get('url', 'N/A')}
• Port: {instance.get('port', 'N/A')}
• Status: {_format_status(instance.get('status', 'unknown'))}"""


def format_instance_details(instance: Dict[str, Any]) -> str:
    """Format detailed instance information for Telegram."""
    return f"""**🖥️ {instance.get('display_name', 'Unknown')} (Detailed)**

**Basic Info:**
• Client: `{instance.get('client_id', 'unknown')}`
• URL: {instance.get('url', 'N/A')}
• Port: {instance.get('port', 'N/A')}
• Status: {_format_status(instance.get('status', 'unknown'))}

**Storage & Config:**
• Data Directory: `{instance.get('data_dir', 'N/A')}`
• Port Reserved: {'Yes' if instance.get('reserved') else 'No'}"""


def format_instances_list(instances: List[Dict[str, Any]]) -> str:
    """Format multiple instances for Telegram list."""
    if not instances:
        return "**📋 No instances found**\n\nUse `/inst create <client>` to create your first instance."
    
    lines = ["**📋 Client Instances**\n"]
    
    for instance in instances:
        lines.append(f"• **{instance.get('display_name', 'Unknown')}**")
        lines.append(f"  `{instance.get('client_id', 'unknown')}` → {instance.get('url', 'N/A')}")
        lines.append(f"  Port {instance.get('port', 'N/A')}, {_format_status(instance.get('status', 'unknown'))}")
        lines.append("")  # Empty line between instances
    
    return "\n".join(lines)


def format_creation_result(result: Dict[str, Any]) -> str:
    """Format instance creation result for Telegram."""
    if not result.get('ok'):
        return f"❌ **Creation Failed**\n\n{result.get('error', 'Unknown error')}"
    
    audit_id = result.get('audit_id', '')
    audit_info = f"\n*Audit ID: {audit_id}*" if audit_id else ""
    
    return f"""✅ **Instance Created Successfully**

**{result.get('display_name', 'Unknown')}**
• Client: `{result.get('client_id', 'unknown')}`
• URL: {result.get('url', 'N/A')}
• Port: {result.get('port', 'N/A')}
• Status: {_format_status(result.get('status', 'unknown'))}

{result.get('message', 'Instance is ready to use.')}{audit_info}"""


def format_deletion_result(result: Dict[str, Any]) -> str:
    """Format instance deletion result for Telegram."""
    if not result.get('ok'):
        return f"❌ **Deletion Failed**\n\n{result.get('error', 'Unknown error')}"
    
    mode = result.get('mode', 'unknown')
    audit_id = result.get('audit_id', '')
    audit_info = f"\n*Audit ID: {audit_id}*" if audit_id else ""
    
    mode_emoji = "🗂️" if mode == "keep" else "🗑️"
    mode_text = "Data Preserved" if mode == "keep" else "Complete Removal"
    
    return f"""{mode_emoji} **Instance Deleted - {mode_text}**

{result.get('message', 'Operation completed.')}{audit_info}"""


def format_error(error_message: str) -> str:
    """Format error message for Telegram."""
    return f"❌ **Error**\n\n{error_message}"


def format_help() -> str:
    """Format help text for /inst commands."""
    return """**🏢 Instance Management Commands**

**Create Instance:**
• `create instance <client>` - Auto-assign port
• `create instance <client> name "Display Name"` - Custom name
• `create instance <client> port <20012>` - Specific port

**List & View:**
• `list instances` - Show all instances
• `show instance <client>` - Detailed view

**Delete Instance (Admin Only):**
• `delete instance <client> keep` - Archive, preserve data
• `delete instance <client> wipe` - Permanent removal

**Examples:**
• `create instance acme-corp`
• `create instance startup-x name "Startup X n8n"`
• `create instance test-env port 20050`
• `show instance acme-corp`
• `delete instance test-env wipe`

**Notes:**
• Client names: lowercase, numbers, hyphens only
• Port range: 20000-21000
• Deletion requires admin privileges"""


def _format_status(status: str) -> str:
    """Format status with emoji."""
    status_map = {
        'active': '🟢 Active',
        'archived': '🟡 Archived',
        'inactive': '🔴 Inactive',
        'unknown': '⚪ Unknown'
    }
    return status_map.get(status.lower(), f'❓ {status.title()}')