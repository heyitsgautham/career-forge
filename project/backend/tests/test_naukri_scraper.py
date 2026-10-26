"""Naukri scraper: role expansion, search URLs and parsing the search API JSON, offline."""

import asyncio
from urllib.parse import parse_qs, urlparse

from app.services import naukri_scraper
from app.services.naukri_scraper import (
    NaukriScraper,
    _expand_roles,
    _parse_naukri_job,
    build_naukri_url,
)

RAW = {
    "title": "Backend Intern",
    "jdURL": "/job-listings-backend-intern-sample-labs-1",
    "companyName": " Sample Labs ",
    "placeholders": [
        {"type": "location", "label": "Chennai, Bengaluru, Pune"},
        {"type": "salary", "label": "15-20k"},
        {"type": "date", "label": "2 days ago"},
    ],
    "jobDescription": "<p>Build <b>REST</b> APIs</p>",
    "tagsAndSkills": "python,fastapi",
}


def test_expand_roles_splits_or_groups_and_adds_the_suffix_once():
    roles = _expand_roles(
        [
            '("Software Engineer" OR "SDE") Intern',
            '("Research Intern" OR "SDE") Intern',
            '"Data Analyst"',
        ]
    )
    assert roles == ["Software Engineer intern", "SDE intern", "Research Intern", "Data Analyst"]


def test_build_url_puts_roles_and_cities_in_the_query():
    url = build_naukri_url(["SDE intern", "ML intern"], ["chennai", "pune"], job_age=1, path="jobs")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.path == "/jobs"
    assert query["k"] == ["SDE intern, ML intern"]
    assert query["l"] == ["chennai, pune"]
    assert query["jobAge"] == ["1"]


def test_parses_a_search_result():
    assert _parse_naukri_job(RAW) == {
        "title": "Backend Intern",
        "company": "Sample Labs",
        "location": "Chennai, Bengaluru",
        "description": "Build  REST  APIs",
        "url": "https://www.naukri.com/job-listings-backend-intern-sample-labs-1",
        "source": "naukri",
        "date_posted": "2 days ago",
        "salary": None,
        "job_type": "Internship",
    }


def test_falls_back_to_skills_and_direct_fields():
    job = _parse_naukri_job(
        {
            "title": "SDE",
            "url": "https://www.naukri.com/x",
            "company": {"name": "Demo Corp"},
            "location": ["Remote"],
            "tagsAndSkills": ["Go", "SQL"],
            "createdDate": 1700000000000,
            "salary": "Not disclosed",
        }
    )
    assert job["company"] == "Demo Corp"
    assert job["location"] == "Remote"
    assert job["description"] == "Go, SQL"
    assert job["date_posted"] == "1700000000000"
    assert job["salary"] == "Not disclosed"
    assert job["job_type"] == "Full-time"


def test_skips_results_without_a_title_or_link():
    assert _parse_naukri_job({"title": "SDE"}) is None
    assert _parse_naukri_job({"jdURL": "/x"}) is None


def test_a_company_given_as_text_is_used_as_is():
    # Regression: {"company": "Demo Corp"}.get raised and the whole batch was lost.
    job = _parse_naukri_job({"title": "SDE", "jdURL": "/x", "company": "Demo Corp"})
    assert job["company"] == "Demo Corp"


def test_one_unparsable_result_does_not_lose_the_batch(monkeypatch):
    async def fake_fetch(url, **_kwargs):
        return [RAW, {"title": "SDE", "jdURL": "/y", "placeholders": ["not a dict"]}, RAW]

    monkeypatch.setattr(naukri_scraper, "_fetch_jobs_via_browser", fake_fetch)
    monkeypatch.setattr(naukri_scraper, "_get_role_list", lambda: ["SDE intern"])
    jobs = asyncio.run(NaukriScraper().scrape_location_batch(["chennai"]))
    assert len(jobs) >= 2


def test_scrape_all_covers_both_pages_and_both_city_batches(monkeypatch):
    seen_urls = []

    async def fake_fetch(url, **_kwargs):
        seen_urls.append(url)
        return [RAW]

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(naukri_scraper, "_fetch_jobs_via_browser", fake_fetch)
    monkeypatch.setattr(naukri_scraper, "_get_role_list", lambda: ["SDE intern"])
    monkeypatch.setattr(naukri_scraper.asyncio, "sleep", no_sleep)
    jobs = asyncio.run(NaukriScraper().scrape_all())
    assert len(seen_urls) == 4
    assert len(jobs) == 1
