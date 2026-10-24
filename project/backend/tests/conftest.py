"""Shared pytest setup.

The environment below is set before any app module is imported, because
app.core.config builds its settings singleton at import time. It keeps the
suite offline: no Secrets Manager calls, SQLite instead of DynamoDB, and dummy
AWS credentials so boto3 never looks for a real profile.
"""

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="careerforge-tests-")

os.environ.update(
    {
        "APP_ENV": "test",
        "DEBUG": "false",
        "USE_SECRETS_MANAGER": "false",
        "USE_DYNAMO": "false",
        "DATABASE_URL": f"sqlite+aiosqlite:///{_TMP}/test.db",
        "UPLOAD_DIR": f"{_TMP}/uploads",
        "JWT_SECRET_KEY": "test-jwt-secret-key-that-is-long-enough",
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
