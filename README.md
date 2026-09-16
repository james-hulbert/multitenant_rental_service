# Multi-Tenant Equipment Reservation API

A robust FastAPI backend powering multi-tenant equipment rentals, token-based JWT security, dynamic PostgreSQL database queries, and Stripe payment processing. Built with a comprehensive automated test suite and high test coverage.

## Key Features

* **Multi-Tenancy:** Isolated data and reservation workflows enforced securely at both the database and API levels.
* **JWT Authentication:** Secure token-based auth with robust password hashing via `bcrypt`.
* **Reservation Engine:** Date-overlap prevention logic to handle conflicting rental schedules seamlessly.
* **Stripe Integration:** Webhook handlers for automated payment status synchronization.
* **Automated Testing:** Comprehensive `pytest` suite covering API endpoints, database interactions, and data models with `pytest-cov` reporting.

## Project Structure

```text
backend-capstone/
├── app/
│   ├── __init__.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── security.py
├── tests/
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_database.py
│   └── test_models.py
├── .env.example
├── .gitignore
├── README.md
├── pytest.ini
├── requirements.txt
└── seed.py