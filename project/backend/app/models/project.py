"""
Project Model
=============
Projects extracted from GitHub repos, documents, or manual entry.
"""

import uuid
from datetime import datetime, date
from typing import Optional, List
from enum import Enum

from sqlalchemy import String, Boolean, DateTime, Date, Text, ForeignKey, Integer, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.db_types import GUID, JSON


class ProjectSourceType(str, Enum):
    """Source of project data."""
    GITHUB = "github"
    DOCUMENT = "document"
    MANUAL = "manual"


class Project(Base):
    """
    Project model - core entity for resume generation.
    Contains verified project data from various sources.
    """
    
    __tablename__ = "projects"
    
    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), 
        primary_key=True, 
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), 
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True
    )
    
    # Source tracking
    source_type: Mapped[ProjectSourceType] = mapped_column(
        SQLEnum(ProjectSourceType),
        default=ProjectSourceType.MANUAL
    )
    source_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Core project data
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    
    # Technologies (verified stack)
    technologies: Mapped[list] = mapped_column(JSON(), default=list)
    
    # Bullet point highlights for resume
    highlights: Mapped[dict] = mapped_column(JSON(), default=list)
    # Format: ["Built X that improved Y by Z%", "Led team of N engineers", ...]
    
    # Timeline
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Links
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    demo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Verification and visibility
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Raw content for embedding
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Vector store reference
    embedding_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="projects")
    github_repo: Mapped[Optional["GithubRepo"]] = relationship(
        "GithubRepo",
        back_populates="project",
        uselist=False
    )


class GithubRepo(Base):
    """
    GitHub repository metadata.
    Linked to a Project record after ingestion.
    """
    
    __tablename__ = "github_repos"
    
    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), 
        primary_key=True, 
        default=uuid.uuid4
    )
    github_connection_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), 
        ForeignKey("github_connections.id", ondelete="CASCADE"),
        index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), 
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        unique=True
    )
    
    # GitHub identifiers
    github_id: Mapped[int] = mapped_column(Integer, unique=True)
    full_name: Mapped[str] = mapped_column(String(255))  # owner/repo
    name: Mapped[str] = mapped_column(String(255))
    
    # Repository metadata
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    readme_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Language stats (bytes per language)
    languages: Mapped[dict] = mapped_column(JSON(), default=dict)
    # Format: {"Python": 50000, "JavaScript": 30000}
    
    # Topics/tags
    topics: Mapped[list] = mapped_column(JSON(), default=list)
    
    # Stats
    stars: Mapped[int] = mapped_column(Integer, default=0)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    watchers: Mapped[int] = mapped_column(Integer, default=0)
    open_issues: Mapped[int] = mapped_column(Integer, default=0)
    commits_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Dates
    created_at_github: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    pushed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_commit_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Flags
    is_fork: Mapped[bool] = mapped_column(Boolean, default=False)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Extracted tech stack (parsed from package.json, etc.)
    extracted_tech: Mapped[list] = mapped_column(JSON(), default=list)
    
    # Ingestion metadata
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    github_connection: Mapped["GithubConnection"] = relationship(
        "GithubConnection", 
        back_populates="repos"
    )
    project: Mapped[Optional["Project"]] = relationship(
        "Project", 
        back_populates="github_repo"
    )


# Import for type hints
from app.models.user import User, GithubConnection
