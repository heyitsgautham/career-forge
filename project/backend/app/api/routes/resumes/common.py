"""Router and helpers shared by the resume route modules.

Every module registers its endpoints on this one router, so the routes keep
their original order and the empty-path list and create routes still work.
"""

from fastapi import APIRouter

router = APIRouter()


async def _rank_projects_by_relevance(projects, job_description):
    """Rank projects by relevance to job description using simple keyword matching."""

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
        "job_id": r.get("jobId"),
        "type": r.get("type", "standard"),
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
