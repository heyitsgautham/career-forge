"""
Job Scraper Service
===================
Scrapes job listings from LinkedIn and Indeed using jobspy.
Stores results in DynamoDB as shared jobs (no userId — visible to all users).
Supports multi-query scraping with filtering and deduplication.
"""

import asyncio
import hashlib
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog

from app.core.config import settings
from app.services.dynamo_service import dynamo_service

logger = structlog.get_logger()

# ── Search queries covering major CS/tech roles ─────────────────────────────

SEARCH_QUERIES = [
    '("Software Engineer" OR "Software Developer" OR "SDE" OR "Full Stack" OR "Developer") Intern',
    '("Machine Learning" OR "AI Engineer" OR "Deep Learning" OR "Computer Vision" OR "NLP" OR "LLM") Intern',
    '("Data Scientist" OR "Data Analyst" OR "Data Engineer" OR "Business Intelligence" OR "Analytics") Intern',
    '("Web Developer" OR "Frontend Developer" OR "Backend Developer" OR "React" OR "Next.js" OR "Vue" OR "Angular") Intern',
    '("Android Developer" OR "iOS Developer" OR "Flutter" OR "React Native" OR "Mobile App") Intern',
    '("DevOps" OR "Cloud Engineer" OR "Site Reliability" OR "Platform Engineer" OR "Infrastructure" OR "AWS" OR "GCP" OR "Azure") Intern',
    '("Cyber Security" OR "Security Engineer" OR "Penetration Testing" OR "QA Engineer" OR "Automation Testing" OR "SDET") Intern',
    '("Systems Engineer" OR "Embedded" OR "Firmware" OR "IoT" OR "VLSI") Intern',
    '("Blockchain" OR "Web3" OR "Game Developer" OR "Unity" OR "Unreal" OR "AR/VR") Intern',
    '("Research Engineer" OR "Research Intern" OR "Algorithm" OR "HPC" OR "Compiler") Intern',
    '("Database" OR "SQL" OR "PostgreSQL" OR "Backend" OR "API Developer" OR "Microservices" OR "GraphQL") Intern',
    '("Generative AI" OR "GenAI" OR "MLOps" OR "AI/ML" OR "Prompt Engineer" OR "RAG") Intern',
]

# ── Management / non-engineering role keywords to always exclude ─────────────

MANAGEMENT_ROLE_KEYWORDS = [
    "project manager", "product manager", "program manager", "hr intern",
    "human resources", "recruiter", "business development", "sales intern",
    "marketing intern", "operations manager", "scrum master", "agile coach",
    "account manager", "customer success", "talent acquisition", "social media",
    "content writer", "content marketing", "digital marketing", "seo intern",
    "finance intern", "accounting intern", "legal intern", "procurement",
    "supply chain", "logistics", "operations intern", "management trainee",
    "business analyst intern",
]


def _generate_job_id(job_url: str) -> str:
    """Generate a deterministic job ID from the URL for dedup."""
    return hashlib.md5(job_url.encode()).hexdigest()


def _is_management_role(title: str) -> bool:
    """Check if a job title matches management/non-engineering keywords."""
    title_lower = title.lower()
    return any(kw in title_lower for kw in MANAGEMENT_ROLE_KEYWORDS)


def _extract_salary_from_description(description: str) -> Optional[str]:
    """Extract salary from description using regex patterns as a fallback."""
    if not description:
        return None

    clean = re.sub(r"[*_]", "", description)
    clean = re.sub(r"\s+", " ", clean)

    patterns = [
        (r"stipend\s*:?\s*₹\s*(\d+(?:,\d+)*)\s*(?:-|to)\s*₹?\s*(\d+(?:,\d+)*)", "range_inr"),
        (r"stipend\s*:?\s*Rs\.?\s*(\d+(?:,\d+)*)\s*(?:per|/)?\s*(month|year)?", "stipend_rs"),
        (r"stipend\s*:?\s*₹\s*(\d+(?:,\d+)*)\s*(?:per|/)?\s*(month|year)?", "stipend_inr"),
        (r"(\d+(?:,\d+)*)\s*(?:-|to)\s*(\d+(?:,\d+)*)\s*(?:LPA|lpa)", "lpa_range"),
        (r"(\d+(?:\.\d+)?)\s*(?:LPA|lpa)", "lpa_single"),
        (r"CTC\s*:?\s*₹?\s*(\d+(?:,\d+)*)", "ctc"),
        (r"\$\s*(\d+(?:,\d+)*)\s*(?:-|to)\s*\$?\s*(\d+(?:,\d+)*)", "usd_range"),
    ]

    for pattern, label in patterns:
        match = re.search(pattern, clean, re.IGNORECASE)
        if match:
            groups = match.groups()
            if label == "range_inr":
                return f"₹{groups[0]}–₹{groups[1]}"
            elif label in ("stipend_rs", "stipend_inr"):
                suffix = f" / {groups[1]}" if len(groups) > 1 and groups[1] else ""
                return f"₹{groups[0]}{suffix}"
            elif label == "lpa_range":
                return f"{groups[0]}–{groups[1]} LPA"
            elif label == "lpa_single":
                return f"{groups[0]} LPA"
            elif label == "ctc":
                return f"CTC ₹{groups[0]}"
            elif label == "usd_range":
                return f"${groups[0]}–${groups[1]}"
    return None


class JobScraper:
    """
    Job scraper using jobspy library.
    Fetches from LinkedIn, Indeed, and other supported sites.
    Jobs are stored as shared resources (no userId).
    """

    DEFAULT_SITES = ["indeed", "linkedin"]
    DEFAULT_LOCATION = "India"
    DEFAULT_RESULTS_WANTED = 25
    DEFAULT_HOURS_OLD = 72  # 3 days

    def __init__(self):
        self._existing_urls: set = set()

    async def _load_existing_urls(self):
        """Load existing job URLs from DynamoDB for deduplication."""
        try:
            jobs = await dynamo_service.scan("Jobs")
            self._existing_urls = {j.get("url", "") for j in jobs if j.get("url")}
        except Exception:
            self._existing_urls = set()

    async def scrape_jobs(
        self,
        search_term: str,
        location: Optional[str] = None,
        sites: Optional[List[str]] = None,
        results_wanted: int = DEFAULT_RESULTS_WANTED,
        hours_old: int = DEFAULT_HOURS_OLD,
        country: str = "India",
    ) -> List[Dict[str, Any]]:
        """Scrape real jobs from LinkedIn / Indeed via jobspy."""
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
        """Scrape real jobs using jobspy."""
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

        try:
            df = await asyncio.to_thread(
                scrape_jobs,
                site_name=sites,
                search_term=search_term,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                country_indeed=country,
            )
        except Exception as e:
            logger.warning(f"Scrape failed for '{search_term}': {e}")
            return []

        jobs = []
        for _, row in df.iterrows():
            # ── Salary: built from real scraped fields, fallback to regex ─────
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

            # Regex fallback for salary
            if not salary:
                salary = _extract_salary_from_description(
                    str(row.get("description") or "")
                )

            # ── Job type: normalise casing ───────────────────────────────────
            raw_type = str(row.get("job_type") or "").lower().strip()
            job_type = JOB_TYPE_MAP.get(raw_type, raw_type.capitalize())

            title = str(row.get("title") or "").strip() or None
            url = str(row.get("job_url") or "")

            # Skip incomplete rows
            if not title or not url:
                continue

            # Always exclude management roles
            if _is_management_role(title):
                continue

            # Safely convert date_posted — pd.NaT is falsy so "or" short-circuits
            raw_date = row.get("date_posted")
            try:
                import pandas as pd
                date_posted_str = raw_date.strftime("%Y-%m-%d") if raw_date and raw_date is not pd.NaT else ""
            except Exception:
                s = str(raw_date) if raw_date else ""
                date_posted_str = "" if s.lower() in ("nan", "nat", "none", "null") else s

            job = {
                "title": title,
                "company": str(row.get("company") or "").strip() or None,
                "location": str(row.get("location") or location).strip(),
                "description": str(row.get("description") or ""),
                "url": url,
                "source": str(row.get("site") or "unknown"),
                "date_posted": date_posted_str,
                "salary": salary,
                "job_type": job_type,
            }
            jobs.append(job)

        logger.info(f"Scraped {len(jobs)} real jobs for '{search_term}'")
        return jobs

    async def scrape_all_queries(
        self,
        location: Optional[str] = None,
        results_per_query: int = 15,
    ) -> Dict[str, Any]:
        """
        Iterate through all SEARCH_QUERIES, scrape, deduplicate, and store.
        Called by the scheduler. Jobs are shared (no userId).

        Returns:
            Dict with total_found, new_jobs, duplicates_skipped counts.
        """
        await self._load_existing_urls()

        all_raw_jobs: List[Dict[str, Any]] = []
        seen_urls: set = set()

        for query in SEARCH_QUERIES:
            try:
                jobs = await self.scrape_jobs(
                    search_term=query,
                    location=location,
                    results_wanted=results_per_query,
                )
                for job in jobs:
                    url = job.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_raw_jobs.append(job)
            except Exception as e:
                logger.warning(f"Query '{query[:50]}...' failed: {e}")
                continue

        # Store new jobs (dedup against existing DB)
        new_count = 0
        now = dynamo_service.now_iso()

        for raw_job in all_raw_jobs:
            url = raw_job.get("url", "")
            if url in self._existing_urls:
                continue  # already in DB

            job_id = _generate_job_id(url)
            item = {
                "jobId": job_id,
                "title": raw_job["title"],
                "company": raw_job["company"],
                "location": raw_job.get("location", ""),
                "description": raw_job.get("description", ""),
                "url": url,
                "source": raw_job.get("source", "unknown"),
                "datePosted": raw_job.get("date_posted", ""),
                "salary": raw_job.get("salary"),
                "jobType": raw_job.get("job_type", ""),
                "category": None,
                "requiredSkills": [],
                "preferredSkills": [],
                "experienceLevel": None,
                "atsKeywords": [],
                "isAnalyzed": False,
                "isPaid": None,
                "searchTerm": raw_job.get("_query", ""),
                "createdAt": now,
                "updatedAt": now,
            }

            try:
                await dynamo_service.put_item("Jobs", item)
                self._existing_urls.add(url)
                new_count += 1
            except Exception as e:
                logger.warning(f"Failed to store job: {e}")

        total = len(all_raw_jobs)
        logger.info(
            f"Scrape complete: {total} total, {new_count} new, "
            f"{total - new_count} duplicates skipped"
        )
        return {
            "total_found": total,
            "new_jobs": new_count,
            "duplicates_skipped": total - new_count,
        }

    async def scrape_and_store(
        self,
        search_term: str,
        location: Optional[str] = None,
        sites: Optional[List[str]] = None,
        results_wanted: int = DEFAULT_RESULTS_WANTED,
    ) -> List[Dict[str, Any]]:
        """
        Scrape jobs and store them in DynamoDB (shared — no userId).

        Returns:
            List of stored job items (with jobId assigned)
        """
        await self._load_existing_urls()

        raw_jobs = await self.scrape_jobs(
            search_term=search_term,
            location=location,
            sites=sites,
            results_wanted=results_wanted,
        )

        stored_jobs = []
        now = dynamo_service.now_iso()

        for raw_job in raw_jobs:
            url = raw_job.get("url", "")
            if url in self._existing_urls:
                continue  # dedup

            job_id = _generate_job_id(url) if url else dynamo_service.generate_id()
            item = {
                "jobId": job_id,
                "title": raw_job["title"],
                "company": raw_job["company"],
                "location": raw_job.get("location", ""),
                "description": raw_job.get("description", ""),
                "url": url,
                "source": raw_job.get("source", "unknown"),
                "datePosted": raw_job.get("date_posted", ""),
                "salary": raw_job.get("salary"),
                "jobType": raw_job.get("job_type", ""),
                "category": None,
                "requiredSkills": [],
                "preferredSkills": [],
                "experienceLevel": None,
                "atsKeywords": [],
                "isAnalyzed": False,
                "isPaid": None,
                "searchTerm": search_term,
                "createdAt": now,
                "updatedAt": now,
            }

            try:
                await dynamo_service.put_item("Jobs", item)
                self._existing_urls.add(url)
                stored_jobs.append(item)
            except Exception as e:
                logger.error("Failed to store job", job_title=raw_job["title"], error=str(e))

        logger.info(
            f"Stored {len(stored_jobs)}/{len(raw_jobs)} scraped jobs",
            search_term=search_term,
        )
        return stored_jobs


# Global instance
job_scraper = JobScraper()
