"use client";

import type { CanvasTool } from "@/lib/canvas/types";

const TOOLS: Array<{ id: CanvasTool; label: string; title: string; key: string }> = [
  { id: "select", label: "V", title: "Select (V)", key: "V" },
  { id: "pan", label: "H", title: "Hand (H)", key: "H" },
  { id: "note", label: "N", title: "Note (N)", key: "N" },
  { id: "text", label: "T", title: "Text (T)", key: "T" },
  { id: "ink", label: "P", title: "Pen (P)", key: "P" },
  { id: "rect", label: "□", title: "Rectangle", key: "" },
  { id: "ellipse", label: "○", title: "Ellipse (O)", key: "O" },
  { id: "diamond", label: "◇", title: "Diamond", key: "" },
  { id: "line", label: "/", title: "Line (L)", key: "L" },
  { id: "arrow", label: "→", title: "Arrow (A)", key: "A" },
  { id: "region", label: "R", title: "Region crop (R)", key: "R" },
];

export function ToolRail({
  tool,
  onTool,
}: {
  tool: CanvasTool;
  onTool: (tool: CanvasTool) => void;
}) {
  return (
    <div className="glass pointer-events-auto flex flex-col items-center gap-0.5 rounded-full px-1.5 py-2">
      {TOOLS.map((entry) => (
        <button
          key={entry.id}
          type="button"
          title={entry.title}
          onClick={() => onTool(tool === entry.id && entry.id !== "select" ? "select" : entry.id)}
          className={`h-8 w-8 rounded-full font-display text-sm transition-colors ${
            tool === entry.id ? "bg-cyan/15 text-cyan" : "text-white/40 hover:text-cyan"
          }`}
        >
          {entry.label}
        </button>
      ))}
    </div>
  );
}
