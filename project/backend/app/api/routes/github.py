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
) -> dict:
    """
    Shared ingestion logic used by both the /ingest endpoint
    and the auto-trigger on first login (1.6.4).
    
    Returns:
        Summary dict with total, processed, failed, lastRunAt
    """
    # Mark ingestion as in_progress
    await dynamo_service.update_item(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Users",
        key={"userId": user_id},
        updates={"ingestionStatus": "in_progress"},
    )

    try:
        # Fetch user-selected repos via installation token (or OAuth fallback)
        repos = await github_service.fetch_user_repos_fast(
            encrypted_token=github_token,
            installation_id=installation_id,
            include_forks=include_forks,
        )

        processed, failed = 0, 0
        for repo_meta in repos:
            try:
                await asyncio.sleep(0.1)  # respect rate limits
                
                # Fetch README, dep files, root dirs
                repo_detail = await github_service.fetch_repo_details(
                    full_name=repo_meta["full_name"],
                    encrypted_token=github_token,
                )
                
                # Bedrock structured summary → .md content
                project_data = await github_service.create_project_from_repo(repo_detail)
                
                # Upload .md to S3, persist to DynamoDB
                project_id = str(uuid.uuid4())
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
            "total": len(repos),
            "processed": processed,
            "failed": failed,
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
    current_user: dict = Depends(get_current_user_dynamo),
):
    """
    Full ingestion pipeline:
    Fetch repos → Bedrock summary → .md to S3 → project to DynamoDB.
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
        )
        return {"status": "done", **summary}
    except Exception as e:
        raise HTTPException(500, f"Ingestion failed: {e}")


@router.get("/ingest-status")
async def get_ingest_status(
    current_user: dict = Depends(get_current_user_dynamo),
):
    """Return ingestionStatus + ingestionSummary from Users table (for frontend polling)."""
    return {
        "status": current_user.get("ingestionStatus", "none"),
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
