"use client";

import { useEffect, useRef, useState } from "react";
import { useCanvasActions } from "@/lib/canvas/store";
import type { NoteColor, NoteItem } from "@/lib/canvas/types";

const PALETTE: Record<NoteColor, { background: string; border: string; text: string }> = {
  amber: { background: "rgba(245, 193, 108, 0.16)", border: "rgba(245, 193, 108, 0.45)", text: "#f7dcae" },
  cyan: { background: "rgba(62, 224, 212, 0.14)", border: "rgba(62, 224, 212, 0.45)", text: "#bff3ee" },
  rose: { background: "rgba(240, 130, 160, 0.14)", border: "rgba(240, 130, 160, 0.45)", text: "#f6cdd9" },
  slate: { background: "rgba(148, 178, 196, 0.12)", border: "rgba(148, 178, 196, 0.4)", text: "#d7eef2" },
};

export function NoteCard({ item }: { item: NoteItem }) {
  const { dispatch } = useCanvasActions();
  const [editing, setEditing] = useState(!item.text);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const colors = PALETTE[item.color] ?? PALETTE.amber;

  useEffect(() => {
    if (!editing) return;
    textarea.current?.focus();
    textarea.current?.select();
  }, [editing]);

  return (
    <div
      className="h-full w-full overflow-hidden rounded-sm p-4 shadow-hud backdrop-blur-sm"
      style={{ background: colors.background, border: `1px solid ${colors.border}`, color: colors.text }}
      onDoubleClick={(event) => {
        event.stopPropagation();
        setEditing(true);
      }}
    >
      {editing ? (
        <textarea
          ref={textarea}
          data-canvas-interactive="true"
          value={item.text}
          onChange={(event) => dispatch({ type: "updateItem", id: item.id, patch: { text: event.target.value } })}
          onBlur={() => setEditing(false)}
          onKeyDown={(event) => {
            if (event.key === "Escape") setEditing(false);
            event.stopPropagation();
          }}
          className="h-full w-full resize-none bg-transparent text-[15px] leading-snug outline-none"
        />
      ) : (
        <p className="h-full w-full select-none whitespace-pre-wrap break-words text-[15px] leading-snug">
          {item.text || <span className="opacity-40">Double-click to write</span>}
        </p>
      )}
    </div>
  );
}
