"use client";

import { STROKE_COLORS, type StrokeItem } from "@/lib/canvas/types";

export function StrokeCard({ item }: { item: StrokeItem }) {
  const color = STROKE_COLORS[item.color] ?? STROKE_COLORS.cyan;
  const weight = Math.max(1, item.weight || 2);
  const d = item.points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");
  const last = item.points[item.points.length - 1];
  const prev = item.points[item.points.length - 2];
  const angle =
    last && prev ? (Math.atan2(last.y - prev.y, last.x - prev.x) * 180) / Math.PI : 0;

  return (
    <svg className="pointer-events-none h-full w-full overflow-visible" width={item.w} height={item.h}>
      <path
        d={d || "M 0 0"}
        fill="none"
        stroke={color}
        strokeWidth={weight}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {item.mode === "arrow" && last ? (
        <polygon
          points="0,-5 12,0 0,5"
          fill={color}
          transform={`translate(${last.x}, ${last.y}) rotate(${angle})`}
        />
      ) : null}
    </svg>
  );
}
