    async def _handle_updates_action(self, action: str, params: Dict[str, Any], user_id: int, is_admin: bool) -> Dict[str, Any]:
        """Handle auto-update watcher actions."""
        
        if action == "updates.scan":
            force = params.get("force", False)
            
            try:
                # Skip scan if recent one exists and not forced
                if not force and self.update_watcher.last_scan:
                    from datetime import datetime, timedelta
                    if datetime.now() - self.update_watcher.last_scan < timedelta(minutes=30):
                        return {
                            "success": True,
                            "message": "Recent scan available, use force=true to rescan",
                            "scan_results": self.update_watcher.get_scan_results(),
                            "last_scan": self.update_watcher.last_scan.isoformat()
                        }
                
                # Perform scan
                scan_results = await self.update_watcher.scan()
                
                # Format results
                formatted_results = {}
                for service_name, result in scan_results.items():
                    formatted_results[service_name] = {
                        "current_digest": result.current_digest[:12] + "...",
                        "available_digest": result.available_digest[:12] + "...",
                        "needs_update": result.needs_update,
                        "risk_level": result.risk_level.value,
                        "release_notes": result.release_notes
                    }
                
                updates_available = sum(1 for r in scan_results.values() if r.needs_update)
                
                return {
                    "success": True,
                    "scan_results": formatted_results,
                    "summary": {
                        "services_scanned": len(scan_results),
                        "updates_available": updates_available,
                        "last_scan": self.update_watcher.last_scan.isoformat()
                    }
                }
                
            except Exception as e:
                return {"success": False, "error": f"Scan failed: {str(e)}"}
        
        elif action == "updates.plan_main":
            target_tag = params.get("target_tag")
            target_digest = params.get("target_digest")
            
            try:
                plan = await self.update_watcher.plan_main_blue_green(target_tag, target_digest)
                
                return {
                    "success": True,
                    "plan": {
                        "id": plan.id,
                        "service_name": plan.service_name,
                        "target_tag": plan.target_tag,
                        "risk_level": plan.risk_level.value,
                        "steps_count": len(plan.steps),
                        "estimated_duration": plan.estimated_duration,
                        "requires_double_confirm": plan.requires_double_confirm,
                        "created_at": plan.created_at.isoformat()
                    },
                    "steps_preview": [{
                        "id": step["id"],
                        "description": step["description"],
                        "timeout": step["timeout"]
                    } for step in plan.steps[:5]]  # Show first 5 steps
                }
                
            except Exception as e:
                return {"success": False, "error": f"Plan creation failed: {str(e)}"}
        
        elif action == "updates.plan_client":
            client_name = params.get("client_name", "").strip()
            when = params.get("when", "window")
            
            if not client_name:
                return {"success": False, "error": "Client name required"}
            
            try:
                plan = await self.update_watcher.plan_client(client_name, when)
                
                return {
                    "success": True,
                    "plan": {
                        "id": plan.id,
                        "client_name": plan.service_name,
                        "target_tag": plan.target_tag,
                        "risk_level": plan.risk_level.value,
                        "steps_count": len(plan.steps),
                        "estimated_duration": plan.estimated_duration,
                        "requires_double_confirm": plan.requires_double_confirm,
                        "scheduled_for": when
                    }
                }
                
            except Exception as e:
                return {"success": False, "error": f"Client plan creation failed: {str(e)}"}
        
        elif action == "updates.apply":
            plan_id = params.get("plan_id", "").strip()
            confirmed = params.get("confirmed", False)
            double_confirmed = params.get("double_confirmed", False)
            
            if not plan_id:
                return {"success": False, "error": "Plan ID required"}
            
            if not confirmed:
                return {
                    "success": False,
                    "error": "Plan execution requires confirmation",
                    "confirmation_required": True
                }
            
            try:
                result = await self.update_watcher.apply(plan_id, confirmed, double_confirmed)
                
                return {
                    "success": True,
                    "execution_result": {
                        "deployment_id": result.get("deployment_id"),
                        "success": result.get("success"),
                        "steps_completed": len(result.get("steps", [])),
                        "duration": result.get("completed_at", 0) - result.get("started_at", 0)
                    },
                    "message": "Update applied successfully" if result.get("success") else "Update failed"
                }
                
            except Exception as e:
                return {"success": False, "error": f"Update application failed: {str(e)}"}
        
        elif action == "updates.rollback":
            service_name = params.get("service_name", "").strip()
            
            if not service_name:
                return {"success": False, "error": "Service name required"}
            
            try:
                result = await self.update_watcher.rollback(service_name)
                
                return {
                    "success": True,
                    "rollback_result": result,
                    "message": f"Service {service_name} rolled back successfully"
                }
                
            except Exception as e:
                return {"success": False, "error": f"Rollback failed: {str(e)}"}
        
        elif action == "updates.freeze":
            service_name = params.get("service_name", "").strip()
            frozen = params.get("frozen", True)
            
            if not service_name:
                return {"success": False, "error": "Service name required"}
            
            try:
                result = await self.update_watcher.freeze(service_name, frozen)
                
                return {
                    "success": True,
                    "result": result,
                    "message": f"Service {service_name} {'frozen' if frozen else 'unfrozen'}"
                }
                
            except Exception as e:
                return {"success": False, "error": f"Freeze operation failed: {str(e)}"}
        
        elif action == "updates.window":
            service_name = params.get("service_name", "").strip()
            window = params.get("window", "").strip()
            
            if not service_name or not window:
                return {"success": False, "error": "Service name and window required"}
            
            try:
                result = await self.update_watcher.set_maintenance_window(service_name, window)
                
                return {
                    "success": True,
                    "result": result,
                    "message": f"Maintenance window set for {service_name}: {window}"
                }
                
            except Exception as e:
                return {"success": False, "error": f"Window setting failed: {str(e)}"}
        
        elif action == "updates.status":
            try:
                status = self.update_watcher.get_status()
                scan_results = self.update_watcher.get_scan_results()
                active_plans = self.update_watcher.get_active_plans()
                
                # Format scan results summary
                scan_summary = {}
                for service_name, result in scan_results.items():
                    scan_summary[service_name] = {
                        "needs_update": result.needs_update,
                        "risk_level": result.risk_level.value
                    }
                
                return {
                    "success": True,
                    "status": status,
                    "scan_summary": scan_summary,
                    "active_plans": {
                        "count": len(active_plans),
                        "plans": [{
                            "id": plan.id,
                            "service": plan.service_name,
                            "risk": plan.risk_level.value
                        } for plan in active_plans.values()]
                    }
                }
                
            except Exception as e:
                return {"success": False, "error": f"Status retrieval failed: {str(e)}"}
        
        elif action == "updates.start_scheduler":
            try:
                await self.update_watcher.start_scheduler()
                
                return {
                    "success": True,
                    "message": "Update scheduler started",
                    "next_scan": self.update_watcher._get_next_scan_time().isoformat()
                }
                
            except Exception as e:
                return {"success": False, "error": f"Scheduler start failed: {str(e)}"}
        
        elif action == "updates.stop_scheduler":
            try:
                await self.update_watcher.stop_scheduler()
                
                return {
                    "success": True,
                    "message": "Update scheduler stopped"
                }
                
            except Exception as e:
                return {"success": False, "error": f"Scheduler stop failed: {str(e)}"}
        
        return {"success": False, "error": f"Unknown updates action: {action}"}
