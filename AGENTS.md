# Jarvis — Agent & Skill Map

Persistent guidance for Cursor agents working in this repo during capability testing and builds.

## Docs of Record

| Doc | Role |
|-----|------|
| `docs/SYSTEM_TRUTH.md` | **Single source of truth** — current state, locked decisions, architecture, all rules |
| `docs/ROADMAP.md` | **Next steps & priorities** — phased execution plan |
| `docs/CURRENT.md` | **As-built** — what works on the desk today |
| `docs/overhaul/EXPERIENCE_DECISIONS.md` | Scroll-substrate HUD decisions (`X#`) — landing, sections, orb, layers, queue, deck |
| `docs/overhaul/PLATFORM_DECISIONS.md` | Feature platform decisions (`P#`) — folders, manifests, SDK, stores, backend wiring, Phase 3 order |
| `work/CAPABILITY_TEST_MATRIX.md` | Capability test IDs and log |

## Rules

| Rule | Applies | Role |
|------|---------|------|
| `.cursor/rules/core/00-jarvis-core.mdc` | Always | Stack, HITL, ports, HUD shape, playbooks |
| `.cursor/rules/frontend/22-scroll-substrate.mdc` | `frontend/src/**` | Root-hoisted substrate, 4-tier layers, scroll/orb pipeline, feature templates |
| `.cursor/rules/ops/42-dispatch.mdc` | On request | Test-run protocol; subagents only when the user asks |

## HUD Architecture (Scroll Substrate)

One page, not three lenses. A landing overlay preloads the desk, then the owner lands on the saved or ambient section of a vertically scrolling page: **Monitor → Casual → Engineering** (feature sections slot in by `order`).

- **Hoisting:** `app/layout.tsx` → `JarvisRoot` owns the only WebGL context (`frontend/src/substrate/`, worker `OffscreenCanvas`) for the tab's lifetime. It never remounts on route change.
- **Layers:** L0 backdrop · L1 substrate · L2 sections/cards · L3 decor + chrome (StatusCluster, SectionNav, TaskDock, CommandBaton); modal/toast/landing tiers above. Tailwind z-tokens only.
- **Orb:** one persistent casberry-style particle swarm; each section runs an owner-chosen formula (`frontend/src/substrate/formulas/`, see `docs/overhaul/ORB_FORMULAS.md`) and scroll morphs between them; FSM states move formula controls only (HITL also centres it). Evil Eye is gone.
- **State:** `orchestratorFsm.ts` is a pure reducer + `effectsFor`; stores under `frontend/src/core/stores/` run effects; `core/scroll/director.ts` owns every programmatic scroll.
- **Adding things:** a feature is `frontend/src/features/<id>/feature.ts` (+ `backend/app/features/<id>/`) registered with one line, importing Jarvis code only via `@/sdk`. Start with `npm run new:feature <id>`. Templates: `.cursor/rules/frontend/22-scroll-substrate.mdc` §6–9. **Never edit `core/`, `substrate/`, the FSM or the root layout to ship a feature.**

Until overhaul Phase 3 merges, the running HUD is the single-pane `OrchestratorShell` described in `docs/CURRENT.md`.

## Skills (Auto-Routed by Description)

| Skill | Use When |
|-------|----------|
| `jarvis-architecture` | Any structural / stack / workflow change |
| `jarvis-quote-playbook` | Quote/RFQ workflow, shop-quote skill, `quote_verify`, Engineering desk |
| `jarvis-react-bits` | Adding or fixing React Bits surfaces |
| `jarvis-capability-test` | Running matrix IDs A1…J* |
| `jarvis-observation-dispatch` | User reports a live observation mid-test |

## Specialized Subagents (`.cursor/agents/`)

The coordinator **can implement and review code directly**. Subagents are dispatched **only when the user explicitly requests them** for tasks that are:
- Very simple and well-scoped
- Zero ambiguity — no chance of the sub-agent deviating from the coordinator's intent
- Example of BAD use: coordinator consolidates a file, asks subagent to write it → subagent uses its own reasoning instead of writing what coordinator prepared
- Example of GOOD use: "run this specific test and report pass/fail", "apply this exact diff to this file"

The user specifies the `subagent_type` and `model` at dispatch time — no defaults, no automatic dispatch. Background unless the user asks to wait. Placement matters more than the spawn mechanism.

| Agent | Owns | Needs Desk Machine? |
|-------|------|---------------------|
| `jarvis-uiux` | Sections, cards, layers, React Bits, visual polish | No for rendering/layout/scroll/card-state — cloud worker can build/serve HUD and verify headlessly. Yes only when check depends on live Hermes content. |
| `jarvis-voice` | Gemini TTS, `/api/tts`, Charon playback, silence on quota | Yes — needs the Gemini speech key and a speaker |
| `jarvis-workflows` | Mail, HITL, RFQ/quote, calendar, Hermes/snapshot tools | Yes for live mail/Hermes; no for logic + `backend/tests` |
| `jarvis-builder` | General agreed implementation / restarts / verify | Only for restarts and live verification against Hermes/Gmail |

**UI/UX Rule:** Always reuse `jarvis-uiux` for visual work — do not invent ad-hoc UI agents.

**Placement Policy:** Cloud workers run on isolated VMs with browser: HUD builds/serves in cloud, headless Chrome can load/screenshot/script. Cloud **can** verify HUD rendering, layout, scroll, card states. Cloud **cannot** reach: Hermes (`:8642`), live Gemini speech playback, real Google OAuth, GPU-representative Ollama, physical mic/speaker.

**Kickoff Rule:** Worker gets repo, `AGENTS.md`, `.cursor/rules/` — nothing from coordinator chat. Every kickoff carries goal, files in scope, acceptance check, "do not expand scope". Isolated branch worker commits/pushes; shared desk worker does not commit unless told.

## Rule Hierarchy (`.cursor/rules/`)

```
core/
  00-jarvis-core.mdc          # Always-on (alwaysApply: true)
backend/
  10-api-python.mdc           # Module ownership, config, imports, timeouts
  11-hitl-safety.mdc          # Claim-once, external_effects, tools queue
  12-data-schema.mdc          # Migrations, money, units, UTC, provenance
  13-turn-ledger.mdc          # Server turn ledger (gated, default off)
domain/
  30-quote-playbook.mdc       # Quote workflow: provenance, MHR, proof, HITL
frontend/
  22-scroll-substrate.mdc     # Substrate hoisting, 4-tier layers, scroll/orb, feature templates
ops/
  42-dispatch.mdc             # Roster, placement, kickoff, test protocol
```

## Capability Tests

- Matrix: `work/CAPABILITY_TEST_MATRIX.md`
- Run log: Auto-appended by API to `work/LIVE_TEST.md` + JSONL
- Human verdict log: `work/CAPABILITY_TEST_RUN_*.md` (when created)

## Runtime Quick Check

```text
HUD       http://127.0.0.1:3000
API       http://127.0.0.1:8000/api/health
Turns     http://127.0.0.1:8000/api/turns/recent
Hermes    http://127.0.0.1:8642
Speech    Gemini TTS, Charon, via `POST /api/tts`
```