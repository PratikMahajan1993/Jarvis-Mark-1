---
name: jarvis-observation-dispatch
description: >
  Dispatch a specialized Jarvis background worker, only when the user explicitly
  asks for one, for an observation reported during capability testing or live
  HUD use. By default the coordinator fixes observations directly. When a worker
  is requested, prefer roster agents over ad-hoc generalPurpose.
---

# Observation → specialist dispatch

## When

The user explicitly asks for a background worker to take a fix (for example, so
they can keep testing elsewhere). Without that request, the coordinator fixes
the observation itself — this skill does not apply.

## Steps

1. Classify the observation (UI / voice / workflow / other).
2. Stay with the user on the next test; **do not** block on the fix.
3. Delegate to the matching roster worker, in the background. The user names the model; if they did not, use the default (inherit):

| Signal | Agent (roster name) |
| ------ | ------------------- |
| Layout, scroll, React Bits, weather, cards, polish | `jarvis-uiux` |
| Speak, Gemini TTS, silence, TTS latency | `jarvis-voice` |
| Mail, HITL, RFQ, calendar, Hermes, tools, compose | `jarvis-workflows` |
| Agreed code task / restart / verify | `jarvis-builder` |

4. Prompt template (fill in):

```
Repo: the Jarvis checkout (desk machine D:\Codex\Jarvis; isolated worker /workspace)
Placement: cloud by default, including HUD/layout/scroll/card-state checks (headless
  Chrome — see jarvis-react-bits skill for the WebGL flag) — desk machine only when the
  check needs Hermes, live Gemini speech, real Google OAuth, GPU-representative Ollama, or
  physical mic/speaker hardware
Observation: <user words>
Capability ID (if any): <e.g. E2>
Repro: <steps>
Context the worker needs: <it cannot see this chat — restate it>
Likely files: <paths>
Constraints: follow .cursor/rules/core/00-jarvis-core.mdc; no scope creep; no commits unless asked
Acceptance: <what must be true in HUD/API>
Return format: DONE / FILES / TRY / GAPS
```

5. Tell the user which specialist was launched (link with `[Name](id)` if available).
6. On completion notification: 2–3 line summary; offer re-test of that ID.

## Hard rules

- Always reuse **`jarvis-uiux`** for UI/UX — do not spawn anonymous UI agents.
- One concern per agent. Split mixed reports into multiple Tasks.
- Never send an isolated worker a task whose acceptance check needs Hermes, live Gemini speech,
  real Google OAuth, GPU-representative Ollama, or physical mic/speaker hardware —
  those five need the desk machine. HUD rendering/layout/scroll/card-state checks are
  cloud-verifiable (headless Chrome + screenshot); do not default those to the desk
  machine.
- Never commit secrets or expand into unrelated matrix IDs.
