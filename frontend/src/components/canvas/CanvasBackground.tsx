import type { CanvasCamera } from "@/lib/canvas/types";

const BASE_SPACING = 32;
const MIN_SCREEN_SPACING = 14;

/** Steps the grid up in powers of four so dots never crowd together when zoomed out. */
function gridSpacing(zoom: number): number {
  let spacing = BASE_SPACING;
  while (spacing * zoom < MIN_SCREEN_SPACING) spacing *= 4;
  while (spacing * zoom > MIN_SCREEN_SPACING * 8) spacing /= 4;
  return spacing;
}

export function CanvasBackground({ camera }: { camera: CanvasCamera }) {
  const size = gridSpacing(camera.z) * camera.z;
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0"
      style={{
        backgroundImage: "radial-gradient(circle, rgba(62, 224, 212, 0.16) 1px, transparent 1px)",
        backgroundSize: `${size}px ${size}px`,
        backgroundPosition: `${camera.x}px ${camera.y}px`,
      }}
    />
  );
}
