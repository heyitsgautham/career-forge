"""LinkedIn profile and certification imports, with the browser scraper faked."""

import pytest

from app.services import linkedin_scraper
from app.services.linkedin_merge import ProfileSnapshot, append_new, merge_linkedin_profile

URL = "https://www.linkedin.com/in/asha-example"
SCRAPED = {
    "name": "Asha LinkedIn",
    "headline": "Backend developer",
    "location": "Chennai",
    "summary": "Builds APIs",
    "website": "https://asha.example",
    "education": [
        {"school": "Example Institute", "degree": "B.Tech"},
        {"school": "example institute", "degree": "duplicate spelling"},
        {"school": "", "degree": "no school"},
    ],
    "certifications": [{"name": "AWS Cloud Practitioner"}, {"name": None}],
}


def test_merge_keeps_what_the_user_filled_in_and_refreshes_the_rest():
    merge = merge_linkedin_profile(
        URL,
        ProfileSnapshot(name="Asha Example", certifications=[{"name": "aws cloud practitioner"}]),
        SCRAPED,
    )
    assert merge.updates["linkedin_url"] == URL
    assert "name" not in merge.updates
    assert merge.updates["headline"] == "Backend developer"
    assert merge.updates["location"] == "Chennai"
    assert [e["school"] for e in merge.new_education] == ["Example Institute"]
    assert merge.new_certifications == []
    assert merge.updates["certifications"] == [{"name": "aws cloud practitioner"}]


def test_append_new_ignores_blank_and_null_names():
    assert append_new(
        [], [{"name": None}, {"name": " "}, {"name": "A"}, {"name": "a"}], "name"
    ) == [{"name": "A"}]


@pytest.fixture
def scraper(monkeypatch):
    calls = []

    async def scrape_profile(url):
        calls.append(url)
        return SCRAPED

    async def scrape_certs(url):
        calls.append(url)
        return [{"name": "AWS Cloud Practitioner"}, {"name": "Kubernetes"}]

    monkeypatch.setattr(linkedin_scraper, "scrape_linkedin_profile", scrape_profile)
    monkeypatch.setattr(linkedin_scraper, "scrape_linkedin_certifications", scrape_certs)
    return calls


@pytest.mark.parametrize("backend", ["sqlite", "dynamodb"])
def test_profile_import_fills_the_profile(request, backend, scraper):
    client = request.getfixturevalue("client" if backend == "sqlite" else "dynamo_client")
    user = request.getfixturevalue("auth" if backend == "sqlite" else "dynamo_auth")
    h = user["headers"]

    body = client.post("/api/auth/linkedin/import-profile", json={"linkedin_url": URL}, headers=h)
    assert body.status_code == 200
    imported = body.json()["imported"]
    assert imported["education_added"] == 1
    assert imported["certifications_added"] == 1
    assert scraper == [URL]

    profile = client.get("/api/auth/profile", headers=h).json()
    assert profile["headline"] == "Backend developer"
    assert profile["linkedin_url"] == URL
    assert [c["name"] for c in profile["certifications"]] == ["AWS Cloud Practitioner"]


def test_profile_import_needs_a_valid_url(client, auth, scraper):
    h = auth["headers"]
    assert client.post("/api/auth/linkedin/import-profile", headers=h).status_code == 400
    bad = client.post(
        "/api/auth/linkedin/import-profile",
        json={"linkedin_url": "https://example.com/in/x"},
        headers=h,
    )
    assert bad.status_code == 400
    assert scraper == []


def test_profile_import_failure_is_a_generic_500(client, auth, monkeypatch):
    async def blocked(url):
        raise RuntimeError("Login wall at https://www.linkedin.com/checkpoint/abc")

    monkeypatch.setattr(linkedin_scraper, "scrape_linkedin_profile", blocked)
    response = client.post(
        "/api/auth/linkedin/import-profile", json={"linkedin_url": URL}, headers=auth["headers"]
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to import the LinkedIn profile."


def test_certification_import_adds_only_new_certificates(client, auth, scraper):
    h = auth["headers"]
    assert client.post("/api/auth/linkedin/scrape-certifications", headers=h).status_code == 400

    client.put(
        "/api/auth/profile",
        json={"linkedin_url": URL, "certifications": [{"name": "aws cloud practitioner"}]},
        headers=h,
    )
    body = client.post("/api/auth/linkedin/scrape-certifications", headers=h).json()
    assert [c["name"] for c in body["certifications"]] == ["Kubernetes"]
    assert body["total_certifications"] == 2
