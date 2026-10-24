"""DynamoDB CRUD wrapper, run against moto."""

from decimal import Decimal

import pytest
from boto3.dynamodb.conditions import Attr

from app.services.dynamo_service import _convert_decimals, _convert_floats, dynamo_service


def test_float_and_decimal_conversion_round_trips():
    stored = _convert_floats({"score": 0.75, "tags": [1.5, "x"], "nested": {"n": 2.0}})
    assert stored == {
        "score": Decimal("0.75"),
        "tags": [Decimal("1.5"), "x"],
        "nested": {"n": Decimal("2.0")},
    }
    assert _convert_decimals(stored) == {"score": 0.75, "tags": [1.5, "x"], "nested": {"n": 2}}


async def test_put_get_and_delete(aws):
    await dynamo_service.put_item(
        "Users", {"userId": "u1", "name": "Asha", "score": 0.5, "phone": None}
    )
    item = await dynamo_service.get_item("Users", {"userId": "u1"})
    assert item == {"userId": "u1", "name": "Asha", "score": 0.5}
    await dynamo_service.delete_item("Users", {"userId": "u1"})
    assert await dynamo_service.get_item("Users", {"userId": "u1"}) is None


async def test_put_honours_condition_expression(aws):
    from botocore.exceptions import ClientError

    await dynamo_service.put_item("Users", {"userId": "u1"})
    with pytest.raises(ClientError):
        await dynamo_service.put_item(
            "Users", {"userId": "u1"}, condition_expression=Attr("userId").not_exists()
        )


async def test_query_by_partition_and_sort_key(aws):
    for pid in ["gh-1", "gh-2", "manual-1"]:
        await dynamo_service.put_item("Projects", {"userId": "u1", "projectId": pid})
    await dynamo_service.put_item("Projects", {"userId": "u2", "projectId": "gh-9"})

    everything = await dynamo_service.query("Projects", "userId", "u1")
    assert [p["projectId"] for p in everything] == ["gh-1", "gh-2", "manual-1"]

    newest_first = await dynamo_service.query("Projects", "userId", "u1", scan_forward=False)
    assert newest_first[0]["projectId"] == "manual-1"

    exact = await dynamo_service.query(
        "Projects", "userId", "u1", sk_name="projectId", sk_value="gh-2"
    )
    assert [p["projectId"] for p in exact] == ["gh-2"]

    prefixed = await dynamo_service.query(
        "Projects", "userId", "u1", sk_name="projectId", sk_begins_with="gh-"
    )
    assert [p["projectId"] for p in prefixed] == ["gh-1", "gh-2"]


async def test_query_never_returns_more_than_the_limit(aws):
    # DynamoDB applies Limit before the filter, so the wrapper pages until it
    # has enough. Page one (p00-p02) holds one match, page two (p03-p05) three.
    matches = {0, 3, 4, 5}
    for i in range(8):
        await dynamo_service.put_item(
            "Projects", {"userId": "u1", "projectId": f"p{i:02d}", "keep": i in matches}
        )
    found = await dynamo_service.query(
        "Projects", "userId", "u1", filter_expression=Attr("keep").eq(True), limit=3
    )
    assert [p["projectId"] for p in found] == ["p00", "p03", "p04"]


async def test_update_sets_and_removes_attributes(aws):
    await dynamo_service.put_item("Users", {"userId": "u1", "name": "Asha", "phone": "123"})
    updated = await dynamo_service.update_item(
        "Users", {"userId": "u1"}, {"name": "Asha E.", "phone": None, "fit": 0.25}
    )
    assert updated == {"userId": "u1", "name": "Asha E.", "fit": 0.25}


async def test_scan_filters_and_limits(aws):
    for i in range(5):
        await dynamo_service.put_item(
            "Jobs", {"jobId": f"j{i}", "source": "naukri" if i < 3 else "unstop"}
        )
    naukri = await dynamo_service.scan("Jobs", filter_expression=Attr("source").eq("naukri"))
    assert sorted(j["jobId"] for j in naukri) == ["j0", "j1", "j2"]
    assert len(await dynamo_service.scan("Jobs", limit=2)) == 2


async def test_upsert_job_inserts_then_backfills_only_empty_descriptions(aws):
    assert (
        await dynamo_service.upsert_job({"jobId": "j1", "title": "SDE", "description": ""}) is True
    )
    assert (
        await dynamo_service.upsert_job({"jobId": "j1", "title": "SDE", "description": ""}) is False
    )
    assert (
        await dynamo_service.upsert_job(
            {"jobId": "j1", "description": "Build APIs", "updatedAt": "t1"}
        )
        is True
    )
    assert (await dynamo_service.get_item("Jobs", {"jobId": "j1"}))["description"] == "Build APIs"
    assert await dynamo_service.upsert_job({"jobId": "j1", "description": "Other text"}) is False
    assert (await dynamo_service.get_item("Jobs", {"jobId": "j1"}))["description"] == "Build APIs"


async def test_ensure_job_scout_tables_is_idempotent(aws):
    aws.Table("ProjectRoadmaps").delete()
    await dynamo_service.ensure_job_scout_tables()
    await dynamo_service.ensure_job_scout_tables()
    assert "ProjectRoadmaps" in aws.meta.client.list_tables()["TableNames"]


def test_ids_and_timestamps():
    assert len(dynamo_service.generate_id()) == 36
    assert dynamo_service.now_iso().endswith("Z")
