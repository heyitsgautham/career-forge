"""
Celery Application Configuration
================================
Async task queue for background jobs.
"""

from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "latex_agent",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.ingestion",
        "app.tasks.compilation",
        "app.tasks.generation",
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    worker_prefetch_multiplier=1,
    result_expires=3600,  # Results expire after 1 hour
)
