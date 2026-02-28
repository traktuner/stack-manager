"""Stack management operations — replaces external mgmt.sh script."""
from __future__ import annotations

import asyncio
import re
import uuid
from pathlib import Path

from app.config import COMPOSE_CMD, DOCKER_APPS_PATH
from app.services import process_service, stack_service

_PASS_URI_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=pass://(.+)$")


def _stack_dir(name: str) -> str:
    return str(Path(DOCKER_APPS_PATH) / name)


def _compose_args(*extra: str) -> list[str]:
    return [*COMPOSE_CMD, *extra]


def _pass_compose_args(*extra: str) -> list[str]:
    """Build a pass-cli wrapped compose command."""
    return [
        "pass-cli", "run", "--env-file", ".env.template", "--",
        *COMPOSE_CMD, "--env-file", ".env.template",
        *extra,
    ]


async def _check_secret(uri: str, cwd: str) -> bool:
    """Silently check if a pass-cli secret exists (no output)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pass-cli", "item", "view", uri,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=cwd,
        )
        await proc.wait()
        return proc.returncode == 0
    except Exception:
        return False


async def _validate_secrets(
    template_path: Path, cwd: str, task: process_service.TaskState
) -> bool:
    """Parse .env.template for pass:// refs and verify each secret exists.

    Returns True if all secrets are valid, False otherwise.
    """
    task.lines.append("Validating secrets...\n")
    checked = 0
    errors = 0

    for line in template_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _PASS_URI_RE.match(line)
        if not m:
            continue

        var_name = m.group(1)
        uri = f"pass://{m.group(2)}"
        checked += 1

        if await _check_secret(uri, cwd):
            task.lines.append(f"  ✓ {var_name}\n")
        else:
            task.lines.append(f"  ✗ {var_name} — secret not found: {uri}\n")
            errors += 1

    if checked == 0:
        task.lines.append("  No pass:// references found in template.\n")
    else:
        task.lines.append(f"  {checked} secret(s) checked, {errors} error(s).\n")

    return errors == 0


async def start_stack(name: str) -> process_service.TaskState:
    """Start a stack (equivalent to mgmt.sh use <name>)."""
    stack = stack_service.get_stack(name)
    if stack is None:
        return await _error_task(f'Stack "{name}" not found.')

    cwd = _stack_dir(name)

    if stack.mode == "pass":
        async def _script(task: process_service.TaskState) -> int:
            task.lines.append(f"[{name}] Using Proton Pass secret injection\n")

            task.lines.append("Checking pass-cli session...\n")
            code = await process_service.run_subprocess(
                ["pass-cli", "test"], cwd, task,
            )
            if code != 0:
                task.lines.append("Error: pass-cli session not active.\n")
                return 1

            template = Path(cwd) / ".env.template"
            if not await _validate_secrets(template, cwd, task):
                task.lines.append(f"Secret validation failed for {name}. Aborting.\n")
                return 1

            task.lines.append(f"Starting {name}...\n")
            code = await process_service.run_subprocess(
                _pass_compose_args("up", "-d", "--remove-orphans"),
                cwd, task,
            )
            if code == 0:
                Path(cwd, ".inuse").touch()
                task.lines.append(f"{name} started successfully.\n")
            return code

        return await process_service.run_script(_script, name, f"start {name}")
    else:
        async def _script(task: process_service.TaskState) -> int:
            task.lines.append(f"Starting {name}...\n")
            code = await process_service.run_subprocess(
                _compose_args("up", "-d", "--remove-orphans"), cwd, task,
            )
            if code == 0:
                Path(cwd, ".inuse").touch()
                task.lines.append(f"{name} started successfully.\n")
            return code

        return await process_service.run_script(_script, name, f"start {name}")


async def stop_stack(name: str) -> process_service.TaskState:
    """Stop a stack (equivalent to mgmt.sh stop <name>)."""
    stack = stack_service.get_stack(name)
    if stack is None:
        return await _error_task(f'Stack "{name}" not found.')

    cwd = _stack_dir(name)

    async def _script(task: process_service.TaskState) -> int:
        task.lines.append(f"Stopping {name}...\n")
        env_args = ["--env-file", ".env.template"] if stack.mode == "pass" else []
        code = await process_service.run_subprocess(
            _compose_args(*env_args, "down", "--remove-orphans"), cwd, task,
        )
        Path(cwd, ".inuse").unlink(missing_ok=True)
        task.lines.append(f"{name} stopped.\n")
        return code

    return await process_service.run_script(_script, name, f"stop {name}")


async def update_configs() -> process_service.TaskState:
    """Git pull latest stack definitions."""
    git_dir = Path(DOCKER_APPS_PATH) / ".git"
    if not git_dir.is_dir():
        return await _error_task(
            f"No git repository found at {DOCKER_APPS_PATH}.\n"
            "Mount a git-cloned repo as your DOCKER_APPS_PATH volume."
        )

    async def _script(task: process_service.TaskState) -> int:
        git_config_file = Path(DOCKER_APPS_PATH) / ".git" / "config"
        remote_url = ""
        try:
            for line in git_config_file.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith("url = "):
                    remote_url = stripped[6:]
                    break
        except Exception:
            pass

        git_cmd = ["git", "-C", DOCKER_APPS_PATH]

        if remote_url.startswith("git@") or remote_url.startswith("ssh://"):
            task.lines.append(
                "Remote uses SSH — using temporary HTTPS override\n\n"
            )
            git_cmd.extend([
                "-c", "url.https://github.com/.insteadOf=git@github.com:",
                "-c", "url.https://github.com/.insteadOf=ssh://git@github.com/",
            ])

        task.lines.append("Running git pull...\n")
        code = await process_service.run_subprocess(
            [*git_cmd, "pull", "--ff-only"],
            DOCKER_APPS_PATH, task,
        )
        if code == 0:
            task.lines.append("Update complete.\n")
        else:
            task.lines.append("Git pull failed.\n")
        return code

    return await process_service.run_script(_script, "__update__", "git pull")


async def pull_images() -> process_service.TaskState:
    """Pull Docker images for all active stacks."""

    async def _script(task: process_service.TaskState) -> int:
        stacks = stack_service.list_stacks()
        active = [s for s in stacks if s.active]
        if not active:
            task.lines.append("No active stacks to pull.\n")
            return 0

        task.lines.append("Pulling images for active stacks...\n")
        failed = 0
        for s in active:
            task.lines.append(f"  {s.name}... ")
            code = await process_service.run_subprocess(
                _compose_args("pull", "-q"),
                _stack_dir(s.name), task,
                suppress_env_warnings=True,
            )
            if code == 0:
                task.lines.append(f"  {s.name} done\n")
            else:
                task.lines.append(f"  {s.name} warning: pull failed\n")
                failed += 1

        task.lines.append("Pull complete.\n")
        return 1 if failed else 0

    return await process_service.run_script(_script, "__pull__", "pull images")


async def upgrade_all() -> process_service.TaskState:
    """Upgrade all active stacks (pull + recreate)."""

    async def _script(task: process_service.TaskState) -> int:
        stacks = stack_service.list_stacks()
        active = [s for s in stacks if s.active]
        if not active:
            task.lines.append("No active stacks to upgrade.\n")
            return 0

        needs_pass = any(s.mode == "pass" for s in active)
        if needs_pass:
            task.lines.append("Checking pass-cli session...\n")
            code = await process_service.run_subprocess(
                ["pass-cli", "test"], DOCKER_APPS_PATH, task,
            )
            if code != 0:
                task.lines.append("Error: pass-cli session required but not active. Aborting.\n")
                return 1
            task.lines.append("pass-cli session active.\n\n")

        success = 0
        failed = 0
        failed_names: list[str] = []

        task.lines.append("Upgrading active stacks...\n")
        task.lines.append("=========================\n\n")

        for s in active:
            cwd = _stack_dir(s.name)
            task.lines.append(f"[{s.name}] Upgrading...\n")

            if s.mode == "pass":
                template = Path(cwd) / ".env.template"
                if not await _validate_secrets(template, cwd, task):
                    task.lines.append(f"[{s.name}] Secret validation failed. Skipping.\n\n")
                    failed += 1
                    failed_names.append(s.name)
                    continue

                code = await process_service.run_subprocess(
                    _pass_compose_args("up", "-d", "--remove-orphans"),
                    cwd, task,
                )
            else:
                code = await process_service.run_subprocess(
                    _compose_args("up", "-d", "--remove-orphans"),
                    cwd, task,
                )

            if code == 0:
                success += 1
                task.lines.append(f"[{s.name}] OK\n\n")
            else:
                failed += 1
                failed_names.append(s.name)
                task.lines.append(f"[{s.name}] FAILED\n\n")

        task.lines.append("=========================\n")
        task.lines.append(f"Upgrade summary: {success} succeeded, {failed} failed\n")
        if failed_names:
            for n in failed_names:
                task.lines.append(f"  Failed: {n}\n")

        return 1 if failed else 0

    return await process_service.run_script(_script, "__upgrade__", "upgrade all")


async def upgrade_stack(name: str) -> process_service.TaskState:
    """Upgrade a single stack (pull + recreate all services)."""
    stack = stack_service.get_stack(name)
    if stack is None:
        return await _error_task(f'Stack "{name}" not found.')

    cwd = _stack_dir(name)

    async def _script(task: process_service.TaskState) -> int:
        task.lines.append(f"[{name}] Upgrading stack...\n")

        if stack.mode == "pass":
            task.lines.append("Checking pass-cli session...\n")
            code = await process_service.run_subprocess(
                ["pass-cli", "test"], cwd, task,
            )
            if code != 0:
                task.lines.append("Error: pass-cli session not active.\n")
                return 1

            template = Path(cwd) / ".env.template"
            if not await _validate_secrets(template, cwd, task):
                task.lines.append(f"Secret validation failed for {name}. Aborting.\n")
                return 1

            task.lines.append(f"Pulling images...\n")
            await process_service.run_subprocess(
                _pass_compose_args("pull"), cwd, task,
                suppress_env_warnings=True,
            )

            task.lines.append(f"Recreating containers...\n")
            code = await process_service.run_subprocess(
                _pass_compose_args("up", "-d", "--remove-orphans"), cwd, task,
            )
        else:
            task.lines.append(f"Pulling images...\n")
            await process_service.run_subprocess(
                _compose_args("pull"), cwd, task,
                suppress_env_warnings=True,
            )

            task.lines.append(f"Recreating containers...\n")
            code = await process_service.run_subprocess(
                _compose_args("up", "-d", "--remove-orphans"), cwd, task,
            )

        if code == 0:
            task.lines.append("Cleaning up old images...\n")
            await process_service.run_subprocess(
                ["docker", "image", "prune", "-f"], cwd, task,
            )
            task.lines.append(f"[{name}] Upgrade complete.\n")
        else:
            task.lines.append(f"[{name}] Upgrade failed.\n")
        return code

    return await process_service.run_script(_script, name, f"upgrade {name}")


async def upgrade_service(stack_name: str, service_name: str) -> process_service.TaskState:
    """Upgrade a single service within a stack (pull + recreate)."""
    stack = stack_service.get_stack(stack_name)
    if stack is None:
        return await _error_task(f'Stack "{stack_name}" not found.')

    cwd = _stack_dir(stack_name)

    async def _script(task: process_service.TaskState) -> int:
        task.lines.append(f"[{stack_name}] Upgrading service '{service_name}'...\n")

        task.lines.append(f"Pulling image for {service_name}...\n")
        if stack.mode == "pass":
            code = await process_service.run_subprocess(
                _pass_compose_args("pull", service_name), cwd, task,
                suppress_env_warnings=True,
            )
        else:
            code = await process_service.run_subprocess(
                _compose_args("pull", service_name), cwd, task,
                suppress_env_warnings=True,
            )
        if code != 0:
            task.lines.append(f"Pull failed for {service_name}.\n")
            return code

        task.lines.append(f"Recreating {service_name}...\n")
        if stack.mode == "pass":
            code = await process_service.run_subprocess(
                _pass_compose_args("up", "-d", service_name), cwd, task,
            )
        else:
            code = await process_service.run_subprocess(
                _compose_args("up", "-d", service_name), cwd, task,
            )

        if code == 0:
            task.lines.append("Cleaning up old images...\n")
            await process_service.run_subprocess(
                ["docker", "image", "prune", "-f"], cwd, task,
            )
            task.lines.append(f"[{stack_name}/{service_name}] Upgrade complete.\n")
        else:
            task.lines.append(f"[{stack_name}/{service_name}] Upgrade failed.\n")
        return code

    return await process_service.run_script(_script, stack_name, f"upgrade {stack_name}/{service_name}")


async def cleanup() -> process_service.TaskState:
    """Remove unused Docker resources (images + containers, but NOT volumes)."""
    return await process_service.run_command(
        ["docker", "system", "prune", "--all", "--force"],
        stack_name="__cleanup__",
        cwd=DOCKER_APPS_PATH,
        label="docker system prune",
    )


async def _error_task(message: str) -> process_service.TaskState:
    """Create an immediately-failed task with an error message."""
    ts = process_service.TaskState(
        task_id=str(uuid.uuid4()),
        command="error",
        stack_name="__error__",
    )
    ts.lines.append(f"{message}\n")
    ts.done = True
    ts.exit_code = 1
    process_service._tasks[ts.task_id] = ts
    return ts
