"""JobScraper: turning jobspy rows into jobs, India sources, and storing new jobs, offline."""

import asyncio
from datetime import date

import jobspy
import pandas as pd
import pytest

from app.services import job_scraper as scraper_module
from app.services.job_scraper import JobScraper

ROWS = [
    {
        "title": "Backend Intern",
        "job_url": "https://jobs.example.com/1",
        "company": "Sample Labs",
        "location": "Chennai",
        "description": "Build APIs",
        "site": "linkedin",
        "date_posted": date(2026, 3, 9),
        "min_amount": 15000.0,
        "max_amount": 20000.0,
        "currency": "₹",
        "interval": "monthly",
        "job_type": "internship",
    },
    {
        # jobspy fills missing columns with NaN, which is truthy.
        "title": "Data Intern",
        "job_url": "https://jobs.example.com/2",
        "company": float("nan"),
        "location": float("nan"),
        "description": float("nan"),
        "site": "indeed",
        "date_posted": pd.NaT,
        "min_amount": float("nan"),
        "max_amount": float("nan"),
        "currency": float("nan"),
        "interval": float("nan"),
        "job_type": float("nan"),
    },
    {"title": "Product Manager", "job_url": "https://jobs.example.com/3"},
    {"title": "", "job_url": "https://jobs.example.com/4"},
]


@pytest.fixture
def jobspy_rows(monkeypatch):
    calls = []

    def fake_scrape_jobs(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame(ROWS)

    monkeypatch.setattr(jobspy, "scrape_jobs", fake_scrape_jobs)
    return calls


def test_jobspy_rows_become_jobs(jobspy_rows):
    jobs = asyncio.run(JobScraper().scrape_jobs("backend intern"))
    assert jobspy_rows[0]["site_name"] == ["indeed", "linkedin"]
    assert [j["title"] for j in jobs] == ["Backend Intern", "Data Intern"]
    assert jobs[0] == {
        "title": "Backend Intern",
        "company": "Sample Labs",
        "location": "Chennai",
        "description": "Build APIs",
        "url": "https://jobs.example.com/1",
        "source": "linkedin",
        "date_posted": "2026-03-09",
        "salary": "₹15,000–₹20,000 / monthly",
        "job_type": "Internship",
    }


def test_missing_jobspy_values_stay_empty_instead_of_crashing(jobspy_rows):
    # Regression: int(nan) raised on a row without a salary, which lost every job
    # for the query, and NaN text fields were stored as the string "nan".
    data_intern = asyncio.run(JobScraper().scrape_jobs("intern"))[1]
    assert data_intern["salary"] is None
    assert data_intern["company"] is None
    assert data_intern["location"] == "India"
    assert data_intern["description"] == ""
    assert data_intern["date_posted"] == ""
    assert data_intern["job_type"] == ""


def test_a_jobspy_failure_returns_no_jobs(monkeypatch):
    def broken(**_kwargs):
        raise RuntimeError("LinkedIn 429")

    monkeypatch.setattr(jobspy, "scrape_jobs", broken)
    assert asyncio.run(JobScraper().scrape_jobs("x")) == []


def test_india_sources_are_merged_without_duplicates_or_stale_unstop_posts(monkeypatch):
    async def naukri():
        return [
            {"url": "u1", "title": "A"},
            {"url": "u1", "title": "A again"},
            {"url": "", "title": "B"},
        ]

    async def unstop():
        return [
            {"url": "u2", "title": "Fresh", "date_posted": "2099-01-01"},
            {"url": "u3", "title": "Old", "date_posted": "2001-01-01"},
        ]

    monkeypatch.setattr(scraper_module.naukri_scraper, "scrape_all", naukri)
    monkeypatch.setattr(scraper_module.unstop_scraper, "scrape_all", unstop)
    jobs = asyncio.run(
        JobScraper().scrape_india_sources(sources=["naukri", "unstop", "x"], max_age_hours=24)
    )
    assert [j["title"] for j in jobs] == ["A", "Fresh"]


def test_a_failing_india_source_does_not_stop_the_others(monkeypatch):
    async def down():
        raise RuntimeError("blocked")

    async def unstop():
        return [{"url": "u2", "title": "Fresh"}]

    monkeypatch.setattr(scraper_module.naukri_scraper, "scrape_all", down)
    monkeypatch.setattr(scraper_module.unstop_scraper, "scrape_all", unstop)
    assert [j["title"] for j in asyncio.run(JobScraper().scrape_india_sources())] == ["Fresh"]


def test_scrape_and_store_saves_only_unseen_jobs(dynamo_client, jobspy_rows):
    from app.services.dynamo_service import dynamo_service

    scraper = JobScraper()
    stored = asyncio.run(scraper.scrape_and_store("backend intern"))
    assert [j["title"] for j in stored] == ["Backend Intern", "Data Intern"]
    assert stored[0]["searchTerm"] == "backend intern"

    again = asyncio.run(scraper.scrape_and_store("backend intern"))
    assert again == []
    assert len(asyncio.run(dynamo_service.scan("Jobs"))) == 2


def test_scrape_all_queries_counts_new_jobs(dynamo_client, jobspy_rows, monkeypatch):
    monkeypatch.setattr(scraper_module, "SEARCH_QUERIES", ["q1", "q2"])
    summary = asyncio.run(JobScraper().scrape_all_queries(include_india_sources=False))
    assert summary == {"total_found": 2, "new_jobs": 2, "duplicates_skipped": 0}
    again = asyncio.run(JobScraper().scrape_all_queries(include_india_sources=False))
    assert again == {"total_found": 2, "new_jobs": 0, "duplicates_skipped": 2}
