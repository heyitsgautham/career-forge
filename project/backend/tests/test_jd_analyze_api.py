"""Saved job descriptions on DynamoDB: CRUD, analysis and project matching."""

import asyncio

from app.services.dynamo_service import dynamo_service
from app.services.vector_store import VectorStoreService

JD = {
    "title": "Backend Intern",
    "company": "Sample Labs",
    "raw_text": "Build REST APIs in Python with Docker and SQL.",
}


def create(client, auth):
    return client.post("/api/jobs", json=JD, headers=auth["headers"]).json()


def test_dynamo_jd_crud_is_scoped_to_the_owner(dynamo_client, dynamo_auth):
    h = dynamo_auth["headers"]
    jd = create(dynamo_client, dynamo_auth)
    asyncio.run(dynamo_service.put_item("Jobs", {"jobId": "scraped", "title": "Shared job"}))
    assert [j["id"] for j in dynamo_client.get("/api/jobs", headers=h).json()] == [jd["id"]]
    assert (
        dynamo_client.get(f"/api/jobs/{jd['id']}", headers=h).json()["raw_text"] == JD["raw_text"]
    )
    assert dynamo_client.get("/api/jobs/scraped", headers=h).status_code == 404
    assert dynamo_client.delete("/api/jobs/scraped", headers=h).status_code == 404
    assert dynamo_client.delete(f"/api/jobs/{jd['id']}", headers=h).json() == {
        "message": "Job description deleted"
    }


def test_analyze_stores_skills_and_an_embedding_then_matches_projects(
    dynamo_client, dynamo_auth, bedrock, chroma
):
    bedrock.embedding = [1.0, 0.0]
    bedrock.reply(
        {"required_skills": ["Python", "Docker"], "preferred_skills": [], "keywords": ["rest"]}
    )
    asyncio.run(
        chroma.add_embedding(
            VectorStoreService.COLLECTION_PROJECTS,
            "proj-1",
            [1.0, 0.0],
            {"user_id": dynamo_auth["user_id"], "technologies": ["python", "docker"]},
            "rest api in python",
        )
    )
    jd = create(dynamo_client, dynamo_auth)
    body = dynamo_client.post(
        f"/api/jobs/{jd['id']}/analyze", headers=dynamo_auth["headers"]
    ).json()

    assert body["job_description"]["required_skills"] == ["Python", "Docker"]
    assert body["job_description"]["is_analyzed"] is True
    assert [m["project_id"] for m in body["matched_projects"]] == ["proj-1"]
    stored = asyncio.run(dynamo_service.get_item("Jobs", {"jobId": jd["id"]}))
    assert stored["embeddingId"]
    assert asyncio.run(
        chroma.get_by_id(VectorStoreService.COLLECTION_JOB_DESCRIPTIONS, stored["embeddingId"])
    )

    # A second analyze reuses the stored analysis and the stored embedding
    calls_before = len(bedrock.calls)
    dynamo_client.post(f"/api/jobs/{jd['id']}/analyze", headers=dynamo_auth["headers"])
    assert len(bedrock.calls) == calls_before

    dynamo_client.delete(f"/api/jobs/{jd['id']}", headers=dynamo_auth["headers"])
    assert (
        asyncio.run(
            chroma.get_by_id(VectorStoreService.COLLECTION_JOB_DESCRIPTIONS, stored["embeddingId"])
        )
        is None
    )


def test_analyze_falls_back_to_keyword_skills(dynamo_client, dynamo_auth, monkeypatch):
    from app.services import matching_engine as engine_module

    async def broken(text):
        raise RuntimeError("bedrock down")

    monkeypatch.setattr(engine_module.matching_engine, "analyze_job_description", broken)
    jd = create(dynamo_client, dynamo_auth)
    body = dynamo_client.post(
        f"/api/jobs/{jd['id']}/analyze", headers=dynamo_auth["headers"]
    ).json()
    assert body["job_description"]["required_skills"] == ["python", "sql", "docker", "api", "rest"]
    assert body["matched_projects"] == []


def test_sqlite_analyze_uses_the_same_flow(client, auth, bedrock, chroma):
    bedrock.embedding = [1.0, 0.0]
    bedrock.reply({"required_skills": ["Python"], "preferred_skills": [], "keywords": []})
    jd = client.post("/api/jobs", json=JD, headers=auth["headers"]).json()
    body = client.post(f"/api/jobs/{jd['id']}/analyze", headers=auth["headers"]).json()
    assert body["job_description"]["required_skills"] == ["Python"]
    assert client.post(f"/api/jobs/{jd['id']}/analyze", headers=auth["headers"]).status_code == 200


def test_sqlite_analyze_keyword_fallback(client, auth, monkeypatch):
    from app.services import matching_engine as engine_module

    async def broken(text):
        raise RuntimeError("down")

    monkeypatch.setattr(engine_module.matching_engine, "analyze_job_description", broken)
    jd = client.post("/api/jobs", json=JD, headers=auth["headers"]).json()
    body = client.post(f"/api/jobs/{jd['id']}/analyze", headers=auth["headers"]).json()
    assert "python" in body["job_description"]["required_skills"]
    assert (
        client.post(
            "/api/jobs/00000000-0000-0000-0000-000000000000/analyze", headers=auth["headers"]
        ).status_code
        == 404
    )
