"""In-memory desk runs. The browser subscribes here; Hermes stays on the server."""

from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from .runs import approve_hermes_run, stop_hermes_run


@dataclass
class LiveRun:
    jarvis_id: str
    session_id: str
    events: queue.Queue = field(default_factory=queue.Queue)
    hermes_run_id: str = ""
    cancelled: threading.Event = field(default_factory=threading.Event)


_LOCK = threading.Lock()
_RUNS: dict[str, LiveRun] = {}


def open_run(session_id: str) -> LiveRun:
    run = LiveRun(jarvis_id=f"jr_{uuid.uuid4().hex}", session_id=session_id or "default")
    with _LOCK:
        _RUNS[run.jarvis_id] = run
    return run


def get_run(run_id: str) -> LiveRun | None:
    with _LOCK:
        return _RUNS.get(run_id)


def drop_run(run_id: str) -> None:
    with _LOCK:
        _RUNS.pop(run_id, None)


def request_stop(run: LiveRun, *, base_url: str | None = None) -> dict[str, Any]:
    run.cancelled.set()
    if run.hermes_run_id:
        stop_hermes_run(run.hermes_run_id, base_url=base_url)
    return {"run_id": run.jarvis_id, "status": "stopping"}


def dispatch_desk_turn(message: str, session_id: str) -> dict[str, Any]:
    """Same routing as /api/chat, so the desk stream and the blocking route agree."""
    import asyncio

    from ..agent import run_agent
    from ..conversations import asks_to_close_drawing, close_drawing_view, is_drawing_session
    from ..hud_state import remember_hud
    from ..semantic_router import classify_intent, handle_ui_command, stamp_route, try_obvious_casual

    if asks_to_close_drawing(message) and is_drawing_session(session_id):
        result = close_drawing_view(session_id)
        data = result.model_dump()
        remember_hud(session_id, data)
        return data

    classification = try_obvious_casual(message)
    if classification is None:
        classification = asyncio.run(classify_intent(message))
    if getattr(classification, "intent", "") == "ui_command":
        result = handle_ui_command(message, session_id, classification)
    else:
        result = run_agent(message, session_id, route=classification)
        result = stamp_route(result, classification)
    data = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    remember_hud(session_id, data)
    try:
        from ..turn_log import record_turn

        record_turn(session_id=session_id, user=message, response=data, source="chat")
    except Exception:
        pass
    return data


def start_desk_run(message: str, session_id: str) -> LiveRun:
    """Start the turn in the background and publish Hermes events onto the run queue."""
    from .runs import RunHooks, approval_action, reset_run_hooks, set_run_hooks

    run = open_run(session_id)

    def publish(event: dict[str, Any]) -> None:
        if str(event.get("event") or "").startswith("reasoning"):
            return
        forwarded = dict(event)
        if forwarded.get("event") == "run.started":
            run.hermes_run_id = str(forwarded.get("run_id") or "")
        if forwarded.get("event") == "approval.request":
            forwarded["pending"] = approval_action(forwarded, run.jarvis_id)
        run.events.put(forwarded)

    def worker() -> None:
        token = set_run_hooks(RunHooks(publish=publish, stopped=run.cancelled.is_set))
        try:
            if run.cancelled.is_set():
                return
            data = dispatch_desk_turn(message, session_id)
            if not run.cancelled.is_set():
                run.events.put({"event": "jarvis.done", "response": data})
        except Exception as exc:
            if not run.cancelled.is_set():
                run.events.put({"event": "run.failed", "error": str(exc)[:500]})
        finally:
            reset_run_hooks(token)
            run.events.put(None)

    threading.Thread(target=worker, name=f"jarvis-run-{run.jarvis_id}", daemon=True).start()
    return run


def submit_approval(
    run: LiveRun,
    choice: str,
    request_id: str = "",
    *,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Approve continues the Hermes run. Deny and reject stop it."""
    normalized = (choice or "").strip().lower()
    if normalized in {"deny", "reject", "rejected", "no"}:
        return request_stop(run, base_url=base_url)
    if not run.hermes_run_id:
        raise RuntimeError("Hermes run is not active")
    return approve_hermes_run(
        run.hermes_run_id,
        "once" if normalized in {"approve", "approved", "allow", "once"} else normalized,
        request_id,
        base_url=base_url,
    )
