"""Feature job runner. Exists for load_features; stays off unless a test starts it."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.features import Job

_stop: asyncio.Event | None = None
_task: asyncio.Task | None = None


def running() -> bool:
    return _task is not None and not _task.done()


async def start(jobs: list[Job]) -> None:
    """Start single-flight interval jobs. No-op when empty. Not called from lifespan."""
    global _stop, _task
    if running() or not jobs:
        return
    _stop = asyncio.Event()
    stop = _stop

    async def loop(job: Job) -> None:
        while not stop.is_set():
            try:
                await job.run()
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop.wait(), job.every_s)
            except asyncio.TimeoutError:
                pass

    _task = asyncio.create_task(asyncio.gather(*(loop(j) for j in jobs)))


async def stop() -> None:
    global _stop, _task
    if _stop is not None:
        _stop.set()
    if _task is not None:
        try:
            await asyncio.wait_for(_task, timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            _task.cancel()
        _task = None
    _stop = None
