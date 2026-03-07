"""
Naukri Job Scraper  (Playwright-powered)
=========================================
Uses a headless Chromium browser to navigate Naukri search pages.
The browser generates a valid Nkparam token automatically, then makes
the real /jobapi/v3/search call.  We intercept that XHR response and
extract the job JSON — no token reverse-engineering needed.

Search URL pattern (same as incognito mode):
    https://www.naukri.com/internship-jobs?
        k=Software Engineer intern, Machine Learning intern, ...
        l=chennai, bengaluru, mumbai, hyderabad, pune
        experience=0
        jobAge=7

One browser session per location batch (all roles in one k= param).
"""

import asyncio
import os
import platform
import re
import subprocess
import sys
import time as _time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from playwright.async_api import async_playwright, Response as PwResponse
from playwright_stealth import Stealth
import structlog

logger = structlog.get_logger()

# ── Target locations ──────────────────────────────────────────────────────────

NAUKRI_METRO_CITIES = ["chennai", "bengaluru", "mumbai", "hyderabad", "pune", "noida"]

# ── Role expansion: same SEARCH_QUERIES → flat keyword list ──────────────────

def _expand_roles(queries: List[str]) -> List[str]:
    """
    Split boolean-OR queries into individual role strings.
    E.g. '("Software Engineer" OR "SDE") Intern' → ["Software Engineer intern", "SDE intern"]
    Handles 'Research Intern' so the suffix isn't doubled.
    """
    roles: List[str] = []
    seen: set = set()
    for q in queries:
        role_names = re.findall(r'"([^"]+)"', q)
        suffix_match = re.search(r'\)\s+(\w+)\s*$', q)
        suffix = suffix_match.group(1).lower() if suffix_match else ""
        for role in role_names:
            if suffix and role.lower().endswith(suffix):
                kw = role.strip()
            elif suffix:
                kw = f"{role} {suffix}".strip()
            else:
                kw = role.strip()
            if kw.lower() not in seen:
                seen.add(kw.lower())
                roles.append(kw)
    return roles


_ROLE_LIST: Optional[List[str]] = None


def _get_role_list() -> List[str]:
    """Lazy-load the expanded role list from SEARCH_QUERIES (avoids circular import)."""
    global _ROLE_LIST
    if _ROLE_LIST is None:
        from app.services.job_scraper import SEARCH_QUERIES
        _ROLE_LIST = _expand_roles(SEARCH_QUERIES)
        logger.info(f"Naukri: {len(_ROLE_LIST)} expanded roles ready")
    return _ROLE_LIST


# ── URL builder ───────────────────────────────────────────────────────────────

def build_naukri_url(
    roles: List[str],
    locations: List[str],
    job_age: int = 7,
    path: str = "internship-jobs",
) -> str:
    """
    Build the exact search URL Naukri uses in the browser.
    path: 'internship-jobs' (default) or 'jobs' for full-time roles.
    """
    params = {
        "k": ", ".join(roles),
        "l": ", ".join(locations),
        "nignbevent_src": "jobsearchDeskGNB",
        "experience": "0",
        "jobAge": str(job_age),
    }
    return f"https://www.naukri.com/{path}?" + urlencode(params)


# ── Job parser ────────────────────────────────────────────────────────────────

def _parse_naukri_job(raw: dict) -> Optional[Dict[str, Any]]:
    """Parse a single Naukri job dict from the /jobapi/v3/search JSON response."""
    title = (raw.get("title") or "").strip()
    url = (raw.get("jdURL") or raw.get("jobUrl") or raw.get("url") or "").strip()
    if not title or not url:
        return None
    if not url.startswith("http"):
        url = "https://www.naukri.com" + url

    company = (
        raw.get("companyName")
        or (raw.get("company") or {}).get("name", "")
        or ""
    ).strip() or "Unknown"

    # Location from placeholders array or direct field
    loc_parts: List[str] = []
    for ph in raw.get("placeholders") or []:
        if ph.get("type") == "location":
            loc_parts = [lo.strip() for lo in (ph.get("label") or "").split(",") if lo.strip()]
            break
    if not loc_parts:
        raw_loc = raw.get("location") or raw.get("locationText") or "India"
        loc_parts = raw_loc if isinstance(raw_loc, list) else [str(raw_loc)]
    location = ", ".join(loc_parts[:2])

    salary = (raw.get("salary") or "").strip() or None

    # Full JD text/HTML from the search result (Naukri includes this in search API)
    jd_html = (
        raw.get("jobDescription")
        or raw.get("jobDesc")
        or raw.get("jdText")
        or ""
    ).strip()
    # Strip HTML tags for plain text storage
    import re as _re
    jd_text = _re.sub(r"<[^>]+>", " ", jd_html).strip() if jd_html else ""
    # Fall back to skill tags if no JD text
    tags = raw.get("tagsAndSkills") or raw.get("skills") or []
    tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
    description = jd_text if jd_text else tags_str

    date_posted = ""
    for ph in raw.get("placeholders") or []:
        if ph.get("type") in ("date", "posted"):
            date_posted = ph.get("label") or ""
            break
    if not date_posted:
        date_posted = str(raw.get("createdDate") or "")

    return {
        "title": title,
        "company": company,
        "location": location or "India",
        "description": description,
        "url": url,
        "source": "naukri",
        "date_posted": date_posted,
        "salary": salary,
        "job_type": "Internship" if "intern" in title.lower() else "Full-time",
    }


# ── Playwright fetch + intercept ──────────────────────────────────────────────

async def _fetch_jobs_via_browser(
    url: str,
    timeout_ms: int = 40_000,
) -> List[dict]:
    """
    Launch headed Chromium with stealth patches, warm up on the Naukri homepage
    (to acquire session cookies and pass the CDN WAF), then navigate to the
    search URL and intercept the /jobapi/v3/search XHR response.

    headless=True is blocked by Naukri's Akamai CDN (403); headless=False
    passes because it shares the real Chromium TLS fingerprint.
    Browser runs inside a PyVirtualDisplay (Xvfb) so no window appears on screen.
    """
    captured: List[dict] = []
    _is_linux = sys.platform.startswith("linux")

    # ── Virtual display setup (Linux-only) ───────────────────────────────────
    # On Linux (including Wayland sessions), we start an Xvfb virtual
    # framebuffer and force Chromium to use X11 so no window appears.
    # On macOS / Windows, Selenium-style virtual displays aren't available
    # without Docker — headless=False will briefly flash a window, which is
    # acceptable for local dev.  Production deployments should use Docker.
    xvfb_proc = None
    if _is_linux:
        subprocess.run(["pkill", "-f", "Xvfb :99"], capture_output=True)
        _time.sleep(0.3)
        xvfb_proc = subprocess.Popen(
            ["Xvfb", ":99", "-screen", "0", "1280x900x24", "-ac"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        os.environ["DISPLAY"] = ":99"
        os.environ.pop("WAYLAND_DISPLAY", None)   # prevent Chromium Wayland fallback
        os.environ.pop("XDG_SESSION_TYPE", None)
        # Wait for Xvfb to be ready (up to 5 s)
        for _attempt in range(10):
            _time.sleep(0.5)
            if subprocess.run(["xdpyinfo", "-display", ":99"], capture_output=True).returncode == 0:
                logger.debug("Xvfb :99 ready", attempt=_attempt)
                break
        else:
            logger.warning("Xvfb :99 did not become ready in time — window may appear")
    else:
        _os_name = platform.system()   # 'Darwin' or 'Windows'
        logger.info(
            f"Naukri: running on {_os_name} — Xvfb not available. "
            "Browser window may briefly appear. Use Docker for invisible operation."
        )

    # Chromium launch args — only include X11 flag on Linux
    _chromium_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--window-size=1280,900",
    ]
    if _is_linux:
        _chromium_args.insert(0, "--ozone-platform=x11")  # force X11, ignore Wayland

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=False,
                args=_chromium_args,
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-IN",
                timezone_id="Asia/Kolkata",
                viewport={"width": 1280, "height": 900},
                java_script_enabled=True,
            )
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)

            async def _on_response(response: PwResponse) -> None:
                if "jobapi/v3/search" in response.url:
                    try:
                        data = await response.json()
                        jobs_raw = data.get("jobDetails") or []
                        if jobs_raw:
                            logger.info(
                                "Naukri API intercepted",
                                jobs=len(jobs_raw),
                                url=response.url[:120],
                            )
                            captured.extend(jobs_raw)
                    except Exception as exc:
                        logger.warning(f"Naukri response parse error: {exc}")

            page.on("response", _on_response)

            try:
                # Warm up: homepage sets session cookies that pass CDN checks
                logger.info("Naukri: loading homepage for session cookies")
                await page.goto(
                    "https://www.naukri.com/",
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )
                await asyncio.sleep(2)

                logger.info("Naukri Playwright navigating", url=url[:120])
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                await asyncio.sleep(6)   # let lazy API call fire

                if not captured:
                    logger.debug("Naukri: no results yet, scrolling to trigger lazy load")
                    await page.evaluate("window.scrollTo(0, 600)")
                    await asyncio.sleep(4)

            except Exception as exc:
                logger.warning(f"Naukri page.goto error: {exc}")
            finally:
                await browser.close()
    finally:
        if xvfb_proc is not None:
            try:
                xvfb_proc.terminate()
            except Exception:
                pass

    return captured


# ── Scraper class ─────────────────────────────────────────────────────────────

class NaukriScraper:
    """
    Scrapes Naukri.com using a headless Chromium browser.

    One browser session per city-batch:
    - All role keywords sent as a single comma-separated k= param
    - Browser executes Naukri JS → generates real Nkparam → triggers API call
    - We intercept the /jobapi/v3/search XHR response
    - Parse + return structured job dicts
    """

    def __init__(self, job_age: int = 7):
        self._job_age = job_age

    async def scrape_location_batch(
        self,
        locations: List[str],
        job_age: Optional[int] = None,
        path: str = "internship-jobs",
    ) -> List[Dict[str, Any]]:
        """One browser session: all roles × given cities → parsed jobs."""
        roles = _get_role_list()
        url = build_naukri_url(roles, locations, job_age=job_age or self._job_age, path=path)
        raw_jobs = await _fetch_jobs_via_browser(url)
        parsed = [j for raw in raw_jobs if (j := _parse_naukri_job(raw))]
        logger.info(f"Naukri batch {locations} ({path}): {len(parsed)} jobs")
        return parsed

    async def scrape_all(self) -> List[Dict[str, Any]]:
        """Scrape internships + full-time jobs across metro cities, deduplicated."""
        seen: set = set()
        all_jobs: List[Dict[str, Any]] = []

        # Scrape both internship and full-time job pages
        for path in ["internship-jobs", "jobs"]:
            for batch_name, batch in [
                ("metro", NAUKRI_METRO_CITIES),
                ("india-wide", ["india"]),
            ]:
                logger.info(f"Naukri batch: {batch_name} ({path})")
                jobs = await self.scrape_location_batch(batch, path=path)
                for job in jobs:
                    key = job.get("url", "")
                    if key and key not in seen:
                        seen.add(key)
                        all_jobs.append(job)
                await asyncio.sleep(2)

        logger.info(f"Naukri total: {len(all_jobs)} unique jobs")
        return all_jobs

    def scrape(self, location: str = "india") -> List[Dict[str, Any]]:
        """Sync wrapper for use outside an async context."""
        return asyncio.run(self.scrape_location_batch([location]))


# ── Global instance ───────────────────────────────────────────────────────────

# job_age=1: scheduler runs every 24 h — only fetch last 1 day from Naukri API
naukri_scraper = NaukriScraper(job_age=1)
