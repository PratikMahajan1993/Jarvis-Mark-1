"""Hermes cron entry. Gathers the existing briefing and stores the desk cache.

No model call. Hermes runs this with --no-agent, so it does not change the
Hermes model, tool search, fallbacks, or checkpoints.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _backend() -> Path:
    here = Path(__file__).resolve()
    candidate = here.parents[1]
    if (candidate / "app" / "briefing.py").is_file():
        return candidate
    return Path(r"d:\Cursor\Jarvis\backend")


def main() -> int:
    backend = _backend()
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from app.briefing import store_morning_brief

    payload = store_morning_brief()
    speak = str(payload.get("speak") or "").strip()
    if speak:
        print(speak)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
