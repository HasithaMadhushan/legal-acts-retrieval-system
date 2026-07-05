"""Rate limiting is disabled globally in tests (see conftest.py) so the auth
fixtures used across the rest of the suite can log in freely. These tests
flip it on temporarily to verify the limiter itself works.
"""

import pytest

from app.core.config import get_settings
from app.core.rate_limit import limiter


@pytest.fixture()
def rate_limiting_enabled():
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()


def _set_auth_rate_limit(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    # `auth_rate_limit()` reads `get_settings().auth_rate_limit` fresh on every
    # request, so patching the cached Settings instance affects the already
    # registered `@limiter.limit(auth_rate_limit)` decorator on each call.
    monkeypatch.setattr(get_settings(), "auth_rate_limit", value)


def test_login_is_rate_limited_per_ip(client, rate_limiting_enabled, monkeypatch):
    _set_auth_rate_limit(monkeypatch, "3/minute")

    payload = {"email": "admin@example.com", "password": "wrong-password"}
    responses = [client.post("/api/v1/auth/login", json=payload) for _ in range(4)]

    assert [r.status_code for r in responses[:3]] == [401, 401, 401]
    assert responses[3].status_code == 429


def test_register_is_rate_limited_per_ip(client, rate_limiting_enabled, monkeypatch):
    _set_auth_rate_limit(monkeypatch, "2/minute")

    def _payload(n: int) -> dict:
        return {
            "full_name": "Rate Limit Test",
            "email": f"rate-limit-{n}@example.com",
            "password": "SomePass123!",
        }

    responses = [client.post("/api/v1/auth/register", json=_payload(n)) for n in range(3)]

    assert [r.status_code for r in responses[:2]] == [201, 201]
    assert responses[2].status_code == 429


def test_other_endpoints_are_not_rate_limited_by_auth_limit(
    client, rate_limiting_enabled, monkeypatch
):
    _set_auth_rate_limit(monkeypatch, "1/minute")

    login_payload = {"email": "admin@example.com", "password": "AdminPass123!"}
    first = client.post("/api/v1/auth/login", json=login_payload)
    assert first.status_code == 200

    second = client.post("/api/v1/auth/login", json=login_payload)
    assert second.status_code == 429

    disclaimer_response = client.get("/api/v1/legal-disclaimer")
    assert disclaimer_response.status_code == 200
