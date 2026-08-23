from datetime import UTC, datetime, timedelta

import jwt


def test_register_derives_full_name_and_stays_general_user(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new.reader@example.com",
            "password": "SecurePass1",
            "account_type": "general",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.reader@example.com"
    assert body["full_name"] == "New Reader"
    assert body["role"] == "GENERAL_USER"
    assert body["lawyer_request_status"] == "none"


def test_register_rejects_password_without_letters_and_numbers(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "weak@example.com", "password": "abcdefgh"},
    )
    assert response.status_code == 422


def test_remember_me_extends_token_lifetime(client):
    short = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "UserPass123!", "remember_me": False},
    )
    long = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "UserPass123!", "remember_me": True},
    )
    assert short.status_code == 200
    assert long.status_code == 200
    short_exp = datetime.fromtimestamp(
        jwt.decode(short.json()["access_token"], "test-secret", algorithms=["HS256"])["exp"],
        UTC,
    )
    long_exp = datetime.fromtimestamp(
        jwt.decode(long.json()["access_token"], "test-secret", algorithms=["HS256"])["exp"],
        UTC,
    )
    assert long_exp - short_exp > timedelta(days=20)


def test_lawyer_verification_stays_general_until_admin_approves(client, admin_token):
    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "counsel@example.com",
            "password": "CounselPass1",
            "account_type": "attorney",
        },
    )
    assert register.status_code == 201
    assert register.json()["role"] == "GENERAL_USER"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "counsel@example.com", "password": "CounselPass1"},
    )
    token = login.json()["access_token"]
    response = client.post(
        "/api/v1/auth/lawyer-verification",
        data={"enrollment_number": "SL-44521"},
        files={"file": ("proof.pdf", b"%PDF-1.4 enrollment proof", "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "GENERAL_USER"
    assert body["lawyer_request_status"] == "pending"
    assert body["enrollment_number"] == "SL-44521"

    pending = client.get(
        "/api/v1/users",
        params={"lawyer_request_status": "pending"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert pending.status_code == 200
    assert {item["email"] for item in pending.json()} == {"counsel@example.com"}

    user_id = pending.json()[0]["id"]
    approved = client.post(
        f"/api/v1/users/{user_id}/lawyer-requests/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approved.status_code == 200
    assert approved.json()["role"] == "LAWYER"
    assert approved.json()["lawyer_request_status"] == "approved"

    workspace = client.get(
        "/api/v1/saved-items",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert workspace.status_code == 200


def test_admin_can_reject_lawyer_request(client, admin_token):
    client.post(
        "/api/v1/auth/register",
        json={"email": "rejectme@example.com", "password": "RejectPass1"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "rejectme@example.com", "password": "RejectPass1"},
    )
    token = login.json()["access_token"]
    submitted = client.post(
        "/api/v1/auth/lawyer-verification",
        data={"enrollment_number": "SL-99"},
        files={"file": ("proof.pdf", b"%PDF-1.4 proof", "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = submitted.json()["id"]
    rejected = client.post(
        f"/api/v1/users/{user_id}/lawyer-requests/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["role"] == "GENERAL_USER"
    assert rejected.json()["lawyer_request_status"] == "rejected"

    workspace = client.get(
        "/api/v1/saved-items",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert workspace.status_code == 403


def test_forgot_and_reset_password(client):
    login_before = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "UserPass123!"},
    )
    assert login_before.status_code == 200
    old_token = login_before.json()["access_token"]

    forgot = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "user@example.com"},
    )
    assert forgot.status_code == 200
    token = forgot.json()["reset_token"]
    assert token
    assert "/reset-password?token=" in forgot.json()["reset_url"]

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "BrandNewPass1"},
    )
    assert reset.status_code == 200

    stale_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert stale_me.status_code == 401

    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "UserPass123!"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "BrandNewPass1"},
    )
    assert new_login.status_code == 200

    reused = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "AnotherPass1"},
    )
    assert reused.status_code == 400


def test_forgot_password_hides_token_outside_development(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("ENVIRONMENT", "staging")
    get_settings.cache_clear()
    try:
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "user@example.com"},
        )
        assert response.status_code == 200
        assert "reset_token" not in response.json()
        assert "reset_url" not in response.json()
    finally:
        monkeypatch.setenv("ENVIRONMENT", "development")
        get_settings.cache_clear()


def test_forgot_password_unknown_email_does_not_leak(client):
    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "missing@example.com"},
    )
    assert response.status_code == 200
    assert "reset_token" not in response.json()
    assert "reset_url" not in response.json()


def test_admin_can_download_enrollment_proof(client, admin_token):
    client.post(
        "/api/v1/auth/register",
        json={"email": "proofuser@example.com", "password": "ProofPass1"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "proofuser@example.com", "password": "ProofPass1"},
    )
    token = login.json()["access_token"]
    submitted = client.post(
        "/api/v1/auth/lawyer-verification",
        data={"enrollment_number": "SL-777"},
        files={"file": ("proof.pdf", b"%PDF-1.4 enrollment proof bytes", "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = submitted.json()["id"]
    response = client.get(
        f"/api/v1/users/{user_id}/enrollment-proof",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert "attachment" in response.headers.get("content-disposition", "")
