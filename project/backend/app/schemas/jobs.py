"""
Job schemas
===========
Request and response models for the /api/jobs routes.
"""

from typing import List, Optional

from pydantic import BaseModel


class JobDescriptionCreate(BaseModel):
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    raw_text: str
    source_url: Optional[str] = None


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


class JobStatsResponse(BaseModel):
    totalJobs: int
    analyzedJobs: int
    averageMatch: Optional[float]
    topCategories: List[dict]
    matchDistribution: dict
    newToday: int = 0
    lastScrape: Optional[dict] = None


class TrackingStatusUpdate(BaseModel):
    status: str  # "saved", "applied", "interviewing", "offered", "rejected", "ignored"
    notes: Optional[str] = None


class BlacklistRequest(BaseModel):
    companyName: str


class SchedulerStatusResponse(BaseModel):
    running: bool
    nextRunTime: Optional[str]
    lastScrape: Optional[dict]
