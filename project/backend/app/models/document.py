"""
Document Model
==============
Uploaded documents (resumes, certificates, project docs).
"""

import uuid
from datetime import datetime
from typing import Optional
from enum import Enum

from sqlalchemy import String, DateTime, Text, ForeignKey, Integer, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.db_types import GUID, JSON


class DocumentFileType(str, Enum):
    """Supported document file types."""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"


class DocumentType(str, Enum):
    """Type of document content."""
    RESUME = "resume"
    COVER_LETTER = "cover_letter"
    PROJECT = "project"
    CERTIFICATE = "certificate"
    REFERENCE = "reference"
    OTHER = "other"


class Document(Base):
    """
    Uploaded document model.
    Stores metadata and extracted text from user uploads.
    """
    
    __tablename__ = "documents"
    
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
    
    # File information
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[DocumentFileType] = mapped_column(SQLEnum(DocumentFileType))
    file_path: Mapped[str] = mapped_column(String(500))
    file_size: Mapped[int] = mapped_column(Integer)  # bytes
    file_hash: Mapped[str] = mapped_column(String(64), index=True)  # SHA-256 for dedup
    
    # Content
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Classification
    doc_type: Mapped[DocumentType] = mapped_column(
        SQLEnum(DocumentType),
        default=DocumentType.OTHER
    )
    
    # Extracted metadata (varies by doc_type)
    doc_metadata: Mapped[dict] = mapped_column(JSON(), default=dict)
    # For resumes: {"name": "...", "email": "...", "skills": [...]}
    # For certificates: {"issuer": "...", "date": "...", "credential_id": "..."}
    
    # Vector store reference
    embedding_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Processing status
    is_processed: Mapped[bool] = mapped_column(default=False)
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="documents")


# Import for type hints
from app.models.user import User
