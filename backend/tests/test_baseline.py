import pytest
from fastapi.testclient import TestClient
from main import app
from scraper import clean_price
from decimal import Decimal

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_clean_price_parser():
    assert clean_price("£37") == Decimal("37.00")
    assert clean_price("1299.99 €") == Decimal("1299.99")
    assert clean_price("$49.95") == Decimal("49.95")

def test_admin_login_and_auth():
    # Test login with default admin credentials
    response = client.post(
        "/users/login",
        data={"username": "admin", "password": "changeme"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test GET /users/me
    me_resp = client.get("/users/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "admin"
    
    # Test GET /products with auth
    products_resp = client.get("/products", headers=headers)
    assert products_resp.status_code == 200
    assert isinstance(products_resp.json(), list)
