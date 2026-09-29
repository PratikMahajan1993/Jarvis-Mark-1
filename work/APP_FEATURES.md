# App features (decision log)

What the owner wants Jarvis to keep doing. **What is built is `docs/CURRENT.md`.** Do not add as-built checklists here.

## Standing choices

- One Hermes brain. Tools own mail, calendar, files, and every number.
- Jobs are Hermes playbooks. The first shipped job is shop-quote.
- Authorize / Reject before mail send, Task for Gemini, calendar writes, quote send, and broad memory wipe. Later parks an approval. A chip cannot Authorize or Reject.
- New capabilities ship as features (`frontend/src/features/<id>/` and `backend/app/features/<id>/`), importing Jarvis only via `@/sdk`. Do not add a feature by editing scroll, the canvas, the shell, or the turn state machine.
- Open notes stay capped at 3 expanded.

## Log

- 2026-09-29 Owner asked for feature-platform scaffolding; weather is the reference feature.
- 2026-09-30 PR #24 merged. The same-day review is archived at `archive/2026-09-30-scroll-review/SCROLL_OVERHAUL_REVIEW.md`.
- 2026-09-30 Docs pass: platform status (SDK, OpenAPI file, `new:feature` registration, scheduler still off at boot) is only in `docs/CURRENT.md`.
