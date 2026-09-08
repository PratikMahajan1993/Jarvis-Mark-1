"use client";

import { useCanvasActions, selectedOf, useCanvasState } from "@/lib/canvas/store";
import {
  COLOR_KEYS,
  NOTE_COLORS,
  STROKE_COLORS,
  type NoteColor,
  type StrokeColor,
} from "@/lib/canvas/types";
import { alignItems, distributeItems, type AlignEdge } from "@/lib/canvas/geometry";

export function Inspector() {
  const state = useCanvasState();
  const { dispatch } = useCanvasActions();
  const selected = selectedOf(state);
  if (!selected.length) return null;
  const primary = selected[0];
  const locked = selected.every((item) => item.locked);

  const patchAll = (patch: Record<string, unknown>) => {
    dispatch({ type: "checkpoint" });
    for (const item of selected) dispatch({ type: "updateItem", id: item.id, patch });
  };

  const applyAlign = (edge: AlignEdge) => {
    dispatch({ type: "checkpoint" });
    const moved = alignItems(selected, edge);
    const byId = new Map(moved.map((item) => [item.id, item]));
    dispatch({
      type: "replaceItems",
      items: state.board.items.map((item) => byId.get(item.id) ?? item),
    });
  };

  const applyDistribute = (axis: "x" | "y") => {
    dispatch({ type: "checkpoint" });
    const moved = distributeItems(selected, axis);
    const byId = new Map(moved.map((item) => [item.id, item]));
    dispatch({
      type: "replaceItems",
      items: state.board.items.map((item) => byId.get(item.id) ?? item),
    });
  };

  return (
    <div className="glass pointer-events-auto flex flex-col gap-2 rounded-2xl px-3 py-3">
      <p className="px-1 font-display text-[11px] tracking-[0.2em] text-white/30">
        {selected.length > 1 ? `${selected.length} SELECTED` : primary.kind.toUpperCase()}
      </p>
      {selected.length > 1 ? (
        <div className="flex flex-wrap gap-1">
          {(["left", "center", "right", "top", "middle", "bottom"] as AlignEdge[]).map((edge) => (
            <button
              key={edge}
              type="button"
              title={`Align ${edge}`}
              onClick={() => applyAlign(edge)}
              className="px-2 py-1 text-[11px] capitalize text-white/40 hover:text-cyan"
            >
              {edge[0]}
            </button>
          ))}
          <button
            type="button"
            title="Distribute horizontally"
            onClick={() => applyDistribute("x")}
            className="px-2 py-1 text-[11px] text-white/40 hover:text-cyan"
          >
            |||
          </button>
          <button
            type="button"
            title="Distribute vertically"
            onClick={() => applyDistribute("y")}
            className="px-2 py-1 text-[11px] text-white/40 hover:text-cyan"
          >
            ≡
          </button>
        </div>
      ) : null}

      {primary.kind === "note" ? (
        <SwatchRow
          colors={NOTE_COLORS}
          current={primary.color}
          onPick={(color) => patchAll({ color })}
        />
      ) : null}

      {primary.kind === "shape" || primary.kind === "stroke" || primary.kind === "text" ? (
        <SwatchRow
          colors={COLOR_KEYS}
          current={primary.kind === "shape" ? primary.stroke : primary.color}
          onPick={(color) => patchAll(primary.kind === "shape" ? { stroke: color } : { color })}
        />
      ) : null}

      {primary.kind === "shape" ? (
        <button
          type="button"
          onClick={() => patchAll({ fill: primary.fill === "none" ? primary.stroke : "none" })}
          className="px-2 py-1 text-left text-[11px] text-white/40 hover:text-cyan"
        >
          {primary.fill === "none" ? "Fill" : "No fill"}
        </button>
      ) : null}

      <div className="flex gap-1">
        <button
          type="button"
          onClick={() => {
            dispatch({ type: "checkpoint" });
            for (const item of selected) {
              dispatch({ type: "updateItem", id: item.id, patch: { locked: !locked } });
            }
          }}
          className="px-2 py-1 text-[11px] text-white/40 hover:text-cyan"
        >
          {locked ? "Unlock" : "Lock"}
        </button>
        <button
          type="button"
          onClick={() => dispatch({ type: "bringToFront", ids: selected.map((item) => item.id) })}
          className="px-2 py-1 text-[11px] text-white/40 hover:text-cyan"
        >
          Front
        </button>
        <button
          type="button"
          onClick={() => dispatch({ type: "sendToBack", ids: selected.map((item) => item.id) })}
          className="px-2 py-1 text-[11px] text-white/40 hover:text-cyan"
        >
          Back
        </button>
      </div>
    </div>
  );
}

function SwatchRow({
  colors,
  current,
  onPick,
}: {
  colors: readonly string[];
  current: string;
  onPick: (color: StrokeColor | NoteColor) => void;
}) {
  return (
    <div className="flex gap-1.5 px-1">
      {colors.map((color) => (
        <button
          key={color}
          type="button"
          title={color}
          onClick={() => onPick(color as StrokeColor)}
          className={`h-4 w-4 rounded-full border ${current === color ? "border-white" : "border-transparent"}`}
          style={{ background: STROKE_COLORS[color as StrokeColor] ?? STROKE_COLORS.amber }}
        />
      ))}
    </div>
  );
}
