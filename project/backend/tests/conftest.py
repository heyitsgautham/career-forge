"""Shared pytest setup.

The environment below is set before any app module is imported, because
app.core.config builds its settings singleton at import time. It keeps the
suite offline: no Secrets Manager calls, SQLite instead of DynamoDB, and dummy
AWS credentials so boto3 never looks for a real profile.
"""

import os
import tempfile
import uuid

_TMP = tempfile.mkdtemp(prefix="careerforge-tests-")

os.environ.update(
    {
        "APP_ENV": "test",
        "DEBUG": "false",
        "USE_SECRETS_MANAGER": "false",
        "USE_DYNAMO": "false",
        "DATABASE_URL": f"sqlite+aiosqlite:///{_TMP}/test.db",
        "UPLOAD_DIR": f"{_TMP}/uploads",
        "JWT_SECRET_KEY": "test-jwt-secret-key-that-is-long-enough-for-hs256",
        "SECRET_KEY": "test-app-secret-key",
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_EC2_METADATA_DISABLED": "true",
    }
)
os.makedirs(os.environ["UPLOAD_DIR"], exist_ok=True)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client():
    """A TestClient that runs the app lifespan, so SQLite tables exist."""
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def register_user(client, name="Test Person"):
    """Register a synthetic user and return its auth headers and id."""
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    token = client.post(
        "/api/auth/register",
        json={"email": email, "password": "pw-for-tests", "full_name": name},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/auth/me", headers=headers).json()
    return {"headers": headers, "user_id": uuid.UUID(me["id"]), "email": email}


@pytest.fixture
def auth(client):
    return register_user(client)
