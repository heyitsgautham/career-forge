"""
Resume routes: crud
===================
List, create, fetch and delete resumes.
"""

import uuid
from typing import List

import structlog
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.routes.resumes.common import _resume_from_dynamo, router
from app.core.config import settings
from app.core.database import get_db
from app.models.project import Project
from app.models.resume import Resume, ResumeStatus
from app.models.template import Template
from app.models.user import User
from app.schemas.resumes import (
    ResumeCreate,
    ResumeResponse,
)

logger = structlog.get_logger()


@router.get("", response_model=List[ResumeResponse])
async def list_resumes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all resumes for the current user."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service

        items = await dynamo_service.query("Resumes", "userId", str(current_user.id))
        return [ResumeResponse(**_resume_from_dynamo(r)) for r in items]

    result = await db.execute(
        select(Resume).where(Resume.user_id == current_user.id).order_by(Resume.updated_at.desc())
    )
    resumes = result.scalars().all()

    return [
        ResumeResponse(
            id=str(r.id),
            name=r.name,
            template_id=str(r.template_id) if r.template_id else None,
            job_description_id=str(r.job_description_id) if r.job_description_id else None,
            selected_project_ids=[str(pid) for pid in (r.selected_project_ids or [])],
            status=r.status.value,
            latex_content=r.latex_content,
            pdf_path=r.pdf_path,
            error_message=r.error_message,
            created_at=r.created_at.isoformat(),
            updated_at=r.updated_at.isoformat(),
        )
        for r in resumes
    ]


@router.post("", response_model=ResumeResponse)
async def create_resume(
    resume_data: ResumeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new resume draft."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service

        resume_id = dynamo_service.generate_id()
        now = dynamo_service.now_iso()
        item = {
            "userId": str(current_user.id),
            "resumeId": resume_id,
            "name": resume_data.name,
            "templateId": resume_data.template_id,
            "jobDescriptionId": resume_data.job_description_id,
            "selectedProjectIds": resume_data.project_ids or [],
            "status": "draft",
            "createdAt": now,
            "updatedAt": now,
        }
        await dynamo_service.put_item("Resumes", item)
        return ResumeResponse(**_resume_from_dynamo(item))

    template_uuid = None
    project_uuids = []

    # Validate template if provided
    if resume_data.template_id:
        result = await db.execute(
            select(Template).where(Template.id == uuid.UUID(resume_data.template_id))
        )
        template = result.scalar_one_or_none()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        template_uuid = uuid.UUID(resume_data.template_id)

    # Validate projects if provided
    if resume_data.project_ids:
        project_uuids = [uuid.UUID(pid) for pid in resume_data.project_ids]
        result = await db.execute(
            select(Project).where(
                Project.id.in_(project_uuids),
                Project.user_id == current_user.id,
            )
        )
        projects = result.scalars().all()
        if len(projects) != len(project_uuids):
            raise HTTPException(status_code=400, detail="Some projects not found")

    # Create resume
    resume = Resume(
        user_id=current_user.id,
        name=resume_data.name,
        template_id=template_uuid,
        job_description_id=uuid.UUID(resume_data.job_description_id)
        if resume_data.job_description_id
        else None,
        selected_project_ids=project_uuids,
        status=ResumeStatus.DRAFT,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    return ResumeResponse(
        id=str(resume.id),
        name=resume.name,
        template_id=str(resume.template_id) if resume.template_id else None,
        job_description_id=str(resume.job_description_id) if resume.job_description_id else None,
        selected_project_ids=[str(pid) for pid in (resume.selected_project_ids or [])],
        status=resume.status.value,
        latex_content=resume.latex_content,
        pdf_path=resume.pdf_path,
        error_message=resume.error_message,
        created_at=resume.created_at.isoformat(),
        updated_at=resume.updated_at.isoformat(),
    )


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific resume."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service

        item = await dynamo_service.get_item(
            "Resumes", {"userId": str(current_user.id), "resumeId": resume_id}
        )
        if not item:
            raise HTTPException(status_code=404, detail="Resume not found")
        return ResumeResponse(**_resume_from_dynamo(item))

    result = await db.execute(
        select(Resume).where(
            Resume.id == uuid.UUID(resume_id),
            Resume.user_id == current_user.id,
        )
    )
    resume = result.scalar_one_or_none()

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    return ResumeResponse(
        id=str(resume.id),
        name=resume.name,
        template_id=str(resume.template_id) if resume.template_id else None,
        job_description_id=str(resume.job_description_id) if resume.job_description_id else None,
        selected_project_ids=[str(pid) for pid in (resume.selected_project_ids or [])],
        status=resume.status.value,
        latex_content=resume.latex_content,
        pdf_path=resume.pdf_path,
        error_message=resume.error_message,
        created_at=resume.created_at.isoformat(),
        updated_at=resume.updated_at.isoformat(),
    )


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a resume and its S3 files."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service
        from app.services.s3_service import s3_service

        item = await dynamo_service.get_item(
            "Resumes", {"userId": str(current_user.id), "resumeId": resume_id}
        )
        if not item:
            raise HTTPException(status_code=404, detail="Resume not found")

        # Clean up S3 files
        for key_field in ("pdfS3Key", "texS3Key"):
            s3_key = item.get(key_field)
            if s3_key and not s3_key.startswith("/"):
                try:
                    await s3_service.delete_file(s3_key)
                except Exception as e:
                    logger.warning("S3 cleanup failed", key=s3_key, error=str(e))

        await dynamo_service.delete_item(
            "Resumes", {"userId": str(current_user.id), "resumeId": resume_id}
        )
        return {"message": "Resume deleted"}

    result = await db.execute(
        select(Resume).where(
            Resume.id == uuid.UUID(resume_id),
            Resume.user_id == current_user.id,
        )
    )
    resume = result.scalar_one_or_none()

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    await db.delete(resume)
    await db.commit()

    return {"message": "Resume deleted"}
