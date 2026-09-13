export type RailConversation = {
  id: string;
  title: string;
  time?: string;
  preview?: string;
  minimized?: boolean;
};

export function ConversationRail({
  items,
  dimmed = false,
  onToggle,
}: {
  items: RailConversation[];
  dimmed?: boolean;
  onToggle?: (id: string) => void;
}) {
  if (!items.length) return null;
  return (
    <div
      className={[
        "absolute right-12 top-12 z-[5] flex w-80 flex-col items-end gap-4 transition-opacity duration-[600ms]",
        dimmed ? "pointer-events-none opacity-10" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {items.map((item) => (
        <div
          key={item.id}
          className={[
            "w-full overflow-hidden rounded-lg border border-[color:var(--border)] bg-white/[0.03] backdrop-blur-[10px] transition",
            item.minimized ? "" : "",
          ].join(" ")}
        >
          <button
            type="button"
            className="flex w-full cursor-pointer items-center justify-between px-4 py-3 font-mono text-xs text-[color:var(--muted)]"
            onClick={() => onToggle?.(item.id)}
          >
            <span className="opacity-70">{item.time || ""}</span>
            <span className="uppercase tracking-[0.05em] transition hover:text-[color:var(--fg)]">{item.title}</span>
          </button>
          {!item.minimized && item.preview ? (
            <div className="px-4 pb-4 text-[0.85rem] leading-relaxed text-[color:var(--muted)]">
              {item.preview}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
