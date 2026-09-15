# Code Tightening Improvements

## Type Hints & API Returns
- Added proper FastAPI return type hints (`RedirectResponse`, `FileResponse`) to routes in `backend/app/main.py` that were missing them (`api_google_auth`, `api_google_callback`, `api_artifact_download`, `api_drawing_download`, `api_canvas_file`). This helps FastAPI generate better OpenAPI docs and improves static analysis.

## Linting and Syntax Fixes
- Addressed Ruff linting warnings in `backend/app/intent.py` by converting regular expression `re.I` aliases to their descriptive `re.IGNORECASE` counterparts, and `re.S` to `re.DOTALL`, improving overall code readability and adhering to Python best practices.
- Identified exceptions being broadly caught in `backend/app/hermes/bridge.py` (`except Exception: pass`) but due to the need for latency/stability didn't modify it to avoid breaking changes to the core Hermes event loop.

## Hermes Latency Optimizations
- Increased timeout (`timeout=3.0` up from `1.5`) when checking `hermes_gateway_reachable` to prevent transient cold-starts from improperly falling back to the much slower CLI tool.
- Increased `_run_via_gateway` chat timeout to 45.0 seconds so complex tasks or long outputs have more breathing room before forcing the UI to reset or fallback.

## Fine-Tuned Intent Classifications
- Widened the exact match rules for `_COMPOSE_START`, `_FORWARD`, `_SAVE`, `_READ`, `_CAL_CREATE`, and `_CAL_LIST` to include common real-world synonyms (e.g., "shoot an email", "pass this along", "store/keep", "pull up", "schedule", "sync with", "what's on my plate/agenda"). This ensures a broader range of natural language prompts map successfully to the dedicated tools instead of misfiring or falling back to chat.
- Added strict `e mail` normalization logic in `prepare()` to correctly route split words like "e mail from Neha" to `mail_read` rather than hallucinating a draft intent, passing `backend/tests/test_resilience.py`.

## Framework Deprecations Fixed
- Converted FastAPI startup logic from the deprecated `@app.on_event("startup")` approach to a standard async `lifespan` context manager in `backend/app/main.py`. This resolves warnings emitted during the test suite and improves FastAPI 0.93+ compliance.
- Removed an overly broad try/except block masking a deprecation warning in `backend/app/memory/store.py` (`table_names()` -> `list_tables()`), eliminating warnings in test runs while maintaining backward compatibility with older LanceDB versions.
- Also cleaned up linting and import ordering on `backend/app/main.py`. Note: many exceptions in this codebase are intentionally suppressed (`except Exception: pass`) for telemetry, prefetching, and robust background operations where crashing the request loop would be catastrophic.
