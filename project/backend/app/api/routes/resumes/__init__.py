"""
Resume Routes
=============
Mounted under /api/resumes. Supports both the legacy template-fill flow and
the M2 S3-summary flow.

The modules register on the shared router in common.py, and importing them in
this order keeps the original route order.
"""

# ruff: noqa: I001, F401
from app.api.routes.resumes import generation
from app.api.routes.resumes import crud
from app.api.routes.resumes import compile
from app.api.routes.resumes import files
from app.api.routes.resumes import editing
from app.api.routes.resumes.common import router

__all__ = ["router"]
