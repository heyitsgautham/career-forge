"""API routes module initialization."""

from app.api.routes import auth, health, jobs, projects, resumes, templates

__all__ = [
    "health",
    "auth",
    "projects",
    "templates",
    "jobs",
    "resumes",
]
