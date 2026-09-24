# UI / UX inventory (reconnaissance)

**Branch:** `overhaul` (`41542be`). Fresh source-based survey of HUD routes, components, states, and journeys, rechecked 2026-09-24.
**Uncertainty:** *Unknown — requires further investigation.*

---

## 1. Next.js routes

| Route | File | UI |
| --- | --- | --- |
| `/` | `frontend/src/app/page.tsx` | Primary **Orchestrator** desk (dynamic import, no SSR) |
| `/canvas` | `frontend/src/app/canvas/page.tsx` | **Canvas** whiteboard (`CanvasShell`) — separate from orchestrator |
| `/lab/diarize` | `frontend/src/app/lab/diarize/page.tsx` | Lab tool (`DiarizeLab`) |
| Layout | `frontend/src/app/layout.tsx`, `globals.css` | Root HTML shell, design tokens (`--accent`, workspace themes via pane) |

**Query overrides (orchestrator):** `?lens=monitor|casual|engineering` read in `OrchestratorShell` (`workspaceFromLensQuery()`). Perf tooling: `?perf=1` (see `frontend/src/lib/pane/perf.ts`, `perf-gate.mjs`).

---

## 2. Primary user surface: Orchestrator + Pane

### Composition hierarchy

```text
HomePage
└── OrchestratorShell
    ├── Pane (always mounted)
    │   ├── Substrate (WebGL worker canvas)
    │   ├── Field / Dock / PanePanel slots
    │   ├── LensTabs (workspace ↔ lens)
    │   ├── CommandBaton (compose + mic)
    │   └── StatusCluster / Vignette
    ├── Modals/overlays (parallel to pane store overlay kind)
    │   ├── HitlModal
    │   ├── DraftComposeModal
    │   ├── ConnectGoogleModal
    │   └── PreferencesPanel
    ├── ConversationRail (open notes, max 3 expanded)
    ├── Orchestra / AgentOrbit (monitor lens)
    ├── SceneBoard (mail/quote widgets — SpotlightCard scroll pattern)
    ├── Bench panels (engineering): DrawingStage, QuoteSheet via pane slots
    ├── WeatherCard + SuggestedTasksPanel (right rail)
    ├── JarvisCore (orb — Particles/LightRays accents)
    ├── TurnStageLine (ledger stage label when turn_id set)
    └── ActivityStream, TurnStageLine, error/voice lines
```

**Living notes claim** (`work/ARCHITECTURE_POINTS.md`): per-workspace skin folders `orchestrator/casual|monitor|engineering/` — **not present** in tree; only `engineering/` and `monitor/` subfolders under `components/orchestrator/` plus shared shell. Layout is **pane lens-driven**, not separate route trees.

---

## 3. Workspace ↔ lens ↔ labels

| HUD workspace (`HudWorkspace`) | Pane lens (`Lens`) | UI label (`WORKSPACE_LABELS`) | Primary affordances |
| --- | --- | --- | --- |
| `monitor` | `watch` | Monitor | Agent orbit, activity stream, Evil Eye accent (React Bits), status utterances stay here |
| `casual` | `converse` | Casual | Conversation rail, mail/chat boards, LightRays/Particles on orb |
| `engineering` | `bench` | Engineering | Drawing stage + quote sheet at depth 0, engineering widgets (variance, vision queue, tool change, fact chips) |

Mapping: `lensForWorkspace()` / `workspaceForLens()` in `frontend/src/lib/pane/lenses.ts`.  
Sync: `useSyncWorkspaceLens(workspace)` in `LensTabs.tsx`; pin/auto rules in `hudWorkspace.ts` (`persistWorkspace`, `initialWorkspaceFromBootstrap`, `talkJumpWorkspace`).

---

## 4. Panel layout by lens

Source: `LENS_LAYOUT` in `lenses.ts` — eight panel ids: `voice`, `notes`, `weather`, `tasks`, `agents`, `activity`, `stage`, `sheet`. Each has `slot` + `depth` (0 = hero, 3 = deep/back).

**Bench lens:** `stage` and `sheet` at depth 0 (engineering hero); voice moves to `strip` slot.  
**Watch lens:** `tasks`/`agents`/`activity` promoted; stage/sheet recessed to depth 3 (still mounted — no destroy on switch per `docs/CURRENT.md`).

Pane gesture state: `paneStore.ts` — `phase: settled | moving`, `displayLens` frozen while moving; settle via worker + hero panel callbacks or 1400ms watchdog.

---

## 5. State machines and UI modes

### A. Turn FSM (`frontend/src/lib/orchestratorFsm.ts`)

| `JarvisState.mode` | User-visible behavior (typical) |
| --- | --- |
| `IDLE` | Awaiting instruction copy / idle voice line |
| `LISTENING` | Mic open (`voice.startListening`) |
| `THINKING` | Busy; optional `TurnStageLine` stage text when ledger on |
| `SPEAKING` | TTS / voice line active |
| `AWAITING_HITL` | HitlModal; subflags `listening` (confirm mic), `resolving` (confirm API in flight) |
| `EXECUTING` | Post-approve execution |

Events: `SEND`, `LISTEN_*`, `SPEAK_*`, `AWAIT_HITL`, `DECIDE_*`, `RESET`, `RECONCILE` (ledger snapshot).  
Server mapping: `hydrate()` / `failureLineForTurn()` aligned with backend turn states (comment references backend tests).

### B. Orchestrator chrome mode (`OrchestratorMode` in `frontend/src/lib/orchestrator.ts`)

`idle | listening | busy | hitl` — drives pane **presence** via `Pane` `modeToPresence()` → substrate `PresenceMode` (`idle`, `listening`, `thinking`, `speaking`, `hitl`).

### C. Pane overlay kind (`paneStore.ts`)

`OverlayKind`: `none | hitl | compose | prefs | google` — *wiring to modals in OrchestratorShell; exact setOverlay call sites — partially in shell, not fully enumerated here.*

### D. Focus mode

`FocusMode`: `normal | stage` in pane store — stage emphasis for bench drawing.

---

## 6. Component inventory (orchestrator)

| Component | Path | Role |
| --- | --- | --- |
| OrchestratorShell | `orchestrator/OrchestratorShell.tsx` | Root conductor |
| Pane | `pane/Pane.tsx` | Lens shell + panel grid |
| JarvisCore | `orchestrator/JarvisCore.tsx` | Center orb / voice visual |
| CommandBaton | `orchestrator/CommandBaton.tsx` | Text + mic entry |
| HitlModal | `orchestrator/HitlModal.tsx` | Authorize / Reject |
| ConversationRail | `orchestrator/ConversationRail.tsx` | Open notes |
| WorkspaceSwitcher | `orchestrator/WorkspaceSwitcher.tsx` | Manual workspace |
| WeatherCard | `orchestrator/WeatherCard.tsx` | Pinned weather (shrink-0 pattern) |
| SuggestedTasksPanel | `orchestrator/SuggestedTasksPanel.tsx` | Scrollable tasks |
| SceneBoard | `SceneBoard.tsx` | Widget board inside SpotlightCard |
| Orchestra | `orchestrator/Orchestra.tsx` | Agent strip |
| AgentOrbit | `monitor/AgentOrbit.tsx` | Monitor visualization |
| ActivityStream | `orchestrator/ActivityStream.tsx` | Activity feed |
| TurnStageLine | `orchestrator/TurnStageLine.tsx` | Ledger stage + SSE |
| DraftComposeModal | `orchestrator/DraftComposeModal.tsx` | Email compose chrome |
| ConnectGoogleModal | `orchestrator/ConnectGoogleModal.tsx` | OAuth prompt |
| PreferencesPanel | `orchestrator/PreferencesPanel.tsx` | User prefs |
| Engineering | `engineering/*.tsx` | VisionBenchQueue, VarianceCard, ToolChangeField, FactConfirmChips, CustomerVisionConsent |
| Bench | `bench/*.tsx` | DrawingStage, QuoteSheet, ConverseStrip, ProofStrip, etc. |

### Pane infrastructure

`pane/Dock.tsx`, `Field.tsx`, `PanePanel.tsx`, `Substrate.tsx`, `LensTabs.tsx`, `StatusCluster.tsx`, `Vignette.tsx`, `PerfOverlay.tsx`, hooks `usePaneIdleDim.ts`, `useWatchFindingsGlance.ts`.

### Substrate / WebGL

`frontend/src/substrate/` — `createSubstrate.ts`, `substrate.worker.ts`, `engine.ts`, shaders (`presence.frag.ts`), protocol types in `protocol.ts`. Single canvas; lens tweens weights (per `docs/CURRENT.md`).

---

## 7. React Bits accents (vendored)

Path: `frontend/src/components/react-bits/` (13 components):  
`SpotlightCard`, `GlareHover`, `GradientText`, `BlurText`, `ClickSpark`, `ElectricBorder`, `Particles`, `LightRays`, `EvilEye`, `AeroShards`, `Magnet`, `CardSwap` (+ css).

Placement rules: `.cursor/rules/frontend/21-react-bits.mdc`, skill `jarvis-react-bits`.  
**Headless note:** WebGL bits need Chrome `--enable-unsafe-swiftshader` for CI/cloud (documented in rule file).

---

## 8. User journeys (HUD)

### J1 — Ambient monitor → casual mail

1. Default workspace `monitor` when ambient session `default` (`autoWorkspaceFromFocus`).
2. User speaks mail intent from monitor → `talkJumpWorkspace` → `casual` before send (`OrchestratorShell.send`).
3. Lens animates to `converse`; conversation rail may show discussion.
4. Chat response renders SceneBoard widgets / voice line.

### J2 — Monitor status question (no jump)

Short status utterance matches `isStatusUtterance()` → `talkJumpWorkspace` returns null → stays monitor.

### J3 — Monitor → engineering quote

Engineering regex in `talkJumpWorkspace` → `engineering` lens `bench` → bench stage/sheet panels surface (`BenchStagePanel`, `BenchQuotePanel` in shell).

### J4 — Open note / job focus

User expands conversation (max 3) → `ConversationRail` → session switch → `loadSessionSurface()` restores pending HITL if any (`api.pending`, FSM `AWAIT_HITL` without auto confirm-mic).

### J5 — HITL authorize

Pending action from API → HitlModal → Authorize/Reject or spoken yes/no (`classifyDecision` client + server) → `api.confirm` → `EXECUTING` or reset.

### J6 — Email compose modal

Mail draft intent → pending `email_compose` → DraftComposeModal; merge/fill paths on server (`mail_compose`, `agent.py`).

### J7 — Google connect

Incomplete Google services → `ConnectGoogleModal` + `googleConnectSpeakLine`; OAuth via `/api/google/auth` popup flow.

### J8 — Turn ledger path (when API flag on)

Send → `{ turn_id }` only → `TurnStageLine` SSE → completion applies full `ChatResponse`. On load, `reconcileOpenTurn()` hydrates FSM from `/api/turns/open`.

*With default `turn_ledger_enabled=false`, journey J8 is dormant at API but UI code remains.*

### J9 — Canvas (separate app area)

Navigate to `/canvas` → `CanvasShell` — boards/files API; not integrated into Orchestrator workspace switcher.

### J10 — Preferences / workspace pin

User pins workspace → `persistWorkspacePinned`; unpinned auto workspace from conversation category (`workspaceFromCategory`: drawing/workflow → engineering, discussion → casual).

---

## 9. API touchpoints (HUD)

Central client: `frontend/src/lib/api.ts` — health, chat, confirm, pending, conversations, briefing, glance, RFQ, artifacts, session, turns, TTS, suggested tasks, knowledge, vision bench, canvas, live-log, hermes warm, etc.

**Auth header:** mutating requests from non-local browser origins may need `NEXT_PUBLIC_JARVIS_API_TOKEN` when API enforces LAN bearer middleware.

---

## 10. Visual / motion systems

- **GSAP / Motion:** `motion/react` in `Pane` (`LayoutGroup`, `MotionConfig reducedMotion="user"`); pane springs in `lib/pane/springs.ts`, conductor in `lib/pane/conductor.ts`.
- **Idle dim:** `usePaneIdleDim` ties dimming to orchestrator mode + listening.
- **Perf instrumentation:** `PerfOverlay`, `recordOrchestratorShellCommit`, React `Profiler` in shell when `?perf=1`.
- **Themes:** per-lens CSS variables via `LENS_THEME` and substrate; accent `#7dffe0` (casual/converse), watch uses warm accent (`LensSparkShell` uses `#FF6F37` on watch lens).

---

## 11. Documented UX locks vs code (observations)

| Source | Observation |
| --- | --- |
| `work/ARCHITECTURE_POINTS.md` | Three workspace skin directories — **not found**; pane lens replaces per-route desks. |
| `docs/CURRENT.md` | Single pane, bench panels stay mounted — **matches** `Pane` + bench components. |
| `.cursor/rules/frontend/20-hud-shell.mdc` | Describes OrchestratorShell + FSM — **matches**; read for scroll/HITL constraints. |
| `work/SONNET_UI_VISION.md` | Perf thresholds referenced in `CURRENT.md` — latest gate result in `work/perf/phase-6.json` (long tasks on load). |

---

## 12. Secondary / lab UI

- **Diarize lab:** `frontend/src/app/lab/diarize/` — isolated from production desk flows.
- **Canvas:** collaborative board UI under `frontend/src/components/canvas/` (*full component list not expanded here*).

---

## 13. Related paths

- Workspace logic: `frontend/src/components/orchestrator/hudWorkspace.ts`
- FSM: `frontend/src/lib/orchestratorFsm.ts`
- Pane store: `frontend/src/lib/pane/paneStore.ts`
- Voice UX: `frontend/src/lib/voice.ts`
- Types: `frontend/src/lib/types.ts`
