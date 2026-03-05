"""
Job Description Model
=====================
Parsed and analyzed job descriptions.
"""

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.db_types import GUID, JSON


class JobDescription(Base):
    """
    Job description model.
    Stores raw JD text and extracted structured data.
    """
    
    __tablename__ = "job_descriptions"
    
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
    
    # Basic info
    title: Mapped[str] = mapped_column(String(255))
    company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Raw content
    raw_text: Mapped[str] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Parsed requirements
    parsed_requirements: Mapped[dict] = mapped_column(JSON(), default=dict)
    # Format: {
    #   "responsibilities": ["..."],
    #   "qualifications": ["..."],
    #   "benefits": ["..."],
    #   "salary_range": "...",
    #   "employment_type": "full-time",
    #   "experience_years": {"min": 3, "max": 5},
    # }
    
    # Extracted skills (for matching)
    required_skills: Mapped[list] = mapped_column(JSON(), default=list)
    preferred_skills: Mapped[list] = mapped_column(JSON(), default=list)
    
    # Keywords for matching
    keywords: Mapped[list] = mapped_column(JSON(), default=list)
    
    # Vector store reference
    embedding_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Processing status
    is_analyzed: Mapped[bool] = mapped_column(default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="job_descriptions")
    resumes: Mapped[List["Resume"]] = relationship("Resume", back_populates="job_description")


# Import for type hints
from app.models.user import User
from app.models.resume import Resume
