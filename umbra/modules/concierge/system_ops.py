"""
System Operations for Concierge

Provides comprehensive system monitoring using psutil:
- CPU usage, load averages, core information
- Memory usage (RAM, swap)
- Disk usage and I/O statistics
- Network statistics
- Process monitoring
- System uptime and boot time
"""
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

@dataclass
class SystemMetrics:
    """System metrics data structure."""
    timestamp: float
    cpu_percent: float
    cpu_count: int
    load_average: Tuple[float, float, float]
    memory_total: int
    memory_available: int
    memory_percent: float
    swap_total: int
    swap_used: int
    swap_percent: float
    disk_total: int
    disk_used: int
    disk_free: int
    disk_percent: float
    boot_time: float
    uptime_seconds: float

@dataclass
class ProcessInfo:
    """Process information structure."""
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    memory_rss: int
    status: str
    create_time: float
    cmdline: List[str]

class SystemOps:
    """System operations and monitoring using psutil."""
    
    def __init__(self):
        self.last_cpu_check = 0
        self.cpu_interval = 1.0  # seconds
    
    def check_system(self) -> SystemMetrics:
        """
        Get comprehensive system status.
        
        Returns:
            SystemMetrics object with current system state
        """
        # CPU information
        cpu_percent = psutil.cpu_percent(interval=self.cpu_interval)
        cpu_count = psutil.cpu_count(logical=True)
        
        # Load averages (Unix-like systems)
        try:
            load_avg = psutil.getloadavg()
        except AttributeError:
            # Windows doesn't have load average
            load_avg = (0.0, 0.0, 0.0)
        
        # Memory information
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # Disk information (root filesystem)
        disk = psutil.disk_usage('/')
        
        # System boot time and uptime
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        
        return SystemMetrics(
            timestamp=time.time(),
            cpu_percent=cpu_percent,
            cpu_count=cpu_count,
            load_average=load_avg,
            memory_total=memory.total,
            memory_available=memory.available,
            memory_percent=memory.percent,
            swap_total=swap.total,
            swap_used=swap.used,
            swap_percent=swap.percent,
            disk_total=disk.total,
            disk_used=disk.used,
            disk_free=disk.free,
            disk_percent=(disk.used / disk.total) * 100,
            boot_time=boot_time,
            uptime_seconds=uptime_seconds
        )
    
    def get_detailed_cpu_info(self) -> Dict[str, Any]:
        """Get detailed CPU information."""
        try:
            cpu_times = psutil.cpu_times()
            cpu_percent_per_core = psutil.cpu_percent(interval=1, percpu=True)
            cpu_freq = psutil.cpu_freq()
            
            return {
                "logical_cores": psutil.cpu_count(logical=True),
                "physical_cores": psutil.cpu_count(logical=False),
                "current_frequency": cpu_freq.current if cpu_freq else None,
                "min_frequency": cpu_freq.min if cpu_freq else None,
                "max_frequency": cpu_freq.max if cpu_freq else None,
                "per_core_usage": cpu_percent_per_core,
                "cpu_times": {
                    "user": cpu_times.user,
                    "system": cpu_times.system,
                    "idle": cpu_times.idle,
                    "iowait": getattr(cpu_times, 'iowait', 0),
                    "steal": getattr(cpu_times, 'steal', 0),
                }
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_memory_details(self) -> Dict[str, Any]:
        """Get detailed memory information."""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            return {
                "virtual_memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used,
                    "free": memory.free,
                    "active": getattr(memory, 'active', 0),
                    "inactive": getattr(memory, 'inactive', 0),
                    "buffers": getattr(memory, 'buffers', 0),
                    "cached": getattr(memory, 'cached', 0),
                    "shared": getattr(memory, 'shared', 0),
                },
                "swap_memory": {
                    "total": swap.total,
                    "used": swap.used,
                    "free": swap.free,
                    "percent": swap.percent,
                    "sin": swap.sin,
                    "sout": swap.sout,
                }
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_disk_info(self, path: str = '/') -> Dict[str, Any]:
        """Get disk usage and I/O information."""
        try:
            usage = psutil.disk_usage(path)
            io_counters = psutil.disk_io_counters()
            
            result = {
                "usage": {
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": (usage.used / usage.total) * 100,
                },
                "partitions": []
            }
            
            # Get all mounted partitions
            partitions = psutil.disk_partitions()
            for partition in partitions:
                try:
                    partition_usage = psutil.disk_usage(partition.mountpoint)
                    result["partitions"].append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "total": partition_usage.total,
                        "used": partition_usage.used,
                        "free": partition_usage.free,
                        "percent": (partition_usage.used / partition_usage.total) * 100,
                    })
                except PermissionError:
                    # Skip partitions we can't access
                    continue
            
            # Add I/O counters if available
            if io_counters:
                result["io_counters"] = {
                    "read_count": io_counters.read_count,
                    "write_count": io_counters.write_count,
                    "read_bytes": io_counters.read_bytes,
                    "write_bytes": io_counters.write_bytes,
                    "read_time": io_counters.read_time,
                    "write_time": io_counters.write_time,
                }
            
            return result
        except Exception as e:
            return {"error": str(e)}
    
    def get_network_info(self) -> Dict[str, Any]:
        """Get network statistics and interface information."""
        try:
            io_counters = psutil.net_io_counters(pernic=True)
            connections = psutil.net_connections()
            
            result = {
                "interfaces": {},
                "connections": {
                    "total": len(connections),
                    "listening": len([c for c in connections if c.status == 'LISTEN']),
                    "established": len([c for c in connections if c.status == 'ESTABLISHED']),
                }
            }
            
            # Interface statistics
            for interface, stats in io_counters.items():
                result["interfaces"][interface] = {
                    "bytes_sent": stats.bytes_sent,
                    "bytes_recv": stats.bytes_recv,
                    "packets_sent": stats.packets_sent,
                    "packets_recv": stats.packets_recv,
                    "errin": stats.errin,
                    "errout": stats.errout,
                    "dropin": stats.dropin,
                    "dropout": stats.dropout,
                }
            
            return result
        except Exception as e:
            return {"error": str(e)}
    
    def get_top_processes(self, limit: int = 10, sort_by: str = 'cpu') -> List[ProcessInfo]:
        """
        Get top processes by CPU or memory usage.
        
        Args:
            limit: Number of processes to return
            sort_by: Sort by 'cpu' or 'memory'
        
        Returns:
            List of ProcessInfo objects
        """
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 
                                        'memory_info', 'status', 'create_time', 'cmdline']):
            try:
                pinfo = proc.info
                
                # Skip kernel threads and processes with no CPU/memory usage
                if pinfo['cpu_percent'] == 0 and pinfo['memory_percent'] == 0:
                    continue
                
                process_info = ProcessInfo(
                    pid=pinfo['pid'],
                    name=pinfo['name'] or 'Unknown',
                    cpu_percent=pinfo['cpu_percent'] or 0,
                    memory_percent=pinfo['memory_percent'] or 0,
                    memory_rss=pinfo['memory_info'].rss if pinfo['memory_info'] else 0,
                    status=pinfo['status'],
                    create_time=pinfo['create_time'],
                    cmdline=pinfo['cmdline'] or []
                )
                
                processes.append(process_info)
                
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        # Sort processes
        if sort_by == 'memory':
            processes.sort(key=lambda x: x.memory_percent, reverse=True)
        else:  # default to CPU
            processes.sort(key=lambda x: x.cpu_percent, reverse=True)
        
        return processes[:limit]
    
    def get_system_uptime(self) -> Dict[str, Any]:
        """Get system uptime information."""
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        
        # Convert to human readable format
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        seconds = int(uptime_seconds % 60)
        
        return {
            "boot_time": boot_time,
            "boot_time_iso": datetime.fromtimestamp(boot_time).isoformat(),
            "uptime_seconds": uptime_seconds,
            "uptime_human": f"{days}d {hours}h {minutes}m {seconds}s",
            "uptime_components": {
                "days": days,
                "hours": hours,
                "minutes": minutes,
                "seconds": seconds
            }
        }
    
    def get_system_users(self) -> List[Dict[str, Any]]:
        """Get logged in users."""
        try:
            users = psutil.users()
            return [
                {
                    "name": user.name,
                    "terminal": user.terminal,
                    "host": user.host,
                    "started": user.started,
                    "started_iso": datetime.fromtimestamp(user.started).isoformat()
                }
                for user in users
            ]
        except Exception as e:
            return [{"error": str(e)}]
    
    def format_bytes(self, bytes_value: int) -> str:
        """Format bytes in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"
    
    def format_system_summary(self, metrics: SystemMetrics) -> str:
        """Format system metrics for display."""
        uptime_str = str(timedelta(seconds=int(metrics.uptime_seconds)))
        
        return f"""**🖥️ System Status**

**CPU:** {metrics.cpu_percent:.1f}% ({metrics.cpu_count} cores)
**Load:** {metrics.load_average[0]:.2f}, {metrics.load_average[1]:.2f}, {metrics.load_average[2]:.2f}
**Memory:** {metrics.memory_percent:.1f}% ({self.format_bytes(metrics.memory_available)} available)
**Swap:** {metrics.swap_percent:.1f}% ({self.format_bytes(metrics.swap_total - metrics.swap_used)} free)
**Disk:** {metrics.disk_percent:.1f}% ({self.format_bytes(metrics.disk_free)} free)
**Uptime:** {uptime_str}"""
    
    def get_health_status(self, metrics: SystemMetrics) -> Dict[str, Any]:
        """Determine system health based on metrics."""
        health_score = 100
        issues = []
        
        # CPU health
        if metrics.cpu_percent > 90:
            health_score -= 20
            issues.append("High CPU usage")
        elif metrics.cpu_percent > 80:
            health_score -= 10
            issues.append("Elevated CPU usage")
        
        # Memory health
        if metrics.memory_percent > 95:
            health_score -= 25
            issues.append("Critical memory usage")
        elif metrics.memory_percent > 85:
            health_score -= 15
            issues.append("High memory usage")
        
        # Disk health
        if metrics.disk_percent > 95:
            health_score -= 30
            issues.append("Critical disk usage")
        elif metrics.disk_percent > 85:
            health_score -= 20
            issues.append("High disk usage")
        
        # Load average health (relative to CPU cores)
        if metrics.load_average[0] > metrics.cpu_count * 2:
            health_score -= 15
            issues.append("High system load")
        
        # Swap usage
        if metrics.swap_percent > 50:
            health_score -= 10
            issues.append("High swap usage")
        
        # Determine overall status
        if health_score >= 90:
            status = "excellent"
        elif health_score >= 75:
            status = "good"
        elif health_score >= 50:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "health_score": max(0, health_score),
            "issues": issues,
            "timestamp": metrics.timestamp
        }

# Export
__all__ = ["SystemMetrics", "ProcessInfo", "SystemOps"]
