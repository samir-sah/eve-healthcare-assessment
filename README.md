# EVE Healthcare booking API

A FastAPI/PostgreSQL backend for diagnostic-test bookings, simulated payments, and idempotent
provider webhooks. It is a modular service with production-adjacent optional enhancements while
preserving the assessment's booking and payment invariants.

## Implemented scope

- Signup/login with Argon2 password hashes and expiring JWTs.
- Public centre/test catalogue reads; staff-only writes.
- Centre-specific diagnostic offerings and immutable booking price snapshots.
- Owner-scoped create/list/detail/cancel bookings.
- Server-controlled mock payment outcomes and replayed-payment responses.
- HMAC-SHA256 protected webhook receipts with semantic fingerprints and terminal-state guards.
- PostgreSQL schema/migration for users, centres, tests, offerings, bookings, payments, and webhook
  events.
- Offset pagination on catalogue and owner booking lists, with a bounded page size of 100.
- Redis-backed catalogue caching, cache invalidation after staff writes, and Redis-backed fixed-window
  rate limiting with a safe in-process fallback when Redis is unavailable.
- JSON request logs with correlation IDs, Celery retry handling for transient webhook database errors,
  and a Docker Compose API/worker/PostgreSQL/Redis stack.

The local suite has 16 passing non-database checks; PostgreSQL integration tests are skipped locally
when `RUN_POSTGRES_TESTS` is absent. GitHub Actions provisions PostgreSQL, migrates, seeds, and runs
the full suite successfully, including API flow and concurrent payment/webhook tests.

## Stack

- Python 3.12+
- FastAPI, Pydantic, SQLAlchemy 2.x, Alembic, and PostgreSQL
- PyJWT and pwdlib/Argon2
- Redis and Celery
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

## Docker Compose

The included Compose stack starts PostgreSQL, Redis, the API, and a Celery worker. It applies the
migration and seed before serving the API:

```powershell
docker compose up --build
```

Open `http://127.0.0.1:8000/docs` once the API reports readiness. `docker compose down` stops the
stack; include `--volumes` only when you intentionally want to remove the local PostgreSQL data.

## Operational enhancements

`GET /centres/`, `GET /tests/`, and `GET /bookings/` accept `limit` (1–100, default 20) and
`offset` (default 0). Each response includes:

```json
{"pagination":{"limit":20,"offset":0,"total":42}}
```

Catalogue responses are cached in Redis for `CACHE_TTL_SECONDS` (60 by default). Staff catalogue
writes bump a cache namespace version, making prior list and detail keys unreachable immediately.
If Redis is unavailable, reads fall back to PostgreSQL and rate limiting continues within the API
process rather than taking the service down.

`POST /auth/signup/` and `POST /auth/login/` share a per-client fixed-window limit controlled by
`LOGIN_RATE_LIMIT`; `POST /payments/webhook/` uses `WEBHOOK_RATE_LIMIT`. Exceeded requests return
`429 RATE_LIMITED` with `Retry-After`. Every request receives an `X-Request-ID` response header;
the API logs this ID, route, status, and elapsed time as JSON.

On a transient database failure while processing a verified webhook, the API enqueues the same
signed-and-validated payload to Celery and returns `202` with `queued: true`. The worker retries
database operational errors with exponential backoff. Normal and retried delivery use the same
database idempotency constraints, so retries cannot create another receipt or alter terminal state.

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

## Example API flow

After completing the local setup and seed, this PowerShell sequence creates an account, logs in,
uses the first seeded offering, creates a booking, and simulates its payment:

```powershell
$api = "http://127.0.0.1:8000"
$email = "demo-$([guid]::NewGuid().ToString('N').Substring(0, 8))@example.com"
$password = "demo-password-123"

Invoke-RestMethod -Method Post -Uri "$api/auth/signup/" -ContentType "application/json" `
  -Body (@{ email = $email; password = $password } | ConvertTo-Json)
$login = Invoke-RestMethod -Method Post -Uri "$api/auth/login/" -ContentType "application/json" `
  -Body (@{ email = $email; password = $password } | ConvertTo-Json)
$headers = @{ Authorization = "Bearer $($login.access_token)" }

$centre = (Invoke-RestMethod -Uri "$api/centres/?limit=1").items[0]
$offering = (Invoke-RestMethod -Uri "$api/centres/$($centre.id)/").offerings[0]
$appointment = (Get-Date).ToUniversalTime().AddDays(7).ToString("o")
$booking = Invoke-RestMethod -Method Post -Uri "$api/bookings/" -Headers $headers `
  -ContentType "application/json" -Body (@{
    offering_id = $offering.id
    appointment_at = $appointment
  } | ConvertTo-Json)
$payment = Invoke-RestMethod -Method Post -Uri "$api/payments/" -Headers $headers `
  -ContentType "application/json" -Body (@{ booking_id = $booking.id } | ConvertTo-Json)
```

`$payment.status` is `SUCCESS` or `FAILED` according to `MOCK_PAYMENT_MODE`. The interactive
OpenAPI documentation at `/docs` provides request/response schemas and examples for every route.

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

The schema has seven focused tables: `users` stores account and staff status; `centres`, `tests`, and
`offerings` form the public catalogue; `bookings` stores the immutable commercial snapshot and state;
`payments` enforces one mock payment per booking; and `webhook_events` stores the unique provider
event and semantic payload fingerprint used for idempotency. Foreign keys model ownership and catalogue
relationships, while database unique/check constraints protect the key invariants independently of API
validation.

The scope deliberately excludes slot capacity, patient dependents, refunds, multiple payment
attempts, real payment gateways, and refresh tokens. Retry handling is limited to transient webhook
processing failures: it does not create a second payment attempt or change the payment state model.

## Future improvements

- Add centre capacity, slots, time-zone-aware availability, and appointment rescheduling.
- Introduce a real payment-provider adapter, payment attempts/refunds, and reconciliation tooling.
- Add refresh-token rotation, email verification, stronger staff administration, and audit trails.
- Use a shared Redis cluster and durable task monitoring/alerting in a production deployment.
- Add load, security, and end-to-end container tests; publish versioned API documentation and deploy
  through a managed CI/CD environment.
