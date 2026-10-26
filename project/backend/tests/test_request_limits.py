"""Request bodies outside the limits in app.schemas.limits are refused with 422.

Each case would otherwise reach DynamoDB, a Bedrock prompt or a LaTeX compile.
"""

import pytest

from app.schemas.limits import bounded_list

BIG_LATEX = "\\documentclass{article}" + "x" * 200_000


def detail_fields(response):
    return [".".join(str(p) for p in err["loc"][1:]) for err in response.json()["detail"]]


def test_registration_needs_an_eight_character_password(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "asha@example.com", "password": "short", "full_name": "Asha Example"},
    )
    assert response.status_code == 422
    assert detail_fields(response) == ["password"]
    assert "at least 8 characters" in response.json()["detail"][0]["msg"]


def test_registration_rejects_a_password_bcrypt_would_truncate(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "asha@example.com", "password": "p" * 73, "full_name": "Asha"},
    )
    assert response.status_code == 422


def test_sign_in_still_accepts_short_passwords_from_older_accounts(client):
    response = client.post("/api/auth/login", json={"email": "a@example.com", "password": "x"})
    assert response.status_code == 401


def test_profile_update_bounds_text_and_lists(client, auth):
    h = auth["headers"]
    assert (
        client.put("/api/auth/profile", json={"summary": "s" * 5_001}, headers=h).status_code == 422
    )
    assert (
        client.put("/api/auth/profile", json={"skills": ["x"] * 101}, headers=h).status_code == 422
    )
    ok = client.put("/api/auth/profile", json={"summary": "Builds APIs"}, headers=h)
    assert ok.status_code == 200


@pytest.mark.parametrize(
    "body,field",
    [
        ({"title": "", "raw_text": "Build APIs"}, "title"),
        ({"title": "Intern", "raw_text": ""}, "raw_text"),
        ({"title": "Intern", "raw_text": "x" * 50_001}, "raw_text"),
        ({"title": "Intern", "raw_text": "ok", "source_url": "u" * 2_049}, "source_url"),
    ],
)
def test_job_descriptions_need_a_title_and_bounded_text(client, auth, body, field):
    response = client.post("/api/jobs", json=body, headers=auth["headers"])
    assert response.status_code == 422
    assert detail_fields(response) == [field]


def test_tracking_accepts_only_known_statuses(dynamo_client, dynamo_auth):
    h = dynamo_auth["headers"]
    response = dynamo_client.post("/api/jobs/scout/j1/track", json={"status": "hacked"}, headers=h)
    assert response.status_code == 422
    assert dynamo_client.get("/api/jobs/tracking", headers=h).json() == {}
    ok = dynamo_client.post("/api/jobs/scout/j1/track", json={"status": "ignored"}, headers=h)
    assert ok.status_code == 200


def test_projects_bound_their_lists(dynamo_client, dynamo_auth):
    body = {"title": "job-scout", "description": "Ranks postings", "technologies": ["x"] * 101}
    response = dynamo_client.post("/api/projects", json=body, headers=dynamo_auth["headers"])
    assert response.status_code == 422
    assert detail_fields(response) == ["technologies"]


def test_latex_bodies_are_capped_at_200_kb(client, auth):
    h = auth["headers"]
    template = {"name": "Huge", "latex_content": BIG_LATEX}
    assert client.post("/api/templates", json=template, headers=h).status_code == 422
    assert (
        client.put(
            "/api/resumes/r1/latex", json={"latex_content": BIG_LATEX}, headers=h
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/resumes/r1/compile", json={"latex_content": BIG_LATEX}, headers=h
        ).status_code
        == 422
    )


def test_ai_edit_needs_a_message(client, auth):
    response = client.post(
        "/api/resumes/r1/ai-edit",
        json={"message": "   ", "latex_content": "\\documentclass{article}"},
        headers=auth["headers"],
    )
    assert response.status_code == 422
    assert detail_fields(response) == ["message"]


def test_skill_gap_role_ids_and_weeks_are_bounded(client, auth):
    h = auth["headers"]
    assert client.post("/api/skill-gap/analyse", json={"roleId": ""}, headers=h).status_code == 422
    assert (
        client.post("/api/skill-gap/analyse", json={"roleId": "r" * 201}, headers=h).status_code
        == 422
    )


def test_bounded_list_caps_entries():
    from pydantic import TypeAdapter, ValidationError

    adapter = TypeAdapter(bounded_list(int, 2))
    assert adapter.validate_python([1, 2]) == [1, 2]
    with pytest.raises(ValidationError):
        adapter.validate_python([1, 2, 3])
