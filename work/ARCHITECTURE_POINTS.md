# Architecture points (decision log)

Owner decisions only. **Status of the desk is `docs/CURRENT.md`.** Contracts are `docs/overhaul/PLATFORM_DECISIONS.md` and `docs/overhaul/EXPERIENCE_DECISIONS.md`. Do not add as-built checklists here.

The 2026-09-16 through 2026-09-23 entries that `docs/SYSTEM_TRUTH.md` §15 cites lived in an earlier copy of this file. Those decisions are restated in System Truth. Rows marked superseded there are not current.

## Log

- 2026-09-29 Owner approved the scroll overhaul and the feature-platform approach: feature folders plus a manifest.
- 2026-09-29 Landing gates are real signals: substrate, fonts, desk, monitor and casual DOM, engineering chunk prefetch. Hermes is displayed and is not a gate.
- 2026-09-29 Owner deferred the scroll-snap wording. Code uses Lenis `"lock"`. Contract X2 still says “mandatory”. Do not change either until the owner decides.
- 2026-09-30 PR #24 merged to `overhaul` (`7742e79`). The review of that commit is `archive/2026-09-30-scroll-review/SCROLL_OVERHAUL_REVIEW.md`.
- 2026-09-30 Review bugs from that note (Space in fields, baton flush, Engineering autosave, draft beacon, parked TTL, deck badge scope, event-loop-safe `publish`) were fixed on the working tree.
- 2026-09-30 Docs pass: this file stopped carrying status. Open gaps are only in `docs/CURRENT.md`.
