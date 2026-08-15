"""System power management router.

Provides endpoints to check service status and hibernate/wake/shutdown
the Docker stack from the web UI. Uses aiodocker to communicate with
the Docker Engine API via the mounted Docker socket.
"""

import logging
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system/power", tags=["system-power"])

# Docker Compose service names (from the `com.docker.compose.service` label).
# These are independent of the project name / directory name.
HIBERNATE_SERVICES = {"ai-service", "worker"}

# All Joidy services to show in the status list (by compose service name).
ALL_SERVICES = {"ai-service", "worker", "frontend", "api", "postgres"}

# Services to stop during full shutdown (in order).
# postgres and api are kept so the response can be sent and data isn't lost.
SHUTDOWN_SERVICES = ["frontend", "ai-service", "worker"]

_docker_client = None


async def get_docker():
    """Lazily create and cache the aiodocker client."""
    global _docker_client
    if _docker_client is None:
        try:
            import aiodocker

            sock_path = os.environ.get("DOCKER_SOCK_PATH", "/var/run/docker.sock")
            _docker_client = aiodocker.Docker(url=f"unix://{sock_path}")
        except Exception as exc:
            logger.warning("Docker socket not accessible: %s", exc)
            return None
    return _docker_client


class ServiceStatus(BaseModel):
    name: str
    status: Literal["running", "stopped", "unknown"]
    healthy: bool | None = None


class PowerStatusResponse(BaseModel):
    docker_available: bool
    services: list[ServiceStatus]
    hibernating: bool


class PowerActionResponse(BaseModel):
    status: str
    message: str
    affected: list[str] = []


def _get_compose_service(container: dict) -> str | None:
    """Extract the Docker Compose service name from container labels."""
    labels = container.get("Labels") or {}
    if isinstance(labels, dict):
        return labels.get("com.docker.compose.service")
    # Docker API returns labels as a list of "key=value" strings in some versions
    if isinstance(labels, list):
        for label in labels:
            if isinstance(label, str) and label.startswith("com.docker.compose.service="):
                return label.split("=", 1)[1]
    return None


def _get_container_name(container: dict) -> str:
    """Get the container name without the leading slash."""
    names = container.get("Names") or []
    if names:
        return names[0].lstrip("/")
    return container.get("Id", "unknown")[:12]


def _parse_health(container: dict) -> bool | None:
    """Parse health status from the Docker API list response.

    Returns True (healthy), False (unhealthy), or None (no healthcheck).
    """
    health = container.get("Health")
    if health and isinstance(health, dict):
        status = health.get("Status")
        if status == "healthy":
            return True
        if status == "unhealthy":
            return False
        # "none" or other values → no healthcheck configured
        return None

    # Fallback: parse the Status string (e.g., "Up 2 hours (healthy)")
    status_str = container.get("Status", "")
    if "(healthy)" in status_str:
        return True
    if "(unhealthy)" in status_str:
        return False
    return None


@router.get("/status", response_model=PowerStatusResponse)
async def get_power_status(_=Depends(get_current_user)):
    """Get the status of all Joidy services."""
    docker = await get_docker()
    if docker is None:
        return PowerStatusResponse(
            docker_available=False,
            services=[],
            hibernating=False,
        )

    try:
        containers = await docker.containers.list(all=True)
    except Exception as exc:
        logger.error("Failed to list containers: %s", exc)
        return PowerStatusResponse(
            docker_available=False,
            services=[],
            hibernating=False,
        )

    # Filter to Joidy containers by compose service label
    joidy_containers = []
    for c in containers:
        svc = _get_compose_service(c)
        if svc and svc in ALL_SERVICES:
            joidy_containers.append((svc, c))

    # Sort by a fixed order for consistent display
    service_order = ["postgres", "api", "ai-service", "worker", "frontend"]
    joidy_containers.sort(key=lambda pair: service_order.index(pair[0]) if pair[0] in service_order else 99)

    services: list[ServiceStatus] = []
    hibernating = False

    for svc_name, c in joidy_containers:
        state = c.get("State", "unknown")
        status = "running" if state == "running" else "stopped"
        healthy = _parse_health(c) if status == "running" else None

        services.append(ServiceStatus(name=svc_name, status=status, healthy=healthy))

        if svc_name in HIBERNATE_SERVICES and status == "stopped":
            hibernating = True

    return PowerStatusResponse(
        docker_available=True,
        services=services,
        hibernating=hibernating,
    )


@router.post("/sleep", response_model=PowerActionResponse)
async def hibernate_services(_=Depends(get_current_user)):
    """Stop heavy services (ai-service, worker) to save resources.
    api, frontend, and postgres remain running."""
    docker = await get_docker()
    if docker is None:
        raise HTTPException(status_code=503, detail="Docker socket not available. Use the CLI instead.")

    affected: list[str] = []
    for c in await docker.containers.list(all=True):
        svc = _get_compose_service(c)
        if svc not in HIBERNATE_SERVICES:
            continue
        try:
            container_name = _get_container_name(c)
            container = await docker.containers.get(container_name)
            info = await container.show()
            if info.get("State", {}).get("Running"):
                await container.stop()
                affected.append(svc)
                logger.info("Stopped container %s for hibernation", container_name)
        except Exception as exc:
            logger.warning("Failed to stop %s: %s", svc, exc)

    return PowerActionResponse(
        status="ok",
        message=f"Hibernated {len(affected)} service(s). Use Wake or 'joidy wake' to restart them.",
        affected=affected,
    )


@router.post("/wake", response_model=PowerActionResponse)
async def wake_services(_=Depends(get_current_user)):
    """Restart heavy services (ai-service, worker) from hibernation."""
    docker = await get_docker()
    if docker is None:
        raise HTTPException(status_code=503, detail="Docker socket not available. Use the CLI instead.")

    affected: list[str] = []
    for c in await docker.containers.list(all=True):
        svc = _get_compose_service(c)
        if svc not in HIBERNATE_SERVICES:
            continue
        try:
            container_name = _get_container_name(c)
            container = await docker.containers.get(container_name)
            info = await container.show()
            if not info.get("State", {}).get("Running"):
                await container.start()
                affected.append(svc)
                logger.info("Started container %s from hibernation", container_name)
        except Exception as exc:
            logger.warning("Failed to start %s: %s", svc, exc)

    return PowerActionResponse(
        status="ok",
        message=f"Woke {len(affected)} service(s).",
        affected=affected,
    )


@router.post("/shutdown", response_model=PowerActionResponse)
async def shutdown_services(_=Depends(get_current_user)):
    """Stop all services except postgres and the api itself.
    The user must use the CLI ('joidy up') to restart everything."""
    docker = await get_docker()
    if docker is None:
        raise HTTPException(status_code=503, detail="Docker socket not available. Use the CLI instead.")

    # Build a map of compose service name → container name
    svc_to_container_name: dict[str, str] = {}
    for c in await docker.containers.list(all=True):
        svc = _get_compose_service(c)
        if svc and svc in SHUTDOWN_SERVICES:
            svc_to_container_name[svc] = _get_container_name(c)

    affected: list[str] = []
    for svc_name in SHUTDOWN_SERVICES:
        container_name = svc_to_container_name.get(svc_name)
        if not container_name:
            continue
        try:
            container = await docker.containers.get(container_name)
            info = await container.show()
            if info.get("State", {}).get("Running"):
                await container.stop()
                affected.append(svc_name)
                logger.info("Stopped container %s for shutdown", container_name)
        except Exception as exc:
            logger.warning("Failed to stop %s: %s", svc_name, exc)

    return PowerActionResponse(
        status="ok",
        message="Shutdown complete. Run 'joidy up' in your terminal to restart all services.",
        affected=affected,
    )
