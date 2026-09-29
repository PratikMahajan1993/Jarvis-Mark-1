# Overhaul — Experience Decisions (Phase 3 contract)

**Locked:** 2026-09-29 (owner interview, rounds 1–2)
**Scope:** what the owner sees and feels. Code structure lives in [`PLATFORM_DECISIONS.md`](PLATFORM_DECISIONS.md). Operating rule: [`.cursor/rules/frontend/22-scroll-substrate.mdc`](../../.cursor/rules/frontend/22-scroll-substrate.mdc).
**Until Phase 3 merges,** `docs/CURRENT.md` still describes the running single-pane HUD.

Each decision has an ID (`X#`). Phase 3 commits and tests cite these IDs.

---

## X1 — Landing

- Shown on **every full document load**. The markup is server-rendered with CSS-only first frames, so it paints before JavaScript runs.
- **Visual:** the 20,000 particles start as a scattered cloud (a random ±50-unit cube, which is casberry's own start state) and gather into the **target section's formula** as gates pass. The gathering pull strengthens with gate progress. Under the orb, one mono status line names the real gate in progress: *Waking substrate · Loading desk · Checking Hermes · Ready*. A hairline progress bar shows gates passed out of the total. No logo splash, no percentages.
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
  2. The landing fades and blurs out over 600 ms while the swarm finishes settling into its shape and moves to the section's placement.
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
  - `JarvisCore`: its CSS halo, core and nucleus, its rotating rings and ticks, and its 2D-canvas dust loop (owner chose option a, 2026-09-29).
  
  React Bits `Particles` and `LightRays` are already unused on the desk. They stay vendored only. The current glow shader (`presence.frag.ts`) and light-ray pass (`rays.ts`) are replaced by the swarm.
- **Model: a casberry-style particle swarm** (owner chose option c, 2026-09-29).
  - **Particles:** 20,000, drawn as instanced tetrahedra (size 0.25) in flat colour.
  - **Motion:** every frame, a per-section **formula** (casberry-compatible JavaScript) runs in the substrate worker. It gives each particle a target position and colour, and each particle eases toward its target (0.1 per frame at 60 fps, made frame-rate independent). That easing is also how shapes **morph** into each other.
  - **Camera and look:** camera at z = 100 with a 60° field of view, slow auto-rotate about the vertical axis, and a lightweight bloom (strength 1.8, radius 0.4, threshold 0) at reduced resolution.
  - **No Three.js:** it runs on the existing `ogl` renderer, in the same single context.
- **Formulas per section.** They are stored verbatim in `substrate/formulas/`, with details and code in [`ORB_FORMULAS.md`](ORB_FORMULAS.md):

| Section | Formula | Placement | Dim | State controls |
|---|---|---|---|---|
| Casual | Cortex Dinamico (idle = owner export) | Large, centred; outer shell about 78% of content height | 1.0 | Synaptic Chaos, Pulse Speed (Neuroactivity for HITL amber) |
| Monitor | ASCI System (default formula) | Tall: 70% of viewport height, bottom edge above the command baton | 1.0 | Flow Speed, Organic Distortion |
| Engineering | CHAT GPT (default formula) | Side orb at the right edge, upper third | 0.35 | Generic modifiers |

- **Colour** comes from the formula. Section UI accents (the Casual mint, for example) stay in the DOM theme.
- **Between sections,** the worker evaluates **both** neighbouring formulas and blends their targets by scroll position (smoothstep). Placement blends the same way. At rest, only one formula runs.
- **States move formula controls only, never the orb's position, except HITL.** Controls ease between state values (springs). The per-section values are in `ORB_FORMULAS.md`. The pattern:

| State | Pattern |
|---|---|
| idle | Owner's exported values |
| listening | Calmer: less chaos or distortion, slower pulse or flow |
| thinking / executing | Agitated: more chaos or distortion, faster pulse or flow |
| speaking | Chaos or distortion follows `level` (an `AnalyserNode` on the TTS WAV, about 30 Hz) |
| hitl | Slow and amber (through the formula's own colour control when it has one, otherwise a tint toward `#FFB020`). The swarm moves to screen centre, at scale ≥ 0.6 of viewport height, **while the modal is open.** A parked approval does not move it. |

- **Morphing between sections must be very smooth** (owner requirement, 2026-09-29). This is how it's guaranteed:
  - **The morph follows the scroll.** Targets, colours and placement blend continuously with scroll position (smoothstep), so the swarm is always part-way between the two shapes. It never pops, and scrolling backwards reverses the morph.
  - **Two layers of smoothing:** the per-particle easing (k = 1 − 0.9^(dt·60)), plus placement springs. Fast flicks and Lenis snaps therefore still read as a glide.
  - **Direct jumps:** when the director jumps across sections (for example Monitor → Engineering), the morph goes **straight from origin to destination** on the scroll's own progress. It does not flash through the shape of the section in between.
  - **Wave, not a cloud-swap.** Each particle starts its morph slightly offset by index (a stagger of about 15% of the blend), with a small outward bulge mid-morph. The shape visibly unfolds into the next one instead of 20,000 particles crossing randomly.
  - **One shared clock** for all formulas, so a shape never restarts or jumps when you arrive at it. State control values keep easing through a morph.
  - **Frames are protected during a morph:** the simulation stays at 60 Hz. If over budget, bloom resolution drops first.
  - **Reduced motion:** no wave or bulge. Particles snap to the destination shape with a 200 ms fade.
  - **Acceptance:**
    - *Vitest:* a scripted sweep over 60 frames between every pair of sections shows no particle moving more than 3 world units in one frame, and no discontinuity at blend 0 or 1.
    - *Headless:* a screen recording of a slow and a fast scroll through all sections shows no popping.
- **Formulas without named controls** (currently CHAT GPT) use generic modifiers: time-scale (thinking ×2), brightness (listening ×1.25; speaking 1 + 0.6·level), and the HITL tint.
- In Engineering the swarm is dimmed, but state changes apply at full strength, so it stays reactive.
- **Performance budget:** formula evaluation ≤ 6 ms of worker time per frame (it doubles while blending two sections). When over budget, the degrade order is:
  1. bloom resolution;
  2. simulation at 30 Hz with rendering still interpolated at 60.
  
  The particle count stays 20,000 because the shapes depend on it.
- **Other routes:** the swarm is frozen and hidden (opacity 0). The WebGL context stays alive.
- **Reduced motion:** no auto-rotate and no pulse animation. Particles snap to their targets, and one frame is drawn per change.

## X6 — Four layers

| Tier | Contents | Motion |
|---|---|---|
| **L0 Backdrop** (fixed) | Section tint blend, Engineering grid, vignette, grain | `translateY(−0.3 × scrollY)` |
| **L1 Substrate** (fixed) | The WebGL canvas (particle swarm) | Only the swarm moves, never the canvas |
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

## Confirmed by owner (2026-09-29)

1. **X1:** the landing also plays on refresh, in its short 0.6 s form.
2. **X4:** Engineering → Casual happens only on an explicit request, never on every casual utterance.
3. **X5:** `JarvisCore` leaves the desk (option a).
4. **X8:** parked approvals are tracked client-side, so no database migration is needed.
5. **X5:** option c, casberry-style formulas in the worker.
6. **X5:** all three formula exports received and stored verbatim in `ORB_FORMULAS.md`.
7. **X5:** Cortex idle = the owner's exported `PARAMS`, not the slider defaults.
8. **X5:** formula colours win on the canvas.
9. **P2:** Weather becomes the first plug-in feature.

Bloom and auto-rotate are kept exactly as in the owner's exports; the owner raised no objection. Speed controls act as clock rates (see `ORB_FORMULAS.md`), so state changes never scramble the swarm.

**Phase 3 is waiting for the owner's explicit "go".**
