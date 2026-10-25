"""
Job filters
===========
Pure helpers the job scraper uses to decide what to keep: posting freshness,
deterministic job IDs, non-engineering role filtering and salary parsing, plus
the search queries every scrape runs.
"""

import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional

# ── Date freshness helper ─────────────────────────────────────────────────────


def _is_recent_job(date_posted: str, max_age_hours: int) -> bool:
    """
    Return True if the job was posted within max_age_hours.
    Handles:
      - ISO date strings: "2026-03-08" (from Unstop created_at)
      - Internshala relative text: "Today", "Just added", "1 d", "3 d"
    Unknown / empty dates are included (benefit of the doubt).
    """
    if not date_posted:
        return True
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=max_age_hours)

    # ISO date: "2026-03-08" — Unstop and Internshala JSON blob
    try:
        dt = datetime.strptime(date_posted[:10], "%Y-%m-%d")
        return dt >= cutoff
    except ValueError:
        pass

    # Internshala relative text from HTML card: "Today", "Just added", "1 d", "3 d"
    lower = date_posted.lower().strip()
    if lower in ("today", "just added", "0 d", "few hours ago", "1 d"):
        return True
    if lower.endswith(" d"):
        try:
            days = int(lower[:-2].strip())
            return days * 24 <= max_age_hours
        except ValueError:
            pass

    return True  # unknown format — include by default


# ── Search queries covering major CS/tech roles ─────────────────────────────

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

# ── Management / non-engineering role keywords to always exclude ─────────────

MANAGEMENT_ROLE_KEYWORDS = [
    "project manager",
    "product manager",
    "program manager",
    "hr intern",
    "human resources",
    "recruiter",
    "business development",
    "sales intern",
    "marketing intern",
    "operations manager",
    "scrum master",
    "agile coach",
    "account manager",
    "customer success",
    "talent acquisition",
    "social media",
    "content writer",
    "content marketing",
    "digital marketing",
    "seo intern",
    "finance intern",
    "accounting intern",
    "legal intern",
    "procurement",
    "supply chain",
    "logistics",
    "operations intern",
    "management trainee",
    "business analyst intern",
]


def _generate_job_id(job_url: str) -> str:
    """Generate a deterministic job ID from the URL for dedup."""
    return hashlib.md5(job_url.encode()).hexdigest()


def _is_management_role(title: str) -> bool:
    """Check if a job title matches management/non-engineering keywords."""
    title_lower = title.lower()
    return any(kw in title_lower for kw in MANAGEMENT_ROLE_KEYWORDS)


def _extract_salary_from_description(description: str) -> Optional[str]:
    """Extract salary from description using regex patterns as a fallback."""
    if not description:
        return None

    clean = re.sub(r"[*_]", "", description)
    clean = re.sub(r"\s+", " ", clean)

    patterns = [
        (r"stipend\s*:?\s*₹\s*(\d+(?:,\d+)*)\s*(?:-|to)\s*₹?\s*(\d+(?:,\d+)*)", "range_inr"),
        (r"stipend\s*:?\s*Rs\.?\s*(\d+(?:,\d+)*)\s*(?:per|/)?\s*(month|year)?", "stipend_rs"),
        (r"stipend\s*:?\s*₹\s*(\d+(?:,\d+)*)\s*(?:per|/)?\s*(month|year)?", "stipend_inr"),
        (r"(\d+(?:,\d+)*)\s*(?:-|to)\s*(\d+(?:,\d+)*)\s*(?:LPA|lpa)", "lpa_range"),
        (r"(\d+(?:\.\d+)?)\s*(?:LPA|lpa)", "lpa_single"),
        (r"CTC\s*:?\s*₹?\s*(\d+(?:,\d+)*)", "ctc"),
        (r"\$\s*(\d+(?:,\d+)*)\s*(?:-|to)\s*\$?\s*(\d+(?:,\d+)*)", "usd_range"),
    ]

    for pattern, label in patterns:
        match = re.search(pattern, clean, re.IGNORECASE)
        if match:
            groups = match.groups()
            if label == "range_inr":
                return f"₹{groups[0]}–₹{groups[1]}"
            elif label in ("stipend_rs", "stipend_inr"):
                suffix = f" / {groups[1]}" if len(groups) > 1 and groups[1] else ""
                return f"₹{groups[0]}{suffix}"
            elif label == "lpa_range":
                return f"{groups[0]}–{groups[1]} LPA"
            elif label == "lpa_single":
                return f"{groups[0]} LPA"
            elif label == "ctc":
                return f"CTC ₹{groups[0]}"
            elif label == "usd_range":
                return f"${groups[0]}–${groups[1]}"
    return None
