"""
Skill Gap & Roadmap Routes
===========================
Endpoints for skill gap analysis and LearnWeave roadmap generation.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import structlog

from app.api.deps import get_current_user
from app.services.gap_analysis import (
    get_all_roles,
    run_gap_analysis,
    get_cached_report,
)
from app.services.roadmap_generator import (
    generate_roadmap,
    get_roadmap,
    get_user_roadmaps,
    mark_milestone_complete,
)


router = APIRouter()
logger = structlog.get_logger()


# ─── Request / Response Models ───────────────────────────────────────────────

class GapAnalysisRequest(BaseModel):
    roleId: str


class RoadmapGenerateRequest(BaseModel):
    roleId: str
    reportId: Optional[str] = None


class MilestoneCompleteRequest(BaseModel):
    weekNumber: int


# ─── Skill Gap Endpoints ─────────────────────────────────────────────────────

@router.get("/roles")
async def list_roles():
    """List available career roles with their skill domains."""
    return {"roles": get_all_roles()}


@router.post("/analyse")
async def analyse_skill_gap(
    body: GapAnalysisRequest,
    current_user=Depends(get_current_user),
):
    """
    Compute skill gap analysis for user vs. target role.
    Uses Claude to score the user's GitHub projects against role benchmarks.
    Results are cached in DynamoDB.
    """
    user_id = str(current_user.id)

    try:
        report = await run_gap_analysis(user_id, body.roleId)
        return report
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Gap analysis failed", error=str(e), userId=user_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to compute skill gap analysis",
        )


@router.get("/report")
async def get_gap_report(
    roleId: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """Fetch the most recent cached gap report for the current user."""
    user_id = str(current_user.id)
    report = await get_cached_report(user_id, role_id=roleId)
    if not report:
        return {"report": None}
    return report


# ─── Roadmap Endpoints ───────────────────────────────────────────────────────

@router.post("/roadmap/generate")
async def generate_learning_roadmap(
    body: RoadmapGenerateRequest,
    current_user=Depends(get_current_user),
):
    """
    Generate a personalised 4-week learning roadmap from gap analysis.
    Uses Claude to create project-based learning plan.
    """
    user_id = str(current_user.id)

    try:
        roadmap = await generate_roadmap(
            user_id=user_id,
            role_id=body.roleId,
            report_id=body.reportId,
        )
        return roadmap
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Roadmap generation failed", error=str(e), userId=user_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate learning roadmap",
        )


@router.get("/roadmap/{roadmap_id}")
async def fetch_roadmap(
    roadmap_id: str,
    current_user=Depends(get_current_user),
):
    """Fetch a specific roadmap by ID."""
    roadmap = await get_roadmap(roadmap_id)
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return roadmap


@router.get("/roadmaps")
async def list_user_roadmaps(
    current_user=Depends(get_current_user),
):
    """List all roadmaps for the current user."""
    user_id = str(current_user.id)
    roadmaps = await get_user_roadmaps(user_id)
    return {"roadmaps": roadmaps}


@router.patch("/roadmap/{roadmap_id}/milestone/{week_number}")
async def complete_milestone(
    roadmap_id: str,
    week_number: int,
    current_user=Depends(get_current_user),
):
    """Mark a roadmap milestone (week) as complete."""
    user_id = str(current_user.id)

    try:
        result = await mark_milestone_complete(
            roadmap_id=roadmap_id,
            week_number=week_number,
            user_id=user_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            "Milestone completion failed",
            error=str(e),
            roadmapId=roadmap_id,
            week=week_number,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to mark milestone complete",
        )
