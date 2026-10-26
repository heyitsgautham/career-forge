"""
Job schemas
===========
Request and response models for the /api/jobs routes.
"""

from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.limits import Name, Paragraph, ShortText, Url


class JobDescriptionCreate(BaseModel):
    title: Name
    company: Optional[ShortText] = None
    location: Optional[ShortText] = None
    raw_text: Annotated[str, StringConstraints(min_length=1, max_length=50_000)]
    source_url: Optional[Url] = None


class JobDescriptionResponse(BaseModel):
    id: str
    title: str
    company: Optional[str]
    location: Optional[str]
    raw_text: str
    source_url: Optional[str]
    required_skills: List[str]
    preferred_skills: List[str]
    keywords: List[str]
    is_analyzed: bool

    model_config = ConfigDict(from_attributes=True)


class ProjectMatch(BaseModel):
    project_id: str
    total_score: float
    semantic_score: float
    tech_overlap_score: float
    keyword_score: float
    match_explanation: str


class AnalyzeResponse(BaseModel):
    job_description: JobDescriptionResponse
    matched_projects: List[ProjectMatch]


# ── Job Scout Pydantic models ────────────────────────────────────────────────


class ScrapeRequest(BaseModel):
    search_term: str = "Software Developer"
    location: Optional[str] = "India"
    # jobspy sites (global): "linkedin", "indeed"
    sites: Optional[List[str]] = None
    results_wanted: int = 20
    # India-specific sources; None = scrape all
    india_sources: Optional[List[str]] = None  # ["naukri", "unstop"]
    include_india_sources: bool = True


class ScoutJobResponse(BaseModel):
    """A single job card for the Job Scout board."""

    jobId: str
    title: str
    company: str
    location: Optional[str]
    url: Optional[str]
    source: Optional[str]
    datePosted: Optional[str]
    salary: Optional[str]
    jobType: Optional[str]
    category: Optional[str]
    requiredSkills: List[str]
    preferredSkills: List[str]
    missingSkills: List[str]
    experienceLevel: Optional[str]
    atsKeywords: List[str]
    matchScore: Optional[float]
    matchBreakdown: Optional[dict]
    isAnalyzed: bool
    description: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class JobStatsResponse(BaseModel):
    totalJobs: int
    analyzedJobs: int
    averageMatch: Optional[float]
    topCategories: List[dict]
    matchDistribution: dict
    newToday: int = 0
    lastScrape: Optional[dict] = None


TrackingStatus = Literal[
    "pending", "saved", "applied", "interviewing", "offered", "rejected", "ignored"
]


class TrackingStatusUpdate(BaseModel):
    status: TrackingStatus
    notes: Optional[Paragraph] = None


class BlacklistRequest(BaseModel):
    companyName: Name


class SchedulerStatusResponse(BaseModel):
    running: bool
    nextRunTime: Optional[str]
    lastScrape: Optional[dict]
