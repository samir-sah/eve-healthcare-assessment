"""Create the initial EVE booking schema.

Revision ID: 20261002_0001
Revises:
Create Date: 2026-10-02 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20261002_0001"
down_revision = None
branch_labels = None
depends_on = None


def uuid_pk() -> sa.Column[sa.UUID]:
    return sa.Column("id", sa.Uuid(), primary_key=True, nullable=False)


def upgrade() -> None:
    op.create_table(
        "users",
        uuid_pk(),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_staff", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "centres",
        uuid_pk(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_centres_name_nonempty"),
        sa.CheckConstraint("length(btrim(location)) > 0", name="ck_centres_location_nonempty"),
    )
    op.create_table(
        "tests",
        uuid_pk(),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("length(btrim(code)) > 0", name="ck_tests_code_nonempty"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_tests_name_nonempty"),
        sa.UniqueConstraint("code", name="uq_tests_code"),
    )
    op.create_table(
        "offerings",
        uuid_pk(),
        sa.Column("centre_id", sa.Uuid(), nullable=False),
        sa.Column("test_id", sa.Uuid(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("price > 0", name="ck_offerings_price_positive"),
        sa.ForeignKeyConstraint(["centre_id"], ["centres.id"]),
        sa.ForeignKeyConstraint(["test_id"], ["tests.id"]),
        sa.UniqueConstraint("centre_id", "test_id", name="uq_offerings_centre_test"),
    )
    op.create_index("ix_offerings_centre_id", "offerings", ["centre_id"])
    op.create_table(
        "bookings",
        uuid_pk(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("offering_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("amount > 0", name="ck_bookings_amount_positive"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'FAILED', 'CANCELLED')",
            name="ck_bookings_valid_status",
        ),
        sa.ForeignKeyConstraint(["offering_id"], ["offerings.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_bookings_user_created", "bookings", ["user_id", "created_at"])
    op.create_table(
        "payments",
        uuid_pk(),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, server_default="mock"),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("provider = 'mock'", name="ck_payments_mock_provider"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'SUCCESS', 'FAILED')", name="ck_payments_valid_status"
        ),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"]),
        sa.UniqueConstraint("booking_id", name="uq_payments_booking"),
    )
    op.create_table(
        "webhook_events",
        uuid_pk(),
        sa.Column("provider", sa.String(32), nullable=False, server_default="mock"),
        sa.Column("event_id", sa.String(128), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("provider = 'mock'", name="ck_webhook_events_mock_provider"),
        sa.CheckConstraint(
            "outcome IN ('SUCCESS', 'FAILED')", name="ck_webhook_events_valid_outcome"
        ),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event"),
    )


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("payments")
    op.drop_index("ix_bookings_user_created", table_name="bookings")
    op.drop_table("bookings")
    op.drop_index("ix_offerings_centre_id", table_name="offerings")
    op.drop_table("offerings")
    op.drop_table("tests")
    op.drop_table("centres")
    op.drop_table("users")
