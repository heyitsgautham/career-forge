"""
Applications Routes (M5)
========================
Tailored resume generation + application tracking endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import structlog

from app.core.config import settings
from app.api.deps import get_current_user
from app.services.dynamo_service import dynamo_service


router = APIRouter()
logger = structlog.get_logger()


# ─── Request/Response Models ──────────────────────────────────────────────────

class TailorRequest(BaseModel):
    """Request to generate a tailored resume for a job."""
    jobId: str


class TailorResponse(BaseModel):
    """Response from tailored resume generation."""
    resumeId: str
    pdfUrl: Optional[str] = None
    texUrl: Optional[str] = None
    jobId: str
    matchKeywords: List[str] = []
    diffSummary: dict = {}
    compilationError: Optional[str] = None


class ApplicationCreate(BaseModel):
    """Request to create an application record."""
    jobId: str
    resumeId: Optional[str] = None
    companyName: Optional[str] = None
    roleTitle: Optional[str] = None
    notes: Optional[str] = ""
    url: Optional[str] = None


class ApplicationUpdate(BaseModel):
    """Request to update an application."""
    status: Optional[str] = None
    notes: Optional[str] = None
    resumeId: Optional[str] = None


class ApplicationResponse(BaseModel):
    """Single application record."""
    applicationId: str
    userId: str
    jobId: str
    companyName: str
    roleTitle: str
    resumeId: Optional[str] = None
    status: str
    appliedAt: str
    updatedAt: str
    notes: str = ""
    url: Optional[str] = None


class ApplicationStats(BaseModel):
    """Application stats summary."""
    total: int = 0
    saved: int = 0
    applied: int = 0
    viewed: int = 0
    interviewing: int = 0
    offered: int = 0
    rejected: int = 0


# ─── Tailor Endpoints ─────────────────────────────────────────────────────────

@router.post("/resumes/tailor", response_model=TailorResponse)
async def tailor_resume(
    body: TailorRequest,
    current_user=Depends(get_current_user),
):
    """
    Generate a tailored resume for a specific job.
    Uses user's project summaries + job analysis to create an optimized resume.
    """
    from app.services.resume_tailor import tailor_resume_for_job
    import json as _json

    user_id = str(current_user.id)

    # Gather personal info from user profile
    def _safe(attr, default=""):
        v = getattr(current_user, attr, None)
        return v if v is not None else default

    def _parse_json(v):
        if not v:
            return []
        if isinstance(v, str):
            try:
                return _json.loads(v)
            except _json.JSONDecodeError:
                return []
        return v if isinstance(v, list) else []

    personal_info = {
        "name": _safe("name") or (_safe("email", "").split("@")[0] if _safe("email") else ""),
        "email": _safe("email"),
        "phone": _safe("phone"),
        "location": _safe("location"),
        "linkedin_url": _safe("linkedin_url"),
        "website": _safe("website"),
        "github": getattr(current_user, "_data", {}).get("githubUsername", "") if hasattr(current_user, "_data") else "",
    }

    education = _parse_json(_safe("education", None))
    experience = _parse_json(_safe("experience", None))
    skills = _parse_json(_safe("skills", None))
    certifications = _parse_json(_safe("certifications", None))
    achievements = _parse_json(_safe("achievements", None))

    try:
        result = await tailor_resume_for_job(
            user_id=user_id,
            job_id=body.jobId,
            personal_info=personal_info,
            education=education,
            experience=experience,
            skills=skills,
            certifications=certifications,
            achievements=achievements,
        )

        return TailorResponse(
            resumeId=result.resume_id,
            pdfUrl=result.pdf_url,
            texUrl=result.tex_url,
            jobId=result.job_id,
            matchKeywords=result.match_keywords,
            diffSummary=result.diff_summary,
            compilationError=result.compilation_error,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        error_str = str(e)
        tb = traceback.format_exc()
        logger.error(
            "Resume tailoring failed",
            error=error_str,
            traceback=tb,
            user_id=user_id,
            job_id=body.jobId,
        )
        # Surface a clear message for Bedrock access issues
        if "ResourceNotFoundException" in tb or "use case details" in error_str:
            raise HTTPException(
                status_code=503,
                detail="AI model not available — Bedrock model access has not been granted for this AWS account. "
                       "Submit the Anthropic use-case form in the AWS Bedrock console and retry in ~15 minutes.",
            )
        raise HTTPException(status_code=500, detail=error_str)


@router.get("/resumes/job/{job_id}", response_model=TailorResponse)
async def get_tailored_resume(
    job_id: str,
    current_user=Depends(get_current_user),
):
    """Fetch the tailored resume for a specific job."""
    from app.services.s3_service import s3_service

    user_id = str(current_user.id)

    # Query Resumes table for tailored resume with this jobId
    from boto3.dynamodb.conditions import Attr
    resumes = await dynamo_service.query(
        table="Resumes",
        pk_name="userId",
        pk_value=user_id,
        filter_expression=Attr("jobId").eq(job_id) & Attr("type").eq("tailored"),
    )

    if not resumes:
        raise HTTPException(status_code=404, detail="No tailored resume found for this job")

    # Get the most recent one
    resume = sorted(resumes, key=lambda r: r.get("createdAt", ""), reverse=True)[0]

    # Generate fresh presigned URLs
    pdf_url = None
    tex_url = None
    if resume.get("pdfS3Key"):
        pdf_url = await s3_service.get_presigned_url(resume["pdfS3Key"])
    if resume.get("texS3Key"):
        tex_url = await s3_service.get_presigned_url(resume["texS3Key"])

    return TailorResponse(
        resumeId=resume["resumeId"],
        pdfUrl=pdf_url,
        texUrl=tex_url,
        jobId=job_id,
        matchKeywords=resume.get("matchKeywords", []),
        diffSummary=resume.get("diffSummary", {}),
        compilationError=resume.get("errorMessage"),
    )


# ─── Application CRUD Endpoints ───────────────────────────────────────────────

VALID_STATUSES = {"saved", "applied", "viewed", "interviewing", "offered", "rejected"}


@router.post("/applications", response_model=ApplicationResponse)
async def create_application(
    body: ApplicationCreate,
    current_user=Depends(get_current_user),
):
    """Create an application record. Auto-creates when a tailored resume is generated."""
    user_id = str(current_user.id)

    # Fetch job data for company/role if not provided
    company = body.companyName
    role = body.roleTitle
    if not company or not role:
        job = await dynamo_service.get_item("Jobs", {"jobId": body.jobId})
        if job:
            company = company or job.get("company", "Unknown")
            role = role or job.get("title", "Unknown Role")
        else:
            company = company or "Unknown"
            role = role or "Unknown Role"

    now = dynamo_service.now_iso()
    application_id = dynamo_service.generate_id()

    item = {
        "userId": user_id,
        "applicationId": application_id,
        "jobId": body.jobId,
        "companyName": company,
        "roleTitle": role,
        "resumeId": body.resumeId or "",
        "status": "applied",
        "appliedAt": now,
        "updatedAt": now,
        "notes": body.notes or "",
        "url": body.url or "",
    }

    await dynamo_service.put_item("Applications", item)
    logger.info("Application created", application_id=application_id, company=company, role=role)

    return ApplicationResponse(**item)


@router.get("/applications/user/{user_id}", response_model=List[ApplicationResponse])
async def list_applications(
    user_id: str,
    status_filter: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """List all applications for a user. Supports ?status_filter= query param."""
    # Security: only allow users to see their own applications
    current_id = str(current_user.id)
    if user_id != current_id:
        raise HTTPException(status_code=403, detail="Cannot access other user's applications")

    filter_expr = None
    if status_filter and status_filter in VALID_STATUSES:
        from boto3.dynamodb.conditions import Attr
        filter_expr = Attr("status").eq(status_filter)

    applications = await dynamo_service.query(
        table="Applications",
        pk_name="userId",
        pk_value=user_id,
        filter_expression=filter_expr,
        scan_forward=False,
    )

    return [ApplicationResponse(**app) for app in applications]


@router.patch("/applications/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: str,
    body: ApplicationUpdate,
    current_user=Depends(get_current_user),
):
    """Update application status or notes."""
    user_id = str(current_user.id)

    # Verify ownership
    app = await dynamo_service.get_item(
        "Applications",
        {"userId": user_id, "applicationId": application_id},
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    updates = {"updatedAt": dynamo_service.now_iso()}

    if body.status is not None:
        if body.status not in VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}",
            )
        updates["status"] = body.status

    if body.notes is not None:
        updates["notes"] = body.notes

    if body.resumeId is not None:
        updates["resumeId"] = body.resumeId

    updated = await dynamo_service.update_item(
        table="Applications",
        key={"userId": user_id, "applicationId": application_id},
        updates=updates,
    )

    return ApplicationResponse(**updated)


@router.delete("/applications/{application_id}", status_code=204)
async def delete_application(
    application_id: str,
    current_user=Depends(get_current_user),
):
    """Delete an application record."""
    user_id = str(current_user.id)

    # Verify ownership
    app = await dynamo_service.get_item(
        "Applications",
        {"userId": user_id, "applicationId": application_id},
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    await dynamo_service.delete_item(
        "Applications",
        {"userId": user_id, "applicationId": application_id},
    )
    logger.info("Application deleted", application_id=application_id)


@router.get("/applications/stats/{user_id}", response_model=ApplicationStats)
async def application_stats(
    user_id: str,
    current_user=Depends(get_current_user),
):
    """Get summary counts per status for a user."""
    current_id = str(current_user.id)
    if user_id != current_id:
        raise HTTPException(status_code=403, detail="Cannot access other user's stats")

    applications = await dynamo_service.query(
        table="Applications",
        pk_name="userId",
        pk_value=user_id,
    )

    counts = {s: 0 for s in VALID_STATUSES}
    for app in applications:
        s = app.get("status", "applied")
        if s in counts:
            counts[s] += 1

    return ApplicationStats(
        total=len(applications),
        saved=counts.get("saved", 0),
        applied=counts.get("applied", 0),
        viewed=counts.get("viewed", 0),
        interviewing=counts.get("interviewing", 0),
        offered=counts.get("offered", 0),
        rejected=counts.get("rejected", 0),
    )
