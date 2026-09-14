# Jarvis — what works today (2026-09-14 foundation build)

Short as-built snapshot after foundation phases P0–P4 scaffolding.

## Product shape

- **Jarvis** = HUD + voice + HITL + connectors + local RAG/memory + office-day cards.
- **Hermes** = cognitive brain (gateway API on `:8642`), preferred over Gemini for open chat; compose fill prefers Hermes when warm.
- **Honcho** = Hermes memory provider (cloud, still live); Jarvis **dual-writes** durable facts into local store.

## Foundation gates (Aspect 14)

| Gate | Status |
| ---- | ------ |
| P0 Observability / HITL blast-radius + mission log + `/api/metrics` | Shipped |
| P1 Local memory / RAG (SQLite + LanceDB-when-available) + MCP memory tools | Shipped |
| P2 Hermes-first MCP expand + compose fill + quote skill stub + safety deny-list | Shipped |
| P3 Office-day spine (weather, suggested tasks, quote sheet/PDF/HITL send, vision helper) | Shipped (dry-run ready) |
| P4 Stretch browser evidence tools + docs | Shipped scaffolding |

## Working capabilities

- Orchestrator HUD with suggested-task modals, weather chip, Authorize blast-radius card.
- Draft-email compose modal; fill prefers Hermes gateway then Gemini.
- Hermes warm gateway bridge; `hermes_enabled` defaults **True**.
- Mission step log + Hermes latency samples via `/api/metrics` and `/api/missions`.
- Local memory upsert/search/forget + mail reindex; `remember` dual-writes to profile namespace.
- Quote path tools: `quote_analyze_drawing`, `quote_build`, `quote_pdf`, `quote_send` (HITL).
- Browser evidence record + HITL queue tools (stretch).

## Still deepen with real office use

- Live Google Sheet quotation workbook bind (local xlsx works now).
- Continuous mail→attachment worker robustness on production Gmail volume.
- Honcho → local cutover when local recall quality is proven.
- Full Hermes browser computer-use with screenshots end-to-end.

## Runtime notes

- Start Hermes gateway (login item / `hermes gateway`).
- Jarvis API `:8000`, frontend `:3000`.
- Plan: `work/FOUNDATION_BUILD_PLAN.md`. Vision: `work/VISION_WORKBOOK.md`.
