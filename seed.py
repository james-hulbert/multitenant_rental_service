from app.database import (
    create_tables,
    get_all_tenants,
    insert_tenant,
    get_user_by_email,
    insert_sample_user,
    get_all_equipment,
    insert_equipment,
)


def seed_database():
    # Ensure database tables exist
    create_tables()

    # 1. Seed Default Tenant
    tenants = get_all_tenants()
    tenant = next((t for t in tenants if t["name"] == "Apex Tool Rentals"), None)
    if not tenant:
        tenant = insert_tenant("Apex Tool Rentals")
        print("Seeded Tenant: Apex Tool Rentals")
    else:
        print("Tenant 'Apex Tool Rentals' already exists.")

    tenant_id = tenant["id"]

    # 2. Seed Admin User
    admin = get_user_by_email("admin@example.com", tenant_id)
    if not admin:
        insert_sample_user(tenant_id, "admin@example.com", "admin123", role="admin")
        print("Seeded Admin: admin@example.com")

    # 3. Seed Standard User
    user = get_user_by_email("test@example.com", tenant_id)
    if not user:
        insert_sample_user(tenant_id, "test@example.com", "secretpassword", role="user")
        print("Seeded User: test@example.com")

    # 4. Seed Equipment
    equipment_list = get_all_equipment(tenant_id)
    if not equipment_list:
        insert_equipment(
            tenant_id=tenant_id,
            name="DeWalt 20V Max Rotary Hammer",
            description="Heavy-duty SDS-Plus hammer drill for concrete and masonry",
            daily_rate=45.00,
            status="available",
        )
        print("Seeded Equipment: DeWalt 20V Max Rotary Hammer")

    print("\nDatabase seeding completed successfully!")


if __name__ == "__main__":
    seed_database()