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


# ── In-memory AWS for the DynamoDB code paths ──────────────────────────────

# Key schemas from milestones/M0-aws-setup.md, plus the tables
# ensure_job_scout_tables creates at startup.
DYNAMO_TABLES = {
    "Users": ("userId",),
    "Projects": ("userId", "projectId"),
    "Resumes": ("userId", "resumeId"),
    "Jobs": ("jobId",),
    "Applications": ("userId", "applicationId"),
    "Roadmaps": ("userId", "roadmapId"),
    "SkillGapReports": ("userId", "reportId"),
    "UserJobStatuses": ("userId", "jobId"),
    "BlacklistedCompanies": ("companyName",),
    "ProjectRoadmaps": ("userId", "projectRoadmapId"),
}


def _reset_aws_clients():
    from app.services.bedrock_client import bedrock_client
    from app.services.dynamo_service import dynamo_service
    from app.services.s3_service import s3_service

    dynamo_service._resource = None
    s3_service._client = None
    bedrock_client._client = None


@pytest.fixture
def aws():
    """moto-backed DynamoDB and S3 with every CareerForge table and the PDF bucket."""
    import boto3
    from moto import mock_aws

    from app.core.config import settings

    with mock_aws():
        _reset_aws_clients()
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        for name, keys in DYNAMO_TABLES.items():
            schema = [{"AttributeName": keys[0], "KeyType": "HASH"}]
            if len(keys) > 1:
                schema.append({"AttributeName": keys[1], "KeyType": "RANGE"})
            dynamodb.create_table(
                TableName=name,
                KeySchema=schema,
                AttributeDefinitions=[{"AttributeName": k, "AttributeType": "S"} for k in keys],
                BillingMode="PAY_PER_REQUEST",
            )
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=settings.S3_BUCKET)
        yield dynamodb
        _reset_aws_clients()


@pytest.fixture
def dynamo_client(aws, monkeypatch):
    """A TestClient running the DynamoDB code paths against moto."""
    from app.core.config import settings
    from app.main import app
    from app.services import scheduler

    monkeypatch.setattr(settings, "USE_DYNAMO", True)
    monkeypatch.setattr(scheduler, "start_scheduler", lambda: None)
    monkeypatch.setattr(scheduler, "stop_scheduler", lambda: None)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def dynamo_auth(dynamo_client):
    """A registered user on the DynamoDB backend."""
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    token = dynamo_client.post(
        "/api/auth/register",
        json={"email": email, "password": "pw-for-tests", "full_name": "Asha Example"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_id = dynamo_client.get("/api/auth/me", headers=headers).json()["id"]
    return {"headers": headers, "user_id": user_id, "email": email}


class FakeBedrock:
    """Stands in for the boto3 bedrock-runtime client.

    Queue replies with reply(); each converse call pops the next one. A reply
    can be a string, a dict or list (sent as JSON), an Exception to raise, or a
    callable that takes the prompt text.
    """

    def __init__(self):
        self.replies = []
        self.calls = []
        self.embedding = [0.1, 0.2, 0.3]

    def reply(self, *replies):
        self.replies.extend(replies)
        return self

    def _next(self, kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0) if self.replies else "{}"
        if callable(reply) and not isinstance(reply, Exception):
            reply = reply(kwargs["messages"][0]["content"][0]["text"])
        if isinstance(reply, Exception):
            raise reply
        if not isinstance(reply, str):
            import json

            reply = json.dumps(reply)
        return reply

    def converse(self, **kwargs):
        return {"output": {"message": {"content": [{"text": self._next(kwargs)}]}}}

    def converse_stream(self, **kwargs):
        text = self._next(kwargs)
        chunks = [text[i : i + 5] for i in range(0, len(text), 5)]
        return {"stream": [{"contentBlockDelta": {"delta": {"text": c}}} for c in chunks]}

    def invoke_model(self, **kwargs):
        import io
        import json

        self.calls.append(kwargs)
        return {"body": io.BytesIO(json.dumps({"embedding": self.embedding}).encode())}

    @property
    def prompts(self):
        return [c["messages"][0]["content"][0]["text"] for c in self.calls if "messages" in c]


@pytest.fixture
def bedrock(monkeypatch):
    """Replace the Bedrock runtime client with a FakeBedrock."""
    from app.services.bedrock_client import bedrock_client

    fake = FakeBedrock()
    monkeypatch.setattr(bedrock_client, "_client", fake)
    return fake


@pytest.fixture
def make_admin(dynamo_client):
    """Give a DynamoDB-backed user the admin role."""
    import asyncio

    from app.services.dynamo_service import dynamo_service

    def promote(user):
        asyncio.run(
            dynamo_service.update_item("Users", {"userId": user["user_id"]}, {"role": "admin"})
        )
        return user

    return promote


@pytest.fixture
def chroma(monkeypatch):
    """An in-memory Chroma client in place of the Chroma server."""
    import chromadb
    from chromadb.config import Settings

    from app.services.vector_store import vector_store

    client = chromadb.EphemeralClient(
        settings=Settings(anonymized_telemetry=False, allow_reset=True)
    )
    client.reset()
    monkeypatch.setattr(vector_store, "_client", client)
    monkeypatch.setattr(vector_store, "_collections", {})
    yield vector_store
    client.reset()
