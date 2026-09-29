/** First paint of X1. No client hooks — the server sends this before JavaScript runs. */

export function LandingReadout({ line, progress }: { line: string; progress: number }) {
  const width = `${Math.max(0, Math.min(1, progress)) * 100}%`;
  return (
    <>
      <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-[color:var(--muted)]">{line}</p>
      <div className="mt-3 h-px w-56 bg-[color:var(--border)]">
        <div
          className="h-px bg-[color:var(--accent)] transition-[width] duration-300"
          style={{ width }}
        />
      </div>
    </>
  );
}

/** CSS-only landing frame. The client overlay removes this node once it mounts. */
export function LandingFirstFrame() {
  return (
    <div
      className="fixed inset-0 z-landing flex flex-col items-center justify-end pb-[12vh]"
      data-landing-static=""
      role="status"
    >
      <LandingReadout line="Waking substrate" progress={0} />
    </div>
  );
}
