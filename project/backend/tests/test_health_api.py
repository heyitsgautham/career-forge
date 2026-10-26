"""Health endpoints report failures with 503, so load balancers and Docker see them."""

from app.services.bedrock_client import bedrock_client
from app.services.vector_store import vector_store


def boom(*_args, **_kwargs):
    raise RuntimeError("secret-host:5432 refused connection")


def test_database_health_is_503_when_the_database_is_down(client, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession

    async def failing_execute(*_args, **_kwargs):
        boom()

    monkeypatch.setattr(AsyncSession, "execute", failing_execute)
    response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "database": "disconnected"}


def test_database_health_is_healthy_on_dynamodb(dynamo_client):
    # Regression: the check called DynamoService._get_client, which does not exist,
    # so DynamoDB deployments always reported unhealthy.
    response = dynamo_client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "dynamodb"}


def test_database_health_is_503_when_dynamodb_is_unreachable(dynamo_client, monkeypatch):
    from app.services.dynamo_service import dynamo_service

    monkeypatch.setattr(dynamo_service, "_get_resource", boom)
    client = dynamo_client
    response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "database": "dynamodb"}


def test_services_health_is_healthy_when_clients_build(client, monkeypatch):
    monkeypatch.setattr(bedrock_client, "_get_client", lambda: object())
    monkeypatch.setattr(vector_store, "_get_client", lambda: object())
    response = client.get("/health/services")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "services": {"bedrock": "configured", "vector_store": "connected"},
    }


def test_services_health_names_the_failing_service_without_its_error(client, monkeypatch):
    monkeypatch.setattr(bedrock_client, "_get_client", lambda: object())
    monkeypatch.setattr(vector_store, "_get_client", boom)
    response = client.get("/health/services")
    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "services": {"bedrock": "configured", "vector_store": "error"},
    }
    assert "secret-host" not in response.text
