"""The JD analysis steps degrade instead of failing the request."""

import asyncio

from app.services import jd_matching
from app.services.jd_matching import fallback_required_skills


def test_fallback_skills_are_substring_matches_capped_at_ten():
    text = "We use Python, React, AWS and Docker with REST APIs, SQL, Git, Node, GraphQL, TypeScript, Java"
    assert fallback_required_skills(text) == [
        "python",
        "java",
        "react",
        "node",
        "sql",
        "aws",
        "docker",
        "git",
        "api",
        "rest",
    ]
    assert fallback_required_skills("Cooking and gardening") == []


def test_each_step_returns_an_empty_result_when_its_service_is_down(monkeypatch):
    async def down(*_args, **_kwargs):
        raise RuntimeError("bedrock throttled")

    monkeypatch.setattr(jd_matching.matching_engine, "analyze_job_description", down)
    monkeypatch.setattr(jd_matching.embedding_service, "embed_text", down)

    assert asyncio.run(jd_matching.parse_requirements("text")) is None
    assert asyncio.run(jd_matching.store_embedding("u1", "t", "c", "text")) is None
    assert asyncio.run(jd_matching.match_projects("u1", "text", None, None, 5)) == []
