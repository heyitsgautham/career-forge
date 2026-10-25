"""Skill gap analysis and learning roadmap routes on DynamoDB (moto)."""

import asyncio

from app.services import gap_analysis
from app.services.dynamo_service import dynamo_service
from app.services.gap_analysis import get_role_benchmark

ROLE = "backend-sde"
DOMAINS = list(get_role_benchmark(ROLE)["skills"])

ROADMAP = {
    "weeks": [
        {
            "week": i,
            "projectTitle": f"Project {i}",
            "techStack": ["Python"],
            "resources": [{"title": "Docs", "url": "https://docs.python.org"}] * 4,
        }
        for i in range(1, 6)
    ]
}


def add_project(user_id):
    asyncio.run(
        dynamo_service.put_item(
            "Projects",
            {
                "userId": user_id,
                "projectId": "p1",
                "name": "job-scout",
                "technologies": ["Python"],
                "highlights": ["h"],
            },
        )
    )


def test_roles_are_public(dynamo_client):
    roles = dynamo_client.get("/api/skill-gap/roles").json()["roles"]
    assert ROLE in [r["roleId"] for r in roles]


def test_analysis_scores_projects_and_caches_the_report(dynamo_client, dynamo_auth, bedrock):
    add_project(dynamo_auth["user_id"])
    bedrock.reply({DOMAINS[0]: 150, DOMAINS[1]: "40", DOMAINS[2]: -5})
    report = dynamo_client.post(
        "/api/skill-gap/analyse", json={"roleId": ROLE}, headers=dynamo_auth["headers"]
    ).json()
    assert report["userScores"][DOMAINS[0]] == 100
    assert report["userScores"][DOMAINS[1]] == 40
    assert report["userScores"][DOMAINS[2]] == 0
    assert report["projectCount"] == 1
    assert "### Project 1: job-scout" in bedrock.prompts[0]

    cached = dynamo_client.get("/api/skill-gap/report", headers=dynamo_auth["headers"]).json()
    assert cached["reportId"] == report["reportId"]
    assert dynamo_client.get(
        "/api/skill-gap/report?roleId=frontend-dev", headers=dynamo_auth["headers"]
    ).json() == {"report": None}


def test_analysis_without_projects_scores_zero(dynamo_client, dynamo_auth, bedrock):
    report = dynamo_client.post(
        "/api/skill-gap/analyse", json={"roleId": ROLE}, headers=dynamo_auth["headers"]
    ).json()
    assert set(report["userScores"].values()) == {0}
    assert report["overallFitPercent"] == 0
    assert bedrock.calls == []


def test_scoring_failure_falls_back_to_zero(dynamo_client, dynamo_auth, bedrock):
    add_project(dynamo_auth["user_id"])
    bedrock.reply("not json")
    report = dynamo_client.post(
        "/api/skill-gap/analyse", json={"roleId": ROLE}, headers=dynamo_auth["headers"]
    ).json()
    assert set(report["userScores"].values()) == {0}


def test_unknown_role_is_a_400(dynamo_client, dynamo_auth):
    r = dynamo_client.post(
        "/api/skill-gap/analyse", json={"roleId": "astronaut"}, headers=dynamo_auth["headers"]
    )
    assert (r.status_code, r.json()["detail"]) == (400, "Unknown role: astronaut")


def test_analysis_crash_is_a_500(dynamo_client, dynamo_auth, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("dynamo down")

    monkeypatch.setattr(gap_analysis.dynamo_service, "query", boom)
    r = dynamo_client.post(
        "/api/skill-gap/analyse", json={"roleId": ROLE}, headers=dynamo_auth["headers"]
    )
    assert r.status_code == 500


def test_roadmap_generation_and_milestones(dynamo_client, dynamo_auth, bedrock):
    h = dynamo_auth["headers"]
    assert (
        dynamo_client.post(
            "/api/skill-gap/roadmap/generate", json={"roleId": ROLE}, headers=h
        ).status_code
        == 400
    )

    dynamo_client.post("/api/skill-gap/analyse", json={"roleId": ROLE}, headers=h)
    bedrock.reply(ROADMAP)
    roadmap = dynamo_client.post(
        "/api/skill-gap/roadmap/generate", json={"roleId": ROLE}, headers=h
    ).json()
    assert roadmap["totalWeeks"] == 4
    assert len(roadmap["weeks"][0]["resources"]) == 3
    assert "Backend SDE" in bedrock.prompts[0]

    rid = roadmap["roadmapId"]
    assert dynamo_client.get(f"/api/skill-gap/roadmap/{rid}", headers=h).json()["roadmapId"] == rid
    assert [
        r["roadmapId"]
        for r in dynamo_client.get("/api/skill-gap/roadmaps", headers=h).json()["roadmaps"]
    ] == [rid]

    done = dynamo_client.patch(f"/api/skill-gap/roadmap/{rid}/milestone/2", headers=h).json()
    assert done["completedWeeks"] == 1
    assert done["weeks"][1]["completedAt"]
    assert (
        dynamo_client.get(f"/api/skill-gap/roadmap/{rid}", headers=h).json()["completedWeeks"] == 1
    )

    assert (
        dynamo_client.patch(f"/api/skill-gap/roadmap/{rid}/milestone/9", headers=h).status_code
        == 400
    )
    assert (
        dynamo_client.patch("/api/skill-gap/roadmap/nope/milestone/1", headers=h).status_code == 400
    )
    assert dynamo_client.get("/api/skill-gap/roadmap/nope", headers=h).status_code == 404


def test_roadmap_generation_failure_is_a_400(dynamo_client, dynamo_auth, bedrock):
    h = dynamo_auth["headers"]
    dynamo_client.post("/api/skill-gap/analyse", json={"roleId": ROLE}, headers=h)
    bedrock.reply("garbage")
    r = dynamo_client.post("/api/skill-gap/roadmap/generate", json={"roleId": ROLE}, headers=h)
    assert r.status_code == 400
    assert r.json()["detail"].startswith("Failed to generate learning roadmap")


def test_report_endpoint_returns_the_newest_analysis(dynamo_client, dynamo_auth):
    uid = dynamo_auth["user_id"]
    # reportId is a random UUID and the table's sort key, so put the newest
    # report on the smallest id to show order must come from createdAt
    for report_id, created in [
        ("ffff", "2026-01-01T00:00:00Z"),
        ("0000", "2026-03-01T00:00:00Z"),
        ("8888", "2026-02-01T00:00:00Z"),
    ]:
        asyncio.run(
            dynamo_service.put_item(
                "SkillGapReports",
                {
                    "userId": uid,
                    "reportId": report_id,
                    "roleId": ROLE,
                    "createdAt": created,
                    "gaps": [],
                },
            )
        )
    assert (
        dynamo_client.get("/api/skill-gap/report", headers=dynamo_auth["headers"]).json()[
            "reportId"
        ]
        == "0000"
    )


def test_reports_beyond_the_first_ten_ids_are_still_found(dynamo_client, dynamo_auth):
    uid = dynamo_auth["user_id"]
    for i in range(12):
        asyncio.run(
            dynamo_service.put_item(
                "SkillGapReports",
                {
                    "userId": uid,
                    "reportId": f"r{i:02d}",
                    "roleId": "frontend-dev" if i == 0 else ROLE,
                    "createdAt": f"2026-01-{i + 1:02d}",
                },
            )
        )
    found = dynamo_client.get(
        "/api/skill-gap/report?roleId=frontend-dev", headers=dynamo_auth["headers"]
    ).json()
    assert found["reportId"] == "r00"


def test_roadmaps_list_newest_first(dynamo_client, dynamo_auth):
    uid = dynamo_auth["user_id"]
    for roadmap_id, created in [("ffff", "2026-01-01"), ("0000", "2026-03-01")]:
        asyncio.run(
            dynamo_service.put_item(
                "Roadmaps", {"userId": uid, "roadmapId": roadmap_id, "createdAt": created}
            )
        )
    listed = dynamo_client.get("/api/skill-gap/roadmaps", headers=dynamo_auth["headers"]).json()[
        "roadmaps"
    ]
    assert [r["roadmapId"] for r in listed] == ["0000", "ffff"]


def test_users_cannot_read_each_others_roadmaps(dynamo_client, dynamo_auth):
    asyncio.run(
        dynamo_service.put_item(
            "Roadmaps", {"userId": "someone-else", "roadmapId": "theirs", "weeks": []}
        )
    )
    assert (
        dynamo_client.get(
            "/api/skill-gap/roadmap/theirs", headers=dynamo_auth["headers"]
        ).status_code
        == 404
    )
    assert (
        dynamo_client.patch(
            "/api/skill-gap/roadmap/theirs/milestone/1", headers=dynamo_auth["headers"]
        ).status_code
        == 400
    )
