from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass

import docker


@dataclass
class ContainerStatus:
    name: str
    status: str  # running, exited, paused, restarting, created, removing, dead
    health: str  # healthy, unhealthy, starting, none, n/a
    image: str
    started_at: str


_client: docker.DockerClient | None = None


def _get_client() -> docker.DockerClient:
    global _client
    if _client is None:
        _client = docker.DockerClient(base_url="unix:///var/run/docker.sock")
    return _client


def get_all_container_statuses() -> dict[str, ContainerStatus]:
    """Return {container_name: ContainerStatus} for all containers."""
    try:
        client = _get_client()
        containers = client.containers.list(all=True)
    except Exception:
        return {}

    result = {}
    for c in containers:
        health_data = c.attrs.get("State", {}).get("Health", {})
        health = health_data.get("Status", "n/a") if health_data else "n/a"

        tags = c.image.tags if c.image.tags else []
        image = tags[0] if tags else c.attrs.get("Config", {}).get("Image", "unknown")

        result[c.name] = ContainerStatus(
            name=c.name,
            status=c.status,
            health=health,
            image=image,
            started_at=c.attrs.get("State", {}).get("StartedAt", ""),
        )
    return result


def get_stack_status(service_names: list[str], all_statuses: dict[str, ContainerStatus]) -> dict:
    """Determine overall stack status from its service container names."""
    if not service_names:
        return {"state": "unknown", "running": 0, "total": 0, "containers": []}

    containers = []
    running = 0
    for name in service_names:
        cs = all_statuses.get(name)
        if cs and cs.status == "running":
            running += 1
        containers.append({
            "name": name,
            "status": cs.status if cs else "not found",
            "health": cs.health if cs else "n/a",
        })

    total = len(service_names)
    if running == total:
        state = "running"
    elif running > 0:
        state = "partial"
    else:
        state = "stopped"

    return {"state": state, "running": running, "total": total, "containers": containers}


async def check_pass_cli() -> bool:
    """Check if pass-cli session is active."""
    if not shutil.which("pass-cli"):
        return False
    try:
        proc = await asyncio.create_subprocess_exec(
            "pass-cli", "test",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0
    except Exception:
        return False
