"""
Backfill datePosted for LinkedIn jobs that have an empty/None value.

For each LinkedIn job in DynamoDB with a missing datePosted, this script:
  1. Fetches the LinkedIn job page via requests (no auth needed for the
     basic job listing page that returns the <time> tag in the HTML).
  2. Parses the <time class="posted-time-ago__..."> or the
     <span class="posted-time-ago__..."> to find the ISO date in the
     `datetime` attribute.
  3. Writes the ISO date (YYYY-MM-DD) back to DynamoDB.

Usage:
    cd project/backend
    python scripts/backfill_linkedin_dates.py [--dry-run]
"""

import argparse
import asyncio
import re
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
from bs4 import BeautifulSoup
from app.services.dynamo_service import dynamo_service


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Rate limiting: seconds between requests
REQUEST_DELAY = 1.5


def _fetch_li_date(job_url: str) -> str | None:
    """
    Fetch a LinkedIn job page and return YYYY-MM-DD date string, or None.
    Works with the public guest listing page (no login required).
    """
    try:
        resp = requests.get(job_url, headers=HEADERS, timeout=15, allow_redirects=True)
        if resp.status_code != 200:
            print(f"    HTTP {resp.status_code} for {job_url}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # LinkedIn renders the date in various places; try several selectors
        selectors = [
            # job listing card
            {"tag": "time", "attrs": {"class": re.compile(r"job-search-card__listdate")}},
            # job detail page
            {"tag": "span", "attrs": {"class": re.compile(r"posted-time-ago__")}},
            # fallback: any <time> with a datetime attr
        ]

        for sel in selectors:
            el = soup.find(sel["tag"], attrs=sel["attrs"])
            if el and el.get("datetime"):
                raw = el["datetime"].strip()
                # Might be full ISO datetime or just date
                m = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
                if m:
                    return m.group(1)

        # Broader fallback: any <time datetime="YYYY-MM-DD"> on the page
        for time_tag in soup.find_all("time", attrs={"datetime": True}):
            raw = time_tag["datetime"].strip()
            m = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
            if m:
                return m.group(1)

    except Exception as e:
        print(f"    Error fetching {job_url}: {e}")

    return None


async def backfill(dry_run: bool = False):
    print("Scanning Jobs table for LinkedIn entries with empty datePosted …")
    all_jobs = await dynamo_service.scan("Jobs")

    def _is_missing_date(d: str) -> bool:
        """True when the stored value is blank, 'nan', 'none', 'null', or 'NaT'."""
        return not d or d.strip().lower() in ("", "nan", "none", "null", "nat")

    # Filter: LinkedIn source AND datePosted is missing / empty / 'nan'
    targets = [
        j for j in all_jobs
        if j.get("source", "").lower() == "linkedin"
        and _is_missing_date(j.get("datePosted", ""))
    ]

    print(f"Found {len(targets)} LinkedIn jobs with empty datePosted.")
    if not targets:
        return

    updated = 0
    skipped = 0

    for i, job in enumerate(targets, 1):
        job_id = job.get("jobId", "")
        url = job.get("url", "")
        title = job.get("title", "N/A")[:60]

        if not url:
            print(f"[{i}/{len(targets)}] SKIP (no URL): {title}")
            skipped += 1
            continue

        print(f"[{i}/{len(targets)}] Fetching date for: {title}")
        date_str = _fetch_li_date(url)

        if not date_str:
            print(f"    -> Could not determine date, skipping.")
            skipped += 1
            time.sleep(REQUEST_DELAY)
            continue

        print(f"    -> datePosted = {date_str}", end="")

        if dry_run:
            print(" (dry-run, not saved)")
        else:
            try:
                await dynamo_service.update_item(
                    "Jobs",
                    key={"jobId": job_id},
                    updates={"datePosted": date_str},
                )
                updated += 1
                print(" ✓ saved")
            except Exception as e:
                print(f" ERROR: {e}")
                skipped += 1

        time.sleep(REQUEST_DELAY)

    print(f"\nDone. Updated: {updated}, Skipped/failed: {skipped}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill LinkedIn job posted dates")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    asyncio.run(backfill(dry_run=args.dry_run))
