"""
Docker Operations for Concierge

Provides safe Docker container management with locking:
- List containers with detailed information
- Tail logs with truncation and filtering
- Restart containers with safety checks
- Container stats and monitoring
- Resource locks for sensitive operations
"""
import subprocess
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

@dataclass
class ContainerInfo:
    """Container information structure."""
    container_id: str
    name: str
    image: str
    status: str
    state: str
    created: str
    ports: List[Dict[str, Any]]
    mounts: List[Dict[str, Any]]
    networks: List[str]
    labels: Dict[str, str]

@dataclass
class ContainerStats:
    """Container statistics structure."""
    container_id: str
    name: str
    cpu_percent: float
    memory_usage: int
    memory_limit: int
    memory_percent: float
    network_rx: int
    network_tx: int
    block_read: int
    block_write: int
    pids: int

class ContainerLock:
    """Thread-safe lock for container operations."""
    
    def __init__(self):
        self._locks = {}
        self._lock_mutex = threading.Lock()
    
    def acquire(self, container_name: str, timeout: float = 30.0) -> bool:
        """Acquire lock for container operation."""
        with self._lock_mutex:
            if container_name not in self._locks:
                self._locks[container_name] = threading.Lock()
        
        container_lock = self._locks[container_name]
        return container_lock.acquire(timeout=timeout)
    
    def release(self, container_name: str):
        """Release lock for container operation."""
        with self._lock_mutex:
            if container_name in self._locks:
                self._locks[container_name].release()
    
    def is_locked(self, container_name: str) -> bool:
        """Check if container is locked."""
        with self._lock_mutex:
            if container_name not in self._locks:
                return False
            return self._locks[container_name].locked()

class DockerOps:
    """Docker operations with safety features and locking."""
    
    def __init__(self):
        self.container_locks = ContainerLock()
        self.docker_available = self._check_docker_availability()
    
    def _check_docker_availability(self) -> bool:
        """Check if Docker is available and accessible."""
        try:
            result = subprocess.run(
                ['docker', 'version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _run_docker_command(self, cmd: List[str], timeout: int = 30) -> Tuple[bool, str, str]:
        """
        Run Docker command safely with timeout.
        
        Returns:
            Tuple of (success, stdout, stderr)
        """
        try:
            result = subprocess.run(
                ['docker'] + cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)
    
    def list_containers(self, all_containers: bool = True) -> List[ContainerInfo]:
        """
        List Docker containers with detailed information.
        
        Args:
            all_containers: Include stopped containers
        
        Returns:
            List of ContainerInfo objects
        """
        if not self.docker_available:
            return []
        
        cmd = ['ps', '--format', '{{json .}}']
        if all_containers:
            cmd.append('--all')
        
        success, stdout, stderr = self._run_docker_command(cmd)
        if not success:
            return []
        
        containers = []
        for line in stdout.strip().split('\n'):
            if line:
                try:
                    data = json.loads(line)
                    
                    # Get detailed info for each container
                    container_info = self._get_container_details(data['ID'])
                    if container_info:
                        containers.append(container_info)
                        
                except json.JSONDecodeError:
                    continue
        
        return containers
    
    def _get_container_details(self, container_id: str) -> Optional[ContainerInfo]:
        """Get detailed information for a specific container."""
        success, stdout, stderr = self._run_docker_command(['inspect', container_id])
        if not success:
            return None
        
        try:
            data = json.loads(stdout)[0]
            
            # Extract port mappings
            ports = []
            if data.get('NetworkSettings', {}).get('Ports'):
                for container_port, host_bindings in data['NetworkSettings']['Ports'].items():
                    if host_bindings:
                        for binding in host_bindings:
                            ports.append({
                                'container_port': container_port,
                                'host_ip': binding.get('HostIp', ''),
                                'host_port': binding.get('HostPort', '')
                            })
                    else:
                        ports.append({
                            'container_port': container_port,
                            'host_ip': '',
                            'host_port': ''
                        })
            
            # Extract mount information
            mounts = []
            for mount in data.get('Mounts', []):
                mounts.append({
                    'type': mount.get('Type'),
                    'source': mount.get('Source'),
                    'destination': mount.get('Destination'),
                    'mode': mount.get('Mode'),
                    'rw': mount.get('RW', True)
                })
            
            # Extract network information
            networks = list(data.get('NetworkSettings', {}).get('Networks', {}).keys())
            
            return ContainerInfo(
                container_id=data['Id'][:12],
                name=data['Name'].lstrip('/'),
                image=data['Config']['Image'],
                status=data['State']['Status'],
                state=data['State']['Status'],
                created=data['Created'],
                ports=ports,
                mounts=mounts,
                networks=networks,
                labels=data['Config'].get('Labels', {}) or {}
            )
            
        except (json.JSONDecodeError, KeyError, IndexError):
            return None
    
    def tail_logs(
        self, 
        container: str, 
        lines: int = 100, 
        since: Optional[str] = None,
        follow: bool = False,
        timestamps: bool = True
    ) -> Tuple[bool, str]:
        """
        Tail container logs with options.
        
        Args:
            container: Container name or ID
            lines: Number of lines to return
            since: Show logs since timestamp (e.g., "2h", "1m")
            follow: Follow log output (not recommended for Telegram)
            timestamps: Include timestamps
        
        Returns:
            Tuple of (success, logs)
        """
        if not self.docker_available:
            return False, "Docker not available"
        
        cmd = ['logs']
        
        if timestamps:
            cmd.append('--timestamps')
        
        if lines > 0:
            cmd.extend(['--tail', str(lines)])
        
        if since:
            cmd.extend(['--since', since])
        
        if follow:
            cmd.append('--follow')
        
        cmd.append(container)
        
        # Use shorter timeout for log tailing
        success, stdout, stderr = self._run_docker_command(cmd, timeout=15)
        
        if success:
            # Truncate if too long (Telegram message limits)
            output = stdout
            if len(output) > 4000:  # Leave room for formatting
                lines = output.split('\n')
                truncated_lines = lines[-50:]  # Last 50 lines
                output = '\n'.join(truncated_lines)
                output = f"[Truncated to last 50 lines]\n\n{output}"
            
            return True, output
        else:
            return False, stderr
    
    def restart_container(self, container: str) -> Tuple[bool, str]:
        """
        Restart a container with safety checks and locking.
        
        Args:
            container: Container name or ID
        
        Returns:
            Tuple of (success, message)
        """
        if not self.docker_available:
            return False, "Docker not available"
        
        # Acquire lock for this container
        if not self.container_locks.acquire(container, timeout=30):
            return False, f"Container {container} is locked by another operation"
        
        try:
            # Check if container exists and get current state
            containers = self.list_containers(all_containers=True)
            target_container = None
            
            for c in containers:
                if c.name == container or c.container_id == container:
                    target_container = c
                    break
            
            if not target_container:
                return False, f"Container {container} not found"
            
            # Check if container is already stopped
            if target_container.status in ['exited', 'dead']:
                # Start instead of restart
                success, stdout, stderr = self._run_docker_command(['start', container])
                if success:
                    return True, f"Container {container} started successfully"
                else:
                    return False, f"Failed to start container: {stderr}"
            
            # Restart the container
            success, stdout, stderr = self._run_docker_command(['restart', container], timeout=60)
            
            if success:
                return True, f"Container {container} restarted successfully"
            else:
                return False, f"Failed to restart container: {stderr}"
        
        finally:
            # Always release the lock
            self.container_locks.release(container)
    
    def get_container_stats(self, container: Optional[str] = None) -> List[ContainerStats]:
        """
        Get container resource statistics.
        
        Args:
            container: Specific container name/ID, or None for all running containers
        
        Returns:
            List of ContainerStats objects
        """
        if not self.docker_available:
            return []
        
        cmd = ['stats', '--no-stream', '--format', '{{json .}}']
        
        if container:
            cmd.append(container)
        
        success, stdout, stderr = self._run_docker_command(cmd, timeout=20)
        if not success:
            return []
        
        stats = []
        for line in stdout.strip().split('\n'):
            if line:
                try:
                    data = json.loads(line)
                    
                    # Parse memory usage
                    memory_usage = 0
                    memory_limit = 0
                    memory_percent = 0.0
                    
                    if 'MemUsage' in data:
                        mem_parts = data['MemUsage'].split(' / ')
                        if len(mem_parts) == 2:
                            memory_usage = self._parse_bytes(mem_parts[0])
                            memory_limit = self._parse_bytes(mem_parts[1])
                            if memory_limit > 0:
                                memory_percent = (memory_usage / memory_limit) * 100
                    
                    # Parse network I/O
                    network_rx = 0
                    network_tx = 0
                    if 'NetIO' in data:
                        net_parts = data['NetIO'].split(' / ')
                        if len(net_parts) == 2:
                            network_rx = self._parse_bytes(net_parts[0])
                            network_tx = self._parse_bytes(net_parts[1])
                    
                    # Parse block I/O
                    block_read = 0
                    block_write = 0
                    if 'BlockIO' in data:
                        block_parts = data['BlockIO'].split(' / ')
                        if len(block_parts) == 2:
                            block_read = self._parse_bytes(block_parts[0])
                            block_write = self._parse_bytes(block_parts[1])
                    
                    container_stats = ContainerStats(
                        container_id=data.get('Container', '')[:12],
                        name=data.get('Name', ''),
                        cpu_percent=float(data.get('CPUPerc', '0%').rstrip('%')),
                        memory_usage=memory_usage,
                        memory_limit=memory_limit,
                        memory_percent=memory_percent,
                        network_rx=network_rx,
                        network_tx=network_tx,
                        block_read=block_read,
                        block_write=block_write,
                        pids=int(data.get('PIDs', 0))
                    )
                    
                    stats.append(container_stats)
                    
                except (json.JSONDecodeError, ValueError, KeyError):
                    continue
        
        return stats
    
    def _parse_bytes(self, byte_str: str) -> int:
        """Parse byte string with units (e.g., '1.5GB') to integer bytes."""
        byte_str = byte_str.strip()
        if not byte_str:
            return 0
        
        # Remove any non-alphanumeric characters except decimal point
        import re
        clean_str = re.sub(r'[^0-9.a-zA-Z]', '', byte_str)
        
        # Extract number and unit
        number_match = re.match(r'([\d.]+)([a-zA-Z]*)', clean_str)
        if not number_match:
            return 0
        
        number = float(number_match.group(1))
        unit = number_match.group(2).upper()
        
        # Convert to bytes
        multipliers = {
            '': 1,
            'B': 1,
            'KB': 1024,
            'MB': 1024**2,
            'GB': 1024**3,
            'TB': 1024**4,
            'K': 1024,
            'M': 1024**2,
            'G': 1024**3,
            'T': 1024**4
        }
        
        return int(number * multipliers.get(unit, 1))
    
    def get_docker_system_info(self) -> Dict[str, Any]:
        """Get Docker system information."""
        if not self.docker_available:
            return {"error": "Docker not available"}
        
        success, stdout, stderr = self._run_docker_command(['system', 'df', '--format', 'json'])
        if not success:
            return {"error": stderr}
        
        try:
            data = json.loads(stdout)
            return data
        except json.JSONDecodeError:
            return {"error": "Failed to parse Docker system info"}
    
    def format_container_list(self, containers: List[ContainerInfo]) -> str:
        """Format container list for display."""
        if not containers:
            return "No containers found"
        
        lines = ["**🐳 Docker Containers**\n"]
        
        for container in containers:
            status_emoji = "🟢" if container.status == "running" else "🔴"
            
            # Format ports
            port_info = ""
            if container.ports:
                port_mappings = []
                for port in container.ports:
                    if port['host_port']:
                        port_mappings.append(f"{port['host_port']}:{port['container_port']}")
                    else:
                        port_mappings.append(port['container_port'])
                port_info = f" • Ports: {', '.join(port_mappings)}"
            
            lines.append(
                f"{status_emoji} **{container.name}**\n"
                f"   • ID: `{container.container_id}`\n"
                f"   • Image: {container.image}\n"
                f"   • Status: {container.status}{port_info}\n"
            )
        
        return "\n".join(lines)
    
    def format_container_stats(self, stats: List[ContainerStats]) -> str:
        """Format container statistics for display."""
        if not stats:
            return "No container statistics available"
        
        lines = ["**📊 Container Statistics**\n"]
        
        for stat in stats:
            lines.append(
                f"**{stat.name}**\n"
                f"   • CPU: {stat.cpu_percent:.1f}%\n"
                f"   • Memory: {stat.memory_percent:.1f}% "
                f"({self._format_bytes(stat.memory_usage)}/{self._format_bytes(stat.memory_limit)})\n"
                f"   • Network: ↓{self._format_bytes(stat.network_rx)} ↑{self._format_bytes(stat.network_tx)}\n"
                f"   • PIDs: {stat.pids}\n"
            )
        
        return "\n".join(lines)
    
    def _format_bytes(self, bytes_value: int) -> str:
        """Format bytes in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f}{unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f}PB"

# Export
__all__ = ["ContainerInfo", "ContainerStats", "ContainerLock", "DockerOps"]
