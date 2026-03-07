"""
Unstop Job / Internship Scraper
================================
Scrapes opportunities from Unstop.com (formerly Dare2Compete) via their
public REST API.

Key endpoints:
    GET https://unstop.com/api/public/opportunity/search-result
        ?opportunity=jobs|internship
        &search=<keyword>
        &per_page=20
        &page=1
        &oppstatus=open

Returns jobs as dicts compatible with the shared JobScraper job schema.
"""

import asyncio
import hashlib
from typing import List, Dict, Any, Optional

import httpx
import structlog

logger = structlog.get_logger()

# ── Constants ────────────────────────────────────────────────────────────────

UNSTOP_API = "https://unstop.com/api/public/opportunity/search-result"

UNSTOP_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "accept": "application/json, text/plain, */*",
    "referer": "https://unstop.com/",
    "origin": "https://unstop.com",
}

UNSTOP_SEARCH_KEYWORDS = [
    "software engineer",
    "software developer",
    "machine learning",
    "data science",
    "full stack developer",
    "frontend developer",
    "backend developer",
    "android developer",
    "devops",
    "data analyst",
    "generative AI",
    "web developer",
    "python developer",
    "react developer",
    "cloud engineer",
]

# Opportunity types to scrape
UNSTOP_OPP_TYPES = ["jobs", "internship"]

# ── Helper ───────────────────────────────────────────────────────────────────

def _job_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _parse_unstop_opportunity(item: dict, opp_type: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single Unstop search-result item.
    `item` is the dict inside data.data[].
    """
    # Title may live at item.title or item.opportunity_name
    title = (
        item.get("title")
        or item.get("opportunity_name")
        or item.get("name")
        or ""
    ).strip()

    if not title:
        return None

    # Canonical URL
    slug = item.get("public_url") or item.get("slug") or ""
    opp_id = item.get("id", "")
    if slug:
        url = f"https://unstop.com/{slug}"
    elif opp_id:
        category = "jobs" if opp_type == "jobs" else "internship"
        url = f"https://unstop.com/{category}/{opp_id}"
    else:
        return None

    # Organisation / company name
    org = item.get("organisation") or {}
    company = (
        org.get("name")
        if isinstance(org, dict)
        else str(org)
    ).strip() if org else ""

    # Location — may be a list of strings or a single string
    raw_loc = item.get("location") or item.get("city") or ""
    if isinstance(raw_loc, list):
        location = ", ".join(str(l).strip() for l in raw_loc[:2] if l)
    else:
        location = str(raw_loc).strip() or "India / Remote"

    # Salary / stipend
    salary_min = item.get("salary_min") or item.get("min_stipend")
    salary_max = item.get("salary_max") or item.get("max_stipend")
    currency = item.get("currency") or "₹"
    if salary_min and salary_max:
        salary = f"{currency}{int(salary_min):,}–{currency}{int(salary_max):,}"
    elif salary_min:
        salary = f"{currency}{int(salary_min):,}+"
    else:
        salary = None

    # Job type
    if opp_type == "internship":
        job_type = "Internship"
    elif "intern" in title.lower():
        job_type = "Internship"
    else:
        job_type = "Full-time"

    # Date
    date_posted = str(item.get("start_date") or item.get("created_at") or "").split("T")[0]

    # Description — concatenate available text fields
    description_parts = []
    if item.get("description"):
        description_parts.append(item["description"])
    if item.get("eligibility"):
        description_parts.append(f"Eligibility: {item['eligibility']}")
    description = "\n".join(description_parts)

    return {
        "title": title,
        "company": company or "Unknown",
        "location": location,
        "description": description,
        "url": url,
        "source": "unstop",
        "date_posted": date_posted,
        "salary": salary,
        "job_type": job_type,
    }


# ── Scraper class ────────────────────────────────────────────────────────────

class UnstopScraper:
    """Async scraper for Unstop.com's public search API."""

    def __init__(self, timeout: int = 15, max_retries: int = 2):
        self._timeout = timeout
        self._max_retries = max_retries

    # ── Public API ───────────────────────────────────────────────────────────

    async def scrape(
        self,
        keyword: str,
        opp_type: str = "jobs",          # "jobs" or "internship"
        results_wanted: int = 20,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        """Scrape Unstop for a single keyword + opportunity type."""
        params = {
            "opportunity": opp_type,
            "search": keyword,
            "per_page": results_wanted,
            "page": page,
            "oppstatus": "open",
        }

        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    headers=UNSTOP_HEADERS, timeout=self._timeout, follow_redirects=True
                ) as client:
                    resp = await client.get(UNSTOP_API, params=params)
                    resp.raise_for_status()
                    data = resp.json()

                items = (data.get("data") or {}).get("data") or []
                results: List[Dict[str, Any]] = []
                for item in items:
                    parsed = _parse_unstop_opportunity(item, opp_type)
                    if parsed:
                        results.append(parsed)

                logger.info(
                    "Unstop scrape complete",
                    keyword=keyword,
                    opp_type=opp_type,
                    found=len(results),
                )
                return results

            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"Unstop HTTP error (attempt {attempt}): {e.response.status_code}"
                )
            except Exception as e:
                logger.warning(f"Unstop error (attempt {attempt}): {e}")

            if attempt < self._max_retries:
                await asyncio.sleep(2 * attempt)

        return []

    async def scrape_all(
        self,
        results_per_keyword: int = 15,
    ) -> List[Dict[str, Any]]:
        """
        Iterate all keywords × opportunity types.
        Returns deduplicated list of job dicts.
        """
        seen_urls: set = set()
        all_jobs: List[Dict[str, Any]] = []

        for opp_type in UNSTOP_OPP_TYPES:
            for kw in UNSTOP_SEARCH_KEYWORDS:
                jobs = await self.scrape(
                    kw, opp_type=opp_type, results_wanted=results_per_keyword
                )
                for job in jobs:
                    url = job.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_jobs.append(job)
                await asyncio.sleep(1.0)  # gentle rate-limit delay

        logger.info(f"Unstop total scraped: {len(all_jobs)} unique opportunities")
        return all_jobs


# ── Global instance ──────────────────────────────────────────────────────────

unstop_scraper = UnstopScraper()
