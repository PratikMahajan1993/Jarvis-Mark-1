"use client";

import type { MouseEvent } from "react";
import { useCanvasActions, useCanvasState } from "@/lib/canvas/store";
import { itemBounds } from "@/lib/canvas/camera";
import type { CanvasCamera } from "@/lib/canvas/types";

const W = 168;
const H = 108;
const PAD = 10;

export function MiniMap({ viewport }: { viewport: { width: number; height: number } }) {
  const { board } = useCanvasState();
  const { dispatch } = useCanvasActions();
  const bounds = itemBounds(board.items);
  if (!bounds || viewport.width <= 0) return null;

  const worldW = Math.max(1, bounds.maxX - bounds.minX);
  const worldH = Math.max(1, bounds.maxY - bounds.minY);
  const scale = Math.min((W - PAD * 2) / worldW, (H - PAD * 2) / worldH);
  const ox = PAD + ((W - PAD * 2) - worldW * scale) / 2;
  const oy = PAD + ((H - PAD * 2) - worldH * scale) / 2;
  const camera = board.camera;

  const view = viewRect(camera, viewport, bounds, scale, ox, oy);

  const jump = (event: MouseEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    const worldX = bounds.minX + (px - ox) / scale;
    const worldY = bounds.minY + (py - oy) / scale;
    dispatch({
      type: "setCamera",
      camera: {
        z: camera.z,
        x: viewport.width / 2 - worldX * camera.z,
        y: viewport.height / 2 - worldY * camera.z,
      },
    });
  };

  return (
    <div
      className="glass pointer-events-auto relative overflow-hidden rounded-md"
      style={{ width: W, height: H }}
      onClick={jump}
      title="Minimap"
    >
      {board.items.map((item) => (
        <div
          key={item.id}
          className="absolute bg-cyan/35"
          style={{
            left: ox + (item.x - bounds.minX) * scale,
            top: oy + (item.y - bounds.minY) * scale,
            width: Math.max(2, item.w * scale),
            height: Math.max(2, item.h * scale),
          }}
        />
      ))}
      <div
        className="absolute border border-cyan/80"
        style={{ left: view.x, top: view.y, width: view.w, height: view.h }}
      />
    </div>
  );
}

function viewRect(
  camera: CanvasCamera,
  viewport: { width: number; height: number },
  bounds: { minX: number; minY: number; maxX: number; maxY: number },
  scale: number,
  ox: number,
  oy: number,
) {
  const x = (-camera.x) / camera.z;
  const y = (-camera.y) / camera.z;
  const w = viewport.width / camera.z;
  const h = viewport.height / camera.z;
  return {
    x: ox + (x - bounds.minX) * scale,
    y: oy + (y - bounds.minY) * scale,
    w: w * scale,
    h: h * scale,
  };
}
