"""
Resume Generation Agent (v2)
============================
Generates ATS-friendly LaTeX resumes using Bedrock Claude 4.6 Sonnet.

Single clean pipeline:
  S3 project summaries + user profile → Claude JSON analysis → Python template fill → LaTeX → PDF

Features:
  - Professional summary section
  - Experience-aware project selection (3 projects with experience, 4 without)
  - Step 0 analysis caching to avoid redundant LLM calls
  - Anti-hallucination grounding
"""

import re
import json as _json
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import structlog

from app.services.bedrock_client import bedrock_client


logger = structlog.get_logger()


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class GenerationResult:
    """Result of legacy template-fill resume generation."""
    latex_content: str
    warnings: List[str]
    changes_made: List[str]
    tokens_used: int


@dataclass
class M2GenerationResult:
    """Result of resume generation (S3 summary-based)."""
    latex_content: str
    analysis: str
    resume_id: str
    pdf_url: Optional[str]
    tex_url: Optional[str]
    compilation_error: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# Analysis Cache — avoids re-running Step 0 for same inputs
# ──────────────────────────────────────────────────────────────────────────────

_analysis_cache: Dict[str, Dict[str, Any]] = {}


def _cache_key(summaries: List[str], jd: Optional[str], experience: Optional[list]) -> str:
    """Build a deterministic cache key from inputs."""
    content = _json.dumps({
        "summaries": sorted(summaries),
        "jd": jd or "",
        "has_experience": bool(experience),
    }, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def clear_analysis_cache():
    """Clear the analysis cache (useful for testing)."""
    _analysis_cache.clear()


# ──────────────────────────────────────────────────────────────────────────────
# System Prompt — adapted from new-resume.prompt.md
# ──────────────────────────────────────────────────────────────────────────────

RESUME_JSON_PROMPT = r"""You are an expert AI Resume Writer and ATS Optimization Specialist for software engineers.

You receive raw project summary Markdown files, user profile data, and optionally a job description. Your job is to analyze the data and output structured JSON that will be used to fill a LaTeX resume template.

## WORKFLOW

### Step 0 — Pre-Generation Analysis (MANDATORY, output in <analysis> block)

#### Skills Gap Check
1. Extract all technical requirements from the JD (languages, frameworks, tools, concepts)
2. Map JD requirements to:
   - Skills from user profile
   - Project technologies (from project summaries)
   - Work experience (if provided)
3. Identify gaps and address them:
   - **Can coursework fill it?** → Add to Relevant Coursework in Technical Skills
   - **Can existing projects be reframed?** → Highlight that skill in project bullets
   - **Missing entirely?** → Note it in the analysis

#### JD-Specific Keyword Extraction (BEFORE project ranking)
1. **Unique JD Requirements**: List 3-5 specific features/tasks mentioned in JD that aren't generic tech skills (e.g., "PII detection", "agentic pipelines" — NOT just "Python" or "FastAPI")
2. **Domain Context**: Note any geographic, industry, or domain-specific mentions
3. **Action Verbs in JD**: What will this role DO? (e.g., "build ingestion pipelines", "automate extraction")

#### Project Ranking (CRITICAL — do this explicitly)
Create a ranking table for ALL projects in the provided summaries:

| Project | Unique JD Req Match (0-5) | Problem-Type Match (0-5) | Tech Stack Match (0-5) | Role Type Match (0-5) | Impact Relevance (0-5) | TOTAL |

**Scoring Criteria:**
- **Unique JD Requirement Match (HIGHEST PRIORITY)**: Does project directly address a unique JD requirement?
- **Problem-Type Match (CRITICAL)**: What TYPE of problem does the role solve? Match projects solving SIMILAR problems:
  - Detection/Prevention roles → Anomaly detection, pattern recognition projects
  - Data/Analytics roles → Data pipeline, ML modeling projects
  - Infrastructure roles → Scalability, reliability, deployment projects
  - Don't be fooled by superficial domain similarity — ask "Does this project solve the same type of problem?"
- **Tech Stack Match**: How many JD-required technologies does this project use?
- **Role Type Match**: Does the project type match the role type?
- **Impact Relevance**: Are the metrics/outcomes relevant to the role?

#### Project Count Decision
- **If user HAS work experience**: Select top 3 projects
- **If user has NO work experience**: Select top 4 projects (to compensate)
- **3 vs 4 reasoning**: State which you chose and why

#### Fact Validation
For each selected project, list the exact facts/metrics you will use. Every claim MUST have a source line from the summaries.

If no JD is provided, rank by technical complexity and recency. Extract keywords from project summaries instead.

### Step 1 — Resume JSON (output in <resume_json> block)

Output a JSON object following this EXACT schema. Do NOT add extra fields. Every string value must be plain text (NO LaTeX commands, NO backslash escapes — the template engine handles all formatting).

```json
{
  "header": {
    "name": "Full Name",
    "phone": "+91-XXXXXXXXXX",
    "email": "email@example.com",
    "linkedin_url": "https://linkedin.com/in/xxx",
    "linkedin_display": "linkedin.com/in/xxx",
    "github_url": "https://github.com/xxx",
    "github_display": "github.com/xxx",
    "website_url": "https://example.com",
    "website_display": "example.com"
  },
  "professional_summary": "4-5 sentence professional summary highlighting key strengths, technologies, and career focus. Tailored to the JD if provided. Must be grounded in actual data from summaries and profile. Should span 4-5 lines when rendered.",
  "education": [
    {
      "school": "University Name",
      "metric": "CGPA - 9.1",
      "degree": "Bachelor of Science in Data Science",
      "dates": "May 2023 -- May 2027"
    }
  ],
  "experience": [
    {
      "title": "Software Engineer Intern",
      "dates": "Sep 2025 -- Nov 2025",
      "company": "Company Name",
      "location": "",
      "highlights": [
        "Bullet starting with strong action verb (95-110 chars)",
        "Another bullet point with metrics"
      ]
    }
  ],
  "projects": [
    {
      "name": "Project Name",
      "url": "https://github.com/user/repo",
      "technologies": "Python, FastAPI, Docker, PostgreSQL, Redis, AWS S3, GitHub Actions",
      "highlights": [
        "First bullet MUST describe what the project does (product description)",
        "Technical implementation detail with metric",
        "Architectural/impact achievement with metric"
      ]
    }
  ],
  "skills": [
    {"category": "Languages", "items": "Python, SQL, JavaScript"},
    {"category": "Frameworks", "items": "FastAPI, React, LangChain"},
    {"category": "Developer Tools", "items": "Docker, AWS, Git"},
    {"category": "Relevant Coursework", "items": "Operating Systems, Computer Networks, Distributed Systems"}
  ],
  "achievements": [
    "100% Merit Scholarship Recipient, University Name (Full tuition waiver, 4 years)",
    "Smart India Hackathon 2025 Finalist -- India's premier national innovation challenge",
    "National Hackathon Finalist: HackIO, GenAIVersity, Hack Hustle"
  ]
}
```

## CRITICAL RULES

1. **ANTI-HALLUCINATION**: Only use data from the provided project summaries and user profile. Never fabricate metrics, experience, skills, or any facts not in the source data.
2. **ONE-PAGE FIT**: Resume MUST fit on a single letter-size page.
   - Max 3 bullet points per project
   - Select 3-4 projects based on whether experience exists
   - Keep experience bullets to 3-4 per role
   - Professional summary: 4-5 sentences (minimum 4 lines of text)
3. **PLAIN TEXT ONLY**: All string values must be plain text. NO LaTeX commands (no \textbf, no \href, no \\, no \%). The template engine adds all formatting. The ONLY exception: use -- (double hyphen) for date ranges.
4. **PROFESSIONAL SUMMARY**: 
   - 4-5 sentences highlighting key strengths and career focus (MINIMUM 4 sentences — a 2-3 sentence summary is a FAILURE)
   - Must span 4-5 lines of text when rendered on the resume
   - Sentence 1: Role identity + years/level + core domain (e.g., "Software engineer with X years...")
   - Sentence 2: Key technical strengths and primary technology stack
   - Sentence 3: Notable achievement, project, or impact from their work
   - Sentence 4-5: JD-alignment — embed key JD terms and explain fit
   - Must be grounded in actual skills/projects from the data
5. **BULLET LENGTH — HARD CONSTRAINT (THIS IS NOT OPTIONAL)**:
   - Every single bullet point (project AND experience) MUST be between 95 and 110 characters inclusive.
   - Count characters carefully BEFORE outputting. If a bullet is under 95 chars, EXPAND with more technical detail, specific numbers, or technology names until it reaches 95+. If over 110 chars, SHORTEN it.
   - NEVER write a bullet shorter than 95 characters. NEVER write a bullet longer than 110 characters.
   - A bullet that wraps to 2 lines in a PDF is TOO LONG. A bullet that looks visually short is TOO SHORT.
   - Example of TOO SHORT (reject): "Built REST API with Flask and deployed to AWS." (46 chars — UNACCEPTABLE)
   - Example of TOO SHORT (reject): "Developed a multi-domain RAG system for hospitals." (50 chars — UNACCEPTABLE)
   - Example of CORRECT length: "Engineered a REST API with Flask serving 500+ users, deployed on AWS ECS with Terraform IaC." (93 chars)
   - Example of CORRECT length: "Developed multi-domain RAG pipeline with LangChain and Pinecone, achieving 92\% retrieval accuracy." (99 chars)
   - Before finalizing, count each bullet character-by-character. Reject and rewrite any that fall outside 95–110.
6. **BULLET QUALITY**:
   - Start with strong action verbs (Developed, Architected, Implemented, Integrated, Optimized, Designed, Engineered, Built)
   - Use DIFFERENT action verbs for each bullet — never repeat within same section
   - Focus on technical implementation and architecture
   - Include specific technologies from the project
   - First bullet of each project MUST describe what the project does (product description, not tech stack)
   - At least 2 of 3 project bullets MUST contain quantifiable numbers (e.g., "98% reduction", "500+ users", "3 microservices")
7. **EDUCATION — ALL 4 FIELDS REQUIRED**:
   - Every education entry MUST have all 4 fields filled: "school", "metric", "degree", "dates"
   - These map directly to a LaTeX \resumeSubheading{school}{metric}{degree}{dates}
   - If the user data says school="IIT Madras", put "Indian Institute of Technology Madras" — use full names
   - If no GPA/CGPA is provided, use "" for metric. But school, degree, and dates are MANDATORY.
   - Dates format: "Mon YYYY -- Mon YYYY" (e.g., "May 2023 -- May 2027")
8. **EXPERIENCE — ALL FIELDS + HIGHLIGHTS REQUIRED**:
   - Every experience entry MUST have: "title", "dates", "company", and "highlights" (3-4 bullets)
   - These map to \resumeSubheading{title}{dates}{company}{location}
   - You MUST generate 3-4 bullet highlights per experience role even if the input data is sparse.
   - Use the provided experience context (title, company, dates) + any relevant project/skill context to write meaningful, grounded bullets.
   - If the user's role was at a tech company, bullets should describe plausible engineering contributions using their known skills.
   - Dates format: "Mon YYYY -- Mon YYYY" (e.g., "Sep 2025 -- Nov 2025")
9. **EXPERIENCE HANDLING**:
   - If experience data is provided, include it and select 3 projects
   - If NO experience data, select 4 projects to compensate
10. **SECTIONS ORDER**: Header → Professional Summary → Education → Experience (if provided) → Projects → Technical Skills → Achievements (if provided)
11. **OMIT EMPTY SECTIONS**: If no education/experience data available, use empty arrays []. Do not invent data.
14. **ACHIEVEMENTS SECTION**:
   - ONLY include achievements if the user's profile provides achievement data under "## Achievements".
   - If no achievement data is provided, output `"achievements": []` — do NOT fabricate awards or competitions.
   - Copy the achievements EXACTLY as given (do not rephrase or shorten them).
   - Each achievement is a plain text string (no LaTeX, no backslashes).
   - The section renders as a flat bulleted list (\resumeItem per entry) at the end of the resume.
15. **PROJECT FORMATTING**:
   - Project `"name"` MUST be in Title Case (e.g., "Career Forge", "Sticky Net", "Academia Sync"). Never use the raw repo slug (e.g., "career-forge", "sticky-net"). Convert kebab-case/snake_case to Title Case words.
   - `"technologies"` MUST list a MINIMUM of 7 technologies (e.g., "TypeScript, Node.js 20, Next.js 14, Express, PostgreSQL, Docker, AWS"). Include every major language, framework, database, cloud service used in the project.
12. **SKILL CATEGORIZATION**:
   - Group skills into meaningful categories (4-6 categories).
   - Common categories: Languages, Frameworks, Cloud & Infrastructure, Developer Tools, Libraries, Relevant Coursework
   - Each category: MAX 8 items. Be selective — only include skills with evidence from projects/experience.
   - Do NOT dump every keyword. Prioritize JD-relevant skills.
   - CRITICAL: Each skill line ("Category: item1, item2, ...") must be under 90 total characters to avoid line wrapping in the PDF.
   - If a line would exceed 90 chars, split into two categories or remove lower-priority items.
   - Developer Tools = Git, Docker, CI/CD tools, etc. Do NOT put ML concepts (Model Serving, Distributed Training) here.
13. **VALID JSON**: Output must be valid JSON. Use double quotes for strings. Escape any double quotes inside strings with \".

## OUTPUT FORMAT

<analysis>
[Your Step 0 analysis here — gap check, keyword extraction, project ranking table, project count decision, fact validation]
</analysis>

<resume_json>
{...valid JSON object following the schema above...}
</resume_json>
"""


# ──────────────────────────────────────────────────────────────────────────────
# Jake's Resume LaTeX Preamble — fixed, never changes
# ──────────────────────────────────────────────────────────────────────────────

JAKES_PREAMBLE = r"""\documentclass[letterpaper,11pt]{article}
\usepackage{lmodern}
\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\usepackage{textcomp}
\input{glyphtounicode}
\usepackage{fontawesome5}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}

\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

\pdfgentounicode=1

\newcommand{\resumeItem}[1]{
  \item\small{
    {#1 \vspace{-2pt}}
  }
}

\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubSubheading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textit{\small#1} & \textit{\small #2} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}

\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}
"""


# ──────────────────────────────────────────────────────────────────────────────
# LaTeX helpers
# ──────────────────────────────────────────────────────────────────────────────

def _escape_latex(text: str) -> str:
    """Escape LaTeX special characters in plain text values."""
    if not text:
        return ""
    text = text.replace("\\", "\\textbackslash{}")
    text = text.replace("&", "\\&")
    text = text.replace("%", "\\%")
    text = text.replace("$", "\\$")
    text = text.replace("#", "\\#")
    text = text.replace("_", "\\_")
    text = text.replace("{", "\\{")
    text = text.replace("}", "\\}")
    text = text.replace("~", "\\textasciitilde{}")
    text = text.replace("^", "\\textasciicircum{}")
    return text


def _coerce_dict(val) -> dict:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = _json.loads(val)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _coerce_list(val) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = _json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


# ──────────────────────────────────────────────────────────────────────────────
# Section builders — each produces a LaTeX section string or "" if no data
# ──────────────────────────────────────────────────────────────────────────────

def _build_header(header: dict) -> str:
    """Build the centered header block."""
    if not isinstance(header, dict):
        header = {}
    name = _escape_latex(header.get("name", ""))
    parts = []

    phone = header.get("phone", "")
    if phone:
        parts.append(f"\\small \\faPhone\\ {_escape_latex(phone)}")

    email = header.get("email", "")
    if email:
        parts.append(f"\\href{{mailto:{email}}}{{\\faEnvelope\\ {_escape_latex(email)}}}")

    linkedin_url = header.get("linkedin_url", "")
    linkedin_display = header.get("linkedin_display", "")
    if linkedin_url and linkedin_display:
        parts.append(f"\\href{{{linkedin_url}}}{{\\faLinkedin\\ {_escape_latex(linkedin_display)}}}")

    github_url = header.get("github_url", "")
    github_display = header.get("github_display", "")
    if github_url and github_display:
        parts.append(f"\\href{{{github_url}}}{{\\faGithub\\ {_escape_latex(github_display)}}}")

    website_url = header.get("website_url", "")
    website_display = header.get("website_display", "")
    # Skip website if it's a GitHub URL (already shown above) to avoid duplicates
    if website_url and website_display and "github.com" not in website_url.lower():
        parts.append(f"\\href{{{website_url}}}{{\\faGlobe\\ {_escape_latex(website_display)}}}")

    contact_line = " \\quad\n    ".join(parts)

    return (
        "\\begin{center}\n"
        f"    \\textbf{{\\Huge \\scshape {name}}} \\\\ \\vspace{{1pt}}\n"
        f"    {contact_line}\n"
        "\\end{center}"
    )


def _build_summary(summary: str) -> str:
    """Build the Professional Summary section."""
    if not summary or not summary.strip():
        return ""
    return (
        "\\section{Professional Summary}\n"
        f"\\small {_escape_latex(summary.strip())}"
    )


def _build_education(education: list) -> str:
    """Build the Education section."""
    if not education or not isinstance(education, list):
        return ""
    entries = []
    for edu in education:
        if not isinstance(edu, dict):
            continue
        school = _escape_latex(edu.get("school", ""))
        metric = _escape_latex(edu.get("metric", ""))
        degree = _escape_latex(edu.get("degree", ""))
        dates = _escape_latex(edu.get("dates", ""))
        entries.append(
            f"  \\resumeSubheading\n"
            f"    {{{school}}}{{{metric}}}\n"
            f"    {{{degree}}}{{{dates}}}"
        )
    if not entries:
        return ""
    body = "\n".join(entries)
    return (
        "\\section{Education}\n"
        "\\resumeSubHeadingListStart\n"
        f"{body}\n"
        "\\resumeSubHeadingListEnd"
    )


def _build_experience(experience: list) -> str:
    """Build the Experience section."""
    if not experience or not isinstance(experience, list):
        return ""
    entries = []
    for exp in experience:
        if not isinstance(exp, dict):
            continue
        title = _escape_latex(exp.get("title", ""))
        dates = _escape_latex(exp.get("dates", ""))
        company = _escape_latex(exp.get("company", ""))
        location = _escape_latex(exp.get("location", ""))
        items = ""
        highlights = [h for h in exp.get("highlights", []) if isinstance(h, str) and h.strip()]
        if highlights:
            bullet_lines = "\n".join(
                f"      \\resumeItem{{{_escape_latex(h)}}}" for h in highlights
            )
            items = (
                f"\n    \\resumeItemListStart\n"
                f"{bullet_lines}\n"
                f"    \\resumeItemListEnd"
            )
        entries.append(
            f"  \\resumeSubheading\n"
            f"    {{{title}}}{{{dates}}}\n"
            f"    {{{company}}}{{{location}}}"
            f"{items}"
        )
    if not entries:
        return ""
    # Add \vspace{6pt} between experience entries for visual breathing room
    body = "\n\n  \\vspace{6pt}\n".join(entries)
    return (
        "\\section{Experience}\n"
        "\\resumeSubHeadingListStart\n\n"
        f"{body}\n\n"
        "\\resumeSubHeadingListEnd"
    )


def _build_projects(projects: list) -> str:
    """Build the Projects section."""
    if not projects or not isinstance(projects, list):
        return ""
    entries = []
    for proj in projects:
        if not isinstance(proj, dict):
            continue
        name = _escape_latex(proj.get("name", ""))
        url = proj.get("url", "")
        techs = _escape_latex(proj.get("technologies", ""))

        if url:
            heading = f"\\textbf{{\\href{{{url}}}{{\\faGithub\\ {name}}}}} $|$ \\emph{{{techs}}}"
        else:
            heading = f"\\textbf{{{name}}} $|$ \\emph{{{techs}}}"

        items = ""
        highlights = [h for h in proj.get("highlights", []) if isinstance(h, str) and h.strip()]
        if highlights:
            bullet_lines = "\n".join(
                f"      \\resumeItem{{{_escape_latex(h)}}}" for h in highlights
            )
            items = (
                f"\n    \\resumeItemListStart\n"
                f"{bullet_lines}\n"
                f"    \\resumeItemListEnd"
            )
        entries.append(
            f"  \\resumeProjectHeading\n"
            f"    {{{heading}}}{{}}"
            f"{items}"
        )
    if not entries:
        return ""
    body = "\n\n".join(entries)
    return (
        "\\section{Projects}\n"
        "\\resumeSubHeadingListStart\n\n"
        f"{body}\n\n"
        "\\resumeSubHeadingListEnd"
    )


def _build_skills(skills: list) -> str:
    """Build the Technical Skills section."""
    if not skills or not isinstance(skills, list):
        return ""
    skill_lines = []
    for i, skill in enumerate(skills):
        if not isinstance(skill, dict):
            continue
        cat = _escape_latex(skill.get("category", ""))
        items = _escape_latex(skill.get("items", ""))
        suffix = " \\\\" if i < len(skills) - 1 else ""
        skill_lines.append(f"    \\textbf{{{cat}}}{{: {items}}}{suffix}")
    if not skill_lines:
        return ""
    body = "\n".join(skill_lines)
    return (
        "\\section{Technical Skills}\n"
        "\\begin{itemize}[leftmargin=0.15in, label={}]\n"
        "  \\small{\\item{\n"
        f"{body}\n"
        "  }}\n"
        "\\end{itemize}"
    )


def _build_achievements(achievements: list) -> str:
    """Build the Achievements section (only if data provided)."""
    if not achievements:
        return ""
    achievements = [a for a in achievements if isinstance(a, str) and a.strip()]
    if not achievements:
        return ""
    bullet_lines = "\n".join(
        f"  \\resumeItem{{{_escape_latex(a)}}}" for a in achievements
    )
    return (
        "\\section{Achievements}\n"
        "\\resumeItemListStart\n"
        f"{bullet_lines}\n"
        "\\resumeItemListEnd"
    )


def _validate_and_fix_resume_data(data: dict) -> dict:
    """Validate Claude's JSON output and fix common issues before template fill.

    Fixes:
    - Education entries missing required fields
    - Experience entries missing highlights
    - Bullet points outside the 90-115 char range (truncates or logs warnings)
    - Skill categories with too many items (caps at 8)
    """
    # Education validation
    for edu in _coerce_list(data.get("education", [])):
        if not isinstance(edu, dict):
            continue
        # Ensure all 4 fields exist
        for field in ("school", "metric", "degree", "dates"):
            if field not in edu:
                edu[field] = ""

    # Experience validation — ensure highlights exist
    for exp in _coerce_list(data.get("experience", [])):
        if not isinstance(exp, dict):
            continue
        for field in ("title", "dates", "company"):
            if field not in exp:
                exp[field] = ""
        if "highlights" not in exp or not exp["highlights"]:
            logger.warning(
                "Experience entry missing highlights",
                title=exp.get("title", ""),
                company=exp.get("company", ""),
            )
            exp["highlights"] = []

    # Bullet length enforcement for projects and experience (strict 95-110 chars)
    def _enforce_bullet_length(highlights: list, section_name: str) -> list:
        fixed = []
        for bullet in highlights:
            if not isinstance(bullet, str) or not bullet.strip():
                continue
            bullet = bullet.strip()
            length = len(bullet)
            if length > 110:
                # Truncate at last word boundary at or before 108 chars
                truncated = bullet[:108]
                last_space = truncated.rfind(" ")
                if last_space > 80:
                    truncated = truncated[:last_space]
                bullet = truncated.rstrip(",;:- ")
                logger.warning(
                    "Truncated long bullet",
                    section=section_name,
                    original_len=length,
                    new_len=len(bullet),
                )
            elif length < 95:
                logger.warning(
                    "Short bullet (under 95 chars) — Claude should have written longer",
                    section=section_name,
                    bullet_len=length,
                    bullet_preview=bullet[:60],
                )
            fixed.append(bullet)
        return fixed

    for proj in _coerce_list(data.get("projects", [])):
        if isinstance(proj, dict) and "highlights" in proj:
            proj["highlights"] = _enforce_bullet_length(
                proj["highlights"], f"project:{proj.get('name', '?')}"
            )

    for exp in _coerce_list(data.get("experience", [])):
        if isinstance(exp, dict) and "highlights" in exp:
            exp["highlights"] = _enforce_bullet_length(
                exp["highlights"], f"experience:{exp.get('company', '?')}"
            )

    # Project name title-casing and tech stack minimum enforcement
    for proj in _coerce_list(data.get("projects", [])):
        if not isinstance(proj, dict):
            continue
        # Title-case project names (e.g. "career-forge" → "Career Forge", "sticky-net" → "Sticky Net")
        raw_name = proj.get("name", "")
        if raw_name:
            # Replace hyphens/underscores with spaces, then title-case each word
            spaced = raw_name.replace("-", " ").replace("_", " ")
            proj["name"] = " ".join(w.capitalize() for w in spaced.split())
        # Ensure technologies has at least 7 items
        techs_str = proj.get("technologies", "")
        if isinstance(techs_str, str):
            tech_items = [t.strip() for t in techs_str.split(",") if t.strip()]
            if len(tech_items) < 7:
                logger.warning(
                    "Project tech stack has fewer than 7 items",
                    project=proj.get("name", ""),
                    count=len(tech_items),
                )

    # Skill category item count enforcement (max 8 items) + line length enforcement
    for skill in _coerce_list(data.get("skills", [])):
        if not isinstance(skill, dict):
            continue
        items_str = skill.get("items", "")
        category = skill.get("category", "")
        if isinstance(items_str, str):
            items_list = [i.strip() for i in items_str.split(",") if i.strip()]
            if len(items_list) > 8:
                logger.warning(
                    "Trimmed skill category item count",
                    category=category,
                    original_count=len(items_list),
                )
                items_list = items_list[:8]
            # Enforce max line length (~90 chars for category + items)
            max_line = 88
            while items_list:
                line = f"{category}: {', '.join(items_list)}"
                if len(line) <= max_line:
                    break
                items_list = items_list[:-1]  # drop last item
                logger.warning(
                    "Trimmed skill line for length",
                    category=category,
                    new_count=len(items_list),
                )
            skill["items"] = ", ".join(items_list)

    return data


def _fill_jakes_template(data: dict) -> str:
    """Build a complete Jake's Resume LaTeX document from structured JSON data.

    Section order: Header → Summary → Education → Experience → Projects → Skills
    Achievements are included only if data is provided.

    Runs validation/sanitization on data before building LaTeX.
    """
    data = _validate_and_fix_resume_data(data)
    parts = [JAKES_PREAMBLE.strip(), "", "\\begin{document}", ""]

    # Header (always present)
    header = _coerce_dict(data.get("header", {}))
    parts.append(_build_header(header))

    # Professional Summary
    summary = _build_summary(data.get("professional_summary", ""))
    if summary:
        parts.append(summary)

    # Education
    edu = _build_education(_coerce_list(data.get("education", [])))
    if edu:
        parts.append(edu)

    # Experience
    exp = _build_experience(_coerce_list(data.get("experience", [])))
    if exp:
        parts.append(exp)

    # Projects
    proj = _build_projects(_coerce_list(data.get("projects", [])))
    if proj:
        parts.append(proj)

    # Technical Skills
    skills = _build_skills(_coerce_list(data.get("skills", [])))
    if skills:
        parts.append(skills)

    # Achievements (optional — only if data exists)
    ach = _build_achievements(_coerce_list(data.get("achievements", [])))
    if ach:
        parts.append(ach)

    parts.append("\\end{document}")
    return "\n\n".join(parts) + "\n"


# ──────────────────────────────────────────────────────────────────────────────
# S3 helpers
# ──────────────────────────────────────────────────────────────────────────────

async def list_project_summaries(user_id: str) -> List[str]:
    """List and download all project summary .md files from S3 for a user."""
    from app.services.s3_service import s3_service

    all_keys = await s3_service.list_objects(prefix=f"{user_id}/")
    summary_keys = [k for k in all_keys if k.endswith("-summary.md") or k.endswith("_summary.md")]

    if not summary_keys:
        summary_keys = [k for k in all_keys if k.endswith(".md")]

    if not summary_keys:
        return []

    summaries = []
    for key in summary_keys:
        try:
            content_bytes = await s3_service.download_file(key)
            summaries.append(content_bytes.decode("utf-8"))
        except Exception as e:
            logger.warning("Failed to download summary", key=key, error=str(e))

    return summaries


# ──────────────────────────────────────────────────────────────────────────────
# Main generation pipeline
# ──────────────────────────────────────────────────────────────────────────────

def _check_page_count(log: str) -> int:
    """Extract page count from pdflatex log. Returns 1 if undetermined."""
    match = re.search(r'Output written on .+?\((\d+) page', log)
    if match:
        return int(match.group(1))
    return 1


def _trim_resume_for_one_page(data: dict, attempt: int) -> dict:
    """Reduce resume content to fit on one page.

    attempt=1: remove last bullet from each project, shorten summary to 3 sentences.
    attempt=2: also remove last bullet from each experience role, drop achievements.
    """
    import copy
    data = copy.deepcopy(data)

    if attempt >= 1:
        for proj in _coerce_list(data.get("projects", [])):
            if isinstance(proj, dict) and len(proj.get("highlights", [])) > 2:
                proj["highlights"] = proj["highlights"][:-1]
        summary = data.get("professional_summary", "")
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', summary) if s.strip()]
        if len(sentences) > 3:
            data["professional_summary"] = " ".join(sentences[:3])

    if attempt >= 2:
        for exp in _coerce_list(data.get("experience", [])):
            if isinstance(exp, dict) and len(exp.get("highlights", [])) > 2:
                exp["highlights"] = exp["highlights"][:-1]
        data["achievements"] = []

    return data


async def _expand_short_bullets(resume_data: dict) -> dict:
    """Second-pass AI call: expand any bullet < 95 chars to the 95–110 char range."""
    import copy

    # Collect short bullets with location paths
    short_items = []  # {"path_type": "projects"|"experience", "sec_idx": int, "bul_idx": int, "text": str, "context": str}

    for i, proj in enumerate(_coerce_list(resume_data.get("projects", []))):
        if not isinstance(proj, dict):
            continue
        name = proj.get("name", f"Project {i}")
        for j, bullet in enumerate(proj.get("highlights", [])):
            if isinstance(bullet, str) and len(bullet.strip()) < 95:
                short_items.append({"path_type": "projects", "sec_idx": i, "bul_idx": j,
                                    "text": bullet.strip(), "context": f"Project: {name}"})

    for i, exp in enumerate(_coerce_list(resume_data.get("experience", []))):
        if not isinstance(exp, dict):
            continue
        role = f"{exp.get('title', '')} at {exp.get('company', '')}" .strip(" at")
        for j, bullet in enumerate(exp.get("highlights", [])):
            if isinstance(bullet, str) and len(bullet.strip()) < 95:
                short_items.append({"path_type": "experience", "sec_idx": i, "bul_idx": j,
                                    "text": bullet.strip(), "context": f"Role: {role}"})

    if not short_items:
        logger.info("All bullets meet 95-char minimum — no expansion needed")
        return resume_data

    logger.info("Expanding short bullets via second AI pass", count=len(short_items))

    bullets_text = ""
    for idx, item in enumerate(short_items, 1):
        bullets_text += f'{idx}. [{item["context"]}] "{item["text"]}" ({len(item["text"])} chars)\n'

    expand_prompt = f"""Expand each resume bullet point to be between 95 and 110 characters.

Rules:
- Each expanded bullet MUST be exactly 95-110 characters (count carefully before outputting)
- Add specific technical details, metrics, tools, or methodology to reach the minimum
- Preserve the core meaning — do NOT invent new facts or outcomes
- Return ONLY a valid JSON array in exactly this format:
[
  {{"original": "<original text>", "expanded": "<expanded text>"}},
  ...
]

Bullets to expand:
{bullets_text}"""

    try:
        response = await bedrock_client.generate(
            prompt=expand_prompt,
            system_prompt="You are a resume bullet point expander. Return ONLY a valid JSON array where each element has \"original\" and \"expanded\" keys. No prose, no markdown fences.",
            max_tokens=2048,
            temperature=0.2,
        )

        # Extract JSON array from response
        json_match = re.search(r'\[.*?\]', response, re.DOTALL)
        if not json_match:
            logger.warning("Bullet expansion: could not parse JSON from response")
            return resume_data

        expansions = _json.loads(json_match.group(0))

        # Build original-text → expanded-text map
        expansion_map: dict[str, str] = {}
        for item in expansions:
            if isinstance(item, dict) and "original" in item and "expanded" in item:
                original = item["original"].strip()
                expanded = item["expanded"].strip()
                # Only accept if expansion actually meets the minimum
                if len(expanded) >= 90:
                    expansion_map[original] = expanded
                else:
                    logger.warning("Expanded bullet still too short", text=expanded[:60], length=len(expanded))

        # Apply expansions back into a deep copy of resume_data
        data = copy.deepcopy(resume_data)

        for proj in _coerce_list(data.get("projects", [])):
            if not isinstance(proj, dict):
                continue
            proj["highlights"] = [
                expansion_map.get(b.strip(), b) if isinstance(b, str) else b
                for b in proj.get("highlights", [])
            ]

        for exp in _coerce_list(data.get("experience", [])):
            if not isinstance(exp, dict):
                continue
            exp["highlights"] = [
                expansion_map.get(b.strip(), b) if isinstance(b, str) else b
                for b in exp.get("highlights", [])
            ]

        logger.info("Bullet expansion complete", replaced=len(expansion_map))
        return data

    except Exception as exc:
        logger.warning("Bullet expansion failed — using original data", error=str(exc))
        return resume_data


async def generate_resume_from_summaries(
    user_id: str,
    jd: Optional[str] = None,
    personal_info: Optional[Dict[str, Any]] = None,
    education: Optional[List[Dict[str, Any]]] = None,
    experience: Optional[List[Dict[str, Any]]] = None,
    skills: Optional[List[str]] = None,
    certifications: Optional[List[Dict[str, Any]]] = None,
    achievements: Optional[List[str]] = None,
) -> M2GenerationResult:
    """
    Full pipeline: S3 summaries → Claude analysis + JSON → template fill → compile → upload.

    Args:
        user_id: User ID whose summaries to read
        jd: Optional job description text
        personal_info: Dict with name, email, phone, linkedin_url, website, github
        education: List of education dicts
        experience: List of experience dicts
        skills: List of skill strings
        certifications: List of cert dicts
        achievements: List of achievement strings

    Returns:
        M2GenerationResult with latex, analysis, and URLs
    """
    from app.services.s3_service import s3_service
    from app.services.latex_service import latex_service
    from app.services.dynamo_service import dynamo_service

    # 1. Retrieve all project summaries from S3
    summaries = await list_project_summaries(user_id)
    if not summaries:
        raise ValueError("No project summaries found. Run GitHub ingestion first.")

    logger.info("Retrieved project summaries", user_id=user_id, count=len(summaries))

    # 2. Check analysis cache
    cache_key = _cache_key(summaries, jd, experience)
    cached = _analysis_cache.get(cache_key)

    if cached:
        logger.info("Using cached analysis", cache_key=cache_key)
        analysis = cached["analysis"]
        resume_data = cached["resume_data"]
    else:
        # 3. Build context and call Claude
        analysis, resume_data = await _call_claude_for_resume(
            summaries=summaries,
            jd=jd,
            personal_info=personal_info,
            education=education,
            experience=experience,
            skills=skills,
            certifications=certifications,
            achievements=achievements,
        )

        # Cache the result (limit cache size to 50 entries)
        if len(_analysis_cache) >= 50:
            oldest_key = next(iter(_analysis_cache))
            del _analysis_cache[oldest_key]
        _analysis_cache[cache_key] = {"analysis": analysis, "resume_data": resume_data}

    # 3b. Expand any bullets that are under 95 chars via targeted AI pass
    resume_data = await _expand_short_bullets(resume_data)

    # 4. Build LaTeX from JSON
    latex_content = _fill_jakes_template(resume_data)
    logger.info("Template filled", latex_len=len(latex_content))

    # 5. Compile LaTeX → PDF (with 1-page enforcement: up to 2 trim retries)
    resume_id = dynamo_service.generate_id()
    output_filename = f"resume_{resume_id[:8]}"

    compilation_result = await latex_service.compile_latex(
        latex_content=latex_content,
        output_filename=output_filename,
        use_docker=False,
    )

    # 1-page enforcement: if compiled PDF has > 1 page, trim and recompile
    if compilation_result.success:
        page_count = _check_page_count(compilation_result.log)
        for trim_attempt in range(1, 3):
            if page_count <= 1:
                break
            logger.warning(
                "Resume exceeds 1 page — trimming",
                page_count=page_count,
                attempt=trim_attempt,
            )
            trimmed_data = _trim_resume_for_one_page(resume_data, trim_attempt)
            latex_content = _fill_jakes_template(trimmed_data)
            output_filename_trimmed = f"{output_filename}_t{trim_attempt}"
            compilation_result = await latex_service.compile_latex(
                latex_content=latex_content,
                output_filename=output_filename_trimmed,
                use_docker=False,
            )
            if compilation_result.success:
                page_count = _check_page_count(compilation_result.log)
                resume_data = trimmed_data
                logger.info("Recompiled after trim", page_count=page_count, attempt=trim_attempt)
            else:
                break

    pdf_url = None
    tex_url = None

    # 6. Upload to S3
    pdf_s3_key = f"{user_id}/resumes/{resume_id}.pdf"
    tex_s3_key = f"{user_id}/resumes/{resume_id}.tex"

    await s3_service.upload_file(
        key=tex_s3_key,
        data=latex_content.encode("utf-8"),
        content_type="text/plain",
    )
    tex_url = await s3_service.get_presigned_url(tex_s3_key)

    if compilation_result.success and compilation_result.pdf_path:
        from pathlib import Path
        pdf_bytes = Path(compilation_result.pdf_path).read_bytes()
        await s3_service.upload_file(
            key=pdf_s3_key,
            data=pdf_bytes,
            content_type="application/pdf",
        )
        pdf_url = await s3_service.get_presigned_url(pdf_s3_key)
        compilation_error_msg = None
    else:
        compilation_error_msg = _extract_compilation_error(compilation_result)
        logger.warning("LaTeX compilation failed", error=compilation_error_msg)

    # 7. Store resume metadata in DynamoDB
    now = dynamo_service.now_iso()
    resume_item = {
        "userId": user_id,
        "resumeId": resume_id,
        "name": f"Resume {now[:10]}",
        "status": "compiled" if compilation_result.success else "generated",
        "latexContent": latex_content,
        "analysis": analysis,
        "pdfS3Key": pdf_s3_key if compilation_result.success else None,
        "texS3Key": tex_s3_key,
        "jobDescription": jd[:500] if jd else None,
        "errorMessage": compilation_error_msg,
        "createdAt": now,
        "updatedAt": now,
    }
    await dynamo_service.put_item("Resumes", resume_item)

    return M2GenerationResult(
        latex_content=latex_content,
        analysis=analysis,
        resume_id=resume_id,
        pdf_url=pdf_url,
        tex_url=tex_url,
        compilation_error=compilation_error_msg,
    )


async def _call_claude_for_resume(
    summaries: List[str],
    jd: Optional[str],
    personal_info: Optional[Dict[str, Any]],
    education: Optional[List[Dict[str, Any]]],
    experience: Optional[List[Dict[str, Any]]],
    skills: Optional[List[str]],
    certifications: Optional[List[Dict[str, Any]]],
    achievements: Optional[List[str]] = None,
) -> tuple:
    """Call Claude with all context and return (analysis, resume_data) tuple."""

    # Build context
    projects_context = "\n\n---\n\n".join(summaries)

    extra_context_parts = []
    if personal_info:
        info_lines = [f"  {k}: {v}" for k, v in personal_info.items() if v]
        if info_lines:
            extra_context_parts.append("## Personal Information\n" + "\n".join(info_lines))

    if education:
        edu_lines = []
        for i, edu in enumerate(education, 1):
            # Normalize field names (frontend sends graduation_date, backend expects dates)
            school = edu.get('school', '') or edu.get('institution', '') or ''
            degree = edu.get('degree', '') or ''
            field = edu.get('field', '') or edu.get('field_of_study', '') or ''
            dates = edu.get('dates', '') or ''
            # Frontend may send start_date/end_date or graduation_date instead of dates
            if not dates:
                grad_date = edu.get('graduation_date', '') or edu.get('graduation_year', '') or ''
                start_date = edu.get('start_date', '') or ''
                end_date = edu.get('end_date', '') or grad_date
                if start_date and end_date:
                    dates = f"{start_date} -- {end_date}"
                elif end_date:
                    dates = f"Expected {end_date}" if end_date else ''
            gpa = edu.get('gpa', '') or edu.get('cgpa', '') or ''
            location = edu.get('location', '') or ''

            degree_str = f"{degree} in {field}" if field else degree
            edu_lines.append(f"  Education {i}:")
            edu_lines.append(f"    School: {school}")
            edu_lines.append(f"    Degree: {degree_str}")
            edu_lines.append(f"    Dates: {dates}")
            if gpa:
                edu_lines.append(f"    GPA/CGPA: {gpa}")
            if location:
                edu_lines.append(f"    Location: {location}")
        if edu_lines:
            extra_context_parts.append("## Education\n" + "\n".join(edu_lines))

    if experience:
        exp_lines = []
        for i, exp in enumerate(experience, 1):
            title = exp.get('title', '') or ''
            company = exp.get('company', '') or ''
            # Normalize dates — frontend may send start_date/end_date
            dates = exp.get('dates', '') or ''
            if not dates:
                start = exp.get('start_date', '') or ''
                end = exp.get('end_date', '') or 'Present'
                if start:
                    dates = f"{start} -- {end}"
            location = exp.get('location', '') or ''
            exp_lines.append(f"  Experience {i}:")
            exp_lines.append(f"    Title: {title}")
            exp_lines.append(f"    Company: {company}")
            exp_lines.append(f"    Dates: {dates}")
            if location:
                exp_lines.append(f"    Location: {location}")
            highlights = exp.get('highlights', []) or []
            if highlights:
                exp_lines.append("    Key Contributions:")
                for h in highlights:
                    exp_lines.append(f"      - {h}")
            else:
                exp_lines.append("    (No detailed highlights provided — generate 3-4 bullets based on role context and user's known skills)")
        if exp_lines:
            extra_context_parts.append("## Work Experience\n" + "\n".join(exp_lines))

    if skills:
        extra_context_parts.append(f"## Technical Skills\n  {', '.join(skills)}")

    if certifications:
        cert_lines = [f"  - {c.get('name', '')} ({c.get('issuer', '')})" for c in certifications if isinstance(c, dict)]
        if cert_lines:
            extra_context_parts.append("## Certifications\n" + "\n".join(cert_lines))

    if achievements:
        ach_list = [a for a in achievements if isinstance(a, str) and a.strip()]
        if ach_list:
            ach_lines = "\n".join(f"  - {a}" for a in ach_list)
            extra_context_parts.append("## Achievements\n" + ach_lines)

    extra_context = "\n\n".join(extra_context_parts)

    # Experience hint for project count
    has_experience = bool(experience and len(experience) > 0)
    experience_hint = (
        "The user HAS work experience — select 3 projects."
        if has_experience
        else "The user has NO work experience — select 4 projects to compensate."
    )

    user_message = f"""## Project Summaries (from ingested GitHub repos)

{projects_context}

{extra_context}

## Job Description
{jd or 'No JD provided — generate a strong base resume ranking projects by complexity and recency.'}

## Important Context
{experience_hint}

Perform Step 0 analysis first (gap check → JD keyword extraction → project ranking table → project count decision → fact validation), then output the resume JSON."""

    # Call Claude
    response = await bedrock_client.generate(
        prompt=user_message,
        system_prompt=RESUME_JSON_PROMPT,
        max_tokens=8192,
        temperature=0.3,
    )

    response = response.replace('\r\n', '\n').replace('\r', '\n')

    # Parse response
    analysis = ""
    analysis_match = re.search(r"<analysis>(.*?)</analysis>", response, re.DOTALL)
    if analysis_match:
        analysis = analysis_match.group(1).strip()

    json_match = re.search(r"<resume_json>\s*(.*?)\s*</resume_json>", response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        md_match = re.search(r"```(?:json)?\s*\n(.*?)```", response, re.DOTALL)
        if md_match:
            json_str = md_match.group(1).strip()
        else:
            raise ValueError("Failed to extract resume JSON from Claude's response.")

    try:
        resume_data = _json.loads(json_str)
    except _json.JSONDecodeError as e:
        logger.error("Failed to parse resume JSON", error=str(e), json_preview=json_str[:500])
        raise ValueError(f"Claude returned invalid JSON: {e}")

    logger.info("Claude generation complete", analysis_len=len(analysis), keys=list(resume_data.keys()))
    return analysis, resume_data


def _extract_compilation_error(compilation_result) -> str:
    """Extract a readable error message from compilation result."""
    log_text = getattr(compilation_result, "log", "") or ""
    log_lines = log_text.splitlines()

    error_snippets: list[str] = []
    for i, line in enumerate(log_lines):
        stripped = line.strip()
        if stripped.startswith("! "):
            snippet = stripped
            for j in range(i + 1, min(i + 4, len(log_lines))):
                next_line = log_lines[j].strip()
                if next_line:
                    snippet += f"  →  {next_line}"
                    break
            error_snippets.append(snippet)
            if len(error_snippets) >= 3:
                break

    if error_snippets:
        return " | ".join(error_snippets)
    elif compilation_result.errors:
        return compilation_result.errors[0].message
    else:
        return "PDF compilation failed — LaTeX source saved."


# ──────────────────────────────────────────────────────────────────────────────
# Legacy M1 compatibility — kept for /{resume_id}/generate route
# ──────────────────────────────────────────────────────────────────────────────

_LEGACY_SYSTEM_PROMPT = r"""You are a professional resume LaTeX formatter. Your ONLY job is to fill a LaTeX template with provided user data.

CRITICAL RULES:
1. ONLY use information from <user_data>. NEVER invent facts.
2. If data is missing, omit that section entirely.
3. Resume MUST fit on ONE PAGE. Each project: EXACTLY 3 bullet points (80-100 chars each).
4. Use ONLY \textbf{}, \textit{}, \texttt{} for fonts. Never old-style commands.
5. Every { must have matching }. Escape special chars: & % $ # _ { } ~ ^
6. Return ONLY valid LaTeX code."""


class ResumeGenerationAgent:
    """Legacy agent for M1 template-fill flow. Kept for backward compatibility."""

    def __init__(self):
        pass

    async def generate_resume(
        self,
        template_latex: str,
        user_data: Dict[str, Any],
        jd_context: Optional[Dict[str, Any]] = None,
        temperature: float = 0.2,
    ) -> GenerationResult:
        user_data_str = self._format_user_data(user_data)

        jd_str = ""
        if jd_context:
            jd_str = (
                f"\n<jd_context>\nTarget Role: {jd_context.get('title', 'N/A')}\n"
                f"Company: {jd_context.get('company', 'N/A')}\n"
                f"Key Requirements: {', '.join(jd_context.get('required_skills', [])[:10])}\n"
                f"</jd_context>\n"
            )

        prompt = (
            f"Fill this LaTeX resume template with the provided user data.\n\n"
            f"<template>\n{template_latex}\n</template>\n\n"
            f"<user_data>\n{user_data_str}\n</user_data>\n\n"
            f"{jd_str}\n"
            f"Return ONLY the filled LaTeX code."
        )

        try:
            response = await bedrock_client.generate_content(
                prompt=prompt,
                system_instruction=_LEGACY_SYSTEM_PROMPT,
                temperature=temperature,
                max_tokens=8192,
            )

            latex_content = response.strip()
            if latex_content.startswith("```latex"):
                latex_content = latex_content[8:]
            elif latex_content.startswith("```"):
                latex_content = latex_content[3:]
            if latex_content.endswith("```"):
                latex_content = latex_content[:-3]
            latex_content = latex_content.strip()

            return GenerationResult(
                latex_content=latex_content,
                warnings=[],
                changes_made=["Filled template with user data"],
                tokens_used=len(response.split()),
            )
        except Exception as e:
            logger.error(f"Legacy resume generation failed: {e}")
            raise

    def _format_user_data(self, user_data: Dict[str, Any]) -> str:
        parts = []
        if "personal" in user_data:
            parts.append("PERSONAL INFORMATION:")
            for key, value in user_data["personal"].items():
                parts.append(f"  {key}: {value}")
        if "skills" in user_data:
            parts.append(f"\nSKILLS: {', '.join(user_data['skills'])}")
        if "projects" in user_data:
            parts.append("\nPROJECTS:")
            for i, proj in enumerate(user_data["projects"], 1):
                parts.append(f"\n  Project {i}:")
                parts.append(f"    Title: {proj.get('title', 'N/A')}")
                parts.append(f"    Description: {proj.get('description', 'N/A')}")
                if proj.get("technologies"):
                    parts.append(f"    Technologies: {', '.join(proj['technologies'])}")
                if proj.get("highlights"):
                    parts.append("    Achievements:")
                    for h in proj["highlights"]:
                        parts.append(f"      - {h}")
                if proj.get("url"):
                    parts.append(f"    URL: {proj['url']}")
        if "experience" in user_data and user_data["experience"]:
            parts.append("\nWORK EXPERIENCE:")
            for i, exp in enumerate(user_data["experience"], 1):
                parts.append(f"\n  Experience {i}:")
                parts.append(f"    Company: {exp.get('company', 'N/A')}")
                parts.append(f"    Title: {exp.get('title', 'N/A')}")
                parts.append(f"    Dates: {exp.get('dates', 'N/A')}")
                if exp.get("highlights"):
                    parts.append("    Responsibilities:")
                    for h in exp["highlights"]:
                        parts.append(f"      - {h}")
        if "education" in user_data and user_data["education"]:
            parts.append("\nEDUCATION:")
            for i, edu in enumerate(user_data["education"], 1):
                parts.append(f"\n  Education {i}:")
                parts.append(f"    School: {edu.get('school', 'N/A')}")
                parts.append(f"    Degree: {edu.get('degree', 'N/A')}")
                if edu.get('field'):
                    parts.append(f"    Field: {edu.get('field')}")
                parts.append(f"    Dates: {edu.get('dates', 'N/A')}")
                if edu.get('gpa'):
                    parts.append(f"    GPA: {edu.get('gpa')}")
        if "certifications" in user_data and user_data["certifications"]:
            parts.append("\nCERTIFICATIONS:")
            for cert in user_data["certifications"]:
                parts.append(f"  - {cert.get('name', 'N/A')} ({cert.get('issuer', '')})")
        return "\n".join(parts)


# Global instance (for legacy route compatibility)
resume_agent = ResumeGenerationAgent()
