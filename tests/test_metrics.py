"""Test metrics functionality."""
import pytest
from umbra.core.metrics import UmbraMetrics, Counter, Gauge, Histogram

class TestMetrics:
    """Test metrics collection system."""
    
    def test_counter_creation_and_increment(self):
        """Test counter metric creation and increment."""
        counter = Counter("test_counter", "Test counter metric", ["label1", "label2"])
        
        # Test increment with labels
        counter.inc(amount=5, label1="value1", label2="value2")
        counter.inc(amount=3, label1="value1", label2="value2")
        
        samples = counter.get_samples()
        assert len(samples) == 1
        assert samples[0].value == 8
        assert samples[0].labels == {"label1": "value1", "label2": "value2"}
    
    def test_gauge_creation_and_operations(self):
        """Test gauge metric creation and operations."""
        gauge = Gauge("test_gauge", "Test gauge metric", ["env"])
        
        # Test set
        gauge.set(10.5, env="prod")
        samples = gauge.get_samples()
        assert len(samples) == 1
        assert samples[0].value == 10.5
        
        # Test increment
        gauge.inc(2.5, env="prod")
        samples = gauge.get_samples()
        assert samples[0].value == 13.0
        
        # Test decrement
        gauge.dec(1.0, env="prod")
        samples = gauge.get_samples()
        assert samples[0].value == 12.0
    
    def test_histogram_creation_and_observe(self):
        """Test histogram metric creation and observation."""
        histogram = Histogram("test_histogram", "Test histogram metric", ["method"])
        
        # Observe some values
        histogram.observe(0.1, method="GET")
        histogram.observe(0.5, method="GET")
        histogram.observe(2.0, method="GET")
        
        samples = histogram.get_samples()
        
        # Should have bucket samples + sum + count
        assert len(samples) > 3
        
        # Check that buckets are populated correctly
        bucket_samples = [s for s in samples if "le" in s.labels]
        assert len(bucket_samples) > 0
        
        # Values should be in appropriate buckets
        inf_bucket = next(s for s in bucket_samples if s.labels.get("le") == "inf")
        assert inf_bucket.value == 3  # All 3 observations
    
    def test_umbra_metrics_initialization(self):
        """Test UmbraMetrics initialization."""
        metrics = UmbraMetrics()
        
        assert metrics.request_total is not None
        assert metrics.request_duration is not None
        assert metrics.active_users is not None
        assert metrics.module_calls is not None
        assert metrics.errors_total is not None
        assert metrics.permission_checks is not None
    
    def test_record_request(self):
        """Test recording request metrics."""
        metrics = UmbraMetrics()
        
        metrics.record_request("finance", "read", "success", 0.15, "user")
        metrics.record_request("finance", "write", "error", 0.25, "admin")
        
        # Check that metrics were recorded
        request_samples = metrics.request_total.get_samples()
        assert len(request_samples) >= 2
        
        duration_samples = metrics.request_duration.get_samples()
        assert len(duration_samples) > 0
    
    def test_record_permission_check(self):
        """Test recording permission check metrics."""
        metrics = UmbraMetrics()
        
        metrics.record_permission_check("finance", "read", "granted")
        metrics.record_permission_check("admin", "user_management", "denied")
        
        samples = metrics.permission_checks.get_samples()
        assert len(samples) >= 2
        
        # Find the denied permission check
        denied_sample = next((s for s in samples if s.labels.get("result") == "denied"), None)
        assert denied_sample is not None
        assert denied_sample.labels["module"] == "admin"
        assert denied_sample.labels["action"] == "user_management"
    
    def test_prometheus_format_generation(self):
        """Test Prometheus format generation."""
        metrics = UmbraMetrics()
        
        # Record some metrics
        metrics.record_request("test", "action", "success", 0.1, "user")
        metrics.record_error("test", "ValueError")
        
        prometheus_text = metrics.get_prometheus_metrics()
        
        assert isinstance(prometheus_text, str)
        assert "# HELP" in prometheus_text
        assert "# TYPE" in prometheus_text
        assert "umbra_requests_total" in prometheus_text
        assert "umbra_errors_total" in prometheus_text
    
    def test_metrics_summary(self):
        """Test metrics summary generation."""
        metrics = UmbraMetrics()
        
        # Record some test data
        metrics.record_request("finance", "read", "success", 0.1, "user")
        metrics.record_request("finance", "write", "error", 0.2, "user")
        metrics.update_active_users({"user": 5, "admin": 2})
        
        summary = metrics.get_metrics_summary()
        
        assert "timestamp" in summary
        assert "total_requests" in summary
        assert "error_rate" in summary
        assert "active_users" in summary
        assert summary["total_requests"] >= 2
        assert summary["active_users"] >= 7

if __name__ == "__main__":
    pytest.main([__file__])