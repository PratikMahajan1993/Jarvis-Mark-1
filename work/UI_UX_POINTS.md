# UI/UX points (living notes)

Conversation record of owner intent. Full contract: `docs/overhaul/EXPERIENCE_DECISIONS.md` (X1–X13). What the merged HUD actually does: `work/SCROLL_OVERHAUL_REVIEW.md`.

## Current lock

- Landing (X1): swarm gathers as gates pass; minimum 1.4 s (0.6 s on same-tab refresh), cap 4 s, then the desk is shown. Gates are substrate, fonts, desk, monitor DOM, casual DOM, and an engineering chunk prefetch. Hermes is displayed, never a gate. The landing overlay is client-rendered (`page.tsx` loads the desk with `ssr: false`).
- Sections scroll vertically with Lenis. PageUp, PageDown, and Alt+1–9 jump. Space is the mic when the owner is not typing, types a space inside a field (including the baton), and never scrolls the page (X2). Section keys still work from the baton.
- Layers: backdrop, substrate, content, decor, chrome, modal, toast, landing (Tailwind z-tokens). Decor is SVG only, at most 4 per section.
- Command baton docks at the bottom of every section. Text is per section; flushes on section change and `pagehide` so it survives navigation and reload.
- Right-edge TaskDock: parked approvals and an "N engineering tasks" chip. HITL modal has Later. A chip reopens the full Authorize / Reject modal and cannot decide. Parked prune is per session. TTL is `parkedAt`+30 min unless `expires_at`; on expiry the chip leaves, Authorize reopens when idle, and the toast says it needs a decision.
- Engineering with no drawing shows a stacked-card carousel (max 5 visible, hover fan, drag to back, arrow keys), with quote-step chip and parked-approval badge matched to `conversation_id` (session-only match only for engineering kinds with no conversation id). Reduced motion is a flat list.
- Right column on Monitor: weather (shrink-0) above scrollable suggested tasks. Weather is the `features/weather` card in `monitor.rail`, shown when a weather line exists.
- React Bits stays accents only (`.cursor/rules/frontend/21-react-bits.mdc`).

## Open

- Deck pdf thumbnails only when focus already carries a URL. No pdf.js idle render, no IndexedDB cache.
- HITL modal to dock chip shared-layout morph is not built. Card-to-drawing-stage morph is not built.
- Landing chrome fades as one block (500 ms), not staggered 80 ms. The landing line does not name Hermes.
- Deck has no horizontal-trackpad cycle (`deltaX`) and no empty-state drop target.
- Substrate sim cost while blending is still over the 6 ms budget until measured on the desk. The degrader watches frame p95 (20 ms), not `simMs`.
- Scroll snap `"lock"` vs contract “mandatory” — owner decision deferred.

## Log

- 2026-09-29 Owner confirmed the experience decisions in X1–X13 (see "Confirmed by owner" in that doc).
- 2026-09-29 Owner asked for the remaining gaps (voice level, Space key, deck chips, expiry toast, weather feature, real landing gates) to be finished.
- 2026-09-30 Those items shipped in PR #24, then review found Space, draft, and parked-approval bugs.
- 2026-09-30 Review bugs in `work/SCROLL_OVERHAUL_REVIEW.md` phases 1–3 were fixed on the working tree (not committed): Space types in the baton, baton flush, Engineering autosave, beacon, parked prune/TTL + Authorize reopen, deck badge scope.
