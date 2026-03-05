"""
Health Check Routes
==================
System health and status endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.config import settings


router = APIRouter()


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
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


@router.get("/health/services")
async def services_health():
    """Check all service dependencies."""
    from app.services.gemini_client import gemini_client
    from app.services.vector_store import vector_store
    
    status = {
        "gemini": "unknown",
        "vector_store": "unknown",
    }
    
    # Check Gemini
    try:
        gemini_client.initialize()
        status["gemini"] = f"configured ({len(gemini_client.api_keys)} keys)"
    except Exception as e:
        status["gemini"] = f"error: {str(e)}"
    
    # Check vector store
    try:
        client = vector_store._get_client()
        status["vector_store"] = "connected"
    except Exception as e:
        status["vector_store"] = f"error: {str(e)}"
    
    all_healthy = all("error" not in str(v) for v in status.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": status,
    }
