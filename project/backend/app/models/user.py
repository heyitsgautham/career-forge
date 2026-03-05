"""
User Model
==========
User account and GitHub connections.
"""

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.db_types import GUID, JSON


class User(Base):
    """User account model."""
    
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), 
        primary_key=True, 
        default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Profile data
    headline: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Address fields
    address_line1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    zip_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Education/Institution (legacy single fields - kept for backward compatibility)
    institution: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    degree: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    field_of_study: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    graduation_year: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    
    # Experience array (stored as JSON)
    # Format: [{"company": str, "title": str, "dates": str, "location": str, "highlights": [str]}]
    experience: Mapped[Optional[list]] = mapped_column(JSON(), nullable=True)
    
    # Education array (stored as JSON)
    # Format: [{"school": str, "degree": str, "field": str, "dates": str, "location": str, "gpa": str}]
    education: Mapped[Optional[list]] = mapped_column(JSON(), nullable=True)
    
    # Skills (stored as JSON)
    skills: Mapped[Optional[list]] = mapped_column(JSON(), nullable=True)
    
    # Certifications array (stored as JSON)
    # Format: [{"name": str, "issuer": str, "date": str, "credential_id": str, "url": str}]
    certifications: Mapped[Optional[list]] = mapped_column(JSON(), nullable=True)
    
    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    github_connections: Mapped[List["GithubConnection"]] = relationship(
        "GithubConnection", 
        back_populates="user",
        cascade="all, delete-orphan"
    )
    linkedin_connections: Mapped[List["LinkedInConnection"]] = relationship(
        "LinkedInConnection", 
        back_populates="user",
        cascade="all, delete-orphan"
    )
    projects: Mapped[List["Project"]] = relationship(
        "Project", 
        back_populates="user",
        cascade="all, delete-orphan"
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document", 
        back_populates="user",
        cascade="all, delete-orphan"
    )
    templates: Mapped[List["Template"]] = relationship(
        "Template", 
        back_populates="user",
        cascade="all, delete-orphan"
    )
    resumes: Mapped[List["Resume"]] = relationship(
        "Resume", 
        back_populates="user",
        cascade="all, delete-orphan"
    )
    job_descriptions: Mapped[List["JobDescription"]] = relationship(
        "JobDescription", 
        back_populates="user",
        cascade="all, delete-orphan"
    )


class LinkedInConnection(Base):
    """LinkedIn account connection for a user."""
    
    __tablename__ = "linkedin_connections"
    
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
    
    # LinkedIn data
    linkedin_user_id: Mapped[str] = mapped_column(String(255), unique=True)
    linkedin_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Encrypted access token
    encrypted_token: Mapped[str] = mapped_column(Text)
    
    # Connection metadata
    scopes: Mapped[Optional[list]] = mapped_column(JSON(), nullable=True)
    
    # Timestamps
    connected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    token_updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="linkedin_connections")


class GithubConnection(Base):
    """GitHub account connection for a user."""
    
    __tablename__ = "github_connections"
    
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
    
    # GitHub data
    github_user_id: Mapped[int] = mapped_column(unique=True)
    github_username: Mapped[str] = mapped_column(String(255))
    github_avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Encrypted access token
    encrypted_token: Mapped[str] = mapped_column(Text)
    
    # Connection metadata
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    scopes: Mapped[Optional[list]] = mapped_column(JSON(), nullable=True)
    
    # Timestamps
    connected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    token_updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="github_connections")
    repos: Mapped[List["GithubRepo"]] = relationship(
        "GithubRepo",
        back_populates="github_connection",
        cascade="all, delete-orphan"
    )


# Import for type hints (avoid circular imports)
from app.models.project import Project, GithubRepo
from app.models.document import Document
from app.models.template import Template
from app.models.resume import Resume
from app.models.job_description import JobDescription
