import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# --- BASIC & SECURITY TESTS ---

def test_read_root():
    """Verify public root endpoint availability."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Multi-Tenant Equipment Reservation API"}


def test_unauthorized_equipment_access():
    """Verify endpoint protection without JWT token."""
    response = client.get("/equipment")
    assert response.status_code == 401


def test_invalid_login():
    """Verify failed authentication attempt."""
    payload = {
        "tenant_id": 999,
        "email": "nonexistent@example.com",
        "password": "wrongpassword"
    }
    response = client.post("/token", json=payload)
    assert response.status_code == 401


# --- FIXTURES FOR MULTI-TENANT AUTHORIZATION ---

@pytest.fixture
def auth_headers_tenant_1():
    """Ensure Tenant 1 user exists and return valid auth headers."""
    client.post("/users", json={
        "tenant_id": 1,
        "email": "test_tenant1@example.com",
        "password": "secretpassword",
        "role": "user"
    })
    response = client.post("/token", json={
        "tenant_id": 1,
        "email": "test_tenant1@example.com",
        "password": "secretpassword"
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_tenant_2():
    """Ensure Tenant 2 user exists and return valid auth headers."""
    client.post("/users", json={
        "tenant_id": 2,
        "email": "test_tenant2@example.com",
        "password": "secretpassword",
        "role": "user"
    })
    response = client.post("/token", json={
        "tenant_id": 2,
        "email": "test_tenant2@example.com",
        "password": "secretpassword"
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --- MULTI-TENANCY & BUSINESS LOGIC TESTS ---

def test_tenant_isolation_returns_404(auth_headers_tenant_2):
    """Tenant 2 user trying to reserve Tenant 1 resources should receive a 404."""
    payload = {
        "user_id": 1,
        "equipment_id": 1,  # Belongs to Tenant 1
        "start_date": "2026-10-01T10:00:00Z",
        "end_date": "2026-10-05T10:00:00Z"
    }
    response = client.post("/reservations", json=payload, headers=auth_headers_tenant_2)
    assert response.status_code == 404
    detail = response.json()["detail"].lower()
    assert "not found" in detail or "does not exist" in detail


def test_reservation_date_overlap_returns_409(auth_headers_tenant_1):
    """Reserving equipment for overlapping dates within the same tenant should return a 409 conflict."""
    payload = {
        "user_id": 1,
        "equipment_id": 1,
        "start_date": "2026-11-01T10:00:00Z",
        "end_date": "2026-11-05T10:00:00Z"
    }
    # Initial reservation (accepts 201 created or 409 if already seeded)
    first_res = client.post("/reservations", json=payload, headers=auth_headers_tenant_1)
    assert first_res.status_code in [201, 409]

    # Duplicate date overlap attempt
    second_res = client.post("/reservations", json=payload, headers=auth_headers_tenant_1)
    assert second_res.status_code == 409
    assert "already reserved" in second_res.json()["detail"].lower()


def test_create_and_list_equipment(auth_headers_tenant_1):
    # Create equipment
    response = client.post("/equipment", json={
        "name": "Industrial Generator",
        "description": "50kW diesel generator",
        "daily_rate": 120.00
    }, headers=auth_headers_tenant_1)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Industrial Generator"
    equip_id = data["id"]

    # List equipment for tenant
    list_response = client.get("/equipment", headers=auth_headers_tenant_1)
    assert list_response.status_code == 200
    items = list_response.json()
    assert any(item["id"] == equip_id for item in items)


def test_bulk_archive_equipment(auth_headers_tenant_1):
    # Create an item to archive
    create_res = client.post("/equipment", json={
        "name": "Portable Light Tower",
        "description": "LED mast",
        "daily_rate": 75.00
    }, headers=auth_headers_tenant_1)
    equip_id = create_res.json()["id"]

    # Bulk archive
    archive_res = client.put("/equipment/batch-archive", json={
        "equipment_ids": [equip_id]
    }, headers=auth_headers_tenant_1)

    assert archive_res.status_code == 200
    archived_items = archive_res.json()
    assert len(archived_items) == 1
    assert archived_items[0]["status"] == "archived"


def test_stripe_webhook_payment_success():
    # Simulate a Stripe webhook payload for payment_intent.succeeded
    webhook_payload = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_test_webhook_123",
                "status": "succeeded"
            }
        }
    }
    response = client.post("/webhook", json=webhook_payload)
    # Expect success response from webhook handler
    assert response.status_code in [200, 204]