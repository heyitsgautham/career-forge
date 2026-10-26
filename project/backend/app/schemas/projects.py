"""
Project schemas
===============
Request and response models for the /api/projects routes.
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.limits import Name, Paragraph, ShortText, TagList, Url, bounded_list


class ProjectCreate(BaseModel):
    title: Name
    description: Paragraph
    technologies: TagList
    highlights: Optional[bounded_list(Paragraph, 20)] = None
    url: Optional[Url] = None
    demo_url: Optional[Url] = None
    start_date: Optional[ShortText] = None
    end_date: Optional[ShortText] = None


class ProjectUpdate(BaseModel):
    title: Optional[Name] = None
    description: Optional[Paragraph] = None
    technologies: Optional[TagList] = None
    highlights: Optional[bounded_list(Paragraph, 20)] = None
    url: Optional[Url] = None
    demo_url: Optional[Url] = None
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

    model_config = ConfigDict(from_attributes=True)


class GitHubIngestRequest(BaseModel):
    repo_urls: Optional[bounded_list(Url)] = None
    full_names: Optional[bounded_list(ShortText)] = None  # preferred: skip URL parsing entirely
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
