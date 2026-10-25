"""
Project schemas
===============
Request and response models for the /api/projects routes.
"""

from typing import List, Optional

from pydantic import BaseModel


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
