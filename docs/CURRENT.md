# Implementation map

Updated 2 October 2026. This is a code navigation guide, not a design contract or a report of live verification. The frontend uses the branch's committed implementation; the recent UI proposal is retained for review and has not been accepted as a completed implementation.

## Frontend

frontend/package.json currently includes Next.js, React, Tailwind, Motion, TanStack Query, Lenis, OGL, GSAP, and VGPU.

frontend/src/app/layout.tsx mounts core/root/JarvisRoot. The main page loads core/desk/Desk. Current section modules are under core/sections/monitor, casual, and engineering. Separate routes include /masterdata, /canvas, and /lab/diarize.

Rendering code is under substrate/ and core/root/, with createSubstrate.ts and the worker protocol in substrate/protocol.ts. Scroll handling is under core/scroll/. These are implementation locations that may change during redesign.

core/desk/controller.ts coordinates sessions, server UI hints, pending approvals, and related effects. core/stores/ contains frontend stores; lib/orchestratorFsm.ts contains the turn reducer. The rendering of assistant activity may change without changing the outcome of an operation.

components/orchestrator/ contains input, approval, preference, and content surfaces. components/bench/ contains drawing and quote UI. features/ contains registered capabilities; sdk/ provides reusable integration hooks. frontend/scripts/new-feature.mjs is an optional scaffold for capabilities, not a requirement for UI redesign.

## API and integrations

backend/app/main.py exposes the FastAPI application. agent.py coordinates assistant turns and confirmations. tools/registry.py dispatches tools; conversations.py and db.py manage conversation data. intent.py, semantic_router.py, core/router.py, and snapshot.py support routing and local read paths.

backend/app/hermes/ contains the bridge, MCP tools, persona, and runtime shop playbooks. The bridge installs quote and master-data playbooks for Hermes. These files are used by the application.

gemini_tts.py implements speech; frontend/src/lib/voice.ts plays responses. Speech defaults and fallback settings are in backend/app/config.py.

quote.py implements quotation analysis, building, verification, and release checks. masterdata/ implements business records and temporal changes. Drawing and quote UI uses real backend fields, including confirmation state and provenance.

## Persistence and approvals

Default storage is data/jarvis.db, data/memory/, data/hermes_sessions.json, and exports/. Relative locations are anchored to this repository by backend/app/config.py.

Sessions, drafts, quote revisions, pending actions, and operation outcomes are persistent business state. UI changes should keep their identities and edit bindings intact.

The application queues consequential external actions for approval. A parked approval is not authorization. Repeated decisions must not create duplicate effects; pending/failed/unknown outcomes must remain visible and truthful. Read agent.py and quote.py when changing their integration.

## Verification and UI material

Use [behavioral checks](../work/CAPABILITY_TEST_MATRIX.md) for functional verification. Frontend scripts are listed in package.json; pytest configuration is at the repository root.

[UI discovery](uiux-discovery/README.md) records an inspection snapshot. [Phase 1 documents](../work/references/jarvis-ui-phase-1/SPECIFICATION.md) contain the recent design proposal, decisions, inventory, and execution workflow. Their presence does not establish that implementation or acceptance checks have passed.

Live Hermes, Google accounts, speech playback, and GPU performance have not been verified by this documentation update.
