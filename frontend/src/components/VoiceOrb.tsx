type Mood = "idle" | "listen" | "think";

type Props = {
  mood: Mood;
  onClick: () => void;
};

export function VoiceOrb({ mood, onClick }: Props) {
  const glow =
    mood === "listen" ? "bg-amber shadow-[0_0_50px_rgba(245,193,108,0.45)]" :
    mood === "think" ? "bg-cyan shadow-[0_0_48px_rgba(62,224,212,0.4)]" :
    "bg-cyan/80 shadow-[0_0_36px_rgba(62,224,212,0.28)]";

  return (
    <button
      type="button"
      onClick={onClick}
      className="relative grid h-28 w-28 place-items-center rounded-full"
      aria-label={mood === "listen" ? "Stop listening" : "Speak to Jarvis"}
    >
      {mood !== "idle" ? <span className="orb-think absolute inset-0 rounded-full border border-white/25" /> : null}
      <span className={`orb-core h-10 w-10 rounded-full ${glow}`} />
    </button>
  );
}
