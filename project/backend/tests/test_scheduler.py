"""Hourly scrape scheduler: the job body, lifecycle and status."""

import asyncio
from datetime import datetime

import pytest

from app.services import jd_analyzer as jd_module
from app.services import job_scraper as scraper_module
from app.services import scheduler
from app.services.dynamo_service import dynamo_service


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    monkeypatch.setattr(scheduler, "last_scrape_result", dict(scheduler.last_scrape_result))
    monkeypatch.setattr(scheduler, "_scheduler", None)


async def test_scheduled_scrape_records_success(aws, monkeypatch):
    async def scrape_all_queries():
        return {"total_found": 12, "new_jobs": 3}

    async def analyze_and_store(jobs):
        return len(jobs)

    monkeypatch.setattr(scraper_module.job_scraper, "scrape_all_queries", scrape_all_queries)
    monkeypatch.setattr(jd_module.jd_analyzer, "analyze_and_store", analyze_and_store)
    await dynamo_service.put_item("Jobs", {"jobId": "j1"})
    await dynamo_service.put_item("Jobs", {"jobId": "j2", "isAnalyzed": True})

    await scheduler._scheduled_scrape()
    result = scheduler.get_scheduler_status()["last_scrape"]
    assert result["status"] == "success"
    assert result["message"] == "Found 12 jobs, 3 new, 1 analyzed"


async def test_scheduled_scrape_records_failure(monkeypatch):
    async def broken():
        raise RuntimeError("portal down")

    monkeypatch.setattr(scraper_module.job_scraper, "scrape_all_queries", broken)
    await scheduler._scheduled_scrape()
    result = scheduler.last_scrape_result
    assert (result["status"], result["message"]) == ("failed", "portal down")


async def test_start_reports_the_next_hourly_run_and_stop_ends_it():
    scheduler.start_scheduler()
    try:
        status = scheduler.get_scheduler_status()
        assert status["running"] is True
        next_run = datetime.fromisoformat(status["next_run_time"])
        assert (next_run.minute, next_run.second) == (0, 0)
    finally:
        scheduler.stop_scheduler()
    await asyncio.sleep(0)
    assert scheduler.get_scheduler_status()["running"] is False


def test_stop_without_start_is_a_no_op():
    scheduler.stop_scheduler()
    assert scheduler.get_scheduler_status()["running"] is False
