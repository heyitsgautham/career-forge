"""App wiring: root, health endpoints and Cache-Control headers."""


def test_root_reports_running(client):
    body = client.get("/").json()
    assert body["status"] == "running"
    assert body["docs"] == "/docs"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["environment"] == "test"


def test_database_health_uses_sqlite_in_tests(client):
    response = client.get("/health/db")
    assert response.json() == {"status": "healthy", "database": "connected"}


def test_mutations_are_never_cached(client):
    response = client.post("/api/auth/login", json={"email": "a@example.com", "password": "x"})
    assert response.headers["cache-control"] == "no-store"


def test_failed_gets_get_no_cache_rule(client):
    response = client.get("/api/resumes")
    assert response.status_code in (401, 403)
    assert "cache-control" not in response.headers


def test_get_rules_match_by_prefix():
    import asyncio

    from starlette.requests import Request
    from starlette.responses import Response

    from app.core.cache_middleware import CacheControlMiddleware

    middleware = CacheControlMiddleware(app=None)

    def run(path, preset=None):
        scope = {"type": "http", "method": "GET", "path": path, "headers": [], "query_string": b""}

        async def call_next(request):
            response = Response("ok")
            if preset:
                response.headers["Cache-Control"] = preset
            return response

        return asyncio.run(middleware.dispatch(Request(scope), call_next)).headers.get(
            "cache-control"
        )

    assert run("/api/templates/abc") == "private, max-age=1800, stale-while-revalidate=3600"
    assert run("/api/job-scout/feed") == "no-cache"
    assert run("/api/projects") == "private, no-cache"
    assert run("/api/unlisted") is None
    assert run("/api/jobs", preset="no-store") == "no-store"
