import type { ThemeTokens } from "./defineSection";

export const MONITOR_THEME: ThemeTokens = {
  bg: "oklch(12% 0.022 55)",
  surface: "oklch(16% 0.028 52)",
  fg: "oklch(94% 0.018 75)",
  muted: "oklch(58% 0.04 62)",
  border: "oklch(24% 0.03 55)",
  accent: "oklch(72% 0.14 78)",
  gridOpacity: 0,
  vignetteOpacity: 0.9,
};

export const CASUAL_THEME: ThemeTokens = {
  bg: "oklch(10% 0.005 240)",
  surface: "oklch(14% 0.008 240)",
  fg: "oklch(96% 0.004 240)",
  muted: "oklch(62% 0.008 240)",
  border: "oklch(22% 0.01 240)",
  accent: "oklch(74% 0.15 160)",
  gridOpacity: 0,
  vignetteOpacity: 0.8,
};

export const ENGINEERING_THEME: ThemeTokens = {
  bg: "oklch(9% 0.004 240)",
  surface: "oklch(13% 0.005 240)",
  fg: "oklch(95% 0.003 240)",
  muted: "oklch(60% 0.006 240)",
  border: "oklch(20% 0.006 240)",
  accent: "oklch(74% 0.10 165)",
  mat: "oklch(16% 0.004 240)",
  gridOpacity: 0.35,
  vignetteOpacity: 0.5,
};

/** Theme tokens as the CSS custom properties the HUD components read. */
export function themeVars(theme: ThemeTokens): Record<string, string> {
  return {
    "--bg": theme.bg,
    "--surface": theme.surface,
    "--fg": theme.fg,
    "--muted": theme.muted,
    "--border": theme.border,
    "--accent": theme.accent,
    "--mat": theme.mat ?? "transparent",
  };
}
