import os
import psycopg2
from psycopg2.extras import RealDictCursor
from app.security import get_password_hash, verify_password

# Database connection settings (supports environment variables with fallback defaults)
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "postgres"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "826As6523$$$"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}


def get_db_connection():
    """Establishes and returns a direct connection to PostgreSQL."""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)


def hash_password(password: str) -> str:
    """Hash a plain text password using centralized security configuration."""
    return get_password_hash(password)


def create_tables():
    """Creates initial database tables for multi-tenancy if they do not exist."""
    commands = (
        """
        CREATE TABLE IF NOT EXISTS tenants
        (
            id         SERIAL PRIMARY KEY,
            name       VARCHAR(255) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS users
        (
            id            SERIAL PRIMARY KEY,
            tenant_id     INTEGER REFERENCES tenants (id) ON DELETE CASCADE,
            email         VARCHAR(255) NOT NULL,
            password_hash VARCHAR(255),
            role          VARCHAR(50) DEFAULT 'user',
            is_active     BOOLEAN     DEFAULT TRUE,
            created_at    TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_email_per_tenant UNIQUE (tenant_id, email)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS equipment
        (
            id          SERIAL PRIMARY KEY,
            tenant_id   INTEGER REFERENCES tenants (id) ON DELETE CASCADE,
            name        VARCHAR(255)   NOT NULL,
            description TEXT,
            daily_rate  NUMERIC(10, 2) NOT NULL,
            status      VARCHAR(50) DEFAULT 'available',
            created_at  TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS reservations
        (
            id                SERIAL PRIMARY KEY,
            tenant_id         INTEGER REFERENCES tenants (id) ON DELETE CASCADE,
            user_id           INTEGER REFERENCES users (id) ON DELETE CASCADE,
            equipment_id      INTEGER REFERENCES equipment (id) ON DELETE CASCADE,
            start_date        TIMESTAMP      NOT NULL,
            end_date          TIMESTAMP      NOT NULL,
            total_cost        NUMERIC(10, 2) NOT NULL,
            payment_intent_id VARCHAR(255),
            payment_status    VARCHAR(50) DEFAULT 'pending',
            created_at        TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            for command in commands:
                cursor.execute(command)
        conn.commit()
        print("✅ Database tables successfully ensured!")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        conn.rollback()
    finally:
        conn.close()


# --- TENANT HELPERS ---

def insert_tenant(name: str):
    """Creates a new tenant account."""
    insert_sql = "INSERT INTO tenants (name) VALUES (%s) RETURNING id, name, created_at;"
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(insert_sql, (name,))
            new_tenant = cursor.fetchone()
            conn.commit()
            return new_tenant
    except psycopg2.IntegrityError:
        conn.rollback()
        return None
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_all_tenants():
    """Retrieves all registered tenants."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM tenants;")
            return cursor.fetchall()
    finally:
        conn.close()


# --- USER HELPERS ---

def insert_sample_user(tenant_id: int, email: str, password: str = "secretpassword", role: str = "user"):
    """Inserts a user tied to a specific tenant with a hashed password."""
    pwd_hash = hash_password(password)
    insert_sql = """
    INSERT INTO users (tenant_id, email, password_hash, role)
    VALUES (%s, %s, %s, %s)
    RETURNING id, tenant_id, email, role, is_active, created_at;
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(insert_sql, (tenant_id, str(email), pwd_hash, str(role)))
            new_user = cursor.fetchone()
            conn.commit()
            return new_user
    except psycopg2.IntegrityError:
        conn.rollback()
        return None
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_all_users():
    """Retrieves all user records."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, tenant_id, email, role, is_active, created_at FROM users;")
            return cursor.fetchall()
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    """Fetches a user record by primary key."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = %s;", (user_id,))
            return cursor.fetchone()
    finally:
        conn.close()


def get_user_by_email(email: str, tenant_id: int):
    """Fetches a user by email and tenant for authentication."""
    query = """
    SELECT id, tenant_id, email, password_hash, role, is_active, created_at 
    FROM users 
    WHERE email = %s AND tenant_id = %s;
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (email, tenant_id))
            return cursor.fetchone()
    finally:
        conn.close()


# --- EQUIPMENT HELPERS ---

def insert_equipment(tenant_id: int, name: str, description: str, daily_rate: float, status: str = "available"):
    """Inserts equipment tied to a specific tenant."""
    insert_sql = """
    INSERT INTO equipment (tenant_id, name, description, daily_rate, status)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING id, tenant_id, name, description, daily_rate, status, created_at;
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(insert_sql, (tenant_id, name, description, daily_rate, status))
            new_item = cursor.fetchone()
            conn.commit()
            if new_item:
                new_item["daily_rate"] = float(new_item["daily_rate"])
            return new_item
    finally:
        conn.close()


def get_all_equipment(tenant_id: int | None = None):
    """Retrieves equipment items, optionally filtered by tenant."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if tenant_id is not None:
                cursor.execute("SELECT * FROM equipment WHERE tenant_id = %s;", (tenant_id,))
            else:
                cursor.execute("SELECT * FROM equipment;")
            items = cursor.fetchall()
            for item in items:
                item["daily_rate"] = float(item["daily_rate"])
            return items
    finally:
        conn.close()


def get_equipment_by_tenant(tenant_id: int):
    """Retrieves all equipment items belonging to a specific tenant."""
    return get_all_equipment(tenant_id=tenant_id)


def get_equipment_by_id(equipment_id: int):
    """Fetches an equipment record by primary key."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM equipment WHERE id = %s;", (equipment_id,))
            item = cursor.fetchone()
            if item:
                item["daily_rate"] = float(item["daily_rate"])
            return item
    finally:
        conn.close()


def get_equipment_by_id_and_tenant(equipment_id: int, tenant_id: int):
    """Fetches an equipment record strictly within a tenant scope."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM equipment WHERE id = %s AND tenant_id = %s;", (equipment_id, tenant_id))
            item = cursor.fetchone()
            if item:
                item["daily_rate"] = float(item["daily_rate"])
            return item
    finally:
        conn.close()


def update_equipment_db(equipment_id: int, tenant_id: int, name: str, description: str, daily_rate: float, status: str):
    """Updates an existing equipment item."""
    update_sql = """
    UPDATE equipment
    SET name = %s, description = %s, daily_rate = %s, status = %s
    WHERE id = %s AND tenant_id = %s
    RETURNING id, tenant_id, name, description, daily_rate, status, created_at;
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(update_sql, (name, description, daily_rate, status, equipment_id, tenant_id))
            row = cursor.fetchone()
            conn.commit()
            if row:
                row["daily_rate"] = float(row["daily_rate"])
            return row
    finally:
        conn.close()


def batch_archive_equipment(tenant_id: int, equipment_ids: list[int]):
    """Archives multiple equipment items at once."""
    if not equipment_ids:
        return []

    update_sql = """
    UPDATE equipment
    SET status = 'archived'
    WHERE tenant_id = %s AND id = ANY(%s)
    RETURNING id, tenant_id, name, description, daily_rate, status, created_at;
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(update_sql, (tenant_id, equipment_ids))
            archived_list = cursor.fetchall()
            conn.commit()
            for item in archived_list:
                item["daily_rate"] = float(item["daily_rate"])
            return archived_list
    finally:
        conn.close()


# --- RESERVATION HELPERS ---

def get_reservation_by_id(reservation_id: int):
    """Fetches a reservation record by primary key."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM reservations WHERE id = %s;", (reservation_id,))
            res = cursor.fetchone()
            if res:
                res["total_cost"] = float(res["total_cost"])
            return res
    finally:
        conn.close()


def check_reservation_overlap(equipment_id: int, start_date, end_date, tenant_id: int | None = None) -> bool:
    """Returns True if the equipment is already reserved during the specified time range within a tenant scope."""
    start_str = start_date.isoformat() if hasattr(start_date, "isoformat") else str(start_date)
    end_str = end_date.isoformat() if hasattr(end_date, "isoformat") else str(end_date)

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if tenant_id is not None:
                overlap_sql = """
                SELECT id FROM reservations
                WHERE equipment_id = %s AND tenant_id = %s AND start_date < %s AND end_date > %s;
                """
                cursor.execute(overlap_sql, (equipment_id, tenant_id, end_str, start_str))
            else:
                overlap_sql = """
                SELECT id FROM reservations
                WHERE equipment_id = %s AND start_date < %s AND end_date > %s;
                """
                cursor.execute(overlap_sql, (equipment_id, end_str, start_str))
            return cursor.fetchone() is not None
    finally:
        conn.close()


def insert_reservation(tenant_id, user_id, equipment_id, start_date, end_date, total_cost, payment_intent_id, payment_status):
    """Insert a new reservation into PostgreSQL using RETURNING *."""
    start_str = start_date.isoformat() if hasattr(start_date, "isoformat") else str(start_date)
    end_str = end_date.isoformat() if hasattr(end_date, "isoformat") else str(end_date)

    insert_sql = """
    INSERT INTO reservations (tenant_id, user_id, equipment_id, start_date, end_date, total_cost, payment_intent_id, payment_status)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id, tenant_id, user_id, equipment_id, start_date, end_date, total_cost, payment_intent_id, payment_status, created_at;
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                insert_sql,
                (tenant_id, user_id, equipment_id, start_str, end_str, total_cost, payment_intent_id, payment_status)
            )
            new_res = cursor.fetchone()
            conn.commit()
            if new_res:
                new_res["total_cost"] = float(new_res["total_cost"])
            return new_res
    finally:
        conn.close()


def get_all_reservations(tenant_id: int | None = None):
    """Retrieves reservations, optionally filtered by tenant."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if tenant_id is not None:
                cursor.execute("SELECT * FROM reservations WHERE tenant_id = %s;", (tenant_id,))
            else:
                cursor.execute("SELECT * FROM reservations;")
            reservations = cursor.fetchall()
            for res in reservations:
                res["total_cost"] = float(res["total_cost"])
            return reservations
    finally:
        conn.close()


def update_reservation_payment_status(payment_intent_id: str, new_status: str):
    """Update reservation payment status when a Stripe webhook event fires."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE reservations
                SET payment_status = %s
                WHERE payment_intent_id = %s
                RETURNING id, tenant_id, payment_status;
                """,
                (new_status, payment_intent_id),
            )
            updated_record = cursor.fetchone()
            conn.commit()
            return updated_record
    except Exception as e:
        print(f"Error updating payment status: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def update_reservation_db(reservation_id: int, tenant_id: int, start_date, end_date, total_cost: float, payment_status: str):
    """Updates an existing reservation."""
    update_sql = """
    UPDATE reservations
    SET start_date = %s, end_date = %s, total_cost = %s, payment_status = %s
    WHERE id = %s AND tenant_id = %s
    RETURNING id, tenant_id, user_id, equipment_id, start_date, end_date, total_cost, payment_intent_id, payment_status, created_at;
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(update_sql, (start_date, end_date, total_cost, payment_status, reservation_id, tenant_id))
            row = cursor.fetchone()
            conn.commit()
            if row:
                row["total_cost"] = float(row["total_cost"])
            return row
    finally:
        conn.close()


if __name__ == "__main__":
    create_tables()
    tenant = insert_tenant("Default Rental Co")
    if tenant:
        user = insert_sample_user(tenant["id"], "james@example.com", "secretpassword")
        print(f"Inserted Tenant: {tenant}")
        print(f"Inserted User: {user}")