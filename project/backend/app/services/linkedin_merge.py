"""
Merging scraped LinkedIn data into a profile
============================================
Pure rules for what a LinkedIn import may change: details the user already
filled in are kept, the headline and summary are refreshed, and education and
certifications are appended without duplicating a school or certificate name.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProfileSnapshot:
    """The profile fields a LinkedIn import reads before it writes."""

    name: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    education: List[dict] = field(default_factory=list)
    certifications: List[dict] = field(default_factory=list)


@dataclass
class LinkedInMerge:
    updates: Dict[str, Any]
    new_education: List[dict]
    new_certifications: List[dict]


def _key(entry: dict, name: str) -> str:
    return str(entry.get(name) or "").strip().lower()


def append_new(existing: List[dict], scraped: List[dict], key: str) -> List[dict]:
    """Entries from `scraped` whose `key` is set and not already in `existing`, case-insensitively."""
    seen = {_key(e, key) for e in existing}
    fresh = []
    for entry in scraped:
        name = _key(entry, key)
        if name and name not in seen:
            seen.add(name)
            fresh.append(entry)
    return fresh


def merge_linkedin_profile(
    linkedin_url: str, current: ProfileSnapshot, data: dict
) -> LinkedInMerge:
    """The profile updates a LinkedIn import makes, and what it adds."""
    updates: Dict[str, Any] = {"linkedin_url": linkedin_url}

    # Only fill personal details the user has not set themselves
    for name in ("name", "location", "website", "phone", "email"):
        if data.get(name) and not getattr(current, name):
            updates[name] = data[name]
    # LinkedIn is the source of truth for these two
    for name in ("headline", "summary"):
        if data.get(name):
            updates[name] = data[name]

    new_education = append_new(current.education, data.get("education") or [], "school")
    if data.get("education"):
        updates["education"] = current.education + new_education

    new_certifications = append_new(
        current.certifications, data.get("certifications") or [], "name"
    )
    if data.get("certifications"):
        updates["certifications"] = current.certifications + new_certifications

    return LinkedInMerge(updates, new_education, new_certifications)
