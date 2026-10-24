"""Pure helpers in the job scraper: freshness, dedup ids, role filters, salary parsing."""

from datetime import datetime, timedelta

import pytest

from app.services.job_scraper import (
    _extract_salary_from_description,
    _generate_job_id,
    _is_management_role,
    _is_recent_job,
)


def test_empty_date_counts_as_recent():
    assert _is_recent_job("", 24)
    assert _is_recent_job(None, 24)


def test_iso_dates_compare_against_the_cutoff():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    old = (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%d")
    assert _is_recent_job(today + "T09:00:00Z", 48)
    assert not _is_recent_job(old, 48)


@pytest.mark.parametrize("text", ["Today", "Just added", "1 d", "few hours ago"])
def test_relative_fresh_labels_are_recent(text):
    assert _is_recent_job(text, 24)


def test_day_counts_respect_max_age():
    assert _is_recent_job("3 d", 72)
    assert not _is_recent_job("3 d", 48)


def test_unknown_formats_are_included():
    assert _is_recent_job("posted a while back", 1)


def test_job_id_is_stable_per_url():
    url = "https://jobs.example.com/view/123"
    assert _generate_job_id(url) == _generate_job_id(url)
    assert _generate_job_id(url) != _generate_job_id(url + "4")
    assert len(_generate_job_id(url)) == 32


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Product Manager Intern", True),
        ("Digital Marketing Intern", True),
        ("Backend Developer Intern", False),
        ("ML Engineer", False),
    ],
)
def test_management_roles_are_flagged(title, expected):
    assert _is_management_role(title) is expected


@pytest.mark.parametrize(
    "description,expected",
    [
        ("Stipend: ₹10,000 - ₹15,000 per month", "₹10,000–₹15,000"),
        ("**Stipend**: Rs. 8000 per month", "₹8000 / month"),
        ("Offering 6-8 LPA for freshers", "6–8 LPA"),
        ("Package of 4.5 LPA", "4.5 LPA"),
        ("CTC: ₹600000", "CTC ₹600000"),
        ("Pay is $50,000 to $70,000", "$50,000–$70,000"),
        ("Competitive pay", None),
        ("", None),
    ],
)
def test_salary_extraction(description, expected):
    assert _extract_salary_from_description(description) == expected
