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

Launch with Task `subagent_type` = name below, **`run_in_background: true`** during capability runs.

| Agent | Owns |
| ----- | ---- |
| `jarvis-uiux` | Layout, React Bits, weather/tasks panels, visual polish |
| `jarvis-voice` | Voicebox, `/api/tts`, speak bridge, double-play, latency |
| `jarvis-workflows` | Mail, HITL, RFQ/quote, calendar, Hermes/snapshot tools |
| `jarvis-builder` | General agreed implementation / restarts / verify |

**UI/UX rule:** always reuse `jarvis-uiux` for visual work — do not invent ad-hoc UI agents.

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
