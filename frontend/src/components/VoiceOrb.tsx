import { Ring, type Accent } from "./hud/Hud";

type Mood = "idle" | "listen" | "think";

type Props = {
  mood: Mood;
  onClick: () => void;
};

const MOOD_ACCENT: Record<Mood, Accent> = {
  idle: "cyan",
  listen: "amber",
  think: "violet",
};

const MOOD_GLOW: Record<Mood, string> = {
  idle: "bg-cyan/80 shadow-[0_0_36px_rgba(62,224,212,0.28)]",
  listen: "bg-amber shadow-[0_0_50px_rgba(245,193,108,0.45)]",
  think: "bg-violet shadow-[0_0_48px_rgba(164,140,242,0.4)]",
};

export function VoiceOrb({ mood, onClick }: Props) {
  const accent = MOOD_ACCENT[mood];

  return (
    <button
      type="button"
      onClick={onClick}
      className="relative grid h-28 w-28 place-items-center rounded-full"
      aria-label={mood === "listen" ? "Stop listening" : "Speak to Jarvis"}
    >
      <Ring size={112} accent={accent} thickness={1.5} spinning={mood !== "idle"} className="absolute inset-0" />
      {mood !== "idle" ? <span className="orb-think absolute inset-0 rounded-full border border-white/25" /> : null}
      <span className={`orb-core relative h-10 w-10 rounded-full ${MOOD_GLOW[mood]}`} />
    </button>
  );
}
