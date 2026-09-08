"use client";

import { STROKE_COLORS, type ShapeItem } from "@/lib/canvas/types";

export function ShapeCard({ item }: { item: ShapeItem }) {
  const stroke = STROKE_COLORS[item.stroke] ?? STROKE_COLORS.cyan;
  const fill =
    item.fill === "none" ? "none" : `${STROKE_COLORS[item.fill] ?? STROKE_COLORS.cyan}33`;
  const weight = Math.max(1, item.weight || 2);
  const inset = weight / 2;
  return (
    <svg
      className="pointer-events-none h-full w-full overflow-visible"
      viewBox={`0 0 ${item.w} ${item.h}`}
      preserveAspectRatio="none"
    >
      {item.shape === "ellipse" ? (
        <ellipse
          cx={item.w / 2}
          cy={item.h / 2}
          rx={Math.max(1, item.w / 2 - inset)}
          ry={Math.max(1, item.h / 2 - inset)}
          fill={fill}
          stroke={stroke}
          strokeWidth={weight}
        />
      ) : item.shape === "diamond" ? (
        <polygon
          points={`${item.w / 2},${inset} ${item.w - inset},${item.h / 2} ${item.w / 2},${item.h - inset} ${inset},${item.h / 2}`}
          fill={fill}
          stroke={stroke}
          strokeWidth={weight}
        />
      ) : (
        <rect
          x={inset}
          y={inset}
          width={Math.max(1, item.w - weight)}
          height={Math.max(1, item.h - weight)}
          fill={fill}
          stroke={stroke}
          strokeWidth={weight}
        />
      )}
    </svg>
  );
}
