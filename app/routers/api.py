from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import DOCKER_APPS_PATH, MGMT_SCRIPT, SELF_STACK_NAME
from app.services import docker_service, process_service, stack_service

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

router = APIRouter()


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
    stack = stack_service.get_stack(name)
    if stack is None:
        return HTMLResponse(f'<div class="output-error">Stack "{name}" not found.</div>', status_code=404)

    if stack.is_self:
        return HTMLResponse('<div class="output-error">Cannot start stack-manager from within itself.</div>')

    task = await process_service.run_mgmt_command(
        [MGMT_SCRIPT, "use", name],
        stack_name=name,
        cwd=DOCKER_APPS_PATH,
    )
    return templates.TemplateResponse("partials/output.html", {
        "request": request,
        "task_id": task.task_id,
        "command": f"mgmt.sh use {name}",
    })


@router.post("/api/stacks/{name}/stop", response_class=HTMLResponse)
async def stop_stack(name: str, request: Request):
    stack = stack_service.get_stack(name)
    if stack is None:
        return HTMLResponse(f'<div class="output-error">Stack "{name}" not found.</div>', status_code=404)

    if stack.is_self:
        return HTMLResponse('<div class="output-error">Cannot stop stack-manager from within itself. Use the CLI.</div>')

    task = await process_service.run_mgmt_command(
        [MGMT_SCRIPT, "stop", name],
        stack_name=name,
        cwd=DOCKER_APPS_PATH,
    )
    return templates.TemplateResponse("partials/output.html", {
        "request": request,
        "task_id": task.task_id,
        "command": f"mgmt.sh stop {name}",
    })


@router.post("/api/stacks/upgrade", response_class=HTMLResponse)
async def upgrade_all(request: Request):
    task = await process_service.run_mgmt_command(
        [MGMT_SCRIPT, "upgrade"],
        stack_name="__upgrade__",
        cwd=DOCKER_APPS_PATH,
    )
    return templates.TemplateResponse("partials/output.html", {
        "request": request,
        "task_id": task.task_id,
        "command": "mgmt.sh upgrade",
    })


@router.post("/api/stacks/pull", response_class=HTMLResponse)
async def pull_all(request: Request):
    task = await process_service.run_mgmt_command(
        [MGMT_SCRIPT, "pull"],
        stack_name="__pull__",
        cwd=DOCKER_APPS_PATH,
    )
    return templates.TemplateResponse("partials/output.html", {
        "request": request,
        "task_id": task.task_id,
        "command": "mgmt.sh pull",
    })


@router.post("/api/cleanup", response_class=HTMLResponse)
async def cleanup(request: Request):
    task = await process_service.run_mgmt_command(
        [MGMT_SCRIPT, "cleanup"],
        stack_name="__cleanup__",
        cwd=DOCKER_APPS_PATH,
    )
    return templates.TemplateResponse("partials/output.html", {
        "request": request,
        "task_id": task.task_id,
        "command": "mgmt.sh cleanup",
    })


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
