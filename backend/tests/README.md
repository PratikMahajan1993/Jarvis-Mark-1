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
The suite never opens or writes `<repo>/data/jarvis.db`, and never
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

`live_service` is the umbrella marker for tests that need a separately
running service, so `-m "not live_service"` remains the fully isolated
offline suite. The nine tests in `test_stability_e2e.py` are additionally
marked `api_service`: they require only the Jarvis API on `:8000`, not Hermes,
Voicebox, or Google OAuth, and are cloud-testable. The two
`test_hermes_e2e.py` tests require Hermes.

When no relevant service is running, these modules' runtime `skipif` checks
skip them cleanly. There is no test in the suite that requires real Google
OAuth credentials; mail/calendar/sheets tests monkeypatch
`app.connectors.google_auth` instead.

### Run the API-only checks

Start the API from the repo root, then run the API-only marker:

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
# In a second terminal:
.venv/bin/python -m pytest -m api_service -v
```

The tests configure direct setup helpers with the same `data` and `exports`
paths used by that default server, so confirmations run against server-owned
SQLite state. For a server configured with non-default locations, pass those
paths explicitly to pytest:

```bash
JARVIS_API_DATA_DIR=/absolute/server/data \
JARVIS_API_EXPORTS_DIR=/absolute/server/exports \
.venv/bin/python -m pytest -m api_service -v
```

Run Hermes checks only when its gateway is reachable:

```bash
.venv/bin/python -m pytest backend/tests/test_hermes_e2e.py -v
```

With both services available, select all live-service tests:

```bash
.venv/bin/python -m pytest -m live_service -v
```

The isolated offline suite remains:

```bash
.venv/bin/python -m pytest -m "not live_service"
```
