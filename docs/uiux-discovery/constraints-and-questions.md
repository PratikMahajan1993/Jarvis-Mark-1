# Observations and questions

Inspection snapshot from 1 October 2026. These notes are not a gate. Design and implementation may proceed without answering them.

## Functional requirements

Preserve capability bindings, drafts, session identity, approval decisions, and provenance. Label demo data and present loading/errors honestly. Keep controls usable with keyboard, touch, supported viewports, and reduced motion. Layout and rendering remain design choices.

## Inspected behavior

The app used Monitor, Casual, and Engineering, a root-mounted particle renderer, landing feedback, and fixed controls. These are implementation observations, not obligations.

Parked approvals were reached through Notifications; TaskDock provided an Engineering shortcut. Confirm current behavior in the app. Scroll and renderer implementation is changing; this report is a snapshot.

## Observations (interpretations, not facts)

- The center orb, voice line, drag/drop target, and adjacent cards share the Casual viewport. The drop target is an invisible central overlay, so the affordance may be hard to discover (`CasualSection.tsx:69-94`).
- Monitor and Casual both show suggestions, while Monitor labels them “findings” and Casual “suggested”; users may not know whether these are the same queue or different concepts (`MonitorSection.tsx:38-46`; `CasualSection.tsx:134-142`).
- Dock terminology may feel inconsistent: “engineering tasks” is a section jump, while parked approvals are handled through Notifications. The current code structure makes these separate pathways.
- The desk’s persistent chrome and orb compete for visual attention with dense Engineering quote/drawing controls; this is a hypothesis to validate with the owner and users, not a usability finding.
- Separate `/canvas` and `/masterdata` routes are not represented as sections in SectionNav; their discoverability from the desk should be checked in the running UI.

## Open questions

1. Who are the main user roles and which tasks should dominate their first visit: monitoring, conversation, or quote work?
2. Should `/canvas` and `/masterdata` be discoverable from the desk chrome, and who uses each regularly?
3. Are Monitor and Casual suggestions intentionally distinct, or should they read as one task system?
4. Where should users expect parked approvals to live: a dedicated queue, notification surface, or dock? Should the current split remain?
5. Which navigation and scroll feel best serve the owner?
6. Which visual elements are essential identity (particle formulas, dark palette, typography, motion), and which are open to change?
7. What screen sizes, input modes, accessibility needs, and reduced-motion expectations should anchor the redesign?
8. Which behaviors must remain visible during live work: turn progress, source/proof status, approval impact, and autosave confirmation?

## Related

Start at [README](README.md); use [desk map](desk-map.md) and [shared UI](shared-ui.md) for implementation context.
