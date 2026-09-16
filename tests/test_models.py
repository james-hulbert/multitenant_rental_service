from datetime import datetime
import pytest
from pydantic import ValidationError
from app.models import TenantCreate, UserCreate, EquipmentCreate, ReservationCreate


def test_tenant_create_valid():
    """Verify valid tenant schema instantiation."""
    tenant = TenantCreate(name="Test Rentals")
    assert tenant.name == "Test Rentals"


def test_user_create_valid():
    """Verify valid user creation payload."""
    user = UserCreate(
        tenant_id=1,
        email="test@example.com",
        password="secretpassword",
        role="admin"
    )
    assert user.email == "test@example.com"
    assert user.tenant_id == 1


def test_equipment_create_valid():
    """Verify valid equipment creation payload."""
    item = EquipmentCreate(
        name="Excavator CAT 320",
        description="20-ton hydraulic excavator",
        daily_rate=250.00,
        status="available"
    )
    assert item.name == "Excavator CAT 320"
    assert item.daily_rate == 250.00


def test_reservation_create_invalid_dates():
    """Verify Pydantic validates reservation fields."""
    payload = {
        "user_id": 1,
        "equipment_id": 1,
        "start_date": "2026-10-01T10:00:00Z",
        "end_date": "2026-10-05T10:00:00Z"
    }
    reservation = ReservationCreate(**payload)
    assert reservation.user_id == 1
    assert isinstance(reservation.start_date, datetime)