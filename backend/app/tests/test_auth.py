from app.core.security import hash_password, verify_password


def test_password_hashing_round_trip():
    hashed = hash_password("AdminPass123!")
    assert hashed != "AdminPass123!"
    assert verify_password("AdminPass123!", hashed)
    assert not verify_password("Wrong123!", hashed)


def test_login_and_me(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "AdminPass123!"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "ADMIN"
    assert "does not provide legal advice" in me.json()["disclaimer"]


def test_invalid_login_is_rejected(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "WrongPass123!"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials."


def test_current_user_requires_authentication(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_public_disclaimer_does_not_require_authentication(client):
    response = client.get("/api/v1/legal-disclaimer")
    assert response.status_code == 200
    assert "does not provide legal advice" in response.json()["disclaimer"]


def test_role_restriction_blocks_non_admin_user_list(client, user_token):
    response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 403


def test_role_restriction_blocks_lawyer_from_admin_user_list(client, lawyer_token):
    response = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {lawyer_token}"},
    )
    assert response.status_code == 403


def test_admin_can_list_users(client, admin_token):
    response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    assert {item["email"] for item in response.json()} >= {
        "admin@example.com",
        "lawyer@example.com",
        "user@example.com",
    }


def test_lawyer_can_access_lawyer_workspace_api(client, lawyer_token):
    response = client.get(
        "/api/v1/saved-items",
        headers={"Authorization": f"Bearer {lawyer_token}"},
    )
    assert response.status_code == 200


def test_general_user_is_blocked_from_lawyer_workspace_api(client, user_token):
    response = client.get(
        "/api/v1/saved-items",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


def test_cors_allows_localhost_and_loopback_frontends(client):
    for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
        response = client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
