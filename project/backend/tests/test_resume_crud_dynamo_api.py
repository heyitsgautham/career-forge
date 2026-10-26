"""Resume CRUD on the DynamoDB backend, including S3 cleanup on delete."""

import asyncio

from app.services.dynamo_service import dynamo_service


def test_dynamo_create_list_get_and_delete(dynamo_client, dynamo_auth, monkeypatch):
    from app.services.s3_service import s3_service

    deleted_keys = []

    async def delete_file(key):
        deleted_keys.append(key)

    monkeypatch.setattr(s3_service, "delete_file", delete_file)
    h = dynamo_auth["headers"]

    created = dynamo_client.post(
        "/api/resumes", json={"name": "Backend resume", "project_ids": ["p1"]}, headers=h
    ).json()
    assert created["status"] == "draft"
    assert created["selected_project_ids"] == ["p1"]

    asyncio.run(
        dynamo_service.update_item(
            "Resumes",
            {"userId": dynamo_auth["user_id"], "resumeId": created["id"]},
            {"pdfS3Key": "u1/r.pdf", "texS3Key": "/local/r.tex"},
        )
    )
    assert [r["id"] for r in dynamo_client.get("/api/resumes", headers=h).json()] == [created["id"]]
    assert dynamo_client.get(f"/api/resumes/{created['id']}", headers=h).json()["name"] == (
        "Backend resume"
    )

    assert dynamo_client.delete(f"/api/resumes/{created['id']}", headers=h).json() == {
        "message": "Resume deleted"
    }
    # Only S3 keys are cleaned up; local paths are skipped.
    assert deleted_keys == ["u1/r.pdf"]
    assert dynamo_client.get(f"/api/resumes/{created['id']}", headers=h).status_code == 404
    assert dynamo_client.delete(f"/api/resumes/{created['id']}", headers=h).status_code == 404


def test_dynamo_delete_survives_an_s3_failure(dynamo_client, dynamo_auth, monkeypatch):
    from app.services.s3_service import s3_service

    async def broken(key):
        raise RuntimeError("bucket gone")

    monkeypatch.setattr(s3_service, "delete_file", broken)
    h = dynamo_auth["headers"]
    created = dynamo_client.post("/api/resumes", json={"name": "R"}, headers=h).json()
    asyncio.run(
        dynamo_service.update_item(
            "Resumes",
            {"userId": dynamo_auth["user_id"], "resumeId": created["id"]},
            {"pdfS3Key": "u1/r.pdf"},
        )
    )
    assert dynamo_client.delete(f"/api/resumes/{created['id']}", headers=h).status_code == 200


def test_resume_names_and_project_lists_are_bounded(client, auth):
    h = auth["headers"]
    assert client.post("/api/resumes", json={"name": ""}, headers=h).status_code == 422
    assert client.post("/api/resumes", json={"name": "x" * 201}, headers=h).status_code == 422
    too_many = {"name": "R", "project_ids": [f"p{i}" for i in range(101)]}
    assert client.post("/api/resumes", json=too_many, headers=h).status_code == 422
