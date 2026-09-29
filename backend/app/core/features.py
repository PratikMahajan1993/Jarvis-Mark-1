"""Feature registry: a feature declares intents, tools, approval kinds and jobs."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from fastapi import APIRouter
from fastapi.responses import StreamingResponse


@dataclass
class Intent:
    name: str
    keywords: tuple[str, ...] = ()


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., Any]


@dataclass
class ApprovalKind:
    kind: str
    title: str


@dataclass
class Job:
    name: str
    every_s: float
    run: Callable[[], Awaitable[None]]


@dataclass
class Feature:
    id: str
    intents: list[Intent] = field(default_factory=list)
    tools: list[ToolSpec] = field(default_factory=list)
    approvals: list[ApprovalKind] = field(default_factory=list)
    jobs: list[Job] = field(default_factory=list)


_features: dict[str, Feature] = {}
_subscribers: set[asyncio.Queue] = set()


def register_feature(feature: Feature) -> Feature:
    _features[feature.id] = feature
    return feature


def features() -> list[Feature]:
    return list(_features.values())


def publish(topic: str, data: Any) -> None:
    payload = {"topic": topic, "data": data}
    for q in list(_subscribers):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass


async def run_jobs(stop: asyncio.Event) -> None:
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

    await asyncio.gather(*(loop(j) for f in features() for j in f.jobs))


events_router = APIRouter()


@events_router.get("/api/events")
async def events(topics: str = "") -> StreamingResponse:
    wanted = {t for t in topics.split(",") if t}
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.add(q)

    async def stream():
        try:
            yield ": open\n\n"
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), 15)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                if not wanted or item["topic"] in wanted:
                    yield f"event: {item['topic']}\ndata: {json.dumps(item['data'])}\n\n"
        finally:
            _subscribers.discard(q)

    return StreamingResponse(stream(), media_type="text/event-stream")
