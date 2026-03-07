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
