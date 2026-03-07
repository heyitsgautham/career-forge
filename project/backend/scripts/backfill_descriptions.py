"""
Backfill job descriptions for all jobs that have missing/nan descriptions.

Sources handled:
  • LinkedIn  — requests + BeautifulSoup on the public guest job page
  • Unstop    — curl_cffi (Chrome TLS) hitting /api/public/competition/{id}
  • Naukri    — headless=False + Xvfb + playwright_stealth (same as naukri_scraper.py)

To run:
    cd project/backend
    source venv/bin/activate
    pip install curl_cffi   # one-time, if not already installed
    python scripts/backfill_descriptions.py [--dry-run] [--source linkedin|unstop|naukri]
"""

import argparse
import asyncio
import os
import re
import subprocess
import sys
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
from bs4 import BeautifulSoup
try:
    from curl_cffi import requests as cf_requests
    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False
from app.services.dynamo_service import dynamo_service

# ── Sentinel check ─────────────────────────────────────────────────────────────

_EMPTY = {"", "nan", "none", "null", "n/a", "na"}

def _is_empty(val) -> bool:
    return not val or str(val).strip().lower() in _EMPTY


# ── LinkedIn ───────────────────────────────────────────────────────────────────

HEADERS_LINKEDIN = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch_linkedin_description(url: str) -> str | None:
    """Fetch LinkedIn public job page and return plain-text description."""
    try:
        resp = requests.get(url, headers=HEADERS_LINKEDIN, timeout=20, allow_redirects=True)
        if resp.status_code != 200:
            print(f"    LinkedIn HTTP {resp.status_code}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Primary container used by LinkedIn guest view
        for sel in [
            {"class": re.compile(r"show-more-less-html__markup")},
            {"class": re.compile(r"description__text")},
            {"class": re.compile(r"job-description")},
        ]:
            el = soup.find("div", attrs=sel)
            if el:
                text = el.get_text(separator="\n", strip=True)
                if len(text) > 50:
                    return text

        # Fallback: JSON-LD schema
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                d = json.loads(tag.string or "{}")
                desc = d.get("description", "")
                if desc and len(str(desc)) > 50:
                    text = re.sub(r"<[^>]+>", " ", str(desc))
                    return re.sub(r"\s{2,}", " ", text).strip()
            except Exception:
                pass

        return None
    except Exception as e:
        print(f"    LinkedIn fetch error: {e}")
        return None


# ── Unstop ────────────────────────────────────────────────────────────────────

_UNSTOP_ID_RE = re.compile(r"-(\d+)$")

HEADERS_UNSTOP = {
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://unstop.com/",
    "origin": "https://unstop.com",
}


def _fetch_unstop_description(url: str) -> str | None:
    """
    Fetch Unstop job description via /api/public/competition/{id}.
    Uses curl_cffi to impersonate Chrome TLS and bypass bot detection.
    The description lives in data.competition.details (HTML).
    """
    if not _HAS_CURL_CFFI:
        print("    curl_cffi not installed — run: pip install curl_cffi")
        return None

    m = _UNSTOP_ID_RE.search(url.rstrip("/").split("?")[0])
    if not m:
        print(f"    Could not extract ID from URL: {url}")
        return None
    opp_id = m.group(1)

    api_url = f"https://unstop.com/api/public/competition/{opp_id}"
    try:
        r = cf_requests.get(api_url, headers=HEADERS_UNSTOP, impersonate="chrome124", timeout=15)
        if r.status_code != 200:
            print(f"    Unstop API HTTP {r.status_code} for id={opp_id}")
            return None

        comp = r.json().get("data", {}).get("competition", {})

        # "details" is the main HTML description field
        for field in ["details", "description", "about", "eligibility"]:
            raw = comp.get(field)
            if raw and len(str(raw)) > 30:
                text = re.sub(r"<[^>]+>", " ", str(raw))
                text = re.sub(r"\s{2,}", " ", text).strip()
                if len(text) > 30:
                    return text

        # Fallback: build from skills + type
        parts = []
        skills = comp.get("required_skills") or comp.get("skills") or []
        if isinstance(skills, list) and skills:
            labels = [s.get("label", str(s)) if isinstance(s, dict) else str(s) for s in skills]
            parts.append("Skills: " + ", ".join(labels))
        if comp.get("type"):
            parts.append(f"Type: {comp['type']}")
        return "\n".join(parts) if parts else None

    except Exception as e:
        print(f"    Unstop fetch error: {e}")
        return None


# ── Naukri (headless=False + Xvfb + playwright_stealth) ──────────────────────

def _start_xvfb() -> "subprocess.Popen | None":
    """Start Xvfb :99 virtual display on Linux. Returns the Popen handle."""
    if not sys.platform.startswith("linux"):
        return None
    subprocess.run(["pkill", "-f", "Xvfb :99"], capture_output=True)
    time.sleep(0.3)
    proc = subprocess.Popen(
        ["Xvfb", ":99", "-screen", "0", "1280x900x24", "-ac"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    os.environ["DISPLAY"] = ":99"
    os.environ.pop("WAYLAND_DISPLAY", None)
    os.environ.pop("XDG_SESSION_TYPE", None)
    for _ in range(10):
        time.sleep(0.5)
        if subprocess.run(["xdpyinfo", "-display", ":99"], capture_output=True).returncode == 0:
            return proc
    return proc  # still return even if not confirmed


async def _fetch_naukri_descriptions_batch(jobs: list, dry_run: bool) -> dict:
    """
    Use headless=False Chromium + Xvfb + playwright_stealth (same technique as
    naukri_scraper.py) to intercept /jobapi/v4/job/{id} responses.
    Returns dict of {jobId: description}.
    """
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    if dry_run:
        for i, job in enumerate(jobs, 1):
            print(f"  [{i}/{len(jobs)}] {job.get('title','')[:60]}")
            print(f"    DRY-RUN: would visit {job['url']}")
        return {}

    results: dict = {}
    xvfb = _start_xvfb()
    if xvfb:
        print("  Xvfb :99 started")

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=False,
                args=[
                    "--ozone-platform=x11",
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--window-size=1280,900",
                ],
            )
            ctx = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-IN",
                timezone_id="Asia/Kolkata",
                viewport={"width": 1280, "height": 900},
            )
            # One common page reused per job (better cookie/session carryover)
            page = await ctx.new_page()
            await Stealth().apply_stealth_async(page)

            # Warm up on homepage — sets Akamai session cookies
            print("  Warming up on Naukri homepage...")
            await page.goto("https://www.naukri.com/", wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(2)

            for i, job in enumerate(jobs, 1):
                url = job["url"]
                job_id = job["jobId"]
                title = job.get("title", "")[:60]
                print(f"  [{i}/{len(jobs)}] {title}")

                captured: list = []

                async def _on_resp(r, cap=captured):
                    if "jobapi/v4/job/" in r.url and r.status == 200:
                        try:
                            body = await r.json()
                            jd = body.get("jobDetails") or body.get("jobDescription") or body
                            if isinstance(jd, dict):
                                raw = (
                                    jd.get("jobDescription")
                                    or jd.get("description")
                                    or jd.get("jdText")
                                    or ""
                                )
                                if raw and len(str(raw)) > 30:
                                    text = re.sub(r"<[^>]+>", " ", str(raw))
                                    text = re.sub(r"\s{2,}", " ", text).strip()
                                    cap.append(text)
                        except Exception:
                            pass

                page.on("response", _on_resp)

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=40_000)
                    await asyncio.sleep(4)

                    # DOM fallback using Naukri's rendered class names
                    if not captured:
                        for sel in [".dang-inner-html", ".job-desc", "#job-desc", "[class*='description']"]:
                            el = await page.query_selector(sel)
                            if el:
                                text = await el.inner_text()
                                if len(text) > 50:
                                    captured.append(text.strip())
                                    break

                    if captured:
                        results[job_id] = captured[0]
                        print(f"    ✓ {len(captured[0])} chars")
                    else:
                        print(f"    ✗ No description found")

                except Exception as e:
                    print(f"    ✗ Page error: {e}")
                finally:
                    page.remove_listener("response", _on_resp)

                await asyncio.sleep(2)  # polite rate limit

            await browser.close()
    finally:
        if xvfb:
            xvfb.terminate()

    return results


# ── Main backfill ──────────────────────────────────────────────────────────────

async def backfill(dry_run: bool = False, only_source: str = None, limit: int = None):
    print("Scanning DynamoDB Jobs table…")
    jobs = await dynamo_service.scan("Jobs")

    # Filter jobs with empty/nan descriptions
    targets = [
        j for j in jobs
        if _is_empty(j.get("description"))
        and j.get("url")
        and (only_source is None or j.get("source", "").lower() == only_source.lower())
    ]

    by_source = {}
    for j in targets:
        src = j.get("source", "unknown").lower()
        by_source.setdefault(src, []).append(j)

    # Apply per-source limit if requested
    if limit:
        by_source = {src: lst[:limit] for src, lst in by_source.items()}

    total = sum(len(v) for v in by_source.values())

    print(f"Found {total} recoverable jobs:")
    for src, lst in sorted(by_source.items()):
        print(f"  {src}: {len(lst)}")

    if total == 0:
        print("Nothing to do.")
        return

    done = 0
    failed = 0
    now = dynamo_service.now_iso()

    # ── Naukri via Playwright ──────────────────────────────────────────────────
    if "naukri" in by_source:
        naukri_jobs = by_source.pop("naukri")
        print(f"\n── NAUKRI ({len(naukri_jobs)} jobs, Playwright) ──")
        desc_map = await _fetch_naukri_descriptions_batch(naukri_jobs, dry_run)

        if not dry_run:
            for job in naukri_jobs:
                job_id = job["jobId"]
                desc = desc_map.get(job_id)
                if desc:
                    try:
                        await dynamo_service.update_item(
                            "Jobs",
                            {"jobId": job_id},
                            {"description": desc, "updatedAt": now},
                        )
                        done += 1
                    except Exception as e:
                        print(f"    DynamoDB write error for {job_id}: {e}")
                        failed += 1
                else:
                    failed += 1

    # ── LinkedIn + Unstop via requests ─────────────────────────────────────────
    RATE_LIMITS = {"linkedin": 2.5, "unstop": 0.8, "naukri": 0}
    for src, jobs_list in sorted(by_source.items()):
        print(f"\n── {src.upper()} ({len(jobs_list)} jobs) ──")

        for i, job in enumerate(jobs_list, 1):
            url = job["url"]
            job_id = job["jobId"]
            title = job.get("title", "")[:60]
            print(f"  [{i}/{len(jobs_list)}] {title}")

            if dry_run:
                print(f"    DRY-RUN: would fetch {url}")
                continue

            desc = None
            if src == "linkedin":
                desc = _fetch_linkedin_description(url)
            elif src == "unstop":
                desc = _fetch_unstop_description(url)

            if desc and len(desc.strip()) > 20:
                try:
                    await dynamo_service.update_item(
                        "Jobs",
                        {"jobId": job_id},
                        {"description": desc.strip(), "updatedAt": now},
                    )
                    print(f"    ✓ {len(desc)} chars")
                    done += 1
                except Exception as e:
                    print(f"    ✗ DynamoDB write failed: {e}")
                    failed += 1
            else:
                print(f"    ✗ No description retrieved")
                failed += 1

            # Rate limit between requests
            if i < len(jobs_list):
                time.sleep(RATE_LIMITS.get(src, 1.0))

    print(f"\n{'DRY-RUN — ' if dry_run else ''}Done: {done} updated, {failed} failed / {total} total")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill missing job descriptions")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    parser.add_argument("--source", choices=["linkedin", "unstop", "naukri"],
                        help="Only process one source (default: all)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max jobs to process per source (useful for testing)")
    args = parser.parse_args()

    asyncio.run(backfill(dry_run=args.dry_run, only_source=args.source, limit=args.limit))
