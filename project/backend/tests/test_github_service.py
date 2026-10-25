"""GitHub ingestion service with GitHub, Secrets Manager, S3 and DynamoDB faked."""

import base64
import json
from datetime import datetime

import httpx
import pytest
from github import GithubException

from app.core.security import TokenEncryptor
from app.services import github_service as gh_module
from app.services.dynamo_service import dynamo_service
from app.services.github_service import GitHubIngestionService

TOKEN = TokenEncryptor().encrypt("ghp_test_token")


def api_repo(i, **extra):
    return {
        "id": i,
        "full_name": f"asha-example/repo{i}",
        "name": f"repo{i}",
        "html_url": f"https://github.com/asha-example/repo{i}",
        "description": None,
        "stargazers_count": i,
        **extra,
    }


@pytest.fixture
def github_api(monkeypatch):
    """Route httpx calls in github_service through a MockTransport."""
    seen = []
    pages = {}

    def handler(request):
        seen.append(request)
        if request.url.path.endswith("/access_tokens"):
            return httpx.Response(201, json={"token": "inst-token"})
        page = int(request.url.params.get("page", 1))
        data = pages.get(request.url.path, {}).get(page, [])
        if request.url.path == "/installation/repositories":
            return httpx.Response(200, json={"repositories": data})
        return httpx.Response(200, json=data)

    real = httpx.AsyncClient
    monkeypatch.setattr(
        gh_module.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )
    return seen, pages


async def test_fast_fetch_pages_and_filters_oauth_repos(github_api):
    seen, pages = github_api
    first = [api_repo(i) for i in range(100)]
    first[0]["fork"] = True
    first[1]["private"] = True
    pages["/user/repos"] = {1: first, 2: [api_repo(200, topics=["ml"])]}

    repos = await GitHubIngestionService().fetch_user_repos_fast(
        TOKEN, include_forks=False, include_private=False
    )
    assert len(repos) == 99
    assert repos[-1]["topics"] == ["ml"]
    assert repos[-1]["description"] == ""
    assert seen[0].headers["Authorization"] == "Bearer ghp_test_token"
    assert [r.url.params["page"] for r in seen] == ["1", "2"]


async def test_fast_fetch_uses_the_installation_token(github_api, monkeypatch):
    seen, pages = github_api
    pages["/installation/repositories"] = {1: [api_repo(1)]}
    svc = GitHubIngestionService()

    async def installation_token(installation_id):
        assert installation_id == 42
        return "inst-token"

    monkeypatch.setattr(svc, "get_installation_token", installation_token)
    repos = await svc.fetch_user_repos_fast(TOKEN, installation_id=42)
    assert [r["full_name"] for r in repos] == ["asha-example/repo1"]
    assert seen[0].headers["Authorization"] == "Bearer inst-token"


async def test_fast_fetch_falls_back_to_oauth_when_the_app_token_fails(github_api, monkeypatch):
    seen, pages = github_api
    pages["/user/repos"] = {1: [api_repo(5)]}
    svc = GitHubIngestionService()

    async def broken(_):
        raise RuntimeError("no private key")

    monkeypatch.setattr(svc, "get_installation_token", broken)
    assert len(await svc.fetch_user_repos_fast(TOKEN, installation_id=42)) == 1
    assert seen[0].url.path == "/user/repos"


async def test_installation_token_signs_a_jwt_with_the_app_key(github_api, aws, monkeypatch):
    import boto3
    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    from app.core.config import settings

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    boto3.client("secretsmanager", region_name="us-east-1").create_secret(
        Name=settings.GITHUB_APP_PRIVATE_KEY_SECRET, SecretString=pem
    )
    monkeypatch.setattr(settings, "GITHUB_APP_ID", "123")

    seen, _ = github_api
    assert await GitHubIngestionService().get_installation_token(42) == "inst-token"
    request = seen[0]
    assert request.url.path == "/app/installations/42/access_tokens"
    claims = jwt.decode(
        request.headers["Authorization"].split()[1], key.public_key(), algorithms=["RS256"]
    )
    assert claims["iss"] == "123"
    assert claims["exp"] - claims["iat"] == 600


# ── PyGithub-backed paths ───────────────────────────────────────────────────


class Content:
    def __init__(self, text=None, name=None, kind="file", encoding="base64"):
        self.content = base64.b64encode((text or "").encode()).decode()
        self.decoded_content = (text or "").encode()
        self.encoding = encoding
        self.name = name
        self.type = kind


class FakeRepo:
    def __init__(self, files, languages=None, **attrs):
        self.files = files
        self.languages = languages or {"Python": 1200}
        defaults = dict(
            id=7,
            full_name="asha-example/job-scout",
            name="job-scout",
            description=None,
            html_url="https://github.com/asha-example/job-scout",
            homepage=None,
            stargazers_count=3,
            forks_count=1,
            watchers_count=3,
            open_issues_count=0,
            fork=False,
            private=True,
            archived=False,
            created_at=datetime(2025, 1, 2),
            pushed_at=None,
            default_branch="main",
            language="Python",
        )
        defaults.update(attrs)
        self.__dict__.update(defaults)

    def get_contents(self, path):
        if path not in self.files:
            raise GithubException(404, {"message": "Not Found"}, None)
        return self.files[path]

    def get_languages(self):
        return self.languages

    def get_topics(self):
        return ["jobs"]


class FakeGithub:
    def __init__(self, repo):
        self.repo = repo

    def get_repo(self, full_name):
        assert full_name == "asha-example/job-scout"
        return self.repo


@pytest.fixture
def use_repo(monkeypatch):
    def install(repo):
        monkeypatch.setattr(gh_module, "Github", lambda *a, **k: FakeGithub(repo))
        return repo

    return install


async def test_repo_details_collect_readme_and_tech(use_repo):
    use_repo(
        FakeRepo(
            {
                "README.md": Content("# job-scout\nRanks postings"),
                "requirements.txt": Content("fastapi==0.110\n"),
                "package.json": Content(json.dumps({"dependencies": {"react": "18"}})),
                "go.mod": Content("module x"),
            }
        )
    )
    data = await GitHubIngestionService().fetch_repo_details("asha-example/job-scout", TOKEN)
    assert data["readme_content"].startswith("# job-scout")
    assert {"Python", "FastAPI", "React", "Go", "Node.js"} <= set(data["extracted_tech"])
    assert data["root_dirs"] == []
    assert data["created_at"] == "2025-01-02T00:00:00"
    assert data["topics"] == ["jobs"]


async def test_repo_without_readme_lists_root_folders(use_repo):
    use_repo(
        FakeRepo(
            {
                "": [Content(name="src", kind="dir"), Content(name="setup.py")],
                "Cargo.toml": Content("x"),
            }
        )
    )
    data = await GitHubIngestionService().fetch_repo_details("asha-example/job-scout", TOKEN)
    assert data["readme_content"] is None
    assert data["root_dirs"] == ["src"]
    assert "Rust" in data["extracted_tech"]


async def test_plain_encoded_readme_is_decoded(use_repo):
    use_repo(FakeRepo({"README": Content("plain text", encoding=None)}))
    data = await GitHubIngestionService().fetch_repo_details("asha-example/job-scout", TOKEN)
    assert data["readme_content"] == "plain text"


async def test_fetch_repo_by_url_works_without_a_token(use_repo):
    use_repo(FakeRepo({}))
    data = await GitHubIngestionService().fetch_repo_by_url(
        "https://github.com/asha-example/job-scout"
    )
    assert data["full_name"] == "asha-example/job-scout"
    assert data["is_private"] is True


async def test_create_project_uses_the_bedrock_summary(bedrock):
    bedrock.reply(
        {
            "oneLiner": "Ranks internship postings",
            "languages": ["Python"],
            "frameworks": ["FastAPI"],
            "infrastructure": ["AWS"],
            "highlights": ["Scores 500 postings a day"],
        }
    )
    project = await GitHubIngestionService().create_project_from_repo(
        {"name": "job-scout", "readme_content": "x" * 5000, "languages": {"Python": 1}}
    )
    assert project["technologies"] == ["Python", "FastAPI", "AWS"]
    assert project["description"] == "Ranks internship postings"
    assert project["summaryMd"].startswith("# job-scout")
    assert "x" * 3000 in bedrock.prompts[0] and "x" * 3001 not in bedrock.prompts[0]


@pytest.mark.parametrize("reply", [RuntimeError("down"), "[1, 2]"])
async def test_summary_falls_back_when_bedrock_fails(bedrock, reply):
    bedrock.reply(reply)
    project = await GitHubIngestionService().create_project_from_repo(
        {"name": "job-scout", "description": "Job ranker", "languages": {"Python": 1, "Go": 2}}
    )
    assert project["summary"]["oneLiner"] == "Job ranker"
    assert project["highlights"] == ["Developed job-scout using Python, Go"]


async def test_ingest_writes_the_summary_to_s3_and_the_project_to_dynamo(aws):
    import boto3

    from app.core.config import settings

    repo = {
        "name": "job-scout",
        "url": "https://github.com/asha-example/job-scout",
        "stars": 3,
        "github_id": 7,
    }
    project = {
        "summary": {"oneLiner": "Ranks postings", "frameworks": ["FastAPI"]},
        "summaryMd": "# job-scout",
        "technologies": ["Python"],
        "highlights": ["h"],
        "description": "Ranks postings",
    }
    assert await GitHubIngestionService().ingest_and_embed_repo(repo, project, "u1", "p1") == "p1"

    item = await dynamo_service.get_item("Projects", {"userId": "u1", "projectId": "p1"})
    assert item["sourceType"] == "github"
    assert item["summaryS3Key"] == "u1/job-scout-summary.md"
    body = boto3.client("s3", region_name="us-east-1").get_object(
        Bucket=settings.S3_BUCKET, Key="u1/job-scout-summary.md"
    )
    assert body["Body"].read() == b"# job-scout"
