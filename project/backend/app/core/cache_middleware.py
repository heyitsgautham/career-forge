"""
Cache-Control middleware for CareerForge API.

Sets HTTP cache headers on GET responses based on endpoint patterns.
All user-specific endpoints use 'private' to prevent CDN/proxy caching.
Mutating requests (POST/PUT/PATCH/DELETE) always get 'no-store'.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# (pattern_prefix, cache_control_value)
# Order matters — first match wins.
_CACHE_RULES: list[tuple[str, str]] = [
    # Job scout — real-time, never cache
    ("/api/job-scout", "no-cache"),
    # Templates — very stable
    ("/api/templates", "private, max-age=1800, stale-while-revalidate=3600"),
    # Skill gap & roadmap — computed, stable once generated
    ("/api/skill-gap", "private, max-age=600, stale-while-revalidate=1200"),
    # User profile
    ("/api/auth/profile", "private, max-age=600"),
    ("/api/auth/github/status", "private, max-age=600"),
    # Resumes — moderate churn
    ("/api/resumes", "private, max-age=60, stale-while-revalidate=120"),
    # Projects & GitHub
    ("/api/projects", "private, max-age=120, stale-while-revalidate=300"),
    ("/api/github", "private, max-age=120, stale-while-revalidate=300"),
    # Jobs
    ("/api/jobs", "private, max-age=120, stale-while-revalidate=300"),
]


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        # Only set cache headers on successful GET/HEAD requests
        if request.method not in ("GET", "HEAD") or response.status_code >= 400:
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                response.headers["Cache-Control"] = "no-store"
            return response

        # Skip if the route handler already set Cache-Control
        if "cache-control" in response.headers:
            return response

        path = request.url.path
        for prefix, value in _CACHE_RULES:
            if path.startswith(prefix):
                response.headers["Cache-Control"] = value
                return response

        return response
