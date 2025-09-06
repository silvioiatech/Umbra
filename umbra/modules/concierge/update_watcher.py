"""
Concierge Auto-Update Watcher - Docker Image Update Management
Provides scheduled scanning, planning, and execution of Docker image updates
with blue-green deployment for main service and maintenance windows for clients.
"""
import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Any, Tuple
import json
import hashlib
from dataclasses import dataclass, asdict
from enum import Enum

from ...core.config import UmbraConfig
from .docker_registry import DockerRegistryHelper
from .blue_green import BlueGreenManager
# from .update_clients import ClientUpdateManager  # Commented to avoid circular import


class UpdateStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class UpdatePlan:
    id: str
    service_name: str
    current_digest: str
    target_digest: str
    target_tag: str
    risk_level: RiskLevel
    steps: List[Dict[str, Any]]
    estimated_duration: int  # seconds
    created_at: datetime
    requires_double_confirm: bool
    rollback_plan: Optional[Dict[str, Any]] = None


@dataclass
class ScanResult:
    service_name: str
    current_tag: str
    current_digest: str
    available_tag: str
    available_digest: str
    needs_update: bool
    risk_level: RiskLevel
    release_notes: Optional[str] = None
    changelog_url: Optional[str] = None


class UpdateWatcher:
    """Main auto-update watcher with scheduling and plan management."""
    
    def __init__(self, config: UmbraConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Core components
        self.registry_helper = DockerRegistryHelper(config)
        self.blue_green = BlueGreenManager(config)
        self.client_manager = ClientUpdateManager(config)
        
        # State management
        self.active_plans: Dict[str, UpdatePlan] = {}
        self.scan_results: Dict[str, ScanResult] = {}
        self.last_scan: Optional[datetime] = None
        self.scheduler_task: Optional[asyncio.Task] = None
        
        # Configuration
        self.check_times = self._parse_check_times()
        self.main_service = config.get('MAIN_SERVICE', 'n8n-main')
        self.maintenance_windows = config.get('MAINTENANCE_WINDOWS', {})
        self.freeze_list = set(config.get('FREEZE_LIST', []))
        self.require_double_confirm = config.get('REQUIRE_DOUBLE_CONFIRM_ON_MAJOR', True)
        
        self.logger.info(f"UpdateWatcher initialized for service '{self.main_service}'")
        self.logger.info(f"Scheduled scans at: {[t.strftime('%H:%M') for t in self.check_times]} Europe/Zurich")

    def _parse_check_times(self) -> List[time]:
        """Parse check times from config."""
        check_times_str = self.config.get('UPDATES_CHECKS_AT', ['07:00', '19:00'])
        times = []
        
        for time_str in check_times_str:
            try:
                hour, minute = map(int, time_str.split(':'))
                times.append(time(hour, minute))
            except (ValueError, AttributeError):
                self.logger.warning(f"Invalid check time format: {time_str}, skipping")
        
        if not times:
            # Fallback to default times
            times = [time(7, 0), time(19, 0)]
            self.logger.warning("No valid check times found, using defaults: 07:00, 19:00")
        
        return times

    async def start_scheduler(self):
        """Start the automatic update scheduler."""
        if self.scheduler_task and not self.scheduler_task.done():
            self.logger.warning("Scheduler already running")
            return
            
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        self.logger.info("Update scheduler started")

    async def stop_scheduler(self):
        """Stop the automatic update scheduler."""
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
            self.logger.info("Update scheduler stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop that runs automatic scans."""
        while True:
            try:
                next_scan_time = self._get_next_scan_time()
                wait_seconds = (next_scan_time - datetime.now()).total_seconds()
                
                if wait_seconds > 0:
                    self.logger.debug(f"Next scan scheduled for {next_scan_time.strftime('%Y-%m-%d %H:%M')} Europe/Zurich")
                    await asyncio.sleep(wait_seconds)
                
                # Perform automatic scan
                self.logger.info("Starting scheduled update scan")
                await self.scan()
                
                # Process any automatic updates based on policies
                await self._process_automatic_updates()
                
            except asyncio.CancelledError:
                self.logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}")
                # Wait 5 minutes before retrying on error
                await asyncio.sleep(300)

    def _get_next_scan_time(self) -> datetime:
        """Calculate the next scan time based on configured schedule."""
        now = datetime.now()
        today_times = [datetime.combine(now.date(), t) for t in self.check_times]
        
        # Find next future time today
        future_times = [t for t in today_times if t > now]
        if future_times:
            return min(future_times)
        
        # If no more times today, use first time tomorrow
        tomorrow = now.date() + timedelta(days=1)
        return datetime.combine(tomorrow, self.check_times[0])

    async def scan(self) -> Dict[str, ScanResult]:
        """Scan for available updates across all services."""
        self.logger.info("Starting update scan")
        
        try:
            # Scan main service
            main_result = await self._scan_service(self.main_service)
            if main_result:
                self.scan_results[self.main_service] = main_result
            
            # Scan client services
            client_services = await self.client_manager.list_client_services()
            for service_name in client_services:
                if service_name not in self.freeze_list:
                    client_result = await self._scan_service(service_name)
                    if client_result:
                        self.scan_results[service_name] = client_result
            
            self.last_scan = datetime.now()
            
            # Log scan summary
            updates_available = sum(1 for r in self.scan_results.values() if r.needs_update)
            self.logger.info(f"Scan completed: {updates_available} services have updates available")
            
            return self.scan_results
            
        except Exception as e:
            self.logger.error(f"Error during scan: {e}")
            raise

    async def _scan_service(self, service_name: str) -> Optional[ScanResult]:
        """Scan a single service for updates."""
        try:
            # Get current image info
            current_info = await self.registry_helper.get_current_image_info(service_name)
            if not current_info:
                self.logger.warning(f"Could not get current image info for {service_name}")
                return None
            
            current_tag = current_info['tag']
            current_digest = current_info['digest']
            
            # Get remote image info
            remote_info = await self.registry_helper.get_remote_image_info(
                current_info['repository'], current_tag
            )
            if not remote_info:
                self.logger.warning(f"Could not get remote image info for {service_name}")
                return None
            
            available_digest = remote_info['digest']
            needs_update = current_digest != available_digest
            
            # Assess risk level
            risk_level = await self._assess_update_risk(
                service_name, current_tag, current_info['repository']
            )
            
            # Get release notes if available
            release_notes = None
            changelog_url = None
            if needs_update:
                release_notes, changelog_url = await self.registry_helper.get_release_info(
                    current_info['repository'], current_tag
                )
            
            return ScanResult(
                service_name=service_name,
                current_tag=current_tag,
                current_digest=current_digest,
                available_tag=current_tag,  # Same tag, different digest
                available_digest=available_digest,
                needs_update=needs_update,
                risk_level=risk_level,
                release_notes=release_notes,
                changelog_url=changelog_url
            )
            
        except Exception as e:
            self.logger.error(f"Error scanning service {service_name}: {e}")
            return None

    async def _assess_update_risk(self, service_name: str, current_tag: str, repository: str) -> RiskLevel:
        """Assess the risk level of an update."""
        try:
            # Get version info from tags
            version_info = await self.registry_helper.parse_version_info(current_tag, repository)
            
            if not version_info:
                return RiskLevel.MEDIUM  # Unknown version, medium risk
            
            current_major = version_info.get('major', 0)
            current_minor = version_info.get('minor', 0)
            
            # Check for version jumps
            if version_info.get('major_jump', False):
                return RiskLevel.CRITICAL
            elif version_info.get('minor_jump', False) and current_major >= 1:
                return RiskLevel.HIGH
            elif version_info.get('patch_jump', False):
                return RiskLevel.LOW
            else:
                return RiskLevel.LOW  # Patch updates or same version
                
        except Exception as e:
            self.logger.warning(f"Could not assess risk for {service_name}: {e}")
            return RiskLevel.MEDIUM

    async def plan_main_blue_green(self, target_tag: Optional[str] = None, 
                                 target_digest: Optional[str] = None) -> UpdatePlan:
        """Create an update plan for the main service using blue-green deployment."""
        service_name = self.main_service
        
        # Get current service info
        current_info = await self.registry_helper.get_current_image_info(service_name)
        if not current_info:
            raise ValueError(f"Could not get current info for {service_name}")
        
        # Determine target
        if target_digest:
            target_info = {'digest': target_digest, 'tag': target_tag or current_info['tag']}
        elif target_tag:
            target_info = await self.registry_helper.get_remote_image_info(
                current_info['repository'], target_tag
            )
            if not target_info:
                raise ValueError(f"Could not resolve tag {target_tag}")
        else:
            # Use latest available from scan
            if service_name in self.scan_results:
                scan_result = self.scan_results[service_name]
                target_info = {
                    'digest': scan_result.available_digest,
                    'tag': scan_result.available_tag
                }
            else:
                raise ValueError("No target specified and no scan results available")
        
        # Assess risk
        risk_level = await self._assess_update_risk(
            service_name, target_info['tag'], current_info['repository']
        )
        
        # Create plan steps
        steps = await self.blue_green.create_deployment_steps(
            service_name=service_name,
            current_digest=current_info['digest'],
            target_digest=target_info['digest'],
            target_tag=target_info['tag']
        )
        
        # Create rollback plan
        rollback_plan = await self.blue_green.create_rollback_steps(
            service_name=service_name,
            rollback_digest=current_info['digest']
        )
        
        # Generate plan ID
        plan_data = f"{service_name}:{current_info['digest']}:{target_info['digest']}"
        plan_id = hashlib.md5(plan_data.encode()).hexdigest()[:8]
        
        plan = UpdatePlan(
            id=plan_id,
            service_name=service_name,
            current_digest=current_info['digest'],
            target_digest=target_info['digest'],
            target_tag=target_info['tag'],
            risk_level=risk_level,
            steps=steps,
            estimated_duration=await self._estimate_duration(steps),
            created_at=datetime.now(),
            requires_double_confirm=risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL],
            rollback_plan=rollback_plan
        )
        
        self.active_plans[plan_id] = plan
        
        self.logger.info(f"Created blue-green update plan {plan_id} for {service_name}")
        self.logger.info(f"Risk level: {risk_level.value}, Steps: {len(steps)}, Duration: ~{plan.estimated_duration}s")
        
        return plan

    async def plan_client(self, client_name: str, when: str = "window") -> UpdatePlan:
        """Create an update plan for a client service."""
        return await self.client_manager.create_client_plan(client_name, when)

    async def apply(self, plan_id: str, confirmed: bool = False, 
                   double_confirmed: bool = False) -> Dict[str, Any]:
        """Apply an update plan."""
        if plan_id not in self.active_plans:
            raise ValueError(f"Plan {plan_id} not found")
        
        plan = self.active_plans[plan_id]
        
        # Check confirmations
        if not confirmed:
            raise ValueError("Plan execution requires confirmation")
        
        if plan.requires_double_confirm and not double_confirmed:
            raise ValueError("This plan requires double confirmation due to high risk")
        
        self.logger.info(f"Applying update plan {plan_id} for {plan.service_name}")
        
        try:
            if plan.service_name == self.main_service:
                # Use blue-green deployment
                result = await self.blue_green.execute_deployment(plan)
            else:
                # Use client update manager
                result = await self.client_manager.execute_client_update(plan)
            
            self.logger.info(f"Update plan {plan_id} completed successfully")
            return result
            
        except Exception as e:
            self.logger.error(f"Update plan {plan_id} failed: {e}")
            
            # Attempt automatic rollback
            if plan.rollback_plan:
                try:
                    self.logger.info(f"Attempting automatic rollback for plan {plan_id}")
                    await self._execute_rollback(plan)
                except Exception as rollback_error:
                    self.logger.error(f"Rollback failed for plan {plan_id}: {rollback_error}")
            
            raise

    async def rollback(self, service_name: str) -> Dict[str, Any]:
        """Rollback a service to its previous version."""
        self.logger.info(f"Rolling back service {service_name}")
        
        if service_name == self.main_service:
            return await self.blue_green.rollback_service(service_name)
        else:
            return await self.client_manager.rollback_client(service_name)

    async def _execute_rollback(self, plan: UpdatePlan) -> Dict[str, Any]:
        """Execute rollback for a failed plan."""
        if not plan.rollback_plan:
            raise ValueError("No rollback plan available")
        
        if plan.service_name == self.main_service:
            return await self.blue_green.execute_rollback(plan.rollback_plan)
        else:
            return await self.client_manager.execute_rollback(plan.rollback_plan)

    async def freeze(self, service_name: str, frozen: bool = True) -> Dict[str, Any]:
        """Freeze or unfreeze a service from automatic updates."""
        if frozen:
            self.freeze_list.add(service_name)
            action = "frozen"
        else:
            self.freeze_list.discard(service_name)
            action = "unfrozen"
        
        self.logger.info(f"Service {service_name} {action}")
        
        # Save to persistent config if available
        # This would normally update a config file or database
        
        return {
            "service_name": service_name,
            "frozen": frozen,
            "freeze_list": list(self.freeze_list)
        }

    async def set_maintenance_window(self, service_name: str, window: str) -> Dict[str, Any]:
        """Set maintenance window for a service (format: "HH:MM-HH:MM")."""
        # Validate window format
        try:
            start_str, end_str = window.split('-')
            start_hour, start_min = map(int, start_str.split(':'))
            end_hour, end_min = map(int, end_str.split(':'))
            
            # Validate time ranges
            if not (0 <= start_hour <= 23 and 0 <= start_min <= 59):
                raise ValueError("Invalid start time")
            if not (0 <= end_hour <= 23 and 0 <= end_min <= 59):
                raise ValueError("Invalid end time")
                
        except (ValueError, IndexError):
            raise ValueError("Invalid window format. Use 'HH:MM-HH:MM'")
        
        self.maintenance_windows[service_name] = window
        
        self.logger.info(f"Set maintenance window for {service_name}: {window}")
        
        return {
            "service_name": service_name,
            "window": window,
            "maintenance_windows": self.maintenance_windows
        }

    async def _process_automatic_updates(self):
        """Process any updates that can be applied automatically based on policies."""
        # This would implement automatic update policies
        # For now, we just log that automatic processing would happen here
        
        auto_updates = []
        for service_name, scan_result in self.scan_results.items():
            if not scan_result.needs_update:
                continue
                
            if service_name in self.freeze_list:
                continue
                
            # Only auto-apply low-risk updates for now
            if scan_result.risk_level == RiskLevel.LOW:
                # Check if we're in maintenance window for clients
                if service_name != self.main_service:
                    if not await self.client_manager.is_in_maintenance_window(service_name):
                        continue
                
                auto_updates.append(service_name)
        
        if auto_updates:
            self.logger.info(f"Services eligible for automatic update: {auto_updates}")
            # In a real implementation, we might auto-apply low-risk updates
            # For safety, we'll just log for now

    async def _estimate_duration(self, steps: List[Dict[str, Any]]) -> int:
        """Estimate duration for a set of steps."""
        # Simple estimation based on step types
        duration = 0
        
        for step in steps:
            step_type = step.get('type', '')
            
            if step_type == 'pull_image':
                duration += 120  # 2 minutes for image pull
            elif step_type == 'start_container':
                duration += 30   # 30 seconds to start
            elif step_type == 'health_check':
                duration += 60   # 1 minute for health checks
            elif step_type == 'switch_nginx':
                duration += 10   # 10 seconds for nginx reload
            elif step_type == 'stop_container':
                duration += 15   # 15 seconds to stop
            else:
                duration += 30   # Default 30 seconds
        
        return duration

    def get_scan_results(self) -> Dict[str, ScanResult]:
        """Get the latest scan results."""
        return self.scan_results.copy()

    def get_active_plans(self) -> Dict[str, UpdatePlan]:
        """Get all active update plans."""
        return self.active_plans.copy()

    def get_status(self) -> Dict[str, Any]:
        """Get overall update watcher status."""
        return {
            "scheduler_running": self.scheduler_task is not None and not self.scheduler_task.done(),
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "next_scan": self._get_next_scan_time().isoformat(),
            "check_times": [t.strftime('%H:%M') for t in self.check_times],
            "active_plans": len(self.active_plans),
            "services_with_updates": sum(1 for r in self.scan_results.values() if r.needs_update),
            "frozen_services": list(self.freeze_list),
            "maintenance_windows": self.maintenance_windows
        }
