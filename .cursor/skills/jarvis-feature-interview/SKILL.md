---
name: jarvis-feature-interview
description: >
  Interviews the owner in gated stages before a Jarvis feature is built, then
  wires it through the feature SDK. Use when the user wants to add a feature,
  run a feature interview, turn a workflow into a plug-in, or write an
  implementation plan for a feature or for the Jarvis manifesto core.
---

# Jarvis feature interview

The owner adds work in two windows. This skill is the interview window. It produces a written plan and stops. A later coding window implements that plan and does not interview again.

Read `docs/JARVIS_MANIFESTO.md` before the first question. It is the product intent. `docs/CURRENT.md` is what already runs. Do not re-decide a locked manifesto rule.

## Stop between stages

Ask only the active stage. Then wait. Do not write application code during Stages 0–4. Do not scaffold a feature until the owner says to build, and only a plug-in feature is scaffolded here.

## Stage 0 — Classify

Decide which track this request is.

**Manifesto core.** The owner asks to implement `docs/JARVIS_MANIFESTO.md`, or the work changes the quote spine, Hermes, the particle field, voice rules, WhatsApp as the live quote thread, or HITL send gates. Skip Stages 1–3. Those decisions are already locked. Write the implementation plan in Stage 4 from the manifesto, then stop. Do not run `npm run new:feature` for that plan. The quote spine is not one plug-in feature.

**Plug-in feature.** The work can live in `frontend/src/features/<id>/` and `backend/app/features/<id>/`, importing Jarvis only through `@/sdk`. Continue at Stage 1.

If a request is both, split it. The core part goes in the manifesto plan. The plug-in part gets its own feature id.

## Stage 1 — Problem, people, workflow

Six to eight questions. Who does this, what they may finish, and the step where a person has to act. Push once if an answer lets a price, a date, a drawing, or a send leave without the person the manifesto names.

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

A new section's card uses that section's slot, `<id>.main`, unless the owner names a core slot (`monitor.rail`, `casual.left`, `casual.right`, `engineering.side`, `engineering.deck-empty`).

Numbers come from stored rows. The particle field shows listening, thinking, speaking, or waiting. It does not show a price, a margin, or a tolerance.

## Stage 3 — Failure and blast radius

What can leave the building, who may release it, what happens when the line is down, and what a second tap must not repeat. A quote email, a delivery date, a purchase, a drawing, and master data stay with the owner. An inspection result stays with the marked quality inspector. Staff mail that grows a price, a date, or a commitment is held.

## Stage 4 — Write the plan, then stop

**Plug-in.** Write `docs/features/<id>.md` with: the id, the flags, the slots, the approval kind, what is deterministic, who releases an external act, and the acceptance check. Wait until the owner says to build.

**Manifesto core.** Write `docs/plans/MANIFESTO_CORE.md`. One row per manifesto behavior. Each row is `plugin`, `core`, or `config`, with the file that owns it and a check that proves it. Do not re-interview. Do not start coding. Tell the owner to open a coding window on that file.

The coding window implements the plan as written. It does not interview, and it does not invent a gate the plan does not contain.

## Stage 5 — Plug in, only after the owner says to build

From `frontend/`:

```text
npm run new:feature <id> [--section] [--card <slot>] [--approval <kind>] [--tool <name>] [--intent] [--job <name>] [--migration <slug>]
```

Then fill the stubs. Import Jarvis only from `@/sdk`. Do not edit `core/`, `substrate/`, `lib/orchestratorFsm.ts`, or `app/layout.tsx` to ship the feature.

What the scaffold does:

- `--section` writes a section component and a `defineSection` block. The desk merges it by `order` on the next render. Orders are the next free hundred after 300.
- `--migration <slug>` writes `backend/migrations/NNNN_<id>_<slug>.sql` from the forward-only template. Put the SQL in that file. Do not add an `ALTER` in `init_db()`.
- `--job <name>` registers a job. The API lifespan runs every job on the loaded features. The job body must not perform an external send. An error is logged and the schedule continues.
- `--tool` with an external effect queues a pending action. The feature does not mark it sent.
- Weather's backend file is `backend/app/features_weather.py`. New features use `backend/app/features/<id>/`.

A disabled feature flag hides that feature's section body and its cards. The section's viewport slot stays, so the scroll does not jump.
