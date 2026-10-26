"""
Project routes: GitHub imports
==============================
Import chosen repositories as projects, and list the repositories on the
user's GitHub account and the ones already imported.
"""

import re
import uuid
from typing import List, Optional

import structlog
from fastapi import Depends, HTTPException
from github import UnknownObjectException
from pydantic import BaseModel

from app.api.deps import get_current_user_dynamo
from app.api.routes.projects.common import router
from app.core.config import settings
from app.schemas.projects import GitHubIngestRequest
from app.services.dynamo_service import dynamo_service
from app.services.github_service import github_service

logger = structlog.get_logger()


def _import_error(exc: Exception) -> str:
    """What the user sees for a repository that failed to import.

    The exception itself goes to the log; its text can name internal hosts or services.
    """
    if isinstance(exc, UnknownObjectException):
        return (
            "GitHub did not return this repository. Check it exists and that the "
            "CareerForge GitHub App can see it."
        )
    return "Could not import this repository. Try again in a few minutes."


@router.post("/ingest/github")
async def ingest_github_repos(
    request: GitHubIngestRequest,
    current_user: dict = Depends(get_current_user_dynamo),
):
    """
    Ingest specific GitHub repos (or all) via the M1.6 pipeline.
    Stores structured summaries in S3 + DynamoDB Projects table.
    """
    github_token = current_user.get("githubToken")
    installation_id = current_user.get("githubInstallationId")
    user_id = current_user["userId"]

    logger.info(
        "repo_import_started",
        user_id=user_id,
        sync_all=request.sync_all,
        requested=len(request.full_names or request.repo_urls or []),
    )

    if not github_token:
        raise HTTPException(
            status_code=400,
            detail="No GitHub account connected. Please connect your GitHub account first.",
        )

    ingested = []

    if request.sync_all:
        repos_meta = await github_service.fetch_user_repos_fast(
            encrypted_token=github_token,
            installation_id=installation_id,
            include_forks=request.include_forks,
        )
    elif request.full_names:
        # Preferred path: full_name already parsed by caller, no regex needed
        repos_meta = []
        for full_name in request.full_names:
            name = full_name.split("/")[-1]
            repos_meta.append({"full_name": full_name, "name": name})
    elif request.repo_urls:
        # Fallback: derive full_names from URLs (URL-import mode)
        repos_meta = []
        for url in request.repo_urls:
            m = re.search(r"github\.com/([^/]+)/([^/]+)", url)
            if m:
                # removesuffix, not rstrip: rstrip(".git") strips any trailing
                # '.', 'g', 'i' or 't', so "job-scout" became "job-scou"
                name = m.group(2).removesuffix(".git")
                full_name = f"{m.group(1)}/{name}"
                repos_meta.append({"full_name": full_name, "name": name})
            else:
                ingested.append({"url": url, "error": "Invalid GitHub URL"})
    else:
        raise HTTPException(
            status_code=400,
            detail="Either sync_all=true, full_names, or repo_urls must be provided",
        )

    # ── De-duplicate: build name→projectId map from existing projects ──
    existing_items = await dynamo_service.query(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        pk_name="userId",
        pk_value=user_id,
    )
    existing_name_to_id = {
        item.get("name", ""): item["projectId"] for item in existing_items if item.get("projectId")
    }

    for repo_meta in repos_meta:
        full_name = repo_meta["full_name"]
        log = logger.bind(user_id=user_id, repo=full_name)
        try:
            detailed = await github_service.fetch_repo_details(
                full_name=full_name,
                encrypted_token=github_token,
            )
            project_data = await github_service.create_project_from_repo(detailed)
            reused = repo_meta["name"] in existing_name_to_id
            project_id = existing_name_to_id.get(repo_meta["name"]) or str(uuid.uuid4())
            await github_service.ingest_and_embed_repo(
                repo_data=detailed,
                project_data=project_data,
                user_id=user_id,
                project_id=project_id,
            )
            log.info(
                "repo_imported",
                project_id=project_id,
                reused_project=reused,
                technologies=project_data.get("technologies", []),
            )
            ingested.append({"full_name": full_name, "status": "success", "project_id": project_id})
        except Exception as e:
            log.error("repo_import_failed", error_type=type(e).__name__, exc_info=e)
            ingested.append({"full_name": full_name, "status": "error", "error": _import_error(e)})

    successes = sum(1 for r in ingested if r.get("status") == "success")
    failures = sum(1 for r in ingested if r.get("status") == "error")
    logger.info(
        "repo_import_finished",
        user_id=user_id,
        succeeded=successes,
        failed=failures,
        total=len(repos_meta),
    )

    return {"message": f"Processed {len(repos_meta)} repositories", "results": ingested}


@router.get("/github/repos")
async def list_github_repos(
    current_user: dict = Depends(get_current_user_dynamo),
):
    """List all ingested GitHub repos (sourced from DynamoDB Projects table)."""
    items = await dynamo_service.query(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        pk_name="userId",
        pk_value=current_user["userId"],
    )
    # Return only github-sourced items in the legacy GitHubRepoResponse shape
    return [
        {
            "id": p.get("projectId", ""),
            "full_name": p.get("name", ""),
            "name": p.get("name", ""),
            "description": p.get("description"),
            "stars": p.get("stars", 0),
            "languages": p.get("languages", {}),
            "topics": p.get("topics", []),
            "project_id": p.get("projectId"),
        }
        for p in items
        if p.get("sourceType") == "github"
    ]


class GitHubUserRepo(BaseModel):
    """GitHub repository from user's account."""

    full_name: str
    name: str
    description: Optional[str]
    html_url: str
    stars: int
    forks: int
    language: Optional[str]
    is_private: bool
    is_fork: bool


@router.get("/github/user-repos", response_model=List[GitHubUserRepo])
async def list_github_user_repos(
    current_user: dict = Depends(get_current_user_dynamo),
):
    """
    List ALL repositories from the user's GitHub account.
    Uses DynamoDB-stored token (GitHub App flow from M1.6).
    """
    github_token = current_user.get("githubToken")
    installation_id = current_user.get("githubInstallationId")

    if not github_token:
        raise HTTPException(
            status_code=400,
            detail="No GitHub account connected. Please connect your GitHub account first.",
        )

    # Fetch repos via installation token (or OAuth fallback)
    repos = await github_service.fetch_user_repos_fast(
        encrypted_token=github_token,
        installation_id=installation_id,
        include_forks=True,
    )

    # Convert to response format
    return [
        GitHubUserRepo(
            full_name=repo["full_name"],
            name=repo["name"],
            description=repo.get("description"),
            html_url=repo.get("url", repo.get("html_url", "")),
            stars=repo.get("stars", 0),
            forks=repo.get("forks", 0),
            language=repo.get("language"),
            is_private=repo.get("is_private", False),
            is_fork=repo.get("is_fork", False),
        )
        for repo in repos
    ]
