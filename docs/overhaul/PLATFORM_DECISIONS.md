# Overhaul — Platform Decisions (Phase 3 contract)

**Locked:** 2026-09-29 (owner interview, rounds 1–2; question 16 answered in full)
**Goal:** after Phase 3, adding a card, a voice command, an approval, a Hermes tool, a full-screen section or a background job is **at most a day's work**. It never requires touching scrolling, the canvas, the layout shell or the turn state machine.
**Companions:** [`EXPERIENCE_DECISIONS.md`](EXPERIENCE_DECISIONS.md) (the `X#` IDs) and [`.cursor/rules/frontend/22-scroll-substrate.mdc`](../../.cursor/rules/frontend/22-scroll-substrate.mdc).

**Owner priority, most frequent first:** cards in existing sections › voice commands › new approvals › new Hermes tools › new full-screen sections › background jobs. The SDK is built in that order.

---

## P1 — Approach: feature folders plus a manifest (option A)

```text
frontend/src/
  app/layout.tsx          → <JarvisRoot>: providers, L0 backdrop, L1 substrate, portals
  app/page.tsx            → <Landing/> + <SectionStack/>
  core/                   LOCKED BASE. Features never import from here.
    root/                 JarvisRoot, QueryClient, portal roots
    layers/               tokens.ts, Backdrop, Foreground, Decor
    scroll/               engine.ts (Lenis), director.ts, progress.ts
    sections/             defineSection, registry, SectionStack, SectionFrame, Slot
      monitor/ casual/ engineering/   the three core sections, built with the same API as features
    stores/               turnStore, deskStore, taskQueueStore, sectionStore
    landing/              Landing, gates
    queue/                TaskDock, DraftChip
    boundary/             FeatureBoundary
  substrate/              engine (Evil Eye removed), presets.ts, protocol v2
  sdk/                    THE ONLY import surface for features
  features/index.ts       explicit list of registered features
  features/<id>/          feature.ts plus the feature's components
  lib/api/                schema.gen.ts (generated) and client.ts

backend/app/
  core/features.py        Feature, Intent, ToolSpec, ApprovalKind, Job, and load_features(app)
  core/events.py          publish(topic, data) and GET /api/events (server push)
  core/scheduler.py       asyncio job runner, started in lifespan
  features/__init__.py    FEATURES = [...]   explicit list
  features/<id>/          feature.py, routes.py, tools.py, approvals.py, jobs.py
backend/migrations/NNNN_<feature>_<what>.sql     one global numbered sequence
backend/tests/features/test_<id>.py
```

- The current `components/orchestrator/*` and `components/pane/*` code moves into `core/sections/{monitor,casual,engineering}` and `core/stores`.
- The pane lens system (`LENS_LAYOUT`, `Lens`, `LensTabs`, conductor) is **deleted**. Each section lays out its own slots.
- `HudWorkspace` (`casual | monitor | engineering`) stays.

## P2 — Registration

- Explicit, one line per side:
  - `frontend/src/features/index.ts`: `export const FEATURES = [weather, …] as const`
  - `backend/app/features/__init__.py`: `FEATURES = [weather.FEATURE, …]`
- **The frontend registry validates at boot.** It throws in development; in production it logs and skips the bad feature. Checks:
  - ids are unique;
  - section `order` values are unique;
  - every card slot exists;
  - orb preset values are in range;
  - every approval view's `kind` exists in `GET /api/features`.
- `GET /api/features` returns the backend manifests (ids, intents, approval kinds, topics), so the frontend and backend can be checked for alignment in tests.
- **Dogfooding:** Phase 3 ports `WeatherCard` into `features/weather/`. That exercises the whole pipeline once.

## P3 — Manifest shapes

**Frontend (`@/sdk`):**

```ts
defineFeature({ id, title, flag?: { default: boolean },
  sections?: SectionDef[], cards?: CardDef[], approvals?: ApprovalView[] })

defineSection({ id, order, label, icon, workspace?, orb: OrbPreset, theme: ThemeTokens,
  decor?: DecorPiece[], lazy?: { mountWithin: number; unmountBeyond: number },
  baton?: boolean /* default true */, slots: SlotId[], component })

defineCard({ id, slot, order, size: "sm" | "md" | "lg", component /* lazy() allowed */, flag? })

defineApprovalView({ kind, Card /* Authorize body */, Chip /* parked draft chip */ })
```

**Core card slots:**

| Section | Slots |
|---|---|
| Monitor | `monitor.main`, `monitor.rail` |
| Casual | `casual.left`, `casual.right` |
| Engineering | `engineering.side`, `engineering.deck-empty` |

**Backend:**

```py
Feature(id, router=None, tools=[], intents=[], approvals=[], jobs=[], topics=[])
Intent(id, examples=[...], route="tool_ops" | "ui_command", section="<section id>")
ToolSpec(name, description, params_schema, fn, external=False)   # external=True ⇒ must queue a pending action, never execute
ApprovalKind(kind, summarize(payload) -> AuthorizeCard, execute(payload, ctx) -> Result)
Job(id, every_s=None, cron=None, fn=..., run_on_start=False)
```

## P4 — SDK (`frontend/src/sdk`)

| Export | Purpose |
|---|---|
| `useJarvisState()` | `{ mode, workspace, section, busy }`, read-only |
| `useJarvisSend()` | `send(text, { section? })`: same path as typing in the baton |
| `useSpeak()` | `speak(text)` through `voice.ts`. Silent when TTS quota is out. |
| `useSection()` | `{ active, progress, go(id), isActive(id) }`. `go` is a *user* scroll. |
| `useOrb()` | `glance(elementOrPoint, ms)`, `pulse("ack" \| "warn")` |
| `useTaskQueue()` | `{ items, park, resume, add(draft), remove }` |
| `requestApproval(kind, payload)` | `POST /api/approvals`. The core inserts it through the HITL envelope. |
| `useFeatureQuery(key, fn, { topics?, interval? })` | TanStack Query wrapper. Refetches when a topic event arrives. |
| `useFeatureMutation(fn, { invalidates? })` | TanStack mutation wrapper |
| `useTopic(topic, handler)` | Subscribe to the server event stream |
| `api` | Typed client generated from OpenAPI |
| `useActiveSession()` | Active `session_id` / conversation |
| `useFeatureFlag(id)` | Whether a feature, section or card is enabled |
| `useToast()` | Show a non-blocking notice |
| `useDraft(key, { server? })` | Autosave (X10 triggers). `localStorage` or the server draft endpoint. |
| `useReducedMotion()` | Honour the OS setting |

**Features must never:**
- change the turn state machine directly;
- own or listen to page scroll (no `window` scroll or wheel listeners);
- create a WebGL context;
- start their own `requestAnimationFrame` loops;
- call Gmail, Calendar or Drive, or send anything external, without an approval;
- use raw `z-index` values (use the layer tokens).

**ESLint `no-restricted-imports` for `src/features/**`:**
- **Allowed:** `@/sdk`, `@/components/react-bits/*`, `@/components/ui/*`, `react`, `motion/react`, and ordinary third-party libraries.
- **Blocked:** `@/core/*`, `@/substrate/*`, `@/lib/*`, `@/components/orchestrator/*`, `@/components/pane/*`, `lenis`, `ogl`, `three`.

## P5 — Stores, state machine, scroll director

- **Stores** use `useSyncExternalStore`, the same pattern as today's `paneStore`. No new state library.
  - `turnStore`: wraps `jarvisReducer` and runs its effects.
  - `deskStore`: sessions, conversations, desk items.
  - `taskQueueStore`: pending approvals, parked ids, drafts.
  - `sectionStore`: active section, scroll position, workspace, pin.
  
  `OrchestratorShell.tsx` (1,871 lines) is dismantled into these stores and the three core sections.
- **`orchestratorFsm.ts` stays a pure function.** Additions:
  - `HITL_PARK { actionId }`: `AWAITING_HITL` (not resolving, same id) → `IDLE`.
  - `HITL_RESUME { action }`: `IDLE` or `LISTENING` → `AWAITING_HITL`.
  - `ROUTE_HINT { section, reason }`: the state is unchanged. It exists only to produce effects.
  - `RECONCILE` gains `parkedIds`, so a parked pending row keeps the state at `IDLE`.
  - `effectsFor(prev, next, event): Effect[]` is pure and returns:
    - `{ kind: "orb-mode", mode }`
    - `{ kind: "scroll", section, reason, source: "auto" }`
    - `{ kind: "autosave", reason }`
  
  Vitest covers every new transition and effect.
- **The effect runner** (in `turnStore`) executes effects after each state change. The reducer never touches the DOM.
- **Scroll director** (`core/scroll/director.ts`): `request(section, { source: "auto" | "user", reason })`.
  - A user request always wins.
  - An auto request is dropped if the page is pinned, if the user scrolled or held the pointer down within the last 1,200 ms, or if a modal is open.
  - A newer auto request replaces a pending one.
  - Under reduced motion, the jump is immediate.
  - Before leaving Engineering, the director emits `autosave` and waits up to 300 ms.
- **One animation loop on the main thread:** motion's frame loop drives Lenis (`frame.update`), the throttled orb posts, and parallax. Feature code has no separate `requestAnimationFrame` loops.

## P6 — Substrate protocol v2

- **Messages in:**
  - `init`, `resize`, `pointer`, `glance`, `visibility`, `reducedMotion`, `quality`: kept.
  - `orb { target: OrbTarget }`: **replaces `lens`**.
  - `mode { mode }`: now read by the engine. `executing` is mapped to `thinking` on the main thread.
  - `level { value: 0..1 }`: speaking amplitude.
  - `route { active }`: freeze and hide off `/`.
- **Messages out:** `ready`, `settled` (no lens field), `stats`, `contextLost`.
- **Uniforms:** `uTime`, `uResolution`, `uMouse`, `uOrb`, `uCenter`, `uScale` (renamed from `uPresenceScale`), `uAccent`, `uDim`, `uSpread`, `uSwirl`, `uTint`, `uLevel`, `uState` (vec4: brightness, pulse, tint mix, ring pulse). **Removed:** `uEye`, `uNoiseTexture`, and every eye property.
- **Scroll → uniforms:** `useScroll()` and `useTransform()` produce a scroll position in section units. `useMotionValueEvent` calls `blendPresets()`, which is pure and tested. The result is posted **at most once per frame**, and only when it changes by more than epsilon.
- **Hosting:** mounted once in `JarvisRoot`, which the App Router never unmounts across navigation. StrictMode-safe: the canvas is created in the effect and disposed in cleanup. The `window.__JARVIS_SUBSTRATE__` debug handle stays.

## P7 — Data layer

- **TanStack Query:** one `QueryClient` in `JarvisRoot`, defaults `staleTime: 5s`, `retry: 1`, `refetchOnWindowFocus: false`. Keys are `["core", …]` or `[featureId, …]`.
- **Server push:** `GET /api/events?topics=a,b` is a single event stream with a 15 s heartbeat. The backend publishes with `events.publish(topic, data)`. Each tab opens one multiplexed `EventSource`, and `useFeatureQuery({ topics })` refetches when an event arrives. `interval` polling covers sources without push. The existing turn and Hermes-run streams stay as they are.
- **Types:**
  1. `backend/scripts/dump_openapi.py` writes `frontend/openapi.json` offline, from `app.openapi()`, so no server needs to be running.
  2. `npm run api:types` runs `openapi-typescript` to produce `src/lib/api/schema.gen.ts`. It is committed, so backend drift fails `typecheck`.
  
  `lib/api.ts` stays for core code until migrated. New code uses the typed client.

## P8 — Backend feature wiring

- **Loader:** `load_features(app)` runs at startup.
- **Routes:** each router mounts at `prefix="/api/<id>"`. The loader asserts the prefix and rejects collisions.
- **Tools:** registered into the `tools/registry.execute_tool` dispatch and the Hermes MCP server as `jarvis_<feature>_<name>`. `external=True` tools may only queue a pending action.
- **Intents:** example phrases are appended to the local ONNX router's example bank (`core/router.py`) at startup. The **0.65 threshold and quote-start precedence stay core-owned.** An intent's `section` becomes the `ui.section` hint (X4).
- **Chat contract:**
  - `ChatRequest` gains `section: str | None`.
  - `ChatResponse` gains `ui: { section, reason } | None`.
  - When the ledger is on, `/api/turns/{id}/events` also emits `ui` at routing time.
- **Approvals:** feature executors plug into the core confirm path. **The core owns** claim-once, `Idempotency-Key`, the `external_effects` intent→settle bracket, and copy discipline. A feature can never mark something as sent.
- **Draft endpoint:** `PUT /api/engineering/tasks/{conversation_id}/draft` stores owner fields that existing `/api/quote/*` writes don't cover. Stored as JSON in `memories`, so no new table.
- **Jobs:** `core/scheduler.py` is started in `lifespan`.
  - Supports interval or cron (using `settings.tz`).
  - Each job runs single-flight, and errors go to the live log.
  - No external effects without HITL.
  - Jobs are off in tests unless explicitly started.
- **Migrations:** one global sequence, named `NNNN_<feature>_<what>.sql`, copied from `TEMPLATE.sql`. Forward-only and idempotent.

## P9 — Scaffolding

`npm run new:feature <id> [--section] [--card <slot>] [--approval <kind>] [--tool <name>] [--intent] [--job <name>]` generates:
- `frontend/src/features/<id>/`: `feature.ts` plus stub components;
- `backend/app/features/<id>/`: `feature.py` plus the requested modules;
- a migration stub with the next number (only when asked);
- `frontend/src/features/<id>/feature.test.ts` and `backend/tests/features/test_<id>.py`;
- the registration line in both index files.

It is idempotent and refuses an id that already exists.

## P10 — Containment and flags

- **`FeatureBoundary`** wraps every section and card: a React error boundary plus a Suspense skeleton.
  - On failure it shows a small "*title* failed · Retry" tile and writes a live-log entry. The rest of the desk is unaffected.
  - A failed section keeps its `100dvh` slot, so scroll positions never shift.
- **Flags** live in `localStorage` (`jarvis.feature.<id>`), and the Preferences panel lists them. A disabled feature's sections and cards don't render. Its backend stays loaded; backend flags come later.

## P11 — Tests and gates

- **Frontend (Vitest, `npm run test`):** registry validation, preset blending, state machine transitions plus `effectsFor`, director rules, and draft debounce. jsdom only where needed.
- **Backend (pytest, offline):** loader collisions, the approval envelope for feature kinds, the `/api/events` stream, the scheduler's single-flight, and `ChatResponse.ui` hints.
- **Gates:** `npm run lint`, `npm run typecheck`, `npm run test`, pytest, and `npm run perf` on the desk.

## P12 — "A day's work" checklists

| Add | Steps |
|---|---|
| Card | `new:feature x --card casual.right`. Build the component with SDK hooks. Register. Test. |
| Voice command | `--intent`. Add 5–10 example phrases and a `section`. Run the pytest hint test. |
| Approval | `--approval kind`. Write the backend `execute` and `summarize`, plus the frontend `Card` and `Chip`. The envelope is automatic. |
| Hermes tool | `--tool name`. Write `ToolSpec` and `fn`. It is exposed to MCP automatically. `external=True` ⇒ queue a pending action. |
| Section | `--section`. Set `order`, orb preset, theme, slots, and an optional workspace. The nav, snap, orb blend and lazy loading are automatic. |
| Job | `--job name`. Set the schedule and `fn`. Publish a topic so the UI refetches. |

## P13 — Phase 3 order (one commit or more per step)

1. **Tooling:** `lenis`, `@tanstack/react-query`, `openapi-typescript` (dev), `vitest` (dev); ESLint import boundaries; layer z-tokens in Tailwind.
2. **Substrate v2:** remove the eye; add presets, state modifiers, protocol v2 and `level`; hoist into `JarvisRoot`.
3. **Stores:** extract them; add the state machine events and `effectsFor`; add the effect runner (with tests).
4. **Sections:** scroll engine, section registry and `SectionStack`; port the three core sections; SectionNav, L0/L3 layers, baton dimming.
5. **Landing** and its gates.
6. **Director** plus the backend `ui` hint (`ChatRequest.section`, `ChatResponse.ui`).
7. **Task queue:** TaskDock, the draft-chip morph, and `HitlModal` Later / resume.
8. **Engineering deck** plus autosave and the draft endpoint.
9. **Feature platform:** SDK, `core/features.py`, `/api/events`, scheduler, OpenAPI types, `new:feature`, and the `weather` port.
10. **Wrap-up:** extend the perf gate; update `docs/CURRENT.md` to the as-built state; add capability matrix IDs for the scroll HUD.

**Main risk:** step 3 touches voice, HITL and session restore at once. Mitigations: backend mirror tests stay green; Vitest covers the reducer and effects; a headless walk (landing → each section → HITL park/resume) runs after steps 3, 4 and 7.
