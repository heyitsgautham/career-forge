"""
Resume Routes
=============
Resume generation and compilation endpoints.
Supports both legacy template-fill flow and M2 S3-summary flow.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid
from datetime import datetime
import structlog

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.project import Project
from app.models.template import Template
from app.models.job_description import JobDescription
from app.models.resume import Resume, ResumeStatus
from app.api.deps import get_current_user
from app.services.resume_agent import resume_agent
from app.services.latex_service import latex_service


router = APIRouter()
logger = structlog.get_logger()


# ─── M2 Models ────────────────────────────────────────────────────────────────

class M2GenerateRequest(BaseModel):
    """Request body for M2 resume generation (S3-summary-based)."""
    jd: Optional[str] = None


class M2GenerateResponse(BaseModel):
    """Response from M2 resume generation."""
    resume_id: str
    pdf_url: Optional[str]
    tex_url: Optional[str]
    analysis: str
    status: str
    compilation_error: Optional[str] = None  # Set when LaTeX compiled but PDF failed


# ─── M2 Endpoint ──────────────────────────────────────────────────────────────

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
        "github": getattr(current_user, "_data", {}).get("githubUsername", "") if hasattr(current_user, "_data") else "",
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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("M2 resume generation failed", error=str(e), user_id=user_id)
        raise HTTPException(status_code=500, detail=str(e))


# Helper function to rank projects by JD relevance
async def _rank_projects_by_relevance(projects, job_description):
    """Rank projects by relevance to job description using simple keyword matching."""
    from app.services.bedrock_client import bedrock_client
    
    # Extract JD keywords
    jd_text = f"{job_description.title} {job_description.raw_text} {' '.join(job_description.required_skills or [])}"
    jd_keywords = set(jd_text.lower().split())
    
    # Score each project
    scored_projects = []
    for project in projects:
        # Combine project text
        project_text = f"{project.title} {project.description} {' '.join(project.technologies or [])} {' '.join(project.highlights or [])}"
        project_keywords = set(project_text.lower().split())
        
        # Calculate relevance score (keyword overlap)
        overlap = len(jd_keywords & project_keywords)
        score = overlap
        
        scored_projects.append((score, project))
    
    # Sort by score descending
    scored_projects.sort(key=lambda x: x[0], reverse=True)
    
    return [project for score, project in scored_projects]


def _resume_from_dynamo(r: dict) -> dict:
    return {
        "id": r.get("resumeId", ""),
        "name": r.get("name", ""),
        "template_id": r.get("templateId"),
        "job_description_id": r.get("jobDescriptionId"),
        "selected_project_ids": r.get("selectedProjectIds") or [],
        "status": r.get("status", "draft"),
        "latex_content": r.get("latexContent"),
        "pdf_path": r.get("pdfS3Key"),
        "error_message": r.get("errorMessage"),
        "analysis": r.get("analysis"),
        "tex_s3_key": r.get("texS3Key"),
        "created_at": r.get("createdAt", ""),
        "updated_at": r.get("updatedAt", ""),
    }


# Pydantic models
class ResumeCreate(BaseModel):
    name: str
    template_id: Optional[str] = None
    job_description_id: Optional[str] = None
    project_ids: Optional[List[str]] = None


class ResumeGenerateRequest(BaseModel):
    personal: Optional[dict] = None  # name, email, phone, location, etc.
    skills: Optional[List[str]] = None
    experience: Optional[List[dict]] = None
    education: Optional[List[dict]] = None
    tailor_to_jd: bool = True


class ResumeResponse(BaseModel):
    id: str
    name: str
    template_id: Optional[str] = None
    job_description_id: Optional[str] = None
    selected_project_ids: List[str] = []
    status: str
    latex_content: Optional[str] = None
    pdf_path: Optional[str] = None
    error_message: Optional[str] = None
    analysis: Optional[str] = None
    tex_s3_key: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class CompilationResponse(BaseModel):
    success: bool
    pdf_url: Optional[str]
    errors: List[dict]
    warnings: List[str]


class LatexUpdateRequest(BaseModel):
    """Body for PUT /api/resumes/{id}/latex"""
    latex_content: str


class LatexUpdateResponse(BaseModel):
    id: str
    updated_at: str


class CompileOnDemandRequest(BaseModel):
    """Optional body for POST /api/resumes/{id}/compile"""
    latex_content: Optional[str] = None


class CompileOnDemandResponse(BaseModel):
    pdf_url: Optional[str]
    status: str  # "compiled" | "error"
    error_message: Optional[str] = None


class AiEditRequest(BaseModel):
    """Body for POST /api/resumes/{id}/ai-edit"""
    message: str
    latex_content: str


# Routes
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
        select(Resume)
        .where(Resume.user_id == current_user.id)
        .order_by(Resume.updated_at.desc())
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
        job_description_id=uuid.UUID(resume_data.job_description_id) if resume_data.job_description_id else None,
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
        item = await dynamo_service.get_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id})
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
        from app.services.dynamo_service import dynamo_service
        import os
        item = await dynamo_service.get_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id})
        if not item:
            raise HTTPException(status_code=404, detail="Resume not found")
        await dynamo_service.update_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id}, {"status": "generating", "updatedAt": dynamo_service.now_iso()})
        try:
            template_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "templates", "base_resume_template.tex")
            if not os.path.exists(template_path):
                raise HTTPException(status_code=404, detail="No template file found")
            with open(template_path, "r") as f:
                template_latex = f.read()
            jd_context = None
            if item.get("jobDescriptionId") and generate_data.tailor_to_jd:
                jd = await dynamo_service.get_item("Jobs", {"jobId": item["jobDescriptionId"]})
                if jd:
                    jd_context = {"title": jd.get("title"), "company": jd.get("company"), "required_skills": jd.get("requiredSkills") or []}
            project_ids = item.get("selectedProjectIds") or []
            if project_ids:
                projects = [p for p in [await dynamo_service.get_item("Projects", {"userId": str(current_user.id), "projectId": pid}) for pid in project_ids] if p]
            else:
                projects = await dynamo_service.query("Projects", "userId", str(current_user.id))
            projects = projects[:3]
            def _get(attr, default=""):
                v = getattr(current_user, attr, None)
                return v if v is not None else default
            import json
            def _parse(v):
                if not v: return []
                return json.loads(v) if isinstance(v, str) else v
            personal = generate_data.personal or {"name": _get("name") or _get("email", "").split("@")[0], "email": _get("email"), "phone": _get("phone"), "location": _get("location"), "linkedin_url": _get("linkedin_url"), "website": _get("website")}
            user_data = {
                "personal": personal,
                "skills": generate_data.skills or _parse(_get("skills", None)),
                "projects": [{"title": p.get("title","") if isinstance(p,dict) else p.title, "description": p.get("description","") if isinstance(p,dict) else p.description, "technologies": (p.get("technologies") or []) if isinstance(p,dict) else (p.technologies or []), "highlights": (p.get("highlights") or []) if isinstance(p,dict) else (p.highlights if isinstance(p.highlights,list) else []), "url": p.get("url") if isinstance(p,dict) else p.url} for p in projects],
                "experience": generate_data.experience or _parse(_get("experience", None)),
                "education": generate_data.education or _parse(_get("education", None)),
                "certifications": _parse(_get("certifications", None)),
            }
            generation_result = await resume_agent.generate_resume(template_latex=template_latex, user_data=user_data, jd_context=jd_context)
            updates = {"latexContent": generation_result.latex_content, "status": "generated", "updatedAt": dynamo_service.now_iso()}
            await dynamo_service.update_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id}, updates)
            item.update(updates)
        except Exception as e:
            await dynamo_service.update_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id}, {"status": "error", "errorMessage": str(e), "updatedAt": dynamo_service.now_iso()})
            raise HTTPException(status_code=500, detail=str(e))
        return ResumeResponse(**_resume_from_dynamo(item))

    # Get resume
    result = await db.execute(
        select(Resume).where(
            Resume.id == uuid.UUID(resume_id),
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
            result = await db.execute(
                select(Template).where(Template.is_system == True).limit(1)
            )
            template = result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(status_code=404, detail="No template available. Please create or select a template.")
        
        # Get job description if set
        job_description = None
        if resume.job_description_id:
            job_description = await db.get(JobDescription, resume.job_description_id)
        
        # Get user's projects if none selected
        project_ids = resume.selected_project_ids or []
        if not project_ids:
            # Get all user's projects
            result = await db.execute(
                select(Project).where(Project.user_id == current_user.id)
            )
            projects = result.scalars().all()
        else:
            result = await db.execute(
                select(Project).where(Project.id.in_(project_ids))
            )
            projects = result.scalars().all()
        
        # Limit projects to top 3, ranked by JD relevance if available
        if len(projects) > 3:
            if job_description:
                # Rank by relevance to JD
                projects = await _rank_projects_by_relevance(projects, job_description)
            projects = projects[:3]
        
        # Build default personal data from user if not provided
        default_personal = {
            "name": current_user.name or current_user.email.split('@')[0],
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
        if hasattr(current_user, 'education') and current_user.education:
            import json
            if isinstance(current_user.education, str):
                default_education = json.loads(current_user.education)
            elif isinstance(current_user.education, list):
                default_education = current_user.education
        # Fallback to old single education fields
        elif current_user.institution:
            default_education = [{
                "school": current_user.institution or "",
                "degree": current_user.degree or "",
                "field": current_user.field_of_study or "",
                "dates": current_user.graduation_year or "",
            }]
        
        # Build default experience from user if not provided
        default_experience = []
        if hasattr(current_user, 'experience') and current_user.experience:
            import json
            if isinstance(current_user.experience, str):
                default_experience = json.loads(current_user.experience)
            elif isinstance(current_user.experience, list):
                default_experience = current_user.experience
        
        # Build default certifications from user if not provided
        default_certifications = []
        if hasattr(current_user, 'certifications') and current_user.certifications:
            import json
            if isinstance(current_user.certifications, str):
                default_certifications = json.loads(current_user.certifications)
            elif isinstance(current_user.certifications, list):
                default_certifications = current_user.certifications
        
        # Build user data
        user_data = {
            "personal": generate_data.personal or default_personal,
            "skills": generate_data.skills or getattr(current_user, 'skills', None) or [],
            "projects": [
                {
                    "title": p.title,
                    "description": p.description,
                    "technologies": p.technologies or [],
                    "highlights": p.highlights if isinstance(p.highlights, list) else [],
                    "url": p.url,
                    "dates": f"{p.start_date} - {p.end_date or 'Present'}" if p.start_date else None,
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
        raise HTTPException(status_code=500, detail=str(e))
    
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


@router.post("/{resume_id}/compile", response_model=CompileOnDemandResponse)
async def compile_resume(
    resume_id: str,
    body: Optional[CompileOnDemandRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compile resume LaTeX to PDF. Optional body allows overriding latex_content."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service
        from app.services.s3_service import s3_service
        item = await dynamo_service.get_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id})
        if not item:
            raise HTTPException(status_code=404, detail="Resume not found")
        latex_to_compile = (body.latex_content if body and body.latex_content else None) or item.get("latexContent")
        if not latex_to_compile:
            raise HTTPException(status_code=400, detail="No LaTeX content to compile. Generate first.")
        await dynamo_service.update_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id}, {"status": "compiling", "updatedAt": dynamo_service.now_iso()})
        try:
            is_safe, issues = latex_service.validate_latex_safety(latex_to_compile)
            if not is_safe:
                raise HTTPException(status_code=400, detail=f"Unsafe LaTeX: {', '.join(issues)}")
            output_filename = f"resume_{resume_id[:8]}"
            try:
                compilation_result = await latex_service.compile_latex(latex_content=latex_to_compile, output_filename=output_filename, use_docker=False)
            except FileNotFoundError:
                await dynamo_service.update_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id}, {"status": "generated", "updatedAt": dynamo_service.now_iso()})
                return CompileOnDemandResponse(status="error", pdf_url=None, error_message="LaTeX compiler not available. Install TeX Live or use Overleaf.")
            except Exception as e:
                await dynamo_service.update_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id}, {"status": "error", "errorMessage": str(e), "updatedAt": dynamo_service.now_iso()})
                return CompileOnDemandResponse(status="error", pdf_url=None, error_message=str(e))
            if compilation_result.success:
                # latex_service uploads to "compiled/{output_filename}.pdf" — use that same key
                pdf_s3_key = f"compiled/{output_filename}.pdf"
                await dynamo_service.update_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id}, {"status": "compiled", "pdfS3Key": pdf_s3_key, "updatedAt": dynamo_service.now_iso()})
                try:
                    presigned_url = await s3_service.get_presigned_url(pdf_s3_key)
                except Exception:
                    presigned_url = None
                return CompileOnDemandResponse(status="compiled", pdf_url=presigned_url, error_message=None)
            else:
                error_msg = "; ".join(e.message for e in compilation_result.errors)
                await dynamo_service.update_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id}, {"status": "error", "errorMessage": error_msg, "updatedAt": dynamo_service.now_iso()})
                return CompileOnDemandResponse(status="error", pdf_url=None, error_message=error_msg)
        except HTTPException:
            raise
        except Exception as e:
            await dynamo_service.update_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id}, {"status": "error", "errorMessage": str(e), "updatedAt": dynamo_service.now_iso()})
            raise HTTPException(status_code=500, detail=str(e))

    # Get resume
    result = await db.execute(
        select(Resume).where(
            Resume.id == uuid.UUID(resume_id),
            Resume.user_id == current_user.id,
        )
    )
    resume = result.scalar_one_or_none()
    
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Allow overriding latex content from request body
    latex_to_compile = (body.latex_content if body and body.latex_content else None) or resume.latex_content
    
    if not latex_to_compile:
        raise HTTPException(status_code=400, detail="No LaTeX content to compile. Generate first.")
    
    resume.status = ResumeStatus.COMPILING
    await db.commit()
    
    try:
        # Validate LaTeX safety
        is_safe, issues = latex_service.validate_latex_safety(latex_to_compile)
        if not is_safe:
            raise HTTPException(
                status_code=400,
                detail=f"LaTeX content contains unsafe commands: {', '.join(issues)}"
            )
        
        output_filename = f"resume_{resume.id.hex[:8]}"
        try:
            compilation_result = await latex_service.compile_latex(
                latex_content=latex_to_compile,
                output_filename=output_filename,
                use_docker=False,
            )
        except FileNotFoundError:
            resume.status = ResumeStatus.GENERATED
            await db.commit()
            return CompileOnDemandResponse(
                status="error",
                pdf_url=None,
                error_message="LaTeX compiler not available. Install TeX Live or use Overleaf.",
            )
        except Exception as e:
            logger.error(f"LaTeX compilation error: {e}")
            resume.status = ResumeStatus.ERROR
            resume.error_message = str(e)
            await db.commit()
            return CompileOnDemandResponse(status="error", pdf_url=None, error_message=str(e))
        
        if compilation_result.success:
            resume.pdf_path = compilation_result.pdf_path
            resume.status = ResumeStatus.COMPILED
            resume.compiled_at = datetime.utcnow()
            resume.compilation_log = compilation_result.log
            resume.compilation_warnings = compilation_result.warnings
            resume.error_message = None
            await db.commit()
            return CompileOnDemandResponse(
                status="compiled",
                pdf_url=f"/uploads/pdfs/{output_filename}.pdf",
                error_message=None,
            )
        else:
            error_msg = "; ".join(e.message for e in compilation_result.errors)
            resume.status = ResumeStatus.ERROR
            resume.error_message = error_msg
            resume.compilation_log = compilation_result.log
            await db.commit()
            return CompileOnDemandResponse(status="error", pdf_url=None, error_message=error_msg)
        
    except Exception as e:
        import traceback
        logger.error(f"Resume compilation failed: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        resume.status = ResumeStatus.ERROR
        resume.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{resume_id}/pdf")
async def download_pdf(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download compiled PDF. Returns presigned S3 URL or local file."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service
        from app.services.s3_service import s3_service
        from fastapi.responses import RedirectResponse

        item = await dynamo_service.get_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id})
        if not item:
            raise HTTPException(status_code=404, detail="Resume not found")

        # Try S3 presigned URL first (M2 flow stores full key)
        pdf_key = item.get("pdfS3Key")
        if not pdf_key:
            raise HTTPException(status_code=400, detail="PDF not available. Compile first.")

        # If it's an S3 key (not a local path), generate presigned URL
        if not pdf_key.startswith("/"):
            url = await s3_service.get_presigned_url(pdf_key)
            return RedirectResponse(url=url)

        # Legacy: local file path
        return FileResponse(path=pdf_key, filename=f"{item.get('name','resume').replace(' ','_')}.pdf", media_type="application/pdf")

    result = await db.execute(
        select(Resume).where(
            Resume.id == uuid.UUID(resume_id),
            Resume.user_id == current_user.id,
        )
    )
    resume = result.scalar_one_or_none()


@router.get("/{resume_id}/pdf-url")
async def get_pdf_url(
    resume_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return presigned S3 URL as JSON for iframe preview (avoids redirect + auth header issues)."""
    if not settings.USE_DYNAMO:
        raise HTTPException(status_code=501, detail="Only available with DynamoDB backend")

    from app.services.dynamo_service import dynamo_service
    from app.services.s3_service import s3_service

    item = await dynamo_service.get_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id})
    if not item:
        raise HTTPException(status_code=404, detail="Resume not found")

    pdf_key = item.get("pdfS3Key")
    if not pdf_key:
        raise HTTPException(status_code=400, detail="PDF not available. Compile first.")

    if pdf_key.startswith("/"):
        raise HTTPException(status_code=400, detail="Local file preview not supported via URL")

    url = await s3_service.get_presigned_url(pdf_key)
    return {"url": url}
    
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    if not resume.pdf_path:
        raise HTTPException(status_code=400, detail="PDF not available. Compile first.")
    
    return FileResponse(
        path=resume.pdf_path,
        filename=f"{resume.name.replace(' ', '_')}.pdf",
        media_type="application/pdf",
    )


@router.get("/{resume_id}/tex")
async def download_tex(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download .tex source with Content-Disposition: attachment so the browser saves the file."""
    from fastapi.responses import Response as FastAPIResponse

    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service
        from app.services.s3_service import s3_service

        item = await dynamo_service.get_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id})
        if not item:
            raise HTTPException(status_code=404, detail="Resume not found")

        tex_key = item.get("texS3Key")
        latex_content = item.get("latexContent")
        safe_name = item.get("name", "resume").replace(" ", "_")
        filename = f"{safe_name}.tex"

        if tex_key and not tex_key.startswith("/"):
            try:
                content_bytes = await s3_service.download_file(tex_key)
                return FastAPIResponse(
                    content=content_bytes,
                    media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                )
            except Exception as e:
                logger.warning("s3_tex_download_failed", error=str(e), falling_back="latexContent")

        if latex_content:
            return FastAPIResponse(
                content=latex_content.encode("utf-8"),
                media_type="text/plain; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        raise HTTPException(status_code=404, detail="LaTeX source not available")

    db_result = await db.execute(
        select(Resume).where(
            Resume.id == uuid.UUID(resume_id),
            Resume.user_id == current_user.id,
        )
    )
    resume = db_result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if not resume.latex_content:
        raise HTTPException(status_code=404, detail="LaTeX source not available")

    return FastAPIResponse(
        content=resume.latex_content.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{resume.name.replace(" ", "_")}.tex"'},
    )


@router.patch("/{resume_id}/latex")
async def update_latex(
    resume_id: str,
    latex_content: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update resume LaTeX content directly."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service
        item = await dynamo_service.get_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id})
        if not item:
            raise HTTPException(status_code=404, detail="Resume not found")
        await dynamo_service.update_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id}, {"latexContent": latex_content, "status": "generated", "pdfS3Key": None, "updatedAt": dynamo_service.now_iso()})
        return {"message": "LaTeX updated"}

    result = await db.execute(
        select(Resume).where(
            Resume.id == uuid.UUID(resume_id),
            Resume.user_id == current_user.id,
        )
    )
    resume = result.scalar_one_or_none()
    
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    resume.latex_content = latex_content
    resume.status = ResumeStatus.GENERATED
    resume.pdf_path = None  # Invalidate old PDF
    
    await db.commit()
    
    return {"message": "LaTeX updated"}


@router.put("/{resume_id}/latex", response_model=LatexUpdateResponse)
async def save_latex(
    resume_id: str,
    body: LatexUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    M2.5 — Save updated LaTeX content.
    Also syncs to S3 if a tex_s3_key exists.
    """
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service
        item = await dynamo_service.get_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id})
        if not item:
            raise HTTPException(status_code=404, detail="Resume not found")

        now = dynamo_service.now_iso()
        updates: dict = {"latexContent": body.latex_content, "status": "generated", "updatedAt": now}

        # Sync updated .tex to S3 if we have an existing key
        tex_key = item.get("texS3Key")
        if tex_key and not tex_key.startswith("/"):
            try:
                from app.services.s3_service import s3_service
                await s3_service.upload_file(
                    key=tex_key,
                    data=body.latex_content.encode("utf-8"),
                    content_type="text/plain; charset=utf-8",
                )
            except Exception as e:
                logger.warning("s3_tex_update_failed", error=str(e))

        await dynamo_service.update_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id}, updates)
        return LatexUpdateResponse(id=resume_id, updated_at=now)

    result = await db.execute(
        select(Resume).where(
            Resume.id == uuid.UUID(resume_id),
            Resume.user_id == current_user.id,
        )
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    resume.latex_content = body.latex_content
    resume.status = ResumeStatus.GENERATED
    resume.pdf_path = None  # Invalidate old PDF
    resume.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(resume)
    return LatexUpdateResponse(id=str(resume.id), updated_at=resume.updated_at.isoformat())


@router.post("/{resume_id}/ai-edit")
async def ai_edit_resume(
    resume_id: str,
    body: AiEditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    M2.5 — SSE streaming AI edit.
    Streams Claude's conversational response as 'delta' events; emits a final
    'latex' event with the full updated .tex extracted from a <latex>...</latex> block.
    """
    import asyncio
    from fastapi.responses import StreamingResponse
    from app.services.bedrock_client import bedrock_client

    # Verify ownership
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service
        item = await dynamo_service.get_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id})
        if not item:
            raise HTTPException(status_code=404, detail="Resume not found")
        resume_name = item.get("name", "resume")
    else:
        result = await db.execute(
            select(Resume).where(
                Resume.id == uuid.UUID(resume_id),
                Resume.user_id == current_user.id,
            )
        )
        resume_obj = result.scalar_one_or_none()
        if not resume_obj:
            raise HTTPException(status_code=404, detail="Resume not found")
        resume_name = resume_obj.name

    system_prompt = f"""You are an expert LaTeX resume editor assistant.
The user is editing their resume named "{resume_name}".

You will receive:
1. The current full LaTeX source of the resume
2. A natural language instruction from the user

Your task:
1. Respond conversationally (2-3 sentences) explaining what change you made and why.
2. After your explanation, output the complete modified LaTeX wrapped in <latex> and </latex> tags.
   The user will apply this with one click.

Rules:
- ALWAYS include the full updated LaTeX in <latex>...</latex> tags, even for small changes.
- Keep all existing sections unless explicitly told to remove them.
- Preserve all LaTeX packages and preamble unless there's a good reason to change them.
- Your conversational explanation must come BEFORE the <latex> block.
- Do not include any text after the closing </latex> tag.
"""

    user_message = f"""Current LaTeX source:
```latex
{body.latex_content}
```

User instruction: {body.message}"""

    async def event_stream():
        import json as _json
        import re as _re

        full_response = ""
        emitted_up_to = 0   # char index up to which we have already sent deltas
        latex_started = False
        # "<latex>" is 7 chars — hold back that many chars from the end of the
        # buffer so a partial opening tag never leaks to the client.
        LATEX_TAG_LEN = len("<latex>")

        try:
            async for chunk in bedrock_client.stream_generate(
                prompt=user_message,
                system_prompt=system_prompt,
                max_tokens=8192,
            ):
                full_response += chunk

                if latex_started:
                    # Past the <latex> marker — collect silently for extraction
                    pass
                else:
                    latex_pos = full_response.find("<latex>")
                    if latex_pos != -1:
                        # Emit everything before the tag that we haven't sent yet
                        latex_started = True
                        safe_text = full_response[emitted_up_to:latex_pos]
                        if safe_text:
                            yield f"event: delta\ndata: {_json.dumps({'text': safe_text})}\n\n"
                        emitted_up_to = latex_pos
                    else:
                        # No <latex> yet — emit up to (len - LATEX_TAG_LEN) to
                        # guarantee no partial tag sneaks through
                        safe_end = max(emitted_up_to, len(full_response) - LATEX_TAG_LEN)
                        safe_text = full_response[emitted_up_to:safe_end]
                        if safe_text:
                            yield f"event: delta\ndata: {_json.dumps({'text': safe_text})}\n\n"
                            emitted_up_to = safe_end

                await asyncio.sleep(0)  # yield control

            # Stream ended — flush any remaining safe conversational text
            if not latex_started and emitted_up_to < len(full_response):
                # No <latex> block came at all — emit the rest
                remaining = full_response[emitted_up_to:]
                if remaining:
                    yield f"event: delta\ndata: {_json.dumps({'text': remaining})}\n\n"

            # Extract the <latex>...</latex> block from the full response
            latex_match = _re.search(r"<latex>(.*?)</latex>", full_response, _re.DOTALL)
            if latex_match:
                new_latex = latex_match.group(1).strip()
                yield f"event: latex\ndata: {_json.dumps({'latex': new_latex})}\n\n"

            yield "event: done\ndata: {}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {_json.dumps({'message': str(e)})}\n\n"
            yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
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

        item = await dynamo_service.get_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id})
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

        await dynamo_service.delete_item("Resumes", {"userId": str(current_user.id), "resumeId": resume_id})
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
