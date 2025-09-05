"""Prometheus-ready metrics system for Umbra bot."""
import time
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from threading import Lock
from datetime import datetime
import json

@dataclass
class MetricSample:
    """A single metric sample."""
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)

class Counter:
    """Prometheus-style counter metric."""
    
    def __init__(self, name: str, description: str, labels: List[str] = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)
        self._lock = Lock()
    
    def inc(self, amount: float = 1.0, **label_values):
        """Increment counter by amount."""
        with self._lock:
            label_key = self._make_label_key(label_values)
            self._values[label_key] += amount
    
    def get_samples(self) -> List[MetricSample]:
        """Get all samples for this counter."""
        with self._lock:
            samples = []
            for label_tuple, value in self._values.items():
                labels = dict(zip(self.labels, label_tuple))
                samples.append(MetricSample(value=value, labels=labels))
            return samples
    
    def _make_label_key(self, label_values: Dict[str, str]) -> tuple:
        """Create a tuple key from label values."""
        return tuple(label_values.get(label, "") for label in self.labels)

class Gauge:
    """Prometheus-style gauge metric."""
    
    def __init__(self, name: str, description: str, labels: List[str] = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)
        self._lock = Lock()
    
    def set(self, value: float, **label_values):
        """Set gauge to specific value."""
        with self._lock:
            label_key = self._make_label_key(label_values)
            self._values[label_key] = value
    
    def inc(self, amount: float = 1.0, **label_values):
        """Increment gauge by amount."""
        with self._lock:
            label_key = self._make_label_key(label_values)
            self._values[label_key] += amount
    
    def dec(self, amount: float = 1.0, **label_values):
        """Decrement gauge by amount."""
        self.inc(-amount, **label_values)
    
    def get_samples(self) -> List[MetricSample]:
        """Get all samples for this gauge."""
        with self._lock:
            samples = []
            for label_tuple, value in self._values.items():
                labels = dict(zip(self.labels, label_tuple))
                samples.append(MetricSample(value=value, labels=labels))
            return samples
    
    def _make_label_key(self, label_values: Dict[str, str]) -> tuple:
        """Create a tuple key from label values."""
        return tuple(label_values.get(label, "") for label in self.labels)

class Histogram:
    """Prometheus-style histogram metric."""
    
    DEFAULT_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float('inf')]
    
    def __init__(self, name: str, description: str, labels: List[str] = None, buckets: List[float] = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self.buckets = buckets or self.DEFAULT_BUCKETS
        
        # Track counts per bucket and overall stats
        self._bucket_counts: Dict[tuple, Dict[float, int]] = defaultdict(lambda: defaultdict(int))
        self._sums: Dict[tuple, float] = defaultdict(float)
        self._counts: Dict[tuple, int] = defaultdict(int)
        self._lock = Lock()
    
    def observe(self, value: float, **label_values):
        """Observe a value in the histogram."""
        with self._lock:
            label_key = self._make_label_key(label_values)
            
            # Update bucket counts
            for bucket in self.buckets:
                if value <= bucket:
                    self._bucket_counts[label_key][bucket] += 1
            
            # Update sum and count
            self._sums[label_key] += value
            self._counts[label_key] += 1
    
    def get_samples(self) -> List[MetricSample]:
        """Get all samples for this histogram."""
        with self._lock:
            samples = []
            
            for label_tuple in self._counts.keys():
                labels = dict(zip(self.labels, label_tuple))
                
                # Bucket samples
                for bucket in self.buckets:
                    bucket_labels = {**labels, 'le': str(bucket)}
                    count = self._bucket_counts[label_tuple][bucket]
                    samples.append(MetricSample(
                        value=count,
                        labels=bucket_labels
                    ))
                
                # Sum sample
                sum_labels = {**labels}
                samples.append(MetricSample(
                    value=self._sums[label_tuple],
                    labels=sum_labels
                ))
                
                # Count sample
                count_labels = {**labels}
                samples.append(MetricSample(
                    value=self._counts[label_tuple],
                    labels=count_labels
                ))
            
            return samples
    
    def _make_label_key(self, label_values: Dict[str, str]) -> tuple:
        """Create a tuple key from label values."""
        return tuple(label_values.get(label, "") for label in self.labels)

class MetricsRegistry:
    """Registry for all metrics."""
    
    def __init__(self):
        self._metrics: Dict[str, Any] = {}
        self._lock = Lock()
    
    def register(self, metric) -> Any:
        """Register a metric."""
        with self._lock:
            if metric.name in self._metrics:
                raise ValueError(f"Metric {metric.name} already registered")
            self._metrics[metric.name] = metric
            return metric
    
    def get_metric(self, name: str) -> Optional[Any]:
        """Get a metric by name."""
        with self._lock:
            return self._metrics.get(name)
    
    def get_all_samples(self) -> Dict[str, List[MetricSample]]:
        """Get all samples from all registered metrics."""
        with self._lock:
            all_samples = {}
            for name, metric in self._metrics.items():
                all_samples[name] = metric.get_samples()
            return all_samples
    
    def generate_prometheus_format(self) -> str:
        """Generate Prometheus exposition format."""
        lines = []
        all_samples = self.get_all_samples()
        
        for metric_name, samples in all_samples.items():
            metric = self._metrics[metric_name]
            
            # Add help and type comments
            lines.append(f"# HELP {metric_name} {metric.description}")
            
            if isinstance(metric, Counter):
                lines.append(f"# TYPE {metric_name} counter")
            elif isinstance(metric, Gauge):
                lines.append(f"# TYPE {metric_name} gauge")
            elif isinstance(metric, Histogram):
                lines.append(f"# TYPE {metric_name} histogram")
            
            # Add samples
            for sample in samples:
                if sample.labels:
                    label_str = ','.join(f'{k}="{v}"' for k, v in sample.labels.items())
                    lines.append(f"{metric_name}{{{label_str}}} {sample.value}")
                else:
                    lines.append(f"{metric_name} {sample.value}")
        
        return '\n'.join(lines)

class UmbraMetrics:
    """Umbra bot metrics collection."""
    
    def __init__(self):
        self.registry = MetricsRegistry()
        self._init_metrics()
    
    def _init_metrics(self):
        """Initialize core metrics."""
        # Request metrics
        self.request_total = self.registry.register(Counter(
            name="umbra_requests_total",
            description="Total number of requests",
            labels=["module", "action", "status", "user_role"]
        ))
        
        self.request_duration = self.registry.register(Histogram(
            name="umbra_request_duration_seconds",
            description="Request duration in seconds",
            labels=["module", "action", "status"]
        ))
        
        # User metrics
        self.active_users = self.registry.register(Gauge(
            name="umbra_active_users",
            description="Number of active users",
            labels=["role"]
        ))
        
        # Module metrics
        self.module_calls = self.registry.register(Counter(
            name="umbra_module_calls_total",
            description="Total module calls",
            labels=["module", "method", "status"]
        ))
        
        # Error metrics
        self.errors_total = self.registry.register(Counter(
            name="umbra_errors_total",
            description="Total number of errors",
            labels=["module", "error_type"]
        ))
        
        # Permission metrics
        self.permission_checks = self.registry.register(Counter(
            name="umbra_permission_checks_total",
            description="Total permission checks",
            labels=["module", "action", "result"]
        ))
        
        # System metrics
        self.bot_uptime = self.registry.register(Gauge(
            name="umbra_bot_uptime_seconds",
            description="Bot uptime in seconds"
        ))
        
        self.memory_usage = self.registry.register(Gauge(
            name="umbra_memory_usage_bytes",
            description="Memory usage in bytes"
        ))
    
    def record_request(self, module: str, action: str, status: str, duration: float, user_role: str = "unknown"):
        """Record a request with timing."""
        self.request_total.inc(module=module, action=action, status=status, user_role=user_role)
        self.request_duration.observe(duration, module=module, action=action, status=status)
    
    def record_module_call(self, module: str, method: str, status: str):
        """Record a module call."""
        self.module_calls.inc(module=module, method=method, status=status)
    
    def record_error(self, module: str, error_type: str):
        """Record an error."""
        self.errors_total.inc(module=module, error_type=error_type)
    
    def record_permission_check(self, module: str, action: str, result: str):
        """Record a permission check."""
        self.permission_checks.inc(module=module, action=action, result=result)
    
    def update_active_users(self, role_counts: Dict[str, int]):
        """Update active user counts by role."""
        for role, count in role_counts.items():
            self.active_users.set(count, role=role)
    
    def update_system_metrics(self, uptime: float, memory_usage: float):
        """Update system metrics."""
        self.bot_uptime.set(uptime)
        self.memory_usage.set(memory_usage)
    
    def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        return self.registry.generate_prometheus_format()
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of key metrics for admin dashboard."""
        all_samples = self.registry.get_all_samples()
        
        summary = {
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "total_requests": 0,
            "error_rate": 0.0,
            "avg_response_time": 0.0,
            "active_users": 0,
            "module_usage": {},
            "top_errors": []
        }
        
        # Calculate summary from samples
        request_samples = all_samples.get("umbra_requests_total", [])
        if request_samples:
            total_requests = sum(sample.value for sample in request_samples)
            error_requests = sum(sample.value for sample in request_samples 
                               if sample.labels.get("status") == "error")
            summary["total_requests"] = int(total_requests)
            summary["error_rate"] = error_requests / total_requests if total_requests > 0 else 0.0
        
        # Active users
        user_samples = all_samples.get("umbra_active_users", [])
        if user_samples:
            summary["active_users"] = int(sum(sample.value for sample in user_samples))
        
        return summary

# Global metrics instance
metrics = UmbraMetrics()