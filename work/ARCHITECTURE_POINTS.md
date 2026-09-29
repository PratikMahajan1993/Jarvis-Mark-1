# Architecture points (living notes)

Conversation record of owner intent. As-built snapshot: `docs/CURRENT.md`. Contracts: `docs/overhaul/PLATFORM_DECISIONS.md` (P1–P13). Review of what actually landed: `work/SCROLL_OVERHAUL_REVIEW.md`.

## Current lock

- HUD is one vertically scrolling page of sections (Monitor, Casual, Engineering), rendered by `core/desk/Desk.tsx` and `core/sections/SectionStack.tsx`. Sections are declared with `defineSection` in `core/sections/registry.ts`. Merged to `overhaul` at `7742e79` (PR #24).
- Section is a scroll position; HUD workspace is derived from it. Server chat and Hermes-run start carry `ui: {section, reason}` (`backend/app/section_hint.py`, stamped in `semantic_router.py`). The scroll director (`core/scroll/director.ts`, applied in `sectionStore.requestSection`) drops or defers automatic jumps when pinned, when a modal is open, or when the user was active in the last 1.2 s. Engineering only yields to `explicit`.
- Substrate (particle orb) is driven by `postSubstrate` messages (protocol v2, `frontend/src/substrate/protocol.ts`). UI never touches WebGL directly. One canvas, owned by `JarvisRoot`.
- State lives in small stores (`core/stores/`: turn, desk, taskQueue, section). The orchestrator FSM stays pure (`lib/orchestratorFsm.ts`), including `HITL_PARK`, `HITL_RESUME`, `ROUTE_HINT`, and `effectsFor`.
- Feature platform is a scaffold, not the full P2–P9 loader. Shipped: weather card, `defineFeature` / `defineCard` / `Slot`, `useSection`, `useTopic`, `useDraft`, and `app/core/features.py` (register, event-loop-safe `publish`, `GET /api/events`; jobs stay off until a feature registers one). Not shipped: `GET /api/features`, scheduler start, OpenAPI types, `backend/app/features/`, remaining SDK hooks (`useJarvisSend`, `useOrb`, `useFeatureQuery`, loader). `npm run new:feature` writes files and does not register them. `.cursor/rules/frontend/22-scroll-substrate.mdc` only documents hooks that exist.
- Drafts have a SQLite table `drafts` and `PUT`/`POST /api/drafts/{key}` (JSON or `text/plain` JSON), key pattern `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`, 64 KB body cap. Baton text is also in `localStorage` and flushes on section change and `pagehide`. Programmatic leave of Engineering awaits autosave (300 ms); wheel/snap fires autosave once from `reportScroll`.
- Parked-approval prune is per session. Client TTL is `parkedAt`+30 min unless `expires_at`; on TTL the chip leaves and Authorize reopens when the turn is idle. Deck badges match `conversation_id` (session-only match only for engineering kinds with no conversation id).
- `lib/pane/` still holds `springs`, `perf`, `quoteContract`, and `knowledge`. Do not treat those as removed.
- HITL (Authorize / Reject, plus "Later" parking) still gates mail send, calendar writes, quote send, and broad memory wipe. Open notes stay capped at 3.
- Stack, ports, and file rules: `.cursor/rules/core/00-jarvis-core.mdc`. API prefers `127.0.0.1:8000`. Speech is Gemini TTS, Charon, `POST /api/tts`.

## Open

- Scroll snap: Lenis `"lock"` is what shipped (`core/scroll/engine.ts`). Contract wording is "mandatory". Owner will decide later.
- Feature SDK landed (`useFeatureQuery`, `useOrb`, `useJarvisSend`, and the rest of `@/sdk`). Remaining platform work: `GET /api/features`, scheduler start, OpenAPI types.
- Morphs, pdf thumbs, deck drop, and landing are done. Capability matrix (`work/CAPABILITY_TEST_MATRIX.md`) now describes the scroll HUD (existing IDs plus section **S**). Substrate blend `simMs` measured over 6 ms on this desk; the degrader now keys off worker `simMs` (bloom first, then 30 Hz sim under 60 Hz render).

## Log

- 2026-09-29 Owner approved the scroll overhaul (Phase 3 contract) and the feature-platform approach: feature folders plus manifest.
- 2026-09-29 Landing gates are real signals: substrate, fonts, desk, monitor and casual DOM, engineering chunk prefetch.
- 2026-09-29 Owner: scroll snap decision deferred; everything else in the overhaul steps up to documentation is to be completed.
- 2026-09-30 PR #24 merged to `overhaul` (`7742e79`). Review of as-built gaps is `work/SCROLL_OVERHAUL_REVIEW.md`. Living notes corrected so agents do not treat partial platform and autosave work as done.
- 2026-09-30 Review bugs in `work/SCROLL_OVERHAUL_REVIEW.md` phases 1–3 were fixed on the working tree (not committed): Space in fields, baton flush, Engineering autosave await + scroll-away, `text/plain` beacon + draft key check, per-session parked prune + `parkedAt` TTL, conversation-scoped deck badge, event-loop-safe `publish`, rule budget cut.
- 2026-09-30 Feature SDK landed. Desk `simMs` measured over 6 ms on Monitor→Casual blend; degrader now keys off `simMs` (bloom, then 30 Hz sim). Morphs, thumbs, drop, and landing done.
- 2026-09-30 Capability matrix rewritten for the scroll-substrate HUD (kept A1…J*; added S1–S5).
