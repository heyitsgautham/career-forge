"""Helpers shared by the resume routes."""

from types import SimpleNamespace

from app.api.routes.resumes.common import _rank_projects_by_relevance, _resume_from_dynamo


def project(title, technologies, description="", highlights=None):
    return SimpleNamespace(
        title=title,
        description=description,
        technologies=technologies,
        highlights=highlights or [],
    )


async def test_projects_rank_by_keyword_overlap_with_the_jd():
    jd = SimpleNamespace(
        title="Backend Engineer",
        raw_text="Build fastapi services on aws with postgres",
        required_skills=["Python", "Docker"],
    )
    chat = project("Chat app", ["React", "Firebase"])
    api = project("Billing API", ["Python", "FastAPI", "Postgres"], "fastapi service on aws")
    infra = project("Deploy kit", ["Docker"])

    ranked = await _rank_projects_by_relevance([chat, infra, api], jd)
    assert ranked == [api, infra, chat]


async def test_ranking_tolerates_missing_lists():
    jd = SimpleNamespace(title="Data", raw_text="sql", required_skills=None)
    bare = SimpleNamespace(title="Bare", description="", technologies=None, highlights=None)
    assert await _rank_projects_by_relevance([bare], jd) == [bare]


def test_resume_from_dynamo_maps_camel_case_fields():
    item = {
        "resumeId": "r-1",
        "name": "SDE resume",
        "templateId": "t-1",
        "selectedProjectIds": None,
        "pdfS3Key": "resumes/r-1.pdf",
        "texS3Key": "resumes/r-1.tex",
        "createdAt": "2026-01-01T00:00:00",
    }
    mapped = _resume_from_dynamo(item)
    assert mapped["id"] == "r-1"
    assert mapped["template_id"] == "t-1"
    assert mapped["selected_project_ids"] == []
    assert mapped["pdf_path"] == "resumes/r-1.pdf"
    assert mapped["tex_s3_key"] == "resumes/r-1.tex"
    assert mapped["status"] == "draft"
    assert mapped["type"] == "standard"
    assert mapped["updated_at"] == ""
