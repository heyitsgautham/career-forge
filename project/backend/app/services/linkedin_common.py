"""LinkedIn profile URL validation and the local Chrome profile lookup."""

import logging
import os
import platform
import re
from typing import Optional

logger = logging.getLogger(__name__)

# LinkedIn profile slugs are letters, digits, hyphens and underscores (plus
# percent-encoded non-ASCII). Anything else is rejected before it reaches a script.
_SLUG = r"(?P<slug>[A-Za-z0-9_%-]{3,100})"
_PROFILE_URL = re.compile(
    r"(?:https?://)?(?:[a-z]{2,3}\.)?(?:www\.)?linkedin\.com/in/" + _SLUG + r"(?:[/?#].*)?",
    re.DOTALL,
)
_PROFILE_SLUG = re.compile(_SLUG)


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


def parse_linkedin_url(url: str) -> Optional[str]:
    """
    Validate and normalize a LinkedIn profile URL.

    Accepts [https://][www.|xx.]linkedin.com/in/<slug>, with any trailing path,
    query or fragment, or a bare <slug>, and returns
    https://www.linkedin.com/in/<slug>. Anything else returns None.
    The result is embedded in a generated Playwright script, so only the
    characters LinkedIn allows in a profile slug get through.

    Args:
        url: LinkedIn profile URL or username

    Returns:
        Normalized URL or None if invalid
    """
    if not url:
        return None

    url = url.strip()
    match = _PROFILE_URL.fullmatch(url) or _PROFILE_SLUG.fullmatch(url)
    if not match:
        return None
    return f"https://www.linkedin.com/in/{match.group('slug')}"
