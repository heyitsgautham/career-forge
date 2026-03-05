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
    if settings.USE_DYNAMO:
        try:
            from app.services.dynamo_service import dynamo_service
            dynamo_service._get_client()
            return {"status": "healthy", "database": "dynamodb"}
        except Exception as e:
            return {"status": "unhealthy", "database": "dynamodb", "error": str(e)}
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


@router.get("/health/services")
async def services_health():
    """Check all service dependencies."""
    from app.services.bedrock_client import bedrock_client
    from app.services.vector_store import vector_store
    
    status = {
        "bedrock": "unknown",
        "vector_store": "unknown",
    }
    
    # Check Bedrock
    try:
        bedrock_client._get_client()
        status["bedrock"] = "configured"
    except Exception as e:
        status["bedrock"] = f"error: {str(e)}"
    
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
