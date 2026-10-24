"""LaTeX rendering of structured resume data.

All names, schools and links below are synthetic.
"""

from app.services.resume_agent import _cache_key, _analysis_cache, clear_analysis_cache
from app.services.resume_latex import (
    _build_achievements,
    _build_education,
    _build_experience,
    _build_header,
    _build_projects,
    _build_skills,
    _build_summary,
    _coerce_dict,
    _coerce_list,
    _escape_latex,
    _fill_jakes_template,
)

SAMPLE = {
    "header": {
        "name": "Asha Example",
        "phone": "+91 90000 00000",
        "email": "asha@example.com",
        "github_url": "https://github.com/asha-example",
        "github_display": "asha-example",
        "linkedin_url": "https://linkedin.com/in/asha-example",
        "linkedin_display": "",
    },
    "professional_summary": "Backend engineer who ships FastAPI services & data pipelines.",
    "education": [
        {"school": "Example Institute", "metric": "CGPA 8.9", "degree": "B.Tech CSE", "dates": "2021 -- 2025"}
    ],
    "experience": [
        {
            "title": "Intern",
            "dates": "2024",
            "company": "Sample Labs",
            "location": "Remote",
            "highlights": ["Cut p95 latency by 40%", "  "],
        }
    ],
    "projects": [
        {"name": "job_scout", "url": "https://github.com/asha-example/job_scout", "technologies": "Python, AWS", "highlights": ["Ranks 500 jobs/day"]},
        {"name": "offline-tool", "technologies": "Go", "highlights": []},
    ],
    "skills": [
        {"category": "Languages", "items": "Python, C#"},
        {"category": "Cloud", "items": "AWS"},
    ],
    "achievements": ["Won a hackathon", 42, ""],
}


def test_escape_latex_escapes_special_characters():
    assert _escape_latex("50% & $5 #1 a_b") == r"50\% \& \$5 \#1 a\_b"
    assert _escape_latex("{x}") == r"\{x\}"
    assert _escape_latex("") == ""
    assert _escape_latex(None) == ""


def test_coerce_dict_and_list_accept_json_strings():
    assert _coerce_dict('{"a": 1}') == {"a": 1}
    assert _coerce_dict("[1, 2]") == {}
    assert _coerce_dict("not json") == {}
    assert _coerce_dict(None) == {}
    assert _coerce_list("[1, 2]") == [1, 2]
    assert _coerce_list('{"a": 1}') == []
    assert _coerce_list(7) == []


def test_header_only_links_profiles_that_have_display_text():
    header = _build_header(SAMPLE["header"])
    assert r"\scshape Asha Example" in header
    assert r"\href{mailto:asha@example.com}" in header
    assert r"\faGithub\ asha-example" in header
    assert "linkedin.com" not in header


def test_header_tolerates_non_dict_input():
    assert r"\begin{center}" in _build_header("oops")


def test_empty_sections_render_nothing():
    assert _build_summary("   ") == ""
    assert _build_education([]) == ""
    assert _build_education(["not a dict"]) == ""
    assert _build_experience(None) == ""
    assert _build_projects("nope") == ""
    assert _build_skills([]) == ""
    assert _build_achievements(["", None]) == ""


def test_experience_drops_blank_highlights_and_escapes_text():
    section = _build_experience(SAMPLE["experience"])
    assert section.startswith(r"\section{Experience}")
    assert r"\resumeItem{Cut p95 latency by 40\%}" in section
    assert section.count(r"\resumeItem{") == 1


def test_projects_link_only_when_url_present():
    section = _build_projects(SAMPLE["projects"])
    assert r"\href{https://github.com/asha-example/job_scout}{\faGithub\ job\_scout}" in section
    assert r"\textbf{offline-tool} $|$ \emph{Go}" in section
    assert section.count(r"\resumeItemListStart") == 1


def test_skills_put_line_breaks_between_rows_only():
    section = _build_skills(SAMPLE["skills"])
    assert r"\textbf{Languages}{: Python, C\#} \\" in section
    assert r"\textbf{Cloud}{: AWS}" + "\n" in section


def test_achievements_keep_only_non_empty_strings():
    section = _build_achievements(SAMPLE["achievements"])
    assert section.count(r"\resumeItem{") == 1


def test_full_template_orders_sections():
    doc = _fill_jakes_template(SAMPLE)
    order = ["\\begin{document}", "Professional Summary", "{Education}", "{Experience}", "{Projects}", "Technical Skills", "{Achievements}", "\\end{document}"]
    positions = [doc.index(marker) for marker in order]
    assert positions == sorted(positions)
    assert doc.startswith(r"\documentclass")


def test_full_template_accepts_json_encoded_sections():
    import json

    data = {"header": json.dumps({"name": "Ravi Sample"}), "skills": json.dumps(SAMPLE["skills"])}
    doc = _fill_jakes_template(data)
    assert "Ravi Sample" in doc
    assert "Technical Skills" in doc
    assert "{Education}" not in doc


def test_cache_key_ignores_summary_order_and_experience_contents():
    a = _cache_key(["p1", "p2"], "jd", [{"title": "x"}])
    b = _cache_key(["p2", "p1"], "jd", [{"title": "y"}])
    assert a == b
    assert len(a) == 16
    assert a != _cache_key(["p1", "p2"], "jd", None)
    assert a != _cache_key(["p1", "p2"], "other jd", [{"title": "x"}])


def test_clear_analysis_cache_empties_cache():
    _analysis_cache["k"] = {"v": 1}
    clear_analysis_cache()
    assert _analysis_cache == {}
