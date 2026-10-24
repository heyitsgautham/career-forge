"""Resume list, create, get and delete on the SQLite backend."""

import uuid

from tests.conftest import register_user


def test_create_list_get_and_delete(client, auth):
    headers = auth["headers"]
    created = client.post("/api/resumes", json={"name": "Backend resume"}, headers=headers)
    assert created.status_code == 200
    resume = created.json()
    assert resume["name"] == "Backend resume"
    assert resume["status"] == "draft"
    assert resume["selected_project_ids"] == []

    listed = client.get("/api/resumes", headers=headers).json()
    assert [r["id"] for r in listed] == [resume["id"]]

    fetched = client.get(f"/api/resumes/{resume['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Backend resume"

    deleted = client.delete(f"/api/resumes/{resume['id']}", headers=headers)
    assert deleted.json() == {"message": "Resume deleted"}
    assert client.get(f"/api/resumes/{resume['id']}", headers=headers).status_code == 404


def test_unknown_template_is_rejected(client, auth):
    response = client.post(
        "/api/resumes",
        json={"name": "x", "template_id": str(uuid.uuid4())},
        headers=auth["headers"],
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Template not found"


def test_unknown_projects_are_rejected(client, auth):
    response = client.post(
        "/api/resumes",
        json={"name": "x", "project_ids": [str(uuid.uuid4())]},
        headers=auth["headers"],
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Some projects not found"


def test_users_cannot_see_each_others_resumes(client, auth):
    other = register_user(client, name="Other Person")
    resume_id = client.post("/api/resumes", json={"name": "Mine"}, headers=auth["headers"]).json()[
        "id"
    ]

    assert client.get("/api/resumes", headers=other["headers"]).json() == []
    assert client.get(f"/api/resumes/{resume_id}", headers=other["headers"]).status_code == 404
    assert client.delete(f"/api/resumes/{resume_id}", headers=other["headers"]).status_code == 404


def test_resume_routes_require_a_token(client):
    assert client.get("/api/resumes").status_code in (401, 403)
    assert client.post("/api/resumes", json={"name": "x"}).status_code in (401, 403)
