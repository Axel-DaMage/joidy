"""Tests for pagination metadata headers on list endpoints (#579).

Verifies that:
1. /notes/ returns X-Total-Count, X-Has-More, X-Page-Size, X-Page-Offset headers
2. /personal-streaks/ returns the same pagination headers
3. /tags/graph returns X-Total-Nodes and X-Total-Edges headers
4. X-Has-More is correct when there are more items beyond the current page
5. X-Has-More is "false" when all items fit in the current page
6. Response body remains a plain list (backward compatible)

Note: Tests run against the real database, so they must not assume an
empty state. Instead, they create data and verify headers relative to
the observed total.
"""

from fastapi.testclient import TestClient


def test_notes_pagination_headers_present(client: TestClient):
    """/notes/ should have all pagination headers."""
    response = client.get("/notes/")
    assert response.status_code == 200
    assert "X-Total-Count" in response.headers
    assert "X-Has-More" in response.headers
    assert "X-Page-Size" in response.headers
    assert "X-Page-Offset" in response.headers
    # Body should still be a list (backward compatible)
    assert isinstance(response.json(), list)


def test_notes_pagination_has_more_true(client: TestClient):
    """With limit=1, has_more should be true if there are >1 notes."""
    # Create at least 2 notes
    client.post("/notes/", json={"title": "Pag Test A", "content": "Content A", "tags": []})
    client.post("/notes/", json={"title": "Pag Test B", "content": "Content B", "tags": []})

    response = client.get("/notes/?limit=1&skip=0")
    assert response.status_code == 200
    total = int(response.headers["X-Total-Count"])
    assert total >= 2
    assert response.headers["X-Has-More"] == "true"
    assert response.headers["X-Page-Size"] == "1"
    assert response.headers["X-Page-Offset"] == "0"
    assert len(response.json()) == 1


def test_notes_pagination_has_more_false_with_large_limit(client: TestClient):
    """With a very large limit, has_more should be false."""
    response = client.get("/notes/?limit=1000&skip=0")
    assert response.status_code == 200
    total = int(response.headers["X-Total-Count"])
    # With limit=1000 and skip=0, has_more is false if total <= 1000
    if total <= 1000:
        assert response.headers["X-Has-More"] == "false"
    assert response.headers["X-Page-Size"] == "1000"


def test_notes_pagination_with_skip(client: TestClient):
    """Pagination headers should reflect skip correctly."""
    response = client.get("/notes/?limit=1&skip=2")
    assert response.status_code == 200
    assert response.headers["X-Page-Offset"] == "2"
    assert response.headers["X-Page-Size"] == "1"
    # has_more should be true if there are items beyond skip+limit
    total = int(response.headers["X-Total-Count"])
    expected_has_more = (2 + 1) < total
    assert response.headers["X-Has-More"] == ("true" if expected_has_more else "false")


def test_personal_streaks_pagination_headers(client: TestClient):
    """Personal streaks should have pagination headers."""
    response = client.get("/personal-streaks/")
    assert response.status_code == 200
    assert "X-Total-Count" in response.headers
    assert "X-Has-More" in response.headers
    assert "X-Page-Size" in response.headers
    assert "X-Page-Offset" in response.headers
    # Body should still be a list (backward compatible)
    assert isinstance(response.json(), list)


def test_personal_streaks_pagination_with_limit(client: TestClient):
    """Personal streaks with limit=1 should have has_more=true if >1 streaks."""
    # Create at least 2 streaks
    client.post(
        "/personal-streaks/",
        json={"name": "Pag Streak A", "frequency": "DAILY", "category": "salud"},
    )
    client.post(
        "/personal-streaks/",
        json={"name": "Pag Streak B", "frequency": "DAILY", "category": "salud"},
    )

    response = client.get("/personal-streaks/?limit=1&offset=0")
    assert response.status_code == 200
    total = int(response.headers["X-Total-Count"])
    assert total >= 2
    assert response.headers["X-Has-More"] == "true"
    assert response.headers["X-Page-Size"] == "1"
    assert len(response.json()) == 1


def test_tags_graph_count_headers(client: TestClient):
    """Tags graph should have X-Total-Nodes and X-Total-Edges headers."""
    # Create a note with a tag to ensure graph has data
    client.post("/notes/", json={"title": "Graph Pag Test", "content": "Content #pagtest", "tags": ["pagtest"]})

    response = client.get("/tags/graph")
    assert response.status_code == 200
    assert "X-Total-Nodes" in response.headers
    assert "X-Total-Edges" in response.headers
    total_nodes = int(response.headers["X-Total-Nodes"])
    total_edges = int(response.headers["X-Total-Edges"])
    assert total_nodes > 0
    # Body should still be {nodes, edges} (backward compatible)
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) == total_nodes
    assert len(data["edges"]) == total_edges
