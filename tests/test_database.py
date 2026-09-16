import uuid
import pytest
from datetime import datetime, timedelta, timezone
from app.database import (
    insert_tenant,
    insert_sample_user,
    insert_equipment,
    get_equipment_by_id_and_tenant,
    batch_archive_equipment,
    insert_reservation,
    update_reservation_payment_status,
    get_all_reservations,
    update_equipment_db,
    update_reservation_db
)


def get_unique_name(base: str) -> str:
    """Generates a unique name to prevent UNIQUE constraint violations on re-runs."""
    return f"{base}_{uuid.uuid4().hex[:8]}"


def test_db_insert_and_get_equipment():
    # 1. Create tenant with unique name
    tenant = insert_tenant(get_unique_name("DB Test Tenant Equipment"))
    assert tenant is not None

    # 2. Insert equipment
    item = insert_equipment(
        tenant_id=tenant["id"],
        name="Heavy Excavator",
        description="20-ton excavator",
        daily_rate=250.00
    )
    assert item["name"] == "Heavy Excavator"
    assert item["daily_rate"] == 250.00

    # 3. Fetch with tenant scope
    fetched = get_equipment_by_id_and_tenant(item["id"], tenant["id"])
    assert fetched is not None
    assert fetched["id"] == item["id"]


def test_db_batch_archive_equipment():
    tenant = insert_tenant(get_unique_name("DB Test Tenant Batch"))
    item1 = insert_equipment(tenant["id"], "Generator A", "10kW", 50.0)
    item2 = insert_equipment(tenant["id"], "Generator B", "12kW", 60.0)

    archived = batch_archive_equipment(tenant["id"], [item1["id"], item2["id"]])
    assert len(archived) == 2
    for item in archived:
        assert item["status"] == "archived"


def test_db_reservation_lifecycle_and_payment():
    tenant = insert_tenant(get_unique_name("DB Test Tenant Reservation"))
    user = insert_sample_user(tenant["id"], get_unique_name("res_user") + "@example.com", "pass123")
    equip = insert_equipment(tenant["id"], "Scaffolding Set", "Standard", 35.0)

    start = datetime.now(timezone.utc)
    end = start + timedelta(days=3)
    payment_id = get_unique_name("pi_test")

    # 1. Insert reservation
    res = insert_reservation(
        tenant_id=tenant["id"],
        user_id=user["id"],
        equipment_id=equip["id"],
        start_date=start,
        end_date=end,
        total_cost=105.00,
        payment_intent_id=payment_id,
        payment_status="pending"
    )
    assert res is not None
    assert res["payment_intent_id"] == payment_id
    assert res["total_cost"] == 105.00

    # 2. Update payment status
    updated_res = update_reservation_payment_status(payment_id, "succeeded")
    assert updated_res is not None
    assert updated_res["payment_status"] == "succeeded"


def test_db_update_equipment_and_reservation():
    tenant = insert_tenant(get_unique_name("DB Test Tenant Update"))
    user = insert_sample_user(tenant["id"], get_unique_name("update_user") + "@example.com", "pass123")
    equip = insert_equipment(tenant["id"], "Compactor", "Plate compactor", 45.0)

    # Update Equipment
    updated_equip = update_equipment_db(
        equipment_id=equip["id"],
        tenant_id=tenant["id"],
        name="Upgraded Compactor",
        description="Heavy-duty plate compactor",
        daily_rate=55.0,
        status="available"
    )
    assert updated_equip["name"] == "Upgraded Compactor"
    assert updated_equip["daily_rate"] == 55.0

    # Create & Update Reservation
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=2)
    res = insert_reservation(tenant["id"], user["id"], equip["id"], start, end, 90.0, get_unique_name("pi_up"),
                             "pending")

    updated_res = update_reservation_db(
        reservation_id=res["id"],
        tenant_id=tenant["id"],
        start_date=start,
        end_date=end + timedelta(days=1),
        total_cost=135.0,
        payment_status="succeeded"
    )
    assert updated_res["total_cost"] == 135.0
    assert updated_res["payment_status"] == "succeeded"