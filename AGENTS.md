# Jarvis — agent & skill map

Persistent guidance for Cursor agents working in this repo during capability testing and builds.

## Always-on rules

| Rule | Role |
| ---- | ---- |
| `.cursor/rules/jarvis-core.mdc` | Stack, HITL, ports, HUD shape |
| `.cursor/rules/jarvis-capability-run.mdc` | Test-run: observe → dispatch → continue |
| `.cursor/rules/jarvis-subagent-dispatch.mdc` | All code changes via Composer 2.5 Fast roster workers |
| `.cursor/rules/jarvis-react-bits.mdc` | HUD accents (when editing frontend) |

## Skills (auto-routed by description)

| Skill | Use when |
| ----- | -------- |
| `jarvis-architecture` | Any structural / stack / workflow change |
| `jarvis-react-bits` | Adding or fixing React Bits surfaces |
| `jarvis-capability-test` | Running matrix IDs A1…J* |
| `jarvis-observation-dispatch` | User reports a live observation mid-test |

## Specialized subagents (`.cursor/agents/`)

The coordinator does not implement. Every code change is a Task with `subagent_type` from the roster below and **`model: composer-2.5-fast`** (Composer 2.5 Fast). Background unless the user asks to wait. Placement matters more than the spawn mechanism — see the right-hand column.

| Agent | Owns | Needs the desk machine? |
| ----- | ---- | ---- |
| `jarvis-uiux` | Layout, React Bits, weather/tasks panels, visual polish | No for rendering/layout/scroll/card-state — a cloud worker can build/serve the HUD and verify it headlessly (see `jarvis-react-bits` skill). Yes only when the check depends on live Voicebox or Hermes content. |
| `jarvis-voice` | Voicebox, `/api/tts`, speak bridge, double-play, latency | Yes — Voicebox lives on `:17493` |
| `jarvis-workflows` | Mail, HITL, RFQ/quote, calendar, Hermes/snapshot tools | Yes for live mail/Hermes; no for logic + `backend/tests` |
| `jarvis-builder` | General agreed implementation / restarts / verify | Only for restarts and live verification against Hermes/Voicebox/Gmail |

**UI/UX rule:** always reuse `jarvis-uiux` for visual work — do not invent ad-hoc UI agents.

**Placement policy:** cloud workers run on isolated VMs, but they do have a browser: the HUD builds and serves in the cloud (`next build` / `next dev`), and a headless Chrome can load, screenshot, and script it (see `jarvis-react-bits` skill for the one WebGL flag the orb's particle background needs headlessly). So HUD rendering, layout, scroll behavior, and card states are cloud-verifiable, and work whose acceptance is "the code/HUD is correct" can run in the cloud by default. What a cloud worker genuinely cannot reach is Hermes (`:8642`), Voicebox (`:17493`), real Google OAuth, GPU-representative Ollama (no owner GPU in the cloud), and physical mic/speaker hardware — work that depends on one of those five needs the desk machine.

**Kickoff rule:** a worker gets the repo, `AGENTS.md`, and `.cursor/rules/` automatically — and nothing from the coordinator's chat. Every kickoff carries goal, files in scope, acceptance check, and "do not expand scope". A worker with an isolated branch commits and pushes it; a worker sharing the desk checkout does not commit unless told.

## Capability tests

- Matrix: [`work/CAPABILITY_TEST_MATRIX.md`](work/CAPABILITY_TEST_MATRIX.md)
- Turn log (last 20): [`work/LAST_TURNS.md`](work/LAST_TURNS.md) — auto-written by API after each chat/confirm
- Vision: [`work/VISION_WORKBOOK.md`](work/VISION_WORKBOOK.md)
- As-built: [`docs/CURRENT.md`](docs/CURRENT.md)

## Runtime quick check

```text
HUD     http://127.0.0.1:3000
API     http://127.0.0.1:8000/api/health
Turns   http://127.0.0.1:8000/api/turns/recent
Hermes  http://127.0.0.1:8642
Voicebox http://127.0.0.1:17493
```
