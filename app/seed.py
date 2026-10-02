from __future__ import annotations

from sqlalchemy import select

from app.auth import hash_password, normalize_email
from app.config import get_settings
from app.db import get_session_factory
from app.models import Centre, DiagnosticTest, Offering, User


def get_or_create_centre(session, name: str, location: str) -> Centre:
    centre = session.scalar(select(Centre).where(Centre.name == name))
    if centre is None:
        centre = Centre(name=name, location=location)
        session.add(centre)
        session.flush()
    return centre


def get_or_create_test(session, code: str, name: str) -> DiagnosticTest:
    diagnostic_test = session.scalar(select(DiagnosticTest).where(DiagnosticTest.code == code))
    if diagnostic_test is None:
        diagnostic_test = DiagnosticTest(code=code, name=name)
        session.add(diagnostic_test)
        session.flush()
    return diagnostic_test


def seed() -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        staff_email = normalize_email(settings.seed_staff_email)
        staff = session.scalar(select(User).where(User.email == staff_email))
        if staff is None:
            session.add(
                User(
                    email=staff_email,
                    password_hash=hash_password(settings.seed_staff_password.get_secret_value()),
                    is_staff=True,
                )
            )

        central = get_or_create_centre(session, "EVE Central Diagnostics", "Koramangala")
        north = get_or_create_centre(session, "EVE North Diagnostics", "Indiranagar")
        cbc = get_or_create_test(session, "CBC", "Complete Blood Count")
        thyroid = get_or_create_test(session, "THYROID", "Thyroid Profile")
        for centre, diagnostic_test, price in [
            (central, cbc, "750.00"),
            (central, thyroid, "1200.00"),
            (north, cbc, "800.00"),
        ]:
            existing = session.scalar(
                select(Offering).where(
                    Offering.centre_id == centre.id, Offering.test_id == diagnostic_test.id
                )
            )
            if existing is None:
                session.add(Offering(centre_id=centre.id, test_id=diagnostic_test.id, price=price))
        session.commit()


if __name__ == "__main__":
    seed()
