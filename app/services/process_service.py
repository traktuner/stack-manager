from __future__ import annotations

import asyncio
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Awaitable

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
# Docker Compose warnings about unset env vars (expected for pass mode stacks)
_BLANK_STRING_RE = re.compile(r'.*variable is not set\. Defaulting to a blank string\.')

# Per-stack locks to prevent concurrent operations
_stack_locks: dict[str, asyncio.Lock] = {}

# In-memory task store
_tasks: dict[str, "TaskState"] = {}

# Task retention: max age in seconds and max count
_TASK_MAX_AGE = 3600  # 1 hour
_TASK_MAX_COUNT = 200


@dataclass
class TaskState:
    task_id: str
    command: str
    stack_name: str
    lines: list[str] = field(default_factory=list)
    done: bool = False
    exit_code: int | None = None
    created_at: float = field(default_factory=time.time)


def _get_lock(stack_name: str) -> asyncio.Lock:
    if stack_name not in _stack_locks:
        _stack_locks[stack_name] = asyncio.Lock()
    return _stack_locks[stack_name]


def _cleanup_tasks() -> None:
    """Remove old completed tasks to prevent memory leaks."""
    now = time.time()
    to_remove = [
        tid for tid, t in _tasks.items()
        if t.done and (now - t.created_at) > _TASK_MAX_AGE
    ]
    for tid in to_remove:
        del _tasks[tid]

    # If still too many, remove oldest completed tasks
    if len(_tasks) > _TASK_MAX_COUNT:
        completed = sorted(
            ((tid, t) for tid, t in _tasks.items() if t.done),
            key=lambda x: x[1].created_at,
        )
        excess = len(_tasks) - _TASK_MAX_COUNT
        for tid, _ in completed[:excess]:
            del _tasks[tid]


def _busy_task(stack_name: str, label: str) -> TaskState:
    """Create an immediately-failed task indicating the stack is busy."""
    ts = TaskState(
        task_id=str(uuid.uuid4()),
        command=label,
        stack_name=stack_name,
    )
    ts.lines.append(f"Operation '{stack_name}' is already running.\n")
    ts.done = True
    ts.exit_code = 1
    _tasks[ts.task_id] = ts
    return ts


def get_task(task_id: str) -> TaskState | None:
    return _tasks.get(task_id)


def is_stack_busy(stack_name: str) -> bool:
    lock = _stack_locks.get(stack_name)
    return lock is not None and lock.locked()


async def run_subprocess(
    args: list[str], cwd: str, task: TaskState, *, suppress_env_warnings: bool = False,
) -> int:
    """Run a subprocess, streaming output into an existing TaskState. Returns exit code."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
        )
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = ANSI_RE.sub("", line.decode("utf-8", errors="replace"))
            if suppress_env_warnings and _BLANK_STRING_RE.match(text.strip()):
                continue
            task.lines.append(text)
        await proc.wait()
        return proc.returncode
    except Exception as exc:
        task.lines.append(f"Error: {exc}\n")
        return 1


async def run_command(args: list[str], stack_name: str, cwd: str, label: str = "") -> TaskState:
    """Run a single command asynchronously, streaming output into a TaskState."""
    _cleanup_tasks()

    lock = _get_lock(stack_name)
    if lock.locked():
        return _busy_task(stack_name, label or " ".join(args))

    task_id = str(uuid.uuid4())
    ts = TaskState(
        task_id=task_id,
        command=label or " ".join(args),
        stack_name=stack_name,
    )
    _tasks[task_id] = ts

    async def _run():
        async with lock:
            ts.exit_code = await run_subprocess(args, cwd, ts)
            ts.done = True

    asyncio.create_task(_run())
    await asyncio.sleep(0.05)
    return ts


async def run_script(
    script_fn: Callable[[TaskState], Awaitable[int]],
    stack_name: str,
    label: str,
) -> TaskState:
    """Run a multi-step async script, streaming output into a TaskState.

    script_fn receives the TaskState (to append lines) and returns an exit code.
    """
    _cleanup_tasks()

    lock = _get_lock(stack_name)
    if lock.locked():
        return _busy_task(stack_name, label)

    task_id = str(uuid.uuid4())
    ts = TaskState(
        task_id=task_id,
        command=label,
        stack_name=stack_name,
    )
    _tasks[task_id] = ts

    async def _run():
        async with lock:
            try:
                ts.exit_code = await script_fn(ts)
            except Exception as exc:
                ts.lines.append(f"Error: {exc}\n")
                ts.exit_code = 1
            finally:
                ts.done = True

    asyncio.create_task(_run())
    await asyncio.sleep(0.05)
    return ts
