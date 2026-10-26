"""
Resume routes: generation
=========================
Resume generation, from S3 project summaries (M2) and from a template.
"""

from datetime import datetime
from pathlib import Path

import structlog
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.ids import path_uuid
from app.api.routes.resumes.common import _rank_projects_by_relevance, _resume_from_dynamo, router
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import internal_error
from app.models.job_description import JobDescription
from app.models.project import Project
from app.models.resume import Resume, ResumeStatus
from app.models.template import Template
from app.models.user import User
from app.schemas.resumes import (
    M2GenerateRequest,
    M2GenerateResponse,
    ResumeGenerateRequest,
    ResumeResponse,
)
from app.services.resume_agent import resume_agent

logger = structlog.get_logger()

# project/backend/templates, found from this file's place in app/api/routes/resumes/
_BASE_TEMPLATE = Path(__file__).resolve().parents[4] / "templates" / "base_resume_template.tex"


@router.post("/generate", response_model=M2GenerateResponse)
async def generate_resume_m2(
    body: M2GenerateRequest = None,
    current_user: User = Depends(get_current_user),
):
    """
    M2 Resume Generation: reads project summaries from S3, runs Claude Step 0
    analysis, generates LaTeX, compiles to PDF, uploads everything to S3.

    Input: optional JD text.
    Output: resumeId, pdfUrl, texUrl, analysis block.
    """
    if body is None:
        body = M2GenerateRequest()

    from app.services.resume_agent import generate_resume_from_summaries

    user_id = str(current_user.id)

    # Gather personal info from user profile
    def _safe(attr, default=""):
        v = getattr(current_user, attr, None)
        return v if v is not None else default

    import json as _json

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
        "github": getattr(current_user, "_data", {}).get("githubUsername", "")
        if hasattr(current_user, "_data")
        else "",
    }

    education = _parse_json(_safe("education", None))
    experience = _parse_json(_safe("experience", None))
    skills = _parse_json(_safe("skills", None))
    certifications = _parse_json(_safe("certifications", None))

    try:
        result = await generate_resume_from_summaries(
            user_id=user_id,
            jd=body.jd,
            personal_info=personal_info,
            education=education,
            experience=experience,
            skills=skills,
            certifications=certifications,
        )

        return M2GenerateResponse(
            resume_id=result.resume_id,
            pdf_url=result.pdf_url,
            tex_url=result.tex_url,
            analysis=result.analysis,
            status="compiled" if result.pdf_url else "generated",
            compilation_error=result.compilation_error,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("M2 resume generation failed", error=str(e), user_id=user_id)
        raise internal_error("Resume generation failed. Please try again.") from e


@router.post("/{resume_id}/generate", response_model=ResumeResponse)
async def generate_resume(
    resume_id: str,
    generate_data: ResumeGenerateRequest = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate resume LaTeX content from template and data."""
    # Handle empty body
    if generate_data is None:
        generate_data = ResumeGenerateRequest()

    if settings.USE_DYNAMO:
        import os

        from app.services.dynamo_service import dynamo_service

        item = await dynamo_service.get_item(
            "Resumes", {"userId": str(current_user.id), "resumeId": resume_id}
        )
        if not item:
            raise HTTPException(status_code=404, detail="Resume not found")
        await dynamo_service.update_item(
            "Resumes",
            {"userId": str(current_user.id), "resumeId": resume_id},
            {"status": "generating", "updatedAt": dynamo_service.now_iso()},
        )
        try:
            template_path = str(_BASE_TEMPLATE)
            if not os.path.exists(template_path):
                raise HTTPException(status_code=404, detail="No template file found")
            with open(template_path, "r") as f:
                template_latex = f.read()
            jd_context = None
            if item.get("jobDescriptionId") and generate_data.tailor_to_jd:
                jd = await dynamo_service.get_item("Jobs", {"jobId": item["jobDescriptionId"]})
                if jd:
                    jd_context = {
                        "title": jd.get("title"),
                        "company": jd.get("company"),
                        "required_skills": jd.get("requiredSkills") or [],
                    }
            project_ids = item.get("selectedProjectIds") or []
            if project_ids:
                projects = [
                    p
                    for p in [
                        await dynamo_service.get_item(
                            "Projects", {"userId": str(current_user.id), "projectId": pid}
                        )
                        for pid in project_ids
                    ]
                    if p
                ]
            else:
                projects = await dynamo_service.query("Projects", "userId", str(current_user.id))
            projects = projects[:3]

            def _get(attr, default=""):
                v = getattr(current_user, attr, None)
                return v if v is not None else default

            import json

            def _parse(v):
                if not v:
                    return []
                return json.loads(v) if isinstance(v, str) else v

            personal = generate_data.personal or {
                "name": _get("name") or _get("email", "").split("@")[0],
                "email": _get("email"),
                "phone": _get("phone"),
                "location": _get("location"),
                "linkedin_url": _get("linkedin_url"),
                "website": _get("website"),
            }
            user_data = {
                "personal": personal,
                "skills": generate_data.skills or _parse(_get("skills", None)),
                "projects": [
                    {
                        # DynamoDB project items store the title as "name" and the link as "repoUrl"
                        "title": (p.get("title") or p.get("name", ""))
                        if isinstance(p, dict)
                        else p.title,
                        "description": p.get("description", "")
                        if isinstance(p, dict)
                        else p.description,
                        "technologies": (p.get("technologies") or [])
                        if isinstance(p, dict)
                        else (p.technologies or []),
                        "highlights": (p.get("highlights") or [])
                        if isinstance(p, dict)
                        else (p.highlights if isinstance(p.highlights, list) else []),
                        "url": (p.get("url") or p.get("repoUrl")) if isinstance(p, dict) else p.url,
                    }
                    for p in projects
                ],
                "experience": generate_data.experience or _parse(_get("experience", None)),
                "education": generate_data.education or _parse(_get("education", None)),
                "certifications": _parse(_get("certifications", None)),
            }
            generation_result = await resume_agent.generate_resume(
                template_latex=template_latex, user_data=user_data, jd_context=jd_context
            )
            updates = {
                "latexContent": generation_result.latex_content,
                "status": "generated",
                "updatedAt": dynamo_service.now_iso(),
            }
            await dynamo_service.update_item(
                "Resumes", {"userId": str(current_user.id), "resumeId": resume_id}, updates
            )
            item.update(updates)
        except Exception as e:
            await dynamo_service.update_item(
                "Resumes",
                {"userId": str(current_user.id), "resumeId": resume_id},
                {"status": "error", "errorMessage": str(e), "updatedAt": dynamo_service.now_iso()},
            )
            logger.error("resume_generation_failed", resume_id=resume_id, error=str(e))
            raise internal_error("Resume generation failed. Please try again.") from e
        return ResumeResponse(**_resume_from_dynamo(item))

    # Get resume
    result = await db.execute(
        select(Resume).where(
            Resume.id == path_uuid(resume_id, "Resume"),
            Resume.user_id == current_user.id,
        )
    )
    resume = result.scalar_one_or_none()

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    resume.status = ResumeStatus.GENERATING
    await db.commit()

    try:
        # Get template - use default if not set
        template = None
        if resume.template_id:
            template = await db.get(Template, resume.template_id)

        # Use default template if none found
        if not template:
            # Try to get a system template
            result = await db.execute(select(Template).where(Template.is_system.is_(True)).limit(1))
            template = result.scalar_one_or_none()

        if not template:
            raise HTTPException(
                status_code=404, detail="No template available. Please create or select a template."
            )

        # Get job description if set
        job_description = None
        if resume.job_description_id:
            job_description = await db.get(JobDescription, resume.job_description_id)

        # Get user's projects if none selected
        project_ids = resume.selected_project_ids or []
        if not project_ids:
            # Get all user's projects
            result = await db.execute(select(Project).where(Project.user_id == current_user.id))
            projects = result.scalars().all()
        else:
            result = await db.execute(select(Project).where(Project.id.in_(project_ids)))
            projects = result.scalars().all()

        # Limit projects to top 3, ranked by JD relevance if available
        if len(projects) > 3:
            if job_description:
                # Rank by relevance to JD
                projects = await _rank_projects_by_relevance(projects, job_description)
            projects = projects[:3]

        # Build default personal data from user if not provided
        default_personal = {
            "name": current_user.name or current_user.email.split("@")[0],
            "email": current_user.email,
            "phone": current_user.phone or "",
            "location": current_user.location or "",
            "city": current_user.city or "",
            "state": current_user.state or "",
            "country": current_user.country or "",
            "linkedin_url": current_user.linkedin_url or "",
            "website": current_user.website or "",
            "address_line1": current_user.address_line1 or "",
            "address_line2": current_user.address_line2 or "",
            "zip_code": current_user.zip_code or "",
            "headline": current_user.headline or "",
            "summary": current_user.summary or "",
        }

        # Build default education from user if not provided
        default_education = []
        # First check for education array (new format)
        if hasattr(current_user, "education") and current_user.education:
            import json

            if isinstance(current_user.education, str):
                default_education = json.loads(current_user.education)
            elif isinstance(current_user.education, list):
                default_education = current_user.education
        # Fallback to old single education fields
        elif current_user.institution:
            default_education = [
                {
                    "school": current_user.institution or "",
                    "degree": current_user.degree or "",
                    "field": current_user.field_of_study or "",
                    "dates": current_user.graduation_year or "",
                }
            ]

        # Build default experience from user if not provided
        default_experience = []
        if hasattr(current_user, "experience") and current_user.experience:
            import json

            if isinstance(current_user.experience, str):
                default_experience = json.loads(current_user.experience)
            elif isinstance(current_user.experience, list):
                default_experience = current_user.experience

        # Build default certifications from user if not provided
        default_certifications = []
        if hasattr(current_user, "certifications") and current_user.certifications:
            import json

            if isinstance(current_user.certifications, str):
                default_certifications = json.loads(current_user.certifications)
            elif isinstance(current_user.certifications, list):
                default_certifications = current_user.certifications

        # Build user data
        user_data = {
            "personal": generate_data.personal or default_personal,
            "skills": generate_data.skills or getattr(current_user, "skills", None) or [],
            "projects": [
                {
                    "title": p.title,
                    "description": p.description,
                    "technologies": p.technologies or [],
                    "highlights": p.highlights if isinstance(p.highlights, list) else [],
                    "url": p.url,
                    "dates": f"{p.start_date} - {p.end_date or 'Present'}"
                    if p.start_date
                    else None,
                }
                for p in projects
            ],
            "experience": generate_data.experience or default_experience,
            "education": generate_data.education or default_education,
            "certifications": default_certifications,
        }

        # Get JD context if available
        jd_context = None
        if resume.job_description_id and generate_data.tailor_to_jd:
            jd = await db.get(JobDescription, resume.job_description_id)
            if jd:
                jd_context = {
                    "title": jd.title,
                    "company": jd.company,
                    "required_skills": jd.required_skills or [],
                }

        # Generate LaTeX
        generation_result = await resume_agent.generate_resume(
            template_latex=template.latex_content,
            user_data=user_data,
            jd_context=jd_context,
        )

        resume.latex_content = generation_result.latex_content
        resume.status = ResumeStatus.GENERATED
        resume.generated_at = datetime.utcnow()
        resume.generation_params = {
            "warnings": generation_result.warnings,
            "changes_made": generation_result.changes_made,
            "tokens_used": generation_result.tokens_used,
        }

        if generation_result.warnings:
            resume.error_message = "; ".join(generation_result.warnings)

        # Increment template use count
        template.use_count += 1

        await db.commit()
        await db.refresh(resume)

    except Exception as e:
        resume.status = ResumeStatus.ERROR
        resume.error_message = str(e)
        await db.commit()
        logger.error("resume_generation_failed", resume_id=str(resume.id), error=str(e))
        raise internal_error("Resume generation failed. Please try again.") from e

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
