from unittest.mock import MagicMock

from sqlalchemy.exc import IntegrityError

from app.db.seed import seed_demo_users
from app.db.session import SessionLocal
from app.models.user import User


def test_seed_demo_users_creates_all_demo_accounts_from_empty(client):
    with SessionLocal() as db:
        db.query(User).delete()
        db.commit()

        seed_demo_users(db)

        emails = {user.email for user in db.query(User).all()}
    assert {"admin@example.com", "lawyer@example.com", "user@example.com"} <= emails


def test_seed_demo_users_is_idempotent_on_rerun(client):
    with SessionLocal() as db:
        seed_demo_users(db)
        seed_demo_users(db)

        count = db.query(User).filter(User.email == "admin@example.com").count()
    assert count == 1


def test_seed_demo_users_survives_concurrent_insert_race(client):
    """Every Gunicorn worker calls this independently at startup (see
    app.main.lifespan), so two workers can race to insert the same
    not-yet-existing demo user. Simulate the resulting unique-constraint
    violation and confirm it's swallowed instead of crashing the worker.
    """
    with SessionLocal() as db:
        db.commit = MagicMock(
            side_effect=IntegrityError("INSERT ...", {}, Exception("duplicate key value"))
        )
        rollback = MagicMock(wraps=db.rollback)
        db.rollback = rollback

        seed_demo_users(db)  # must not raise

        rollback.assert_called_once()
