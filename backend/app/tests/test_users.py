from uuid import uuid4


def test_non_admin_cannot_list_or_create_users(client, user_token, lawyer_token):
    for token in (user_token, lawyer_token):
        listed = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
        assert listed.status_code == 403
        created = client.post(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "full_name": "Blocked User",
                "email": "blocked@example.com",
                "password": "BlockedPass123!",
                "role": "GENERAL_USER",
            },
        )
        assert created.status_code == 403


def test_admin_can_create_patch_deactivate_and_list_users(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    email = f"new-user-{uuid4().hex[:8]}@example.com"
    created = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "full_name": "New Staff",
            "email": email,
            "password": "StaffPass123!",
            "role": "GENERAL_USER",
        },
    )
    assert created.status_code == 201
    user_id = created.json()["id"]

    listed = client.get("/api/v1/users", headers=headers)
    assert listed.status_code == 200
    assert any(row["email"] == email for row in listed.json())

    patched = client.patch(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"role": "LAWYER"},
    )
    assert patched.status_code == 200
    assert patched.json()["role"] == "LAWYER"

    deactivated = client.delete(f"/api/v1/users/{user_id}", headers=headers)
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
