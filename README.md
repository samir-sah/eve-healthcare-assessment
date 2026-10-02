# EVE Healthcare booking API

This repository implements the EVE Healthcare backend assessment: authenticated diagnostic-test
bookings, simulated payments, and an idempotent payment webhook.

## Current status

Foundation work is in progress. The project contains the FastAPI application factory, PostgreSQL
schema models, an initial Alembic migration, configuration contract, and a database health check.
Authentication, catalogue, booking, payment, webhook, seed data, and automated tests are the next
milestones and are not represented as complete yet.

The supplied architecture and handoff material is preserved locally in `reference-pack/` (ignored
from the implementation repository). The source assignment asks for a small, well-designed backend,
so this project uses one modular service and one PostgreSQL database.

## Stack

- Python 3.12+
- FastAPI and Pydantic validation
- PostgreSQL with SQLAlchemy and Alembic
- JWT authentication and Argon2 password hashing (next milestone)

## Local setup

1. Create a PostgreSQL database named `eve_booking` and a separate `eve_booking_test` database.
2. Copy `.env.example` to `.env` and replace every placeholder, especially the two independent
   secrets and database URLs. Never commit `.env`.
3. Create and activate a virtual environment, then install the project:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -e ".[dev]"
   ```

4. Apply the initial schema once configuration is valid:

   ```powershell
   alembic upgrade head
   ```

5. Start the API:

   ```powershell
   uvicorn app.main:app --reload
   ```

`GET /health/` checks database connectivity. `/docs` exposes generated OpenAPI documentation.

## Schema direction

The initial migration establishes seven tables: users, centres, tests, offerings, bookings,
payments, and webhook events. An offering binds one centre and one test with a price; bookings will
snapshot that price. A unique payment per booking and a unique provider-event pair are the database
backstops for payment replay and webhook idempotency.

## Assumptions being implemented

- The authenticated user is the patient.
- Catalogue reads will be public and writes staff-only.
- INR is the single demo currency, serialized as a decimal string.
- A booking allows one payment attempt; terminal outcomes are not reversed.
- Webhooks will use HMAC-SHA256 over the exact request body and timestamp.

## Planned verification

The next increment adds the test harness against real PostgreSQL. Critical scenarios will cover
authorization, price snapshots, payment replay, webhook duplication and conflicts, transaction
rollback, and concurrent delivery. SQLite will not be used as evidence for PostgreSQL locking.
