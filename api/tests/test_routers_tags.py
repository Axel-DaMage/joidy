import json
from uuid import uuid4

from fastapi.testclient import TestClient
from models.gamification import XPEvent


def _topic_connected_events(db_session, child_id: int):
    events = db_session.query(XPEvent).filter(XPEvent.event_type == "topic_connected").all()
    return [e for e in events if json.loads(e.metadata_json or "{}").get("child_id") == child_id]


def test_list_tags_empty(client: TestClient):
    response = client.get("/tags/")
    assert response.status_code == 200
    assert response.json() == []


def test_create_tag(client: TestClient):
    payload = {"name": "Work"}
    response = client.post("/tags/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "work"  # gets lowercased
    tag_id = data["id"]

    list_res = client.get("/tags/")
    tags = list_res.json()
    assert len(tags) == 1
    assert tags[0]["id"] == tag_id


def test_set_parent_tag(client: TestClient):
    client.post("/tags/", json={"name": "parent"})
    client.post("/tags/", json={"name": "child"})

    tags = client.get("/tags/").json()
    parent_id = next(t["id"] for t in tags if t["name"] == "parent")
    child_id = next(t["id"] for t in tags if t["name"] == "child")

    res = client.put(f"/tags/{child_id}/parent?parent_id={parent_id}")
    assert res.status_code == 200
    assert res.json()["parent_id"] == parent_id


def test_create_tag_with_parent_registers_topic_connected(client, db_session):
    suffix = uuid4().hex[:8]
    parent = client.post("/tags/", json={"name": f"parent-{suffix}"}).json()

    res = client.post("/tags/", json={"name": f"child-{suffix}", "parent_id": parent["id"]})
    assert res.status_code == 201

    events = _topic_connected_events(db_session, res.json()["id"])
    assert len(events) == 1
    assert events[0].xp == 8
    assert json.loads(events[0].metadata_json) == {
        "child_id": res.json()["id"],
        "parent_id": parent["id"],
    }


def test_create_tag_without_parent_no_topic_connected(client, db_session):
    suffix = uuid4().hex[:8]
    res = client.post("/tags/", json={"name": f"solo-{suffix}"})
    assert res.status_code == 201

    assert _topic_connected_events(db_session, res.json()["id"]) == []


def test_set_parent_registers_topic_connected_and_awards_xp(client, db_session):
    suffix = uuid4().hex[:8]
    stats_before = client.get("/gamification/stats").json()
    parent = client.post("/tags/", json={"name": f"parent-{suffix}"}).json()
    child = client.post("/tags/", json={"name": f"child-{suffix}"}).json()

    res = client.put(f"/tags/{child['id']}/parent?parent_id={parent['id']}")
    assert res.status_code == 200

    events = _topic_connected_events(db_session, child["id"])
    assert len(events) == 1
    assert events[0].xp == 8

    stats_after = client.get("/gamification/stats").json()
    assert stats_after["total_xp"] >= stats_before["total_xp"] + 8


def test_set_parent_same_parent_no_duplicate_event(client, db_session):
    suffix = uuid4().hex[:8]
    parent = client.post("/tags/", json={"name": f"parent-{suffix}"}).json()
    child = client.post("/tags/", json={"name": f"child-{suffix}"}).json()

    first = client.put(f"/tags/{child['id']}/parent?parent_id={parent['id']}")
    assert first.status_code == 200
    second = client.put(f"/tags/{child['id']}/parent?parent_id={parent['id']}")
    assert second.status_code == 200

    assert len(_topic_connected_events(db_session, child["id"])) == 1


def test_reparent_to_different_parent_registers_new_event(client, db_session):
    suffix = uuid4().hex[:8]
    parent_a = client.post("/tags/", json={"name": f"parent-a-{suffix}"}).json()
    parent_b = client.post("/tags/", json={"name": f"parent-b-{suffix}"}).json()
    child = client.post("/tags/", json={"name": f"child-{suffix}", "parent_id": parent_a["id"]}).json()

    res = client.put(f"/tags/{child['id']}/parent?parent_id={parent_b['id']}")
    assert res.status_code == 200
    assert res.json()["parent_id"] == parent_b["id"]

    events = _topic_connected_events(db_session, child["id"])
    assert len(events) == 2
    assert [json.loads(e.metadata_json)["parent_id"] for e in events] == [
        parent_a["id"],
        parent_b["id"],
    ]
