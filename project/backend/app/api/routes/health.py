"""
Health Check Routes
==================
System health and status endpoints.

A failing check answers 503, so Docker health checks and load balancers take
the instance out of rotation. Error details go to the log, not the response,
because these endpoints need no authentication.
"""

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

router = APIRouter()
logger = structlog.get_logger()


def _unavailable(body: dict) -> JSONResponse:
    return JSONResponse(status_code=503, content=body)


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
    }


@router.get("/health/db")
async def database_health(db: AsyncSession = Depends(get_db)):
    """Database connectivity check."""
    if settings.USE_DYNAMO:
        try:
            from app.services.dynamo_service import dynamo_service

            dynamo_service._get_resource()
            return {"status": "healthy", "database": "dynamodb"}
        except Exception as e:
            logger.warning("health_check_failed", check="dynamodb", error=str(e))
            return _unavailable({"status": "unhealthy", "database": "dynamodb"})
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.warning("health_check_failed", check="database", error=str(e))
        return _unavailable({"status": "unhealthy", "database": "disconnected"})


@router.get("/health/services")
async def services_health():
    """Check all service dependencies."""
    from app.services.bedrock_client import bedrock_client
    from app.services.vector_store import vector_store

    checks = {
        "bedrock": ("configured", bedrock_client._get_client),
        "vector_store": ("connected", vector_store._get_client),
    }
    status = {}
    for name, (ok_label, build_client) in checks.items():
        try:
            build_client()
            status[name] = ok_label
        except Exception as e:
            logger.warning("health_check_failed", check=name, error=str(e))
            status[name] = "error"

    if "error" in status.values():
        return _unavailable({"status": "degraded", "services": status})
    return {"status": "healthy", "services": status}
