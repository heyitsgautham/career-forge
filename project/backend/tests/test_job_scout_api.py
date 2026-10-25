"""Job Scout, tracking and blacklist routes on DynamoDB (moto)."""

import asyncio
from datetime import datetime, timezone

import pytest

from app.services import jd_analyzer as jd_module
from app.services import job_scraper as scraper_module
from app.services.dynamo_service import dynamo_service

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def seed_jobs():
    jobs = [
        {
            "jobId": "a",
            "title": "SDE Intern",
            "company": "Sample Labs",
            "category": "SDE",
            "matchScore": 80,
            "createdAt": f"{TODAY}T09:00:00",
            "isAnalyzed": True,
        },
        {
            "jobId": "b",
            "title": "ML Intern",
            "company": "acme ai",
            "category": "AI/ML",
            "matchScore": 40,
            "createdAt": "2026-01-01T00:00:00",
            "isAnalyzed": True,
        },
        {
            "jobId": "c",
            "title": "Data Intern",
            "company": "Blocked Co",
            "category": ["Data"],
            "matchScore": 10,
            "createdAt": "2026-02-01T00:00:00",
        },
        {"jobId": "d", "title": "Ops", "company": "Zeta", "createdAt": "2026-03-01T00:00:00"},
    ]
    for job in jobs:
        asyncio.run(dynamo_service.put_item("Jobs", job))
    asyncio.run(dynamo_service.put_item("BlacklistedCompanies", {"companyName": "blocked co"}))


def test_matches_hide_blacklisted_companies_and_sort(dynamo_client, dynamo_auth):
    seed_jobs()
    h = dynamo_auth["headers"]
    by_date = dynamo_client.get("/api/jobs/matches", headers=h).json()
    assert [j["jobId"] for j in by_date] == ["a", "d", "b"]

    by_match = dynamo_client.get("/api/jobs/matches?sort_by=match", headers=h).json()
    assert [j["jobId"] for j in by_match] == ["a", "b", "d"]
    by_company = dynamo_client.get("/api/jobs/matches?sort_by=company", headers=h).json()
    assert [j["company"] for j in by_company] == ["acme ai", "Sample Labs", "Zeta"]

    assert [
        j["jobId"] for j in dynamo_client.get("/api/jobs/matches?role=ai", headers=h).json()
    ] == ["b"]
    assert [
        j["jobId"] for j in dynamo_client.get("/api/jobs/matches?minMatch=50", headers=h).json()
    ] == ["a"]
    assert len(dynamo_client.get("/api/jobs/matches?limit=1", headers=h).json()) == 1


def test_stats_summarise_every_job(dynamo_client, dynamo_auth):
    seed_jobs()
    stats = dynamo_client.get("/api/jobs/stats", headers=dynamo_auth["headers"]).json()
    assert stats["totalJobs"] == 4
    assert stats["analyzedJobs"] == 2
    assert stats["newToday"] == 1
    assert stats["averageMatch"] == pytest.approx(43.3)
    assert stats["matchDistribution"] == {"0-25": 1, "25-50": 1, "50-75": 0, "75-100": 1}
    assert {"category": "Uncategorized", "count": 1} in stats["topCategories"]
    assert {"category": "Data", "count": 1} in stats["topCategories"]


def test_scheduler_status_reports_not_running(dynamo_client, dynamo_auth):
    body = dynamo_client.get("/api/jobs/scheduler/status", headers=dynamo_auth["headers"]).json()
    assert body["running"] is False
    assert body["nextRunTime"] is None


def test_job_detail_and_admin_delete(dynamo_client, dynamo_auth, make_admin):
    seed_jobs()
    h = dynamo_auth["headers"]
    assert dynamo_client.get("/api/jobs/scout/a", headers=h).json()["title"] == "SDE Intern"
    assert dynamo_client.get("/api/jobs/scout/zz", headers=h).status_code == 404

    assert dynamo_client.delete("/api/jobs/scout/a", headers=h).status_code == 403
    make_admin(dynamo_auth)
    assert dynamo_client.delete("/api/jobs/scout/a", headers=h).json() == {"message": "Job deleted"}
    assert dynamo_client.delete("/api/jobs/scout/a", headers=h).status_code == 404


def test_tracking_statuses_are_per_user(dynamo_client, dynamo_auth):
    h = dynamo_auth["headers"]
    r = dynamo_client.post(
        "/api/jobs/scout/a/track", json={"status": "applied", "notes": "Sent"}, headers=h
    )
    assert r.json() == {"message": "Status updated", "status": "applied"}
    dynamo_client.post("/api/jobs/scout/b/track", json={"status": "saved"}, headers=h)
    assert dynamo_client.get("/api/jobs/tracking", headers=h).json() == {
        "a": {"status": "applied", "notes": "Sent"},
        "b": {"status": "saved", "notes": ""},
    }


def test_blacklist_is_admin_only(dynamo_client, dynamo_auth, make_admin):
    h = dynamo_auth["headers"]
    assert dynamo_client.get("/api/jobs/blacklist", headers=h).status_code == 403
    make_admin(dynamo_auth)
    assert dynamo_client.post(
        "/api/jobs/blacklist", json={"companyName": "Spam Inc"}, headers=h
    ).json() == {"message": "'Spam Inc' blacklisted"}
    assert [
        b["companyName"] for b in dynamo_client.get("/api/jobs/blacklist", headers=h).json()
    ] == ["Spam Inc"]
    dynamo_client.delete("/api/jobs/blacklist/Spam Inc", headers=h)
    assert dynamo_client.get("/api/jobs/blacklist", headers=h).json() == []


@pytest.fixture
def fake_scrapers(monkeypatch):
    scraper = scraper_module.job_scraper
    state = {"analyzed": []}

    async def scrape_and_store(**kwargs):
        state["jobspy"] = kwargs
        return [{"jobId": "x"}]

    async def load_existing_urls():
        scraper._existing_urls = {"https://jobs.example/seen"}

    async def scrape_india_sources(sources=None):
        return [
            {
                "url": "https://jobs.example/new",
                "title": "SDE",
                "company": "Sample Labs",
                "source": "naukri",
            },
            {"url": "https://jobs.example/seen", "title": "Old"},
            {"url": "", "title": "No URL"},
        ]

    async def scrape_all_queries(include_india_sources=False):
        return {"total_found": 9, "new_jobs": 2}

    async def analyze_and_store(jobs):
        state["analyzed"].append([j["jobId"] for j in jobs])
        return len(jobs)

    for fn in (scrape_and_store, scrape_india_sources, scrape_all_queries):
        monkeypatch.setattr(scraper, fn.__name__, fn)
    monkeypatch.setattr(scraper, "_load_existing_urls", load_existing_urls)
    monkeypatch.setattr(jd_module.jd_analyzer, "analyze_and_store", analyze_and_store)
    return state


def test_manual_scrape_stores_new_india_jobs_and_analyzes(
    dynamo_client, dynamo_auth, make_admin, fake_scrapers
):
    make_admin(dynamo_auth)
    body = dynamo_client.post(
        "/api/jobs/scout/scrape",
        json={"search_term": "python intern", "include_india_sources": True},
        headers=dynamo_auth["headers"],
    ).json()
    assert body["jobspy_new"] == 1 and body["india_new"] == 1 and body["total_new"] == 2
    assert body["analyzed"] == 1
    stored = asyncio.run(dynamo_service.scan("Jobs"))
    assert [j["url"] for j in stored] == ["https://jobs.example/new"]
    assert fake_scrapers["jobspy"]["search_term"] == "python intern"


def test_full_scrape_reports_sources(dynamo_client, dynamo_auth, make_admin, fake_scrapers):
    make_admin(dynamo_auth)
    body = dynamo_client.post("/api/jobs/scout/scrape/all", headers=dynamo_auth["headers"]).json()
    assert body["total_found"] == 9
    assert body["analyzed"] == 0
    assert "naukri" in body["sources"]


def test_scrape_is_admin_only(dynamo_client, dynamo_auth):
    assert (
        dynamo_client.post("/api/jobs/scout/scrape/all", headers=dynamo_auth["headers"]).status_code
        == 403
    )
