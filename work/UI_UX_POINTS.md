# UI / UX points

Living notes from conversation. Update when the owner wants a new look, layout, or interaction.  
React Bits: vendored in `frontend/src/components/react-bits/`.

---

## Current lock (2026-09-16)

### Shared

- Voice-first, keyboard-equal. Center is “who you’re talking to now.”
- HITL copy on this desk: **Authorize / Reject** (not Shall I). Overlay, not a new conversation.
- Workspace switcher: Casual | Monitor | Engineering + pin. Activity orb sits under the switcher (not on top of it).
- Casual mint accent `#7dffe0` stays on Casual/Engineering. Monitor uses warmer amber/gold tokens only under `[data-workspace="monitor"]`.
- Workspace morph is staged, never a hard cut: **presence** (orb ↔ eye ↔ bench, ~1.2s crossfade in the same center) → **theme** (interpolated `--bg/--accent`, after presence) → **chrome** (rails, weather, findings, agent suns last). Reduced-motion snaps.

### Casual (desk)

- Keep today’s layout: mint orb (`JarvisCore`), left Open notes, weather chip, suggested tasks, CommandBaton, tiny orchestra dots.
- Mail / tool **modals and boards** must leave legacy cyan `Widgets` / `hud/Hud` and use React Bits (SpotlightCard, GlareHover, etc.). Strip leaked HTML from suggested-task details.

### Monitor (watch)

- Warmer palette after the eye is in. **Evil Eye** is the presence, screen-centered, larger stock params (`eyeColor="#FF6F37"`, `intensity={1.5}`, `pupilSize={0.6}`, `irisWidth={0.25}`, `glowIntensity={0.3}`, `scale={0.8}`, `noiseScale={1}`, `pupilFollow={1}`, `flameSpeed={1}`, `backgroundColor="#120F17"`). Renders at **~55% internal resolution / 30fps** so the flame stays smooth on typical laptop GPUs; CSS upscales. Pauses when Monitor is off-screen.
- **No Aero Shards** on Monitor.
- **Agent suns sit still under the eye** — a quiet horizontal row, not a revolving orbit. Small amber discs, low glow, muted codes. Active a touch brighter; otherwise almost still. They fade in **last** with chrome.
- Hide: weather card, left conversation rail, bottom `[RES.01]` dots. No giant “Awaiting instruction” over the eye.
- Keep: CommandBaton (quieter), switcher, prefs, activity.
- Right column: same task data framed as **Findings** (agent work), not a casual to-do list. Findings fade in with chrome (last).

### Engineering (bench)

- Drawing is the hero. **No** Evil Eye / Aero Shards / casual orb under drawings.
- Proposed layout: large restyled `DrawingViewer` (~55%) + quote/machining stack (~40%). SpotlightCard / GlareHover; HITL overlay unchanged.
- Free hand on React Bits and other OSS UI; no parallel `/canvas` as the primary bench.

---

## Log

### 2026-09-16 — Overhaul direction

Owner wants a look-and-feel overhaul after mapping the current HUD. Agreed three visual workspaces (Casual keep-current, Monitor eye+shards+orbit, Engineering workbench). Eye mood: watchful, not horror. Suggested tasks on Monitor stay as lighter agent findings.

### 2026-09-16 — Monitor HUD revision

Owner: Evil Eye was cropped on both sides; 2D agent orbs felt boring (want a 3D orbit around the eye); Aero Shards must not be circular — upper 40% of the HUD, left-to-right stream. Shift the eye a bit lower and make it 10% smaller; orbs still orbit it.

### 2026-09-16 — Staged morph; shards off; eye recentered

Owner: Casual→Monitor must not hard-cut. Orb fades out and the eye appears **in its place first**; then the warmer HUD palette; shards were meant to arrive last — then **remove Aero Shards completely**. Bring the eye back to screen center, bigger, with the stock EvilEye params above. Every workspace transition should feel as smooth as possible.

### 2026-09-17 — Agent suns, no orbit

Owner: stop the revolving sub-agent orbs on Monitor. Keep the sun-agent orbs **below** the Evil Eye, more subtle and classy.

### 2026-09-17 — Eye GPU budget

Owner: reduce resolution (or similar) so the Evil Eye animation plays without lag on almost all laptops.
