"""
Resume Routes
=============
Resume generation and compilation endpoints.
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


# Helper function to rank projects by JD relevance
async def _rank_projects_by_relevance(projects, job_description):
    """Rank projects by relevance to job description using simple keyword matching."""
    from app.services.gemini_client import gemini_client
    
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
    template_id: Optional[str]
    job_description_id: Optional[str]
    selected_project_ids: List[str]
    status: str
    latex_content: Optional[str]
    pdf_path: Optional[str]
    error_message: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class CompilationResponse(BaseModel):
    success: bool
    pdf_url: Optional[str]
    errors: List[dict]
    warnings: List[str]


# Routes
@router.get("", response_model=List[ResumeResponse])
async def list_resumes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all resumes for the current user."""
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


@router.post("/{resume_id}/compile", response_model=CompilationResponse)
async def compile_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compile resume LaTeX to PDF."""
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
    
    if not resume.latex_content:
        raise HTTPException(status_code=400, detail="No LaTeX content to compile. Generate first.")
    
    resume.status = ResumeStatus.COMPILING
    await db.commit()
    
    try:
        # Validate LaTeX safety
        is_safe, issues = latex_service.validate_latex_safety(resume.latex_content)
        if not is_safe:
            raise HTTPException(
                status_code=400,
                detail=f"LaTeX content contains unsafe commands: {', '.join(issues)}"
            )
        
        # Try to compile (will use online service if Docker/pdflatex unavailable)
        try:
            compilation_result = await latex_service.compile_latex(
                latex_content=resume.latex_content,
                output_filename=f"resume_{resume.id.hex[:8]}",
                use_docker=False,  # Force local compilation which will fallback to online
            )
        except FileNotFoundError:
            # No LaTeX compiler available
            resume.status = ResumeStatus.GENERATED
            await db.commit()
            return CompilationResponse(
                success=False,
                pdf_url=None,
                errors=[{
                    "line": 0,
                    "message": "LaTeX compiler not available. Install TeX Live or use Docker to compile PDFs.",
                    "suggestion": "You can copy the LaTeX code and compile it using Overleaf or a local TeX installation."
                }],
                warnings=["PDF compilation skipped - no compiler available"],
            )
        except Exception as e:
            # Handle any other compilation errors
            logger.error(f"LaTeX compilation error: {e}")
            resume.status = ResumeStatus.ERROR
            resume.error_message = str(e)
            await db.commit()
            return CompilationResponse(
                success=False,
                pdf_url=None,
                errors=[{
                    "line": 0,
                    "message": f"Compilation error: {str(e)}",
                    "suggestion": "Check the LaTeX syntax or try compiling manually"
                }],
                warnings=[],
            )
        
        if compilation_result.success:
            resume.pdf_path = compilation_result.pdf_path
            resume.status = ResumeStatus.COMPILED
            resume.compiled_at = datetime.utcnow()
            resume.compilation_log = compilation_result.log
            resume.compilation_warnings = compilation_result.warnings
            resume.error_message = None
        else:
            resume.status = ResumeStatus.ERROR
            resume.error_message = "; ".join(
                e.message for e in compilation_result.errors
            )
            resume.compilation_log = compilation_result.log
        
        await db.commit()
        
        return CompilationResponse(
            success=compilation_result.success,
            pdf_url=f"/uploads/pdfs/{resume.id.hex[:8]}.pdf" if compilation_result.success else None,
            errors=[
                {"line": e.line, "message": e.message, "suggestion": e.suggestion}
                for e in compilation_result.errors
            ],
            warnings=compilation_result.warnings,
        )
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"Resume compilation failed: {str(e)}")
        logger.error(f"Traceback: {error_traceback}")
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
    """Download compiled PDF."""
    result = await db.execute(
        select(Resume).where(
            Resume.id == uuid.UUID(resume_id),
            Resume.user_id == current_user.id,
        )
    )
    resume = result.scalar_one_or_none()
    
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    if not resume.pdf_path:
        raise HTTPException(status_code=400, detail="PDF not available. Compile first.")
    
    return FileResponse(
        path=resume.pdf_path,
        filename=f"{resume.name.replace(' ', '_')}.pdf",
        media_type="application/pdf",
    )


@router.patch("/{resume_id}/latex")
async def update_latex(
    resume_id: str,
    latex_content: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update resume LaTeX content directly."""
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


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a resume."""
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
