"""Resume generation routes: the M2 summary pipeline and the legacy template fill."""

import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

from app.models.project import Project
from app.models.template import Template
from app.services import resume_agent as agent_module
from app.services.dynamo_service import dynamo_service

FILLED = "\\documentclass{article}\\begin{document}Filled\\end{document}"


@pytest.fixture
def fake_m2(monkeypatch):
    calls = []

    async def generate(**kwargs):
        calls.append(kwargs)
        if kwargs["jd"] == "fail-400":
            raise ValueError("No project summaries found. Run GitHub ingestion first.")
        if kwargs["jd"] == "fail-500":
            raise RuntimeError("bedrock down")
        return SimpleNamespace(
            resume_id="r1",
            pdf_url=None,
            tex_url="https://s3/tex",
            analysis="a",
            compilation_error="! err",
        )

    monkeypatch.setattr(agent_module, "generate_resume_from_summaries", generate)
    return calls


def test_m2_generate_passes_the_dynamo_profile(dynamo_client, dynamo_auth, fake_m2):
    asyncio.run(
        dynamo_service.update_item(
            "Users",
            {"userId": dynamo_auth["user_id"]},
            {"skills": ["Python"], "experience": "[bad"},
        )
    )
    body = dynamo_client.post(
        "/api/resumes/generate", json={"jd": "Python intern"}, headers=dynamo_auth["headers"]
    ).json()
    assert body == {
        "resume_id": "r1",
        "pdf_url": None,
        "tex_url": "https://s3/tex",
        "analysis": "a",
        "status": "generated",
        "compilation_error": "! err",
    }
    call = fake_m2[0]
    assert call["skills"] == ["Python"]
    assert call["experience"] == []
    assert call["personal_info"]["name"] == "Asha Example"


@pytest.mark.parametrize("jd,status", [("fail-400", 400), ("fail-500", 500)])
def test_m2_generate_error_codes(dynamo_client, dynamo_auth, fake_m2, jd, status):
    assert (
        dynamo_client.post(
            "/api/resumes/generate", json={"jd": jd}, headers=dynamo_auth["headers"]
        ).status_code
        == status
    )


def test_m2_generate_accepts_an_empty_body(dynamo_client, dynamo_auth, fake_m2):
    assert (
        dynamo_client.post("/api/resumes/generate", headers=dynamo_auth["headers"]).status_code
        == 200
    )
    assert fake_m2[0]["jd"] is None


def test_legacy_generate_on_dynamo_fills_the_template(dynamo_client, dynamo_auth, bedrock):
    h = dynamo_auth["headers"]
    dynamo_client.post(
        "/api/projects",
        json={
            "title": "job-scout",
            "description": "Ranks postings",
            "technologies": ["Python"],
            "highlights": ["h"],
            "url": "https://github.com/asha-example/job-scout",
        },
        headers=h,
    )
    jd = dynamo_client.post(
        "/api/jobs",
        json={"title": "SDE Intern", "company": "Sample Labs", "raw_text": "Python APIs"},
        headers=h,
    ).json()
    resume = dynamo_client.post(
        "/api/resumes", json={"name": "Mine", "job_description_id": jd["id"]}, headers=h
    ).json()
    bedrock.reply(f"```latex\n{FILLED}\n```")

    body = dynamo_client.post(f"/api/resumes/{resume['id']}/generate", json={}, headers=h).json()
    assert body["status"] == "generated"
    assert body["latex_content"] == FILLED
    prompt = bedrock.prompts[0]
    assert "Target Role: SDE Intern" in prompt
    assert "Title: job-scout" in prompt
    assert "URL: https://github.com/asha-example/job-scout" in prompt


def test_legacy_generate_on_dynamo_records_errors(dynamo_client, dynamo_auth, bedrock):
    h = dynamo_auth["headers"]
    resume = dynamo_client.post("/api/resumes", json={"name": "Mine"}, headers=h).json()
    bedrock.reply(RuntimeError("bedrock down"))
    assert dynamo_client.post(f"/api/resumes/{resume['id']}/generate", headers=h).status_code == 500
    item = asyncio.run(
        dynamo_service.get_item(
            "Resumes", {"userId": dynamo_auth["user_id"], "resumeId": resume["id"]}
        )
    )
    assert (item["status"], item["errorMessage"]) == ("error", "bedrock down")
    assert dynamo_client.post("/api/resumes/missing/generate", headers=h).status_code == 404


def add_sqlite(*objects):
    from app.core.database import AsyncSessionLocal

    async def _add():
        async with AsyncSessionLocal() as db:
            for obj in objects:
                db.add(obj)
            await db.commit()
            return [o.id for o in objects]

    return asyncio.run(_add())


def test_legacy_generate_on_sqlite_uses_a_system_template_and_top_projects(client, auth, bedrock):
    h, uid = auth["headers"], auth["user_id"]
    add_sqlite(Template(name="Jake", latex_content="TEMPLATE", is_system=True))
    add_sqlite(
        *[
            Project(
                user_id=uid,
                title=f"proj-{i}",
                description="d",
                technologies=["Python"],
                highlights=["h"],
                start_date=date(2025, 1, 1),
            )
            for i in range(4)
        ]
    )
    jd = client.post(
        "/api/jobs", json={"title": "SDE", "raw_text": "proj-2 python"}, headers=h
    ).json()
    resume = client.post(
        "/api/resumes", json={"name": "Mine", "job_description_id": jd["id"]}, headers=h
    ).json()
    bedrock.reply(FILLED)

    body = client.post(
        f"/api/resumes/{resume['id']}/generate",
        json={"skills": ["Go"], "personal": {"name": "Asha"}},
        headers=h,
    ).json()
    assert body["status"] == "generated"
    assert body["latex_content"] == FILLED
    prompt = bedrock.prompts[0]
    assert "<template>\nTEMPLATE\n</template>" in prompt
    assert prompt.count("Title: proj-") == 3
    assert "SKILLS: Go" in prompt
    assert "Target Role: SDE" in prompt


def test_legacy_generate_on_sqlite_errors(client, auth, bedrock):
    h = auth["headers"]
    resume = client.post("/api/resumes", json={"name": "Mine"}, headers=h).json()
    r = client.post(f"/api/resumes/{resume['id']}/generate", headers=h)
    if r.status_code == 500 and "No template available" in r.json()["detail"]:
        return
    bedrock.reply(RuntimeError("down"))
    r = client.post(f"/api/resumes/{resume['id']}/generate", headers=h)
    assert r.status_code == 500
    assert client.get(f"/api/resumes/{resume['id']}", headers=h).json()["status"] == "error"
