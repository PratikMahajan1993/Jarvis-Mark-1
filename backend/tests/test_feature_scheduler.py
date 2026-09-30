from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.core import scheduler
from app.core.features import Job
from app.main import app


def test_scheduler_runs_a_job_once_per_start():
    hit = asyncio.Event()

    async def _run() -> None:
        hit.set()

    async def _exercise() -> None:
        await scheduler.stop()
        await scheduler.start([Job(name="probe", every_s=3600, run=_run)])
        await asyncio.wait_for(hit.wait(), timeout=1)
        assert scheduler.running()
        await scheduler.stop()
        assert not scheduler.running()

    asyncio.run(_exercise())


def test_lifespan_starts_and_stops_scheduler(monkeypatch):
    calls: list[str] = []

    async def fake_start(jobs):
        calls.append(f"start:{len(jobs)}")

    async def fake_stop():
        calls.append("stop")

    monkeypatch.setattr(scheduler, "start", fake_start)
    monkeypatch.setattr(scheduler, "stop", fake_stop)
    with TestClient(app) as client:
        response = client.get("/api/features")
        assert response.status_code == 200
    assert any(item.startswith("start:") for item in calls)
    assert calls[-1] == "stop"
