# Overhaul — Experience Decisions (Phase 3 contract)

**Locked:** 2026-09-29 (owner interview, rounds 1–2)
**Scope:** what the owner sees and feels. Code structure lives in [`PLATFORM_DECISIONS.md`](PLATFORM_DECISIONS.md). Operating rule: [`.cursor/rules/frontend/22-scroll-substrate.mdc`](../../.cursor/rules/frontend/22-scroll-substrate.mdc).
**Until Phase 3 merges,** `docs/CURRENT.md` still describes the running single-pane HUD.

Each decision has an ID (`X#`). Phase 3 commits and tests cite these IDs.

---

## X1 — Landing

- Shown on **every full document load**. The markup is server-rendered with CSS-only first frames, so it paints before JavaScript runs.
- **Visual:** the substrate orb gathers from diffuse particles (preset `landing`, spread 1.0 → 0.35 as gates pass). Under it, one mono status line names the real gate in progress: *Waking substrate · Loading desk · Checking Hermes · Ready*. A hairline progress bar shows gates passed out of the total. No logo splash, no percentages.
- **Gates** (run in parallel):

| Gate | Passes when |
|---|---|
| G1 substrate | Worker posts `ready`. If it posts `contextLost`, continue without the orb. |
| G2 fonts | `document.fonts.ready` |
| G3 desk | Bootstrap queries settled: session, conversations, pending |
| G4 Monitor | Section mounted |
| G5 Casual | Section mounted |
| G6 Engineering | Code chunks prefetched: `DrawingViewer` and a warm pdf.js worker. **Not mounted.** |

  Hermes health is **displayed but never gates** the landing.
- **Timing:** minimum 1.4 s, so the animation reads. Exits as soon as every gate has passed after the minimum. Hard cap 4.0 s: whatever is late shows a skeleton. A same-tab refresh (`sessionStorage["jarvis.landed"]`) uses a 0.6 s minimum.
- **Exit:**
  1. The page jumps instantly (no animation) to the target section.
  2. The landing fades and blurs out over 600 ms while the orb springs from `landing` to the target section's preset.
  3. The chrome fades in, staggered 80 ms apart.
- **Target section:** if pinned, the saved workspace. Otherwise the ambient rule: a restored conversation's category decides the section; with no conversation, Monitor.
- **Reduced motion:** static orb and a 200 ms fade. Same gates.

## X2 — Page and sections

- **Order, top to bottom:** Monitor (`order: 100`), Casual (`200`), Engineering (`300`). Feature sections slot in by `order`.
- Each section is exactly **`100dvh`**. Its content box excludes the chrome: `--chrome-top`, `--chrome-bottom`, `--nav-w` and `--dock-w`.
- **Scrolling:** Lenis smooth scroll on the document, with **mandatory snap** to section tops (Lenis snap, not CSS scroll-snap, because the two fight). About 0.9 s, easing expo-out.
- **Scroll areas inside a section** carry `data-lenis-prevent` and `overscroll-behavior: contain`. The drawing viewer captures the wheel for zoom and **never** scrolls the page.
- **Keyboard:** PageUp, PageDown and Space move to the previous or next section. Alt+1…9 jumps to the nth section. Keys are ignored while typing in a field.
- **SectionNav** sits in L3 on the left edge: section labels plus a live progress mark. Clicking one is a user scroll.

## X3 — Section ↔ workspace

- **Active section:** the section more than 60% in view, meaning `|scrollPos − i| ≤ 0.4` in viewport units. Between thresholds, the previous section stays active.
- An active section that declares a `workspace` sets `HudWorkspace` (persisted, as today). A section without one leaves `HudWorkspace` unchanged.
- **Pin** blocks **automatic** scrolls only. You can always scroll by hand.
- **Dropped:** the ambient auto-jump to Monitor.

## X4 — Context jumps (automatic scroll)

| From | Trigger | To |
|---|---|---|
| Monitor | Server hint: drawing, quote, shop strategy | Engineering |
| Monitor | Server hint: mail, chat | Casual |
| Monitor | Status question | Stay |
| Casual | Server hint: `is_quote_start`, or `vision_task` with a drawing | Engineering, with the stage opened on that drawing |
| Engineering | **Explicit only:** "back to chat", a nav click, or a `ui_command` intent | Casual. The draft is autosaved first. |
| Any | HITL arrives | **No scroll.** The modal opens where you are and the orb moves to the centre. |

- **Where the hint comes from:** `/api/chat` requests carry `section` (the current one), and responses carry `ui: { section, reason } | null`. When the turn event stream is on, the same hint is also emitted at routing time, so the scroll starts before the reply arrives.
- The client keyword function `talkJumpWorkspace` is **retired**.
- Automatic scrolls go through the scroll director's rules (see P5 in the platform doc).

## X5 — The orb (L1)

- **One orb, drawn only by the substrate.** Removed:
  - the Evil Eye: its shader path, noise texture, `STOCK_EYE`, `EvilEye.tsx`, and the Monitor eye specs;
  - the `JarvisCore` DOM rings;
  - React Bits `Particles` and `LightRays` on the desk.
- **Presets** are tunable data in `substrate/presets.ts`:

| Preset | Centre (x, y from top-left) | Scale | Accent | Dim | Spread | Swirl |
|---|---|---|---|---|---|---|
| `landing` | 0.50, 0.46 | 0.55 | `#7dffe0` | 0.50 | 1.0 → 0.35 | 0.6 |
| `monitor` | 0.50, 0.42 | 0.62 | `#FF6F37` | 0.55 | 0.45 | 0.4 |
| `casual` | 0.50, 0.40 | 0.72 | `#7dffe0` | 0.30 | 0.35 | 0.5 |
| `engineering` | 0.93, 0.18 | 0.16 | `#7dffe0` | 0.35 | 0.25 | 0.5 |

- **Between sections,** the target is a smoothstep blend of the two neighbouring presets by scroll position. Springs smooth the result.
- **State modifiers change shape and colour only. They never move the orb, except HITL.**

| State | Effect |
|---|---|
| idle | Breath: 7 s period, ±6% brightness |
| listening | Spread ×0.8, brightness ×1.25, swirl ×0.8 |
| thinking / executing | Swirl ×2.2, ring pulse at 1.2 Hz |
| speaking | Brightness ×(1 + 0.6·level), spread ×(1 + 0.15·level). `level` comes from an `AnalyserNode` on the TTS WAV, about 30 Hz. |
| hitl | Tint `#FFB020` mixed at 0.65, pulse at 0.5 Hz. Centre moves to (0.5, 0.5) and scale to max(current, 0.6) **while the modal is open.** A parked approval does not move the orb. |

- In Engineering the orb is dimmed, but the modifiers apply at full strength, so it stays reactive.
- **Other routes:** the orb is frozen and hidden (opacity 0). The WebGL context stays alive.
- **Reduced motion:** springs snap to their targets, there is no breath or pulse, and one frame is drawn per change.

## X6 — Four layers

| Tier | Contents | Motion |
|---|---|---|
| **L0 Backdrop** (fixed) | Section tint blend, Engineering grid, vignette, grain | `translateY(−0.3 × scrollY)` |
| **L1 Substrate** (fixed) | The WebGL canvas | Only the uniforms move |
| **L2 Content** | Sections and their cards | 1× |
| **L3 Foreground** | **Decor**, then **chrome** above it: StatusCluster (top), SectionNav (left), TaskDock (right), CommandBaton (bottom) | Decor 1.2–1.4×. Chrome is fixed. |
| Modal tier | HITL, compose, prefs, Google connect | — |
| Toast tier, landing tier | — | — |

- **Decor rules:** SVG or CSS only, never WebGL. `pointer-events: none`. At most 0.35 opacity where it overlaps cards. At most 4 pieces per section. Static under reduced motion. Examples: hairline reticle arcs, coordinate ticks, section numerals, dimension lines in Engineering. Keep it minimal. No literal scenery.

## X7 — Command baton

- Visible in **every** section, bottom centre, in L3.
- **While scrolling** (|velocity| above a threshold): opacity 0.35, blur 2 px, scale 0.98. It restores 400 ms after the scroll stops, or immediately on focus or typing. It stays interactive throughout.

## X8 — Task queue and draft chip

- **TaskDock:** right edge, vertically centred, in L3. Collapsed chips show an icon and a short title, with a count badge. The dock expands on hover or focus and is keyboard reachable.
- **Parking:** the HITL modal gains **Later**. Pressing it morphs the modal into a draft chip (shared-layout animation) that flies into the dock. The turn state machine moves from `AWAITING_HITL` to `IDLE` for that action, so chat and the mic work again.
- **Resume:** clicking a chip morphs it back into the full Authorize / Reject modal. **You can never Authorize or Reject from a chip.**
- **Queue contents:** every server pending action with status `pending`, across all sessions. Which ones are parked is stored client-side (`localStorage`), so a refresh keeps them parked. Expiry and abandon stay server-governed: an expired item leaves the dock with a toast.
- Engineering tasks appear in the dock as a single "*N* engineering tasks" chip, which scrolls to Engineering.

## X9 — Engineering deck (stacked-card carousel)

- **Engineering task** = an open conversation with category `drawing` or `workflow`.
- **Save for later** on the active task autosaves its draft, detaches the stage, and adds the card to the deck. Leaving Engineering autosaves but keeps the task active.
- **Layout:**
  - With no active task, the deck is the **hero** of Engineering, in the centre.
  - With an active task, the deck collapses into a stacked pile on the left edge of the stage, showing three card edges. Hover fans the pile out, and clicking opens a card.
- **Stack geometry:** at most 5 visible cards. Card *n* is offset −14·*n* px vertically, scaled 0.94ⁿ, darkened 12%·*n*, and blurred beyond depth 2. Perspective is 1200 px. A "+N" pill counts the rest.
- **Interactions:**
  - Drag the front card sideways to send it to the back (velocity-aware spring).
  - Arrow keys, and horizontal trackpad scroll (`deltaX`), also cycle the deck.
  - Hover fans the stack apart, like Sonner's expanding toast stack.
  - Click or Enter on the front card resumes it: the card morphs into the drawing stage (shared layout).
  - The vertical wheel **always** scrolls the page.
- **Card content (tool-owned data only):**
  - drawing thumbnail: first page, rendered by pdf.js at idle and cached in IndexedDB by file sha256;
  - customer, drawing number and revision;
  - quote step chip: Scope → RM → Strategy → MHR → Assemble;
  - verify status: blocker and warning counts from the last `quote_verify`;
  - a badge if an approval is parked for this task;
  - last touched.
  
  A total appears only if a verified revision exists, labelled **Draft**.
- **References:** Apple Wallet's pass stack, the fluid morphs in the Family wallet app, and Sonner's toast stack.
- **Reduced motion:** a flat horizontal list with crossfades.
- **Empty state:** the line "No engineering tasks waiting", plus a drop target for a drawing.

## X10 — Draft autosave

- **Triggers:** leaving the Engineering section, a 2 s debounce while editing, Save for later, and `pagehide` (sent with `sendBeacon`).
- **Quote edits** go to the server. The existing `/api/quote/*` writes already persist; owner fields they don't cover go to the draft endpoint in P8. **Baton text** goes to `localStorage`, per section.
- Autosave **never** sends anything or queues an external action.

## X11 — Lazy mounting

- A section declares `lazy: { mountWithin, unmountBeyond }` in viewport heights. Engineering uses `{ 1, 2 }`, with its code prefetched during the landing. Monitor and Casual mount eagerly.
- The drawing stage stays mounted while its task is active and it is within 2 viewports.
- This **replaces** the old "all panels always mounted" lock.

## X12 — Other routes

- `/masterdata`, `/canvas` and `/lab` keep their current layouts. No Lenis, no sections. The substrate is frozen and hidden there.

## X13 — Performance and acceptance

- **Frame rate:** 60 fps target, 30 fps floor. p95 frame time ≤ 20 ms while scrolling on the desk.
- **WebGL:** exactly **one** context on `/`. pdf.js uses 2D canvas.
- **Hygiene:** zero hydration warnings. Listener counts stay stable after 20 section round-trips and 10 route navigations.
- **Perf gate:** `npm run perf` adds landing-to-ready time, 20 section round-trips, WebGL context count, and listener count.
- **Checks:** `npm run lint`, `npm run typecheck` and `npm run test` pass.

---

## Pending confirmation (owner, before Phase 3)

1. **X1:** the landing also plays on refresh, in its short 0.6 s form.
2. **X4:** Engineering → Casual happens only on an explicit request, never on every casual utterance.
3. **X5:** the `JarvisCore` DOM rings and the React Bits `Particles` / `LightRays` leave the desk, so the substrate orb is the only orb.
4. **X8:** parked approvals are tracked client-side, so no database migration is needed.
