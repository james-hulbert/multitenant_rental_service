import pytest
from app.database import get_db_connection
from app.security import get_password_hash


@pytest.fixture(autouse=True)
def clean_database():
    """Automatically truncates tables, reseeds default tenants/users/equipment, and fixes sequences."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Truncate all tables and reset identity sequences
            cursor.execute("""
                           TRUNCATE TABLE reservations, equipment, users, tenants 
                RESTART IDENTITY CASCADE;
                           """)

            # 2. Insert default tenants (forcing IDs 1 and 2)
            cursor.execute("""
                           INSERT INTO tenants (id, name)
                           VALUES (1, 'Tenant One'),
                                  (2, 'Tenant Two');
                           """)

            # 3. Advance the tenants ID sequence past 2
            cursor.execute("SELECT setval(pg_get_serial_sequence('tenants', 'id'), 2, true);")

            # 4. Seed baseline user with a VALID bcrypt hash for 'secretpassword'
            valid_hash = get_password_hash("secretpassword")
            cursor.execute("""
                           INSERT INTO users (id, tenant_id, email, password_hash, role)
                           VALUES (1, 1, 'test_tenant1@example.com', %s, 'user');
                           """, (valid_hash,))
            cursor.execute("SELECT setval(pg_get_serial_sequence('users', 'id'), 1, true);")

            # 5. Seed baseline equipment
            cursor.execute("""
                           INSERT INTO equipment (id, tenant_id, name, description, daily_rate, status)
                           VALUES (1, 1, 'Test Excavator', 'Standard machine', 150.00, 'available');
                           """)
            cursor.execute("SELECT setval(pg_get_serial_sequence('equipment', 'id'), 1, true);")

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()