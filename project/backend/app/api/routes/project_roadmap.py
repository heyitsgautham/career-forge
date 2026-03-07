"""
Project Roadmap Routes
=======================
Two-step flow:
  POST /suggest  → 3 project ideas for a domain
  POST /plan     → 7-day roadmap for chosen project
  GET  /list     → user's saved roadmaps
  GET  /{id}     → specific roadmap
  PATCH /{id}/day/{n}/complete → mark a day done
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import structlog

from app.api.deps import get_current_user
from app.services.project_roadmap_service import (
    suggest_projects,
    generate_day_plan,
    get_project_roadmap,
    get_user_project_roadmaps,
    mark_day_complete,
    unlock_all_days,
    delete_project_roadmap,
)


router = APIRouter()
logger = structlog.get_logger()


# ─── Request Models ──────────────────────────────────────────────────────────

class SuggestRequest(BaseModel):
    domain: str = Field(..., min_length=2, max_length=100)


class PlanRequest(BaseModel):
    domain: str = Field(..., min_length=2, max_length=100)
    projectTitle: str = Field(..., min_length=2, max_length=200)
    projectDescription: str = Field(..., min_length=2, max_length=2000)
    techStack: List[str] = Field(default_factory=list)


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/suggest")
async def suggest(
    body: SuggestRequest,
    current_user=Depends(get_current_user),
):
    """Suggest 3 project ideas (medium/hard) for a domain."""
    try:
        return await suggest_projects(
            domain=body.domain,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Suggest failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to suggest projects")


@router.post("/plan")
async def plan(
    body: PlanRequest,
    current_user=Depends(get_current_user),
):
    """Generate a 7-day build plan for the chosen project."""
    user_id = str(current_user.id)

    try:
        return await generate_day_plan(
            user_id=user_id,
            domain=body.domain,
            project_title=body.projectTitle,
            project_description=body.projectDescription,
            tech_stack=body.techStack,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Plan generation failed", error=str(e), userId=user_id)
        raise HTTPException(status_code=500, detail="Failed to generate project plan")


@router.get("/list")
async def list_roadmaps(
    current_user=Depends(get_current_user),
):
    """List all project roadmaps for the current user."""
    user_id = str(current_user.id)
    roadmaps = await get_user_project_roadmaps(user_id)
    return {"roadmaps": roadmaps}


@router.get("/{roadmap_id}")
async def fetch_roadmap(
    roadmap_id: str,
    current_user=Depends(get_current_user),
):
    """Fetch a specific project roadmap."""
    roadmap = await get_project_roadmap(roadmap_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="Project roadmap not found")
    return roadmap


@router.patch("/{roadmap_id}/day/{day_number}/complete")
async def complete_day(
    roadmap_id: str,
    day_number: int,
    current_user=Depends(get_current_user),
):
    """Mark a day in the roadmap as complete."""
    user_id = str(current_user.id)

    try:
        result = await mark_day_complete(
            roadmap_id=roadmap_id,
            day_number=day_number,
            user_id=user_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Day completion failed", error=str(e), roadmapId=roadmap_id, day=day_number)
        raise HTTPException(status_code=500, detail="Failed to mark day complete")


@router.patch("/{roadmap_id}/unlock-all")
async def unlock_all(
    roadmap_id: str,
    current_user=Depends(get_current_user),
):
    """Unlock all days so the user can access any day freely."""
    user_id = str(current_user.id)
    try:
        result = await unlock_all_days(roadmap_id=roadmap_id, user_id=user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unlock all failed", error=str(e), roadmapId=roadmap_id)
        raise HTTPException(status_code=500, detail="Failed to unlock all days")


@router.delete("/{roadmap_id}")
async def remove_roadmap(
    roadmap_id: str,
    current_user=Depends(get_current_user),
):
    """Delete a project roadmap."""
    user_id = str(current_user.id)
    try:
        await delete_project_roadmap(roadmap_id=roadmap_id, user_id=user_id)
        return {"deleted": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Delete roadmap failed", error=str(e), roadmapId=roadmap_id)
        raise HTTPException(status_code=500, detail="Failed to delete roadmap")
