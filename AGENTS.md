# Jarvis

Jarvis is an office assistant for a precision machining company. These instructions apply in every checkout.

## Freedom

Decide how to build. Within the task you were given:

- Choose the architecture, data flow, libraries, and dependencies when a better approach is justified.
- Redesign the interface: layout, navigation, typography, motion, components, scroll, rendering, and information architecture.
- Refactor or replace weak code. Existing structure is evidence of what is there, not a requirement to keep it.
- Use the browser, visual inspection, external tools, and external skills.
- Dispatch subagents when they speed up investigation or implementation. Keep the product judgment for the task you were given.
- Make ordinary technical choices without a planning document, an interview, or an extra approval step.

`docs/CURRENT.md` is a map of the code. `docs/uiux-discovery/` is an inspection snapshot. `work/CAPABILITY_TEST_MATRIX.md` is a list of behaviors worth checking. None of them freezes the design.

## Protections

- Prices, dates, dimensions, rates, mail, and calendar facts come from tools or stored records. If the source is missing, ask or leave the fact missing.
- Outbound mail, calendar writes, quote send, sheet writes, CNC promotion, and broad memory wipes wait for the owner to authorize them. A queued or parked action has not been done. Do not claim success until execution records the outcome.
- Do not bypass quote verification. Do not transmit a program to a machine, a control, or a DNC link.
- Preserve user data, drafts, conversation identity, and approval outcomes when the interface changes.
- Do not perform an external send just to show a screen. Label fixtures as fixtures.
- Do not commit `.env`, tokens, databases, customer files, or `exports/`.

Business intent is `docs/PRODUCT_BRIEF.md`. It does not dictate frontend structure. Schema changes follow `docs/MIGRATION_STANDARDS.md`.

## Checks

Verify the behavior you changed. Frontend scripts are in `frontend/package.json`. From the repo root, backend checks are `python -m pytest -m "not live_service"`. When the interface changes, look at it in a browser, including the states that change can break. Report what passed, what failed, and what still needs live services or hardware.
