"""Template routes: the file-based template on DynamoDB and user templates on SQLite."""

import asyncio
import uuid

from app.models.template import Template
from tests.conftest import register_user

MINE = {"name": "Compact", "latex_content": "\\documentclass{article}", "category": "minimal"}


def test_dynamo_serves_the_built_in_template(dynamo_client, dynamo_auth):
    listed = dynamo_client.get("/api/templates").json()
    assert [t["id"] for t in listed] == ["system-base-template"]
    full = dynamo_client.get("/api/templates/system-base-template").json()
    assert full["latex_content"].startswith("\\documentclass")
    assert full["is_ats_tested"] is True
    assert dynamo_client.get("/api/templates/other").status_code == 404


def test_dynamo_rejects_template_writes(dynamo_client, dynamo_auth):
    h = dynamo_auth["headers"]
    assert dynamo_client.post("/api/templates", json=MINE, headers=h).status_code == 501
    assert dynamo_client.patch("/api/templates/x", json={"name": "y"}, headers=h).status_code == 501
    assert dynamo_client.delete("/api/templates/x", headers=h).status_code == 501
    assert dynamo_client.post("/api/templates/init-system").json() == {
        "message": "Templates are file-based in DynamoDB mode"
    }


def add_system_template():
    from app.core.database import AsyncSessionLocal

    async def _add():
        async with AsyncSessionLocal() as db:
            t = Template(
                name=f"System {uuid.uuid4().hex[:4]}",
                latex_content="SYS",
                is_system=True,
                category="pro",
            )
            db.add(t)
            await db.commit()
            return str(t.id)

    return asyncio.run(_add())


def test_sqlite_template_lifecycle(client, auth):
    h = auth["headers"]
    created = client.post("/api/templates", json=MINE, headers=h).json()
    assert (created["name"], created["is_system"], created["is_public"]) == (
        "Compact",
        False,
        False,
    )
    tid = created["id"]

    assert tid in [t["id"] for t in client.get("/api/templates", headers=h).json()]
    assert tid in [t["id"] for t in client.get("/api/templates?category=minimal", headers=h).json()]
    assert tid not in [t["id"] for t in client.get("/api/templates").json()]

    patched = client.patch(
        f"/api/templates/{tid}", json={"name": "Compact v2", "is_public": True}, headers=h
    ).json()
    assert (patched["name"], patched["is_public"]) == ("Compact v2", True)
    assert tid in [t["id"] for t in client.get("/api/templates").json()]

    assert client.delete(f"/api/templates/{tid}", headers=h).status_code == 200
    assert client.get(f"/api/templates/{tid}", headers=h).status_code == 404


def test_private_templates_are_hidden_from_other_users(client, auth):
    tid = client.post("/api/templates", json=MINE, headers=auth["headers"]).json()["id"]
    other = register_user(client, "Other Person")
    assert client.get(f"/api/templates/{tid}", headers=other["headers"]).status_code == 403
    assert (
        client.patch(
            f"/api/templates/{tid}", json={"name": "x"}, headers=other["headers"]
        ).status_code
        == 404
    )
    assert client.delete(f"/api/templates/{tid}", headers=other["headers"]).status_code == 404


def test_system_templates_are_read_only(client, auth):
    tid = add_system_template()
    h = auth["headers"]
    assert client.get(f"/api/templates/{tid}").json()["latex_content"] == "SYS"
    assert client.patch(f"/api/templates/{tid}", json={"name": "x"}, headers=h).status_code in (
        403,
        404,
    )
    assert client.delete(f"/api/templates/{tid}", headers=h).status_code in (403, 404)
    assert client.post("/api/templates/init-system").json()["message"].startswith("Initialized")
