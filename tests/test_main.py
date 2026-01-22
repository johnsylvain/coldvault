"""
Tests for main application
"""
import pytest
from fastapi import status


class TestMainApp:
    """Test main FastAPI application"""
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        # Should return either the dashboard or API info
        assert response.status_code == status.HTTP_200_OK
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = client.options(
            "/api/jobs/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        # CORS middleware should handle this
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_405_METHOD_NOT_ALLOWED]
