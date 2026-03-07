"""
demo_naukri_full.py
====================
Naukri scrape demo:
  • Search: "software development" (internship + job pages)
  • Time windows: 1 day, 7 days, 30 days
  • Locations: Chennai, Bengaluru, Mumbai, Hyderabad, Delhi/NCR

Run:
    source backend/venv/bin/activate
    python backend/scripts/demo_naukri_full.py

Output → http://localhost:7790/
"""

import asyncio
import http.server
import socketserver
import threading
import time
from pathlib import Path
from urllib.parse import urlencode
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright, Response as PwResponse
from playwright_stealth import Stealth
from pyvirtualdisplay import Display

# ── Config ─────────────────────────────────────────────────────────────────────

SEARCH_KEYWORD = "software development"
LOCATIONS      = ["chennai", "bengaluru", "mumbai", "hyderabad", "delhi ncr"]
TIME_WINDOWS   = [
    (1,  "Last 1 Day"),
    (7,  "Last 7 Days"),
    (30, "Last 1 Month"),
]
OUTPUT_HTML = Path("/tmp/naukri_full_demo.html")
PORT        = 7790

# ── URL builder ────────────────────────────────────────────────────────────────

def build_url(keyword: str, locations: List[str], job_age: int, path: str) -> str:
    params = {
        "k": keyword,
        "l": ", ".join(locations),
        "nignbevent_src": "jobsearchDeskGNB",
        "experience": "0",
        "jobAge": str(job_age),
    }
    return f"https://www.naukri.com/{path}?" + urlencode(params)


# ── Job parser ──────────────────────────────────────────────────────────────────

def parse_job(raw: dict, job_age: int, path: str) -> Optional[Dict[str, Any]]:
    title = (raw.get("title") or "").strip()
    url   = (raw.get("jdURL") or raw.get("jobUrl") or raw.get("url") or "").strip()
    if not title or not url:
        return None
    if not url.startswith("http"):
        url = "https://www.naukri.com" + url

    company = (raw.get("companyName") or (raw.get("company") or {}).get("name", "") or "—").strip()

    loc_parts: List[str] = []
    for ph in raw.get("placeholders") or []:
        if ph.get("type") == "location":
            loc_parts = [x.strip() for x in (ph.get("label") or "").split(",") if x.strip()]
            break
    if not loc_parts:
        rl = raw.get("location") or raw.get("locationText") or "India"
        loc_parts = rl if isinstance(rl, list) else [str(rl)]
    location = ", ".join(loc_parts[:2]) or "India"

    tags = raw.get("tagsAndSkills") or raw.get("skills") or ""
    skills = ", ".join(tags) if isinstance(tags, list) else str(tags)

    job_type = "Internship" if path == "internship-jobs" else "Full-time"

    return {
        "title":    title,
        "company":  company,
        "location": location,
        "skills":   skills[:80],
        "type":     job_type,
        "url":      url,
        "window":   job_age,
    }


# ── Browser scrape ──────────────────────────────────────────────────────────────

async def scrape_one(keyword: str, locations: List[str], job_age: int, path: str) -> List[dict]:
    """Run one browser session and return raw job dicts."""
    url = build_url(keyword, locations, job_age, path)
    captured: List[dict] = []
    label = f"[{path}|{job_age}d]"

    print(f"  {label} → {url[:100]}...")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox",
                  "--disable-dev-shm-usage", "--window-size=1280,900"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        async def on_resp(resp: PwResponse) -> None:
            if "jobapi/v3/search" in resp.url:
                try:
                    data = await resp.json()
                    jobs_raw = data.get("jobDetails") or []
                    print(f"  {label} ✓ intercepted {len(jobs_raw)} raw jobs")
                    captured.extend(jobs_raw)
                except Exception as e:
                    print(f"  {label} ✗ parse error: {e}")

        page.on("response", on_resp)
        try:
            await page.goto("https://www.naukri.com/", wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(2)
            await page.goto(url, wait_until="domcontentloaded", timeout=40_000)
            await asyncio.sleep(6)
            if not captured:
                await page.evaluate("window.scrollTo(0, 600)")
                await asyncio.sleep(4)
        except Exception as e:
            print(f"  {label} ✗ navigation error: {e}")
        finally:
            await browser.close()

    return [j for raw in captured if (j := parse_job(raw, job_age, path))]


# ── Main scrape loop ────────────────────────────────────────────────────────────

async def run_all():
    """Run all time-window × path combos, one at a time."""
    results: Dict[int, List[dict]] = {}  # job_age → jobs

    vdisplay = Display(visible=False, size=(1280, 900))
    vdisplay.start()
    try:
        for job_age, label in TIME_WINDOWS:
            print(f"\n{'='*60}")
            print(f"  Window: {label}  (jobAge={job_age})")
            print(f"{'='*60}")
            window_jobs: List[dict] = []
            seen_urls: set = set()

            for path in ["internship-jobs", "jobs"]:
                jobs = await scrape_one(SEARCH_KEYWORD, LOCATIONS, job_age, path)
                for j in jobs:
                    if j["url"] not in seen_urls:
                        seen_urls.add(j["url"])
                        window_jobs.append(j)
                await asyncio.sleep(3)

            results[job_age] = window_jobs
            print(f"  → {len(window_jobs)} unique jobs for {label}")

    finally:
        vdisplay.stop()

    return results


# ── HTML render ─────────────────────────────────────────────────────────────────

def render_html(results: Dict[int, List[dict]]) -> str:
    total = sum(len(v) for v in results.values())

    sections = ""
    for job_age, label in TIME_WINDOWS:
        jobs = results.get(job_age, [])

        # Location breakdown
        from collections import Counter
        loc_counts = Counter(j["location"] for j in jobs)

        rows = ""
        for j in jobs:
            type_badge = (
                '<span style="background:#0ea5e9;color:#fff;padding:1px 6px;border-radius:4px;font-size:11px">Internship</span>'
                if j["type"] == "Internship" else
                '<span style="background:#8b5cf6;color:#fff;padding:1px 6px;border-radius:4px;font-size:11px">Full-time</span>'
            )
            rows += f"""
            <tr>
              <td><a href="{j['url']}" target="_blank" style="color:#38bdf8;text-decoration:none">{j['title']}</a></td>
              <td>{j['company']}</td>
              <td>📍 {j['location']}</td>
              <td>{type_badge}</td>
              <td style="font-size:11px;color:#94a3b8">{j['skills'][:60]}</td>
            </tr>"""

        loc_pills = " ".join(
            f'<span style="background:#1e293b;border:1px solid #334155;padding:2px 8px;border-radius:12px;font-size:12px">'
            f'{city} <b style="color:#38bdf8">{cnt}</b></span>'
            for city, cnt in sorted(loc_counts.items(), key=lambda x: -x[1])
        )

        sections += f"""
        <div style="margin-bottom:48px">
          <h2 style="color:#f1f5f9;font-size:18px;margin-bottom:4px">{label}</h2>
          <p style="color:#64748b;margin-bottom:12px">{len(jobs)} jobs found</p>
          <div style="margin-bottom:16px;display:flex;flex-wrap:wrap;gap:6px">{loc_pills}</div>
          <div style="overflow-x:auto">
            <table style="width:100%;border-collapse:collapse;font-size:13px">
              <thead>
                <tr style="background:#1e293b;color:#94a3b8;text-transform:uppercase;font-size:11px;letter-spacing:.05em">
                  <th style="padding:10px 12px;text-align:left">Title</th>
                  <th style="padding:10px 12px;text-align:left">Company</th>
                  <th style="padding:10px 12px;text-align:left">Location</th>
                  <th style="padding:10px 12px;text-align:left">Type</th>
                  <th style="padding:10px 12px;text-align:left">Skills</th>
                </tr>
              </thead>
              <tbody style="divide-y:1px solid #1e293b">
                {"" if rows else "<tr><td colspan='5' style='padding:20px;color:#475569;text-align:center'>No jobs found for this window</td></tr>"}
                {rows}
              </tbody>
            </table>
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Naukri Demo — "{SEARCH_KEYWORD}"</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui,sans-serif; background:#0f172a; color:#e2e8f0; padding:32px; }}
    tr:nth-child(even) td {{ background:#0f172a; }}
    tr:nth-child(odd)  td {{ background:#111827; }}
    td {{ padding:9px 12px; border-bottom:1px solid #1e293b; vertical-align:top; }}
  </style>
</head>
<body>
  <div style="max-width:1100px;margin:0 auto">
    <h1 style="font-size:24px;font-weight:700;margin-bottom:4px">
      🔍 Naukri Scrape Demo
    </h1>
    <p style="color:#64748b;margin-bottom:8px">
      Keyword: <b style="color:#f1f5f9">"{SEARCH_KEYWORD}"</b> &nbsp;|&nbsp;
      Locations: <b style="color:#f1f5f9">{", ".join(LOCATIONS)}</b> &nbsp;|&nbsp;
      Total: <b style="color:#38bdf8">{total} jobs</b> across all windows
    </p>
    <p style="color:#475569;font-size:12px;margin-bottom:32px">
      Scraped: {time.strftime("%Y-%m-%d %H:%M:%S")} &nbsp;·&nbsp;
      Sources: internship-jobs page + jobs page &nbsp;·&nbsp;
      Browser: Playwright + Stealth + Xvfb (invisible)
    </p>
    {sections}
  </div>
</body>
</html>"""


# ── HTTP server ─────────────────────────────────────────────────────────────────

def serve(path: Path, port: int):
    content = path.read_bytes()
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content)
        def log_message(self, *a): pass
    try:
        with socketserver.TCPServer(("", port), H) as httpd:
            httpd.serve_forever()
    except OSError:
        pass


# ── Entry point ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Naukri Scrape Demo")
    print(f"  Keyword  : {SEARCH_KEYWORD}")
    print(f"  Locations: {', '.join(LOCATIONS)}")
    print(f"  Windows  : 1d / 7d / 30d   ×   internships + full-time jobs")
    print(f"  Browser  : runs invisibly via Xvfb (no popup)")
    print("=" * 60)

    results = asyncio.run(run_all())

    html = render_html(results)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"\n  HTML saved → {OUTPUT_HTML}")

    t = threading.Thread(target=serve, args=(OUTPUT_HTML, PORT), daemon=True)
    t.start()
    print(f"  Serving  → http://localhost:{PORT}/")
    print("  Press Ctrl+C to stop.\n")

    total = sum(len(v) for v in results.values())
    for job_age, label in TIME_WINDOWS:
        jobs = results.get(job_age, [])
        locs = sorted({j["location"] for j in jobs})
        print(f"  {label:14s}: {len(jobs):3d} jobs  |  locations: {', '.join(locs[:6]) or 'none'}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Stopped.")
