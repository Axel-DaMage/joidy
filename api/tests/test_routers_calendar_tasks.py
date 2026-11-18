"""Router tests for the calendar tasks CRUD endpoints (#1230)."""

import datetime as dt

from fastapi.testclient import TestClient
from models.calendar_task import CalendarTask

FUTURE_DATE = "2099-07-20"


def _make_task(db_session, title="Test task", date=dt.date(2099, 7, 20), **kwargs):
    task = CalendarTask(title=title, date=date, **kwargs)
    db_session.add(task)
    db_session.commit()
    return task


def test_list_tasks_empty(client: TestClient):
    response = client.get("/calendar/tasks?start=2099-01-01&end=2099-12-31")
    assert response.status_code == 200
    assert response.json() == []


def test_create_task_minimal(client: TestClient):
    response = client.post(
        "/calendar/tasks",
        json={"title": "Write tests", "date": FUTURE_DATE},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Write tests"
    assert data["priority"] == "MEDIUM"
    assert data["done"] is False
    assert data["source"] == "JOIDY"
    assert data["start_time"] is None


def test_create_task_full(client: TestClient):
    response = client.post(
        "/calendar/tasks",
        json={
            "title": "Urgent thing",
            "date": FUTURE_DATE,
            "start_time": "10:30:00",
            "end_time": "11:30:00",
            "priority": "URGENT",
            "color": "#ff0000",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["priority"] == "URGENT"
    assert data["start_time"] == "10:30:00"
    assert data["end_time"] == "11:30:00"
    assert data["color"] == "#ff0000"


def test_create_task_rejects_empty_title(client: TestClient):
    response = client.post("/calendar/tasks", json={"title": "", "date": FUTURE_DATE})
    assert response.status_code == 422


def test_create_task_rejects_bad_priority(client: TestClient):
    response = client.post(
        "/calendar/tasks",
        json={"title": "x", "date": FUTURE_DATE, "priority": "WHENEVER"},
    )
    assert response.status_code == 422


def test_create_task_rejects_end_before_start(client: TestClient):
    response = client.post(
        "/calendar/tasks",
        json={
            "title": "x",
            "date": FUTURE_DATE,
            "start_time": "11:00:00",
            "end_time": "10:00:00",
        },
    )
    assert response.status_code == 400


def test_create_task_unknown_goal_404(client: TestClient):
    response = client.post(
        "/calendar/tasks",
        json={"title": "x", "date": FUTURE_DATE, "goal_id": 99999999},
    )
    assert response.status_code == 404


def test_list_tasks_filters_by_range(client: TestClient, db_session):
    _make_task(db_session, title="In range", date=dt.date(2099, 7, 20))
    _make_task(db_session, title="Out of range", date=dt.date(2098, 1, 1))

    response = client.get("/calendar/tasks?start=2099-07-01&end=2099-07-31")
    assert response.status_code == 200
    titles = [t["title"] for t in response.json()]
    assert "In range" in titles
    assert "Out of range" not in titles


def test_list_tasks_orders_by_date_then_time(client: TestClient, db_session):
    _make_task(db_session, title="Later", date=dt.date(2099, 7, 20), start_time=dt.time(14, 0))
    _make_task(db_session, title="Earlier", date=dt.date(2099, 7, 20), start_time=dt.time(9, 0))
    _make_task(db_session, title="No time", date=dt.date(2099, 7, 20))
    _make_task(db_session, title="Prev day", date=dt.date(2099, 7, 19), start_time=dt.time(20, 0))

    response = client.get("/calendar/tasks?start=2099-07-01&end=2099-07-31")
    assert response.status_code == 200
    titles = [t["title"] for t in response.json()]
    assert titles == ["Prev day", "Earlier", "Later", "No time"]


def test_list_tasks_filter_by_single_date(client: TestClient, db_session):
    _make_task(db_session, title="On day", date=dt.date(2099, 7, 20))
    _make_task(db_session, title="Other day", date=dt.date(2099, 7, 21))

    response = client.get("/calendar/tasks?date=2099-07-20")
    assert response.status_code == 200
    titles = [t["title"] for t in response.json()]
    assert titles == ["On day"]


def test_list_tasks_invalid_date_400(client: TestClient):
    assert client.get("/calendar/tasks?date=not-a-date").status_code == 400
    assert client.get("/calendar/tasks?start=20-01-2099").status_code == 400


def test_patch_task_partial(client: TestClient, db_session):
    task = _make_task(db_session, title="Original")

    response = client.patch(f"/calendar/tasks/{task.id}", json={"priority": "HIGH"})
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Original"
    assert data["priority"] == "HIGH"


def test_patch_task_done_sets_done_at(client: TestClient, db_session):
    task = _make_task(db_session, title="To do")

    response = client.patch(f"/calendar/tasks/{task.id}", json={"done": True})
    assert response.status_code == 200
    data = response.json()
    assert data["done"] is True
    assert data["done_at"] is not None

    response = client.patch(f"/calendar/tasks/{task.id}", json={"done": False})
    assert response.status_code == 200
    data = response.json()
    assert data["done"] is False
    assert data["done_at"] is None


def test_patch_task_rejects_bad_times(client: TestClient, db_session):
    task = _make_task(db_session, title="Times", start_time=dt.time(15, 0))

    response = client.patch(
        f"/calendar/tasks/{task.id}",
        json={"end_time": "14:00:00"},
    )
    assert response.status_code == 400


def test_patch_task_unknown_goal_404(client: TestClient, db_session):
    task = _make_task(db_session, title="With goal")

    response = client.patch(f"/calendar/tasks/{task.id}", json={"goal_id": 99999999})
    assert response.status_code == 404


def test_toggle_done(client: TestClient, db_session):
    task = _make_task(db_session, title="Toggle me")

    r1 = client.post(f"/calendar/tasks/{task.id}/done")
    assert r1.status_code == 200
    assert r1.json()["done"] is True

    r2 = client.post(f"/calendar/tasks/{task.id}/done")
    assert r2.status_code == 200
    assert r2.json()["done"] is False


def test_delete_task(client: TestClient, db_session):
    task = _make_task(db_session, title="Delete me")

    response = client.delete(f"/calendar/tasks/{task.id}")
    assert response.status_code == 204
    assert client.get(f"/calendar/tasks?date={FUTURE_DATE}").json() == []


def test_404_on_missing_task(client: TestClient):
    assert client.patch("/calendar/tasks/99999999", json={"title": "x"}).status_code == 404
    assert client.delete("/calendar/tasks/99999999").status_code == 404
    assert client.post("/calendar/tasks/99999999/done").status_code == 404
