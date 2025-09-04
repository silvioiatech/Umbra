"""
Connection Status Checker - Verify all external service connections
"""
import asyncio
import logging
import aiohttp
import psutil
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import subprocess
import os

class ConnectionChecker:
    """Check connectivity to all external services."""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.start_time = time.time()
        
    async def check_all_connections(self) -> Dict[str, Any]:
        """Check all external service connections."""
        results = {
            'timestamp': datetime.now().isoformat(),
            'uptime': self.get_uptime(),
            'connections': {},
            'system': await self.get_system_info(),
            'bot_info': self.get_bot_info()
        }
        
        # Run all checks concurrently
        checks = [
            ('openrouter', self.check_openrouter()),
            ('telegram', self.check_telegram()),
            ('vps_ssh', self.check_vps_connection()),
            ('docker', self.check_docker()),
            ('storage', self.check_storage()),
            ('n8n', self.check_n8n()),
            ('mcp', self.check_mcp()),
            ('creator_apis', self.check_creator_apis()),
            ('database', self.check_database()),
            ('network', self.check_network())
        ]
        
        # Execute all checks concurrently with timeout
        for name, check_coro in checks:
            try:
                result = await asyncio.wait_for(check_coro, timeout=5.0)
                results['connections'][name] = result
            except asyncio.TimeoutError:
                results['connections'][name] = {
                    'status': 'timeout',
                    'message': 'Check timed out after 5 seconds',
                    'emoji': '⏱️'
                }
            except Exception as e:
                results['connections'][name] = {
                    'status': 'error',
                    'message': str(e)[:100],
                    'emoji': '❌'
                }
        
        return results
    
    def get_uptime(self) -> Dict[str, Any]:
        """Get bot uptime information."""
        uptime_seconds = time.time() - self.start_time
        uptime_delta = timedelta(seconds=int(uptime_seconds))
        
        days = uptime_delta.days
        hours, remainder = divmod(uptime_delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        return {
            'total_seconds': uptime_seconds,
            'formatted': f"{days}d {hours}h {minutes}m {seconds}s",
            'start_time': datetime.fromtimestamp(self.start_time).isoformat()
        }
    
    def get_bot_info(self) -> Dict[str, Any]:
        """Get bot runtime information."""
        import sys
        
        return {
            'version': '2.0.0',
            'python_version': sys.version.split()[0],
            'platform': sys.platform,
            'pid': os.getpid(),
            'environment': os.environ.get('ENVIRONMENT', 'unknown'),
            'features': {
                'ai_enabled': bool(os.environ.get('OPENROUTER_API_KEY')),
                'docker_enabled': bool(os.environ.get('DOCKER_AVAILABLE', 'false').lower() == 'true'),
                'metrics_enabled': bool(os.environ.get('FEATURE_METRICS_COLLECTION', 'true').lower() == 'true')
            }
        }
    
    async def get_system_info(self) -> Dict[str, Any]:
        """Get system resource information."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network I/O
            net_io = psutil.net_io_counters()
            
            return {
                'cpu': {
                    'percent': cpu_percent,
                    'cores': psutil.cpu_count(),
                    'status': '✅' if cpu_percent < 80 else '⚠️'
                },
                'memory': {
                    'percent': memory.percent,
                    'used_gb': round(memory.used / (1024**3), 2),
                    'total_gb': round(memory.total / (1024**3), 2),
                    'status': '✅' if memory.percent < 85 else '⚠️'
                },
                'disk': {
                    'percent': disk.percent,
                    'used_gb': round(disk.used / (1024**3), 2),
                    'total_gb': round(disk.total / (1024**3), 2),
                    'status': '✅' if disk.percent < 90 else '⚠️'
                },
                'network': {
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv,
                    'packets_sent': net_io.packets_sent,
                    'packets_recv': net_io.packets_recv
                }
            }
        except Exception as e:
            self.logger.error(f"System info error: {e}")
            return {'error': str(e)[:100]}
    
    async def check_openrouter(self) -> Dict[str, Any]:
        """Check OpenRouter AI API connection."""
        if not os.environ.get('OPENROUTER_API_KEY'):
            return {
                'status': 'not_configured',
                'message': 'API key not set',
                'emoji': '⚠️'
            }
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f"Bearer {os.environ.get('OPENROUTER_API_KEY')}",
                    'Content-Type': 'application/json'
                }
                
                # Test with a minimal request
                data = {
                    'model': 'openai/gpt-3.5-turbo',
                    'messages': [{'role': 'user', 'content': 'test'}],
                    'max_tokens': 1
                }
                
                async with session.post(
                    'https://openrouter.ai/api/v1/chat/completions',
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        return {
                            'status': 'connected',
                            'message': 'API responding',
                            'emoji': '✅',
                            'latency_ms': response.headers.get('X-Response-Time', 'unknown')
                        }
                    else:
                        return {
                            'status': 'error',
                            'message': f'HTTP {response.status}',
                            'emoji': '❌'
                        }
                        
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)[:50],
                'emoji': '❌'
            }
    
    async def check_telegram(self) -> Dict[str, Any]:
        """Check Telegram Bot API connection."""
        if not self.config.TELEGRAM_BOT_TOKEN:
            return {
                'status': 'not_configured',
                'message': 'Bot token not set',
                'emoji': '⚠️'
            }
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.telegram.org/bot{self.config.TELEGRAM_BOT_TOKEN}/getMe"
                
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('ok'):
                            bot_info = data.get('result', {})
                            return {
                                'status': 'connected',
                                'message': f"@{bot_info.get('username', 'unknown')}",
                                'emoji': '✅',
                                'bot_name': bot_info.get('first_name', 'Umbra')
                            }
                    
                    return {
                        'status': 'error',
                        'message': f'HTTP {response.status}',
                        'emoji': '❌'
                    }
                    
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)[:50],
                'emoji': '❌'
            }
    
    async def check_vps_connection(self) -> Dict[str, Any]:
        """Check VPS/SSH connectivity."""
        vps_host = os.environ.get('VPS_HOST')
        
        if not vps_host:
            return {
                'status': 'not_configured',
                'message': 'VPS_HOST not set',
                'emoji': '⚠️'
            }
        
        try:
            # Try to ping the host
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '2', vps_host],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            if result.returncode == 0:
                # Extract ping time
                import re
                match = re.search(r'time=(\d+\.?\d*)', result.stdout)
                ping_time = match.group(1) if match else 'unknown'
                
                return {
                    'status': 'connected',
                    'message': f'Ping: {ping_time}ms',
                    'emoji': '✅',
                    'host': vps_host
                }
            else:
                return {
                    'status': 'unreachable',
                    'message': 'Ping failed',
                    'emoji': '❌'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'status': 'timeout',
                'message': 'Ping timeout',
                'emoji': '⏱️'
            }
        except FileNotFoundError:
            # Ping command not available (maybe on Railway)
            return {
                'status': 'unavailable',
                'message': 'Ping not available',
                'emoji': '⚠️'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)[:50],
                'emoji': '❌'
            }
    
    async def check_docker(self) -> Dict[str, Any]:
        """Check Docker daemon connectivity."""
        try:
            result = subprocess.run(
                ['docker', 'version', '--format', '{{.Server.Version}}'],
                capture_output=True,
                text=True,
                timeout=3
            )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                
                # Get container count
                ps_result = subprocess.run(
                    ['docker', 'ps', '-q'],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                
                container_count = len(ps_result.stdout.strip().split('\n')) if ps_result.stdout.strip() else 0
                
                return {
                    'status': 'connected',
                    'message': f'v{version}, {container_count} containers',
                    'emoji': '🐳',
                    'version': version,
                    'containers_running': container_count
                }
            else:
                return {
                    'status': 'not_running',
                    'message': 'Docker daemon not accessible',
                    'emoji': '❌'
                }
                
        except FileNotFoundError:
            return {
                'status': 'not_installed',
                'message': 'Docker not installed',
                'emoji': '⚠️'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)[:50],
                'emoji': '❌'
            }
    
    async def check_storage(self) -> Dict[str, Any]:
        """Check storage/bucket connectivity."""
        bucket_url = os.environ.get('STORAGE_BUCKET_URL')
        
        if not bucket_url:
            # Check local storage
            try:
                data_path = self.config.DATABASE_PATH
                if os.path.exists(data_path):
                    size = os.path.getsize(data_path)
                    return {
                        'status': 'local',
                        'message': f'Local DB: {size/1024:.1f}KB',
                        'emoji': '💾',
                        'type': 'sqlite'
                    }
            except:
                pass
            
            return {
                'status': 'local_only',
                'message': 'No cloud storage configured',
                'emoji': '💾'
            }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(bucket_url, timeout=aiohttp.ClientTimeout(total=3)) as response:
                    if response.status < 400:
                        return {
                            'status': 'connected',
                            'message': 'Cloud storage accessible',
                            'emoji': '☁️'
                        }
                    else:
                        return {
                            'status': 'error',
                            'message': f'HTTP {response.status}',
                            'emoji': '❌'
                        }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)[:50],
                'emoji': '❌'
            }
    
    async def check_n8n(self) -> Dict[str, Any]:
        """Check n8n workflow automation connection."""
        n8n_url = os.environ.get('N8N_WEBHOOK_URL') or os.environ.get('N8N_API_URL')
        
        if not n8n_url:
            return {
                'status': 'not_configured',
                'message': 'n8n URL not set',
                'emoji': '⚠️'
            }
        
        try:
            async with aiohttp.ClientSession() as session:
                # Extract base URL from webhook URL
                import urllib.parse
                parsed = urllib.parse.urlparse(n8n_url)
                base_url = f"{parsed.scheme}://{parsed.netloc}"
                
                async with session.get(
                    f"{base_url}/healthz",
                    timeout=aiohttp.ClientTimeout(total=3)
                ) as response:
                    if response.status == 200:
                        return {
                            'status': 'connected',
                            'message': 'Workflows available',
                            'emoji': '🔄'
                        }
                    else:
                        return {
                            'status': 'error',
                            'message': f'HTTP {response.status}',
                            'emoji': '❌'
                        }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)[:50],
                'emoji': '❌'
            }
    
    async def check_mcp(self) -> Dict[str, Any]:
        """Check MCP (Model Context Protocol) connection."""
        mcp_endpoint = os.environ.get('MCP_ENDPOINT')
        
        if not mcp_endpoint:
            return {
                'status': 'not_configured',
                'message': 'MCP endpoint not set',
                'emoji': '⚠️'
            }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{mcp_endpoint}/status",
                    timeout=aiohttp.ClientTimeout(total=3)
                ) as response:
                    if response.status == 200:
                        return {
                            'status': 'connected',
                            'message': 'MCP server online',
                            'emoji': '🔌'
                        }
                    else:
                        return {
                            'status': 'error',
                            'message': f'HTTP {response.status}',
                            'emoji': '❌'
                        }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)[:50],
                'emoji': '❌'
            }
    
    async def check_creator_apis(self) -> Dict[str, Any]:
        """Check creator module APIs (image generation, etc.)."""
        apis_status = {}
        
        # Check DALL-E / OpenAI
        if os.environ.get('OPENAI_API_KEY'):
            apis_status['openai'] = '✅'
        else:
            apis_status['openai'] = '⚠️'
        
        # Check Stability AI
        if os.environ.get('STABILITY_API_KEY'):
            apis_status['stability'] = '✅'
        else:
            apis_status['stability'] = '⚠️'
        
        # Check Replicate
        if os.environ.get('REPLICATE_API_TOKEN'):
            apis_status['replicate'] = '✅'
        else:
            apis_status['replicate'] = '⚠️'
        
        configured_count = sum(1 for v in apis_status.values() if v == '✅')
        
        return {
            'status': 'partial' if configured_count > 0 else 'not_configured',
            'message': f'{configured_count}/3 APIs configured',
            'emoji': '🎨' if configured_count > 0 else '⚠️',
            'apis': apis_status
        }
    
    async def check_database(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            db_path = self.config.DATABASE_PATH
            
            if os.path.exists(db_path):
                # Get database size and stats
                size = os.path.getsize(db_path)
                
                # Try to connect and get table count
                import aiosqlite
                async with aiosqlite.connect(db_path) as db:
                    cursor = await db.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                    )
                    table_count = (await cursor.fetchone())[0]
                    
                    # Get user count
                    try:
                        cursor = await db.execute("SELECT COUNT(*) FROM users")
                        user_count = (await cursor.fetchone())[0]
                    except:
                        user_count = 0
                
                return {
                    'status': 'connected',
                    'message': f'{table_count} tables, {user_count} users',
                    'emoji': '✅',
                    'size_kb': round(size / 1024, 2),
                    'tables': table_count,
                    'users': user_count
                }
            else:
                return {
                    'status': 'not_found',
                    'message': 'Database file not found',
                    'emoji': '⚠️'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)[:50],
                'emoji': '❌'
            }
    
    async def check_network(self) -> Dict[str, Any]:
        """Check general network connectivity."""
        try:
            # Try to reach Google DNS
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://1.1.1.1/dns-query',
                    timeout=aiohttp.ClientTimeout(total=3)
                ) as response:
                    if response.status < 400:
                        return {
                            'status': 'connected',
                            'message': 'Internet accessible',
                            'emoji': '🌐'
                        }
                    else:
                        return {
                            'status': 'limited',
                            'message': 'Limited connectivity',
                            'emoji': '⚠️'
                        }
        except Exception as e:
            return {
                'status': 'error',
                'message': 'No internet connection',
                'emoji': '❌'
            }
    
    def format_status_message(self, results: Dict[str, Any]) -> str:
        """Format the status results as a readable message."""
        lines = [
            "🖥️ **Comprehensive System Status**",
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            ""
        ]
        
        # Bot information
        uptime = results.get('uptime', {})
        bot_info = results.get('bot_info', {})
        
        lines.extend([
            "**🤖 Bot Information**",
            f"• Version: {bot_info.get('version', 'unknown')}",
            f"• Uptime: {uptime.get('formatted', 'unknown')}",
            f"• Environment: {bot_info.get('environment', 'unknown')}",
            f"• Python: {bot_info.get('python_version', 'unknown')}",
            f"• PID: {bot_info.get('pid', 'unknown')}",
            ""
        ])
        
        # System resources
        system = results.get('system', {})
        if 'error' not in system:
            cpu = system.get('cpu', {})
            memory = system.get('memory', {})
            disk = system.get('disk', {})
            
            lines.extend([
                "**💻 System Resources**",
                f"• CPU: {cpu.get('percent', 0):.1f}% ({cpu.get('cores', 0)} cores) {cpu.get('status', '❓')}",
                f"• Memory: {memory.get('percent', 0):.1f}% ({memory.get('used_gb', 0):.1f}/{memory.get('total_gb', 0):.1f}GB) {memory.get('status', '❓')}",
                f"• Disk: {disk.get('percent', 0):.1f}% ({disk.get('used_gb', 0):.1f}/{disk.get('total_gb', 0):.1f}GB) {disk.get('status', '❓')}",
                ""
            ])
        
        # Connection statuses
        lines.append("**🔌 Service Connections**")
        
        connections = results.get('connections', {})
        
        # Define display order and names
        connection_display = [
            ('telegram', '📱 Telegram API'),
            ('openrouter', '🧠 AI (OpenRouter)'),
            ('database', '💾 Database'),
            ('docker', '🐳 Docker'),
            ('vps_ssh', '🖥️ VPS/SSH'),
            ('storage', '☁️ Storage'),
            ('n8n', '🔄 n8n Workflows'),
            ('mcp', '🔌 MCP Server'),
            ('creator_apis', '🎨 Creator APIs'),
            ('network', '🌐 Internet')
        ]
        
        for key, display_name in connection_display:
            if key in connections:
                conn = connections[key]
                emoji = conn.get('emoji', '❓')
                status = conn.get('status', 'unknown')
                message = conn.get('message', '')
                
                # Format status
                if status == 'connected':
                    status_text = 'Connected'
                elif status == 'not_configured':
                    status_text = 'Not configured'
                elif status == 'error':
                    status_text = 'Error'
                elif status == 'timeout':
                    status_text = 'Timeout'
                else:
                    status_text = status.replace('_', ' ').title()
                
                lines.append(f"• {display_name}: {emoji} {status_text} - {message}")
        
        lines.append("")
        
        # Feature flags
        features = bot_info.get('features', {})
        lines.extend([
            "**⚙️ Feature Status**",
            f"• AI Conversation: {'✅ Enabled' if features.get('ai_enabled') else '⚠️ Disabled (add OPENROUTER_API_KEY)'}",
            f"• Docker Support: {'✅ Enabled' if features.get('docker_enabled') else '⚠️ Disabled'}",
            f"• Metrics Collection: {'✅ Enabled' if features.get('metrics_enabled') else '⚠️ Disabled'}",
            ""
        ])
        
        # Overall health
        total_connections = len(connections)
        connected_count = sum(1 for c in connections.values() if c.get('status') == 'connected')
        configured_count = sum(1 for c in connections.values() if c.get('status') not in ['not_configured', 'error', 'timeout'])
        
        if connected_count == total_connections:
            overall_status = "✅ All systems operational"
        elif connected_count >= total_connections * 0.7:
            overall_status = "🟡 Partially operational"
        elif connected_count >= total_connections * 0.3:
            overall_status = "🟠 Degraded performance"
        else:
            overall_status = "🔴 Major issues detected"
        
        lines.extend([
            "**📊 Overall Status**",
            f"• Health: {overall_status}",
            f"• Services: {connected_count}/{configured_count} connected",
            f"• Uptime: {uptime.get('formatted', 'unknown')}"
        ])
        
        return "\n".join(lines)
