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

logger = logging.getLogger(__name__)


def _run_playwright_script(profile_url: str) -> str:
    """Run Playwright in a separate process to avoid Windows asyncio issues."""
    # Ensure we're going to the certifications section
    # LinkedIn profile URL: https://www.linkedin.com/in/username/
    # Certifications section: https://www.linkedin.com/in/username/details/certifications/
    
    base_url = profile_url.rstrip('/')
    certs_url = f"{base_url}/details/certifications/"
    
    # Create a temporary Python script that runs Playwright
    script = f'''
import sys
import io
import os
from playwright.sync_api import sync_playwright
import time

# Force UTF-8 encoding for stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

profile_url = "{profile_url}"
certs_url = "{certs_url}"

# Use a persistent user data directory to remember login
user_data_dir = os.path.join(os.path.expanduser("~"), ".linkedin_playwright_data")
os.makedirs(user_data_dir, exist_ok=True)

def is_login_page(url):
    """Check if current page is a login/auth page."""
    login_indicators = ['login', 'authwall', 'checkpoint', 'uas/login', 'signin', 'session']
    url_lower = url.lower()
    return any(indicator in url_lower for indicator in login_indicators)

try:
    with sync_playwright() as p:
        # Use persistent context to remember login
        context = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=['--start-maximized', '--disable-blink-features=AutomationControlled'],
            slow_mo=100,
            viewport={{'width': 1920, 'height': 1080}},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        # Navigate to LinkedIn login page directly
        sys.stderr.write("Opening LinkedIn...\\n")
        page.goto("https://www.linkedin.com/login", timeout=60000, wait_until='domcontentloaded')
        time.sleep(3)
        
        # Get actual URL using JavaScript (more reliable)
        actual_url = page.evaluate("() => window.location.href")
        sys.stderr.write(f"Current URL after navigation: {{actual_url}}\\n")
        
        # Check if already logged in (redirected to feed)
        if 'feed' in actual_url or ('/in/' in actual_url and 'login' not in actual_url):
            sys.stderr.write("Already logged in!\\n")
        else:
            # Wait for user to log in
            sys.stderr.write("\\n" + "="*60 + "\\n")
            sys.stderr.write("PLEASE LOG IN TO LINKEDIN IN THE BROWSER WINDOW\\n")
            sys.stderr.write("After logging in, the script will continue automatically\\n")
            sys.stderr.write("You have 5 minutes to complete the login\\n")
            sys.stderr.write("="*60 + "\\n\\n")
            
            max_wait = 300  # 5 minutes
            waited = 0
            logged_in = False
            
            while waited < max_wait:
                time.sleep(3)
                waited += 3
                
                try:
                    # Use JavaScript to get the actual URL from the browser
                    # This is more reliable than page.url for detecting navigation
                    current_url = page.evaluate("() => window.location.href")
                    sys.stderr.write(f"Checking URL: {{current_url}}\\n")
                    
                    # Also check the document title for additional context
                    try:
                        title = page.evaluate("() => document.title")
                        sys.stderr.write(f"Page title: {{title}}\\n")
                    except:
                        pass
                    
                    # Check if we're on the feed page (means login was successful)
                    if 'linkedin.com/feed' in current_url:
                        logged_in = True
                        sys.stderr.write("Login detected (feed page)! Continuing...\\n")
                        break
                    
                    # Check if we're on a profile page
                    if '/in/' in current_url and 'login' not in current_url:
                        logged_in = True
                        sys.stderr.write("Login detected (profile page)! Continuing...\\n")
                        break
                    
                    # Check if we're on mynetwork or other logged-in pages
                    if 'mynetwork' in current_url or 'messaging' in current_url or 'jobs' in current_url:
                        logged_in = True
                        sys.stderr.write("Login detected (other page)! Continuing...\\n")
                        break
                    
                    # Check for session_redirect which also indicates successful login
                    if 'session_redirect' in current_url or 'trk=' in current_url:
                        logged_in = True
                        sys.stderr.write("Login detected (redirect)! Continuing...\\n")
                        break
                    
                    # Check if we're still on login page
                    if is_login_page(current_url):
                        sys.stderr.write(f"Still on login page, waiting... ({{waited}}s)\\n")
                        continue
                except Exception as e:
                    sys.stderr.write(f"Check error (continuing): {{e}}\\n")
                    continue
            
            if not logged_in:
                final_url = page.evaluate("() => window.location.href")
                if is_login_page(final_url):
                    context.close()
                    raise Exception("Login timeout - please try again and complete login within 5 minutes")
        
        sys.stderr.write("Login successful! Navigating to certifications...\\n")
        time.sleep(2)
        
        # Now navigate to the certifications section
        sys.stderr.write(f"Going to: {{certs_url}}\\n")
        page.goto(certs_url, timeout=60000, wait_until='domcontentloaded')
        time.sleep(3)
        
        # Wait for page to fully load
        try:
            page.wait_for_load_state('networkidle', timeout=15000)
        except:
            pass
        time.sleep(2)
        
        # Check if we landed on the certifications page
        if 'certifications' not in page.url and 'licenses' not in page.url:
            sys.stderr.write(f"Warning: May not be on certifications page. Current URL: {{page.url}}\\n")
            # Try alternative URL
            alt_url = profile_url.rstrip('/') + "/details/licenses-and-certifications/"
            sys.stderr.write(f"Trying alternative URL: {{alt_url}}\\n")
            page.goto(alt_url, timeout=60000, wait_until='domcontentloaded')
            time.sleep(3)
        
        # Scroll to load all certifications
        sys.stderr.write("Scrolling to load all content...\\n")
        try:
            for i in range(5):
                page.evaluate("window.scrollBy(0, 400)")
                time.sleep(0.5)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            # Scroll back up
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(1)
        except Exception as e:
            sys.stderr.write(f"Scroll warning (ignored): {{e}}\\n")
        
        html = page.content()
        sys.stderr.write(f"Got page content ({{len(html)}} chars)\\n")
        context.close()
        print(html)
        
except Exception as e:
    sys.stderr.write(f"Error: {{str(e)}}\\n")
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
'''
    
    try:
        # Write script to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(script)
            script_path = f.name
        
        # Run the script in a separate process
        logger.info(f"Running Playwright script for: {profile_url}")
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=420,  # 7 minutes timeout to allow for login + navigation
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
        # Clean up temp file
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
