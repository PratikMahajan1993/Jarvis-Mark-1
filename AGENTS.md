# Jarvis — Agent & Skill Map

Persistent guidance for Cursor agents working in this repo during capability testing and builds.

## Docs of Record

| Doc | Role |
|-----|------|
| `docs/SYSTEM_TRUTH.md` | **Single source of truth** — current state, locked decisions, architecture, all rules |
| `docs/ROADMAP.md` | **Next steps & priorities** — phased execution plan |
| `docs/CURRENT.md` | **As-built** — what works on the desk today |
| `work/CAPABILITY_TEST_MATRIX.md` | Capability test IDs and log |

## Always-On Rules

| Rule | Role |
|------|------|
| `.cursor/rules/core/00-jarvis-core.mdc` | Stack, HITL, ports, HUD shape, playbooks |
| `.cursor/rules/ops/42-dispatch.mdc` | Test-run: observe → dispatch → continue |
| `.cursor/rules/ops/41-living-notes.mdc` | When to update `docs/SYSTEM_TRUTH.md` or `docs/ROADMAP.md` |

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
| `jarvis-uiux` | Layout, React Bits, weather/tasks panels, visual polish | No for rendering/layout/scroll/card-state — cloud worker can build/serve HUD and verify headlessly. Yes only when check depends on live Voicebox or Hermes content. |
| `jarvis-voice` | Voicebox, `/api/tts`, speak bridge, double-play, latency | Yes — Voicebox lives on `:17493` |
| `jarvis-workflows` | Mail, HITL, RFQ/quote, calendar, Hermes/snapshot tools | Yes for live mail/Hermes; no for logic + `backend/tests` |
| `jarvis-builder` | General agreed implementation / restarts / verify | Only for restarts and live verification against Hermes/Voicebox/Gmail |

**UI/UX Rule:** Always reuse `jarvis-uiux` for visual work — do not invent ad-hoc UI agents.

**Placement Policy:** Cloud workers run on isolated VMs with browser: HUD builds/serves in cloud, headless Chrome can load/screenshot/script. Cloud **can** verify HUD rendering, layout, scroll, card states. Cloud **cannot** reach: Hermes (`:8642`), Voicebox (`:17493`), real Google OAuth, GPU-representative Ollama, physical mic/speaker.

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
  31-gcode-optimiser.mdc      # G-code: draft, verify, never transmit
  32-master-data.mdc          # Temporal lookups, aliases, demo attestation
  33-knowledge-rag.mdc        # Three planes, ingest bans, embeddings
  34-drawing-vision.mdc       # Two gates: consent + quota, local-first
frontend/
  20-hud-shell.mdc            # FSM reducer, ledger vs workspace, reconciliation
  21-react-bits.mdc           # Accents placement, headless testing
  22-frontend-uiux.mdc        # Single pane, lenses, substrate, depth, motion
ops/
  40-tests.mdc                # live_service marker, offline-first, regressions
  41-living-notes.mdc         # Update SYSTEM_TRUTH/ROADMAP on new intent
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
Voicebox  http://127.0.0.1:17493
```