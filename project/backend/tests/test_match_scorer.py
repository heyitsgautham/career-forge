"""Job match scoring: keyword overlap, cosine similarity, blended score."""

import pytest

from app.services import match_scorer as match_scorer_module
from app.services.match_scorer import MatchScorer


@pytest.fixture
def scorer():
    return MatchScorer()


def test_keyword_overlap_counts_exact_and_partial_matches(scorer):
    score, matched, missing = scorer._keyword_overlap(
        ["Python", "React", "docker"], ["python", "React.js", "Kubernetes", "Docker"]
    )
    assert set(matched) == {"python", "React.js", "Docker"}
    assert missing == ["Kubernetes"]
    assert score == pytest.approx(0.75)


def test_keyword_overlap_is_neutral_without_requirements(scorer):
    assert scorer._keyword_overlap(["Python"], []) == (0.5, [], [])


def test_cosine_similarity_edge_cases(scorer):
    assert scorer._cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
    assert scorer._cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
    assert scorer._cosine_similarity([1, 0], [-1, 0]) == 0.0
    assert scorer._cosine_similarity([1, 2], [1]) == 0.0
    assert scorer._cosine_similarity([0, 0], [1, 1]) == 0.0
    assert scorer._cosine_similarity([], []) == 0.0


@pytest.mark.parametrize(
    "keyword,vector,expected",
    [
        (0.9, 0.9, ["Excellent skill match", "Strong semantic match"]),
        (0.6, 0.65, ["Good skill overlap", "Good semantic relevance"]),
        (0.3, 0.1, ["Partial skill match"]),
        (0.1, 0.1, ["Limited skill overlap"]),
    ],
)
def test_explanation_tiers(scorer, keyword, vector, expected):
    text = scorer._build_explanation(vector, keyword, [], [])
    assert text.split(" · ") == expected


def test_explanation_limits_listed_skills(scorer):
    text = scorer._build_explanation(0.0, 0.5, list("abcdefg"), list("wxyz"))
    assert "Matching: a, b, c, d, e" in text
    assert "To learn: w, x, y" in text
    assert "z" not in text.split("To learn: ")[1]


async def test_compute_match_without_embedding_uses_neutral_vector(scorer):
    job = {"jobId": "job-1", "requiredSkills": ["Python", "SQL"], "description": "x"}
    result = await scorer.compute_match(["python"], None, job)
    assert result.job_id == "job-1"
    assert result.vector_score == 0.5
    assert result.keyword_score == 0.5
    # 0.55 * 0.5 + 0.45 * 0.5 = 0.5
    assert result.total_score == 50.0
    assert result.missing_skills == ["SQL"]


async def test_compute_match_blends_embedding_similarity(scorer, monkeypatch):
    async def fake_embed(text):
        assert text == "Python, Go"
        return [1.0, 0.0]

    monkeypatch.setattr(match_scorer_module.embedding_service, "embed_text", fake_embed)
    job = {"jobId": "job-2", "requiredSkills": ["Python"], "preferredSkills": ["Go"]}
    result = await scorer.compute_match(["Python"], [1.0, 0.0], job)
    assert result.vector_score == 1.0
    assert result.keyword_score == 1.0
    assert result.total_score == 100.0


async def test_compute_match_survives_embedding_errors(scorer, monkeypatch):
    async def broken(text):
        raise RuntimeError("bedrock down")

    monkeypatch.setattr(match_scorer_module.embedding_service, "embed_text", broken)
    result = await scorer.compute_match(["Python"], [1.0], {"requiredSkills": ["Python"]})
    assert result.vector_score == 0.5
