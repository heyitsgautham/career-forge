"""
Scheduler Service
=================
APScheduler-based hourly cron for scraping jobs across all search queries.
Runs once for all users — jobs are shared.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = structlog.get_logger()

# ── In-memory state ──────────────────────────────────────────────────────────

_scheduler: Optional[AsyncIOScheduler] = None

last_scrape_result: dict = {
    "timestamp": None,
    "total_jobs": 0,
    "new_jobs": 0,
    "status": None,
    "message": None,
}


# ── Scheduled job ────────────────────────────────────────────────────────────

async def _scheduled_scrape():
    """Hourly scrape job: iterate all queries → scrape → analyze."""
    global last_scrape_result

    logger.info("Scheduled scrape starting...")

    try:
        from app.services.job_scraper import job_scraper
        from app.services.jd_analyzer import jd_analyzer
        from app.services.dynamo_service import dynamo_service

        # 1. Scrape all search queries (shared, no userId)
        result = await job_scraper.scrape_all_queries()

        # 2. Analyze new unanalyzed jobs
        all_jobs = await dynamo_service.scan("Jobs")
        unanalyzed = [j for j in all_jobs if not j.get("isAnalyzed")]
        analyzed_count = 0
        if unanalyzed:
            analyzed_count = await jd_analyzer.analyze_and_store(unanalyzed)

        last_scrape_result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_jobs": result.get("total_found", 0),
            "new_jobs": result.get("new_jobs", 0),
            "status": "success",
            "message": (
                f"Found {result.get('total_found', 0)} jobs, "
                f"{result.get('new_jobs', 0)} new, "
                f"{analyzed_count} analyzed"
            ),
        }
        logger.info("Scheduled scrape complete", **last_scrape_result)

    except Exception as e:
        logger.error(f"Scheduled scrape failed: {e}")
        last_scrape_result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_jobs": 0,
            "new_jobs": 0,
            "status": "failed",
            "message": str(e),
        }


# ── Lifecycle ────────────────────────────────────────────────────────────────

def start_scheduler():
    """Start the hourly scheduler. First scrape after a 10-second delay."""
    global _scheduler

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _scheduled_scrape,
        trigger=IntervalTrigger(hours=1),
        id="job_scrape",
        name="Hourly Job Scrape",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=10),
    )
    _scheduler.start()
    logger.info("Job scrape scheduler started (interval: 1 hour, first run in 10s)")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Job scrape scheduler stopped")


def get_scheduler_status() -> dict:
    """Return scheduler status, next run time, and last scrape result."""
    global _scheduler, last_scrape_result

    if not _scheduler or not _scheduler.running:
        return {
            "running": False,
            "next_run_time": None,
            "last_scrape": last_scrape_result,
        }

    job = _scheduler.get_job("job_scrape")
    next_run = None
    if job and job.next_run_time:
        next_run = job.next_run_time.isoformat()

    return {
        "running": True,
        "next_run_time": next_run,
        "last_scrape": last_scrape_result,
    }
