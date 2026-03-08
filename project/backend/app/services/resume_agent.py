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
  "professional_summary": "2-3 sentence professional summary highlighting key strengths, technologies, and career focus. Tailored to the JD if provided. Must be grounded in actual data from summaries and profile.",
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
        "Bullet starting with strong action verb (Strictly Exactly 95-110 chars)",
        "Another bullet point with metrics"
      ]
    }
  ],
  "projects": [
    {
      "name": "Project Name",
      "url": "https://github.com/user/repo",
      "technologies": "Python, FastAPI, Docker, Next.js, GCP, RAG, Typescript",
      "highlights": [
        "First bullet MUST describe what the project does (Strictly Exactly 95-110 chars)",
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
  ]
}
```

## CRITICAL RULES

1. **ANTI-HALLUCINATION**: Only use data from the provided project summaries and user profile. Never fabricate metrics, experience, skills, or any facts not in the source data.
2. **ONE-PAGE FIT**: Resume MUST fit on a single letter-size page.
   - Max 3 bullet points per project (single line each, Strictly Exactly 95-110 chars)
   - Select 3-4 projects based on whether experience exists
   - Keep experience bullets to 3-4 per role (Strictly Exactly 95-110 chars each)
   - Professional summary: 2-3 concise sentences
3. **PLAIN TEXT ONLY**: All string values must be plain text. NO LaTeX commands (no \textbf, no \href, no \\, no \%). The template engine adds all formatting. The ONLY exception: use -- (double hyphen) for date ranges.
4. **PROFESSIONAL SUMMARY**: 
   - 2-3 sentences highlighting key strengths and career focus
   - Tailored to JD if provided (embed key JD terms naturally)
   - Must be grounded in actual skills/projects from the data
   - Start with role identity (e.g., "Software engineer with experience in...")
5. **BULLET POINTS**:
   - Start with strong action verbs (Developed, Architected, Implemented, Integrated, Optimized, Designed, Engineered, Built)
   - Use DIFFERENT action verbs for each bullet — never repeat within same section
   - Focus on technical implementation and architecture
   - Include specific technologies from the project
   - First bullet of each project MUST describe what the project does (product description, not tech stack)
   - At least 2 of 3 project bullets MUST contain quantifiable numbers (e.g., "98% reduction", "500+ users", "3 microservices")
   - Each bullet: Strictly Exactly 95-110 characters. Under 95 = too short, expand it
6. **EXPERIENCE HANDLING**:
   - If experience data is provided, include it and select 3 projects
   - If NO experience data, select 4 projects to compensate
   - Generate 3-4 bullets per experience role (Strictly Exactly 95-110 chars each)
   - Experience bullets must be based on provided experience data only
7. **SECTIONS ORDER**: Header → Professional Summary → Education → Experience (if provided) → Projects → Technical Skills
8. **OMIT EMPTY SECTIONS**: If no education/experience data available, use empty arrays []. Do not invent data.
9. **SKILL CATEGORIZATION**: Group skills into meaningful categories. Common categories: Languages, Frameworks, Databases, Developer Tools, Libraries, Other Skills, Certificates, Relevant Coursework.
   - Rewrite skills to match the JD — lead with JD-required skills
   - Include Relevant Coursework when it fills JD skill gaps
10. **VALID JSON**: Output must be valid JSON. Use double quotes for strings. Escape any double quotes inside strings with \".

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
    if website_url and website_display:
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
    body = "\n\n".join(entries)
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


def _fill_jakes_template(data: dict) -> str:
    """Build a complete Jake's Resume LaTeX document from structured JSON data.

    Section order: Header → Summary → Education → Experience → Projects → Skills
    Achievements are included only if data is provided.
    """
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

    # 4. Build LaTeX from JSON
    latex_content = _fill_jakes_template(resume_data)
    logger.info("Template filled", latex_len=len(latex_content))

    # 5. Compile LaTeX → PDF
    resume_id = dynamo_service.generate_id()
    output_filename = f"resume_{resume_id[:8]}"

    compilation_result = await latex_service.compile_latex(
        latex_content=latex_content,
        output_filename=output_filename,
        use_docker=False,
    )

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
            edu_lines.append(
                f"  Education {i}: {edu.get('degree', '')} in {edu.get('field', '')} "
                f"from {edu.get('school', '')} ({edu.get('dates', '')})"
            )
            if edu.get('gpa'):
                edu_lines.append(f"    GPA: {edu['gpa']}")
            if edu.get('location'):
                edu_lines.append(f"    Location: {edu['location']}")
        if edu_lines:
            extra_context_parts.append("## Education\n" + "\n".join(edu_lines))

    if experience:
        exp_lines = []
        for i, exp in enumerate(experience, 1):
            exp_lines.append(
                f"  Experience {i}: {exp.get('title', '')} at "
                f"{exp.get('company', '')} ({exp.get('dates', '')})"
            )
            for h in exp.get("highlights", []):
                exp_lines.append(f"    - {h}")
        if exp_lines:
            extra_context_parts.append("## Work Experience\n" + "\n".join(exp_lines))

    if skills:
        extra_context_parts.append(f"## Technical Skills\n  {', '.join(skills)}")

    if certifications:
        cert_lines = [f"  - {c.get('name', '')} ({c.get('issuer', '')})" for c in certifications if isinstance(c, dict)]
        if cert_lines:
            extra_context_parts.append("## Certifications\n" + "\n".join(cert_lines))

    if achievements:
        ach_lines = [f"  - {a}" for a in achievements if isinstance(a, str) and a.strip()]
        if ach_lines:
            extra_context_parts.append("## Achievements\n" + "\n".join(ach_lines))

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
