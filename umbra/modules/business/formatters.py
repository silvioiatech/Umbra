"""
Instance Formatters for Business Module

Provides Telegram-optimized formatting for instance data,
including compact lists, detailed views, and operation results.
"""
from typing import Dict, List, Any
from datetime import datetime

class InstanceFormatter:
    """
    Formatter for instance data optimized for Telegram display.
    
    Provides consistent, compact formatting for various instance
    operations and data views.
    """
    
    def __init__(self):
        self.status_emojis = {
            'running': '🟢',
            'stopped': '🔴', 
            'archived': '📦',
            'deleted': '❌',
            'unknown': '❓'
        }
    
    def format_instances_list(self, instances: List[Dict[str, Any]]) -> str:
        """Format list of instances for Telegram."""
        if not instances:
            return "📋 **No instances found**\n\nUse `/inst create` to create your first instance."
        
        lines = [f"📋 **Client Instances** ({len(instances)} total)\n"]
        
        for instance in instances:
            status_emoji = self.status_emojis.get(instance.get('status', 'unknown'), '❓')
            client_id = instance.get('client_id', 'unknown')
            display_name = instance.get('display_name', client_id)
            url = instance.get('url', 'N/A')
            port = instance.get('port', 'N/A')
            status = instance.get('status', 'unknown')
            
            lines.append(
                f"{status_emoji} **{display_name}**\n"
                f"   • Client: `{client_id}`\n"
                f"   • URL: {url}\n"
                f"   • Port: {port}\n"
                f"   • Status: {status}\n"
            )
        
        lines.append(f"\n💡 Use `/inst show <client>` for detailed view")
        
        return "\n".join(lines)
    
    def format_instance_details(self, instance: Dict[str, Any]) -> str:
        """Format detailed instance view for Telegram."""
        status_emoji = self.status_emojis.get(instance.get('status', 'unknown'), '❓')
        client_id = instance.get('client_id', 'unknown')
        display_name = instance.get('display_name', client_id)
        url = instance.get('url', 'N/A')
        port = instance.get('port', 'N/A')
        status = instance.get('status', 'unknown')
        data_dir = instance.get('data_dir', 'N/A')
        reserved = instance.get('reserved', False)
        created_at = instance.get('created_at', 'N/A')
        updated_at = instance.get('updated_at', 'N/A')
        
        # Format dates
        created_formatted = self._format_datetime(created_at)
        updated_formatted = self._format_datetime(updated_at)
        
        reserved_flag = " 🔒" if reserved else ""
        
        details = [
            f"{status_emoji} **{display_name}**{reserved_flag}\n",
            f"**Client ID:** `{client_id}`",
            f"**URL:** {url}",
            f"**Port:** {port}",
            f"**Status:** {status}",
            f"**Data Directory:** `{data_dir}`",
            f"**Port Reserved:** {'Yes' if reserved else 'No'}",
            f"**Created:** {created_formatted}",
            f"**Updated:** {updated_formatted}"
        ]
        
        if status == 'running':
            details.append(f"\n🌐 **Access:** [Open n8n Interface]({url})")
        
        details.append(f"\n💡 Use `/inst delete {client_id} keep|wipe` to remove")
        
        return "\n".join(details)
    
    def format_instance_created(self, instance: Dict[str, Any]) -> str:
        """Format instance creation success message."""
        status_emoji = self.status_emojis.get(instance.get('status', 'unknown'), '❓')
        client_id = instance.get('client_id', 'unknown')
        display_name = instance.get('display_name', client_id)
        url = instance.get('url', 'N/A')
        port = instance.get('port', 'N/A')
        status = instance.get('status', 'unknown')
        
        lines = [
            f"✅ **Instance Created Successfully**\n",
            f"{status_emoji} **{display_name}**",
            f"• Client ID: `{client_id}`",
            f"• URL: {url}",
            f"• Port: {port}",
            f"• Status: {status}"
        ]
        
        if status == 'running':
            lines.append(f"\n🌐 **Ready to use:** [Open n8n Interface]({url})")
        elif status == 'stopped':
            lines.append(f"\n⚠️ **Container stopped** - may need manual restart")
        
        lines.append(f"\n💡 Use `/inst show {client_id}` for full details")
        
        return "\n".join(lines)
    
    def format_deletion_result(self, result: Dict[str, Any]) -> str:
        """Format instance deletion result."""
        mode = result.get('mode', 'unknown')
        message = result.get('message', '')
        audit_id = result.get('audit_id', '')
        
        if mode == 'keep':
            emoji = "📦"
            mode_desc = "archived (data preserved, port reserved)"
        elif mode == 'wipe':
            emoji = "🗑️"
            mode_desc = "completely removed (data deleted, port freed)"
        else:
            emoji = "✅"
            mode_desc = mode
        
        lines = [
            f"{emoji} **Instance Deleted Successfully**\n",
            f"**Mode:** {mode_desc}"
        ]
        
        if message:
            lines.append(f"**Result:** {message}")
        
        if audit_id:
            lines.append(f"**Audit ID:** `{audit_id}`")
        
        if mode == 'keep':
            lines.append(f"\n💡 Data preserved - you can recreate this instance later")
        elif mode == 'wipe':
            lines.append(f"\n⚠️ All data permanently deleted - cannot be recovered")
        
        return "\n".join(lines)
    
    def format_instance_stats(self, stats: Dict[str, Any]) -> str:
        """Format instance registry statistics."""
        port_usage = stats.get('port_usage', {})
        instance_counts = stats.get('instance_counts', {})
        
        total_ports = port_usage.get('total_ports', 0)
        used_ports = port_usage.get('used_ports', 0)
        available_ports = port_usage.get('available_ports', 0)
        utilization = port_usage.get('utilization_percent', 0)
        port_range = port_usage.get('port_range', 'unknown')
        
        total_instances = instance_counts.get('total', 0)
        by_status = instance_counts.get('by_status', {})
        
        lines = [
            "📊 **Instance Registry Statistics**\n",
            f"**🔌 Port Usage**",
            f"• Range: {port_range}",
            f"• Used: {used_ports}/{total_ports} ({utilization}%)",
            f"• Available: {available_ports}",
            f"",
            f"**📦 Instances**",
            f"• Total: {total_instances}"
        ]
        
        if by_status:
            for status, count in sorted(by_status.items()):
                emoji = self.status_emojis.get(status, '❓')
                lines.append(f"• {emoji} {status.title()}: {count}")
        
        # Health indicator
        if utilization > 90:
            lines.append(f"\n⚠️ **High port utilization** - consider expanding range")
        elif utilization > 75:
            lines.append(f"\n💡 **Moderate utilization** - monitor growth")
        else:
            lines.append(f"\n✅ **Good availability** - plenty of ports free")
        
        return "\n".join(lines)
    
    def format_error(self, error_message: str, context: str = None) -> str:
        """Format error message for Telegram."""
        lines = ["❌ **Operation Failed**\n"]
        
        if context:
            lines.append(f"**Operation:** {context}")
        
        lines.append(f"**Error:** {error_message}")
        
        # Add helpful hints for common errors
        if "client id" in error_message.lower():
            lines.append(f"\n💡 Client IDs must be lowercase, alphanumeric with hyphens (e.g., 'client1', 'test-client')")
        elif "port" in error_message.lower():
            lines.append(f"\n💡 Ports must be in allowed range - use auto-allocation or check available range")
        elif "not found" in error_message.lower():
            lines.append(f"\n💡 Use `/inst list` to see all available instances")
        elif "admin" in error_message.lower():
            lines.append(f"\n💡 This operation requires administrator privileges")
        
        return "\n".join(lines)
    
    def format_help(self) -> str:
        """Format help text for instance commands."""
        return """📋 **Instance Management Commands**

**📦 Create Instance**
• `/inst create <client>` - Auto-allocate port
• `/inst create <client> name "Display Name"` - With custom name  
• `/inst create <client> port 20005` - Specific port

**📋 List & View**
• `/inst list` - Show all instances
• `/inst show <client>` - Detailed view

**🗑️ Delete Instance**
• `/inst delete <client> keep` - Remove container, keep data
• `/inst delete <client> wipe` - Remove everything permanently

**📊 Statistics**
• `/inst stats` - Port usage and registry stats

**💡 Tips**
• Client IDs: lowercase, alphanumeric, hyphens (max 32 chars)
• Deletion requires admin privileges and approval
• Use 'keep' mode to preserve data for later recreation
• Use 'wipe' mode only when data is no longer needed

**🔗 Quick Actions**
• Click instance URLs to open n8n interface
• Use inline buttons for common operations"""
    
    def _format_datetime(self, dt_str: str) -> str:
        """Format datetime string for display."""
        if not dt_str or dt_str == 'N/A':
            return 'N/A'
        
        try:
            # Try to parse and reformat datetime
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M')
        except:
            # Return as-is if parsing fails
            return dt_str

# Export
__all__ = ["InstanceFormatter"]
