import type { ButtonHTMLAttributes, ReactNode } from "react";

export type Accent = "cyan" | "violet" | "magenta" | "amber" | "red" | "green" | "white";

const ACCENT_PANEL_CLASS: Record<Accent, string> = {
  cyan: "hud-accent-cyan",
  violet: "hud-accent-violet",
  magenta: "hud-accent-magenta",
  amber: "hud-accent-amber",
  red: "hud-accent-red",
  green: "hud-accent-green",
  white: "hud-accent-white",
};

export const ACCENT_TEXT_SOFT: Record<Accent, string> = {
  cyan: "text-cyan/70",
  violet: "text-violet/70",
  magenta: "text-magenta/70",
  amber: "text-amber/70",
  red: "text-red/70",
  green: "text-green/70",
  white: "text-white/50",
};

export const ACCENT_SOLID_BG: Record<Accent, string> = {
  cyan: "bg-cyan",
  violet: "bg-violet",
  magenta: "bg-magenta",
  amber: "bg-amber",
  red: "bg-red",
  green: "bg-green",
  white: "bg-white/40",
};

export const ACCENT_TEXT: Record<Accent, string> = {
  cyan: "text-cyan",
  violet: "text-violet",
  magenta: "text-magenta",
  amber: "text-amber",
  red: "text-red",
  green: "text-green",
  white: "text-white/70",
};

export const ACCENT_BORDER: Record<Accent, string> = {
  cyan: "border-cyan/40",
  violet: "border-violet/40",
  magenta: "border-magenta/40",
  amber: "border-amber/40",
  red: "border-red/40",
  green: "border-green/40",
  white: "border-white/15",
};

const ACCENT_STROKE: Record<Accent, string> = {
  cyan: "#3ee0d4",
  violet: "#a48cf2",
  magenta: "#f45fb0",
  amber: "#f5c16c",
  red: "#f2555c",
  green: "#43e0a0",
  white: "rgba(255,255,255,0.5)",
};

/* ---------------------------------------------------------------------- */
/* Panel — bracket-cornered HUD frame with an optional labelled header    */
/* ---------------------------------------------------------------------- */

export function Panel({
  accent = "cyan",
  title,
  eyebrow,
  right,
  className = "",
  bodyClassName,
  children,
}: {
  accent?: Accent;
  title?: ReactNode;
  eyebrow?: ReactNode;
  right?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children?: ReactNode;
}) {
  return (
    <div className={`hud-panel ${ACCENT_PANEL_CLASS[accent]} ${className}`}>
      {title || eyebrow || right ? (
        <div className="flex items-center justify-between gap-3 border-b border-white/5 px-4 py-2.5">
          <div className="min-w-0">
            {eyebrow ? (
              <p className={`font-mono text-[10px] uppercase tracking-[0.22em] ${ACCENT_TEXT_SOFT[accent]}`}>{eyebrow}</p>
            ) : null}
            {title ? <p className="truncate text-sm text-white/80">{title}</p> : null}
          </div>
          {right}
        </div>
      ) : null}
      <div className={bodyClassName ?? "p-4"}>{children}</div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* HudButton — outlined neon action button, four semantic variants        */
/* ---------------------------------------------------------------------- */

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  primary: "border-cyan/50 text-cyan bg-cyan/5 hover:border-cyan hover:bg-cyan/15 hover:shadow-glow-cyan",
  secondary: "border-violet/50 text-violet bg-violet/5 hover:border-violet hover:bg-violet/15 hover:shadow-glow-violet",
  danger: "border-red/50 text-red bg-red/5 hover:border-red hover:bg-red/15 hover:shadow-glow-red",
  ghost: "border-white/15 text-white/55 hover:border-white/30 hover:bg-white/5 hover:text-white",
};

export function HudButton({
  variant = "ghost",
  className = "",
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      type="button"
      {...rest}
      className={`rounded-sm border px-4 py-1.5 text-xs uppercase tracking-[0.14em] transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-30 ${BUTTON_VARIANT[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

/* ---------------------------------------------------------------------- */
/* Ring — circular SVG gauge / decorative scan ring                       */
/* ---------------------------------------------------------------------- */

export function Ring({
  size = 96,
  accent = "cyan",
  value,
  spinning = false,
  thickness = 3,
  children,
  className = "",
}: {
  size?: number;
  accent?: Accent;
  value?: number;
  spinning?: boolean;
  thickness?: number;
  children?: ReactNode;
  className?: string;
}) {
  const stroke = ACCENT_STROKE[accent];
  const radius = size / 2 - thickness * 2;
  const circumference = 2 * Math.PI * radius;
  const dash = value == null ? circumference * 0.7 : (Math.max(0, Math.min(100, value)) / 100) * circumference;
  const innerRadius = Math.max(0, radius - thickness * 2.5);

  return (
    <div className={`relative grid place-items-center ${className}`} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="absolute inset-0">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={thickness} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={stroke}
          strokeWidth={thickness}
          strokeDasharray={`${dash} ${circumference - dash}`}
          strokeLinecap="round"
          opacity={0.9}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          className={spinning ? "hud-ring-spin" : ""}
          style={{ transformOrigin: "50% 50%" }}
        />
        {innerRadius > 4 ? (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={innerRadius}
            fill="none"
            stroke="rgba(255,255,255,0.1)"
            strokeWidth={1}
            strokeDasharray="2 5"
            className={spinning ? "hud-ring-spin-slow" : ""}
            style={{ transformOrigin: "50% 50%" }}
          />
        ) : null}
      </svg>
      {children ? <div className="relative z-10">{children}</div> : null}
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* ProgressBar — slim gradient-capable bar                                */
/* ---------------------------------------------------------------------- */

export function ProgressBar({
  value,
  accent = "cyan",
  className = "",
}: {
  value: number;
  accent?: Accent;
  className?: string;
}) {
  return (
    <div className={`h-1 w-full overflow-hidden rounded-full bg-white/5 ${className}`}>
      <div
        className={`h-full rounded-full ${ACCENT_SOLID_BG[accent]} transition-all duration-300`}
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Alert — left-border tinted status banner                               */
/* ---------------------------------------------------------------------- */

export type Tone = "info" | "warn" | "error" | "success";

const TONE_BORDER: Record<Tone, string> = {
  info: "border-cyan/30 bg-cyan/5",
  warn: "border-amber/30 bg-amber/5",
  error: "border-red/30 bg-red/5",
  success: "border-green/30 bg-green/5",
};

const TONE_DOT: Record<Tone, string> = {
  info: "bg-cyan",
  warn: "bg-amber",
  error: "bg-red",
  success: "bg-green",
};

export function Alert({
  tone = "info",
  children,
  className = "",
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex items-center gap-2.5 border-l-2 px-3 py-2 ${TONE_BORDER[tone]} ${className}`}>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${TONE_DOT[tone]}`} />
      <span className="min-w-0 flex-1 text-sm text-white/80">{children}</span>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* StatusDot — small solid or pulsing indicator dot                       */
/* ---------------------------------------------------------------------- */

export function StatusDot({
  accent = "cyan",
  pulse = false,
  className = "",
}: {
  accent?: Accent;
  pulse?: boolean;
  className?: string;
}) {
  return <span className={`inline-block h-1.5 w-1.5 rounded-full ${ACCENT_SOLID_BG[accent]} ${pulse ? "orb-core" : ""} ${className}`} />;
}

/* ---------------------------------------------------------------------- */
/* StatCard — small bracket-cornered readout, for header strips           */
/* ---------------------------------------------------------------------- */

export function StatCard({
  label,
  value,
  accent = "cyan",
  className = "",
}: {
  label: ReactNode;
  value: ReactNode;
  accent?: Accent;
  className?: string;
}) {
  return (
    <div className={`hud-panel ${ACCENT_PANEL_CLASS[accent]} px-3 py-1.5 ${className}`}>
      <p className={`font-mono text-[9px] uppercase tracking-[0.2em] ${ACCENT_TEXT_SOFT[accent]}`}>{label}</p>
      <p className="mt-0.5 truncate font-display text-sm leading-tight text-white/85">{value}</p>
    </div>
  );
}
