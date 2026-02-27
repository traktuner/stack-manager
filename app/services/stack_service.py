from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.config import DOCKER_APPS_PATH, SELF_STACK_NAME

COMPOSE_FILENAMES = ("docker-compose.yml", "docker-compose.yaml")
PASS_URI_RE = re.compile(r"^pass://")


@dataclass
class StackInfo:
    name: str
    path: str
    mode: str  # "pass" | "legacy" | "none"
    active: bool  # .inuse marker exists
    compose_file: str = ""
    services: list[str] = field(default_factory=list)
    service_map: dict[str, str] = field(default_factory=dict)  # container_name -> service_name
    pass_refs: list[str] = field(default_factory=list)
    is_self: bool = False


def _find_compose_file(stack_dir: Path) -> Path | None:
    for name in COMPOSE_FILENAMES:
        p = stack_dir / name
        if p.is_file():
            return p
    return None


def _parse_services(compose_path: Path) -> tuple[list[str], dict[str, str]]:
    """Parse compose file, return (container_names, {container_name: service_name})."""
    try:
        data = yaml.safe_load(compose_path.read_text())
        if not data or "services" not in data:
            return [], {}
        services = []
        service_map = {}
        for svc_name, svc_conf in data["services"].items():
            container_name = svc_conf.get("container_name", svc_name)
            services.append(container_name)
            service_map[container_name] = svc_name
        return services, service_map
    except Exception:
        return [], {}


def _parse_pass_refs(template_path: Path) -> list[str]:
    refs = []
    try:
        for line in template_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                value = line.split("=", 1)[1]
                if PASS_URI_RE.match(value):
                    refs.append(value)
    except Exception:
        pass
    return refs


def list_stacks() -> list[StackInfo]:
    apps_dir = Path(DOCKER_APPS_PATH)
    if not apps_dir.is_dir():
        return []

    stacks = []
    for entry in sorted(apps_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue

        compose = _find_compose_file(entry)
        if compose is None:
            continue

        template = entry / ".env.template"
        env_file = entry / ".env"
        inuse = entry / ".inuse"

        if template.is_file():
            mode = "pass"
            pass_refs = _parse_pass_refs(template)
        elif env_file.is_file():
            mode = "legacy"
            pass_refs = []
        else:
            mode = "none"
            pass_refs = []

        services, service_map = _parse_services(compose)
        stacks.append(StackInfo(
            name=entry.name,
            path=str(entry),
            mode=mode,
            active=inuse.is_file(),
            compose_file=compose.name,
            services=services,
            service_map=service_map,
            pass_refs=pass_refs,
            is_self=(entry.name == SELF_STACK_NAME),
        ))

    return stacks


def get_stack(name: str) -> StackInfo | None:
    for s in list_stacks():
        if s.name == name:
            return s
    return None
