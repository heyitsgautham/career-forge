"""LinkedIn OAuth connection: the callback the dashboard posts to, and the status."""

import pytest

from app.api.routes.auth import linkedin as linkedin_routes
from app.core.config import settings
from tests.fake_http import fake_http

TOKEN_URL = ("POST", "https://www.linkedin.com/oauth/v2/accessToken")
USERINFO_URL = ("GET", "https://api.linkedin.com/v2/userinfo")
ANSWERS = {
    TOKEN_URL: {"access_token": "li-token"},
    USERINFO_URL: {"sub": "li-42", "email": "asha@example.com"},
}


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_ID", "li-client")
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_SECRET", "li-secret")


def connect(client, headers):
    # This is the body the dashboard's /dashboard/linkedin-callback page sends.
    return client.post("/api/auth/linkedin/callback", json={"code": "c1"}, headers=headers)


def test_connecting_stores_the_account_and_reports_it(client, auth, monkeypatch):
    # Regression: the route read `code` from the query string, so the JSON body the
    # dashboard sends always got a 422 and LinkedIn could never be connected.
    http = fake_http(monkeypatch, linkedin_routes, ANSWERS)
    response = connect(client, auth["headers"])
    assert response.status_code == 200
    assert response.json() == {"message": "LinkedIn connected successfully"}
    assert http.calls[0][2]["data"]["code"] == "c1"

    status = client.get("/api/auth/linkedin/status", headers=auth["headers"]).json()
    assert status["connected"] is True
    assert status["email"] == "asha@example.com"

    assert connect(client, auth["headers"]).status_code == 200


def test_connecting_on_dynamodb(dynamo_client, dynamo_auth, monkeypatch):
    fake_http(monkeypatch, linkedin_routes, ANSWERS)
    assert connect(dynamo_client, dynamo_auth["headers"]).status_code == 200
    status = dynamo_client.get("/api/auth/linkedin/status", headers=dynamo_auth["headers"]).json()
    assert status == {
        "connected": True,
        "email": "asha@example.com",
        "connected_at": status["connected_at"],
    }


def test_status_is_disconnected_by_default(client, auth):
    assert client.get("/api/auth/linkedin/status", headers=auth["headers"]).json() == {
        "connected": False
    }


def test_status_is_disconnected_by_default_on_dynamodb(dynamo_client, dynamo_auth):
    assert dynamo_client.get(
        "/api/auth/linkedin/status", headers=dynamo_auth["headers"]
    ).json() == {"connected": False}


def test_linkedin_errors_become_400(client, auth, monkeypatch):
    fake_http(
        monkeypatch,
        linkedin_routes,
        {**ANSWERS, TOKEN_URL: {"error": "invalid_request", "error_description": "code reused"}},
    )
    response = connect(client, auth["headers"])
    assert response.status_code == 400
    assert response.json()["detail"] == "LinkedIn OAuth error: code reused"


def test_linkedin_must_be_configured(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "LINKEDIN_CLIENT_ID", None)
    assert connect(client, auth["headers"]).status_code == 503
    assert client.get("/api/auth/linkedin/authorize").status_code == 503


def test_authorize_url(client):
    url = client.get("/api/auth/linkedin/authorize").json()["authorization_url"]
    assert url.startswith("https://www.linkedin.com/oauth/v2/authorization?response_type=code")
    assert "client_id=li-client" in url
