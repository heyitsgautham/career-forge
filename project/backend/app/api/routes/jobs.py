"""
Job Description Routes
======================
JD management and analysis endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid

from app.core.database import get_db
from app.models.user import User
from app.models.job_description import JobDescription
from app.api.deps import get_current_user
from app.services.matching_engine import matching_engine, MatchScore
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store, VectorStoreService


router = APIRouter()


# Pydantic models
class JobDescriptionCreate(BaseModel):
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    raw_text: str
    source_url: Optional[str] = None


class JobDescriptionResponse(BaseModel):
    id: str
    title: str
    company: Optional[str]
    location: Optional[str]
    raw_text: str
    source_url: Optional[str]
    required_skills: List[str]
    preferred_skills: List[str]
    keywords: List[str]
    is_analyzed: bool

    class Config:
        from_attributes = True


class ProjectMatch(BaseModel):
    project_id: str
    total_score: float
    semantic_score: float
    tech_overlap_score: float
    keyword_score: float
    match_explanation: str


class AnalyzeResponse(BaseModel):
    job_description: JobDescriptionResponse
    matched_projects: List[ProjectMatch]


# Routes
@router.get("", response_model=List[JobDescriptionResponse])
async def list_job_descriptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all job descriptions for the current user."""
    result = await db.execute(
        select(JobDescription)
        .where(JobDescription.user_id == current_user.id)
        .order_by(JobDescription.created_at.desc())
    )
    jds = result.scalars().all()
    
    return [
        JobDescriptionResponse(
            id=str(jd.id),
            title=jd.title,
            company=jd.company,
            location=jd.location,
            raw_text=jd.raw_text,
            source_url=jd.source_url,
            required_skills=jd.required_skills or [],
            preferred_skills=jd.preferred_skills or [],
            keywords=jd.keywords or [],
            is_analyzed=jd.is_analyzed,
        )
        for jd in jds
    ]


@router.post("", response_model=JobDescriptionResponse)
async def create_job_description(
    jd_data: JobDescriptionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new job description."""
    jd = JobDescription(
        user_id=current_user.id,
        title=jd_data.title,
        company=jd_data.company,
        location=jd_data.location,
        raw_text=jd_data.raw_text,
        source_url=jd_data.source_url,
    )
    db.add(jd)
    await db.commit()
    await db.refresh(jd)
    
    return JobDescriptionResponse(
        id=str(jd.id),
        title=jd.title,
        company=jd.company,
        location=jd.location,
        raw_text=jd.raw_text,
        source_url=jd.source_url,
        required_skills=jd.required_skills or [],
        preferred_skills=jd.preferred_skills or [],
        keywords=jd.keywords or [],
        is_analyzed=jd.is_analyzed,
    )


@router.get("/{jd_id}", response_model=JobDescriptionResponse)
async def get_job_description(
    jd_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific job description."""
    result = await db.execute(
        select(JobDescription).where(
            JobDescription.id == uuid.UUID(jd_id),
            JobDescription.user_id == current_user.id,
        )
    )
    jd = result.scalar_one_or_none()
    
    if not jd:
        raise HTTPException(status_code=404, detail="Job description not found")
    
    return JobDescriptionResponse(
        id=str(jd.id),
        title=jd.title,
        company=jd.company,
        location=jd.location,
        raw_text=jd.raw_text,
        source_url=jd.source_url,
        required_skills=jd.required_skills or [],
        preferred_skills=jd.preferred_skills or [],
        keywords=jd.keywords or [],
        is_analyzed=jd.is_analyzed,
    )


@router.post("/{jd_id}/analyze", response_model=AnalyzeResponse)
async def analyze_job_description(
    jd_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    top_n: int = 10,
):
    """Analyze job description and match with user's projects."""
    result = await db.execute(
        select(JobDescription).where(
            JobDescription.id == uuid.UUID(jd_id),
            JobDescription.user_id == current_user.id,
        )
    )
    jd = result.scalar_one_or_none()
    
    if not jd:
        raise HTTPException(status_code=404, detail="Job description not found")
    
    # Analyze JD if not already done
    if not jd.is_analyzed:
        try:
            parsed = await matching_engine.analyze_job_description(jd.raw_text)
            
            jd.required_skills = parsed.get("required_skills", [])
            jd.preferred_skills = parsed.get("preferred_skills", [])
            jd.keywords = parsed.get("keywords", [])
            jd.parsed_requirements = parsed
            
            # Generate and store embedding
            try:
                embedding = await embedding_service.embed_text(jd.raw_text)
                embedding_id = vector_store.generate_embedding_id()
                
                await vector_store.add_embedding(
                    collection_name=VectorStoreService.COLLECTION_JOB_DESCRIPTIONS,
                    embedding_id=embedding_id,
                    embedding=embedding,
                    metadata={
                        "user_id": str(current_user.id),
                        "title": jd.title,
                        "company": jd.company or "",
                    },
                    document=jd.raw_text,
                )
                
                jd.embedding_id = embedding_id
            except ValueError:
                # Embeddings not available
                pass
            
            jd.is_analyzed = True
            await db.commit()
            await db.refresh(jd)
        except Exception as e:
            # If analysis fails, use basic extraction
            import re
            # Simple skill extraction
            common_skills = ["python", "java", "javascript", "react", "node", "sql", "aws", "docker", "kubernetes", "git", "api", "rest", "graphql", "typescript", "fastapi", "django", "flask", "spring", "angular", "vue", "mongodb", "postgresql", "mysql", "redis", "kafka", "rabbitmq", "ci/cd", "devops", "agile", "scrum"]
            text_lower = jd.raw_text.lower()
            found_skills = [s for s in common_skills if s in text_lower]
            jd.required_skills = found_skills[:10]
            jd.is_analyzed = True
            await db.commit()
            await db.refresh(jd)
    
    # Match projects
    matches = []
    jd_embedding = None
    
    try:
        if jd.embedding_id:
            stored = await vector_store.get_by_id(
                VectorStoreService.COLLECTION_JOB_DESCRIPTIONS,
                jd.embedding_id,
            )
            if stored:
                jd_embedding = stored.get("embedding")
        
        if not jd_embedding:
            jd_embedding = await embedding_service.embed_text(jd.raw_text)
        
        matches = await matching_engine.match_projects(
            user_id=str(current_user.id),
            jd_text=jd.raw_text,
            jd_embedding=jd_embedding,
            parsed_jd=jd.parsed_requirements,
            top_n=top_n,
        )
    except (ValueError, Exception) as e:
        # Embeddings/matching not available - return empty matches
        pass
    
    return AnalyzeResponse(
        job_description=JobDescriptionResponse(
            id=str(jd.id),
            title=jd.title,
            company=jd.company,
            location=jd.location,
            raw_text=jd.raw_text,
            source_url=jd.source_url,
            required_skills=jd.required_skills or [],
            preferred_skills=jd.preferred_skills or [],
            keywords=jd.keywords or [],
            is_analyzed=jd.is_analyzed,
        ),
        matched_projects=[
            ProjectMatch(
                project_id=m.project_id,
                total_score=m.total_score,
                semantic_score=m.semantic_score,
                tech_overlap_score=m.tech_overlap_score,
                keyword_score=m.keyword_score,
                match_explanation=m.match_explanation,
            )
            for m in matches
        ],
    )


@router.delete("/{jd_id}")
async def delete_job_description(
    jd_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a job description."""
    result = await db.execute(
        select(JobDescription).where(
            JobDescription.id == uuid.UUID(jd_id),
            JobDescription.user_id == current_user.id,
        )
    )
    jd = result.scalar_one_or_none()
    
    if not jd:
        raise HTTPException(status_code=404, detail="Job description not found")
    
    # Delete embedding
    if jd.embedding_id:
        await vector_store.delete_embedding(
            VectorStoreService.COLLECTION_JOB_DESCRIPTIONS,
            jd.embedding_id,
        )
    
    await db.delete(jd)
    await db.commit()
    
    return {"message": "Job description deleted"}
