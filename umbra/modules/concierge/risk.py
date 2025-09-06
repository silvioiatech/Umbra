"""
Risk Classification System for Concierge Operations

Classifies commands and operations by risk level:
- SAFE: Read-only operations, basic diagnostics
- SENSITIVE: Configuration changes, service restarts
- DESTRUCTIVE: Data deletion, system modifications
- CATASTROPHIC: Filesystem destruction, security bypasses

Includes blocklist for extremely dangerous operations.
"""
import re
from enum import Enum
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

class RiskLevel(Enum):
    """Risk levels for operations."""
    SAFE = "SAFE"
    SENSITIVE = "SENSITIVE" 
    DESTRUCTIVE = "DESTRUCTIVE"
    CATASTROPHIC = "CATASTROPHIC"

@dataclass
class RiskPattern:
    """Pattern for risk classification."""
    pattern: str
    risk_level: RiskLevel
    description: str
    requires_approval: bool = False
    requires_double_confirm: bool = False
    blocked: bool = False

class RiskClassifier:
    """Classifies operations by risk level with comprehensive pattern matching."""
    
    def __init__(self):
        self.patterns = self._initialize_patterns()
        self.blocklist = self._initialize_blocklist()
    
    def _initialize_patterns(self) -> List[RiskPattern]:
        """Initialize risk classification patterns."""
        return [
            # SAFE operations (read-only, diagnostics)
            RiskPattern(r"^(ps|top|htop|free|df|du|uptime|date|whoami|id|pwd|ls|cat|head|tail|grep|find|which|whereis)", 
                       RiskLevel.SAFE, "Read-only system commands"),
            RiskPattern(r"^docker (ps|images|info|version|stats)", 
                       RiskLevel.SAFE, "Docker read-only commands"),
            RiskPattern(r"^systemctl status", 
                       RiskLevel.SAFE, "Service status check"),
            RiskPattern(r"^journalctl", 
                       RiskLevel.SAFE, "Log viewing"),
            RiskPattern(r"^(ping|curl|wget) ", 
                       RiskLevel.SAFE, "Network diagnostics"),
            
            # SENSITIVE operations (configuration, service management)
            RiskPattern(r"^docker (restart|start|stop)", 
                       RiskLevel.SENSITIVE, "Docker container management", requires_approval=True),
            RiskPattern(r"^systemctl (start|stop|restart|reload)", 
                       RiskLevel.SENSITIVE, "Service management", requires_approval=True),
            RiskPattern(r"^(nano|vim|vi|emacs) ", 
                       RiskLevel.SENSITIVE, "File editing", requires_approval=True),
            RiskPattern(r"^chmod [0-7]{3} ", 
                       RiskLevel.SENSITIVE, "Permission change", requires_approval=True),
            RiskPattern(r"^chown ", 
                       RiskLevel.SENSITIVE, "Ownership change", requires_approval=True),
            RiskPattern(r"^iptables ", 
                       RiskLevel.SENSITIVE, "Firewall modification", requires_approval=True),
            
            # DESTRUCTIVE operations (data modification, high risk)
            RiskPattern(r"^rm -r", 
                       RiskLevel.DESTRUCTIVE, "Recursive deletion", requires_approval=True, requires_double_confirm=True),
            RiskPattern(r"^docker (rm|rmi)", 
                       RiskLevel.DESTRUCTIVE, "Docker removal", requires_approval=True, requires_double_confirm=True),
            RiskPattern(r"^systemctl (disable|mask)", 
                       RiskLevel.DESTRUCTIVE, "Service disabling", requires_approval=True, requires_double_confirm=True),
            RiskPattern(r"^(killall|pkill) ", 
                       RiskLevel.DESTRUCTIVE, "Process termination", requires_approval=True, requires_double_confirm=True),
            RiskPattern(r"^chmod -R ", 
                       RiskLevel.DESTRUCTIVE, "Recursive permission change", requires_approval=True, requires_double_confirm=True),
            RiskPattern(r"^dd if=", 
                       RiskLevel.DESTRUCTIVE, "Direct disk write", requires_approval=True, requires_double_confirm=True),
            
            # CATASTROPHIC operations (blocked by default)
            RiskPattern(r"^rm -rf /", 
                       RiskLevel.CATASTROPHIC, "Root filesystem deletion", blocked=True),
            RiskPattern(r"^mkfs", 
                       RiskLevel.CATASTROPHIC, "Filesystem creation", blocked=True),
            RiskPattern(r"^fdisk ", 
                       RiskLevel.CATASTROPHIC, "Disk partitioning", blocked=True),
            RiskPattern(r"^parted ", 
                       RiskLevel.CATASTROPHIC, "Partition management", blocked=True),
            RiskPattern(r"^wipefs ", 
                       RiskLevel.CATASTROPHIC, "Filesystem signature removal", blocked=True),
            RiskPattern(r"^shred ", 
                       RiskLevel.CATASTROPHIC, "Secure file deletion", blocked=True),
        ]
    
    def _initialize_blocklist(self) -> List[str]:
        """Initialize list of completely blocked commands."""
        return [
            "rm -rf /",
            "rm -rf /*", 
            ":(){ :|:& };:",  # Fork bomb
            "chmod 777 -R /",
            "chown -R root:root /",
            "dd if=/dev/zero of=/dev/sda",
            "mkfs.ext4 /dev/sda",
            "fdisk /dev/sda",
            "parted /dev/sda",
            "wipefs -a /dev/sda",
            "init 0",
            "shutdown -h now",
            "reboot",
            "poweroff"
        ]
    
    def classify_command(self, command: str) -> Tuple[RiskLevel, RiskPattern, bool]:
        """
        Classify a command by risk level.
        
        Returns:
            Tuple of (risk_level, matching_pattern, is_blocked)
        """
        command = command.strip()
        
        # Check blocklist first
        for blocked_cmd in self.blocklist:
            if blocked_cmd in command.lower():
                # Find catastrophic pattern for this command
                for pattern in self.patterns:
                    if pattern.risk_level == RiskLevel.CATASTROPHIC and re.search(pattern.pattern, command, re.IGNORECASE):
                        return RiskLevel.CATASTROPHIC, pattern, True
                # Create a default catastrophic pattern if no specific one found
                catastrophic_pattern = RiskPattern(
                    pattern=blocked_cmd,
                    risk_level=RiskLevel.CATASTROPHIC,
                    description="Blocked dangerous operation",
                    blocked=True
                )
                return RiskLevel.CATASTROPHIC, catastrophic_pattern, True
        
        # Check patterns in order of severity (most dangerous first)
        severity_order = [RiskLevel.CATASTROPHIC, RiskLevel.DESTRUCTIVE, RiskLevel.SENSITIVE, RiskLevel.SAFE]
        
        for severity in severity_order:
            for pattern in self.patterns:
                if pattern.risk_level == severity:
                    if re.search(pattern.pattern, command, re.IGNORECASE):
                        return pattern.risk_level, pattern, pattern.blocked
        
        # Default to SENSITIVE for unknown commands
        default_pattern = RiskPattern(
            pattern=".*",
            risk_level=RiskLevel.SENSITIVE,
            description="Unknown command - default to sensitive",
            requires_approval=True
        )
        return RiskLevel.SENSITIVE, default_pattern, False
    
    def get_approval_requirements(self, risk_level: RiskLevel, pattern: RiskPattern) -> Dict[str, bool]:
        """Get approval requirements for a risk level."""
        return {
            "requires_approval": pattern.requires_approval or risk_level in [RiskLevel.SENSITIVE, RiskLevel.DESTRUCTIVE, RiskLevel.CATASTROPHIC],
            "requires_double_confirm": pattern.requires_double_confirm or risk_level in [RiskLevel.DESTRUCTIVE, RiskLevel.CATASTROPHIC],
            "is_blocked": pattern.blocked or risk_level == RiskLevel.CATASTROPHIC,
            "timeout_seconds": self._get_approval_timeout(risk_level)
        }
    
    def _get_approval_timeout(self, risk_level: RiskLevel) -> int:
        """Get approval timeout based on risk level."""
        timeouts = {
            RiskLevel.SAFE: 0,          # No timeout needed
            RiskLevel.SENSITIVE: 300,   # 5 minutes
            RiskLevel.DESTRUCTIVE: 300, # 5 minutes
            RiskLevel.CATASTROPHIC: 0   # Blocked entirely
        }
        return timeouts.get(risk_level, 300)
    
    def get_safe_macros(self) -> Dict[str, str]:
        """Get predefined safe command macros."""
        return {
            "df_h": "df -h",
            "free_m": "free -m", 
            "docker_stats": "docker stats --no-stream",
            "docker_ps": "docker ps -a",
            "system_load": "uptime && free -m && df -h",
            "network_info": "ip addr show && netstat -tulpn",
            "process_info": "ps aux | head -20",
            "disk_usage": "du -sh /var/log /tmp /home",
            "service_status": "systemctl list-units --type=service --state=running",
            "docker_images": "docker images",
            "docker_volumes": "docker volume ls",
            "docker_networks": "docker network ls"
        }
    
    def expand_macro(self, command: str) -> Optional[str]:
        """Expand a safe macro to its full command."""
        macros = self.get_safe_macros()
        return macros.get(command.strip(), None)

# Export
__all__ = ["RiskLevel", "RiskPattern", "RiskClassifier"]
