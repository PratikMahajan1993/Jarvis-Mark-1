# App features (living notes)

Capabilities the owner wants Jarvis to have. As-built status is in `docs/CURRENT.md`. Gaps after the scroll merge: `work/SCROLL_OVERHAUL_REVIEW.md`.

## Current lock

- Talk or type to one Hermes brain. Tools own mail, calendar, files, and Drive. The brain never invents prices, mail, or calendar facts.
- Jobs are Hermes playbooks. The first shipped job is shop-quote (Engineering desk, `quote_verify`).
- Approvals (Authorize / Reject) before mail send, Task for Gemini, calendar writes, quote send, and broad memory wipe. Later parks an approval so chat and the mic work again. A chip cannot Authorize or Reject. Parked prune is per session; TTL from `parkedAt` reopens Authorize when it needs a decision.
- Chat may move the desk to the right section (quote or drawing words) via server `ui` hints. The user's scroll and a pin win. Engineering leaves only on an explicit request ("back to chat", nav, or a `ui_command`).
- Engineering task deck lists open drawing, workflow, and job notes (still capped at 3 expanded notes) and resumes one when its card is clicked. Parked badge matches `conversation_id`.
- Drafts (baton text, engineering owner fields) autosave and survive section change, Engineering leave, and `pagehide` (beacon + key/size checks on `/api/drafts`). Do not tell the owner a draft was saved unless a write finished.
- Weather line on the Monitor rail, from `features/weather`.
- New capabilities are meant to ship as features (manifest with intents, tools, approval kinds, jobs, cards). Only the weather card is wired. Do not add a feature by editing scroll, the canvas, the shell, or the turn state machine.

## Open

- Full feature-platform SDK still deferred: `useJarvisSend`, `useOrb`, `useFeatureQuery`, loader, scheduler, OpenAPI commit, `new:feature` registration, `backend/app/features/`. Jobs stay off until a feature registers one.
- Perf-gate rewrite for the scroll desk and capability-matrix ids for the overhaul.
- Experience morphs and deck polish (HITL-to-chip, card-to-stage, pdf thumbnails, `deltaX`, empty drop target, landing Hermes line / staggered chrome) stay out until chosen.

## Log

- 2026-09-29 Owner asked for feature-platform scaffolding so new features are a folder plus a manifest; weather ported as the reference feature.
- 2026-09-30 PR #24 merged. Feature platform and draft autosave were partial; review listed data-loss bugs.
- 2026-09-30 Review bugs in `work/SCROLL_OVERHAUL_REVIEW.md` phases 1–3 were fixed on the working tree (not committed). Feature platform remains a scaffold; full SDK and morph/polish gaps stay open.
