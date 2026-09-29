# React Bits catalog (Jarvis)

| File | Role in Jarvis |
| ---- | -------------- |
| `SpotlightCard.tsx` | Cursor radial glow; `bodyClassName` for scroll/padding |
| `GlareHover.tsx` | Diagonal glare on hover (task cards) |
| `GradientText.tsx` | Animated gradient label text |
| `BlurText.tsx` | Word/letter reveal for voice line |
| `ClickSpark.tsx` | Click sparks on orch-root |
| `ElectricBorder.tsx` | Canvas border for HITL |
| `Particles.tsx` | Vendored WebGL dust — **not mounted** (the orb is the substrate swarm) |
| `LightRays.tsx` | Vendored WebGL rays — **not mounted** |
| `AeroShards.tsx` | Vendored WebGPU shard field — **not mounted** |
| `Magnet.tsx` | Magnetic pull on `Orchestra.tsx` — use sparingly |
| `CardSwap.tsx` | Vendored stack swap — **not mounted** |
| `ClickSpark.tsx` | Vendored — **not mounted** |
| `BlurText.tsx` | Vendored — **not mounted** |

`EvilEye` and `JarvisCore` are removed. Do not add them back.

## Consumers

- `SuggestedTasksPanel.tsx` — GradientText, GlareHover, SpotlightCard
- `features/weather/WeatherCard.tsx` and `components/orchestrator/WeatherCard.tsx` — SpotlightCard + `shrink-0`
- `CasualSection.tsx` — SpotlightCard around `SceneBoard` (`bodyClassName` scroll)
- `HitlModal.tsx`, `ConnectGoogleModal.tsx` — ElectricBorder
- `CommandBaton.tsx` — GlareHover
- `StatusCluster.tsx` — GradientText
- `Orchestra.tsx` — Magnet
- Engineering cards (`VarianceCard`, `FactConfirmChips`, `VisionBenchQueue`, `ToolChangeField`, `CustomerVisionConsent`) and `PreferencesPanel` — GradientText + SpotlightCard

When adding a new bit from reactbits.dev: port TS+Tailwind, add to this folder, wire one surface, document here. Do not open a second WebGL context.
