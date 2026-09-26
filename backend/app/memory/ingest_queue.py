"""Off-hot-path ingest queue. Search never waits on these workers."""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Any | Awaitable[Any]]


class IngestPriority(Enum):
    HIGH = 0
    NORMAL = 1
    LOW = 2


@dataclass
class IngestTask:
    kind: str
    payload: dict[str, Any]
    priority: IngestPriority = IngestPriority.NORMAL
    retries: int = 0
    max_retries: int = 3


@dataclass
class IngestQueue:
    max_workers: int = 2
    backoff: Callable[[int], float] = field(default=lambda retries: float(2**retries))
    queue: asyncio.PriorityQueue[tuple[int, int, IngestTask]] = field(init=False)
    workers: list[asyncio.Task[None]] = field(default_factory=list)
    handlers: dict[str, Handler] = field(default_factory=dict)
    running: bool = False
    loop: asyncio.AbstractEventLoop | None = None
    completed: int = 0
    failed: int = 0
    _seq: int = 0

    def __post_init__(self) -> None:
        self.queue = asyncio.PriorityQueue()

    def register_handler(self, kind: str, handler: Handler, max_retries: int = 3) -> None:
        del max_retries
        self.handlers[kind] = handler

    def depth(self) -> int:
        return self.queue.qsize()

    async def enqueue(self, task: IngestTask) -> None:
        self._seq += 1
        await self.queue.put((task.priority.value, self._seq, task))

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.loop = asyncio.get_running_loop()
        for _ in range(self.max_workers):
            self.workers.append(asyncio.create_task(self._worker()))

    async def stop(self) -> None:
        self.running = False
        for worker in self.workers:
            worker.cancel()
        if self.workers:
            await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()

    async def _worker(self) -> None:
        while self.running:
            try:
                _priority, _seq, task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                raise
            try:
                await self._execute(task)
            finally:
                self.queue.task_done()

    async def _execute(self, task: IngestTask) -> None:
        handler = self.handlers.get(task.kind)
        if not handler:
            log.warning("No handler for ingest kind: %s", task.kind)
            self.failed += 1
            return
        try:
            result = handler(task.payload)
            if inspect.isawaitable(result):
                await result
            self.completed += 1
        except Exception as exc:
            log.warning("Ingest %s failed: %s", task.kind, exc)
            if task.retries < task.max_retries:
                task.retries += 1
                await asyncio.sleep(self.backoff(task.retries))
                await self.enqueue(task)
            else:
                self.failed += 1
                log.error(
                    "Ingest %s failed after %s retries: %s",
                    task.kind,
                    task.max_retries,
                    exc,
                )


ingest_queue = IngestQueue(max_workers=2)


def try_enqueue(task: IngestTask) -> bool:
    """Schedule work without blocking the caller. False when the worker loop is down."""
    loop = ingest_queue.loop
    if not ingest_queue.running or loop is None or loop.is_closed():
        return False
    asyncio.run_coroutine_threadsafe(ingest_queue.enqueue(task), loop)
    return True


async def _handle_drawing(payload: dict[str, Any]) -> None:
    from .ingest import ingest_drawing_summary

    ingest_drawing_summary(
        str(payload.get("name") or "drawing"),
        str(payload.get("summary") or ""),
        meta=payload.get("meta") if isinstance(payload.get("meta"), dict) else None,
    )


async def _handle_mail(payload: dict[str, Any]) -> None:
    from .ingest import reindex_recent_mail

    limit = int(payload.get("limit") or 20)
    await asyncio.to_thread(reindex_recent_mail, limit)


async def _handle_production(payload: dict[str, Any]) -> None:
    from .ingest import ingest_text

    text = str(payload.get("text") or "").strip()
    if not text:
        return
    ingest_text(
        text,
        namespace="corpus",
        key=str(payload.get("key") or ""),
        meta={"kind": "production"},
    )


async def _handle_mail_reindex(payload: dict[str, Any]) -> None:
    await _handle_mail(payload)


async def _handle_full_reindex(payload: dict[str, Any]) -> None:
    del payload
    from .ingest import reindex_all_mail_in_db

    await asyncio.to_thread(reindex_all_mail_in_db)


async def _handle_shop_rebuild(payload: dict[str, Any]) -> None:
    del payload
    from ..shop.state import rebuild_shop_floor, rebuild_shop_state

    await asyncio.to_thread(rebuild_shop_state)
    await asyncio.to_thread(rebuild_shop_floor)


def register_default_handlers() -> None:
    ingest_queue.register_handler("mail_attachment", _handle_mail)
    ingest_queue.register_handler("drawing", _handle_drawing)
    ingest_queue.register_handler("production", _handle_production)
    ingest_queue.register_handler("mail_reindex", _handle_mail_reindex)
    ingest_queue.register_handler("full_reindex", _handle_full_reindex)
    ingest_queue.register_handler("shop_rebuild", _handle_shop_rebuild)


async def start_ingest_workers() -> None:
    register_default_handlers()
    await ingest_queue.start()


async def stop_ingest_workers() -> None:
    await ingest_queue.stop()


async def nightly_ingest() -> dict[str, Any]:
    await ingest_queue.enqueue(IngestTask(kind="mail_reindex", payload={}, priority=IngestPriority.LOW))
    await ingest_queue.enqueue(IngestTask(kind="full_reindex", payload={}, priority=IngestPriority.LOW))
    await ingest_queue.enqueue(IngestTask(kind="shop_rebuild", payload={}, priority=IngestPriority.LOW))
    return {"ok": True, "queue_depth": ingest_queue.depth()}
