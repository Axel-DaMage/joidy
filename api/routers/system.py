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

# Services that are stopped during hibernation (heavy compute).
# api, frontend, and postgres stay running so the web UI remains accessible.
HIBERNATE_SERVICES = ["joidy-ai-service-1", "joidy-worker-1"]

# All Joidy services (for full shutdown). The api itself is excluded because
# stopping it from within itself would prevent sending the response.
ALL_SERVICES = [
    "joidy-ai-service-1",
    "joidy-worker-1",
    "joidy-frontend-1",
    # postgres is kept running so data isn't lost; user can stop it via CLI.
]

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

    joidy_containers = [c for c in containers if c["Names"][0].lstrip("/") in ALL_SERVICES + ["joidy-postgres-1"]]

    services: list[ServiceStatus] = []
    hibernating = False

    for c in joidy_containers:
        name = c["Names"][0].lstrip("/")
        state = c.get("State", "unknown")
        status = "running" if state == "running" else "stopped"
        healthy = None
        if status == "running":
            health = c.get("Health", {})
            if health:
                healthy = health.get("Status") == "healthy"

        services.append(ServiceStatus(name=name, status=status, healthy=healthy))

        if name in HIBERNATE_SERVICES and status == "stopped":
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
    for name in HIBERNATE_SERVICES:
        try:
            container = await docker.containers.get(name)
            info = await container.show()
            if info.get("State", {}).get("Running"):
                await container.stop()
                affected.append(name)
                logger.info("Stopped container %s for hibernation", name)
        except Exception as exc:
            logger.warning("Failed to stop %s: %s", name, exc)

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
    for name in HIBERNATE_SERVICES:
        try:
            container = await docker.containers.get(name)
            info = await container.show()
            if not info.get("State", {}).get("Running"):
                await container.start()
                affected.append(name)
                logger.info("Started container %s from hibernation", name)
        except Exception as exc:
            logger.warning("Failed to start %s: %s", name, exc)

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

    affected: list[str] = []
    # Stop in reverse dependency order: frontend → ai-service → worker
    stop_order = ["joidy-frontend-1", "joidy-ai-service-1", "joidy-worker-1"]
    for name in stop_order:
        try:
            container = await docker.containers.get(name)
            info = await container.show()
            if info.get("State", {}).get("Running"):
                await container.stop()
                affected.append(name)
                logger.info("Stopped container %s for shutdown", name)
        except Exception as exc:
            logger.warning("Failed to stop %s: %s", name, exc)

    return PowerActionResponse(
        status="ok",
        message="Shutdown complete. Run 'joidy up' in your terminal to restart all services.",
        affected=affected,
    )
