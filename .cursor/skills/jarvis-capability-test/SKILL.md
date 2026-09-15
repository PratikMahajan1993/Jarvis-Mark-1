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

The matrix is driven by the user on the desk machine, with the coordinator alongside.
It is not delegated to an isolated worker — the pass bar is live HUD behaviour.

## Method

1. Confirm servers: HUD `:3000`, API `127.0.0.1:8000`, Hermes/Voicebox if the case needs them.
2. Pick **one** ID (suggested order in the matrix).
3. Run the “How to test” steps yourself or guide the user.
4. After each case, read **`work/LAST_TURNS.md`** (or `GET /api/turns/recent`) for the last ≤20 exchanges before judging speak/board/pending.
5. Log with the template:

```
ID:
Result: pass | fail | flaky
Latency:
Notes:
Fix (if any):
Retest:
```

6. On fail/flaky observation → skill **`jarvis-observation-dispatch`** (background worker; place it per that skill).
7. Do not skip HITL cases or mark pass if Authorize was bypassed.
8. Latency targets: casual ≤~5s warm; simple tools ≤~15s; HUD idle &lt;~2s.

## Pass bar

- Correct behavior
- HITL never skipped on external write
- No HUD errors
- Note latency vs target

## After a fix

Re-run **only** the failed ID (and direct dependents). Continue the matrix with the user.
