"""
Projects Routes
===============
Mounted under /api/projects. Project CRUD on DynamoDB and GitHub repository
imports. The modules register on the shared router in common.py; the import
routes come first so /github/... and /ingest/... are not read as project ids.
"""

# ruff: noqa: I001, F401
from app.api.routes.projects import github_imports
from app.api.routes.projects import crud
from app.api.routes.projects.common import router

__all__ = ["router"]
