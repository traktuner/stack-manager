from __future__ import annotations

import asyncio

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.services.process_service import get_task

router = APIRouter()


@router.get("/api/stream/{task_id}")
async def stream_output(task_id: str):
    task = get_task(task_id)
    if task is None:
        async def _not_found():
            yield {"event": "error", "data": "Task not found"}
            yield {"event": "done", "data": "1"}
        return EventSourceResponse(_not_found())

    async def _generate():
        idx = 0
        while True:
            while idx < len(task.lines):
                yield {"event": "output", "data": task.lines[idx].rstrip("\n")}
                idx += 1

            if task.done:
                yield {"event": "done", "data": str(task.exit_code or 0)}
                return

            await asyncio.sleep(0.1)

    return EventSourceResponse(_generate())
