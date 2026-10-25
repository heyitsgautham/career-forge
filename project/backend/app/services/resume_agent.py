"""
Resume Generation Agent (v2)
============================
Generates ATS-friendly LaTeX resumes using Bedrock Claude 4.6 Sonnet.

Single clean pipeline:
  S3 project summaries + user profile → Claude JSON analysis → Python template fill → LaTeX → PDF

Features:
  - Professional summary section
  - Experience-aware project selection (3 projects with experience, 4 without)
  - Step 0 analysis caching to avoid redundant LLM calls
  - Anti-hallucination grounding
"""

import hashlib
import json as _json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import structlog

from app.services.bedrock_client import bedrock_client
from app.services.resume_latex import _fill_jakes_template

# The legacy agent lives in resume_legacy; re-exported for existing callers
from app.services.resume_legacy import (  # noqa: F401
    GenerationResult,
    ResumeGenerationAgent,
    resume_agent,
)
from app.services.resume_prompts import RESUME_JSON_PROMPT

logger = structlog.get_logger()


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class M2GenerationResult:
    """Result of resume generation (S3 summary-based)."""

    latex_content: str
    analysis: str
    resume_id: str
    pdf_url: Optional[str]
    tex_url: Optional[str]
    compilation_error: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# Analysis Cache — avoids re-running Step 0 for same inputs
# ──────────────────────────────────────────────────────────────────────────────

_analysis_cache: Dict[str, Dict[str, Any]] = {}


def _cache_key(summaries: List[str], jd: Optional[str], experience: Optional[list]) -> str:
    """Build a deterministic cache key from inputs."""
    content = _json.dumps(
        {
            "summaries": sorted(summaries),
            "jd": jd or "",
            "has_experience": bool(experience),
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def clear_analysis_cache():
    """Clear the analysis cache (useful for testing)."""
    _analysis_cache.clear()


# ──────────────────────────────────────────────────────────────────────────────
# S3 helpers
# ──────────────────────────────────────────────────────────────────────────────


async def list_project_summaries(user_id: str) -> List[str]:
    """List and download all project summary .md files from S3 for a user."""
    from app.services.s3_service import s3_service

    all_keys = await s3_service.list_objects(prefix=f"{user_id}/")
    summary_keys = [k for k in all_keys if k.endswith("-summary.md") or k.endswith("_summary.md")]

    if not summary_keys:
        summary_keys = [k for k in all_keys if k.endswith(".md")]

    if not summary_keys:
        return []

    summaries = []
    for key in summary_keys:
        try:
            content_bytes = await s3_service.download_file(key)
            summaries.append(content_bytes.decode("utf-8"))
        except Exception as e:
            logger.warning("Failed to download summary", key=key, error=str(e))

    return summaries


# ──────────────────────────────────────────────────────────────────────────────
# Main generation pipeline
# ──────────────────────────────────────────────────────────────────────────────


async def generate_resume_from_summaries(
    user_id: str,
    jd: Optional[str] = None,
    personal_info: Optional[Dict[str, Any]] = None,
    education: Optional[List[Dict[str, Any]]] = None,
    experience: Optional[List[Dict[str, Any]]] = None,
    skills: Optional[List[str]] = None,
    certifications: Optional[List[Dict[str, Any]]] = None,
    achievements: Optional[List[str]] = None,
) -> M2GenerationResult:
    """
    Full pipeline: S3 summaries → Claude analysis + JSON → template fill → compile → upload.

    Args:
        user_id: User ID whose summaries to read
        jd: Optional job description text
        personal_info: Dict with name, email, phone, linkedin_url, website, github
        education: List of education dicts
        experience: List of experience dicts
        skills: List of skill strings
        certifications: List of cert dicts

    Returns:
        M2GenerationResult with latex, analysis, and URLs
    """
    from app.services.dynamo_service import dynamo_service
    from app.services.latex_service import latex_service
    from app.services.s3_service import s3_service

    # 1. Retrieve all project summaries from S3
    summaries = await list_project_summaries(user_id)
    if not summaries:
        raise ValueError("No project summaries found. Run GitHub ingestion first.")

    logger.info("Retrieved project summaries", user_id=user_id, count=len(summaries))

    # 2. Check analysis cache
    cache_key = _cache_key(summaries, jd, experience)
    cached = _analysis_cache.get(cache_key)

    if cached:
        logger.info("Using cached analysis", cache_key=cache_key)
        analysis = cached["analysis"]
        resume_data = cached["resume_data"]
    else:
        # 3. Build context and call Claude
        analysis, resume_data = await _call_claude_for_resume(
            summaries=summaries,
            jd=jd,
            personal_info=personal_info,
            education=education,
            experience=experience,
            skills=skills,
            certifications=certifications,
            achievements=achievements,
        )

        # Cache the result (limit cache size to 50 entries)
        if len(_analysis_cache) >= 50:
            oldest_key = next(iter(_analysis_cache))
            del _analysis_cache[oldest_key]
        _analysis_cache[cache_key] = {"analysis": analysis, "resume_data": resume_data}

    # 4. Build LaTeX from JSON
    latex_content = _fill_jakes_template(resume_data)
    logger.info("Template filled", latex_len=len(latex_content))

    # 5. Compile LaTeX → PDF
    resume_id = dynamo_service.generate_id()
    output_filename = f"resume_{resume_id[:8]}"

    compilation_result = await latex_service.compile_latex(
        latex_content=latex_content,
        output_filename=output_filename,
        use_docker=False,
    )

    pdf_url = None
    tex_url = None

    # 6. Upload to S3
    pdf_s3_key = f"{user_id}/resumes/{resume_id}.pdf"
    tex_s3_key = f"{user_id}/resumes/{resume_id}.tex"

    await s3_service.upload_file(
        key=tex_s3_key,
        data=latex_content.encode("utf-8"),
        content_type="text/plain",
    )
    tex_url = await s3_service.get_presigned_url(tex_s3_key)

    if compilation_result.success and compilation_result.pdf_path:
        from pathlib import Path

        pdf_bytes = Path(compilation_result.pdf_path).read_bytes()
        await s3_service.upload_file(
            key=pdf_s3_key,
            data=pdf_bytes,
            content_type="application/pdf",
        )
        pdf_url = await s3_service.get_presigned_url(pdf_s3_key)
        compilation_error_msg = None
    else:
        compilation_error_msg = _extract_compilation_error(compilation_result)
        logger.warning("LaTeX compilation failed", error=compilation_error_msg)

    # 7. Store resume metadata in DynamoDB
    now = dynamo_service.now_iso()
    resume_item = {
        "userId": user_id,
        "resumeId": resume_id,
        "name": f"Resume {now[:10]}",
        "status": "compiled" if compilation_result.success else "generated",
        "latexContent": latex_content,
        "analysis": analysis,
        "pdfS3Key": pdf_s3_key if compilation_result.success else None,
        "texS3Key": tex_s3_key,
        "jobDescription": jd[:500] if jd else None,
        "errorMessage": compilation_error_msg,
        "createdAt": now,
        "updatedAt": now,
    }
    await dynamo_service.put_item("Resumes", resume_item)

    return M2GenerationResult(
        latex_content=latex_content,
        analysis=analysis,
        resume_id=resume_id,
        pdf_url=pdf_url,
        tex_url=tex_url,
        compilation_error=compilation_error_msg,
    )


async def _call_claude_for_resume(
    summaries: List[str],
    jd: Optional[str],
    personal_info: Optional[Dict[str, Any]],
    education: Optional[List[Dict[str, Any]]],
    experience: Optional[List[Dict[str, Any]]],
    skills: Optional[List[str]],
    certifications: Optional[List[Dict[str, Any]]],
    achievements: Optional[List[str]] = None,
) -> tuple:
    """Call Claude with all context and return (analysis, resume_data) tuple."""

    # Build context
    projects_context = "\n\n---\n\n".join(summaries)

    extra_context_parts = []
    if personal_info:
        info_lines = [f"  {k}: {v}" for k, v in personal_info.items() if v]
        if info_lines:
            extra_context_parts.append("## Personal Information\n" + "\n".join(info_lines))

    if education:
        edu_lines = []
        for i, edu in enumerate(education, 1):
            edu_lines.append(
                f"  Education {i}: {edu.get('degree', '')} in {edu.get('field', '')} "
                f"from {edu.get('school', '')} ({edu.get('dates', '')})"
            )
            if edu.get("gpa"):
                edu_lines.append(f"    GPA: {edu['gpa']}")
            if edu.get("location"):
                edu_lines.append(f"    Location: {edu['location']}")
        if edu_lines:
            extra_context_parts.append("## Education\n" + "\n".join(edu_lines))

    if experience:
        exp_lines = []
        for i, exp in enumerate(experience, 1):
            exp_lines.append(
                f"  Experience {i}: {exp.get('title', '')} at "
                f"{exp.get('company', '')} ({exp.get('dates', '')})"
            )
            for h in exp.get("highlights", []):
                exp_lines.append(f"    - {h}")
        if exp_lines:
            extra_context_parts.append("## Work Experience\n" + "\n".join(exp_lines))

    if skills:
        extra_context_parts.append(f"## Technical Skills\n  {', '.join(skills)}")

    if certifications:
        cert_lines = [
            f"  - {c.get('name', '')} ({c.get('issuer', '')})"
            for c in certifications
            if isinstance(c, dict)
        ]
        if cert_lines:
            extra_context_parts.append("## Certifications\n" + "\n".join(cert_lines))

    if achievements:
        ach_lines = [f"  - {a}" for a in achievements if isinstance(a, str) and a.strip()]
        if ach_lines:
            extra_context_parts.append("## Achievements\n" + "\n".join(ach_lines))

    extra_context = "\n\n".join(extra_context_parts)

    # Experience hint for project count
    has_experience = bool(experience and len(experience) > 0)
    experience_hint = (
        "The user HAS work experience — select 3 projects."
        if has_experience
        else "The user has NO work experience — select 4 projects to compensate."
    )

    user_message = f"""## Project Summaries (from ingested GitHub repos)

{projects_context}

{extra_context}

## Job Description
{jd or 'No JD provided — generate a strong base resume ranking projects by complexity and recency.'}

## Important Context
{experience_hint}

Perform Step 0 analysis first (gap check → JD keyword extraction → project ranking table → project count decision → fact validation), then output the resume JSON."""

    # Call Claude
    response = await bedrock_client.generate(
        prompt=user_message,
        system_prompt=RESUME_JSON_PROMPT,
        max_tokens=8192,
        temperature=0.3,
    )

    response = response.replace("\r\n", "\n").replace("\r", "\n")

    # Parse response
    analysis = ""
    analysis_match = re.search(r"<analysis>(.*?)</analysis>", response, re.DOTALL)
    if analysis_match:
        analysis = analysis_match.group(1).strip()

    json_match = re.search(r"<resume_json>\s*(.*?)\s*</resume_json>", response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        md_match = re.search(r"```(?:json)?\s*\n(.*?)```", response, re.DOTALL)
        if md_match:
            json_str = md_match.group(1).strip()
        else:
            raise ValueError("Failed to extract resume JSON from Claude's response.")

    try:
        resume_data = _json.loads(json_str)
    except _json.JSONDecodeError as e:
        logger.error("Failed to parse resume JSON", error=str(e), json_preview=json_str[:500])
        raise ValueError(f"Claude returned invalid JSON: {e}") from e

    logger.info(
        "Claude generation complete", analysis_len=len(analysis), keys=list(resume_data.keys())
    )
    return analysis, resume_data


def _extract_compilation_error(compilation_result) -> str:
    """Extract a readable error message from compilation result."""
    log_text = getattr(compilation_result, "log", "") or ""
    log_lines = log_text.splitlines()

    error_snippets: list[str] = []
    for i, line in enumerate(log_lines):
        stripped = line.strip()
        if stripped.startswith("! "):
            snippet = stripped
            for j in range(i + 1, min(i + 4, len(log_lines))):
                next_line = log_lines[j].strip()
                if next_line:
                    snippet += f"  →  {next_line}"
                    break
            error_snippets.append(snippet)
            if len(error_snippets) >= 3:
                break

    if error_snippets:
        return " | ".join(error_snippets)
    elif compilation_result.errors:
        return compilation_result.errors[0].message
    else:
        return "PDF compilation failed — LaTeX source saved."
