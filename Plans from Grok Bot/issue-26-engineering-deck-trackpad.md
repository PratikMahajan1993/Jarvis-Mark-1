# Plan: #26 Engineering deck horizontal trackpad scroll

**Repo:** PratikMahajan1993/Jarvis-Mark-1  
**Issue:** https://github.com/PratikMahajan1993/Jarvis-Mark-1/issues/26  
**Priority:** Medium  
**Status:** Plan only — no implementation until accepted

## Goal
Horizontal trackpad gestures (`deltaX`) cycle the Engineering task deck the same way as ArrowLeft / ArrowRight, per contract X9. Page scroll must not move while the deck consumes a horizontal gesture. Vertical wheel outside the deck still scrolls the page.

## Constraints
- Do not change Lenis snap type (`lock` in `frontend/src/core/scroll/engine.ts`); X2 stays mandatory.
- Do not open a second WebGL context or edit `frontend/src/substrate/`.
- Do not change quote proof, master data, or HITL.
- Threshold so a small diagonal scroll does not both turn the card and scroll the page.

## Current behavior
`frontend/src/core/sections/engineering/EngineeringDeck.tsx`:
- ArrowRight / ArrowLeft → cycle / back
- Front card drag-x → `deck:cycle`
- No `wheel` / trackpad `deltaX` handler

## Proposed approach
1. Attach a non-passive `wheel` listener on the deck stack container (not document-wide).
2. Consume when `|deltaX|` exceeds threshold **and** dominates `|deltaY|` (e.g. `|deltaX| > T` and `|deltaX| > |deltaY|`).
3. On consume: call the same cycle/back as keys; `preventDefault()` so Lenis does not move the page.
4. Skip when focus is in `input, textarea, [contenteditable]` (mirror key handler).
5. Optional: short cooldown so one flick does not multi-cycle.
6. Leave Lenis and substrate untouched.
7. Manual check: horizontal swipe on deck cycles; vertical outside scrolls; diagonal does not do both.

## Files
- Primary: `frontend/src/core/sections/engineering/EngineeringDeck.tsx`
- Reference only: `docs/overhaul/EXPERIENCE_DECISIONS.md` (X9), `docs/CURRENT.md`

## Done when
Plan accepted; implementation is a separate step (local edits by owner).
