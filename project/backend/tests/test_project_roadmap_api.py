"""Project roadmap routes: suggestions, 7-day plans and day progress, on DynamoDB (moto)."""

import asyncio

from app.services.dynamo_service import dynamo_service

PLAN = {
    "domain": "Backend",
    "projectTitle": "URL shortener",
    "projectDescription": "Short links with stats",
    "techStack": ["Go"],
}
DAYS = {
    "days": [
        {
            "title": f"Day {i}",
            "tasks": [f"t{j}" for j in range(8)],
            "resources": [{"title": "Docs", "url": "https://go.dev"}] * 5,
            "estimatedHours": 2,
        }
        for i in range(1, 9)
    ]
}


def test_suggestions_are_capped_at_three(dynamo_client, dynamo_auth, bedrock):
    bedrock.reply({"projects": [{"title": f"Idea {i}", "difficulty": "hard"} for i in range(5)]})
    body = dynamo_client.post(
        "/api/project-roadmap/suggest", json={"domain": "Backend"}, headers=dynamo_auth["headers"]
    ).json()
    assert body["domain"] == "Backend"
    assert [p["title"] for p in body["projects"]] == ["Idea 0", "Idea 1", "Idea 2"]
    assert "**Backend**" in bedrock.prompts[0]


def test_suggestion_failures_are_reported(dynamo_client, dynamo_auth, bedrock):
    bedrock.reply("garbage")
    r = dynamo_client.post(
        "/api/project-roadmap/suggest", json={"domain": "Backend"}, headers=dynamo_auth["headers"]
    )
    assert r.status_code == 400
    assert (
        dynamo_client.post(
            "/api/project-roadmap/suggest", json={"domain": "x"}, headers=dynamo_auth["headers"]
        ).status_code
        == 422
    )


def test_plan_progress_unlock_and_delete(dynamo_client, dynamo_auth, bedrock):
    h = dynamo_auth["headers"]
    bedrock.reply(DAYS)
    plan = dynamo_client.post("/api/project-roadmap/plan", json=PLAN, headers=h).json()
    assert plan["totalDays"] == 7 and plan["totalHours"] == 14
    assert len(plan["days"][0]["tasks"]) == 6 and len(plan["days"][0]["resources"]) == 3
    rid = plan["projectRoadmapId"]

    assert [
        r["projectRoadmapId"]
        for r in dynamo_client.get("/api/project-roadmap/list", headers=h).json()["roadmaps"]
    ] == [rid]
    assert (
        dynamo_client.get(f"/api/project-roadmap/{rid}", headers=h).json()["projectTitle"]
        == "URL shortener"
    )

    skipped = dynamo_client.patch(f"/api/project-roadmap/{rid}/day/2/complete", headers=h)
    assert skipped.status_code == 400 and "day 1 is not yet completed" in skipped.json()["detail"]
    assert (
        dynamo_client.patch(f"/api/project-roadmap/{rid}/day/1/complete", headers=h).json()[
            "completedDays"
        ]
        == 1
    )
    assert (
        "already completed"
        in dynamo_client.patch(f"/api/project-roadmap/{rid}/day/1/complete", headers=h).json()[
            "detail"
        ]
    )
    assert (
        dynamo_client.patch(f"/api/project-roadmap/{rid}/day/99/complete", headers=h).status_code
        == 400
    )

    assert (
        dynamo_client.patch(f"/api/project-roadmap/{rid}/unlock-all", headers=h).json()[
            "unlockedAll"
        ]
        is True
    )
    assert dynamo_client.get(f"/api/project-roadmap/{rid}", headers=h).json()["unlockedAll"] is True

    assert dynamo_client.delete(f"/api/project-roadmap/{rid}", headers=h).json() == {
        "deleted": True
    }
    assert dynamo_client.get(f"/api/project-roadmap/{rid}", headers=h).status_code == 404
    assert dynamo_client.delete(f"/api/project-roadmap/{rid}", headers=h).status_code == 400


def test_plan_failure_is_a_400(dynamo_client, dynamo_auth, bedrock):
    bedrock.reply("garbage")
    assert (
        dynamo_client.post(
            "/api/project-roadmap/plan", json=PLAN, headers=dynamo_auth["headers"]
        ).status_code
        == 400
    )


def test_roadmaps_are_private_and_listed_newest_first(dynamo_client, dynamo_auth):
    uid, h = dynamo_auth["user_id"], dynamo_auth["headers"]
    for rid, created in [("ffff", "2026-01-01"), ("0000", "2026-03-01")]:
        asyncio.run(
            dynamo_service.put_item(
                "ProjectRoadmaps",
                {"userId": uid, "projectRoadmapId": rid, "createdAt": created, "days": []},
            )
        )
    asyncio.run(
        dynamo_service.put_item(
            "ProjectRoadmaps", {"userId": "someone-else", "projectRoadmapId": "theirs", "days": []}
        )
    )

    listed = dynamo_client.get("/api/project-roadmap/list", headers=h).json()["roadmaps"]
    assert [r["projectRoadmapId"] for r in listed] == ["0000", "ffff"]
    assert dynamo_client.get("/api/project-roadmap/theirs", headers=h).status_code == 404
    for path in ("/theirs/unlock-all", "/theirs/day/1/complete"):
        assert dynamo_client.patch(f"/api/project-roadmap{path}", headers=h).status_code == 400
    assert dynamo_client.delete("/api/project-roadmap/theirs", headers=h).status_code == 400
