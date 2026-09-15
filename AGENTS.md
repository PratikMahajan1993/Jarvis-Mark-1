# Jarvis — agent & skill map

Persistent guidance for Cursor agents working in this repo during capability testing and builds.

## Always-on rules

| Rule | Role |
| ---- | ---- |
| `.cursor/rules/jarvis-core.mdc` | Stack, HITL, ports, HUD shape |
| `.cursor/rules/jarvis-capability-run.mdc` | Test-run: observe → dispatch → continue |
| `.cursor/rules/jarvis-subagent-dispatch.mdc` | Roster specialists for observations |
| `.cursor/rules/jarvis-react-bits.mdc` | HUD accents (when editing frontend) |

## Skills (auto-routed by description)

| Skill | Use when |
| ----- | -------- |
| `jarvis-architecture` | Any structural / stack / workflow change |
| `jarvis-react-bits` | Adding or fixing React Bits surfaces |
| `jarvis-capability-test` | Running matrix IDs A1…J* |
| `jarvis-observation-dispatch` | User reports a live observation mid-test |

## Specialized subagents (`.cursor/agents/`)

Delegate to the worker named below, in the background during capability runs. Where the Task tool is available, the name is the `subagent_type`. Placement matters more than the spawn mechanism — see the right-hand column.

| Agent | Owns | Needs the desk machine? |
| ----- | ---- | ---- |
| `jarvis-uiux` | Layout, React Bits, weather/tasks panels, visual polish | Yes whenever the check is visual |
| `jarvis-voice` | Voicebox, `/api/tts`, speak bridge, double-play, latency | Yes — Voicebox lives on `:17493` |
| `jarvis-workflows` | Mail, HITL, RFQ/quote, calendar, Hermes/snapshot tools | Yes for live mail/Hermes; no for logic + `backend/tests` |
| `jarvis-builder` | General agreed implementation / restarts / verify | Only for restarts and live verification |

**UI/UX rule:** always reuse `jarvis-uiux` for visual work — do not invent ad-hoc UI agents.

**Placement policy:** cloud workers run on isolated VMs and cannot reach Hermes (`:8642`), Voicebox (`:17493`), Google credentials, or a browser. Work whose acceptance is "it looked or sounded right" must run on the user's own machine; work whose acceptance is "the code is correct" can run in the cloud.

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
