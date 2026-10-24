"""Saved job descriptions on SQLite and the DynamoDB mapping helpers."""

from decimal import Decimal

from app.api.routes.jobs.common import (
    _jd_response_from_dynamo,
    _scout_response_from_dynamo,
    _to_str,
)
from tests.conftest import register_user

JD = {
    "title": "Backend Intern",
    "company": "Sample Labs",
    "location": "Remote",
    "raw_text": "Build FastAPI services with PostgreSQL and Docker.",
    "source_url": "https://jobs.example.com/123",
}


def test_create_list_get_and_delete_job_description(client, auth):
    headers = auth["headers"]
    created = client.post("/api/jobs", json=JD, headers=headers)
    assert created.status_code == 200
    jd = created.json()
    assert jd["title"] == "Backend Intern"
    assert jd["is_analyzed"] is False

    assert [j["id"] for j in client.get("/api/jobs", headers=headers).json()] == [jd["id"]]
    assert client.get(f"/api/jobs/{jd['id']}", headers=headers).json()["company"] == "Sample Labs"

    assert client.delete(f"/api/jobs/{jd['id']}", headers=headers).status_code == 200
    assert client.get(f"/api/jobs/{jd['id']}", headers=headers).status_code == 404


def test_job_descriptions_are_private_to_their_owner(client, auth):
    jd_id = client.post("/api/jobs", json=JD, headers=auth["headers"]).json()["id"]
    other = register_user(client, name="Other Person")
    assert client.get("/api/jobs", headers=other["headers"]).json() == []
    assert client.get(f"/api/jobs/{jd_id}", headers=other["headers"]).status_code == 404


def test_create_requires_title_and_text(client, auth):
    response = client.post("/api/jobs", json={"title": "No text"}, headers=auth["headers"])
    assert response.status_code == 422


def test_to_str_handles_dynamo_value_types():
    assert _to_str(None) is None
    assert _to_str([]) is None
    assert _to_str(["SDE", "AI/ML"]) == "SDE, AI/ML"
    assert _to_str(Decimal("12")) == "12"


def test_scout_response_fills_list_defaults():
    job = _scout_response_from_dynamo(
        {
            "jobId": "j1",
            "title": "SDE Intern",
            "company": "Sample Labs",
            "salary": 20000,
            "category": ["SDE"],
        }
    )
    assert job.jobId == "j1"
    assert job.salary == "20000"
    assert job.category == "SDE"
    assert job.requiredSkills == []
    assert job.isAnalyzed is False


def test_jd_response_falls_back_to_scraped_field_names():
    jd = _jd_response_from_dynamo(
        {
            "jobId": "j2",
            "title": "Data Intern",
            "description": "SQL and Python",
            "url": "https://x.example",
            "atsKeywords": ["ETL"],
        }
    )
    assert jd.raw_text == "SQL and Python"
    assert jd.source_url == "https://x.example"
    assert jd.keywords == ["ETL"]
