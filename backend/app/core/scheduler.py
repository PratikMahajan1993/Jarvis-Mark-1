"""Feature job runner. The API lifespan starts every job the loaded features registered."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.features import Job

log = logging.getLogger("jarvis.jobs")

_stop: asyncio.Event | None = None
_task: asyncio.Task | None = None


def running() -> bool:
    return _task is not None and not _task.done()


async def start(jobs: list[Job]) -> None:
    """Start single-flight interval jobs. No-op when there is nothing to run."""
    global _stop, _task
    if running() or not jobs:
        return
    runnable = [job for job in jobs if job.every_s > 0]
    for job in jobs:
        if job.every_s <= 0:
            log.error("feature job %s skipped: every_s must be positive", job.name)
    if not runnable:
        return
    _stop = asyncio.Event()
    stop = _stop

    async def loop(job: Job) -> None:
        while not stop.is_set():
            try:
                await job.run()
            except Exception:
                log.exception("feature job %s failed", job.name)
            try:
                await asyncio.wait_for(stop.wait(), job.every_s)
            except asyncio.TimeoutError:
                pass

    async def run_all() -> None:
        await asyncio.gather(*(loop(j) for j in runnable))

    _task = asyncio.create_task(run_all())


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
