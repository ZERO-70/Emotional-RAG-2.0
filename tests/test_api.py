"""Test API endpoints."""

import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "gemini_api" in data
    assert "database" in data


@pytest.mark.asyncio
async def test_models_endpoint():
    """Test models list endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/v1/models")
    
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) > 0


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test root endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Emotional RAG Backend"
    assert "endpoints" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
