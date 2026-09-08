"use client";

import { useEffect, useRef, useState } from "react";
import { useCanvasActions } from "@/lib/canvas/store";
import { STROKE_COLORS, type TextItem } from "@/lib/canvas/types";

export function TextCard({ item }: { item: TextItem }) {
  const { dispatch } = useCanvasActions();
  const [editing, setEditing] = useState(!item.text);
  const field = useRef<HTMLTextAreaElement>(null);
  const color = STROKE_COLORS[item.color] ?? STROKE_COLORS.white;

  useEffect(() => {
    if (!editing) return;
    field.current?.focus();
    field.current?.select();
  }, [editing]);

  return (
    <div
      className="h-full w-full"
      onDoubleClick={(event) => {
        event.stopPropagation();
        setEditing(true);
      }}
    >
      {editing ? (
        <textarea
          ref={field}
          data-canvas-interactive="true"
          value={item.text}
          onChange={(event) => dispatch({ type: "updateItem", id: item.id, patch: { text: event.target.value } })}
          onBlur={() => setEditing(false)}
          onKeyDown={(event) => {
            if (event.key === "Escape") setEditing(false);
            event.stopPropagation();
          }}
          className="h-full w-full resize-none bg-transparent font-display leading-tight outline-none"
          style={{ color, fontSize: item.size || 28 }}
        />
      ) : (
        <p
          className="h-full w-full select-none whitespace-pre-wrap break-words font-display leading-tight"
          style={{ color, fontSize: item.size || 28 }}
        >
          {item.text || <span className="opacity-40">Text</span>}
        </p>
      )}
    </div>
  );
}
