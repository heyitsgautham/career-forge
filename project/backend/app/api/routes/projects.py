"""
Projects Routes
===============
Project management and GitHub ingestion endpoints.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import re
import uuid

import structlog

from app.core.config import settings
from app.api.deps import get_current_user, get_current_user_dynamo
from app.services.github_service import github_service
from app.services.dynamo_service import dynamo_service
from app.services.bedrock_client import bedrock_client


router = APIRouter()
logger = structlog.get_logger()


# Pydantic models
class ProjectCreate(BaseModel):
    title: str
    description: str
    technologies: List[str]
    highlights: Optional[List[str]] = None
    url: Optional[str] = None
    demo_url: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    technologies: Optional[List[str]] = None
    highlights: Optional[List[str]] = None
    url: Optional[str] = None
    demo_url: Optional[str] = None
    is_featured: Optional[bool] = None


class ProjectResponse(BaseModel):
    id: str
    title: str
    description: str
    technologies: List[str]
    highlights: List[str]
    url: Optional[str]
    demo_url: Optional[str]
    source_type: str
    is_verified: bool
    is_featured: bool
    start_date: Optional[str]
    end_date: Optional[str]

    class Config:
        from_attributes = True


class GitHubIngestRequest(BaseModel):
    repo_urls: Optional[List[str]] = None
    full_names: Optional[List[str]] = None  # preferred: skip URL parsing entirely
    include_forks: bool = False
    include_private: bool = True
    sync_all: bool = False


class GitHubRepoResponse(BaseModel):
    id: str
    full_name: str
    name: str
    description: Optional[str]
    stars: int
    languages: dict
    topics: List[str]
    project_id: Optional[str]


def _dynamo_to_response(p: dict) -> dict:
    """Normalise a DynamoDB project item to frontend-expected shape."""
    return {
        "id":           p.get("projectId") or p.get("id", ""),
        "title":        p.get("name") or p.get("title", ""),
        "description":  p.get("description", ""),
        "technologies": p.get("technologies") or [],
        "highlights":   p.get("highlights") or [],
        "url":          p.get("repoUrl") or p.get("url") or p.get("demo_url"),
        "demo_url":     p.get("demo_url"),
        "source_type":  p.get("sourceType", "github"),
        "is_verified":  True,
        "is_featured":  p.get("isFeatured", False),
        "start_date":   p.get("start_date"),
        "end_date":     p.get("end_date"),
        "created_at":   p.get("createdAt", ""),
    }


# Routes
@router.get("")
async def list_projects(
    current_user: dict = Depends(get_current_user_dynamo),
):
    """List all projects for the current user from DynamoDB."""
    items = await dynamo_service.query(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        pk_name="userId",
        pk_value=current_user["userId"],
        scan_forward=False,
    )
    return [_dynamo_to_response(p) for p in items]


@router.get("/user/{user_id}")
async def list_projects_for_user(
    user_id: str,
    current_user: dict = Depends(get_current_user_dynamo),
):
    """List projects for a user from DynamoDB (used by M2 resume generator)."""
    items = await dynamo_service.query(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        pk_name="userId",
        pk_value=user_id,
    )
    return items


@router.post("")
async def create_project(
    project_data: ProjectCreate,
    current_user: dict = Depends(get_current_user_dynamo),
):
    """Create a new manual project — stored in DynamoDB."""
    # Auto-generate highlights if not provided or empty
    highlights = project_data.highlights
    if not highlights or len(highlights) == 0:
        try:
            from app.services.bedrock_client import bedrock_client
            
            prompt = f"""Generate exactly 3 concise, technical bullet points for this project. Each point should:
- Be one line (max 80-100 characters)
- Start with a strong action verb (Developed, Implemented, Architected, Designed, Built, Integrated, Optimized)
- Focus on technical implementation and impact
- Include technologies used: {', '.join(project_data.technologies)}
- Be specific about what was accomplished

Project Title: {project_data.title}
Project Description: {project_data.description}

Return ONLY the 3 bullet points, one per line, no numbering or bullets."""

            response = await bedrock_client.generate_content(
                prompt=prompt,
                temperature=0.7,
                max_tokens=300,
            )
            
            # Parse the response into lines
            generated_highlights = [line.strip() for line in response.strip().split('\n') if line.strip()]
            if len(generated_highlights) >= 3:
                highlights = generated_highlights[:3]
            else:
                highlights = project_data.highlights or []
        except Exception as e:
            # If generation fails, use provided highlights or empty
            highlights = project_data.highlights or []
    
    # Create project
    project = Project(
        user_id=current_user.id,
        source_type=ProjectSourceType.MANUAL,
        title=project_data.title,
        description=project_data.description,
        technologies=project_data.technologies,
        highlights=highlights,
        url=project_data.url,
        demo_url=project_data.demo_url,
        is_verified=True,  # Manual entries are trusted
        raw_content=f"{project_data.title}\n{project_data.description}",
    )
    db.add(project)
    await db.flush()
    
    # Generate embedding (optional - requires Gemini API keys)
    try:
        text = embedding_service.combine_texts_for_embedding(
            title=project.title,
            description=project.description,
            technologies=project.technologies,
            highlights=project_data.highlights,
        )
        embedding = await embedding_service.embed_text(text)
        
        embedding_id = vector_store.generate_embedding_id()
        await vector_store.add_embedding(
            collection_name=VectorStoreService.COLLECTION_PROJECTS,
            embedding_id=embedding_id,
            embedding=embedding,
            metadata={
                "user_id": str(current_user.id),
                "source_type": "manual",
                "name": project.title,
                "technologies": project.technologies,
            },
            document=text,
        )
        
        project.embedding_id = embedding_id
    except ValueError as e:
        # Embeddings not available, skip
        pass
    await db.commit()
    await db.refresh(project)
    
    return ProjectResponse(
        id=str(project.id),
        title=project.title,
        description=project.description,
        technologies=project.technologies or [],
        highlights=project.highlights if isinstance(project.highlights, list) else [],
        url=project.url,
        demo_url=project.demo_url,
        source_type=project.source_type.value,
        is_verified=project.is_verified,
        is_featured=project.is_featured,
        start_date=str(project.start_date) if project.start_date else None,
        end_date=str(project.end_date) if project.end_date else None,
    )


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    current_user: dict = Depends(get_current_user_dynamo),
):
    """Get a specific project from DynamoDB."""
    project = await dynamo_service.get_item(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        key={"userId": current_user["userId"], "projectId": project_id},
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _dynamo_to_response(project)


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    update_data: ProjectUpdate,
    current_user: dict = Depends(get_current_user_dynamo),
):
    """Update a project in DynamoDB."""
    # Verify ownership
    project = await dynamo_service.get_item(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        key={"userId": current_user["userId"], "projectId": project_id},
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Map frontend fields to DynamoDB attribute names
    field_map = {
        "title":        "name",
        "description":  "description",
        "technologies": "technologies",
        "highlights":   "highlights",
        "url":          "repoUrl",
        "demo_url":     "demo_url",
        "is_featured":  "isFeatured",
    }
    updates = {field_map.get(k, k): v for k, v in update_data.model_dump(exclude_unset=True).items()}
    updates["updatedAt"] = datetime.utcnow().isoformat()

    updated = await dynamo_service.update_item(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        key={"userId": current_user["userId"], "projectId": project_id},
        updates=updates,
    )
    # Re-fetch to return full updated item
    refreshed = await dynamo_service.get_item(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        key={"userId": current_user["userId"], "projectId": project_id},
    )
    return _dynamo_to_response(refreshed or project)


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user: dict = Depends(get_current_user_dynamo),
):
    """Delete a project from DynamoDB."""
    project = await dynamo_service.get_item(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        key={"userId": current_user["userId"], "projectId": project_id},
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await dynamo_service.delete_item(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        key={"userId": current_user["userId"], "projectId": project_id},
    )
    return {"message": "Project deleted"}


@router.post("/ingest/github")
async def ingest_github_repos(
    request: GitHubIngestRequest,
    current_user: dict = Depends(get_current_user_dynamo),
):
    """
    Ingest specific GitHub repos (or all) via the M1.6 pipeline.
    Stores structured summaries in S3 + DynamoDB Projects table.
    """
    import traceback

    github_token = current_user.get("githubToken")
    installation_id = current_user.get("githubInstallationId")
    user_id = current_user["userId"]

    logger.info(f"[INGEST] user={user_id} has_token={bool(github_token)} installation_id={installation_id}")
    logger.info(f"[INGEST] request: sync_all={request.sync_all} repo_urls={request.repo_urls}")

    if not github_token:
        raise HTTPException(
            status_code=400,
            detail="No GitHub account connected. Please connect your GitHub account first.",
        )

    ingested = []

    if request.sync_all:
        repos_meta = await github_service.fetch_user_repos_fast(
            encrypted_token=github_token,
            installation_id=installation_id,
            include_forks=request.include_forks,
        )
        logger.info(f"[INGEST] sync_all: fetched {len(repos_meta)} repos")
    elif request.full_names:
        # Preferred path: full_name already parsed by caller, no regex needed
        repos_meta = []
        for full_name in request.full_names:
            name = full_name.split("/")[-1]
            repos_meta.append({"full_name": full_name, "name": name})
            logger.info(f"[INGEST] queued repo: full_name={full_name}")
    elif request.repo_urls:
        # Fallback: derive full_names from URLs (URL-import mode)
        repos_meta = []
        for url in request.repo_urls:
            m = re.search(r"github\.com/([^/]+)/([^/]+)", url)
            if m:
                full_name = f"{m.group(1)}/{m.group(2)}".rstrip(".git")
                name = m.group(2).rstrip(".git")
                repos_meta.append({"full_name": full_name, "name": name})
                logger.info(f"[INGEST] queued repo: full_name={full_name}")
            else:
                logger.warning(f"[INGEST] invalid URL skipped: {url}")
                ingested.append({"url": url, "error": "Invalid GitHub URL"})
    else:
        raise HTTPException(status_code=400, detail="Either sync_all=true, full_names, or repo_urls must be provided")

    for repo_meta in repos_meta:
        full_name = repo_meta["full_name"]
        logger.info(f"[INGEST] ── processing {full_name} ──────────────────────")
        try:
            logger.info(f"[INGEST] [{full_name}] step 1: fetch_repo_details (PyGithub + token)")
            detailed = await github_service.fetch_repo_details(
                full_name=full_name,
                encrypted_token=github_token,
            )
            logger.info(
                f"[INGEST] [{full_name}] fetch_repo_details OK "
                f"readme_len={len(detailed.get('readme_content') or '')} "
                f"tech={detailed.get('extracted_tech', [])} "
                f"root_dirs={detailed.get('root_dirs', [])}"
            )

            logger.info(f"[INGEST] [{full_name}] step 2: create_project_from_repo (Bedrock summary)")
            project_data = await github_service.create_project_from_repo(detailed)
            logger.info(
                f"[INGEST] [{full_name}] create_project_from_repo OK "
                f"technologies={project_data.get('technologies', [])} "
                f"highlights_count={len(project_data.get('highlights', []))}"
            )

            project_id = str(uuid.uuid4())
            logger.info(f"[INGEST] [{full_name}] step 3: ingest_and_embed_repo project_id={project_id}")
            await github_service.ingest_and_embed_repo(
                repo_data=detailed,
                project_data=project_data,
                user_id=user_id,
                project_id=project_id,
            )
            logger.info(f"[INGEST] [{full_name}] ✅ SUCCESS project_id={project_id}")
            ingested.append({"full_name": full_name, "status": "success", "project_id": project_id})
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(
                f"[INGEST] [{full_name}] ❌ FAILED: {type(e).__name__}: {e}\n{tb}"
            )
            ingested.append({"full_name": full_name, "status": "error", "error": f"{type(e).__name__}: {e}"})

    successes = sum(1 for r in ingested if r.get("status") == "success")
    failures = sum(1 for r in ingested if r.get("status") == "error")
    logger.info(f"[INGEST] DONE: {successes} succeeded, {failures} failed out of {len(repos_meta)} repos")

    return {"message": f"Processed {len(repos_meta)} repositories", "results": ingested}


@router.get("/github/repos")
async def list_github_repos(
    current_user: dict = Depends(get_current_user_dynamo),
):
    """List all ingested GitHub repos (sourced from DynamoDB Projects table)."""
    items = await dynamo_service.query(
        table=f"{settings.DYNAMO_TABLE_PREFIX}Projects",
        pk_name="userId",
        pk_value=current_user["userId"],
    )
    # Return only github-sourced items in the legacy GitHubRepoResponse shape
    return [
        {
            "id":         p.get("projectId", ""),
            "full_name":  p.get("name", ""),
            "name":       p.get("name", ""),
            "description": p.get("description"),
            "stars":      p.get("stars", 0),
            "languages":  p.get("languages", {}),
            "topics":     p.get("topics", []),
            "project_id": p.get("projectId"),
        }
        for p in items
        if p.get("sourceType") == "github"
    ]


class GitHubUserRepo(BaseModel):
    """GitHub repository from user's account."""
    full_name: str
    name: str
    description: Optional[str]
    html_url: str
    stars: int
    forks: int
    language: Optional[str]
    is_private: bool
    is_fork: bool


@router.get("/github/user-repos", response_model=List[GitHubUserRepo])
async def list_github_user_repos(
    current_user: dict = Depends(get_current_user_dynamo),
):
    """
    List ALL repositories from the user's GitHub account.
    Uses DynamoDB-stored token (GitHub App flow from M1.6).
    """
    github_token = current_user.get("githubToken")
    installation_id = current_user.get("githubInstallationId")

    if not github_token:
        raise HTTPException(
            status_code=400,
            detail="No GitHub account connected. Please connect your GitHub account first.",
        )

    # Fetch repos via installation token (or OAuth fallback)
    repos = await github_service.fetch_user_repos_fast(
        encrypted_token=github_token,
        installation_id=installation_id,
        include_forks=True,
    )

    # Convert to response format
    return [
        GitHubUserRepo(
            full_name=repo["full_name"],
            name=repo["name"],
            description=repo.get("description"),
            html_url=repo.get("url", repo.get("html_url", "")),
            stars=repo.get("stars", 0),
            forks=repo.get("forks", 0),
            language=repo.get("language"),
            is_private=repo.get("is_private", False),
            is_fork=repo.get("is_fork", False),
        )
        for repo in repos
    ]
