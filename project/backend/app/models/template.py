"""
Template Model
==============
LaTeX resume templates with placeholder definitions.
"""

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.db_types import GUID, JSON


class Template(Base):
    """
    LaTeX template model.
    Stores template content and placeholder definitions.
    """
    
    __tablename__ = "templates"
    
    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), 
        primary_key=True, 
        default=uuid.uuid4
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), 
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,  # NULL = system template
        index=True
    )
    
    # Template info
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # LaTeX content
    latex_content: Mapped[str] = mapped_column(Text)
    
    # Placeholder definitions
    placeholders: Mapped[dict] = mapped_column(JSON(), default=dict)
    # Format: {
    #   "NAME": {"type": "text", "required": true, "label": "Full Name"},
    #   "PROJECTS": {"type": "array", "min": 2, "max": 6, "item_fields": [...]},
    #   ...
    # }
    
    # Preview
    preview_image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Flags
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ats_tested: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Categorization
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # e.g., "professional", "academic", "creative", "minimal"
    
    # Usage stats
    use_count: Mapped[int] = mapped_column(default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="templates")
    resumes: Mapped[List["Resume"]] = relationship("Resume", back_populates="template")


# Import for type hints
from app.models.user import User
from app.models.resume import Resume
