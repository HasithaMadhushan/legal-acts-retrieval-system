import os

os.environ["DATABASE_URL"] = "sqlite:///./test_legal_acts.db"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["UPLOAD_DIR"] = "test_uploads"
os.environ["DOC_PARSER_PRIMARY"] = "pymupdf"
os.environ["DOCLING_ENABLED"] = "false"
# Tests manage the schema directly via create_all (see init_db) for speed and
# per-test isolation; Alembic migrations are exercised separately.
os.environ["AUTO_MIGRATE_ON_STARTUP"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.seed import seed_demo_users
from app.db.session import engine
from app.main import app


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
