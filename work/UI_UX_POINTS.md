# UI/UX points (living notes)

Conversation record of owner intent. Full contract: `docs/overhaul/EXPERIENCE_DECISIONS.md` (X1-X13).

## Current lock

- Landing (X1): swarm gathers as gates pass; minimum 1.4 s (0.6 s on same-tab refresh), cap 4 s, then fades to the desk.
- Sections scroll vertically with Lenis and snap; PageUp/PageDown and Alt+1-9 jump. Space stays the mic and never scrolls (X2).
- Layers: backdrop, substrate, content, decor, chrome, modal, toast, landing (Tailwind z-tokens). Decor is SVG only, at most 4 per section.
- Command baton docks at the bottom; text restores per section and autosaves.
- Right-edge TaskDock: parked approvals and an "N engineering tasks" chip. HITL modal has a "Later" button that parks it; parked approvals expire with a toast.
- Engineering with no drawing shows a stacked-card carousel deck of engineering tasks (max 5 visible, hover fan, drag to back, arrow keys), with quote-step chip and parked-approval badge. Reduced motion gives a flat list.
- Right column on Monitor: weather (shrink-0) above scrollable suggested tasks.
- React Bits stays accents only (`.cursor/rules/jarvis-react-bits.mdc`).

## Open

- Deck pdf thumbnails only when focus carries a URL.
- HITL modal to dock chip shared-layout morph not built.

## Log

- 2026-09-29 Owner confirmed the experience decisions in X1-X13 (see "Confirmed by owner" in that doc).
- 2026-09-29 Owner asked for the remaining gaps (voice level, Space key, deck chips, expiry toast, weather feature, real landing gates) to be finished.
