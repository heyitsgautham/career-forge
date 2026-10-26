"""Malformed ids in paths are a 404, not a 500."""

import pytest

from app.api.ids import path_uuid


@pytest.mark.parametrize(
    "path",
    [
        "/api/resumes/not-a-uuid",
        "/api/jobs/not-a-uuid",
        "/api/templates/not-a-uuid",
    ],
)
def test_malformed_ids_are_not_found(client, auth, path):
    # Regression: uuid.UUID("not-a-uuid") raised ValueError and the request failed with 500.
    response = client.get(path, headers=auth["headers"])
    assert response.status_code == 404


def test_malformed_ids_on_writes_are_not_found(client, auth):
    h = auth["headers"]
    assert client.delete("/api/resumes/nope", headers=h).status_code == 404
    assert client.delete("/api/jobs/nope", headers=h).status_code == 404
    assert (
        client.put("/api/resumes/nope/latex", json={"latex_content": "x"}, headers=h).status_code
        == 404
    )


def test_path_uuid_accepts_any_uuid_spelling():
    assert str(path_uuid("6F9619FF-8B86-D011-B42D-00C04FC964FF", "Thing")) == (
        "6f9619ff-8b86-d011-b42d-00c04fc964ff"
    )
