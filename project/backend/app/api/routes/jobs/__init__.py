"""
Job Description Routes
======================
Mounted under /api/jobs. JD management, analysis, scraping and Job Scout
endpoints, on DynamoDB (AWS) or SQLite (local fallback).

The modules register on the shared router in common.py. Scout and tracking
routes come first so their fixed paths win over the /{jd_id} routes.
"""

# ruff: noqa: I001, F401
from app.api.routes.jobs import scout
from app.api.routes.jobs import tracking
from app.api.routes.jobs import descriptions
from app.api.routes.jobs.common import router

__all__ = ["router"]
