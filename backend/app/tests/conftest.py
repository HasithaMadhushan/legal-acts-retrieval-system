import os

os.environ["DATABASE_URL"] = "sqlite:///./test_legal_acts.db"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["UPLOAD_DIR"] = "test_uploads"
os.environ["DOC_PARSER_PRIMARY"] = "pymupdf"
os.environ["PDF_INSPECTOR_ENABLED"] = "false"
os.environ["DOCLING_ENABLED"] = "false"
# Tests manage the schema directly via create_all (see init_db) for speed and
# per-test isolation; Alembic migrations are exercised separately.
os.environ["AUTO_MIGRATE_ON_STARTUP"] = "false"
# Auth fixtures log in many times per test run from a single TestClient "IP";
# the production rate limiter is exercised separately in test_rate_limit.py.
os.environ["RATE_LIMIT_ENABLED"] = "false"
# Allow hash-test provider selection via fixtures (see use_hash_test_embeddings).
os.environ["ENVIRONMENT"] = "test"

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401 — register SQLAlchemy models for metadata
from app.core.config import get_settings
from app.db.base import Base
from app.db.seed import seed_demo_users
from app.db.session import engine
from app.main import app


@pytest.fixture(autouse=True)
def use_hash_test_embeddings(request, monkeypatch):
    """Select deterministic embeddings through settings, not pytest process sniffing.

    Config-unit tests construct Settings() to assert production defaults, so they
    opt out. All other tests (including embed_text callers) use hash-test.
    """
    if request.fspath.basename == "test_config.py":
        yield
        return
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hash-test")
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        seed_demo_users(db)
    yield


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def admin_token(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture()
def lawyer_token(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "lawyer@example.com", "password": "LawyerPass123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture()
def user_token(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "UserPass123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]
