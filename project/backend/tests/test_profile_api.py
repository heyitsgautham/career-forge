"""Profile read, update and resume-upload parsing on both backends."""

import json

import pytest

PROFILE = {
    "name": "Asha Example",
    "headline": "Backend developer",
    "linkedin_url": "https://www.linkedin.com/in/asha-example",
    "zip_code": "600001",
    "field_of_study": "CSE",
    "skills": ["Python", "SQL"],
    "experience": [
        {"company": "Sample Labs", "title": "Intern", "dates": "2025", "highlights": ["APIs"]}
    ],
    "achievements": ["Won a hackathon"],
}

RESUME_TEXT = (
    "Asha Example\nasha.alt@example.com\nBackend developer in Chennai\n"
    "Experience: Intern at Sample Labs building FastAPI services.\nSkills: Python, SQL, Docker\n"
)


@pytest.fixture(params=["sqlite", "dynamo"])
def backend(request):
    if request.param == "sqlite":
        client = request.getfixturevalue("client")
        auth = request.getfixturevalue("auth")
    else:
        client = request.getfixturevalue("dynamo_client")
        auth = request.getfixturevalue("dynamo_auth")
    return client, auth["headers"]


def test_profile_update_round_trips_every_field(backend):
    client, h = backend
    body = client.put("/api/auth/profile", json={**PROFILE, "phone": None}, headers=h).json()
    for key, value in PROFILE.items():
        assert body[key] == value, key
    fetched = client.get("/api/auth/profile", headers=h).json()
    assert fetched["linkedin_url"] == PROFILE["linkedin_url"]
    assert fetched["zip_code"] == "600001"
    assert fetched["phone"] is None


def upload(client, h, name="resume.txt", content=RESUME_TEXT.encode()):
    return client.post(
        "/api/auth/upload-resume", files={"file": (name, content, "text/plain")}, headers=h
    )


def test_upload_fills_the_profile_from_the_parsed_resume(backend, bedrock):
    client, h = backend
    bedrock.reply(
        {
            "name": "Asha Example",
            "email": "asha.alt@example.com",
            "headline": "Backend developer",
            "skills": ["Python", "SQL", "Docker"],
            "city": None,
            "unknown_field": "ignored",
        }
    )
    body = upload(client, h).json()
    assert body["fields_updated"] == 3
    profile = client.get("/api/auth/profile", headers=h).json()
    assert profile["skills"] == ["Python", "SQL", "Docker"]
    assert profile["email"].endswith("@example.com") and profile["email"] != "asha.alt@example.com"
    assert RESUME_TEXT[:40] in bedrock.prompts[0]


def test_upload_retries_with_plain_generation_when_json_mode_fails(client, auth, bedrock):
    bedrock.reply(
        "Here it is", "Sure:\n```json\n" + json.dumps({"headline": "Data engineer"}) + "\n```"
    )
    assert upload(client, auth["headers"]).json()["fields_updated"] == 1
    assert (
        client.get("/api/auth/profile", headers=auth["headers"]).json()["headline"]
        == "Data engineer"
    )


def test_upload_reports_parse_failures(client, auth, bedrock):
    bedrock.reply("nope", "still nope")
    r = upload(client, auth["headers"])
    assert r.status_code == 500
    # The model's error text stays in the log.
    assert r.json()["detail"] == "Failed to parse the resume with AI. Please try again."


@pytest.mark.parametrize(
    "name,content,detail",
    [
        ("resume.exe", b"MZ", "Unsupported file type"),
        ("resume.txt", b"too short", "Could not extract meaningful text"),
    ],
)
def test_upload_rejects_bad_files(client, auth, name, content, detail):
    r = upload(client, auth["headers"], name, content)
    assert r.status_code == 400
    assert r.json()["detail"].startswith(detail)


def test_upload_reports_unreadable_files(client, auth):
    # A corrupt file is a 400 the user can act on, not a 500.
    r = upload(client, auth["headers"], "resume.pdf", b"not really a pdf" * 10)
    assert r.status_code == 400
    assert r.json()["detail"].startswith("Could not read the document")
