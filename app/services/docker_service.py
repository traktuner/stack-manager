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
    update_available: bool = False


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

        # Check if a newer image exists locally for this container
        update_available = False
        if c.status == "running":
            image_ref = c.attrs.get("Config", {}).get("Image", "")
            if image_ref:
                try:
                    current = client.images.get(image_ref)
                    update_available = current.id != c.image.id
                except Exception:
                    pass

        result[c.name] = ContainerStatus(
            name=c.name,
            status=c.status,
            health=health,
            image=image,
            started_at=c.attrs.get("State", {}).get("StartedAt", ""),
            update_available=update_available,
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
            "image": cs.image if cs else "unknown",
            "update_available": cs.update_available if cs else False,
        })

    total = len(service_names)
    if running == total:
        state = "running"
    elif running > 0:
        state = "partial"
    else:
        state = "stopped"

    # Check if any running container is unhealthy
    has_unhealthy = any(
        c["health"] == "unhealthy" for c in containers if c["status"] == "running"
    )
    if has_unhealthy and state in ("running", "partial"):
        state = "unhealthy"

    updates = sum(1 for c in containers if c["update_available"])

    return {"state": state, "running": running, "total": total, "containers": containers, "updates": updates}


def get_container_logs(name: str, tail: int = 100) -> str:
    """Return the last N lines of logs for a container."""
    try:
        client = _get_client()
        container = client.containers.get(name)
        logs = container.logs(tail=tail, timestamps=True).decode("utf-8", errors="replace")
        return logs
    except docker.errors.NotFound:
        return f"Container '{name}' not found."
    except Exception as e:
        return f"Error fetching logs: {e}"


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
