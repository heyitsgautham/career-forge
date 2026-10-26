"""Email addresses match without regard to case, on both storage backends.

Phones capitalise the first letter of an email field, so "Asha@example.com"
and "asha@example.com" must be the same account.
"""

import uuid

import pytest


def fresh_email(prefix="Asha"):
    return f"{prefix}.{uuid.uuid4().hex[:6]}@Example.com"


def register(client, email, password="correct horse battery"):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "full_name": "Asha Example"},
    )


def login(client, email, password="correct horse battery"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


@pytest.fixture(params=["sqlite", "dynamodb"])
def any_client(request):
    name = "client" if request.param == "sqlite" else "dynamo_client"
    return request.getfixturevalue(name)


def test_sign_in_ignores_the_case_of_the_email(any_client):
    email = fresh_email()
    assert register(any_client, email).status_code == 200
    # Regression: the lower-case spelling of the same address was rejected with 401.
    assert login(any_client, email.lower()).status_code == 200
    assert login(any_client, email.upper()).status_code == 200


def test_the_same_address_in_another_case_cannot_register_twice(any_client):
    email = fresh_email()
    assert register(any_client, email).status_code == 200
    second = register(any_client, email.lower())
    assert second.status_code == 400
    assert second.json()["detail"] == "Email already registered"


def test_new_accounts_store_the_address_in_lower_case(any_client):
    email = fresh_email()
    token = register(any_client, email).json()["access_token"]
    me = any_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["email"] == email.lower()


def test_wrong_passwords_and_unknown_addresses_are_401(any_client):
    email = fresh_email()
    register(any_client, email)
    assert login(any_client, email, "wrong password").status_code == 401
    assert login(any_client, "nobody@example.com").status_code == 401
