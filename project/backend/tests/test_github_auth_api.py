"""GitHub sign-in: the code exchange, account matching and the connection status."""

import pytest

from app.api.routes.auth import github as github_routes
from app.core.config import settings
from app.core.security import create_access_token
from tests.fake_http import FakeResponse, fake_http

TOKEN_URL = ("POST", "https://github.com/login/oauth/access_token")
USER_URL = ("GET", "https://api.github.com/user")
EMAILS_URL = ("GET", "https://api.github.com/user/emails")

GH_USER = {"id": 9001, "login": "asha-example", "name": "Asha Example", "avatar_url": None}


def github_answers(emails=None, token=None):
    return {
        TOKEN_URL: token or {"access_token": "gho_test"},
        USER_URL: GH_USER,
        EMAILS_URL: emails
        if emails is not None
        else [{"email": "asha@example.com", "primary": True, "verified": True}],
    }


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_APP_CLIENT_ID", "client-id")
    monkeypatch.setattr(settings, "GITHUB_APP_CLIENT_SECRET", "client-secret")


def me(client, token):
    return client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()


def sign_in(client, **body):
    return client.post("/api/auth/github/callback", json={"code": "c1", **body})


def test_first_sign_in_creates_the_account_and_connection(client, monkeypatch):
    http = fake_http(monkeypatch, github_routes, github_answers())
    response = sign_in(client)
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    me = client.get("/api/auth/me", headers=headers).json()
    assert me["email"] == "asha@example.com"
    status = client.get("/api/auth/github/status", headers=headers).json()
    assert status["connected"] is True
    assert status["username"] == "asha-example"
    assert http.calls[0][2]["data"]["client_secret"] == "client-secret"


def test_signing_in_again_reuses_the_account(client, monkeypatch):
    fake_http(monkeypatch, github_routes, github_answers())
    first = sign_in(client).json()["access_token"]
    second = sign_in(client).json()["access_token"]
    assert me(client, first)["id"] == me(client, second)["id"]


def test_github_errors_become_400(client, monkeypatch):
    fake_http(
        monkeypatch,
        github_routes,
        github_answers(token={"error": "bad_verification_code", "error_description": "expired"}),
    )
    response = sign_in(client)
    assert response.status_code == 400
    assert response.json()["detail"] == "GitHub OAuth error: expired"


def test_an_unverified_primary_email_is_not_trusted(client, monkeypatch):
    # Regression: an unverified address could match, and sign into, someone else's account.
    emails = [{"email": "victim@example.com", "primary": True, "verified": False}]
    fake_http(monkeypatch, github_routes, github_answers(emails=emails))
    response = sign_in(client)
    assert response.status_code == 400
    assert response.json()["detail"] == "Could not get email from GitHub"


def test_an_error_from_the_emails_api_is_a_400_not_a_crash(client, monkeypatch):
    # Without the user:email scope GitHub answers with an object, not a list.
    fake_http(
        monkeypatch,
        github_routes,
        github_answers(emails=FakeResponse({"message": "Not Found"}, 404)),
    )
    assert sign_in(client).status_code == 400


def test_the_public_profile_email_is_the_fallback(client, monkeypatch):
    # A GitHub App without the email permission gets 403 from /user/emails.
    answers = github_answers(emails=FakeResponse({"message": "Forbidden"}, 403))
    answers[USER_URL] = {**GH_USER, "email": "asha@example.com"}
    fake_http(monkeypatch, github_routes, answers)
    assert sign_in(client).status_code == 200


def test_sign_in_needs_github_credentials(client, monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_APP_CLIENT_ID", None)
    monkeypatch.setattr(settings, "GITHUB_CLIENT_ID", None)
    assert sign_in(client).status_code == 503


def test_status_is_disconnected_by_default(client, auth):
    assert client.get("/api/auth/github/status", headers=auth["headers"]).json() == {
        "connected": False
    }


def test_dynamodb_sign_in_links_github_to_the_signed_in_user(
    dynamo_client, dynamo_auth, monkeypatch
):
    fake_http(monkeypatch, github_routes, github_answers())
    link = create_access_token({"sub": dynamo_auth["user_id"]})
    response = sign_in(dynamo_client, installation_id=77, link_token=link)
    assert response.status_code == 200

    status = dynamo_client.get("/api/auth/github/status", headers=dynamo_auth["headers"]).json()
    assert status["connected"] is True
    assert status["username"] == "asha-example"


def test_dynamodb_sign_in_creates_then_reuses_an_account(dynamo_client, monkeypatch):
    fake_http(monkeypatch, github_routes, github_answers())
    first = sign_in(dynamo_client).json()["access_token"]
    second = sign_in(dynamo_client).json()["access_token"]
    assert me(dynamo_client, first)["id"] == me(dynamo_client, second)["id"]
    assert me(dynamo_client, first)["email"] == "asha@example.com"
