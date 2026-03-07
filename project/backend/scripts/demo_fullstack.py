"""
demo_fullstack.py  —  scrape "full stack" jobs from Naukri (past 7 days)
No DynamoDB.  Results served at http://localhost:7791/

Run:
    source project/backend/venv/bin/activate
    python project/backend/scripts/demo_fullstack.py
"""

# ── start Xvfb and force X11 (not Wayland) BEFORE playwright loads ───────────
import os, subprocess, time as _t
subprocess.run(["pkill", "-f", "Xvfb :99"], capture_output=True)
_t.sleep(0.3)
_xvfb = subprocess.Popen(
    ["Xvfb", ":99", "-screen", "0", "1280x900x24", "-ac"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
os.environ["DISPLAY"] = ":99"
os.environ.pop("WAYLAND_DISPLAY", None)
os.environ.pop("XDG_SESSION_TYPE", None)
for _i in range(10):
    _t.sleep(0.5)
    if subprocess.run(["xdpyinfo", "-display", ":99"], capture_output=True).returncode == 0:
        break
import atexit; atexit.register(_xvfb.terminate)

import asyncio, http.server, socketserver, threading, time
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright, Response as PwResponse
from playwright_stealth import Stealth

# ── config ──────────────────────────────────────────────────────────────────
KEYWORD    = "full stack developer"
LOCATIONS  = ["chennai", "bengaluru", "mumbai", "hyderabad", "delhi ncr", "pune", "noida"]
JOB_AGE    = 7
OUTPUT     = Path("/tmp/demo_fullstack.html")
PORT       = 7791

# ── URL builder ──────────────────────────────────────────────────────────────
def _url(keyword: str, locs: List[str], age: int, path: str) -> str:
    return (
        f"https://www.naukri.com/{path}?"
        + urlencode({"k": keyword, "l": ", ".join(locs),
                     "nignbevent_src": "jobsearchDeskGNB",
                     "experience": "0", "jobAge": str(age)})
    )

# ── parser ───────────────────────────────────────────────────────────────────
def _parse(raw: dict, path: str) -> Optional[Dict[str, Any]]:
    title = (raw.get("title") or "").strip()
    url   = (raw.get("jdURL") or raw.get("jobUrl") or raw.get("url") or "").strip()
    if not title or not url:
        return None
    if not url.startswith("http"):
        url = "https://www.naukri.com" + url
    company = (raw.get("companyName") or (raw.get("company") or {}).get("name","") or "—").strip()

    loc_parts: List[str] = []
    for ph in raw.get("placeholders") or []:
        if ph.get("type") == "location":
            loc_parts = [x.strip() for x in (ph.get("label") or "").split(",") if x.strip()]
            break
    if not loc_parts:
        rl = raw.get("location") or raw.get("locationText") or "India"
        loc_parts = rl if isinstance(rl, list) else [str(rl)]
    location = ", ".join(loc_parts[:2]) or "India"

    tags  = raw.get("tagsAndSkills") or raw.get("skills") or ""
    skills= ", ".join(tags) if isinstance(tags, list) else str(tags)

    jtype = "Internship" if path == "internship-jobs" else "Full-time"
    return dict(title=title, company=company, location=location,
                skills=skills[:100], type=jtype, url=url)

# ── browser scrape ────────────────────────────────────────────────────────────
async def _scrape_one(keyword: str, locs: List[str], age: int, path: str) -> List[dict]:
    target = _url(keyword, locs, age, path)
    captured: List[dict] = []
    label   = f"[{path}|age={age}d]"
    print(f"  {label}  →  {target[:100]}…")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--ozone-platform=x11",
                  "--disable-blink-features=AutomationControlled",
                  "--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-gpu", "--window-size=1280,900"],
        )
        ctx = await browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"),
            locale="en-IN", timezone_id="Asia/Kolkata",
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()
        await Stealth().apply_stealth_async(page)

        async def _on(resp: PwResponse):
            if "jobapi/v3/search" in resp.url:
                try:
                    data = await resp.json()
                    raw_list = data.get("jobDetails") or []
                    print(f"  {label}  ✓  {len(raw_list)} raw jobs intercepted")
                    captured.extend(raw_list)
                except Exception as e:
                    print(f"  {label}  ✗  parse error: {e}")

        page.on("response", _on)
        try:
            await page.goto("https://www.naukri.com/", wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(2)
            await page.goto(target, wait_until="domcontentloaded", timeout=40_000)
            await asyncio.sleep(6)
            if not captured:
                await page.evaluate("window.scrollTo(0, 600)")
                await asyncio.sleep(4)
        except Exception as e:
            print(f"  {label}  ✗  nav error: {e}")
        finally:
            await browser.close()

    return [j for raw in captured if (j := _parse(raw, path))]

# ── main ──────────────────────────────────────────────────────────────────────
async def run():
    jobs: List[dict] = []
    seen: set         = set()

    for path in ["internship-jobs", "jobs"]:
        batch = await _scrape_one(KEYWORD, LOCATIONS, JOB_AGE, path)
        for j in batch:
            if j["url"] not in seen:
                seen.add(j["url"])
                jobs.append(j)
        await asyncio.sleep(3)

    print(f"\n  Total unique jobs: {len(jobs)}")
    return jobs

# ── HTML ──────────────────────────────────────────────────────────────────────
def _html(jobs: List[dict]) -> str:
    lc = Counter(j["location"] for j in jobs)
    pills = " ".join(
        f'<span style="background:#1e293b;border:1px solid #334155;padding:2px 10px;'
        f'border-radius:12px;font-size:12px">{city} <b style="color:#38bdf8">{n}</b></span>'
        for city, n in sorted(lc.items(), key=lambda x: -x[1])
    )
    rows = ""
    for j in jobs:
        badge = (
            '<span style="background:#0ea5e9;color:#fff;padding:1px 6px;border-radius:4px;font-size:11px">Intern</span>'
            if j["type"] == "Internship" else
            '<span style="background:#8b5cf6;color:#fff;padding:1px 6px;border-radius:4px;font-size:11px">Full-time</span>'
        )
        rows += (
            f'<tr><td><a href="{j["url"]}" target="_blank" '
            f'style="color:#38bdf8;text-decoration:none">{j["title"]}</a></td>'
            f'<td>{j["company"]}</td><td>📍 {j["location"]}</td>'
            f'<td>{badge}</td>'
            f'<td style="font-size:11px;color:#94a3b8">{j["skills"][:70]}</td></tr>'
        )

    return f"""<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8">
<title>Full Stack Jobs — Naukri (7 days)</title>
<style>
* {{box-sizing:border-box;margin:0;padding:0}}
body {{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;padding:32px}}
tr:nth-child(even) td {{background:#0f172a}}
tr:nth-child(odd)  td {{background:#111827}}
td {{padding:9px 12px;border-bottom:1px solid #1e293b;vertical-align:top}}
</style></head>
<body><div style="max-width:1100px;margin:0 auto">
  <h1 style="font-size:22px;font-weight:700;margin-bottom:6px">
    🔍 Full Stack Jobs — Naukri (past {JOB_AGE} days)
  </h1>
  <p style="color:#64748b;margin-bottom:10px">
    Keyword: <b style="color:#f1f5f9">"{KEYWORD}"</b> &nbsp;·&nbsp;
    <b style="color:#38bdf8">{len(jobs)}</b> unique jobs &nbsp;·&nbsp;
    Scraped: {time.strftime("%Y-%m-%d %H:%M")} &nbsp;·&nbsp; invisible browser (Xvfb)
  </p>
  <div style="margin-bottom:20px;display:flex;flex-wrap:wrap;gap:6px">{pills}</div>
  <div style="overflow-x:auto">
  <table style="width:100%;border-collapse:collapse;font-size:13px">
    <thead><tr style="background:#1e293b;color:#94a3b8;
                      text-transform:uppercase;font-size:11px;letter-spacing:.05em">
      <th style="padding:10px 12px;text-align:left">Title</th>
      <th style="padding:10px 12px;text-align:left">Company</th>
      <th style="padding:10px 12px;text-align:left">Location</th>
      <th style="padding:10px 12px;text-align:left">Type</th>
      <th style="padding:10px 12px;text-align:left">Skills</th>
    </tr></thead>
    <tbody>{rows if rows else
      "<tr><td colspan='5' style='padding:20px;color:#475569;text-align:center'>No jobs found</td></tr>"
    }</tbody>
  </table></div>
</div></body></html>"""

# ── HTTP server ───────────────────────────────────────────────────────────────
def _serve(path: Path, port: int):
    data = path.read_bytes()
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type","text/html;charset=utf-8")
            self.end_headers()
            self.wfile.write(data)
        def log_message(self,*a): pass
    try:
        with socketserver.TCPServer(("", port), H) as s:
            s.serve_forever()
    except OSError:
        pass

# ── entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print(f"  Keyword  : {KEYWORD}")
    print(f"  Locations: {', '.join(LOCATIONS)}")
    print(f"  Window   : past {JOB_AGE} days  (internships + full-time)")
    print(f"  Browser  : invisible (Xvfb — no popup)")
    print("=" * 60)

    jobs = asyncio.run(run())

    html = _html(jobs)
    OUTPUT.write_text(html, encoding="utf-8")

    threading.Thread(target=_serve, args=(OUTPUT, PORT), daemon=True).start()
    print(f"\n  → http://localhost:{PORT}/\n  Press Ctrl+C to stop.")

    lc = Counter(j["location"] for j in jobs)
    for loc, n in sorted(lc.items(), key=lambda x: -x[1]):
        print(f"    {loc:<25} {n} jobs")

    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Stopped.")
