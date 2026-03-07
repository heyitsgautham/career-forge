"""
Job Description Routes
======================
JD management, analysis, scraping, and Job Scout endpoints.
Supports both DynamoDB (AWS) and SQLite (local fallback) backends.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
import uuid

from app.core.database import get_db
from app.core.config import settings
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


# ── Job Scout Pydantic models ────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    search_term: str = "Software Developer"
    location: Optional[str] = "India"
    sites: Optional[List[str]] = None
    results_wanted: int = 20


class ScoutJobResponse(BaseModel):
    """A single job card for the Job Scout board."""
    jobId: str
    title: str
    company: str
    location: Optional[str]
    url: Optional[str]
    source: Optional[str]
    datePosted: Optional[str]
    salary: Optional[str]
    jobType: Optional[str]
    category: Optional[str]
    requiredSkills: List[str]
    preferredSkills: List[str]
    missingSkills: List[str]
    experienceLevel: Optional[str]
    atsKeywords: List[str]
    matchScore: Optional[float]
    matchBreakdown: Optional[dict]
    isAnalyzed: bool
    description: Optional[str]

    class Config:
        from_attributes = True


class JobStatsResponse(BaseModel):
    totalJobs: int
    analyzedJobs: int
    averageMatch: Optional[float]
    topCategories: List[dict]
    matchDistribution: dict


def _scout_response_from_dynamo(job: dict) -> ScoutJobResponse:
    """Convert DynamoDB job item to ScoutJobResponse."""
    return ScoutJobResponse(
        jobId=job.get("jobId", ""),
        title=job.get("title", ""),
        company=job.get("company", ""),
        location=job.get("location"),
        url=job.get("url"),
        source=job.get("source"),
        datePosted=job.get("datePosted"),
        salary=job.get("salary"),
        jobType=job.get("jobType"),
        category=job.get("category"),
        requiredSkills=job.get("requiredSkills") or [],
        preferredSkills=job.get("preferredSkills") or [],
        missingSkills=job.get("missingSkills") or [],
        experienceLevel=job.get("experienceLevel"),
        atsKeywords=job.get("atsKeywords") or [],
        matchScore=job.get("matchScore"),
        matchBreakdown=job.get("matchBreakdown"),
        isAnalyzed=job.get("isAnalyzed", False),
        description=job.get("description"),
    )


def _jd_response_from_dynamo(jd: dict) -> JobDescriptionResponse:
    """Convert DynamoDB item to JobDescriptionResponse."""
    return JobDescriptionResponse(
        id=jd.get("jobId", ""),
        title=jd.get("title", ""),
        company=jd.get("company"),
        location=jd.get("location"),
        raw_text=jd.get("rawText", jd.get("description", "")),
        source_url=jd.get("sourceUrl", jd.get("url")),
        required_skills=jd.get("requiredSkills") or [],
        preferred_skills=jd.get("preferredSkills") or [],
        keywords=jd.get("keywords", jd.get("atsKeywords")) or [],
        is_analyzed=jd.get("isAnalyzed", False),
    )


# ---------------------------------------------------------------------------
# Job Scout endpoints (M4)
# ---------------------------------------------------------------------------

@router.post("/scrape", response_model=List[ScoutJobResponse])
async def trigger_scrape(
    req: ScrapeRequest,
    current_user=Depends(get_current_user),
):
    """Trigger a manual job scrape. Scrapes, analyzes, and scores jobs."""
    from app.services.job_scraper import job_scraper
    from app.services.jd_analyzer import jd_analyzer
    from app.services.match_scorer import match_scorer

    user_id = str(current_user.id)

    # 1. Scrape
    stored_jobs = await job_scraper.scrape_and_store(
        user_id=user_id,
        search_term=req.search_term,
        location=req.location,
        sites=req.sites,
        results_wanted=req.results_wanted,
    )

    if not stored_jobs:
        return []

    # 2. Analyze with Bedrock
    await jd_analyzer.analyze_and_store(stored_jobs)

    # 3. Re-fetch analyzed jobs
    from app.services.dynamo_service import dynamo_service
    from boto3.dynamodb.conditions import Attr

    all_jobs = await dynamo_service.scan(
        "Jobs",
        filter_expression=Attr("userId").eq(user_id),
    )

    # 4. Score against user profile
    user_skills = await _get_user_skills(user_id)
    analyzed_jobs = [j for j in all_jobs if j.get("isAnalyzed")]
    if analyzed_jobs:
        await match_scorer.score_all_jobs(user_id, user_skills, analyzed_jobs)

    # 5. Re-fetch with scores and return
    final_jobs = await dynamo_service.scan(
        "Jobs",
        filter_expression=Attr("userId").eq(user_id),
    )
    final_jobs.sort(key=lambda j: j.get("matchScore") or 0, reverse=True)
    return [_scout_response_from_dynamo(j) for j in final_jobs]


@router.get("/matches", response_model=List[ScoutJobResponse])
async def list_matched_jobs(
    current_user=Depends(get_current_user),
    role: Optional[str] = Query(None, description="Filter by category"),
    min_match: Optional[float] = Query(None, alias="minMatch", description="Minimum match %"),
    sort_by: Optional[str] = Query("match", description="Sort: match, date, company"),
    limit: int = Query(50, le=100),
):
    """List all scraped jobs sorted by match score for the authenticated user."""
    from app.services.dynamo_service import dynamo_service
    from boto3.dynamodb.conditions import Attr

    user_id = str(current_user.id)
    jobs = await dynamo_service.scan(
        "Jobs",
        filter_expression=Attr("userId").eq(user_id),
    )

    # Apply filters
    if role:
        role_lower = role.lower()
        jobs = [j for j in jobs if role_lower in (j.get("category") or "").lower()]

    if min_match is not None:
        jobs = [j for j in jobs if (j.get("matchScore") or 0) >= min_match]

    # Sort
    if sort_by == "date":
        jobs.sort(key=lambda j: j.get("datePosted") or "", reverse=True)
    elif sort_by == "company":
        jobs.sort(key=lambda j: (j.get("company") or "").lower())
    else:  # default: match score
        jobs.sort(key=lambda j: j.get("matchScore") or 0, reverse=True)

    return [_scout_response_from_dynamo(j) for j in jobs[:limit]]


@router.get("/stats", response_model=JobStatsResponse)
async def get_job_stats(
    current_user=Depends(get_current_user),
):
    """Summary stats: total jobs, avg match, top categories."""
    from app.services.dynamo_service import dynamo_service
    from boto3.dynamodb.conditions import Attr

    user_id = str(current_user.id)
    jobs = await dynamo_service.scan(
        "Jobs",
        filter_expression=Attr("userId").eq(user_id),
    )

    total = len(jobs)
    analyzed = sum(1 for j in jobs if j.get("isAnalyzed"))

    # Average match
    scores = [j.get("matchScore") for j in jobs if j.get("matchScore") is not None]
    avg_match = round(sum(scores) / len(scores), 1) if scores else None

    # Category counts
    cat_counts: dict = {}
    for j in jobs:
        cat = j.get("category") or "Uncategorized"
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    top_categories = sorted(
        [{"category": k, "count": v} for k, v in cat_counts.items()],
        key=lambda c: c["count"],
        reverse=True,
    )[:5]

    # Match distribution buckets
    dist = {"0-25": 0, "25-50": 0, "50-75": 0, "75-100": 0}
    for s in scores:
        if s < 25:
            dist["0-25"] += 1
        elif s < 50:
            dist["25-50"] += 1
        elif s < 75:
            dist["50-75"] += 1
        else:
            dist["75-100"] += 1

    return JobStatsResponse(
        totalJobs=total,
        analyzedJobs=analyzed,
        averageMatch=avg_match,
        topCategories=top_categories,
        matchDistribution=dist,
    )


async def _get_user_skills(user_id: str) -> List[str]:
    """Fetch user's skills from profile + ingested projects."""
    from app.services.dynamo_service import dynamo_service
    from boto3.dynamodb.conditions import Attr

    skills: set = set()

    # From user profile
    user = await dynamo_service.get_item("Users", {"userId": user_id})
    if user:
        for s in (user.get("skills") or []):
            skills.add(s)

    # From projects
    projects = await dynamo_service.scan(
        "Projects",
        filter_expression=Attr("userId").eq(user_id),
    )
    for proj in projects:
        for tech in (proj.get("technologies") or proj.get("skills") or []):
            skills.add(tech)

    return list(skills)


@router.get("/scout/{job_id}", response_model=ScoutJobResponse)
async def get_scout_job_detail(
    job_id: str,
    current_user=Depends(get_current_user),
):
    """Full job detail + JD analysis + match breakdown for Job Scout."""
    from app.services.dynamo_service import dynamo_service

    job = await dynamo_service.get_item("Jobs", {"jobId": job_id})
    if not job or job.get("userId") != str(current_user.id):
        raise HTTPException(status_code=404, detail="Job not found")
    return _scout_response_from_dynamo(job)


@router.delete("/scout/{job_id}")
async def delete_scout_job(
    job_id: str,
    current_user=Depends(get_current_user),
):
    """Delete a scraped job from Job Scout."""
    from app.services.dynamo_service import dynamo_service

    job = await dynamo_service.get_item("Jobs", {"jobId": job_id})
    if not job or job.get("userId") != str(current_user.id):
        raise HTTPException(status_code=404, detail="Job not found")

    await dynamo_service.delete_item("Jobs", {"jobId": job_id})
    return {"message": "Job deleted"}


# ---------------------------------------------------------------------------
# Legacy JD Routes (manual JD management)
# ---------------------------------------------------------------------------

@router.get("", response_model=List[JobDescriptionResponse])
async def list_job_descriptions(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """List all job descriptions for the current user."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service
        from boto3.dynamodb.conditions import Attr

        jds = await dynamo_service.scan(
            "Jobs",
            filter_expression=Attr("userId").eq(str(current_user.id)),
        )
        return [_jd_response_from_dynamo(jd) for jd in jds]
    else:
        from sqlalchemy import select
        from app.models.job_description import JobDescription

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
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Create a new job description."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service

        job_id = dynamo_service.generate_id()
        now = dynamo_service.now_iso()
        item = {
            "jobId": job_id,
            "userId": str(current_user.id),
            "title": jd_data.title,
            "company": jd_data.company,
            "location": jd_data.location,
            "rawText": jd_data.raw_text,
            "sourceUrl": jd_data.source_url,
            "requiredSkills": [],
            "preferredSkills": [],
            "keywords": [],
            "isAnalyzed": False,
            "createdAt": now,
            "updatedAt": now,
        }
        await dynamo_service.put_item("Jobs", item)
        return _jd_response_from_dynamo(item)
    else:
        from app.models.job_description import JobDescription

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
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Get a specific job description."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service

        jd = await dynamo_service.get_item("Jobs", {"jobId": jd_id})
        if not jd or jd.get("userId") != str(current_user.id):
            raise HTTPException(status_code=404, detail="Job description not found")
        return _jd_response_from_dynamo(jd)
    else:
        from sqlalchemy import select
        from app.models.job_description import JobDescription

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
    current_user=Depends(get_current_user),
    db=Depends(get_db),
    top_n: int = 10,
):
    """Analyze job description and match with user's projects."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service

        jd = await dynamo_service.get_item("Jobs", {"jobId": jd_id})
        if not jd or jd.get("userId") != str(current_user.id):
            raise HTTPException(status_code=404, detail="Job description not found")

        # ---- Analyze if not yet done ----
        if not jd.get("isAnalyzed"):
            try:
                parsed = await matching_engine.analyze_job_description(jd["rawText"])
                updates = {
                    "requiredSkills": parsed.get("required_skills", []),
                    "preferredSkills": parsed.get("preferred_skills", []),
                    "keywords": parsed.get("keywords", []),
                    "parsedRequirements": parsed,
                    "isAnalyzed": True,
                    "updatedAt": dynamo_service.now_iso(),
                }

                # Generate embedding
                try:
                    embedding = await embedding_service.embed_text(jd["rawText"])
                    emb_id = vector_store.generate_embedding_id()
                    await vector_store.add_embedding(
                        collection_name=VectorStoreService.COLLECTION_JOB_DESCRIPTIONS,
                        embedding_id=emb_id,
                        embedding=embedding,
                        metadata={
                            "user_id": str(current_user.id),
                            "title": jd.get("title", ""),
                            "company": jd.get("company", ""),
                        },
                        document=jd["rawText"],
                    )
                    updates["embeddingId"] = emb_id
                except (ValueError, Exception):
                    pass

                await dynamo_service.update_item("Jobs", {"jobId": jd_id}, updates)
                jd.update(updates)
            except Exception:
                # Fallback: basic keyword extraction
                common_skills = [
                    "python", "java", "javascript", "react", "node", "sql",
                    "aws", "docker", "kubernetes", "git", "api", "rest",
                    "graphql", "typescript",
                ]
                text_lower = jd["rawText"].lower()
                found = [s for s in common_skills if s in text_lower][:10]
                await dynamo_service.update_item(
                    "Jobs", {"jobId": jd_id},
                    {"requiredSkills": found, "isAnalyzed": True},
                )
                jd["requiredSkills"] = found
                jd["isAnalyzed"] = True

        # ---- Match projects ----
        matches: list = []
        try:
            jd_embedding = None
            if jd.get("embeddingId"):
                stored = await vector_store.get_by_id(
                    VectorStoreService.COLLECTION_JOB_DESCRIPTIONS,
                    jd["embeddingId"],
                )
                if stored:
                    jd_embedding = stored.get("embedding")
            if not jd_embedding:
                jd_embedding = await embedding_service.embed_text(jd["rawText"])

            matches = await matching_engine.match_projects(
                user_id=str(current_user.id),
                jd_text=jd["rawText"],
                jd_embedding=jd_embedding,
                parsed_jd=jd.get("parsedRequirements"),
                top_n=top_n,
            )
        except (ValueError, Exception):
            pass

        return AnalyzeResponse(
            job_description=_jd_response_from_dynamo(jd),
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
    else:
        # ---- SQLAlchemy path ----
        from sqlalchemy import select
        from app.models.job_description import JobDescription

        result = await db.execute(
            select(JobDescription).where(
                JobDescription.id == uuid.UUID(jd_id),
                JobDescription.user_id == current_user.id,
            )
        )
        jd = result.scalar_one_or_none()
        if not jd:
            raise HTTPException(status_code=404, detail="Job description not found")

        if not jd.is_analyzed:
            try:
                parsed = await matching_engine.analyze_job_description(jd.raw_text)
                jd.required_skills = parsed.get("required_skills", [])
                jd.preferred_skills = parsed.get("preferred_skills", [])
                jd.keywords = parsed.get("keywords", [])
                jd.parsed_requirements = parsed

                try:
                    embedding = await embedding_service.embed_text(jd.raw_text)
                    emb_id = vector_store.generate_embedding_id()
                    await vector_store.add_embedding(
                        collection_name=VectorStoreService.COLLECTION_JOB_DESCRIPTIONS,
                        embedding_id=emb_id,
                        embedding=embedding,
                        metadata={
                            "user_id": str(current_user.id),
                            "title": jd.title,
                            "company": jd.company or "",
                        },
                        document=jd.raw_text,
                    )
                    jd.embedding_id = emb_id
                except ValueError:
                    pass

                jd.is_analyzed = True
                await db.commit()
                await db.refresh(jd)
            except Exception:
                common_skills = [
                    "python", "java", "javascript", "react", "node", "sql",
                    "aws", "docker", "kubernetes", "git", "api", "rest",
                    "graphql", "typescript",
                ]
                text_lower = jd.raw_text.lower()
                jd.required_skills = [s for s in common_skills if s in text_lower][:10]
                jd.is_analyzed = True
                await db.commit()
                await db.refresh(jd)

        matches = []
        try:
            jd_embedding = None
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
        except (ValueError, Exception):
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
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Delete a job description."""
    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service

        jd = await dynamo_service.get_item("Jobs", {"jobId": jd_id})
        if not jd or jd.get("userId") != str(current_user.id):
            raise HTTPException(status_code=404, detail="Job description not found")

        if jd.get("embeddingId"):
            await vector_store.delete_embedding(
                VectorStoreService.COLLECTION_JOB_DESCRIPTIONS,
                jd["embeddingId"],
            )

        await dynamo_service.delete_item("Jobs", {"jobId": jd_id})
        return {"message": "Job description deleted"}
    else:
        from sqlalchemy import select
        from app.models.job_description import JobDescription

        result = await db.execute(
            select(JobDescription).where(
                JobDescription.id == uuid.UUID(jd_id),
                JobDescription.user_id == current_user.id,
            )
        )
        jd = result.scalar_one_or_none()
        if not jd:
            raise HTTPException(status_code=404, detail="Job description not found")

        if jd.embedding_id:
            await vector_store.delete_embedding(
                VectorStoreService.COLLECTION_JOB_DESCRIPTIONS,
                jd.embedding_id,
            )

        await db.delete(jd)
        await db.commit()
        return {"message": "Job description deleted"}
