"""
LaTeX Resume Agent - FastAPI Application
=========================================
A JD-aware, GitHub-grounded resume generation system.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import structlog

# Set stdlib logging level so structlog's filter_by_level passes INFO through
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

from app.core.config import settings
from app.core.database import init_db
from app.core.cache_middleware import CacheControlMiddleware
from app.api.routes import projects, resumes, templates, jobs, auth, health, github, skill_gap, applications


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting CareerForge", version="1.0.0")
    
    if settings.USE_DYNAMO:
        logger.info("Using DynamoDB for data storage")
        # Ensure Job Scout tables exist
        from app.services.dynamo_service import dynamo_service
        await dynamo_service.ensure_job_scout_tables()
        # Start hourly scrape scheduler
        from app.services.scheduler import start_scheduler
        start_scheduler()
    else:
        await init_db()
        logger.info("SQLite database initialized")
    
    yield
    
    # Shutdown
    if settings.USE_DYNAMO:
        from app.services.scheduler import stop_scheduler
        stop_scheduler()
    logger.info("Shutting down CareerForge")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="JD-Aware, GitHub-Grounded LaTeX Resume Agent",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://latex-agent-2dat.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache-Control headers for browser caching
app.add_middleware(CacheControlMiddleware)

# Mount static files for uploads
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include API routes
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(github.router, prefix="/api/github", tags=["GitHub"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(templates.router, prefix="/api/templates", tags=["Templates"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Job Descriptions"])
app.include_router(resumes.router, prefix="/api/resumes", tags=["Resumes"])
app.include_router(skill_gap.router, prefix="/api/skill-gap", tags=["Skill Gap & Roadmap"])
app.include_router(applications.router, prefix="/api", tags=["Applications & Tailor"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }
