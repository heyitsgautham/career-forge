"""Google sign-in through Cognito: code exchange, id_token claims and account matching."""

import base64
import json

import pytest

from app.api.routes.auth import cognito as cognito_routes
from app.core.config import settings
from tests.fake_http import fake_http

TOKEN_URL = ("POST", "https://auth.example.com/oauth2/token")


def id_token(**claims):
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"header.{body}.signature"


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "COGNITO_APP_CLIENT_ID", "client-id")
    monkeypatch.setattr(settings, "COGNITO_APP_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(settings, "COGNITO_DOMAIN", "auth.example.com")


def sign_in(client, monkeypatch, token_answer):
    http = fake_http(monkeypatch, cognito_routes, {TOKEN_URL: token_answer})
    return client.post("/api/auth/cognito/callback", json={"code": "c1"}), http


def me(client, response):
    token = response.json()["access_token"]
    return client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()


def test_first_google_sign_in_creates_an_account(dynamo_client, monkeypatch):
    token = id_token(sub="g-1", email="asha@example.com", name="Asha Example", email_verified=True)
    response, http = sign_in(dynamo_client, monkeypatch, {"id_token": token})
    assert response.status_code == 200
    assert me(dynamo_client, response)["email"] == "asha@example.com"
    assert http.calls[0][2]["headers"]["Authorization"].startswith("Basic ")


def test_google_sign_in_joins_the_password_account_with_the_same_email(
    dynamo_client, dynamo_auth, monkeypatch
):
    token = id_token(sub="g-2", email=dynamo_auth["email"], email_verified="true")
    response, _ = sign_in(dynamo_client, monkeypatch, {"id_token": token})
    assert me(dynamo_client, response)["id"] == dynamo_auth["user_id"]

    again, _ = sign_in(dynamo_client, monkeypatch, {"id_token": token})
    assert me(dynamo_client, again)["id"] == dynamo_auth["user_id"]


def test_an_unverified_email_never_joins_an_existing_account(
    dynamo_client, dynamo_auth, monkeypatch
):
    # Regression: an unverified address from the identity provider matched the existing account.
    token = id_token(sub="g-3", email=dynamo_auth["email"], email_verified="false")
    response, _ = sign_in(dynamo_client, monkeypatch, {"id_token": token})
    assert response.status_code == 400
    assert response.json()["detail"] == "Email not verified by the identity provider"


@pytest.mark.parametrize(
    "answer,detail",
    [
        (
            {"error": "invalid_grant", "error_description": "code expired"},
            "Cognito error: code expired",
        ),
        ({"access_token": "x"}, "No id_token in Cognito response"),
        ({"id_token": "not-a-jwt"}, "Malformed id_token"),
        ({"id_token": id_token(sub="g-4")}, "No email in Cognito token"),
    ],
)
def test_bad_token_answers_become_400(dynamo_client, monkeypatch, answer, detail):
    response, _ = sign_in(dynamo_client, monkeypatch, answer)
    assert response.status_code == 400
    assert response.json()["detail"] == detail


def test_cognito_must_be_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "COGNITO_DOMAIN", None)
    assert client.post("/api/auth/cognito/callback", json={"code": "c1"}).status_code == 503
    assert client.get("/api/auth/cognito/authorize").status_code == 503


def test_authorize_url_points_at_the_hosted_ui(client):
    url = client.get("/api/auth/cognito/authorize").json()["authorization_url"]
    assert url.startswith("https://auth.example.com/oauth2/authorize?client_id=client-id")
    assert "identity_provider=Google" in url
