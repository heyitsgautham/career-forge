"""
Job routes: tracking
====================
Application tracking status and the company blacklist.
"""

from fastapi import Depends

from app.api.deps import get_current_user, require_admin
from app.api.routes.jobs.common import router
from app.schemas.jobs import (
    BlacklistRequest,
    TrackingStatusUpdate,
)

# ── Application tracking ─────────────────────────────────────────────────────


@router.post("/scout/{job_id}/track")
async def track_job(
    job_id: str,
    body: TrackingStatusUpdate,
    current_user=Depends(get_current_user),
):
    """Set or update user's tracking status for a job."""
    from app.services.dynamo_service import dynamo_service

    user_id = str(current_user.id)
    now = dynamo_service.now_iso()

    item = {
        "userId": user_id,
        "jobId": job_id,
        "status": body.status,
        "notes": body.notes or "",
        "updatedAt": now,
    }
    await dynamo_service.put_item("UserJobStatuses", item)
    return {"message": "Status updated", "status": body.status}


@router.get("/tracking")
async def get_tracking_statuses(
    current_user=Depends(get_current_user),
):
    """Get all job tracking statuses for the current user."""
    from app.services.dynamo_service import dynamo_service

    user_id = str(current_user.id)
    try:
        statuses = await dynamo_service.query(
            "UserJobStatuses",
            pk_name="userId",
            pk_value=user_id,
        )
    except Exception:
        statuses = []

    return {s["jobId"]: {"status": s["status"], "notes": s.get("notes", "")} for s in statuses}


# ── Blacklist management (admin only) ────────────────────────────────────────


@router.get("/blacklist")
async def list_blacklist(
    current_user=Depends(require_admin),
):
    """List all blacklisted companies."""
    from app.services.dynamo_service import dynamo_service

    try:
        items = await dynamo_service.scan("BlacklistedCompanies")
    except Exception:
        items = []
    return items


@router.post("/blacklist")
async def add_to_blacklist(
    body: BlacklistRequest,
    current_user=Depends(require_admin),
):
    """Add a company to the blacklist."""
    from app.services.dynamo_service import dynamo_service

    item = {
        "companyName": body.companyName,
        "addedBy": str(current_user.id),
        "createdAt": dynamo_service.now_iso(),
    }
    await dynamo_service.put_item("BlacklistedCompanies", item)
    return {"message": f"'{body.companyName}' blacklisted"}


@router.delete("/blacklist/{company_name}")
async def remove_from_blacklist(
    company_name: str,
    current_user=Depends(require_admin),
):
    """Remove a company from the blacklist."""
    from app.services.dynamo_service import dynamo_service

    await dynamo_service.delete_item("BlacklistedCompanies", {"companyName": company_name})
    return {"message": f"'{company_name}' removed from blacklist"}
