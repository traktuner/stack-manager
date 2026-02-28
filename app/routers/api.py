from __future__ import annotations

import os
import shutil
from html import escape
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.config import SAFE_NAME_RE
from app.main_templates import templates
from app.services import docker_service, mgmt_service, process_service, stack_service

router = APIRouter()


def _validate_name(name: str) -> str | None:
    """Return an HTML error response string if name is invalid, else None."""
    if not SAFE_NAME_RE.match(name):
        return f'<div class="output-error">Invalid name: "{escape(name)}"</div>'
    return None


def _build_stack_data() -> list[dict]:
    """Build enriched stack data with container statuses."""
    stacks = stack_service.list_stacks()
    all_statuses = docker_service.get_all_container_statuses()

    result = []
    for s in stacks:
        status = docker_service.get_stack_status(s.services, all_statuses)
        result.append({
            "name": s.name,
            "mode": s.mode,
            "active": s.active,
            "is_self": s.is_self,
            "busy": process_service.is_stack_busy(s.name),
            "services": s.services,
            "service_map": s.service_map,
            "status": status,
        })

    # Sort: running first, then partial, then stopped, then alphabetical
    state_order = {"running": 0, "partial": 1, "stopped": 2, "unknown": 3}
    result.sort(key=lambda x: (state_order.get(x["status"]["state"], 9), x["name"]))
    return result


@router.get("/api/stacks", response_class=HTMLResponse)
async def get_stacks(request: Request):
    stacks = _build_stack_data()
    return templates.TemplateResponse("partials/stack_list.html", {
        "request": request,
        "stacks": stacks,
    })


@router.post("/api/stacks/{name}/start", response_class=HTMLResponse)
async def start_stack(name: str, request: Request):
    err = _validate_name(name)
    if err:
        return HTMLResponse(err, status_code=400)

    stack = stack_service.get_stack(name)
    if stack is None:
        return HTMLResponse(f'<div class="output-error">Stack "{escape(name)}" not found.</div>', status_code=404)

    if stack.is_self:
        return HTMLResponse('<div class="output-error">Cannot start stack-manager from within itself.</div>')

    task = await mgmt_service.start_stack(name)
    return templates.TemplateResponse("partials/output.html", {
        "request": request,
        "task_id": task.task_id,
        "command": f"start {name}",
    })


@router.post("/api/stacks/{name}/stop", response_class=HTMLResponse)
async def stop_stack(name: str, request: Request):
    err = _validate_name(name)
    if err:
        return HTMLResponse(err, status_code=400)

    stack = stack_service.get_stack(name)
    if stack is None:
        return HTMLResponse(f'<div class="output-error">Stack "{escape(name)}" not found.</div>', status_code=404)

    if stack.is_self:
        return HTMLResponse('<div class="output-error">Cannot stop stack-manager from within itself.</div>')

    task = await mgmt_service.stop_stack(name)
    return templates.TemplateResponse("partials/output.html", {
        "request": request,
        "task_id": task.task_id,
        "command": f"stop {name}",
    })


@router.post("/api/stacks/{stack_name}/services/{service_name}/upgrade", response_class=HTMLResponse)
async def upgrade_service(stack_name: str, service_name: str, request: Request):
    for n in (stack_name, service_name):
        err = _validate_name(n)
        if err:
            return HTMLResponse(err, status_code=400)

    stack = stack_service.get_stack(stack_name)
    if stack is None:
        return HTMLResponse(f'<div class="output-error">Stack "{escape(stack_name)}" not found.</div>', status_code=404)

    if stack.is_self:
        return HTMLResponse('<div class="output-error">Cannot modify stack-manager from within itself.</div>')

    if service_name not in stack.service_map.values():
        return HTMLResponse(
            f'<div class="output-error">Service "{escape(service_name)}" not found in stack "{escape(stack_name)}".</div>',
            status_code=404,
        )

    task = await mgmt_service.upgrade_service(stack_name, service_name)
    return templates.TemplateResponse("partials/output.html", {
        "request": request,
        "task_id": task.task_id,
        "command": f"upgrade {stack_name}/{service_name}",
    })


@router.post("/api/stacks/{name}/upgrade", response_class=HTMLResponse)
async def upgrade_stack(name: str, request: Request):
    err = _validate_name(name)
    if err:
        return HTMLResponse(err, status_code=400)

    stack = stack_service.get_stack(name)
    if stack is None:
        return HTMLResponse(f'<div class="output-error">Stack "{escape(name)}" not found.</div>', status_code=404)

    if stack.is_self:
        return HTMLResponse('<div class="output-error">Cannot modify stack-manager from within itself.</div>')

    task = await mgmt_service.upgrade_stack(name)
    return templates.TemplateResponse("partials/output.html", {
        "request": request,
        "task_id": task.task_id,
        "command": f"upgrade {name}",
    })


@router.post("/api/stacks/upgrade", response_class=HTMLResponse)
async def upgrade_all(request: Request):
    task = await mgmt_service.upgrade_all()
    return templates.TemplateResponse("partials/output.html", {
        "request": request,
        "task_id": task.task_id,
        "command": "upgrade all",
    })


@router.post("/api/stacks/pull", response_class=HTMLResponse)
async def pull_all(request: Request):
    task = await mgmt_service.pull_images()
    return templates.TemplateResponse("partials/output.html", {
        "request": request,
        "task_id": task.task_id,
        "command": "pull images",
    })


@router.post("/api/cleanup", response_class=HTMLResponse)
async def cleanup(request: Request):
    task = await mgmt_service.cleanup()
    return templates.TemplateResponse("partials/output.html", {
        "request": request,
        "task_id": task.task_id,
        "command": "docker system prune",
    })


@router.post("/api/update", response_class=HTMLResponse)
async def update_configs(request: Request):
    task = await mgmt_service.update_configs()
    return templates.TemplateResponse("partials/output.html", {
        "request": request,
        "task_id": task.task_id,
        "command": "git pull",
    })


@router.post("/api/pass/login", response_class=HTMLResponse)
async def pass_login(request: Request):
    # Check pass-cli is installed
    if not shutil.which("pass-cli"):
        return HTMLResponse(
            '<div class="output-error">pass-cli is not installed in this container.</div>'
        )

    # Check storage is writable (needs a volume mount for data + config)
    data_dir = Path.home() / ".local" / "share"
    config_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    errors = []
    for label, d in [("data", data_dir), ("config", config_dir)]:
        try:
            d.mkdir(parents=True, exist_ok=True)
            test_file = d / ".write-test"
            test_file.touch()
            test_file.unlink()
        except OSError:
            errors.append(label)
    if errors:
        return HTMLResponse(
            '<div class="output-error">'
            "Cannot write to storage (" + ", ".join(errors) + " directory is read-only).<br><br>"
            "Mount a volume and set XDG_CONFIG_HOME in your docker-compose.yml:<br><br>"
            "<code>volumes:<br>"
            "&nbsp;&nbsp;- pass-cli-data:/root/.local/share<br><br>"
            "environment:<br>"
            "&nbsp;&nbsp;- XDG_CONFIG_HOME=/root/.local/share/config</code>"
            "</div>"
        )

    # Ensure pass-cli subdirectories exist (pass-cli doesn't create them itself)
    for d in [
        data_dir / "proton-pass-cli",
        config_dir / "proton-pass-cli",
    ]:
        d.mkdir(parents=True, exist_ok=True)

    # Ensure PROTON_PASS_KEY_PROVIDER is set for headless operation
    if not os.environ.get("PROTON_PASS_KEY_PROVIDER"):
        os.environ["PROTON_PASS_KEY_PROVIDER"] = "fs"

    form = await request.form()
    email = form.get("email", "").strip()
    if not email:
        return HTMLResponse('<div class="output-error">Email is required.</div>')

    task = await process_service.run_command(
        ["pass-cli", "login", email],
        stack_name="__pass_login__",
        cwd=str(data_dir),
        label=f"pass-cli login {email}",
    )
    return templates.TemplateResponse("partials/output.html", {
        "request": request,
        "task_id": task.task_id,
        "command": f"pass-cli login {email}",
    })


@router.get("/api/containers/{name}/logs")
async def container_logs(name: str, lines: int = 100):
    err = _validate_name(name)
    if err:
        return {"container": name, "logs": "Invalid container name."}

    # Clamp lines to prevent DoS
    lines = min(max(lines, 1), 10000)

    logs = docker_service.get_container_logs(name, tail=lines)
    return {"container": name, "logs": logs}


@router.get("/api/status")
async def status():
    stacks = stack_service.list_stacks()
    pass_ok = await docker_service.check_pass_cli()
    active = sum(1 for s in stacks if s.active)
    return {
        "pass_cli": "ok" if pass_ok else "inactive",
        "stacks_total": len(stacks),
        "stacks_active": active,
    }
