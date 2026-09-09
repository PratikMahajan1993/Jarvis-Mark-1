"use client";

export type MenuAction = {
  label: string;
  shortcut?: string;
  disabled?: boolean;
  run: () => void;
};

export function ContextMenu({
  x,
  y,
  actions,
  onClose,
}: {
  x: number;
  y: number;
  actions: MenuAction[];
  onClose: () => void;
}) {
  return (
    <div
      className="glass pointer-events-auto absolute z-50 min-w-[11rem] rounded-md py-1"
      style={{ left: x, top: y }}
      data-canvas-interactive="true"
      onPointerDown={(event) => event.stopPropagation()}
    >
      {actions.map((action) => (
        <button
          key={action.label}
          type="button"
          disabled={action.disabled}
          onClick={() => {
            action.run();
            onClose();
          }}
          className="flex w-full items-center justify-between gap-6 px-3 py-1.5 text-left text-sm text-white/55 hover:text-cyan disabled:opacity-30"
        >
          <span>{action.label}</span>
          {action.shortcut ? <span className="font-display text-[11px] tracking-wide text-white/25">{action.shortcut}</span> : null}
        </button>
      ))}
    </div>
  );
}

const ROWS: Array<{ keys: string; label: string }> = [
  { keys: "V / H", label: "Select / Hand" },
  { keys: "N T P", label: "Note, Text, Pen" },
  { keys: "O L A R", label: "Oval, Line, Arrow, Region" },
  { keys: "Space", label: "Hold to pan" },
  { keys: "⇧ click / drag", label: "Add to selection" },
  { keys: "⌘ C V D", label: "Copy, paste, duplicate" },
  { keys: "⌘ Z / ⇧Z", label: "Undo / redo" },
  { keys: "⌘ A", label: "Select all" },
  { keys: "⌘ G", label: "Group / ungroup" },
  { keys: "⌘ L", label: "Lock" },
  { keys: "⌘ ] [", label: "Front / back" },
  { keys: "Arrows", label: "Nudge · ⇧ for 10px" },
  { keys: "G", label: "Snap to grid" },
  { keys: "0 / 1 / 2", label: "100% · fit · selection" },
  { keys: "⌘ E", label: "Export PNG" },
  { keys: "Alt-drag", label: "Duplicate" },
  { keys: "?", label: "This list" },
];

export function ShortcutHelp({ onClose }: { onClose: () => void }) {
  return (
    <div className="pointer-events-auto absolute inset-0 z-40 grid place-items-center bg-black/40" onClick={onClose}>
      <div
        className="glass max-h-[80vh] w-[22rem] overflow-auto rounded-lg px-5 py-4"
        onClick={(event) => event.stopPropagation()}
      >
        <p className="mb-3 font-display text-sm tracking-[0.25em] text-cyan/70">KEYS</p>
        <div className="flex flex-col gap-1.5">
          {ROWS.map((row) => (
            <div key={row.keys} className="flex items-baseline justify-between gap-4 text-sm">
              <span className="font-display tracking-wide text-white/45">{row.keys}</span>
              <span className="text-white/35">{row.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
