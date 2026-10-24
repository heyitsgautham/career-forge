"""Router and DynamoDB mapping helpers shared by the job route modules.

Every module registers its endpoints on this one router. Fixed paths such as
/matches and /stats must be registered before the /{jd_id} catch-all.
"""

from typing import Optional

from fastapi import APIRouter

from app.schemas.jobs import (
    JobDescriptionResponse,
    ScoutJobResponse,
)

router = APIRouter()


def _to_str(val) -> Optional[str]:
    """Safely coerce a DynamoDB value to str, handling int/Decimal/list."""
    if val is None:
        return None
    if isinstance(val, list):
        return ", ".join(str(v) for v in val) if val else None
    return str(val)


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
        salary=_to_str(job.get("salary")),
        jobType=job.get("jobType"),
        category=_to_str(job.get("category")),
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
