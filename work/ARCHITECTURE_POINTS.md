# Architecture points (decision log)

Historical notes. They do not lock the desk structure, the renderer, snap behavior, or where new code must live. Current guidance is `AGENTS.md`. Business requirements are `docs/PRODUCT_BRIEF.md`.

## Log

- 2026-09-29 Owner approved the scroll overhaul and the feature-platform approach: feature folders plus a manifest.
- 2026-09-29 Landing gates are real signals: substrate, fonts, desk, monitor and casual DOM, engineering chunk prefetch. Hermes is displayed and is not a gate.
- 2026-09-29 Owner deferred the scroll-snap wording. Code at that time used Lenis `"lock"`. That deferral is closed; snap behavior may change with the interface.
- 2026-09-30 PR #24 merged to `overhaul` (`7742e79`). The review of that commit is `archive/2026-09-30-scroll-review/SCROLL_OVERHAUL_REVIEW.md`.
- 2026-09-30 Review bugs from that note (Space in fields, baton flush, Engineering autosave, draft beacon, parked TTL, deck badge scope, event-loop-safe `publish`) were fixed on the working tree.
- 2026-09-30 Docs pass: this file stopped carrying status. Open gaps are only in `docs/CURRENT.md`.
