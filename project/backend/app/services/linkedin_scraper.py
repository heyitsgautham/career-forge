"""LinkedIn profile scraper for extracting certifications."""
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import re
import logging
import asyncio
import subprocess
import sys
import json
import tempfile
import os
import platform

logger = logging.getLogger(__name__)


def _get_chrome_user_data_dir() -> Optional[str]:
    """Return the path to Chrome's user data directory on this OS."""
    system = platform.system()
    if system == "Darwin":
        path = os.path.expanduser("~/Library/Application Support/Google/Chrome")
    elif system == "Linux":
        path = os.path.expanduser("~/.config/google-chrome")
    elif system == "Windows":
        path = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    else:
        return None
    return path if os.path.isdir(path) else None


def _run_playwright_script(profile_url: str) -> str:
    """
    Run Playwright in a separate process.

    Strategy (in order):
    1. Use the real Chrome profile (headless) — already logged in to LinkedIn,
       no browser window at all. Requires Chrome to not be running (profile lock).
    2. If Chrome is running (profile locked), fall back to the Playwright-managed
       persistent session (~/.linkedin_playwright_data). After the first login in
       that browser, all future calls also run headlessly with no visible window.
    """
    base_url = profile_url.rstrip('/')
    certs_url = f"{base_url}/details/certifications/"
    chrome_user_data = _get_chrome_user_data_dir() or ""

    script = f'''
import sys
import io
import os
from playwright.sync_api import sync_playwright
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

profile_url = "{profile_url}"
certs_url = "{certs_url}"
chrome_user_data = r"{chrome_user_data}"

# Fallback persistent dir for Playwright's own Chromium
fallback_data_dir = os.path.join(os.path.expanduser("~"), ".linkedin_playwright_data")
os.makedirs(fallback_data_dir, exist_ok=True)

def is_login_page(url):
    indicators = ["login", "authwall", "checkpoint", "uas/login", "signin", "session"]
    return any(i in url.lower() for i in indicators)

def scrape_certs_page(page):
    page.goto(certs_url, timeout=60000, wait_until="domcontentloaded")
    time.sleep(3)
    current_url = page.evaluate("() => window.location.href")
    if "certifications" not in current_url and "licenses" not in current_url:
        alt_url = profile_url.rstrip("/") + "/details/licenses-and-certifications/"
        sys.stderr.write(f"Trying alt URL: {{alt_url}}\\n")
        page.goto(alt_url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(3)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except:
        pass
    time.sleep(2)
    for _ in range(5):
        page.evaluate("window.scrollBy(0, 400)")
        time.sleep(0.5)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(2)
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(1)
    return page.content()

def check_logged_in(page):
    page.goto("https://www.linkedin.com/feed", timeout=30000, wait_until="domcontentloaded")
    time.sleep(2)
    url = page.evaluate("() => window.location.href")
    return not is_login_page(url) and any(k in url for k in ["feed", "/in/", "mynetwork"])

try:
    with sync_playwright() as p:
        html = None

        # ── Strategy 1: real Chrome profile (no login needed, headless) ──
        if chrome_user_data and os.path.isdir(chrome_user_data):
            sys.stderr.write("Trying real Chrome profile (headless)...\\n")
            try:
                context = p.chromium.launch_persistent_context(
                    chrome_user_data,
                    channel="chrome",
                    headless=True,
                    args=[
                        "--profile-directory=Default",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-blink-features=AutomationControlled",
                    ],
                    viewport={{"width": 1280, "height": 900}},
                )
                page = context.new_page()
                if check_logged_in(page):
                    sys.stderr.write("Logged in via Chrome profile — scraping headlessly...\\n")
                    html = scrape_certs_page(page)
                    context.close()
                else:
                    sys.stderr.write("Chrome profile not logged in to LinkedIn, will try fallback...\\n")
                    context.close()
            except Exception as chrome_err:
                sys.stderr.write(f"Chrome profile attempt failed ({{chrome_err}}), trying fallback...\\n")

        # ── Strategy 2: Playwright's own persistent Chromium profile ──
        if html is None:
            sys.stderr.write("Using Playwright persistent profile...\\n")
            context = p.chromium.launch_persistent_context(
                fallback_data_dir,
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={{"width": 1280, "height": 900}},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            )
            page = context.new_page()
            if check_logged_in(page):
                sys.stderr.write("Saved session valid — scraping headlessly...\\n")
                html = scrape_certs_page(page)
                context.close()
            else:
                context.close()
                sys.stderr.write("No saved session. Opening browser for one-time login...\\n")

                # Visible browser — login once, session saved for all future headless calls
                context = p.chromium.launch_persistent_context(
                    fallback_data_dir,
                    headless=False,
                    args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
                    slow_mo=100,
                    viewport={{"width": 1920, "height": 1080}},
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                )
                page = context.new_page()
                page.goto("https://www.linkedin.com/login", timeout=60000, wait_until="domcontentloaded")
                time.sleep(3)

                actual_url = page.evaluate("() => window.location.href")
                if is_login_page(actual_url):
                    sys.stderr.write("\\n" + "="*60 + "\\n")
                    sys.stderr.write("PLEASE LOG IN TO LINKEDIN IN THE BROWSER WINDOW\\n")
                    sys.stderr.write("Your session will be saved — you will NEVER need to do this again.\\n")
                    sys.stderr.write("="*60 + "\\n\\n")

                    max_wait, waited, logged_in = 300, 0, False
                    while waited < max_wait:
                        time.sleep(3)
                        waited += 3
                        try:
                            current_url = page.evaluate("() => window.location.href")
                            if any(k in current_url for k in ["feed", "mynetwork", "messaging", "jobs"]):
                                logged_in = True
                                break
                            if "/in/" in current_url and "login" not in current_url:
                                logged_in = True
                                break
                        except:
                            pass
                    if not logged_in:
                        context.close()
                        raise Exception("Login timeout — please try again")

                sys.stderr.write("Logged in! Scraping certifications...\\n")
                html = scrape_certs_page(page)
                context.close()

        sys.stderr.write(f"Got {{len(html)}} chars of HTML\\n")
        print(html)

except Exception as e:
    sys.stderr.write(f"Error: {{str(e)}}\\n")
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
'''

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(script)
            script_path = f.name

        logger.info(f"Running Playwright script for: {profile_url}")
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=420,
            encoding='utf-8',
            errors='replace'
        )

        if result.returncode != 0:
            error_msg = result.stderr or "Unknown error"
            logger.error(f"Playwright script error: {error_msg}")
            raise Exception(f"Playwright script failed: {error_msg}")

        if not result.stdout or len(result.stdout) < 100:
            raise Exception("Failed to get page content from LinkedIn")

        return result.stdout
    finally:
        try:
            os.unlink(script_path)
        except:
            pass


async def scrape_linkedin_certifications(profile_url: str) -> List[Dict[str, str]]:
    """
    Scrape certifications from a LinkedIn profile URL.
    
    Args:
        profile_url: LinkedIn profile URL (e.g., https://www.linkedin.com/in/username/)
    
    Returns:
        List of certification dictionaries with keys: name, issuer, date, credential_id, url
    """
    try:
        # Run Playwright in separate process to avoid Windows asyncio issues
        loop = asyncio.get_event_loop()
        html = await loop.run_in_executor(None, _run_playwright_script, profile_url)
        
        # Save HTML for debugging
        debug_path = os.path.join(os.path.dirname(__file__), '..', '..', 'linkedin_debug.html')
        try:
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f"Saved debug HTML to: {debug_path}")
        except Exception as e:
            logger.warning(f"Could not save debug HTML: {e}")
        
        soup = BeautifulSoup(html, 'html.parser')
        certifications = []
        
        logger.info(f"HTML length: {len(html)}")
        
        # Check page title to see where we are
        title = soup.find('title')
        logger.info(f"Page title: {title.get_text() if title else 'No title'}")
        
        # LinkedIn certifications page structure - look for list items
        # The certifications page uses pvs-list__paged-list-wrapper
        cert_list = soup.find_all('li', class_=lambda x: x and 'pvs-list__paged-list-item' in str(x))
        logger.info(f"Found {len(cert_list)} pvs-list items")
        
        if not cert_list:
            # Try alternative selector
            cert_list = soup.find_all('li', class_=lambda x: x and 'artdeco-list__item' in str(x))
            logger.info(f"Found {len(cert_list)} artdeco-list items")
        
        if not cert_list:
            # Try finding any li with certification-like content
            cert_list = soup.find_all('li', class_=lambda x: x and 'pvs-list' in str(x))
            logger.info(f"Found {len(cert_list)} pvs-list items (broader)")
        
        for item in cert_list:
            cert = {}
            
            # Extract certification name - in div with "mr1 t-bold" class
            name_elem = item.find('div', class_=lambda x: x and 'mr1' in str(x) and 't-bold' in str(x))
            if name_elem:
                # Get the aria-hidden span for clean text
                name_span = name_elem.find('span', {'aria-hidden': 'true'})
                if name_span:
                    cert['name'] = name_span.get_text(strip=True)
                else:
                    cert['name'] = name_elem.get_text(strip=True)
            
            # Extract issuer - in span with "t-14 t-normal" but NOT "t-black--light"
            issuer_spans = item.find_all('span', class_=lambda x: x and 't-14' in str(x) and 't-normal' in str(x) and 't-black--light' not in str(x))
            for span in issuer_spans:
                inner_span = span.find('span', {'aria-hidden': 'true'})
                if inner_span:
                    text = inner_span.get_text(strip=True)
                    # Skip if it's a date or empty
                    if text and 'Issued' not in text and 'Skills' not in text and len(text) > 2:
                        cert['issuer'] = text
                        break
            
            # Extract date - in span with "pvs-entity__caption-wrapper" class
            date_elem = item.find('span', class_=lambda x: x and 'pvs-entity__caption-wrapper' in str(x))
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                # Remove "Issued " prefix
                if 'Issued' in date_text:
                    date_text = date_text.replace('Issued', '').strip()
                if date_text:
                    cert['date'] = date_text
            
            # Extract credential ID (if present)
            for elem in item.find_all(['span', 'div']):
                text = elem.get_text(strip=True)
                if 'Credential ID' in text:
                    cred_text = text.replace('Credential ID', '').strip()
                    if cred_text:
                        cert['credential_id'] = cred_text
                    break
            
            # Extract URL - look for "See credential" link
            url_elem = item.find('a', href=True, string=lambda x: x and 'credential' in str(x).lower())
            if not url_elem:
                # Try finding any external link
                for link in item.find_all('a', href=True):
                    href = link.get('href', '')
                    if href and 'linkedin.com' not in href and href.startswith('http'):
                        url_elem = link
                        break
            
            if url_elem and 'href' in url_elem.attrs:
                cert['url'] = url_elem['href']
            
            # Only add if we got a valid name
            if cert.get('name') and len(cert.get('name', '')) > 2:
                # Clean up the name - remove any extra whitespace
                cert['name'] = ' '.join(cert['name'].split())
                certifications.append(cert)
                logger.info(f"Extracted certification: {cert}")
        
        # If we still found nothing, try a more aggressive search
        if not certifications:
            logger.info("No certifications found with primary method, trying fallback...")
            # Look for any certification-like patterns in the HTML
            all_text = soup.get_text()
            # Find patterns like "Certification Name\nIssuing Organization\nIssued Date"
            
            # Alternative: find all divs that might contain certification info
            potential_certs = soup.find_all('div', class_=lambda x: x and ('entity-result' in str(x) or 'pv-profile' in str(x) or 'certification' in str(x).lower()))
            logger.info(f"Found {len(potential_certs)} potential certification divs")
            
            for div in potential_certs:
                texts = [t.strip() for t in div.stripped_strings]
                if len(texts) >= 2:
                    cert = {
                        'name': texts[0],
                        'issuer': texts[1] if len(texts) > 1 else None,
                        'date': texts[2] if len(texts) > 2 and 'Issued' in texts[2] else None
                    }
                    if cert['name'] and len(cert['name']) > 2:
                        certifications.append(cert)
                        logger.info(f"Fallback extracted: {cert}")
        
        logger.info(f"Total certifications found: {len(certifications)}")
        return certifications
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Error scraping LinkedIn profile: {str(e)}\n{error_details}")
        raise Exception(f"LinkedIn scraping failed: {str(e)}")


def parse_linkedin_url(url: str) -> Optional[str]:
    """
    Validate and normalize LinkedIn profile URL.
    
    Args:
        url: LinkedIn profile URL
    
    Returns:
        Normalized URL or None if invalid
    """
    if not url:
        return None
    
    # Remove trailing slashes
    url = url.rstrip('/')
    
    # Check if it's a valid LinkedIn profile URL
    if 'linkedin.com/in/' in url:
        return url
    
    # If it's just a username, construct full URL
    if not url.startswith('http'):
        return f"https://www.linkedin.com/in/{url}"
    
    return None


def _run_playwright_profile_script(profile_url: str) -> str:
    """
    Run Playwright in a separate process to scrape a full LinkedIn profile.

    Navigates to the main profile, contact-info overlay, /details/education/,
    and /details/certifications/.  Returns a JSON string containing:
      summary, website, email, phone, linkedin_url, education[], certifications[]
    """
    base_url = profile_url.rstrip('/')
    edu_url   = f"{base_url}/details/education/"
    certs_url = f"{base_url}/details/certifications/"
    contact_url = f"{base_url}/overlay/contact-info/"
    chrome_user_data = _get_chrome_user_data_dir() or ""

    script = f'''
import sys, io, os, json, time
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

profile_url  = "{profile_url}"
edu_url      = "{edu_url}"
certs_url    = "{certs_url}"
contact_url  = "{contact_url}"
chrome_user_data = r"{chrome_user_data}"
fallback_data_dir = os.path.join(os.path.expanduser("~"), ".linkedin_playwright_data")
os.makedirs(fallback_data_dir, exist_ok=True)

def is_login_page(url):
    return any(x in url.lower() for x in ["login","authwall","checkpoint","uas/login","signin","session"])

def check_logged_in(page):
    page.goto("https://www.linkedin.com/feed", timeout=30000, wait_until="domcontentloaded")
    time.sleep(2)
    url = page.evaluate("() => window.location.href")
    return not is_login_page(url) and any(k in url for k in ["feed","/in/","mynetwork"])

# ── JS helpers for DOM extraction ──────────────────────────────────────────
JS_PERSONAL = """
() => {{
    const r = {{}};
    // Name
    const h1 = document.querySelector("h1.text-heading-xlarge, h1[aria-label], h1");
    if (h1) r.name = (h1.innerText || h1.textContent || "").trim();
    // Headline – first .text-body-medium inside top section (not nav, not buttons)
    const topSection = document.querySelector(".pv-text-details__left-panel, .mt2.relative, section.artdeco-card");
    if (topSection) {{
        const hl = topSection.querySelector(".text-body-medium");
        if (hl) r.headline = (hl.innerText || hl.textContent || "").trim();
    }}
    if (!r.headline) {{
        const hl = document.querySelector(".text-body-medium.break-words");
        if (hl) r.headline = (hl.innerText || hl.textContent || "").trim();
    }}
    // Location
    const locCandidates = [
        ".pv-text-details__left-panel span.text-body-small.t-black--light",
        "span.t-black--light.break-words",
        ".pv-top-card--list.pv-top-card--list-bullet li",
    ];
    for (const sel of locCandidates) {{
        const el = document.querySelector(sel);
        if (el) {{ r.location = (el.innerText || el.textContent || "").trim(); break; }}
    }}
    return r;
}}
"""

JS_SUMMARY = """
() => {{
    const cards = document.querySelectorAll("section, div.artdeco-card");
    for (const card of cards) {{
        const anchor = card.querySelector("#about");
        if (!anchor) continue;
        const spans = card.querySelectorAll('span[aria-hidden="true"]');
        for (const sp of spans) {{
            const t = (sp.innerText || sp.textContent || "").trim();
            if (t.length > 60) return t;
        }}
    }}
    const ab = document.querySelector(".pv-about-section, .pv-about__summary-text");
    if (ab) return (ab.innerText || ab.textContent || "").trim();
    return null;
}}
"""

JS_CONTACT = """
() => {{
    const result = {{}};
    // Section titles map us to the following sibling value
    const sections = Array.from(document.querySelectorAll("section"));
    for (const sec of sections) {{
        const h3 = sec.querySelector("h3");
        if (!h3) continue;
        const title = (h3.innerText || h3.textContent || "").trim().toLowerCase();
        const valEl = sec.querySelector("a, span.t-14");
        if (!valEl) continue;
        const val  = (valEl.getAttribute("href") || valEl.innerText || valEl.textContent || "").trim();
        if (title.includes("email"))   {{ result.email   = val.replace("mailto:",""); }}
        if (title.includes("phone"))   {{ result.phone   = val; }}
        if (title.includes("website") || title.includes("url")) {{ result.website = val; }}
    }}
    // Fallback: walk all links
    const links = Array.from(document.querySelectorAll("a[href]"));
    for (const a of links) {{
        const href = (a.getAttribute("href") || "").trim();
        if (href.startsWith("mailto:") && !result.email)   {{ result.email   = href.replace("mailto:",""); }}
        if (href.startsWith("http")   && !href.includes("linkedin.com") && !result.website) {{ result.website = href; }}
        if (href.includes("linkedin.com/in/") && !result.linkedin_url) {{ result.linkedin_url = href.split("?")[0].replace(/[/]$/, ""); }}
    }}
    // Phone: any span that looks like a phone number
    if (!result.phone) {{
        const spans = Array.from(document.querySelectorAll("span, a"));
        for (const sp of spans) {{
            const t = (sp.innerText || sp.textContent || "").trim();
            if (new RegExp('^[+.(0-9][0-9 .()+/-]{6,}$').test(t) && t.replace(/[^0-9]/g,'').length >= 6) {{ result.phone = t; break; }}
        }}
    }}
    return result;
}}
"""

JS_LIST_ITEMS = """
() => {{
    const selectors = [
        "li.pvs-list__paged-list-item",
        "li.artdeco-list__item",
    ];
    for (const sel of selectors) {{
        const items = Array.from(document.querySelectorAll(sel));
        if (items.length === 0) continue;
        return items.map(item => {{
            const spans = Array.from(item.querySelectorAll('span[aria-hidden="true"]'))
                            .map(s => (s.innerText || s.textContent || "").trim())
                            .filter(t => t.length > 0);
            // external links
            let url = null;
            for (const a of item.querySelectorAll("a[href]")) {{
                const h = a.getAttribute("href") || "";
                if (h.startsWith("http") && !h.includes("linkedin.com")) {{ url = h; break; }}
            }}
            return {{ spans, url }};
        }}).filter(e => e.spans.length > 0);
    }}
    return [];
}}
"""

JS_EDUCATION = """
() => {{
    function tc(el) {{
        if (!el) return "";
        // Use textContent (not innerText) for reliability on hidden spans,
        // then normalise all whitespace.
        return (el.textContent || "").replace(/\\s+/g, " ").trim();
    }}
    function isDate(t) {{
        return /[12][0-9]{{3}}/.test(t) && (/\\u2013|\\u2014|[-–—]|\\bto\\b|\\bpresent\\b/i.test(t));
    }}
    function isDegree(t) {{
        const KWORDS = [
            "bachelor","master","doctor","phd","b.tech","m.tech","b.e","m.e","mba",
            "b.sc","m.sc","b.a","m.a","associate","diploma","certificate",
            "high school","higher secondary","engineering","technology","science","arts","commerce",
        ];
        const lower = t.toLowerCase();
        return KWORDS.some(k => lower.includes(k));
    }}

    const mainEl = document.querySelector(
        'main, [role="main"], div[class*="scaffold-layout__main"]'
    ) || document;

    // Only direct children of the root list to avoid sub-items
    const rootUl = mainEl.querySelector('ul.pvs-list, ul[class*="pvs-list"]');
    const rows = rootUl
        ? Array.from(rootUl.querySelectorAll(':scope > li'))
        : Array.from(mainEl.querySelectorAll('li.pvs-list__paged-list-item'));

    const results = [];

    for (const item of rows) {{
        const edu = {{}};

        // ── School: first bold text node ──────────────────────────────────────
        const boldSel = [
            ".mr1.t-bold span[aria-hidden='true']",
            ".t-bold span[aria-hidden='true']",
            "span[aria-hidden='true']",         // last resort: very first span
        ];
        for (const sel of boldSel) {{
            const el = item.querySelector(sel);
            const v = tc(el);
            if (v.length >= 3) {{ edu.school = v; break; }}
        }}
        if (!edu.school) continue;

        // ── Degree / field: ALL subtitle spans, deduplicated by value ─────────
        // Strictly target `span.t-14.t-normal` that are NOT `t-black--light`,
        // then take only their direct `span[aria-hidden]` child (the leaf).
        // Using querySelectorAll on the item, then filtering to avoid grabbing
        // spans that live inside nested sub-list items.
        const subtitleTexts = [];
        const seen = new Set();
        const subtitleEls = Array.from(
            item.querySelectorAll("span.t-14.t-normal:not(.t-black--light)")
        );
        for (const se of subtitleEls) {{
            // Skip if this element is inside a nested <ul> (sub-item)
            if (se.closest('ul') !== rootUl && se.closest('ul') !== null) continue;
            // Prefer the aria-hidden child; fall back to the span itself
            const leaf = se.querySelector("span[aria-hidden='true']") || se;
            const v = tc(leaf);
            if (v.length > 0 && !seen.has(v)) {{
                seen.add(v);
                subtitleTexts.push(v);
            }}
        }}

        // Assign degree and field from subtitle texts.
        // LinkedIn sometimes combines them in a single span: "B.Tech · Computer Science"
        // Expand any combined entries by splitting on " · " or ", " so each
        // token becomes its own element before degree/field assignment.
        const rawNonDate = subtitleTexts.filter(t => !isDate(t));
        const nonDate = [];
        for (const t of rawNonDate) {{
            const parts = t.split(/\\s*[·•,]\\s*/).map(p => p.trim()).filter(p => p.length > 0);
            for (const p of parts) nonDate.push(p);
        }}
        if (nonDate.length >= 1) {{
            if (isDegree(nonDate[0])) {{
                edu.degree = nonDate[0];
                if (nonDate[1]) edu.field = nonDate[1];
            }} else {{
                edu.degree = nonDate[0];
                if (nonDate[1] && isDegree(nonDate[1])) {{
                    // swap: second token is actually the degree
                    edu.field = nonDate[0];
                    edu.degree = nonDate[1];
                }} else if (nonDate[1]) {{
                    edu.field = nonDate[1];
                }}
            }}
        }}

        // ── Dates: caption wrapper first, then any dark-light span with year ─
        const capEl = item.querySelector("span.pvs-entity__caption-wrapper[aria-hidden='true']");
        if (capEl) {{
            edu.dates = tc(capEl);
        }} else {{
            const darkEls = Array.from(
                item.querySelectorAll("span.t-14.t-normal.t-black--light span[aria-hidden='true']")
            ).map(tc).filter(isDate);
            if (darkEls.length > 0) edu.dates = darkEls[0];
        }}

        // Require at least one data point beyond the school name
        if (!edu.degree && !edu.dates) continue;

        results.push(edu);
    }}

    return results;
}}
"""

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
        except:
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
                        except:
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
'''

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(script)
            script_path = f.name

        logger.info(f"Running LinkedIn profile script for: {profile_url}")
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=480,
            encoding='utf-8',
            errors='replace'
        )

        if result.returncode != 0:
            raise Exception(f"Profile script failed: {result.stderr or 'Unknown error'}")

        if not result.stdout or len(result.stdout) < 5:
            raise Exception("Empty output from profile script")

        return result.stdout.strip()
    finally:
        try:
            os.unlink(script_path)
        except:
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
        raise Exception(f"LinkedIn profile scraping failed: {str(e)}")
