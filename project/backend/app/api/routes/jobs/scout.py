"""
Job routes: scout
=================
Job Scout: scraped job matches, stats, scraping triggers and job detail.
"""

import hashlib
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import Depends, HTTPException, Query

from app.api.deps import get_current_user, require_admin
from app.api.routes.jobs.common import (
    _scout_response_from_dynamo,
    _to_str,
    router,
)
from app.schemas.jobs import (
    JobStatsResponse,
    SchedulerStatusResponse,
    ScoutJobResponse,
    ScrapeRequest,
)

# ---------------------------------------------------------------------------
# Job Scout endpoints (M4) — shared jobs, no userId filter
# ---------------------------------------------------------------------------


@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status(
    current_user=Depends(get_current_user),
):
    """Return scheduler state: running, next run time, last scrape info."""
    from app.services.scheduler import get_scheduler_status

    s = get_scheduler_status()
    return SchedulerStatusResponse(
        running=s["running"],
        nextRunTime=s.get("next_run_time"),
        lastScrape=s.get("last_scrape"),
    )


@router.get("/matches", response_model=List[ScoutJobResponse])
async def list_matched_jobs(
    current_user=Depends(get_current_user),
    role: Optional[str] = Query(None, description="Filter by category"),
    min_match: Optional[float] = Query(None, alias="minMatch", description="Minimum match %"),
    sort_by: Optional[str] = Query("date", description="Sort: match, date, company"),
    limit: int = Query(200, le=500),
):
    """List all scraped jobs (shared). Sorted by date by default."""
    from app.services.dynamo_service import dynamo_service

    jobs = await dynamo_service.scan("Jobs")

    # Exclude blacklisted companies
    try:
        blacklisted = await dynamo_service.scan("BlacklistedCompanies")
        bl_names = {b["companyName"].lower() for b in blacklisted}
        jobs = [j for j in jobs if (j.get("company") or "").lower() not in bl_names]
    except Exception:
        pass

    # Apply filters
    if role:
        role_lower = role.lower()
        jobs = [j for j in jobs if role_lower in (j.get("category") or "").lower()]

    if min_match is not None:
        jobs = [j for j in jobs if (j.get("matchScore") or 0) >= min_match]

    # Sort
    if sort_by == "match":
        jobs.sort(key=lambda j: j.get("matchScore") or 0, reverse=True)
    elif sort_by == "company":
        jobs.sort(key=lambda j: (j.get("company") or "").lower())
    else:  # default: date
        jobs.sort(key=lambda j: j.get("createdAt") or j.get("datePosted") or "", reverse=True)

    return [_scout_response_from_dynamo(j) for j in jobs[:limit]]


@router.get("/stats", response_model=JobStatsResponse)
async def get_job_stats(
    current_user=Depends(get_current_user),
):
    """Summary stats: total jobs, new today, last scrape, top categories."""
    from app.services.dynamo_service import dynamo_service
    from app.services.scheduler import get_scheduler_status

    jobs = await dynamo_service.scan("Jobs")

    total = len(jobs)
    analyzed = sum(1 for j in jobs if j.get("isAnalyzed"))

    # New today
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_today = sum(1 for j in jobs if (j.get("createdAt") or "").startswith(today))

    # Average match
    scores = [j.get("matchScore") for j in jobs if j.get("matchScore") is not None]
    avg_match = round(sum(scores) / len(scores), 1) if scores else None

    # Category counts
    cat_counts: dict = {}
    for j in jobs:
        raw_cat = j.get("category") or "Uncategorized"
        cat = _to_str(raw_cat) or "Uncategorized"
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    top_categories = sorted(
        [{"category": k, "count": v} for k, v in cat_counts.items()],
        key=lambda c: c["count"],
        reverse=True,
    )[:5]

    # Match distribution buckets
    dist = {"0-25": 0, "25-50": 0, "50-75": 0, "75-100": 0}
    for s in scores:
        if s < 25:
            dist["0-25"] += 1
        elif s < 50:
            dist["25-50"] += 1
        elif s < 75:
            dist["50-75"] += 1
        else:
            dist["75-100"] += 1

    # Last scrape info
    sched = get_scheduler_status()

    return JobStatsResponse(
        totalJobs=total,
        analyzedJobs=analyzed,
        averageMatch=avg_match,
        topCategories=top_categories,
        matchDistribution=dist,
        newToday=new_today,
        lastScrape=sched.get("last_scrape"),
    )


@router.post("/scout/scrape")
async def trigger_scrape(
    body: ScrapeRequest,
    current_user=Depends(require_admin),
):
    """
    Manually trigger a job scrape run (admin only).

    Sources scraped:
     - LinkedIn + Indeed (via jobspy)  — for the provided `search_term`
     - Naukri, Unstop, Internshala    — when `include_india_sources=true`

    Returns: total_found, new_jobs, duplicates_skipped counters.
    """
    from app.services.dynamo_service import dynamo_service
    from app.services.jd_analyzer import jd_analyzer
    from app.services.job_scraper import job_scraper

    # 1. jobspy scrape for the requested term
    jobspy_jobs = await job_scraper.scrape_and_store(
        search_term=body.search_term,
        location=body.location,
        sites=body.sites,
        results_wanted=body.results_wanted,
    )

    india_new = 0
    if body.include_india_sources:
        # 2. India-specific full scrape (all keywords across Naukri/Unstop/Internshala)
        await job_scraper._load_existing_urls()
        india_raw = await job_scraper.scrape_india_sources(sources=body.india_sources)
        now = dynamo_service.now_iso()
        for raw_job in india_raw:
            url = raw_job.get("url", "")
            if not url or url in job_scraper._existing_urls:
                continue
            job_id = hashlib.md5(url.encode()).hexdigest()
            item = {
                "jobId": job_id,
                "title": raw_job["title"],
                "company": raw_job.get("company", ""),
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
                "searchTerm": "",
                "createdAt": now,
                "updatedAt": now,
            }
            try:
                inserted = await dynamo_service.upsert_job(item)
                job_scraper._existing_urls.add(url)
                if inserted:
                    india_new += 1
            except Exception:
                pass

    # 3. Analyze newly stored jobs
    try:
        all_jobs = await dynamo_service.scan("Jobs")
        unanalyzed = [j for j in all_jobs if not j.get("isAnalyzed")]
        analyzed_count = await jd_analyzer.analyze_and_store(unanalyzed) if unanalyzed else 0
    except Exception:
        analyzed_count = 0

    total_new = len(jobspy_jobs) + india_new
    return {
        "message": "Scrape complete",
        "jobspy_new": len(jobspy_jobs),
        "india_new": india_new,
        "total_new": total_new,
        "analyzed": analyzed_count,
    }


@router.post("/scout/scrape/all")
async def trigger_full_scrape(
    current_user=Depends(require_admin),
):
    """
    Trigger a full scrape run across ALL search queries + ALL India sources.
    Same action as the scheduled hourly cron.
    Returns: total_found, new_jobs, duplicates_skipped.
    """
    from app.services.dynamo_service import dynamo_service
    from app.services.jd_analyzer import jd_analyzer
    from app.services.job_scraper import job_scraper

    result = await job_scraper.scrape_all_queries(include_india_sources=True)

    # Analyze new jobs
    try:
        all_jobs = await dynamo_service.scan("Jobs")
        unanalyzed = [j for j in all_jobs if not j.get("isAnalyzed")]
        analyzed_count = await jd_analyzer.analyze_and_store(unanalyzed) if unanalyzed else 0
    except Exception:
        analyzed_count = 0

    return {
        **result,
        "analyzed": analyzed_count,
        "sources": ["linkedin", "indeed", "naukri", "unstop"],
    }


@router.get("/scout/{job_id}", response_model=ScoutJobResponse)
async def get_scout_job_detail(
    job_id: str,
    current_user=Depends(get_current_user),
):
    """Full job detail for Job Scout (shared — no ownership check)."""
    from app.services.dynamo_service import dynamo_service

    job = await dynamo_service.get_item("Jobs", {"jobId": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _scout_response_from_dynamo(job)


@router.delete("/scout/{job_id}")
async def delete_scout_job(
    job_id: str,
    current_user=Depends(require_admin),
):
    """Delete a scraped job (admin only)."""
    from app.services.dynamo_service import dynamo_service

    job = await dynamo_service.get_item("Jobs", {"jobId": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    await dynamo_service.delete_item("Jobs", {"jobId": job_id})
    return {"message": "Job deleted"}


# ---------------------------------------------------------------------------
# Legacy JD Routes (manual JD management)
# ---------------------------------------------------------------------------
