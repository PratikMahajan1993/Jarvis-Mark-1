# Jarvis — Codex workspace guidance

Jarvis is an office assistant for a precision machining business. This checkout is the UI redesign workspace.

## Working here

- Work in this checkout and preserve existing user edits. Do not operate on another checkout or restart shared services unless the task calls for it.
- Use the owner's current request and accepted design decisions to determine scope. Resolve routine design and engineering choices autonomously.
- The frontend is open to substantial redesign: layout, navigation, typography, visual language, components, renderer, scroll behavior, state organization, root layout, and dependencies may change within the requested scope.
- Inspect only the code and documentation relevant to the task. Existing implementation describes what is there; it does not prescribe what the design must become.
- Keep the recent UI documents and reference assets. Apply their decisions when the owner asks to continue that design; keeping a document does not make it a permanent constraint on every future task.
- Use subagents only when the owner explicitly requests them.

## Functional protections

Preserve user data, drafts, conversation identity, working integrations, and approval semantics during UI changes. Do not bypass backend confirmation or quote verification. Do not trigger external sends to demonstrate a visual state. Label fixtures and do not present them as live data. Keep credentials, tokens, databases, customer files, and exports out of commits.

## Useful entry points

- Setup: README.md and docs/INSTALL.md.
- Implementation map: docs/CURRENT.md; inspect code for current behavior.
- Business requirements: docs/PRODUCT_BRIEF.md.
- UI work: work/references/jarvis-ui-phase-1/ and work/references/JARVIS_UI_PHASE_1_PROMPT.md.
- Behavioral checks: work/CAPABILITY_TEST_MATRIX.md.

## Verification

Use checks appropriate to the changed behavior. Frontend scripts in frontend/package.json include typecheck, lint, test, and build. Backend checks run from the repo root with python -m pytest -m "not live_service". Verify visual work in the browser, including relevant input, responsive, and accessibility states. Report what passed, failed, and needs live services or physical hardware.
