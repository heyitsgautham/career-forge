"""
Projects Routes
===============
Project management and GitHub ingestion endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, HttpUrl
import uuid

from app.core.database import get_db
from app.core.security import token_encryptor
from app.models.user import User, GithubConnection
from app.models.project import Project, GithubRepo, ProjectSourceType
from app.api.deps import get_current_user
from app.services.github_service import github_service
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store, VectorStoreService


router = APIRouter()


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


# Routes
@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    featured_only: bool = False,
):
    """List all projects for the current user."""
    query = select(Project).where(Project.user_id == current_user.id)
    if featured_only:
        query = query.where(Project.is_featured == True)
    query = query.order_by(Project.created_at.desc())
    
    result = await db.execute(query)
    projects = result.scalars().all()
    
    return [
        ProjectResponse(
            id=str(p.id),
            title=p.title,
            description=p.description,
            technologies=p.technologies or [],
            highlights=p.highlights if isinstance(p.highlights, list) else [],
            url=p.url,
            demo_url=p.demo_url,
            source_type=p.source_type.value,
            is_verified=p.is_verified,
            is_featured=p.is_featured,
            start_date=str(p.start_date) if p.start_date else None,
            end_date=str(p.end_date) if p.end_date else None,
        )
        for p in projects
    ]


@router.post("", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new manual project."""
    # Auto-generate highlights if not provided or empty
    highlights = project_data.highlights
    if not highlights or len(highlights) == 0:
        try:
            from app.services.gemini_client import gemini_client
            
            prompt = f"""Generate exactly 3 concise, technical bullet points for this project. Each point should:
- Be one line (max 80-100 characters)
- Start with a strong action verb (Developed, Implemented, Architected, Designed, Built, Integrated, Optimized)
- Focus on technical implementation and impact
- Include technologies used: {', '.join(project_data.technologies)}
- Be specific about what was accomplished

Project Title: {project_data.title}
Project Description: {project_data.description}

Return ONLY the 3 bullet points, one per line, no numbering or bullets."""

            response = await gemini_client.generate_content(
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


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific project."""
    result = await db.execute(
        select(Project).where(
            Project.id == uuid.UUID(project_id),
            Project.user_id == current_user.id,
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
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


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    update_data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a project."""
    result = await db.execute(
        select(Project).where(
            Project.id == uuid.UUID(project_id),
            Project.user_id == current_user.id,
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Update fields
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    
    # Re-generate embedding if content changed
    if any([update_data.title, update_data.description, update_data.technologies, update_data.highlights]):
        text = embedding_service.combine_texts_for_embedding(
            title=project.title,
            description=project.description,
            technologies=project.technologies,
            highlights=project.highlights if isinstance(project.highlights, list) else [],
        )
        embedding = await embedding_service.embed_text(text)
        
        if project.embedding_id:
            await vector_store.update_embedding(
                collection_name=VectorStoreService.COLLECTION_PROJECTS,
                embedding_id=project.embedding_id,
                embedding=embedding,
                metadata={
                    "user_id": str(current_user.id),
                    "source_type": project.source_type.value,
                    "name": project.title,
                    "technologies": project.technologies,
                },
                document=text,
            )
    
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


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a project."""
    result = await db.execute(
        select(Project).where(
            Project.id == uuid.UUID(project_id),
            Project.user_id == current_user.id,
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Delete embedding
    if project.embedding_id:
        await vector_store.delete_embedding(
            VectorStoreService.COLLECTION_PROJECTS,
            project.embedding_id,
        )
    
    await db.delete(project)
    await db.commit()
    
    return {"message": "Project deleted"}


@router.post("/ingest/github")
async def ingest_github_repos(
    request: GitHubIngestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ingest GitHub repositories as projects."""
    # Get user's GitHub connection
    result = await db.execute(
        select(GithubConnection).where(
            GithubConnection.user_id == current_user.id,
            GithubConnection.is_primary == True,
        )
    )
    github_conn = result.scalar_one_or_none()
    
    if not github_conn:
        raise HTTPException(
            status_code=400,
            detail="No GitHub account connected. Please connect your GitHub account first.",
        )
    
    ingested = []
    
    if request.sync_all:
        # Fetch all repos
        repos = await github_service.fetch_user_repos(
            encrypted_token=github_conn.encrypted_token,
            include_forks=request.include_forks,
            include_private=request.include_private,
        )
    elif request.repo_urls:
        # Fetch specific repos
        repos = []
        for url in request.repo_urls:
            try:
                repo = await github_service.fetch_repo_by_url(
                    url,
                    github_conn.encrypted_token,
                )
                repos.append(repo)
            except Exception as e:
                ingested.append({"url": url, "error": str(e)})
    else:
        raise HTTPException(
            status_code=400,
            detail="Either sync_all=true or repo_urls must be provided",
        )
    
    # Process each repo
    for repo_data in repos:
        # Check if already ingested
        result = await db.execute(
            select(GithubRepo).where(GithubRepo.github_id == repo_data["github_id"])
        )
        existing_repo = result.scalar_one_or_none()
        
        if existing_repo and existing_repo.project_id:
            # Check if project actually exists
            project_result = await db.execute(
                select(Project).where(Project.id == existing_repo.project_id)
            )
            existing_project = project_result.scalar_one_or_none()
            
            if existing_project:
                ingested.append({
                    "full_name": repo_data["full_name"],
                    "status": "skipped",
                    "reason": "already ingested",
                })
                continue
            else:
                # Orphaned repo entry - delete it and re-import
                await db.delete(existing_repo)
                await db.flush()
        
        try:
            # Fetch detailed info
            detailed = await github_service.fetch_repo_details(
                repo_data["full_name"],
                github_conn.encrypted_token,
            )
            
            # Create project data
            project_data = await github_service.create_project_from_repo(detailed)
            
            # Create project record
            project = Project(
                user_id=current_user.id,
                source_type=ProjectSourceType.GITHUB,
                source_id=str(detailed["github_id"]),
                title=project_data["title"],
                description=project_data["description"],
                technologies=project_data["technologies"],
                highlights=project_data["highlights"],
                url=project_data["url"],
                raw_content=project_data["raw_content"],
                is_verified=True,
            )
            db.add(project)
            await db.flush()
            
            # Create GitHub repo record
            github_repo = GithubRepo(
                github_connection_id=github_conn.id,
                project_id=project.id,
                github_id=detailed["github_id"],
                full_name=detailed["full_name"],
                name=detailed["name"],
                description=detailed.get("description"),
                readme_content=detailed.get("readme_content"),
                languages=detailed.get("languages", {}),
                topics=detailed.get("topics", []),
                stars=detailed.get("stars", 0),
                forks=detailed.get("forks", 0),
                watchers=detailed.get("watchers", 0),
                open_issues=detailed.get("open_issues", 0),
                commits_count=detailed.get("commits_count", 0),
                is_fork=detailed.get("is_fork", False),
                is_private=detailed.get("is_private", False),
                is_archived=detailed.get("is_archived", False),
                extracted_tech=detailed.get("extracted_tech", []),
            )
            db.add(github_repo)
            
            # Generate and store embedding
            embedding_id = await github_service.ingest_and_embed_repo(
                detailed,
                str(current_user.id),
            )
            project.embedding_id = embedding_id
            
            ingested.append({
                "full_name": detailed["full_name"],
                "status": "success",
                "project_id": str(project.id),
            })
            
        except Exception as e:
            ingested.append({
                "full_name": repo_data["full_name"],
                "status": "error",
                "error": str(e),
            })
    
    await db.commit()
    
    return {
        "message": f"Processed {len(repos)} repositories",
        "results": ingested,
    }


@router.get("/github/repos", response_model=List[GitHubRepoResponse])
async def list_github_repos(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all ingested GitHub repositories."""
    result = await db.execute(
        select(GithubRepo).join(GithubConnection).where(
            GithubConnection.user_id == current_user.id
        )
    )
    repos = result.scalars().all()
    
    return [
        GitHubRepoResponse(
            id=str(r.id),
            full_name=r.full_name,
            name=r.name,
            description=r.description,
            stars=r.stars,
            languages=r.languages or {},
            topics=r.topics or [],
            project_id=str(r.project_id) if r.project_id else None,
        )
        for r in repos
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List ALL repositories from the user's GitHub account.
    This fetches directly from GitHub API, not from our database.
    Automatically handles pagination to get all repos.
    """
    # Get user's GitHub connection
    result = await db.execute(
        select(GithubConnection).where(
            GithubConnection.user_id == current_user.id,
            GithubConnection.is_primary == True,
        )
    )
    github_conn = result.scalar_one_or_none()
    
    if not github_conn:
        raise HTTPException(
            status_code=400,
            detail="No GitHub account connected. Please connect your GitHub account first.",
        )
    
    # Fetch ALL repos from GitHub (handles pagination internally)
    repos = await github_service.fetch_user_repos_fast(
        encrypted_token=github_conn.encrypted_token,
        include_forks=True,
        include_private=True,
    )
    
    # Convert to response format
    return [
        GitHubUserRepo(
            full_name=repo["full_name"],
            name=repo["name"],
            description=repo.get("description"),
            html_url=repo["url"],
            stars=repo["stars"],
            forks=repo["forks"],
            language=repo.get("language"),  # Direct from GitHub API
            is_private=repo.get("is_private", False),
            is_fork=repo.get("is_fork", False),
        )
        for repo in repos
    ]
