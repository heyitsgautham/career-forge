"""
Job Scraper Service
===================
Scrapes job listings from multiple portals using jobspy.
Stores results in DynamoDB. AWS-native replacement for old Firestore-based scraper.
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog

from app.core.config import settings
from app.services.dynamo_service import dynamo_service

logger = structlog.get_logger()


class JobScraper:
    """
    Job scraper using jobspy library.
    Fetches from LinkedIn, Indeed, and other supported sites.
    """

    # Defaults
    DEFAULT_SITES = ["indeed", "linkedin"]
    DEFAULT_LOCATION = "India"
    DEFAULT_RESULTS_WANTED = 30
    DEFAULT_HOURS_OLD = 72  # 3 days

    def __init__(self):
        pass

    async def scrape_jobs(
        self,
        search_term: str,
        location: Optional[str] = None,
        sites: Optional[List[str]] = None,
        results_wanted: int = DEFAULT_RESULTS_WANTED,
        hours_old: int = DEFAULT_HOURS_OLD,
        country: str = "India",
    ) -> List[Dict[str, Any]]:
        """
        Scrape real jobs from LinkedIn / Indeed via jobspy.

        Args:
            search_term: Job title / keyword (e.g. "Backend Developer")
            location: Location filter
            sites: List of sites to scrape (default: indeed, linkedin)
            results_wanted: Max results per site
            hours_old: Only jobs posted within this many hours
            country: Country for search context

        Returns:
            List of raw job dicts (all fields from real scrape — no fabricated data)
        """
        location = location or self.DEFAULT_LOCATION
        sites = sites or self.DEFAULT_SITES
        return await self._scrape_with_jobspy(
            search_term=search_term,
            location=location,
            sites=sites,
            results_wanted=results_wanted,
            hours_old=hours_old,
            country=country,
        )

    async def _scrape_with_jobspy(
        self,
        search_term: str,
        location: str,
        sites: List[str],
        results_wanted: int,
        hours_old: int,
        country: str,
    ) -> List[Dict[str, Any]]:
        """Scrape real jobs using jobspy. Raises on failure — no fake-data fallback."""
        from jobspy import scrape_jobs

        JOB_TYPE_MAP = {
            "fulltime": "Full-time",
            "parttime": "Part-time",
            "internship": "Internship",
            "contract": "Contract",
            "temporary": "Temporary",
        }

        logger.info(
            "Scraping real jobs",
            search_term=search_term,
            location=location,
            sites=sites,
            results_wanted=results_wanted,
        )

        df = await asyncio.to_thread(
            scrape_jobs,
            site_name=sites,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            hours_old=hours_old,
            country_indeed=country,
        )

        jobs = []
        for _, row in df.iterrows():
            # ── Salary: built only from real scraped fields ──────────────────
            salary = None
            min_a = row.get("min_amount")
            max_a = row.get("max_amount")
            currency = str(row.get("currency") or "").strip()
            interval = str(row.get("interval") or "").strip()
            if min_a and max_a:
                salary = f"{currency}{int(min_a):,}–{currency}{int(max_a):,}"
                if interval:
                    salary += f" / {interval}"
            elif min_a:
                salary = f"{currency}{int(min_a):,}+"
                if interval:
                    salary += f" / {interval}"
            # If neither field is present, salary stays None

            # ── Job type: normalise casing ───────────────────────────────────
            raw_type = str(row.get("job_type") or "").lower().strip()
            job_type = JOB_TYPE_MAP.get(raw_type, raw_type.capitalize())

            job = {
                "title": str(row.get("title") or "").strip() or None,
                "company": str(row.get("company") or "").strip() or None,
                "location": str(row.get("location") or location).strip(),
                "description": str(row.get("description") or ""),
                "url": str(row.get("job_url") or ""),
                "source": str(row.get("site") or "unknown"),
                "date_posted": str(row.get("date_posted") or ""),
                "salary": salary,
                "job_type": job_type,
            }
            # Skip rows with no title or URL (incomplete scrape rows)
            if job["title"] and job["url"]:
                jobs.append(job)

        logger.info(f"Scraped {len(jobs)} real jobs for '{search_term}'")
        return jobs

    def _generate_mock_jobs(
        self,
        search_term: str,
        location: str,
        count: int,
    ) -> List[Dict[str, Any]]:
        """REMOVED — all data must come from real jobspy scrapes. Returns empty to satisfy the interface."""
        return []

    async def scrape_and_store(
        self,
        user_id: str,
        search_term: str,
        location: Optional[str] = None,
        sites: Optional[List[str]] = None,
        results_wanted: int = DEFAULT_RESULTS_WANTED,
    ) -> List[Dict[str, Any]]:
        """
        Scrape jobs and store them in DynamoDB.

        Args:
            user_id: ID of the user triggering the scrape
            search_term: Job search keyword
            location: Location filter
            sites: Sites to scrape
            results_wanted: Number of results

        Returns:
            List of stored job items (with jobId assigned)
        """
        raw_jobs = await self.scrape_jobs(
            search_term=search_term,
            location=location,
            sites=sites,
            results_wanted=results_wanted,
        )

        stored_jobs = []
        now = dynamo_service.now_iso()

        for raw_job in raw_jobs:
            job_id = dynamo_service.generate_id()
            item = {
                "jobId": job_id,
                "userId": user_id,
                "title": raw_job["title"],
                "company": raw_job["company"],
                "location": raw_job.get("location", ""),
                "description": raw_job.get("description", ""),
                "url": raw_job.get("url", ""),
                "source": raw_job.get("source", "unknown"),
                "datePosted": raw_job.get("date_posted", ""),
                "salary": raw_job.get("salary"),
                "jobType": raw_job.get("job_type", ""),
                # Analysis fields (populated by jd_analyzer later)
                "category": None,
                "requiredSkills": [],
                "preferredSkills": [],
                "experienceLevel": None,
                "atsKeywords": [],
                "isAnalyzed": False,
                "isPaid": None,
                # Match scoring (populated by match_scorer later)
                "matchScore": None,
                "matchBreakdown": None,
                "missingSkills": [],
                # Metadata
                "searchTerm": search_term,
                "createdAt": now,
                "updatedAt": now,
            }

            try:
                await dynamo_service.put_item("Jobs", item)
                stored_jobs.append(item)
            except Exception as e:
                logger.error("Failed to store job", job_title=raw_job["title"], error=str(e))

        logger.info(
            f"Stored {len(stored_jobs)}/{len(raw_jobs)} jobs for user {user_id}",
            search_term=search_term,
        )
        return stored_jobs


# Global instance
job_scraper = JobScraper()
