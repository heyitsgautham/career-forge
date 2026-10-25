"""Vector store and project matching engine against an in-memory Chroma."""

import pytest

from app.services.matching_engine import MatchScore, matching_engine
from app.services.vector_store import VectorStoreService

PROJECTS = VectorStoreService.COLLECTION_PROJECTS


async def add_project(store, pid, vector, technologies, document, user="u1"):
    await store.add_embedding(
        PROJECTS,
        pid,
        vector,
        {"user_id": user, "technologies": technologies, "stars": None, "extra": {"a": 1}},
        document,
    )


async def test_vector_store_round_trip(chroma):
    await add_project(chroma, "p1", [1.0, 0.0], ["Python", "FastAPI"], "fastapi service")
    stored = await chroma.get_by_id(PROJECTS, "p1")
    assert stored["metadata"] == {
        "user_id": "u1",
        "technologies": "Python,FastAPI",
        "extra": "{'a': 1}",
    }
    assert stored["embedding"] == pytest.approx([1.0, 0.0])

    await chroma.update_embedding(PROJECTS, "p1", [0.0, 1.0], {"user_id": "u1"}, "updated")
    assert (await chroma.get_by_id(PROJECTS, "p1"))["document"] == "updated"

    await chroma.delete_embedding(PROJECTS, "p1")
    assert await chroma.get_by_id(PROJECTS, "p1") is None


async def test_search_returns_similarity_for_the_users_projects_only(chroma):
    await add_project(chroma, "p1", [1.0, 0.0], ["Python"], "a")
    await add_project(chroma, "p2", [0.6, 0.8], ["React"], "b")
    await add_project(chroma, "theirs", [1.0, 0.0], ["Python"], "c", user="u2")
    results = await chroma.search_similar(
        PROJECTS, [1.0, 0.0], n_results=2, where={"user_id": "u1"}
    )
    assert [r["id"] for r in results] == ["p1", "p2"]
    assert results[0]["similarity"] == pytest.approx(1.0)
    assert results[1]["similarity"] == pytest.approx(0.6)


async def test_match_projects_blends_semantic_tech_and_keyword_scores(chroma):
    await add_project(
        chroma,
        "api",
        [1.0, 0.0],
        ["python", "fastapi", "docker"],
        "rest api with fastapi and postgres",
    )
    await add_project(chroma, "ui", [0.0, 1.0], ["react"], "a react dashboard")
    parsed = {
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["Docker"],
        "keywords": ["rest", "postgres"],
    }

    matches = await matching_engine.match_projects(
        "u1", "jd", jd_embedding=[1.0, 0.0], parsed_jd=parsed
    )
    assert matches[0].project_id == "api"
    top = matches[0]
    assert top.tech_overlap_score == 1.0
    assert top.keyword_score == 1.0
    assert top.total_score == pytest.approx(0.5 * 1 + 0.3 * 1 + 0.15 * 1 + 0.05 * 0.5)
    assert "Strong semantic relevance" in top.match_explanation
    assert "Excellent tech stack match" in top.match_explanation


async def test_match_projects_with_no_projects_is_empty(chroma, bedrock):
    bedrock.reply({"required_skills": []})
    assert await matching_engine.match_projects("u1", "jd text", jd_embedding=[1.0, 0.0]) == []


async def test_jd_analysis_falls_back_to_empty_fields(bedrock):
    bedrock.reply("not json")
    parsed = await matching_engine.analyze_job_description("Python role")
    assert parsed["required_skills"] == [] and parsed["title"] == ""


def test_scoring_helpers():
    assert matching_engine._calculate_tech_overlap(set(), set(), set()) == 0.5
    assert matching_engine._calculate_tech_overlap(
        {"go"}, {"python", "go"}, {"go"}
    ) == pytest.approx(0.7)
    assert matching_engine._calculate_keyword_match("anything", set()) == 0.5
    assert (
        matching_engine._generate_match_explanation(0.1, 0.1, 0, set(), set())
        == "Potential match based on content"
    )
    assert matching_engine._generate_match_explanation(0.55, 0.45, 0, {"go"}, {"go"}) == (
        "Moderate semantic relevance; Matching skills: go; Good tech stack overlap"
    )


async def test_select_top_projects_keeps_strong_matches_and_pads_to_the_minimum():
    scores = [
        MatchScore(f"p{i}", s, s, s, s, s, "") for i, s in enumerate([0.9, 0.7, 0.5, 0.4, 0.3])
    ]
    picked = await matching_engine.select_top_projects(scores, min_projects=3, max_projects=6)
    assert [s.project_id for s in picked] == ["p0", "p1", "p2"]
    assert await matching_engine.select_top_projects(scores[:2]) == scores[:2]
