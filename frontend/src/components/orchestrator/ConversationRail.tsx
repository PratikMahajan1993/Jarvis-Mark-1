"use client";

export type RailConversation = {
  id: string;
  sessionId: string;
  title: string;
  kindLabel?: string;
  time?: string;
  preview?: string;
  active?: boolean;
  waiting?: boolean;
};

function shortTitle(title: string) {
  const cleaned = (title || "").replace(/\s+/g, " ").trim();
  if (cleaned.length <= 42) return cleaned || "Untitled";
  return `${cleaned.slice(0, 40)}…`;
}

function RailOrbRow({
  title,
  subtitle,
  active = false,
  waiting = false,
  tone = "note",
  onClick,
}: {
  title: string;
  subtitle?: string;
  active?: boolean;
  waiting?: boolean;
  tone?: "ambient" | "note" | "job" | "drawing";
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "orch-rail-row group flex w-full items-center gap-3 rounded-full py-1.5 pr-2 text-left transition",
        active ? "orch-rail-row-active" : "hover:bg-white/[0.03]",
      ].join(" ")}
    >
      <span
        className={[
          "orch-rail-orb relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full border transition duration-300",
          `orch-rail-orb-${tone}`,
          active ? "orch-rail-orb-active" : "",
          waiting ? "orch-rail-orb-waiting" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        aria-hidden
      >
        <span className="orch-rail-orb-core absolute inset-[7px] rounded-full" />
        <span className="orch-rail-orb-ring pointer-events-none absolute -inset-1 rounded-full opacity-0 transition duration-300 group-hover:opacity-100" />
      </span>
      <span className="min-w-0 flex-1">
        <span
          className={[
            "block truncate text-[0.95rem] leading-tight tracking-[-0.01em] transition",
            active ? "text-[color:var(--fg)]" : "text-[color:var(--fg)]/80 group-hover:text-[color:var(--fg)]",
          ].join(" ")}
        >
          {title}
        </span>
        {subtitle ? (
          <span className="mt-0.5 block truncate font-mono text-[0.6rem] uppercase tracking-[0.1em] text-[color:var(--muted)]">
            {subtitle}
          </span>
        ) : null}
      </span>
    </button>
  );
}

export function ConversationRail({
  items,
  openCount = 0,
  maxOpen = 3,
  ambientActive,
  dimmed = false,
  hidden = false,
  onSelectAmbient,
  onSelect,
  onNewDiscussion,
}: {
  items: RailConversation[];
  openCount?: number;
  maxOpen?: number;
  ambientActive: boolean;
  dimmed?: boolean;
  hidden?: boolean;
  onSelectAmbient: () => void;
  onSelect: (id: string) => void;
  onNewDiscussion: () => void;
}) {
  if (hidden) return null;

  return (
    <div
      className={[
        "pointer-events-auto absolute left-4 top-24 z-[5] flex w-[min(280px,88vw)] flex-col gap-2 transition-opacity duration-[600ms]",
        dimmed ? "pointer-events-none opacity-15" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="mb-1 flex items-center justify-between gap-2 px-1">
        <div className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-[color:var(--accent)]">
          Open notes · {Math.min(openCount, maxOpen)}/{maxOpen}
        </div>
        <button
          type="button"
          className="font-mono text-[0.65rem] uppercase tracking-[0.08em] text-[color:var(--muted)] transition hover:text-[color:var(--accent)]"
          onClick={onNewDiscussion}
          title={
            openCount >= maxOpen
              ? `Opens a new note and parks the oldest (max ${maxOpen})`
              : "Start a named discussion"
          }
        >
          + New
        </button>
      </div>

      <RailOrbRow
        title="Everyday desk"
        subtitle="Quick asks"
        tone="ambient"
        active={ambientActive}
        onClick={onSelectAmbient}
      />

      {items.map((item) => {
        const kind = (item.kindLabel || "Note").toLowerCase();
        const tone =
          kind === "job" || kind === "workflow"
            ? "job"
            : kind === "drawing"
              ? "drawing"
              : "note";
        return (
          <RailOrbRow
            key={item.id}
            title={shortTitle(item.title)}
            subtitle={[item.kindLabel || "Note", item.time].filter(Boolean).join(" · ")}
            tone={tone}
            active={Boolean(item.active)}
            waiting={Boolean(item.waiting)}
            onClick={() => onSelect(item.id)}
          />
        );
      })}

      {!items.length ? (
        <p className="px-1 pt-2 font-mono text-[0.65rem] leading-relaxed text-[color:var(--muted)]/70">
          Up to {maxOpen} discussions and jobs stay open here.
        </p>
      ) : null}
    </div>
  );
}
