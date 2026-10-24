"""
Authentication Routes
=====================
Mounted under /api/auth. Each sign-in provider and the profile endpoints live
in their own module; this package combines them into one router.
"""

from fastapi import APIRouter

from app.api.routes.auth import cognito, email, github, linkedin, profile

router = APIRouter()
for module in (email, github, cognito, profile, linkedin):
    router.include_router(module.router)

__all__ = ["router"]
