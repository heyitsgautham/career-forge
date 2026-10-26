"""
Resume schemas
==============
Request and response models for the /api/resumes routes.
"""

from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.limits import LatexSource, LongText


class M2GenerateRequest(BaseModel):
    """Request body for M2 resume generation (S3-summary-based)."""

    jd: Optional[LongText] = None


class M2GenerateResponse(BaseModel):
    """Response from M2 resume generation."""

    resume_id: str
    pdf_url: Optional[str]
    tex_url: Optional[str]
    analysis: str
    status: str
    compilation_error: Optional[str] = None  # Set when LaTeX compiled but PDF failed


class ResumeCreate(BaseModel):
    name: str
    template_id: Optional[str] = None
    job_description_id: Optional[str] = None
    project_ids: Optional[List[str]] = None


class ResumeGenerateRequest(BaseModel):
    personal: Optional[dict] = None  # name, email, phone, location, etc.
    skills: Optional[List[str]] = None
    experience: Optional[List[dict]] = None
    education: Optional[List[dict]] = None
    tailor_to_jd: bool = True


class ResumeResponse(BaseModel):
    id: str
    name: str
    template_id: Optional[str] = None
    job_description_id: Optional[str] = None
    job_id: Optional[str] = None
    type: Optional[str] = None
    selected_project_ids: List[str] = []
    status: str
    latex_content: Optional[str] = None
    pdf_path: Optional[str] = None
    error_message: Optional[str] = None
    analysis: Optional[str] = None
    tex_s3_key: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class CompilationResponse(BaseModel):
    success: bool
    pdf_url: Optional[str]
    errors: List[dict]
    warnings: List[str]


class LatexUpdateRequest(BaseModel):
    """Body for PUT /api/resumes/{id}/latex"""

    latex_content: LatexSource


class LatexUpdateResponse(BaseModel):
    id: str
    updated_at: str


class CompileOnDemandRequest(BaseModel):
    """Optional body for POST /api/resumes/{id}/compile"""

    latex_content: Optional[LatexSource] = None


class CompileOnDemandResponse(BaseModel):
    pdf_url: Optional[str]
    status: str  # "compiled" | "error"
    error_message: Optional[str] = None


class AiEditRequest(BaseModel):
    """Body for POST /api/resumes/{id}/ai-edit"""

    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4_000)
    ]
    latex_content: LatexSource
