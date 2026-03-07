"""
demo_naukri_scrape.py  (Playwright-powered)
=============================================
Uses a headless Chromium browser to scrape Naukri.

The browser navigates to the same URL you would open in incognito, executes
Naukri's JavaScript (which generates a valid Nkparam token automatically),
and triggers the real /jobapi/v3/search API call.  We intercept that XHR
response and extract the job JSON.

Run:
    source backend/venv/bin/activate
    python backend/scripts/demo_naukri_scrape.py

Output:
    • /tmp/naukri_demo.html   — pretty HTML table
    • http://localhost:7788/  — served in your browser
"""

import asyncio
import http.server
import re
import socketserver
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from playwright.async_api import async_playwright, Response as PwResponse
from playwright_stealth import Stealth

# ── Config ────────────────────────────────────────────────────────────────────

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

METRO_CITIES = ["chennai", "bengaluru", "mumbai", "hyderabad", "pune", "noida"]
JOB_AGE_DAYS  = 7
PORT          = 7788
OUTPUT_PATH   = Path("/tmp/naukri_demo.html")

# ── Role expansion ────────────────────────────────────────────────────────────

def expand_roles(queries: List[str]) -> List[str]:
    roles, seen = [], set()
    for q in queries:
        role_names = re.findall(r'"([^"]+)"', q)
        suffix_m = re.search(r'\)\s+(\w+)\s*$', q)
        suffix = suffix_m.group(1).lower() if suffix_m else ""
        for r in role_names:
            kw = r.strip() if (suffix and r.lower().endswith(suffix)) else \
                 f"{r} {suffix}".strip() if suffix else r.strip()
            if kw.lower() not in seen:
                seen.add(kw.lower())
                roles.append(kw)
    return roles


ROLES = expand_roles(SEARCH_QUERIES)


# ── URL builder ───────────────────────────────────────────────────────────────

def build_url(roles: List[str], locations: List[str]) -> str:
    params = {
        "k": ", ".join(roles),
        "l": ", ".join(locations),
        "nignbevent_src": "jobsearchDeskGNB",
        "experience": "0",
        "jobAge": str(JOB_AGE_DAYS),
    }
    return "https://www.naukri.com/internship-jobs?" + urlencode(params)


# ── Job parser ────────────────────────────────────────────────────────────────

def parse_job(raw: dict) -> Optional[Dict[str, Any]]:
    title = (raw.get("title") or "").strip()
    href  = (raw.get("jdURL") or raw.get("jobUrl") or raw.get("url") or "").strip()
    if not title or not href:
        return None
    if not href.startswith("http"):
        href = "https://www.naukri.com" + href

    company = (
        raw.get("companyName") or
        (raw.get("company") or {}).get("name", "") or "Unknown"
    ).strip()

    loc_parts: List[str] = []
    for ph in raw.get("placeholders") or []:
        if ph.get("type") == "location":
            loc_parts = [x.strip() for x in (ph.get("label") or "").split(",") if x.strip()]
            break
    if not loc_parts:
        rl = raw.get("location") or raw.get("locationText") or "India"
        loc_parts = rl if isinstance(rl, list) else [str(rl)]
    location = ", ".join(loc_parts[:2]) or "India"

    salary = (raw.get("salary") or "").strip() or "—"
    tags = raw.get("tagsAndSkills") or raw.get("skills") or ""
    skills = ", ".join(tags) if isinstance(tags, list) else str(tags)

    date_posted = ""
    for ph in raw.get("placeholders") or []:
        if ph.get("type") in ("date", "posted"):
            date_posted = ph.get("label") or ""
            break
    if not date_posted:
        date_posted = str(raw.get("createdDate") or "")

    return {
        "title": title, "company": company, "location": location,
        "skills": skills, "salary": salary,
        "url": href, "date_posted": date_posted,
    }


# ── Playwright scraper ────────────────────────────────────────────────────────

async def scrape_naukri(locations: List[str]) -> List[Dict[str, Any]]:
    """Navigate to Naukri search page in stealth Chromium and intercept the API JSON."""
    url = build_url(ROLES, locations)
    captured: List[dict] = []

    print(f"\n  Browser → {url[:110]}...")
    print("  Waiting for Naukri to load and trigger /jobapi/v3/search ...")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,   # full Chromium — headless-shell gets 403 from Naukri CDN
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1280,900",
                "--start-maximized",
            ],
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

        # Apply full stealth patches (removes webdriver traces, fakes plugins, etc.)
        await Stealth().apply_stealth_async(page)

        async def on_response(resp: PwResponse) -> None:
            rurl = resp.url
            if "naukri.com" in rurl:
                print(f"    [net] {resp.status} {rurl[:90]}")
            if "jobapi/v3/search" in rurl:
                try:
                    data = await resp.json()
                    jobs_raw = data.get("jobDetails") or []
                    print(f"  ✓ Intercepted /jobapi/v3/search  →  {len(jobs_raw)} raw jobs")
                    captured.extend(jobs_raw)
                except Exception as e:
                    print(f"  ✗ Parse error on API response: {e}")

        page.on("response", on_response)

        try:
            # Step 1: warm-up homepage to get session cookies
            print("  Step 1/2: loading homepage for session cookies...")
            await page.goto("https://www.naukri.com/", wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(2)
            print(f"  Homepage title: {await page.title()!r}")

            # Step 2: navigate to search URL
            print("  Step 2/2: loading search results page...")
            await page.goto(url, wait_until="domcontentloaded", timeout=40_000)
            print(f"  Search page title: {await page.title()!r}")

            # Wait for lazy API call to fire
            await asyncio.sleep(6)

            # Scroll to trigger any lazy-loaded cards
            if not captured:
                print("  No results yet — scrolling to trigger lazy load...")
                await page.evaluate("window.scrollTo(0, 600)")
                await asyncio.sleep(4)

        except Exception as e:
            print(f"  ✗ Navigation error: {e}")
        finally:
            await browser.close()

    parsed = [j for raw in captured if (j := parse_job(raw))]
    return parsed


# ── HTML renderer ─────────────────────────────────────────────────────────────

def render_html(jobs: List[Dict[str, Any]], elapsed: float) -> str:
    rows = ""
    for j in jobs:
        rows += f"""
        <tr>
          <td><a href="{j['url']}" target="_blank">{j['title']}</a></td>
          <td>{j['company']}</td>
          <td>{j['location']}</td>
          <td><small>{j['skills'][:80]}</small></td>
          <td>{j['salary']}</td>
          <td>{j['date_posted']}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Career Forge · Naukri Demo ({len(jobs)} jobs)</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background:#0f172a; color:#e2e8f0; padding:2rem; }}
    h1   {{ color:#38bdf8; margin-bottom:.25rem; }}
    p.meta {{ color:#94a3b8; font-size:.85rem; margin-bottom:1.5rem; }}
    table {{ width:100%; border-collapse:collapse; font-size:.85rem; }}
    th   {{ background:#1e293b; color:#7dd3fc; padding:.6rem .9rem; text-align:left; }}
    td   {{ padding:.5rem .9rem; border-bottom:1px solid #1e293b; vertical-align:top; }}
    tr:hover td {{ background:#1e293b; }}
    a    {{ color:#38bdf8; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
  </style>
</head>
<body>
  <h1>🔍 Career Forge · Naukri Internships</h1>
  <p class="meta">
    {len(jobs)} jobs · {len(ROLES)} role keywords · cities: {", ".join(METRO_CITIES)} ·
    jobAge={JOB_AGE_DAYS}d · scraped in {elapsed:.1f}s · powered by Playwright
  </p>
  <table>
    <thead>
      <tr>
        <th>Title</th><th>Company</th><th>Location</th>
        <th>Skills</th><th>Salary</th><th>Posted</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>"""


# ── HTTP mini-server ──────────────────────────────────────────────────────────

class _Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        content = OUTPUT_PATH.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *_): pass


def _serve():
    with socketserver.TCPServer(("", PORT), _Handler) as httpd:
        httpd.serve_forever()


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("  Career Forge — Naukri Scrape  (Playwright)")
    print("=" * 60)
    print(f"  Roles    : {len(ROLES)} keywords")
    print(f"  Cities   : {', '.join(METRO_CITIES)}")
    print(f"  Job age  : {JOB_AGE_DAYS} days")

    t0 = time.time()
    jobs = await scrape_naukri(METRO_CITIES)
    elapsed = time.time() - t0

    print(f"\n  Total jobs parsed: {len(jobs)}")

    if not jobs:
        print("\n  ⚠  0 results — check browser/network logs above.")
        sys.exit(1)

    # Write HTML
    html = render_html(jobs, elapsed)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"\n  HTML saved → {OUTPUT_PATH}")

    # Start server
    threading.Thread(target=_serve, daemon=True).start()
    print(f"  Serving  → http://localhost:{PORT}/")
    print("  Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Bye!")


if __name__ == "__main__":
    asyncio.run(main())
