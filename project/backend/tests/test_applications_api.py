"""Application tracker and resume tailoring routes on DynamoDB (moto)."""

import asyncio
from types import SimpleNamespace

import pytest

from app.services import resume_tailor
from app.services.dynamo_service import dynamo_service


def put(table, item):
    asyncio.run(dynamo_service.put_item(table, item))


def test_application_lifecycle(dynamo_client, dynamo_auth):
    h, uid = dynamo_auth["headers"], dynamo_auth["user_id"]
    put("Jobs", {"jobId": "j1", "company": "Sample Labs", "title": "SDE Intern"})

    created = dynamo_client.post("/api/applications", json={"jobId": "j1"}, headers=h).json()
    assert (created["companyName"], created["roleTitle"], created["status"]) == (
        "Sample Labs",
        "SDE Intern",
        "applied",
    )

    saved = dynamo_client.post(
        "/api/applications",
        json={"jobId": "missing", "status": "saved", "companyName": "Other Co"},
        headers=h,
    ).json()
    assert (saved["companyName"], saved["roleTitle"], saved["status"]) == (
        "Other Co",
        "Unknown Role",
        "saved",
    )

    bogus = dynamo_client.post(
        "/api/applications", json={"jobId": "j1", "status": "ghosted"}, headers=h
    ).json()
    assert bogus["status"] == "applied"

    listed = dynamo_client.get(f"/api/applications/user/{uid}", headers=h).json()
    assert len(listed) == 3
    only_saved = dynamo_client.get(
        f"/api/applications/user/{uid}?status_filter=saved", headers=h
    ).json()
    assert [a["applicationId"] for a in only_saved] == [saved["applicationId"]]

    app_id = created["applicationId"]
    moved = dynamo_client.patch(
        f"/api/applications/{app_id}",
        json={"status": "interviewing", "notes": "Round 2 on Friday"},
        headers=h,
    ).json()
    assert (moved["status"], moved["notes"]) == ("interviewing", "Round 2 on Friday")

    stats = dynamo_client.get(f"/api/applications/stats/{uid}", headers=h).json()
    assert stats == {
        "total": 3,
        "saved": 1,
        "applied": 1,
        "viewed": 0,
        "interviewing": 1,
        "offered": 0,
        "rejected": 0,
    }

    assert dynamo_client.delete(f"/api/applications/{app_id}", headers=h).status_code == 204
    assert (
        dynamo_client.patch(
            f"/api/applications/{app_id}", json={"notes": "x"}, headers=h
        ).status_code
        == 404
    )
    assert dynamo_client.delete(f"/api/applications/{app_id}", headers=h).status_code == 404


def test_invalid_status_update_is_rejected(dynamo_client, dynamo_auth):
    h = dynamo_auth["headers"]
    app_id = dynamo_client.post("/api/applications", json={"jobId": "j1"}, headers=h).json()[
        "applicationId"
    ]
    r = dynamo_client.patch(f"/api/applications/{app_id}", json={"status": "ghosted"}, headers=h)
    assert r.status_code == 400
    assert "Must be one of" in r.json()["detail"]


def test_users_cannot_read_other_users_applications(dynamo_client, dynamo_auth):
    h = dynamo_auth["headers"]
    assert dynamo_client.get("/api/applications/user/someone-else", headers=h).status_code == 403
    assert dynamo_client.get("/api/applications/stats/someone-else", headers=h).status_code == 403


@pytest.fixture
def fake_tailor(monkeypatch):
    calls = []

    async def tailor(**kwargs):
        calls.append(kwargs)
        if kwargs["job_id"] == "bad-job":
            raise ValueError("Job not found")
        if kwargs["job_id"] == "boom":
            raise RuntimeError("latex exploded")
        return SimpleNamespace(
            resume_id="r1",
            pdf_url="https://s3/pdf",
            tex_url="https://s3/tex",
            job_id=kwargs["job_id"],
            match_keywords=["Python"],
            diff_summary={"added": 2},
            compilation_error=None,
        )

    monkeypatch.setattr(resume_tailor, "tailor_resume_for_job", tailor)
    return calls


def test_tailor_passes_the_profile_to_the_tailor(dynamo_client, dynamo_auth, fake_tailor):
    asyncio.run(
        dynamo_service.update_item(
            "Users",
            {"userId": dynamo_auth["user_id"]},
            {
                "skills": '["Python", "SQL"]',
                "education": "not json",
                "githubUsername": "asha-example",
            },
        )
    )
    r = dynamo_client.post(
        "/api/resumes/tailor", json={"jobId": "j1"}, headers=dynamo_auth["headers"]
    )
    assert r.status_code == 200
    assert r.json()["matchKeywords"] == ["Python"]
    call = fake_tailor[0]
    assert call["skills"] == ["Python", "SQL"]
    assert call["education"] == []
    assert call["personal_info"]["name"] == "Asha Example"
    assert call["personal_info"]["github"] == "asha-example"


@pytest.mark.parametrize("job_id,status", [("bad-job", 400), ("boom", 500)])
def test_tailor_errors_map_to_http_codes(dynamo_client, dynamo_auth, fake_tailor, job_id, status):
    r = dynamo_client.post(
        "/api/resumes/tailor", json={"jobId": job_id}, headers=dynamo_auth["headers"]
    )
    assert r.status_code == status


def test_get_tailored_resume_returns_the_newest_with_fresh_urls(dynamo_client, dynamo_auth):
    uid = dynamo_auth["user_id"]
    base = {"userId": uid, "jobId": "j1", "type": "tailored"}
    put("Resumes", {**base, "resumeId": "old", "createdAt": "2026-01-01", "pdfS3Key": "a.pdf"})
    put(
        "Resumes",
        {
            **base,
            "resumeId": "new",
            "createdAt": "2026-02-01",
            "pdfS3Key": "b.pdf",
            "texS3Key": "b.tex",
            "matchKeywords": ["SQL"],
            "errorMessage": "overfull box",
        },
    )
    put("Resumes", {**base, "resumeId": "plain", "type": "standard", "createdAt": "2026-03-01"})

    body = dynamo_client.get("/api/resumes/job/j1", headers=dynamo_auth["headers"]).json()
    assert body["resumeId"] == "new"
    assert "b.pdf" in body["pdfUrl"] and "b.tex" in body["texUrl"]
    assert body["compilationError"] == "overfull box"
    assert (
        dynamo_client.get("/api/resumes/job/none", headers=dynamo_auth["headers"]).status_code
        == 404
    )
