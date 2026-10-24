"""Helpers that turn a stored Job Scout job into the JD text sent to the tailor."""

from app.services.resume_tailor import _build_rich_jd, _safe_dict, _safe_list


def test_safe_dict_and_list_parse_json_and_fall_back():
    assert _safe_dict('{"a": 1}') == {"a": 1}
    assert _safe_dict("[1]") == {}
    assert _safe_dict("{bad") == {}
    assert _safe_dict(None, {"d": 1}) == {"d": 1}
    assert _safe_list('["x"]') == ["x"]
    assert _safe_list('{"a": 1}') == []
    assert _safe_list(5) == []


def test_rich_jd_includes_analysis_and_match_details():
    job = {
        "company": "Sample Labs",
        "title": "SDE Intern",
        "description": "Build APIs.",
        "requiredSkills": ["Python", "SQL"],
        "preferredSkills": '["Docker"]',
        "atsKeywords": ["REST"],
        "experienceLevel": "Entry / 0-2 years",
        "category": "SDE",
        "keyResponsibilities": ["a", "b", "c", "d", "e", "f"],
        "matchScore": 72,
        "matchBreakdown": '{"matchedSkills": ["Python"]}',
        "missingSkills": ["SQL"],
    }
    text = _build_rich_jd(job)
    lines = text.split("\n")
    assert lines[:3] == ["Company: Sample Labs", "Role: SDE Intern", "Location: Not specified"]
    assert "--- Job Description ---" in lines
    assert "Preferred Skills: Docker" in lines
    assert "Key Responsibilities: a, b, c, d, e" in lines
    assert "Match Score: 72%" in text
    assert "Matched Skills: Python" in lines
    assert "Missing Skills: SQL" in lines


def test_rich_jd_skips_empty_sections():
    text = _build_rich_jd({"title": "Data Intern", "rawText": ""})
    assert "Company: Unknown" in text
    assert "--- Job Description ---" not in text
    assert "Match Score" not in text
