"""
Resume Model
============
Generated resumes with versioning support.
"""

import uuid
from datetime import datetime
from typing import Optional, List
from enum import Enum

from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.db_types import GUID, JSON


class ResumeStatus(str, Enum):
    """Resume generation/compilation status."""
    DRAFT = "draft"
    GENERATING = "generating"
    GENERATED = "generated"
    COMPILING = "compiling"
    COMPILED = "compiled"
    ERROR = "error"


class Resume(Base):
    """
    Generated resume model.
    Stores LaTeX content, PDF path, and generation metadata.
    """
    
    __tablename__ = "resumes"
    
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
    template_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), 
        ForeignKey("templates.id", ondelete="SET NULL"),
        nullable=True
    )
    job_description_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), 
        ForeignKey("job_descriptions.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Resume info
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    
    # Content
    latex_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Output
    pdf_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Selected projects (ordered list of project IDs as JSON)
    selected_project_ids: Mapped[list] = mapped_column(
        JSON(), 
        default=list
    )
    
    # Generation parameters and metadata
    generation_params: Mapped[dict] = mapped_column(JSON(), default=dict)
    # Format: {
    #   "model": "gemini-1.5-pro",
    #   "temperature": 0.2,
    #   "matching_scores": {"project_id": 0.87, ...},
    #   "prompts_used": [...],
    # }
    
    # Status tracking
    status: Mapped[ResumeStatus] = mapped_column(
        SQLEnum(ResumeStatus),
        default=ResumeStatus.DRAFT
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Compilation metadata
    compilation_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    compilation_warnings: Mapped[list] = mapped_column(JSON(), default=list)
    
    # Localization
    locale: Mapped[str] = mapped_column(String(10), default="en")
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    compiled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="resumes")
    template: Mapped[Optional["Template"]] = relationship("Template", back_populates="resumes")
    job_description: Mapped[Optional["JobDescription"]] = relationship(
        "JobDescription", 
        back_populates="resumes"
    )


# Import for type hints
from app.models.user import User
from app.models.template import Template
from app.models.job_description import JobDescription
