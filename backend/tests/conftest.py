"""Session-wide test isolation.

Individual test modules insert `backend/` onto `sys.path` and import `app.*`
themselves (see each file's header) so this conftest does not need to do that
again. What it must do, before any test module's top-level code runs, is
redirect `app.config.settings.data_dir` / `exports_dir` away from the repo's
real `backend/data` and `backend/exports` so that running the suite can never
touch the real `jarvis.db` or write outside a throwaway exports directory.

pytest always imports a directory's `conftest.py` before collecting sibling
test modules in that directory, so this runs ahead of every `test_*.py`
top-level import — including the handful of modules (`test_rfq.py`,
`test_jobs.py`, `test_conversations.py`) that additionally point
`settings.data_dir` at their own per-module temp dir. Those per-module
overrides still apply on top of this one; this conftest is just the
session-wide backstop for every other module that never sets `data_dir`
itself and would otherwise default to the real repo paths.

Note: importing `app.config` (whether here or in a test module) has the
existing side effect of creating `backend/data`, `backend/exports`, and
`backend/data/canvas` on disk if they do not already exist (see
`app/config.py`'s module-level `mkdir` calls) before we get a chance to
override the paths. That is unchanged pre-existing behavior of the app, not
something introduced by the test suite, and it only creates empty
directories - it does not write `jarvis.db` or any export file into them.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402

_SESSION_TMP = Path(tempfile.mkdtemp(prefix="jarvis-pytest-session-"))

settings.data_dir = _SESSION_TMP / "data"
settings.exports_dir = _SESSION_TMP / "exports"
settings.canvas_dir = settings.data_dir / "canvas"
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir.mkdir(parents=True, exist_ok=True)
settings.canvas_dir.mkdir(parents=True, exist_ok=True)


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    shutil.rmtree(_SESSION_TMP, ignore_errors=True)
