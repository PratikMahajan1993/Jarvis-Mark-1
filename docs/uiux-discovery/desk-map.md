Inspection snapshot from 1 October 2026. Descriptive details do not constrain redesign.

# Desk map and sections

## Main routes

| Route | Current purpose and user activity | Evidence |
|---|---|---|
| `/` | Main Jarvis desk: view activity and suggestions, switch conversations, talk/type through the baton, handle approvals, and work with drawings/quotes. | `frontend/src/app/page.tsx:4-9`; `core/desk/Desk.tsx:27-31` |
| `/masterdata` | Maintain Customers, Products, Machines, Materials, Suppliers, MHR floors, Outsource vendors, and Shop logs. | `frontend/src/app/masterdata/page.tsx:1-5`; `components/masterdata/MasterDataScreen.tsx` |
| `/canvas` | Open a separate canvas workspace for visual items and editing. | `frontend/src/app/canvas/page.tsx:3-15`; `components/canvas/CanvasShell.tsx` |
| `/lab/diarize` | Separate diarization lab tool, outside the scroll desk. | `frontend/src/app/lab/diarize/page.tsx`; `DiarizeLab.tsx` |

`JarvisRoot` wraps app routes. The inspected root mounted the substrate across routes (frontend/src/app/layout.tsx).

## Core desk sections

All sections are stacked on one page, each `100dvh`, with content inset for top/bottom chrome, left navigation, and right dock (`core/sections/SectionStack.tsx:24-48,90-95`). The registry sorts core and feature sections by `order` (`core/sections/registry.ts`).

### Monitor — order 100

Operational overview: activity stream, weather feature slot, suggested findings/tasks, voice or focus caption, and agent/orchestra visual. The central orb is a persistent substrate layer behind content. Activity appears only when nonempty; weather slot only when a weather line exists; suggestions are hidden during HITL (`core/sections/monitor/MonitorSection.tsx:26-63`).

### Casual — order 200

Conversation and general interaction: choose Ambient or an open note in `ConversationRail`, start a discussion, view weather and suggested tasks, read a document, or drop a drawing onto the central orb area (`core/sections/casual/CasualSection.tsx:67-125`). It includes the Orchestra visualization and a center voice/status line. Open conversations are capped at three expanded (`deskStore.ts`).

### Engineering — order 300

Shop work centered on drawing review and quote preparation. With an active task, users work in the drawing stage and quote sheet; otherwise the stacked task deck provides saved tasks. Deck cards can resume a task or cycle to another; an empty deck accepts a drawing (`core/sections/engineering/EngineeringSection.tsx`; `EngineeringDeck.tsx`). Quote components include `DrawingStage`, `QuoteSheet`, `QuoteBenchStepper`, and proof/freshness panels (`components/bench/`).

## Navigation and movement

- SectionNav is fixed at the left and uses the shared `goToSection` path; clicking is a user navigation (`core/chrome/SectionNav.tsx`; `core/desk/Desk.tsx:50,65`).
- Manual vertical scroll was available in the inspected build. PageUp/PageDown and Alt+1…9 navigated sections; Space activated the mic outside editable fields and typed normally in fields (`core/scroll/engine.ts`).
- The active section determines workspace; automatic context hints can move between sections subject to pin, modal, and recent-user-activity guards. Engineering leaves only for explicit requests (`core/desk/controller.ts`).
- The Engineering dock chip jumps to Engineering (`core/chrome/TaskDock.tsx:39-47`). See [shared UI](shared-ui.md) for other persistent chrome and approval movement.
