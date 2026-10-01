# Agents

- Truth lives in `docs/SYSTEM_TRUTH.md`. Next work is `docs/ROADMAP.md`.
- Rules live in `.cursor/rules/` (5 files). Read them before editing matching globs.
- The coordinator implements and reviews code directly. It may dispatch Cursor subagents for zero-ambiguity execution (mechanical refactors, test runs, screenshots, log reads). Anything that changes product behavior or interprets a locked rule stays with the coordinator.
- HUD: Next.js `frontend/` on :3000. API: FastAPI `backend/app/` on :8000. Hermes gateway :8642.
- Speech: Gemini TTS, voice Charon, via `POST /api/tts`. Quota exhaustion stays silent.
- Data: `data/jarvis.db` (SQLite). Writes only under `exports/`.
- HITL is required before actions that **commit the business** (outbound mail, calendar write, quote send, sheet write, CNC promote, broad memory wipe) or destroy data. Read-only fetches, dev tooling (`npm`, `git`), and connector reads do not need HITL. For exploratory code, drafts, and scratch analysis, treat HITL as guidance — ask before doing something that might commit, not after refusing.
- Feature work: `npm run new:feature <id>` from `frontend/`, then fill the stubs via `@/sdk` only. Scaffold docs are in `docs/overhaul/PLATFORM_DECISIONS.md`.
