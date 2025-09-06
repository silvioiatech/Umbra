"""
Workflow Tester for Production Module

Tests n8n workflows with sample data and validates execution results
before production deployment.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import uuid

from ...core.config import UmbraConfig
from .n8n_client import N8nClient

logger = logging.getLogger(__name__)

@dataclass
class TestExecution:
    """Represents a workflow test execution"""
    test_id: str
    workflow_id: str
    test_data: Optional[Dict[str, Any]]
    start_time: float
    end_time: Optional[float] = None
    status: str = "running"  # running, success, failed, timeout
    execution_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None

@dataclass
class TestResult:
    """Complete test result with analysis"""
    execution: TestExecution
    node_results: List[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    performance_metrics: Dict[str, Any]
    success: bool
    issues: List[str]

class WorkflowTester:
    """Tests workflow execution with sample data"""
    
    def __init__(self, n8n_client: N8nClient, config: UmbraConfig):
        self.n8n_client = n8n_client
        self.config = config
        
        # Test configuration
        self.default_timeout = config.get("PROD_TEST_TIMEOUT_S", 60)
        self.max_parallel_tests = config.get("PROD_MAX_PARALLEL_TESTS", 3)
        
        # Test data generators
        self.test_data_generators = self._initialize_test_generators()
        
        logger.info("Workflow tester initialized")
    
    def _initialize_test_generators(self) -> Dict[str, callable]:
        """Initialize test data generators for different node types"""
        return {
            "webhook": self._generate_webhook_test_data,
            "http": self._generate_http_test_data,
            "email": self._generate_email_test_data,
            "json": self._generate_json_test_data,
            "set": self._generate_set_test_data,
            "if": self._generate_condition_test_data,
            "code": self._generate_code_test_data
        }
    
    async def test_run_workflow(self, workflow_json: Dict[str, Any], payload: Optional[Dict[str, Any]] = None, timeout_s: int = 60) -> Dict[str, Any]:
        """Test run workflow with optional payload"""
        try:
            # Generate test ID
            test_id = f"test_{uuid.uuid4().hex[:8]}"
            
            # Create temporary test workflow
            test_workflow = await self._prepare_test_workflow(workflow_json)
            
            # Generate test data if not provided
            if payload is None:
                payload = await self._generate_test_payload(workflow_json)
            
            # Create test execution record
            execution = TestExecution(
                test_id=test_id,
                workflow_id=test_workflow["id"],
                test_data=payload,
                start_time=time.time()
            )
            
            # Execute test
            test_result = await self._execute_test(execution, test_workflow, payload, timeout_s)
            
            # Clean up test workflow
            await self._cleanup_test_workflow(test_workflow["id"])
            
            return {
                "test_id": test_id,
                "status": test_result.execution.status,
                "success": test_result.success,
                "duration_ms": test_result.execution.duration_ms,
                "output": test_result.output_data,
                "performance": test_result.performance_metrics,
                "issues": test_result.issues,
                "execution_id": test_result.execution.execution_id
            }
            
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return {
                "status": "failed",
                "success": False,
                "error": str(e)
            }
    
    async def _prepare_test_workflow(self, workflow_json: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare workflow for testing (create temporary copy)"""
        test_workflow = workflow_json.copy()
        
        # Modify for testing
        original_name = test_workflow.get("name", "Workflow")
        test_workflow["name"] = f"TEST_{original_name}_{uuid.uuid4().hex[:8]}"
        test_workflow["active"] = False  # Keep inactive during testing
        
        # Add test metadata
        test_workflow.setdefault("meta", {})
        test_workflow["meta"]["x_test_workflow"] = True
        test_workflow["meta"]["x_original_name"] = original_name
        
        # Create in n8n
        created_workflow = await self.n8n_client.create_workflow(test_workflow)
        
        return created_workflow
    
    async def _generate_test_payload(self, workflow_json: Dict[str, Any]) -> Dict[str, Any]:
        """Generate appropriate test payload based on workflow structure"""
        nodes = workflow_json.get("nodes", [])
        
        # Find trigger nodes
        trigger_nodes = [
            node for node in nodes 
            if ("trigger" in node.get("type", "").lower() or
                "webhook" in node.get("type", "").lower())
        ]
        
        if not trigger_nodes:
            # Default test data for manual workflows
            return {
                "test": True,
                "timestamp": int(time.time()),
                "data": {"message": "Test execution"}
            }
        
        # Generate data based on trigger type
        trigger = trigger_nodes[0]
        trigger_type = trigger.get("type", "")
        
        if "webhook" in trigger_type.lower():
            return self._generate_webhook_test_data(trigger)
        elif "email" in trigger_type.lower():
            return self._generate_email_test_data(trigger)
        elif "file" in trigger_type.lower():
            return self._generate_file_test_data(trigger)
        else:
            # Generic test data
            return {
                "test": True,
                "trigger_type": trigger_type,
                "timestamp": int(time.time()),
                "sample_data": "Test execution data"
            }
    
    def _generate_webhook_test_data(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Generate webhook test data"""
        return {
            "headers": {
                "content-type": "application/json",
                "user-agent": "umbra-test-client"
            },
            "body": {
                "event": "test",
                "timestamp": int(time.time()),
                "data": {
                    "user_id": 12345,
                    "action": "test_action",
                    "message": "This is a test webhook payload"
                }
            },
            "query": {
                "test": "true",
                "source": "umbra"
            }
        }
    
    def _generate_http_test_data(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Generate HTTP request test data"""
        return {
            "url": "https://jsonplaceholder.typicode.com/posts/1",
            "method": "GET",
            "headers": {
                "Accept": "application/json"
            }
        }
    
    def _generate_email_test_data(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Generate email test data"""
        return {
            "from": "test@example.com",
            "to": "recipient@example.com",
            "subject": "Test Email from Workflow",
            "body": "This is a test email generated during workflow testing.",
            "attachments": []
        }
    
    def _generate_json_test_data(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Generate JSON processing test data"""
        return {
            "json_data": {
                "users": [
                    {"id": 1, "name": "Alice", "email": "alice@example.com"},
                    {"id": 2, "name": "Bob", "email": "bob@example.com"}
                ],
                "total": 2,
                "page": 1
            }
        }
    
    def _generate_set_test_data(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Generate data transformation test data"""
        return {
            "input_data": {
                "raw_value": "test_value",
                "number": 42,
                "boolean": True,
                "array": [1, 2, 3, 4, 5],
                "nested": {
                    "key": "value",
                    "timestamp": int(time.time())
                }
            }
        }
    
    def _generate_condition_test_data(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Generate conditional logic test data"""
        return {
            "condition_data": {
                "status": "active",
                "score": 85,
                "category": "premium",
                "enabled": True,
                "items": ["item1", "item2", "item3"]
            }
        }
    
    def _generate_code_test_data(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Generate code execution test data"""
        return {
            "code_input": {
                "numbers": [1, 2, 3, 4, 5],
                "text": "Hello World",
                "config": {
                    "debug": True,
                    "version": "1.0"
                }
            }
        }
    
    def _generate_file_test_data(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Generate file processing test data"""
        return {
            "file_data": {
                "filename": "test.txt",
                "content": "This is test file content for workflow testing",
                "mime_type": "text/plain",
                "size": 256
            }
        }
    
    async def _execute_test(self, execution: TestExecution, test_workflow: Dict[str, Any], payload: Dict[str, Any], timeout_s: int) -> TestResult:
        """Execute the actual test"""
        try:
            # Start workflow execution
            run_result = await self.n8n_client.run_workflow(
                test_workflow["id"],
                payload,
                timeout_s
            )
            
            execution.execution_id = run_result.get("exec_id")
            execution.status = run_result.get("status", "unknown")
            execution.end_time = time.time()
            execution.duration_ms = int((execution.end_time - execution.start_time) * 1000)
            
            # Analyze results
            if execution.status == "success":
                return await self._analyze_success_result(execution, run_result)
            elif execution.status == "timeout":
                return await self._analyze_timeout_result(execution, run_result)
            else:
                return await self._analyze_failure_result(execution, run_result)
                
        except Exception as e:
            execution.end_time = time.time()
            execution.duration_ms = int((execution.end_time - execution.start_time) * 1000)
            execution.status = "failed"
            execution.error = str(e)
            
            return TestResult(
                execution=execution,
                node_results=[],
                output_data=None,
                performance_metrics=self._calculate_performance_metrics(execution),
                success=False,
                issues=[f"Test execution failed: {e}"]
            )
    
    async def _analyze_success_result(self, execution: TestExecution, run_result: Dict[str, Any]) -> TestResult:
        """Analyze successful test execution"""
        issues = []
        
        # Extract execution data
        execution_data = run_result.get("data", {})
        node_results = self._extract_node_results(execution_data)
        output_data = self._extract_output_data(execution_data)
        
        # Performance analysis
        performance_metrics = self._calculate_performance_metrics(execution, execution_data)
        
        # Check for potential issues even in successful runs
        if execution.duration_ms and execution.duration_ms > 30000:  # 30 seconds
            issues.append("Workflow execution took longer than 30 seconds")
        
        # Check for empty results
        if not output_data or (isinstance(output_data, dict) and not output_data):
            issues.append("Workflow produced no output data")
        
        # Check for error nodes that didn't fail the workflow
        error_nodes = [nr for nr in node_results if nr.get("error")]
        if error_nodes:
            issues.append(f"Found {len(error_nodes)} nodes with errors despite successful execution")
        
        return TestResult(
            execution=execution,
            node_results=node_results,
            output_data=output_data,
            performance_metrics=performance_metrics,
            success=True,
            issues=issues
        )
    
    async def _analyze_timeout_result(self, execution: TestExecution, run_result: Dict[str, Any]) -> TestResult:
        """Analyze timed out test execution"""
        issues = [
            "Workflow execution timed out",
            f"Execution exceeded {self.default_timeout} seconds",
            "Consider optimizing workflow performance or increasing timeout"
        ]
        
        # Try to get partial results
        execution_data = run_result.get("data", {})
        node_results = self._extract_node_results(execution_data)
        
        # Find where it got stuck
        running_nodes = [nr for nr in node_results if nr.get("status") == "running"]
        if running_nodes:
            issues.append(f"Execution stuck at nodes: {[n.get('name') for n in running_nodes]}")
        
        return TestResult(
            execution=execution,
            node_results=node_results,
            output_data=None,
            performance_metrics=self._calculate_performance_metrics(execution),
            success=False,
            issues=issues
        )
    
    async def _analyze_failure_result(self, execution: TestExecution, run_result: Dict[str, Any]) -> TestResult:
        """Analyze failed test execution"""
        issues = ["Workflow execution failed"]
        
        # Extract error information
        error_msg = run_result.get("error", "Unknown error")
        execution.error = error_msg
        issues.append(f"Error: {error_msg}")
        
        # Extract execution data if available
        execution_data = run_result.get("data", {})
        node_results = self._extract_node_results(execution_data)
        
        # Find failed nodes
        failed_nodes = [nr for nr in node_results if nr.get("error")]
        for failed_node in failed_nodes:
            node_name = failed_node.get("name", "Unknown")
            node_error = failed_node.get("error", "Unknown error")
            issues.append(f"Node '{node_name}' failed: {node_error}")
        
        return TestResult(
            execution=execution,
            node_results=node_results,
            output_data=None,
            performance_metrics=self._calculate_performance_metrics(execution),
            success=False,
            issues=issues
        )
    
    def _extract_node_results(self, execution_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract individual node execution results"""
        node_results = []
        
        # n8n execution data structure varies, handle common formats
        if "data" in execution_data:
            execution_details = execution_data["data"]
        else:
            execution_details = execution_data
        
        # Extract from resultData if available
        result_data = execution_details.get("resultData", {})
        if "runData" in result_data:
            run_data = result_data["runData"]
            
            for node_name, node_executions in run_data.items():
                for i, execution_run in enumerate(node_executions):
                    node_result = {
                        "name": node_name,
                        "execution_index": i,
                        "start_time": execution_run.get("startTime"),
                        "execution_time": execution_run.get("executionTime"),
                        "data": execution_run.get("data"),
                        "error": execution_run.get("error")
                    }
                    node_results.append(node_result)
        
        return node_results
    
    def _extract_output_data(self, execution_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract final output data from execution"""
        try:
            # Try to get the final node's output
            if "data" in execution_data:
                execution_details = execution_data["data"]
                result_data = execution_details.get("resultData", {})
                
                if "lastNodeExecuted" in result_data:
                    last_node = result_data["lastNodeExecuted"]
                    run_data = result_data.get("runData", {})
                    
                    if last_node in run_data:
                        node_executions = run_data[last_node]
                        if node_executions:
                            last_execution = node_executions[-1]
                            return last_execution.get("data", {})
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to extract output data: {e}")
            return None
    
    def _calculate_performance_metrics(self, execution: TestExecution, execution_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate performance metrics"""
        metrics = {
            "total_duration_ms": execution.duration_ms,
            "status": execution.status
        }
        
        if execution_data:
            # Extract detailed timing if available
            try:
                execution_details = execution_data.get("data", {})
                result_data = execution_details.get("resultData", {})
                run_data = result_data.get("runData", {})
                
                node_times = []
                total_execution_time = 0
                
                for node_name, node_executions in run_data.items():
                    for execution_run in node_executions:
                        exec_time = execution_run.get("executionTime", 0)
                        if exec_time:
                            node_times.append({
                                "node": node_name,
                                "time_ms": exec_time
                            })
                            total_execution_time += exec_time
                
                metrics.update({
                    "node_execution_time_ms": total_execution_time,
                    "node_count": len(run_data),
                    "avg_node_time_ms": total_execution_time / len(run_data) if run_data else 0,
                    "slowest_nodes": sorted(node_times, key=lambda x: x["time_ms"], reverse=True)[:3]
                })
                
            except Exception as e:
                logger.debug(f"Could not extract detailed performance metrics: {e}")
        
        return metrics
    
    async def _cleanup_test_workflow(self, workflow_id: str):
        """Clean up test workflow after execution"""
        try:
            await self.n8n_client.delete_workflow(workflow_id)
            logger.debug(f"Cleaned up test workflow {workflow_id}")
        except Exception as e:
            logger.warning(f"Failed to cleanup test workflow {workflow_id}: {e}")
    
    async def test_workflow_nodes_individually(self, workflow_json: Dict[str, Any]) -> Dict[str, Any]:
        """Test individual nodes of workflow for isolated validation"""
        nodes = workflow_json.get("nodes", [])
        node_test_results = {}
        
        for node in nodes:
            node_id = node.get("id", "unknown")
            node_type = node.get("type", "")
            
            try:
                # Create minimal workflow with just this node
                test_workflow = {
                    "name": f"Node Test - {node.get('name', node_id)}",
                    "active": False,
                    "nodes": [node],
                    "connections": {},
                    "meta": {"x_node_test": True}
                }
                
                # Generate appropriate test data
                test_data = await self._generate_node_specific_test_data(node)
                
                # Test the node
                result = await self.test_run_workflow(test_workflow, test_data, 30)
                
                node_test_results[node_id] = {
                    "node_name": node.get("name", node_id),
                    "node_type": node_type,
                    "test_success": result.get("success", False),
                    "issues": result.get("issues", []),
                    "duration_ms": result.get("duration_ms"),
                    "output": result.get("output")
                }
                
            except Exception as e:
                node_test_results[node_id] = {
                    "node_name": node.get("name", node_id),
                    "node_type": node_type,
                    "test_success": False,
                    "issues": [f"Node test failed: {e}"],
                    "error": str(e)
                }
        
        # Compile overall results
        total_nodes = len(node_test_results)
        successful_nodes = len([r for r in node_test_results.values() if r.get("test_success")])
        
        return {
            "node_tests": node_test_results,
            "summary": {
                "total_nodes": total_nodes,
                "successful_nodes": successful_nodes,
                "success_rate": successful_nodes / total_nodes if total_nodes > 0 else 0,
                "overall_success": successful_nodes == total_nodes
            }
        }
    
    async def _generate_node_specific_test_data(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """Generate test data specific to a node type"""
        node_type = node.get("type", "").lower()
        
        # Find appropriate generator
        for pattern, generator in self.test_data_generators.items():
            if pattern in node_type:
                return generator(node)
        
        # Default test data
        return {
            "test": True,
            "node_type": node_type,
            "timestamp": int(time.time())
        }
    
    async def stress_test_workflow(self, workflow_json: Dict[str, Any], concurrent_executions: int = 5, duration_s: int = 60) -> Dict[str, Any]:
        """Perform stress testing on workflow"""
        logger.info(f"Starting stress test: {concurrent_executions} concurrent executions for {duration_s}s")
        
        start_time = time.time()
        end_time = start_time + duration_s
        
        results = []
        semaphore = asyncio.Semaphore(concurrent_executions)
        
        async def run_single_test():
            async with semaphore:
                try:
                    result = await self.test_run_workflow(workflow_json, timeout_s=30)
                    return result
                except Exception as e:
                    return {"success": False, "error": str(e)}
        
        # Run tests continuously until time limit
        tasks = []
        test_count = 0
        
        while time.time() < end_time:
            task = asyncio.create_task(run_single_test())
            tasks.append(task)
            test_count += 1
            
            # Don't overwhelm the system
            await asyncio.sleep(0.1)
        
        # Wait for all tests to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze stress test results
        successful_tests = len([r for r in results if isinstance(r, dict) and r.get("success")])
        failed_tests = len(results) - successful_tests
        
        durations = [r.get("duration_ms", 0) for r in results if isinstance(r, dict) and "duration_ms" in r]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            "stress_test_results": {
                "total_tests": test_count,
                "successful_tests": successful_tests,
                "failed_tests": failed_tests,
                "success_rate": successful_tests / test_count if test_count > 0 else 0,
                "average_duration_ms": avg_duration,
                "max_duration_ms": max(durations) if durations else 0,
                "min_duration_ms": min(durations) if durations else 0,
                "concurrent_executions": concurrent_executions,
                "test_duration_s": duration_s
            },
            "individual_results": results[:10],  # Include first 10 for analysis
            "performance_grade": self._calculate_performance_grade(successful_tests / test_count if test_count > 0 else 0, avg_duration)
        }
    
    def _calculate_performance_grade(self, success_rate: float, avg_duration_ms: float) -> str:
        """Calculate performance grade based on metrics"""
        if success_rate >= 0.95 and avg_duration_ms < 5000:
            return "A"
        elif success_rate >= 0.90 and avg_duration_ms < 10000:
            return "B"
        elif success_rate >= 0.80 and avg_duration_ms < 20000:
            return "C"
        elif success_rate >= 0.70:
            return "D"
        else:
            return "F"
