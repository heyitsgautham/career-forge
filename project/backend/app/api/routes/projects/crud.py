"""
Project routes: CRUD
====================
List, create, read, update and delete the user's projects in DynamoDB.
"""

import uuid
from datetime import datetime

import structlog
from fastapi import Depends, HTTPException

from app.api.deps import get_current_user_dynamo
from app.api.routes.projects.common import _dynamo_to_response, router
from app.core.config import settings
from app.schemas.projects import ProjectCreate, ProjectUpdate
from app.services.bedrock_client import bedrock_client
from app.services.dynamo_service import dynamo_service

logger = structlog.get_logger()


@router.get("")
async def list_projects(
    current_user: dict = Depends(get_current_user_dynamo),
):
    """List all projects for the current user from DynamoDB."""
    items = await dynamo_service.query(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        pk_name="userId",
        pk_value=current_user["userId"],
        scan_forward=False,
    )
    return [_dynamo_to_response(p) for p in items]


@router.get("/user/{user_id}")
async def list_projects_for_user(
    user_id: str,
    current_user: dict = Depends(get_current_user_dynamo),
):
    """List projects for a user from DynamoDB (used by M2 resume generator)."""
    items = await dynamo_service.query(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        pk_name="userId",
        pk_value=user_id,
    )
    return items


@router.post("")
async def create_project(
    project_data: ProjectCreate,
    current_user: dict = Depends(get_current_user_dynamo),
):
    """Create a new manual project — stored in DynamoDB."""
    # Auto-generate highlights if not provided or empty
    highlights = project_data.highlights
    if not highlights or len(highlights) == 0:
        try:
            prompt = f"""Generate exactly 3 concise, technical bullet points for this project. Each point should:
- Be one line (max 80-100 characters)
- Start with a strong action verb (Developed, Implemented, Architected, Designed, Built, Integrated, Optimized)
- Focus on technical implementation and impact
- Include technologies used: {', '.join(project_data.technologies)}
- Be specific about what was accomplished

Project Title: {project_data.title}
Project Description: {project_data.description}

Return ONLY the 3 bullet points, one per line, no numbering or bullets."""

            response = await bedrock_client.generate_content(
                prompt=prompt,
                temperature=0.7,
                max_tokens=300,
            )

            generated_highlights = [
                line.strip() for line in response.strip().split("\n") if line.strip()
            ]
            if len(generated_highlights) >= 3:
                highlights = generated_highlights[:3]
            else:
                highlights = project_data.highlights or []
        except Exception:
            highlights = project_data.highlights or []

    now = datetime.utcnow().isoformat()
    project_id = str(uuid.uuid4())
    user_id = current_user["userId"]

    project_item = {
        "userId": user_id,
        "projectId": project_id,
        "name": project_data.title,
        "description": project_data.description,
        "technologies": project_data.technologies or [],
        "highlights": highlights or [],
        "repoUrl": project_data.url or "",
        "demo_url": project_data.demo_url or "",
        "sourceType": "manual",
        "isFeatured": False,
        "start_date": project_data.start_date,
        "end_date": project_data.end_date,
        "createdAt": now,
        "updatedAt": now,
    }

    await dynamo_service.put_item(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        item=project_item,
    )

    return _dynamo_to_response(project_item)


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    current_user: dict = Depends(get_current_user_dynamo),
):
    """Get a specific project from DynamoDB."""
    project = await dynamo_service.get_item(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        key={"userId": current_user["userId"], "projectId": project_id},
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _dynamo_to_response(project)


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    update_data: ProjectUpdate,
    current_user: dict = Depends(get_current_user_dynamo),
):
    """Update a project in DynamoDB."""
    # Verify ownership
    project = await dynamo_service.get_item(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        key={"userId": current_user["userId"], "projectId": project_id},
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Map frontend fields to DynamoDB attribute names
    field_map = {
        "title": "name",
        "description": "description",
        "technologies": "technologies",
        "highlights": "highlights",
        "url": "repoUrl",
        "demo_url": "demo_url",
        "is_featured": "isFeatured",
    }
    updates = {
        field_map.get(k, k): v for k, v in update_data.model_dump(exclude_unset=True).items()
    }
    updates["updatedAt"] = datetime.utcnow().isoformat()

    await dynamo_service.update_item(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        key={"userId": current_user["userId"], "projectId": project_id},
        updates=updates,
    )
    # Re-fetch to return full updated item
    refreshed = await dynamo_service.get_item(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        key={"userId": current_user["userId"], "projectId": project_id},
    )
    return _dynamo_to_response(refreshed or project)


@router.delete("/all")
async def delete_all_projects(
    current_user: dict = Depends(get_current_user_dynamo),
):
    """Delete ALL projects for the current user from DynamoDB."""
    items = await dynamo_service.query(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        pk_name="userId",
        pk_value=current_user["userId"],
    )
    count = 0
    for item in items:
        await dynamo_service.delete_item(
            table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
            key={"userId": current_user["userId"], "projectId": item["projectId"]},
        )
        count += 1
    return {"message": f"Deleted {count} projects"}


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user: dict = Depends(get_current_user_dynamo),
):
    """Delete a project from DynamoDB."""
    project = await dynamo_service.get_item(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        key={"userId": current_user["userId"], "projectId": project_id},
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await dynamo_service.delete_item(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        key={"userId": current_user["userId"], "projectId": project_id},
    )
    return {"message": "Project deleted"}
