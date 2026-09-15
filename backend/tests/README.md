# Running the backend test suite

## One-command run, from a fresh clone

```bash
.venv/bin/pip install -r backend/requirements.txt -r backend/requirements-dev.txt && .venv/bin/python -m pytest
```

Run from the repo root — `pytest.ini` there points `testpaths` at `backend/tests`.
Each test module inserts `backend/` onto `sys.path` itself and imports as
`app.*`, so no `PYTHONPATH` or extra flags are needed. `pytest` is pinned to
an exact version (`backend/requirements-dev.txt`) so this reproduces the
same collection/pass/skip counts on a fresh venv as it does here:
**208 collected, 197 passed, 11 skipped, 0 failed.**

Data isolation: `backend/tests/conftest.py` redirects
`app.config.settings.data_dir` / `exports_dir` to a session-scoped temp
directory before any test module runs, and removes it when the session ends.
The suite never opens or writes `<repo>/backend/data/jarvis.db`, and never
writes outside a throwaway exports directory. A few modules
(`test_rfq.py`, `test_jobs.py`, `test_conversations.py`) additionally point
`settings.data_dir` at their own per-module temp dir; both layers are
temp-dir only.

This override is independent of how `app/config.py` resolves the *default*
`DATA_DIR`/`EXPORTS_DIR` (currently relative to process CWD; a separate,
unrelated PR is anchoring that to the repo root instead). Either way,
`conftest.py` reassigns `settings.data_dir`/`exports_dir` to a temp
directory after import, so the isolation guarantee holds regardless of
which default resolution is in place.

## Live-service tests

`test_hermes_e2e.py` and `test_stability_e2e.py` are marked
`@pytest.mark.live_service` (module-wide for the latter). They also carry
their own runtime `skipif` (Hermes reachability / `GET :8000/api/health`), so
on a normal cloud VM — no Hermes gateway on `:8642`, no Voicebox on `:17493`,
no live Jarvis API on `:8000` — they skip cleanly instead of failing. There
is no test in the suite that requires real Google OAuth credentials; the
mail/calendar/sheets tests that touch Google code paths monkeypatch
`app.connectors.google_auth` instead of calling the live API.

To actually exercise them on the desk machine, start the services they need
and then run:

```bash
# Hermes-only checks (needs `hermes gateway run` reachable at :8642, or the
# `hermes` CLI on PATH):
.venv/bin/python -m pytest backend/tests/test_hermes_e2e.py -v

# Full live-API checks (needs the backend running: see repo README /
# jarvis-runbook — `uvicorn app.main:app --app-dir backend --port 8000`):
.venv/bin/python -m pytest backend/tests/test_stability_e2e.py -v

# Or, once both are up, select everything tagged live_service:
.venv/bin/python -m pytest -m live_service -v
```

To run everything **except** live-service tests explicitly (this is already
the effective default via the runtime skips above):

```bash
.venv/bin/python -m pytest -m "not live_service"
```
