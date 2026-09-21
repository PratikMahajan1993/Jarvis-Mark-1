# React Bits catalog (Jarvis)

| File | Role in Jarvis |
| ---- | -------------- |
| `SpotlightCard.tsx` | Cursor radial glow; `bodyClassName` for scroll/padding |
| `GlareHover.tsx` | Diagonal glare on hover (task cards) |
| `GradientText.tsx` | Animated gradient label text |
| `BlurText.tsx` | Word/letter reveal for voice line |
| `ClickSpark.tsx` | Click sparks on orch-root |
| `ElectricBorder.tsx` | Canvas border for HITL |
| `Particles.tsx` | WebGL dust (orb) |
| `LightRays.tsx` | WebGL rays (orb) |
| `AeroShards.tsx` | Vendored WebGPU shard field — **unused on Monitor** (owner removed) |
| `EvilEye.tsx` | Center watchful eye (ogl) — **Monitor workspace only**; unmount elsewhere |
| `Magnet.tsx` | Magnetic pull — use sparingly |
| `CardSwap.tsx` | Stack swap animation — optional; not primary desk |

## Consumers

- `OrchestratorShell.tsx` — ClickSpark, GradientText, SpotlightCard (board)
- `SuggestedTasksPanel.tsx` — GradientText, GlareHover, SpotlightCard
- `WeatherCard.tsx` — SpotlightCard + `shrink-0`
- `JarvisCore.tsx` — Particles / LightRays (casual + engineering)
- `monitor/MonitorDesk.tsx` — EvilEye + AgentOrbit (monitor only; unmount on workspace switch; no AeroShards)
- `HitlModal` / confirm UI — ElectricBorder where already wired
- `VoiceLine` — BlurText

When adding a new bit from reactbits.dev: port TS+Tailwind, add to this folder, wire one surface, document here.
