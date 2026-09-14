---
name: jarvis-observation-dispatch
description: >
  Dispatch specialized Jarvis background subagents when the user reports
  observations during capability testing or live HUD use. Use when the user
  describes a UI bug, TTS issue, mail/HITL/workflow problem, or asks to fix
  something while continuing to test. Always prefer roster agents over ad-hoc
  generalPurpose.
---

# Observation → specialist dispatch

## When

User is testing and says things like: “this looks wrong”, “latency”, “played twice”,
“card clipped”, “Authorize failed”, “mail empty”, “weather missing”, or assigns a
fix while wanting to continue testing elsewhere.

## Steps

1. Classify the observation (UI / voice / workflow / other).
2. Stay in the parent chat for the next test; **do not** block on the fix.
3. Launch Task with `run_in_background: true` and the matching `subagent_type`:

| Signal | Agent (`subagent_type`) |
| ------ | ----------------------- |
| Layout, scroll, React Bits, weather, cards, polish | `jarvis-uiux` |
| Speak, Voicebox, double audio, TTS latency | `jarvis-voice` |
| Mail, HITL, RFQ, calendar, Hermes, tools, compose | `jarvis-workflows` |
| Agreed code task / restart / verify | `jarvis-builder` |

4. Prompt template (fill in):

```
Repo: D:\Cursor\Jarvis
Observation: <user words>
Capability ID (if any): <e.g. E2>
Repro: <steps>
Likely files: <paths>
Constraints: follow .cursor/rules/jarvis-core.mdc; no scope creep; no commits unless asked
Acceptance: <what must be true in HUD/API>
Return format: DONE / FILES / TRY / GAPS
```

5. Tell the user which specialist was launched (link with `[Name](id)` if available).
6. On completion notification: 2–3 line summary; offer re-test of that ID.

## Hard rules

- Always reuse **`jarvis-uiux`** for UI/UX — do not spawn anonymous UI agents.
- One concern per agent. Split mixed reports into multiple Tasks.
- Never commit secrets or expand into unrelated matrix IDs.
