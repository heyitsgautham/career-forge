"""
Resume Tailor Service (M5)
==========================
Generates JD-tailored resumes by delegating to the battle-tested
resume_agent pipeline (generate_resume_from_summaries) with a rich JD string.

The agent's RESUME_JSON_PROMPT already handles JD-aware project ranking,
keyword injection, and skill reordering via its Step 0 analysis.

Post-generation, this module re-uploads under the tailored/ S3 prefix
and saves with tailor-specific DynamoDB fields (jobId, type="tailored").
"""

import json as _json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path
import structlog

from app.services.dynamo_service import dynamo_service
from app.services.s3_service import s3_service
from app.services.resume_agent import generate_resume_from_summaries


logger = structlog.get_logger()


def _safe_dict(value, default=None) -> dict:
    """Return value as a dict, parsing JSON strings if needed."""
    if default is None:
        default = {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = _json.loads(value)
            return parsed if isinstance(parsed, dict) else default
        except (_json.JSONDecodeError, TypeError):
            return default
    return default


def _safe_list(value, default=None) -> list:
    """Return value as a list, parsing JSON strings if needed."""
    if default is None:
        default = []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = _json.loads(value)
            return parsed if isinstance(parsed, list) else default
        except (_json.JSONDecodeError, TypeError):
            return default
    return default


@dataclass
class TailorResult:
    """Result of resume tailoring."""
    resume_id: str
    job_id: str
    latex_content: str
    pdf_url: Optional[str]
    tex_url: Optional[str]
    diff_summary: Dict[str, Any]
    match_keywords: List[str]
    compilation_error: Optional[str] = None


async def tailor_resume_for_job(
    user_id: str,
    job_id: str,
    personal_info: Optional[Dict[str, Any]] = None,
    education: Optional[List[Dict[str, Any]]] = None,
    experience: Optional[List[Dict[str, Any]]] = None,
    skills: Optional[List[str]] = None,
    certifications: Optional[List[Dict[str, Any]]] = None,
    achievements: Optional[List[str]] = None,
) -> TailorResult:
    """
    Generate a tailored resume for a specific job.

    Delegates to generate_resume_from_summaries() with a rich JD string
    built from the stored job data, then re-uploads under the tailored/
    S3 prefix.
    """
    # 1. Fetch job data from DynamoDB
    job = await dynamo_service.get_item("Jobs", {"jobId": job_id})
    if not job:
        raise ValueError(f"Job {job_id} not found")

    logger.info(
        "Tailoring resume",
        user_id=user_id,
        job_id=job_id,
        company=job.get("company", ""),
        title=job.get("title", ""),
    )

    # 2. Build a rich JD string from stored job analysis
    jd_text = _build_rich_jd(job)

    # 3. Delegate to the full agent pipeline (same as CLI)
    result = await generate_resume_from_summaries(
        user_id=user_id,
        jd=jd_text,
        personal_info=personal_info,
        education=education,
        experience=experience,
        skills=skills,
        certifications=certifications,
        achievements=achievements,
    )

    # 4. Re-upload under tailored/ S3 prefix (keyed by job_id for overwrite)
    pdf_url = None
    tex_url = None

    tex_s3_key = f"{user_id}/tailored/{job_id}.tex"
    pdf_s3_key = f"{user_id}/tailored/{job_id}.pdf"

    await s3_service.upload_file(
        key=tex_s3_key,
        data=result.latex_content.encode("utf-8"),
        content_type="text/plain",
    )
    tex_url = await s3_service.get_presigned_url(tex_s3_key)

    if result.pdf_url and not result.compilation_error:
        # Download from the base path and re-upload under tailored/
        base_pdf_key = f"{user_id}/resumes/{result.resume_id}.pdf"
        try:
            pdf_bytes = await s3_service.download_file(base_pdf_key)
            await s3_service.upload_file(
                key=pdf_s3_key,
                data=pdf_bytes,
                content_type="application/pdf",
            )
            pdf_url = await s3_service.get_presigned_url(pdf_s3_key)
        except Exception:
            # Fall back to the base URL if re-upload fails
            pdf_url = result.pdf_url

    # 5. Build keywords from the job analysis
    match_keywords = _safe_list(job.get("atsKeywords", []))

    # 6. Store in Resumes table with tailor-specific fields
    now = dynamo_service.now_iso()
    resume_item = {
        "userId": user_id,
        "resumeId": result.resume_id,
        "name": f"Tailored - {job.get('company', '')} {job.get('title', '')} {now[:10]}",
        "type": "tailored",
        "jobId": job_id,
        "status": "compiled" if not result.compilation_error else "generated",
        "latexContent": result.latex_content,
        "analysis": result.analysis,
        "pdfS3Key": pdf_s3_key if not result.compilation_error else None,
        "texS3Key": tex_s3_key,
        "diffSummary": {"delegatedToAgent": True},
        "matchKeywords": match_keywords,
        "errorMessage": result.compilation_error,
        "createdAt": now,
        "updatedAt": now,
    }
    await dynamo_service.put_item("Resumes", resume_item)

    return TailorResult(
        resume_id=result.resume_id,
        job_id=job_id,
        latex_content=result.latex_content,
        pdf_url=pdf_url,
        tex_url=tex_url,
        diff_summary={"delegatedToAgent": True},
        match_keywords=match_keywords,
        compilation_error=result.compilation_error,
    )


def _build_rich_jd(job: Dict[str, Any]) -> str:
    """Build a rich JD string from stored job data + extracted analysis."""
    parts = []

    parts.append(f"Company: {job.get('company', 'Unknown')}")
    parts.append(f"Role: {job.get('title', 'Unknown')}")
    parts.append(f"Location: {job.get('location', 'Not specified')}")
    parts.append("")

    # Raw JD text
    raw = job.get("description", job.get("rawText", ""))
    if raw:
        parts.append("--- Job Description ---")
        parts.append(raw)
        parts.append("")

    # Extracted analysis from JD analyzer
    required = _safe_list(job.get("requiredSkills", []))
    preferred = _safe_list(job.get("preferredSkills", []))
    ats = _safe_list(job.get("atsKeywords", []))
    responsibilities = _safe_list(job.get("keyResponsibilities", []))

    if required:
        parts.append(f"Required Skills: {', '.join(required)}")
    if preferred:
        parts.append(f"Preferred Skills: {', '.join(preferred)}")
    if ats:
        parts.append(f"ATS Keywords: {', '.join(ats)}")
    if job.get("experienceLevel"):
        parts.append(f"Experience Level: {job['experienceLevel']}")
    if job.get("category"):
        parts.append(f"Category: {job['category']}")
    if responsibilities:
        parts.append(f"Key Responsibilities: {', '.join(responsibilities[:5])}")

    # Match analysis from Job Scout
    match_score = job.get("matchScore")
    if match_score is not None:
        parts.append(f"\nMatch Score: {match_score}%")
    matched = _safe_dict(job.get("matchBreakdown", {})).get("matchedSkills", [])
    if matched:
        parts.append(f"Matched Skills: {', '.join(matched)}")
    missing = _safe_list(job.get("missingSkills", []))
    if missing:
        parts.append(f"Missing Skills: {', '.join(missing)}")

    return "\n".join(parts)
