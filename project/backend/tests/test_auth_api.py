"""Email and password auth against the SQLite backend.

Every account here is synthetic and lives in a throwaway test database.
"""

import uuid

import pytest


@pytest.fixture
def account():
    return {
        "email": f"user-{uuid.uuid4().hex[:8]}@example.com",
        "password": "correct horse battery",
        "full_name": "Test Person",
    }


def register(client, account):
    return client.post("/api/auth/register", json=account)


def test_register_login_and_me(client, account):
    created = register(client, account)
    assert created.status_code == 200
    assert created.json()["token_type"] == "bearer"

    login = client.post(
        "/api/auth/login",
        json={"email": account["email"], "password": account["password"]},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == account["email"]
    assert body["name"] == "Test Person"
    assert body["is_verified"] is False


def test_register_rejects_duplicate_email(client, account):
    assert register(client, account).status_code == 200
    again = register(client, account)
    assert again.status_code == 400
    assert again.json()["detail"] == "Email already registered"


def test_register_rejects_invalid_email(client, account):
    account["email"] = "not-an-email"
    assert register(client, account).status_code == 422


def test_register_defaults_name_to_user(client, account):
    del account["full_name"]
    token = register(client, account).json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["name"] == "User"


def test_login_with_wrong_password_is_unauthorised(client, account):
    register(client, account)
    response = client.post(
        "/api/auth/login", json={"email": account["email"], "password": "wrong"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_for_unknown_email_is_unauthorised(client):
    response = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "x"}
    )
    assert response.status_code == 401


def test_me_rejects_missing_and_bad_tokens(client):
    assert client.get("/api/auth/me").status_code in (401, 403)
    bad = client.get("/api/auth/me", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401
    assert bad.json()["detail"] == "Invalid or expired token"


def test_me_rejects_token_for_non_uuid_subject(client):
    from app.core.security import create_access_token

    token = create_access_token({"sub": "not-a-uuid"})
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid user ID in token"
