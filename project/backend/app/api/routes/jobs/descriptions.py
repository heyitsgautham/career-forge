"""
Job routes: descriptions
========================
Saved job descriptions: CRUD and project matching analysis.
"""

from typing import List

from fastapi import Depends, HTTPException

from app.api.deps import get_current_user
from app.api.ids import path_uuid
from app.api.routes.jobs.common import _jd_response_from_dynamo, router
from app.core.config import settings
from app.core.database import get_db
from app.schemas.jobs import (
    AnalyzeResponse,
    JobDescriptionCreate,
    JobDescriptionResponse,
)
from app.services.jd_matching import (
    fallback_required_skills,
    match_projects,
    parse_requirements,
    store_embedding,
)
from app.services.vector_store import VectorStoreService, vector_store


@router.get("", response_model=List[JobDescriptionResponse])
async def list_job_descriptions(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """List all job descriptions for the current user."""
    if settings.USE_DYNAMO:
        from boto3.dynamodb.conditions import Attr

        from app.services.dynamo_service import dynamo_service

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
                JobDescription.id == path_uuid(jd_id, "Job description"),
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
    user_id = str(current_user.id)

    if settings.USE_DYNAMO:
        from app.services.dynamo_service import dynamo_service

        jd = await dynamo_service.get_item("Jobs", {"jobId": jd_id})
        if not jd or jd.get("userId") != user_id:
            raise HTTPException(status_code=404, detail="Job description not found")

        if not jd.get("isAnalyzed"):
            parsed = await parse_requirements(jd["rawText"])
            if parsed is not None:
                updates = {
                    "requiredSkills": parsed.get("required_skills", []),
                    "preferredSkills": parsed.get("preferred_skills", []),
                    "keywords": parsed.get("keywords", []),
                    "parsedRequirements": parsed,
                    "isAnalyzed": True,
                    "updatedAt": dynamo_service.now_iso(),
                }
                embedding_id = await store_embedding(
                    user_id, jd.get("title", ""), jd.get("company", ""), jd["rawText"]
                )
                if embedding_id:
                    updates["embeddingId"] = embedding_id
            else:
                updates = {
                    "requiredSkills": fallback_required_skills(jd["rawText"]),
                    "isAnalyzed": True,
                }
            await dynamo_service.update_item("Jobs", {"jobId": jd_id}, updates)
            jd.update(updates)

        return AnalyzeResponse(
            job_description=_jd_response_from_dynamo(jd),
            matched_projects=await match_projects(
                user_id, jd["rawText"], jd.get("embeddingId"), jd.get("parsedRequirements"), top_n
            ),
        )

    # ---- SQLAlchemy path ----
    from sqlalchemy import select

    from app.models.job_description import JobDescription

    result = await db.execute(
        select(JobDescription).where(
            JobDescription.id == path_uuid(jd_id, "Job description"),
            JobDescription.user_id == current_user.id,
        )
    )
    jd = result.scalar_one_or_none()
    if not jd:
        raise HTTPException(status_code=404, detail="Job description not found")

    if not jd.is_analyzed:
        parsed = await parse_requirements(jd.raw_text)
        if parsed is not None:
            jd.required_skills = parsed.get("required_skills", [])
            jd.preferred_skills = parsed.get("preferred_skills", [])
            jd.keywords = parsed.get("keywords", [])
            jd.parsed_requirements = parsed
            jd.embedding_id = await store_embedding(
                user_id, jd.title, jd.company or "", jd.raw_text
            )
        else:
            jd.required_skills = fallback_required_skills(jd.raw_text)
        jd.is_analyzed = True
        await db.commit()
        await db.refresh(jd)

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
        matched_projects=await match_projects(
            user_id, jd.raw_text, jd.embedding_id, jd.parsed_requirements, top_n
        ),
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
                JobDescription.id == path_uuid(jd_id, "Job description"),
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
