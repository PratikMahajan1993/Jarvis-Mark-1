Inspection snapshot from 1 October 2026. Timing, placement, and motion describe that inspection, not design requirements.

# Shared UI and interaction states

## Persistent desk chrome

`Desk` assembles backdrop, section stack, decor, then fixed chrome and modal layers (`frontend/src/core/desk/Desk.tsx:44-90`).

- **StatusCluster** (top): status/connectivity and preference access (`core/chrome/StatusCluster.tsx`). Preferences include feature flags and Google connections (`components/orchestrator/PreferencesPanel.tsx`; `ConnectGoogleModal.tsx`).
- **SectionNav** (left): section labels/progress and direct user navigation (`core/chrome/SectionNav.tsx`).
- **TaskDock** (right): current implementation shows a single expandable Engineering tasks chip with a count (`core/chrome/TaskDock.tsx:9-20,22-59`).
- **BatonDock / CommandBaton** (bottom): text entry, submit, and mic. It stays interactive while dimmed during scrolling; focus/typing restores emphasis. A two-second debounce plus section change/pagehide saves text (`core/chrome/BatonDock.tsx:18-24,55-72,112-135`).
- **ToastLayer / Notifications**: transient notices and queued approval access (`core/chrome/ToastLayer.tsx`; `Notifications.tsx`).

## Turn and voice states

Turn state is distinct from active workspace: idle, listening, thinking, speaking, awaiting HITL, and executing are represented by the turn store/FSM (`core/stores/turnStore.ts`; `lib/orchestratorFsm.ts`). The baton shows transmitting, progress, errors, and a Cancel control while thinking (`BatonDock.tsx:85-110`). Voice transcript/status lines appear in Monitor and Casual (`MonitorSection.tsx:23-24`; `CasualSection.tsx:22-36`). Input handling is in `core/scroll/engine.ts`; speech playback is in `lib/voice.ts`.

## Approval flow (HITL)

`HitlModal` presents impact/consequence details, Reject, Authorize, and Later; it focuses Authorize on open and disables decision buttons while busy (`components/orchestrator/HitlModal.tsx:28-35,59-109`). Later parks the approval and allows work to resume; resuming restores the full modal. Parking is not authorization; resuming returns to the full decision surface.

## Important transitions

- Landing runs on full load, minimum 1.4 s (0.6 s on same-tab refresh), maximum 4 s, then fades over 600 ms. Hermes status is display-only and never blocks readiness (`core/landing/Landing.tsx:13-18,30-46,70-99`).
- Scrolling dims the baton; focus or typing restores it. Reduced-motion preference affects motion behavior (`BatonDock.tsx:15-16`; `Desk.tsx:35-42`).
- Section content can mount lazily; errors are isolated by a boundary with a retry tile (`core/sections/SectionStack.tsx:24-48`; `core/boundary/FeatureBoundary.tsx`).
- Engineering draft autosave happens during editing, leaving the section, Save for later, and pagehide (`core/desk/autosave.ts`).
- Deck resumes a task into the stage; arrow keys and horizontal trackpad movement cycle cards, while vertical wheel movement scrolls the page (`core/sections/engineering/deckWheel.ts`; `../CURRENT.md`).

## Related

See [desk map](desk-map.md) for inspected section contents and [observations and questions](constraints-and-questions.md) for discovery findings.
