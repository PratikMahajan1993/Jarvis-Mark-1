# Jarvis — Foundation Build Plan

**Status:** Accepted 2026-09-14 · **Implementation:** P0–P4 scaffolding landed  
**Source:** Vision workbook decisions + Cursor plan `foundation_build_plan`  
**Exit criteria (Aspect 14):** casual Hermes warm latency on target; HITL miss rate = 0; morning brief + one RFQ/quote path ending in Authorize-to-send.  
**Stretch:** useful local RAG hit; one browser task with evidence.

## Locked defaults

- Vector engine: **LanceDB** (embedded when installed) + SQLite structured namespaces; local hash embeddings v0.
- Memory: Honcho cloud stays live; Jarvis dual-writes into local store for later cutover.
- Parking-lot in foundation: thin blast-radius (#4) + thin mission audit (#7) only.
- Out of foundation: Toolsmith, Red Team, Ghost clipboard, adaptive voice, 72h nudges, scrubber UI, Telegram remote.

## Phase gates

| Phase | Focus | Gate | Done |
| ----- | ----- | ---- | ---- |
| **0** | Observability + HITL thin slices | Authorize shows irreversibility; mission steps logged; metrics API | [x] |
| **1** | Dual-write memory + local RAG | Corpus upsert/search/forget + MCP | [x] |
| **2** | Hermes-first MCP | Expanded MCP; Hermes compose fill; safety deny-list; quote skill | [x] |
| **3** | Office-day spine | Weather + task cards; quote build/PDF/HITL; vision helper | [x] |
| **4** | Stretch then stop | Browser evidence tools; `docs/CURRENT.md` refreshed | [x] |

## Key modules

- HITL blast-radius: `backend/app/hitl_meta.py`, `hermes/hitl.py`, HUD `HitlModal`
- Metrics / missions: `backend/app/metrics.py`, `/api/metrics`, `/api/missions`
- Memory: `backend/app/memory/`
- Office day: `backend/app/office_day.py`, `/api/suggested-tasks`
- Quote: `backend/app/quote.py`
- Browser evidence: `backend/app/browser_evidence.py`
- Skill: `backend/app/hermes/skills/quote.md`

## Related docs

- [`VISION_WORKBOOK.md`](VISION_WORKBOOK.md)
- [`../docs/CURRENT.md`](../docs/CURRENT.md)
