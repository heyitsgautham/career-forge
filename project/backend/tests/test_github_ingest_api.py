"""GitHub ingestion: sync, import of new repos, status polling and the project list."""

import asyncio
from datetime import datetime, timedelta

import pytest

from app.services.dynamo_service import dynamo_service
from app.services.github_service import github_service

REPOS = [
    {"github_id": 1, "name": "job-scout", "full_name": "asha/job-scout"},
    {"github_id": 2, "name": "notes", "full_name": "asha/notes"},
]


def set_user(user, **fields):
    asyncio.run(dynamo_service.update_item("Users", {"userId": user["user_id"]}, fields))


def user_row(user):
    return asyncio.run(dynamo_service.get_item("Users", {"userId": user["user_id"]}))


@pytest.fixture
def github(monkeypatch):
    """GitHub and Bedrock stand-ins: every repo summarises to a project with two technologies."""
    ingested = []

    async def fetch_user_repos_fast(**_kwargs):
        return REPOS

    async def fetch_repo_details(full_name, **_kwargs):
        if full_name == "asha/broken":
            raise RuntimeError("README fetch failed")
        return {"full_name": full_name}

    async def create_project_from_repo(detail):
        return {"technologies": ["Python", "FastAPI"], "name": detail["full_name"]}

    async def ingest_and_embed_repo(repo_data, project_data, user_id, project_id):
        ingested.append((repo_data["full_name"], project_id))
        await dynamo_service.put_item(
            "Projects",
            {
                "userId": user_id,
                "projectId": project_id,
                "githubId": next(
                    r["github_id"] for r in REPOS if r["full_name"] == repo_data["full_name"]
                ),
                "sourceType": "github",
                "name": repo_data["full_name"],
            },
        )

    for name, fn in {
        "fetch_user_repos_fast": fetch_user_repos_fast,
        "fetch_repo_details": fetch_repo_details,
        "create_project_from_repo": create_project_from_repo,
        "ingest_and_embed_repo": ingest_and_embed_repo,
    }.items():
        monkeypatch.setattr(github_service, name, fn)
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    return ingested


async def _no_sleep(_seconds):
    return None


def test_ingest_needs_a_github_token(dynamo_client, dynamo_auth):
    response = dynamo_client.post("/api/github/ingest", headers=dynamo_auth["headers"])
    assert response.status_code == 400


def test_import_new_then_sync_reuses_project_ids(dynamo_client, dynamo_auth, github):
    set_user(dynamo_auth, githubToken="KMS:abc", skills=["Go"])
    h = dynamo_auth["headers"]

    first = dynamo_client.post("/api/github/ingest?mode=import_new", headers=h).json()
    assert first["processed"] == 2 and first["mode"] == "import_new"
    ids_after_import = {name: pid for name, pid in github}

    second = dynamo_client.post("/api/github/ingest?mode=import_new", headers=h).json()
    assert second["total"] == 0

    synced = dynamo_client.post("/api/github/ingest?mode=sync", headers=h).json()
    assert synced["processed"] == 2
    assert {name: pid for name, pid in github[-2:]} == ids_after_import

    row = user_row(dynamo_auth)
    assert row["skills"] == ["Go", "FastAPI", "Python"]
    assert row["ingestionStatus"] == "done"

    projects = dynamo_client.get("/api/github/projects", headers=h).json()
    assert sorted(p["name"] for p in projects) == ["asha/job-scout", "asha/notes"]


def test_a_failing_repo_is_counted_and_the_rest_continue(
    dynamo_client, dynamo_auth, github, monkeypatch
):
    set_user(dynamo_auth, githubToken="KMS:abc")

    async def with_broken(**_kwargs):
        return REPOS + [{"github_id": 3, "name": "broken", "full_name": "asha/broken"}]

    monkeypatch.setattr(github_service, "fetch_user_repos_fast", with_broken)
    summary = dynamo_client.post(
        "/api/github/ingest?mode=import_new", headers=dynamo_auth["headers"]
    ).json()
    assert (summary["processed"], summary["failed"]) == (2, 1)


def test_a_github_outage_marks_the_ingest_failed(dynamo_client, dynamo_auth, github, monkeypatch):
    set_user(dynamo_auth, githubToken="KMS:abc")

    async def outage(**_kwargs):
        raise RuntimeError("api.github.com 503 token=gho_secret")

    monkeypatch.setattr(github_service, "fetch_user_repos_fast", outage)
    response = dynamo_client.post("/api/github/ingest", headers=dynamo_auth["headers"])
    assert response.status_code == 502
    assert "gho_secret" not in response.text
    assert user_row(dynamo_auth)["ingestionStatus"] == "failed"


def test_an_unknown_mode_is_rejected(dynamo_client, dynamo_auth, github):
    # Regression: any other mode string re-ingested every repository.
    set_user(dynamo_auth, githubToken="KMS:abc")
    response = dynamo_client.post(
        "/api/github/ingest?mode=everything", headers=dynamo_auth["headers"]
    )
    assert response.status_code == 422
    assert github == []


@pytest.mark.parametrize(
    "fields,expected",
    [
        ({}, "none"),
        ({"ingestionStatus": "done", "ingestionSummary": {"processed": 2}}, "done"),
        ({"ingestionStatus": "in_progress"}, "stale"),
        ({"ingestionStatus": "in_progress", "ingestionStartedAt": "not a date"}, "stale"),
        (
            {
                "ingestionStatus": "in_progress",
                "ingestionStartedAt": (datetime.utcnow() - timedelta(minutes=11)).isoformat(),
            },
            "stale",
        ),
        (
            {"ingestionStatus": "in_progress", "ingestionStartedAt": datetime.utcnow().isoformat()},
            "in_progress",
        ),
    ],
)
def test_ingest_status_reports_stale_runs(dynamo_client, dynamo_auth, fields, expected):
    if fields:
        set_user(dynamo_auth, **fields)
    body = dynamo_client.get("/api/github/ingest-status", headers=dynamo_auth["headers"]).json()
    assert body["status"] == expected
