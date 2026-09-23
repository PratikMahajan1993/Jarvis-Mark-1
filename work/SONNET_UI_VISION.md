# Jarvis — Single Pane UI Vision

Principal UI/UX brief for the Jarvis-Mark-1 HUD. Written 2026-09-23 against branch `overhaul` after reading `docs/CURRENT.md`, `work/UI_UX_POINTS.md`, `frontend/package.json`, and the current shell (`OrchestratorShell.tsx`, `hudWorkspace.ts`, `hudMorph.tsx`, `JarvisCore.tsx`, `MonitorDesk.tsx`, `EngineeringDesk.tsx`, `EvilEye.tsx`, `globals.css`).

Stack is fixed and sufficient: **Next.js 15 + Tailwind 3.4 + `motion` 12.43 (Framer Motion) + GSAP 3.15 + `ogl` 1.0 + vendored React Bits.** Nothing new is introduced. Every element below is custom-built on those five.

This document is the design of record for the frontend rebuild. Section 5 is the rule file local agents execute under; Section 4 is the blueprint they execute from. Everything else explains *why*, so a worker who only reads the rule still lands the same product.

---

## 0. Diagnosis — why the current morph drops frames

The staged 1.2 s morph is not slow because the numbers are wrong. It is slow because four separate costs land in the same second, and none of them can be interrupted.

| # | What happens on a workspace switch today | Cost |
| - | --- | --- |
| 1 | `HudPresence id="engineering"` **mounts** `EngineeringDesk` (pdf.js worker boot, `DrawingViewer` canvas at 2× scale, eight `SpotlightCard`s, `GradientText` rAF loops) at t = 0, exactly when the crossfade starts. | One long task (80–250 ms) plus a full layout pass on the first frame of the animation. |
| 2 | Three independent `ogl` renderers (`Particles` 720 px, `LightRays` full-screen, `EvilEye` ≤640 px) each own a **main-thread** `requestAnimationFrame` loop. `keepMounted` keeps two of them alive. On switch, `EvilEye` tears down with `WEBGL_lose_context` and re-creates on return. | Every `renderer.render()` blocks the thread React needs for the FLIP. Context create/lose is a 100–300 ms stall. |
| 3 | `useWorkspaceLayers` fires **three `setTimeout`s** (1200 / 1300 / 2400 ms). A second switch inside that window lets old timers race the new ones (`incomingLit` flicker). The theme is a CSS `transition` on root variables, so every `var(--accent)` consumer repaints per frame, while `backdrop-blur-md` on ~10 panels re-blurs against a live WebGL surface every frame. | Paint storms, GPU re-blur, and a choreography that cannot be reversed mid-flight. |
| 4 | Presence crossfade = two **full-screen** WebGL layers composited over each other for 1.2 s. | Double GPU fill at exactly the moment the DOM is also animating. |

The thesis of this brief is simple: **nothing should mount, nothing should be created, and nothing should block the main thread when the owner changes intent.** The pane is always fully built; intent only changes where light falls and how deep each instrument sits.

---

## 1. The New Visual Paradigm — One Pane, Three Lenses

### 1.1 Metaphor

A machinist's inspection glass. There is one pane. What changes is the **light behind it** (the substrate), **where each instrument rests** (the slot), and **how deep it sits** (the depth). Jarvis is the light. It never leaves the pane; it moves.

The three legacy workspaces survive only as **lenses** — presets of light, slots, and depth — not as mounted trees. The persisted intent enum in `hudWorkspace.ts` (`casual | monitor | engineering`) stays exactly as it is because backend routing, `talkJumpWorkspace`, localStorage keys, and tests depend on it. The visual layer maps it once:

| Intent (`HudWorkspace`) | Lens | Owner's phrase | Light | Palette |
| --- | --- | --- | --- | --- |
| `monitor` | **Watch** | "ambient monitoring of shop-floor agents" | The Eye, screen centre | Ember (warm amber) |
| `casual` | **Converse** | "talk to Jarvis" | The Orb, screen centre | Mint |
| `engineering` | **Bench** | "intense engineering focus on a drawing" | The **pilot light** (the same presence, 7 % scale, top-left) | Graphite + mint hairlines |

### 1.2 Three physical layers, always mounted

```
z 100–120  OVERLAY    HITL card · Draft compose · Preferences · Google connect   (the only backdrop-filter in the app)
z 60–70    CHROME     Status cluster (pilot light · title · lens tabs) · CommandBaton
z 50       VIGNETTE   static radial darkening, pointer-events none
z 10–14    PANE       one Dock, ~9 PanePanels, each at depth 0–3, never unmounted
z 1        FIELD      static CSS: drafting grid, bench mat gradient — opacity only
z 0        SUBSTRATE  one <canvas>, one WebGL2 context, rendered in a Worker
```

The **Substrate** is a single canvas driven by a single worker. It draws the Eye, the Orb (glow + particles + rays), and the pilot light as *weights on one program set*, not as separate components. Switching lens tweens uniforms; it never creates or destroys a context.

The **Pane** is a single CSS grid (`Dock`) holding every instrument (`PanePanel`) the HUD will ever show. A lens is a map `panelId → { slot, depth }`. Changing lens changes grid-area classes; `motion`'s `layout` prop turns that into a transform-only FLIP. Parked panels keep their React state (scroll position, PDF page, expanded note) — the drawing you were reading is exactly where you left it when you come back from a Converse detour.

The **Overlay** is the only place `backdrop-filter` is allowed, because when it is up the substrate is dimmed to 25 % and paused to 30 fps, so there is nothing expensive beneath the blur.

### 1.3 Depth — the fourth design dimension

Every `PanePanel` sits at one of four depths. Depth is the *only* way a panel appears or disappears. No `{cond ? <X/> : null}` for lens-driven visibility anywhere in the pane.

| Depth | Name | `scale` | `opacity` | `pointer-events` | After settle |
| --- | --- | --- | --- | --- | --- |
| 0 | **hero** | 1.00 | 1.00 | auto | — |
| 1 | **rail** | 1.00 | 1.00 | auto | — |
| 2 | **recessed** | 0.97 | 0.55 | auto (click raises to 1 for this lens session) | — |
| 3 | **parked** | 0.94 | 0.00 | none | `visibility: hidden; content-visibility: hidden` so it costs no paint or layout |

Depth is rendered with a `perspective: 1400px` on the Dock, so a recessed panel is physically 30–40 px "behind" the glass (`translateZ(-36px)`), which gives a real parallax when the pointer moves. Pointer parallax is ±3 px at depth 2, ±1 px at depth 1, 0 at depth 0 — enough to read as depth, never enough to be noticed as motion.

### 1.4 The presence travels, it never swaps

This is the signature of the redesign. The Eye and the Orb are **one presence** drawn by one shader family with two weights, `uEye` and `uOrb`, plus `uCenter` and `uScale`.

- **Watch → Converse — "the eye closes, the orb breathes."** `uEye` 1→0 while the pupil parameter rises toward a closed lid (reads as a blink shut, not a fade), `uOrb` 0→1 with the nucleus inheriting the eye's centre and its last glow radius. 0.9 s, one spring, one canvas.
- **Converse → Bench — "Jarvis steps aside."** `uCenter` travels from (0.5, 0.5) to (0.045, 0.075) and `uScale` from 1 to 0.07 on the `hero` spring. The presence becomes the pilot light in the status cluster; the worker scissors rendering to that 96 px region, so the Bench substrate costs almost nothing. The drafting field fades up beneath it.
- **Bench → Watch — "Jarvis returns to the floor."** Pilot light travels back to centre and opens as the Eye.

No screen-sized crossfade of two WebGL layers ever happens. During the 0.9 s morph both weights are non-zero on one canvas at internal scale 0.6 — cheaper than either of today's presences alone at full scale.

### 1.5 One gesture, three voices

The old design staged presence → theme → chrome sequentially (0 / 1.3 / 2.4 s). That is what made it feel like three separate events. The new choreography starts everything at t = 0 and lets differing spring masses give the natural order:

| Voice | Owner | Spring / tween | Settles |
| --- | --- | --- | --- |
| Substrate weights & centre | Worker (spring) | `hero` — heavier, lands last | ~1.08 s |
| Panel slots & depths | `motion` `layout` + variants | `pane` — critically damped, staggered 40 ms by depth (hero first, parked last) | ~0.97 s |
| Theme variables, field, vignette | GSAP conductor | 0.7 s `expo.out` | 0.70 s |

Total gesture ≤ 1.1 s, and every voice is **interruptible**: a second intent change retargets the springs from their current velocity, kills and rebuilds the GSAP timeline from current values, and posts a new target to the worker. No timers, no races.

### 1.6 Ambient behaviour (Watch lens)

Watch is where the HUD lives 90 % of the day, so it must feel alive without being busy.

- **Breath.** The Eye's `uIntensity` follows a 7 s sine (±6 %). Agent suns beneath it dim to 0.42 when idle and never move.
- **Attention pull.** When a Finding arrives, the Eye's pupil glances toward the right rail for 600 ms (`uMouse` override), the Finding slides in at depth 1, and the pane tilts 0.3° toward it (`rotateY` on the Dock, `chip` spring) and back. One pull per finding; never stacked.
- **Idle dim.** After 4 min without pointer, keyboard, or speech, the whole pane goes to 70 % brightness and the worker drops to 30 fps. First input restores at `chip` speed.
- **HITL pending.** Substrate 25 %, Eye pupil narrows, `ElectricBorder` HITL card at z 110. Nothing else moves.

### 1.7 What is gone

- `HudPresence`, `HudChrome`, `useWorkspaceLayers`, `HUD_PRESENCE_MS / HUD_THEME_DELAY_MS / HUD_CHROME_DELAY_MS`, `.hud-presence*`, `.hud-chrome*`.
- Per-component `ogl` renderers on the main thread (`Particles`, `LightRays`, `EvilEye` as DOM components). Their **shaders** are kept and moved into the worker.
- Aero Shards stay out (owner lock).
- `backdrop-blur-*` on cards. Frost is baked (see §4.3).
- Full-screen "Awaiting instruction" copy over the Eye.

---

## 2. Fluidity & Performance Architecture

### 2.1 Thread map

```
┌──────────────── MAIN THREAD ────────────────┐      ┌──────── substrate.worker ────────┐
│ React 19 (commit only on intent/data)       │      │ ogl Renderer({ canvas: offscreen })│
│ motion  — per-panel layout FLIP, variants   │ post │ SubstrateEngine                    │
│ GSAP    — conductor timeline, CSS vars      │─────▶│  · springs for uEye/uOrb/uCenter   │
│ paneStore (useSyncExternalStore)            │◀─────│  · presence programs (eye/orb/rays)│
│ pointer @ ≤30 Hz, ResizeObserver, visibility│ msg  │  · adaptive resolution + fps cap   │
└─────────────────────────────────────────────┘      │  · own rAF loop                    │
                                                     └───────────────────────────────────┘
```

The worker never waits on React. React never waits on the GPU. The only shared state is a handful of `postMessage` calls per intent change plus a throttled pointer stream.

### 2.2 The substrate worker

**Feasibility (verified against `frontend/node_modules/ogl/src/core/Renderer.js`):** `Renderer` accepts a `canvas` option, defaults to `document.createElement` only when none is given, and guards every `canvas.style` access with `if (!this.gl.canvas.style) return;`. `Texture` uploads typed arrays. So the existing `EvilEye`, `Particles`, and `LightRays` GLSL runs unmodified inside a `DedicatedWorkerGlobalScope` against an `OffscreenCanvas`. Chrome/Edge (owner's desk) and Firefox support `transferControlToOffscreen` plus worker `requestAnimationFrame`; Safari ≥ 16.4 too.

**Files**

```
frontend/src/substrate/
  protocol.ts         message types (below), LENS_SUBSTRATE presets
  engine.ts           SubstrateEngine — transport-agnostic, runs in worker OR main
  presence.frag.ts    merged eye + orb glow fragment shader (uEye, uOrb, uCenter, uScale, uAccent, uMode)
  particles.ts        point sprites (from Particles.tsx), alpha × uOrb
  rays.ts             light rays (from LightRays.tsx), alpha × uOrb × 0.7
  spring.ts           10-line critically damped spring used inside the worker
  substrate.worker.ts onmessage → engine
  createSubstrate.ts  main-thread factory: Worker if OffscreenCanvas, else inline shim
frontend/src/components/pane/Substrate.tsx   <canvas> + ResizeObserver + pointer + visibility → post()
```

**Protocol (`protocol.ts`)**

```ts
export type Lens = "watch" | "converse" | "bench";
export type PresenceMode = "idle" | "listening" | "thinking" | "speaking" | "hitl";

export type SubstrateIn =
  | { type: "init"; canvas: OffscreenCanvas; width: number; height: number; dpr: number; lens: Lens; reducedMotion: boolean }
  | { type: "resize"; width: number; height: number; dpr: number }
  | { type: "lens"; lens: Lens; t0: number }            // t0 = absolute ms (timeOrigin + now)
  | { type: "mode"; mode: PresenceMode }
  | { type: "pointer"; x: number; y: number }            // -1..1, ≤30 Hz
  | { type: "glance"; x: number; y: number; ms: number } // attention pull
  | { type: "visibility"; hidden: boolean }
  | { type: "reducedMotion"; on: boolean }
  | { type: "quality"; scale: number; fps: 30 | 60 };    // dev override

export type SubstrateOut =
  | { type: "ready"; webgl2: boolean }
  | { type: "settled"; lens: Lens }
  | { type: "stats"; fps: number; p95ms: number; scale: number }   // 1 Hz, dev only
  | { type: "contextLost" };

export const LENS_SUBSTRATE: Record<Lens, { eye: number; orb: number; center: [number, number]; scale: number; accent: [number, number, number]; dim: number }> = {
  watch:    { eye: 1, orb: 0, center: [0.5, 0.5],    scale: 1,    accent: [1.0, 0.435, 0.216], dim: 1 },    // #FF6F37
  converse: { eye: 0, orb: 1, center: [0.5, 0.5],    scale: 1,    accent: [0.49, 1.0, 0.878],  dim: 1 },    // #7dffe0
  bench:    { eye: 0, orb: 1, center: [0.045, 0.075], scale: 0.07, accent: [0.49, 1.0, 0.878], dim: 0.35 },
};
```

**Engine rules (`engine.ts`)**

1. One `Renderer({ canvas, alpha: true, depth: false, antialias: false, dpr: internalScale, powerPreference: "high-performance" })`. One `Triangle` geometry shared by the full-screen passes. One particle `Geometry`.
2. Per frame: `clear` → for each pass whose weight > 0.01, set uniforms and `render`. Passes: `rays` (if `uOrb`), `particles` (if `uOrb`), `presence` (always; draws eye and/or orb glow). Nothing else.
3. When `scale < 0.15` (pilot light), set `gl.scissor` to the 3 × scale bounding box around `center`, clear only that region, skip `rays` and `particles`.
4. Springs: `uEye`, `uOrb`, `uCenter.xy`, `uScale`, `uAccent.rgb`, `uDim` each on the `hero` spring `{ k: 120, c: 20, m: 1.2 }`, stepped with fixed `dt = 1/120` sub-steps for stability. `lens` messages carry `t0` so the worker starts its spring at the same absolute time as the DOM (`localT0 = t0 - performance.timeOrigin`).
5. Adaptive quality: keep a 60-frame ring of frame deltas. If p95 > 20 ms → step `internalScale` 0.6 → 0.5 → 0.4 and `targetFps` 60 → 30. After 5 s with p95 < 14 ms, step back up one notch. Never change more than one notch per 2 s. Eye noise time is quantised to 30 Hz regardless (it looked right at 30, per owner lock).
6. `visibility.hidden` → stop loop, render one frozen frame. `reducedMotion` → springs snap, loop at 30 fps with `uTime` frozen (eye is still, orb glows, no particles drift).
7. Context loss: listen `webglcontextlost` / `webglcontextrestored` on the offscreen canvas; on restore, rebuild programs; post `contextLost` so the DOM shows a 1 px accent ring on the pilot light until `ready` again.
8. Post `settled` when all springs are at rest (|x−target| < 1e-3 and |v| < 1e-3).

**Main-thread `Substrate.tsx`**

- Renders one `<canvas class="absolute inset-0 z-substrate" aria-hidden>` sized to the pane.
- On mount: `createSubstrate(canvas)` → transfers control, posts `init`.
- `ResizeObserver` → `resize` (debounced to animation frame). `pointermove` on the pane root → `pointer`, rAF-throttled to ≤30 Hz, normalised to −1..1. `visibilitychange`, `matchMedia("(prefers-reduced-motion: reduce)")` → forwarded.
- Subscribes to `paneStore.lens` and `paneStore.mode`; posts `lens` / `mode`.
- Fallback shim (`OffscreenCanvas` missing): `SubstrateEngine` is instantiated in-process with the same `post()` API; loop runs on main `requestAnimationFrame` at 30 fps cap. Same behaviour, lower budget.

### 2.3 Main-thread budget during a lens change

The main thread has one job during the gesture: run `motion`'s FLIP and GSAP's variable tween. Everything else waits.

- `setLens()` writes to `paneStore` (an external store read via `useSyncExternalStore`). Only `Dock`, each `PanePanel`, `Substrate`, and `StatusCluster` subscribe. **`OrchestratorShell` does not re-render on lens change.**
- Data effects keyed on workspace (scene load, findings reframe, quote fetch) gate on `useLensSettled()` and run inside `startTransition`. `paneStore.phase` is `"moving"` from `setLens()` until both `motion`'s `onLayoutAnimationComplete` (hero panel) and the worker's `settled` have fired, or 1.4 s, whichever first.
- Parked panels have `content-visibility: hidden` after settle, so React state changes inside them (a new mail arriving in a parked rail) cost no layout.
- Panels marked `layout` are the **frame only**. Inner content is a child with `layout="position"` or no layout at all, so text is never scale-distorted mid-FLIP. Panels whose width changes between lenses (the sheet) use a fixed inner width column and `layout` on the frame only.
- `useWillChange()` from `motion` is applied to each `PanePanel`, so `will-change: transform` is set only while animating.
- **Compositor-only property rule.** During a gesture the only animated CSS properties are `transform`, `opacity`, and root-level custom properties. Never `width`, `height`, `top/left`, `filter`, `backdrop-filter`, `box-shadow`, `border-color`, or `background` on panels.

### 2.4 Glass without `backdrop-filter`

Blurring a live WebGL canvas through ten panels is the single largest GPU cost in the current build. The pane replaces it with **baked frost**:

- Fill: `oklch(14% 0.006 240 / 0.78)` (lens-tinted via `--surface`).
- Hairline: `box-shadow: inset 0 0 0 1px oklch(100% 0 0 / 0.06)` — static, never animated.
- Grain: an inline SVG `feTurbulence` noise as `background-image`, 3 % opacity, `mix-blend-mode: soft-light`.
- Edge light: a 1 px `linear-gradient` top border at 12 % accent.

Backdrop blur is permitted in exactly one place: the Overlay scrim (`z-overlay`), and only while `paneStore.overlay !== null`, during which the substrate is dimmed and running at 30 fps.

### 2.5 Division of labour — GSAP conducts, `motion` acts, the worker lights

| Concern | Tool | Why |
| --- | --- | --- |
| Per-panel slot and depth animation | `motion` `layout` + `variants` | FLIP with scale-correction is built in; springs retarget from velocity. |
| Hover / press / chip micro-motion | `motion` `whileHover` / `whileTap` | Declarative; automatically hardware-accelerated for transform/opacity. |
| Theme variable interpolation, field/vignette opacity, worker messages, stagger timing | GSAP timeline | Interruptible (`kill()` + rebuild from current), tweens CSS custom properties natively, labels give the choreography one readable score. |
| Bench scrub/scroll-linked effects (sheet row ↔ drawing pin highlight) | GSAP `quickTo` | Sub-millisecond retargeting for pointer-linked values. |
| Substrate weights, centre, scale, accent | Worker spring | Off-thread; identical constants to `hero` so it lands with the DOM. |

**Never** run two systems on the same element or property. `motion` never touches root variables; GSAP never touches a `PanePanel`'s transform.

### 2.6 Reduced motion and accessibility

- `<MotionConfig reducedMotion="user">` at the pane root: `layout` and variant springs become instant.
- `gsap.matchMedia()` with `(prefers-reduced-motion: reduce)` swaps every tween duration to 0.
- Worker receives `reducedMotion` and snaps.
- Depth-3 panels are `aria-hidden` and removed from the tab order; depth-2 panels stay reachable.
- Lens tabs are a `role="tablist"`; `Alt+1/2/3` switch lens; `Esc` exits Bench focus mode.

### 2.7 Measuring — what "60 fps" means here

Ship a dev overlay (`?perf=1`) and a headless gate. Acceptance for any PR that touches the pane:

| Metric | Gate |
| --- | --- |
| Main-thread long tasks (`PerformanceObserver("longtask")`) during a lens change | 0 tasks > 50 ms |
| rAF delta p95 over 20 consecutive lens switches (2 s apart), headless Chrome `--enable-unsafe-swiftshader` | < 20 ms (≥ 50 fps on software GL; the desk GPU is faster) |
| WebGL contexts created after boot | 0 |
| React commits on `OrchestratorShell` per lens change | 0 |
| Layout recalculations (`PerformanceObserver` layout-shift proxy + Chrome trace) per lens change | ≤ 2 (the FLIP measurement pair) |
| Worker `stats.scale` after 60 s idle in Watch on the desk | 0.6 (never degraded) |

---

## 3. The Engineering Bench Reimagined

### 3.1 Principle

The drawing is the material; the sheet is the work; Jarvis is a colleague standing at your elbow, not a chat window. Three surfaces, one purpose: get from a customer's PDF to a verified, authorised quote without the owner's eyes leaving the drawing for long.

### 3.2 Layout (1920 × 1080 reference; grid 12 × 8, 12 px gutters, 16 px pane inset)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ ◉ pilot  RFQ-2411 · Bracket, 6061-T6 · Acme Hydraulics      Watch Converse Bench │ 56px status cluster
├──────────────────────────────────────────────────────┬───────────────────────────┤
│                                                      │  QUOTE SHEET      Sheet · Strategy · Vision │
│                                                      │  ┌─────────────────────┐  │
│         DRAWING STAGE   (cols 1–8, rows 1–6)         │  │ Raw material   ●    │  │
│         depth 0 · pan / zoom / measure / mark        │  │ 6061-T6 flat  ¥1,240│  │
│                                                      │  │ Milling 3-ax   ◐    │  │
│      ⊕ 1        ⊕ 2                                  │  │ 2.4 h × floor ¥7,680│  │
│                       ⊕ 3                            │  │ Anodise (out)  ○    │  │
│   ┆ tool rail (hover)                                │  │ …                   │  │
│   ┆ [pan][measure][mark][crop] · p 1/3 · 148%        │  ├─────────────────────┤  │
├──────────────────────────────────────────────────────┤  │ TOTAL       ¥18,920 │  │
│ ▌ Jarvis: "Tolerance on Ø12 H7 needs a reaming op —  │  │ proof  ✓✓✓✓ ✗  1/5  │  │
│   add 0.3 h?"                       [Authorize] [Reject]│  │ ▶ Authorize send    │  │
│ ▶ ask or dictate…                              ⏺ mic │  └─────────────────────┘  │
└──────────────────────────────────────────────────────┴───────────────────────────┘
   CONVERSE STRIP (cols 1–8, rows 7–8) depth 1           SHEET (cols 9–12, rows 1–8) depth 0
```

Slots used by the Bench lens: `stage` (1–8 / 1–6), `strip` (1–8 / 7–8), `sheet` (9–12 / 1–8). Notes rail parks to a 40 px **peek tab** on the far left edge (depth 3 with a 40 px `translateX` reveal on hover) so an open note is one hover away. Weather, tasks, activity park fully. Agents collapse to four 6 px dots inside the status cluster.

### 3.3 Drawing Stage (`components/bench/DrawingStage.tsx`, wraps the existing `DrawingViewer` engine)

- **Mat.** The PDF/CAD canvas sits on a neutral mat `--mat: oklch(16% 0.004 240)` with an 8 px inset shadow so paper edges read. True drawing colours are preserved (the owner reads real lines). A **Blueprint** toggle applies a static `filter: invert(1) hue-rotate(180deg)` to the pdf canvas only — never animated.
- **Chrome fades like a player.** The vertical tool rail (pan / measure / mark / crop), page pager, and zoom readout appear on pointer movement over the stage and fade to 0 after 2 s idle (`chip` spring). Keyboard: `space` pan, `m` measure, `k` mark, `c` crop, `[`/`]` page, `0` fit.
- **Measure.** Two-click distance with the drawing's declared scale (from `jarvis_quote_analyze_drawing` if present, else owner-set via "calibrate on a dimension"). Readout in mm with 0.01 precision, monospace tabular.
- **Callout pins.** Each BOQ row may carry a `region: { page, x, y, w, h }` (from the analyzer's bbox output, or from the owner's crop tool — dragging a crop onto a sheet row attaches it as evidence). Pins are numbered `⊕ n` in the row order. Hover a row → its pin blooms (`chip` spring, scale 1.25, accent ring). Hover a pin → its row lifts 2 px and the accent hairline lights. Both directions use GSAP `quickTo` so they track the pointer with no React commit.
- **Focus mode.** Double-click the stage or `f`: stage spans cols 1–12, the sheet parks to a 56 px right-edge tab showing only the total and proof count, the strip becomes a one-line ticker. `Esc` or `f` returns. Whole move is one `pane` spring.
- **Empty state.** Faint drafting grid, centred serif line "No drawing on the bench." plus a mono hint "Drop a PDF, say *quote the attachment*, or pick from the inbox." — and a live drop target.

### 3.4 Quote Sheet (`components/bench/QuoteSheet.tsx`, replaces `QuoteStack`)

The sheet is a **ledger**, not a card stack. Every number shows where it came from, because the rule of the house is that the brain never invents a price.

| Provenance | Glyph | Styling | Meaning |
| --- | --- | --- | --- |
| Tool-sourced | ● | solid numeral | Came from `jarvis_quote_*` / MHR floors / RM table |
| Owner-confirmed | ◉ | solid numeral + mint check | Owner accepted a `FactConfirmChip` |
| Pending | ◐ | dashed amber underline, italic | Analyzer proposed; awaiting owner confirm (chip inline in the row) |
| Missing | ○ | em-dash, muted | No source yet — the sheet asks, never guesses |

- **Header.** RFQ id, customer, part, material, qty, due. `Sheet · Strategy · Vision` tabs (a `motion` `layoutId` underline). Strategy hosts `VarianceCard` + `ToolChangeField`; Vision hosts `VisionBenchQueue` + `CustomerVisionConsent`. One column, never three stacked cards.
- **Rows.** Grouped: Raw material · Machining (per op, hours × floor) · Outsource · Fixtures/tooling · Margin. Each row: label, provenance glyph, qty/basis in mono, amount right-aligned in `tabular-nums`. Row height 40 px; hover lifts 2 px; click expands a 72 px detail drawer (`drawer` spring) with the tool payload and the pin thumbnail.
- **Inline edit.** Owner-editable cells (hours, margin, outsource quote) open a mono input in place; commit posts to `jarvis_quote_build`; the row flips to ◉.
- **Totals.** Sticky bottom block: subtotal, margin, total (display serif, 28 px). Under it the **proof strip**: one 10 px pill per `quote_verify` check (✓ mint / ✗ ember) and a `n/N` count. > 2 failures → the Authorize card is disabled with the failing checks listed — mirroring the backend `stop: true` gate exactly, never softer.
- **Authorize send.** The HITL card for `quote_send` is rendered *in the sheet's footer slot* when the pending action belongs to this job, with the same Authorize / Reject controls as the overlay. Mail send for other jobs still uses the overlay.

### 3.5 Converse Strip (`components/bench/ConverseStrip.tsx`)

- Default: **one line** from Jarvis (serif, 17 px, `BlurText` for new lines) and the `CommandBaton` docked beneath it. No chat history on screen.
- **Thread sheet.** Click the line or press `↑`: the last three turns slide *up* over the lower third of the stage as a frosted sheet (`drawer` spring, depth 1). Sending collapses it. Max 3 turns, because the drawing is the record — the sheet and the pins are the memory.
- **Inline HITL for bench-scoped actions** (add op, change hours) appears in the strip's right end as Authorize / Reject chips, not as a full-screen overlay. Anything external (mail, calendar) still goes to the overlay.
- **Voice.** Listening state: the pilot light's pupil widens and a 2 px mint level meter runs along the strip's top edge. Speaking: Jarvis line types in; the pilot light breathes faster. Same `PresenceMode` message that drives the Orb — one model of Jarvis's state on every lens.

### 3.6 Why this is not cluttered

- Exactly **three** surfaces on screen; everything else is parked or tabbed.
- The only always-visible chrome is the 56 px status cluster and the strip.
- Stage chrome is transient; sheet secondary content is tabbed; the thread is on demand.
- Every colour on the Bench is either drawing ink, mint (Jarvis / confirmed), amber (pending / attention), or graphite. No third accent.

---

## 4. Implementation Blueprint

### 4.1 File map

```
frontend/src/
  substrate/                          ← §2.2 (new)
  lib/pane/
    paneStore.ts                      external store: lens, phase, mode, overlay, focusMode
    lenses.ts                         LENS_LAYOUT: panelId → { slot, depth } per lens; LENS_THEME tokens
    springs.ts                        SPRING.* and EASE.* constants (single source)
    conductor.ts                      GSAP timeline factory (playLens, playOverlay, playFocus)
    useLensSettled.ts                 hook gating heavy effects
    perf.ts                           longtask observer + rAF histogram (dev)
  components/pane/
    Pane.tsx                          root: <MotionConfig> <LayoutGroup> Substrate Field Dock Vignette Chrome Overlay
    Substrate.tsx                     canvas + worker bridge
    Field.tsx                         static grid + mat gradient (opacity via conductor)
    Dock.tsx                          CSS grid with perspective; renders PanePanel children
    PanePanel.tsx                     motion.div layout + depth variants + frost
    StatusCluster.tsx                 pilot light ring, title, LensTabs, prefs
    LensTabs.tsx                      role=tablist, Alt+1/2/3
    Overlay.tsx                       HITL / compose / prefs host (only backdrop-filter)
  components/bench/
    DrawingStage.tsx  QuoteSheet.tsx  ConverseStrip.tsx  SheetRow.tsx  ProofStrip.tsx  CalloutPins.tsx
  components/orchestrator/            existing: ConversationRail, WeatherCard, SuggestedTasksPanel,
                                      Orchestra→AgentRow, CommandBaton, HitlModal, TurnStageLine …
                                      OrchestratorShell keeps data + FSM, renders <Pane> and passes props.
```

**Deleted:** `hudMorph.tsx`, `useWorkspaceLayers` and `HUD_*_MS` in `hudWorkspace.ts`, `monitor/MonitorDesk.tsx`, `monitor/AgentOrbit.tsx`, `engineering/EngineeringDesk.tsx`, `engineering/QuoteStack.tsx`, `JarvisCore.tsx` (its CSS rings become a `presence` shader pass or a tiny DOM ring set at depth 0 — implementer's choice, rings are cheap), the `.hud-*` CSS block, `.orch-root[data-workspace]` theme block (replaced by conductor tweens).

**Kept unchanged:** `orchestratorFsm.ts`, every intent helper in `hudWorkspace.ts` (`talkJumpWorkspace`, `isStatusUtterance`, `autoWorkspaceFromFocus`, persistence keys), all API/voice libs, `DrawingViewer` internals (wrapped, not rewritten), `HitlModal` copy (Authorize / Reject).

### 4.2 Component tree

```
<OrchestratorShell>                      data, FSM, voice, sessions — unchanged responsibilities
  <Pane>
    <MotionConfig reducedMotion="user">
      <Substrate />                       z 0
      <Field />                           z 1
      <Dock>                              z 10, perspective 1400px, 12×8 grid
        <LayoutGroup id="pane">
          <PanePanel id="voice">      <VoiceLine/> | <ConverseStrip/> (bench)
          <PanePanel id="notes">      <ConversationRail/>
          <PanePanel id="weather">    <WeatherCard/>
          <PanePanel id="tasks">      <SuggestedTasksPanel frame={lens==="watch"?"findings":"tasks"}/>
          <PanePanel id="agents">     <AgentRow density={lens}/>
          <PanePanel id="activity">   <ActivityStream/>
          <PanePanel id="stage">      <DrawingStage/>
          <PanePanel id="sheet">      <QuoteSheet/>
        </LayoutGroup>
      </Dock>
      <Vignette />                        z 50
      <StatusCluster />                   z 60
      <CommandBaton />                    z 70 (hidden on bench — strip owns it)
      <Overlay />                         z 100–120
    </MotionConfig>
  </Pane>
</OrchestratorShell>
```

### 4.3 Design tokens

**`tailwind.config.ts` additions**

```ts
theme: {
  extend: {
    colors: {
      mint:     { DEFAULT: "oklch(74% 0.15 160)", bright: "#7dffe0" },
      ember:    { DEFAULT: "oklch(72% 0.14 78)",  eye: "#FF6F37" },
      graphite: { 900: "oklch(9% 0.004 240)", 800: "oklch(13% 0.005 240)", 700: "oklch(16% 0.004 240)" },
      pane:     { bg: "var(--bg)", surface: "var(--surface)", fg: "var(--fg)", muted: "var(--muted)", border: "var(--border)", accent: "var(--accent)", mat: "var(--mat)" },
    },
    zIndex: {
      substrate: "0", field: "1", pane: "10", depth3: "11", depth2: "12", depth1: "13", depth0: "14",
      vignette: "50", status: "60", baton: "70", toast: "90", overlay: "100", hitl: "110", modal: "120",
    },
    borderRadius: { pane: "1.25rem", inner: "0.75rem", chip: "0.5rem" },
    boxShadow: {
      hairline: "inset 0 0 0 1px oklch(100% 0 0 / 0.06)",
      "hairline-accent": "inset 0 0 0 1px color-mix(in oklch, var(--accent) 35%, transparent)",
      mat: "inset 0 0 0 1px oklch(100% 0 0 / 0.04), inset 0 8px 24px oklch(0% 0 0 / 0.45)",
      lift: "0 2px 0 0 color-mix(in oklch, var(--accent) 20%, transparent)",
    },
    fontSize: {
      micro: ["10px", { lineHeight: "1", letterSpacing: "0.22em" }],
      readout: ["13px", { lineHeight: "1.2", letterSpacing: "0.02em" }],
      total: ["28px", { lineHeight: "1.05", letterSpacing: "-0.01em" }],
    },
    spacing: { gutter: "12px", inset: "16px", status: "56px", strip: "72px" },
    transitionTimingFunction: { out: "cubic-bezier(0.22, 1, 0.36, 1)" },
  },
},
```

**Root variables (`globals.css`)** — the `@property` registrations already present are kept so GSAP interpolates colours in oklch space. Add `--mat`, `--grid-opacity`, `--vignette-opacity`, `--accent-rgb` (for canvas parity).

| Token | Converse | Watch | Bench |
| --- | --- | --- | --- |
| `--bg` | `oklch(10% 0.005 240)` | `oklch(12% 0.022 55)` | `oklch(9% 0.004 240)` |
| `--surface` | `oklch(14% 0.008 240)` | `oklch(16% 0.028 52)` | `oklch(13% 0.005 240)` |
| `--fg` | `oklch(96% 0.004 240)` | `oklch(94% 0.018 75)` | `oklch(95% 0.003 240)` |
| `--muted` | `oklch(62% 0.008 240)` | `oklch(58% 0.04 62)` | `oklch(60% 0.006 240)` |
| `--border` | `oklch(22% 0.01 240)` | `oklch(24% 0.03 55)` | `oklch(20% 0.006 240)` |
| `--accent` | `oklch(74% 0.15 160)` | `oklch(72% 0.14 78)` | `oklch(74% 0.10 165)` |
| `--mat` | — | — | `oklch(16% 0.004 240)` |
| `--grid-opacity` | 0 | 0 | 0.35 |
| `--vignette-opacity` | 0.8 | 0.9 | 0.5 |

**Frost (baked glass) — `.pane-frost`**

```css
.pane-frost {
  background:
    url("data:image/svg+xml,…feTurbulence baseFrequency=0.9 …") 0 0/128px 128px,   /* 3% grain */
    linear-gradient(to bottom, color-mix(in oklch, var(--accent) 12%, transparent), transparent 1px),
    color-mix(in oklch, var(--surface) 78%, transparent);
  box-shadow: inset 0 0 0 1px oklch(100% 0 0 / 0.06);
  border-radius: 1.25rem;
}
```

No `backdrop-filter` in this class. Ever.

**Type**: display `Source Serif 4` (Jarvis lines, job titles, totals), body `IBM Plex Sans`, mono `IBM Plex Mono` with `font-variant-numeric: tabular-nums` on every numeral in the sheet and every readout.

### 4.4 Motion constants (`lib/pane/springs.ts`) — verified by simulation

Simulated with unit displacement, settle = |x| < 0.001 and |v| < 0.001 for 3 frames (≈ 1 px on a 1000 px move).

```ts
export const SPRING = {
  /** Panel slot/depth FLIP. Critically damped, no overshoot. */
  pane:   { type: "spring", stiffness: 170, damping: 26, mass: 1   } as const,  // ζ 0.997 · settles 971 ms · 0.00 % overshoot
  /** Presence travel + substrate weights. Heavier, lands last, whisper of overshoot. */
  hero:   { type: "spring", stiffness: 120, damping: 20, mass: 1.2 } as const,  // ζ 0.833 · 1075 ms · 0.65 %
  /** Depth opacity/scale changes without slot change. */
  recess: { type: "spring", stiffness: 200, damping: 28, mass: 1   } as const,  // ζ 0.990 · 892 ms · 0.00 %
  /** Row drawers, thread sheet, focus-mode sheet tab. */
  drawer: { type: "spring", stiffness: 260, damping: 30, mass: 0.9 } as const,  // ζ 0.981 · 746 ms · 0.00 %
  /** Chips, pins, hover lift, stage chrome, tilt. */
  chip:   { type: "spring", stiffness: 400, damping: 30, mass: 0.6 } as const,  // ζ 0.968 · 512 ms · 0.00 %
};

export const EASE = {
  out: [0.22, 1, 0.36, 1] as const,   // expo-ish out — theme, field, vignette
  gsapOut: "expo.out",
};

export const DURATION = { theme: 0.7, field: 0.6, chrome: 0.35, staggerDepth: 0.04 };
```

Depth variants for `PanePanel`:

```ts
export const DEPTH_VARIANTS = {
  "0": { scale: 1,    opacity: 1,    z: 0,   visibility: "visible", transition: SPRING.pane },
  "1": { scale: 1,    opacity: 1,    z: -12, visibility: "visible", transition: SPRING.pane },
  "2": { scale: 0.97, opacity: 0.55, z: -36, visibility: "visible", transition: SPRING.recess },
  "3": { scale: 0.94, opacity: 0,    z: -60, transition: SPRING.recess, transitionEnd: { visibility: "hidden" } },
} as const;
```

### 4.5 `PanePanel` (the only way anything is placed on the pane)

```tsx
"use client";
import { motion, useWillChange } from "motion/react";
import { usePane } from "@/lib/pane/paneStore";
import { LENS_LAYOUT } from "@/lib/pane/lenses";
import { DEPTH_VARIANTS } from "@/lib/pane/springs";

export function PanePanel({ id, children, className = "" }: { id: PanelId; children: React.ReactNode; className?: string }) {
  const lens = usePane((s) => s.lens);
  const { slot, depth } = LENS_LAYOUT[lens][id];
  const willChange = useWillChange();
  return (
    <motion.div
      layout                                     // frame only — FLIP via transform
      layoutId={`panel-${id}`}
      data-panel={id}
      data-depth={depth}
      className={`pane-frost slot-${slot} z-depth${depth} ${className}`}
      style={{ willChange, gridArea: `var(--slot-${slot})` }}
      variants={DEPTH_VARIANTS}
      animate={String(depth)}
      initial={false}
      aria-hidden={depth === 3}
      inert={depth === 3}
    >
      <motion.div layout="position" className="h-full min-h-0">{children}</motion.div>
    </motion.div>
  );
}
```

Slots are CSS custom properties on `Dock` (`--slot-stage: 1 / 1 / 7 / 9;` etc.), so the lens change is one class swap on the panel and one measurement pair for `motion`.

### 4.6 Lens layout table (`lib/pane/lenses.ts`)

| Panel | Watch | Converse | Bench |
| --- | --- | --- | --- |
| `voice` | `centre-low` · d1 (one-line status under the Eye) | `centre-low` · d0 (`BlurText`) | `strip` · d1 (`ConverseStrip`) |
| `notes` | `left-rail` · d3 | `left-rail` · d1 | `left-peek` · d3 (40 px hover reveal) |
| `weather` | `right-rail-top` · d3 | `right-rail-top` · d1 | `right-rail-top` · d3 |
| `tasks` | `right-rail` · d1 as **Findings** | `right-rail` · d1 | `right-rail` · d3 |
| `agents` | `under-centre` · d1 (suns row) | `bottom-centre` · d2 (dots) | `status` · d1 (4 micro dots in cluster) |
| `activity` | `bottom-left` · d2 | `bottom-left` · d2 | `bottom-left` · d3 |
| `stage` | `stage` · d3 | `stage` · d3 | `stage` · d0 |
| `sheet` | `sheet` · d3 | `sheet` · d3 | `sheet` · d0 |

Substrate presets per lens are in `LENS_SUBSTRATE` (§2.2). Theme tokens per lens are in `LENS_THEME` (§4.3 table).

### 4.7 Conductor (`lib/pane/conductor.ts`)

```ts
import gsap from "gsap";
import { LENS_THEME } from "./lenses";
import { DURATION, EASE } from "./springs";
import type { Lens } from "@/substrate/protocol";

type Ctx = { root: HTMLElement; substrate: { post(m: SubstrateIn): void }; onSettled(l: Lens): void; tl?: gsap.core.Timeline };

const absNow = () => performance.timeOrigin + performance.now();

export function playLens(ctx: Ctx, to: Lens) {
  ctx.tl?.kill();                                   // interruptible: rebuild from current values
  const T = LENS_THEME[to];
  const tl = gsap.timeline({ defaults: { ease: EASE.gsapOut }, onComplete: () => ctx.onSettled(to) });
  tl.addLabel("go", 0)
    .call(() => ctx.substrate.post({ type: "lens", lens: to, t0: absNow() }), [], "go")
    .to(ctx.root, { "--bg": T.bg, "--surface": T.surface, "--fg": T.fg, "--muted": T.muted, "--border": T.border, "--accent": T.accent, duration: DURATION.theme }, "go")
    .to(ctx.root, { "--grid-opacity": T.gridOpacity, "--vignette-opacity": T.vignetteOpacity, duration: DURATION.field }, "go")
    .to(".status-title", { opacity: 0, y: -4, duration: 0.18 }, "go")
    .to(".status-title", { opacity: 1, y: 0, duration: 0.35 }, "go+=0.22")
    .addLabel("settle", 1.08);                      // hero spring settle; onComplete fires here
  ctx.tl = tl;
}

export function playOverlay(ctx: Ctx, up: boolean) {
  gsap.to(ctx.root, { "--substrate-dim": up ? 0.25 : 1, duration: 0.35, ease: EASE.gsapOut });
  ctx.substrate.post({ type: "mode", mode: up ? "hitl" : "idle" });
}

export const tiltTo = (dock: HTMLElement) => gsap.quickTo(dock, "rotationY", { duration: 0.5, ease: "power3.out" });
```

`setLens(to)` in `paneStore` does three things synchronously: writes `lens` and `phase: "moving"`, calls `playLens`, and lets `motion` pick up the new `LENS_LAYOUT` on the next commit. `phase` returns to `"settled"` on the earlier of `onSettled` + hero-panel `onLayoutAnimationComplete`, or a 1.4 s watchdog.

### 4.8 Step-by-step execution (roster + acceptance)

Each phase is a closed kickoff for a Composer 2.5 Fast worker with the files above in scope. Cloud placement unless noted (headless Chrome with `--enable-unsafe-swiftshader` renders WebGL and supports `OffscreenCanvas` in workers).

| Phase | Worker | Build | Acceptance |
| --- | --- | --- | --- |
| **0 Instrument** | `jarvis-builder` | `lib/pane/perf.ts`, `?perf=1` overlay (fps, long tasks, contexts, commits), a Playwright-free headless script `frontend/scripts/perf-gate.mjs` that loads the HUD, switches lens 20×, dumps JSON. Record the **baseline** on `overhaul`. | Script runs in cloud; baseline JSON committed under `work/perf/`. |
| **1 Substrate** | `jarvis-uiux` | `frontend/src/substrate/*`, `components/pane/Substrate.tsx`. Port Eye + orb glow + particles + rays GLSL into engine passes. Replace `MonitorDesk` / `JarvisCore` canvases with `<Substrate/>` behind the existing DOM. Keep the stock Eye params. | 1 WebGL context total; Eye and Orb both visible via `?lens=` query; worker posts `stats`; fallback shim works with `OffscreenCanvas` deleted in devtools; screenshot parity with `frontend/monitor-pass2.png`. |
| **2 Dock & depth** | `jarvis-uiux` | `paneStore`, `lenses.ts`, `springs.ts`, `Dock`, `PanePanel`, `Field`, `Vignette`, `StatusCluster`, `LensTabs`. Move every rail into a `PanePanel`. Delete `hudMorph.tsx`, `useWorkspaceLayers`, `.hud-*` CSS. | All three lenses render with correct slots; parked panels have `visibility:hidden`; 0 mounts/unmounts on switch (React DevTools profiler); scroll position in `SuggestedTasksPanel` survives a Watch→Converse→Watch round trip. |
| **3 Conductor** | `jarvis-uiux` | `conductor.ts`, `useLensSettled`, remove `.orch-root[data-workspace]` theme block and root CSS transitions; gate scene/findings loads on settled. | Perf gate: 0 long tasks > 50 ms during switches, rAF p95 < 20 ms, 0 `OrchestratorShell` commits per switch. Mid-gesture re-switch is smooth (record 3 rapid switches). |
| **4 Bench** | `jarvis-uiux` (+ `jarvis-workflows` for the sheet's row/provenance contract from `quote.py`) | `DrawingStage`, `QuoteSheet`, `SheetRow`, `ProofStrip`, `ConverseStrip`, `CalloutPins`; delete `EngineeringDesk`, `QuoteStack`. Provenance glyphs, proof gate mirroring `quote_verify`, inline Authorize in the footer. | Sheet renders `backend/tests` fixture quote with correct glyphs; > 2 failures disables send; pins ↔ rows highlight; focus mode; `Esc`. |
| **5 Ambient & a11y** | `jarvis-uiux` | Breath, glance, idle dim, tilt, reduced motion, tablist keys, `inert` on parked. | Reduced motion snaps everything; `Alt+1/2/3`; idle dim after 4 min (use a dev override). |
| **6 Gate** | `jarvis-builder` | Wire `perf-gate.mjs` into `npm run perf`, document in `docs/CURRENT.md`. | Gate thresholds in §2.7 pass on cloud; results in `work/perf/`. Desk-machine run (owner GPU) confirms `stats.scale` stays 0.6. |

Desk-only checks: Voicebox-driven `PresenceMode` timing, Hermes-fed findings glance. Everything else is cloud-verifiable.

### 4.9 Migration safety

- Intent enum, FSM, HITL copy, MAX_EXPANDED = 3, Authorize/Reject, `talkJumpWorkspace` behaviour: unchanged and covered by existing tests.
- `DrawingViewer` is wrapped, not rewritten; its crop/mark/pan code is reused by `DrawingStage`.
- Phase 1 can ship behind `NEXT_PUBLIC_SUBSTRATE=worker|inline|legacy` for one release; `legacy` mounts the old components. Remove the flag in Phase 3.

---

## 5. UI/UX Cursor Rules & Skills

The checked-in Cursor rule is `.cursor/rules/frontend/22-frontend-uiux.mdc` (word-capped enforceable subset; globs unchanged). Do not paste rules from this doc — edit the mdc when locks change. The block below is the full design narrative kept here for reference; it expands sections the mdc compresses.

````mdc
---
description: Jarvis HUD frontend — single glass pane, lens transitions, substrate worker, depth model, z-index contexts, motion specs, state rules. Use when creating or editing anything under frontend/src (components, lib, css, tailwind config).
globs: frontend/src/**/*.{ts,tsx,css}, frontend/tailwind.config.ts
alwaysApply: false
---

# Frontend UI/UX — the Single Pane

Design of record: `work/SONNET_UI_VISION.md`. This rule is the enforceable subset. If code and this rule disagree, fix the code.

## 1. One pane, three lenses

- The HUD is **one always-mounted pane**. Intent enum `HudWorkspace` (`casual|monitor|engineering`, `hudWorkspace.ts`) is unchanged and maps 1:1 to lenses `converse|watch|bench` via `lensFor()` in `lib/pane/lenses.ts`. Never add a fourth value to either.
- A lens is a preset: `LENS_LAYOUT` (panel → slot + depth), `LENS_THEME` (root variables), `LENS_SUBSTRATE` (worker uniforms). Changing lens changes presets. It **never** mounts, unmounts, or conditionally renders a panel.
- Every instrument on the pane is a `<PanePanel id>` inside `<Dock>`. No absolutely positioned one-off panels in `OrchestratorShell`. No `{cond ? <Panel/> : null}` driven by lens; use depth 3.
- `OrchestratorShell` owns data, FSM, voice, sessions. It renders `<Pane>` and passes props. It must **not** subscribe to `paneStore.lens` (0 shell commits per lens change is a gate).

## 2. Depth is the only visibility

| depth | scale | opacity | pointer | notes |
| --- | --- | --- | --- | --- |
| 0 hero | 1 | 1 | auto | |
| 1 rail | 1 | 1 | auto | |
| 2 recessed | 0.97 | 0.55 | auto | click raises to 1 |
| 3 parked | 0.94 | 0 | none | `visibility:hidden; content-visibility:hidden; inert; aria-hidden` after settle |

Use `DEPTH_VARIANTS` from `lib/pane/springs.ts`. Do not hand-write depth values.

## 3. Stacking contexts (Tailwind `z-*` tokens only — no `z-[n]` literals)

`z-substrate 0` canvas · `z-field 1` grid/mat · `z-pane 10` Dock · `z-depth3..z-depth0 11–14` panels · `z-vignette 50` · `z-status 60` · `z-baton 70` · `z-toast 90` · `z-overlay 100` scrim · `z-hitl 110` · `z-modal 120`.
Each layer root sets `isolation: isolate`. Nothing inside a panel may set a z-index token outside its own panel.

## 4. Animation strategy — who owns what

- **Worker** (`frontend/src/substrate/`): all WebGL. One `<canvas>`, one context, `OffscreenCanvas` + `substrate.worker.ts`, inline shim fallback. Eye/orb/pilot light are uniform weights on one program set. **Never** create a second WebGL context, never mount `EvilEye`/`Particles`/`LightRays` as DOM components in the pane, never call `renderer.render` on the main thread except in the shim.
- **`motion`** (`motion/react`): per-panel `layout` FLIP and depth `variants`; `whileHover`/`whileTap` micro-motion; `<MotionConfig reducedMotion="user">` at pane root; `useWillChange()` on panels. `layout` is on the **frame** only; inner content uses `layout="position"` or none.
- **GSAP**: the conductor (`lib/pane/conductor.ts`) — root CSS variables (`--bg --surface --fg --muted --border --accent --grid-opacity --vignette-opacity --substrate-dim`), field/vignette, status title, worker `post()` calls, `quickTo` for pointer-linked pin/row highlights and dock tilt.
- Two systems never animate the same element or property. `motion` never touches root vars; GSAP never touches a `PanePanel` transform.
- Constants come **only** from `lib/pane/springs.ts`: `SPRING.pane {170,26,1}`, `SPRING.hero {120,20,1.2}`, `SPRING.recess {200,28,1}`, `SPRING.drawer {260,30,0.9}`, `SPRING.chip {400,30,0.6}`, `EASE.out [0.22,1,0.36,1]`, `DURATION.theme 0.7`. No inline `transition={{ duration: … }}` literals.
- **Banned:** `setTimeout`/`setInterval` choreography; CSS `transition` on root variables; animating `width height top left filter backdrop-filter box-shadow border-color background`; `backdrop-filter` anywhere except `Overlay.tsx` scrim; full-screen crossfades of two canvases; `AeroShards` on the desk.
- A lens gesture starts all voices at t = 0 (no staging) and must be interruptible: `tl.kill()` + rebuild; springs retarget; worker receives a new target.

## 5. Glass

- Panels use `.pane-frost` (baked: surface fill 78 %, 3 % SVG grain, 1 px hairline, 1 px top accent light). No blur.
- Radii: `rounded-pane` (20 px) frame, `rounded-inner` (12 px) content, `rounded-chip` (8 px).
- Colour: only `var(--accent)` (Jarvis / confirmed), amber `ember` (pending / attention), graphite scale, drawing ink. No third accent. `#7dffe0` is `mint-bright` for canvas parity only.
- Type: display `Source Serif 4` (Jarvis lines, titles, totals), body `IBM Plex Sans`, mono `IBM Plex Mono` with `tabular-nums` on every numeral. Micro labels: `text-micro` uppercase.

## 6. State rules

- `lib/pane/paneStore.ts` is an external store (`useSyncExternalStore`) holding `lens phase mode overlay focusMode`. Panels select the slice they need. No lens state in React context or component `useState`.
- `phase: "moving"` from `setLens()` until settled (hero `onLayoutAnimationComplete` + worker `settled`, or 1.4 s watchdog). Heavy effects (scene fetch, findings reframe, quote build) **must** gate on `useLensSettled()` and run in `startTransition`.
- Turn FSM (`orchestratorFsm.ts`) stays a pure reducer; lens never lives in turn state; `PresenceMode` is derived from FSM mode and posted to the worker — one model of Jarvis's state on every lens.
- Persisted keys `jarvis.hudWorkspace` / `jarvis.hudWorkspacePinned` unchanged.

## 7. Bench specifics

- Three surfaces only: `stage` (cols 1–8 / rows 1–6), `strip` (1–8 / 7–8), `sheet` (9–12 / 1–8). Secondary content is tabbed inside the sheet (`Sheet · Strategy · Vision`), never stacked as cards.
- Sheet rows show provenance: ● tool · ◉ owner-confirmed · ◐ pending (dashed amber) · ○ missing (em-dash). A numeral with no source renders ○ — never a guess.
- Proof strip mirrors `quote_verify`; > 2 failures disables Authorize send. Authorize / Reject copy only.
- Stage chrome fades after 2 s idle; Blueprint invert is a static filter toggle, never animated. `DrawingViewer` is wrapped by `DrawingStage`, not forked.

## 8. Verification before you report DONE

- `npm run typecheck && npm run lint` clean.
- Headless: `google-chrome --headless=new --enable-unsafe-swiftshader` loads `/?perf=1`; switch lenses 20×; report `longTasks>50ms = 0`, `rafP95 < 20ms`, `contexts = 1`, `shellCommits = 0`. Attach the JSON or the screenshot.
- Reduced motion (`--force-prefers-reduced-motion`) snaps with no visual gaps.
- Screenshot each lens; on Bench, a fixture quote with all four provenance glyphs.
- Do not expand scope; do not restyle panels outside the kickoff; do not touch `backend/`.
````

### Companion skill note

The existing skill `jarvis-react-bits` stays valid for **accents inside panels** (`SpotlightCard`, `GlareHover`, `GradientText`, `BlurText`, `ClickSpark`, `ElectricBorder`). Its placement rows for `Particles`, `LightRays`, `EvilEye` become "worker-only — see `frontend/src/substrate/`" once Phase 1 lands; that is a one-table edit for the worker who lands Phase 1.

---

## Appendix A — Assumptions and open decisions for the owner

1. **Callout pin geometry.** The design assumes `jarvis_quote_analyze_drawing` can emit `{page, x, y, w, h}` per detected feature. If it cannot, pins fall back to owner-attached crops only (still useful). `jarvis-workflows` confirms in Phase 4.
2. **Eye stock parameters** are preserved (`#FF6F37`, intensity 1.5, pupil 0.6, iris 0.25, glow 0.3, scale 0.8, noise 1, follow 1, flame 1, bg `#120F17`). The worker renders at internal scale 0.6 by default (was 0.55) because it now shares one context and can afford it; adaptive quality drops it under load.
3. **Casual orb rings** (`.orch-ring-*`) can stay as a lightweight DOM ring set at depth 0 in Converse or become a shader pass. I recommend DOM — they are cheap and the CSS is already tuned.
4. **Bench keeps the mint accent** at reduced chroma (`0.10`) so drawing ink stays the strongest thing on screen. If the owner wants a fully neutral bench, only `LENS_THEME.bench.accent` changes.
5. **Safari** on the desk is not assumed. If it ever is, `OffscreenCanvas` in workers needs ≥ 16.4; the inline shim covers older builds automatically.
