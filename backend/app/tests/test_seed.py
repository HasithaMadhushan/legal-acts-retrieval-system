from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.db.seed import seed_demo_users
from app.db.session import SessionLocal
from app.models.user import User

PROD_SECRET = "x" * 32


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


@pytest.mark.no_hash_test_embeddings
def test_should_seed_demo_data_defaults_to_development_only():
    assert Settings(environment="development").should_seed_demo_data is True
    assert Settings(environment="staging").should_seed_demo_data is False
    assert Settings(environment="production", secret_key=PROD_SECRET).should_seed_demo_data is False


@pytest.mark.no_hash_test_embeddings
def test_should_seed_demo_data_explicit_override_wins():
    assert Settings(seed_demo_data=False).should_seed_demo_data is False
    assert (
        Settings(
            seed_demo_data=True, environment="production", secret_key=PROD_SECRET
        ).should_seed_demo_data
        is True
    )


class _NoSeedSettings:
    auto_migrate_on_startup = False
    environment = "production"
    seed_demo_data = False
    should_seed_demo_data = False
    app_name = "test"


def test_startup_does_not_seed_demo_users_when_disabled(client, monkeypatch):
    import app.main as main_module

    with SessionLocal() as db:
        db.query(User).delete()
        db.commit()

    monkeypatch.setattr(main_module, "get_settings", lambda: _NoSeedSettings())
    with TestClient(main_module.app):
        pass

    with SessionLocal() as db:
        assert db.query(User).count() == 0


def test_startup_seeds_demo_users_when_enabled(client, monkeypatch):
    import app.main as main_module

    with SessionLocal() as db:
        db.query(User).delete()
        db.commit()

    monkeypatch.setattr(main_module, "get_settings", lambda: _NoSeedSettings())
    monkeypatch.setattr(
        _NoSeedSettings, "should_seed_demo_data", True, raising=False
    )
    with TestClient(main_module.app):
        pass

    with SessionLocal() as db:
        assert db.query(User).count() > 0
