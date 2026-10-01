---
name: jarvis-capability-test
description: >
  Run and log Jarvis capability tests from work/CAPABILITY_TEST_MATRIX.md. Use
  when starting a test run, picking the next ID (A1, B1, C3…), recording
  pass/fail/latency, or deciding what to re-test after a fix.
---

# Capability test skill

## Source of truth

`work/CAPABILITY_TEST_MATRIX.md`

## Where this runs

The matrix is normally driven by the user on the desk machine, with the coordinator alongside. If the user asks you to run a subset without them, that is fine — record results the same way. Do not delegate matrix runs to an isolated worker (the pass bar is live HUD behaviour), but the coordinator can run them solo when asked.

## Method

1. Confirm servers: HUD `:3000`, API `127.0.0.1:8000`, Hermes if the case needs it. Speech is Gemini TTS, not a local process.
2. Pick **one** ID (suggested order in the matrix).
3. Run the "How to test" steps yourself or guide the user.
4. After each case, read **`work/LAST_TURNS.md`** (or `GET /api/turns/recent`) for the last ≤ 20 exchanges before judging speak/board/pending.
5. Log with the template:

   ```
   ID:
   Result: pass | fail | flaky
   Latency:
   Notes:
   Fix (if any):
   Retest:
   ```

6. On a fail/flaky observation the coordinator fixes it directly. Dispatch a Cursor subagent only if the user explicitly asks.
7. Do not skip HITL cases or mark pass if Authorize was bypassed.
8. Latency targets: casual ≤ ~5 s warm; simple tools ≤ ~15 s; HUD idle < ~2 s.

## Pass bar

- Correct behavior
- HITL never skipped on external write
- No HUD errors
- Note latency vs target

## After a fix

Re-run **only** the failed ID (and direct dependents). Continue the matrix with the user.
