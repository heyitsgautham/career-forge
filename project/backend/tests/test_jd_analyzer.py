"""Job description analysis: LLM path, normalisation and keyword fallback."""

import pytest

from app.services import jd_analyzer as jd_module
from app.services.jd_analyzer import JDAnalyzer

BACKEND_JD = (
    "We are hiring a backend engineer to build REST API services in Python and FastAPI "
    "on AWS with PostgreSQL and Docker. 3+ years of experience. This is an unpaid internship."
)


@pytest.fixture
def analyzer():
    return JDAnalyzer()


async def test_short_text_returns_empty_analysis(analyzer):
    result = await analyzer.analyze_single("too short")
    assert result["category"] == "Unknown"
    assert result["requiredSkills"] == []


async def test_llm_result_is_normalised(analyzer, monkeypatch):
    async def fake_generate_json(**kwargs):
        assert "FastAPI" in kwargs["prompt"]
        return {"category": "Backend SDE", "requiredSkills": "Python", "atsKeywords": None}

    monkeypatch.setattr(jd_module.bedrock_client, "generate_json", fake_generate_json)
    result = await analyzer.analyze_single(BACKEND_JD)
    assert result["category"] == "Backend SDE"
    assert result["requiredSkills"] == ["Python"]
    assert result["atsKeywords"] == []
    assert result["experienceLevel"] == "Unknown"
    assert result["isPaid"] is True


async def test_llm_failure_falls_back_to_keywords(analyzer, monkeypatch):
    async def broken(**kwargs):
        raise RuntimeError("throttled")

    monkeypatch.setattr(jd_module.bedrock_client, "generate_json", broken)
    result = await analyzer.analyze_single(BACKEND_JD)
    assert result["category"] == "Backend SDE"
    for skill in ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "REST API"]:
        assert skill in result["requiredSkills"]
    assert result["experienceLevel"] == "Mid / 2-5 years"
    assert result["isPaid"] is False


def test_fallback_does_not_duplicate_aliases(analyzer):
    result = analyzer._fallback_analysis(
        "postgres and postgresql, node and node.js, k8s kubernetes"
    )
    assert result["requiredSkills"].count("PostgreSQL") == 1
    assert result["requiredSkills"].count("Node.js") == 1
    assert result["requiredSkills"].count("Kubernetes") == 1


@pytest.mark.parametrize(
    "text,category,level",
    [
        ("Senior frontend engineer with react", "Frontend Developer", "Senior / 5+ years"),
        ("devops role running kubernetes clusters", "DevOps/SRE", "Entry / 0-2 years"),
        ("data science and machine learning", "ML Engineer", "Entry / 0-2 years"),
    ],
)
def test_fallback_infers_category_and_level(analyzer, text, category, level):
    result = analyzer._fallback_analysis(text)
    assert result["category"] == category
    assert result["experienceLevel"] == level


def test_ensure_list(analyzer):
    assert analyzer._ensure_list(["a"]) == ["a"]
    assert analyzer._ensure_list("a") == ["a"]
    assert analyzer._ensure_list(None) == []
