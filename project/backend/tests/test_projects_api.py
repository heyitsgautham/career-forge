"""Project routes on the DynamoDB backend (moto), with GitHub and Bedrock stubbed."""

import pytest

from app.services import github_service as github_module
from app.services.dynamo_service import dynamo_service

MANUAL = {
    "title": "notes-app",
    "description": "Offline-first markdown notes",
    "technologies": ["React", "IndexedDB"],
    "highlights": ["Syncs 1,000 notes in under a second"],
    "url": "https://github.com/asha-example/notes-app",
    "start_date": "2025-01",
}


def test_manual_project_crud(dynamo_client, dynamo_auth):
    h = dynamo_auth["headers"]
    created = dynamo_client.post("/api/projects", json=MANUAL, headers=h).json()
    assert created["title"] == "notes-app"
    assert created["source_type"] == "manual"
    assert created["url"] == MANUAL["url"]

    assert [p["id"] for p in dynamo_client.get("/api/projects", headers=h).json()] == [
        created["id"]
    ]
    assert (
        dynamo_client.get(f"/api/projects/{created['id']}", headers=h).json()["start_date"]
        == "2025-01"
    )

    patched = dynamo_client.patch(
        f"/api/projects/{created['id']}",
        json={"title": "notes-pro", "is_featured": True},
        headers=h,
    ).json()
    assert patched["title"] == "notes-pro"
    assert patched["is_featured"] is True
    assert patched["technologies"] == ["React", "IndexedDB"]

    assert dynamo_client.delete(f"/api/projects/{created['id']}", headers=h).json() == {
        "message": "Project deleted"
    }
    assert dynamo_client.get(f"/api/projects/{created['id']}", headers=h).status_code == 404


def test_missing_projects_return_404(dynamo_client, dynamo_auth):
    h = dynamo_auth["headers"]
    assert (
        dynamo_client.patch("/api/projects/nope", json={"title": "x"}, headers=h).status_code == 404
    )
    assert dynamo_client.delete("/api/projects/nope", headers=h).status_code == 404


def test_highlights_are_generated_when_missing(dynamo_client, dynamo_auth, bedrock):
    bedrock.reply(
        "Built a sync engine\nDesigned the storage layer\nAdded offline search\nExtra line"
    )
    body = {**MANUAL, "highlights": []}
    created = dynamo_client.post("/api/projects", json=body, headers=dynamo_auth["headers"]).json()
    assert created["highlights"] == [
        "Built a sync engine",
        "Designed the storage layer",
        "Added offline search",
    ]
    assert "React, IndexedDB" in bedrock.prompts[0]


def test_short_generated_highlights_are_discarded(dynamo_client, dynamo_auth, bedrock):
    bedrock.reply("Only one line")
    body = {**MANUAL, "highlights": None}
    created = dynamo_client.post("/api/projects", json=body, headers=dynamo_auth["headers"]).json()
    assert created["highlights"] == []


def test_highlight_generation_failure_still_saves(dynamo_client, dynamo_auth, bedrock):
    bedrock.reply(RuntimeError("bedrock down"))
    body = {**MANUAL, "highlights": []}
    assert (
        dynamo_client.post("/api/projects", json=body, headers=dynamo_auth["headers"]).status_code
        == 200
    )


def test_delete_all_only_touches_the_callers_projects(dynamo_client, dynamo_auth):
    h = dynamo_auth["headers"]
    for i in range(3):
        dynamo_client.post("/api/projects", json={**MANUAL, "title": f"p{i}"}, headers=h)
    other = "other-user"
    import asyncio

    asyncio.run(
        dynamo_service.put_item(
            "Projects", {"userId": other, "projectId": "keep", "name": "theirs"}
        )
    )

    assert dynamo_client.delete("/api/projects/all", headers=h).json() == {
        "message": "Deleted 3 projects"
    }
    assert dynamo_client.get("/api/projects", headers=h).json() == []
    assert asyncio.run(dynamo_service.get_item("Projects", {"userId": other, "projectId": "keep"}))


def test_github_repos_lists_only_github_sourced_projects(dynamo_client, dynamo_auth):
    import asyncio

    uid = dynamo_auth["user_id"]
    asyncio.run(
        dynamo_service.put_item(
            "Projects",
            {
                "userId": uid,
                "projectId": "g1",
                "name": "job-scout",
                "sourceType": "github",
                "stars": 4,
            },
        )
    )
    dynamo_client.post("/api/projects", json=MANUAL, headers=dynamo_auth["headers"])
    repos = dynamo_client.get("/api/projects/github/repos", headers=dynamo_auth["headers"]).json()
    assert [(r["name"], r["stars"]) for r in repos] == [("job-scout", 4)]


@pytest.fixture
def github_user(dynamo_client, dynamo_auth):
    import asyncio

    asyncio.run(
        dynamo_service.update_item(
            "Users",
            {"userId": dynamo_auth["user_id"]},
            {"githubToken": "enc-token", "githubInstallationId": 7},
        )
    )
    return dynamo_auth


@pytest.fixture
def fake_github(monkeypatch):
    calls = {"details": [], "ingested": []}

    async def fetch_repo_details(full_name, encrypted_token):
        calls["details"].append((full_name, encrypted_token))
        if full_name.endswith("/broken"):
            raise RuntimeError("repo gone")
        return {"full_name": full_name, "name": full_name.split("/")[1]}

    async def create_project_from_repo(detailed):
        return {"title": detailed["name"], "technologies": ["Python"], "highlights": ["x"]}

    async def ingest_and_embed_repo(repo_data, project_data, user_id, project_id):
        calls["ingested"].append((repo_data["full_name"], project_id))

    async def fetch_user_repos_fast(encrypted_token, installation_id, include_forks):
        calls["fast"] = (encrypted_token, installation_id, include_forks)
        return [
            {
                "full_name": "asha-example/job-scout",
                "name": "job-scout",
                "url": "https://github.com/asha-example/job-scout",
                "stars": 3,
            },
            {
                "full_name": "asha-example/dotfiles",
                "name": "dotfiles",
                "html_url": "https://github.com/asha-example/dotfiles",
                "is_fork": True,
            },
        ]

    svc = github_module.github_service
    for fn in (
        fetch_repo_details,
        create_project_from_repo,
        ingest_and_embed_repo,
        fetch_user_repos_fast,
    ):
        monkeypatch.setattr(svc, fn.__name__, fn)
    return calls


def test_ingest_requires_a_connected_github_account(dynamo_client, dynamo_auth):
    r = dynamo_client.post(
        "/api/projects/ingest/github", json={"sync_all": True}, headers=dynamo_auth["headers"]
    )
    assert r.status_code == 400
    assert "No GitHub account connected" in r.json()["detail"]


def test_ingest_needs_some_repos(dynamo_client, github_user, fake_github):
    r = dynamo_client.post("/api/projects/ingest/github", json={}, headers=github_user["headers"])
    assert r.status_code == 400


def test_ingest_by_full_name_reports_each_repo(dynamo_client, github_user, fake_github):
    r = dynamo_client.post(
        "/api/projects/ingest/github",
        json={"full_names": ["asha-example/job-scout", "asha-example/broken"]},
        headers=github_user["headers"],
    ).json()
    statuses = {x["full_name"]: x["status"] for x in r["results"]}
    assert statuses == {"asha-example/job-scout": "success", "asha-example/broken": "error"}
    # Regression: the raw exception text went to the browser's toast.
    broken = next(x for x in r["results"] if x["status"] == "error")
    assert broken["error"] == "Could not import this repository. Try again in a few minutes."
    assert fake_github["details"][0] == ("asha-example/job-scout", "enc-token")


def test_a_repo_github_will_not_show_gets_a_specific_message(
    dynamo_client, github_user, fake_github, monkeypatch
):
    from github import UnknownObjectException

    async def missing(full_name, encrypted_token):
        raise UnknownObjectException(404, {"message": "Not Found"}, None)

    monkeypatch.setattr(github_module.github_service, "fetch_repo_details", missing)
    r = dynamo_client.post(
        "/api/projects/ingest/github",
        json={"full_names": ["asha-example/private"]},
        headers=github_user["headers"],
    ).json()
    assert r["results"][0]["error"] == (
        "GitHub did not return this repository. Check it exists and that the "
        "CareerForge GitHub App can see it."
    )


def test_reingesting_a_repo_reuses_its_project_id(dynamo_client, github_user, fake_github):
    import asyncio

    asyncio.run(
        dynamo_service.put_item(
            "Projects",
            {"userId": github_user["user_id"], "projectId": "existing-id", "name": "job-scout"},
        )
    )
    dynamo_client.post(
        "/api/projects/ingest/github",
        json={"full_names": ["asha-example/job-scout"]},
        headers=github_user["headers"],
    )
    assert fake_github["ingested"] == [("asha-example/job-scout", "existing-id")]


def test_sync_all_uses_the_installation_token(dynamo_client, github_user, fake_github):
    r = dynamo_client.post(
        "/api/projects/ingest/github", json={"sync_all": True}, headers=github_user["headers"]
    ).json()
    assert r["message"] == "Processed 2 repositories"
    assert fake_github["fast"] == ("enc-token", 7, False)


def test_invalid_repo_urls_are_reported(dynamo_client, github_user, fake_github):
    r = dynamo_client.post(
        "/api/projects/ingest/github",
        json={"repo_urls": ["https://gitlab.com/a/b"]},
        headers=github_user["headers"],
    ).json()
    assert r["results"] == [{"url": "https://gitlab.com/a/b", "error": "Invalid GitHub URL"}]


def test_user_repos_lists_the_github_account(dynamo_client, github_user, fake_github):
    repos = dynamo_client.get(
        "/api/projects/github/user-repos", headers=github_user["headers"]
    ).json()
    assert [(r["name"], r["html_url"], r["is_fork"]) for r in repos] == [
        ("job-scout", "https://github.com/asha-example/job-scout", False),
        ("dotfiles", "https://github.com/asha-example/dotfiles", True),
    ]
    assert fake_github["fast"][2] is True


def test_user_repos_requires_github(dynamo_client, dynamo_auth):
    assert (
        dynamo_client.get(
            "/api/projects/github/user-repos", headers=dynamo_auth["headers"]
        ).status_code
        == 400
    )


@pytest.mark.parametrize(
    "url,full_name",
    [
        ("https://github.com/asha-example/chat-bot", "asha-example/chat-bot"),
        ("https://github.com/asha-example/digit", "asha-example/digit"),
        ("https://github.com/asha-example/widget.git", "asha-example/widget"),
        ("https://github.com/asha-example/job-scout.git", "asha-example/job-scout"),
    ],
)
def test_url_import_keeps_the_full_repo_name(
    dynamo_client, github_user, fake_github, url, full_name
):
    r = dynamo_client.post(
        "/api/projects/ingest/github", json={"repo_urls": [url]}, headers=github_user["headers"]
    ).json()
    assert [x["full_name"] for x in r["results"]] == [full_name]


def test_url_import_keeps_github_pages_repo_names(dynamo_client, github_user, fake_github):
    url = "https://github.com/asha-example/asha-example.github.io"
    r = dynamo_client.post(
        "/api/projects/ingest/github", json={"repo_urls": [url]}, headers=github_user["headers"]
    ).json()
    assert [x["full_name"] for x in r["results"]] == ["asha-example/asha-example.github.io"]
