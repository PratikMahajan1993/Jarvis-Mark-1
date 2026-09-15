---
name: jarvis-react-bits
description: >
  Implement or fix React Bits accents on the Jarvis Orchestrator HUD. Use when
  adding SpotlightCard, GlareHover, GradientText, BlurText, ClickSpark,
  ElectricBorder, Particles, LightRays, Magnet, CardSwap; when fixing spotlight
  scroll, weather shrink, or suggested-task card expand/collapse.
paths: frontend/**/*.{tsx,ts,css}
---

# Jarvis React Bits

## Rules of engagement

1. Copy/adapt from `frontend/src/components/react-bits/` — do not paste a full marketing demo page.
2. Keep `"use client"` on every bit.
3. Palette: accent `#7dffe0` / `rgba(125, 255, 224, …)`; dark glass `bg-black/40–50`, `backdrop-blur-md`.
4. Accents only: one job per surface.

## SpotlightCard + scroll (required pattern)

```tsx
<SpotlightCard
  className="rounded-2xl border … bg-black/35 backdrop-blur-md"
  bodyClassName="max-h-[38vh] overflow-y-auto p-4"
>
  {children}
</SpotlightCard>
```

- Glow stays on the outer card; **never** put `overflow-y-auto` + max-height on the outer className.
- In flex sidebars, pin non-scrolling chips: `className="shrink-0 …"`.

## Suggested tasks

- Idle: title + description only (`SuggestedTasksPanel`).
- Hover/focus: kind, dismiss, actions.
- Wrap cards with `GlareHover` + `SpotlightCard`; panel header via `GradientText`.
- Weather: separate `WeatherCard`, not inside the scroll list.

## WebGL

- `Particles` / `LightRays` only behind the orb in `JarvisCore`, loaded with `dynamic(..., { ssr: false })`.
- **Headless Chrome needs one extra flag.** Without it, `Particles.tsx` throws `unable to create webgl context` and the HUD shows Next's error overlay instead of the desk — this happens on cloud VMs with no GPU just as easily as anywhere else. Fix: launch with `--enable-unsafe-swiftshader` (e.g. `google-chrome --headless=new --enable-unsafe-swiftshader --window-size=1440,900 --screenshot=out.png http://127.0.0.1:3000`, or pass it in `args` when launching via `puppeteer-core`/`playwright` with `executablePath` pointed at the system Chrome). Confirmed working on a cloud VM with no GPU — this is a one-line launch-flag fix, not evidence the HUD needs the desk machine.

## Checklist before done

- [ ] No Magnet on CommandBaton / flex-centering parents
- [ ] No ElectricBorder except HITL
- [ ] Browser check: scroll + spotlight + weather text fully visible
- [ ] Match existing component props (see [catalog.md](catalog.md))
