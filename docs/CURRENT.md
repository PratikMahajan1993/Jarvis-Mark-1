# Jarvis — what works today (2026-09-15)

Short as-built snapshot after foundation phases P0–P4 scaffolding + desk/UI hardening.

## Product shape

- **Jarvis** = HUD + voice + HITL + connectors + local RAG/memory + office-day cards.
- **Hermes** = cognitive brain (gateway API on `:8642`), preferred over Gemini for open chat; compose fill prefers Hermes when warm.
- **Honcho** = Hermes memory provider (cloud, still live); Jarvis **dual-writes** durable facts into local store.
- **Voicebox** = local TTS (`:17493`); API uses `/generate` + cache; browser plays once (`frontend/src/lib/voice.ts` bridge).
- **Agent map** = `AGENTS.md` + `.cursor/skills/` + `.cursor/rules/` (capability-test dispatch).

## Foundation gates (Aspect 14)

| Gate | Status |
| ---- | ------ |
| P0 Observability / HITL blast-radius + mission log + `/api/metrics` | Shipped |
| P1 Local memory / RAG (SQLite + LanceDB-when-available) + MCP memory tools | Shipped |
| P2 Hermes-first MCP expand + compose fill + quote skill stub + safety deny-list | Shipped |
| P3 Office-day spine (weather, suggested tasks, quote sheet/PDF/HITL send, vision helper) | Shipped (dry-run ready) |
| P4 Stretch browser evidence tools + docs | Shipped scaffolding |

## Working capabilities

- Orchestrator HUD (`OrchestratorShell`) with Open notes (max **3** expanded), suggested tasks, weather chip, Authorize blast-radius card.
- Right rail: **WeatherCard** (pinned) + scrollable **SuggestedTasksPanel** (idle = title + detail; actions on hover).
- React Bits accents (SpotlightCard, GlareHover, GradientText, BlurText, ClickSpark, ElectricBorder, orb Particles/LightRays).
- Mail board on Orchestrator via SceneBoard inside SpotlightCard (`bodyClassName` scroll).
- Local-fast path for mail/calendar/briefing snapshot kinds (skip Hermes when ready).
- Draft-email compose modal; fill prefers Hermes gateway then Gemini.
- Hermes warm gateway bridge; `hermes_enabled` defaults **True**.
- TTS prefetch + disk cache; browser bridge cutover; no late Voicebox replay.
- Rolling turn log for capability tests: `work/LAST_TURNS.md` (last 20 chat/confirm) + `GET /api/turns/recent`.
- Mission step log + Hermes latency samples via `/api/metrics` and `/api/missions`.
- Local memory upsert/search/forget + mail reindex; `remember` dual-writes to profile namespace.
- Quote path tools: `quote_analyze_drawing`, `quote_build`, `quote_pdf`, `quote_send` (HITL).
- Browser evidence record + HITL queue tools (stretch).

## Still deepen with real office use

- Live Google Sheet quotation workbook bind (local xlsx works now).
- Continuous mail→attachment worker robustness on production Gmail volume.
- Honcho → local cutover when local recall quality is proven.
- Full Hermes browser computer-use with screenshots end-to-end.
- Capability matrix first pass: `work/CAPABILITY_TEST_MATRIX.md`.

## Runtime notes

- Start Hermes gateway (login item / `hermes gateway`). Voicebox desktop app for Mark TTS.
- Prefer API on `127.0.0.1:8000` (avoid duplicate `0.0.0.0:8000` listeners). Frontend `:3000`.
- Data lives at `<repo>/data/` (SQLite `jarvis.db`, `google_token.json`, `tts_cache/`, `memory/`, canvas uploads) and generated files at `<repo>/exports/`. `backend/app/config.py` resolves `DATA_DIR`/`EXPORTS_DIR` against the repo root, not the process CWD, so the location no longer depends on where uvicorn was launched from. Both are gitignored (`/data/`, `/exports/`).
- Install / migration: `docs/INSTALL.md`. Plan: `work/FOUNDATION_BUILD_PLAN.md`. Vision: `work/VISION_WORKBOOK.md`. Agents: `AGENTS.md`.
