"""API routes module initialization."""

from app.api.routes import health, auth, projects, templates, jobs, resumes

__all__ = [
    "health",
    "auth",
    "projects",
    "templates",
    "jobs",
    "resumes",
]
