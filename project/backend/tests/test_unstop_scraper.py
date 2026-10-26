"""Unstop scraper: parsing search results and surviving odd items, offline."""

import asyncio

import pytest

from app.services import unstop_scraper
from app.services.unstop_scraper import UnstopScraper, _parse_unstop_opportunity
from tests.fake_http import FakeResponse

ITEM = {
    "id": 101,
    "title": "Backend Intern",
    "public_url": "internships/backend-intern-sample-labs-101",
    "organisation": {"name": "Sample Labs"},
    "location": ["Bengaluru", "Remote", "Pune"],
    "min_stipend": 15000,
    "max_stipend": 20000,
    "start_date": "2026-03-01T10:00:00Z",
    "description": "Build APIs",
    "eligibility": "Final-year students",
}


def test_parses_a_full_item():
    job = _parse_unstop_opportunity(ITEM, "internship")
    assert job == {
        "title": "Backend Intern",
        "company": "Sample Labs",
        "location": "Bengaluru, Remote",
        "description": "Build APIs\nEligibility: Final-year students",
        "url": "https://unstop.com/internships/backend-intern-sample-labs-101",
        "source": "unstop",
        "date_posted": "2026-03-01",
        "salary": "₹15,000–₹20,000",
        "job_type": "Internship",
    }


def test_falls_back_to_the_id_url_and_defaults():
    job = _parse_unstop_opportunity({"id": 7, "opportunity_name": "SDE Intern"}, "jobs")
    assert job["url"] == "https://unstop.com/jobs/7"
    assert job["company"] == "Unknown"
    assert job["location"] == "India / Remote"
    assert job["salary"] is None
    assert job["job_type"] == "Internship"


def test_skips_items_without_a_title_or_a_link():
    assert _parse_unstop_opportunity({"id": 1}, "jobs") is None
    assert _parse_unstop_opportunity({"title": "No link"}, "jobs") is None


@pytest.mark.parametrize(
    "fields,salary",
    [
        ({"salary_min": "12000.5"}, "₹12,000+"),
        ({"salary_min": "not disclosed"}, None),
        ({"salary_min": 0, "salary_max": 0}, None),
    ],
)
def test_salary_values_that_are_not_whole_numbers(fields, salary):
    # Regression: int("12000.5") raised, and one such item emptied the whole page.
    job = _parse_unstop_opportunity(
        {**ITEM, "min_stipend": None, "max_stipend": None, **fields}, "jobs"
    )
    assert job["salary"] == salary


def test_an_organisation_without_a_name():
    # Regression: {"name": None}.strip() raised.
    job = _parse_unstop_opportunity({**ITEM, "organisation": {"name": None}}, "jobs")
    assert job["company"] == "Unknown"


class FakeClient:
    pages: list = []
    requests: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None):
        type(self).requests.append(params)
        return type(self).pages.pop(0)


@pytest.fixture
def unstop(monkeypatch):
    client = type("Client", (FakeClient,), {"pages": [], "requests": []})
    monkeypatch.setattr(unstop_scraper.httpx, "AsyncClient", client)

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(unstop_scraper.asyncio, "sleep", no_sleep)
    return client


def page(*items):
    return FakeResponse({"data": {"data": list(items)}})


def test_a_bad_item_does_not_drop_the_rest_of_the_page(unstop):
    unstop.pages = [
        page(ITEM, {**ITEM, "id": 2, "public_url": "x-2", "organisation": {"name": None}})
    ]
    jobs = asyncio.run(UnstopScraper().scrape("backend", opp_type="internship"))
    assert len(jobs) == 2
    assert unstop.requests[0]["opportunity"] == "internship"


def test_retries_after_an_http_error_and_gives_up_quietly(unstop):
    unstop.pages = [FakeResponse({}, 503), page(ITEM)]
    assert len(asyncio.run(UnstopScraper(max_retries=2).scrape("backend"))) == 1

    unstop.pages = [FakeResponse({}, 503), FakeResponse({}, 503)]
    assert asyncio.run(UnstopScraper(max_retries=2).scrape("backend")) == []


def test_scrape_all_removes_duplicate_postings(unstop, monkeypatch):
    monkeypatch.setattr(unstop_scraper, "UNSTOP_SEARCH_KEYWORDS", ["a", "b"])
    unstop.pages = [page(ITEM), page(ITEM), page(ITEM), page()]
    jobs = asyncio.run(UnstopScraper().scrape_all(results_per_keyword=5))
    assert [j["url"] for j in jobs] == [
        "https://unstop.com/internships/backend-intern-sample-labs-101"
    ]
    assert len(unstop.requests) == 4
