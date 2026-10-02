# EVE Healthcare booking API

A FastAPI/PostgreSQL backend for diagnostic-test bookings, simulated payments, and idempotent
provider webhooks. It intentionally stays a modular single service: the assessment prioritizes
correctness and maintainability over infrastructure breadth.

## Implemented scope

- Signup/login with Argon2 password hashes and expiring JWTs.
- Public centre/test catalogue reads; staff-only writes.
- Centre-specific diagnostic offerings and immutable booking price snapshots.
- Owner-scoped create/list/detail/cancel bookings.
- Server-controlled mock payment outcomes and replayed-payment responses.
- HMAC-SHA256 protected webhook receipts with semantic fingerprints and terminal-state guards.
- PostgreSQL schema/migration for users, centres, tests, offerings, bookings, payments, and webhook
  events.

The local suite has 14 passing non-database checks; PostgreSQL integration tests are skipped locally
when `RUN_POSTGRES_TESTS` is absent. GitHub Actions provisions PostgreSQL, migrates, seeds, and runs
the full suite successfully, including API flow and concurrent payment/webhook tests.

## Stack

- Python 3.12+
- FastAPI, Pydantic, SQLAlchemy 2.x, Alembic, and PostgreSQL
- PyJWT and pwdlib/Argon2
- pytest, httpx, and Ruff

## Local setup

1. Create PostgreSQL databases `eve_booking` and `eve_booking_test` with a role that can access
   both. The test database must be separate from the application database.
2. Copy `.env.example` to `.env`. Replace the database credentials and both secrets. JWT and webhook
   secrets must be different and at least 32 characters long; never commit `.env`.
3. Create an environment and install dependencies:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -e ".[dev]"
   ```

4. Create the schema and repeatable demo data:

   ```powershell
   python -m alembic upgrade head
   python -m app.seed
   ```

5. Start the API:

   ```powershell
   uvicorn app.main:app --reload
   ```

Open `http://127.0.0.1:8000/docs` for OpenAPI. `GET /health/` returns `200` only when the database
is reachable. Run checks with `python -m ruff check .` and `python -m pytest -q`.

## API summary

| Route | Access | Purpose |
| --- | --- | --- |
| `POST /auth/signup/` | Public | Create an ordinary user; role fields are rejected. |
| `POST /auth/login/` | Public | Issue a bearer JWT. |
| `GET /centres/`, `GET /tests/` | Public | List catalogue records. |
| `GET /centres/{id}/` | Public | View a centre and its priced offerings. |
| `POST/PATCH /centres/…`, `POST /tests/` | Staff | Manage centres and test definitions. |
| `POST /centres/{id}/tests/`, `PATCH /offerings/{id}/` | Staff | Create or update a centre-specific offer. |
| `POST /bookings/`, `GET /bookings/` | User | Create or list owned bookings. |
| `GET /bookings/{id}/`, `POST /bookings/{id}/cancel/` | Owner | View/cancel one booking. |
| `POST /payments/` | Booking owner | Simulate one payment attempt; replays return the stored result. |
| `POST /payments/webhook/` | Signed provider | Process or acknowledge a provider event. |

Write routes require `Authorization: Bearer <token>`, except the webhook. Booking input accepts only
`offering_id` and an offset-aware future `appointment_at`; owner, amount, currency, and state are
derived by the server.

## Payment and webhook behaviour

A booking starts `PENDING`. The mock endpoint uses `MOCK_PAYMENT_MODE=success`, `failure`, or
`random`; clients cannot select an outcome. A single payment row is linked to each booking, so a
repeated `POST /payments/` returns the original payment rather than creating a second attempt.

Webhook requests must have these headers:

```text
X-Webhook-Timestamp: <Unix seconds>
X-Webhook-Signature: sha256=<HMAC-SHA256 hex digest>
```

The signed bytes are `timestamp + "." + raw request body`; timestamps older than five minutes are
rejected. The event table has a unique `(provider, event_id)` key. An identical event acknowledges
with `duplicate: true`; reuse with different semantic content gives `409 EVENT_CONFLICT`; an opposite
terminal outcome gives `409 STATE_CONFLICT` and is not recorded.

After logging in, create and pay for a booking, then send a webhook using the local `.env` secret:

```powershell
python scripts/send_webhook.py --payment-id <payment-id> --event-id evt-demo-001 --status SUCCESS
```

## Data model and assumptions

`offering` joins a diagnostic centre and test with the current price. Bookings copy the price and
currency at creation, so later catalogue price changes never alter historical bookings. The demo uses
INR, treats the authenticated user as the patient, accepts any future offset-aware appointment, and
allows cancellation only before a payment exists.

This first version deliberately excludes slot capacity, patient dependents, refunds, multiple payment
attempts, real payment gateways, refresh tokens, background workers, and Docker. Adding payment
retries would require a new attempt identity and revised webhook/state rules rather than a simple
status update.
