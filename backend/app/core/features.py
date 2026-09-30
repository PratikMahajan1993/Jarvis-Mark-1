"""Feature registry: a feature declares intents, tools, approval kinds and jobs."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


@dataclass
class Intent:
    name: str
    keywords: tuple[str, ...] = ()
    examples: list[str] = field(default_factory=list)
    route: str = "tool_ops"
    section: str | None = None

    @property
    def id(self) -> str:
        return self.name


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., Any]
    external: bool = False
    params_schema: dict[str, Any] | None = None


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
    topics: list[str] = field(default_factory=list)
    router: APIRouter | None = None


_features: dict[str, Feature] = {}
_subscribers: set[asyncio.Queue] = set()
_loop: asyncio.AbstractEventLoop | None = None
_loaded = False


def register_feature(feature: Feature) -> Feature:
    _features[feature.id] = feature
    return feature


def features() -> list[Feature]:
    return list(_features.values())


def feature_manifest(feature: Feature) -> dict[str, Any]:
    return {
        "id": feature.id,
        "intents": [
            {
                "id": i.name,
                "examples": list(i.examples) or list(i.keywords),
                "route": i.route,
                "section": i.section,
            }
            for i in feature.intents
        ],
        "approval_kinds": [a.kind for a in feature.approvals],
        "topics": list(feature.topics),
    }


def publish(topic: str, data: Any) -> None:
    """Enqueue a topic event for SSE subscribers.

    Safe on the event loop and from sync FastAPI threadpool workers
    (via call_soon_threadsafe).
    """
    payload = {"topic": topic, "data": data}

    def _enqueue() -> None:
        for q in list(_subscribers):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # Off the loop (sync FastAPI threadpool) — hop onto the SSE loop.
        loop = _loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(_enqueue)
        return
    _enqueue()


# Jobs collected here are started by the API lifespan via core.scheduler.
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


def load_features(app: FastAPI, feature_list: list[Feature] | None = None) -> None:
    """Mount feature routers at /api/<id> and register manifests. Lifespan starts jobs."""
    global _loaded
    for feat in feature_list or []:
        register_feature(feat)
        if feat.router is None:
            continue
        prefix = f"/api/{feat.id}"
        for route in feat.router.routes:
            path = getattr(route, "path", "") or ""
            if path and not path.startswith(prefix) and path != "/":
                # Router paths are relative; include_router applies prefix.
                pass
        app.include_router(feat.router, prefix=prefix)
    _loaded = True


events_router = APIRouter()


@events_router.get("/api/features")
def api_features() -> dict[str, Any]:
    return {"features": [feature_manifest(f) for f in features()]}


class ApprovalCreate(BaseModel):
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)
    session_id: str = "default"
    title: str | None = None
    summary: str | None = None


@events_router.post("/api/approvals")
def api_create_approval(body: ApprovalCreate) -> dict[str, Any]:
    """Queue a pending HITL action. Never executes external effects."""
    from app.hermes.hitl import request_human_approval

    kind = body.kind.strip()
    if not kind:
        from fastapi import HTTPException

        raise HTTPException(400, "kind required")
    title = (body.title or kind).strip() or kind
    summary = (body.summary or f"Approve {kind}").strip()
    return request_human_approval(
        session_id=body.session_id or "default",
        kind=kind,
        title=title,
        summary=summary,
        payload=dict(body.payload or {}),
    )


@events_router.get("/api/events")
async def events(topics: str = "") -> StreamingResponse:
    global _loop
    _loop = asyncio.get_running_loop()
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
