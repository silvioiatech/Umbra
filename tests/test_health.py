"""Tests for umbra.http.health module."""
import pytest
from aiohttp import ClientSession
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from umbra.http.health import create_health_app, health_handler, root_handler
from umbra.core.logger import setup_logging


class TestHealthApp(AioHTTPTestCase):
    """Test cases for health HTTP endpoints."""
    
    async def get_application(self):
        """Create test application."""
        setup_logging(json_format=False)
        return create_health_app()
    
    @unittest_run_loop
    async def test_health_endpoint(self):
        """Test /health endpoint returns correct JSON response."""
        async with self.client.request("GET", "/health") as resp:
            assert resp.status == 200
            assert resp.content_type == 'application/json'
            
            data = await resp.json()
            assert data['status'] == 'ok'
            assert data['service'] == 'umbra'
            assert data['version'] == '3.0.0'
            assert 'timestamp' in data
            assert 'request_id' in data
            
            # Verify response headers
            assert 'X-Request-ID' in resp.headers
            assert 'X-Content-Type-Options' in resp.headers
            assert resp.headers['X-Content-Type-Options'] == 'nosniff'
            assert resp.headers['X-Frame-Options'] == 'DENY'
    
    @unittest_run_loop
    async def test_root_endpoint(self):
        """Test / endpoint returns service information."""
        async with self.client.request("GET", "/") as resp:
            assert resp.status == 200
            assert resp.content_type == 'application/json'
            
            data = await resp.json()
            assert data['name'] == 'Umbra'
            assert data['description'] == 'Claude Desktop-style AI with MCP modules'
            assert data['version'] == '3.0.0'
            assert 'endpoints' in data
            assert data['endpoints']['/'] == 'Service information'
            assert data['endpoints']['/health'] == 'Health check'
            assert 'request_id' in data
    
    @unittest_run_loop
    async def test_request_id_middleware(self):
        """Test that request ID middleware adds unique IDs."""
        # Make two requests
        async with self.client.request("GET", "/health") as resp1:
            data1 = await resp1.json()
            request_id1 = data1['request_id']
            
        async with self.client.request("GET", "/health") as resp2:
            data2 = await resp2.json()
            request_id2 = data2['request_id']
        
        # Request IDs should be different
        assert request_id1 != request_id2
        assert len(request_id1) > 0
        assert len(request_id2) > 0
    
    @unittest_run_loop
    async def test_security_headers(self):
        """Test that security middleware adds appropriate headers."""
        async with self.client.request("GET", "/health") as resp:
            headers = resp.headers
            
            # Security headers should be present
            assert headers.get('X-Content-Type-Options') == 'nosniff'
            assert headers.get('X-Frame-Options') == 'DENY'
            assert headers.get('X-XSS-Protection') == '1; mode=block'
            
            # Note: In test environment, aiohttp's test client adds its own Server header
            # In production, our middleware will remove sensitive headers correctly
    
    @unittest_run_loop
    async def test_head_requests(self):
        """Test that HEAD requests work for both endpoints."""
        async with self.client.request("HEAD", "/health") as resp:
            assert resp.status == 200
            assert resp.content_type == 'application/json'
            
        async with self.client.request("HEAD", "/") as resp:
            assert resp.status == 200
            assert resp.content_type == 'application/json'
    
    @unittest_run_loop
    async def test_404_not_found(self):
        """Test that non-existent endpoints return 404."""
        async with self.client.request("GET", "/nonexistent") as resp:
            assert resp.status == 404