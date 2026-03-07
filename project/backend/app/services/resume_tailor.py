"""
Resume Tailor Service (M5)
==========================
Generates JD-tailored resumes that differ from the base resume:
  - Skills reordered (JD-required first)
  - Project bullets rewritten with JD keywords
  - Project selection may change (top 3 for this specific JD)
  - Summary/objective tailored to the specific role

Uses the existing M2 pipeline for LaTeX compilation and S3 upload.
"""

import re
import json as _json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import structlog

from app.services.bedrock_client import bedrock_client
from app.services.dynamo_service import dynamo_service
from app.services.s3_service import s3_service
from app.services.latex_service import latex_service
from app.services.resume_agent import _fill_jakes_template, list_project_summaries


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


TAILOR_SYSTEM_PROMPT = r"""You are an expert resume tailoring agent for software engineers. You have the user's base resume data (project summaries + profile) and a TARGET job description with extracted analysis.

Your job is to RE-GENERATE the resume JSON to MAXIMISE ATS match for this SPECIFIC role.

## TAILORING STRATEGY

1. **Skills Reordering**: Lead with skills that match the JD's required/preferred skills and ATS keywords. Move matching skills to the front of each category.
2. **Project Selection**: Pick the top 3-4 projects that best match this JD (may be different from the base resume's selection).
3. **Bullet Rewriting**: Rewrite project bullets to naturally embed JD keywords and emphasize relevant aspects. Same projects, different emphasis.
4. **Technology Emphasis**: In the tech stack line for each project, lead with JD-relevant technologies.
5. **Skill Categories**: Reorganize skill categories to front-load JD-relevant domains.

## CRITICAL RULES

1. **ANTI-HALLUCINATION**: Only use data from the provided project summaries and user profile. NEVER fabricate metrics, experience, skills, or facts not in the source.
2. **ONE-PAGE FIT**: Max 3 bullet points per project (80-100 chars each). Top 3-4 projects only.
3. **PLAIN TEXT ONLY**: All string values must be plain text. NO LaTeX commands. Use -- for date ranges.
4. **MEANINGFUL DIFFERENCES**: The tailored resume MUST differ noticeably from a generic resume. Skill order, project selection, and bullet wording should all reflect the target JD.
5. **KEYWORD INJECTION**: Naturally weave JD keywords into bullets without being forced or unnatural.

## OUTPUT FORMAT

<tailoring_analysis>
- Target role: [role title]
- Key JD requirements matched: [list]
- Key JD requirements NOT matched: [list]
- Projects selected (in order): [list with reason]
- Skills reordered: [what moved where]
- Keywords injected: [list of JD keywords woven into bullets]
</tailoring_analysis>

<diff_summary>
{
  "skillsReordered": true,
  "projectsChanged": ["proj-A replaced by proj-C", "proj-B kept"],
  "keywordsInjected": ["Docker", "Kubernetes", "CI/CD"],
  "bulletsRewritten": 8,
  "sectionsModified": ["skills", "projects"]
}
</diff_summary>

<resume_json>
{...valid JSON object following the standard resume schema...}
</resume_json>
"""


async def tailor_resume_for_job(
    user_id: str,
    job_id: str,
    personal_info: Optional[Dict[str, Any]] = None,
    education: Optional[List[Dict[str, Any]]] = None,
    experience: Optional[List[Dict[str, Any]]] = None,
    skills: Optional[List[str]] = None,
    certifications: Optional[List[Dict[str, Any]]] = None,
) -> TailorResult:
    """
    Generate a tailored resume for a specific job.

    Takes the user's project summaries + profile data and a specific JD,
    then generates a resume optimized for that JD's requirements.

    Args:
        user_id: User ID
        job_id: Job ID (from Jobs table)
        personal_info: Dict with name, email, etc.
        education: Education list
        experience: Experience list
        skills: Skills list
        certifications: Certifications list

    Returns:
        TailorResult with PDF URL, diff summary, etc.
    """
    # 1. Fetch job data from DynamoDB
    job = await dynamo_service.get_item("Jobs", {"jobId": job_id})
    if not job:
        raise ValueError(f"Job {job_id} not found")

    # 2. Retrieve project summaries from S3
    summaries = await list_project_summaries(user_id)
    if not summaries:
        raise ValueError("No project summaries found. Run GitHub ingestion first.")

    logger.info(
        "Tailoring resume",
        user_id=user_id,
        job_id=job_id,
        company=job.get("company", ""),
        title=job.get("title", ""),
        summary_count=len(summaries),
    )

    # 3. Build JD context from stored job analysis
    jd_context = _build_jd_context(job)

    # 4. Build user context
    projects_context = "\n\n---\n\n".join(summaries)
    extra_context = _build_extra_context(
        personal_info, education, experience, skills, certifications
    )

    # 5. Build tailoring prompt
    user_message = f"""## Project Summaries (from ingested GitHub repos)

{projects_context}

{extra_context}

## TARGET Job Description

**Company:** {job.get('company', 'Unknown')}
**Role:** {job.get('title', 'Unknown')}
**Location:** {job.get('location', 'Not specified')}

### Raw JD Text:
{job.get('description', job.get('rawText', 'No description available'))}

### Extracted Analysis:
- **Category:** {job.get('category', 'N/A')}
- **Required Skills:** {', '.join(_safe_list(job.get('requiredSkills', [])))}
- **Preferred Skills:** {', '.join(_safe_list(job.get('preferredSkills', [])))}
- **ATS Keywords:** {', '.join(_safe_list(job.get('atsKeywords', [])))}
- **Experience Level:** {job.get('experienceLevel', 'N/A')}
- **Key Responsibilities:** {', '.join(_safe_list(job.get('keyResponsibilities', []))[:5]) if job.get('keyResponsibilities') else 'N/A'}

### Match Analysis (from Job Scout):
- **Match Score:** {job.get('matchScore', 'N/A')}%
- **Matched Skills:** {', '.join(_safe_dict(job.get('matchBreakdown', {})).get('matchedSkills', []))}
- **Missing Skills:** {', '.join(_safe_list(job.get('missingSkills', [])))}

INSTRUCTIONS:
Generate a resume JSON that is SPECIFICALLY TAILORED for this role at {job.get('company', 'this company')}.
The resume should differ from a generic base resume in:
1. Skill ordering (JD-required skills first in each category)
2. Project selection (pick projects most relevant to THIS role)
3. Bullet wording (naturally embed ATS keywords from this JD)
4. Technology emphasis (lead with JD-relevant tech in project tech lines)
"""

    # 6. Call Bedrock for tailored resume JSON
    response = await bedrock_client.generate(
        prompt=user_message,
        system_prompt=TAILOR_SYSTEM_PROMPT,
        max_tokens=8192,
        temperature=0.3,
    )

    response = response.replace('\r\n', '\n').replace('\r', '\n')

    # 7. Parse response
    diff_summary = _parse_diff_summary(response)
    resume_data = _parse_resume_json(response)
    match_keywords = diff_summary.get("keywordsInjected", [])

    logger.info(
        "Tailoring complete",
        diff_keys=list(diff_summary.keys()),
        project_count=len(resume_data.get("projects", [])),
    )

    # 8. Build LaTeX from tailored JSON
    latex_content = _fill_jakes_template(resume_data)

    # 9. Compile LaTeX → PDF
    resume_id = dynamo_service.generate_id()
    output_filename = f"tailored_{resume_id[:8]}"

    compilation_result = await latex_service.compile_latex(
        latex_content=latex_content,
        output_filename=output_filename,
        use_docker=False,
    )

    pdf_url = None
    tex_url = None
    compilation_error = None

    # 10. Upload to S3 under tailored/ prefix
    pdf_s3_key = f"{user_id}/tailored/{job_id}.pdf"
    tex_s3_key = f"{user_id}/tailored/{job_id}.tex"

    # Always upload .tex source
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
    else:
        compilation_error = _extract_compilation_error(compilation_result)
        logger.warning(
            "Tailored resume compilation failed",
            error=compilation_error,
            job_id=job_id,
        )

    # 11. Store in Resumes table with jobId reference
    now = dynamo_service.now_iso()
    resume_item = {
        "userId": user_id,
        "resumeId": resume_id,
        "name": f"Tailored - {job.get('company', '')} {job.get('title', '')} {now[:10]}",
        "type": "tailored",
        "jobId": job_id,
        "status": "compiled" if compilation_result.success else "generated",
        "latexContent": latex_content,
        "pdfS3Key": pdf_s3_key if compilation_result.success else None,
        "texS3Key": tex_s3_key,
        "diffSummary": diff_summary,
        "matchKeywords": match_keywords,
        "errorMessage": compilation_error,
        "createdAt": now,
        "updatedAt": now,
    }
    await dynamo_service.put_item("Resumes", resume_item)

    return TailorResult(
        resume_id=resume_id,
        job_id=job_id,
        latex_content=latex_content,
        pdf_url=pdf_url,
        tex_url=tex_url,
        diff_summary=diff_summary,
        match_keywords=match_keywords,
        compilation_error=compilation_error,
    )


def _build_jd_context(job: Dict[str, Any]) -> str:
    """Build a structured JD context string from job data."""
    parts = [
        f"Role: {job.get('title', 'Unknown')}",
        f"Company: {job.get('company', 'Unknown')}",
        f"Required Skills: {', '.join(_safe_list(job.get('requiredSkills', [])))}",
        f"Preferred Skills: {', '.join(_safe_list(job.get('preferredSkills', [])))}",
        f"ATS Keywords: {', '.join(_safe_list(job.get('atsKeywords', [])))}",
        f"Category: {job.get('category', 'N/A')}",
        f"Experience Level: {job.get('experienceLevel', 'N/A')}",
    ]
    return "\n".join(parts)


def _build_extra_context(
    personal_info: Optional[Dict[str, Any]],
    education: Optional[List[Dict[str, Any]]],
    experience: Optional[List[Dict[str, Any]]],
    skills: Optional[List[str]],
    certifications: Optional[List[Dict[str, Any]]],
) -> str:
    """Build extra context from user profile data."""
    parts = []

    if personal_info:
        info_lines = [f"  {k}: {v}" for k, v in personal_info.items() if v]
        if info_lines:
            parts.append("## Personal Information\n" + "\n".join(info_lines))

    if education:
        edu_lines = []
        for i, edu in enumerate(education, 1):
            edu_lines.append(
                f"  Education {i}: {edu.get('degree', '')} in {edu.get('field', '')} "
                f"from {edu.get('school', '')} ({edu.get('dates', '')})"
            )
            if edu.get('gpa'):
                edu_lines.append(f"    GPA: {edu['gpa']}")
        if edu_lines:
            parts.append("## Education\n" + "\n".join(edu_lines))

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
            parts.append("## Work Experience\n" + "\n".join(exp_lines))

    if skills:
        parts.append(f"## Technical Skills\n  {', '.join(skills)}")

    if certifications:
        cert_lines = [f"  - {c.get('name', '')} ({c.get('issuer', '')})" for c in certifications]
        if cert_lines:
            parts.append("## Certifications\n" + "\n".join(cert_lines))

    return "\n\n".join(parts)


def _parse_diff_summary(response: str) -> Dict[str, Any]:
    """Extract diff_summary JSON from response."""
    match = re.search(r"<diff_summary>\s*(.*?)\s*</diff_summary>", response, re.DOTALL)
    if match:
        try:
            return _json.loads(match.group(1).strip())
        except _json.JSONDecodeError:
            logger.warning("Failed to parse diff_summary JSON")

    # Fallback
    return {
        "skillsReordered": True,
        "projectsChanged": [],
        "keywordsInjected": [],
        "bulletsRewritten": 0,
        "sectionsModified": ["projects", "skills"],
    }


def _parse_resume_json(response: str) -> Dict[str, Any]:
    """Extract resume JSON from response."""
    json_match = re.search(r"<resume_json>\s*(.*?)\s*</resume_json>", response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # Fallback: try markdown code blocks
        md_match = re.search(r"```(?:json)?\s*\n(.*?)```", response, re.DOTALL)
        if md_match:
            json_str = md_match.group(1).strip()
        else:
            raise ValueError("Failed to extract resume JSON from tailoring response.")

    try:
        return _json.loads(json_str)
    except _json.JSONDecodeError as e:
        logger.error("Failed to parse tailored resume JSON", error=str(e))
        raise ValueError(f"Invalid JSON in tailoring response: {e}")


def _extract_compilation_error(compilation_result) -> str:
    """Extract a readable error message from compilation result."""
    log_text = getattr(compilation_result, "log", "") or ""
    log_lines = log_text.splitlines()

    error_snippets = []
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
