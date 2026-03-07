"""
GitHub Ingestion Routes
=======================
DynamoDB-native endpoints for GitHub repo ingestion pipeline.
Replaces the old SQLAlchemy-based /api/projects/ingest/github.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
import structlog

from app.core.config import settings
from app.api.deps import get_current_user_dynamo
from app.services.github_service import github_service
from app.services.dynamo_service import dynamo_service

logger = structlog.get_logger()

router = APIRouter()


async def run_ingestion(
    user_id: str,
    github_token: str,
    installation_id: Optional[int] = None,
    include_forks: bool = True,
    mode: str = "sync",  # "sync" = refresh existing | "import_new" = import missing
) -> dict:
    """
    Shared ingestion logic.

    mode="sync"       — re-ingests only repos already in the Projects table (updates in-place)
    mode="import_new" — ingests only repos NOT yet in the Projects table (skips existing)

    Returns:
        Summary dict with total, processed, failed, mode, lastRunAt
    """
    # Mark ingestion as in_progress
    await dynamo_service.update_item(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Users",
        key={"userId": user_id},
        updates={"ingestionStatus": "in_progress", "ingestionMode": mode, "ingestionStartedAt": datetime.utcnow().isoformat()},
    )

    try:
        # Fetch all repos the installation has access to
        repos = await github_service.fetch_user_repos_fast(
            encrypted_token=github_token,
            installation_id=installation_id,
            include_forks=include_forks,
        )

        # Fetch existing github projects from DynamoDB
        existing_items = await dynamo_service.query(
            table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
            pk_name="userId",
            pk_value=user_id,
        )
        # Map githubId (str) → projectId for existing imports
        github_id_to_project_id: dict = {
            str(item["githubId"]): item["projectId"]
            for item in existing_items
            if item.get("githubId") and item.get("sourceType") == "github"
        }
        existing_github_ids = set(github_id_to_project_id.keys())

        logger.info(
            "run_ingestion: filtering repos",
            mode=mode,
            total_github=len(repos),
            already_imported=len(existing_github_ids),
        )

        # Filter based on mode
        if mode == "sync":
            # Only repos already in DynamoDB
            repos_to_process = [
                r for r in repos if str(r.get("github_id")) in existing_github_ids
            ]
        elif mode == "import_new":
            # Only repos NOT yet in DynamoDB
            repos_to_process = [
                r for r in repos if str(r.get("github_id")) not in existing_github_ids
            ]
        else:
            repos_to_process = repos

        logger.info("run_ingestion: repos to process", count=len(repos_to_process), mode=mode)

        processed, failed = 0, 0
        for repo_meta in repos_to_process:
            try:
                await asyncio.sleep(0.1)  # respect rate limits

                # Fetch README, dep files, root dirs
                repo_detail = await github_service.fetch_repo_details(
                    full_name=repo_meta["full_name"],
                    encrypted_token=github_token,
                )

                # Bedrock structured summary → .md content
                project_data = await github_service.create_project_from_repo(repo_detail)

                # For sync: reuse existing projectId so put_item overwrites in place
                # For import_new: generate a fresh UUID
                existing_pid = github_id_to_project_id.get(str(repo_meta.get("github_id")))
                project_id = existing_pid if (mode == "sync" and existing_pid) else str(uuid.uuid4())

                await github_service.ingest_and_embed_repo(
                    repo_data=repo_detail,
                    project_data=project_data,
                    user_id=user_id,
                    project_id=project_id,
                )
                processed += 1
            except Exception as e:
                logger.warning(
                    "Failed to ingest repo",
                    repo=repo_meta.get("name", "unknown"),
                    error=str(e),
                )
                failed += 1

        # Update ingestion status
        summary = {
            "total": len(repos_to_process),
            "processed": processed,
            "failed": failed,
            "mode": mode,
            "lastRunAt": datetime.utcnow().isoformat(),
        }
        await dynamo_service.update_item(
            table=f"{settings.DYNAMO_TABLE_PREFIX}Users",
            key={"userId": user_id},
            updates={"ingestionStatus": "done", "ingestionSummary": summary},
        )
        return summary

    except Exception as e:
        await dynamo_service.update_item(
            table=f"{settings.DYNAMO_TABLE_PREFIX}Users",
            key={"userId": user_id},
            updates={"ingestionStatus": "failed"},
        )
        raise


@router.post("/ingest")
async def ingest_github_repos(
    include_forks: bool = True,
    mode: str = "sync",
    current_user: dict = Depends(get_current_user_dynamo),
):
    """
    GitHub ingestion pipeline.
    mode=sync        — refresh only already-imported repos (default)
    mode=import_new  — import repos not yet in the Projects table
    """
    user_id = current_user["userId"]
    github_token = current_user.get("githubToken")
    installation_id = current_user.get("githubInstallationId")

    if not github_token:
        raise HTTPException(400, "No GitHub token. Please re-connect GitHub.")

    try:
        summary = await run_ingestion(
            user_id=user_id,
            github_token=github_token,
            installation_id=installation_id,
            include_forks=include_forks,
            mode=mode,
        )
        return {"status": "done", **summary}
    except Exception as e:
        raise HTTPException(500, f"Ingestion failed: {e}")


@router.get("/ingest-status")
async def get_ingest_status(
    current_user: dict = Depends(get_current_user_dynamo),
):
    """Return ingestionStatus + ingestionSummary from Users table (for frontend polling)."""
    status = current_user.get("ingestionStatus", "none")
    # Detect stale in_progress: if ingestionStartedAt is missing (old record) or job
    # has been running for more than 10 minutes, treat as stale so frontend stops polling.
    if status == "in_progress":
        started_at = current_user.get("ingestionStartedAt")
        if not started_at:
            status = "stale"
        else:
            try:
                elapsed = (datetime.utcnow() - datetime.fromisoformat(started_at)).total_seconds()
                if elapsed > 600:
                    status = "stale"
            except (ValueError, TypeError):
                status = "stale"
    return {
        "status": status,
        "summary": current_user.get("ingestionSummary"),
    }


@router.get("/projects")
async def list_github_projects(
    current_user: dict = Depends(get_current_user_dynamo),
):
    """
    Query careerforge-Projects table by userId.
    Returns all ingested projects for the logged-in user.
    """
    user_id = current_user["userId"]
    items = await dynamo_service.query(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        pk_name="userId",
        pk_value=user_id,
    )
    return items
