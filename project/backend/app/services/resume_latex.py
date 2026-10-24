"""
Resume LaTeX rendering
======================
Turns the structured resume JSON produced by the generation agent into a
complete Jake's Resume LaTeX document. Pure functions, no I/O.
"""

import json as _json

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

_LATEX_ESCAPES = {
    "\\": "\\textbackslash{}",
    "&": "\\&",
    "%": "\\%",
    "$": "\\$",
    "#": "\\#",
    "_": "\\_",
    "{": "\\{",
    "}": "\\}",
    "~": "\\textasciitilde{}",
    "^": "\\textasciicircum{}",
}


def _escape_latex(text: str) -> str:
    """Escape LaTeX special characters in plain text values.

    Works in one pass, so the braces in \\textbackslash{} are never escaped again.
    """
    if not text:
        return ""
    return "".join(_LATEX_ESCAPES.get(ch, ch) for ch in text)


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
        parts.append(
            f"\\href{{{linkedin_url}}}{{\\faLinkedin\\ {_escape_latex(linkedin_display)}}}"
        )

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
    return "\\section{Professional Summary}\n" f"\\small {_escape_latex(summary.strip())}"


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
            items = f"\n    \\resumeItemListStart\n" f"{bullet_lines}\n" f"    \\resumeItemListEnd"
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
            items = f"\n    \\resumeItemListStart\n" f"{bullet_lines}\n" f"    \\resumeItemListEnd"
        entries.append(f"  \\resumeProjectHeading\n" f"    {{{heading}}}{{}}" f"{items}")
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
    bullet_lines = "\n".join(f"  \\resumeItem{{{_escape_latex(a)}}}" for a in achievements)
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
