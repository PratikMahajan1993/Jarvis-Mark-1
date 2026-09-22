from __future__ import annotations

import asyncio
import threading

from . import events, store


async def run_turn_worker(
    turn_id: str,
    *,
    heartbeat_interval_sec: float | None = None,
) -> None:
    from ..agent import run_ledger_chat_turn

    if not store.mark_running(turn_id):
        return

    events.append_turn_event(turn_id, store.STATE_RUNNING, "router")
    hb_task = asyncio.create_task(
        events.heartbeat_while_running(turn_id, interval_sec=heartbeat_interval_sec)
    )
    try:
        await run_ledger_chat_turn(turn_id)
    finally:
        hb_task.cancel()
        try:
            await hb_task
        except asyncio.CancelledError:
            pass
        events.publish_terminal_event(turn_id)


def schedule_turn(turn_id: str) -> None:
    """Fire-and-forget worker so HTTP accept returns before brain work."""

    def _runner() -> None:
        asyncio.run(run_turn_worker(turn_id))

    threading.Thread(target=_runner, daemon=True, name=f"turn-{turn_id}").start()
