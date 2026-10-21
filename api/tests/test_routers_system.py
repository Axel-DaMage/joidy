"""Router tests for the /system/power endpoints (#1001).

Covers:
- GET /system/power/status — docker_available=false path (no socket / list
  failure), service listing, health parsing and hibernation detection.
- POST /system/power/{sleep,wake,shutdown} — 503 without Docker, correct
  per-service stop/start targeting with a fake aiodocker client.
- Pure helpers — compose label parsing for both Docker Compose and
  podman-compose label schemes.

The aiodocker client is faked entirely; no Docker socket is required.
"""

import pytest
from fastapi.testclient import TestClient

from routers import system


# --- Fakes --------------------------------------------------------------------


def _container(name: str, service: str, state: str = "running",
               project: str = "joidy", health: str | None = None,
               label_prefix: str = "com.docker.compose") -> dict:
    labels = {
        f"{label_prefix}.service": service,
        f"{label_prefix}.project": project,
    }
    data = {
        "Names": [f"/{name}"],
        "State": state,
        "Status": "Up 2 hours",
        "Labels": labels,
    }
    if health:
        data["Health"] = {"Status": health}
        data["Status"] = f"Up 2 hours ({health})"
    return data


class _FakeContainerHandle:
    """Stand-in for an aiodocker DockerContainer (show/start/stop)."""

    def __init__(self, data: dict):
        self._data = data
        self.stopped = False
        self.started = False

    async def show(self):
        return {"State": {"Running": self._data["State"] == "running"}}

    async def stop(self):
        self.stopped = True
        self._data["State"] = "exited"

    async def start(self):
        self.started = True
        self._data["State"] = "running"


class _FakeContainers:
    def __init__(self, containers: list[dict]):
        self._by_name = {c["Names"][0].lstrip("/"): _FakeContainerHandle(c) for c in containers}

    async def list(self, all: bool = False):  # noqa: A002 - matches aiodocker API
        return [h._data for h in self._by_name.values()]

    async def get(self, name: str):
        return self._by_name[name]


class _FakeDocker:
    def __init__(self, containers: list[dict]):
        self.containers = _FakeContainers(containers)


@pytest.fixture
def docker_unavailable(monkeypatch):
    """Force the no-Docker path for every endpoint."""
    async def _none():
        return None

    monkeypatch.setattr(system, "get_docker", _none)


@pytest.fixture
def fake_docker(monkeypatch):
    """Install a fake aiodocker client and return the factory."""

    def _install(containers: list[dict]) -> _FakeDocker:
        docker = _FakeDocker(containers)
        monkeypatch.setattr(system, "_docker_client", docker)
        monkeypatch.setattr(system, "_project_name", None)
        return docker

    return _install


# --- Pure helpers --------------------------------------------------------------


def test_container_dict_passthrough():
    data = {"a": 1}
    assert system._container_dict(data) is data


def test_container_dict_aiodocker_object():
    class FakeDockerContainer:
        _container = {"State": "running"}

    assert system._container_dict(FakeDockerContainer()) == {"State": "running"}


def test_compose_project_docker_labels():
    c = _container("api-1", "api", project="myproj")
    assert system._get_compose_project(c) == "myproj"


def test_compose_project_podman_labels():
    c = _container("api-1", "api", project="podproj", label_prefix="io.podman.compose")
    assert system._get_compose_project(c) == "podproj"


def test_compose_service_from_label_list():
    c = _container("api-1", "api")
    c["Labels"] = ["com.docker.compose.service=api", "com.docker.compose.project=joidy"]
    assert system._get_compose_service(c) == "api"


def test_parse_health_variants():
    assert system._parse_health(_container("a", "api", health="healthy")) is True
    assert system._parse_health(_container("a", "api", health="unhealthy")) is False
    assert system._parse_health(_container("a", "api")) is None
    assert system._parse_health({"Status": "Up 1 hour (healthy)", "Names": ["/x"]}) is True


# --- GET /system/power/status ---------------------------------------------------


def test_status_no_docker(client: TestClient, docker_unavailable):
    """Without a Docker socket the endpoint degrades, not 500s."""
    response = client.get("/system/power/status")
    assert response.status_code == 200
    data = response.json()
    assert data["docker_available"] is False
    assert data["services"] == []
    assert data["hibernating"] is False


def test_status_lists_services(client: TestClient, fake_docker):
    containers = [
        _container("joidy-postgres-1", "postgres", health="healthy"),
        _container("joidy-api-1", "api", health="healthy"),
        _container("joidy-ai-service-1", "ai-service", health="healthy"),
        _container("joidy-worker-1", "worker", state="exited"),
        _container("joidy-frontend-1", "frontend"),
        _container("other-1", "not-joidy"),
        _container("other-proj-api-1", "api", project="other-project"),
    ]
    fake_docker(containers)

    response = client.get("/system/power/status")
    assert response.status_code == 200
    data = response.json()
    assert data["docker_available"] is True

    names = [s["name"] for s in data["services"]]
    assert names == ["postgres", "api", "ai-service", "worker", "frontend"]
    assert "not-joidy" not in names
    assert len(names) == 5  # the other-project api container is filtered out

    worker = next(s for s in data["services"] if s["name"] == "worker")
    assert worker["status"] == "stopped"
    assert worker["healthy"] is None
    api = next(s for s in data["services"] if s["name"] == "api")
    assert api["healthy"] is True

    # worker (a HIBERNATE_SERVICE) is stopped -> hibernating
    assert data["hibernating"] is True


def test_status_not_hibernating_when_all_running(client: TestClient, fake_docker):
    containers = [
        _container("joidy-api-1", "api", health="healthy"),
        _container("joidy-ai-service-1", "ai-service"),
        _container("joidy-worker-1", "worker"),
    ]
    fake_docker(containers)

    data = client.get("/system/power/status").json()
    assert data["hibernating"] is False


# --- POST /system/power/sleep ---------------------------------------------------


def test_sleep_no_docker_503(client: TestClient, docker_unavailable):
    response = client.post("/system/power/sleep")
    assert response.status_code == 503


def test_sleep_stops_only_hibernate_services(client: TestClient, fake_docker):
    containers = [
        _container("joidy-api-1", "api", health="healthy"),
        _container("joidy-ai-service-1", "ai-service"),
        _container("joidy-worker-1", "worker"),
        _container("joidy-frontend-1", "frontend"),
        _container("joidy-postgres-1", "postgres"),
    ]
    docker = fake_docker(containers)

    response = client.post("/system/power/sleep")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert sorted(data["affected"]) == ["ai-service", "worker"]

    handles = docker.containers._by_name
    assert handles["joidy-ai-service-1"].stopped
    assert handles["joidy-worker-1"].stopped
    assert not handles["joidy-frontend-1"].stopped
    assert not handles["joidy-postgres-1"].stopped
    assert not handles["joidy-api-1"].stopped


# --- POST /system/power/wake ----------------------------------------------------


def test_wake_no_docker_503(client: TestClient, docker_unavailable):
    assert client.post("/system/power/wake").status_code == 503


def test_wake_starts_only_stopped_hibernate_services(client: TestClient, fake_docker):
    containers = [
        _container("joidy-api-1", "api", health="healthy"),
        _container("joidy-ai-service-1", "ai-service", state="exited"),
        _container("joidy-worker-1", "worker"),
    ]
    docker = fake_docker(containers)

    response = client.post("/system/power/wake")
    assert response.status_code == 200
    data = response.json()
    assert data["affected"] == ["ai-service"]

    handles = docker.containers._by_name
    assert handles["joidy-ai-service-1"].started
    assert not handles["joidy-worker-1"].started  # already running


# --- POST /system/power/shutdown ------------------------------------------------


def test_shutdown_no_docker_503(client: TestClient, docker_unavailable):
    assert client.post("/system/power/shutdown").status_code == 503


def test_shutdown_stops_in_order_keeps_api_and_postgres(client: TestClient, fake_docker):
    containers = [
        _container("joidy-api-1", "api", health="healthy"),
        _container("joidy-postgres-1", "postgres"),
        _container("joidy-frontend-1", "frontend"),
        _container("joidy-ai-service-1", "ai-service"),
        _container("joidy-worker-1", "worker"),
    ]
    docker = fake_docker(containers)

    response = client.post("/system/power/shutdown")
    assert response.status_code == 200
    assert response.json()["affected"] == ["frontend", "ai-service", "worker"]

    handles = docker.containers._by_name
    assert not handles["joidy-api-1"].stopped
    assert not handles["joidy-postgres-1"].stopped
