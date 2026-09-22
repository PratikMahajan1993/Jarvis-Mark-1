from __future__ import annotations

import asyncio
import threading

from . import store


async def run_turn_worker(turn_id: str) -> None:
    from ..agent import run_ledger_chat_turn

    if not store.mark_running(turn_id):
        return
    await run_ledger_chat_turn(turn_id)


def schedule_turn(turn_id: str) -> None:
    """Fire-and-forget worker so HTTP accept returns before brain work."""

    def _runner() -> None:
        asyncio.run(run_turn_worker(turn_id))

    threading.Thread(target=_runner, daemon=True, name=f"turn-{turn_id}").start()
