"""Full LinkedIn profile scraper: summary, contact info, education and certifications."""

import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
from typing import Dict

from app.services.linkedin_common import _get_chrome_user_data_dir
from app.services.linkedin_profile_js import (
    JS_CONTACT,
    JS_EDUCATION,
    JS_LIST_ITEMS,
    JS_PERSONAL,
    JS_SUMMARY,
)

logger = logging.getLogger(__name__)


def _run_playwright_profile_script(profile_url: str) -> str:
    """
    Run Playwright in a separate process to scrape a full LinkedIn profile.

    Navigates to the main profile, contact-info overlay, /details/education/,
    and /details/certifications/.  Returns a JSON string containing:
      summary, website, email, phone, linkedin_url, education[], certifications[]
    """
    base_url = profile_url.rstrip("/")
    edu_url = f"{base_url}/details/education/"
    certs_url = f"{base_url}/details/certifications/"
    contact_url = f"{base_url}/overlay/contact-info/"
    chrome_user_data = _get_chrome_user_data_dir() or ""

    script = f"""
import sys, io, os, json, time
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

profile_url  = {profile_url!r}
edu_url      = {edu_url!r}
certs_url    = {certs_url!r}
contact_url  = {contact_url!r}
chrome_user_data = {chrome_user_data!r}
fallback_data_dir = os.path.join(os.path.expanduser("~"), ".linkedin_playwright_data")
os.makedirs(fallback_data_dir, exist_ok=True)

def is_login_page(url):
    return any(x in url.lower() for x in ["login","authwall","checkpoint","uas/login","signin","session"])

def check_logged_in(page):
    page.goto("https://www.linkedin.com/feed", timeout=30000, wait_until="domcontentloaded")
    time.sleep(2)
    url = page.evaluate("() => window.location.href")
    return not is_login_page(url) and any(k in url for k in ["feed","/in/","mynetwork"])

# ── JS helpers for DOM extraction (see app/services/linkedin_profile_js.py) ──
JS_PERSONAL = {JS_PERSONAL!r}
JS_SUMMARY = {JS_SUMMARY!r}
JS_CONTACT = {JS_CONTACT!r}
JS_LIST_ITEMS = {JS_LIST_ITEMS!r}
JS_EDUCATION = {JS_EDUCATION!r}

def scrape_section(page, url, js_extractor, wait=2):
    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    time.sleep(wait)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except:
        pass
    time.sleep(1)
    for _ in range(4):
        page.evaluate("window.scrollBy(0, 500)")
        time.sleep(0.4)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(1)
    return page.evaluate(js_extractor)

def parse_cert_items(raw):
    import re
    result = []
    for entry in raw:
        spans = entry.get("spans", [])
        if not spans:
            continue
        cert = {{"name": spans[0]}}
        if len(spans) > 1:
            cert["issuer"] = spans[1]
        for s in spans:
            if "Issued" in s or re.search(r"[A-Z][a-z]+ \\d{{4}}", s):
                cert["date"] = s.replace("Issued","").strip(); break
        for s in spans:
            if "Credential ID" in s:
                cert["credential_id"] = s.replace("Credential ID","").strip(); break
        if entry.get("url"):
            cert["url"] = entry["url"]
        result.append(cert)
    return result

def run_scrape(page):
    data = {{}}

    # ── 1. Main profile: personal details + summary ───────────────────────
    sys.stderr.write("Scraping main profile...\\n")
    page.goto(profile_url, timeout=60000, wait_until="domcontentloaded")
    time.sleep(3)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except:
        pass
    for _ in range(4):
        page.evaluate("window.scrollBy(0, 600)")
        time.sleep(0.4)
    personal = page.evaluate(JS_PERSONAL)
    sys.stderr.write(f"Personal: {{personal}}\\n")
    data.update(personal)
    data["summary"] = page.evaluate(JS_SUMMARY)

    # ── 2. Contact info overlay ───────────────────────────────────────────
    sys.stderr.write("Scraping contact info...\\n")
    try:
        page.goto(contact_url, timeout=30000, wait_until="domcontentloaded")
        time.sleep(3)
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except OSError:
            pass
        contact = page.evaluate(JS_CONTACT)
        sys.stderr.write(f"Contact: {{contact}}\\n")
        data.update(contact)
    except Exception as e:
        sys.stderr.write(f"Contact scrape failed (ignored): {{e}}\\n")

    # ── 3. Education ──────────────────────────────────────────────────────
    sys.stderr.write("Scraping education...\\n")
    try:
        data["education"] = scrape_section(page, edu_url, JS_EDUCATION)
        sys.stderr.write(f"Education: {{data['education']}}\\n")
    except Exception as e:
        sys.stderr.write(f"Education scrape failed (ignored): {{e}}\\n")
        data["education"] = []

    # ── 4. Certifications ─────────────────────────────────────────────────
    sys.stderr.write("Scraping certifications...\\n")
    try:
        raw_certs = scrape_section(page, certs_url, JS_LIST_ITEMS)
        data["certifications"] = parse_cert_items(raw_certs)
    except Exception as e:
        sys.stderr.write(f"Cert scrape failed (ignored): {{e}}\\n")
        data["certifications"] = []

    return data

try:
    with sync_playwright() as p:
        page_obj = None
        context  = None

        # Strategy 1: real Chrome profile (headless, already logged in)
        if chrome_user_data and os.path.isdir(chrome_user_data):
            sys.stderr.write("Trying real Chrome profile (headless)...\\n")
            try:
                context = p.chromium.launch_persistent_context(
                    chrome_user_data, channel="chrome", headless=True,
                    args=["--profile-directory=Default","--no-first-run",
                          "--no-default-browser-check",
                          "--disable-blink-features=AutomationControlled"],
                    viewport={{"width": 1280, "height": 900}},
                )
                page_obj = context.new_page()
                if check_logged_in(page_obj):
                    sys.stderr.write("Chrome profile – logged in headlessly\\n")
                else:
                    sys.stderr.write("Chrome profile not logged in, trying fallback...\\n")
                    context.close(); context = None; page_obj = None
            except Exception as e:
                sys.stderr.write(f"Chrome profile failed ({{e}}), trying fallback...\\n")
                if context:
                    try: context.close()
                    except: pass
                context = None; page_obj = None

        # Strategy 2: Playwright persistent Chromium
        if page_obj is None:
            sys.stderr.write("Using Playwright persistent profile...\\n")
            context = p.chromium.launch_persistent_context(
                fallback_data_dir, headless=True,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={{"width": 1280, "height": 900}},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            )
            page_obj = context.new_page()
            if not check_logged_in(page_obj):
                context.close()
                sys.stderr.write("No saved session. Opening browser for one-time login...\\n")
                context = p.chromium.launch_persistent_context(
                    fallback_data_dir, headless=False,
                    args=["--start-maximized","--disable-blink-features=AutomationControlled"],
                    slow_mo=100, viewport={{"width": 1920, "height": 1080}},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                )
                page_obj = context.new_page()
                page_obj.goto("https://www.linkedin.com/login", timeout=60000, wait_until="domcontentloaded")
                time.sleep(3)

                actual_url = page_obj.evaluate("() => window.location.href")
                if is_login_page(actual_url):
                    sys.stderr.write("\\n" + "="*60 + "\\n")
                    sys.stderr.write("PLEASE LOG IN TO LINKEDIN IN THE BROWSER WINDOW\\n")
                    sys.stderr.write("Session will be saved for all future headless calls.\\n")
                    sys.stderr.write("="*60 + "\\n\\n")
                    max_wait, waited, logged_in = 300, 0, False
                    while waited < max_wait:
                        time.sleep(3); waited += 3
                        try:
                            cur = page_obj.evaluate("() => window.location.href")
                            if any(k in cur for k in ["feed","mynetwork","messaging","jobs"]):
                                logged_in = True; break
                            if "/in/" in cur and "login" not in cur:
                                logged_in = True; break
                        except OSError:
                            pass
                    if not logged_in:
                        context.close()
                        raise Exception("Login timeout — please try again")
                sys.stderr.write("Logged in!\\n")

        result = run_scrape(page_obj)
        context.close()
        sys.stderr.write(f"Done. Keys: {{list(result.keys())}}\\n")
        print(json.dumps(result, ensure_ascii=False))

except Exception as e:
    sys.stderr.write(f"Fatal error: {{str(e)}}\\n")
    import traceback; traceback.print_exc(file=sys.stderr)
    sys.exit(1)
"""

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(script)
            script_path = f.name

        logger.info(f"Running LinkedIn profile script for: {profile_url}")
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=480,
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode != 0:
            raise Exception(f"Profile script failed: {result.stderr or 'Unknown error'}")

        if not result.stdout or len(result.stdout) < 5:
            raise Exception("Empty output from profile script")

        return result.stdout.strip()
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


async def scrape_linkedin_profile(profile_url: str) -> Dict:
    """
    Scrape a full LinkedIn profile, extracting:
      - summary (About section)
      - website, email, phone (from contact info overlay)
      - education list
      - certifications list

    Args:
        profile_url: LinkedIn profile URL (e.g. https://www.linkedin.com/in/username/)

    Returns:
        dict with keys: summary, website, email, phone, linkedin_url, education, certifications
    """
    try:
        loop = asyncio.get_event_loop()
        raw_json = await loop.run_in_executor(None, _run_playwright_profile_script, profile_url)
        data = json.loads(raw_json)
        logger.info(f"Profile scrape complete: {list(data.keys())}")
        return data
    except Exception as e:
        import traceback

        logger.error(f"Error scraping LinkedIn profile: {e}\n{traceback.format_exc()}")
        raise Exception(f"LinkedIn profile scraping failed: {str(e)}") from e
