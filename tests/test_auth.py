import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient):
    signup_data = {
        "name": "Test User",
        "email": "test@example.com",
        "password": "Password123"
    }
    response = await client.post("/auth/signup", json=signup_data)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data
    assert data["is_verified"] is False

@pytest.mark.asyncio
async def test_login_unverified(client: AsyncClient):
    # First signup
    signup_data = {
        "name": "Unverified User",
        "email": "unverified@example.com",
        "password": "Password123"
    }
    await client.post("/auth/signup", json=signup_data)
    
    # Try to login
    login_data = {
        "email": "unverified@example.com",
        "password": "Password123"
    }
    response = await client.post("/auth/login", json=login_data)
    assert response.status_code == 403
    assert "verify your email" in response.json()["detail"].lower()
