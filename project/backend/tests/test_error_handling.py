"""Request ids and the catch-all 500 handler."""

from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.errors import REQUEST_ID_HEADER


def test_every_response_carries_a_request_id(client):
    first = client.get("/health").headers[REQUEST_ID_HEADER]
    second = client.get("/health").headers[REQUEST_ID_HEADER]
    assert len(first) == 32 and first != second


def test_a_well_formed_incoming_id_is_kept_and_a_bad_one_replaced(client):
    kept = client.get("/health", headers={REQUEST_ID_HEADER: "edge-proxy.abc-123"})
    assert kept.headers[REQUEST_ID_HEADER] == "edge-proxy.abc-123"
    replaced = client.get("/health", headers={REQUEST_ID_HEADER: "bad id\nwith newline"})
    assert replaced.headers[REQUEST_ID_HEADER] != "bad id\nwith newline"


def test_an_unhandled_error_is_a_generic_500_with_the_request_id(monkeypatch):
    from app.main import app

    router = APIRouter()

    @router.get("/__boom")
    async def boom():
        raise RuntimeError("postgres://admin:hunter2@db.internal failed")

    app.include_router(router)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/__boom", headers={REQUEST_ID_HEADER: "req-1"})
    finally:
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", "") != "/__boom"]

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error", "request_id": "req-1"}
    assert response.headers[REQUEST_ID_HEADER] == "req-1"
    assert "hunter2" not in response.text


def test_routes_report_failures_without_their_cause(client, auth, monkeypatch):
    import app.services.resume_agent as resume_agent

    async def fails(*_args, **_kwargs):
        raise RuntimeError("bedrock arn:aws:bedrock:us-east-1:123456789012 throttled")

    monkeypatch.setattr(resume_agent, "generate_resume_from_summaries", fails)
    response = client.post("/api/resumes/generate", json={"jd": "Backend"}, headers=auth["headers"])
    assert response.status_code == 500
    assert response.json()["detail"] == "Resume generation failed. Please try again."
    assert "123456789012" not in response.text
