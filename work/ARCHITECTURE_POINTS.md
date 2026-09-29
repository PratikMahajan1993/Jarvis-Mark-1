# Architecture points (living notes)

Conversation record of owner intent. As-built lives in `docs/CURRENT.md`; full contracts in `docs/overhaul/PLATFORM_DECISIONS.md` (P1-P13).

## Current lock

- HUD is one vertically scrolling page of sections (Monitor, Casual, Engineering), rendered by `core/desk/Desk.tsx` and `core/sections/SectionStack.tsx`. Sections are declared with `defineSection` in `core/sections/registry.ts`.
- Section is a scroll position; HUD workspace is derived from it. Server chat/run responses carry `ui: {section, reason}` (`backend/app/section_hint.py`); the scroll director (`core/scroll/director.ts`) may drop or defer automatic jumps (pinned, modal open, user active in last 1.2 s). Engineering only yields to `explicit`.
- Substrate (particle orb background) is driven by `postSubstrate` messages (protocol v2, `frontend/src/substrate/protocol.ts`); UI never touches WebGL directly.
- State lives in small stores (`core/stores/`: turn, desk, taskQueue, section); the orchestrator FSM stays pure (`lib/orchestratorFsm.ts`).
- Features plug in through a manifest: backend `app/core/features.py` (`Feature`, `Intent`, `ToolSpec`, `ApprovalKind`, `Job`, `/api/events` SSE); frontend `src/sdk` (`defineFeature`, `defineCard`, `Slot`, hooks). Weather is the first feature. Scaffold with `npm run new:feature <name>`; types via `npm run api:schema` / `api:types`.
- Drafts persist in SQLite table `drafts` via `/api/drafts/{key}` (64 KB cap); baton text also in localStorage.
- HITL (Authorize / Reject, plus "Later" parking) still gates mail send, calendar writes, quote send, broad memory wipe.
- Stack, ports and file rules unchanged (see `.cursor/rules/jarvis-core.mdc`).

## Open

- Scroll snap: "lock" (shipped) vs "mandatory" wording. Owner will decide later.

## Log

- 2026-09-29 Owner approved the scroll overhaul (Phase 3 contract) and the feature-platform approach: feature folders plus manifest.
- 2026-09-29 Landing gates are real signals: substrate, fonts, desk, monitor and casual DOM, engineering chunk prefetch.
- 2026-09-29 Owner: scroll snap decision deferred; everything else in the overhaul steps up to documentation is to be completed.
