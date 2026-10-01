---
name: jarvis-feature-interview
description: >
  Interviews the owner in gated stages before a Jarvis feature is built, then
  wires it through the feature SDK. Use when the user wants to add a feature,
  run a feature interview, or turn a workflow into a plug-in.
---

# Jarvis feature interview

This skill is the interview window. It produces a written plan and stops. A later coding window implements that plan and does not interview again.

`docs/SYSTEM_TRUTH.md` is what already runs and what is locked. Do not re-decide a locked rule.

## Stop between stages

Ask only the active stage. Then wait. Do not write application code during Stages 0–4. Do not scaffold a feature until the owner says to build.

## Stage 0 — Classify

Pick the smallest track that fits.

**Trivial addition.** A read-only card in an existing slot, a new styling variation, a new read-only tool, a new copy line. No new external act, no new approval kind, no migration, no new section. Skip Stages 1–4. Build it directly in the feature folder; mention it in chat. If during the work you realise a number leaves the building, a customer can see it, or a send happens — stop and run Stages 1–4 before continuing.

**Core change.** The work touches the quote spine, Hermes routing, the substrate/particle field, voice, or HITL send gates. Skip Stages 1–3. Write the implementation plan in Stage 4 directly from `docs/SYSTEM_TRUTH.md`. Do **not** run `npm run new:feature` for it.

**Plug-in feature.** Everything else that is a real feature. Continue at Stage 1.

If a request is both, split it. The core part goes in the plan. The plug-in part gets its own feature id.

## Stage 1 — Problem, people, workflow

Six to eight questions. Who does this, what they may finish, and the step where a person has to act. Push once if an answer lets a price, a date, a drawing, or a send leave without the person named by `docs/SYSTEM_TRUTH.md` §3.

## Stage 2 — Placement

Where it sits on the one monitor, and which scaffold flags it needs:

| Need | Flag |
|---|---|
| Full-screen section | `--section` |
| Card in a slot | `--card <slot>` |
| HITL approval kind | `--approval <kind>` |
| Hermes tool | `--tool <name>` |
| Routed phrases | `--intent` |
| Repeating job | `--job <name>` |
| SQL change | `--migration <slug>` |

A new section's card uses that section's slot, `<id>.main`, unless the owner names a core slot (`monitor.rail`, `casual.left`, `casual.right`, `engineering.side`, `engineering.deck-empty`). For SDK shapes and the scaffold template, see `docs/overhaul/PLATFORM_DECISIONS.md` — do not restate them here.

## Stage 3 — Failure and blast radius

What can leave the building, who may release it, what happens when the line is down, and what a second tap must not repeat. A quote email, a delivery date, a purchase, a drawing, and master data stay with the owner.

## Stage 4 — Write the plan, then stop

**Plug-in.** Write `docs/features/<id>.md` with: the id, the flags, the slots, the approval kind, what is deterministic, who releases an external act, and the acceptance check. Wait until the owner says to build.

**Core change.** Write `docs/plans/<name>.md`. One row per behaviour, with the file that owns it and a check that proves it. Do not start coding.

## Stage 5 — Plug in, only after the owner says to build

From `frontend/`:

```text
npm run new:feature <id> [--section] [--card <slot>] [--approval <kind>] [--tool <name>] [--intent] [--job <name>] [--migration <slug>]
```

Then fill the stubs. Import Jarvis only from `@/sdk`. Do not edit `core/`, `substrate/`, `lib/orchestratorFsm.ts`, or `app/layout.tsx` to ship the feature.

- A disabled feature flag hides the section body and its cards; the section's viewport slot stays so scroll does not jump.
- A `--tool` with an external effect queues a pending action; the feature does not mark it sent.
- A `--job <name>` runs at API lifespan start; the job body must not perform an external send.
- Weather's backend file is `backend/app/features_weather.py`. New features use `backend/app/features/<id>/`.
